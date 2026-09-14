# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json

import urllib3
from ads_display_client.api.base_account_service_api import BaseAccountServiceApi
from ads_display_client.exceptions import ApiException
from ads_display_client.models.base_account_service_selector import BaseAccountServiceSelector
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, OAuthProxy, TokenVerifier
from fastmcp.utilities.logging import get_logger
from starlette.authentication import AuthenticationError

from ly_ads_mcp.config import Settings, get_settings
from ly_ads_mcp.servers.common.report_data import LY_ADS_DATA_HANDLING_INSTRUCTIONS
from ly_ads_mcp.servers.display._api_client import display_api_client
from ly_ads_mcp.servers.display.server import display_server
from ly_ads_mcp.servers.namespaces import DISPLAY_SERVER_NAMESPACE, SEARCH_SERVER_NAMESPACE
from ly_ads_mcp.servers.search.server import search_server

logger = get_logger(__name__)


class _LyAdsAccessTokenValidator(TokenVerifier):
    def __init__(self, settings: Settings, timeout_seconds: int = 10):
        super().__init__(required_scopes=[settings.scope])
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            with display_api_client(self.settings.display_api_base_url, token) as client:
                response = await asyncio.to_thread(
                    BaseAccountServiceApi(client).base_account_service_get_post_without_preload_content,
                    BaseAccountServiceSelector(),
                    _request_timeout=self.timeout_seconds,
                )
                await asyncio.to_thread(response.read)
        except (urllib3.exceptions.HTTPError, ApiException) as exc:
            logger.info(
                "LY Ads access token validation request failed: %s: %s",
                type(exc).__name__,
                exc,
            )
            return None

        if response.status in {401, 403}:
            logger.warning(
                "LY Ads access token validation rejected token: status=%d",
                response.status,
            )
            return None

        if response.status == 400:
            try:
                body = json.loads(response.data)
            except (json.JSONDecodeError, Exception):
                raise AuthenticationError("LY Ads API returned status 400 with non-JSON body")
            if "rid" not in body:
                raise AuthenticationError(
                    "LY Ads API 400 response is missing the rid field - possible proxy interference"
                )
            logger.info(
                "LY Ads access token validation request returned non-auth error: status=%d",
                response.status,
            )
        elif not 200 <= response.status < 300:
            logger.warning(
                "LY Ads access token validation request failed: status=%d",
                response.status,
            )
            return None

        return AccessToken(
            token=token,
            client_id="ly-ads",
            scopes=[self.settings.scope],
        )


def create_server() -> FastMCP:
    settings = get_settings()
    auth = OAuthProxy(
        upstream_authorization_endpoint=f"{settings.oauth_base_url}/authorize",
        upstream_token_endpoint=f"{settings.oauth_base_url}/token",
        upstream_client_id=settings.client_id,
        upstream_client_secret=settings.client_secret,
        jwt_signing_key=settings.jwt_signing_key,
        token_verifier=_LyAdsAccessTokenValidator(settings),
        base_url=settings.mcp_base_url,
        redirect_path="/callback",
        # MCP clients use their own ephemeral callback ports; these are separate from this server's /callback.
        allowed_client_redirect_uris=[
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
        valid_scopes=[settings.scope],
        token_endpoint_auth_method="client_secret_post",
        fastmcp_access_token_expiry_seconds=3600,
    )
    mcp = FastMCP(
        "ly-ads-mcp",
        instructions=f"""
        [Role]
        This server provides tools to manage LY Ads (LINEヤフー広告) via the Display Ads API and Search Ads API.

        [Traversal Safety]
        Listing, showing, or checking items does not by itself authorize exhaustive traversal. Follow nextCursor only
        when the user explicitly requests all results, the next page, or a range. Never fan out account-scoped tools
        across multiple baseAccountId or accountId values unless the user explicitly requests every account. If an
        account reference is ambiguous or multiple accounts match, stop and ask the user to choose the target IDs.

        [Account Model]
        LY Ads uses a hierarchical MCC (My Client Center) structure.

        - `baseAccountId`: The base account context for the request, sent as the `x-z-base-account-id` header.
          When set to an MCC account, permissions apply to all ad accounts beneath it in the hierarchy.
        - `accountId`: The target ad account for the operation (campaigns, ad groups, ads, reports, etc.).

        [Authentication]
        Authenticate through the MCP client's OAuth flow before calling LY Ads API tools.
        Do not expose secrets such as client secrets, access tokens, or refresh tokens.

        [API Coverage]
        When the user's intent is ambiguous, ask whether it concerns Display Ads or Search Ads.

        {LY_ADS_DATA_HANDLING_INSTRUCTIONS}
        """,
        auth=auth,
    )
    mcp.mount(display_server, namespace=DISPLAY_SERVER_NAMESPACE)
    mcp.mount(search_server, namespace=SEARCH_SERVER_NAMESPACE)

    return mcp


def run_server() -> None:
    settings: Settings = get_settings()
    create_server().run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        host_origin_protection="auto",
    )


if __name__ == "__main__":
    run_server()
