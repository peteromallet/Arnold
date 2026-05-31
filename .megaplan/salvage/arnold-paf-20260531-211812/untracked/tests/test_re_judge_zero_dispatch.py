"""Tests for re_judge zero-dispatch + live-replay semantics (M5-eval T8)."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan.observability.dispatch_counter import _HERMES_DISPATCH_CALLS
from megaplan.observability.evaluand import EvaluandRecord, emit_evaluand, re_judge
from megaplan.observability.events import EventKind, read_events
from megaplan.observability.prompt_cache import write_prompt_bytes
from megaplan.workers.hermes import PromptCacheMiss


def _reset_counter():
    _HERMES_DISPATCH_CALLS.count = 0


def _mk_record(**over) -> EvaluandRecord:
    base: EvaluandRecord = {
        "piece_version": "pA",
        "judge_version": "jv_old",
        "rubric_version": "rv_old",
        "input_set_hash": "ish_1",
        "score": 0.5,
        "provenance": {"params": {"effort": "low"}},
        "taint": "trusted",
        "recorded_at": "2026-05-30T00:00:00+00:00",
        "model_identity": "mi_old",
        "prompt_hash_canonical": "abc",
        "prompt_hash_raw": "abc_raw",
    }
    base.update(over)
    return base


def _seed_old(plan_dir: Path, **over) -> EvaluandRecord:
    rec = _mk_record(**over)
    emit_evaluand(plan_dir, rec)
    return rec


def test_live_false_zero_dispatch_new_record(tmp_path):
    _reset_counter()
    old = _seed_old(tmp_path)
    before = _HERMES_DISPATCH_CALLS.count
    re_judge(
        tmp_path,
        old["input_set_hash"],
        new_judge_version="jv_new",
        new_rubric_version="rv_new",
        new_model_identity="mi_new",
        live=False,
    )
    assert _HERMES_DISPATCH_CALLS.count == before
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert len(events) == 2
    new_rec = events[-1]["payload"]["record"]
    assert new_rec["judge_version"] == "jv_new"
    assert new_rec["rubric_version"] == "rv_new"
    assert new_rec["model_identity"] == "mi_new"
    assert new_rec["prompt_hash_canonical"] == old["prompt_hash_canonical"]
    # Old record unchanged
    assert events[0]["payload"]["record"] == dict(old)


def test_live_true_increments_counter_once(tmp_path):
    _reset_counter()
    _seed_old(tmp_path, prompt_hash_canonical="ph1", prompt_hash_raw="ph1_raw")
    write_prompt_bytes(
        tmp_path,
        "ph1",
        raw=b"hello",
        canonical=b"hello",
        model_identity="mi_old",
        params={"effort": "low"},
    )
    before = _HERMES_DISPATCH_CALLS.count
    with patch(
        "megaplan.workers.hermes.dispatch_judge",
        wraps=lambda **kw: (
            setattr(_HERMES_DISPATCH_CALLS, "count", _HERMES_DISPATCH_CALLS.count + 1)
            or {"text": "{}", "model_actual": kw["model"], "usage": {}}
        ),
    ):
        re_judge(
            tmp_path,
            "ish_1",
            new_judge_version="jv_new",
            new_rubric_version="rv_new",
            new_model_identity="mi_new",
            live=True,
        )
    assert _HERMES_DISPATCH_CALLS.count == before + 1


def test_live_true_missing_cache_raises(tmp_path):
    _reset_counter()
    _seed_old(tmp_path, prompt_hash_canonical="missing_hash", prompt_hash_raw=None)
    with pytest.raises(PromptCacheMiss):
        re_judge(
            tmp_path,
            "ish_1",
            new_judge_version="jv_new",
            new_rubric_version="rv_new",
            new_model_identity="mi_new",
            live=True,
        )


def test_multi_record_picks_latest_by_recorded_at(tmp_path):
    _reset_counter()
    _seed_old(tmp_path, recorded_at="2026-05-29T00:00:00+00:00", score=0.1)
    _seed_old(tmp_path, recorded_at="2026-05-30T00:00:00+00:00", score=0.9)
    re_judge(
        tmp_path,
        "ish_1",
        new_judge_version="jv_new",
        new_rubric_version="rv_new",
        new_model_identity="mi_new",
        live=False,
    )
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    new_rec = events[-1]["payload"]["record"]
    assert new_rec["score"] == 0.9


def test_old_record_byte_unchanged_after_re_judge(tmp_path):
    _reset_counter()
    old = _seed_old(tmp_path)
    events_before = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    re_judge(
        tmp_path,
        old["input_set_hash"],
        new_judge_version="jv_new",
        new_rubric_version="rv_new",
        new_model_identity="mi_new",
        live=False,
    )
    events_after = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert events_after[0]["payload"]["record"] == events_before[0]["payload"]["record"]
