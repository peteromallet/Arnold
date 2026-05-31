"""T12: behavioral oracle for the Evaluand Ledger (M5-eval).

Seeds a corpus via direct emit_evaluand + write_prompt_bytes into a tmp
plan_dir, then asserts semantic-ordering agreement of `better(...)` with the
arithmetic OLD-path majority would perform over its panel votes, and
asserts zero-dispatch around `re_judge(live=False)`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from megaplan.observability.dispatch_counter import assert_zero_dispatch
from megaplan.observability.evaluand import (
    EvaluandRecord,
    better,
    emit_evaluand,
    re_judge,
)
from megaplan.observability.events import EventKind, read_events
from megaplan.observability.prompt_cache import write_prompt_bytes
from megaplan.workers.hermes import PromptCacheMiss


def _make_record(
    *,
    piece_version: str | None,
    judge_version: str,
    rubric_version: str,
    input_set_hash: str,
    score: float,
    model_identity: str = "test/model@1",
    prompt_hash: str | None = "ph-1",
    recorded_at: str | None = None,
) -> EvaluandRecord:
    return {
        "piece_version": piece_version,
        "judge_version": judge_version,
        "rubric_version": rubric_version,
        "input_set_hash": input_set_hash,
        "score": score,
        "provenance": {"params": {"effort": "low"}},
        "taint": "trusted",
        "recorded_at": recorded_at
        or datetime.now(timezone.utc).isoformat(),
        "model_identity": model_identity,
        "prompt_hash_canonical": prompt_hash,
        "prompt_hash_raw": prompt_hash,
    }


def _seed_prompt(plan_dir, prompt_hash: str, *, raw: bytes = b"the-prompt") -> None:
    write_prompt_bytes(
        plan_dir,
        prompt_hash,
        raw=raw,
        canonical=raw,
        model_identity="test/model@1",
        params={"effort": "low"},
    )


def test_better_semantic_ordering_with_unified_dispatch(monkeypatch, tmp_path):
    """(a)+(b): happy path — better() winner equals higher-scored seeded piece."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    rec_a = _make_record(
        piece_version="pieceA", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-1", score=0.9,
    )
    rec_b = _make_record(
        piece_version="pieceB", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-1", score=0.3,
    )
    _seed_prompt(tmp_path, "ph-1")
    emit_evaluand(tmp_path, rec_a)
    emit_evaluand(tmp_path, rec_b)

    out = better(
        tmp_path, "pieceA", "pieceB",
        judge_version="jv1", rubric_version="rv1", input_set_hash="ish-1",
    )
    # Semantic-ordering bridging: pick the piece with the higher seeded score
    # (the same arithmetic the OLD-path majority_vote performs).
    expected = "pieceA" if rec_a["score"] > rec_b["score"] else "pieceB"
    assert out["winner"] == expected


def test_rubric_version_bump_creates_new_joinable_record(tmp_path):
    """(e-ish): rubric-version bump → distinct joinable record."""
    # Two pieces under rv1; a rv2 bump for pieceB only.
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-2", score=0.5,
    ))
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceB", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-2", score=0.3,
    ))
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceB", judge_version="jv1", rubric_version="rv2",
        input_set_hash="ish-2", score=0.9,
    ))
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert len(events) == 3
    # better() at rv1 filter must not pick up the rv2 record (0.9).
    out_rv1 = better(tmp_path, "pieceA", "pieceB",
                     judge_version="jv1", rubric_version="rv1",
                     input_set_hash="ish-2")
    assert out_rv1["scores"]["pieceA"] == 0.5
    assert out_rv1["scores"]["pieceB"] == 0.3
    assert out_rv1["winner"] == "pieceA"


def test_model_identity_swap_is_distinct_joinable_record(tmp_path):
    """(e): model-version-skew boundary survives as distinct record."""
    _seed_prompt(tmp_path, "ph-1")
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-3", score=0.7,
        model_identity="test/modelA@1",
    ))
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv2", rubric_version="rv1",
        input_set_hash="ish-3", score=0.4,
        model_identity="test/modelB@1",
    ))
    # Each is its own joinable record — filter by judge_version keeps them separate.
    # Add a pieceB at jv1 so better() has two pieces to compare.
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceB", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-3", score=0.5,
        model_identity="test/modelA@1",
    ))
    out_a = better(tmp_path, "pieceA", "pieceB",
                   judge_version="jv1", rubric_version="rv1",
                   input_set_hash="ish-3")
    assert out_a["scores"]["pieceA"] == 0.7
    assert out_a["winner"] == "pieceA"


