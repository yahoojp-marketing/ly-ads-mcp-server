from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.search.client import (
    CampaignTargetServiceExcludedType,
    CampaignTargetServicePlatformType,
    CampaignTargetServiceTargetType,
)
from ly_ads_mcp.servers.search.tools import (
    list_search_campaign_targets as list_search_campaign_targets_tool,
)
from ly_ads_mcp.servers.search.tools.list_search_campaign_targets import (
    ListSearchCampaignTargetsRequest,
)


class FakeCampaignTarget:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeCampaignTargetValue:
    def __init__(self, campaign_target=None):
        self.campaign_target = campaign_target


async def test_list_search_campaign_targets_maps_request_to_selector(monkeypatch, patch_to_thread):
    captured = {}

    class FakeCampaignTargetServiceApi:
        def __init__(self, client):
            pass

        def campaign_target_service_get_post(
            self,
            x_z_base_account_id,
            campaign_target_service_selector,
        ):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = campaign_target_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeCampaignTargetValue(
                            campaign_target=FakeCampaignTarget(
                                {
                                    "accountId": 456,
                                    "bidMultiplier": 1.2,
                                    "campaignId": 789,
                                    "campaignName": "Campaign A",
                                    "target": {
                                        "targetId": "target-1",
                                        "targetType": "LOCATION",
                                        "locationTarget": {
                                            "cityNameEN": "Shinjuku",
                                            "cityNameJA": "新宿区",
                                            "excludedType": "INCLUDED",
                                            "provinceNameEN": "Tokyo",
                                            "provinceNameJA": "東京都",
                                            "targetingStatus": "ACTIVE",
                                        },
                                    },
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(
        list_search_campaign_targets_tool,
        "CampaignTargetServiceApi",
        FakeCampaignTargetServiceApi,
    )
    result = await list_search_campaign_targets_tool.list_search_campaign_targets(
        FakeHandlers(),
        ListSearchCampaignTargetsRequest(
            base_account_id=123,
            account_id=456,
            campaign_ids=[789],
            excluded_type=CampaignTargetServiceExcludedType.INCLUDED,
            platform_types=[CampaignTargetServicePlatformType.DESKTOP],
            target_ids=["target-1"],
            target_types=[CampaignTargetServiceTargetType.LOCATION],
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.campaign_ids == [789]
    assert selector.excluded_type.value == "INCLUDED"
    assert [platform.value for platform in selector.platform_types] == ["DESKTOP"]
    assert selector.target_ids == ["target-1"]
    assert [target_type.value for target_type in selector.target_types] == ["LOCATION"]
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 789
    assert result.items[0].bid_multiplier == 1.2
    assert result.items[0].target is not None
    assert result.items[0].target.target_id == "target-1"
    assert result.items[0].target.location_target is not None
    assert result.items[0].target.location_target.city_name_en == "Shinjuku"
    assert result.items[0].target.location_target.province_name_ja == "東京都"
    location_payload = result.model_dump()["items"][0]["target"]["locationTarget"]
    assert location_payload["cityNameEN"] == "Shinjuku"
    assert location_payload["cityNameJA"] == "新宿区"


async def test_list_search_campaign_targets_uses_fixed_page_size_across_pages(
    monkeypatch,
    patch_to_thread,
):
    captured = []

    class FakeCampaignTargetServiceApi:
        def __init__(self, client):
            pass

        def campaign_target_service_get_post(
            self,
            x_z_base_account_id,
            campaign_target_service_selector,
        ):
            captured.append((x_z_base_account_id, campaign_target_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeCampaignTargetValue(
                            campaign_target=FakeCampaignTarget({"campaignId": campaign_id})
                        )
                        for campaign_id in range(campaign_target_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(
        list_search_campaign_targets_tool,
        "CampaignTargetServiceApi",
        FakeCampaignTargetServiceApi,
    )
    handlers = FakeHandlers()
    first = await list_search_campaign_targets_tool.list_search_campaign_targets(
        handlers,
        ListSearchCampaignTargetsRequest(
            base_account_id=123,
            account_id=456,
            campaign_ids=[789],
        ),
    )
    continued = await list_search_campaign_targets_tool.list_search_campaign_targets(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.campaign_ids for _, selector in captured] == [[789], [789]]
    assert [selector.number_results for _, selector in captured] == [
        DEFAULT_PAGE_SIZE,
        DEFAULT_PAGE_SIZE,
    ]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_search_campaign_targets_rejects_value_with_no_campaign_target(
    monkeypatch,
    patch_to_thread,
):
    class FakeCampaignTargetServiceApi:
        def __init__(self, client):
            pass

        def campaign_target_service_get_post(
            self,
            x_z_base_account_id,
            campaign_target_service_selector,
        ):
            return FakeApiResponse(
                rval=FakeRval(values=[FakeCampaignTargetValue(campaign_target=None)], total=1)
            )

    monkeypatch.setattr(
        list_search_campaign_targets_tool,
        "CampaignTargetServiceApi",
        FakeCampaignTargetServiceApi,
    )

    with pytest.raises(ToolError, match="campaign target entry without campaign target data"):
        await list_search_campaign_targets_tool.list_search_campaign_targets(
            FakeHandlers(),
            ListSearchCampaignTargetsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize("field", ["campaignIds", "targetIds"])
def test_list_search_campaign_targets_rejects_more_than_default_page_size_filter_ids(field):
    values = [str(value) for value in range(DEFAULT_PAGE_SIZE + 1)] if field == "targetIds" else list(
        range(DEFAULT_PAGE_SIZE + 1)
    )
    with pytest.raises(ValidationError):
        ListSearchCampaignTargetsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field: values,
            }
        )
