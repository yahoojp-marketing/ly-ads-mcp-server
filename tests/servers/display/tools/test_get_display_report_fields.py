from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers
from fastmcp.exceptions import ToolError

from ly_ads_mcp.api_utils import LyAdsApiResponseError
from ly_ads_mcp.servers.display.client import (
    ReportDefinitionServiceLang,
    ReportDefinitionServiceReportType,
)
from ly_ads_mcp.servers.display.tools import get_display_report_fields as get_display_report_fields_tool
from ly_ads_mcp.servers.display.tools.get_display_report_fields import GetDisplayReportFieldsRequest


class FakeReportField:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeReportFieldsRval:
    def __init__(self, *, operation_succeeded=True, fields=None, errors=None):
        self.operation_succeeded = operation_succeeded
        self.fields = fields
        self.errors = errors


class FakeError:
    def __init__(self, code=None, message=None):
        self.code = code
        self.message = message


async def test_get_display_report_fields_maps_request_and_response(monkeypatch, patch_to_thread):
    captured = {}

    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(self, report_definition_service_get_report_fields):
            captured["request"] = report_definition_service_get_report_fields
            return FakeApiResponse(
                rval=FakeReportFieldsRval(
                    fields=[
                        FakeReportField(
                            {
                                "displayFieldName": "Campaign ID",
                                "fieldName": "CAMPAIGN_ID",
                                "fieldType": "LONG",
                                "filterable": True,
                                "impossibleCombinationFields": ["AD_ID"],
                                "xmlAttributeName": "campaignId",
                            }
                        )
                    ]
                )
            )

    monkeypatch.setattr(get_display_report_fields_tool, "ReportDefinitionServiceApi", FakeReportDefinitionServiceApi)
    result = await get_display_report_fields_tool.get_display_report_fields(
        FakeHandlers(),
        GetDisplayReportFieldsRequest(
            lang=ReportDefinitionServiceLang.EN,
            report_type=ReportDefinitionServiceReportType.AD,
        ),
    )

    api_request = captured["request"]
    assert api_request.lang == ReportDefinitionServiceLang.EN
    assert api_request.report_type == ReportDefinitionServiceReportType.AD
    assert result.lang == ReportDefinitionServiceLang.EN
    assert result.report_type == ReportDefinitionServiceReportType.AD
    assert result.fields[0].field_name == "CAMPAIGN_ID"
    assert result.fields[0].filterable is True
    assert result.fields[0].impossible_combination_fields == ["AD_ID"]


async def test_get_display_report_fields_allows_an_empty_field_list(monkeypatch, patch_to_thread):
    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(self, report_definition_service_get_report_fields):
            return FakeApiResponse(rval=FakeReportFieldsRval(fields=[]))

    monkeypatch.setattr(get_display_report_fields_tool, "ReportDefinitionServiceApi", FakeReportDefinitionServiceApi)
    result = await get_display_report_fields_tool.get_display_report_fields(
        FakeHandlers(),
        GetDisplayReportFieldsRequest(
            lang=ReportDefinitionServiceLang.JA,
            report_type=ReportDefinitionServiceReportType.REACH,
        ),
    )

    assert result.fields == []


@pytest.mark.parametrize(
    ("rval", "message"),
    [
        (None, "returned no report-field result"),
    ],
)
async def test_get_display_report_fields_rejects_invalid_api_results(monkeypatch, patch_to_thread, rval, message):
    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(self, report_definition_service_get_report_fields):
            return FakeApiResponse(rval=rval)

    monkeypatch.setattr(get_display_report_fields_tool, "ReportDefinitionServiceApi", FakeReportDefinitionServiceApi)

    with pytest.raises(ToolError, match=message):
        await get_display_report_fields_tool.get_display_report_fields(
            FakeHandlers(),
            GetDisplayReportFieldsRequest(
                lang=ReportDefinitionServiceLang.EN,
                report_type=ReportDefinitionServiceReportType.AD,
            ),
        )


async def test_get_display_report_fields_uses_common_api_response_error(monkeypatch, patch_to_thread):
    error = FakeError(code="V0001", message="Invalid value.")

    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(self, report_definition_service_get_report_fields):
            return FakeApiResponse(
                rval=FakeReportFieldsRval(
                    operation_succeeded=False,
                    fields=None,
                    errors=[error],
                )
            )

    monkeypatch.setattr(get_display_report_fields_tool, "ReportDefinitionServiceApi", FakeReportDefinitionServiceApi)

    with pytest.raises(LyAdsApiResponseError) as exc_info:
        await get_display_report_fields_tool.get_display_report_fields(
            FakeHandlers(),
            GetDisplayReportFieldsRequest(
                lang=ReportDefinitionServiceLang.EN,
                report_type=ReportDefinitionServiceReportType.AD,
            ),
        )

    assert exc_info.value.errors == (error,)
