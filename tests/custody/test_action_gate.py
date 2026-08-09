"""M11 Step 10 (T10): cross-contract acceptance for the action-boundary gate.

Step 10 requires current Run Authority grant/fence **plus** current
Custody lease/epoch as authority sources for dispatch, repair, completion,
cancellation, publication, and delivery.  WBC is **evidence-only**: it is
recorded in diagnostics but never creates authority and never gates the
verdict.

The ``wbc_evidence_only`` flag implements the stale-half acceptance fix:

  * Absent RA grant/fence BLOCKS — it must not fall through to AUTHORIZED.
  * Absent Custody lease/epoch BLOCKS — it must not fall through.
  * WBC outcomes are observed but never gate the verdict.

North Star: a stale-half acceptance bug would authorize an action using
only one authority source while the other is absent — these tests prove
that path is closed.
"""

from __future__ import annotations

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_check(source: str, outcome_str: str):
    """Build a SourceCheck with the given source name and outcome."""
    from arnold_pipelines.megaplan.custody.action_validator import (
        SourceCheck,
        ValidationOutcome,
    )
    return SourceCheck(source=source, outcome=ValidationOutcome(outcome_str), detail="test")


def _satisfied_ra_checks():
    """Both RA sources SATISFIED."""
    return (
        _make_check("run_authority_grant", "satisfied"),
        _make_check("run_authority_fence", "satisfied"),
    )


def _satisfied_custody_check():
    return _make_check("custody_lease", "satisfied")


def _missing_wbc_check():
    return _make_check("wbc_attempt", "missing")


def _satisfied_wbc_check():
    return _make_check("wbc_attempt", "satisfied")


# ── Step 10 acceptance test ──────────────────────────────────────────────────


def test_action_boundary_requires_run_authority_and_custody():
    """T10 / Step 10 acceptance: dispatch, repair, completion, cancellation,
    publication, and delivery require current Run Authority grant/fence
    **plus** current Custody lease/epoch.  WBC is evidence-only.

    This is the canonical narrow acceptance test: it proves the stale-half
    fix — neither RA nor Custody may be absent while the other is satisfied,
    and WBC never creates authority.
    """
    from arnold_pipelines.megaplan.custody.action_validator import (
        _compute_gate_result,
        GateResult,
    )

    # ── Baseline: all satisfied → AUTHORIZED ──────────────────────────────
    all_satisfied = (
        _make_check("run_authority_grant", "satisfied"),
        _make_check("run_authority_fence", "satisfied"),
        _make_check("custody_lease", "satisfied"),
        _make_check("wbc_attempt", "satisfied"),
    )
    assert _compute_gate_result(
        all_satisfied, enforcement_enabled=True, wbc_evidence_only=True
    ) == GateResult.AUTHORIZED

    # ── Stale-half fix: absent RA grant → BLOCKED ─────────────────────────
    no_grant = (
        _make_check("run_authority_grant", "missing"),
        _make_check("run_authority_fence", "satisfied"),
        _make_check("custody_lease", "satisfied"),
        _make_check("wbc_attempt", "satisfied"),
    )
    assert _compute_gate_result(
        no_grant, enforcement_enabled=True, wbc_evidence_only=True
    ) == GateResult.BLOCKED_MISSING_GRANT

    # ── Stale-half fix: absent Custody → BLOCKED (RA satisfied) ───────────
    no_custody = (
        _make_check("run_authority_grant", "satisfied"),
        _make_check("run_authority_fence", "satisfied"),
        _make_check("custody_lease", "missing"),
        _make_check("wbc_attempt", "satisfied"),
    )
    assert _compute_gate_result(
        no_custody, enforcement_enabled=True, wbc_evidence_only=True
    ) == GateResult.BLOCKED_NO_LEASE

    # ── WBC evidence-only: missing WBC does NOT block ─────────────────────
    ra_plus_custody_no_wbc = (
        _make_check("run_authority_grant", "satisfied"),
        _make_check("run_authority_fence", "satisfied"),
        _make_check("custody_lease", "satisfied"),
        _make_check("wbc_attempt", "missing"),
    )
    assert _compute_gate_result(
        ra_plus_custody_no_wbc, enforcement_enabled=True, wbc_evidence_only=True
    ) == GateResult.AUTHORIZED


