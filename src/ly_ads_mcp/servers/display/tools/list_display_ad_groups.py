# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_display_ad_groups MCP tool."""

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
    AdGroupServiceApi,
    AdGroupServiceBiddingValueCpcRange,
    AdGroupServiceCreatedDateRange,
    AdGroupServiceSelector,
    AdGroupServiceUpdatedDateRange,
    AdGroupServiceUserStatus,
)
from .base import DisplayHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_display_ad_groups"
_DATE_PATTERN = r"^\d{8}$"


class DisplayAdGroupDateRange(StrictRequestModel):
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
    def validate_range(self) -> DisplayAdGroupDateRange:
        if self.start_date is None and self.end_date is None:
            raise ValueError("Specify at least one of startDate or endDate.")
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("startDate must be earlier than or equal to endDate.")
        return self


class DisplayAdGroupBiddingValueCpcRange(StrictRequestModel):
    min: int | SkipJsonSchema[None] = Field(
        default=None,
        description="Minimum ad group CPC bid value. Omit when only a maximum is needed.",
    )
    max: int | SkipJsonSchema[None] = Field(
        default=None,
        description="Maximum ad group CPC bid value. Omit when only a minimum is needed.",
    )

    @model_validator(mode="after")
    def validate_range(self) -> DisplayAdGroupBiddingValueCpcRange:
        if self.min is None and self.max is None:
            raise ValueError("Specify at least one of min or max.")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be less than or equal to max.")
        return self


class ListDisplayAdGroupsRequest(StrictRequestModel):
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
            "Target Display Ads account ID whose ad groups are listed. "
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
    contains_label: bool | SkipJsonSchema[None] = Field(
        default=None,
        description="Whether returned ad groups should include label details. Omit to use the API default of false.",
    )
    feed_set_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} feed set IDs.",
    )
    label_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} label IDs.",
    )
    user_statuses: list[AdGroupServiceUserStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Ad group user statuses to filter by.",
    )
    created_date_range: DisplayAdGroupDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ad groups by creation date range.",
    )
    updated_date_range: DisplayAdGroupDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ad groups by last-updated date range.",
    )
    bidding_value_cpc_range: DisplayAdGroupBiddingValueCpcRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter ad groups by CPC bid value range.",
    )


class DisplayAdGroupItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the API request context.")
    account_id: int | None = Field(default=None, description="Display Ads account ID that owns the ad group.")
    ad_group_id: int | None = Field(default=None, description="Ad group ID.")
    ad_group_name: str | None = Field(default=None, description="Ad group name.")
    campaign_id: int | None = Field(default=None, description="Campaign ID that owns the ad group.")
    campaign_name: str | None = Field(default=None, description="Campaign name that owns the ad group.")
    bidding_strategy_configuration: dict[str, Any] | None = Field(
        default=None,
        description="Ad group bidding strategy configuration.",
    )
    custom_parameters: dict[str, Any] | None = Field(
        default=None,
        description="Ad group custom tracking parameters.",
    )
    device: list[str] | None = Field(default=None, description="Target device types.")
    device_app: list[str] | None = Field(default=None, description="Target device application types.")
    device_os: list[str] | None = Field(default=None, description="Target device operating systems.")
    device_os_version: str | None = Field(default=None, description="Target device operating system version.")
    feed_set_id: int | None = Field(default=None, description="Feed set ID associated with the ad group.")
    exclude_line_oa_friend_audience_list_id: int | None = Field(
        default=None,
        description="Excluded LINE Official Account friend audience list ID.",
    )
    is_remove_tracking_url: str | None = Field(
        default=None,
        description="Tracking URL removal flag returned by the API.",
    )
    labels: list[dict[str, Any]] | None = Field(default=None, description="Ad group labels when requested.")
    smart_targeting_enabled: str | None = Field(
        default=None,
        description="Whether smart targeting is enabled.",
    )
    tracking_url: str | None = Field(default=None, description="Ad group tracking URL.")
    user_status: str | None = Field(default=None, description="User-configured ad group status.")
    created_date: str | None = Field(default=None, description="Ad group creation date in yyyyMMdd format.")
    updated_date: str | None = Field(default=None, description="Ad group last-updated date in yyyyMMdd format.")


async def list_display_ad_groups(
    handlers: DisplayHandlers,
    request: ListDisplayAdGroupsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[DisplayAdGroupItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListDisplayAdGroupsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_display_ad_groups(handlers, first, start, size),
    )


async def _fetch_display_ad_groups(
    handlers: DisplayHandlers,
    request: ListDisplayAdGroupsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[DisplayAdGroupItem]:
    with handlers.api_client() as client:
        api = AdGroupServiceApi(client)
        response = await asyncio.to_thread(
            api.ad_group_service_get_post,
            x_z_base_account_id=request.base_account_id,
            ad_group_service_selector=AdGroupServiceSelector(
                account_id=request.account_id,
                ad_group_ids=request.ad_group_ids,
                campaign_ids=request.campaign_ids,
                contains_label=request.contains_label,
                feed_set_ids=request.feed_set_ids,
                label_ids=request.label_ids,
                number_results=number_results,
                start_index=start_index,
                user_statuses=request.user_statuses,
                created_date_range=_created_date_range(request.created_date_range),
                updated_date_range=_updated_date_range(request.updated_date_range),
                bidding_value_cpc_range=_bidding_value_cpc_range(request.bidding_value_cpc_range),
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        ad_group = getattr(value, "ad_group", None)
        if ad_group is None:
            raise ToolError(
                "LY Ads Display Ads API returned an ad group entry without ad group data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(ad_group)
        item["baseAccountId"] = request.base_account_id
        items.append(DisplayAdGroupItem.model_validate(item))
    return PageSlice(items=items, total_count=total)


def _created_date_range(value: DisplayAdGroupDateRange | None) -> AdGroupServiceCreatedDateRange | None:
    if value is None:
        return None
    return AdGroupServiceCreatedDateRange(start_date=value.start_date, end_date=value.end_date)


def _updated_date_range(value: DisplayAdGroupDateRange | None) -> AdGroupServiceUpdatedDateRange | None:
    if value is None:
        return None
    return AdGroupServiceUpdatedDateRange(start_date=value.start_date, end_date=value.end_date)


def _bidding_value_cpc_range(
    value: DisplayAdGroupBiddingValueCpcRange | None,
) -> AdGroupServiceBiddingValueCpcRange | None:
    if value is None:
        return None
    return AdGroupServiceBiddingValueCpcRange(min=value.min, max=value.max)
