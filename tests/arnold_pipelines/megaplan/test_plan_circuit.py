"""Tests for plan_circuit — M8A T8.

Covers:
- FailureSignature equivalence (same fields → equivalent; different → not)
- PlanCircuit state machine (record, threshold, circuit_open after threshold)
- Two equivalent worker_budget_exhausted occurrences open circuit before third retry
- Unrelated failure classes do NOT collide
- Unrelated task/batch/attempt identities do NOT collide
- normalize_failure_signature with various error shapes
- classify_with_circuit integration (circuit_open halt kind)
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.orchestration.plan_circuit import (
    DEFAULT_CIRCUIT_THRESHOLD,
    CircuitDecision,
    FailureSignature,
    PlanCircuit,
    normalize_failure_signature,
)
from arnold_pipelines.megaplan.orchestration.phase_result import ExitKind
from arnold_pipelines.megaplan.orchestration.recovery_policy import (
    RecoveryDecision,
    RecoveryPolicy,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _err(**kw) -> SimpleNamespace:
    return SimpleNamespace(**kw)


def _worker_budget_exhausted_err(
    task_id: str = "T7",
    batch_id: str = "B3",
    attempt_id: str = "A2",
) -> SimpleNamespace:
    """Build an error that normalizes to 'worker_budget_exhausted'."""
    return _err(
        halt_kind="worker_budget_exhausted",
        message=f"Task {task_id} exhausted 90 iterations",
        exit_kind=ExitKind.internal_error,
    )


def _context_exhausted_err() -> SimpleNamespace:
    return _err(
        exit_kind=ExitKind.context_exhausted,
        message="model ran out of room in the model's context window",
    )


def _blocker_payload(reason: str = "budget_exhausted") -> dict:
    return {"kind": "budget_exhausted", "reason": reason, "task_id": "T7", "iterations": 90}


def _compute_digest(payload: dict) -> str:
    import json

    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# FailureSignature equivalence
# ---------------------------------------------------------------------------


class TestFailureSignatureEquivalence:
    """FailureSignature must be hashable and equivalent only when all fields match."""

    def test_identical_signatures_are_equal(self):
        s1 = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker_digest="abc123",
            provider="anthropic",
            ref_metadata="abc123def",
            fence="fence-v1",
        )
        s2 = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker_digest="abc123",
            provider="anthropic",
            ref_metadata="abc123def",
            fence="fence-v1",
        )
        assert s1 == s2
        assert hash(s1) == hash(s2)
        assert s1.to_key() == s2.to_key()

    def test_different_class_not_equal(self):
        s1 = FailureSignature(failure_class="worker_budget_exhausted")
        s2 = FailureSignature(failure_class="context_exhausted")
        assert s1 != s2
        assert hash(s1) != hash(s2)

    def test_different_task_id_not_equal(self):
        s1 = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        s2 = FailureSignature(failure_class="worker_budget_exhausted", task_id="T12")
        assert s1 != s2
        assert hash(s1) != hash(s2)

    def test_different_blocker_digest_not_equal(self):
        s1 = FailureSignature(
            failure_class="worker_budget_exhausted", blocker_digest="abc123"
        )
        s2 = FailureSignature(
            failure_class="worker_budget_exhausted", blocker_digest="def456"
        )
        assert s1 != s2
        assert hash(s1) != hash(s2)

    def test_different_provider_not_equal(self):
        s1 = FailureSignature(
            failure_class="worker_budget_exhausted", provider="anthropic"
        )
        s2 = FailureSignature(failure_class="worker_budget_exhausted", provider="openai")
        assert s1 != s2

    def test_different_fence_not_equal(self):
        s1 = FailureSignature(failure_class="worker_budget_exhausted", fence="fence-v1")
        s2 = FailureSignature(failure_class="worker_budget_exhausted", fence="fence-v2")
        assert s1 != s2

    def test_none_fields_treated_equivalently(self):
        """None and empty string are NOT equivalent — they are distinct."""
        s1 = FailureSignature(failure_class="worker_budget_exhausted", task_id=None)
        s2 = FailureSignature(failure_class="worker_budget_exhausted", task_id="")
        assert s1 != s2  # None != ""

    def test_dict_usable_as_key(self):
        """FailureSignature can be used as a dict key."""
        sig = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        d = {sig: 1}
        assert d[sig] == 1
        same = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        assert d[same] == 1

    def test_frozen_immutable(self):
        sig = FailureSignature(failure_class="worker_budget_exhausted")
        with pytest.raises(Exception):
            sig.failure_class = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PlanCircuit state machine
# ---------------------------------------------------------------------------


class TestPlanCircuitStateMachine:
    """PlanCircuit must correctly track occurrences and open circuits."""

    def test_first_occurrence_allows_retry(self):
        circuit = PlanCircuit()
        sig = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        decision = circuit.record_failure(sig)
        assert decision.action == "allow_retry"
        assert decision.occurrence_count == 1
        assert not decision.is_open
        assert decision.may_retry

    def test_second_occurrence_opens_circuit_at_default_threshold(self):
        circuit = PlanCircuit()
        sig = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")

        # First occurrence
        d1 = circuit.record_failure(sig)
        assert d1.action == "allow_retry"
        assert d1.occurrence_count == 1

        # Second occurrence — circuit opens (threshold=2)
        d2 = circuit.record_failure(sig)
        assert d2.action == "open_circuit"
        assert d2.occurrence_count == 2
        assert d2.is_open
        assert not d2.may_retry

    def test_third_occurrence_reports_circuit_open(self):
        """After circuit opens, further occurrences report 'circuit_open'."""
        circuit = PlanCircuit()
        sig = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")

        circuit.record_failure(sig)  # 1: allow_retry
        circuit.record_failure(sig)  # 2: open_circuit
        d3 = circuit.record_failure(sig)  # 3: circuit_open

        assert d3.action == "circuit_open"
        assert d3.is_open
        assert not d3.may_retry
        # Occurrence count should not increment beyond threshold on circuit_open reports
        assert circuit.occurrence_count(sig) == DEFAULT_CIRCUIT_THRESHOLD

    def test_is_circuit_open_after_threshold(self):
        circuit = PlanCircuit()
        sig = FailureSignature(failure_class="worker_budget_exhausted")
        assert not circuit.is_circuit_open(sig)

        circuit.record_failure(sig)
        assert not circuit.is_circuit_open(sig)

        circuit.record_failure(sig)
        assert circuit.is_circuit_open(sig)

    def test_custom_threshold(self):
        circuit = PlanCircuit(threshold=3)
        sig = FailureSignature(failure_class="worker_budget_exhausted")

        d1 = circuit.record_failure(sig)
        assert d1.action == "allow_retry"
        d2 = circuit.record_failure(sig)
        assert d2.action == "allow_retry"
        d3 = circuit.record_failure(sig)
        assert d3.action == "open_circuit"
        assert d3.occurrence_count == 3


# ---------------------------------------------------------------------------
# Unrelated classes / identities do NOT collide
# ---------------------------------------------------------------------------


class TestCircuitNoCollision:
    """Different failure classes or task identities must NOT collide."""

    def test_different_classes_independent_circuits(self):
        """worker_budget_exhausted and context_exhausted track separately."""
        circuit = PlanCircuit()
        sig_wbe = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        sig_ce = FailureSignature(failure_class="context_exhausted", task_id="T7")

        # worker_budget_exhausted first occurrence
        d1 = circuit.record_failure(sig_wbe)
        assert d1.action == "allow_retry"

        # context_exhausted first occurrence — independent circuit
        d2 = circuit.record_failure(sig_ce)
        assert d2.action == "allow_retry"
        assert d2.occurrence_count == 1

        # worker_budget_exhausted second occurrence opens its circuit
        d3 = circuit.record_failure(sig_wbe)
        assert d3.action == "open_circuit"
        assert circuit.is_circuit_open(sig_wbe)

        # context_exhausted still not open
        assert not circuit.is_circuit_open(sig_ce)

    def test_different_task_ids_independent_circuits(self):
        """T7 and T12 with same class are different identities — no collision."""
        circuit = PlanCircuit()
        sig_t7 = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        sig_t12 = FailureSignature(
            failure_class="worker_budget_exhausted", task_id="T12"
        )

        circuit.record_failure(sig_t7)  # T7: 1 occurrence
        circuit.record_failure(sig_t12)  # T12: 1 occurrence (independent)

        # T7 still only has 1 occurrence
        assert circuit.occurrence_count(sig_t7) == 1
        assert circuit.occurrence_count(sig_t12) == 1
        assert not circuit.is_circuit_open(sig_t7)
        assert not circuit.is_circuit_open(sig_t12)

    def test_different_batch_ids_independent(self):
        circuit = PlanCircuit()
        sig_b3 = FailureSignature(
            failure_class="worker_budget_exhausted", task_id="T7", batch_id="B3"
        )
        sig_b4 = FailureSignature(
            failure_class="worker_budget_exhausted", task_id="T7", batch_id="B4"
        )

        circuit.record_failure(sig_b3)
        circuit.record_failure(sig_b3)  # B3 circuit opens
        assert circuit.is_circuit_open(sig_b3)

        # B4 is independent — still just 1 occurrence
        assert circuit.occurrence_count(sig_b4) == 0  # never recorded


# ---------------------------------------------------------------------------
# Two equivalent worker_budget_exhausted → circuit opens before third retry
# ---------------------------------------------------------------------------


class TestWorkerBudgetExhaustedCircuit:
    """End-to-end: two equivalent worker_budget_exhausted occurrences
    open the circuit before a third blind retry."""

    def test_two_equivalent_open_circuit_before_third_retry(self):
        """The core locked decision: two occurrences → circuit open.

        Third call returns circuit_open — no third blind retry is allowed.
        """
        circuit = PlanCircuit()
        blocker = _blocker_payload()
        digest = _compute_digest(blocker)

        sig = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker_digest=digest,
            provider="anthropic",
            ref_metadata="abc123def",
            fence="fence-v1",
        )

        # First occurrence — retry allowed
        d1 = circuit.record_failure(sig)
        assert d1.action == "allow_retry"
        assert d1.occurrence_count == 1
        assert not circuit.is_circuit_open(sig)

        # Second occurrence — circuit opens (BEFORE a third retry)
        d2 = circuit.record_failure(sig)
        assert d2.action == "open_circuit"
        assert d2.occurrence_count == 2
        assert circuit.is_circuit_open(sig)

        # Third call — circuit already open, no retry
        d3 = circuit.record_failure(sig)
        assert d3.action == "circuit_open"
        assert not d3.may_retry

    def test_equivalent_blocker_digests_collide(self):
        """Same blocker payload → same digest → same signature → collision."""
        circuit = PlanCircuit()
        blocker = _blocker_payload()
        digest = _compute_digest(blocker)

        sig1 = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            blocker_digest=digest,
        )
        sig2 = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            blocker_digest=digest,
        )

        assert sig1 == sig2
        circuit.record_failure(sig1)
        d2 = circuit.record_failure(sig2)
        assert d2.action == "open_circuit"

    def test_different_blocker_digests_no_collision(self):
        """Different blocker payloads → different digests → no collision."""
        circuit = PlanCircuit()
        b1 = _blocker_payload("reason_a")
        b2 = _blocker_payload("reason_b")

        sig1 = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            blocker_digest=_compute_digest(b1),
        )
        sig2 = FailureSignature(
            failure_class="worker_budget_exhausted",
            task_id="T7",
            blocker_digest=_compute_digest(b2),
        )

        assert sig1 != sig2
        circuit.record_failure(sig1)
        assert circuit.occurrence_count(sig2) == 0
        assert not circuit.is_circuit_open(sig2)


# ---------------------------------------------------------------------------
# normalize_failure_signature
# ---------------------------------------------------------------------------


class TestNormalizeFailureSignature:
    """normalize_failure_signature must extract correct fields from error shapes."""

    def test_from_halt_kind(self):
        err = _err(halt_kind="worker_budget_exhausted")
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "worker_budget_exhausted"

    def test_from_error_kind(self):
        err = _err(error_kind="rate_limit", exit_kind=ExitKind.external_error)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "rate_limit"

    def test_from_exit_kind_context_exhausted(self):
        err = _err(exit_kind=ExitKind.context_exhausted)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "context_exhausted"

    def test_from_exit_kind_blocked_by_quality(self):
        err = _err(exit_kind=ExitKind.blocked_by_quality)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "blocked_by_quality"

    def test_from_exit_kind_blocked_by_prereq(self):
        err = _err(exit_kind=ExitKind.blocked_by_prereq)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "blocked_by_prereq"

    def test_from_exit_kind_timeout(self):
        err = _err(exit_kind=ExitKind.timeout)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "timeout"

    def test_from_exit_kind_internal_error(self):
        err = _err(exit_kind=ExitKind.internal_error)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "internal_error"

    def test_from_exit_kind_malformed_model_output(self):
        err = _err(exit_kind=ExitKind.malformed_model_output)
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "malformed_model_output"

    def test_explicit_failure_class_override(self):
        err = _err(exit_kind=ExitKind.internal_error)
        sig = normalize_failure_signature(err, failure_class="worker_budget_exhausted")
        assert sig.failure_class == "worker_budget_exhausted"

    def test_includes_all_identity_fields(self):
        err = _err(halt_kind="worker_budget_exhausted")
        blocker = _blocker_payload()
        sig = normalize_failure_signature(
            err,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            ref_metadata="abc123def",
            fence="fence-v1",
        )
        assert sig.task_id == "T7"
        assert sig.batch_id == "B3"
        assert sig.attempt_id == "A2"
        assert sig.blocker_digest == _compute_digest(blocker)
        assert sig.provider == "anthropic"
        assert sig.ref_metadata == "abc123def"
        assert sig.fence == "fence-v1"

    def test_blocker_none_gives_none_digest(self):
        sig = normalize_failure_signature(
            _err(halt_kind="worker_budget_exhausted"), blocker=None
        )
        assert sig.blocker_digest is None

    def test_provider_from_external_error_subobject(self):
        ext = _err(provider="openai")
        err = _err(halt_kind="worker_budget_exhausted", external_error=ext)
        sig = normalize_failure_signature(err)
        assert sig.provider == "openai"

    def test_explicit_provider_overrides_external_error(self):
        ext = _err(provider="openai")
        err = _err(halt_kind="worker_budget_exhausted", external_error=ext)
        sig = normalize_failure_signature(err, provider="anthropic")
        assert sig.provider == "anthropic"

    def test_unclassified_error_yields_unclassified(self):
        err = _err()  # no known fields
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "unclassified"

    def test_fallback_to_class_name(self):
        """When no known fields, falls back to __class__.__name__."""

        class CustomError(Exception):
            pass

        err = CustomError("something broke")
        sig = normalize_failure_signature(err)
        assert sig.failure_class == "CustomError"

    def test_fallback_objects_class_name(self):
        """SimpleNamespace with no known fields falls back to 'unclassified'."""
        err = _err(some_field="value")
        sig = normalize_failure_signature(err)
        # SimpleNamespace is a generic container — not a meaningful error class
        assert sig.failure_class == "unclassified"


# ---------------------------------------------------------------------------
# classify_with_circuit integration
# ---------------------------------------------------------------------------


class TestClassifyWithCircuit:
    """classify_with_circuit must halt with circuit_open when circuit is open."""

    def test_first_occurrence_delegates_to_classify(self):
        policy = RecoveryPolicy()
        circuit = PlanCircuit()
        err = _worker_budget_exhausted_err()

        decision = policy.classify_with_circuit(
            err,
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            phase="execute",
        )
        # First occurrence — circuit not open, delegates to classify.
        # worker_budget_exhausted maps to internal_error (escalate in classify).
        assert decision.action == "escalate"
        assert decision.halt_kind is None

    def test_second_occurrence_opens_circuit(self):
        policy = RecoveryPolicy()
        circuit = PlanCircuit()
        err = _worker_budget_exhausted_err()
        blocker = _blocker_payload()

        # First — allowed
        d1 = policy.classify_with_circuit(
            err,
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )
        assert d1.action == "escalate"  # delegated to classify

        # Second same error — circuit opens
        d2 = policy.classify_with_circuit(
            err,
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )
        assert d2.action == "halt"
        assert d2.halt_kind == "circuit_open"
        assert "Circuit open for failure class" in d2.reason

    def test_third_call_reports_circuit_open_again(self):
        policy = RecoveryPolicy()
        circuit = PlanCircuit()
        err = _worker_budget_exhausted_err()
        blocker = _blocker_payload()
        kwargs = dict(
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )

        policy.classify_with_circuit(err, **kwargs)  # 1: allowed
        policy.classify_with_circuit(err, **kwargs)  # 2: circuit opens
        d3 = policy.classify_with_circuit(err, **kwargs)  # 3: circuit_open

        assert d3.action == "halt"
        assert d3.halt_kind == "circuit_open"

    def test_different_task_no_collision_in_circuit(self):
        """T7 circuit open does NOT block T12 from getting its own classification."""
        policy = RecoveryPolicy()
        circuit = PlanCircuit()
        blocker = _blocker_payload()

        # T7: hit twice → circuit open
        err_t7 = _worker_budget_exhausted_err(task_id="T7")
        kwargs_t7 = dict(
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )
        policy.classify_with_circuit(err_t7, **kwargs_t7)
        d_t7_open = policy.classify_with_circuit(err_t7, **kwargs_t7)
        assert d_t7_open.action == "halt"
        assert d_t7_open.halt_kind == "circuit_open"

        # T12: first occurrence — should NOT be blocked by T7's circuit
        err_t12 = _worker_budget_exhausted_err(task_id="T12")
        kwargs_t12 = dict(
            layer="phase",
            circuit=circuit,
            task_id="T12",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )
        d_t12 = policy.classify_with_circuit(err_t12, **kwargs_t12)
        # T12 gets its own classification — not blocked by T7's circuit
        assert d_t12.action == "escalate"
        assert d_t12.halt_kind is None

    def test_different_class_no_collision_in_circuit(self):
        """context_exhausted does NOT collide with worker_budget_exhausted circuit."""
        policy = RecoveryPolicy()
        circuit = PlanCircuit()
        blocker = _blocker_payload()

        # worker_budget_exhausted: hit twice → circuit open
        err_wbe = _worker_budget_exhausted_err()
        kwargs_wbe = dict(
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )
        policy.classify_with_circuit(err_wbe, **kwargs_wbe)
        policy.classify_with_circuit(err_wbe, **kwargs_wbe)

        # context_exhausted: first occurrence — should NOT be blocked
        err_ce = _context_exhausted_err()
        d_ce = policy.classify_with_circuit(
            err_ce,
            layer="phase",
            circuit=circuit,
            task_id="T7",
            context_retries_used=0,
            phase="plan",
        )
        # context_exhausted with 0 used → retry_fresh
        assert d_ce.action == "retry_fresh"
        assert d_ce.budget_kind == "context"

    def test_same_error_different_fence_no_collision(self):
        """Different fence → different signature → no collision."""
        policy = RecoveryPolicy()
        circuit = PlanCircuit()
        err = _worker_budget_exhausted_err()
        blocker = _blocker_payload()

        # fence-v1: hit twice → circuit open
        kwargs_v1 = dict(
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v1",
            phase="execute",
        )
        policy.classify_with_circuit(err, **kwargs_v1)
        d_v1_open = policy.classify_with_circuit(err, **kwargs_v1)
        assert d_v1_open.halt_kind == "circuit_open"

        # fence-v2: first occurrence — independent
        kwargs_v2 = dict(
            layer="phase",
            circuit=circuit,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            fence="fence-v2",
            phase="execute",
        )
        d_v2 = policy.classify_with_circuit(err, **kwargs_v2)
        assert d_v2.action == "escalate"
        assert d_v2.halt_kind is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPlanCircuitEdgeCases:
    """Edge cases for PlanCircuit behavior."""

    def test_multiple_signatures_independent(self):
        circuit = PlanCircuit()
        sig_a = FailureSignature(failure_class="class_a")
        sig_b = FailureSignature(failure_class="class_b")

        circuit.record_failure(sig_a)
        circuit.record_failure(sig_a)  # A opens
        circuit.record_failure(sig_b)  # B: 1 occurrence

        assert circuit.is_circuit_open(sig_a)
        assert not circuit.is_circuit_open(sig_b)
        assert circuit.occurrence_count(sig_a) == 2
        assert circuit.occurrence_count(sig_b) == 1

    def test_occurrence_count_never_seen(self):
        circuit = PlanCircuit()
        sig = FailureSignature(failure_class="never_seen")
        assert circuit.occurrence_count(sig) == 0

    def test_threshold_zero_opens_immediately(self):
        """threshold=0 means circuit opens on first occurrence."""
        circuit = PlanCircuit(threshold=0)
        sig = FailureSignature(failure_class="any")
        d = circuit.record_failure(sig)
        assert d.action == "open_circuit"
        assert d.occurrence_count == 1

    def test_threshold_one_opens_on_first(self):
        circuit = PlanCircuit(threshold=1)
        sig = FailureSignature(failure_class="any")
        d = circuit.record_failure(sig)
        assert d.action == "open_circuit"
        assert d.occurrence_count == 1

    def test_circuit_decision_frozen(self):
        sig = FailureSignature(failure_class="test")
        d = CircuitDecision(action="allow_retry", signature=sig, occurrence_count=1)
        with pytest.raises(Exception):
            d.action = "open_circuit"  # type: ignore[misc]
