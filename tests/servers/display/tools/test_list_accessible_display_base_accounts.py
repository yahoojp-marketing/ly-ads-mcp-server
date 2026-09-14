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


async def test_list_accessible_display_base_accounts_returns_accounts(monkeypatch, patch_to_thread):
    fake_response = FakeApiResponse(
        rval=FakeRval(
            values=[FakeValue(account=FakeAccount({"accountId": 111, "accountName": "Base A"}))],
            total=1,
        )
    )
    captured = {}

    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            captured["selector"] = base_account_service_selector
            return fake_response

    monkeypatch.setattr(
        list_accessible_display_base_accounts_tool, "BaseAccountServiceApi", FakeBaseAccountServiceApi
    )

    result = await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
        FakeHandlers(),
        ListAccessibleDisplayBaseAccountsRequest(account_name="Base"),
    )

    assert result.total_count == 1
    assert result.next_cursor is None
    assert result.items[0].account_id == 111
    assert captured["selector"].number_results == DEFAULT_PAGE_SIZE
    assert captured["selector"].start_index == 1
    assert captured["selector"].account_name == "Base"


async def test_list_accessible_display_base_accounts_rejects_value_with_no_account(
    monkeypatch, patch_to_thread
):
    fake_response = FakeApiResponse(
        rval=FakeRval(
            values=[
                FakeValue(account=None),
                FakeValue(account=FakeAccount({"accountId": 222})),
            ],
            total=2,
        )
    )

    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            return fake_response

    monkeypatch.setattr(
        list_accessible_display_base_accounts_tool, "BaseAccountServiceApi", FakeBaseAccountServiceApi
    )

    with pytest.raises(ToolError, match="base-account entry without account data"):
        await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
            FakeHandlers(),
            ListAccessibleDisplayBaseAccountsRequest(),
        )


async def test_list_accessible_display_base_accounts_returns_cursor_when_more_results_exist(
    monkeypatch, patch_to_thread
):
    fake_response = FakeApiResponse(
        rval=FakeRval(
            values=[FakeValue(account=FakeAccount({"accountId": 111}))],
            total=DEFAULT_PAGE_SIZE + 1,
        )
    )

    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            return fake_response

    monkeypatch.setattr(
        list_accessible_display_base_accounts_tool, "BaseAccountServiceApi", FakeBaseAccountServiceApi
    )

    result = await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
        FakeHandlers(),
        ListAccessibleDisplayBaseAccountsRequest(),
    )

    assert result.next_cursor is not None
    assert "start_index" not in result.next_cursor


async def test_list_accessible_display_base_accounts_continuation_restores_filters_and_position(
    monkeypatch, patch_to_thread
):
    captured = []

    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            captured.append(base_account_service_selector)
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeValue(
                            account=FakeAccount(
                                {"accountId": base_account_service_selector.start_index}
                            )
                        )
                    ],
                    total=2,
                )
            )

    monkeypatch.setattr(
        list_accessible_display_base_accounts_tool, "BaseAccountServiceApi", FakeBaseAccountServiceApi
    )
    handlers = FakeHandlers()
    first = await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
        handlers,
        ListAccessibleDisplayBaseAccountsRequest(account_name="Base"),
    )
    continued = await list_accessible_display_base_accounts_tool.list_accessible_display_base_accounts(
        handlers,
        cursor=first.next_cursor,
    )

    assert [selector.start_index for selector in captured] == [1, 2]
    assert [selector.account_name for selector in captured] == ["Base", "Base"]
    assert continued.items[0].account_id == 2
    assert continued.next_cursor is None
