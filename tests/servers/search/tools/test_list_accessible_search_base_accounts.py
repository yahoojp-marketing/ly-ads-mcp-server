from __future__ import annotations

import pytest
from ads_search_client.models.base_account_service_include_ssa_account import (
    BaseAccountServiceIncludeSsaAccount,
)
from fakes import FakeAccount, FakeApiResponse, FakeHandlers, FakeRval, FakeValue
from fastmcp.exceptions import ToolError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.search.tools import (
    list_accessible_search_base_accounts as list_accessible_search_base_accounts_tool,
)
from ly_ads_mcp.servers.search.tools.list_accessible_search_base_accounts import (
    ListAccessibleSearchBaseAccountsRequest,
)


async def test_list_accessible_search_base_accounts_excludes_ssa_on_every_page(
    monkeypatch, patch_to_thread
):
    selectors = []

    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            selectors.append(base_account_service_selector)
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeValue(
                            account=FakeAccount(
                                {
                                    "accountId": 111,
                                    "accountName": "Search Base",
                                    "isSsaAccount": "FALSE",
                                }
                            )
                        )
                    ],
                    total=2,
                )
            )

    monkeypatch.setattr(
        list_accessible_search_base_accounts_tool,
        "BaseAccountServiceApi",
        FakeBaseAccountServiceApi,
    )
    handlers = FakeHandlers()

    first = await list_accessible_search_base_accounts_tool.list_accessible_search_base_accounts(
        handlers,
        ListAccessibleSearchBaseAccountsRequest(account_name="Search"),
    )
    continued = await list_accessible_search_base_accounts_tool.list_accessible_search_base_accounts(
        handlers,
        cursor=first.next_cursor,
    )

    assert len(selectors) == 2
    assert all(
        selector.include_ssa_account is BaseAccountServiceIncludeSsaAccount.EXCLUDE_SSA
        for selector in selectors
    )
    assert [selector.number_results for selector in selectors] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for selector in selectors] == [1, 2]
    assert [selector.account_name for selector in selectors] == ["Search", "Search"]
    assert first.items[0].model_dump(by_alias=True) == {
        "accountId": 111,
        "accountName": "Search Base",
        "isSsaAccount": "FALSE",
    }
    assert continued.next_cursor is None


async def test_list_accessible_search_base_accounts_rejects_value_without_account(
    monkeypatch, patch_to_thread
):
    class FakeBaseAccountServiceApi:
        def __init__(self, client):
            pass

        def base_account_service_get_post(self, base_account_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeValue(account=None)], total=1))

    monkeypatch.setattr(
        list_accessible_search_base_accounts_tool,
        "BaseAccountServiceApi",
        FakeBaseAccountServiceApi,
    )

    with pytest.raises(ToolError, match="without account data"):
        await list_accessible_search_base_accounts_tool.list_accessible_search_base_accounts(
            FakeHandlers(),
            ListAccessibleSearchBaseAccountsRequest(),
        )
