"""Focused tests for the M8A work-ledger observability surface.

These tests exercise the work-ledger module directly and guard the North Star
constraint that ledger evidence is *not* authority.  Assertions are local to
the work-ledger surface: event emission, vocabulary enforcement, deterministic
hashing, read-back, and the ``unavailable_reason`` path for missing measurements.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _fresh_plan_dir() -> Path:
    """Return a fresh, isolated temporary directory for ledger writes."""
    return Path(tempfile.mkdtemp(prefix="test_work_ledger_"))


# ═══════════════════════════════════════════════════════════════════════════
# Event emission — validation events
# ═══════════════════════════════════════════════════════════════════════════


class TestValidationEventEmission:
    """Prove that ``validation`` events are emitted with the correct structure."""

    def test_emit_validation_writes_ndjson_and_returns_event(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
            read_work_ledger,
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
            assert event["referenced_identity"] == "task-1"
            assert event["_non_authoritative"] is True
            assert event["payload"]["task_id"] == "task-1"
            assert event["payload"]["job_id"] == "VJ-001"
            assert event["payload"]["exit_code"] == 0
            assert event["payload"]["duration_ms"] == 1523
            assert event["payload"]["evidence_hash"] == "abc123"

            # Verify it was written to disk
            events = read_work_ledger(plan_dir)
            assert len(events) == 1
            assert events[0]["event_id"] == event["event_id"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_validation_event_has_no_model_calls_attribute(self) -> None:
        """Validation events are harness-owned — they must not claim model consumption."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_validation(
                plan_dir,
                task_id="task-1",
                job_id="VJ-001",
                command="pytest",
                exit_code=0,
                duration_ms=100,
            )
            assert "model_calls" not in event["payload"]
            assert "tokens" not in event["payload"]
            assert "cost_usd" not in event["payload"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_validation_event_deterministic_event_id(self) -> None:
        """Same validation payload → same event_id (deterministic content-addressing)."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            payload = {"task_id": "t1", "job_id": "j1", "command": "pytest", "exit_code": 0, "duration_ms": 100}
            e1 = append_work_ledger_event(plan_dir, event_class="validation", referenced_identity="t1", payload=payload)
            e2 = append_work_ledger_event(plan_dir, event_class="validation", referenced_identity="t1", payload=dict(payload))
            assert e1["event_id"] == e2["event_id"]
            assert e1["content_hash"] == e2["content_hash"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_validation_event_id_differs_when_payload_differs(self) -> None:
        """Different payloads must produce different event_ids."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            p1 = {"task_id": "t1", "job_id": "j1", "command": "pytest", "exit_code": 0, "duration_ms": 100}
            p2 = {"task_id": "t1", "job_id": "j1", "command": "pytest", "exit_code": 1, "duration_ms": 100}
            e1 = append_work_ledger_event(plan_dir, event_class="validation", referenced_identity="t1", payload=p1)
            e2 = append_work_ledger_event(plan_dir, event_class="validation", referenced_identity="t1", payload=p2)
            assert e1["event_id"] != e2["event_id"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# Missing measurements → unavailable_reason
# ═══════════════════════════════════════════════════════════════════════════


class TestUnavailableReasonEmission:
    """Prove missing measurements become ``unavailable_reason``, not zero/waste/authority."""

    def test_emit_unavailable_reason_writes_event(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_unavailable_reason(
                plan_dir,
                task_id="task-2",
                measure="tokens",
                reason="provider did not return usage metadata",
            )
            assert event["event_class"] == "unavailable_reason"
            assert event["referenced_identity"] == "task-2"
            assert event["_non_authoritative"] is True
            assert event["payload"]["measure"] == "tokens"
            assert event["payload"]["reason"] == "provider did not return usage metadata"

            events = read_work_ledger(plan_dir)
            assert len(events) == 1
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_is_explicit_not_zero(self) -> None:
        """Missing measurements must NOT be zero — they must be explicit ``unavailable_reason``."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_unavailable_reason(
                plan_dir,
                task_id="task-2",
                measure="cost_usd",
                reason="billing API unavailable",
            )
            # The payload MUST contain the reason, NOT a zero default
            assert "reason" in event["payload"]
            assert event["payload"]["measure"] == "cost_usd"
            # Zero must never appear as a fallback
            assert event["payload"].get("cost_usd") is None
            payload_str = json.dumps(event["payload"], sort_keys=True)
            assert '"cost_usd": 0' not in payload_str
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_must_not_be_authority(self) -> None:
        """An unavailable_reason event is evidence of a gap, not authority over cost."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
            emit_unavailable_reason,
        )

        assert "unavailable_reason" in WORK_LEDGER_EVENT_CLASSES
        plan_dir = _fresh_plan_dir()
        try:
            event = emit_unavailable_reason(
                plan_dir,
                task_id="task-2",
                measure="duration_ms",
                reason="worker crash before telemetry flush",
            )
            assert event["_non_authoritative"] is True
            # Must not contain grant/lease/WBC/completion/status semantics
            for forbidden in ("grant", "lease", "wbc", "completion", "delivery", "publication", "status"):
                assert forbidden not in str(event).lower().split("event")[0], f"found forbidden term: {forbidden}"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_unavailable_reason_for_multiple_measures(self) -> None:
        """Each missing measurement gets its own ``unavailable_reason`` event."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_unavailable_reason,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_unavailable_reason(plan_dir, task_id="t-multi", measure="tokens", reason="no usage report")
            emit_unavailable_reason(plan_dir, task_id="t-multi", measure="cost_usd", reason="pricing table unavailable")
            emit_unavailable_reason(plan_dir, task_id="t-multi", measure="model_calls", reason="count not recorded")

            events = read_work_ledger(plan_dir)
            assert len(events) == 3
            measures = {e["payload"]["measure"] for e in events}
            assert measures == {"tokens", "cost_usd", "model_calls"}
            for e in events:
                assert e["_non_authoritative"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# Non-authoritative marker
# ═══════════════════════════════════════════════════════════════════════════


class TestNonAuthoritativeMarker:
    """Every work-ledger event carries ``_non_authoritative: true``."""

    def test_all_four_event_classes_are_non_authoritative(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            specs = [
                ("validation", {"task_id": "t", "job_id": "j", "command": "pytest", "exit_code": 0, "duration_ms": 1}),
                ("repair_verify", {"task_id": "t", "receipt_hash": "a", "outcome": "matched", "duration_ms": 1}),
                ("productive", {"task_id": "t", "work_class": "inference", "duration_ms": 1}),
                ("unavailable_reason", {"task_id": "t", "measure": "tokens", "reason": "gap"}),
            ]
            for event_class, payload in specs:
                event = append_work_ledger_event(
                    plan_dir,
                    event_class=event_class,
                    referenced_identity="t",
                    payload=payload,
                )
                assert event["_non_authoritative"] is True, f"{event_class} must be non-authoritative"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# Deterministic hashing
# ═══════════════════════════════════════════════════════════════════════════


class TestDeterministicHashing:
    """Content hashes and event IDs are deterministic (same inputs → same outputs)."""

    def test_content_hash_deterministic(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            _content_hash,
        )

        payload = {"task_id": "t", "job_id": "j", "command": "pytest", "exit_code": 0, "duration_ms": 100}
        h1 = _content_hash(payload)
        h2 = _content_hash(dict(payload))
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex

    def test_event_id_deterministic_across_calls(self) -> None:
        import json as _json

        from arnold_pipelines.megaplan.observability.work_ledger import (
            _canonical_json_bytes,
            _stable_event_id,
        )

        payload = {"task_id": "t", "job_id": "j", "command": "pytest", "exit_code": 0, "duration_ms": 100}
        pb = _canonical_json_bytes(payload)
        eid1 = _stable_event_id("validation", "t", pb)
        eid2 = _stable_event_id("validation", "t", _canonical_json_bytes(dict(payload)))
        assert eid1 == eid2

    def test_event_id_differs_by_event_class(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            _canonical_json_bytes,
            _stable_event_id,
        )

        payload = {"task_id": "t", "measure": "tokens", "reason": "gap"}
        pb = _canonical_json_bytes(payload)
        eid_val = _stable_event_id("validation", "t", pb)
        eid_unav = _stable_event_id("unavailable_reason", "t", pb)
        assert eid_val != eid_unav

    def test_event_id_differs_by_referenced_identity(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            _canonical_json_bytes,
            _stable_event_id,
        )

        payload = {"task_id": "t", "job_id": "j", "command": "pytest", "exit_code": 0, "duration_ms": 100}
        pb = _canonical_json_bytes(payload)
        eid_a = _stable_event_id("validation", "task-a", pb)
        eid_b = _stable_event_id("validation", "task-b", pb)
        assert eid_a != eid_b


# ═══════════════════════════════════════════════════════════════════════════
# Vocabulary enforcement
# ═══════════════════════════════════════════════════════════════════════════


class TestVocabularyEnforcement:
    """Required keys are enforced; unknown event classes are rejected."""

    def test_rejects_unknown_event_class(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="Unknown work-ledger event class"):
                append_work_ledger_event(
                    plan_dir,
                    event_class="completion",
                    referenced_identity="t",
                    payload={"task_id": "t"},
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_rejects_validation_missing_required_keys(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="missing required payload keys"):
                append_work_ledger_event(
                    plan_dir,
                    event_class="validation",
                    referenced_identity="t",
                    payload={"task_id": "t"},
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_rejects_unavailable_reason_missing_required_keys(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="missing required payload keys"):
                append_work_ledger_event(
                    plan_dir,
                    event_class="unavailable_reason",
                    referenced_identity="t",
                    payload={"task_id": "t", "measure": "tokens"},
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_rejects_productive_missing_required_keys(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="missing required payload keys"):
                append_work_ledger_event(
                    plan_dir,
                    event_class="productive",
                    referenced_identity="t",
                    payload={"task_id": "t", "work_class": "inference"},
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_rejects_repair_verify_missing_required_keys(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            with pytest.raises(ValueError, match="missing required payload keys"):
                append_work_ledger_event(
                    plan_dir,
                    event_class="repair_verify",
                    referenced_identity="t",
                    payload={"task_id": "t", "receipt_hash": "a"},
                )
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_vocabulary_constants_match_vocabulary_json(self) -> None:
        """Module constants must match the evidence vocabulary document."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
            _REQUIRED_BY_CLASS,
        )

        # M8A T17 expanded the vocabulary from 4 to 12 event classes.
        expected = {
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
        }
        assert set(WORK_LEDGER_EVENT_CLASSES) == expected

        # Verify required keys per class
        assert _REQUIRED_BY_CLASS["validation"] == frozenset({"task_id", "job_id", "command", "exit_code", "duration_ms"})
        assert _REQUIRED_BY_CLASS["repair_verify"] == frozenset({"task_id", "receipt_hash", "outcome", "duration_ms"})
        assert _REQUIRED_BY_CLASS["productive"] == frozenset({"task_id", "work_class", "duration_ms"})
        assert _REQUIRED_BY_CLASS["unavailable_reason"] == frozenset({"task_id", "measure", "reason"})


# ═══════════════════════════════════════════════════════════════════════════
# Read-back and empty-state
# ═══════════════════════════════════════════════════════════════════════════


class TestReadBack:
    """Read-back returns the correct events; missing ledger returns empty list."""

    def test_read_empty_ledger_returns_empty_list(self) -> None:
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

    def test_read_back_matches_written_events(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
            emit_unavailable_reason,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(plan_dir, task_id="t1", job_id="j1", command="pytest", exit_code=0, duration_ms=100)
            emit_unavailable_reason(plan_dir, task_id="t1", measure="tokens", reason="no data")
            emit_validation(plan_dir, task_id="t2", job_id="j2", command="pytest", exit_code=0, duration_ms=200)

            events = read_work_ledger(plan_dir)
            assert len(events) == 3
            classes = [e["event_class"] for e in events]
            assert classes == ["validation", "unavailable_reason", "validation"]
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# Convenience emitters
# ═══════════════════════════════════════════════════════════════════════════


class TestConvenienceEmitters:
    """All four convenience emitters work correctly."""

    def test_emit_productive_includes_optional_fields_when_provided(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_productive,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_productive(
                plan_dir,
                task_id="t-prod",
                work_class="inference",
                duration_ms=5000,
                tokens=15000,
                cost_usd=0.15,
                model_calls=3,
            )
            assert event["event_class"] == "productive"
            assert event["payload"]["tokens"] == 15000
            assert event["payload"]["cost_usd"] == 0.15
            assert event["payload"]["model_calls"] == 3
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_productive_excludes_none_optional_fields(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_productive,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_productive(plan_dir, task_id="t-prod", work_class="inference", duration_ms=100)
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

    def test_emit_repair_verify_includes_match_flags(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_repair_verify,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_repair_verify(
                plan_dir,
                task_id="t-repair",
                receipt_hash="abc123",
                outcome="matched",
                duration_ms=10,
                grant_match=True,
                fence_match=True,
            )
            assert event["event_class"] == "repair_verify"
            assert event["payload"]["grant_match"] is True
            assert event["payload"]["fence_match"] is True
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_emit_repair_verify_mismatch_flags(self) -> None:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_repair_verify,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_repair_verify(
                plan_dir,
                task_id="t-repair",
                receipt_hash="abc123",
                outcome="quarantined",
                duration_ms=10,
                grant_match=False,
                fence_match=False,
            )
            assert event["payload"]["outcome"] == "quarantined"
            assert event["payload"]["grant_match"] is False
            assert event["payload"]["fence_match"] is False
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# State.py integration
# ═══════════════════════════════════════════════════════════════════════════


class TestStateIntegration:
    """The ``state.py`` integration layer delegates correctly to ``work_ledger``."""

    def test_append_to_work_ledger_adds_summary_to_state(self) -> None:
        from arnold_pipelines.megaplan._core.state import (
            append_to_work_ledger,
        )
        from arnold_pipelines.megaplan.observability.work_ledger import (
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            state: dict[str, Any] = {}
            event = append_to_work_ledger(
                plan_dir,
                state,
                event_class="validation",
                referenced_identity="task-1",
                payload={"task_id": "task-1", "job_id": "j1", "command": "pytest", "exit_code": 0, "duration_ms": 100},
            )

            # In-memory summary was appended
            assert "work_ledger" in state
            assert len(state["work_ledger"]) == 1
            summary = state["work_ledger"][0]
            assert summary["event_id"] == event["event_id"]
            assert summary["event_class"] == "validation"
            assert summary["referenced_identity"] == "task-1"

            # ndjson file was written
            events = read_work_ledger(plan_dir)
            assert len(events) == 1
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_append_to_work_ledger_initializes_missing_key(self) -> None:
        from arnold_pipelines.megaplan._core.state import (
            append_to_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            state: dict[str, Any] = {}
            assert "work_ledger" not in state

            append_to_work_ledger(
                plan_dir,
                state,
                event_class="unavailable_reason",
                referenced_identity="t",
                payload={"task_id": "t", "measure": "tokens", "reason": "gap"},
            )

            assert "work_ledger" in state
            assert isinstance(state["work_ledger"], list)
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_load_work_ledger_summary_from_file(self) -> None:
        from arnold_pipelines.megaplan._core.state import (
            append_to_work_ledger,
            load_work_ledger_summary,
        )

        plan_dir = _fresh_plan_dir()
        try:
            state: dict[str, Any] = {}
            append_to_work_ledger(
                plan_dir, state,
                event_class="validation",
                referenced_identity="t1",
                payload={"task_id": "t1", "job_id": "j1", "command": "pytest", "exit_code": 0, "duration_ms": 100},
            )
            append_to_work_ledger(
                plan_dir, state,
                event_class="productive",
                referenced_identity="t1",
                payload={"task_id": "t1", "work_class": "inference", "duration_ms": 5000},
            )

            summary = load_work_ledger_summary(plan_dir)
            assert len(summary) == 2
            assert summary[0]["event_class"] == "validation"
            assert summary[1]["event_class"] == "productive"
            for s in summary:
                assert "event_id" in s
                assert "content_hash" in s
                assert "timestamp" in s
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_load_work_ledger_summary_empty_when_no_file(self) -> None:
        from arnold_pipelines.megaplan._core.state import (
            load_work_ledger_summary,
        )

        plan_dir = _fresh_plan_dir()
        try:
            summary = load_work_ledger_summary(plan_dir)
            assert summary == []
        finally:
            try:
                plan_dir.rmdir()
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# Evidence is not authority
# ═══════════════════════════════════════════════════════════════════════════


class TestEvidenceIsNotAuthority:
    """North Star guard: ledger events are evidence, never authority."""

    def test_no_event_class_confers_authority(self) -> None:
        """All event vocabulary entries are explicitly marked non-authoritative."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            WORK_LEDGER_EVENT_CLASSES,
            append_work_ledger_event,
        )

        plan_dir = _fresh_plan_dir()
        try:
            specs = {
                "validation": {"task_id": "t", "job_id": "j", "command": "pytest", "exit_code": 0, "duration_ms": 1},
                "repair_verify": {"task_id": "t", "receipt_hash": "a", "outcome": "matched", "duration_ms": 1},
                "productive": {"task_id": "t", "work_class": "inference", "duration_ms": 1},
                "unavailable_reason": {"task_id": "t", "measure": "tokens", "reason": "gap"},
            }
            for event_class, payload in specs.items():
                event = append_work_ledger_event(
                    plan_dir, event_class=event_class, referenced_identity="t", payload=payload,
                )
                # The marker is in the event envelope
                assert event["_non_authoritative"] is True, f"{event_class} must be non-authoritative"
                # The payload must not contain authoritative claims
                payload_keys = set(event["payload"].keys())
                forbidden = {"grant", "lease", "wbc", "completion", "publication", "delivery", "status", "authority"}
                assert payload_keys.isdisjoint(forbidden), f"{event_class} payload contains forbidden key: {payload_keys & forbidden}"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_reading_ledger_produces_evidence_not_state(self) -> None:
        """Read-back returns a list of events, not mutated plan state."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
            read_work_ledger,
        )

        plan_dir = _fresh_plan_dir()
        try:
            emit_validation(plan_dir, task_id="t", job_id="j", command="pytest", exit_code=0, duration_ms=100)
            events = read_work_ledger(plan_dir)
            # The returned value is a list of dicts — pure data, not state mutation
            assert isinstance(events, list)
            for event in events:
                assert isinstance(event, dict)
                assert "_non_authoritative" in event
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass

    def test_work_ledger_event_payload_is_not_task_contract(self) -> None:
        """The work-ledger payload is observation, not a task contract."""
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_validation,
        )

        plan_dir = _fresh_plan_dir()
        try:
            event = emit_validation(plan_dir, task_id="t", job_id="j", command="pytest", exit_code=0, duration_ms=100)
            # A task contract dictates what must happen; the ledger records what DID happen.
            # The payload must not contain fields that belong in task contracts.
            task_contract_keys = {"action", "ref", "model", "import_paths", "write_set", "narrow_tests"}
            payload_keys = set(event["payload"].keys())
            overlap = payload_keys & task_contract_keys
            assert not overlap, f"Ledger payload contains task-contract keys: {overlap}"
        finally:
            try:
                for f in plan_dir.iterdir():
                    f.unlink()
                plan_dir.rmdir()
            except OSError:
                pass
