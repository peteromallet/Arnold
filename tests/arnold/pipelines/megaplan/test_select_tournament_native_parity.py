"""Native runtime coverage for the ``select-tournament`` pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline import ParallelStage, Pipeline, run_pipeline
from arnold.pipeline.native import NativeProgram, run_native_pipeline
from arnold.runtime.envelope import RuntimeEnvelope

from arnold.pipelines.megaplan.pipelines.select_tournament import build_pipeline


def _stage_names(result: Any) -> tuple[str, ...]:
    names: list[str] = []
    for stage_id in result.stages:
        parts = stage_id.split("__")
        if len(parts) >= 2:
            names.append(parts[-2])
    return tuple(names)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_select_tournament_attaches_candidate_specific_native_program() -> None:
    pipeline = build_pipeline(candidates=("red", "green", "blue"))

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "select-tournament"
    assert tuple(pipeline.resource_bundles) == ()

    score_stage = pipeline.stages["score_candidates"]
    assert isinstance(score_stage, ParallelStage)
    assert score_stage.max_workers == 3
    assert [step.candidate for step in score_stage.steps] == ["red", "green", "blue"]

    parallel_block = pipeline.native_program.parallel_blocks[0]
    assert parallel_block.name == "score_candidates"
    assert parallel_block.branches == (
        "candidate_score_0",
        "candidate_score_1",
        "candidate_score_2",
    )
    assert [func.__closure__[0].cell_contents.candidate for func in parallel_block.branch_funcs] == [
        "red",
        "green",
        "blue",
    ]


def test_select_tournament_native_default_candidates_rank_and_emit_winner(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline()
    assert pipeline.native_program is not None

    result = run_native_pipeline(pipeline.native_program, artifact_root=tmp_path)

    assert result.suspended is False
    assert _stage_names(result) == (
        "candidate_score_0",
        "candidate_score_1",
        "candidate_score_2",
        "candidate_score_3",
        "pairwise_bracket",
        "winner",
    )
    assert result.state["select_tournament_winner"] == "delta"

    winner = _read_json(tmp_path / "winner" / "v1.json")
    assert winner == {
        "score": 1.0,
        "seed": 3,
        "source_port": "bracket_result",
        "winner": "delta",
    }
    scores = _read_json(tmp_path / "score_candidates" / "v1.json")
    assert [candidate["candidate"] for candidate in scores["candidates"]] == [
        "alpha",
        "beta",
        "gamma",
        "delta",
    ]


def test_select_tournament_native_non_default_candidates_rank_and_emit_winner(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline(candidates=("small", "medium", "large"))
    assert pipeline.native_program is not None

    result = run_native_pipeline(pipeline.native_program, artifact_root=tmp_path)

    assert result.state["select_tournament_winner"] == "large"
    assert _stage_names(result) == (
        "candidate_score_0",
        "candidate_score_1",
        "candidate_score_2",
        "pairwise_bracket",
        "winner",
    )
    scores = _read_json(tmp_path / "score_candidates" / "v1.json")
    assert [candidate["candidate"] for candidate in scores["candidates"]] == [
        "small",
        "medium",
        "large",
    ]
    winner = _read_json(tmp_path / "winner" / "v1.json")
    assert winner["winner"] == "large"
    assert winner["seed"] == 2


def test_select_tournament_executor_uses_native_program_by_default(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline(candidates=("red", "green", "blue"))
    envelope = RuntimeEnvelope(artifact_root=str(tmp_path))

    result = run_pipeline(pipeline, initial_state={}, envelope=envelope)

    assert result.state["select_tournament_winner"] == "blue"
    assert (tmp_path / "winner" / "v1.json").exists()
    assert (tmp_path / "resume_cursor.json").exists() is False


def test_select_tournament_native_resume_after_score_fanout(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline(candidates=("red", "green", "blue"))
    assert pipeline.native_program is not None

    first = run_native_pipeline(
        pipeline.native_program,
        artifact_root=tmp_path,
        max_phases=3,
    )

    assert first.suspended is True
    assert _stage_names(first) == (
        "candidate_score_0",
        "candidate_score_1",
        "candidate_score_2",
    )
    cursor_path = tmp_path / "resume_cursor.json"
    assert cursor_path.exists()
    cursor = _read_json(cursor_path)
    assert cursor["native"]["pc"] == 4
    assert cursor["reentry_stage"] == "select-tournament__pairwise_bracket__pc4"

    second = run_native_pipeline(
        pipeline.native_program,
        artifact_root=tmp_path,
        resume=True,
    )

    assert second.suspended is False
    # The runtime carries already-completed stages across resume; only the
    # newly executed stages after the suspended fanout matter here.
    new_stages = second.stages[len(first.stages) :]
    assert _stage_names(type("R", (), {"stages": new_stages})()) == ("pairwise_bracket", "winner")
    assert second.state["select_tournament_winner"] == "blue"
    winner = _read_json(tmp_path / "winner" / "v1.json")
    assert winner["winner"] == "blue"
