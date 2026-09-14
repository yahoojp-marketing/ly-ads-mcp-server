from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from ly_ads_mcp.servers.common.pagination import (
    DEFAULT_PAGE_SIZE,
    CursorError,
    CursorErrorReason,
    CursorState,
    InMemoryCursorStore,
    PageSlice,
    StrictRequestModel,
    ensure_page_progress,
    generic_paginated_output_schema,
    paginate,
)


class _Request(StrictRequestModel):
    start_index: int = 1
    account_name: str | None = None


def _state(**overrides):
    values = {
        "tool_name": "list_items",
        "schema_version": 1,
        "auth_fingerprint": "auth-a",
        "query": {"account_name": "Example"},
        "start_index": DEFAULT_PAGE_SIZE + 1,
        "number_results": DEFAULT_PAGE_SIZE,
    }
    values.update(overrides)
    return CursorState(**values)


def _resolve(store, cursor, **overrides):
    arguments = {
        "tool_name": "list_items",
        "schema_version": 1,
        "auth_fingerprint": "auth-a",
    }
    arguments.update(overrides)
    return store.resolve(cursor, **arguments)


def test_cursor_is_an_opaque_random_handle():
    store = InMemoryCursorStore()
    cursor = store.issue(_state())

    assert cursor != store.issue(_state())
    assert "Example" not in cursor


def test_cursor_can_be_reused_without_mutating_state():
    store = InMemoryCursorStore()
    cursor = store.issue(_state())

    first = _resolve(store, cursor)
    first.query["account_name"] = "Changed"
    second = _resolve(store, cursor)

    assert second.query == {"account_name": "Example"}
    assert second.start_index == DEFAULT_PAGE_SIZE + 1


def test_cursor_state_rejects_start_index_below_ly_ads_api_minimum():
    with pytest.raises(ValueError, match="start_index must be greater than or equal to 1"):
        _state(start_index=0)


def test_generic_paginated_output_schema_hides_entity_fields():
    schema = generic_paginated_output_schema()

    assert schema["additionalProperties"] is False
    assert schema["properties"]["items"]["items"] == {
        "additionalProperties": True,
        "type": "object",
    }
    assert set(schema["properties"]) == {
        "items",
        "totalCount",
        "nextCursor",
    }


def test_ensure_page_progress_accepts_nonempty_page():
    ensure_page_progress([object()], total_count=2, start_index=1)


def test_ensure_page_progress_rejects_empty_page_before_result_set_end():
    with pytest.raises(ToolError, match="empty page before the end"):
        ensure_page_progress([], total_count=2, start_index=1)


def test_ensure_page_progress_accepts_empty_page_after_result_set_end():
    ensure_page_progress([], total_count=1, start_index=2)


def test_cursor_expires():
    now = [100.0]
    store = InMemoryCursorStore(ttl_seconds=10, clock=lambda: now[0])
    cursor = store.issue(_state())
    now[0] = 110.0

    with pytest.raises(CursorError) as raised:
        _resolve(store, cursor)

    assert raised.value.reason is CursorErrorReason.EXPIRED


def test_cursor_rejects_another_tool():
    store = InMemoryCursorStore()
    cursor = store.issue(_state())

    with pytest.raises(CursorError) as raised:
        _resolve(store, cursor, tool_name="other_tool")

    assert raised.value.reason is CursorErrorReason.TOOL_MISMATCH


def test_cursor_rejects_another_schema_version():
    store = InMemoryCursorStore()
    cursor = store.issue(_state())

    with pytest.raises(CursorError) as raised:
        _resolve(store, cursor, schema_version=2)

    assert raised.value.reason is CursorErrorReason.SCHEMA_VERSION_MISMATCH


def test_cursor_rejects_another_authentication_context():
    store = InMemoryCursorStore()
    cursor = store.issue(_state())

    with pytest.raises(CursorError) as raised:
        _resolve(store, cursor, auth_fingerprint="auth-b")

    assert raised.value.reason is CursorErrorReason.AUTH_MISMATCH


def test_cursor_is_unknown_after_server_restart():
    first_store = InMemoryCursorStore()
    cursor = first_store.issue(_state())
    restarted_store = InMemoryCursorStore()

    with pytest.raises(CursorError) as raised:
        _resolve(restarted_store, cursor)

    assert raised.value.reason is CursorErrorReason.UNKNOWN


def test_cursor_store_evicts_least_recently_used_entry_at_capacity():
    store = InMemoryCursorStore(max_entries=2)
    first = store.issue(_state(start_index=DEFAULT_PAGE_SIZE + 1))
    second = store.issue(_state(start_index=101))
    _resolve(store, first)
    store.issue(_state(start_index=151))

    with pytest.raises(CursorError) as raised:
        _resolve(store, second)

    assert raised.value.reason is CursorErrorReason.UNKNOWN


@pytest.mark.parametrize(
    ("initial_request", "cursor"),
    [
        (None, None),
        (_Request(), "opaque"),
    ],
)
async def test_paginate_requires_exactly_one_of_request_or_cursor(initial_request, cursor):
    async def fetch_page(_request, _start_index, _number_results):
        return PageSlice(items=[], total_count=0)

    with pytest.raises(ToolError, match="Specify exactly one of request or cursor"):
        await paginate(
            initial_request,
            cursor=cursor,
            cursor_store=InMemoryCursorStore(),
            auth_fingerprint="auth-a",
            first_request_type=_Request,
            tool_name="list_items",
            schema_version=1,
            page_size=DEFAULT_PAGE_SIZE,
            fetch_page=fetch_page,
        )


async def test_paginate_restores_query_and_position_from_cursor():
    calls = []

    async def fetch_page(request, start_index, number_results):
        calls.append((request.account_name, start_index, number_results))
        return PageSlice(items=[start_index, start_index + 1], total_count=4)

    store = InMemoryCursorStore()
    first = await paginate(
        _Request(account_name="Example"),
        cursor=None,
        cursor_store=store,
        auth_fingerprint="auth-a",
        first_request_type=_Request,
        tool_name="list_items",
        schema_version=1,
        page_size=DEFAULT_PAGE_SIZE,
        fetch_page=fetch_page,
    )
    assert first.next_cursor is not None

    continued = await paginate(
        None,
        cursor=first.next_cursor,
        cursor_store=store,
        auth_fingerprint="auth-a",
        first_request_type=_Request,
        tool_name="list_items",
        schema_version=1,
        page_size=DEFAULT_PAGE_SIZE,
        fetch_page=fetch_page,
    )

    assert calls == [
        ("Example", 1, DEFAULT_PAGE_SIZE),
        ("Example", 3, DEFAULT_PAGE_SIZE),
    ]
    assert continued.items == [3, 4]
    assert continued.next_cursor is None


async def test_paginate_rejects_empty_page_before_result_set_end():
    async def fetch_page(_request, _start_index, _number_results):
        return PageSlice(items=[], total_count=2)

    with pytest.raises(ToolError, match="empty page before the end"):
        await paginate(
            _Request(),
            cursor=None,
            cursor_store=InMemoryCursorStore(),
            auth_fingerprint="auth-a",
            first_request_type=_Request,
            tool_name="list_items",
            schema_version=1,
            page_size=DEFAULT_PAGE_SIZE,
            fetch_page=fetch_page,
        )
