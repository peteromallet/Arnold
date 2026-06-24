from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

from arnold.pipeline.executor import run_pipeline, run_pipeline_resume
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.topology import compute_topology_hash
from arnold.pipelines.megaplan._pipeline.adapter import to_canonical_pipeline
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE
from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep
from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep
from arnold.pipelines.megaplan._pipeline.types import (
    ParallelStage,
    Pipeline,
    Stage,
    StepContext as MegaplanStepContext,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipeline.native.parity_trace import normalize_event_fold
from tests.arnold.pipelines.megaplan.parity_harness import (
    normalize_cursor_narrow,
    normalize_state_narrow,
)
from tests.arnold.pipelines.megaplan.test_graph_baseline import (
    EXPECTED_EPIC_BLITZ_STAGE_ORDER,
    EXPECTED_EPIC_BLITZ_TOPOLOGY_HASH,
)


_EPIC_MODULE = "arnold.pipelines.megaplan.pipelines.epic_blitz"
_HIGH_REVIEWERS = (
    "existing_system_reuse",
    "conceptual_fit",
    "missing_abstraction",
    "epic_decomposition",
    "strategic_risk",
)
_MID_REVIEWERS = (
    "codebase_convention_fit",
    "data_artifact_model",
    "orchestration_semantics",
    "agent_model_assignment",
    "blast_radius",
)
_LOW_REVIEWERS = (
    "implementation_feasibility",
    "testability",
    "edge_cases",
    "cli_ux_details",
    "migration_backcompat",
)
_EXPECTED_ARTIFACTS = tuple(
    sorted(
        (
            "draft.md",
            "high_revise/v1.md",
            "mid_revise/v1.md",
            "readiness/v1.md",
            "state.json",
            *(f"high_panel/{reviewer}/v1.md" for reviewer in _HIGH_REVIEWERS),
            *(f"mid_panel/{reviewer}/v1.md" for reviewer in _MID_REVIEWERS),
            *(f"low_panel/{reviewer}/v1.md" for reviewer in _LOW_REVIEWERS),
        )
    )
)
_ARTIFACT_SKIP_NAMES = frozenset({
    ".events.init_ts",
    ".events.seq",
    "events.ndjson",
    "resume_cursor.json",
})


@dataclass(frozen=True)
class _EpicBlitzTrace:
    topology_hash: str
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifacts: dict[str, str]


class _TraceHooks(NullExecutorHooks):
    def __init__(self, root: Path, *, suspend_before: str | None = None) -> None:
        super().__init__()
        self.stage_sequence: list[str] = []
        self.final_state: dict[str, Any] | None = None
        self.resume_cursor: dict[str, Any] | None = None
        self._root = root
        self._journal = NdjsonEventJournal(root)
        self._suspend_before = suspend_before
        self._suspended = False

    def on_step_start(self, stage: Any, ctx: Any) -> MegaplanStepContext:
        del stage
        return _to_megaplan_context(ctx)

    def should_halt_loop(
        self,
        stage: Any,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        del state, iteration
        if (
            self._suspend_before is not None
            and not self._suspended
            and stage.name == self._suspend_before
        ):
            self._suspended = True
            self.resume_cursor = {"stage": stage.name, "input": None}
            _write_json(self._root / "resume_cursor.json", self.resume_cursor)
            return True, f"suspend_before_{stage.name}"
        return False, None

    def on_stage_complete(
        self,
        stage: Any,
        ctx: Any,
        result: Any,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, owned_keys
        json_state = _jsonable(state) if isinstance(state, dict) else {}
        assert isinstance(json_state, dict)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)
        self._journal.emit(
            "state_written",
            payload={"stage": stage.name, "state": json_state},
            phase=stage.name,
        )

        skipped_by_pre_stage_suspend = (
            self._suspended
            and self._suspend_before == stage.name
            and not getattr(result, "outputs", {})
        )
        if not skipped_by_pre_stage_suspend:
            self.stage_sequence.append(stage.name)


def _load_epic_module() -> Any:
    return importlib.import_module(_EPIC_MODULE)


def _build_legacy_pipeline() -> Pipeline:
    return _load_epic_module()._build_legacy_graph_pipeline()


def _build_native_projected_pipeline() -> Pipeline:
    return _load_epic_module().build_pipeline()


def _run_trace(
    pipeline_factory: Callable[[], Pipeline],
    root: Path,
    *,
    suspend_before: str | None = None,
    resume: bool = False,
) -> _EpicBlitzTrace:
    pipeline = pipeline_factory()
    _patch_workers(pipeline, _deterministic_worker())
    _setup_draft(root)

    canonical = to_canonical_pipeline(pipeline)
    hooks = _TraceHooks(root, suspend_before=suspend_before)
    envelope = RuntimeEnvelope(
        plugin_id="epic_blitz_parity",
        run_id=root.name,
        artifact_root=str(root),
    )

    if resume:
        run_pipeline_resume(canonical, {}, envelope, hooks=hooks)
    else:
        run_pipeline(canonical, {"draft": root / "draft.md"}, envelope, hooks=hooks)

    cursor_path = root / "resume_cursor.json"
    cursor = (
        json.loads(cursor_path.read_text(encoding="utf-8"))
        if cursor_path.exists()
        else None
    )
    events = read_event_journal(root)
    folded = fold_journal(
        events,
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial=None,
    )
    return _EpicBlitzTrace(
        topology_hash=compute_topology_hash(pipeline),
        stage_sequence=tuple(hooks.stage_sequence),
        state=normalize_state_narrow(hooks.final_state),
        event_fold=normalize_event_fold(folded),
        resume_cursor=normalize_cursor_narrow(cursor),
        artifacts=_artifact_inventory(root),
    )


def _patch_workers(pipeline: Pipeline, worker: Callable[..., str]) -> None:
    for stage in pipeline.stages.values():
        if isinstance(stage, ParallelStage):
            for step in stage.steps:
                if isinstance(step, PanelReviewerStep):
                    step._worker = worker
        elif isinstance(stage, Stage):
            step = stage.step
            if isinstance(step, AgentStep):
                step._worker = worker


def _deterministic_worker() -> Callable[..., str]:
    def worker(**kwargs: object) -> str:
        step_name = str(kwargs.get("step_name") or "")
        inputs = kwargs.get("inputs") or {}
        input_keys = sorted(str(key) for key in dict(inputs))
        return (
            f"step={step_name}\n"
            f"input_keys={','.join(input_keys)}\n"
            "body=deterministic epic-blitz parity output\n"
        )

    return worker


def _setup_draft(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "draft.md").write_text(
        "# Epic Draft\n\nA deterministic epic-blitz parity draft.\n",
        encoding="utf-8",
    )


def _to_megaplan_context(ctx: Any) -> MegaplanStepContext:
    if isinstance(ctx, MegaplanStepContext):
        return ctx
    root = Path(getattr(ctx, "artifact_root", None) or getattr(ctx, "plan_dir", "."))
    raw_state = getattr(ctx, "state", {}) or {}
    raw_inputs = getattr(ctx, "inputs", {}) or {}
    return MegaplanStepContext(
        plan_dir=root,
        state=dict(raw_state) if isinstance(raw_state, dict) else raw_state,
        profile={},
        mode=str(getattr(ctx, "mode", "code") or "code"),
        inputs={
            str(key): Path(value) if isinstance(value, str) else value
            for key, value in dict(raw_inputs).items()
        },
        envelope=EMPTY_ENVELOPE,
    )


def _assert_parity(native: _EpicBlitzTrace, graph: _EpicBlitzTrace) -> None:
    report = {
        "topology_hash": native.topology_hash == graph.topology_hash,
        "stage_sequence": native.stage_sequence == graph.stage_sequence,
        "normalized_state": native.state == graph.state,
        "event_fold": native.event_fold == graph.event_fold,
        "resume_cursor": native.resume_cursor == graph.resume_cursor,
        "artifact_inventory_content_hashes": native.artifacts == graph.artifacts,
    }
    assert all(report.values()), report


def _artifact_inventory(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name in _ARTIFACT_SKIP_NAMES:
            continue
        rel = path.relative_to(root).as_posix()
        inventory[rel] = f"sha256:{_content_digest(path, root)}"
    return inventory


def _content_digest(path: Path, root: Path) -> str:
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _typed_ports_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)


def test_epic_blitz_native_projection_matches_legacy_graph_execution(
    tmp_path: Path,
) -> None:
    graph = _run_trace(_build_legacy_pipeline, tmp_path / "graph")
    native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_projected",
    )

    _assert_parity(native, graph)
    assert native.topology_hash == EXPECTED_EPIC_BLITZ_TOPOLOGY_HASH
    assert native.stage_sequence == EXPECTED_EPIC_BLITZ_STAGE_ORDER
    assert tuple(native.artifacts) == _EXPECTED_ARTIFACTS


def test_epic_blitz_resume_from_panel_barrier_matches_legacy_graph(
    tmp_path: Path,
) -> None:
    suspended_graph = _run_trace(
        _build_legacy_pipeline,
        tmp_path / "graph_resume",
        suspend_before="high_revise",
    )
    suspended_native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_resume",
        suspend_before="high_revise",
    )

    expected_cursor = {"stage": "high_revise", "input": None}
    assert suspended_graph.resume_cursor == expected_cursor
    assert suspended_native.resume_cursor == expected_cursor
    assert suspended_graph.stage_sequence == ("high_panel",)
    assert suspended_native.stage_sequence == ("high_panel",)

    resumed_graph = _run_trace(
        _build_legacy_pipeline,
        tmp_path / "graph_resume",
        resume=True,
    )
    resumed_native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_resume",
        resume=True,
    )
    full_native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_full",
    )

    _assert_parity(resumed_native, resumed_graph)
    assert resumed_native.stage_sequence == (
        "high_revise",
        "mid_panel",
        "mid_revise",
        "low_panel",
        "readiness",
    )
    assert (
        suspended_native.stage_sequence + resumed_native.stage_sequence
        == EXPECTED_EPIC_BLITZ_STAGE_ORDER
    )
    assert resumed_native.state == full_native.state
    assert resumed_native.event_fold == full_native.event_fold
    assert resumed_native.artifacts == full_native.artifacts
