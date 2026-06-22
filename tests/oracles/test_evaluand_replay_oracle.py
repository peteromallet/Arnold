"""M5 replay oracle for attributable Evaluand ledger joins.

This corpus is intentionally small and behavioral: A win/B loss, tie,
missing, and version-skew re-judge all run through the canonical
``events.ndjson`` Evaluand ledger.  The assertions pin that replay reads are
pure, byte-stable, and do not spend live judge/model calls.

After M4 Step 5 deletion the legacy ``_pipeline.eval_judge_wrapper``,
``_pipeline.executor``, and ``_pipeline.types`` modules are gone.
Tests that exercised the wrapper-written planning smoke path through
those deleted surfaces have been converted to negative-absence probes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.observability import (
    BetterResult,
    EvaluandRecord,
    RecordedModelIO,
    ReJudgeOutcome,
    re_judge,
)
from arnold_pipelines.megaplan.observability.evaluand import (
    _reset_for_tests,
    better,
    read_evaluand_events,
    write_evaluand_event,
)
from arnold_pipelines.megaplan.observability.events import EventKind, read_events

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


def test_wrapper_written_planning_smoke_modules_absent() -> None:
    """Legacy ``_pipeline.eval_judge_wrapper`` and ``_pipeline.executor``
    are physically deleted in M4 Step 5.

    The wrapper-written planning smoke test that previously exercised
    these modules through ``EvaluandClarityJudge``, ``run_pipeline``,
    and the legacy ``Stage``/``Edge``/``Pipeline`` types is replaced
    by this negative-absence probe.
    """
    import importlib

    for mod_name in (
        "arnold_pipelines.megaplan._pipeline.eval_judge_wrapper",
        "arnold_pipelines.megaplan._pipeline.executor",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod_name)
