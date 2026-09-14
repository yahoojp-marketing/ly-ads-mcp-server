# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_search_ad_group_keywords MCP tool."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp.exceptions import ToolError
from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from ly_ads_mcp.api_utils import extract_rval, to_plain_dict
from ly_ads_mcp.servers.common.pagination import (
    DEFAULT_PAGE_SIZE,
    McpOutputModel,
    PageSlice,
    PaginatedResult,
    StrictRequestModel,
    paginate,
)

from ..client import (
    AdGroupCriterionServiceApi,
    AdGroupCriterionServiceApprovalStatus,
    AdGroupCriterionServiceBiddingKeywordCpcRange,
    AdGroupCriterionServiceContainsLabelId,
    AdGroupCriterionServiceKeyword,
    AdGroupCriterionServiceKeywordMatchType,
    AdGroupCriterionServiceSelector,
    AdGroupCriterionServiceUse,
    AdGroupCriterionServiceUserStatus,
)
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_search_ad_group_keywords"


class SearchAdGroupKeywordFilter(StrictRequestModel):
    keyword_match_type: AdGroupCriterionServiceKeywordMatchType | SkipJsonSchema[None] = Field(
        default=None,
        description="Keyword match type to filter by. Omit when filtering only by keyword text.",
    )
    text: str | SkipJsonSchema[None] = Field(
        default=None,
        description="Keyword text to filter by. Omit when filtering only by match type.",
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_filter(self) -> SearchAdGroupKeywordFilter:
        if self.keyword_match_type is None and self.text is None:
            raise ValueError("Specify at least one of keywordMatchType or text.")
        return self


class SearchAdGroupKeywordCpcRange(StrictRequestModel):
    min: int | SkipJsonSchema[None] = Field(
        default=None,
        description="Minimum keyword bid amount. Omit when only a maximum is needed.",
    )
    max: int | SkipJsonSchema[None] = Field(
        default=None,
        description="Maximum keyword bid amount. Omit when only a minimum is needed.",
    )

    @model_validator(mode="after")
    def validate_range(self) -> SearchAdGroupKeywordCpcRange:
        if self.min is None and self.max is None:
            raise ValueError("Specify at least one of min or max.")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be less than or equal to max.")
        return self


class ListSearchAdGroupKeywordsRequest(StrictRequestModel):
    start_index: int = Field(
        default=1,
        description="One-based position in the result set from which to start the traversal. The first item is 1.",
        ge=1,
    )
    base_account_id: int = Field(
        description=(
            "Search Ads baseAccountId used as the x-z-base-account-id context. "
            "Use a value returned by list_accessible_search_base_accounts."
        )
    )
    account_id: int = Field(
        description=(
            "Target Search Ads account ID whose ad group keywords are listed. "
            "Use a value returned by list_accessible_search_accounts."
        )
    )
    use: AdGroupCriterionServiceUse = Field(
        description="Keyword use to list: BIDDABLE for bid keywords or NEGATIVE for negative keywords."
    )
    ad_group_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} ad group IDs.",
    )
    approval_statuses: list[AdGroupCriterionServiceApprovalStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Keyword approval statuses to filter by.",
    )
    portfolio_bidding_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} portfolio bidding IDs.",
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    contains_label: bool | SkipJsonSchema[None] = Field(
        default=None,
        description="Whether returned keywords should include label details. Omit to use the API default of false.",
    )
    criterion_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} keyword criterion IDs.",
    )
    label_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} label IDs.",
    )
    user_statuses: list[AdGroupCriterionServiceUserStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Keyword user statuses to filter by.",
    )
    keyword: SearchAdGroupKeywordFilter | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter by keyword text, match type, or both.",
    )
    bidding_keyword_cpc_range: SearchAdGroupKeywordCpcRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter by keyword bid amount range.",
    )


class SearchAdGroupKeywordItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the Search Ads API request context.")
    account_id: int | None = Field(default=None, description="Search Ads account ID that owns the keyword.")
    campaign_id: int | None = Field(default=None, description="Campaign ID that owns the keyword.")
    campaign_name: str | None = Field(default=None, description="Campaign name that owns the keyword.")
    campaign_track_id: int | None = Field(default=None, description="Campaign ID used for tracking.")
    ad_group_id: int | None = Field(default=None, description="Ad group ID that owns the keyword.")
    ad_group_name: str | None = Field(default=None, description="Ad group name that owns the keyword.")
    ad_group_track_id: int | None = Field(default=None, description="Ad group ID used for tracking.")
    criterion_id: int | None = Field(default=None, description="Keyword criterion ID.")
    criterion_track_id: int | None = Field(default=None, description="Keyword criterion ID used for tracking.")
    criterion_type: str | None = Field(default=None, description="Criterion type; currently KEYWORD.")
    keyword: dict[str, Any] | None = Field(default=None, description="Keyword text and match type.")
    use: str | None = Field(default=None, description="Whether the keyword is BIDDABLE or NEGATIVE.")
    biddable_ad_group_criterion: dict[str, Any] | None = Field(
        default=None,
        description="Bid, delivery, review, and destination settings for a biddable keyword.",
    )
    labels: list[dict[str, Any]] | None = Field(default=None, description="Keyword labels when requested.")
    trademark_status: str | None = Field(default=None, description="Keyword trademark review status.")
    invalided_trademarks: list[str] | None = Field(
        default=None,
        description="Trademarks restricted for the keyword.",
    )


async def list_search_ad_group_keywords(
    handlers: SearchHandlers,
    request: ListSearchAdGroupKeywordsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchAdGroupKeywordItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListSearchAdGroupKeywordsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_search_ad_group_keywords(
            handlers, first, start, size
        ),
    )


async def _fetch_search_ad_group_keywords(
    handlers: SearchHandlers,
    request: ListSearchAdGroupKeywordsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchAdGroupKeywordItem]:
    with handlers.api_client() as client:
        api = AdGroupCriterionServiceApi(client)
        response = await asyncio.to_thread(
            api.ad_group_criterion_service_get_post,
            x_z_base_account_id=request.base_account_id,
            ad_group_criterion_service_selector=AdGroupCriterionServiceSelector(
                account_id=request.account_id,
                ad_group_ids=request.ad_group_ids,
                approval_statuses=request.approval_statuses,
                portfolio_bidding_ids=request.portfolio_bidding_ids,
                campaign_ids=request.campaign_ids,
                contains_label_id=_contains_label_id(request.contains_label),
                criterion_ids=request.criterion_ids,
                label_ids=request.label_ids,
                number_results=number_results,
                start_index=start_index,
                use=request.use,
                user_statuses=request.user_statuses,
                keyword=_keyword_filter(request.keyword),
                bidding_keyword_cpc_range=_bidding_keyword_cpc_range(
                    request.bidding_keyword_cpc_range
                ),
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        ad_group_criterion = getattr(value, "ad_group_criterion", None)
        if ad_group_criterion is None:
            raise ToolError(
                "LY Ads Search Ads API returned an ad group keyword entry without keyword data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(ad_group_criterion)
        criterion = item.pop("criterion", None) or {}
        item.update(criterion)
        item["baseAccountId"] = request.base_account_id
        items.append(SearchAdGroupKeywordItem.model_validate(item))
    return PageSlice(items=items, total_count=total)


def _contains_label_id(value: bool | None) -> AdGroupCriterionServiceContainsLabelId | None:
    if value is None:
        return None
    if value:
        return AdGroupCriterionServiceContainsLabelId.TRUE
    return AdGroupCriterionServiceContainsLabelId.FALSE


def _keyword_filter(value: SearchAdGroupKeywordFilter | None) -> AdGroupCriterionServiceKeyword | None:
    if value is None:
        return None
    return AdGroupCriterionServiceKeyword(
        keyword_match_type=value.keyword_match_type,
        text=value.text,
    )


def _bidding_keyword_cpc_range(
    value: SearchAdGroupKeywordCpcRange | None,
) -> AdGroupCriterionServiceBiddingKeywordCpcRange | None:
    if value is None:
        return None
    return AdGroupCriterionServiceBiddingKeywordCpcRange(min=value.min, max=value.max)
