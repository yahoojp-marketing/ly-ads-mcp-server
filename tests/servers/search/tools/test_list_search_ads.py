from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.search.client import (
    AdGroupAdServiceAdType,
    AdGroupAdServiceApprovalStatus,
    AdGroupAdServiceUserStatus,
)
from ly_ads_mcp.servers.search.tools import list_search_ads as list_search_ads_tool
from ly_ads_mcp.servers.search.tools.list_search_ads import (
    ListSearchAdsRequest,
    SearchAdGroupAdDateRange,
    SearchAdGroupAdItem,
)


class FakeAdGroupAd:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeAdGroupAdValue:
    def __init__(self, ad_group_ad=None):
        self.ad_group_ad = ad_group_ad


async def test_list_search_ads_maps_request_to_selector(monkeypatch, patch_to_thread):
    captured = {}

    class FakeAdGroupAdServiceApi:
        def __init__(self, client):
            pass

        def ad_group_ad_service_get_post(self, x_z_base_account_id, ad_group_ad_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = ad_group_ad_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupAdValue(
                            ad_group_ad=FakeAdGroupAd(
                                {
                                    "accountId": 456,
                                    "campaignId": 321,
                                    "adGroupId": 789,
                                    "adId": 987,
                                    "adName": "Responsive Ad A",
                                    "approvalStatus": "APPROVED",
                                    "userStatus": "ACTIVE",
                                    "ad": {
                                        "adType": "RESPONSIVE_SEARCH_AD",
                                        "finalUrl": "https://example.com/",
                                        "responsiveSearchAd": {"headlines": [{"text": "Headline"}]},
                                    },
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_search_ads_tool, "AdGroupAdServiceApi", FakeAdGroupAdServiceApi)
    result = await list_search_ads_tool.list_search_ads(
        FakeHandlers(),
        ListSearchAdsRequest(
            base_account_id=123,
            account_id=456,
            campaign_ids=[321],
            ad_group_ids=[789],
            ad_ids=[987],
            ad_types=[AdGroupAdServiceAdType.RESPONSIVE_SEARCH_AD],
            approval_statuses=[AdGroupAdServiceApprovalStatus.APPROVED],
            user_statuses=[AdGroupAdServiceUserStatus.ACTIVE],
            contains_label=True,
            label_ids=[13],
            created_date_range=SearchAdGroupAdDateRange(start_date="20260801"),
            updated_date_range=SearchAdGroupAdDateRange(end_date="20260815"),
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.campaign_ids == [321]
    assert selector.ad_group_ids == [789]
    assert selector.ad_ids == [987]
    assert [ad_type.value for ad_type in selector.ad_types] == ["RESPONSIVE_SEARCH_AD"]
    assert [status.value for status in selector.approval_statuses] == ["APPROVED"]
    assert [status.value for status in selector.user_statuses] == ["ACTIVE"]
    assert selector.contains_label is True
    assert selector.label_ids == [13]
    assert selector.created_date_range.start_date == "20260801"
    assert selector.updated_date_range.end_date == "20260815"
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 321
    assert result.items[0].ad_group_id == 789
    assert result.items[0].ad_id == 987
    assert result.items[0].ad == {
        "adType": "RESPONSIVE_SEARCH_AD",
        "finalUrl": "https://example.com/",
        "responsiveSearchAd": {"headlines": [{"text": "Headline"}]},
    }


async def test_list_search_ads_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
    captured = []

    class FakeAdGroupAdServiceApi:
        def __init__(self, client):
            pass

        def ad_group_ad_service_get_post(self, x_z_base_account_id, ad_group_ad_service_selector):
            captured.append((x_z_base_account_id, ad_group_ad_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupAdValue(ad_group_ad=FakeAdGroupAd({"adId": ad_id}))
                        for ad_id in range(ad_group_ad_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_search_ads_tool, "AdGroupAdServiceApi", FakeAdGroupAdServiceApi)
    handlers = FakeHandlers()
    first = await list_search_ads_tool.list_search_ads(
        handlers,
        ListSearchAdsRequest(base_account_id=123, account_id=456, ad_group_ids=[789]),
    )
    continued = await list_search_ads_tool.list_search_ads(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.ad_group_ids for _, selector in captured] == [[789], [789]]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_search_ads_rejects_value_with_no_ad(monkeypatch, patch_to_thread):
    class FakeAdGroupAdServiceApi:
        def __init__(self, client):
            pass

        def ad_group_ad_service_get_post(self, x_z_base_account_id, ad_group_ad_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeAdGroupAdValue(ad_group_ad=None)], total=1))

    monkeypatch.setattr(list_search_ads_tool, "AdGroupAdServiceApi", FakeAdGroupAdServiceApi)

    with pytest.raises(ToolError, match="ad entry without ad data"):
        await list_search_ads_tool.list_search_ads(
            FakeHandlers(),
            ListSearchAdsRequest(base_account_id=123, account_id=456),
        )


def test_search_ad_group_ad_item_rejects_null_string_list_elements():
    with pytest.raises(ValidationError):
        SearchAdGroupAdItem.model_validate(
            {
                "baseAccountId": 123,
                "disapprovalReasonCodes": [None],
            }
        )


@pytest.mark.parametrize(
    "date_range",
    [
        {},
        {"startDate": "20260815", "endDate": "20260801"},
        {"startDate": "2026-08-01"},
    ],
)
def test_search_ad_group_ad_date_range_rejects_invalid_ranges(date_range):
    with pytest.raises(ValidationError):
        SearchAdGroupAdDateRange.model_validate(date_range)


@pytest.mark.parametrize("field", ["campaignIds", "adGroupIds", "adIds", "labelIds"])
def test_list_search_ads_rejects_more_than_default_page_size_filter_ids(field):
    with pytest.raises(ValidationError):
        ListSearchAdsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
