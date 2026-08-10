"""Native contract tests for the ``writing-panel-strict`` pipeline (restored from archive/m5).

Verifies the native-first package contract, stage topology, and
continue/stop suspension semantics — converted from graph-topology
assertions to native-contract assertions.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipeline import Pipeline
from arnold.pipeline.types import ParallelStage, Stage
from arnold.pipeline.native import NativeProgram
from arnold.pipeline.native import run_native_pipeline
from arnold.runtime.envelope import RuntimeEnvelope


# ── Package metadata / native contract ───────────────────────────────────


def test_writing_panel_strict_package_metadata() -> None:
    import arnold_pipelines.megaplan.pipelines.writing_panel_strict as pkg

    assert pkg.name == "writing-panel-strict"
    assert pkg.driver[0] == "native"
    assert "native" in pkg.supported_modes
    assert pkg.entrypoint == "build_pipeline"
    assert callable(pkg.build_pipeline)
    assert not hasattr(pkg, "_build_graph_pipeline")


def test_writing_panel_strict_build_pipeline_returns_native_backed_shell() -> None:
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "writing-panel-strict"
    assert tuple(pipeline.resource_bundles) == ()


# ── Stage topology (native contract) ─────────────────────────────────────


def test_writing_panel_strict_stage_order() -> None:
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    assert tuple(pipeline.stages.keys()) == (
        "panel_review",
        "synth",
        "revise",
        "human_decide",
    )
    assert pipeline.entry == "panel_review"


def test_writing_panel_strict_panel_review_is_parallel() -> None:
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    panel = pipeline.stages["panel_review"]
    assert isinstance(panel, ParallelStage)
    # Three reviewers: pessimist, optimist, structuralist
    assert len(panel.steps) == 3


def test_writing_panel_strict_human_decide_has_continue_stop_edges() -> None:
    """The human_decide stage routes continue→panel_review, stop/done→halt."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    human = pipeline.stages["human_decide"]
    assert isinstance(human, Stage)
    edge_map = {e.label: e.target for e in human.edges}
    # Must have continue→panel_review loop and stop/done→halt termination.
    assert edge_map["continue"] == "panel_review"
    assert edge_map["stop"] == "halt"
    assert edge_map.get("done") == "halt"


# ── Native program structure (suspension/resume contract) ────────────────


def test_writing_panel_strict_native_program_has_loop_guard() -> None:
    """The native program has a loop_guard for human_decide continue/stop."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    # Must have a loop guard for the human decide gate.
    assert len(native.loop_guards) >= 1
    guard = native.loop_guards[0]
    assert guard.name == "human_decide"


def test_writing_panel_strict_native_decision_vocabulary() -> None:
    """The human_decide guard has continue/stop in its vocabulary."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    # Find the human_decide decision instruction.
    decision_instrs = [i for i in native.instructions if i.op == "decision"]
    assert len(decision_instrs) >= 1
    human_decide = decision_instrs[0]
    assert human_decide.decision_vocabulary == frozenset({"continue", "stop"})
    assert human_decide.branches == {"continue": 4, "stop": 8}


def test_writing_panel_strict_native_program_has_halt() -> None:
    """The native program terminates with a halt instruction."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    halt_instrs = [i for i in native.instructions if i.op == "halt"]
    assert len(halt_instrs) >= 1


# ── Runtime smoke (suspension) ───────────────────────────────────────────


def test_writing_panel_strict_suspends_on_first_pass(tmp_path: Path) -> None:
    """The native pipeline suspends at human_decide on first pass."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    plan_dir = tmp_path / "wp-suspend"
    plan_dir.mkdir(parents=True, exist_ok=True)

    # Seed the draft file that panel_review expects.
    draft_path = plan_dir / "draft.md"
    draft_path.write_text("# Test Draft\n\nA prose sample.\n")

    result = run_native_pipeline(
        pipeline.native_program,
        artifact_root=str(plan_dir),
        initial_state={"_pipeline_name": "writing-panel-strict", "draft_path": str(draft_path)},
    )

    # The pipeline should suspend (not complete).
    assert result.suspended is True
    # The pipeline has progressed through panel_review, synth, revise to human_decide.
    assert any("panel_review" in s for s in result.stages)
    assert any("synth" in s for s in result.stages)
    assert any("revise" in s for s in result.stages)


def test_writing_panel_strict_resumes_on_continue(tmp_path: Path) -> None:
    """Resuming with 'continue' re-enters the panel_review loop and suspends again."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    plan_dir = tmp_path / "wp-continue"
    plan_dir.mkdir(parents=True, exist_ok=True)

    draft_path = plan_dir / "draft.md"
    draft_path.write_text("# Test Draft\n\nA prose sample.\n")

    # First pass: should suspend.
    result1 = run_native_pipeline(
        pipeline.native_program,
        artifact_root=str(plan_dir),
        initial_state={"_pipeline_name": "writing-panel-strict", "draft_path": str(draft_path)},
    )
    assert result1.suspended is True
    assert any("panel_review" in s for s in result1.stages)

    # Resume with "continue".
    result2 = run_native_pipeline(
        pipeline.native_program,
        artifact_root=str(plan_dir),
        initial_state=result1.state,
        resume=True,
        human_input="continue",
    )
    # Should suspend again at human_decide after another loop iteration.
    assert result2.suspended is True
    assert any("panel_review" in s for s in result2.stages)


def test_writing_panel_strict_stops_on_stop(tmp_path: Path) -> None:
    """Resuming with 'stop' reaches the halt terminator."""
    from arnold_pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline

    pipeline = build_pipeline()
    plan_dir = tmp_path / "wp-stop"
    plan_dir.mkdir(parents=True, exist_ok=True)

    draft_path = plan_dir / "draft.md"
    draft_path.write_text("# Test Draft\n\nA prose sample.\n")

    # First pass: should suspend.
    result1 = run_native_pipeline(
        pipeline.native_program,
        artifact_root=str(plan_dir),
        initial_state={"_pipeline_name": "writing-panel-strict", "draft_path": str(draft_path)},
    )
    assert result1.suspended is True

    # Resume with "stop".
    result2 = run_native_pipeline(
        pipeline.native_program,
        artifact_root=str(plan_dir),
        initial_state=result1.state,
        resume=True,
        human_input="stop",
    )
    # Should complete without suspension.
    assert result2.suspended is False
