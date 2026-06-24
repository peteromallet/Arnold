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

from arnold.pipelines.megaplan.orchestration.phase_result import ExitKind
from arnold.pipelines.megaplan.orchestration.recovery_policy import (
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
    auto_prefix = "arnold.pipelines.megaplan.auto"
    for mod in [m for m in list(sys.modules) if m == auto_prefix or m.startswith(auto_prefix + ".")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    # Re-import recovery_policy in isolation — must NOT drag auto.py in.
    rp_mod = importlib.import_module("arnold.pipelines.megaplan.orchestration.recovery_policy")
    Policy = rp_mod.RecoveryPolicy

    decision = Policy().classify(
        _transient_err(),
        "orchestration",
        phase="critique",
        external_retries_used=0,
    )
    assert decision.action == "retry_transient"
    assert decision.budget_kind == "external"
    # The classify call must NOT have lazily imported auto.py.
    assert auto_prefix not in sys.modules


# ---------------------------------------------------------------------------
# RecoveryDecision is a value object (frozen).
# ---------------------------------------------------------------------------


def test_recovery_decision_is_frozen():
    d = RecoveryDecision(action="escalate")
    with pytest.raises(Exception):
        d.action = "halt"  # type: ignore[misc]


# ===================================================================
# Arnold adapter parity tests: classify_arnold
# ===================================================================
# These tests exercise the classify_arnold bridge that maps an Arnold
# RecoveryContext -> Megaplan classify() args -> Arnold RecoveryDecision.
# They verify that pre-adapter decisions (context / external / blocked /
# timeout / unclassified) are faithfully preserved through the adapter.


def _arnold_context(**metadata):
    """Build a minimal Arnold RecoveryContext for adapter parity tests."""
    from arnold.runtime.recovery import RecoveryContext as ArnoldCtx

    return ArnoldCtx(error="test-error", metadata=metadata)


# --- context exhaustion paths ---


def test_classify_arnold_context_exhausted_retry_under_budget():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        context_retries_used=0,
    )
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    assert decision.status == "decided"
    assert decision.action == "retry_fresh"
    assert decision.budget_consumed["budget_kind"] == "context"
    assert decision.budget_consumed["budget_delta"] == 1


def test_classify_arnold_context_exhausted_halt_at_cap():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        context_retries_used=DEFAULT_MAX_CONTEXT_RETRIES,
    )
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "context_retry_exhausted"
    assert decision.budget_consumed["budget_kind"] == "context"


def test_classify_arnold_context_exhausted_via_message():
    p = RecoveryPolicy()
    err = _err(message="model ran out of room in the model's context window")
    ctx = _arnold_context(layer="phase", context_retries_used=0)
    decision = p.classify_arnold(err, ctx)
    assert decision.action == "retry_fresh"
    assert decision.budget_consumed["budget_kind"] == "context"


# --- transient external paths ---


def test_classify_arnold_external_transient_retry_under_budget():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        external_retries_used=0,
        phase="plan",
    )
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "retry_transient"
    assert decision.budget_consumed["budget_kind"] == "external"
    assert decision.budget_consumed["budget_delta"] == 1


def test_classify_arnold_external_transient_halt_at_cap():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        external_retries_used=DEFAULT_MAX_EXTERNAL_RETRIES,
        phase="plan",
    )
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "external_retry_exhausted"


