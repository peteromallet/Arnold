from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers.hermes import (
    _content_xml_tool_calls,
    _normalize_response_content_tool_calls,
)
from arnold_pipelines.megaplan.workers._impl import _repair_worker_json_once


def _arguments(call: SimpleNamespace) -> dict[str, object]:
    return json.loads(call.function.arguments)


def test_content_tool_calls_parse_self_closing_read_file_alias() -> None:
    calls = _content_xml_tool_calls('<file_read path="src/app.py" offset="3" limit="12"/>')

    assert len(calls) == 1
    assert calls[0].function.name == "read_file"
    assert _arguments(calls[0]) == {"path": "src/app.py", "offset": 3, "limit": 12}


def test_content_tool_calls_parse_invoke_read_alias() -> None:
    calls = _content_xml_tool_calls(
        '<invoke name="read"><parameter name="filePath">src/app.py</parameter></invoke>'
    )

    assert len(calls) == 1
    assert calls[0].function.name == "read_file"
    assert _arguments(calls[0]) == {"path": "src/app.py"}


def test_normalize_response_rejects_write_tool_markup() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='<write_file path="critique_check_scope.json">{"checks":[]}</write_file>',
                    tool_calls=None,
                )
            )
        ]
    )

    with pytest.raises(CliError, match="unsupported tool-call markup"):
        _normalize_response_content_tool_calls(response)


def test_critique_repair_reports_tool_markup_and_check_context() -> None:
    raw = '<read_file path="critique_check_scope.json"/>'

    with pytest.raises(CliError) as excinfo:
        _repair_worker_json_once(
            "critique",
            raw,
            lambda _prompt: "<tool_result>unchanged</tool_result>",
            validate=False,
            template_unchanged=True,
            check_id="scope",
            question="Does the plan cover the requested scope?",
        )

    error = excinfo.value
    assert "unsupported tool-call markup" in error.message
    assert "critique template unchanged" in error.message
    assert "scope" in error.message
    assert error.extra["unsupported_tool_call_markup"] is True
    assert error.extra["critique_template_unchanged"] is True
