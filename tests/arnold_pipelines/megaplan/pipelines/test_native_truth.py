"""Native truth runtime trace tests for subpipeline native programs.

These tests exercise each subpipeline's ``native_program`` through the
native runtime and verify trace contract compliance: event kinds, stage
sequences, artifact outputs, and resume behavior.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold_pipelines.megaplan.pipelines.creative import build_pipeline as build_creative
from arnold_pipelines.megaplan.pipelines.doc import build_pipeline as build_doc
from arnold_pipelines.megaplan.pipelines.jokes import build_pipeline as build_jokes
from arnold_pipelines.megaplan.pipelines.live_supervisor import (
    build_pipeline as build_live_supervisor,
)
from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold_pipelines.megaplan.pipelines.select_tournament import (
    build_pipeline as build_select_tournament,
)
from arnold_pipelines.megaplan.pipelines.writing_panel_strict import (
    build_pipeline as build_writing_panel_strict,
)


def _trace_event_kinds(trace_dir: Path) -> list[str]:
    return [json.loads(line)["kind"] for line in (trace_dir / "events.ndjson").read_text().splitlines()]


def _trace_stage_sequence(trace_dir: Path) -> list[str]:
    return json.loads((trace_dir / "stages.json").read_text())


def _assert_trace_contract(trace_dir: Path, expected_stages: list[str]) -> None:
    kinds = _trace_event_kinds(trace_dir)
    counts = Counter(kinds)

    assert (trace_dir / "state.json").is_file()
    assert (trace_dir / "checkpoint.json").is_file()
    assert _trace_stage_sequence(trace_dir) == expected_stages
    assert kinds[0] == "pipeline.init"
    assert counts["phase.start"] == len(expected_stages)
    assert counts["phase.end"] == len(expected_stages)
    assert counts["stage.complete"] == len(expected_stages)
    assert counts["checkpoint"] == 1


def _live_supervisor_snapshot() -> dict[str, object]:
    entry = PlanEntry(
        plan_id="p1",
        plan_name="plan",
        plan_dir="/tmp/plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    signals = SignalBundle(
        liveness="stalled",
        liveness_reason="no events",
        block_details={"is_blocked": True, "recoverable_via": "resume"},
        doctor_findings=(),
    )
    incident = Incident(plan_entry=entry, signals=signals, triage=Triage.STALE)
    return Snapshot.now(plans=(entry,), incidents=(incident,)).to_dict()


def test_creative_native_truth_runtime_trace_and_output(tmp_path: Path) -> None:
    artifact_root = tmp_path / "creative"
    trace_dir = tmp_path / "creative-trace"

    result = run_native_pipeline(
        build_creative(form="joke").native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={"idea": "write a joke about parsers"},
    )

    assert result.suspended is False
    assert "finalize" in result.state
    assert (artifact_root / "finalize" / "v1.md").read_text(encoding="utf-8").startswith("# finalize")
    _assert_trace_contract(
        trace_dir,
        [
            "prep__pc0",
            "execute_creative__pc1",
            "critique_creative__pc2",
            "revise_creative__pc3",
            "finalize__pc4",
        ],
    )


def test_doc_native_truth_runtime_trace_and_output(tmp_path: Path) -> None:
    artifact_root = tmp_path / "doc"
    trace_dir = tmp_path / "doc-trace"
    outline_dir = artifact_root / "outline"
    outline_dir.mkdir(parents=True)
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
    assert (artifact_root / "section_drafts" / "intro.md").is_file()
    assert (artifact_root / "section_drafts" / "body.md").is_file()
    assert (artifact_root / "assembly" / "final.md").is_file()
    _assert_trace_contract(
        trace_dir,
        [
            "outline__pc0",
            "section_drafts__pc1",
            "critique__pc2",
            "revise__pc3",
            "assembly__pc4",
        ],
    )


def test_jokes_native_truth_runtime_trace_and_output(tmp_path: Path) -> None:
    artifact_root = tmp_path / "jokes"
    trace_dir = tmp_path / "jokes-trace"

    result = run_native_pipeline(
        build_jokes(topic="cats").native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={},
    )

    assert result.suspended is False
    assert "cats" in (artifact_root / "emit" / "v1.md").read_text(encoding="utf-8")
    _assert_trace_contract(
        trace_dir,
        ["draft__pc0", "tighten__pc1", "emit__pc2"],
    )


def test_live_supervisor_native_truth_runtime_trace_and_output(tmp_path: Path) -> None:
    artifact_root = tmp_path / "live-supervisor"
    trace_dir = tmp_path / "live-supervisor-trace"

    result = run_native_pipeline(
        build_live_supervisor().native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={"snapshot": _live_supervisor_snapshot()},
    )

    payload = json.loads((artifact_root / "recheck_emit" / "recheck_emit.json").read_text())
    assert result.suspended is False
    assert payload["resumable"] is True
    assert payload["decisions"][0]["recommended_command"] == "auto"
    _assert_trace_contract(
        trace_dir,
        [
            "classify__pc0",
            "diagnose__pc1",
            "repair_decision__pc2",
            "recheck_emit__pc3",
        ],
    )


def test_select_tournament_native_truth_runtime_trace_and_output(tmp_path: Path) -> None:
    artifact_root = tmp_path / "select-tournament"
    trace_dir = tmp_path / "select-tournament-trace"

    result = run_native_pipeline(
        build_select_tournament(candidates=("a", "b", "c")).native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={},
    )

    winner = json.loads((artifact_root / "winner" / "v1.json").read_text())
    assert result.suspended is False
    assert winner["winner"] == "c"
    _assert_trace_contract(
        trace_dir,
        [
            "candidate_score_0__pc1",
            "candidate_score_1__pc2",
            "candidate_score_2__pc3",
            "pairwise_bracket__pc4",
            "winner__pc5",
        ],
    )


def test_writing_panel_strict_native_truth_route_labels_and_resume(tmp_path: Path) -> None:
    artifact_root = tmp_path / "writing-panel-strict"
    trace_dir = tmp_path / "writing-panel-strict-trace"
    artifact_root.mkdir()
    draft_path = artifact_root / "draft.md"
    draft_path.write_text("Draft body", encoding="utf-8")

    first = run_native_pipeline(
        build_writing_panel_strict().native_program,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
        initial_state={
            "_pipeline_name": "writing-panel-strict",
            "draft_path": str(draft_path),
        },
    )

    cursor = json.loads((artifact_root / "resume_cursor.json").read_text())
    assert first.suspended is True
    assert cursor["stage"] == "writing_panel_strict__human_decide__pc3"
    assert cursor["native"]["suspension_kind"] == "human_gate"
    assert cursor["choices"] == ["continue", "stop"]
    _assert_trace_contract(
        trace_dir,
        ["panel_review__pc0", "synth__pc1", "revise__pc2"],
    )

    resumed = run_native_pipeline(
        build_writing_panel_strict().native_program,
        artifact_root=artifact_root,
        trace_dir=tmp_path / "writing-panel-strict-trace-resume",
        initial_state=first.state,
        resume=True,
        human_input="stop",
    )

    assert resumed.suspended is False
    assert resumed.stages[-1] == "writing_panel_strict__human_decide_guard__pc3"
