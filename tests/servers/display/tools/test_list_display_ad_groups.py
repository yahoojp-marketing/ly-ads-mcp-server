from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.client import AdGroupServiceUserStatus
from ly_ads_mcp.servers.display.tools import list_display_ad_groups as list_display_ad_groups_tool
from ly_ads_mcp.servers.display.tools.list_display_ad_groups import (
    DisplayAdGroupBiddingValueCpcRange,
    DisplayAdGroupDateRange,
    ListDisplayAdGroupsRequest,
)


class FakeAdGroup:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeAdGroupValue:
    def __init__(self, ad_group=None):
        self.ad_group = ad_group


async def test_list_display_ad_groups_maps_request_to_selector(monkeypatch, patch_to_thread):
    captured = {}

    class FakeAdGroupServiceApi:
        def __init__(self, client):
            pass

        def ad_group_service_get_post(self, x_z_base_account_id, ad_group_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = ad_group_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupValue(
                            ad_group=FakeAdGroup(
                                {
                                    "accountId": 456,
                                    "campaignId": 789,
                                    "adGroupId": 987,
                                    "adGroupName": "Ad Group A",
                                    "device": ["SMARTPHONE"],
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_display_ad_groups_tool, "AdGroupServiceApi", FakeAdGroupServiceApi)
    result = await list_display_ad_groups_tool.list_display_ad_groups(
        FakeHandlers(),
        ListDisplayAdGroupsRequest(
            base_account_id=123,
            account_id=456,
            ad_group_ids=[987],
            campaign_ids=[789],
            contains_label=True,
            feed_set_ids=[11],
            label_ids=[12],
            user_statuses=[AdGroupServiceUserStatus.ACTIVE],
            created_date_range=DisplayAdGroupDateRange(start_date="20260801"),
            updated_date_range=DisplayAdGroupDateRange(end_date="20260815"),
            bidding_value_cpc_range=DisplayAdGroupBiddingValueCpcRange(min=100, max=2000),
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.ad_group_ids == [987]
    assert selector.campaign_ids == [789]
    assert selector.contains_label is True
    assert selector.feed_set_ids == [11]
    assert selector.label_ids == [12]
    assert [status.value for status in selector.user_statuses] == ["ACTIVE"]
    assert selector.created_date_range.start_date == "20260801"
    assert selector.updated_date_range.end_date == "20260815"
    assert selector.bidding_value_cpc_range.min == 100
    assert selector.bidding_value_cpc_range.max == 2000
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 789
    assert result.items[0].ad_group_id == 987
    assert result.items[0].device == ["SMARTPHONE"]


async def test_list_display_ad_groups_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
    captured = []

    class FakeAdGroupServiceApi:
        def __init__(self, client):
            pass

        def ad_group_service_get_post(self, x_z_base_account_id, ad_group_service_selector):
            captured.append((x_z_base_account_id, ad_group_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupValue(ad_group=FakeAdGroup({"adGroupId": ad_group_id}))
                        for ad_group_id in range(ad_group_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_display_ad_groups_tool, "AdGroupServiceApi", FakeAdGroupServiceApi)
    handlers = FakeHandlers()
    first = await list_display_ad_groups_tool.list_display_ad_groups(
        handlers,
        ListDisplayAdGroupsRequest(base_account_id=123, account_id=456),
    )
    continued = await list_display_ad_groups_tool.list_display_ad_groups(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_display_ad_groups_rejects_value_with_no_ad_group(monkeypatch, patch_to_thread):
    class FakeAdGroupServiceApi:
        def __init__(self, client):
            pass

        def ad_group_service_get_post(self, x_z_base_account_id, ad_group_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeAdGroupValue(ad_group=None)], total=1))

    monkeypatch.setattr(list_display_ad_groups_tool, "AdGroupServiceApi", FakeAdGroupServiceApi)

    with pytest.raises(ToolError, match="ad group entry without ad group data"):
        await list_display_ad_groups_tool.list_display_ad_groups(
            FakeHandlers(),
            ListDisplayAdGroupsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize(
    "date_range",
    [
        {},
        {"startDate": "20260815", "endDate": "20260801"},
        {"startDate": "2026-08-01"},
    ],
)
def test_display_ad_group_date_range_rejects_invalid_ranges(date_range):
    with pytest.raises(ValidationError):
        DisplayAdGroupDateRange.model_validate(date_range)


@pytest.mark.parametrize(
    "bidding_value_cpc_range",
    [
        {},
        {"min": 2000, "max": 100},
    ],
)
def test_display_ad_group_bidding_value_cpc_range_rejects_invalid_ranges(bidding_value_cpc_range):
    with pytest.raises(ValidationError):
        DisplayAdGroupBiddingValueCpcRange.model_validate(bidding_value_cpc_range)


@pytest.mark.parametrize(
    "field_name",
    ["adGroupIds", "campaignIds", "feedSetIds", "labelIds"],
)
def test_list_display_ad_groups_rejects_more_than_default_page_size_ids(field_name):
    with pytest.raises(ValidationError):
        ListDisplayAdGroupsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field_name: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
