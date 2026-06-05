"""T7 — pattern_joins typed-port flag-ON behavior."""
from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipelines.megaplan._pipeline.types import (
    PipelineVerdict,
    ReduceResult,
    StepContext,
    StepResult,
)


def _ctx(tmp_path: Path) -> StepContext:
    return StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")


def _vote(rec, reviewer_id=None):
    payload = {"reviewer_id": reviewer_id} if reviewer_id is not None else {}
    return StepResult(verdict=PipelineVerdict(score=1.0, recommendation=rec, payload=payload))


def test_majority_vote_flag_off_byte_identical(monkeypatch, tmp_path):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    join = majority_vote()
    results = [_vote("iterate"), _vote("iterate"), _vote("proceed")]
    out = join(results, _ctx(tmp_path))
    assert out.verdict is not None
    assert out.verdict.recommendation == "iterate"
    assert out.next == "iterate"
    assert "reduce_result" not in dict(out.verdict.payload or {})


def test_majority_vote_flag_on_emits_reduce_result(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    join = majority_vote()
    results = [_vote("iterate"), _vote("iterate"), _vote("proceed")]
    out = join(results, _ctx(tmp_path))
    assert out.verdict is not None
    assert out.verdict.recommendation is None
    rr = out.verdict.payload["reduce_result"]
    assert isinstance(rr, ReduceResult)
    assert rr.label == "iterate"
    assert rr.tally == {"iterate": 2, "proceed": 1}
    assert out.next == "iterate"


def test_majority_vote_tie_flag_on(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    join = majority_vote()
    out = join([_vote("iterate"), _vote("proceed")], _ctx(tmp_path))
    rr = out.verdict.payload["reduce_result"]
    assert rr.label is None
    assert out.next == "tiebreaker"


def test_weighted_vote_flag_off_byte_identical(monkeypatch, tmp_path):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    join = weighted_vote({"a": 2.0, "b": 1.0})
    out = join(
        [_vote("iterate", "a"), _vote("proceed", "b")], _ctx(tmp_path)
    )
    assert out.verdict.recommendation == "iterate"
    assert out.next == "iterate"


def test_weighted_vote_flag_on(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    join = weighted_vote({"a": 2.0, "b": 1.0})
    out = join(
        [_vote("iterate", "a"), _vote("proceed", "b")], _ctx(tmp_path)
    )
    assert out.verdict.recommendation is None
    rr = out.verdict.payload["reduce_result"]
    assert isinstance(rr, ReduceResult)
    assert rr.label == "iterate"
    assert out.next == "iterate"
