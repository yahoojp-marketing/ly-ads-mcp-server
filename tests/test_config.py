from __future__ import annotations

import pytest

from ly_ads_mcp.api_version import API_VERSION
from ly_ads_mcp.config import get_settings, resolve_settings


def _set_required_env(monkeypatch):
    monkeypatch.setenv("LY_ADS_CLIENT_ID", "client-id")
    monkeypatch.setenv("LY_ADS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("LY_ADS_MCP_JWT_SIGNING_KEY", "jwt-signing-key-with-at-least-32-characters")


def test_resolve_settings_uses_production_endpoints_by_default(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("LY_ADS_OAUTH_BASE_URL", raising=False)
    monkeypatch.delenv("LY_ADS_DISPLAY_API_HOST", raising=False)
    monkeypatch.delenv("LY_ADS_SEARCH_API_HOST", raising=False)
    monkeypatch.delenv("LY_ADS_REPORT_OUTPUT_DIR", raising=False)

    settings = resolve_settings()

    assert settings.jwt_signing_key == "jwt-signing-key-with-at-least-32-characters"
    assert settings.oauth_base_url == "https://biz-oauth.yahoo.co.jp/oauth/v1"
    assert settings.display_api_base_url == f"https://ads-display.yahooapis.jp/api/{API_VERSION}"
    assert settings.search_api_base_url == f"https://ads-search.yahooapis.jp/api/{API_VERSION}"
    assert settings.report_output_dir.name == "reports"
    assert settings.mcp_base_url == "http://localhost:18765"
    assert settings.mcp_host == "localhost"
    assert settings.mcp_port == 18765


def test_resolve_settings_uses_configured_report_output_directory(monkeypatch, tmp_path):
    _set_required_env(monkeypatch)
    report_output_dir = tmp_path / "custom-reports"
    monkeypatch.setenv("LY_ADS_REPORT_OUTPUT_DIR", str(report_output_dir))

    settings = resolve_settings()

    assert settings.report_output_dir == report_output_dir


def test_resolve_settings_resolves_default_report_output_directory_from_cwd(monkeypatch, tmp_path):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("LY_ADS_REPORT_OUTPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = resolve_settings()

    assert settings.report_output_dir == tmp_path / "reports"


def test_get_settings_keeps_report_output_directory_fixed(monkeypatch, tmp_path):
    _set_required_env(monkeypatch)
    initial_directory = tmp_path / "initial"
    monkeypatch.setenv("LY_ADS_REPORT_OUTPUT_DIR", str(initial_directory))

    settings = get_settings()
    monkeypatch.setenv("LY_ADS_REPORT_OUTPUT_DIR", str(tmp_path / "changed"))

    assert get_settings() is settings
    assert get_settings().report_output_dir == initial_directory


@pytest.mark.parametrize("value", [None, "", "   "])
def test_resolve_settings_rejects_missing_jwt_signing_key(monkeypatch, value):
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("LY_ADS_MCP_JWT_SIGNING_KEY")
    else:
        monkeypatch.setenv("LY_ADS_MCP_JWT_SIGNING_KEY", value)

    with pytest.raises(ValueError, match="LY_ADS_MCP_JWT_SIGNING_KEY"):
        resolve_settings()


@pytest.mark.parametrize(
    ("name", "placeholder"),
    [
        ("LY_ADS_CLIENT_ID", "<your_client_id>"),
        ("LY_ADS_CLIENT_SECRET", "<your_client_secret>"),
        ("LY_ADS_MCP_JWT_SIGNING_KEY", "<your_jwt_signing_key>"),
    ],
)
def test_resolve_settings_rejects_example_placeholders(monkeypatch, name, placeholder):
    _set_required_env(monkeypatch)
    monkeypatch.setenv(name, placeholder)

    with pytest.raises(ValueError, match=f"Invalid placeholder setting: {name}"):
        resolve_settings()


def test_resolve_settings_rejects_short_jwt_signing_key(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LY_ADS_MCP_JWT_SIGNING_KEY", "x" * 31)

    with pytest.raises(ValueError, match="must be at least 32 characters"):
        resolve_settings()


def test_resolve_settings_rejects_jwt_signing_key_equal_to_client_secret(monkeypatch):
    _set_required_env(monkeypatch)
    shared_secret = "秘密" * 16
    monkeypatch.setenv("LY_ADS_CLIENT_SECRET", shared_secret)
    monkeypatch.setenv("LY_ADS_MCP_JWT_SIGNING_KEY", shared_secret)

    with pytest.raises(ValueError, match="must differ from LY_ADS_CLIENT_SECRET") as exc_info:
        resolve_settings()

    assert shared_secret not in str(exc_info.value)
