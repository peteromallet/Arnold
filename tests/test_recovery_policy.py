"""Tests for RecoveryPolicy.classify (M4 T16 / Step 11a).

Covers every branch:
- context_exhausted: retry_fresh while under budget, halt(context_retry_exhausted) at cap
- transient external: retry_transient under budget, halt(external_retry_exhausted) at cap
- permanent external (auth/billing/rate_limit/etc.): halt(permanent_external)
- blocked_by_quality / blocked_by_prereq: retry_fresh / halt(blocked_retry_exhausted)
- timeout / internal_error: escalate
- unclassified: halt(unclassified)

Plus a non-planning-consumer test: classify a transient WITHOUT importing
megaplan.auto.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from megaplan.orchestration.phase_result import ExitKind
from megaplan.orchestration.recovery_policy import (
    DEFAULT_MAX_BLOCKED_RETRIES,
    DEFAULT_MAX_CONTEXT_RETRIES,
    DEFAULT_MAX_EXTERNAL_RETRIES,
    RecoveryDecision,
    RecoveryPolicy,
)


def _err(**kw) -> SimpleNamespace:
    return SimpleNamespace(**kw)


# ---------------------------------------------------------------------------
# Context exhaustion
# ---------------------------------------------------------------------------


def test_context_exhausted_retry_under_budget():
    p = RecoveryPolicy()
    d = p.classify(_err(exit_kind=ExitKind.context_exhausted), "phase", context_retries_used=0)
    assert d.action == "retry_fresh"
    assert d.budget_delta == 1
    assert d.budget_kind == "context"
    assert d.halt_kind is None


def test_context_exhausted_halt_at_cap():
    p = RecoveryPolicy()
    d = p.classify(
        _err(exit_kind=ExitKind.context_exhausted),
        "phase",
        context_retries_used=DEFAULT_MAX_CONTEXT_RETRIES,
    )
    assert d.action == "halt"
    assert d.halt_kind == "context_retry_exhausted"
    assert d.budget_delta == 0


def test_context_exhausted_via_message_substring():
    err = _err(message="model ran out of room in the model's context window")
    d = RecoveryPolicy().classify(err, "phase", context_retries_used=0)
    assert d.action == "retry_fresh"
    assert d.budget_kind == "context"


# ---------------------------------------------------------------------------
# Transient external
# ---------------------------------------------------------------------------


def _transient_err() -> SimpleNamespace:
    # Mirrors the auto._is_retryable_external_error transient pattern.
    return _err(
        exit_kind=ExitKind.external_error,
        error_kind="stream_content_stall",
        error_layer="stream_content_stall",
        message="stream stalled",
        status_code=None,
        retry_after_s=None,
        provider_error_code="",
    )


def test_external_transient_retry_under_budget():
    p = RecoveryPolicy()
    d = p.classify(_transient_err(), "phase", phase="plan", external_retries_used=0)
    assert d.action == "retry_transient"
    assert d.budget_delta == 1
    assert d.budget_kind == "external"


def test_external_transient_halt_at_cap():
    p = RecoveryPolicy()
    d = p.classify(
        _transient_err(),
        "phase",
        phase="plan",
        external_retries_used=DEFAULT_MAX_EXTERNAL_RETRIES,
    )
    assert d.action == "halt"
    assert d.halt_kind == "external_retry_exhausted"


def test_external_permanent_kind_halts():
    err = _err(
        exit_kind=ExitKind.external_error,
        error_kind="auth",
        message="bad key",
    )
    d = RecoveryPolicy().classify(err, "phase", phase="plan")
    assert d.action == "halt"
    assert d.halt_kind == "permanent_external"


def test_external_rate_limit_halts():
    err = _err(
        exit_kind=ExitKind.external_error,
        error_kind="rate_limit",
        retry_after_s=30,
    )
    d = RecoveryPolicy().classify(err, "phase", phase="plan")
    assert d.action == "halt"
    assert d.halt_kind == "permanent_external"


def test_external_on_execute_phase_is_non_retryable():
    # execute is NOT in EXTERNAL_RETRYABLE_PHASES -> permanent.
    d = RecoveryPolicy().classify(_transient_err(), "phase", phase="execute")
    assert d.action == "halt"
    assert d.halt_kind == "permanent_external"


# ---------------------------------------------------------------------------
# Blocked-by-prereq / blocked-by-quality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [ExitKind.blocked_by_quality, ExitKind.blocked_by_prereq])
def test_blocked_retry_under_budget(kind):
    p = RecoveryPolicy()
    d = p.classify(_err(exit_kind=kind), "phase", blocked_retries_used=0)
    assert d.action == "retry_fresh"
    assert d.budget_kind == "blocked"
    assert d.budget_delta == 1


def test_blocked_halt_at_cap():
    p = RecoveryPolicy()
    d = p.classify(
        _err(exit_kind=ExitKind.blocked_by_quality),
        "phase",
        blocked_retries_used=DEFAULT_MAX_BLOCKED_RETRIES,
    )
    assert d.action == "halt"
    assert d.halt_kind == "blocked_retry_exhausted"


# ---------------------------------------------------------------------------
# Escalate (timeout / internal_error)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [ExitKind.timeout, ExitKind.internal_error])
def test_escalate_on_timeout_and_internal(kind):
    d = RecoveryPolicy().classify(_err(exit_kind=kind), "phase")
    assert d.action == "escalate"
    assert d.budget_delta == 0
    assert d.halt_kind is None


# ---------------------------------------------------------------------------
# Unclassified
# ---------------------------------------------------------------------------


def test_unknown_error_halts_unclassified():
    d = RecoveryPolicy().classify(_err(), "phase")
    assert d.action == "halt"
    assert d.halt_kind == "unclassified"


# ---------------------------------------------------------------------------
# Side-effect freedom — classify() must not mutate caller-owned counters.
# ---------------------------------------------------------------------------


def test_classify_returns_budget_delta_without_side_effects():
    p = RecoveryPolicy()
    used = {"context": 0, "external": 0, "blocked": 0}
    d = p.classify(
        _err(exit_kind=ExitKind.context_exhausted),
        "phase",
        context_retries_used=used["context"],
    )
    # caller is responsible for bumping; classifier did NOT bump.
    assert used == {"context": 0, "external": 0, "blocked": 0}
    assert d.budget_delta == 1


# ---------------------------------------------------------------------------
# Non-planning consumer: classify a transient WITHOUT importing megaplan.auto.
# ---------------------------------------------------------------------------


def test_non_planning_consumer_classifies_without_importing_auto(monkeypatch):
    # Wipe a previously-imported auto from sys.modules so we can prove the
    # classifier does not pull it back in.
    for mod in [m for m in list(sys.modules) if m == "megaplan.auto" or m.startswith("megaplan.auto.")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    # Re-import recovery_policy in isolation — must NOT drag auto.py in.
    rp_mod = importlib.import_module("megaplan.orchestration.recovery_policy")
    Policy = rp_mod.RecoveryPolicy

    decision = Policy().classify(
        _transient_err(),
        "orchestration",
        phase="critique",
        external_retries_used=0,
    )
    assert decision.action == "retry_transient"
    assert decision.budget_kind == "external"
    # The classify call must NOT have lazily imported megaplan.auto.
    assert "megaplan.auto" not in sys.modules


# ---------------------------------------------------------------------------
# RecoveryDecision is a value object (frozen).
# ---------------------------------------------------------------------------


def test_recovery_decision_is_frozen():
    d = RecoveryDecision(action="escalate")
    with pytest.raises(Exception):
        d.action = "halt"  # type: ignore[misc]
