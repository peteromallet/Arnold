from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from arnold.cli import workflow as workflow_cli
from arnold.manifest.refs import ImportRef
from arnold.workflow import diagnostics


FIXTURE_DIR = Path("tests/fixtures/workflow_authoring")


def test_workflow_check_source_json_diagnostics_have_agent_schema(
    capsys,
) -> None:
    source_path = FIXTURE_DIR / "invalid_forbidden_root_import.py"

    rc = workflow_cli.main(["check", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["source"] == {"kind": "python", "path": str(source_path)}
    assert len(payload["diagnostics"]) == 1

    diagnostic = payload["diagnostics"][0]
    assert diagnostic["file"] == str(source_path)
    assert diagnostic["line"] == 3
    assert diagnostic["col"] == 1
    assert diagnostic["severity"] == "error"
    assert diagnostic["code"] == "AWF001_INVALID_IMPORT_SOURCE"
    assert diagnostic["message"] == "root package imports are not valid workflow dependencies"
    assert diagnostic["suggestion"]
    assert diagnostic["source_span"] == {
        "path": str(source_path),
        "start_line": 3,
        "start_column": 1,
        "end_line": 3,
        "end_column": 14,
    }
    assert diagnostic["import_ref"] == {
        "module": "arnold",
        "qualname": "__root__",
    }


def test_workflow_check_source_human_diagnostics_show_source_caret_and_fix(
    capsys,
) -> None:
    source_path = FIXTURE_DIR / "invalid_reserved_step_keyword.py"

    rc = workflow_cli.main(["check", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    assert f"{source_path}:9:35" in captured.out
    assert "AWF010_RESERVED_CALL_KEYWORD" in captured.out
    assert "step call keyword 'policy' is reserved" in captured.out
    assert 'plan_output = plan(id="plan", policy=brief)' in captured.out
    assert "^" in captured.out
    assert "Fix:" in captured.out
    assert "reserved keywords are compiler-owned syntax" in captured.out
    assert "generated manifest" not in captured.out.lower()


def test_workflow_check_source_json_spanless_diagnostics_fall_back_to_file(
    capsys,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "invalid_unknown_component.py"
    diagnostic = diagnostics.AuthoringDiagnostic(
        code=diagnostics.DiagnosticCode.UNKNOWN_COMPONENT,
        message="component could not be resolved",
        import_ref=ImportRef("tests.fixtures.workflow_authoring.components", "missing"),
        remediation="export a typed component contract object from the imported module",
    )

    monkeypatch.setattr(
        workflow_cli.workflow,
        "check_workflow_file",
        lambda path: SimpleNamespace(ok=False, diagnostics=(diagnostic,)),
    )

    rc = workflow_cli.main(["check", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["source"] == {"kind": "python", "path": str(source_path)}
    assert len(payload["diagnostics"]) == 1

    rendered = payload["diagnostics"][0]
    assert rendered["file"] == str(source_path)
    assert rendered["line"] is None
    assert rendered["col"] is None
    assert rendered["severity"] == "error"
    assert rendered["code"] == "AWF005_UNKNOWN_COMPONENT"
    assert rendered["message"] == "component could not be resolved"
    assert rendered["suggestion"] == (
        "export a typed component contract object from the imported module"
    )
    assert "source_span" not in rendered


def test_workflow_check_source_human_spanless_diagnostics_do_not_render_caret(
    capsys,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "invalid_unknown_component.py"
    diagnostic = diagnostics.AuthoringDiagnostic(
        code=diagnostics.DiagnosticCode.UNKNOWN_COMPONENT,
        message="component could not be resolved",
        remediation="export a typed component contract object from the imported module",
    )

    monkeypatch.setattr(
        workflow_cli.workflow,
        "check_workflow_file",
        lambda path: SimpleNamespace(ok=False, diagnostics=(diagnostic,)),
    )

    rc = workflow_cli.main(["check", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    assert f"{source_path}:?:?" in captured.out
    assert "AWF005_UNKNOWN_COMPONENT" in captured.out
    assert "component could not be resolved" in captured.out
    assert "Fix: export a typed component contract object from the imported module" in captured.out
    assert "^" not in captured.out


def test_workflow_compile_source_writes_canonical_manifest(tmp_path: Path) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"
    out_path = tmp_path / "manifest.json"

    rc = workflow_cli.main(["compile", str(source_path), "--out", str(out_path)])

    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["id"] == "linear-function"
    assert payload["version"] == "1.0"
    assert payload["manifest_hash"].startswith("sha256:")


def test_workflow_compile_source_failure_does_not_touch_output(tmp_path: Path) -> None:
    source_path = FIXTURE_DIR / "invalid_forbidden_root_import.py"
    out_path = tmp_path / "manifest.json"
    out_path.write_text("{\"keep\": true}", encoding="utf-8")

    rc = workflow_cli.main(["compile", str(source_path), "--out", str(out_path)])

    assert rc == 1
    assert json.loads(out_path.read_text(encoding="utf-8")) == {"keep": True}


def test_workflow_compile_source_failure_emits_diagnostics_json(tmp_path: Path) -> None:
    source_path = FIXTURE_DIR / "invalid_forbidden_root_import.py"
    diag_path = tmp_path / "diagnostics.json"

    rc = workflow_cli.main(
        ["compile", str(source_path), "--out", str(tmp_path / "manifest.json"), "--diagnostics-json", str(diag_path)]
    )

    assert rc == 1
    payload = json.loads(diag_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["source"] == {"kind": "python", "path": str(source_path)}
    assert len(payload["diagnostics"]) == 1
    assert payload["diagnostics"][0]["code"] == "AWF001_INVALID_IMPORT_SOURCE"


def test_workflow_inspect_source_json_has_stable_sections(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["inspect", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"]["id"] == "linear-function"
    assert [c["id"] for c in payload["components"]] == ["plan", "execute", "review"]
    assert len(payload["control_routes"]) == 2


def test_workflow_inspect_source_human_shows_workflow_id(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["inspect", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "linear-function" in captured.out
    assert "control_routes" in captured.out


def test_workflow_explain_source_json_has_ordered_entries(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["explain", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"]["id"] == "linear-function"
    entries = payload["entries"]
    assert len(entries) == 3
    assert entries[0]["kind"] == "step"
    assert entries[0]["id"] == "plan"
    assert "source" in entries[0]


def test_workflow_explain_source_human_lists_steps(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["explain", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "Workflow linear-function" in captured.out
    assert "[step] plan" in captured.out
    assert "[step] execute" in captured.out
    assert "[step] review" in captured.out
