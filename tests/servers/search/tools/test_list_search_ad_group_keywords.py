from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.search.client import (
    AdGroupCriterionServiceApprovalStatus,
    AdGroupCriterionServiceKeywordMatchType,
    AdGroupCriterionServiceUse,
    AdGroupCriterionServiceUserStatus,
)
from ly_ads_mcp.servers.search.tools import (
    list_search_ad_group_keywords as list_search_ad_group_keywords_tool,
)
from ly_ads_mcp.servers.search.tools.list_search_ad_group_keywords import (
    ListSearchAdGroupKeywordsRequest,
    SearchAdGroupKeywordCpcRange,
    SearchAdGroupKeywordFilter,
)


class FakeAdGroupCriterion:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeAdGroupCriterionValue:
    def __init__(self, ad_group_criterion=None):
        self.ad_group_criterion = ad_group_criterion


async def test_list_search_ad_group_keywords_maps_request_to_selector(
    monkeypatch, patch_to_thread
):
    captured = {}

    class FakeAdGroupCriterionServiceApi:
        def __init__(self, client):
            pass

        def ad_group_criterion_service_get_post(
            self, x_z_base_account_id, ad_group_criterion_service_selector
        ):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = ad_group_criterion_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupCriterionValue(
                            ad_group_criterion=FakeAdGroupCriterion(
                                {
                                    "accountId": 456,
                                    "campaignId": 321,
                                    "campaignName": "Campaign A",
                                    "adGroupId": 789,
                                    "adGroupName": "Ad Group A",
                                    "criterion": {
                                        "criterionId": 654,
                                        "criterionTrackId": 655,
                                        "criterionType": "KEYWORD",
                                        "keyword": {
                                            "text": "running shoes",
                                            "keywordMatchType": "EXACT",
                                        },
                                    },
                                    "use": "BIDDABLE",
                                    "biddableAdGroupCriterion": {
                                        "bid": {"keywordCpc": 120},
                                        "userStatus": "ACTIVE",
                                    },
                                    "labels": [{"labelId": 13, "labelName": "Priority"}],
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(
        list_search_ad_group_keywords_tool,
        "AdGroupCriterionServiceApi",
        FakeAdGroupCriterionServiceApi,
    )
    result = await list_search_ad_group_keywords_tool.list_search_ad_group_keywords(
        FakeHandlers(),
        ListSearchAdGroupKeywordsRequest(
            base_account_id=123,
            account_id=456,
            use=AdGroupCriterionServiceUse.BIDDABLE,
            ad_group_ids=[789],
            approval_statuses=[AdGroupCriterionServiceApprovalStatus.APPROVED],
            portfolio_bidding_ids=[11],
            campaign_ids=[321],
            contains_label=True,
            criterion_ids=[654],
            label_ids=[13],
            user_statuses=[AdGroupCriterionServiceUserStatus.ACTIVE],
            keyword=SearchAdGroupKeywordFilter(
                keyword_match_type=AdGroupCriterionServiceKeywordMatchType.EXACT,
                text="running shoes",
            ),
            bidding_keyword_cpc_range=SearchAdGroupKeywordCpcRange(min=100, max=200),
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.ad_group_ids == [789]
    assert [status.value for status in selector.approval_statuses] == ["APPROVED"]
    assert selector.portfolio_bidding_ids == [11]
    assert selector.campaign_ids == [321]
    assert selector.contains_label_id.value == "TRUE"
    assert selector.criterion_ids == [654]
    assert selector.label_ids == [13]
    assert selector.use.value == "BIDDABLE"
    assert [status.value for status in selector.user_statuses] == ["ACTIVE"]
    assert selector.keyword.keyword_match_type.value == "EXACT"
    assert selector.keyword.text == "running shoes"
    assert selector.bidding_keyword_cpc_range.min == 100
    assert selector.bidding_keyword_cpc_range.max == 200
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].ad_group_id == 789
    assert result.items[0].criterion_id == 654
    assert result.items[0].criterion_type == "KEYWORD"
    assert result.items[0].keyword == {
        "text": "running shoes",
        "keywordMatchType": "EXACT",
    }
    assert result.items[0].biddable_ad_group_criterion == {
        "bid": {"keywordCpc": 120},
        "userStatus": "ACTIVE",
    }


async def test_list_search_ad_group_keywords_uses_fixed_page_size_across_pages(
    monkeypatch, patch_to_thread
):
    captured = []

    class FakeAdGroupCriterionServiceApi:
        def __init__(self, client):
            pass

        def ad_group_criterion_service_get_post(
            self, x_z_base_account_id, ad_group_criterion_service_selector
        ):
            captured.append((x_z_base_account_id, ad_group_criterion_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeAdGroupCriterionValue(
                            ad_group_criterion=FakeAdGroupCriterion(
                                {"criterion": {"criterionId": criterion_id}}
                            )
                        )
                        for criterion_id in range(
                            ad_group_criterion_service_selector.number_results
                        )
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(
        list_search_ad_group_keywords_tool,
        "AdGroupCriterionServiceApi",
        FakeAdGroupCriterionServiceApi,
    )
    handlers = FakeHandlers()
    first = await list_search_ad_group_keywords_tool.list_search_ad_group_keywords(
        handlers,
        ListSearchAdGroupKeywordsRequest(
            base_account_id=123,
            account_id=456,
            use=AdGroupCriterionServiceUse.NEGATIVE,
            campaign_ids=[321],
        ),
    )
    continued = await list_search_ad_group_keywords_tool.list_search_ad_group_keywords(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.campaign_ids for _, selector in captured] == [[321], [321]]
    assert [selector.use.value for _, selector in captured] == ["NEGATIVE", "NEGATIVE"]
    assert [selector.number_results for _, selector in captured] == [
        DEFAULT_PAGE_SIZE,
        DEFAULT_PAGE_SIZE,
    ]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_search_ad_group_keywords_rejects_value_with_no_keyword(
    monkeypatch, patch_to_thread
):
    class FakeAdGroupCriterionServiceApi:
        def __init__(self, client):
            pass

        def ad_group_criterion_service_get_post(
            self, x_z_base_account_id, ad_group_criterion_service_selector
        ):
            return FakeApiResponse(
                rval=FakeRval(values=[FakeAdGroupCriterionValue()], total=1)
            )

    monkeypatch.setattr(
        list_search_ad_group_keywords_tool,
        "AdGroupCriterionServiceApi",
        FakeAdGroupCriterionServiceApi,
    )

    with pytest.raises(ToolError, match="keyword entry without keyword data"):
        await list_search_ad_group_keywords_tool.list_search_ad_group_keywords(
            FakeHandlers(),
            ListSearchAdGroupKeywordsRequest(
                base_account_id=123,
                account_id=456,
                use=AdGroupCriterionServiceUse.BIDDABLE,
            ),
        )


@pytest.mark.parametrize(
    "keyword_filter",
    [
        {},
        {"text": ""},
    ],
)
def test_search_ad_group_keyword_filter_rejects_invalid_values(keyword_filter):
    with pytest.raises(ValidationError):
        SearchAdGroupKeywordFilter.model_validate(keyword_filter)


@pytest.mark.parametrize(
    "cpc_range",
    [
        {},
        {"min": 200, "max": 100},
    ],
)
def test_search_ad_group_keyword_cpc_range_rejects_invalid_ranges(cpc_range):
    with pytest.raises(ValidationError):
        SearchAdGroupKeywordCpcRange.model_validate(cpc_range)


@pytest.mark.parametrize(
    "field",
    ["adGroupIds", "portfolioBiddingIds", "campaignIds", "criterionIds", "labelIds"],
)
def test_list_search_ad_group_keywords_rejects_more_than_default_page_size_filter_ids(field):
    with pytest.raises(ValidationError):
        ListSearchAdGroupKeywordsRequest.model_validate(
            {
                "baseAccountId": 123,
                "accountId": 456,
                "use": "BIDDABLE",
                field: list(range(DEFAULT_PAGE_SIZE + 1)),
            }
        )
