# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from ly_ads_mcp.config import Settings, get_settings
from ly_ads_mcp.middleware import LyAdsApiErrorMiddleware
from ly_ads_mcp.servers.common.pagination import PaginatedResult, generic_paginated_output_schema
from ly_ads_mcp.servers.common.report_data import LY_ADS_DATA_HANDLING_INSTRUCTIONS

from .tools import get_display_report_fields as get_display_report_fields_tool
from .tools import list_accessible_display_accounts as list_accessible_display_accounts_tool
from .tools import list_accessible_display_base_accounts as list_accessible_display_base_accounts_tool
from .tools import list_display_ad_group_targets as list_display_ad_group_targets_tool
from .tools import list_display_ad_groups as list_display_ad_groups_tool
from .tools import list_display_ads as list_display_ads_tool
from .tools import list_display_campaigns as list_display_campaigns_tool
from .tools import list_display_labels as list_display_labels_tool
from .tools import read_display_report as read_display_report_tool
from .tools.base import DisplayHandlers
from .tools.get_display_report_fields import GetDisplayReportFieldsRequest, GetDisplayReportFieldsResult
from .tools.list_accessible_display_accounts import DisplayAccountItem, ListAccessibleDisplayAccountsRequest
from .tools.list_accessible_display_base_accounts import (
    DisplayBaseAccountItem,
    ListAccessibleDisplayBaseAccountsRequest,
)
from .tools.list_display_ad_group_targets import DisplayAdGroupTargetItem, ListDisplayAdGroupTargetsRequest
from .tools.list_display_ad_groups import DisplayAdGroupItem, ListDisplayAdGroupsRequest
from .tools.list_display_ads import DisplayAdItem, ListDisplayAdsRequest
from .tools.list_display_campaigns import DisplayCampaignItem, ListDisplayCampaignsRequest
from .tools.list_display_labels import DisplayLabelItem, ListDisplayLabelsRequest
from .tools.read_display_report import (
    ReadDisplayReportRequest,
    read_display_report_output_schema,
)

display_server = FastMCP(
    "LY Ads Display Ads",
    mask_error_details=True,
    middleware=[LyAdsApiErrorMiddleware()],
    instructions=(
        "This MCP server is dedicated to LY Ads Display Ads API. "
        "Most Display Ads API calls require a baseAccountId as the x-z-base-account-id header context. "
        "Use list_accessible_display_base_accounts first to discover baseAccountId values. "
        "If baseAccountId is already known, use list_accessible_display_accounts "
        "to verify accountId values under the base account. "
        "Use list_display_campaigns to list campaigns for a verified accountId. "
        "Use list_display_labels to list labels for a verified accountId. "
        "Use list_display_ad_groups to list ad groups for a verified accountId. "
        "Use list_display_ad_group_targets to list targeting settings for Display Ads ad groups. "
        "Use list_display_ads to list ads for a verified accountId. "
        "Use get_display_report_fields to discover fields available for a Display Ads report type. "
        "Use read_display_report to create, wait for, and read a completed Display Ads CSV report. "
        "List tools return one server-sized page at a time. For the first page, pass request and omit cursor. "
        "If nextCursor is present, pass it back unchanged as cursor and omit request; "
        "do not parse or modify it. A missing nextCursor means pagination has stopped. "
        "Do NOT fetch another page unless the user explicitly asks for all results, the next page, "
        "or a specific range. "
        "Do not use UNKNOWN as a value for any enum parameter — it is an internal sentinel value.\n\n"
        f"{LY_ADS_DATA_HANDLING_INSTRUCTIONS}"
    ),
)


def _get_settings() -> Settings:
    return get_settings()


def _get_report_directory() -> Path:
    return _get_settings().report_output_dir / "display"


@lru_cache(maxsize=1)
def _get_handlers() -> DisplayHandlers:
    return DisplayHandlers(_get_settings())


@display_server.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Get Display Ads Report Fields",
    },
)
async def get_display_report_fields(
    request: Annotated[
        GetDisplayReportFieldsRequest,
        Field(description="Display Ads report type and display-name language. Both fields are required."),
    ],
) -> GetDisplayReportFieldsResult:
    """Get fields available for one LY Ads Display Ads report type in the requested language.

    Use this before creating a report definition to discover valid fieldName values, filterable fields, and invalid
    field combinations. Does NOT create, retrieve, or download a report, and does not require a baseAccountId or
    accountId. Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    Both lang and reportType are required.
    """
    return await get_display_report_fields_tool.get_display_report_fields(_get_handlers(), request)


