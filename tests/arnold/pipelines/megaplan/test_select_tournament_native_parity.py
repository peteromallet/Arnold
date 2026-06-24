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
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipeline.native.parity_trace import normalize_event_fold
from tests.arnold.pipelines.megaplan.parity_harness import (
    normalize_cursor_narrow,
    normalize_state_narrow,
)
from tests.arnold.pipelines.megaplan.test_graph_baseline import (
    EXPECTED_SELECT_TOURNAMENT_TOPOLOGY_HASH,
)


_SELECT_MODULE = "arnold.pipelines.megaplan.pipelines.select-tournament"
_EXPECTED_STAGE_SEQUENCE = ("score_candidates", "pairwise_bracket", "winner")
_EXPECTED_ARTIFACTS = (
    "pairwise_bracket/v1.json",
    "score_candidates/candidate_0.json",
    "score_candidates/candidate_1.json",
    "score_candidates/candidate_2.json",
    "score_candidates/candidate_3.json",
    "score_candidates/v1.json",
    "state.json",
    "winner/v1.json",
)
_ARTIFACT_SKIP_NAMES = frozenset({
    ".events.init_ts",
    ".events.seq",
    "events.ndjson",
    "resume_cursor.json",
})


@dataclass(frozen=True)
class _SelectTournamentTrace:
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


def _load_select_module() -> Any:
    return importlib.import_module(_SELECT_MODULE)


def _build_legacy_pipeline(candidates: tuple[str, ...]) -> Any:
    return _load_select_module()._build_legacy_graph_pipeline(candidates=candidates)


def _build_native_projected_pipeline(candidates: tuple[str, ...]) -> Any:
    return _load_select_module().build_pipeline(candidates=candidates)


def _run_trace(
    pipeline_factory: Callable[[tuple[str, ...]], Any],
    root: Path,
    *,
    candidates: tuple[str, ...],
    suspend_before: str | None = None,
    resume: bool = False,
) -> _SelectTournamentTrace:
    pipeline = pipeline_factory(candidates)
    canonical = to_canonical_pipeline(pipeline)
    hooks = _TraceHooks(root, suspend_before=suspend_before)
    envelope = RuntimeEnvelope(
        plugin_id="select_tournament_parity",
        run_id=root.name,
        artifact_root=str(root),
    )

    if resume:
        run_pipeline_resume(canonical, {}, envelope, hooks=hooks)
    else:
        run_pipeline(canonical, {}, envelope, hooks=hooks)

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
    return _SelectTournamentTrace(
        topology_hash=_topology_hash(pipeline),
        stage_sequence=tuple(hooks.stage_sequence),
        state=normalize_state_narrow(hooks.final_state),
        event_fold=normalize_event_fold(folded),
        resume_cursor=normalize_cursor_narrow(cursor),
        artifacts=_artifact_inventory(root),
    )


def _assert_parity(native: _SelectTournamentTrace, graph: _SelectTournamentTrace) -> None:
    report = {
        "topology_hash": native.topology_hash == graph.topology_hash,
        "stage_sequence": native.stage_sequence == graph.stage_sequence,
        "normalized_state": native.state == graph.state,
        "event_fold": native.event_fold == graph.event_fold,
        "resume_cursor": native.resume_cursor == graph.resume_cursor,
        "artifact_inventory_content_hashes": native.artifacts == graph.artifacts,
    }
    assert all(report.values()), report


def _topology_hash(pipeline: Any) -> str:
    # The select-tournament baseline hash is the structural graph identity.
    # Typed-port execution may attach tuple-keyed binding_map metadata, which
    # is not part of that baseline and is not JSON-key serializable here.
    if getattr(pipeline, "binding_map", None) is not None:
        pipeline = dataclasses.replace(pipeline, binding_map=None)
    return compute_topology_hash(pipeline)


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
def _typed_ports_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")


def test_select_tournament_native_projection_matches_legacy_graph_execution(
    tmp_path: Path,
) -> None:
    candidates = ("alpha", "beta", "gamma", "delta")

    graph = _run_trace(
        _build_legacy_pipeline,
        tmp_path / "graph",
        candidates=candidates,
    )
    native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_projected",
        candidates=candidates,
    )

    _assert_parity(native, graph)
    assert native.topology_hash == EXPECTED_SELECT_TOURNAMENT_TOPOLOGY_HASH
    assert native.stage_sequence == _EXPECTED_STAGE_SEQUENCE
    assert tuple(native.artifacts) == _EXPECTED_ARTIFACTS


def test_select_tournament_resume_from_fan_in_barrier_matches_legacy_graph(
    tmp_path: Path,
) -> None:
    candidates = ("alpha", "beta", "gamma", "delta")

    suspended_graph = _run_trace(
        _build_legacy_pipeline,
        tmp_path / "graph_resume",
        candidates=candidates,
        suspend_before="pairwise_bracket",
    )
    suspended_native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_resume",
        candidates=candidates,
        suspend_before="pairwise_bracket",
    )

    expected_cursor = {"stage": "pairwise_bracket", "input": None}
    assert suspended_graph.resume_cursor == expected_cursor
    assert suspended_native.resume_cursor == expected_cursor
    assert suspended_graph.stage_sequence == ("score_candidates",)
    assert suspended_native.stage_sequence == ("score_candidates",)

    resumed_graph = _run_trace(
        _build_legacy_pipeline,
        tmp_path / "graph_resume",
        candidates=candidates,
        resume=True,
    )
    resumed_native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_resume",
        candidates=candidates,
        resume=True,
    )
    full_native = _run_trace(
        _build_native_projected_pipeline,
        tmp_path / "native_full",
        candidates=candidates,
    )

    _assert_parity(resumed_native, resumed_graph)
    assert resumed_native.stage_sequence == ("pairwise_bracket", "winner")
    assert (
        suspended_native.stage_sequence + resumed_native.stage_sequence
        == _EXPECTED_STAGE_SEQUENCE
    )
    assert resumed_native.state == full_native.state
    assert resumed_native.event_fold == full_native.event_fold
    assert resumed_native.artifacts == full_native.artifacts
