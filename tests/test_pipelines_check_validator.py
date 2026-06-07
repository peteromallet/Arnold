"""W7 — pipelines check static graph validator tests (T13).

Validator scope: Edge.target real-stage-or-halt, no 'halt' as edge LABEL
(except the conventional terminal pair), every decision edge has a valid
label matching the stage's decision vocabulary, and reachability from
entry. NO Port resolution (M2).  M3b: decision edges use kind='decision';
kind='gate' edges are legacy and validated alongside kind='decision'.
"""

from __future__ import annotations

import os
import subprocess
import sys
from argparse import Namespace

from arnold.pipelines.megaplan._pipeline.judge_manifest import (
    EVALUAND_RECORD_CONTENT_TYPE,
    JudgeManifestPort,
    dump_judge_manifest,
    make_judge_manifest,
)
from arnold.pipelines.megaplan._pipeline.judge_manifest_discovery import validate_judge_manifest
from arnold.pipelines.megaplan._pipeline.registry import get_pipeline
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    ReadRef,
    Stage,
    WriteRef,
)
from arnold.pipeline.step_invocation import StepInvocation
from arnold.pipelines.megaplan._pipeline.validator import (
    Diagnostics,
    MISSING_BINDING_CODE,
    UNKNOWN_ADAPTER_CODE,
    UNSATISFIED_CAPABILITY_CODE,
    ValidationIssue,
    contract_diagnostic_code,
    validate,
)


class _NoopStep:
    name = "noop"
    kind = "produce"
    prompt_key = None
    slot = None

    @property
    def produces(self) -> tuple:
        return ()

    @property
    def consumes(self) -> tuple:
        return ()

    def run(self, ctx):  # pragma: no cover - never called by static check
        raise RuntimeError("static validator must not dispatch")


def _stage(name: str, *edges: Edge) -> Stage:
    return Stage(name=name, step=_NoopStep(), edges=tuple(edges))


def _assert_issue(
    diag: Diagnostics,
    *,
    code: str,
    stage: str,
    detail_items: dict[str, object] | None = None,
    edge_items: dict[str, object] | None = None,
    message_contains: str | None = None,
) -> None:
    matches = [
        issue
        for issue in diag.issues
        if issue.code == code
        and issue.stage == stage
        and (
            detail_items is None
            or all(issue.details.get(key) == value for key, value in detail_items.items())
        )
    ]
    assert matches, diag.issues
    issue = matches[0]
    assert issue.message in diag.defects
    if message_contains is not None:
        assert message_contains in issue.message
    if edge_items is not None:
        assert issue.edge is not None
        for key, value in edge_items.items():
            assert issue.edge.get(key) == value


def test_planning_reports_structured_missing_binding_diagnostics() -> None:
    diag = validate(get_pipeline("planning"))
    assert not diag.ok
    assert [issue.code for issue in diag.issues] == [
        MISSING_BINDING_CODE,
        MISSING_BINDING_CODE,
        MISSING_BINDING_CODE,
    ]
    _assert_issue(
        diag,
        code="dataflow.missing_binding",
        stage="critique",
        detail_items={
            "dependency": "plan_payload",
            "route_hint": "(missing from predecessor 'revise')",
        },
        message_contains="unsatisfied",
    )
    _assert_issue(
        diag,
        code="dataflow.missing_binding",
        stage="critique",
        detail_items={
            "dependency": "revise_payload",
            "route_hint": "(missing from predecessor 'plan')",
        },
        message_contains="unsatisfied",
    )
    _assert_issue(
        diag,
        code="dataflow.missing_binding",
        stage="critique",
        detail_items={
            "dependency": "tiebreaker_payload",
            "route_hint": "(missing from predecessor 'plan')",
        },
        message_contains="unsatisfied",
    )


def test_megaplan_validator_shim_reexports_neutral_diagnostic_types_and_codes() -> None:
    issue = ValidationIssue(code=MISSING_BINDING_CODE, message="x")
    assert issue.code == "dataflow.missing_binding"
    assert contract_diagnostic_code("no_match") == "contract.no_match"


