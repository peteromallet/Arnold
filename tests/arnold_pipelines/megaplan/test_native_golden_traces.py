"""Committed native golden trace regression fixtures for deterministic scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold_pipelines.megaplan.pipelines.creative import build_pipeline as build_creative
from arnold_pipelines.megaplan.pipelines.doc import build_pipeline as build_doc
from arnold_pipelines.megaplan.pipelines.jokes import build_pipeline as build_jokes
from arnold_pipelines.megaplan.pipelines.select_tournament import (
    build_pipeline as build_select_tournament,
)
from arnold_pipelines.megaplan.pipelines.writing_panel_strict import (
    build_pipeline as build_writing_panel_strict,
)
from tests.arnold_pipelines.megaplan.fixtures.native_goldens import (
    TRACE_FILE_NAMES,
    compare_native_golden_dir,
    record_native_golden_dir,
)

GOLDEN_ROOT = Path(__file__).resolve().parent / "fixtures" / "native_goldens"
_RECORD_OPTION = "--record-goldens"


@dataclass(frozen=True)
class ScenarioCase:
    scenario_id: str
    runner: Callable[[Path], Path]


def _run_creative(base: Path) -> Path:
    artifact_root = base / "artifacts"
    trace_dir = base / "trace"
    result = run_native_pipeline(
        build_creative(form="joke").native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={"idea": "write a joke about parsers"},
    )
    assert result.suspended is False
    return trace_dir


def _run_doc(base: Path) -> Path:
    artifact_root = base / "artifacts"
    trace_dir = base / "trace"
    outline_dir = artifact_root / "outline"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "sections.json").write_text(
        json.dumps(
            [
                {"section_id": "intro", "section_title": "Intro"},
                {"section_id": "body", "section_title": "Body"},
            ]
        ),
        encoding="utf-8",
    )
    result = run_native_pipeline(
        build_doc().native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={},
    )
    assert result.suspended is False
    return trace_dir


def _run_jokes(base: Path) -> Path:
    artifact_root = base / "artifacts"
    trace_dir = base / "trace"
    result = run_native_pipeline(
        build_jokes(topic="cats").native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={},
    )
    assert result.suspended is False
    return trace_dir


def _run_select_tournament(base: Path) -> Path:
    artifact_root = base / "artifacts"
    trace_dir = base / "trace"
    result = run_native_pipeline(
        build_select_tournament(candidates=("a", "b", "c")).native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={},
    )
    assert result.suspended is False
    return trace_dir


def _run_writing_panel_strict(base: Path) -> Path:
    artifact_root = base / "artifacts"
    trace_dir = base / "trace"
    artifact_root.mkdir(parents=True, exist_ok=True)
    draft_path = artifact_root / "draft.md"
    draft_path.write_text("Draft body", encoding="utf-8")
    result = run_native_pipeline(
        build_writing_panel_strict().native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={
            "_pipeline_name": "writing-panel-strict",
            "draft_path": str(draft_path),
        },
    )
    assert result.suspended is True
    return trace_dir


SCENARIO_CASES: tuple[ScenarioCase, ...] = (
    ScenarioCase("D2-critique", _run_creative),
    ScenarioCase("D3-gate-preflight", _run_writing_panel_strict),
    ScenarioCase("D4-gate-revise", _run_creative),
    ScenarioCase("D5-tiebreaker", _run_select_tournament),
    ScenarioCase("D6-finalize", _run_doc),
    ScenarioCase("D8-execute-gates", _run_writing_panel_strict),
    ScenarioCase("D12-runtime-trace", _run_jokes),
)


def _assert_exact_trace_files(trace_dir: Path, *, allow_hidden: bool = False) -> None:
    assert trace_dir.is_dir(), f"Trace directory missing: {trace_dir}"
    names = {
        path.name for path in trace_dir.iterdir()
        if allow_hidden or not path.name.startswith(".")
    }
    assert names == set(TRACE_FILE_NAMES)


@pytest.mark.parametrize(
    "case",
    SCENARIO_CASES,
    ids=[case.scenario_id for case in SCENARIO_CASES],
)
def test_committed_native_golden_trace(case: ScenarioCase, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    actual_dir = case.runner(tmp_path / case.scenario_id)
    _assert_exact_trace_files(actual_dir, allow_hidden=False)

    golden_dir = GOLDEN_ROOT / case.scenario_id
    if request.config.getoption(_RECORD_OPTION):
        record_native_golden_dir(actual_dir, golden_dir, overwrite=True)

    _assert_exact_trace_files(golden_dir)
    ok, message = compare_native_golden_dir(golden_dir, actual_dir)
    assert ok, message


def test_no_graph_era_single_file_goldens_exist() -> None:
    legacy_names = {
        "golden_graph_trace.json",
        "golden_native_trace.json",
        "golden_composite_cursor.json",
    }
    existing = sorted(path.name for path in GOLDEN_ROOT.rglob("*") if path.name in legacy_names)
    assert existing == []
