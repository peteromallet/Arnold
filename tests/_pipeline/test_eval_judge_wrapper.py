from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.eval_judge_wrapper import (
    EvaluandClarityJudge,
    M5_WRAPPER_JUDGE_VERSION,
    M5_WRAPPER_PIECE_VERSION,
    M5_WRAPPER_RUBRIC_VERSION,
)
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.types import Edge, Pipeline, Port, Stage, StepContext, StepResult
from arnold.pipelines.megaplan.observability import read_evaluand_events
from arnold.pipelines.megaplan.observability.evaluand import EvaluandRecord, better, write_evaluand_event
from arnold.pipelines.megaplan.observability.evaluand import _reset_for_tests
from arnold.pipelines.megaplan.observability.events import EventKind, read_events


@pytest.fixture(autouse=True)
def _clean_evaluand_ledger():
    _reset_for_tests()
    yield
    _reset_for_tests()


def _ctx(tmp_path: Path) -> StepContext:
    candidate = tmp_path / "candidate.md"
    candidate.write_text(
        "The pipeline executor walks stages and dispatches steps in order. "
        "Each step writes artifacts under the plan directory it was handed. "
        "Judges score the fixture document along independent rubric axes.",
        encoding="utf-8",
    )
    return StepContext(
        plan_dir=tmp_path / "plan",
        state={"run_id": "run-wrapper-1"},
        profile=None,
        mode="test",
        inputs={"candidate": candidate},
        budget=None,
    )


@dataclass
class _CandidateProducer:
    name: str = "candidate"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple = field(
        default_factory=lambda: (Port(name="candidate", content_type="text/markdown"),)
    )
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        candidate = Path(ctx.plan_dir) / self.name / "v1.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(
            "The plan is explicit, step-bounded, and executable without hidden assumptions.",
            encoding="utf-8",
        )
        return StepResult(outputs={"candidate": candidate}, next="to_judge")


def test_eval_judge_wrapper_flag_off_preserves_pipeline_verdict(monkeypatch, tmp_path):
    monkeypatch.delenv("UNIFIED_EVALUAND", raising=False)
    ctx = _ctx(tmp_path)
    ctx.plan_dir.mkdir()
    legacy_ctx = StepContext(
        plan_dir=ctx.plan_dir,
        state=ctx.state,
        profile=ctx.profile,
        mode=ctx.mode,
        inputs={"doc": ctx.inputs["candidate"]},
        budget=ctx.budget,
    )
    legacy_result = EvaluandClarityJudge()._legacy_judge.run(legacy_ctx)

    result = EvaluandClarityJudge().run(ctx)

    assert result == legacy_result
    assert result.verdict == legacy_result.verdict
    assert result.verdict is not None
    assert isinstance(result.verdict.score, float)
    assert not (ctx.plan_dir / "events.ndjson").exists()


def test_eval_judge_wrapper_flag_on_writes_event_and_artifact(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIFIED_EVALUAND", "1")
    ctx = _ctx(tmp_path)
    ctx.plan_dir.mkdir()

    result = EvaluandClarityJudge().run(ctx)

    assert result.verdict is not None
    assert set(result.outputs) == {"verdict", "evaluand"}
    artifact = result.outputs["evaluand"]
    assert artifact.exists()

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-wrapper-1"
    assert payload["piece_version"] == M5_WRAPPER_PIECE_VERSION
    assert payload["judge_version"] == M5_WRAPPER_JUDGE_VERSION
    assert payload["rubric_version"] == M5_WRAPPER_RUBRIC_VERSION
    assert payload["score"] == pytest.approx(result.verdict.score)

    events = list(read_events(ctx.plan_dir, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 1
    event_payload = events[0]["payload"]
    assert event_payload["run_id"] == "run-wrapper-1"
    assert event_payload["attribution_key"] == payload["attribution_key"]

    folded = read_evaluand_events(ctx.plan_dir)
    assert tuple(payload["attribution_key"]) in folded
    assert folded[tuple(payload["attribution_key"])].score == pytest.approx(
        result.verdict.score
    )


def test_eval_judge_wrapper_dual_green_smoke_through_pipeline_and_better(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UNIFIED_EVALUAND", "1")
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    judge = EvaluandClarityJudge()
    pipeline = Pipeline(
        stages={
            "candidate": Stage(
                name="candidate",
                step=_CandidateProducer(),
                edges=(Edge("to_judge", "judge"),),
            ),
            "judge": Stage(name="judge", step=judge, edges=(Edge("done", "halt"),)),
        },
        entry="candidate",
        binding_map={("judge", "candidate"): ("candidate", "candidate")},
    )
    ctx = StepContext(
        plan_dir=tmp_path,
        state={"run_id": "run-wrapper-smoke"},
        profile=None,
        mode="plan",
        inputs={},
        budget=None,
    )

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert result["final_stage"] == "judge"
    folded = read_evaluand_events(tmp_path)
    assert len(folded) == 1
    wrapper_key, wrapper_record = next(iter(folded.items()))
    assert wrapper_key[0] == M5_WRAPPER_PIECE_VERSION

    write_evaluand_event(
        "run-competitor",
        EvaluandRecord(
            judge_version=M5_WRAPPER_JUDGE_VERSION,
            rubric_version=M5_WRAPPER_RUBRIC_VERSION,
            input_set_hash=wrapper_record.input_set_hash,
            score=wrapper_record.score - 0.25,
            piece_version="piece:throwaway-planning-competitor@sha256:smoke",
            provenance={"oracle": "dual-green-smoke"},
            taint=("smoke",),
        ),
        plan_dir=tmp_path,
    )

    comparison = better(
        M5_WRAPPER_PIECE_VERSION,
        "piece:throwaway-planning-competitor@sha256:smoke",
        plan_dir=tmp_path,
        judge_version=M5_WRAPPER_JUDGE_VERSION,
        rubric_version=M5_WRAPPER_RUBRIC_VERSION,
        input_set_hash=wrapper_record.input_set_hash,
    )

    assert comparison.status == "winner"
    assert comparison.winner_piece_version == M5_WRAPPER_PIECE_VERSION
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 2
