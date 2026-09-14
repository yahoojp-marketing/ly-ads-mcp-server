from __future__ import annotations

import pytest
from fakes import FakeAccount, FakeApiResponse, FakeHandlers, FakeRval, FakeValue
from fastmcp.exceptions import ToolError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.tools import list_accessible_display_accounts as list_accessible_display_accounts_tool
from ly_ads_mcp.servers.display.tools import (
    list_accessible_display_base_accounts as list_accessible_display_base_accounts_tool,
)
from ly_ads_mcp.servers.display.tools.list_accessible_display_accounts import (
    ListAccessibleDisplayAccountsRequest,
)
from ly_ads_mcp.servers.display.tools.list_accessible_display_base_accounts import (
    ListAccessibleDisplayBaseAccountsRequest,
)


async def test_list_accessible_display_accounts_returns_accounts_with_base_account_id(
    monkeypatch, patch_to_thread
):
    fake_response = FakeApiResponse(
        rval=FakeRval(
            values=[FakeValue(account=FakeAccount({"accountId": 456, "accountName": "Ad Account"}))],
            total=1,
        )
    )
    captured = {}

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = account_service_selector
            return fake_response

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)

    result = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        FakeHandlers(),
        ListAccessibleDisplayAccountsRequest(base_account_id=999),
    )

    assert result.items[0].account_id == 456
    assert result.items[0].base_account_id == 999
    assert captured["base_account_id"] == 999


async def test_list_accessible_display_accounts_rejects_value_with_no_account(monkeypatch, patch_to_thread):
    fake_response = FakeApiResponse(
        rval=FakeRval(
            values=[
                FakeValue(account=None),
                FakeValue(account=FakeAccount({"accountId": 789})),
            ],
            total=2,
        )
    )

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            return fake_response

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)

    with pytest.raises(ToolError, match="ad-account entry without account data"):
        await list_accessible_display_accounts_tool.list_accessible_display_accounts(
            FakeHandlers(),
            ListAccessibleDisplayAccountsRequest(base_account_id=1),
        )


async def test_list_accessible_display_accounts_uses_fixed_page_size_across_pages(
    monkeypatch, patch_to_thread
):
    captured = []

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            captured.append((x_z_base_account_id, account_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeValue(account=FakeAccount({"accountId": account_id}))
                        for account_id in range(account_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)
    handlers = FakeHandlers()
    first = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        handlers,
        ListAccessibleDisplayAccountsRequest(base_account_id=999),
    )
    continued = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [999, 999]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_empty_upstream_page_before_end_is_rejected(monkeypatch, patch_to_thread):
    captured = []

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            captured.append(account_service_selector.start_index)
            return FakeApiResponse(rval=FakeRval(values=[], total=DEFAULT_PAGE_SIZE + 1))

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)
    with pytest.raises(ToolError, match="empty page before the end"):
        await list_accessible_display_accounts_tool.list_accessible_display_accounts(
            FakeHandlers(),
            ListAccessibleDisplayAccountsRequest(base_account_id=1),
        )

    assert captured == [1]


async def test_total_count_shrink_stops_at_current_upstream_end(monkeypatch, patch_to_thread):
    captured = []

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            captured.append(account_service_selector.start_index)
            if account_service_selector.start_index == 1:
                values = [
                    FakeValue(account=FakeAccount({"accountId": account_id}))
                    for account_id in range(DEFAULT_PAGE_SIZE)
                ]
                return FakeApiResponse(rval=FakeRval(values=values, total=DEFAULT_PAGE_SIZE * 2))
            return FakeApiResponse(rval=FakeRval(values=[], total=DEFAULT_PAGE_SIZE - 1))

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)
    handlers = FakeHandlers()
    first = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        handlers,
        ListAccessibleDisplayAccountsRequest(base_account_id=1),
    )
    continued = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        handlers,
        cursor=first.next_cursor,
    )

    assert captured == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.total_count == DEFAULT_PAGE_SIZE - 1
    assert continued.next_cursor is None


async def test_total_count_growth_keeps_pagination_available(monkeypatch, patch_to_thread):
    captured = []

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            captured.append(account_service_selector.start_index)
            total = DEFAULT_PAGE_SIZE + 1 if account_service_selector.start_index == 1 else DEFAULT_PAGE_SIZE * 3
            values = [
                FakeValue(account=FakeAccount({"accountId": account_id}))
                for account_id in range(DEFAULT_PAGE_SIZE)
            ]
            return FakeApiResponse(rval=FakeRval(values=values, total=total))

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)
    handlers = FakeHandlers()
    first = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        handlers,
        ListAccessibleDisplayAccountsRequest(base_account_id=1),
    )
    continued = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        handlers,
        cursor=first.next_cursor,
    )

    assert captured == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.total_count == DEFAULT_PAGE_SIZE * 3
    assert continued.next_cursor is not None


async def test_list_accessible_display_accounts_rejects_cursor_from_other_tool(monkeypatch, patch_to_thread):
    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            return FakeApiResponse(
                rval=FakeRval(
                    values=[FakeValue(account=FakeAccount({"accountId": 1}))],
                    total=DEFAULT_PAGE_SIZE + 1,
                )
            )

    monkeypatch.setattr(
        list_accessible_display_base_accounts_tool, "BaseAccountServiceApi", FakeBaseAccountServiceApi
    )
    handlers = FakeHandlers()
    first = await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
        handlers,
        ListAccessibleDisplayBaseAccountsRequest(),
    )

    with pytest.raises(ToolError, match="different tool.*passing request and omitting cursor"):
        await list_accessible_display_accounts_tool.list_accessible_display_accounts(
            handlers,
            cursor=first.next_cursor,
        )


async def test_list_accessible_display_accounts_rejects_unknown_cursor():
    with pytest.raises(ToolError, match="invalid or expired.*passing request and omitting cursor"):
        await list_accessible_display_accounts_tool.list_accessible_display_accounts(
            FakeHandlers(),
            cursor="tampered-cursor",
        )


async def test_list_accessible_display_accounts_rejects_cursor_from_other_authentication(
    monkeypatch, patch_to_thread
):
    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            return FakeApiResponse(
                rval=FakeRval(
                    values=[FakeValue(account=FakeAccount({"accountId": 1}))],
                    total=DEFAULT_PAGE_SIZE + 1,
                )
            )

    monkeypatch.setattr(list_accessible_display_accounts_tool, "AccountServiceApi", FakeAccountServiceApi)
    first_handlers = FakeHandlers(auth_fingerprint="auth-a")
    first = await list_accessible_display_accounts_tool.list_accessible_display_accounts(
        first_handlers,
        ListAccessibleDisplayAccountsRequest(base_account_id=1),
    )
    other_auth_handlers = FakeHandlers(
        auth_fingerprint="auth-b",
        cursor_store=first_handlers.cursor_store,
    )

    with pytest.raises(
        ToolError, match="different authentication context.*passing request and omitting cursor"
    ):
        await list_accessible_display_accounts_tool.list_accessible_display_accounts(
            other_auth_handlers,
            cursor=first.next_cursor,
        )
