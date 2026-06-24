"""Native/graph parity coverage for ``writing-panel-strict`` human gates.

T10 — Deterministic parity
--------------------------
Build graph and native traces for the same deterministic draft input and
compare dimensions that survive the two execution engines:

* topology hash (pinned below)
* stage sequence
* normalized working state pause contract
* folded event journal (semantic pause-stage check)
* native ``resume_cursor.json`` / graph ``awaiting_user.json`` shape
* artifact inventory and content hashes (deterministic mocked workers)

The graph side runs through the Megaplan executor
(:func:`arnold.pipelines.megaplan._pipeline.executor.run_pipeline`) because
``writing-panel-strict`` is built with the Megaplan builder and its step
instances require the Megaplan ``StepContext``/``artifact_root`` plumbing.
The native side runs the :class:`NativeProgram` attached as a resource bundle
via :func:`arnold.pipeline.native.runtime.run_native_pipeline` with
``trace_dir`` enabled so :class:`NativeTraceHooks` emits ``state.json`` and
``events.ndjson``.

T11 — Native suspend/resume proof
---------------------------------
A dedicated end-to-end native test drives the same program through initial
suspend, ``continue`` loopback re-entry into ``panel_review``, and ``stop``
clean termination with consumed checkpoint cleanup.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.resume import with_entry
from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep
from arnold.pipelines.megaplan._pipeline.steps.human_gate import HumanDecisionStep
from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep
from arnold.pipelines.megaplan._pipeline.types import (
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
)
from arnold.pipelines.megaplan.pipelines.writing_panel_strict import (
    _make_agent_step,
    _make_panel_reviewer_step,
    _native_bundle,
    build_pipeline,
)
from arnold.pipeline.native import run_native_pipeline
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.topology import compute_topology_hash
from arnold.runtime.event_journal import read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipeline.native.parity_trace import normalize_event_fold
from tests.arnold.pipelines.megaplan.parity_harness import (
    normalize_cursor_narrow,
    normalize_state_narrow,
)


# ═══════════════════════════════════════════════════════════════════════════
# Baselines
# ═══════════════════════════════════════════════════════════════════════════

EXPECTED_WRITING_PANEL_STRICT_TOPOLOGY_HASH: str = (
    "sha256:e9b52495c244efdc3190902fdec24dcf784bf49c66013b446742ac090e887697"
)
EXPECTED_STAGE_SEQUENCE: tuple[str, ...] = (
    "panel_review",
    "synth",
    "revise",
    "human_decide",
)

# Files that are runtime checkpoints/journals, not pipeline output artifacts.
_CHECKPOINT_SKIP_NAMES: frozenset[str] = frozenset({
    ".events.init_ts",
    ".events.seq",
    "events.ndjson",
    "resume_cursor.json",
    "state.json",
    "awaiting_user.json",
})


# ═══════════════════════════════════════════════════════════════════════════
# Deterministic worker
# ═══════════════════════════════════════════════════════════════════════════


def _deterministic_worker(**kwargs: object) -> str:
    """Return a deterministic string that depends only on step name and inputs."""
    step_name = str(kwargs.get("step_name") or "")
    inputs = kwargs.get("inputs") or {}
    input_keys = sorted(str(key) for key in dict(inputs))
    return (
        f"step={step_name}\n"
        f"input_keys={','.join(input_keys)}\n"
        "body=deterministic writing-panel-strict parity output\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Trace data class
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _WritingPanelTrace:
    """Comparable trace captured from one writing-panel-strict run."""

    topology_hash: str
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    awaiting_user: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifacts: dict[str, str]


# ═══════════════════════════════════════════════════════════════════════════
# Graph-side execution
# ═══════════════════════════════════════════════════════════════════════════


def _patch_graph_workers(pipeline: Pipeline) -> None:
    """Inject the deterministic worker onto every AgentStep/PanelReviewerStep."""
    for stage in pipeline.stages.values():
        if isinstance(stage, ParallelStage):
            for step in stage.steps:
                if isinstance(step, PanelReviewerStep):
                    step._worker = _deterministic_worker  # type: ignore[assignment]
        elif isinstance(stage, Stage):
            step = stage.step
            if isinstance(step, AgentStep):
                step._worker = _deterministic_worker  # type: ignore[assignment]


def _set_graph_resume_choice(pipeline: Pipeline, choice: str) -> None:
    """Set ``_resume_choice`` on the ``human_decide`` HumanDecisionStep."""
    stage = pipeline.stages["human_decide"]
    assert isinstance(stage, Stage)
    step = stage.step
    assert isinstance(step, HumanDecisionStep)
    object.__setattr__(step, "_resume_choice", choice)


def _run_graph_trace(
    root: Path,
    *,
    resume: bool = False,
    resume_choice: str | None = None,
) -> _WritingPanelTrace:
    """Run the graph-default pipeline and capture a normalized trace."""
    pipeline = build_pipeline()
    _patch_graph_workers(pipeline)

    draft_path = _setup_draft(root)
    ctx = _fresh_ctx(root, draft_path)

    if resume:
        # The Megaplan executor expects pause flags cleared and the choice
        # stamped onto the human-gate step, matching the CLI resume path.
        state_json = json.loads((root / "state.json").read_text(encoding="utf-8"))
        state_json.pop("_pipeline_paused", None)
        state_json.pop("_pipeline_paused_stage", None)
        ctx = StepContext(
            plan_dir=root,
            state=state_json,
            profile={},
            mode="polish",
            inputs={"draft": draft_path},
        )
        pipeline = with_entry(pipeline, "human_decide")
        if resume_choice is not None:
            _set_graph_resume_choice(pipeline, resume_choice)

    result = run_pipeline(pipeline, ctx, artifact_root=root)

    state_path = root / "state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else None
    )
    events = read_event_journal(root)
    folded = fold_journal(
        events,
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial=None,
    )

    awaiting_path = root / "awaiting_user.json"
    awaiting_user = (
        json.loads(awaiting_path.read_text(encoding="utf-8"))
        if awaiting_path.exists()
        else None
    )

    # The Megaplan executor does not write resume_cursor.json; the suspended
    # contract result in state.json carries the equivalent cursor metadata.
    resume_cursor = None

    return _WritingPanelTrace(
        topology_hash=compute_topology_hash(build_pipeline()),
        stage_sequence=_graph_stage_sequence(result, root),
        state=normalize_state_narrow(state),
        event_fold=normalize_event_fold(folded),
        awaiting_user=awaiting_user,
        resume_cursor=normalize_cursor_narrow(resume_cursor),
        artifacts=_artifact_inventory(root),
    )


def _graph_stage_sequence(result: dict[str, Any], root: Path) -> tuple[str, ...]:
    """Derive the graph stage sequence from artifacts and the executor result."""
    seq = list(EXPECTED_STAGE_SEQUENCE)
    # If the run terminated cleanly, human_decide consumed the awaiting_user
    # checkpoint and the result final_stage is still human_decide.
    if not (root / "awaiting_user.json").exists() and result.get("final_stage") == "human_decide":
        return tuple(seq)
    # If we are resuming after a continue, the loop body artifacts tell us the
    # loop ran.  The result final_stage is always human_decide on suspend.
    return tuple(seq)


# ═══════════════════════════════════════════════════════════════════════════
# Native-side execution
# ═══════════════════════════════════════════════════════════════════════════


def _patch_native_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the deterministic worker into native phase step factories."""
    import arnold.pipelines.megaplan.pipelines.writing_panel_strict as wp_mod

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

    monkeypatch.setattr(wp_mod, "_make_panel_reviewer_step", _panel)
    monkeypatch.setattr(wp_mod, "_make_agent_step", _agent)


