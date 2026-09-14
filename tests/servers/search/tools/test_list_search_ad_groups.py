from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.search.client import AdGroupServiceUserStatus
from ly_ads_mcp.servers.search.tools import list_search_ad_groups as list_search_ad_groups_tool
from ly_ads_mcp.servers.search.tools.list_search_ad_groups import (
    ListSearchAdGroupsRequest,
    SearchAdGroupBiddingKeywordCpcRange,
    SearchAdGroupDateRange,
)


class FakeAdGroup:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeAdGroupValue:
    def __init__(self, ad_group=None):
        self.ad_group = ad_group


async def test_list_search_ad_groups_maps_request_to_selector(monkeypatch, patch_to_thread):
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
                                    "adGroupId": 789,
                                    "adGroupName": "Ad Group A",
                                    "campaignId": 321,
                                    "biddingStrategyConfiguration": {"biddingScheme": {"type": "CPC"}},
                                    "disableAiKeywordExpansion": "FALSE",
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_search_ad_groups_tool, "AdGroupServiceApi", FakeAdGroupServiceApi)
    result = await list_search_ad_groups_tool.list_search_ad_groups(
        FakeHandlers(),
        ListSearchAdGroupsRequest(
            base_account_id=123,
            account_id=456,
            ad_group_ids=[789],
            portfolio_bidding_ids=[11],
            campaign_ids=[321],
            contains_label=True,
            label_ids=[13],
            user_statuses=[AdGroupServiceUserStatus.ACTIVE],
            created_date_range=SearchAdGroupDateRange(start_date="20260801"),
            updated_date_range=SearchAdGroupDateRange(end_date="20260815"),
            bidding_keyword_cpc_range=SearchAdGroupBiddingKeywordCpcRange(min=100, max=2000),
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.ad_group_ids == [789]
    assert selector.portfolio_bidding_ids == [11]
    assert selector.campaign_ids == [321]
    assert selector.contains_label is True
    assert selector.label_ids == [13]
    assert [status.value for status in selector.user_statuses] == ["ACTIVE"]
    assert selector.created_date_range.start_date == "20260801"
    assert selector.updated_date_range.end_date == "20260815"
    assert selector.bidding_keyword_cpc_range.min == 100
    assert selector.bidding_keyword_cpc_range.max == 2000
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].ad_group_id == 789
    assert result.items[0].campaign_id == 321
    assert result.items[0].bidding_strategy_configuration == {"biddingScheme": {"type": "CPC"}}
    assert result.items[0].disable_ai_keyword_expansion == "FALSE"


async def test_list_search_ad_groups_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
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

    monkeypatch.setattr(list_search_ad_groups_tool, "AdGroupServiceApi", FakeAdGroupServiceApi)
    handlers = FakeHandlers()
    first = await list_search_ad_groups_tool.list_search_ad_groups(
        handlers,
        ListSearchAdGroupsRequest(base_account_id=123, account_id=456, campaign_ids=[321]),
    )
    continued = await list_search_ad_groups_tool.list_search_ad_groups(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.campaign_ids for _, selector in captured] == [[321], [321]]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_search_ad_groups_rejects_value_with_no_ad_group(monkeypatch, patch_to_thread):
    class FakeAdGroupServiceApi:
        def __init__(self, client):
            pass

        def ad_group_service_get_post(self, x_z_base_account_id, ad_group_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeAdGroupValue(ad_group=None)], total=1))

    monkeypatch.setattr(list_search_ad_groups_tool, "AdGroupServiceApi", FakeAdGroupServiceApi)

    with pytest.raises(ToolError, match="ad group entry without ad group data"):
        await list_search_ad_groups_tool.list_search_ad_groups(
            FakeHandlers(),
            ListSearchAdGroupsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize(
    "date_range",
    [
        {},
        {"startDate": "20260815", "endDate": "20260801"},
        {"startDate": "2026-08-01"},
    ],
)
def test_search_ad_group_date_range_rejects_invalid_ranges(date_range):
    with pytest.raises(ValidationError):
        SearchAdGroupDateRange.model_validate(date_range)


@pytest.mark.parametrize(
    "cpc_range",
    [
        {},
        {"min": 2000, "max": 100},
    ],
)
def test_search_ad_group_bidding_keyword_cpc_range_rejects_invalid_ranges(cpc_range):
    with pytest.raises(ValidationError):
        SearchAdGroupBiddingKeywordCpcRange.model_validate(cpc_range)


@pytest.mark.parametrize("field", ["adGroupIds", "portfolioBiddingIds", "campaignIds", "labelIds"])
def test_list_search_ad_groups_rejects_more_than_default_page_size_filter_ids(field):
    with pytest.raises(ValidationError):
        ListSearchAdGroupsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
