# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_accessible_display_accounts MCP tool."""

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
    AccountServiceApi,
    AccountServiceAutoTaggingEnabled,
    AccountServiceDeliveryStatus,
    AccountServiceIncludeMccAccount,
    AccountServiceIncludeTestAccount,
    AccountServiceIsCancellationPending,
    AccountServiceIsMccAccount,
    AccountServiceIsTestAccount,
    AccountServiceSelector,
    AccountServiceStatus,
    AccountServiceType,
)
from .base import DisplayHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_accessible_display_accounts"


class ListAccessibleDisplayAccountsRequest(StrictRequestModel):
    start_index: int = Field(
        default=1,
        description="One-based position in the result set from which to start the traversal. The first item is 1.",
        ge=1,
    )
    base_account_id: int = Field(
        description=(
            "Display Ads baseAccountId (x-z-base-account-id context). "
            "Use a value returned by list_accessible_display_base_accounts."
        )
    )
    account_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} account IDs.",
    )
    account_name: str | SkipJsonSchema[None] = Field(
        default=None,
        description="Optional account name filter (partial match).",
    )
    account_statuses: list[AccountServiceStatus] | SkipJsonSchema[None] = Field(
        default=None,
        description="Account statuses to filter by. Omit to use the API default.",
    )
    account_types: list[AccountServiceType] | SkipJsonSchema[None] = Field(
        default=None,
        description="Account types to filter by.",
    )
    include_mcc_account: AccountServiceIncludeMccAccount | SkipJsonSchema[None] = Field(
        default=None,
        description="MCC account inclusion filter. Omit to use the API default.",
    )
    include_test_account: AccountServiceIncludeTestAccount | SkipJsonSchema[None] = Field(
        default=None,
        description="Test account inclusion filter. Omit to use the API default.",
    )


class DisplayAccountItem(McpOutputModel):
    base_account_id: int = Field(
        alias="baseAccountId",
        description="Base account ID used as the Display Ads API request context.",
    )
    account_id: int | None = Field(default=None, alias="accountId", description="Ad account ID.")
    account_name: str | None = Field(default=None, alias="accountName", description="Ad account name.")
    account_status: AccountServiceStatus | None = Field(default=None, alias="accountStatus")
    account_type: AccountServiceType | None = Field(default=None, alias="accountType")
    auto_tagging_enabled: AccountServiceAutoTaggingEnabled | None = Field(
        default=None, alias="autoTaggingEnabled"
    )
    delivery_status: AccountServiceDeliveryStatus | None = Field(default=None, alias="deliveryStatus")
    is_test_account: AccountServiceIsTestAccount | None = Field(default=None, alias="isTestAccount")
    is_cancellation_pending: AccountServiceIsCancellationPending | None = Field(
        default=None, alias="isCancellationPending"
    )
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    is_mcc_account: AccountServiceIsMccAccount | None = Field(default=None, alias="isMccAccount")
    contact_biz_id: str | None = Field(default=None, alias="contactBizId")
    optimization_score: float | int | None = Field(default=None, alias="optimizationScore")


async def list_accessible_display_accounts(
    handlers: DisplayHandlers,
    request: ListAccessibleDisplayAccountsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[DisplayAccountItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListAccessibleDisplayAccountsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_accessible_display_accounts(
            handlers, first, start, size
        ),
    )


async def _fetch_accessible_display_accounts(
    handlers: DisplayHandlers,
    request: ListAccessibleDisplayAccountsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[DisplayAccountItem]:
    with handlers.api_client() as client:
        api = AccountServiceApi(client)
        response = await asyncio.to_thread(
            api.account_service_get_post,
            x_z_base_account_id=request.base_account_id,
            account_service_selector=AccountServiceSelector(
                number_results=number_results,
                start_index=start_index,
                account_statuses=request.account_statuses,
                account_types=request.account_types,
                account_name=request.account_name,
                account_ids=request.account_ids,
                include_mcc_account=request.include_mcc_account,
                include_test_account=request.include_test_account,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        account = getattr(value, "account", None)
        if account is None:
            raise ToolError(
                "LY Ads Display Ads API returned an ad-account entry without account data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(account)
        item["baseAccountId"] = request.base_account_id
        items.append(DisplayAccountItem.model_validate(item))
    return PageSlice(items=items, total_count=total)
