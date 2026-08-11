"""Tests for action_validator.py _compute_gate_result — Steps 12A / NSA-M10-GATE-1 (T19/T20).

Focus: the gate computation must block on **any** non-SATISFIED Run Authority
outcome, not just MISSING grant or FENCED fence.  Stale, conflicted, or
superseded RA outcomes must return BLOCKED_RA_UNSATISFIED instead of
falling through to AUTHORIZED.

Also covers the P3 deny-by-default flip: production enforcement defaults ON
and the env var is an explicit-disable switch.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest


@contextmanager
def _env_patch(**kwargs: str | None):
    """Temporarily set/clear environment variables."""
    originals: dict[str, str | None] = {}
    for key, value in kwargs.items():
        originals[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, original in originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_check(source: str, outcome_str: str):
    """Build a SourceCheck with the given source name and outcome."""
    from arnold_pipelines.megaplan.custody.action_validator import (
        SourceCheck,
        ValidationOutcome,
    )
    outcome = ValidationOutcome(outcome_str)
    return SourceCheck(source=source, outcome=outcome, detail="test")


def _satisfied_ra_checks():
    """Both RA sources SATISFIED."""
    return (
        _make_check("run_authority_grant", "satisfied"),
        _make_check("run_authority_fence", "satisfied"),
    )


def _all_satisfied_checks():
    """All four sources SATISFIED."""
    return (
        _make_check("run_authority_grant", "satisfied"),
        _make_check("run_authority_fence", "satisfied"),
        _make_check("custody_lease", "satisfied"),
        _make_check("wbc_attempt", "satisfied"),
    )


# ── Default enforcement (P3 deny-by-default) ─────────────────────────────────


class TestDefaultEnforcement:
    """Enforcement defaults ON; the env var is an explicit-disable switch."""

    def test_production_enforcement_enabled_defaults_true(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            production_enforcement_enabled,
        )
        with _env_patch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None):
            assert production_enforcement_enabled() is True

    def test_production_enforcement_enabled_explicit_disable(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            production_enforcement_enabled,
        )
        for disable in ("0", "false", "no", "off"):
            with _env_patch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=disable):
                assert production_enforcement_enabled() is False, disable

    def test_production_enforcement_enabled_explicit_enable(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            production_enforcement_enabled,
        )
        for enable in ("1", "true", "yes"):
            with _env_patch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=enable):
                assert production_enforcement_enabled() is True, enable

    def test_validate_default_uses_enforcement_on(self):
        """validate_action_boundary without override enforces by default."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            GateResult,
            validate_action_boundary_simple,
        )
        with _env_patch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None):
            # Invalid target -> ERROR only when enforcement is on (default).
            result = validate_action_boundary_simple(
                action_type="repair",
                target={"bad": "target"},
                run_authority_grant_id="g",
                coordinator_fence_token=0,
            )
            assert result.gate_result == GateResult.ERROR
            assert result.enforcement_enabled is True
        with _env_patch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT="0"):
            result = validate_action_boundary_simple(
                action_type="repair",
                target={"bad": "target"},
                run_authority_grant_id="g",
                coordinator_fence_token=0,
            )
            assert result.gate_result == GateResult.SHADOW_PASS
            assert result.enforcement_enabled is False


# ── Shadow mode ─────────────────────────────────────────────────────────────


