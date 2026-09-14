from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.client import (
    AdGroupTargetServiceAreaSearchType,
    AdGroupTargetServiceSortField,
    AdGroupTargetServiceSortType,
    AdGroupTargetServiceTargetType,
)
from ly_ads_mcp.servers.display.tools import list_display_ad_group_targets as list_display_ad_group_targets_tool
from ly_ads_mcp.servers.display.tools.list_display_ad_group_targets import ListDisplayAdGroupTargetsRequest


class FakeAdGroupTarget:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeAdGroupTargetValue:
    def __init__(self, ad_group_target_list=None):
        self.ad_group_target_list = ad_group_target_list


async def test_list_display_ad_group_targets_maps_request_to_selector(monkeypatch, patch_to_thread):
    captured = {}

    class FakeAdGroupTargetServiceApi:
        def __init__(self, client):
            pass

        def ad_group_target_service_get_post(self, x_z_base_account_id, ad_group_target_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = ad_group_target_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupTargetValue(
                            ad_group_target_list=FakeAdGroupTarget(
                                {
                                    "accountId": 456,
                                    "campaignId": 789,
                                    "adGroupId": 987,
                                    "bidMultiplier": 1.2,
                                    "target": {
                                        "targetId": "13",
                                        "targetType": "GEO_TARGET",
                                        "geoTarget": {"areaSearchType": "GEO", "geoNameJa": "東京都"},
                                    },
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_display_ad_group_targets_tool, "AdGroupTargetServiceApi", FakeAdGroupTargetServiceApi)
    result = await list_display_ad_group_targets_tool.list_display_ad_group_targets(
        FakeHandlers(),
        ListDisplayAdGroupTargetsRequest(
            base_account_id=123,
            account_id=456,
            ad_group_ids=[987],
            campaign_ids=[789],
            target_types=[AdGroupTargetServiceTargetType.GEO_TARGET],
            area_search_types=[AdGroupTargetServiceAreaSearchType.GEO],
            sort_field=AdGroupTargetServiceSortField.AREA_SEARCH_TYPE,
            sort_type=AdGroupTargetServiceSortType.ASC,
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.ad_group_ids == [987]
    assert selector.campaign_ids == [789]
    assert [target_type.value for target_type in selector.target_types] == ["GEO_TARGET"]
    assert [area_search_type.value for area_search_type in selector.area_search_types] == ["GEO"]
    assert selector.sort_field is AdGroupTargetServiceSortField.AREA_SEARCH_TYPE
    assert selector.sort_type is AdGroupTargetServiceSortType.ASC
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 789
    assert result.items[0].ad_group_id == 987
    assert result.items[0].bid_multiplier == 1.2
    assert result.items[0].target == {
        "targetId": "13",
        "targetType": "GEO_TARGET",
        "geoTarget": {"areaSearchType": "GEO", "geoNameJa": "東京都"},
    }


async def test_list_display_ad_group_targets_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
    captured = []

    class FakeAdGroupTargetServiceApi:
        def __init__(self, client):
            pass

        def ad_group_target_service_get_post(self, x_z_base_account_id, ad_group_target_service_selector):
            captured.append((x_z_base_account_id, ad_group_target_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupTargetValue(
                            ad_group_target_list=FakeAdGroupTarget({"adGroupId": ad_group_id})
                        )
                        for ad_group_id in range(ad_group_target_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_display_ad_group_targets_tool, "AdGroupTargetServiceApi", FakeAdGroupTargetServiceApi)
    handlers = FakeHandlers()
    first = await list_display_ad_group_targets_tool.list_display_ad_group_targets(
        handlers,
        ListDisplayAdGroupTargetsRequest(base_account_id=123, account_id=456),
    )
    continued = await list_display_ad_group_targets_tool.list_display_ad_group_targets(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_display_ad_group_targets_rejects_value_with_no_ad_group_target(monkeypatch, patch_to_thread):
    class FakeAdGroupTargetServiceApi:
        def __init__(self, client):
            pass

        def ad_group_target_service_get_post(self, x_z_base_account_id, ad_group_target_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeAdGroupTargetValue()], total=1))

    monkeypatch.setattr(list_display_ad_group_targets_tool, "AdGroupTargetServiceApi", FakeAdGroupTargetServiceApi)

    with pytest.raises(ToolError, match="ad group target entry without ad group target data"):
        await list_display_ad_group_targets_tool.list_display_ad_group_targets(
            FakeHandlers(),
            ListDisplayAdGroupTargetsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize("field_name", ["adGroupIds", "campaignIds"])
def test_list_display_ad_group_targets_rejects_more_than_default_page_size_ids(field_name):
    with pytest.raises(ValidationError):
        ListDisplayAdGroupTargetsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field_name: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