def test_classify_arnold_external_permanent_halts():
    p = RecoveryPolicy()
    err = _err(
        exit_kind=ExitKind.external_error,
        error_kind="auth",
        message="bad key",
    )
    ctx = _arnold_context(layer="phase", phase="plan")
    decision = p.classify_arnold(err, ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "permanent_external"


def test_classify_arnold_external_on_execute_phase_halts():
    """execute is NOT in EXTERNAL_RETRYABLE_PHASES -> permanent."""
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase", phase="execute")
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "permanent_external"


# --- blocked paths ---


@pytest.mark.parametrize("kind", [ExitKind.blocked_by_quality, ExitKind.blocked_by_prereq])
def test_classify_arnold_blocked_retry_under_budget(kind):
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase", blocked_retries_used=0)
    decision = p.classify_arnold(_err(exit_kind=kind), ctx)
    assert decision.status == "decided"
    assert decision.action == "retry_fresh"
    assert decision.budget_consumed["budget_kind"] == "blocked"
    assert decision.budget_consumed["budget_delta"] == 1


def test_classify_arnold_blocked_halt_at_cap():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        blocked_retries_used=DEFAULT_MAX_BLOCKED_RETRIES,
    )
    decision = p.classify_arnold(_err(exit_kind=ExitKind.blocked_by_quality), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "blocked_retry_exhausted"


# --- escalate paths (timeout / internal_error) ---


@pytest.mark.parametrize("kind", [ExitKind.timeout, ExitKind.internal_error])
def test_classify_arnold_escalate_on_timeout_and_internal(kind):
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase")
    decision = p.classify_arnold(_err(exit_kind=kind), ctx)
    assert decision.status == "decided"
    assert decision.action == "escalate"
    assert "budget_kind" not in decision.budget_consumed
    assert "halt_kind" not in decision.budget_consumed


# --- unclassified path ---


def test_classify_arnold_unclassified_halts():
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase")
    decision = p.classify_arnold(_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "unclassified"


# --- metadata mapping and defaults ---


def test_classify_arnold_metadata_defaults():
    """When metadata is empty, defaults should be used."""
    p = RecoveryPolicy()
    # Without phase, external transient should NOT be retryable
    ctx = _arnold_context()  # empty metadata -> phase="" -> not in EXTERNAL_RETRYABLE_PHASES
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "permanent_external"


def test_classify_arnold_layer_defaults_to_phase():
    """When layer is not in metadata, it defaults to 'phase'."""
    p = RecoveryPolicy()
    ctx = _arnold_context(context_retries_used=0)
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    assert decision.action == "retry_fresh"


def test_classify_arnold_budget_consumed_carries_reason():
    """reason from Megaplan decision is propagated as-is."""
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase", external_retries_used=0, phase="plan")
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.reason == "transient external"


def test_classify_arnold_budget_consumed_is_dict():
    """budget_consumed is always a dict even when empty."""
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase")
    # Unclassified error -> halt with halt_kind only, no budget_kind or delta
    decision = p.classify_arnold(_err(), ctx)
    assert isinstance(decision.budget_consumed, dict)
    assert decision.budget_consumed["halt_kind"] == "unclassified"


def test_classify_arnold_side_effect_freedom():
    """classify_arnold must not mutate the caller's RecoveryContext."""
    p = RecoveryPolicy()
    meta = {
        "layer": "phase",
        "context_retries_used": 0,
    }
    ctx = _arnold_context(**meta)
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    # The original dict must be unchanged
    assert meta["context_retries_used"] == 0
    assert decision.budget_consumed["budget_delta"] == 1


# ===================================================================
# Regression: NullRecoveryPolicy produces unsupported/unset
# ===================================================================


def test_null_policy_classify_arnold_returns_unset():
    """When no Megaplan policy is available, NullRecoveryPolicy returns unset.

    This is a regression test verifying that the no-plugin-recovery-policy
    path produces an explicit unsupported/unset signal rather than silently
    falling back to Megaplan defaults.
    """
    from arnold.runtime.recovery import NullRecoveryPolicy, RecoveryContext as ArnoldCtx

    np = NullRecoveryPolicy()
    ctx = ArnoldCtx(error="timeout", metadata={"layer": "phase"})
    decision = np.classify("timeout", ctx)
    assert decision.status == "unset"
    assert decision.action == ""
    assert "No recovery policy registered" in decision.reason


# ===================================================================
# Arnold adapter parity tests: classify_arnold
# ===================================================================
# These tests exercise the classify_arnold bridge that maps an Arnold
# RecoveryContext -> Megaplan classify() args -> Arnold RecoveryDecision.
# They verify that pre-adapter decisions (context / external / blocked /
# timeout / unclassified) are faithfully preserved through the adapter.


def _arnold_context(**metadata):
    """Build a minimal Arnold RecoveryContext for adapter parity tests."""
    from arnold.runtime.recovery import RecoveryContext as ArnoldCtx

    return ArnoldCtx(error="test-error", metadata=metadata)


# --- context exhaustion paths ---


def test_classify_arnold_context_exhausted_retry_under_budget():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        context_retries_used=0,
    )
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    assert decision.status == "decided"
    assert decision.action == "retry_fresh"
    assert decision.budget_consumed["budget_kind"] == "context"
    assert decision.budget_consumed["budget_delta"] == 1


def test_classify_arnold_context_exhausted_halt_at_cap():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        context_retries_used=DEFAULT_MAX_CONTEXT_RETRIES,
    )
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "context_retry_exhausted"
    assert decision.budget_consumed["budget_kind"] == "context"


def test_classify_arnold_context_exhausted_via_message():
    p = RecoveryPolicy()
    err = _err(message="model ran out of room in the model's context window")
    ctx = _arnold_context(layer="phase", context_retries_used=0)
    decision = p.classify_arnold(err, ctx)
    assert decision.action == "retry_fresh"
    assert decision.budget_consumed["budget_kind"] == "context"


# --- transient external paths ---


def test_classify_arnold_external_transient_retry_under_budget():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        external_retries_used=0,
        phase="plan",
    )
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "retry_transient"
    assert decision.budget_consumed["budget_kind"] == "external"
    assert decision.budget_consumed["budget_delta"] == 1


def test_classify_arnold_external_transient_halt_at_cap():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        external_retries_used=DEFAULT_MAX_EXTERNAL_RETRIES,
        phase="plan",
    )
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "external_retry_exhausted"


