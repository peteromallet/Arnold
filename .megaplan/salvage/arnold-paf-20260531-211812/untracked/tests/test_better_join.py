"""Tests for megaplan.observability.evaluand.better (T7)."""

from unittest.mock import patch
from megaplan.observability.evaluand import emit_evaluand, better


def _emit(plan_dir, piece_version, judge_version, rubric_version, input_set_hash, score, model_identity="model-a"):
    emit_evaluand(plan_dir, {
        "piece_version": piece_version,
        "judge_version": judge_version,
        "rubric_version": rubric_version,
        "input_set_hash": input_set_hash,
        "score": score,
        "provenance": {"params": {}},
        "taint": "trusted",
        "recorded_at": "2026-01-01T00:00:00Z",
        "model_identity": model_identity,
        "prompt_hash_canonical": None,
        "prompt_hash_raw": None,
    })


def test_two_judgments_winner_and_attribution(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _emit(plan_dir, "v1", "j1", "r1", "h1", score=0.9)
    _emit(plan_dir, "v2", "j1", "r1", "h1", score=0.7)
    result = better(plan_dir, "v1", "v2", judge_version="j1", rubric_version="r1", input_set_hash="h1")
    assert result["winner"] == "v1"
    assert result["scores"]["v1"] == 0.9
    assert result["scores"]["v2"] == 0.7
    assert len(result["attribution"]) == 2


def test_rubric_version_bump_creates_new_record(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _emit(plan_dir, "v1", "j1", "r1", "h1", score=0.8)
    _emit(plan_dir, "v2", "j1", "r1", "h1", score=0.6)
    _emit(plan_dir, "v1", "j1", "r2", "h1", score=0.5)
    _emit(plan_dir, "v2", "j1", "r2", "h1", score=0.9)
    old = better(plan_dir, "v1", "v2", judge_version="j1", rubric_version="r1", input_set_hash="h1")
    new = better(plan_dir, "v1", "v2", judge_version="j1", rubric_version="r2", input_set_hash="h1")
    assert old["winner"] == "v1"
    assert new["winner"] == "v2"


def test_model_identity_swap_distinct_judge_version(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _emit(plan_dir, "v1", "j-modelA", "r1", "h1", score=0.9, model_identity="model-a")
    _emit(plan_dir, "v2", "j-modelA", "r1", "h1", score=0.6, model_identity="model-a")
    _emit(plan_dir, "v1", "j-modelB", "r1", "h1", score=0.4, model_identity="model-b")
    _emit(plan_dir, "v2", "j-modelB", "r1", "h1", score=0.8, model_identity="model-b")
    result_a = better(plan_dir, "v1", "v2", judge_version="j-modelA", rubric_version="r1", input_set_hash="h1")
    result_b = better(plan_dir, "v1", "v2", judge_version="j-modelB", rubric_version="r1", input_set_hash="h1")
    assert result_a["winner"] == "v1"
    assert result_b["winner"] == "v2"


def test_better_performs_zero_network_io(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _emit(plan_dir, "v1", "j1", "r1", "h1", score=0.8)
    _emit(plan_dir, "v2", "j1", "r1", "h1", score=0.6)
    with patch("megaplan.workers.hermes.dispatch_judge", create=True) as mock_dispatch:
        better(plan_dir, "v1", "v2", judge_version="j1", rubric_version="r1", input_set_hash="h1")
        assert mock_dispatch.call_count == 0
