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
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.observability.events import EventKind, read_events
from arnold_pipelines.megaplan.observability.work_ledger import (
    LEDGER_FILE,
    PRODUCER_CONTRACTS,
    WorkClass,
    WorkLedgerEvent,
    emit_git_activity,
    emit_compaction,
    emit_productive,
    emit_queue_idle,
    emit_repair_verification,
    emit_replay,
    emit_retry_wait,
    emit_review_proof,
    emit_strategy_m4_baseline_events,
    emit_tool_activity,
    emit_transition_activity,
    emit_validation,
    emit_worker_inference,
    emit_work_ledger_event,
    validate_producer_contract,
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
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.001,
            accepted_output_delta=0,
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
            assert record["unavailable_reason"] == "queue_idle_no_model_no_output_delta"

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
            assert record["unavailable_reason"] == "retry_wait_no_model_no_output_delta"

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

    def test_emit_strategy_m4_baseline_preserves_non_waste_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            emit_strategy_m4_baseline_events(plan_dir)

            records = [
                json.loads(line)
                for line in (plan_dir / LEDGER_FILE).read_text(encoding="utf-8").splitlines()
            ]
            assert [record["work_class"] for record in records] == [
                "productive",
                "review_proof",
            ]
            assert records[0]["elapsed_ms"] == 7_397_000
            assert records[0]["metadata"]["duration_label"] == "2h03m17s"
            assert records[0]["metadata"]["classification_guard"] == (
                "productive_implementation_not_waste"
            )
            assert records[1]["metadata"]["classification_guard"] == (
                "required_review_not_waste"
            )


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
            assert d1["unavailable_reason"] == "queue_idle_no_model_no_output_delta"

        # Validation — via convenience emitter
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            emit_validation(plan_dir, elapsed_ms=100)
            ledger_path = plan_dir / LEDGER_FILE
            d2 = json.loads(ledger_path.read_text().strip())
            assert d2["model_calls"] == 0
            assert d2["total_tokens"] == 0
            assert d2["cost_usd"] == 0.0

    def test_no_model_contract_events_validate_without_warnings(self) -> None:
        """Concrete no-model producer rows satisfy the declared contracts."""
        examples = [
            WorkLedgerEvent(
                work_class=WorkClass.QUEUE_IDLE,
                elapsed_ms=100,
                model_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                unavailable_reason="queue_idle_no_model_no_output_delta",
            ),
            WorkLedgerEvent(
                work_class=WorkClass.RETRY_WAIT,
                elapsed_ms=100,
                model_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                unavailable_reason="retry_wait_no_model_no_output_delta",
            ),
            WorkLedgerEvent(
                work_class=WorkClass.VALIDATION,
                elapsed_ms=100,
                model_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                unavailable_reason="subprocess_validation_no_model",
            ),
            WorkLedgerEvent(
                work_class=WorkClass.REPAIR_VERIFICATION,
                elapsed_ms=100,
                model_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                unavailable_reason="read_only_verification_no_model",
            ),
        ]
        for event in examples:
            assert event.validate() == []
            assert validate_producer_contract(event) == []

    def test_no_waste_class(self) -> None:
        """There is no 'waste' work class — missing measures are 'unavailable'."""
        classes = {c.value for c in WorkClass}
        assert "waste" not in classes


class TestNaturalBoundaryEmitters:
    """Runtime checks for the helper emitters used by producer call sites."""

    def _ledger_records(self, plan_dir: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (plan_dir / LEDGER_FILE).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_every_work_class_has_a_producer_contract(self) -> None:
        assert set(PRODUCER_CONTRACTS) == set(WorkClass)

    def test_worker_inference_emits_session_inference_and_productive_rows(self) -> None:
        worker = SimpleNamespace(
            auth_metadata={"wbc_dispatch": {"attempt_id": "attempt-1"}},
            cost_usd=0.012,
            duration_ms=1234,
            model_actual="gpt-test",
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            session_id="session-1",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            emit_worker_inference(
                plan_dir,
                phase="execute",
                worker=worker,
                work_class=WorkClass.PRODUCTIVE,
                batch_id="25",
                accepted_output_delta=55,
                agent="codex",
                metadata={"boundary": "execute_batch_worker"},
            )

            ledger = self._ledger_records(plan_dir)
            assert len(ledger) == 1
            assert ledger[0]["work_class"] == "productive"
            assert ledger[0]["attempt_id"] == "attempt-1"
            assert ledger[0]["accepted_output_delta"] == 55
            assert "unavailable_reason" not in ledger[0]

            events = list(
                read_events(
                    plan_dir,
                    kinds=[EventKind.SESSION_START, EventKind.INFERENCE],
                )
            )
            assert [event["kind"] for event in events] == [
                EventKind.SESSION_START,
                EventKind.INFERENCE,
            ]
            inference_payload = events[1]["payload"]
            assert inference_payload["tokens_in"] == 100
            assert inference_payload["tokens_out"] == 40
            assert inference_payload["duration_s"] == 1.234
            assert inference_payload["boundary"] == "execute_batch_worker"

    def test_tool_git_and_transition_emit_companion_events_and_validation_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            emit_tool_activity(
                plan_dir,
                phase="execute",
                tool_name="compiled_validation_jobs",
                elapsed_ms=10,
                batch_id="25",
            )
            emit_git_activity(
                plan_dir,
                phase="execute",
                operation="status_before_batch",
                elapsed_ms=20,
            )
            emit_transition_activity(
                plan_dir,
                phase="review",
                transition="review_outcome",
                from_state="executed",
                to_state="reviewed",
            )

            ledger = self._ledger_records(plan_dir)
            assert [record["work_class"] for record in ledger] == [
                "validation",
                "validation",
                "validation",
            ]
            assert all(
                record["unavailable_reason"] == "subprocess_validation_no_model"
                for record in ledger
            )

            events = list(
                read_events(
                    plan_dir,
                    kinds=[EventKind.TOOL, EventKind.GIT, EventKind.TRANSITION],
                )
            )
            assert [event["kind"] for event in events] == [
                EventKind.TOOL,
                EventKind.GIT,
                EventKind.TOOL,
                EventKind.TRANSITION,
                EventKind.TOOL,
            ]
            assert events[0]["payload"]["duration_s"] == 0.01
            assert events[1]["payload"]["operation"] == "status_before_batch"
            assert events[3]["payload"]["transition"] == "review_outcome"


class TestProducerWiring:
    """Producer call sites cover the M9 natural execution boundaries."""

    TARGET_FILES = {
        "auto.py": Path("arnold_pipelines/megaplan/auto.py"),
        "chain/__init__.py": Path("arnold_pipelines/megaplan/chain/__init__.py"),
        "execute/batch.py": Path("arnold_pipelines/megaplan/execute/batch.py"),
        "handlers/execute.py": Path("arnold_pipelines/megaplan/handlers/execute.py"),
        "handlers/review.py": Path("arnold_pipelines/megaplan/handlers/review.py"),
        "handlers/gate.py": Path("arnold_pipelines/megaplan/handlers/gate.py"),
        "handlers/finalize.py": Path("arnold_pipelines/megaplan/handlers/finalize.py"),
    }

    def _source(self, name: str) -> str:
        return self.TARGET_FILES[name].read_text(encoding="utf-8")

    def test_auto_driver_emits_wait_retry_compaction_and_transition_boundaries(self) -> None:
        source = self._source("auto.py")
        assert "emit_queue_idle" in source
        assert "emit_retry_wait" in source
        assert "emit_compaction" in source
        assert "emit_transition_activity" in source
        assert "auto_driver_wait_no_model" in source
        assert "auto_context_retry_usage_unavailable" in source

    def test_chain_driver_emits_session_git_retry_transition_and_replay_boundaries(self) -> None:
        source = self._source("chain/__init__.py")
        assert "emit_session_start" in source
        assert "emit_git_activity" in source
        assert "emit_retry_wait" in source
        assert "emit_transition_activity" in source
        assert "emit_replay" in source
        assert "blocked_plan_replay_suppressed" in source

    def test_handlers_and_batch_emit_worker_tool_git_and_transition_boundaries(self) -> None:
        expected = {
            "execute/batch.py": [
                "emit_worker_inference",
                "emit_tool_activity",
                "emit_git_activity",
                "emit_transition_activity",
                "emit_replay",
            ],
            "handlers/execute.py": ["emit_tool_activity", "REPAIR_VERIFICATION"],
            "handlers/review.py": ["emit_worker_inference", "emit_transition_activity"],
            "handlers/gate.py": ["emit_worker_inference", "emit_transition_activity"],
            "handlers/finalize.py": ["emit_worker_inference", "emit_transition_activity"],
        }
        for name, needles in expected.items():
            source = self._source(name)
            for needle in needles:
                assert needle in source, f"{needle} missing from {name}"
