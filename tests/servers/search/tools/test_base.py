from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastmcp.exceptions import AuthorizationError

from ly_ads_mcp.servers.search.tools.base import SearchHandlers


def test_handlers_api_client_raises_when_token_is_none(monkeypatch, settings):
    monkeypatch.setattr("ly_ads_mcp.servers.search.tools.base.get_access_token", lambda: None)
    handlers = SearchHandlers(settings)
    with pytest.raises(AuthorizationError):
        with handlers.api_client():
            pass


def test_handlers_api_client_raises_when_token_value_is_none(monkeypatch, settings):
    class _FakeToken:
        token = None

    monkeypatch.setattr("ly_ads_mcp.servers.search.tools.base.get_access_token", lambda: _FakeToken())
    handlers = SearchHandlers(settings)
    with pytest.raises(AuthorizationError):
        with handlers.api_client():
            pass


def test_handlers_api_client_uses_search_api_settings(monkeypatch, settings):
    captured = {}

    class _FakeToken:
        token = "search-token"

    @contextmanager
    def fake_search_api_client(base_url, access_token):
        captured.update(base_url=base_url, access_token=access_token)
        yield object()

    monkeypatch.setattr("ly_ads_mcp.servers.search.tools.base.get_access_token", lambda: _FakeToken())
    monkeypatch.setattr("ly_ads_mcp.servers.search.tools.base.search_api_client", fake_search_api_client)

    with SearchHandlers(settings).api_client():
        pass

    assert captured == {
        "base_url": "https://search.example.test/api/v19",
        "access_token": "search-token",
    }
