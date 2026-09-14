# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_search_campaigns MCP tool."""

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
    CampaignServiceApi,
    CampaignServiceBudgetAmountRange,
    CampaignServiceCreatedDateRange,
    CampaignServiceSelector,
    CampaignServiceUpdatedDateRange,
    CampaignServiceUserStatus,
)
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_search_campaigns"
_DATE_PATTERN = r"^\d{8}$"


class SearchCampaignDateRange(StrictRequestModel):
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
    def validate_range(self) -> SearchCampaignDateRange:
        if self.start_date is None and self.end_date is None:
            raise ValueError("Specify at least one of startDate or endDate.")
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("startDate must be earlier than or equal to endDate.")
        return self


class SearchCampaignBudgetAmountRange(StrictRequestModel):
    min: int | SkipJsonSchema[None] = Field(
        default=None,
        description="Minimum campaign budget amount. Omit when only a maximum is needed.",
    )
    max: int | SkipJsonSchema[None] = Field(
        default=None,
        description="Maximum campaign budget amount. Omit when only a minimum is needed.",
    )

    @model_validator(mode="after")
    def validate_range(self) -> SearchCampaignBudgetAmountRange:
        if self.min is None and self.max is None:
            raise ValueError("Specify at least one of min or max.")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be less than or equal to max.")
        return self


class ListSearchCampaignsRequest(StrictRequestModel):
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
            "Target Search Ads account ID whose campaigns are listed. "
            "Use a value returned by list_accessible_search_accounts."
        )
    )
    campaign_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} campaign IDs.",
    )
    campaign_budget_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} shared campaign budget IDs.",
    )
    portfolio_bidding_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} portfolio bidding IDs.",
    )
    contains_label: bool | SkipJsonSchema[None] = Field(
        default=None,
        description="Whether returned campaigns should include label details. Omit to use the API default of false.",
    )
    label_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} label IDs.",
    )
    user_statuses: list[CampaignServiceUserStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Campaign user statuses to filter by.",
    )
    created_date_range: SearchCampaignDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter campaigns by creation date range.",
    )
    updated_date_range: SearchCampaignDateRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter campaigns by last-updated date range.",
    )
    budget_amount_range: SearchCampaignBudgetAmountRange | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter campaigns by budget amount range.",
    )


class SearchCampaignItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the Search Ads API request context.")
    account_id: int | None = Field(default=None, description="Search Ads account ID that owns the campaign.")
    campaign_id: int | None = Field(default=None, description="Campaign ID.")
    campaign_name: str | None = Field(default=None, description="Campaign name.")
    campaign_track_id: int | None = Field(default=None, description="Campaign ID used for tracking.")
    type: str | None = Field(default=None, description="Campaign type.")
    user_status: str | None = Field(default=None, description="User-configured campaign status.")
    serving_status: str | None = Field(default=None, description="Current campaign serving status.")
    budget: dict[str, Any] | None = Field(default=None, description="Campaign budget configuration.")
    bidding_strategy_configuration: dict[str, Any] | None = Field(
        default=None,
        description="Campaign or portfolio bidding strategy configuration.",
    )
    failed_bidding_strategy_configuration: dict[str, Any] | None = Field(
        default=None,
        description="Bidding strategy configuration that failed to apply.",
    )
    bidding_strategy_failed_reason: str | None = Field(
        default=None,
        description="Reason the bidding strategy configuration failed.",
    )
    conversion_optimizer_eligibility: str | None = Field(
        default=None,
        description="Campaign eligibility for conversion optimization.",
    )
    conversion_setting: dict[str, Any] | None = Field(
        default=None,
        description="Campaign conversion settings.",
    )
    custom_parameters: dict[str, Any] | None = Field(
        default=None,
        description="Campaign custom tracking parameters.",
    )
    app_id: str | None = Field(default=None, description="Application ID or Android package name.")
    app_os_type: str | None = Field(default=None, description="Application operating system type.")
    start_date: str | None = Field(default=None, description="Campaign start date in yyyyMMdd format.")
    end_date: str | None = Field(default=None, description="Campaign end date in yyyyMMdd format.")
    tracking_url: str | None = Field(default=None, description="Campaign tracking URL.")
    labels: list[dict[str, Any]] | None = Field(default=None, description="Campaign labels when requested.")
    settings: list[dict[str, Any]] | None = Field(default=None, description="Campaign settings.")
    url_review_data: dict[str, Any] | None = Field(default=None, description="URL review information.")
    enable_ai_setting: str | None = Field(default=None, description="AI keyword expansion setting.")
    created_date: str | None = Field(default=None, description="Campaign creation date in yyyyMMdd format.")
    updated_date: str | None = Field(default=None, description="Campaign last-updated date in yyyyMMdd format.")


async def list_search_campaigns(
    handlers: SearchHandlers,
    request: ListSearchCampaignsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchCampaignItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListSearchCampaignsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_search_campaigns(handlers, first, start, size),
    )


async def _fetch_search_campaigns(
    handlers: SearchHandlers,
    request: ListSearchCampaignsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchCampaignItem]:
    with handlers.api_client() as client:
        api = CampaignServiceApi(client)
        response = await asyncio.to_thread(
            api.campaign_service_get_post,
            x_z_base_account_id=request.base_account_id,
            campaign_service_selector=CampaignServiceSelector(
                account_id=request.account_id,
                portfolio_bidding_ids=request.portfolio_bidding_ids,
                campaign_ids=request.campaign_ids,
                campaign_budget_ids=request.campaign_budget_ids,
                contains_label=request.contains_label,
                label_ids=request.label_ids,
                number_results=number_results,
                start_index=start_index,
                user_statuses=request.user_statuses,
                created_date_range=_created_date_range(request.created_date_range),
                updated_date_range=_updated_date_range(request.updated_date_range),
                budget_amount_range=_budget_amount_range(request.budget_amount_range),
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        campaign = getattr(value, "campaign", None)
        if campaign is None:
            raise ToolError(
                "LY Ads Search Ads API returned a campaign entry without campaign data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(campaign)
        item["baseAccountId"] = request.base_account_id
        items.append(SearchCampaignItem.model_validate(item))
    return PageSlice(items=items, total_count=total)


def _created_date_range(value: SearchCampaignDateRange | None) -> CampaignServiceCreatedDateRange | None:
    if value is None:
        return None
    return CampaignServiceCreatedDateRange(start_date=value.start_date, end_date=value.end_date)


def _updated_date_range(value: SearchCampaignDateRange | None) -> CampaignServiceUpdatedDateRange | None:
    if value is None:
        return None
    return CampaignServiceUpdatedDateRange(start_date=value.start_date, end_date=value.end_date)


def _budget_amount_range(
    value: SearchCampaignBudgetAmountRange | None,
) -> CampaignServiceBudgetAmountRange | None:
    if value is None:
        return None
    return CampaignServiceBudgetAmountRange(min=value.min, max=value.max)
