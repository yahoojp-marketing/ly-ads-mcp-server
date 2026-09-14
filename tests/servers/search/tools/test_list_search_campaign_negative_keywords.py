from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.search.client import CampaignCriterionServiceUse
from ly_ads_mcp.servers.search.tools import (
    list_search_campaign_negative_keywords as list_search_campaign_negative_keywords_tool,
)
from ly_ads_mcp.servers.search.tools.list_search_campaign_negative_keywords import (
    ListSearchCampaignNegativeKeywordsRequest,
)


class FakeCampaignCriterion:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeCampaignCriterionValue:
    def __init__(self, campaign_criterion=None):
        self.campaign_criterion = campaign_criterion


async def test_list_search_campaign_negative_keywords_maps_request_to_selector(
    monkeypatch, patch_to_thread
):
    captured = {}

    class FakeCampaignCriterionServiceApi:
        def __init__(self, client):
            pass

        def campaign_criterion_service_get_post(
            self, x_z_base_account_id, campaign_criterion_service_selector
        ):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = campaign_criterion_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeCampaignCriterionValue(
                            campaign_criterion=FakeCampaignCriterion(
                                {
                                    "accountId": 456,
                                    "campaignId": 789,
                                    "campaignName": "Campaign A",
                                    "criterion": {
                                        "criterionId": 987,
                                        "criterionType": "KEYWORD",
                                        "keyword": {
                                            "keywordMatchType": "EXACT",
                                            "text": "blocked phrase",
                                        },
                                    },
                                    "use": "NEGATIVE",
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(
        list_search_campaign_negative_keywords_tool,
        "CampaignCriterionServiceApi",
        FakeCampaignCriterionServiceApi,
    )
    result = await list_search_campaign_negative_keywords_tool.list_search_campaign_negative_keywords(
        FakeHandlers(),
        ListSearchCampaignNegativeKeywordsRequest(
            base_account_id=123,
            account_id=456,
            campaign_ids=[789],
            criterion_ids=[987],
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.campaign_ids == [789]
    assert selector.criterion_ids == [987]
    assert selector.use is CampaignCriterionServiceUse.NEGATIVE
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].campaign_id == 789
    assert result.items[0].criterion is not None
    assert result.items[0].criterion.criterion_id == 987
    assert result.items[0].criterion.keyword is not None
    assert result.items[0].criterion.keyword.keyword_match_type == "EXACT"
    assert result.items[0].criterion.keyword.text == "blocked phrase"
    assert result.items[0].use == "NEGATIVE"


async def test_list_search_campaign_negative_keywords_uses_fixed_page_size_across_pages(
    monkeypatch, patch_to_thread
):
    captured = []

    class FakeCampaignCriterionServiceApi:
        def __init__(self, client):
            pass

        def campaign_criterion_service_get_post(
            self, x_z_base_account_id, campaign_criterion_service_selector
        ):
            captured.append((x_z_base_account_id, campaign_criterion_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeCampaignCriterionValue(
                            campaign_criterion=FakeCampaignCriterion({"campaignId": campaign_id})
                        )
                        for campaign_id in range(campaign_criterion_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(
        list_search_campaign_negative_keywords_tool,
        "CampaignCriterionServiceApi",
        FakeCampaignCriterionServiceApi,
    )
    handlers = FakeHandlers()
    first = await list_search_campaign_negative_keywords_tool.list_search_campaign_negative_keywords(
        handlers,
        ListSearchCampaignNegativeKeywordsRequest(base_account_id=123, account_id=456),
    )
    continued = await list_search_campaign_negative_keywords_tool.list_search_campaign_negative_keywords(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.use for _, selector in captured] == [
        CampaignCriterionServiceUse.NEGATIVE,
        CampaignCriterionServiceUse.NEGATIVE,
    ]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_search_campaign_negative_keywords_rejects_value_with_no_campaign_criterion(
    monkeypatch, patch_to_thread
):
    class FakeCampaignCriterionServiceApi:
        def __init__(self, client):
            pass

        def campaign_criterion_service_get_post(
            self, x_z_base_account_id, campaign_criterion_service_selector
        ):
            return FakeApiResponse(rval=FakeRval(values=[FakeCampaignCriterionValue()], total=1))

    monkeypatch.setattr(
        list_search_campaign_negative_keywords_tool,
        "CampaignCriterionServiceApi",
        FakeCampaignCriterionServiceApi,
    )

    with pytest.raises(ToolError, match="entry without campaign criterion data"):
        await list_search_campaign_negative_keywords_tool.list_search_campaign_negative_keywords(
            FakeHandlers(),
            ListSearchCampaignNegativeKeywordsRequest(base_account_id=123, account_id=456),
        )


@pytest.mark.parametrize("field_name", ["campaignIds", "criterionIds"])
def test_list_search_campaign_negative_keywords_rejects_more_than_default_page_size_ids(field_name):
    with pytest.raises(ValidationError):
        ListSearchCampaignNegativeKeywordsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                field_name: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
