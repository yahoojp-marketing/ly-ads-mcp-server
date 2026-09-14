# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
"""Schemas and implementation for the get_display_report_fields MCP tool."""

from __future__ import annotations

import asyncio

from fastmcp.exceptions import ToolError
from pydantic import Field

from ly_ads_mcp.api_utils import raise_for_api_errors, to_plain_dict
from ly_ads_mcp.servers.common.pagination import McpOutputModel, StrictRequestModel

from ..client import (
    ReportDefinitionServiceApi,
    ReportDefinitionServiceGetReportFields,
    ReportDefinitionServiceLang,
    ReportDefinitionServiceReportType,
)
from .base import DisplayHandlers


class GetDisplayReportFieldsRequest(StrictRequestModel):
    lang: ReportDefinitionServiceLang = Field(
        description="Language used for displayFieldName values in the Display Ads report-field metadata."
    )
    report_type: ReportDefinitionServiceReportType = Field(
        description="Display Ads report type whose available fields are returned."
    )


class DisplayReportField(McpOutputModel):
    display_field_name: str | None = Field(
        default=None,
        description="Localized field name shown in a downloaded Display Ads report.",
    )
    field_name: str | None = Field(
        default=None,
        description="Field identifier to use in a Display Ads report definition.",
    )
    field_type: str | None = Field(
        default=None,
        description="Field data type, such as a number, string, or enum.",
    )
    filterable: bool | None = Field(
        default=None,
        description="Whether the field can be used as a Display Ads report filter.",
    )
    impossible_combination_fields: list[str] | None = Field(
        default=None,
        description="Field identifiers that cannot be selected together with this field.",
    )
    xml_attribute_name: str | None = Field(
        default=None,
        description="XML attribute name used for this field in downloaded XML reports.",
    )


class GetDisplayReportFieldsResult(McpOutputModel):
    lang: ReportDefinitionServiceLang = Field(
        description="Language requested for displayFieldName values."
    )
    report_type: ReportDefinitionServiceReportType = Field(
        description="Display Ads report type to which the returned fields apply."
    )
    fields: list[DisplayReportField] = Field(
        description="Fields available for the requested Display Ads report type."
    )


async def get_display_report_fields(
    handlers: DisplayHandlers,
    request: GetDisplayReportFieldsRequest,
) -> GetDisplayReportFieldsResult:
    with handlers.api_client() as client:
        api = ReportDefinitionServiceApi(client)
        response = await asyncio.to_thread(
            api.report_definition_service_get_report_fields_post,
            report_definition_service_get_report_fields=ReportDefinitionServiceGetReportFields(
                lang=request.lang,
                report_type=request.report_type,
            ),
        )

    raise_for_api_errors(response)
    rval = getattr(response, "rval", None)
    if rval is None:
        raise ToolError(
            "LY Ads Display Ads API returned no report-field result. "
            "Retry the request; if it persists, report the upstream API response."
        )
    if getattr(rval, "operation_succeeded", None) is not True:
        raise ToolError(
            "LY Ads Display Ads API failed to get report fields without error details. Check lang and reportType."
        )

    return GetDisplayReportFieldsResult(
        lang=request.lang,
        report_type=request.report_type,
        fields=[DisplayReportField.model_validate(to_plain_dict(field)) for field in rval.fields],
    )
