# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_display_ads MCP tool."""

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
    AdGroupAdServiceMainMediaFormat,
    AdGroupAdServiceSelector,
    AdGroupAdServiceUpdatedDateRange,
    AdGroupAdServiceUserStatus,
)
from .base import DisplayHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_display_ads"
_DATE_PATTERN = r"^\d{8}$"


class DisplayAdDateRange(StrictRequestModel):
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
    def validate_range(self) -> DisplayAdDateRange:
        if self.start_date is None and self.end_date is None:
            raise ValueError("Specify at least one of startDate or endDate.")
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("startDate must be earlier than or equal to endDate.")
        return self


class ListDisplayAdsRequest(StrictRequestModel):
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
            "Target Display Ads account ID whose ads are listed. "
            "Use a value returned by list_accessible_display_accounts."
        )
    )
    ad_group_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} ad group IDs.",
    )
    ad_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} ad IDs.",
    )
    approval_statuses: list[AdGroupAdServiceApprovalStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad approval statuses to filter by.",
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    contains_label: bool | SkipJsonSchema[None] = Field(
        default=None,
        description="Whether returned ads should include label details. Omit to use the API default of false.",
    )
    label_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} label IDs.",
    )
    media_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} media IDs.",
    )
    ad_types: list[AdGroupAdServiceAdType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad types to filter by.",
    )
    main_media_formats: list[AdGroupAdServiceMainMediaFormat] | SkipJsonSchema[None] = Field(
        default=None,
        description="Main media formats to filter by.",
    )
    user_statuses: list[AdGroupAdServiceUserStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad user statuses to filter by.",
    )
    created_date_range: DisplayAdDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ads by creation date range.",
    )
    updated_date_range: DisplayAdDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ads by last-updated date range.",
    )


class DisplayAdItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the API request context.")
    account_id: int | None = Field(default=None, description="Display Ads account ID that owns the ad.")
    ad: dict[str, Any] | None = Field(default=None, description="Ad type, media format, creative, and URL details.")
    ad_group_id: int | None = Field(default=None, description="Ad group ID that owns the ad.")
    ad_group_name: str | None = Field(default=None, description="Ad group name that owns the ad.")
    ad_id: int | None = Field(default=None, description="Ad ID.")
    ad_name: str | None = Field(default=None, description="Ad name.")
    approval_status: str | None = Field(default=None, description="Current ad approval status.")
    campaign_id: int | None = Field(default=None, description="Campaign ID that owns the ad.")
    campaign_name: str | None = Field(default=None, description="Campaign name that owns the ad.")
    disapproval_reason_codes: list[str] | None = Field(
        default=None,
        description="Editorial disapproval reason codes.",
    )
    disapproval_reason_description: str | None = Field(
        default=None,
        description="Editorial disapproval reason details.",
    )
    impression_beacon_urls: list[str] | None = Field(
        default=None,
        description="Impression beacon URLs.",
    )
    viewable_impression_beacon_urls: list[str] | None = Field(
        default=None,
        description="Viewable impression beacon URLs.",
    )
    is_remove_impression_beacon_urls: str | None = Field(
        default=None,
        description="Impression beacon URL removal flag returned by the API.",
    )
    is_remove_viewable_impression_beacon_urls: str | None = Field(
        default=None,
        description="Viewable impression beacon URL removal flag returned by the API.",
    )
    is_remove_third_party_tracking_script_url: str | None = Field(
        default=None,
        description="Third-party tracking script URL removal flag returned by the API.",
    )
    labels: list[dict[str, Any]] | None = Field(default=None, description="Ad labels when requested.")
    media_id: int | None = Field(default=None, description="Media ID associated with the ad.")
    third_party_tracking_script_url: str | None = Field(
        default=None,
        description="Third-party tracking script URL.",
    )
    third_party_tracking_vendor: str | None = Field(
        default=None,
        description="Third-party tracking vendor inferred by the API.",
    )
    user_status: str | None = Field(default=None, description="User-configured ad status.")
    created_date: str | None = Field(default=None, description="Ad creation date in yyyyMMdd format.")
    updated_date: str | None = Field(default=None, description="Ad last-updated date in yyyyMMdd format.")


async def list_display_ads(
    handlers: DisplayHandlers,
    request: ListDisplayAdsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[DisplayAdItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListDisplayAdsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_display_ads(handlers, first, start, size),
    )


async def _fetch_display_ads(
    handlers: DisplayHandlers,
    request: ListDisplayAdsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[DisplayAdItem]:
    with handlers.api_client() as client:
        api = AdGroupAdServiceApi(client)
        response = await asyncio.to_thread(
            api.ad_group_ad_service_get_post,
            x_z_base_account_id=request.base_account_id,
            ad_group_ad_service_selector=AdGroupAdServiceSelector(
                account_id=request.account_id,
                ad_group_ids=request.ad_group_ids,
                ad_ids=request.ad_ids,
                approval_statuses=request.approval_statuses,
                campaign_ids=request.campaign_ids,
                contains_label=request.contains_label,
                label_ids=request.label_ids,
                media_ids=request.media_ids,
                ad_types=request.ad_types,
                main_media_formats=request.main_media_formats,
                number_results=number_results,
                start_index=start_index,
                user_statuses=request.user_statuses,
                created_date_range=_created_date_range(request.created_date_range),
                updated_date_range=_updated_date_range(request.updated_date_range),
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        ad_group_ad = getattr(value, "ad_group_ad", None)
        if ad_group_ad is None:
            raise ToolError(
                "LY Ads Display Ads API returned an ad entry without ad data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(ad_group_ad)
        item["baseAccountId"] = request.base_account_id
        items.append(DisplayAdItem.model_validate(item))
    return PageSlice(items=items, total_count=total)


def _created_date_range(value: DisplayAdDateRange | None) -> AdGroupAdServiceCreatedDateRange | None:
    if value is None:
        return None
    return AdGroupAdServiceCreatedDateRange(start_date=value.start_date, end_date=value.end_date)


def _updated_date_range(value: DisplayAdDateRange | None) -> AdGroupAdServiceUpdatedDateRange | None:
    if value is None:
        return None
    return AdGroupAdServiceUpdatedDateRange(start_date=value.start_date, end_date=value.end_date)