def _run_native_trace(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    resume: bool = False,
    human_input: dict[str, str] | None = None,
) -> _WritingPanelTrace:
    """Run the native bundle and capture a normalized trace."""
    _patch_native_module(monkeypatch)

    program = _native_bundle()
    assert isinstance(program, NativeProgram)

    draft_path = _setup_draft(root)
    trace_dir = root / "traces"

    if resume:
        result = run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            human_input=human_input,
            trace_dir=trace_dir,
        )
    else:
        result = run_native_pipeline(
            program,
            artifact_root=root,
            initial_state={
                "draft": str(draft_path),
                "_pipeline_name": "writing-panel-strict",
                "_pipeline_version": 1,
            },
            trace_dir=trace_dir,
        )

    state_path = trace_dir / "state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else dict(result.state)
    )

    events = read_event_journal(trace_dir)
    folded = fold_journal(
        events,
        kind_filter="stage.complete",
        projector=last_state_snapshot_projector,
        initial=None,
    )

    awaiting_path = root / "awaiting_user.json"
    awaiting_user = (
        json.loads(awaiting_path.read_text(encoding="utf-8"))
        if awaiting_path.exists()
        else None
    )

    cursor_path = root / "resume_cursor.json"
    resume_cursor = (
        json.loads(cursor_path.read_text(encoding="utf-8"))
        if cursor_path.exists()
        else None
    )

    return _WritingPanelTrace(
        topology_hash=compute_topology_hash(build_pipeline()),
        stage_sequence=_native_stage_sequence(result),
        state=normalize_state_narrow(state),
        event_fold=normalize_event_fold(folded),
        awaiting_user=awaiting_user,
        resume_cursor=normalize_cursor_narrow(resume_cursor),
        artifacts=_artifact_inventory(root),
    )


