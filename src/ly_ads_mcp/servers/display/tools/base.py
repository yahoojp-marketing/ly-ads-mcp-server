# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Generator

from fastmcp.exceptions import AuthorizationError
from fastmcp.server.dependencies import get_access_token

from ly_ads_mcp.config import Settings
from ly_ads_mcp.servers.common.pagination import InMemoryCursorStore

from .._api_client import display_api_client
from ..client import ApiClient


class DisplayHandlers:
    def __init__(self, settings: Settings, cursor_store: InMemoryCursorStore | None = None) -> None:
        self.settings = settings
        self.cursor_store = cursor_store or InMemoryCursorStore()

    def access_token_fingerprint(self) -> str:
        return hashlib.sha256(self._access_token().encode()).hexdigest()

    @contextmanager
    def api_client(self) -> Generator[ApiClient, None, None]:
        token = self._access_token()
        with display_api_client(self.settings.display_api_base_url, token) as client:
            yield client

    @staticmethod
    def _access_token() -> str:
        token = get_access_token()
        if token is None or token.token is None:
            raise AuthorizationError("No access token in request context")
        return token.token