def test_classify_arnold_external_permanent_halts():
    p = RecoveryPolicy()
    err = _err(
        exit_kind=ExitKind.external_error,
        error_kind="auth",
        message="bad key",
    )
    ctx = _arnold_context(layer="phase", phase="plan")
    decision = p.classify_arnold(err, ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "permanent_external"


def test_classify_arnold_external_on_execute_phase_halts():
    """execute is NOT in EXTERNAL_RETRYABLE_PHASES -> permanent."""
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase", phase="execute")
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "permanent_external"


# --- blocked paths ---


@pytest.mark.parametrize("kind", [ExitKind.blocked_by_quality, ExitKind.blocked_by_prereq])
def test_classify_arnold_blocked_retry_under_budget(kind):
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase", blocked_retries_used=0)
    decision = p.classify_arnold(_err(exit_kind=kind), ctx)
    assert decision.status == "decided"
    assert decision.action == "retry_fresh"
    assert decision.budget_consumed["budget_kind"] == "blocked"
    assert decision.budget_consumed["budget_delta"] == 1


def test_classify_arnold_blocked_halt_at_cap():
    p = RecoveryPolicy()
    ctx = _arnold_context(
        layer="phase",
        blocked_retries_used=DEFAULT_MAX_BLOCKED_RETRIES,
    )
    decision = p.classify_arnold(_err(exit_kind=ExitKind.blocked_by_quality), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "blocked_retry_exhausted"


# --- escalate paths (timeout / internal_error) ---


@pytest.mark.parametrize("kind", [ExitKind.timeout, ExitKind.internal_error])
def test_classify_arnold_escalate_on_timeout_and_internal(kind):
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase")
    decision = p.classify_arnold(_err(exit_kind=kind), ctx)
    assert decision.status == "decided"
    assert decision.action == "escalate"
    assert "budget_kind" not in decision.budget_consumed
    assert "halt_kind" not in decision.budget_consumed


# --- unclassified path ---


def test_classify_arnold_unclassified_halts():
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase")
    decision = p.classify_arnold(_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "unclassified"


# --- metadata mapping and defaults ---


def test_classify_arnold_metadata_defaults():
    """When metadata is empty, defaults should be used."""
    p = RecoveryPolicy()
    # Without phase, external transient should NOT be retryable
    ctx = _arnold_context()  # empty metadata -> phase="" -> not in EXTERNAL_RETRYABLE_PHASES
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.status == "decided"
    assert decision.action == "halt"
    assert decision.budget_consumed["halt_kind"] == "permanent_external"


def test_classify_arnold_layer_defaults_to_phase():
    """When layer is not in metadata, it defaults to 'phase'."""
    p = RecoveryPolicy()
    ctx = _arnold_context(context_retries_used=0)
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    assert decision.action == "retry_fresh"


def test_classify_arnold_budget_consumed_carries_reason():
    """reason from Megaplan decision is propagated as-is."""
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase", external_retries_used=0, phase="plan")
    decision = p.classify_arnold(_transient_err(), ctx)
    assert decision.reason == "transient external"


def test_classify_arnold_budget_consumed_is_dict():
    """budget_consumed is always a dict even when empty."""
    p = RecoveryPolicy()
    ctx = _arnold_context(layer="phase")
    # Unclassified error -> halt with halt_kind only, no budget_kind or delta
    decision = p.classify_arnold(_err(), ctx)
    assert isinstance(decision.budget_consumed, dict)
    assert decision.budget_consumed["halt_kind"] == "unclassified"


def test_classify_arnold_side_effect_freedom():
    """classify_arnold must not mutate the caller's RecoveryContext."""
    p = RecoveryPolicy()
    meta = {
        "layer": "phase",
        "context_retries_used": 0,
    }
    ctx = _arnold_context(**meta)
    decision = p.classify_arnold(_err(exit_kind=ExitKind.context_exhausted), ctx)
    # The original dict must be unchanged
    assert meta["context_retries_used"] == 0
    assert decision.budget_consumed["budget_delta"] == 1


# ===================================================================
# Regression: NullRecoveryPolicy produces unsupported/unset
# ===================================================================


def test_null_policy_classify_arnold_returns_unset():
    """When no Megaplan policy is available, NullRecoveryPolicy returns unset.

    This is a regression test verifying that the no-plugin-recovery-policy
    path produces an explicit unsupported/unset signal rather than silently
    falling back to Megaplan defaults.
    """
    from arnold.runtime.recovery import NullRecoveryPolicy, RecoveryContext as ArnoldCtx

    np = NullRecoveryPolicy()
    ctx = ArnoldCtx(error="timeout", metadata={"layer": "phase"})
    decision = np.classify("timeout", ctx)
    assert decision.status == "unset"
    assert decision.action == ""
    assert "No recovery policy registered" in decision.reason
