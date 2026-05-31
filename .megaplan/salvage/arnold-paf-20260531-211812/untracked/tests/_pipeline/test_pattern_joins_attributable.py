"""T6: attributable joins + select_join (M5-eval)."""

from __future__ import annotations

import os

import pytest

from megaplan._pipeline.pattern_joins import (
    majority_vote,
    majority_vote_attributable,
    weighted_vote,
)
from megaplan._pipeline.patterns import select_join
from megaplan._pipeline.types import (
    PipelineVerdict,
    StepContext,
    StepResult,
)
from megaplan.observability.events import EventKind, read_events


def _judge_result(rec: str, evaluand: dict) -> StepResult:
    return StepResult(
        verdict=PipelineVerdict(
            score=evaluand.get("score", 0.0),
            recommendation=rec,  # type: ignore[arg-type]
            payload={"evaluand": evaluand},
        )
    )


def _ev(piece: str, judge_version: str, score: float) -> dict:
    return {
        "piece_version": piece,
        "judge_version": judge_version,
        "rubric_version": "r1",
        "input_set_hash": "ish-1",
        "score": score,
        "provenance": {"params": {}},
        "taint": "trusted",
        "recorded_at": "2026-05-30T00:00:00+00:00",
        "model_identity": "test/model@1",
        "prompt_hash_canonical": None,
        "prompt_hash_raw": None,
    }


def test_select_join_flag_off_returns_legacy_behavior(monkeypatch, tmp_path):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    j_off = select_join(kind="majority")
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    results = [
        _judge_result("proceed", _ev("pA", "jv-a", 1.0)),
        _judge_result("proceed", _ev("pA", "jv-b", 1.0)),
        _judge_result("iterate", _ev("pB", "jv-c", 0.0)),
    ]
    out = j_off(results, ctx)
    # legacy attaches reduce_result, NOT evaluand
    assert "reduce_result" in (out.verdict.payload or {})
    assert "evaluand" not in (out.verdict.payload or {})
    # legacy never writes EVALUAND_JUDGMENT events
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert events == []


def test_select_join_flag_on_returns_attributable(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    j_on = select_join(kind="majority")
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    children_versions = ["jv-1", "jv-2", "jv-3"]
    results = [
        _judge_result("proceed", _ev("pA", "jv-1", 1.0)),
        _judge_result("proceed", _ev("pA", "jv-2", 1.0)),
        _judge_result("proceed", _ev("pA", "jv-3", 1.0)),
    ]
    out = j_on(results, ctx)

    # parent attached to verdict.payload
    assert "evaluand" in (out.verdict.payload or {})
    parent = out.verdict.payload["evaluand"]
    # provenance references ALL 3 child judge_versions
    assert set(parent["provenance"]["children"]) == set(children_versions)

    # parent reachable via read_events
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert len(events) == 1
    journaled = events[0]["payload"]["record"]
    assert set(journaled["provenance"]["children"]) == set(children_versions)

    # 4-bucket: unanimous proceed → 'proceed' recommendation
    assert out.verdict.recommendation == "proceed"
    # result.next is the winning child's label (here: 'proceed' as the
    # majority label that all three children voted)
    assert out.next == "proceed"


def test_attributable_tie_yields_tiebreaker(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    j_on = majority_vote_attributable()
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    # 1 vs 1 — tie
    results = [
        _judge_result("proceed", _ev("pA", "jv-a", 0.6)),
        _judge_result("iterate", _ev("pB", "jv-b", 0.4)),
    ]
    out = j_on(results, ctx)
    assert out.verdict.recommendation == "tiebreaker"
    # tie → parent EvaluandRecord emitted with undetermined-style winner
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert len(events) == 1


def test_returned_stepresult_sets_recommendation_and_next(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    j_on = majority_vote_attributable()
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    results = [
        _judge_result("proceed", _ev("pA", "jv-a", 1.0)),
        _judge_result("proceed", _ev("pA", "jv-b", 1.0)),
        _judge_result("iterate", _ev("pB", "jv-c", 0.0)),
    ]
    out = j_on(results, ctx)
    assert out.verdict.recommendation is not None
    assert out.next is not None and out.next != "halt"
