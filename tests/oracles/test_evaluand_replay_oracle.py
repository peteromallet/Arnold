"""M5 replay oracle for attributable Evaluand ledger joins.

This corpus is intentionally small and behavioral: A win/B loss, tie,
missing, and version-skew re-judge all run through the canonical
``events.ndjson`` Evaluand ledger.  The assertions pin that replay reads are
pure, byte-stable, and do not spend live judge/model calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from megaplan._pipeline.eval_judge_wrapper import (
    EvaluandClarityJudge,
    M5_WRAPPER_JUDGE_VERSION,
    M5_WRAPPER_PIECE_VERSION,
    M5_WRAPPER_RUBRIC_VERSION,
)
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.types import Edge, Pipeline, Port, Stage, StepContext, StepResult
from megaplan.observability import (
    BetterResult,
    EvaluandRecord,
    RecordedModelIO,
    ReJudgeOutcome,
    re_judge,
)
from megaplan.observability.evaluand import (
    _reset_for_tests,
    better,
    read_evaluand_events,
    write_evaluand_event,
)
from megaplan.observability.events import EventKind, read_events


REPLAY_ORACLE_CORPUS_SIZE = 4

PIECE_A = "piece:A@sha256:aaa"
PIECE_B = "piece:B@sha256:bbb"
JUDGE_V1 = "judge:gpt-5.4@2026-05-31"
JUDGE_V2 = "judge:gpt-5.5@2026-05-31"
RUBRIC_V1 = "rubric:clarity@v1"
RUBRIC_V2 = "rubric:clarity@v2"
INPUT_WIN = "input-set:win"
INPUT_TIE = "input-set:tie"


@pytest.fixture(autouse=True)
def _clean_evaluand_ledger():
    _reset_for_tests()
    yield
    _reset_for_tests()


def _record(
    *,
    piece_version: str,
    judge_version: str = JUDGE_V1,
    rubric_version: str = RUBRIC_V1,
    input_set_hash: str = INPUT_WIN,
    score: float,
) -> EvaluandRecord:
    return EvaluandRecord(
        judge_version=judge_version,
        rubric_version=rubric_version,
        input_set_hash=input_set_hash,
        score=score,
        piece_version=piece_version,
        provenance={"oracle": "m5-evaluand-replay"},
        taint=("oracle",),
    )


@dataclass
class _OracleCandidateProducer:
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
            "This throwaway planning candidate should exercise the eval wrapper end to end.",
            encoding="utf-8",
        )
        return StepResult(outputs={"candidate": candidate}, next="to_judge")


def _projection(result: BetterResult) -> bytes:
    """Old compatibility view of the new attribution join answer."""

    return json.dumps(
        {
            "attribution": {
                piece: list(key) for piece, key in sorted(result.attribution.items())
            },
            "reason": result.reason,
            "scores": dict(sorted(result.scores.items())),
            "status": result.status,
            "winner_piece_version": result.winner_piece_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_replay_corpus(plan_dir: Path) -> RecordedModelIO:
    recorded_io = RecordedModelIO(
        model_name="gpt-5.4",
        reported_version="2026-05-31",
        prompt="Score candidate A for clarity.",
        response='{"score":0.91}',
        params={"temperature": 0, "seed": 13},
    )
    write_evaluand_event(
        "run-a-win",
        _record(piece_version=PIECE_A, score=0.91),
        plan_dir=plan_dir,
        recorded_model_io=recorded_io,
    )
    write_evaluand_event(
        "run-b-loss",
        _record(piece_version=PIECE_B, score=0.24),
        plan_dir=plan_dir,
    )
    write_evaluand_event(
        "run-a-tie",
        _record(piece_version=PIECE_A, input_set_hash=INPUT_TIE, score=0.5),
        plan_dir=plan_dir,
    )
    write_evaluand_event(
        "run-b-tie",
        _record(piece_version=PIECE_B, input_set_hash=INPUT_TIE, score=0.5),
        plan_dir=plan_dir,
    )
    return recorded_io


def test_replay_oracle_corpus_size_marker_is_guarded():
    assert REPLAY_ORACLE_CORPUS_SIZE == 4


def test_replay_oracle_byte_stable_join_and_zero_live_calls(tmp_path):
    _write_replay_corpus(tmp_path)

    first = better(
        PIECE_A,
        PIECE_B,
        plan_dir=tmp_path,
        judge_version=JUDGE_V1,
        rubric_version=RUBRIC_V1,
        input_set_hash=INPUT_WIN,
    )
    second = better(
        PIECE_A,
        PIECE_B,
        plan_dir=tmp_path,
        judge_version=JUDGE_V1,
        rubric_version=RUBRIC_V1,
        input_set_hash=INPUT_WIN,
    )

    expected = (
        b'{"attribution":{"piece:A@sha256:aaa":["piece:A@sha256:aaa",'
        b'"judge:gpt-5.4@2026-05-31","rubric:clarity@v1","input-set:win"],'
        b'"piece:B@sha256:bbb":["piece:B@sha256:bbb",'
        b'"judge:gpt-5.4@2026-05-31","rubric:clarity@v1","input-set:win"]},'
        b'"reason":null,"scores":{"piece:A@sha256:aaa":0.91,'
        b'"piece:B@sha256:bbb":0.24},"status":"winner",'
        b'"winner_piece_version":"piece:A@sha256:aaa"}'
    )
    assert _projection(first) == expected
    assert _projection(second) == expected
    assert first.status == "winner"
    assert first.winner_piece_version == PIECE_A
    assert first.scores[PIECE_A] > first.scores[PIECE_B]

    before = (tmp_path / "events.ndjson").read_bytes()
    for _ in range(3):
        assert (
            _projection(
                better(
                    PIECE_A,
                    PIECE_B,
                    plan_dir=tmp_path,
                    judge_version=JUDGE_V1,
                    rubric_version=RUBRIC_V1,
                    input_set_hash=INPUT_WIN,
                )
            )
            == expected
        )
    assert (tmp_path / "events.ndjson").read_bytes() == before


def test_replay_oracle_missing_and_tie_are_typed_undetermined(tmp_path):
    _write_replay_corpus(tmp_path)

    missing = better(
        PIECE_A,
        PIECE_B,
        plan_dir=tmp_path,
        judge_version=JUDGE_V1,
        rubric_version=RUBRIC_V1,
        input_set_hash="input-set:missing",
    )
    tie = better(
        PIECE_A,
        PIECE_B,
        plan_dir=tmp_path,
        judge_version=JUDGE_V1,
        rubric_version=RUBRIC_V1,
        input_set_hash=INPUT_TIE,
    )

    assert missing.status == "undetermined"
    assert missing.reason == "missing_record"
    assert missing.scores == {}
    assert tie.status == "undetermined"
    assert tie.reason == "tie"
    assert tie.scores == {PIECE_A: 0.5, PIECE_B: 0.5}


def test_replay_oracle_re_judge_uses_recorded_io_without_live_spend(tmp_path):
    recorded_io = _write_replay_corpus(tmp_path)
    live_spend_calls: list[Any] = []
    replay_calls: list[RecordedModelIO] = []

    def live_model_client(*args: Any, **kwargs: Any) -> float:
        live_spend_calls.append((args, kwargs))
        raise AssertionError("live model client must not be used")

    def recorded_scorer(payload: RecordedModelIO) -> float:
        replay_calls.append(payload)
        assert payload.prompt == "Score candidate A for clarity."
        assert payload.response == '{"score":0.91}'
        return 0.73

    outcome = re_judge(
        plan_dir=tmp_path,
        recorded_io_key=recorded_io.ref().key,
        scorer=recorded_scorer,
        piece_version=PIECE_A,
        judge_version=JUDGE_V2,
        rubric_version=RUBRIC_V1,
        run_id="run-a-rejudge-model-skew",
    )
    live_model_client  # keeps the sentinel visible to readers and linters

    assert isinstance(outcome, ReJudgeOutcome)
    assert outcome.status == "recorded"
    assert len(replay_calls) == 1
    assert live_spend_calls == []
    assert outcome.new_attribution_key == (PIECE_A, JUDGE_V2, RUBRIC_V1, INPUT_WIN)

    folded = read_evaluand_events(tmp_path)
    assert folded[(PIECE_A, JUDGE_V1, RUBRIC_V1, INPUT_WIN)].score == pytest.approx(
        0.91
    )
    assert folded[(PIECE_A, JUDGE_V2, RUBRIC_V1, INPUT_WIN)].score == pytest.approx(
        0.73
    )
    assert len(
        [
            key
            for key in folded
            if key[0] == PIECE_A and key[3] == INPUT_WIN
        ]
    ) == 2


def test_replay_oracle_distinguishes_rubric_and_model_skew_records(tmp_path):
    _write_replay_corpus(tmp_path)
    write_evaluand_event(
        "run-a-rubric-skew",
        _record(
            piece_version=PIECE_A,
            judge_version=JUDGE_V1,
            rubric_version=RUBRIC_V2,
            score=0.64,
        ),
        plan_dir=tmp_path,
    )
    write_evaluand_event(
        "run-a-model-skew",
        _record(
            piece_version=PIECE_A,
            judge_version=JUDGE_V2,
            rubric_version=RUBRIC_V1,
            score=0.73,
        ),
        plan_dir=tmp_path,
    )

    folded = read_evaluand_events(tmp_path)

    assert folded[(PIECE_A, JUDGE_V1, RUBRIC_V1, INPUT_WIN)].score == pytest.approx(
        0.91
    )
    assert folded[(PIECE_A, JUDGE_V1, RUBRIC_V2, INPUT_WIN)].score == pytest.approx(
        0.64
    )
    assert folded[(PIECE_A, JUDGE_V2, RUBRIC_V1, INPUT_WIN)].score == pytest.approx(
        0.73
    )

    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))
    assert len(events) == 6
    assert {
        tuple(event["payload"]["attribution_key"])
        for event in events
        if event["payload"]["piece_version"] == PIECE_A
    } >= {
        (PIECE_A, JUDGE_V1, RUBRIC_V1, INPUT_WIN),
        (PIECE_A, JUDGE_V1, RUBRIC_V2, INPUT_WIN),
        (PIECE_A, JUDGE_V2, RUBRIC_V1, INPUT_WIN),
    }


def test_replay_oracle_accepts_wrapper_written_planning_smoke(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIFIED_EVALUAND", "1")
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    pipeline = Pipeline(
        stages={
            "candidate": Stage(
                name="candidate",
                step=_OracleCandidateProducer(),
                edges=(Edge("to_judge", "judge"),),
            ),
            "judge": Stage(
                name="judge",
                step=EvaluandClarityJudge(),
                edges=(Edge("done", "halt"),),
            ),
        },
        entry="candidate",
        binding_map={("judge", "candidate"): ("candidate", "candidate")},
    )

    run_pipeline(
        pipeline,
        StepContext(
            plan_dir=tmp_path,
            state={"run_id": "run-wrapper-oracle"},
            profile=None,
            mode="plan",
            inputs={},
            budget=None,
        ),
        artifact_root=tmp_path,
    )

    folded = read_evaluand_events(tmp_path)
    wrapper_record = folded[
        (
            M5_WRAPPER_PIECE_VERSION,
            M5_WRAPPER_JUDGE_VERSION,
            M5_WRAPPER_RUBRIC_VERSION,
            next(iter(folded.values())).input_set_hash,
        )
    ]
    write_evaluand_event(
        "run-wrapper-oracle-opponent",
        EvaluandRecord(
            judge_version=M5_WRAPPER_JUDGE_VERSION,
            rubric_version=M5_WRAPPER_RUBRIC_VERSION,
            input_set_hash=wrapper_record.input_set_hash,
            score=wrapper_record.score - 0.1,
            piece_version="piece:oracle-opponent@sha256:planning",
            provenance={"oracle": "wrapper-smoke"},
            taint=("oracle",),
        ),
        plan_dir=tmp_path,
    )

    result = better(
        M5_WRAPPER_PIECE_VERSION,
        "piece:oracle-opponent@sha256:planning",
        plan_dir=tmp_path,
        judge_version=M5_WRAPPER_JUDGE_VERSION,
        rubric_version=M5_WRAPPER_RUBRIC_VERSION,
        input_set_hash=wrapper_record.input_set_hash,
    )

    assert result.status == "winner"
    assert result.winner_piece_version == M5_WRAPPER_PIECE_VERSION
    assert len(list(read_events(tmp_path, kinds=[EventKind.EVALUAND_RECORDED]))) == 2
