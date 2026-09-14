from __future__ import annotations

from types import SimpleNamespace

import pytest
from fakes import FakeApiResponse, FakeHandlers
from fastmcp.exceptions import ToolError

from ly_ads_mcp.api_utils import LyAdsApiResponseError
from ly_ads_mcp.servers.search.client import ReportDefinitionServiceReportType
from ly_ads_mcp.servers.search.tools import get_search_report_fields as get_search_report_fields_tool
from ly_ads_mcp.servers.search.tools.get_search_report_fields import GetSearchReportFieldsRequest


class FakeReportField:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


async def test_get_search_report_fields_maps_request_and_response(monkeypatch, patch_to_thread):
    captured = {}

    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(
            self, report_definition_service_get_report_fields
        ):
            captured["request"] = report_definition_service_get_report_fields
            return FakeApiResponse(
                rval=SimpleNamespace(
                    operation_succeeded=True,
                    errors=None,
                    fields=[
                        FakeReportField(
                            {
                                "fieldName": "CAMPAIGN_ID",
                                "fieldType": "LONG",
                                "displayFieldNameEn": "Campaign ID",
                                "displayFieldNameJa": "キャンペーンID",
                                "selectable": True,
                                "filterable": True,
                                "impossibleCombinationFields": ["OTHER_FIELD"],
                                "xmlAttributeName": "campaignID",
                            }
                        )
                    ],
                )
            )

    monkeypatch.setattr(
        get_search_report_fields_tool,
        "ReportDefinitionServiceApi",
        FakeReportDefinitionServiceApi,
    )

    result = await get_search_report_fields_tool.get_search_report_fields(
        FakeHandlers(),
        GetSearchReportFieldsRequest(report_type=ReportDefinitionServiceReportType.CAMPAIGN),
    )

    assert captured["request"].report_type is ReportDefinitionServiceReportType.CAMPAIGN
    assert result.report_type is ReportDefinitionServiceReportType.CAMPAIGN
    assert result.fields[0].field_name == "CAMPAIGN_ID"
    assert result.fields[0].field_type == "LONG"
    assert result.fields[0].impossible_combination_fields == ["OTHER_FIELD"]


async def test_get_search_report_fields_rejects_missing_result(monkeypatch, patch_to_thread):
    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(
            self, report_definition_service_get_report_fields
        ):
            return FakeApiResponse(rval=None)

    monkeypatch.setattr(
        get_search_report_fields_tool,
        "ReportDefinitionServiceApi",
        FakeReportDefinitionServiceApi,
    )

    with pytest.raises(ToolError, match="returned no report-field result"):
        await get_search_report_fields_tool.get_search_report_fields(
            FakeHandlers(),
            GetSearchReportFieldsRequest(report_type=ReportDefinitionServiceReportType.CAMPAIGN),
        )


async def test_get_search_report_fields_reports_operation_errors(monkeypatch, patch_to_thread):
    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(
            self, report_definition_service_get_report_fields
        ):
            return FakeApiResponse(
                rval=SimpleNamespace(
                    operation_succeeded=False,
                    errors=[SimpleNamespace(code="E0001", message="Invalid report type")],
                    fields=None,
                )
            )

    monkeypatch.setattr(
        get_search_report_fields_tool,
        "ReportDefinitionServiceApi",
        FakeReportDefinitionServiceApi,
    )

    with pytest.raises(LyAdsApiResponseError) as exc_info:
        await get_search_report_fields_tool.get_search_report_fields(
            FakeHandlers(),
            GetSearchReportFieldsRequest(report_type=ReportDefinitionServiceReportType.UNKNOWN),
        )

    assert exc_info.value.errors[0].code == "E0001"
    assert exc_info.value.errors[0].message == "Invalid report type"


async def test_get_search_report_fields_rejects_success_without_fields(
    monkeypatch, patch_to_thread
):
    class FakeReportDefinitionServiceApi:
        def __init__(self, client):
            pass

        def report_definition_service_get_report_fields_post(
            self, report_definition_service_get_report_fields
        ):
            return FakeApiResponse(
                rval=SimpleNamespace(operation_succeeded=True, errors=None, fields=None)
            )

    monkeypatch.setattr(
        get_search_report_fields_tool,
        "ReportDefinitionServiceApi",
        FakeReportDefinitionServiceApi,
    )

    with pytest.raises(ToolError, match="reported success without report fields"):
        await get_search_report_fields_tool.get_search_report_fields(
            FakeHandlers(),
            GetSearchReportFieldsRequest(report_type=ReportDefinitionServiceReportType.CAMPAIGN),
        )