class TestActionBoundaryRequiresRunAuthorityAndCustody:
    """T10 / Step 10: RA grant/fence AND Custody lease/epoch are required
    authority sources.  WBC is evidence-only and never gates the verdict."""

    # ── All-satisfied baseline (WBC also satisfied) ────────────────────────

    def test_all_satisfied_yields_authorized_with_wbc_evidence_only(self):
        """When ``wbc_evidence_only=True`` and all sources satisfied,
        the gate returns AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _satisfied_custody_check(),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.AUTHORIZED

    # ── Stale-half fix: absent RA blocks (must not fall through) ───────────

    def test_absent_run_authority_grant_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: missing RA grant → BLOCKED, not AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "missing"),
            _make_check("run_authority_fence", "satisfied"),
            _satisfied_custody_check(),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_MISSING_GRANT
        assert result != GateResult.AUTHORIZED

    def test_stale_run_authority_grant_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: stale RA grant → BLOCKED, not AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "stale"),
            _make_check("run_authority_fence", "satisfied"),
            _satisfied_custody_check(),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_RA_UNSATISFIED
        assert result != GateResult.AUTHORIZED

    def test_absent_run_authority_fence_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: fenced RA → BLOCKED, not AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "satisfied"),
            _make_check("run_authority_fence", "fenced"),
            _satisfied_custody_check(),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_FENCE_MISMATCH
        assert result != GateResult.AUTHORIZED

    def test_ra_source_entirely_absent_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: when an RA source check is missing entirely
        (not even present in the checks tuple), it BLOCKS — it does not
        fall through to AUTHORIZED.  This is the core stale-half bug
        class: authority created from absence."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        # Only custody + wbc — RA grant and fence absent entirely.
        checks = (
            _satisfied_custody_check(),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_MISSING_GRANT
        assert result != GateResult.AUTHORIZED

    # ── Stale-half fix: absent Custody blocks (must not fall through) ──────

    def test_absent_custody_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: missing custody lease → BLOCKED, not AUTHORIZED,
        even when RA is satisfied."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _make_check("custody_lease", "missing"),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_NO_LEASE
        assert result != GateResult.AUTHORIZED

    def test_expired_custody_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: expired custody lease → BLOCKED, not AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _make_check("custody_lease", "expired"),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_EXPIRED_LEASE
        assert result != GateResult.AUTHORIZED

    def test_stale_epoch_custody_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: stale-epoch custody → BLOCKED, not AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _make_check("custody_lease", "stale"),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_STALE_EPOCH
        assert result != GateResult.AUTHORIZED

    def test_not_owner_custody_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: not-owner custody → BLOCKED, not AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _make_check("custody_lease", "not_owner"),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_NOT_OWNER
        assert result != GateResult.AUTHORIZED

    def test_custody_source_entirely_absent_blocks_with_wbc_evidence_only(self):
        """Stale-half fix: when the custody source check is missing
        entirely (not even present in the checks tuple), it BLOCKS even
        when RA is satisfied.  No authority from absence."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _satisfied_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.BLOCKED_NO_LEASE
        assert result != GateResult.AUTHORIZED

    # ── WBC is evidence-only: absent/conflicting WBC never gates ───────────

    def test_missing_wbc_still_authorizes_with_wbc_evidence_only(self):
        """WBC evidence-only: when RA and Custody are satisfied, a MISSING
        WBC outcome does NOT block.  WBC is recorded as evidence but never
        creates authority or gates the verdict."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _satisfied_custody_check(),
            _missing_wbc_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.AUTHORIZED

    def test_conflict_wbc_still_authorizes_with_wbc_evidence_only(self):
        """WBC evidence-only: a CONFLICT WBC outcome does NOT block when
        RA and Custody are satisfied."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _satisfied_custody_check(),
            _make_check("wbc_attempt", "conflict"),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.AUTHORIZED

    def test_wbc_source_entirely_absent_still_authorizes(self):
        """WBC evidence-only: when no WBC source is present at all and
        RA + Custody are satisfied, the verdict is still AUTHORIZED.
        Authority is created only from RA grant/fence and Custody
        lease/epoch."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            *_satisfied_ra_checks(),
            _satisfied_custody_check(),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=True, wbc_evidence_only=True
        )
        assert result == GateResult.AUTHORIZED

    # ── Shadow mode: wbc_evidence_only still returns SHADOW_PASS ───────────

    def test_shadow_mode_returns_shadow_pass_with_wbc_evidence_only(self):
        """Enforcement-disabled (shadow) returns SHADOW_PASS regardless of
        the per-source outcomes — but checks are still populated."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            _compute_gate_result,
            GateResult,
        )
        checks = (
            _make_check("run_authority_grant", "missing"),
            _make_check("custody_lease", "missing"),
        )
        result = _compute_gate_result(
            checks, enforcement_enabled=False, wbc_evidence_only=True
        )
        assert result == GateResult.SHADOW_PASS


# ── ActionGate (action_gate.py) wbc_evidence_only path ──────────────────────