def test_megaplan_validator_shim_distinguishes_contract_mismatches_from_missing_binding() -> None:
    pipeline = Pipeline(
        stages={
            "start": Stage(
                name="start",
                step=_NoopStep(),
                writes=(Port(name="draft", content_type="text/plain"),),
                edges=(
                    Edge(label="to-contract", target="needs-contract"),
                    Edge(label="to-missing", target="needs-missing"),
                ),
            ),
            "needs-contract": Stage(
                name="needs-contract",
                step=_NoopStep(),
                reads=(PortRef(port_name="draft", content_type="text/markdown"),),
                edges=(Edge(label="halt", target="halt"),),
            ),
            "needs-missing": Stage(
                name="needs-missing",
                step=_NoopStep(),
                reads=(ReadRef(name="missing.md"),),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="start",
    )

    diag = validate(pipeline)

    _assert_issue(
        diag,
        code="contract.content_type_mismatch",
        stage="needs-contract",
        detail_items={"dependency": "draft", "error_kind": "content_type_mismatch"},
        message_contains="expects content_type 'text/markdown'",
    )
    _assert_issue(
        diag,
        code=MISSING_BINDING_CODE,
        stage="needs-missing",
        detail_items={
            "dependency": "missing.md",
            "route_hint": "(missing from predecessor 'start')",
        },
        message_contains="dependency 'missing.md' is unsatisfied",
    )


def test_megaplan_validator_shim_preserves_legacy_untyped_passthrough() -> None:
    pipeline = Pipeline(
        stages={
            "start": Stage(
                name="start",
                step=_NoopStep(),
                writes=(WriteRef(name="draft.md"),),
                edges=(Edge(label="next", target="end"),),
            ),
            "end": Stage(
                name="end",
                step=_NoopStep(),
                reads=(ReadRef(name="draft.md"),),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="start",
    )

    diag = validate(pipeline)

    assert diag.ok, diag.issues


def test_megaplan_validator_shim_surfaces_invocation_and_capability_codes() -> None:
    pipeline = Pipeline(
        stages={
            "review": Stage(
                name="review",
                step=_NoopStep(),
                invocation=StepInvocation(kind="custom-collector-v2"),
                required_capabilities=("model:vision",),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="review",
    )

    diag = validate(pipeline)

    _assert_issue(
        diag,
        code=UNKNOWN_ADAPTER_CODE,
        stage="review",
        detail_items={
            "invocation_kind": "custom-collector-v2",
            "registered_kinds": ["model"],
        },
        message_contains="registered adapter",
    )
    _assert_issue(
        diag,
        code=UNSATISFIED_CAPABILITY_CODE,
        stage="review",
        detail_items={
            "required_capabilities": ["model:vision"],
            "unsatisfied_capabilities": ["model:vision"],
        },
        message_contains="required capabilities are not satisfied",
    )


def test_edge_to_nonexistent_stage_is_flagged() -> None:
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="go", target="missing")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    _assert_issue(
        diag,
        code="edge_target_unknown_stage",
        stage="start",
        detail_items={"known_stages": ["start"]},
        edge_items={"label": "go", "target": "missing", "kind": "normal"},
        message_contains="missing",
    )


def test_gate_verdict_with_no_edge_is_flagged() -> None:
    # A gate edge without a recommendation cannot dispatch ⇒ defect.
    pipeline = Pipeline(
        stages={
            "start": _stage(
                "start",
                Edge(label="g", target="halt", kind="gate", recommendation=None),
            ),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    _assert_issue(
        diag,
        code="decision_edge_missing_key",
        stage="start",
        detail_items={"vocabulary": ["escalate", "iterate", "proceed", "tiebreaker"]},
        edge_items={"label": "g", "target": "halt", "kind": "gate"},
        message_contains="no recommendation",
    )


def test_unreachable_stage_is_flagged() -> None:
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="halt", target="halt")),
            "orphan": _stage("orphan", Edge(label="halt", target="halt")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    _assert_issue(
        diag,
        code="stage_unreachable",
        stage="orphan",
        detail_items={"entry": "start"},
        message_contains="unreachable",
    )


def test_halt_label_is_ok_when_target_is_halt() -> None:
    # The conventional terminal label='halt' target='halt' must NOT be flagged.
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="halt", target="halt")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert diag.ok, diag.defects


def test_halt_label_with_non_halt_target_is_flagged() -> None:
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="halt", target="end")),
            "end": _stage("end", Edge(label="halt", target="halt")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    _assert_issue(
        diag,
        code="edge_reserved_halt_label",
        stage="start",
        detail_items={"reserved_label": "halt"},
        edge_items={"label": "halt", "target": "end", "kind": "normal"},
        message_contains="reserved label 'halt'",
    )


def test_diagnostics_ok_property() -> None:
    assert Diagnostics(defects=[]).ok is True
    assert Diagnostics(defects=["x"]).ok is False


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "arnold.pipelines.megaplan", *argv],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_pipelines_check_planning_reports_human_readable_defects() -> None:
    result = _run_cli("pipelines", "check", "planning")
    assert result.returncode == 1
    assert "pipelines check: 'planning' has 3 defect(s):" in result.stderr
    assert "[dataflow.missing_binding]" in result.stderr
    assert "stage 'critique': dependency 'plan_payload' is unsatisfied" in result.stderr


def test_cli_pipelines_check_no_name_exits_zero() -> None:
    result = _run_cli("pipelines", "check")
    assert result.returncode == 0


def test_cli_pipelines_check_judge_manifest_does_not_import_implementation(
    tmp_path,
) -> None:
    user_dir = tmp_path / ".megaplan" / "pipelines"
    user_dir.mkdir(parents=True)
    (user_dir / "exploding_judge.py").write_text(
        "raise RuntimeError('implementation import must not run')\n",
        encoding="utf-8",
    )
    manifest = make_judge_manifest(
        name="exploding-judge",
        implementation="exploding_judge:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "score deterministically"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:deadbeef",
    )
    dump_judge_manifest(manifest, user_dir / "exploding-judge.judge.json")

    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = _run_cli("pipelines", "check", "exploding-judge", env=env)

    assert result.returncode == 0, result.stderr
    assert "exploding-judge" in result.stdout
    assert "implementation import must not run" not in result.stderr


def test_cli_pipelines_check_falls_back_to_pipeline_registry() -> None:
    result = _run_cli("pipelines", "check", "planning")
    assert result.returncode == 1
    assert "tiebreaker_payload" in result.stderr


def test_cli_pipelines_check_distinguishes_contract_mismatch_from_missing_binding(
    monkeypatch,
    capsys,
) -> None:
    from arnold.pipelines.megaplan import cli as cli_mod
    from arnold.pipelines.megaplan._pipeline import registry as registry_mod

    pipeline = Pipeline(
        stages={
            "start": Stage(
                name="start",
                step=_NoopStep(),
                writes=(Port(name="draft", content_type="text/plain"),),
                edges=(
                    Edge(label="to-contract", target="needs-contract"),
                    Edge(label="to-missing", target="needs-missing"),
                ),
            ),
            "needs-contract": Stage(
                name="needs-contract",
                step=_NoopStep(),
                reads=(PortRef(port_name="draft", content_type="text/markdown"),),
                edges=(Edge(label="halt", target="halt"),),
            ),
            "needs-missing": Stage(
                name="needs-missing",
                step=_NoopStep(),
                reads=(ReadRef(name="missing.md"),),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="start",
    )

    monkeypatch.setattr(registry_mod, "scan_python_pipelines", lambda: [])
    monkeypatch.setattr(registry_mod, "get_pipeline", lambda name: pipeline)

    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="check", pipeline_name="typed-diagnostics"),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "pipelines check: 'typed-diagnostics' has 2 defect(s):" in captured.err
    assert "[contract.content_type_mismatch]" in captured.err
    assert "[dataflow.missing_binding]" in captured.err
    assert "typed dependency 'draft' expects content_type 'text/markdown'" in captured.err
    assert "dependency 'missing.md' is unsatisfied" in captured.err


def test_cli_pipelines_check_reports_declaration_drift_with_stable_code(
    monkeypatch,
    capsys,
) -> None:
    from arnold.pipelines.megaplan import cli as cli_mod
    from arnold.pipelines.megaplan._pipeline import registry as registry_mod

    pipeline = Pipeline(
        stages={
            "start": Stage(
                name="start",
                step=_NoopStep(),
                writes=(Port(name="draft", content_type="text/plain"),),
                produces=(Port(name="draft", content_type="text/markdown"),),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="start",
    )

    monkeypatch.setattr(registry_mod, "scan_python_pipelines", lambda: [])
    monkeypatch.setattr(registry_mod, "get_pipeline", lambda name: pipeline)

    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="check", pipeline_name="drifted-authoring"),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "[contract.declaration_drift]" in captured.err
    assert "conflicting explicit and typed produces declarations" in captured.err


def test_cli_pipelines_check_preserves_existing_graph_validation_codes(
    monkeypatch,
    capsys,
) -> None:
    from arnold.pipelines.megaplan import cli as cli_mod
    from arnold.pipelines.megaplan._pipeline import registry as registry_mod

    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="go", target="missing")),
        },
        entry="start",
    )

    monkeypatch.setattr(registry_mod, "scan_python_pipelines", lambda: [])
    monkeypatch.setattr(registry_mod, "get_pipeline", lambda name: pipeline)

    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="check", pipeline_name="broken-graph"),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "[edge_target_unknown_stage]" in captured.err
    assert "edge 'go' targets unknown stage 'missing'" in captured.err