def test_tie_returns_undetermined(tmp_path):
    """(f): tie → undetermined dict with reason='tie'."""
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-4", score=0.5,
    ))
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceB", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-4", score=0.5,
    ))
    out = better(tmp_path, "pieceA", "pieceB",
                 judge_version="jv1", rubric_version="rv1",
                 input_set_hash="ish-4")
    assert out == {"winner": None, "undetermined": True, "reason": "tie"}


def test_multi_record_input_set_hash_latest_by_recorded_at(tmp_path):
    """(g): multi-record input_set_hash → LATEST-by-recorded_at wins for re_judge."""
    _seed_prompt(tmp_path, "ph-1")
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv-old", rubric_version="rv1",
        input_set_hash="ish-5", score=0.2,
        recorded_at="2026-01-01T00:00:00+00:00",
    ))
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv-old", rubric_version="rv1",
        input_set_hash="ish-5", score=0.7,
        recorded_at="2026-05-01T00:00:00+00:00",
    ))

    # re_judge(live=False) wrapped in ENFORCED assert_zero_dispatch and picks
    # the LATEST prior by recorded_at.
    with assert_zero_dispatch():
        re_judge(
            tmp_path, "ish-5",
            new_judge_version="jv-new",
            new_rubric_version="rv2",
            new_model_identity="test/model@2",
            live=False,
        )
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    new_records = [e["payload"]["record"] for e in events
                   if e["payload"]["record"]["judge_version"] == "jv-new"]
    assert len(new_records) == 1
    # Inherits score from LATEST prior (0.7), not 0.2.
    assert new_records[0]["score"] == 0.7


def test_re_judge_live_increments_counter_once_and_records_fresh_io(
    tmp_path, monkeypatch
):
    """(d): re_judge(live=True) recovers cached prompt bytes, increments
    dispatch counter exactly once, records fresh-I/O hash."""
    _seed_prompt(tmp_path, "ph-1", raw=b"original-prompt-bytes")
    emit_evaluand(tmp_path, _make_record(
        piece_version="pieceA", judge_version="jv1", rubric_version="rv1",
        input_set_hash="ish-6", score=0.5,
        prompt_hash="ph-1",
    ))

    from megaplan.observability import dispatch_counter
    from megaplan.workers import hermes as hermes_mod

    # Stub dispatch_judge so live path doesn't try to call a real model.
    # The dispatch_judge function itself increments the counter at the top,
    # so leave that path intact via a thin wrapper.
    real_dispatch = hermes_mod.dispatch_judge

    def fake_dispatch(*, prompt, model, effort=None):
        # Mimic counter increment exactly like dispatch_judge would.
        dispatch_counter._HERMES_DISPATCH_CALLS.count = (
            getattr(dispatch_counter._HERMES_DISPATCH_CALLS, "count", 0) + 1
        )
        return {"text": "ok", "model_actual": model, "usage": {}}

    monkeypatch.setattr(hermes_mod, "dispatch_judge", fake_dispatch)
    # Also patch the import site used by evaluand.re_judge (local import).
    import megaplan.observability.evaluand as _ev_mod
    monkeypatch.setattr(_ev_mod, "re_judge", _ev_mod.re_judge)  # no-op alias

    # Reset counter
    dispatch_counter._HERMES_DISPATCH_CALLS.count = 0

    re_judge(
        tmp_path, "ish-6",
        new_judge_version="jv2",
        new_rubric_version="rv2",
        new_model_identity="test/model@2",
        live=True,
    )

    assert dispatch_counter._HERMES_DISPATCH_CALLS.count == 1
    # Fresh-I/O hash recorded
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    fresh = [e["payload"]["record"] for e in events
             if e["payload"]["record"]["judge_version"] == "jv2"]
    assert len(fresh) == 1
    assert fresh[0]["prompt_hash_raw"] is not None
    assert fresh[0]["prompt_hash_canonical"] is not None
