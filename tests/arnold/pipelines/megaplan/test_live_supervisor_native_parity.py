"""Native/graph parity coverage for ``live-supervisor`` pipeline.

The final ``recheck_emit`` stage writes a wall-clock ``recheck_after``
timestamp. These tests normalize only that named value before comparing
state, event folds, and artifact content hashes.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import StepResult
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.native import run_native_pipeline
from arnold.pipeline.native.hooks import NullNativeRuntimeHooks
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.topology import compute_topology_hash
from arnold.pipelines.megaplan.pipelines import live_supervisor as live_supervisor_mod
from arnold.pipelines.megaplan.pipelines.live_supervisor import build_pipeline
from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    HealthCategory,
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold.pipelines.megaplan.pipelines.live_supervisor.pipelines import _native_bundle
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipelines.megaplan.parity_harness import (
    normalize_cursor_narrow,
    normalize_state_narrow,
)


EXPECTED_LIVE_SUPERVISOR_TOPOLOGY_HASH = (
    "sha256:037bc66606d01104c0a2742c82cf00d0b0004c78b18377f473f4ff4fd6b7e74e"
)
EXPECTED_STAGE_SEQUENCE = (
    "classify",
    "diagnose",
    "repair_decision",
    "recheck_emit",
)
_RECHECK_AFTER_SENTINEL = "<recheck-after>"
_CHECKPOINT_SKIP_NAMES = frozenset({
    ".events.init_ts",
    ".events.seq",
    "events.ndjson",
    "resume_cursor.json",
    "state.json",
    "awaiting_user.json",
})


@dataclass(frozen=True)
class _LiveSupervisorTrace:
    topology_hash: str
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifacts: dict[str, str]


class _GraphTraceHooks(NullExecutorHooks):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.stage_sequence: list[str] = []
        self.final_state: dict[str, Any] | None = None
        self._root = root
        self._journal = NdjsonEventJournal(root)

    def on_stage_complete(
        self,
        stage: Any,
        ctx: Any,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, result, owned_keys
        json_state = _jsonable(state) if isinstance(state, dict) else {}
        assert isinstance(json_state, dict)
        self.stage_sequence.append(stage.name)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)
        self._journal.emit(
            "state_written",
            payload={"stage": stage.name, "state": json_state},
            phase=stage.name,
        )


class _NativeTraceHooks(NullNativeRuntimeHooks):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.stage_sequence: list[str] = []
        self.final_state: dict[str, Any] | None = None
        self._root = root
        self._journal = NdjsonEventJournal(root)

    def on_stage_complete(
        self,
        instr: Any,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, result, owned_keys
        json_state = _jsonable(state)
        assert isinstance(json_state, dict)
        self.stage_sequence.append(instr.name)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)
        self._journal.emit(
            "state_written",
            payload={"stage": instr.name, "state": json_state},
            phase=instr.name,
        )

    def on_checkpoint(self, cursor: dict[str, Any], state: dict[str, Any]) -> None:
        json_state = _jsonable(state)
        assert isinstance(json_state, dict)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)


def _snapshot_with_false_stall() -> Snapshot:
    entry = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    incident = Incident(
        plan_entry=entry,
        signals=SignalBundle(
            liveness="progressing",
            liveness_reason="llm in flight",
            block_details={},
            doctor_findings=(),
            has_in_flight_llm=True,
            last_event_age_seconds=350.0,
        ),
        triage=Triage.LIVE,
    )
    return Snapshot(
        scan_ts_utc="2026-06-20T00:00:00+00:00",
        plans=(entry,),
        incidents=(incident,),
    )


def _initial_state() -> dict[str, Any]:
    return {
        "snapshot": _snapshot_with_false_stall().to_dict(),
        "_pipeline_name": "live-supervisor",
        "_pipeline_version": 1,
    }


def _run_graph_trace(root: Path, initial_state: dict[str, Any]) -> _LiveSupervisorTrace:
    pipeline = build_pipeline()
    hooks = _GraphTraceHooks(root)
    envelope = RuntimeEnvelope(
        plugin_id="live_supervisor_parity",
        run_id="graph",
        artifact_root=str(root),
    )

    import os

    previous_runtime = os.environ.get("ARNOLD_PIPELINE_RUNTIME")
    os.environ["ARNOLD_PIPELINE_RUNTIME"] = "graph"
    try:
        run_pipeline(
            pipeline,
            initial_state=copy.deepcopy(initial_state),
            envelope=envelope,
            hooks=hooks,
        )
    finally:
        if previous_runtime is None:
            os.environ.pop("ARNOLD_PIPELINE_RUNTIME", None)
        else:
            os.environ["ARNOLD_PIPELINE_RUNTIME"] = previous_runtime

    return _trace_from_root(
        root,
        topology_hash=compute_topology_hash(build_pipeline()),
        stage_sequence=tuple(hooks.stage_sequence),
        state=hooks.final_state,
    )


def _run_native_trace(
    root: Path,
    initial_state: dict[str, Any],
    *,
    resume: bool = False,
    max_phases: int | None = None,
) -> _LiveSupervisorTrace:
    program = _native_bundle()
    assert isinstance(program, NativeProgram)

    hooks = _NativeTraceHooks(root)
    if resume:
        result = run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            hooks=hooks,
        )
    else:
        result = run_native_pipeline(
            program,
            artifact_root=root,
            initial_state=copy.deepcopy(initial_state),
            max_phases=max_phases,
            hooks=hooks,
        )

    return _trace_from_root(
        root,
        topology_hash=compute_topology_hash(build_pipeline()),
        stage_sequence=_native_stage_sequence(result),
        state=hooks.final_state,
    )


def _native_stage_sequence(result: Any) -> tuple[str, ...]:
    seq: list[str] = []
    for stage_id in result.stages:
        parts = stage_id.split("__")
        if len(parts) >= 2:
            seq.append(parts[-2])
    return tuple(seq)


def _trace_from_root(
    root: Path,
    *,
    topology_hash: str,
    stage_sequence: tuple[str, ...],
    state: dict[str, Any] | None,
) -> _LiveSupervisorTrace:
    events = read_event_journal(root)
    folded = fold_journal(
        events,
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial=None,
    )
    cursor_path = root / "resume_cursor.json"
    resume_cursor = (
        json.loads(cursor_path.read_text(encoding="utf-8"))
        if cursor_path.exists()
        else None
    )

    return _LiveSupervisorTrace(
        topology_hash=topology_hash,
        stage_sequence=stage_sequence,
        state=_normalize_state(state),
        event_fold=_normalize_state(folded),
        resume_cursor=normalize_cursor_narrow(resume_cursor),
        artifacts=_artifact_inventory(root),
    )


def _normalize_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    normalized = normalize_state_narrow(state)
    return _normalize_recheck_after(normalized)


def _normalize_recheck_after(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                _RECHECK_AFTER_SENTINEL
                if str(key) == "recheck_after"
                else _normalize_recheck_after(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_recheck_after(item) for item in value]
    return value


def _artifact_inventory(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name in _CHECKPOINT_SKIP_NAMES:
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
        normalized = _normalize_recheck_after(_normalize_artifact_payload(payload, root))
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
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


class TestLiveSupervisorNativeParity:
    def test_topology_hash_matches_baseline_and_driver_is_native(self) -> None:
        pipeline = build_pipeline()

        assert live_supervisor_mod.driver == ("native", "linear")
        assert compute_topology_hash(pipeline) == EXPECTED_LIVE_SUPERVISOR_TOPOLOGY_HASH
        native_program = pipeline.native_program
        assert isinstance(native_program, NativeProgram)
        assert [phase.name for phase in native_program.phases] == list(
            EXPECTED_STAGE_SEQUENCE
        )

    def test_full_run_parity_with_normalized_recheck_after(
        self,
        tmp_path: Path,
    ) -> None:
        initial_state = _initial_state()

        graph = _run_graph_trace(tmp_path / "graph", initial_state)
        native = _run_native_trace(tmp_path / "native", initial_state)

        assert graph.topology_hash == native.topology_hash == (
            EXPECTED_LIVE_SUPERVISOR_TOPOLOGY_HASH
        )
        assert graph.stage_sequence == native.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert graph.state == native.state
        assert graph.event_fold == native.event_fold
        assert graph.artifacts == native.artifacts

        recheck = native.state.get("recheck_emit") if native.state else None
        assert isinstance(recheck, dict)
        assert recheck["recheck_after"] == _RECHECK_AFTER_SENTINEL
        assert recheck["resumable"] is True
        assert recheck["decisions"]
        assert recheck["decisions"][0]["plan_id"] == "p1"
        assert recheck["decisions"][0]["health_category"] == (
            HealthCategory.FALSE_STALL.value
        )

    def test_resume_after_repair_decision(
        self,
        tmp_path: Path,
    ) -> None:
        initial_state = _initial_state()
        root = tmp_path / "native_resume"

        first = _run_native_trace(
            root,
            initial_state,
            max_phases=3,
        )

        assert first.stage_sequence == (
            "classify",
            "diagnose",
            "repair_decision",
        )
        cursor_path = root / "resume_cursor.json"
        assert cursor_path.exists()
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert cursor["reentry_stage"].endswith("__recheck_emit__pc3")
        assert cursor["native"]["pc"] >= 3

        second = _run_native_trace(root, initial_state, resume=True)

        assert second.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert second.state is not None
        recheck = second.state.get("recheck_emit")
        assert isinstance(recheck, dict)
        assert recheck["recheck_after"] == _RECHECK_AFTER_SENTINEL
        assert recheck["resumable"] is True
        for stage in EXPECTED_STAGE_SEQUENCE:
            assert (root / stage).is_dir()
