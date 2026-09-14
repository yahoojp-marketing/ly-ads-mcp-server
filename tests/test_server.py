from __future__ import annotations

import fastmcp
import httpx
import pytest
from fastmcp import Client, FastMCP

from ly_ads_mcp import server
from ly_ads_mcp.servers.common.report_data import LY_ADS_DATA_HANDLING_INSTRUCTIONS


def _set_required_env(monkeypatch):
    monkeypatch.setenv("LY_ADS_CLIENT_ID", "client-id")
    monkeypatch.setenv("LY_ADS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("LY_ADS_MCP_JWT_SIGNING_KEY", "jwt-signing-key-with-at-least-32-characters")


def test_create_server_configures_oauth_proxy_and_does_not_register_auth_bootstrap(monkeypatch):
    _set_required_env(monkeypatch)
    created = {}

    class FakeOAuthProxy:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeFastMCP:
        def __init__(self, name, instructions, auth=None):
            self.name = name
            self.instructions = instructions
            self.auth = auth
            self.middlewares = []
            self.mounted = []
            created["mcp"] = self

        def add_middleware(self, middleware):
            self.middlewares.append(middleware)

        def mount(self, sub_server, **kwargs):
            self.mounted.append((sub_server, kwargs))

    monkeypatch.setattr(server, "OAuthProxy", FakeOAuthProxy)
    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)

    mcp = server.create_server()

    assert mcp is created["mcp"]
    assert mcp.name == "ly-ads-mcp"
    assert isinstance(mcp.auth, FakeOAuthProxy)
    assert mcp.auth.kwargs["upstream_authorization_endpoint"] == "https://biz-oauth.yahoo.co.jp/oauth/v1/authorize"
    assert mcp.auth.kwargs["upstream_token_endpoint"] == "https://biz-oauth.yahoo.co.jp/oauth/v1/token"
    assert mcp.auth.kwargs["upstream_client_id"] == "client-id"
    assert mcp.auth.kwargs["upstream_client_secret"] == "client-secret"
    assert mcp.auth.kwargs["jwt_signing_key"] == "jwt-signing-key-with-at-least-32-characters"
    assert mcp.auth.kwargs["base_url"] == "http://localhost:18765"
    assert mcp.auth.kwargs["redirect_path"] == "/callback"
    assert mcp.auth.kwargs["allowed_client_redirect_uris"] == [
        "http://localhost:*",
        "http://127.0.0.1:*",
    ]
    assert mcp.auth.kwargs["valid_scopes"] == ["yahooads"]
    assert mcp.auth.kwargs["token_endpoint_auth_method"] == "client_secret_post"
    assert mcp.auth.kwargs["fastmcp_access_token_expiry_seconds"] == 3600
    assert mcp.mounted == [
        (server.display_server, {"namespace": "ly_ads_display"}),
        (server.search_server, {"namespace": "ly_ads_search"}),
    ]


def test_create_server_puts_traversal_safety_near_start_of_instructions(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr(server, "OAuthProxy", lambda **kwargs: None)

    mcp = server.create_server()
    first_512_characters = mcp.instructions[:512]

    assert "Listing, showing, or checking items does not by itself authorize" in first_512_characters
    assert "Never fan out account-scoped tools" in first_512_characters


async def test_all_servers_include_common_trust_boundary_in_initialize_response(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr(server, "OAuthProxy", lambda **kwargs: None)

    servers = [server.create_server(), server.display_server, server.search_server]
    for mcp in servers:
        async with Client(mcp) as client:
            initialize_result = await client.initialize()

        assert initialize_result.instructions is not None
        assert LY_ADS_DATA_HANDLING_INSTRUCTIONS in initialize_result.instructions


def test_run_server_uses_streamable_http_transport(monkeypatch):
    _set_required_env(monkeypatch)
    run_kwargs = {}

    class FakeMCP:
        def run(self, **kwargs):
            run_kwargs.update(kwargs)

    monkeypatch.setattr(server, "create_server", lambda: FakeMCP())

    server.run_server()

    assert run_kwargs == {
        "transport": "streamable-http",
        "host": "localhost",
        "port": 18765,
        "host_origin_protection": "auto",
    }


@pytest.fixture
async def protected_http_client():
    app = FastMCP("test").http_app(host_origin_protection="auto")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        yield client


async def test_http_transport_rejects_invalid_host(protected_http_client):
    response = await protected_http_client.get("/not-found", headers={"host": "attacker.example"})

    assert response.status_code == 421


async def test_http_transport_rejects_invalid_origin(protected_http_client):
    response = await protected_http_client.get(
        "/not-found",
        headers={
            "host": "localhost",
            "origin": "https://attacker.example",
        },
    )

    assert response.status_code == 403


@pytest.fixture
async def oauth_http_client(monkeypatch, settings, tmp_path):
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    monkeypatch.setattr(fastmcp.settings, "home", tmp_path)
    app = server.create_server().http_app(host_origin_protection="auto")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=settings.mcp_base_url) as client:
        yield client


async def test_dynamic_client_registration_rejects_external_redirect_uri(oauth_http_client):
    response = await oauth_http_client.post(
        "/register",
        json={
            "redirect_uris": ["https://attacker.example/callback"],
            "token_endpoint_auth_method": "none",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "http://localhost:49152/callback",
        "http://127.0.0.1:49153/callback",
    ],
)
async def test_dynamic_client_registration_accepts_loopback_redirect_uri(oauth_http_client, redirect_uri):
    response = await oauth_http_client.post(
        "/register",
        json={
            "redirect_uris": [redirect_uri],
            "token_endpoint_auth_method": "none",
        },
    )

    assert response.status_code == 201
    assert response.json()["redirect_uris"] == [redirect_uri]