class TestShadowMode:
    """When enforcement is off, gate result is SHADOW_PASS regardless."""

    def test_shadow_pass_with_no_checks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        result = _compute_gate_result((), enforcement_enabled=False)
        assert result == GateResult.SHADOW_PASS

    def test_shadow_pass_even_with_errors(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (_make_check("run_authority_grant", "error"),)
        result = _compute_gate_result(checks, enforcement_enabled=False)
        assert result == GateResult.SHADOW_PASS


# ── All-satisfied → AUTHORIZED ───────────────────────────────────────────────


class TestAuthorizedWhenAllSatisfied:
    """With enforcement on, all SATISFIED checks yield AUTHORIZED."""

    def test_all_satisfied_yields_authorized(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        result = _compute_gate_result(_all_satisfied_checks(), enforcement_enabled=True)
        assert result == GateResult.AUTHORIZED

    def test_authorized_value_is_distinct(self):
        """GateResult.AUTHORIZED has a unique value (not aliased)."""
        from arnold_pipelines.megaplan.custody.action_validator import GateResult
        values = [m.value for m in GateResult]
        assert len(values) == len(set(values)), "duplicate gate result values"

    def test_authorized_not_equal_to_shadow_pass(self):
        from arnold_pipelines.megaplan.custody.action_validator import GateResult
        assert GateResult.AUTHORIZED != GateResult.SHADOW_PASS
        assert GateResult.AUTHORIZED is not GateResult.SHADOW_PASS


# ── NSA-M10-GATE-1 / Step 12A: any non-SATISFIED RA blocks ──────────────────


class TestRaUnsatisfiedBlocking:
    """Any non-SATISFIED RA outcome (not just MISSING/FENCED) must block."""

    def test_stale_grant_blocks(self):
        """STALE grant outcome → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "stale"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_conflicted_grant_blocks(self):
        """CONFLICT grant outcome → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "conflict"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_stale_fence_blocks(self):
        """STALE fence outcome → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "stale"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_conflicted_fence_blocks(self):
        """CONFLICT fence outcome → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "conflict"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_expired_grant_blocks(self):
        """EXPIRED grant outcome → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "expired"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_ra_not_owner_blocks(self):
        """NOT_OWNER RA outcome → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "not_owner"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_both_ra_unsatisfied_blocks(self):
        """Both RA sources unsatisfied → BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "stale"),
            _make_check("run_authority_fence", "conflict"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_RA_UNSATISFIED

    def test_ra_unsatisfied_does_not_fall_through_to_authorized(self):
        """Critical regression: stale RA must NOT produce AUTHORIZED.

        Before T19, only MISSING grant and FENCED fence were checked.
        Any other RA outcome fell through to AUTHORIZED.
        """
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        # STALE is neither MISSING nor FENCED — old code fell through
        checks = (
            _make_check("run_authority_grant", "stale"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result != GateResult.AUTHORIZED


# ── Existing gate outcomes still work ────────────────────────────────────────


class TestExistingGateOutcomes:
    """Pre-existing blocking paths remain functional."""

    def test_error_takes_precedence(self):
        """ERROR check takes precedence over all other outcomes."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "error"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.ERROR

    def test_missing_grant_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "missing"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_MISSING_GRANT

    def test_fenced_fence_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "fenced"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_FENCE_MISMATCH

    def test_missing_lease_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "missing"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_NO_LEASE

    def test_expired_lease_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "expired"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_EXPIRED_LEASE

    def test_stale_epoch_lease_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "stale"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_STALE_EPOCH

    def test_not_owner_lease_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "not_owner"),
            _make_check("wbc_attempt", "satisfied"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_NOT_OWNER

    def test_missing_wbc_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "missing"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_WBC_MISSING

    def test_conflict_wbc_blocks(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "satisfied"),
            _make_check("custody_lease", "satisfied"),
            _make_check("wbc_attempt", "conflict"),
        )
        result = _compute_gate_result(checks, enforcement_enabled=True)
        assert result == GateResult.BLOCKED_WBC_CONFLICT


# ── Empty checks ─────────────────────────────────────────────────────────────


class TestEmptyChecks:
    def test_empty_checks_enforced_yields_authorized(self):
        """No checks at all with enforcement → AUTHORIZED (vacuous truth)."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        result = _compute_gate_result((), enforcement_enabled=True)
        assert result == GateResult.AUTHORIZED


# ── Result property tests ────────────────────────────────────────────────────


class TestActionBoundaryResultProperties:
    """ActionBoundaryResult.authorized and .blocked behave correctly."""

    def test_authorized_property_true_only_for_authorized(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            ActionBoundaryResult,
            GateResult,
        )
        result = ActionBoundaryResult(
            gate_result=GateResult.AUTHORIZED,
            action_type="dispatch",
            target_digest="abc123",
            checks=(),
            enforcement_enabled=True,
        )
        assert result.authorized is True
        assert result.blocked is False

    def test_shadow_pass_not_authorized(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            ActionBoundaryResult,
            GateResult,
        )
        result = ActionBoundaryResult(
            gate_result=GateResult.SHADOW_PASS,
            action_type="dispatch",
            target_digest="abc123",
            checks=(),
            enforcement_enabled=False,
        )
        assert result.authorized is False
        assert result.blocked is False
        assert result.is_shadow is True

    def test_blocked_result(self):
        from arnold_pipelines.megaplan.custody.action_validator import (
            ActionBoundaryResult,
            GateResult,
        )
        result = ActionBoundaryResult(
            gate_result=GateResult.BLOCKED_RA_UNSATISFIED,
            action_type="dispatch",
            target_digest="abc123",
            checks=(),
            enforcement_enabled=True,
        )
        assert result.authorized is False
        assert result.blocked is True
