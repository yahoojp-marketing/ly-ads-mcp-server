from __future__ import annotations

import asyncio

import pytest
from fakes import FakeHandlers

from ly_ads_mcp.config import Settings, get_settings

# ── Settings ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        client_id="client-id",
        client_secret="client-secret",
        jwt_signing_key="jwt-signing-key-with-at-least-32-characters",
        oauth_base_url="https://oauth.example.test",
        display_api_base_url="https://display.example.test/api/v19",
        search_api_base_url="https://search.example.test/api/v19",
        scope="yahooads",
        report_output_dir=tmp_path / "reports",
        mcp_base_url="http://localhost:18765",
        mcp_host="localhost",
        mcp_port=18765,
    )


# ── asyncio.to_thread bypass ────────────────────────────────────────────────


@pytest.fixture
def patch_to_thread(monkeypatch):
    async def fake_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)


@pytest.fixture
def fake_handlers() -> FakeHandlers:
    return FakeHandlers()