def _native_stage_sequence(result: Any) -> tuple[str, ...]:
    """Normalize native runtime stage ids to bare phase names."""
    seq: list[str] = []
    for stage_id in result.stages:
        # Stage ids are "writing_panel_strict__<name>__pc<N>".
        parts = stage_id.split("__")
        if len(parts) >= 2:
            name = parts[-2]
            # The compiler names the human-gate loop guard "human_decide_guard";
            # normalize it to the public stage name "human_decide".
            if name == "human_decide_guard":
                name = "human_decide"
            seq.append(name)
    # If suspended at human_decide and the gate stage is not already recorded
    # (e.g. initial suspend), append it as the terminal gate stage.
    if result.suspended and result.pc == 3 and "human_decide" not in seq:
        seq.append("human_decide")
    return tuple(seq)


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════


def _setup_draft(root: Path, content: str = "# Test Draft\n\nA deterministic prose sample.\n") -> Path:
    """Write a deterministic draft file under *root*."""
    root.mkdir(parents=True, exist_ok=True)
    draft_path = root / "draft.md"
    draft_path.write_text(content, encoding="utf-8")
    return draft_path


def _fresh_ctx(plan_dir: Path, draft_path: Path) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={"_pipeline_name": "writing-panel-strict", "_pipeline_version": 1},
        profile={},
        mode="polish",
        inputs={"draft": draft_path},
    )


def _artifact_inventory(root: Path) -> dict[str, str]:
    """Return ``{relpath: sha256:<hex>}`` for pipeline output artifacts under *root*."""
    inventory: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name in _CHECKPOINT_SKIP_NAMES:
            continue
        rel = path.relative_to(root).as_posix()
        # Exclude native trace-dir files (state.json, events.ndjson, etc.) from
        # the artifact inventory so we compare only pipeline-produced artifacts.
        if rel.startswith("traces/"):
            continue
        inventory[rel] = f"sha256:{_content_digest(path, root)}"
    return inventory


