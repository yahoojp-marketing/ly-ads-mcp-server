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

from .tools import get_search_report_fields as get_search_report_fields_tool
from .tools import list_accessible_search_accounts as list_accessible_search_accounts_tool
from .tools import list_accessible_search_base_accounts as list_accessible_search_base_accounts_tool
from .tools import list_search_ad_group_keywords as list_search_ad_group_keywords_tool
from .tools import list_search_ad_groups as list_search_ad_groups_tool
from .tools import list_search_ads as list_search_ads_tool
from .tools import list_search_campaign_negative_keywords as list_search_campaign_negative_keywords_tool
from .tools import list_search_campaign_targets as list_search_campaign_targets_tool
from .tools import list_search_campaigns as list_search_campaigns_tool
from .tools import list_search_labels as list_search_labels_tool
from .tools import read_search_report as read_search_report_tool
from .tools.base import SearchHandlers
from .tools.get_search_report_fields import GetSearchReportFieldsRequest, GetSearchReportFieldsResult
from .tools.list_accessible_search_accounts import ListAccessibleSearchAccountsRequest, SearchAccountItem
from .tools.list_accessible_search_base_accounts import (
    ListAccessibleSearchBaseAccountsRequest,
    SearchBaseAccountItem,
)
from .tools.list_search_ad_group_keywords import (
    ListSearchAdGroupKeywordsRequest,
    SearchAdGroupKeywordItem,
)
from .tools.list_search_ad_groups import ListSearchAdGroupsRequest, SearchAdGroupItem
from .tools.list_search_ads import ListSearchAdsRequest, SearchAdGroupAdItem
from .tools.list_search_campaign_negative_keywords import (
    ListSearchCampaignNegativeKeywordsRequest,
    SearchCampaignNegativeKeywordItem,
)
from .tools.list_search_campaign_targets import (
    ListSearchCampaignTargetsRequest,
    SearchCampaignTargetItem,
)
from .tools.list_search_campaigns import ListSearchCampaignsRequest, SearchCampaignItem
from .tools.list_search_labels import ListSearchLabelsRequest, SearchLabelItem
from .tools.read_search_report import (
    ReadSearchReportRequest,
    read_search_report_output_schema,
)

search_server = FastMCP(
    "LY Ads Search Ads",
    mask_error_details=True,
    middleware=[LyAdsApiErrorMiddleware()],
    instructions=(
        "This MCP server is dedicated to LY Ads Search Ads API. "
        "Most Search Ads API calls require a baseAccountId as the x-z-base-account-id header context. "
        "Use list_accessible_search_base_accounts first to discover baseAccountId values. "
        "Shopping Search Ads (SSA) accounts are outside this server's scope and are always excluded. "
        "If baseAccountId is already known, use list_accessible_search_accounts "
        "to verify accountId values under the base account. "
        "Use list_search_campaigns to list campaigns for a verified accountId. "
        "Use list_search_campaign_targets to list campaign targeting settings for a verified accountId. "
        "Use list_search_campaign_negative_keywords to list campaign-level negative keywords. "
        "Use list_search_ad_groups to list ad groups for a verified accountId. "
        "Use list_search_ad_group_keywords to list biddable or negative keywords assigned to ad groups. "
        "Use list_search_ads to list ads for a verified accountId. "
        "Use list_search_labels to list labels for a verified accountId. "
        "Use get_search_report_fields before creating a report definition to discover the fields available "
        "for a Search Ads report type. "
        "Use read_search_report to create, wait for, and read a completed Search Ads CSV report. "
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
    return _get_settings().report_output_dir / "search"


@lru_cache(maxsize=1)
def _get_handlers() -> SearchHandlers:
    return SearchHandlers(_get_settings())


@search_server.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Get Search Ads Report Fields",
    },
)
async def get_search_report_fields(
    request: Annotated[
        GetSearchReportFieldsRequest,
        Field(description="LY Ads Search Ads report type whose available fields should be retrieved."),
    ],
) -> GetSearchReportFieldsResult:
    """Get fields available for one LY Ads Search Ads report type.

    Use this before creating a Search Ads report definition to determine selectable and filterable fields and
    field combinations that are not allowed. Does NOT create, run, or download a report. Shopping Search Ads
    (SSA) report fields are outside this server's scope.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    Choose a concrete reportType value other than UNKNOWN.
    """
    return await get_search_report_fields_tool.get_search_report_fields(_get_handlers(), request)


