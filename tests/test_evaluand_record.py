"""M4 T23 — EvaluandRecord tests."""
from __future__ import annotations

import pytest

from megaplan.observability import EvaluandRecord
from megaplan.observability.evaluand import (
    _reset_for_tests,
    read_evaluand,
    write_evaluand,
)


@pytest.fixture(autouse=True)
def _clean():
    _reset_for_tests()
    yield
    _reset_for_tests()


def test_write_then_no_recompute_read_returns_record():
    rec = EvaluandRecord(
        judge_version="j-1",
        rubric_version="r-2",
        input_set_hash="abc123",
        score=0.83,
    )
    write_evaluand("run-7", rec)
    out = read_evaluand("run-7")
    assert out is rec
    assert out.score == pytest.approx(0.83)
    assert out.judge_version == "j-1"


def test_bare_float_is_rejected():
    with pytest.raises(TypeError):
        write_evaluand("run-7", 0.83)  # type: ignore[arg-type]


def test_missing_run_id_is_rejected():
    rec = EvaluandRecord("j", "r", "h", 0.0)
    with pytest.raises(ValueError):
        write_evaluand("", rec)


def test_read_missing_returns_none():
    assert read_evaluand("nope") is None


def test_exported_from_observability_package():
    from megaplan import observability as ob
    assert "EvaluandRecord" in ob.__all__
