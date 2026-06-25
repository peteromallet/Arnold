"""Native coverage for the dynamic-width ``doc`` pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.native import run_native_pipeline
from arnold.pipeline.native.hooks import NullNativeRuntimeHooks
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipelines.megaplan.pipelines.doc import build_pipeline
from arnold.pipelines.megaplan.pipelines.doc.steps import SectionDraftStep
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector


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
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    artifacts: dict[str, str]


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


def _run_native_trace(
    root: Path,
    sections: list[dict[str, str]] | None,
    *,
    resume: bool = False,
    max_phases: int | None = None,
) -> _DocTrace:
    pipeline = build_pipeline()
    program = pipeline.native_program
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
            initial_state=_initial_state(),
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
    return _DocTrace(
        stage_sequence=stage_sequence,
        state=_normalize_state(state, root),
        event_fold=_normalize_state(folded, root),
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


def _normalize_state(value: Any, root: Path) -> Any:
    if isinstance(value, str):
        return value.replace(str(root), "<artifact-root>")
    if isinstance(value, dict):
        return {str(key): _normalize_state(item, root) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_state(item, root) for item in value]
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


class TestDocNative:
    def test_split_public_surface_and_native_bundle(self) -> None:
        import arnold.pipelines.megaplan.pipelines.doc as doc
        import arnold.pipelines.megaplan.pipelines.doc.pipeline as doc_pipeline
        import arnold_pipelines.megaplan.pipelines.doc as mirror
        import arnold_pipelines.megaplan.pipelines.doc.pipeline as mirror_pipeline

        pipeline = doc.build_pipeline()
        native_program = pipeline.native_program

        assert doc.build_pipeline is doc_pipeline.build_pipeline
        assert mirror.build_pipeline is doc.build_pipeline
        assert mirror_pipeline.build_pipeline is doc_pipeline.build_pipeline
        assert doc.supported_modes == ("native",)
        assert doc.driver == ("native", "dynamic-fanout")
        assert not hasattr(doc, "_build_graph_pipeline")
        assert isinstance(native_program, NativeProgram)
        assert native_program.name == "doc"
        assert [phase.name for phase in native_program.phases] == list(
            EXPECTED_STAGE_SEQUENCE
        )
        assert tuple(pipeline.resource_bundles) == ()

    @pytest.mark.parametrize("section_count", [0, 1, 3])
    def test_native_section_fanout_artifacts_and_final_assembly(
        self,
        tmp_path: Path,
        section_count: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sections = [] if section_count == 0 else _sections(section_count)
        call_section_ids: list[str] = []
        original_run = SectionDraftStep.run

        def spy_run(self: SectionDraftStep, ctx: Any) -> Any:
            call_section_ids.append(self.section_id)
            return original_run(self, ctx)

        monkeypatch.setattr(SectionDraftStep, "run", spy_run)

        trace = _run_native_trace(tmp_path / "native", sections)

        assert trace.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert call_section_ids == [section["section_id"] for section in sections]
        _assert_section_artifacts(tmp_path / "native", sections)
        final = tmp_path / "native" / "assembly" / "final.md"
        assert final.exists()
        assert "assembly/final.md" in trace.artifacts
        assert trace.state is not None
        assert trace.event_fold == trace.state

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
