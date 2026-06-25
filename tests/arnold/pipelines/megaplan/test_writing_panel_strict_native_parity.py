"""Native coverage for ``writing-panel-strict`` suspend/resume behavior."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from arnold.pipeline import Pipeline
from arnold.pipeline.native import NativeProgram, run_native_pipeline
from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep
from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep
from arnold.runtime.event_journal import read_event_journal
from arnold.runtime.wal_fold import fold_journal

from arnold.pipelines.megaplan.pipelines.writing_panel_strict import build_pipeline
from arnold.pipelines.megaplan.pipelines.writing_panel_strict.steps import (
    _make_agent_step,
    _make_panel_reviewer_step,
)


_CHECKPOINT_SKIP_NAMES: frozenset[str] = frozenset({
    ".events.init_ts",
    ".events.seq",
    "awaiting_user.json",
    "events.ndjson",
    "resume_cursor.json",
    "state.json",
})


def _deterministic_worker(**kwargs: object) -> str:
    step_name = str(kwargs.get("step_name") or "")
    inputs = kwargs.get("inputs") or {}
    input_keys = sorted(str(key) for key in dict(inputs))
    return (
        f"step={step_name}\n"
        f"input_keys={','.join(input_keys)}\n"
        "body=deterministic writing-panel-strict native output\n"
    )


def _patch_native_module(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_mod = importlib.import_module(
        "arnold.pipelines.megaplan.pipelines.writing_panel_strict.pipeline"
    )

    def _panel(reviewer_id: str, prompt_ref: str) -> PanelReviewerStep:
        step = _make_panel_reviewer_step(reviewer_id, prompt_ref)
        step._worker = _deterministic_worker  # type: ignore[assignment]
        return step

    def _agent(
        stage_name: str,
        prompt_ref: str,
        inputs: tuple[str, ...],
        panel_reviewer_order: dict[str, tuple[str, ...]],
    ) -> AgentStep:
        step = _make_agent_step(stage_name, prompt_ref, inputs, panel_reviewer_order)
        step._worker = _deterministic_worker  # type: ignore[assignment]
        return step

    monkeypatch.setattr(pipeline_mod, "_make_panel_reviewer_step", _panel)
    monkeypatch.setattr(pipeline_mod, "_make_agent_step", _agent)


def _setup_draft(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    draft_path = root / "draft.md"
    draft_path.write_text("# Test Draft\n\nA deterministic prose sample.\n", encoding="utf-8")
    return draft_path


def _program() -> NativeProgram:
    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    return pipeline.native_program


def _run_native(
    root: Path,
    *,
    resume: bool = False,
    human_input: dict[str, str] | None = None,
) -> Any:
    program = _program()
    if resume:
        return run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            human_input=human_input,
            trace_dir=root / "traces",
        )
    draft_path = _setup_draft(root)
    return run_native_pipeline(
        program,
        artifact_root=root,
        initial_state={
            "draft": str(draft_path),
            "_pipeline_name": "writing-panel-strict",
            "_pipeline_version": 1,
        },
        trace_dir=root / "traces",
    )


def _artifact_inventory(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if path.name in _CHECKPOINT_SKIP_NAMES or rel.startswith("traces/"):
            continue
        payload = path.read_bytes().replace(str(root).encode("utf-8"), b"<artifact-root>")
        inventory[rel] = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return inventory


def _public_names(module: ModuleType) -> set[str]:
    exported = set(getattr(module, "__all__", ()))
    discovered = {name for name in vars(module) if not name.startswith("_")}
    return exported | discovered


def _append_event_phase(acc: list[str], ev: dict[str, Any]) -> list[str]:
    phase = ev.get("phase")
    return [*acc, str(phase)] if phase else acc


def test_public_surface_is_native_split_and_mirrored() -> None:
    public_mod = importlib.import_module(
        "arnold.pipelines.megaplan.pipelines.writing_panel_strict"
    )
    pipeline_mod = importlib.import_module(
        "arnold.pipelines.megaplan.pipelines.writing_panel_strict.pipeline"
    )
    mirror_mod = importlib.import_module(
        "arnold_pipelines.megaplan.pipelines.writing_panel_strict.pipeline"
    )

    assert public_mod.build_pipeline is pipeline_mod.build_pipeline
    assert mirror_mod.build_pipeline is pipeline_mod.build_pipeline
    assert public_mod.driver[0] == "native"
    assert "native" in public_mod.supported_modes

    public = _public_names(public_mod)
    assert not {
        name
        for name in public
        if name.startswith("build_") and ("graph" in name or "legacy" in name)
    }


def test_build_pipeline_attaches_direct_native_program() -> None:
    pipeline = build_pipeline()

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "writing-panel-strict"
    assert pipeline.resource_bundles == ()
    assert tuple(pipeline.stages) == (
        "panel_review",
        "synth",
        "revise",
        "human_decide",
    )


def test_native_suspend_persists_state_cursor_events_and_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_native_module(monkeypatch)

    result = _run_native(tmp_path)

    assert result.suspended is True
    assert result.pc == 3
    assert (tmp_path / "awaiting_user.json").exists()
    assert (tmp_path / "resume_cursor.json").exists()

    awaiting = json.loads((tmp_path / "awaiting_user.json").read_text(encoding="utf-8"))
    assert awaiting["stage"] == "human_decide"
    assert awaiting["artifact_stage"] == "revise"
    assert awaiting["choices"] == ["continue", "stop"]

    cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
    assert cursor["stage"] == "writing_panel_strict__human_decide__pc3"
    assert cursor["native"]["suspension_kind"] == "human_gate"
    assert cursor["choices"] == ["continue", "stop"]

    artifacts = _artifact_inventory(tmp_path)
    assert "panel_review/pessimist/v1.md" in artifacts
    assert "panel_review/optimist/v1.md" in artifacts
    assert "panel_review/structuralist/v1.md" in artifacts
    assert "synth/v1.md" in artifacts
    assert "revise/v1.md" in artifacts

    events = read_event_journal(tmp_path / "traces")
    folded = fold_journal(
        events,
        kind_filter="stage.complete",
        projector=_append_event_phase,
        initial=[],
    )
    assert events
    assert folded == ["panel_review", "synth", "revise"]


def test_native_continue_reenters_loop_and_refreshes_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_native_module(monkeypatch)

    _run_native(tmp_path)
    result = _run_native(
        tmp_path,
        resume=True,
        human_input={"choice": "continue"},
    )

    assert result.suspended is True
    assert (tmp_path / "awaiting_user.json").exists()
    assert (tmp_path / "resume_cursor.json").exists()
    assert (tmp_path / "panel_review" / "pessimist" / "v2.md").exists()
    assert (tmp_path / "panel_review" / "optimist" / "v2.md").exists()
    assert (tmp_path / "panel_review" / "structuralist" / "v2.md").exists()
    assert (tmp_path / "synth" / "v2.md").exists()
    assert (tmp_path / "revise" / "v2.md").exists()

    cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
    assert cursor["stage"] == "writing_panel_strict__human_decide__pc3"
    assert "writing_panel_strict__panel_review__pc4" in cursor.get("stages", [])


def test_native_stop_terminates_and_cleans_human_gate_checkpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_native_module(monkeypatch)

    _run_native(tmp_path)
    result = _run_native(
        tmp_path,
        resume=True,
        human_input={"choice": "stop"},
    )

    assert result.suspended is False
    assert result.state.get("_pipeline_paused") is None
    assert result.state.get("_pipeline_paused_stage") is None
    assert result.state.get("awaiting_user") is None
    assert not (tmp_path / "awaiting_user.json").exists()
    assert not (tmp_path / "resume_cursor.json").exists()
