from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.client import (
    AdGroupAdServiceAdType,
    AdGroupAdServiceApprovalStatus,
    AdGroupAdServiceMainMediaFormat,
    AdGroupAdServiceUserStatus,
)
from ly_ads_mcp.servers.display.tools import list_display_ads as list_display_ads_tool
from ly_ads_mcp.servers.display.tools.list_display_ads import DisplayAdDateRange, ListDisplayAdsRequest


class FakeAd:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeAdValue:
    def __init__(self, ad_group_ad=None):
        self.ad_group_ad = ad_group_ad


async def test_list_display_ads_maps_request_to_selector(monkeypatch, patch_to_thread):
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
                        FakeAdValue(
                            ad_group_ad=FakeAd(
                                {
                                    "accountId": 456,
                                    "campaignId": 789,
                                    "adGroupId": 987,
                                    "adId": 654,
                                    "adName": "Ad A",
                                    "ad": {
                                        "adType": "RESPONSIVE_AD",
                                        "mainMediaFormat": "IMAGE",
                                        "responsiveAd": {"headline": "Headline"},
                                    },
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_display_ads_tool, "AdGroupAdServiceApi", FakeAdGroupAdServiceApi)
    result = await list_display_ads_tool.list_display_ads(
        FakeHandlers(),
        ListDisplayAdsRequest(
            base_account_id=123,
            account_id=456,
            ad_group_ids=[987],
            ad_ids=[654],
            approval_statuses=[AdGroupAdServiceApprovalStatus.APPROVED],
            campaign_ids=[789],
            contains_label=True,
            label_ids=[12],
            media_ids=[13],
            ad_types=[AdGroupAdServiceAdType.RESPONSIVE_AD],
            main_media_formats=[AdGroupAdServiceMainMediaFormat.IMAGE],
            user_statuses=[AdGroupAdServiceUserStatus.ACTIVE],
            created_date_range=DisplayAdDateRange(start_date="20260801"),
            updated_date_range=DisplayAdDateRange(end_date="20260815"),
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.ad_group_ids == [987]
    assert selector.ad_ids == [654]
    assert [status.value for status in selector.approval_statuses] == ["APPROVED"]
    assert selector.campaign_ids == [789]
    assert selector.contains_label is True
    assert selector.label_ids == [12]
    assert selector.media_ids == [13]
    assert [ad_type.value for ad_type in selector.ad_types] == ["RESPONSIVE_AD"]
    assert [media_format.value for media_format in selector.main_media_formats] == ["IMAGE"]
    assert [status.value for status in selector.user_statuses] == ["ACTIVE"]
    assert selector.created_date_range.start_date == "20260801"
    assert selector.updated_date_range.end_date == "20260815"
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 789
    assert result.items[0].ad_group_id == 987
    assert result.items[0].ad_id == 654
    assert result.items[0].ad == {
        "adType": "RESPONSIVE_AD",
        "mainMediaFormat": "IMAGE",
        "responsiveAd": {"headline": "Headline"},
    }


async def test_list_display_ads_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
    captured = []

    class FakeAdGroupAdServiceApi:
        def __init__(self, client):
            pass

        def ad_group_ad_service_get_post(self, x_z_base_account_id, ad_group_ad_service_selector):
            captured.append((x_z_base_account_id, ad_group_ad_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdValue(ad_group_ad=FakeAd({"adId": ad_id}))
                        for ad_id in range(ad_group_ad_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_display_ads_tool, "AdGroupAdServiceApi", FakeAdGroupAdServiceApi)
    handlers = FakeHandlers()
    first = await list_display_ads_tool.list_display_ads(
        handlers,
        ListDisplayAdsRequest(base_account_id=123, account_id=456),
    )
    continued = await list_display_ads_tool.list_display_ads(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_display_ads_rejects_value_with_no_ad(monkeypatch, patch_to_thread):
    class FakeAdGroupAdServiceApi:
        def __init__(self, client):
            pass

        def ad_group_ad_service_get_post(self, x_z_base_account_id, ad_group_ad_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeAdValue(ad_group_ad=None)], total=1))

    monkeypatch.setattr(list_display_ads_tool, "AdGroupAdServiceApi", FakeAdGroupAdServiceApi)

    with pytest.raises(ToolError, match="ad entry without ad data"):
        await list_display_ads_tool.list_display_ads(
            FakeHandlers(),
            ListDisplayAdsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize(
    "date_range",
    [
        {},
        {"startDate": "20260815", "endDate": "20260801"},
        {"startDate": "2026-08-01"},
    ],
)
def test_display_ad_date_range_rejects_invalid_ranges(date_range):
    with pytest.raises(ValidationError):
        DisplayAdDateRange.model_validate(date_range)


@pytest.mark.parametrize(
    "field_name",
    ["adGroupIds", "adIds", "campaignIds", "labelIds", "mediaIds"],
)
def test_list_display_ads_rejects_more_than_default_page_size_ids(field_name):
    with pytest.raises(ValidationError):
        ListDisplayAdsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field_name: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