@search_server.tool(
    timeout=80.0,
    output_schema=read_search_report_output_schema(),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "title": "Read Search Ads Report",
    },
)
async def read_search_report(
    request: Annotated[
        ReadSearchReportRequest,
        Field(
            description=(
                "Search Ads report definition. The server fixes the output to an uncompressed UTF-8 CSV, returns "
                "at most the first 50 records as a preview, and saves the complete CSV to a local file."
            )
        ),
    ],
) -> ToolResult:
    """Create a LY Ads Search Ads CSV report and return its first 50 records plus the complete local file path.

    Calls the Search Ads ReportDefinitionService add, get, and download operations, waiting up to 60 seconds for
    completion. The complete UTF-8 CSV is saved on the machine running this MCP server. file.path is a plain local
    path under LY_ADS_REPORT_OUTPUT_DIR/search/YYYY-MM-DD, not an MCP Resource, and remote or sandboxed clients may
    not be able to read it. The server does not automatically delete saved reports. hasMore only
    indicates that the CSV contains records beyond the 50-record preview; do not call this tool again to retrieve
    them—read file.path.
    Requires a baseAccountId, accountId, reportType, reportName, and fields. Use get_search_report_fields first to
    discover valid fieldName values and invalid combinations. reportDateRangeType is required except for
    BID_MODIFIER reports, where it and dateRange must be omitted. Do not use UNKNOWN in any enum parameter; it is
    reserved for API responses. Choose a concrete reportType value other than UNKNOWN. If no filter is intended,
    omit the parameter. Shopping Search Ads (SSA) reports are outside this tool's scope.
    """
    return await read_search_report_tool.read_search_report(
        _get_handlers(),
        request,
        report_directory=_get_report_directory(),
    )


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Accessible Search Ads Base Accounts",
    },
)
async def list_accessible_search_base_accounts(
    request: Annotated[
        ListAccessibleSearchBaseAccountsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size and always excludes Shopping Search Ads accounts."
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
) -> PaginatedResult[SearchBaseAccountItem]:
    """List one page of LY Ads Search Ads base accounts accessible to the authenticated user.

    Shopping Search Ads (SSA) accounts are always excluded because this server does not support that product.
    Does NOT return ad accounts — use list_accessible_search_accounts for those.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if accounts change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_accessible_search_base_accounts_tool.list_accessible_search_base_accounts(
        _get_handlers(), request, cursor
    )


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Accessible Search Ads Accounts",
    },
)
async def list_accessible_search_accounts(
    request: Annotated[
        ListAccessibleSearchAccountsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchAccountItem]:
    """List one page of LY Ads Search Ads ad accounts under a base account.

    Requires a baseAccountId from list_accessible_search_base_accounts.
    Does NOT list base accounts — use list_accessible_search_base_accounts for those.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if accounts change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_accessible_search_accounts_tool.list_accessible_search_accounts(
        _get_handlers(), request, cursor
    )


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Campaigns",
    },
)
async def list_search_campaigns(
    request: Annotated[
        ListSearchCampaignsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchCampaignItem]:
    """List one page of LY Ads Search Ads campaigns for an ad account.

    Requires a baseAccountId from list_accessible_search_base_accounts and an accountId from
    list_accessible_search_accounts. Does NOT create, update, or delete campaigns.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if campaigns change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_search_campaigns_tool.list_search_campaigns(_get_handlers(), request, cursor)


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Labels",
    },
)
async def list_search_labels(
    request: Annotated[
        ListSearchLabelsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchLabelItem]:
    """List one page of LY Ads Search Ads labels for an ad account.

    Requires a baseAccountId from list_accessible_search_base_accounts and an accountId from
    list_accessible_search_accounts. Does NOT create, update, or delete labels.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if labels change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_search_labels_tool.list_search_labels(_get_handlers(), request, cursor)


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Campaign Targets",
    },
)
async def list_search_campaign_targets(
    request: Annotated[
        ListSearchCampaignTargetsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchCampaignTargetItem]:
    """List one page of LY Ads Search Ads campaign targeting settings for an ad account.

    Requires a baseAccountId from list_accessible_search_base_accounts and an accountId from
    list_accessible_search_accounts. Use list_search_campaigns when campaign information is needed instead.
    Does NOT create, update, or delete campaign targeting settings.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if campaign targeting settings change during traversal. Never retrieve another page
    unless the user explicitly requests all results, the next page, or a range.
    """
    return await list_search_campaign_targets_tool.list_search_campaign_targets(
        _get_handlers(), request, cursor
    )


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Campaign Negative Keywords",
    },
)
async def list_search_campaign_negative_keywords(
    request: Annotated[
        ListSearchCampaignNegativeKeywordsRequest | SkipJsonSchema[None],
        Field(
            description=(
                "Filters and starting position for the first page. Pass this and omit cursor for an initial request. "
                "The server determines the page size and always retrieves negative criteria."
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
) -> PaginatedResult[SearchCampaignNegativeKeywordItem]:
    """List one page of LY Ads Search Ads campaign-level negative keywords for an ad account.

    Requires a baseAccountId from list_accessible_search_base_accounts and an accountId from
    list_accessible_search_accounts. Does NOT return positive keywords, ad-group-level negative keywords,
    or campaign details; use list_search_campaigns when campaign information is needed.
    Does NOT add or remove negative keywords.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if negative keywords change during traversal. Never retrieve another page unless
    the user explicitly requests all results, the next page, or a range.
    """
    return await list_search_campaign_negative_keywords_tool.list_search_campaign_negative_keywords(
        _get_handlers(), request, cursor
    )


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Ad Groups",
    },
)
async def list_search_ad_groups(
    request: Annotated[
        ListSearchAdGroupsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchAdGroupItem]:
    """List one page of LY Ads Search Ads ad groups for an ad account.

    Requires a baseAccountId from list_accessible_search_base_accounts and an accountId from
    list_accessible_search_accounts. Use list_search_campaigns when campaign information is needed instead.
    Does NOT create, update, or delete ad groups.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if ad groups change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_search_ad_groups_tool.list_search_ad_groups(_get_handlers(), request, cursor)


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Ad Group Keywords",
    },
)
async def list_search_ad_group_keywords(
    request: Annotated[
        ListSearchAdGroupKeywordsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchAdGroupKeywordItem]:
    """List one page of LY Ads Search Ads keywords assigned to ad groups.

    Requires a baseAccountId from list_accessible_search_base_accounts, an accountId from
    list_accessible_search_accounts, and use set to BIDDABLE or NEGATIVE. Use list_search_ad_groups when ad group
    information is needed instead. Does NOT list campaign-level negative keywords or create, update, or remove
    keywords.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if keywords change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_search_ad_group_keywords_tool.list_search_ad_group_keywords(
        _get_handlers(), request, cursor
    )


@search_server.tool(
    output_schema=generic_paginated_output_schema(),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "List Search Ads Advertisements",
    },
)
async def list_search_ads(
    request: Annotated[
        ListSearchAdsRequest | SkipJsonSchema[None],
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
) -> PaginatedResult[SearchAdGroupAdItem]:
    """List one page of LY Ads Search Ads advertisements for an ad account.

    Requires a baseAccountId from list_accessible_search_base_accounts and an accountId from
    list_accessible_search_accounts. Use list_search_ad_groups when ad group information is needed instead.
    Does NOT create, update, or delete ads.
    Do not use UNKNOWN in any enum parameter; it is reserved for API responses.
    If no filter is intended, omit the parameter.
    For the first page, pass request and omit cursor. For a following page, pass the previous nextCursor unchanged
    as cursor and omit request. A missing nextCursor means pagination has stopped. Results are best-effort and
    do not provide a snapshot if ads change during traversal. Never retrieve another page unless the user
    explicitly requests all results, the next page, or a range.
    """
    return await list_search_ads_tool.list_search_ads(_get_handlers(), request, cursor)
