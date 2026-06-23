from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from arnold.workflow import diagnostics


FIXTURE_DIR = Path("tests/fixtures/workflow_authoring")
GRAMMAR_VERSION = "arnold.workflow.authoring.v1"
EXPECTED_CASES = {
    "valid_linear": "valid",
    "invalid_forbidden_root_import": "invalid",
    "invalid_star_import": "invalid",
    "invalid_dynamic_import": "invalid",
    "invalid_intrinsic_shadowing": "invalid",
    "invalid_alias_provenance_loss": "invalid",
}
SOURCE_SPAN_FIELDS = {"start_line", "start_column", "end_line", "end_column"}
COMMON_SIDECAR_FIELDS = {"grammar_version", "source_path", "outcome", "expected_diagnostics"}


def test_python_authoring_acceptance_fixture_set_is_complete() -> None:
    source_cases = {path.stem for path in FIXTURE_DIR.glob("*.py")}
    sidecar_cases = {path.name.removesuffix(".expected.json") for path in FIXTURE_DIR.glob("*.expected.json")}

    assert source_cases == set(EXPECTED_CASES)
    assert sidecar_cases == set(EXPECTED_CASES)


def test_python_authoring_fixture_sidecars_match_contract() -> None:
    known_codes = {code.value for code in diagnostics.DiagnosticCode}

    for case_name, outcome in EXPECTED_CASES.items():
        source_path = FIXTURE_DIR / f"{case_name}.py"
        sidecar = _load_sidecar(case_name)

        expected_fields = COMMON_SIDECAR_FIELDS | ({"expected_provenance"} if outcome == "valid" else set())
        assert set(sidecar) == expected_fields
        assert sidecar["grammar_version"] == GRAMMAR_VERSION
        assert sidecar["source_path"] == source_path.as_posix()
        assert source_path.exists()
        assert sidecar["outcome"] == outcome

        diagnostics_payload = sidecar["expected_diagnostics"]
        if outcome == "valid":
            assert diagnostics_payload == []
            _assert_valid_provenance_sidecar(sidecar, source_path)
        else:
            assert diagnostics_payload
            for diagnostic in diagnostics_payload:
                assert set(diagnostic) >= {"code", "message", "source_span"}
                assert diagnostic["code"] in known_codes
                assert diagnostic["message"]
                _assert_span_matches_source(source_path, diagnostic["source_span"])


def _load_sidecar(case_name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / f"{case_name}.expected.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _assert_valid_provenance_sidecar(sidecar: dict[str, Any], source_path: Path) -> None:
    provenance = sidecar["expected_provenance"]
    assert provenance["workflow"]["id"] == "linear-import-first"
    _assert_span_matches_source(source_path, provenance["workflow"]["source_span"])

    imports = provenance["imports"]
    assert [item["local_name"] for item in imports] == ["workflow", "plan", "execute", "review"]
    assert {item["kind"] for item in imports} == {"intrinsic", "step"}
    for item in imports:
        assert item["module"]
        assert item["qualname"]
        _assert_span_matches_source(source_path, item["source_span"])

    steps = provenance["steps"]
    assert [step["id"] for step in steps] == ["plan", "execute", "review"]
    for step in steps:
        assert step["component_ref"].endswith(f":{step['id']}")
        assert step["generated_dsl_id"] == f"step:{step['id']}"
        assert step["generated_manifest_node_id"] == step["id"]
        _assert_span_matches_source(source_path, step["source_span"])


def _assert_span_matches_source(source_path: Path, span: dict[str, int]) -> None:
    _assert_source_span_shape(span)
    expected = (
        span["start_line"],
        span["start_column"] - 1,
        span["end_line"],
        span["end_column"] - 1,
    )
    actual_spans = {
        (
            node.lineno,
            node.col_offset,
            node.end_lineno,
            node.end_col_offset,
        )
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8")))
        if hasattr(node, "lineno")
    }
    assert expected in actual_spans


def _assert_source_span_shape(span: dict[str, int]) -> None:
    assert set(span) == SOURCE_SPAN_FIELDS
    assert all(isinstance(value, int) for value in span.values())
    assert all(value >= 1 for value in span.values())
    assert (span["end_line"], span["end_column"]) >= (
        span["start_line"],
        span["start_column"],
    )
