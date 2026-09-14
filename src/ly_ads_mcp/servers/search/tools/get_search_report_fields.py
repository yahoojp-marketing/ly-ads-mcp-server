# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the get_search_report_fields MCP tool."""

from __future__ import annotations

import asyncio

from fastmcp.exceptions import ToolError
from pydantic import Field

from ly_ads_mcp.api_utils import raise_for_api_errors, to_plain_dict
from ly_ads_mcp.servers.common.pagination import McpOutputModel, StrictRequestModel

from ..client import (
    ReportDefinitionServiceApi,
    ReportDefinitionServiceGetReportFields,
    ReportDefinitionServiceReportType,
)
from .base import SearchHandlers


class GetSearchReportFieldsRequest(StrictRequestModel):
    report_type: ReportDefinitionServiceReportType = Field(
        description="LY Ads Search Ads report type whose available report-definition fields are returned."
    )


class SearchReportField(McpOutputModel):
    filterable: bool | None = Field(
        default=None,
        description="Whether this field can be used in a report filter.",
    )
    selectable: bool | None = Field(
        default=None,
        description="Whether this field can be selected for report output.",
    )
    display_field_name_en: str | None = Field(
        default=None,
        description="Field name displayed in downloaded reports in English.",
    )
    display_field_name_ja: str | None = Field(
        default=None,
        description="Field name displayed in downloaded reports in Japanese.",
    )
    field_name: str | None = Field(
        default=None,
        description="Field identifier used in a Search Ads report definition.",
    )
    field_type: str | None = Field(
        default=None,
        description="Value type of the report field, such as an integer, string, or enum.",
    )
    impossible_combination_fields: list[str] | None = Field(
        default=None,
        description="Other report fields that cannot be selected together with this field.",
    )
    xml_attribute_name: str | None = Field(
        default=None,
        description="XML attribute name used for this field in a downloaded report.",
    )


class GetSearchReportFieldsResult(McpOutputModel):
    report_type: ReportDefinitionServiceReportType = Field(
        description="LY Ads Search Ads report type requested by the caller."
    )
    fields: list[SearchReportField] = Field(
        description="Report-definition fields available for the requested report type."
    )


async def get_search_report_fields(
    handlers: SearchHandlers,
    request: GetSearchReportFieldsRequest,
) -> GetSearchReportFieldsResult:
    with handlers.api_client() as client:
        api = ReportDefinitionServiceApi(client)
        response = await asyncio.to_thread(
            api.report_definition_service_get_report_fields_post,
            report_definition_service_get_report_fields=ReportDefinitionServiceGetReportFields(
                report_type=request.report_type
            ),
        )

    raise_for_api_errors(response)
    rval = getattr(response, "rval", None)
    if rval is None:
        raise ToolError(
            "LY Ads Search Ads API returned no report-field result. "
            "Retry the request; if it persists, report the upstream API response."
        )
    if getattr(rval, "operation_succeeded", None) is False:
        raise ToolError(
            "LY Ads Search Ads API failed to retrieve report fields without error details. "
            "Choose a concrete reportType other than UNKNOWN and retry."
        )

    fields = getattr(rval, "fields", None)
    if fields is None:
        raise ToolError(
            "LY Ads Search Ads API reported success without report fields. "
            "Retry the request; if it persists, report the upstream API response."
        )

    return GetSearchReportFieldsResult(
        report_type=request.report_type,
        fields=[SearchReportField.model_validate(to_plain_dict(field)) for field in fields],
    )