@display_server.tool(
    timeout=80.0,
    output_schema=read_display_report_output_schema(),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "title": "Read Display Ads Report",
    },
)
async def read_display_report(
    request: Annotated[
        ReadDisplayReportRequest,
        Field(
            description=(
                "Display Ads report definition. The server fixes the output to an uncompressed UTF-8 CSV, returns "
                "at most the first 50 records as a preview, and saves the complete CSV to a local file."
            )
        ),
    ],
) -> ToolResult:
    """Create a LY Ads Display Ads CSV report and return its first 50 records plus the complete local file path.

    Calls the Display Ads ReportDefinitionService add, get, and download operations, waiting up to 60 seconds for
    completion. The complete UTF-8 CSV is saved on the machine running this MCP server. file.path is a plain local
    path under LY_ADS_REPORT_OUTPUT_DIR/display/YYYY-MM-DD, not an MCP Resource, and remote or sandboxed clients may
    not be able to read it. The server does not automatically delete saved reports. hasMore only
    indicates that the CSV contains records beyond the 50-record preview; do not call this tool again to retrieve
    them—read file.path.
    Requires baseAccountId and accountId. Use get_display_report_fields first to discover valid fieldName values and
    invalid combinations. IMPORTANT: For ordinary reports, you MUST NOT specify
    request.reportTypeCondition.reportType; omit request.reportTypeCondition entirely. reportTypeCondition is only for
    REACH, CONVERSION_PATH, CROSS_CAMPAIGN_REACHES, and MODEL_COMPARISON reports. For those special reports, supply the
    condition matching reportType. To compare multiple campaigns that share one buying type, such as auction
    campaigns, retrieve 2 to 3 matching campaign IDs and use crossCampaignType CAMPAIGN_ID; CAMPAIGN_BUYING_TYPE is
    only for comparing the AUCTION and GUARANTEED buying-type categories. Do not use UNKNOWN in any enum parameter;
    it is reserved for API responses.
    """
    return await read_display_report_tool.read_display_report(
        _get_handlers(),
        request,
        report_directory=_get_report_directory(),
    )


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Accessible Display Ads Base Accounts",
    },
)
async def list_accessible_display_base_accounts(
    request: Annotated[
        ListAccessibleDisplayBaseAccountsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayBaseAccountItem]:
    """List one page of LY Ads Display Ads base accounts accessible to the authenticated user.

    Does NOT return ad accounts — use list_accessible_display_accounts for those.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if accounts change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
        _get_handlers(), request, cursor
    )


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Accessible Display Ads Accounts",
    },
)
async def list_accessible_display_accounts(
    request: Annotated[
        ListAccessibleDisplayAccountsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayAccountItem]:
    """List one page of LY Ads Display Ads ad accounts under a base account.

    Requires a baseAccountId from list_accessible_display_base_accounts.
    Does NOT list base accounts — use list_accessible_display_base_accounts for those.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if accounts change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        _get_handlers(), request, cursor
    )


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Display Ads Campaigns",
    },
)
async def list_display_campaigns(
    request: Annotated[
        ListDisplayCampaignsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayCampaignItem]:
    """List one page of LY Ads Display Ads campaigns for an ad account.

    Requires a baseAccountId from list_accessible_display_base_accounts and an accountId from
    list_accessible_display_accounts. Does NOT create, update, or delete campaigns.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A
    missing nextCursor means pagination has stopped. Results are best-effort and do not provide a snapshot if
    campaigns change during traversal. Never retrieve another page unless the user explicitly requests all results,
    the next page, or a range.
    """
    return await list_display_campaigns_tool.list_display_campaigns(_get_handlers(), request, cursor)


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Display Ads Labels",
    },
)
async def list_display_labels(
    request: Annotated[
        ListDisplayLabelsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayLabelItem]:
    """List one page of LY Ads Display Ads labels for an ad account.

    Requires a baseAccountId from list_accessible_display_base_accounts and an accountId from
    list_accessible_display_accounts. Does NOT create, update, or delete labels. Use list_display_campaigns,
    list_display_ad_groups, or list_display_ads when those entities rather than label definitions are needed.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if labels change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_display_labels_tool.list_display_labels(_get_handlers(), request, cursor)


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Display Ads Ad Groups",
    },
)
async def list_display_ad_groups(
    request: Annotated[
        ListDisplayAdGroupsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayAdGroupItem]:
    """List one page of LY Ads Display Ads ad groups for an ad account.

    Requires a baseAccountId from list_accessible_display_base_accounts and an accountId from
    list_accessible_display_accounts. Does NOT create, update, or delete ad groups. Use list_display_campaigns
    when campaign information rather than ad group information is needed.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if ad groups change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_display_ad_groups_tool.list_display_ad_groups(_get_handlers(), request, cursor)


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Display Ads Ad Group Targets",
    },
)
async def list_display_ad_group_targets(
    request: Annotated[
        ListDisplayAdGroupTargetsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayAdGroupTargetItem]:
    """List one page of LY Ads Display Ads targeting settings for ad groups in an ad account.

    Requires a baseAccountId from list_accessible_display_base_accounts and an accountId from
    list_accessible_display_accounts. Does NOT add, update, replace, or remove targeting settings. Use
    list_display_ad_groups when ad group information rather than targeting settings is needed.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if targeting settings change during traversal. Never retrieve another page unless
    the user explicitly requests all results, the next page, or a range.
    """
    return await list_display_ad_group_targets_tool.list_display_ad_group_targets(_get_handlers(), request, cursor)


@display_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Display Ads Advertisements",
    },
)
async def list_display_ads(
    request: Annotated[
        ListDisplayAdsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | SkipJsonSchema[None],
        Field(
            description="Opaque nextCursor returned by the previous call. Pass it unchanged and omit request.",
            min_length=1,
            max_length=256,
        ),
    ] = None,
) -> PaginatedResult[DisplayAdItem]:
    """List one page of ads in an LY Ads Display Ads ad account.

    Requires a baseAccountId from list_accessible_display_base_accounts and an accountId from
    list_accessible_display_accounts. Does NOT create, update, or delete ads. Use list_display_ad_groups or
    list_display_campaigns when ad group or campaign information is needed. Does NOT return guaranteed ads.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if ads change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_display_ads_tool.list_display_ads(_get_handlers(), request, cursor)