def test_cli_pipelines_check_non_model_invocation_is_authorable_but_fail_closed(
    monkeypatch,
    capsys,
) -> None:
    from arnold.pipelines.megaplan import cli as cli_mod
    from arnold.pipelines.megaplan._pipeline import registry as registry_mod

    run_attempted = False

    class _ExplodingStep:
        name = "exploding"
        kind = "produce"
        prompt_key = None
        slot = None

        @property
        def produces(self) -> tuple:
            return ()

        @property
        def consumes(self) -> tuple:
            return ()

        def run(self, ctx):
            nonlocal run_attempted
            run_attempted = True
            raise AssertionError("pipelines check must not execute authored steps")

    pipeline = Pipeline(
        stages={
            "review": Stage(
                name="review",
                step=_ExplodingStep(),
                invocation=StepInvocation.with_adapter_config(
                    kind="tool",
                    adapter_config={"action": "approve"},
                ),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="review",
    )

    monkeypatch.setattr(registry_mod, "scan_python_pipelines", lambda: [])
    monkeypatch.setattr(registry_mod, "get_pipeline", lambda name: pipeline)

    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="check", pipeline_name="tool-review"),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "[invocation.unknown_adapter]" in captured.err
    assert "invocation kind 'tool' does not resolve to a registered adapter" in captured.err
    assert run_attempted is False


def test_m5_judge_manifest_shape_validates() -> None:
    manifest = make_judge_manifest(
        name="m5-wrapper-eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "return an EvaluandRecord judgment"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:cafebabe",
    )

    diag = validate_judge_manifest(manifest, path="m5-wrapper-eval.judge.json")

    assert diag.ok, diag.defects


def test_cli_pipelines_check_registered_m5_manifest_does_not_import_wrapper(
    monkeypatch,
) -> None:
    from arnold.pipelines.megaplan.cli import _handle_pipelines

    def blocked_import(name, package=None):
        if name == "megaplan._pipeline.eval_judge_wrapper":
            raise AssertionError("pipelines check imported the eval judge wrapper")
        return real_import_module(name, package=package)

    import importlib

    real_import_module = importlib.import_module
    monkeypatch.setattr(importlib, "import_module", blocked_import)

    rc = _handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="check", pipeline_name="m5-wrapper-eval"),
    )

    assert rc == 0
