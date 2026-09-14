from __future__ import annotations

from types import SimpleNamespace

import pytest
from fakes import FakeApiResponse, FakeRval, FakeValue

from ly_ads_mcp.api_utils import LyAdsApiResponseError, extract_rval


def test_extract_rval_returns_values_and_total():
    rval = FakeRval(values=[FakeValue(), FakeValue()], total=10)
    values, total = extract_rval(FakeApiResponse(rval=rval))
    assert len(values) == 2
    assert total == 10


def test_extract_rval_when_rval_is_none():
    values, total = extract_rval(FakeApiResponse(rval=None))
    assert values == []
    assert total == 0


def test_extract_rval_rejects_top_level_api_errors():
    error = SimpleNamespace(code="V0001", message="Invalid value.")

    with pytest.raises(LyAdsApiResponseError) as exc_info:
        extract_rval(FakeApiResponse(errors=[error]))

    assert exc_info.value.errors == (error,)


def test_extract_rval_rejects_rval_and_value_api_errors():
    rval_error = SimpleNamespace(code="V0001", message="Invalid selector.")
    value_error = SimpleNamespace(code="V0002", message="Invalid account.")
    rval = SimpleNamespace(
        errors=[rval_error],
        values=[SimpleNamespace(errors=[value_error])],
        total_num_entries=0,
    )

    with pytest.raises(LyAdsApiResponseError) as exc_info:
        extract_rval(FakeApiResponse(rval=rval))

    assert exc_info.value.errors == (rval_error, value_error)
