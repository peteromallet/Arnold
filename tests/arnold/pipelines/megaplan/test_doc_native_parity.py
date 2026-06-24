"""Native/graph parity coverage for the dynamic-width ``doc`` pipeline."""

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
from arnold.pipelines.megaplan.pipelines.doc import _native_bundle, build_pipeline
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipelines.megaplan.parity_harness import (
    MegaplanParityHarness,
    normalize_cursor_narrow,
    normalize_state_narrow,
)


EXPECTED_DOC_TOPOLOGY_HASH = (
    "sha256:4f7945027fc5d1a035f24779e3cfb733eadb9d41cf6b3334b60b8d56c158e666"
)
EXPECTED_STAGE_SEQUENCE = (
    "outline",
    "section_drafts",
    "critique",
    "revise",
    "assembly",
)
_CHECKPOINT_SKIP_NAMES = frozenset({
    ".events.init_ts",
    ".events.seq",
    "events.ndjson",
    "resume_cursor.json",
    "state.json",
    "awaiting_user.json",
})


@dataclass(frozen=True)
class _DocTrace:
    topology_hash: str
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifacts: dict[str, str]

    def as_harness_dict(self) -> dict[str, Any]:
        return {
            "topology_hash": self.topology_hash,
            "stage_sequence": list(self.stage_sequence),
            "state": self.state,
            "envelope": None,
            "resume_cursor": self.resume_cursor,
            "artifact_inventory": self.artifacts,
            "event_fold": self.event_fold,
        }


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


def _initial_state() -> dict[str, Any]:
    return {
        "_pipeline_name": "doc",
        "_pipeline_version": 1,
    }


def _sections(count: int) -> list[dict[str, str]]:
    all_sections = [
        {"section_id": "intro", "section_title": "Intro"},
        {"section_id": "body", "section_title": "Body"},
        {"section_id": "conclusion", "section_title": "Conclusion"},
    ]
    return all_sections[:count]


def _seed_sections(root: Path, sections: list[dict[str, str]] | None) -> None:
    if sections is None:
        return
    outline = root / "outline" / "sections.json"
    outline.parent.mkdir(parents=True, exist_ok=True)
    outline.write_text(json.dumps(sections), encoding="utf-8")


def _run_graph_trace(
    root: Path,
    sections: list[dict[str, str]] | None,
) -> _DocTrace:
    root.mkdir(parents=True, exist_ok=True)
    _seed_sections(root, sections)

    pipeline = build_pipeline()
    hooks = _GraphTraceHooks(root)
    envelope = RuntimeEnvelope(
        plugin_id="doc_native_parity",
        run_id="graph",
        artifact_root=str(root),
    )
    import os

    previous_runtime = os.environ.get("ARNOLD_PIPELINE_RUNTIME")
    os.environ["ARNOLD_PIPELINE_RUNTIME"] = "graph"
    try:
        run_pipeline(
            pipeline,
            initial_state=copy.deepcopy(_initial_state()),
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
        stage_sequence=tuple(hooks.stage_sequence),
        state=hooks.final_state,
    )


def _run_native_trace(
    root: Path,
    sections: list[dict[str, str]] | None,
    *,
    resume: bool = False,
    max_phases: int | None = None,
) -> _DocTrace:
    program = _native_bundle()
    assert isinstance(program, NativeProgram)

    root.mkdir(parents=True, exist_ok=True)
    if not resume:
        _seed_sections(root, sections)

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
            initial_state=copy.deepcopy(_initial_state()),
            max_phases=max_phases,
            hooks=hooks,
        )

    return _trace_from_root(
        root,
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
    stage_sequence: tuple[str, ...],
    state: dict[str, Any] | None,
) -> _DocTrace:
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

    return _DocTrace(
        topology_hash=compute_topology_hash(build_pipeline()),
        stage_sequence=stage_sequence,
        state=normalize_state_narrow(state),
        event_fold=normalize_state_narrow(folded),
        resume_cursor=normalize_cursor_narrow(resume_cursor),
        artifacts=_artifact_inventory(root),
    )


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
    data = raw.replace(str(root).encode("utf-8"), b"<artifact-root>")
    return hashlib.sha256(data).hexdigest()


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


def _assert_section_artifacts(
    root: Path,
    sections: list[dict[str, str]],
) -> None:
    if not sections:
        assert not list((root / "section_drafts").glob("*.md"))
        return
    for section in sections:
        sid = section["section_id"]
        title = section["section_title"]
        path = root / "section_drafts" / f"{sid}.md"
        assert path.read_text(encoding="utf-8") == f"# {title}\n"


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)


class TestDocNativeParity:
    def test_topology_hash_and_native_bundle(self) -> None:
        pipeline = build_pipeline()
        native_programs = [
            bundle for bundle in pipeline.resource_bundles
            if isinstance(bundle, NativeProgram)
        ]

        assert compute_topology_hash(pipeline) == EXPECTED_DOC_TOPOLOGY_HASH
        assert len(native_programs) == 1
        assert [phase.name for phase in native_programs[0].phases] == list(
            EXPECTED_STAGE_SEQUENCE
        )

    @pytest.mark.parametrize("section_count", [0, 1, 3])
    def test_graph_native_parity_for_dynamic_section_widths(
        self,
        tmp_path: Path,
        section_count: int,
    ) -> None:
        sections = None if section_count == 0 else _sections(section_count)
        expected_sections = [] if sections is None else sections

        graph = _run_graph_trace(tmp_path / "graph", sections)
        native = _run_native_trace(tmp_path / "native", sections)
        report = MegaplanParityHarness().compare_native_to_graph(
            native.as_harness_dict(),
            graph.as_harness_dict(),
            topology_hash=EXPECTED_DOC_TOPOLOGY_HASH,
        )

        assert graph.stage_sequence == native.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert report["topology_hash"] == "match"
        assert report["stage_sequence"] == "match"
        assert report["state"] == "match"
        assert report["resume_cursor"] == "match"
        assert report["artifact_inventory"] == "match"
        assert report["event_fold"] == "match"
        _assert_section_artifacts(tmp_path / "graph", expected_sections)
        _assert_section_artifacts(tmp_path / "native", expected_sections)

    @pytest.mark.parametrize(
        ("max_phases", "expected_first_sequence", "expected_reentry_suffix"),
        [
            (1, ("outline",), "__section_drafts__pc1"),
            (2, ("outline", "section_drafts"), "__critique__pc2"),
        ],
    )
    def test_native_resume_before_and_after_section_drafts(
        self,
        tmp_path: Path,
        max_phases: int,
        expected_first_sequence: tuple[str, ...],
        expected_reentry_suffix: str,
    ) -> None:
        sections = _sections(3)
        root = tmp_path / f"resume_{max_phases}"
        full = _run_native_trace(tmp_path / f"full_{max_phases}", sections)

        first = _run_native_trace(root, sections, max_phases=max_phases)
        assert first.stage_sequence == expected_first_sequence
        cursor_path = root / "resume_cursor.json"
        assert cursor_path.exists()
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert cursor["reentry_stage"].endswith(expected_reentry_suffix)
        assert cursor["native"]["pc"] >= max_phases

        if max_phases >= 2:
            _assert_section_artifacts(root, sections)

        second = _run_native_trace(root, sections, resume=True)
        assert second.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert second.state == full.state
        assert second.event_fold == full.event_fold
        assert second.artifacts == full.artifacts
        _assert_section_artifacts(root, sections)
