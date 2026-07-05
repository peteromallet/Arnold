from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from arnold.cli import workflow as workflow_cli
from arnold.cli.workflow_diagnostics import normalize_diagnostic
from arnold.manifest.refs import ImportRef
from arnold.workflow import diagnostics
from arnold.workflow import ManifestValidationIssue, SourceSpan
from arnold_pipelines.megaplan.workflows import planning
from tests.fixtures.workflow import demo_pipeline


FIXTURE_DIR = Path("tests/fixtures/workflow_authoring")
DEMO_TARGET = "tests.fixtures.workflow.demo_pipeline:build_pipeline"
MEGAPLAN_SOURCE_PATH = Path("arnold_pipelines/megaplan/workflows/workflow.pypeline")
MEGAPLAN_TARGET = "arnold_pipelines.megaplan.workflows.planning:build_pipeline"


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


def test_workflow_check_source_json_static_prompt_resource_diagnostics(capsys) -> None:
    source_path = FIXTURE_DIR / "invalid_static_prompt_resource_dependencies.py"

    rc = workflow_cli.main(["check", str(source_path), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["source"] == {"kind": "python", "path": str(source_path)}
    assert [diagnostic["code"] for diagnostic in payload["diagnostics"]] == [
        "AWF022_MISSING_PROMPT_DEPENDENCY",
        "AWF023_MISSING_RESOURCE_DEPENDENCY",
    ]
    prompt_diagnostic, resource_diagnostic = payload["diagnostics"]
    assert prompt_diagnostic["line"] == 10
    assert prompt_diagnostic["col"] == 9
    assert prompt_diagnostic["suggestion"] == (
        "attach a PromptComponent to the StepComponent or remove the static prompt_key metadata"
    )
    assert prompt_diagnostic["details"] == {"prompt_key": "review"}
    assert resource_diagnostic["line"] == 11
    assert resource_diagnostic["col"] == 9
    assert resource_diagnostic["suggestion"] == (
        "declare the required resource in component metadata resources or remove the dependency"
    )
    assert resource_diagnostic["details"] == {
        "available_resources": ["cache"],
        "missing_resources": ["model"],
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


def test_manifest_validation_normalization_renders_source_backed_node_issue() -> None:
    span = SourceSpan("workflow.py", 12, 9, 12, 31)
    diagnostic = ManifestValidationIssue(
        code="invalid_node_output",
        message="node 'plan' output has invalid ref format: 'draft/out'",
        field="nodes[].outputs[]",
        node_id="plan",
        source_span=span,
        details={"value": "draft/out"},
    )

    rendered = normalize_diagnostic(diagnostic)

    assert rendered["file"] == "workflow.py"
    assert rendered["line"] == 12
    assert rendered["col"] == 9
    assert rendered["source_span"] == {
        "path": "workflow.py",
        "start_line": 12,
        "start_column": 9,
        "end_line": 12,
        "end_column": 31,
    }
    assert rendered["node_id"] == "plan"
    assert rendered["field"] == "nodes[].outputs[]"
    assert rendered["details"] == {"value": "draft/out"}
    assert rendered["suggestion"] == (
        "edit the authored workflow source for node 'plan' so manifest field "
        "nodes[].outputs[] satisfies validation"
    )


def test_manifest_validation_normalization_renders_source_backed_edge_issue() -> None:
    span = SourceSpan("workflow.py", 14, 9, 14, 41)
    diagnostic = ManifestValidationIssue(
        code="dangling_edge_target",
        message="edge 'plan-review' target 'review' is dangling",
        field="edges[].target",
        edge_id="plan-review",
        source_span=span,
        details={"target": "review"},
    )

    rendered = normalize_diagnostic(diagnostic)

    assert rendered["line"] == 14
    assert rendered["col"] == 9
    assert rendered["edge_id"] == "plan-review"
    assert rendered["source_span"]["path"] == "workflow.py"
    assert rendered["suggestion"] == (
        "edit the authored workflow source for edge 'plan-review' so manifest field "
        "edges[].target satisfies validation"
    )


def test_manifest_validation_normalization_keeps_global_issue_spanless() -> None:
    diagnostic = ManifestValidationIssue(
        code="manifest_hash_mismatch",
        message="manifest_hash does not match canonical manifest",
        field="manifest_hash",
    )

    rendered = normalize_diagnostic(diagnostic, source_path="workflow.py")

    assert rendered["file"] == "workflow.py"
    assert rendered["line"] is None
    assert rendered["col"] is None
    assert "source_span" not in rendered
    assert "node_id" not in rendered
    assert "edge_id" not in rendered
    assert rendered["suggestion"] == (
        "fix manifest-level invariant 'manifest_hash' and regenerate the manifest from valid source"
    )


def test_workflow_check_module_uses_builder_advertised_source_path(
    capsys,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "invalid_forbidden_root_import.py"
    monkeypatch.setattr(
        demo_pipeline.build_pipeline,
        "AUTHORING_SOURCE_PATH",
        source_path,
        raising=False,
    )

    rc = workflow_cli.main(["check", "--module", DEMO_TARGET, "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["source"] == {"kind": "python", "path": str(source_path.resolve())}
    assert payload["diagnostics"][0]["code"] == "AWF001_INVALID_IMPORT_SOURCE"


def test_workflow_check_module_uses_module_advertised_source_path(
    capsys,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"
    monkeypatch.setattr(
        demo_pipeline,
        "AUTHORING_SOURCE_PATH",
        source_path,
        raising=False,
    )

    rc = workflow_cli.main(["check", "--module", DEMO_TARGET, "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload == {
        "ok": True,
        "source": {"kind": "python", "path": str(source_path.resolve())},
        "diagnostics": [],
    }


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


def test_workflow_compile_module_stays_builder_backed_with_advertised_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "invalid_forbidden_root_import.py"
    out_path = tmp_path / "manifest.json"
    monkeypatch.setattr(
        demo_pipeline.build_pipeline,
        "AUTHORING_SOURCE_PATH",
        source_path,
        raising=False,
    )

    rc = workflow_cli.main(["compile", "--module", DEMO_TARGET, "--out", str(out_path)])

    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["id"] == "demo"


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


def test_workflow_inspect_module_uses_advertised_source_path(
    capsys,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"
    monkeypatch.setattr(
        demo_pipeline.build_pipeline,
        "AUTHORING_SOURCE_PATH",
        source_path,
        raising=False,
    )

    rc = workflow_cli.main(["inspect", "--module", DEMO_TARGET, "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"]["id"] == "linear-function"
    assert payload["workflow"]["source_path"] == str(source_path.resolve())
    assert payload["builder_target"] == DEMO_TARGET


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


def test_workflow_explain_module_uses_advertised_source_path(
    capsys,
    monkeypatch,
) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"
    monkeypatch.setattr(
        demo_pipeline.build_pipeline,
        "AUTHORING_SOURCE_PATH",
        source_path,
        raising=False,
    )

    rc = workflow_cli.main(["explain", "--module", DEMO_TARGET, "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"] == {
        "id": "linear-function",
        "version": "1.0",
        "source_path": str(source_path.resolve()),
    }
    assert payload["entries"][0]["id"] == "plan"


def test_workflow_explain_source_human_lists_steps(capsys) -> None:
    source_path = FIXTURE_DIR / "valid_function_linear.py"

    rc = workflow_cli.main(["explain", str(source_path)])

    captured = capsys.readouterr()
    assert rc == 0
    assert "Workflow linear-function" in captured.out
    assert "[step] plan" in captured.out
    assert "[step] execute" in captured.out
    assert "[step] review" in captured.out


def test_workflow_check_megaplan_source_json_envelope(capsys) -> None:
    rc = workflow_cli.main(["check", str(MEGAPLAN_SOURCE_PATH), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload == {
        "ok": True,
        "source": {"kind": "python", "path": str(MEGAPLAN_SOURCE_PATH)},
        "diagnostics": [],
    }


def test_workflow_compile_megaplan_source_writes_manifest(tmp_path: Path) -> None:
    out_path = tmp_path / "megaplan-manifest.json"

    rc = workflow_cli.main(["compile", str(MEGAPLAN_SOURCE_PATH), "--out", str(out_path)])

    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["id"] == "megaplan"
    assert payload["version"] == "m4-phase3"
    assert payload["manifest_hash"].startswith("sha256:")


def test_workflow_inspect_megaplan_source_json_metadata(capsys) -> None:
    rc = workflow_cli.main(["inspect", str(MEGAPLAN_SOURCE_PATH), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["workflow"] == {
        "id": "megaplan",
        "version": "m4-phase3",
        "source_form": "function",
        "function_name": "planning_workflow",
        "parameters": ["brief"],
        "source_path": str(MEGAPLAN_SOURCE_PATH),
    }
    assert {component["id"] for component in payload["components"]} >= {"prep", "plan"}
    assert payload["components"][0]["source_span"]["path"] == str(MEGAPLAN_SOURCE_PATH)


def test_workflow_explain_megaplan_source_json_metadata(capsys) -> None:
    rc = workflow_cli.main(["explain", str(MEGAPLAN_SOURCE_PATH), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["workflow"] == {
        "id": "megaplan",
        "version": "m4-phase3",
        "source_path": str(MEGAPLAN_SOURCE_PATH),
    }
    assert payload["entries"][0]["id"] == "prep"
    assert payload["entries"][0]["source"]["path"] == str(MEGAPLAN_SOURCE_PATH)


def test_workflow_check_megaplan_module_uses_advertised_source_json(capsys) -> None:
    rc = workflow_cli.main(["check", "--module", MEGAPLAN_TARGET, "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload == {
        "ok": True,
        "source": {"kind": "python", "path": str(planning.AUTHORING_SOURCE_PATH)},
        "diagnostics": [],
    }


def test_workflow_explain_megaplan_module_uses_advertised_source_path(
    capsys,
) -> None:
    rc = workflow_cli.main(["explain", "--module", MEGAPLAN_TARGET, "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["workflow"] == {
        "id": "megaplan",
        "version": "m4-phase3",
        "source_path": str(planning.AUTHORING_SOURCE_PATH),
    }
    assert payload["entries"][0]["source"]["path"] == str(planning.AUTHORING_SOURCE_PATH)


# --- .pypeline CLI acceptance tests ---

PYPELINE_FIXTURE = FIXTURE_DIR / "valid_direct_linear.pypeline"


def test_workflow_check_pypeline_source_json_accepts_and_preserves_kind(capsys) -> None:
    rc = workflow_cli.main(["check", str(PYPELINE_FIXTURE), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload == {
        "ok": True,
        "source": {"kind": "python", "path": str(PYPELINE_FIXTURE)},
        "diagnostics": [],
    }


def test_workflow_compile_pypeline_source_writes_manifest(tmp_path: Path) -> None:
    out_path = tmp_path / "manifest.json"

    rc = workflow_cli.main(["compile", str(PYPELINE_FIXTURE), "--out", str(out_path)])

    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["id"] == "linear-direct"
    assert payload["version"] == "1.0"
    assert payload["manifest_hash"].startswith("sha256:")


def test_workflow_inspect_pypeline_source_json_has_stable_sections(capsys) -> None:
    rc = workflow_cli.main(["inspect", str(PYPELINE_FIXTURE), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"]["id"] == "linear-direct"
    assert [c["id"] for c in payload["components"]] == ["plan", "execute", "review"]
    assert len(payload["control_routes"]) == 2


def test_workflow_explain_pypeline_source_json_has_ordered_entries(capsys) -> None:
    rc = workflow_cli.main(["explain", str(PYPELINE_FIXTURE), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["workflow"]["id"] == "linear-direct"
    entries = payload["entries"]
    assert len(entries) == 3
    assert entries[0]["kind"] == "step"
    assert entries[0]["id"] == "plan"
    assert "source" in entries[0]


def test_workflow_graph_pypeline_source_json_includes_spans(capsys) -> None:
    rc = workflow_cli.main(["graph", str(PYPELINE_FIXTURE), "--format", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert len(payload["nodes"]) == 3
    for node in payload["nodes"]:
        assert "source_span" in node
        span = node["source_span"]
        assert span is not None
        assert span["path"] == str(PYPELINE_FIXTURE)
    assert len(payload["edges"]) == 2