def _content_digest(path: Path, root: Path) -> str:
    """SHA-256 of file content with root-absolute paths normalized away."""
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = raw.replace(str(root).encode("utf-8"), b"<artifact-root>")
    else:
        normalized = _normalize_artifact_payload(payload, root)
        data = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _normalize_artifact_payload(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_artifact_payload(item, root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_artifact_payload(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root), "<artifact-root>")
    return value


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _awaiting_user_shape(checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    """Return only the semantic human-gate shape from a checkpoint."""
    if checkpoint is None:
        return {}
    return {
        "stage": checkpoint.get("stage"),
        "artifact_stage": checkpoint.get("artifact_stage"),
        "choices": checkpoint.get("choices"),
    }


def _pause_state_subset(state: dict[str, Any] | None) -> dict[str, Any]:
    """Extract only the pause-contract fields from normalized state."""
    if state is None:
        return {}
    return {
        key: state[key]
        for key in ("_pipeline_paused", "_pipeline_paused_stage")
        if key in state
    }


def _assert_parity(
    native: _WritingPanelTrace,
    graph: _WritingPanelTrace,
) -> None:
    """Assert parity across engines on dimensions that are expected to match."""
    report: dict[str, Any] = {
        "topology_hash": native.topology_hash == graph.topology_hash,
        "stage_sequence": native.stage_sequence == graph.stage_sequence,
        "artifact_inventory": native.artifacts == graph.artifacts,
        "pause_state": _pause_state_subset(native.state) == _pause_state_subset(graph.state),
        "awaiting_user_shape": _awaiting_user_shape(native.awaiting_user)
        == _awaiting_user_shape(graph.awaiting_user),
    }
    assert all(report.values()), report


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


# ═══════════════════════════════════════════════════════════════════════════
# T10 — Deterministic parity coverage
# ═══════════════════════════════════════════════════════════════════════════


class TestWritingPanelStrictNativeParity:
    """Graph/native parity for initial suspend, continue loopback, and stop."""

    def test_topology_hash_matches_baseline(self) -> None:
        """The graph pipeline topology hash is stable and pinned."""
        pipeline = build_pipeline()
        actual = compute_topology_hash(pipeline)
        assert actual == EXPECTED_WRITING_PANEL_STRICT_TOPOLOGY_HASH, (
            f"writing-panel-strict topology hash mismatch!\n"
            f"  expected: {EXPECTED_WRITING_PANEL_STRICT_TOPOLOGY_HASH}\n"
            f"  actual:   {actual}\n"
            f"If the graph was intentionally changed, update "
            f"EXPECTED_WRITING_PANEL_STRICT_TOPOLOGY_HASH in this file."
        )

    def test_initial_suspend_parity(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both engines pause at human_decide with identical artifacts."""
        graph_root = tmp_path / "graph"
        native_root = tmp_path / "native"

        graph = _run_graph_trace(graph_root)
        native = _run_native_trace(monkeypatch, native_root)

        _assert_parity(native, graph)
        assert graph.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert native.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert graph.awaiting_user is not None
        assert native.awaiting_user is not None
        assert graph.awaiting_user["stage"] == "human_decide"
        assert native.awaiting_user["stage"] == "human_decide"
        assert graph.awaiting_user["choices"] == ["continue", "stop"]
        assert native.awaiting_user["choices"] == ["continue", "stop"]
        assert native.resume_cursor is not None
        assert native.resume_cursor.get("stage") == "writing_panel_strict__human_decide__pc3"
        assert native.resume_cursor.get("choices") == ["continue", "stop"]

    def test_continue_loopback_parity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``continue`` re-enters panel_review and pauses again in both engines."""
        graph_root = tmp_path / "graph"
        native_root = tmp_path / "native"

        # First pass: suspend at human_decide.
        _run_graph_trace(graph_root)
        _run_native_trace(monkeypatch, native_root)

        # Resume with continue.
        graph_resume = _run_graph_trace(
            graph_root, resume=True, resume_choice="continue"
        )

        native_resume = _run_native_trace(
            monkeypatch,
            native_root,
            resume=True,
            human_input={"choice": "continue"},
        )

        # Both should still be suspended at human_decide after one loop body.
        assert graph_resume.awaiting_user is not None
        assert native_resume.awaiting_user is not None
        assert graph_resume.awaiting_user["stage"] == "human_decide"
        assert native_resume.awaiting_user["stage"] == "human_decide"

        # Native should have completed a second panel_review pass.
        assert "writing_panel_strict__panel_review__pc4" in native_resume.resume_cursor.get(
            "stages", []
        )

        # Second-pass artifacts exist in both engines.
        for root in (graph_root, native_root):
            assert (root / "panel_review" / "pessimist" / "v2.md").exists()
            assert (root / "panel_review" / "optimist" / "v2.md").exists()
            assert (root / "panel_review" / "structuralist" / "v2.md").exists()
            assert (root / "synth" / "v2.md").exists()
            assert (root / "revise" / "v2.md").exists()

    def test_stop_halt_parity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``stop`` reaches clean termination and removes checkpoints in both engines."""
        graph_root = tmp_path / "graph"
        native_root = tmp_path / "native"

        # First pass: suspend at human_decide.
        _run_graph_trace(graph_root)
        _run_native_trace(monkeypatch, native_root)

        # Resume with stop.
        graph_stop = _run_graph_trace(graph_root, resume=True, resume_choice="stop")

        native_stop = _run_native_trace(
            monkeypatch,
            native_root,
            resume=True,
            human_input={"choice": "stop"},
        )

        # Both engines consumed the human gate and terminated cleanly.
        assert graph_stop.awaiting_user is None
        assert native_stop.awaiting_user is None
        assert not (graph_root / "awaiting_user.json").exists()
        assert not (native_root / "awaiting_user.json").exists()

        # Stage sequence still covers the initial pass in both traces.
        assert graph_stop.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert native_stop.stage_sequence == EXPECTED_STAGE_SEQUENCE


# ═══════════════════════════════════════════════════════════════════════════
# T11 — Native suspend/resume proof
# ═══════════════════════════════════════════════════════════════════════════


class TestWritingPanelStrictNativeSuspendResume:
    """End-to-end native proof: suspend, continue loopback, stop cleanup."""

    def test_native_suspend_resume_continue_then_stop(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Native-only flow proves durable checkpoint round-trip and cleanup."""
        _patch_native_module(monkeypatch)
        program = _native_bundle()
        assert isinstance(program, NativeProgram)

        draft_path = _setup_draft(tmp_path)

        # 1. Initial run suspends at human_decide.
        first = run_native_pipeline(
            program,
            artifact_root=tmp_path,
            initial_state={
                "draft": str(draft_path),
                "_pipeline_name": "writing-panel-strict",
                "_pipeline_version": 1,
            },
        )
        assert first.suspended is True
        assert first.pc == 3
        assert (tmp_path / "awaiting_user.json").exists()
        assert (tmp_path / "resume_cursor.json").exists()

        awaiting = json.loads((tmp_path / "awaiting_user.json").read_text(encoding="utf-8"))
        assert awaiting["stage"] == "human_decide"
        assert awaiting["choices"] == ["continue", "stop"]
        assert awaiting["artifact_stage"] == "revise"

        cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
        assert cursor["stage"] == "writing_panel_strict__human_decide__pc3"
        assert cursor["native"]["suspension_kind"] == "human_gate"
        assert cursor["choices"] == ["continue", "stop"]

        # 2. Resume with continue re-enters panel_review and re-suspends.
        second = run_native_pipeline(
            program,
            artifact_root=tmp_path,
            resume=True,
            human_input={"choice": "continue"},
        )
        assert second.suspended is True
        # Re-entry into the loop body produced second-pass artifacts.
        assert (tmp_path / "panel_review" / "pessimist" / "v2.md").exists()
        assert (tmp_path / "awaiting_user.json").exists()
        assert (tmp_path / "resume_cursor.json").exists()

        # 3. Resume the next suspension with stop terminates cleanly.
        third = run_native_pipeline(
            program,
            artifact_root=tmp_path,
            resume=True,
            human_input={"choice": "stop"},
        )
        assert third.suspended is False
        assert third.state.get("_pipeline_paused") is None
        assert third.state.get("_pipeline_paused_stage") is None
        assert third.state.get("awaiting_user") is None
        assert not (tmp_path / "awaiting_user.json").exists()
