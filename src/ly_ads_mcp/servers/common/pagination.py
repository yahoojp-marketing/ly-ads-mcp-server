# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from enum import Enum
from threading import Lock
from typing import Any, Generic, TypeVar

from fastmcp.exceptions import ToolError
from fastmcp.utilities.json_schema import compress_schema
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_serializer
from pydantic.alias_generators import to_camel

T = TypeVar("T")
FirstRequestT = TypeVar("FirstRequestT", bound=BaseModel)
ItemT = TypeVar("ItemT")

DEFAULT_PAGE_SIZE = 50


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class CursorErrorReason(str, Enum):
    UNKNOWN = "unknown"
    EXPIRED = "expired"
    TOOL_MISMATCH = "tool_mismatch"
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    AUTH_MISMATCH = "auth_mismatch"


class CursorError(Exception):
    def __init__(self, reason: CursorErrorReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CursorState:
    tool_name: str
    schema_version: int
    auth_fingerprint: str
    query: dict[str, Any]
    start_index: int
    number_results: int
    expires_at: float | None = None

    def __post_init__(self) -> None:
        if self.start_index < 1:
            raise ValueError("start_index must be greater than or equal to 1")
        if self.number_results < 1:
            raise ValueError("number_results must be greater than or equal to 1")


@dataclass(frozen=True, slots=True)
class PageSlice(Generic[T]):
    items: list[T]
    total_count: int


class McpOutputModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    @model_serializer(mode="wrap")
    def _omit_none(self, handler):
        return {key: value for key, value in handler(self).items() if value is not None}


class PaginatedResult(McpOutputModel, Generic[T]):
    items: list[T] = Field(description="Items returned in this page.")
    total_count: int = Field(
        alias="totalCount",
        description="Total number of matching entries reported by the upstream API.",
        ge=0,
    )
    next_cursor: str | None = Field(
        default=None,
        alias="nextCursor",
        description=(
            "Opaque cursor for the next page. Only when the user explicitly requests the next page, all results, "
            "or a specific range, pass it back unchanged as the top-level cursor and omit request. Do not fetch "
            "another page otherwise. Its absence means the end of the result set has been reached."
        ),
    )


def generic_paginated_output_schema() -> dict[str, Any]:
    """Build the public paginated output schema without entity-specific item fields."""
    schema = TypeAdapter(PaginatedResult[dict[str, Any]]).json_schema(
        mode="serialization",
        by_alias=True,
    )
    return compress_schema(schema, prune_titles=True)


class InMemoryCursorStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = 15 * 60,
        max_entries: int = 1_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, CursorState] = OrderedDict()
        self._lock = Lock()

    def issue(self, state: CursorState) -> str:
        now = self._clock()
        stored_state = replace(
            deepcopy(state),
            expires_at=now + self._ttl_seconds,
        )
        with self._lock:
            self._purge_expired(now)
            while len(self._entries) >= self._max_entries:
                self._entries.popitem(last=False)
            cursor = secrets.token_urlsafe(32)
            while cursor in self._entries:
                cursor = secrets.token_urlsafe(32)
            self._entries[cursor] = stored_state
        return cursor

    def resolve(
        self,
        cursor: str,
        *,
        tool_name: str,
        schema_version: int,
        auth_fingerprint: str,
    ) -> CursorState:
        now = self._clock()
        with self._lock:
            stored = self._entries.get(cursor)
            if stored is None:
                raise CursorError(CursorErrorReason.UNKNOWN)
            state = stored
            if state.expires_at is None or state.expires_at <= now:
                del self._entries[cursor]
                raise CursorError(CursorErrorReason.EXPIRED)
            if state.tool_name != tool_name:
                raise CursorError(CursorErrorReason.TOOL_MISMATCH)
            if state.schema_version != schema_version:
                raise CursorError(CursorErrorReason.SCHEMA_VERSION_MISMATCH)
            if not secrets.compare_digest(state.auth_fingerprint, auth_fingerprint):
                raise CursorError(CursorErrorReason.AUTH_MISMATCH)
            self._entries.move_to_end(cursor)
            return deepcopy(state)

    def _purge_expired(self, now: float) -> None:
        expired = [
            cursor
            for cursor, stored in self._entries.items()
            if stored.expires_at is None or stored.expires_at <= now
        ]
        for cursor in expired:
            del self._entries[cursor]


def ensure_page_progress(items: Sequence[object], total_count: int, start_index: int) -> None:
    if not items and start_index <= total_count:
        raise ToolError(
            "LY Ads API returned an empty page before the end of the result set. "
            "Retry the request; if it persists, report the upstream API response."
        )


async def paginate(
    request: FirstRequestT | None,
    *,
    cursor: str | None,
    cursor_store: InMemoryCursorStore,
    auth_fingerprint: str,
    first_request_type: type[FirstRequestT],
    tool_name: str,
    schema_version: int,
    fetch_page: Callable[[FirstRequestT, int, int], Awaitable[PageSlice[ItemT]]],
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PaginatedResult[ItemT]:
    if page_size < 1:
        raise ValueError("page_size must be greater than or equal to 1")

    if (request is None) == (cursor is None):
        raise ToolError(
            "Specify exactly one of request or cursor. "
            "For the first page, pass request. "
            "For a following page, pass only the nextCursor value as cursor."
        )

    if cursor is not None:
        state = _resolve_cursor(
            cursor_store,
            cursor,
            tool_name=tool_name,
            schema_version=schema_version,
            auth_fingerprint=auth_fingerprint,
        )
        first_request = first_request_type.model_validate(
            {
                "start_index": state.start_index,
                **state.query,
            }
        )
    else:
        assert request is not None
        first_request = request
        state = CursorState(
            tool_name=tool_name,
            schema_version=schema_version,
            auth_fingerprint=auth_fingerprint,
            query=first_request.model_dump(
                mode="json",
                exclude={"start_index"},
                exclude_none=True,
            ),
            start_index=first_request.start_index,
            number_results=page_size,
        )

    page = await fetch_page(first_request, state.start_index, state.number_results)
    ensure_page_progress(page.items, page.total_count, state.start_index)
    next_start_index = state.start_index + len(page.items)

    next_cursor = None
    if next_start_index <= page.total_count:
        next_cursor = cursor_store.issue(replace(state, start_index=next_start_index))

    return PaginatedResult[ItemT](
        items=page.items,
        total_count=page.total_count,
        next_cursor=next_cursor,
    )


def _resolve_cursor(
    cursor_store: InMemoryCursorStore,
    cursor: str,
    *,
    tool_name: str,
    schema_version: int,
    auth_fingerprint: str,
) -> CursorState:
    try:
        return cursor_store.resolve(
            cursor,
            tool_name=tool_name,
            schema_version=schema_version,
            auth_fingerprint=auth_fingerprint,
        )
    except CursorError as exc:
        if exc.reason is CursorErrorReason.TOOL_MISMATCH:
            message = "This cursor belongs to a different tool."
        elif exc.reason is CursorErrorReason.SCHEMA_VERSION_MISMATCH:
            message = "This cursor was issued for an incompatible tool schema."
        elif exc.reason is CursorErrorReason.AUTH_MISMATCH:
            message = "This cursor belongs to a different authentication context."
        else:
            message = "This cursor is invalid or expired."
        raise ToolError(f"{message} Start again by passing request and omitting cursor.") from exc
