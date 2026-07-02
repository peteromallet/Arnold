"""Deliberation pipeline native behavior tests.

Verify projected stage names match native program phases, and that
resume-after-max-phases produces the same final report as a full run.
"""

from __future__ import annotations

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipelines.deliberation import build_pipeline


def _phase_names(pipeline_name: str, stages: list[str]) -> list[str]:
    return [f"{pipeline_name}__{stage}__pc{i}" for i, stage in enumerate(stages)]


def _normalize_report_paths(report: str, artifact_root: str) -> str:
    return report.replace(artifact_root, "<artifact-root>")


def test_projected_pipeline_stage_names_match_native_program_phases() -> None:
    pipeline = build_pipeline()
    projected_stage_names = list(pipeline.stages)
    phase_names = [phase.name for phase in pipeline.native_program.phases]

    assert projected_stage_names == [
        "question_gen",
        "human_gate",
        "draft_plan",
        "layer_high_panel",
        "layer_high_synth",
        "layer_mid_panel",
        "layer_mid_synth",
        "layer_low_panel",
        "layer_low_synth",
        "final_report",
    ]
    assert phase_names == projected_stage_names


def test_resume_after_max_phases_reaches_same_final_report_as_full_run(tmp_path: Path) -> None:
    pipeline = build_pipeline()
    full_root = tmp_path / "full"
    resumed_root = tmp_path / "resumed"
    idea = "Ship the migration safely."

    full = run_native_pipeline(
        pipeline.native_program,
        artifact_root=full_root,
        initial_state={"idea": idea},
    )
    partial = run_native_pipeline(
        pipeline.native_program,
        artifact_root=resumed_root,
        initial_state={"idea": idea},
        max_phases=4,
    )

    assert (resumed_root / "resume_cursor.json").is_file()

    resumed = run_native_pipeline(
        pipeline.native_program,
        artifact_root=resumed_root,
        resume=True,
    )

    assert full.suspended is False
    assert partial.suspended is True
    assert resumed.suspended is False
    assert full.stages == _phase_names("deliberation", list(pipeline.stages))
    assert resumed.stages == full.stages

    full_report = (full_root / "final_report" / "report" / "v1.md").read_text(encoding="utf-8")
    resumed_report = (resumed_root / "final_report" / "report" / "v1.md").read_text(encoding="utf-8")
    assert _normalize_report_paths(resumed_report, str(resumed_root)) == _normalize_report_paths(
        full_report,
        str(full_root),
    )
