# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_display_ad_group_targets MCP tool."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

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
    AdGroupTargetServiceApi,
    AdGroupTargetServiceAreaSearchType,
    AdGroupTargetServiceSelector,
    AdGroupTargetServiceSortField,
    AdGroupTargetServiceSortType,
    AdGroupTargetServiceTargetType,
)
from .base import DisplayHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_display_ad_group_targets"


class ListDisplayAdGroupTargetsRequest(StrictRequestModel):
    start_index: int = Field(
        default=1,
        description="One-based position in the result set from which to start the traversal. The first item is 1.",
        ge=1,
    )
    base_account_id: int = Field(
        description=(
            "Display Ads baseAccountId used as the x-z-base-account-id context. "
            "Use a value returned by list_accessible_display_base_accounts."
        )
    )
    account_id: int = Field(
        description=(
            "Target Display Ads account ID whose ad group targets are listed. "
            "Use a value returned by list_accessible_display_accounts."
        )
    )
    ad_group_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} ad group IDs.",
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    target_types: list[AdGroupTargetServiceTargetType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad group target types to filter by.",
    )
    area_search_types: list[AdGroupTargetServiceAreaSearchType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Geographic area search types to filter by.",
    )
    sort_field: AdGroupTargetServiceSortField | SkipJsonSchema[None] = Field(
        default=None,
        description="Field by which to sort matching ad group targets.",
    )
    sort_type: AdGroupTargetServiceSortType | SkipJsonSchema[None] = Field(
        default=None,
        description="Sort direction for matching ad group targets.",
    )


class DisplayAdGroupTargetItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the API request context.")
    account_id: int | None = Field(default=None, description="Display Ads account ID that owns the target.")
    campaign_id: int | None = Field(default=None, description="Campaign ID that owns the target.")
    ad_group_id: int | None = Field(default=None, description="Ad group ID that owns the target.")
    bid_multiplier: float | int | None = Field(default=None, description="Bid adjustment configured for the target.")
    target: dict[str, Any] | None = Field(default=None, description="Ad group targeting type and its settings.")


async def list_display_ad_group_targets(
    handlers: DisplayHandlers,
    request: ListDisplayAdGroupTargetsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[DisplayAdGroupTargetItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListDisplayAdGroupTargetsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_display_ad_group_targets(handlers, first, start, size),
    )


async def _fetch_display_ad_group_targets(
    handlers: DisplayHandlers,
    request: ListDisplayAdGroupTargetsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[DisplayAdGroupTargetItem]:
    with handlers.api_client() as client:
        api = AdGroupTargetServiceApi(client)
        response = await asyncio.to_thread(
            api.ad_group_target_service_get_post,
            x_z_base_account_id=request.base_account_id,
            ad_group_target_service_selector=AdGroupTargetServiceSelector(
                account_id=request.account_id,
                ad_group_ids=request.ad_group_ids,
                campaign_ids=request.campaign_ids,
                target_types=request.target_types,
                area_search_types=request.area_search_types,
                sort_field=request.sort_field,
                sort_type=request.sort_type,
                number_results=number_results,
                start_index=start_index,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        ad_group_target = getattr(value, "ad_group_target_list", None)
        if ad_group_target is None:
            raise ToolError(
                "LY Ads Display Ads API returned an ad group target entry without ad group target data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(ad_group_target)
        item["baseAccountId"] = request.base_account_id
        items.append(DisplayAdGroupTargetItem.model_validate(item))
    return PageSlice(items=items, total_count=total)
