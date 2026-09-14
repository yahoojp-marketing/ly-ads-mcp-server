from __future__ import annotations

import pytest
from fakes import FakeApiResponse, FakeHandlers, FakeRval
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ly_ads_mcp.servers.common.pagination import DEFAULT_PAGE_SIZE
from ly_ads_mcp.servers.display.tools import list_display_labels as list_display_labels_tool
from ly_ads_mcp.servers.display.tools.list_display_labels import ListDisplayLabelsRequest


class FakeLabel:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeLabelValue:
    def __init__(self, label=None):
        self.label = label


async def test_list_display_labels_maps_request_to_selector(monkeypatch, patch_to_thread):
    captured = {}

    class FakeLabelServiceApi:
        def __init__(self, client):
            pass

        def label_service_get_post(self, x_z_base_account_id, label_service_selector):
            captured["base_account_id"] = x_z_base_account_id
            captured["selector"] = label_service_selector
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeLabelValue(
                            label=FakeLabel(
                                {
                                    "accountId": 456,
                                    "labelId": 789,
                                    "labelName": "Important",
                                    "color": "#FF0000",
                                    "description": "Important campaigns",
                                }
                            )
                        )
                    ],
                    total=1,
                )
            )

    monkeypatch.setattr(list_display_labels_tool, "LabelServiceApi", FakeLabelServiceApi)
    result = await list_display_labels_tool.list_display_labels(
        FakeHandlers(),
        ListDisplayLabelsRequest(
            base_account_id=123,
            account_id=456,
            label_ids=[789],
        ),
    )

    selector = captured["selector"]
    assert captured["base_account_id"] == 123
    assert selector.account_id == 456
    assert selector.label_ids == [789]
    assert selector.start_index == 1
    assert selector.number_results == DEFAULT_PAGE_SIZE
    assert result.items[0].base_account_id == 123
    assert result.items[0].account_id == 456
    assert result.items[0].label_id == 789
    assert result.items[0].label_name == "Important"
    assert result.items[0].color == "#FF0000"
    assert result.items[0].description == "Important campaigns"


async def test_list_display_labels_uses_fixed_page_size_across_pages(monkeypatch, patch_to_thread):
    captured = []

    class FakeLabelServiceApi:
        def __init__(self, client):
            pass

        def label_service_get_post(self, x_z_base_account_id, label_service_selector):
            captured.append((x_z_base_account_id, label_service_selector))
            return FakeApiResponse(
                rval=FakeRval(
                    values=[
                        FakeLabelValue(label=FakeLabel({"labelId": label_id}))
                        for label_id in range(label_service_selector.number_results)
                    ],
                    total=DEFAULT_PAGE_SIZE * 2,
                )
            )

    monkeypatch.setattr(list_display_labels_tool, "LabelServiceApi", FakeLabelServiceApi)
    handlers = FakeHandlers()
    first = await list_display_labels_tool.list_display_labels(
        handlers,
        ListDisplayLabelsRequest(base_account_id=123, account_id=456),
    )
    continued = await list_display_labels_tool.list_display_labels(
        handlers,
        cursor=first.next_cursor,
    )

    assert [base_account_id for base_account_id, _ in captured] == [123, 123]
    assert [selector.account_id for _, selector in captured] == [456, 456]
    assert [selector.number_results for _, selector in captured] == [DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE]
    assert [selector.start_index for _, selector in captured] == [1, DEFAULT_PAGE_SIZE + 1]
    assert continued.next_cursor is None


async def test_list_display_labels_rejects_value_with_no_label(monkeypatch, patch_to_thread):
    class FakeLabelServiceApi:
        def __init__(self, client):
            pass

        def label_service_get_post(self, x_z_base_account_id, label_service_selector):
            return FakeApiResponse(rval=FakeRval(values=[FakeLabelValue(label=None)], total=1))

    monkeypatch.setattr(list_display_labels_tool, "LabelServiceApi", FakeLabelServiceApi)

    with pytest.raises(ToolError, match="label entry without label data"):
        await list_display_labels_tool.list_display_labels(
            FakeHandlers(),
            ListDisplayLabelsRequest(base_account_id=123, account_id=456),
        )


def test_list_display_labels_rejects_too_many_label_ids():
    with pytest.raises(ValidationError):
        ListDisplayLabelsRequest(
            base_account_id=123,
            account_id=456,
            label_ids=list(range(DEFAULT_PAGE_SIZE + 1)),
        )
