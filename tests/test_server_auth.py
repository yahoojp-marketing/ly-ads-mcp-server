from __future__ import annotations

import asyncio

import pytest
import urllib3
from ads_display_client.exceptions import ApiException
from ads_display_client.models.base_account_service_selector import BaseAccountServiceSelector
from starlette.authentication import AuthenticationError

from ly_ads_mcp import server
from ly_ads_mcp.server import _LyAdsAccessTokenValidator


class _FakeResponse:
    def __init__(self, status: int, body: str = "{}") -> None:
        self.status = status
        self.reason = f"status-{status}"
        self.data = body.encode()
        self.headers = {"content-type": "application/json"}

    def read(self):
        return self.data

    def getheaders(self):
        return self.headers


class _FakeClient:
    def __init__(self, marker: dict[str, object]) -> None:
        self.marker = marker


def _patch_display_api_client(monkeypatch, created: dict[str, object] | None = None) -> None:
    class _FakeContextManager:
        def __init__(self, client: _FakeClient) -> None:
            self.client = client

        def __enter__(self) -> _FakeClient:
            return self.client

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_display_api_client(base_url: str, access_token: str, base_account_id: str | None = None):
        marker = {
            "base_url": base_url,
            "access_token": access_token,
            "base_account_id": base_account_id,
        }
        if created is not None:
            created["display_api_client"] = marker
        return _FakeContextManager(_FakeClient(marker))

    monkeypatch.setattr("ly_ads_mcp.server.display_api_client", fake_display_api_client)


def _patch_to_thread(monkeypatch, calls: list[dict[str, object]]) -> None:
    async def fake_to_thread(func, /, *args, **kwargs):
        calls.append(
            {
                "func": getattr(func, "__name__", repr(func)),
                "args": args,
                "kwargs": kwargs,
            }
        )
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)


async def test_access_token_validator_uses_generated_client_for_base_account_service(monkeypatch, settings):
    created = {}
    _patch_display_api_client(monkeypatch, created)
    to_thread_calls = []
    _patch_to_thread(monkeypatch, to_thread_calls)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            created["base_account_service_api_client"] = api_client

        def base_account_service_get_post_without_preload_content(
            self,
            base_account_service_selector,
            _request_timeout=None,
        ):
            created["base_account_service_get"] = {
                "selector": base_account_service_selector,
                "request_timeout": _request_timeout,
            }
            return _FakeResponse(200)

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    result = await _LyAdsAccessTokenValidator(settings, timeout_seconds=7).verify_token("ly-access-token")

    assert result is not None
    assert result.token == "ly-access-token"
    assert result.client_id == "ly-ads"
    assert result.scopes == ["yahooads"]
    assert created["display_api_client"] == {
        "base_url": "https://display.example.test/api/v19",
        "access_token": "ly-access-token",
        "base_account_id": None,
    }
    assert [call["func"] for call in to_thread_calls] == [
        "base_account_service_get_post_without_preload_content",
        "read",
    ]
    assert created["base_account_service_api_client"].marker == created["display_api_client"]
    assert created["base_account_service_get"]["selector"] == BaseAccountServiceSelector()
    assert created["base_account_service_get"]["request_timeout"] == 7


async def test_access_token_validator_treats_bad_request_as_authenticated_token(monkeypatch, settings):
    _patch_display_api_client(monkeypatch)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            body = '{"rid":"a1eff65e85815f541b1c233d8569efce","errors":[{"message":"invalid"}]}'
            return _FakeResponse(400, body=body)

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    result = await _LyAdsAccessTokenValidator(settings).verify_token("valid-token-with-bad-request")

    assert result is not None
    assert result.token == "valid-token-with-bad-request"


async def test_access_token_validator_raises_when_bad_request_has_no_rid(monkeypatch, settings):
    _patch_display_api_client(monkeypatch)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            return _FakeResponse(400, body='{"errors":[{"message":"bad gateway"}]}')

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    with pytest.raises(AuthenticationError, match="rid"):
        await _LyAdsAccessTokenValidator(settings).verify_token("token-via-proxy")


@pytest.mark.parametrize("status_code", [401, 403])
async def test_access_token_validator_returns_none_when_base_account_service_rejects_token(
    monkeypatch, settings, status_code
):
    _patch_display_api_client(monkeypatch)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            return _FakeResponse(status_code, body='{"error":"do not expose this body"}')

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    result = await _LyAdsAccessTokenValidator(settings).verify_token("rejected-token")

    assert result is None


async def test_access_token_validator_does_not_log_response_body_when_base_account_service_rejects_token(
    monkeypatch, settings
):
    _patch_display_api_client(monkeypatch)
    logged = {}

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            return _FakeResponse(401, body='{"error":"sensitive-body"}')

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)
    monkeypatch.setattr(server.logger, "warning", lambda *args: logged.setdefault("args", args))

    result = await _LyAdsAccessTokenValidator(settings).verify_token("rejected-token")

    assert result is None
    assert logged["args"] == (
        "LY Ads access token validation rejected token: status=%d",
        401,
    )


async def test_access_token_validator_returns_none_when_base_account_service_is_unavailable(monkeypatch, settings):
    _patch_display_api_client(monkeypatch)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            return _FakeResponse(500, body='{"error":"do not expose this body"}')

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    result = await _LyAdsAccessTokenValidator(settings).verify_token("server-error-token")

    assert result is None


async def test_access_token_validator_returns_none_when_request_fails(monkeypatch, settings):
    _patch_display_api_client(monkeypatch)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            raise urllib3.exceptions.HTTPError("network failed")

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    result = await _LyAdsAccessTokenValidator(settings).verify_token("network-error-token")

    assert result is None


async def test_access_token_validator_returns_none_when_api_exception_raised(monkeypatch, settings):
    _patch_display_api_client(monkeypatch)

    class FakeBaseAccountServiceApi:
        def __init__(self, api_client):
            self.api_client = api_client

        def base_account_service_get_post_without_preload_content(self, *args, **kwargs):
            raise ApiException(status=0, reason="SSL: CERTIFICATE_VERIFY_FAILED")

    monkeypatch.setattr("ly_ads_mcp.server.BaseAccountServiceApi", FakeBaseAccountServiceApi)

    result = await _LyAdsAccessTokenValidator(settings).verify_token("ssl-error-token")

    assert result is None
