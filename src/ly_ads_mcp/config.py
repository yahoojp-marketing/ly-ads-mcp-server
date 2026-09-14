# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ly_ads_mcp.api_version import API_VERSION

_OAUTH_BASE_URL = "https://biz-oauth.yahoo.co.jp/oauth/v1"
_DISPLAY_API_HOST = "https://ads-display.yahooapis.jp"
_SEARCH_API_HOST = "https://ads-search.yahooapis.jp"
_MCP_HOST = "localhost"
_MCP_PORT = 18765
_MCP_BASE_URL = f"http://{_MCP_HOST}:{_MCP_PORT}"
_REPORT_OUTPUT_DIR = Path("reports")
_JWT_SIGNING_KEY_MIN_LENGTH = 32
_PLACEHOLDER_VALUES = {
    "<your_client_id>",
    "<your_client_secret>",
    "<your_jwt_signing_key>",
}


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    jwt_signing_key: str
    oauth_base_url: str
    display_api_base_url: str
    search_api_base_url: str
    scope: str
    report_output_dir: Path
    mcp_base_url: str = _MCP_BASE_URL
    mcp_host: str = _MCP_HOST
    mcp_port: int = _MCP_PORT


def resolve_settings() -> Settings:
    client_id = _read_required("LY_ADS_CLIENT_ID")
    client_secret = _read_required("LY_ADS_CLIENT_SECRET")
    jwt_signing_key = _read_required("LY_ADS_MCP_JWT_SIGNING_KEY")
    _validate_jwt_signing_key(jwt_signing_key, client_secret)

    return Settings(
        client_id=client_id,
        client_secret=client_secret,
        jwt_signing_key=jwt_signing_key,
        oauth_base_url=_strip_slash(_read_optional("LY_ADS_OAUTH_BASE_URL", _OAUTH_BASE_URL)),
        display_api_base_url=_build_api_url(_read_optional("LY_ADS_DISPLAY_API_HOST", _DISPLAY_API_HOST)),
        search_api_base_url=_build_api_url(_read_optional("LY_ADS_SEARCH_API_HOST", _SEARCH_API_HOST)),
        scope="yahooads",
        report_output_dir=_read_path("LY_ADS_REPORT_OUTPUT_DIR", _REPORT_OUTPUT_DIR),
        mcp_base_url=_MCP_BASE_URL,
        mcp_host=_MCP_HOST,
        mcp_port=_MCP_PORT,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return resolve_settings()


def _read_required(name: str) -> str:
    value = os.environ.get(name)
    if not value or not value.strip():
        raise ValueError(f"Missing required setting: {name}")
    trimmed = value.strip()
    if trimmed in _PLACEHOLDER_VALUES:
        raise ValueError(f"Invalid placeholder setting: {name}")
    return trimmed


def _validate_jwt_signing_key(jwt_signing_key: str, client_secret: str) -> None:
    if len(jwt_signing_key) < _JWT_SIGNING_KEY_MIN_LENGTH:
        raise ValueError(
            f"Invalid setting: LY_ADS_MCP_JWT_SIGNING_KEY must be at least {_JWT_SIGNING_KEY_MIN_LENGTH} characters"
        )
    if secrets.compare_digest(jwt_signing_key.encode(), client_secret.encode()):
        raise ValueError("Invalid setting: LY_ADS_MCP_JWT_SIGNING_KEY must differ from LY_ADS_CLIENT_SECRET")


def _read_optional(name: str, default: str | None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    trimmed = value.strip()
    return trimmed if trimmed else default


def _build_api_url(host: str | None) -> str:
    base = (host or "").rstrip("/")
    return f"{base}/api/{API_VERSION}"


def _strip_slash(value: str | None) -> str:
    if value is None:
        return ""
    return value.rstrip("/")


def _read_path(name: str, default: Path) -> Path:
    value = _read_optional(name, str(default))
    return Path(value or default).expanduser().resolve()
