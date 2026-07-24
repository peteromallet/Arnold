from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers.hermes import (
    _content_xml_tool_calls,
    _normalize_response_content_tool_calls,
)
from arnold_pipelines.megaplan.workers._impl import (
    _contains_mutating_deepseek_tool_markup,
    _deepseek_tool_markup_names,
    _repair_worker_json_once,
)


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


@pytest.mark.parametrize(
    "markup",
    [
        "<read_file></read_file>",
        '<read_file path="   "/>',
        '<file_read offset="3"/>',
        '<invoke name="read"><parameter name="offset">3</parameter></invoke>',
        "<search_files></search_files>",
        '<web_search query="   "/>',
        "<web_extract></web_extract>",
    ],
)
def test_content_tool_calls_ignore_markup_missing_required_args(markup: str) -> None:
    assert _content_xml_tool_calls(markup) == []


def test_normalize_response_recovers_write_tool_markup() -> None:
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

    _normalize_response_content_tool_calls(response)
    assert response.choices[0].message.content == '{"checks":[]}'


def test_normalize_response_recovers_invoke_write_file_markup() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '<invoke name="write_file">'
                        '<parameter name="path">critique_check_scope.json</parameter>'
                        '<parameter name="content">{"checks":[{"id":"scope","status":"ok"}]}</parameter>'
                        '</invoke>'
                    ),
                    tool_calls=None,
                )
            )
        ]
    )

    _normalize_response_content_tool_calls(response)
    assert json.loads(response.choices[0].message.content)["checks"][0]["id"] == "scope"


def test_normalize_response_still_rejects_unrecoverable_write_markup() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='<write_file path="x.txt">not valid json</write_file>',
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


def test_deepseek_tool_markup_names_detects_dsml_invoke() -> None:
    raw = '<｜DSML｜invoke name="write_file"><｜DSML｜parameter name="path">x.json</｜DSML｜parameter></｜DSML｜invoke>'
    assert "write_file" in _deepseek_tool_markup_names(raw)
    assert _contains_mutating_deepseek_tool_markup(raw)


def test_normalize_response_recovers_dsml_invoke_write_file_markup() -> None:
    payload = json.dumps({"checks": [{"id": "scope", "status": "ok"}]})
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '<｜DSML｜invoke name="write_file">'
                        '<｜DSML｜parameter name="path">critique_check_scope.json</｜DSML｜parameter>'
                        f'<｜DSML｜parameter name="content">{payload}</｜DSML｜parameter>'
                        '</｜DSML｜invoke>'
                    ),
                    tool_calls=None,
                )
            )
        ]
    )

    _normalize_response_content_tool_calls(response)
    assert json.loads(response.choices[0].message.content)["checks"][0]["id"] == "scope"


def test_normalize_response_recovers_bash_heredoc_markup() -> None:
    payload = json.dumps({"checks": [{"id": "scope", "status": "ok"}]})
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '<bash>cat <<\'EOF\' > critique_check_scope.json\n'
                        f'{payload}\n'
                        'EOF</bash>'
                    ),
                    tool_calls=None,
                )
            )
        ]
    )

    _normalize_response_content_tool_calls(response)
    assert json.loads(response.choices[0].message.content)["checks"][0]["id"] == "scope"
