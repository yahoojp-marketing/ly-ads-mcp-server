# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_accessible_search_base_accounts MCP tool."""

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
    BaseAccountServiceAccountStatus,
    BaseAccountServiceApi,
    BaseAccountServiceAuthType,
    BaseAccountServiceHasAdminAuth,
    BaseAccountServiceIncludeAdminAuth,
    BaseAccountServiceIncludeMccAccount,
    BaseAccountServiceIncludeSsaAccount,
    BaseAccountServiceIncludeTestAccount,
    BaseAccountServiceIsMccAccount,
    BaseAccountServiceIsRootMccAccount,
    BaseAccountServiceIsSsaAccount,
    BaseAccountServiceIsTestAccount,
    BaseAccountServiceSelector,
)
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_accessible_search_base_accounts"


class ListAccessibleSearchBaseAccountsRequest(StrictRequestModel):
    start_index: int = Field(
        default=1,
        description="One-based position in the result set from which to start the traversal. The first item is 1.",
        ge=1,
    )
    account_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} base account IDs.",
    )
    account_name: str | SkipJsonSchema[None] = Field(
        default=None,
        description="Optional account name filter (partial match).",
    )
    account_statuses: list[BaseAccountServiceAccountStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Base account statuses to filter by.",
    )
    auth_type: BaseAccountServiceAuthType | SkipJsonSchema[None] = Field(
        default=None,
        description="Filter by auth type granted to the authenticated user.",
    )
    include_admin_auth: BaseAccountServiceIncludeAdminAuth | SkipJsonSchema[None] = Field(
        default=None,
        description="Admin auth inclusion filter.",
    )
    include_mcc_account: BaseAccountServiceIncludeMccAccount | SkipJsonSchema[None] = Field(
        default=None,
        description="MCC account inclusion filter.",
    )
    include_test_account: BaseAccountServiceIncludeTestAccount | SkipJsonSchema[None] = Field(
        default=None,
        description="Test account inclusion filter.",
    )


class SearchBaseAccountItem(McpOutputModel):
    account_id: int | None = Field(default=None, alias="accountId", description="Base account ID.")
    account_name: str | None = Field(default=None, alias="accountName", description="Base account name.")
    account_status: BaseAccountServiceAccountStatus | None = Field(default=None, alias="accountStatus")
    auth_type: BaseAccountServiceAuthType | None = Field(default=None, alias="authType")
    has_admin_auth: BaseAccountServiceHasAdminAuth | None = Field(default=None, alias="hasAdminAuth")
    is_root_mcc_account: BaseAccountServiceIsRootMccAccount | None = Field(
        default=None, alias="isRootMccAccount"
    )
    is_mcc_account: BaseAccountServiceIsMccAccount | None = Field(default=None, alias="isMccAccount")
    is_test_account: BaseAccountServiceIsTestAccount | None = Field(default=None, alias="isTestAccount")
    is_ssa_account: BaseAccountServiceIsSsaAccount | None = Field(
        default=None,
        alias="isSsaAccount",
        description="Whether the returned base account is a Shopping Search Ads account.",
    )


async def list_accessible_search_base_accounts(
    handlers: SearchHandlers,
    request: ListAccessibleSearchBaseAccountsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchBaseAccountItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListAccessibleSearchBaseAccountsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_accessible_search_base_accounts(
            handlers, first, start, size
        ),
    )


async def _fetch_accessible_search_base_accounts(
    handlers: SearchHandlers,
    request: ListAccessibleSearchBaseAccountsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchBaseAccountItem]:
    with handlers.api_client() as client:
        api = BaseAccountServiceApi(client)
        response = await asyncio.to_thread(
            api.base_account_service_get_post,
            base_account_service_selector=BaseAccountServiceSelector(
                number_results=number_results,
                start_index=start_index,
                account_name=request.account_name,
                account_ids=request.account_ids,
                account_statuses=request.account_statuses,
                auth_type=request.auth_type,
                include_admin_auth=request.include_admin_auth,
                include_mcc_account=request.include_mcc_account,
                include_test_account=request.include_test_account,
                include_ssa_account=BaseAccountServiceIncludeSsaAccount.EXCLUDE_SSA,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        account = getattr(value, "account", None)
        if account is None:
            raise ToolError(
                "LY Ads Search Ads API returned a base-account entry without account data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        items.append(SearchBaseAccountItem.model_validate(to_plain_dict(account)))
    return PageSlice(items=items, total_count=total)
