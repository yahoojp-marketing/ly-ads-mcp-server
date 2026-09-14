# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the list_search_labels MCP tool."""

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

from ..client import LabelServiceApi, LabelServiceCountLabeledEntity, LabelServiceSelector
from .base import SearchHandlers

_CURSOR_SCHEMA_VERSION = 1
_TOOL_NAME = "list_search_labels"


class ListSearchLabelsRequest(StrictRequestModel):
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
            "Target Search Ads account ID whose labels are listed. "
            "Use a value returned by list_accessible_search_accounts."
        )
    )
    label_ids: Annotated[list[int], Field(max_length=DEFAULT_PAGE_SIZE)] | SkipJsonSchema[None] = Field(
        default=None,
        description=f"Filter by up to {DEFAULT_PAGE_SIZE} label IDs.",
    )
    count_labeled_entity: LabelServiceCountLabeledEntity | SkipJsonSchema[None] = Field(
        default=None,
        description=(
            "Whether to include the number of campaigns, ad groups, advertisements, and keywords associated "
            "with each label. Omit to use the Search Ads API default."
        ),
    )


class SearchLabelItem(McpOutputModel):
    base_account_id: int = Field(description="Base account ID used as the Search Ads API request context.")
    account_id: int | None = Field(default=None, description="Search Ads account ID that owns the label.")
    label_id: int | None = Field(default=None, description="Label ID.")
    label_name: str | None = Field(default=None, description="Label name.")
    color: str | None = Field(default=None, description="Label color code, such as #FFFFFF.")
    description: str | None = Field(default=None, description="Label description.")
    labeled_campaign: int | None = Field(
        default=None,
        description="Number of campaigns associated with the label when counts are requested.",
    )
    labeled_ad_group: int | None = Field(
        default=None,
        description="Number of ad groups associated with the label when counts are requested.",
    )
    labeled_ad_group_ad: int | None = Field(
        default=None,
        description="Number of advertisements associated with the label when counts are requested.",
    )
    labeled_ad_group_criterion: int | None = Field(
        default=None,
        description="Number of keywords associated with the label when counts are requested.",
    )


async def list_search_labels(
    handlers: SearchHandlers,
    request: ListSearchLabelsRequest | None = None,
    cursor: str | None = None,
) -> PaginatedResult[SearchLabelItem]:
    return await paginate(
        request,
        cursor=cursor,
        cursor_store=handlers.cursor_store,
        auth_fingerprint=handlers.access_token_fingerprint(),
        first_request_type=ListSearchLabelsRequest,
        tool_name=_TOOL_NAME,
        schema_version=_CURSOR_SCHEMA_VERSION,
        fetch_page=lambda first, start, size: _fetch_search_labels(handlers, first, start, size),
    )


async def _fetch_search_labels(
    handlers: SearchHandlers,
    request: ListSearchLabelsRequest,
    start_index: int,
    number_results: int,
) -> PageSlice[SearchLabelItem]:
    with handlers.api_client() as client:
        api = LabelServiceApi(client)
        response = await asyncio.to_thread(
            api.label_service_get_post,
            x_z_base_account_id=request.base_account_id,
            label_service_selector=LabelServiceSelector(
                account_id=request.account_id,
                count_labeled_entity=request.count_labeled_entity,
                label_ids=request.label_ids,
                number_results=number_results,
                start_index=start_index,
            ),
        )

    values, total = extract_rval(response)
    items = []
    for value in values:
        label = getattr(value, "label", None)
        if label is None:
            raise ToolError(
                "LY Ads Search Ads API returned a label entry without label data. "
                "Retry the request; if it persists, report the upstream API response."
            )
        item = to_plain_dict(label)
        item["baseAccountId"] = request.base_account_id
        items.append(SearchLabelItem.model_validate(item))
    return PageSlice(items=items, total_count=total)
