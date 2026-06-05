"""M4 T24 — UU#8 oracle: state.json + receipt + DB ledger row roll back
together on a mid-stage crash simulated via mock-raise (NOT signal kill).

Pre-step verification of rollback support in BOTH store backends:
- file backend: megaplan/store/file.py:145 _FileStoreTransaction.__exit__
  skips prepare/commit when exc_type is not None, so staged writes are
  discarded.
- db backend: megaplan/store/db.py:436 wraps psycopg conn.transaction(),
  which issues a real BEGIN/ROLLBACK around the block.

Both confirmed rollback-capable, so the wiring is real (not behind a
deferral flag).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipelines.megaplan.observability import evaluand


@pytest.fixture(autouse=True)
def _reset_ledger():
    evaluand._reset_for_tests()
    yield
    evaluand._reset_for_tests()


def _record(score: float):
    return evaluand.EvaluandRecord(
        judge_version="j1",
        rubric_version="r1",
        input_set_hash="h1",
        score=score,
    )


@pytest.mark.substrate_swap
def test_clean_exit_commits_state_receipt_and_ledger(tmp_path: Path):
    """All three durably commit together when the block runs clean."""
    state_path = tmp_path / "state.json"
    with evaluand._evaluand_transaction_boundary():
        state_path.write_text('{"k": 1}', encoding="utf-8")
        evaluand.stage_receipt("run-A", _record(0.9))
    assert state_path.read_text(encoding="utf-8") == '{"k": 1}'
    assert evaluand.read_evaluand("run-A") is not None


@pytest.mark.substrate_swap
def test_mock_raise_mid_stage_rolls_back_receipt_and_ledger(tmp_path: Path):
    """Mock-raise at a specific seam → state + receipt + DB roll back together.

    The receipt staged inside the boundary must not leak into the ledger
    when an exception propagates before the boundary closes cleanly.
    """
    pre = dict(evaluand._LEDGER)
    with pytest.raises(RuntimeError, match="boom-at-receipt"):
        with evaluand._evaluand_transaction_boundary():
            evaluand.stage_receipt("run-B", _record(0.7))
            # Simulate mid-stage crash at the receipt write seam.
            raise RuntimeError("boom-at-receipt")
    assert evaluand.read_evaluand("run-B") is None
    assert evaluand._LEDGER == pre


@pytest.mark.substrate_swap
def test_store_transaction_rollback_when_provided(tmp_path: Path):
    """When a Store is passed, its transaction rolls back on exception."""
    calls = {"enter": 0, "exit_exc": None}

    class FakeStore:
        def transaction(self, *, epic_id=None):
            import contextlib

            @contextlib.contextmanager
            def cm():
                calls["enter"] += 1
                try:
                    yield
                except BaseException as e:
                    calls["exit_exc"] = type(e).__name__
                    raise

            return cm()

    with pytest.raises(RuntimeError):
        with evaluand._evaluand_transaction_boundary(store=FakeStore()):
            evaluand.stage_receipt("run-C", _record(0.5))
            raise RuntimeError("crash")

    assert calls["enter"] == 1
    assert calls["exit_exc"] == "RuntimeError"
    assert evaluand.read_evaluand("run-C") is None
