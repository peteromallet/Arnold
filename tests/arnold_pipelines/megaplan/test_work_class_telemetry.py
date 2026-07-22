"""Work-class telemetry tests — validation events, zero model calls, and deferred reconciliation.

These tests prove that:
- Validation jobs emit real ``validation`` work-class events (not ``productive``).
- Work-ledger events are evidence-only with the ``_non_authoritative`` marker.
- Aggregate reconciliation (counting, status, completion) remains deferred.
- No model calls or worker dispatch are recorded in validation events.
- Content hashes and event IDs are deterministic.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_plan_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="test_work_class_telemetry_"))


def _suite_run_evidence(
    *,
    job_id: str = "VJ1",
    task_id: str = "T1",
    exit_code: int = 0,
    status: str = "passed",
    passes: list[str] | None = None,
    failures: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "kind": "narrow_recheck",
        "command": "pytest tests/test_t1.py -q",
        "exit_code": exit_code,
        "duration": 1.5,
        "raw_log_path": "/tmp/raw_abc.log",
        "code_hash": "sha256:deadbeef",
        "passes": passes or ["test_a", "test_b"],
        "failures": failures or [],
        "status": status,
        "collected": len(passes or ["test_a", "test_b"]) + len(failures or []),
        "collections_parse_ok": True,
        "timeout_reason": None,
        "referenced_task_id": task_id,
        "evidence_hash": "sha256:ev_hash",
    }


# ---------------------------------------------------------------------------
# Validation events — real, not productive
# ---------------------------------------------------------------------------


class TestValidationEventsAreReal:
    """Prove validation jobs emit real ``validation`` events, not ``productive``."""

    def test_emit_validation_produces_validation_event_class(self) -> None:
        """emit_validation creates an event with event_class='validation'."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="VJ-001",
                command="pytest tests/foo.py",
                exit_code=0,
                duration_ms=1523,
                evidence_hash="abc123",
            )

            assert event["event_class"] == "validation"
            assert event["event_class"] != "productive"
            assert event["referenced_identity"] == "task-1"
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_validation_event_never_classified_as_productive(self) -> None:
        """A validation event must not use the 'productive' event class."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
            emit_validation,
        )

        assert "validation" in WORK_LEDGER_EVENT_CLASSES
        assert "productive" in WORK_LEDGER_EVENT_CLASSES

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="VJ-001",
                command="pytest tests/foo.py",
                exit_code=0,
                duration_ms=1000,
                evidence_hash="hash1",
            )

            # The event_class must be exactly 'validation', never 'productive'
            assert event["event_class"] == "validation"
            assert event["event_class"] != "productive"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_validation_event_payload_excludes_model_attribution(self) -> None:
        """Validation events never carry model_calls, tokens, or cost_usd."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="VJ-001",
                command="pytest tests/foo.py",
                exit_code=0,
                duration_ms=500,
                evidence_hash="hash2",
            )

            payload = event["payload"]
            assert "model_calls" not in payload
            assert "tokens" not in payload
            assert "cost_usd" not in payload
            # productive-only fields must not leak into validation
            assert "work_class" not in payload
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_validation_event_stores_evidence_hash(self) -> None:
        """Validation events link to content-addressed evidence artifacts."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            evidence_hash = "sha256:abc123def456"
            event = emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="VJ-002",
                command="pytest tests/bar.py",
                exit_code=1,
                duration_ms=2500,
                evidence_hash=evidence_hash,
            )

            assert event["payload"]["evidence_hash"] == evidence_hash
            assert event["payload"]["exit_code"] == 1
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Aggregate reconciliation is deferred — work-ledger is non-authoritative
# ---------------------------------------------------------------------------


class TestAggregateReconciliationDeferred:
    """Work-ledger events are evidence-only; aggregate reconciliation remains deferred."""

    def test_all_events_have_non_authoritative_marker(self) -> None:
        """Every emitted event carries _non_authoritative: True."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_productive,
            emit_repair_verify,
            emit_unavailable_reason,
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            val_event = emit_validation(
                plan_dir, task_id="t1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )
            assert val_event["_non_authoritative"] is True

            prod_event = emit_productive(
                plan_dir, task_id="t1", work_class="implementation",
                duration_ms=5000, tokens=100,
            )
            assert prod_event["_non_authoritative"] is True

            repair_event = emit_repair_verify(
                plan_dir, task_id="t1", receipt_hash="r1",
                outcome="adopted", duration_ms=200,
            )
            assert repair_event["_non_authoritative"] is True

            unavail_event = emit_unavailable_reason(
                plan_dir, task_id="t1", measure="tokens",
                reason="not applicable for validation",
            )
            assert unavail_event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_work_ledger_has_no_completion_or_status_semantics(self) -> None:
        """Work-ledger vocabulary excludes completion/status/grant/lease terms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
        )

        # No completion, grant, lease, delivery, or status words
        forbidden = {"completed", "grant", "lease", "delivery", "status", "publication"}
        for event_class in WORK_LEDGER_EVENT_CLASSES:
            assert event_class not in forbidden, (
                f"Event class '{event_class}' must not imply authority/status"
            )

    def test_validation_events_do_not_count_toward_completion(self) -> None:
        """Validation events record observations — they don't signal task completion."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir, task_id="t1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )
            emit_validation(
                plan_dir, task_id="t2", job_id="vj2",
                command="pytest", exit_code=1, duration_ms=200,
                evidence_hash="h2",
            )

            events = read_work_ledger(plan_dir)
            assert len(events) == 2

            for event in events:
                assert "completed" not in event
                assert "status" not in event.get("payload", {})
                assert event.get("_non_authoritative") is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_aggregate_counts_are_computed_externally_not_ledger(self) -> None:
        """The ledger never computes aggregates — it only appends events."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            # Append multiple events — no counting/summarizing happens
            for i in range(5):
                append_work_ledger_event(
                    plan_dir,
                    event_class="validation",
                    referenced_identity=f"task-{i}",
                    payload={
                        "task_id": f"task-{i}",
                        "job_id": f"VJ-{i}",
                        "command": "pytest",
                        "exit_code": 0,
                        "duration_ms": 100,
                    },
                )

            events = read_work_ledger(plan_dir)
            assert len(events) == 5

            # None of the events carry aggregate counts
            for event in events:
                assert "aggregate" not in event
                assert "total" not in event
                assert "summary" not in event
                assert "report" not in event.get("payload", {})
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Content-addressed determinism
# ---------------------------------------------------------------------------


class TestEventDeterminism:
    """Event IDs and content hashes are deterministic from content."""

    def test_validation_event_id_is_deterministic(self) -> None:
        """Same inputs → same event_id (content-addressed)."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir_a = _fresh_plan_dir()
        plan_dir_b = _fresh_plan_dir()
        try:
            event_a = emit_validation(
                plan_dir_a, task_id="t1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )
            event_b = emit_validation(
                plan_dir_b, task_id="t1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )

            # Same inputs (excluding timestamp) must produce same event_id
            assert event_a["event_id"] == event_b["event_id"]
            assert event_a["content_hash"] == event_b["content_hash"]
        finally:
            for d in (plan_dir_a, plan_dir_b):
                try:
                    for f in d.iterdir():
                        f.unlink()
                    d.rmdir()
                except OSError:
                    pass

    def test_different_payloads_produce_different_event_ids(self) -> None:
        """Different payloads produce different event_ids."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event_pass = emit_validation(
                plan_dir, task_id="t1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h_pass",
            )
            event_fail = emit_validation(
                plan_dir, task_id="t1", job_id="vj1",
                command="pytest", exit_code=1, duration_ms=100,
                evidence_hash="h_fail",
            )

            assert event_pass["event_id"] != event_fail["event_id"]
            assert event_pass["content_hash"] != event_fail["content_hash"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_event_id_changes_with_different_referenced_identity(self) -> None:
        """Different referenced_identity → different event_id, even with same payload."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event_t1 = emit_validation(
                plan_dir, task_id="task-1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )
            event_t2 = emit_validation(
                plan_dir, task_id="task-2", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )

            assert event_t1["event_id"] != event_t2["event_id"]
            # referenced_identity differs, so event_id must differ
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Unavailable reason — explicit absence, never default
# ---------------------------------------------------------------------------


class TestUnavailableReasonForValidation:
    """When validation telemetry is missing, emit unavailable_reason — never default to zero."""

    def test_unavailable_reason_never_defaults_to_zero(self) -> None:
        """Missing measurements must be explicit, not zero-defaulted."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_unavailable_reason(
                plan_dir,
                task_id="task-1",
                measure="model_calls",
                reason="validation jobs never invoke models",
            )

            assert event["event_class"] == "unavailable_reason"
            assert event["payload"]["measure"] == "model_calls"
            assert "validation" in event["payload"]["reason"]
            assert event["_non_authoritative"] is True
            # Must not contain zero measurement
            assert "value" not in event["payload"]
            assert "count" not in event["payload"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_for_validation_duration_is_explicit(self) -> None:
        """When duration is missing from a validation run, it's an unavailable_reason."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_unavailable_reason(
                plan_dir,
                task_id="task-1",
                measure="duration_ms",
                reason="validation job timed out before measurement",
            )

            assert event["event_class"] == "unavailable_reason"
            assert event["payload"]["measure"] == "duration_ms"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Validation event vocabulary — only recognized event classes
# ---------------------------------------------------------------------------


class TestValidationEventVocabulary:
    """The work-ledger vocabulary for validation is stable and bounded."""

    def test_work_ledger_recognizes_all_four_classes(self) -> None:
        """The four stable event classes are present."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
        )

        # M8A T17 expanded the vocabulary from 4 to 12 event classes.
        assert WORK_LEDGER_EVENT_CLASSES == frozenset({
            "validation",
            "repair_verify",
            "productive",
            "unavailable_reason",
            "review_proof",
            "queue",
            "retry_wait",
            "compaction",
            "replay",
            "tool",
            "git",
            "transition",
        })

    def test_reject_unknown_event_class(self) -> None:
        """Unregistered event classes raise ValueError."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="Unknown work-ledger event class"):
                append_work_ledger_event(
                    plan_dir,
                    event_class="bogus_class",
                    referenced_identity="task-1",
                    payload={"task_id": "task-1", "job_id": "vj1",
                             "command": "pytest", "exit_code": 0,
                             "duration_ms": 100},
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_missing_required_payload_keys_raises(self) -> None:
        """Missing required payload keys raise ValueError."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="missing required payload"):
                # Missing "task_id" (required for validation)
                append_work_ledger_event(
                    plan_dir,
                    event_class="validation",
                    referenced_identity="task-1",
                    payload={
                        # task_id missing intentionally
                        "job_id": "vj1",
                        "command": "pytest",
                        "exit_code": 0,
                        "duration_ms": 100,
                    },
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Work-ledger read-back for deferred reconciliation
# ---------------------------------------------------------------------------


class TestWorkLedgerReadBack:
    """The work-ledger supports read-back but never computes aggregates."""

    def test_read_work_ledger_returns_events_in_append_order(self) -> None:
        """Events are returned in append order."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir, task_id="t1", job_id="vj1",
                command="pytest a", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )
            emit_validation(
                plan_dir, task_id="t2", job_id="vj2",
                command="pytest b", exit_code=0, duration_ms=200,
                evidence_hash="h2",
            )
            emit_validation(
                plan_dir, task_id="t3", job_id="vj3",
                command="pytest c", exit_code=1, duration_ms=300,
                evidence_hash="h3",
            )

            events = read_work_ledger(plan_dir)
            assert len(events) == 3
            assert events[0]["referenced_identity"] == "t1"
            assert events[1]["referenced_identity"] == "t2"
            assert events[2]["referenced_identity"] == "t3"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_empty_ledger_reads_as_empty_list(self) -> None:
        """An empty ledger returns an empty list, not an error."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            events = read_work_ledger(plan_dir)
            assert events == []
        finally:
            try:
                plan_dir.rmdir()
            except OSError:
                pass

    def test_read_ledger_is_non_mutating(self) -> None:
        """Reading the ledger does not change it."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir, task_id="t1", job_id="vj1",
                command="pytest", exit_code=0, duration_ms=100,
                evidence_hash="h1",
            )

            events_a = read_work_ledger(plan_dir)
            events_b = read_work_ledger(plan_dir)
            assert len(events_a) == 1
            assert len(events_b) == 1
            assert events_a == events_b
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Reconciliation primitives — aggregate_by_class, aggregate_by_task, etc.
# ---------------------------------------------------------------------------


class TestReconciliationPrimitives:
    """Prove that aggregate_by_class, aggregate_by_task, reconcile_unavailable_measures,
    and build_work_class_summary correctly compute from ledger events."""

    def test_aggregate_by_class_groups_by_event_class(self) -> None:
        """aggregate_by_class returns per-class counts and durations."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            aggregate_by_class,
            emit_productive,
            emit_queue,
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir,
                task_id="t1",
                job_id="vj1",
                command="pytest",
                exit_code=0,
                duration_ms=100,
                evidence_hash="h1",
            )
            emit_validation(
                plan_dir,
                task_id="t2",
                job_id="vj2",
                command="pytest",
                exit_code=0,
                duration_ms=200,
                evidence_hash="h2",
            )
            emit_productive(
                plan_dir,
                task_id="t1",
                work_class="implementation",
                duration_ms=5000,
            )
            emit_queue(
                plan_dir,
                task_id="t1",
                duration_ms=300,
                queue_reason="slot_wait",
            )

            result = aggregate_by_class(plan_dir)

            assert result["validation"]["count"] == 2
            assert result["validation"]["total_duration_ms"] == 300
            assert result["validation"]["category"] == "productive"
            assert result["productive"]["count"] == 1
            assert result["productive"]["total_duration_ms"] == 5000
            assert result["queue"]["count"] == 1
            assert result["queue"]["total_duration_ms"] == 300
            assert result["queue"]["category"] == "overhead"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_aggregate_by_class_empty_ledger_returns_all_classes(self) -> None:
        """Even an empty ledger returns entries for all known event classes (count=0)."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
            aggregate_by_class,
        )

        plan_dir = _fresh_plan_dir()
        try:
            result = aggregate_by_class(plan_dir)

            for cls in WORK_LEDGER_EVENT_CLASSES:
                assert cls in result
                assert result[cls]["count"] == 0
                assert result[cls]["total_duration_ms"] is None
                assert result[cls]["task_ids"] == []
        finally:
            try:
                plan_dir.rmdir()
            except OSError:
                pass

    def test_aggregate_by_task_groups_by_referenced_identity(self) -> None:
        """aggregate_by_task returns per-task breakdowns with class counts."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            aggregate_by_task,
            emit_productive,
            emit_queue,
            emit_unavailable_reason,
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir,
                task_id="task-a",
                job_id="vj1",
                command="pytest",
                exit_code=0,
                duration_ms=100,
                evidence_hash="h1",
            )
            emit_productive(
                plan_dir,
                task_id="task-a",
                work_class="implementation",
                duration_ms=2000,
            )
            emit_queue(
                plan_dir,
                task_id="task-b",
                duration_ms=50,
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="task-b",
                measure="tokens",
                reason="provider did not return token count",
            )

            result = aggregate_by_task(plan_dir)

            assert "task-a" in result
            assert "task-b" in result

            # task-a: 1 validation + 1 productive
            assert result["task-a"]["event_classes"]["validation"] == 1
            assert result["task-a"]["event_classes"]["productive"] == 1
            assert result["task-a"]["total_duration_ms"] == 2100

            # task-b: 1 queue + 1 unavailable_reason
            assert result["task-b"]["event_classes"]["queue"] == 1
            assert result["task-b"]["event_classes"]["unavailable_reason"] == 1
            assert result["task-b"]["total_duration_ms"] == 50

            # task-b has unavailable measure
            assert len(result["task-b"]["unavailable_measures"]) == 1
            assert result["task-b"]["unavailable_measures"][0] == (
                "tokens",
                "provider did not return token count",
            )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_reconcile_unavailable_measures_lists_all_gaps(self) -> None:
        """reconcile_unavailable_measures returns every unavailable measure."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
            reconcile_unavailable_measures,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_unavailable_reason(
                plan_dir,
                task_id="t1",
                measure="tokens",
                reason="api did not return usage",
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="t2",
                measure="cost_usd",
                reason="pricing unknown for model",
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="t1",
                measure="model_calls",
                reason="validation job, no model calls",
            )

            gaps = reconcile_unavailable_measures(plan_dir)

            assert len(gaps) == 3
            measures = {(g["task_id"], g["measure"], g["reason"]) for g in gaps}
            assert ("t1", "tokens", "api did not return usage") in measures
            assert ("t2", "cost_usd", "pricing unknown for model") in measures
            assert ("t1", "model_calls", "validation job, no model calls") in measures
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_build_work_class_summary_is_rebuildable(self) -> None:
        """build_work_class_summary produces a deterministic, rebuildable aggregate."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            build_work_class_summary,
            emit_productive,
            emit_queue,
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir,
                task_id="t1",
                job_id="vj1",
                command="pytest",
                exit_code=0,
                duration_ms=150,
                evidence_hash="h1",
            )
            emit_productive(
                plan_dir,
                task_id="t2",
                work_class="implementation",
                duration_ms=3000,
            )
            emit_queue(
                plan_dir,
                task_id="t2",
                duration_ms=200,
            )

            summary = build_work_class_summary(plan_dir)

            assert summary["_non_authoritative"] is True
            assert summary["_rebuildable"] is True
            assert "by_class" in summary
            assert "by_task" in summary
            assert "totals" in summary
            assert "unavailable_measures" in summary

            # Totals should reflect productive vs overhead split
            totals = summary["totals"]
            # productive includes validation (150) + productive (3000) = 3150
            # overhead includes queue (200)
            assert totals["productive_duration_ms"] == 3150
            assert totals["overhead_duration_ms"] == 200
            assert totals["unavailable_measure_count"] == 0
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_build_work_class_summary_handles_empty_ledger(self) -> None:
        """Empty ledger produces valid aggregate with null durations."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            build_work_class_summary,
        )

        plan_dir = _fresh_plan_dir()
        try:
            summary = build_work_class_summary(plan_dir)

            assert summary["_non_authoritative"] is True
            assert summary["_rebuildable"] is True
            assert summary["totals"]["productive_duration_ms"] is None
            assert summary["totals"]["overhead_duration_ms"] is None
            assert summary["totals"]["unavailable_measure_count"] == 0
            assert summary["unavailable_measures"] == []
        finally:
            try:
                plan_dir.rmdir()
            except OSError:
                pass

    def test_aggregate_by_class_deduplicates_task_ids(self) -> None:
        """Multiple events from the same task produce deduplicated task_ids."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            aggregate_by_class,
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="vj1",
                command="pytest",
                exit_code=0,
                duration_ms=100,
                evidence_hash="h1",
            )
            emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="vj2",
                command="pytest",
                exit_code=0,
                duration_ms=200,
                evidence_hash="h2",
            )
            emit_validation(
                plan_dir,
                task_id="task-2",
                job_id="vj3",
                command="pytest",
                exit_code=0,
                duration_ms=300,
                evidence_hash="h3",
            )

            result = aggregate_by_class(plan_dir)
            assert result["validation"]["count"] == 3
            assert result["validation"]["task_ids"] == ["task-1", "task-2"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Extended event-class emitters — all 12 event classes
# ---------------------------------------------------------------------------


class TestExtendedEventClassEmitters:
    """All 12 event classes can be emitted with correct payload schemas."""

    def test_emit_review_proof_produces_correct_payload(self) -> None:
        """review_proof event has required keys: task_id, review_kind, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_review_proof,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_review_proof(
                plan_dir,
                task_id="t1",
                review_kind="code_review",
                duration_ms=4500,
                verdict="accepted",
                reviewer_id="reviewer-1",
            )
            assert event["event_class"] == "review_proof"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["review_kind"] == "code_review"
            assert event["payload"]["duration_ms"] == 4500
            assert event["payload"]["verdict"] == "accepted"
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_queue_produces_correct_payload(self) -> None:
        """queue event has required keys: task_id, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_queue,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_queue(
                plan_dir,
                task_id="t1",
                duration_ms=350,
                queue_reason="slot_wait",
            )
            assert event["event_class"] == "queue"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["duration_ms"] == 350
            assert event["payload"]["queue_reason"] == "slot_wait"
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_retry_wait_produces_correct_payload(self) -> None:
        """retry_wait event has required keys: task_id, duration_ms, attempt_number."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_retry_wait,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_retry_wait(
                plan_dir,
                task_id="t1",
                duration_ms=2000,
                attempt_number=3,
                wait_reason="backoff_cooldown",
            )
            assert event["event_class"] == "retry_wait"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["duration_ms"] == 2000
            assert event["payload"]["attempt_number"] == 3
            assert event["payload"]["wait_reason"] == "backoff_cooldown"
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_compaction_produces_correct_payload(self) -> None:
        """compaction event has required keys: task_id, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_compaction,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_compaction(
                plan_dir,
                task_id="t1",
                duration_ms=1200,
                compacted_tokens=5000,
                strategy="summary",
            )
            assert event["event_class"] == "compaction"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["duration_ms"] == 1200
            assert event["payload"]["compacted_tokens"] == 5000
            assert event["payload"]["strategy"] == "summary"
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_replay_produces_correct_payload(self) -> None:
        """replay event has required keys: task_id, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_replay,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_replay(
                plan_dir,
                task_id="t1",
                duration_ms=800,
                fixture_path="/tmp/fixture.json",
                exit_code=0,
            )
            assert event["event_class"] == "replay"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["duration_ms"] == 800
            assert event["payload"]["fixture_path"] == "/tmp/fixture.json"
            assert event["payload"]["exit_code"] == 0
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_tool_produces_correct_payload(self) -> None:
        """tool event has required keys: task_id, tool_name, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_tool,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_tool(
                plan_dir,
                task_id="t1",
                tool_name="terminal",
                duration_ms=450,
                exit_code=0,
            )
            assert event["event_class"] == "tool"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["tool_name"] == "terminal"
            assert event["payload"]["duration_ms"] == 450
            assert event["payload"]["exit_code"] == 0
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_git_produces_correct_payload(self) -> None:
        """git event has required keys: task_id, operation, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_git,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_git(
                plan_dir,
                task_id="t1",
                operation="commit",
                duration_ms=320,
                exit_code=0,
            )
            assert event["event_class"] == "git"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["operation"] == "commit"
            assert event["payload"]["duration_ms"] == 320
            assert event["payload"]["exit_code"] == 0
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_transition_produces_correct_payload(self) -> None:
        """transition event has required keys: task_id, from_state, to_state, duration_ms."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_transition,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_transition(
                plan_dir,
                task_id="t1",
                from_state="queued",
                to_state="running",
                duration_ms=75,
            )
            assert event["event_class"] == "transition"
            assert event["payload"]["task_id"] == "t1"
            assert event["payload"]["from_state"] == "queued"
            assert event["payload"]["to_state"] == "running"
            assert event["payload"]["duration_ms"] == 75
            assert event["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Cost attribution — tokens, cost_usd, model_calls reconcile to explicit classes
# ---------------------------------------------------------------------------


class TestCostAttributionReconciliation:
    """Cost measures (tokens, cost_usd, model_calls) reconcile to explicit
    classes or unavailable_reason — never defaulted to zero."""

    def test_productive_event_can_carry_tokens_cost_and_model_calls(self) -> None:
        """emit_productive accepts optional tokens, cost_usd, model_calls."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_productive,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_productive(
                plan_dir,
                task_id="t1",
                work_class="implementation",
                duration_ms=5000,
                tokens=15000,
                cost_usd=0.075,
                model_calls=3,
            )
            assert event["event_class"] == "productive"
            assert event["payload"]["tokens"] == 15000
            assert event["payload"]["cost_usd"] == 0.075
            assert event["payload"]["model_calls"] == 3
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_productive_event_without_cost_still_valid(self) -> None:
        """emit_productive is valid without tokens, cost_usd, or model_calls."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_productive,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_productive(
                plan_dir,
                task_id="t1",
                work_class="implementation",
                duration_ms=1000,
            )
            assert event["event_class"] == "productive"
            assert "tokens" not in event["payload"]
            assert "cost_usd" not in event["payload"]
            assert "model_calls" not in event["payload"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_for_tokens_is_explicit(self) -> None:
        """Missing tokens → emit unavailable_reason, not default to zero."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
            reconcile_unavailable_measures,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_unavailable_reason(
                plan_dir,
                task_id="t1",
                measure="tokens",
                reason="provider API did not return usage info",
            )

            gaps = reconcile_unavailable_measures(plan_dir)
            assert len(gaps) == 1
            assert gaps[0]["task_id"] == "t1"
            assert gaps[0]["measure"] == "tokens"
            assert "provider" in gaps[0]["reason"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_for_cost_usd_is_explicit(self) -> None:
        """Missing cost_usd → emit unavailable_reason, not default to zero."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
            reconcile_unavailable_measures,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_unavailable_reason(
                plan_dir,
                task_id="t2",
                measure="cost_usd",
                reason="model pricing unknown",
            )

            gaps = reconcile_unavailable_measures(plan_dir)
            assert len(gaps) == 1
            assert gaps[0]["task_id"] == "t2"
            assert gaps[0]["measure"] == "cost_usd"
            assert "pricing" in gaps[0]["reason"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_for_model_calls_is_explicit(self) -> None:
        """Missing model_calls → emit unavailable_reason, not default to zero."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
            reconcile_unavailable_measures,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_unavailable_reason(
                plan_dir,
                task_id="t3",
                measure="model_calls",
                reason="validation jobs never invoke models",
            )

            gaps = reconcile_unavailable_measures(plan_dir)
            assert len(gaps) == 1
            assert gaps[0]["task_id"] == "t3"
            assert gaps[0]["measure"] == "model_calls"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_full_accounting_all_measures_explicit(self) -> None:
        """Every measure (duration, tokens, cost_usd, model_calls) is either
        present in productive events or explicitly unavailable."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            build_work_class_summary,
            emit_productive,
            emit_unavailable_reason,
        )

        plan_dir = _fresh_plan_dir()
        try:
            # Productive event WITH full cost attribution
            emit_productive(
                plan_dir,
                task_id="task-full",
                work_class="implementation",
                duration_ms=5000,
                tokens=10000,
                cost_usd=0.05,
                model_calls=2,
            )

            # Productive event WITHOUT cost attribution → explicit unavailable
            emit_productive(
                plan_dir,
                task_id="task-missing-cost",
                work_class="implementation",
                duration_ms=3000,
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="task-missing-cost",
                measure="tokens",
                reason="provider did not return token count",
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="task-missing-cost",
                measure="cost_usd",
                reason="unknown pricing for model",
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="task-missing-cost",
                measure="model_calls",
                reason="provider did not return call count",
            )

            summary = build_work_class_summary(plan_dir)

            # Full accounting: unavailable_measures are explicit
            assert summary["totals"]["unavailable_measure_count"] == 3
            assert len(summary["unavailable_measures"]) == 3

            # task-full has productive event with cost, no unavailability
            assert "task-full" in summary["by_task"]
            assert summary["by_task"]["task-full"]["event_classes"]["productive"] == 1
            assert summary["by_task"]["task-full"]["unavailable_measures"] == []

            # task-missing-cost has productive + 3 unavailable_reason events
            assert "task-missing-cost" in summary["by_task"]
            assert summary["by_task"]["task-missing-cost"]["event_classes"]["productive"] == 1
            assert summary["by_task"]["task-missing-cost"]["event_classes"]["unavailable_reason"] == 3
            assert len(summary["by_task"]["task-missing-cost"]["unavailable_measures"]) == 3
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_duration_always_reconciles_to_explicit_class(self) -> None:
        """Every event's duration_ms contributes to a specific event class total."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            aggregate_by_class,
            emit_productive,
            emit_queue,
            emit_review_proof,
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(
                plan_dir,
                task_id="t1",
                job_id="vj1",
                command="pytest",
                exit_code=0,
                duration_ms=100,
                evidence_hash="h1",
            )
            emit_productive(
                plan_dir,
                task_id="t1",
                work_class="implementation",
                duration_ms=5000,
            )
            emit_queue(
                plan_dir,
                task_id="t1",
                duration_ms=200,
            )
            emit_review_proof(
                plan_dir,
                task_id="t1",
                review_kind="code_review",
                duration_ms=3000,
            )

            by_class = aggregate_by_class(plan_dir)

            # Each duration lands in exactly one class
            assert by_class["validation"]["total_duration_ms"] == 100
            assert by_class["productive"]["total_duration_ms"] == 5000
            assert by_class["queue"]["total_duration_ms"] == 200
            assert by_class["review_proof"]["total_duration_ms"] == 3000

            # No duration is counted twice
            total = sum(
                v["total_duration_ms"]
                for v in by_class.values()
                if v["total_duration_ms"] is not None
            )
            assert total == 100 + 5000 + 200 + 3000
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_never_defaults_cost_to_zero(self) -> None:
        """When cost is unavailable, reconcile_unavailable_measures lists it —
        build_work_class_summary never defaults cost to zero."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            build_work_class_summary,
            emit_productive,
            emit_unavailable_reason,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_productive(
                plan_dir,
                task_id="t1",
                work_class="implementation",
                duration_ms=2000,
                # no tokens, cost_usd, or model_calls
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="t1",
                measure="tokens",
                reason="not available",
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="t1",
                measure="cost_usd",
                reason="not available",
            )
            emit_unavailable_reason(
                plan_dir,
                task_id="t1",
                measure="model_calls",
                reason="not available",
            )

            summary = build_work_class_summary(plan_dir)

            # unavailable_measures are explicit, totals don't default cost to zero
            unavailable_measures = summary["unavailable_measures"]
            measures_seen = {m["measure"] for m in unavailable_measures}
            assert "tokens" in measures_seen
            assert "cost_usd" in measures_seen
            assert "model_calls" in measures_seen

            # No cost field is defaulted to zero in totals
            assert "cost_usd" not in summary["totals"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass
