from __future__ import annotations

import pytest
from fastmcp.exceptions import AuthorizationError

from ly_ads_mcp.servers.display.tools.base import DisplayHandlers


def test_handlers_api_client_raises_when_token_is_none(monkeypatch, settings):
    monkeypatch.setattr("ly_ads_mcp.servers.display.tools.base.get_access_token", lambda: None)
    handlers = DisplayHandlers(settings)
    with pytest.raises(AuthorizationError):
        with handlers.api_client():
            pass


def test_handlers_api_client_raises_when_token_value_is_none(monkeypatch, settings):
    class _FakeToken:
        token = None

    monkeypatch.setattr(
        "ly_ads_mcp.servers.display.tools.base.get_access_token", lambda: _FakeToken()
    )
    handlers = DisplayHandlers(settings)
    with pytest.raises(AuthorizationError):
        with handlers.api_client():
            pass
