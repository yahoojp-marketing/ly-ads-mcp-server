# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_search_campaign_negative_keywords MCP tool."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastmcp.exceptions import ToolError
from pydantic import Field
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
    CampaignCriterionServiceApi,
    CampaignCriterionServiceSelector,
    CampaignCriterionServiceUse,
)
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_search_campaign_negative_keywords"


class ListSearchCampaignNegativeKeywordsRequest(StrictRequestModel):
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
            "Target Search Ads account ID whose campaign-level negative keywords are listed. "
            "Use a value returned by list_accessible_search_accounts."
        )
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    criterion_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign negative keyword criterion IDs.",
    )


class SearchCampaignNegativeKeywordDetails(McpOutputModel):
    keyword_match_type: str | None = Field(default=None, description="Negative keyword match type.")
    text: str | None = Field(default=None, description="Negative keyword text.")


class SearchCampaignNegativeKeywordCriterion(McpOutputModel):
    criterion_id: int | None = Field(default=None, description="Campaign criterion ID.")
    criterion_track_id: int | None = Field(
        default=None,
        description="Campaign criterion tracking ID; the API normally omits it for negative keywords.",
    )
    criterion_type: str | None = Field(default=None, description="Campaign criterion type.")
    keyword: SearchCampaignNegativeKeywordDetails | None = Field(
        default=None,
        description="Negative keyword text and match type.",
    )


class SearchCampaignNegativeKeywordItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the Search Ads API request context.")
    account_id: int | None = Field(default=None, description="Search Ads account ID that owns the criterion.")
    campaign_id: int | None = Field(default=None, description="Campaign ID that owns the criterion.")
    campaign_name: str | None = Field(default=None, description="Campaign name that owns the criterion.")
    criterion: SearchCampaignNegativeKeywordCriterion | None = Field(
        default=None,
        description="Campaign-level negative keyword criterion.",
    )
    use: str | None = Field(default=None, description="Criterion use, normally NEGATIVE.")


async def list_search_campaign_negative_keywords(
    handlers: SearchHandlers,
    request: ListSearchCampaignNegativeKeywordsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchCampaignNegativeKeywordItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListSearchCampaignNegativeKeywordsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_search_campaign_negative_keywords(
            handlers, first, start, size
        ),
    )


async def _fetch_search_campaign_negative_keywords(
    handlers: SearchHandlers,
    request: ListSearchCampaignNegativeKeywordsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchCampaignNegativeKeywordItem]:
    with handlers.api_client() as client:
        api = CampaignCriterionServiceApi(client)
        response = await asyncio.to_thread(
            api.campaign_criterion_service_get_post,
            x_z_base_account_id=request.base_account_id,
            campaign_criterion_service_selector=CampaignCriterionServiceSelector(
                account_id=request.account_id,
                campaign_ids=request.campaign_ids,
                criterion_ids=request.criterion_ids,
                number_results=number_results,
                start_index=start_index,
                use=CampaignCriterionServiceUse.NEGATIVE,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        campaign_criterion = getattr(value, "campaign_criterion", None)
        if campaign_criterion is None:
            raise ToolError(
                "LY Ads Search Ads API returned a campaign negative keyword entry without campaign criterion data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(campaign_criterion)
        item["baseAccountId"] = request.base_account_id
        items.append(SearchCampaignNegativeKeywordItem.model_validate(item))
    return PageSlice(items=items, total_count=total)
