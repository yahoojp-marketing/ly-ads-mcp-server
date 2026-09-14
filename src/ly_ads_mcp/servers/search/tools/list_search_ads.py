# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_search_ads MCP tool."""

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
    AdGroupAdServiceAdType,
    AdGroupAdServiceApi,
    AdGroupAdServiceApprovalStatus,
    AdGroupAdServiceCreatedDateRange,
    AdGroupAdServiceSelector,
    AdGroupAdServiceUpdatedDateRange,
    AdGroupAdServiceUserStatus,
)
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_search_ads"
_DATE_PATTERN = r"^\d{8}$"


class SearchAdGroupAdDateRange(StrictRequestModel):
    start_date: str | SkipJsonSchema[None] = Field(
        default=None,
        description="Inclusive start date in yyyyMMdd format. Omit when only an end date is needed.",
        pattern=_DATE_PATTERN,
    )
    end_date: str | SkipJsonSchema[None] = Field(
        default=None,
        description="Inclusive end date in yyyyMMdd format. Omit when only a start date is needed.",
        pattern=_DATE_PATTERN,
    )

    @model_validator(mode="after")
    def validate_range(self) -> SearchAdGroupAdDateRange:
        if self.start_date is None and self.end_date is None:
            raise ValueError("Specify at least one of startDate or endDate.")
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("startDate must be earlier than or equal to endDate.")
        return self


class ListSearchAdsRequest(StrictRequestModel):
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
            "Target Search Ads account ID whose ads are listed. "
            "Use a value returned by list_accessible_search_accounts."
        )
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    ad_group_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} ad group IDs.",
    )
    ad_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} ad IDs.",
    )
    ad_types: list[AdGroupAdServiceAdType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad types to filter by.",
    )
    approval_statuses: list[AdGroupAdServiceApprovalStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad approval statuses to filter by.",
    )
    user_statuses: list[AdGroupAdServiceUserStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad user statuses to filter by.",
    )
    contains_label: bool | SkipJsonSchema[None] = Field(
        default=None,
        description="Whether returned ads should include label details. Omit to use the API default of false.",
    )
    label_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} label IDs.",
    )
    created_date_range: SearchAdGroupAdDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ads by creation date range.",
    )
    updated_date_range: SearchAdGroupAdDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ads by last-updated date range.",
    )


class SearchAdGroupAdItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the Search Ads API request context.")
    account_id: int | None = Field(default=None, description="Search Ads account ID that owns the ad.")
    ad: dict[str, Any] | None = Field(default=None, description="Ad creative and destination configuration.")
    ad_group_id: int | None = Field(default=None, description="Ad group ID that owns the ad.")
    ad_group_name: str | None = Field(default=None, description="Ad group name that owns the ad.")
    ad_group_track_id: int | None = Field(default=None, description="Ad group ID used for tracking.")
    ad_id: int | None = Field(default=None, description="Ad ID.")
    ad_name: str | None = Field(default=None, description="Ad name.")
    ad_track_id: int | None = Field(default=None, description="Ad ID used for tracking.")
    approval_status: str | None = Field(default=None, description="Current ad approval status.")
    campaign_id: int | None = Field(default=None, description="Campaign ID that owns the ad.")
    campaign_name: str | None = Field(default=None, description="Campaign name that owns the ad.")
    campaign_track_id: int | None = Field(default=None, description="Campaign ID used for tracking.")
    disapproval_reason_codes: list[str] | None = Field(
        default=None,
        description="Codes explaining why the ad was disapproved.",
    )
    feed_id: int | None = Field(default=None, description="Feed ID associated with the ad.")
    invalided_trademarks: list[str] | None = Field(
        default=None,
        description="Trademarks restricted for the ad.",
    )
    labels: list[dict[str, Any]] | None = Field(default=None, description="Ad labels when requested.")
    trademark_status: str | None = Field(default=None, description="Trademark review status.")
    user_status: str | None = Field(default=None, description="User-configured ad status.")
    created_date: str | None = Field(default=None, description="Ad creation date in yyyyMMdd format.")
    updated_date: str | None = Field(default=None, description="Ad last-updated date in yyyyMMdd format.")


async def list_search_ads(
    handlers: SearchHandlers,
    request: ListSearchAdsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchAdGroupAdItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListSearchAdsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_search_ads(handlers, first, start, size),
    )


async def _fetch_search_ads(
    handlers: SearchHandlers,
    request: ListSearchAdsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchAdGroupAdItem]:
    with handlers.api_client() as client:
        api = AdGroupAdServiceApi(client)
        response = await asyncio.to_thread(
            api.ad_group_ad_service_get_post,
            x_z_base_account_id=request.base_account_id,
            ad_group_ad_service_selector=AdGroupAdServiceSelector(
                account_id=request.account_id,
                campaign_ids=request.campaign_ids,
                ad_group_ids=request.ad_group_ids,
                ad_ids=request.ad_ids,
                ad_types=request.ad_types,
                approval_statuses=request.approval_statuses,
                user_statuses=request.user_statuses,
                contains_label=request.contains_label,
                label_ids=request.label_ids,
                created_date_range=_created_date_range(request.created_date_range),
                updated_date_range=_updated_date_range(request.updated_date_range),
                number_results=number_results,
                start_index=start_index,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        ad_group_ad = getattr(value, "ad_group_ad", None)
        if ad_group_ad is None:
            raise ToolError(
                "LY Ads Search Ads API returned an ad entry without ad data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(ad_group_ad)
        item["baseAccountId"] = request.base_account_id
        items.append(SearchAdGroupAdItem.model_validate(item))
    return PageSlice(items=items, total_count=total)


def _created_date_range(value: SearchAdGroupAdDateRange | None) -> AdGroupAdServiceCreatedDateRange | None:
    if value is None:
        return None
    return AdGroupAdServiceCreatedDateRange(start_date=value.start_date, end_date=value.end_date)


def _updated_date_range(value: SearchAdGroupAdDateRange | None) -> AdGroupAdServiceUpdatedDateRange | None:
    if value is None:
        return None
    return AdGroupAdServiceUpdatedDateRange(start_date=value.start_date, end_date=value.end_date)
