# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from ads_display_client.exceptions import ApiException as DisplayApiException
from ads_search_client.exceptions import ApiException as SearchApiException
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from pydantic import ValidationError

from ly_ads_mcp.api_utils import LyAdsApiResponseError, to_plain_dict


class LyAdsApiErrorMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next) -> Any:
        try:
            return await call_next(context)
        except ToolError as exc:
            if isinstance(exc.__cause__, (DisplayApiException, SearchApiException)):
                raise ToolError(_format_api_error(exc.__cause__)) from exc.__cause__
            if isinstance(exc.__cause__, LyAdsApiResponseError):
                raise ToolError(_format_response_error(exc.__cause__)) from exc.__cause__
            raise
        except (DisplayApiException, SearchApiException) as exc:
            raise ToolError(_format_api_error(exc)) from exc
        except LyAdsApiResponseError as exc:
            raise ToolError(_format_response_error(exc)) from exc
        except ValidationError as exc:
            raise ToolError(f"Validation error: please check your arguments. Details: {exc}") from exc


def _format_api_error(exc: DisplayApiException | SearchApiException) -> str:
    try:
        body = json.loads(exc.body)
        errors = body.get("errors", [])
        if errors:
            return _format_errors(f"LY Ads API error (HTTP {exc.status})", errors)
    except Exception:
        pass
    return f"LY Ads API error (HTTP {exc.status})"


def _format_response_error(exc: LyAdsApiResponseError) -> str:
    return _format_errors("LY Ads API error", exc.errors)


def _format_errors(prefix: str, errors: Iterable[Any]) -> str:
    summaries = [_format_error(error) for error in errors]
    details = "; ".join(summary for summary in summaries if summary)
    return f"{prefix}: {details}" if details else prefix


def _format_error(error: Any) -> str:
    data = to_plain_dict(error)
    summary = ": ".join(str(value) for value in (data.get("code"), data.get("message")) if value)

    formatted_details = []
    for detail in data.get("details") or []:
        parts = [
            f"{key}={detail[key]}"
            for key in ("requestKey", "requestValue")
            if detail.get(key) is not None
        ]
        if parts:
            formatted_details.append(", ".join(parts))

    if not formatted_details:
        return summary

    detail_text = "; ".join(formatted_details)
    return f"{summary} ({detail_text})" if summary else detail_text