class TestActionGateWbcEvidenceOnly:
    """T10 / Step 10: the ActionGate (second-fence) honours
    ``wbc_evidence_only`` on ``ActionGateConfig``."""

    def test_action_gate_config_has_wbc_evidence_only_flag(self):
        """ActionGateConfig exposes the ``wbc_evidence_only`` flag,
        defaulting to ``False`` for backward compatibility."""
        from arnold_pipelines.megaplan.custody.action_gate import ActionGateConfig
        config = ActionGateConfig()
        assert config.wbc_evidence_only is False

    def test_action_gate_wbc_evidence_only_blocks_absent_ra(self):
        """When ``wbc_evidence_only=True`` and RA is absent, the gate
        verdict is BLOCKED_RA_UNSATISFIED (stale-half fix)."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        from arnold_pipelines.run_authority.current_source import (
            CurrentSourceRequest,
        )
        ra_request = CurrentSourceRequest(
            run_id="run-1",
            run_revision="rev-1",
            coordinator_attempt_id="ca-1",
            grant_id="g-1",
            fence_token=1,
            subject_attempt_id="sa-1",
            decision_id="d-1",
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.EFFECT}),
                wbc_evidence_only=True,
            ),
            ra_view_provider=lambda: None,
            custody_lease_provider=lambda attempt_id: True,
        )
        decision = gate.evaluate(
            action_family=ActionFamily.EFFECT,
            action_target="dispatch",
            ra_request=ra_request,
            custody_attempt_id="ca-1",
        )
        # RA provider returns None → ra_result stays None → BLOCKED_RA_UNSATISFIED
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_RA_UNSATISFIED
        assert not decision.result.is_authorized

    def test_action_gate_wbc_evidence_only_blocks_absent_custody(self):
        """When ``wbc_evidence_only=True``, RA satisfied, but custody
        absent, the verdict is BLOCKED_CUSTODY (stale-half fix)."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        from arnold_pipelines.run_authority.current_source import (
            CurrentSourceRequest,
            CurrentSourceResult,
            SATISFIED,
        )

        ra_request = CurrentSourceRequest(
            run_id="run-1",
            run_revision="rev-1",
            coordinator_attempt_id="ca-1",
            grant_id="g-1",
            fence_token=1,
            subject_attempt_id="sa-1",
            decision_id="d-1",
        )
        satisfied_ra = CurrentSourceResult(SATISFIED, "all match", {})

        # Patch evaluate_current_source to return SATISFIED
        import arnold_pipelines.megaplan.custody.action_gate as ag_mod
        original = ag_mod.evaluate_current_source
        ag_mod.evaluate_current_source = lambda view, req: satisfied_ra
        try:
            gate = ActionGate(
                config=ActionGateConfig(
                    enforced_families=frozenset({ActionFamily.EFFECT}),
                    wbc_evidence_only=True,
                ),
                ra_view_provider=lambda: object(),
                custody_lease_provider=lambda attempt_id: None,
            )
            decision = gate.evaluate(
                action_family=ActionFamily.EFFECT,
                action_target="dispatch",
                ra_request=ra_request,
                custody_attempt_id="ca-1",
            )
        finally:
            ag_mod.evaluate_current_source = original
        # custody provider returns None → custody_active False → BLOCKED_CUSTODY
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_CUSTODY
        assert not decision.result.is_authorized

    def test_action_gate_wbc_evidence_only_authorizes_ra_plus_custody(self):
        """When ``wbc_evidence_only=True``, RA satisfied, custody active,
        and WBC entirely absent — the verdict is AUTHORIZED.
        WBC never gates the verdict."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        from arnold_pipelines.run_authority.current_source import (
            CurrentSourceRequest,
            CurrentSourceResult,
            SATISFIED,
        )

        ra_request = CurrentSourceRequest(
            run_id="run-1",
            run_revision="rev-1",
            coordinator_attempt_id="ca-1",
            grant_id="g-1",
            fence_token=1,
            subject_attempt_id="sa-1",
            decision_id="d-1",
        )
        satisfied_ra = CurrentSourceResult(SATISFIED, "all match", {})

        import arnold_pipelines.megaplan.custody.action_gate as ag_mod
        original = ag_mod.evaluate_current_source
        ag_mod.evaluate_current_source = lambda view, req: satisfied_ra
        try:
            gate = ActionGate(
                config=ActionGateConfig(
                    enforced_families=frozenset({ActionFamily.EFFECT}),
                    wbc_evidence_only=True,
                ),
                ra_view_provider=lambda: object(),
                custody_lease_provider=lambda attempt_id: True,
                wbc_store_provider=lambda ref: None,
            )
            decision = gate.evaluate(
                action_family=ActionFamily.EFFECT,
                action_target="dispatch",
                ra_request=ra_request,
                custody_attempt_id="ca-1",
            )
        finally:
            ag_mod.evaluate_current_source = original
        assert decision.result.verdict == ActionGateVerdict.AUTHORIZED
        assert decision.result.is_authorized


# ── Cross-action coverage ────────────────────────────────────────────────────


class TestAllActionBoundariesCovered:
    """Step 10 names six action boundaries: dispatch, repair, completion,
    cancellation, publication, delivery.  This confirms the boundary type
    vocabulary enumerates them and that the validator accepts each."""

    def test_six_named_action_boundaries_exist(self):
        """The ACTION_BOUNDARY_TYPES set includes the six Step-10 named
        boundaries: dispatch, repair, completion, cancellation,
        publication, delivery."""
        from arnold_pipelines.megaplan.custody.action_validator import (
            ACTION_BOUNDARY_TYPES,
        )
        expected = {"dispatch", "repair", "completion", "cancellation", "publication", "delivery"}
        actual = set(ACTION_BOUNDARY_TYPES)
        assert expected.issubset(actual), (
            f"Step 10 named boundaries missing from ACTION_BOUNDARY_TYPES: "
            f"{expected - actual}"
        )
