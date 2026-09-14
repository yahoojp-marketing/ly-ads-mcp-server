# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_search_campaign_targets MCP tool."""

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
    CampaignTargetServiceApi,
    CampaignTargetServiceExcludedType,
    CampaignTargetServicePlatformType,
    CampaignTargetServiceSelector,
    CampaignTargetServiceTargetType,
)
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_search_campaign_targets"


class ListSearchCampaignTargetsRequest(StrictRequestModel):
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
            "Target Search Ads account ID whose campaign targeting settings are listed. "
            "Use a value returned by list_accessible_search_accounts."
        )
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    excluded_type: CampaignTargetServiceExcludedType | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter by whether targets are included in or excluded from ad delivery.",
    )
    platform_types: list[CampaignTargetServicePlatformType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter by target platform types.",
    )
    target_ids: Annotated[list[str], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign target IDs.",
    )
    target_types: list[CampaignTargetServiceTargetType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter by campaign target types.",
    )


class SearchCampaignLocationTarget(McpOutputModel):
    city_name_en: str | None = Field(default=None, alias="cityNameEN", description="City name in English.")
    city_name_ja: str | None = Field(default=None, alias="cityNameJA", description="City name in Japanese.")
    excluded_type: str | None = Field(
        default=None,
        description="Whether the location is included in or excluded from ad delivery.",
    )
    province_name_en: str | None = Field(
        default=None,
        alias="provinceNameEN",
        description="Prefecture name in English.",
    )
    province_name_ja: str | None = Field(
        default=None,
        alias="provinceNameJA",
        description="Prefecture name in Japanese.",
    )
    targeting_status: str | None = Field(default=None, description="Current location targeting status.")


class SearchCampaignNetworkTarget(McpOutputModel):
    network_coverage_type: str | None = Field(default=None, description="Search network coverage type.")


class SearchCampaignPlatformTarget(McpOutputModel):
    platform_type: str | None = Field(default=None, description="Target device platform type.")


class SearchCampaignRadiusTarget(McpOutputModel):
    latitude_in_micro_degrees: int | None = Field(
        default=None,
        description="Center latitude expressed in microdegrees.",
    )
    longitude_in_micro_degrees: int | None = Field(
        default=None,
        description="Center longitude expressed in microdegrees.",
    )
    radius: int | None = Field(default=None, description="Target radius in kilometers.")
    description: str | None = Field(default=None, description="Description of the target location.")


class SearchCampaignScheduleTarget(McpOutputModel):
    day_of_week: str | None = Field(default=None, description="Day of week for scheduled delivery.")
    end_hour: int | None = Field(default=None, description="Ending hour in 24-hour time.")
    end_minute: str | None = Field(default=None, description="Ending minute of the hour.")
    start_hour: int | None = Field(default=None, description="Starting hour in 24-hour time.")
    start_minute: str | None = Field(default=None, description="Starting minute of the hour.")


class SearchCampaignTargetDetail(McpOutputModel):
    location_target: SearchCampaignLocationTarget | None = Field(
        default=None,
        description="Location targeting details when targetType is LOCATION.",
    )
    network_target: SearchCampaignNetworkTarget | None = Field(
        default=None,
        description="Network targeting details when targetType is NETWORK.",
    )
    platform_target: SearchCampaignPlatformTarget | None = Field(
        default=None,
        description="Platform targeting details when targetType is PLATFORM.",
    )
    radius_target: SearchCampaignRadiusTarget | None = Field(
        default=None,
        description="Radius targeting details when targetType is RADIUS.",
    )
    schedule_target: SearchCampaignScheduleTarget | None = Field(
        default=None,
        description="Schedule targeting details when targetType is SCHEDULE.",
    )
    target_id: str | None = Field(default=None, description="Campaign target ID.")
    target_type: str | None = Field(default=None, description="Campaign target type.")


class SearchCampaignTargetItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the Search Ads API request context.")
    account_id: int | None = Field(default=None, description="Search Ads account ID that owns the campaign.")
    bid_multiplier: int | float | None = Field(default=None, description="Bid adjustment multiplier.")
    campaign_id: int | None = Field(default=None, description="Campaign ID.")
    campaign_name: str | None = Field(default=None, description="Campaign name.")
    target: SearchCampaignTargetDetail | None = Field(default=None, description="Campaign targeting details.")


async def list_search_campaign_targets(
    handlers: SearchHandlers,
    request: ListSearchCampaignTargetsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchCampaignTargetItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListSearchCampaignTargetsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_search_campaign_targets(handlers, first, start, size),
    )


async def _fetch_search_campaign_targets(
    handlers: SearchHandlers,
    request: ListSearchCampaignTargetsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchCampaignTargetItem]:
    with handlers.api_client() as client:
        api = CampaignTargetServiceApi(client)
        response = await asyncio.to_thread(
            api.campaign_target_service_get_post,
            x_z_base_account_id=request.base_account_id,
            campaign_target_service_selector=CampaignTargetServiceSelector(
                account_id=request.account_id,
                campaign_ids=request.campaign_ids,
                excluded_type=request.excluded_type,
                platform_types=request.platform_types,
                number_results=number_results,
                start_index=start_index,
                target_ids=request.target_ids,
                target_types=request.target_types,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        campaign_target = getattr(value, "campaign_target", None)
        if campaign_target is None:
            raise ToolError(
                "LY Ads Search Ads API returned a campaign target entry without campaign target data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(campaign_target)
        item["baseAccountId"] = request.base_account_id
        items.append(SearchCampaignTargetItem.model_validate(item))
    return PageSlice(items=items, total_count=total)
