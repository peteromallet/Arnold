"""M9 work-class ledger tests.

Covers:
- WorkClass enum values
- WorkLedgerEvent construction, serialization, and validation
- Convenience emitters for every work class
- unavailable_reason enforcement (never zero for missing measures)
- JSONL write and read-back
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.observability.work_ledger import (
    LEDGER_FILE,
    WorkClass,
    WorkLedgerEvent,
    emit_compaction,
    emit_productive,
    emit_queue_idle,
    emit_repair_verification,
    emit_replay,
    emit_retry_wait,
    emit_review_proof,
    emit_validation,
    emit_work_ledger_event,
)


# ---------------------------------------------------------------------------
# WorkClass
# ---------------------------------------------------------------------------


class TestWorkClass:
    """WorkClass enum covers all required classes."""

    def test_all_classes_present(self) -> None:
        classes = {c.value for c in WorkClass}
        assert "productive" in classes
        assert "review_proof" in classes
        assert "queue_idle" in classes
        assert "retry_wait" in classes
        assert "compaction" in classes
        assert "validation" in classes
        assert "repair_verification" in classes
        assert "replay" in classes

    def test_is_string_enum(self) -> None:
        assert WorkClass.PRODUCTIVE.value == "productive"
        assert isinstance(WorkClass.PRODUCTIVE.value, str)


# ---------------------------------------------------------------------------
# WorkLedgerEvent construction & serialization
# ---------------------------------------------------------------------------


class TestWorkLedgerEvent:
    """Construction, serialization, and validation of WorkLedgerEvent."""

    def test_minimal_construction(self) -> None:
        event = WorkLedgerEvent(work_class=WorkClass.PRODUCTIVE)
        d = event.to_dict()
        assert d["work_class"] == "productive"
        assert "ts" in d
        assert "task_id" not in d  # omitted when None

    def test_full_construction(self) -> None:
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
            task_id="T1",
            batch_id="b1",
            attempt_id="a1",
            elapsed_ms=1500,
            model_calls=1,
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.003,
            metadata={"provider": "codex"},
        )
        d = event.to_dict()
        assert d["work_class"] == "productive"
        assert d["task_id"] == "T1"
        assert d["batch_id"] == "b1"
        assert d["attempt_id"] == "a1"
        assert d["elapsed_ms"] == 1500
        assert d["model_calls"] == 1
        assert d["prompt_tokens"] == 500
        assert d["completion_tokens"] == 200
        assert d["total_tokens"] == 700
        assert d["cost_usd"] == 0.003
        assert d["metadata"] == {"provider": "codex"}

    def test_to_dict_preserves_none_for_measures(self) -> None:
        """Measures are None, not 0, when unavailable."""
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
            unavailable_reason="test_reason",
        )
        d = event.to_dict()
        assert d["elapsed_ms"] is None
        assert d["model_calls"] is None
        assert d["prompt_tokens"] is None
        assert d["completion_tokens"] is None
        assert d["total_tokens"] is None
        assert d["cost_usd"] is None
        assert d["unavailable_reason"] == "test_reason"

    def test_explicit_zero_is_preserved(self) -> None:
        """Zero is intentional — it must be preserved, not treated as missing."""
        event = WorkLedgerEvent(
            work_class=WorkClass.QUEUE_IDLE,
            elapsed_ms=0,
            model_calls=0,
            total_tokens=0,
            cost_usd=0.0,
            unavailable_reason="intentional_zero_for_queue_idle",
        )
        d = event.to_dict()
        assert d["elapsed_ms"] == 0
        assert d["model_calls"] == 0
        assert d["total_tokens"] == 0
        assert d["cost_usd"] == 0.0

    # -- Validation ----------------------------------------------------------

    def test_validate_passes_when_all_measures_present(self) -> None:
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
            elapsed_ms=100,
            model_calls=1,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            cost_usd=0.001,
        )
        assert event.validate() == []

    def test_validate_passes_when_missing_with_reason(self) -> None:
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
            unavailable_reason="worker_crash",
        )
        assert event.validate() == []

    def test_validate_fails_when_missing_without_reason(self) -> None:
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
        )
        issues = event.validate()
        assert len(issues) > 0
        assert any("unavailable_reason" in issue for issue in issues)

    def test_validate_partial_missing(self) -> None:
        """Only some measures missing still requires unavailable_reason."""
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
            elapsed_ms=100,
            model_calls=1,
            # tokens and cost missing
        )
        issues = event.validate()
        assert len(issues) > 0


# ---------------------------------------------------------------------------
# JSONL write and read-back
# ---------------------------------------------------------------------------


class TestWorkLedgerJsonl:
    """Emission and read-back of work ledger events to JSONL."""

    def test_emit_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            event = WorkLedgerEvent(
                work_class=WorkClass.PRODUCTIVE,
                task_id="T1",
                batch_id="b1",
                elapsed_ms=100,
                model_calls=1,
                total_tokens=50,
                cost_usd=0.002,
            )
            emit_work_ledger_event(plan_dir, event)

            ledger_path = plan_dir / LEDGER_FILE
            assert ledger_path.is_file()

            lines = ledger_path.read_text().strip().split("\n")
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["work_class"] == "productive"
            assert record["task_id"] == "T1"
            assert record["batch_id"] == "b1"
            assert record["elapsed_ms"] == 100
            assert record["model_calls"] == 1
            assert record["total_tokens"] == 50
            assert record["cost_usd"] == 0.002

    def test_multiple_events_appended(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            for i in range(3):
                emit_work_ledger_event(
                    plan_dir,
                    WorkLedgerEvent(
                        work_class=WorkClass.PRODUCTIVE,
                        task_id=f"T{i}",
                        elapsed_ms=10 * i,
                    ),
                )

            ledger_path = plan_dir / LEDGER_FILE
            lines = ledger_path.read_text().strip().split("\n")
            assert len(lines) == 3
            for i, line in enumerate(lines):
                record = json.loads(line)
                assert record["task_id"] == f"T{i}"

    def test_emit_to_nonexistent_dir_does_not_raise(self) -> None:
        """Emission to a non-existent directory must not raise."""
        plan_dir = Path("/tmp/nonexistent_work_ledger_test_dir_xyz")
        # Should not raise
        emit_work_ledger_event(
            plan_dir,
            WorkLedgerEvent(work_class=WorkClass.PRODUCTIVE),
        )


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------


class TestConvenienceBuilders:
    """Each convenience emitter writes a correctly-classified event."""

    def _emit_and_read(self, plan_dir: Path, emit_fn, **kwargs) -> dict:
        emit_fn(plan_dir, **kwargs)
        ledger_path = plan_dir / LEDGER_FILE
        lines = ledger_path.read_text().strip().split("\n")
        return json.loads(lines[-1])

    def test_emit_productive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_productive,
                task_id="T1",
                batch_id="b1",
                attempt_id="a1",
                elapsed_ms=5000,
                model_calls=1,
                prompt_tokens=1000,
                completion_tokens=500,
                total_tokens=1500,
                cost_usd=0.015,
            )
            assert record["work_class"] == "productive"
            assert record["task_id"] == "T1"
            assert record["elapsed_ms"] == 5000
            assert record["total_tokens"] == 1500

    def test_emit_productive_missing_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_productive,
                task_id="T2",
                elapsed_ms=1000,
                unavailable_reason="model_did_not_report",
            )
            assert record["work_class"] == "productive"
            assert record["unavailable_reason"] == "model_did_not_report"
            assert record["total_tokens"] is None

    def test_emit_review_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_review_proof,
                task_id="T3",
                elapsed_ms=3000,
                model_calls=1,
                total_tokens=800,
                cost_usd=0.008,
            )
            assert record["work_class"] == "review_proof"
            assert record["task_id"] == "T3"

    def test_emit_queue_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_queue_idle,
                elapsed_ms=20000,
                batch_id="b2",
            )
            assert record["work_class"] == "queue_idle"
            assert record["elapsed_ms"] == 20000
            # Queue idle must have zero model usage, not None
            assert record["model_calls"] == 0
            assert record["total_tokens"] == 0
            assert record["cost_usd"] == 0.0

    def test_emit_retry_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_retry_wait,
                elapsed_ms=60000,
                task_id="T4",
                attempt_id="a2",
            )
            assert record["work_class"] == "retry_wait"
            assert record["elapsed_ms"] == 60000
            assert record["model_calls"] == 0

    def test_emit_compaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_compaction,
                elapsed_ms=500,
                model_calls=1,
                prompt_tokens=2000,
                completion_tokens=100,
                total_tokens=2100,
                cost_usd=0.001,
            )
            assert record["work_class"] == "compaction"

    def test_emit_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_validation,
                task_id="T5",
                elapsed_ms=1500,
            )
            assert record["work_class"] == "validation"
            assert record["model_calls"] == 0
            assert record["unavailable_reason"] == "subprocess_validation_no_model"

    def test_emit_repair_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_repair_verification,
                elapsed_ms=50,
                metadata={"total_receipts": 3},
            )
            assert record["work_class"] == "repair_verification"
            assert record["model_calls"] == 0
            assert record["unavailable_reason"] == "read_only_verification_no_model"

    def test_emit_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            record = self._emit_and_read(
                plan_dir,
                emit_replay,
                task_id="T6",
                elapsed_ms=2000,
                model_calls=1,
                total_tokens=600,
                cost_usd=0.006,
            )
            assert record["work_class"] == "replay"


# ---------------------------------------------------------------------------
# Never zero for missing measures
# ---------------------------------------------------------------------------


class TestNeverZeroForMissing:
    """Missing measures must be None with unavailable_reason, never zero."""

    def test_productive_missing_measures_are_none(self) -> None:
        """When tokens/cost are missing, they stay None."""
        event = WorkLedgerEvent(
            work_class=WorkClass.PRODUCTIVE,
            elapsed_ms=100,
            unavailable_reason="provider_timeout",
        )
        d = event.to_dict()
        assert d["prompt_tokens"] is None
        assert d["completion_tokens"] is None
        assert d["total_tokens"] is None
        assert d["cost_usd"] is None
        assert d["unavailable_reason"] == "provider_timeout"

    def test_review_missing_measures_are_none(self) -> None:
        event = WorkLedgerEvent(
            work_class=WorkClass.REVIEW_PROOF,
            elapsed_ms=200,
            unavailable_reason="model_call_failed",
        )
        d = event.to_dict()
        assert d["total_tokens"] is None
        assert d["cost_usd"] is None

    def test_explicit_zero_only_for_no_model_classes(self) -> None:
        """Validation, repair_verification, queue_idle, retry_wait
        correctly use zero because there genuinely is no model call.
        The convenience emitters set model_calls=0, total_tokens=0, cost_usd=0.0
        because these classes genuinely involve no model."""
        # Queue idle — via convenience emitter
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            emit_queue_idle(plan_dir, elapsed_ms=100)
            ledger_path = plan_dir / LEDGER_FILE
            d1 = json.loads(ledger_path.read_text().strip())
            assert d1["model_calls"] == 0
            assert d1["total_tokens"] == 0
            assert d1["cost_usd"] == 0.0

        # Validation — via convenience emitter
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            emit_validation(plan_dir, elapsed_ms=100)
            ledger_path = plan_dir / LEDGER_FILE
            d2 = json.loads(ledger_path.read_text().strip())
            assert d2["model_calls"] == 0
            assert d2["total_tokens"] == 0
            assert d2["cost_usd"] == 0.0

    def test_no_waste_class(self) -> None:
        """There is no 'waste' work class — missing measures are 'unavailable'."""
        classes = {c.value for c in WorkClass}
        assert "waste" not in classes
