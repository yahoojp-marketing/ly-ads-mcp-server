# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastmcp.exceptions import ToolError


class LyAdsApiResponseError(Exception):
    def __init__(self, errors: Sequence[Any]) -> None:
        super().__init__("LY Ads API returned errors in a successful HTTP response")
        self.errors = tuple(errors)


def to_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, exclude_none=True)
    raise ToolError(f"unsupported API response type: {type(value)}")


def extract_rval(response: Any) -> tuple[list[Any], int]:
    """Extract (values, total_num_entries) from a typed API response object."""
    raise_for_api_errors(response)
    rval = getattr(response, "rval", None)
    values = (getattr(rval, "values", None) or []) if rval is not None else []
    total = int(getattr(rval, "total_num_entries", None) or 0) if rval is not None else 0
    return list(values), total


def raise_for_api_errors(response: Any) -> None:
    errors = _collect_api_errors(response)
    if errors:
        raise LyAdsApiResponseError(errors)


def _collect_api_errors(response: Any) -> list[Any]:
    containers = [response]
    rval = getattr(response, "rval", None)
    if rval is not None:
        containers.append(rval)
        values = getattr(rval, "values", None)
        if isinstance(values, list):
            containers.extend(value for value in values if value is not None)

    errors = []
    for container in containers:
        container_errors = getattr(container, "errors", None)
        if isinstance(container_errors, list):
            errors.extend(error for error in container_errors if error is not None)
    return errors
