from __future__ import annotations

import pytest
from fakes import FakeAccount, FakeApiResponse, FakeHandlers, FakeRval, FakeValue
from fastmcp.exceptions import ToolError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.tools import (
    list_accessible_display_base_accounts as list_accessible_display_base_accounts_tool,
)
from ly_ads_mcp.servers.display.tools.list_accessible_display_base_accounts import (
    ListAccessibleDisplayBaseAccountsRequest,
)
from ly_ads_mcp.servers.search.tools import (
    list_accessible_search_accounts as list_accessible_search_accounts_tool,
)
from ly_ads_mcp.servers.search.tools.list_accessible_search_accounts import (
    ListAccessibleSearchAccountsRequest,
)


async def test_list_accessible_search_accounts_returns_accounts_with_base_account_id(
    monkeypatch, patch_to_thread
):
    captured = {}

    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = account_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeValue(account=FakeAccount({"accountId": 456, "accountName": "Search Account"}))
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(
        list_accessible_search_accounts_tool,
        "AccountServiceApi",
        FakeAccountServiceApi,
    )

    result = await list_accessible_search_accounts_tool.list_accessible_search_accounts(
        FakeHandlers(),
        ListAccessibleSearchAccountsRequest(base_account_id=999),
    )

    assert result.items[0].account_id == 456
    assert result.items[0].base_account_id == 999
    assert captured["base_account_id"] == 999
    assert captured["selector"].number_results == DEFAULT_PAGE_SIZE
    assert captured["selector"].start_index == 1


async def test_list_accessible_search_accounts_restores_filters_and_page_size(
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
                        FakeValue(
                            account=FakeAccount({"accountId": account_service_selector.start_index})
                        )
                    ],
                    total=2,
                )
            )

    monkeypatch.setattr(
        list_accessible_search_accounts_tool,
        "AccountServiceApi",
        FakeAccountServiceApi,
    )
    handlers = FakeHandlers()

    first = await list_accessible_search_accounts_tool.list_accessible_search_accounts(
        handlers,
        ListAccessibleSearchAccountsRequest(base_account_id=999, account_name="Search"),
    )
    continued = await list_accessible_search_accounts_tool.list_accessible_search_accounts(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [999, 999]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, 2]
    assert [selector.account_name for _, selector in captured] == ["Search", "Search"]
    assert continued.next_cursor is None


async def test_list_accessible_search_accounts_rejects_value_without_account(
    monkeypatch, patch_to_thread
):
    class FakeAccountServiceApi:
        def __init__(self, client):
            pass

        def account_service_get_post(self, x_z_base_account_id, account_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeValue(account=None)], total=1))

    monkeypatch.setattr(
        list_accessible_search_accounts_tool,
        "AccountServiceApi",
        FakeAccountServiceApi,
    )

    with pytest.raises(ToolError, match="without account data"):
        await list_accessible_search_accounts_tool.list_accessible_search_accounts(
            FakeHandlers(),
            ListAccessibleSearchAccountsRequest(base_account_id=1),
        )


async def test_list_accessible_search_accounts_rejects_display_cursor(monkeypatch, patch_to_thread):
    class FakeDisplayBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            return FakeApiResponse(
                rval=FakeRval(
                    values=[FakeValue(account=FakeAccount({"accountId": 111}))],
                    total=2,
                )
            )

    monkeypatch.setattr(
        list_accessible_display_base_accounts_tool,
        "BaseAccountServiceApi",
        FakeDisplayBaseAccountServiceApi,
    )
    handlers = FakeHandlers()
    display_page = (
        await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
            handlers,
            ListAccessibleDisplayBaseAccountsRequest(),
        )
    )

    with pytest.raises(ToolError, match="different tool"):
        await list_accessible_search_accounts_tool.list_accessible_search_accounts(
            handlers,
            cursor=display_page.next_cursor,
        )
