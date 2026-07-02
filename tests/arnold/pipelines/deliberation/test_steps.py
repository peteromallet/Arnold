from __future__ import annotations

import json
from pathlib import Path

from arnold.pipeline.types import StepContext
from arnold.runtime.event_journal import NdjsonEventJournal
from arnold.pipelines.deliberation.steps import (
    build_draft_plan_stage,
    build_human_gate_stage,
    load_questions,
    reconstruct_plan_from_journal,
)


def test_load_questions_reads_latest_versioned_artifact(tmp_path: Path) -> None:
    questions_dir = tmp_path / "question_gen" / "questions"
    questions_dir.mkdir(parents=True)
    (questions_dir / "v1.json").write_text('{"questions":[{"q":"old"}]}', encoding="utf-8")
    (questions_dir / "v2.json").write_text('{"questions":[{"q":"new"}]}', encoding="utf-8")

    loaded = load_questions(tmp_path)

    assert loaded == {"questions": [{"q": "new"}]}


def test_build_human_gate_stage_uses_answers_collected_resume_label(tmp_path: Path) -> None:
    stage = build_human_gate_stage()
    result = stage.step.run(
        StepContext(
            artifact_root=str(tmp_path),
            state={},
            inputs={},
            mode="native",
        )
    )

    assert stage.edges[0].label == "answers_collected"
    assert stage.edges[0].target == "draft_plan"
    assert result.next == "halt"
    checkpoint = json.loads((tmp_path / "awaiting_user.json").read_text(encoding="utf-8"))
    assert checkpoint["choices"] == ["answers_collected"]
    assert checkpoint["stage"] == "human_gate"


def test_draft_plan_stage_guard_reads_answers_file_content(tmp_path: Path) -> None:
    answers_path = tmp_path / "answers.json"
    questions_path = tmp_path / "questions.json"
    answers_path.write_text('{"answers":[{"q":"Scope?","a":"Tight"}]}', encoding="utf-8")
    questions_path.write_text('{"questions":[{"q":"Scope?"}]}', encoding="utf-8")
    calls: list[dict[str, str]] = []

    def worker(**kwargs: object) -> str:
        calls.append(kwargs["inputs"])  # type: ignore[arg-type]
        return '{"sections":[{"title":"Plan","content":"Do it"}]}'

    stage = build_draft_plan_stage(prompt_source=None, worker=worker)
    stage.step.run(
        StepContext(
            artifact_root=str(tmp_path),
            state={},
            inputs={
                "questions": str(questions_path),
                "answers": str(answers_path),
            },
            mode="native",
        )
    )

    assert calls == [
        {
            "questions": questions_path.read_text(encoding="utf-8"),
            "answers": answers_path.read_text(encoding="utf-8"),
        }
    ]


def test_reconstruct_plan_from_journal_returns_latest_state_snapshot(tmp_path: Path) -> None:
    journal = NdjsonEventJournal(tmp_path)
    journal.emit("state", payload={"state": {"plan_version": 1}})
    journal.emit("state", payload={"state": {"plan_version": 2, "summary": "latest"}})

    assert reconstruct_plan_from_journal(tmp_path) == {
        "plan_version": 2,
        "summary": "latest",
    }
