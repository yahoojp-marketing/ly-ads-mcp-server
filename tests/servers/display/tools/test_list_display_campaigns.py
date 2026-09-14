from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.client import CampaignServiceUserStatus
from ly_ads_mcp.servers.display.tools import list_display_campaigns as list_display_campaigns_tool
from ly_ads_mcp.servers.display.tools.list_display_campaigns import (
    DisplayCampaignBudgetAmountRange,
    DisplayCampaignDateRange,
    ListDisplayCampaignsRequest,
)


class FakeCampaign:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeCampaignValue:
    def __init__(self, campaign=None):
        self.campaign = campaign


async def test_list_display_campaigns_maps_request_to_selector(monkeypatch, patch_to_thread):
    captured = {}

    class FakeCampaignServiceApi:
        def __init__(self, client):
            pass

        def campaign_service_get_post(self, x_z_base_account_id, campaign_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = campaign_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeCampaignValue(
                            campaign=FakeCampaign(
                                {
                                    "accountId": 456,
                                    "campaignId": 789,
                                    "campaignName": "Campaign A",
                                    "budget": {"amount": 1000},
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_display_campaigns_tool, "CampaignServiceApi", FakeCampaignServiceApi)
    result = await list_display_campaigns_tool.list_display_campaigns(
        FakeHandlers(),
        ListDisplayCampaignsRequest(
            base_account_id=123,
            account_id=456,
            campaign_ids=[789],
            campaign_budget_ids=[11],
            portfolio_bidding_ids=[12],
            contains_label=True,
            feed_ids=[13],
            label_ids=[14],
            user_statuses=[CampaignServiceUserStatus.ACTIVE],
            created_date_range=DisplayCampaignDateRange(start_date="20260801"),
            updated_date_range=DisplayCampaignDateRange(end_date="20260815"),
            conversion_group_ids=[15],
            conversion_tracker_ids=[16],
            budget_amount_range=DisplayCampaignBudgetAmountRange(min=100, max=2000),
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.campaign_ids == [789]
    assert selector.campaign_budget_ids == [11]
    assert selector.portfolio_bidding_ids == [12]
    assert selector.contains_label is True
    assert selector.feed_ids == [13]
    assert selector.label_ids == [14]
    assert [status.value for status in selector.user_statuses] == ["ACTIVE"]
    assert selector.created_date_range.start_date == "20260801"
    assert selector.updated_date_range.end_date == "20260815"
    assert selector.conversion_group_ids == [15]
    assert selector.conversion_tracker_ids == [16]
    assert selector.budget_amount_range.min == 100
    assert selector.budget_amount_range.max == 2000
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 789
    assert result.items[0].budget == {"amount": 1000}


async def test_list_display_campaigns_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
    captured = []

    class FakeCampaignServiceApi:
        def __init__(self, client):
            pass

        def campaign_service_get_post(self, x_z_base_account_id, campaign_service_selector):
            captured.append((x_z_base_account_id, campaign_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeCampaignValue(campaign=FakeCampaign({"campaignId": campaign_id}))
                        for campaign_id in range(campaign_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_display_campaigns_tool, "CampaignServiceApi", FakeCampaignServiceApi)
    handlers = FakeHandlers()
    first = await list_display_campaigns_tool.list_display_campaigns(
        handlers,
        ListDisplayCampaignsRequest(base_account_id=123, account_id=456),
    )
    continued = await list_display_campaigns_tool.list_display_campaigns(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_display_campaigns_rejects_value_with_no_campaign(monkeypatch, patch_to_thread):
    class FakeCampaignServiceApi:
        def __init__(self, client):
            pass

        def campaign_service_get_post(self, x_z_base_account_id, campaign_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeCampaignValue(campaign=None)], total=1))

    monkeypatch.setattr(list_display_campaigns_tool, "CampaignServiceApi", FakeCampaignServiceApi)

    with pytest.raises(ToolError, match="campaign entry without campaign data"):
        await list_display_campaigns_tool.list_display_campaigns(
            FakeHandlers(),
            ListDisplayCampaignsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize(
    "date_range",
    [
        {},
        {"startDate": "20260815", "endDate": "20260801"},
        {"startDate": "2026-08-01"},
    ],
)
def test_display_campaign_date_range_rejects_invalid_ranges(date_range):
    with pytest.raises(ValidationError):
        DisplayCampaignDateRange.model_validate(date_range)


@pytest.mark.parametrize(
    "budget_range",
    [
        {},
        {"min": 2000, "max": 100},
    ],
)
def test_display_campaign_budget_amount_range_rejects_invalid_ranges(budget_range):
    with pytest.raises(ValidationError):
        DisplayCampaignBudgetAmountRange.model_validate(budget_range)
