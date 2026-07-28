"""Tests for action_gate.py — Steps 11B, 12B, 12C (T20).

Step 11B: action_gate rereads current RA/Custody/WBC at action time.
Step 12B: WBC evidence must come from the store; synthetic wbc-ref-* and
          projection-only evidence is rejected.
Step 12C: enforcement is staged per action family (shadow vs enforce).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _satisfied_ra_result():
    """A current_source result that is SATISFIED."""
    from arnold_pipelines.run_authority.current_source import (
        CurrentSourceResult,
        SATISFIED,
    )
    return CurrentSourceResult(SATISFIED, "all match", {})


def _denied_ra_result():
    """A current_source result that is DENIED."""
    from arnold_pipelines.run_authority.current_source import (
        CurrentSourceResult,
        DENIED,
    )
    return CurrentSourceResult(DENIED, "stale grant", {})


def _make_store_reservation():
    """A fake WBC store reservation (authoritative store evidence)."""
    return SimpleNamespace(
        attempt_id="att-100",
        global_logical_effect_key="glek-abc123",
        effect_identity=SimpleNamespace(effect_family="git"),
    )


# ── Step 11B: reread RA/Custody/WBC at action time ──────────────────────────


class TestStep11BRereadAtActionTime:
    """Step 11B: each source is reread fresh — no cached projections trusted."""

    def test_shadow_authorized_when_family_not_enforced(self):
        """Non-enforced family returns SHADOW_AUTHORIZED, never AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )

        gate = ActionGate(
            config=ActionGateConfig(enforced_families=frozenset()),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
        )
        assert decision.result.verdict == ActionGateVerdict.SHADOW_AUTHORIZED
        assert not decision.result.is_authorized

    def test_shadow_blocked_when_ra_denied_in_shadow_mode(self):
        """Shadow mode still reports RA denial as SHADOW_BLOCKED."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )

        gate = ActionGate(
            config=ActionGateConfig(enforced_families=frozenset()),
            ra_view_provider=lambda: MagicMock(),
        )
        from arnold_pipelines.run_authority.current_source import (
            CurrentSourceRequest,
        )
        ra_request = CurrentSourceRequest(
            run_id="run-1",
            run_revision="rev-1",
            coordinator_attempt_id="ca-1",
            grant_id="g-1",
            fence_token="ft-1",
            subject_attempt_id="sa-1",
            decision_id="d-1",
        )

        # Patch evaluate_current_source to return DENIED
        import arnold_pipelines.megaplan.custody.action_gate as ag_mod
        original = ag_mod.evaluate_current_source
        ag_mod.evaluate_current_source = lambda view, req: _denied_ra_result()
        try:
            decision = gate.evaluate(
                action_family=ActionFamily.GIT,
                action_target="pr_merge",
                ra_request=ra_request,
            )
            assert decision.result.verdict == ActionGateVerdict.SHADOW_BLOCKED
            assert not decision.result.is_authorized
        finally:
            ag_mod.evaluate_current_source = original

    def test_enforced_blocks_when_ra_denied(self):
        """Enforced family with DENIED RA blocks with BLOCKED_RA_UNSATISFIED."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )

        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            ra_view_provider=lambda: MagicMock(),
        )
        from arnold_pipelines.run_authority.current_source import (
            CurrentSourceRequest,
        )
        ra_request = CurrentSourceRequest(
            run_id="run-1",
            run_revision="rev-1",
            coordinator_attempt_id="ca-1",
            grant_id="g-1",
            fence_token="ft-1",
            subject_attempt_id="sa-1",
            decision_id="d-1",
        )

        import arnold_pipelines.megaplan.custody.action_gate as ag_mod
        original = ag_mod.evaluate_current_source
        ag_mod.evaluate_current_source = lambda view, req: _denied_ra_result()
        try:
            decision = gate.evaluate(
                action_family=ActionFamily.GIT,
                action_target="pr_merge",
                ra_request=ra_request,
            )
            assert decision.result.verdict == ActionGateVerdict.BLOCKED_RA_UNSATISFIED
        finally:
            ag_mod.evaluate_current_source = original

    def test_enforced_blocks_when_custody_inactive(self):
        """Enforced family with no active custody lease blocks."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )

        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            custody_lease_provider=lambda attempt_id: None,
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            custody_attempt_id="att-50",
        )
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_CUSTODY

    def test_enforced_blocks_when_custody_provider_raises(self):
        """Custody reread error does not authorize."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )

        def boom(_):
            raise RuntimeError("db down")

        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            custody_lease_provider=boom,
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            custody_attempt_id="att-51",
        )
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_CUSTODY
        assert "custody reread error" in decision.result.custody_detail.get("reason", "")

    def test_ra_provider_exception_yields_denied(self):
        """When RA reread throws, result is DENIED (never authorized)."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )

        def boom():
            raise RuntimeError("view unavailable")

        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            ra_view_provider=boom,
        )
        from arnold_pipelines.run_authority.current_source import (
            CurrentSourceRequest,
        )
        ra_request = CurrentSourceRequest(
            run_id="run-1",
            run_revision="rev-1",
            coordinator_attempt_id="ca-1",
            grant_id="g-1",
            fence_token="ft-1",
            subject_attempt_id="sa-1",
            decision_id="d-1",
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            ra_request=ra_request,
        )
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_RA_UNSATISFIED

    def test_no_ra_request_skips_ra_check(self):
        """If no ra_request is given, RA check is skipped (None result)."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
        )
        # No providers at all: RA None (skip), custody None (skip),
        # WBC missing → BLOCKED_WBC_MISSING
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_WBC_MISSING


# ── Step 12B: WBC evidence classification ────────────────────────────────────


class TestStep12BWbcEvidence:
    """Step 12B: only WbcEvidenceKind.STORE is authoritative."""

    def test_synthetic_wbc_ref_prefix_rejected(self):
        """Synthetic wbc-ref-* references are classified and blocked."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
            WbcEvidenceKind,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="wbc-ref-fake-123",
        )
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.SYNTHETIC
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_WBC_SYNTHETIC

    def test_missing_wbc_when_no_provider_and_no_ref(self):
        """Empty WBC reference yields MISSING evidence."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
            WbcEvidenceKind,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="",
        )
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.MISSING
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_WBC_MISSING

    def test_missing_wbc_when_provider_returns_none(self):
        """Store provider returning None yields MISSING evidence."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
            WbcEvidenceKind,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            wbc_store_provider=lambda ref: None,
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="att-200",
        )
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.MISSING
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_WBC_MISSING

    def test_missing_wbc_when_no_provider_but_ref_given(self):
        """Reference given but no provider yields MISSING evidence."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
            WbcEvidenceKind,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="att-300",
        )
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.MISSING
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_WBC_MISSING

    def test_missing_wbc_when_provider_raises(self):
        """Store provider exception yields MISSING (fail-closed)."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
            WbcEvidenceKind,
        )

        def boom(_):
            raise RuntimeError("store unavailable")

        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            wbc_store_provider=boom,
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="att-301",
        )
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.MISSING
        assert decision.result.verdict == ActionGateVerdict.BLOCKED_WBC_MISSING

    def test_store_evidence_is_authoritative(self):
        """Valid store reservation yields STORE evidence and AUTHORIZED."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
            WbcEvidenceKind,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            wbc_store_provider=lambda ref: _make_store_reservation(),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="att-400",
        )
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.STORE
        assert decision.result.wbc_evidence.is_authoritative
        assert decision.result.verdict == ActionGateVerdict.AUTHORIZED

    def test_store_evidence_carries_glek(self):
        """STORE evidence preserves the global_logical_effect_key."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            wbc_store_provider=lambda ref: _make_store_reservation(),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="att-401",
        )
        assert decision.result.wbc_evidence.global_logical_effect_key == "glek-abc123"

    def test_require_wbc_store_evidence_false_skips_wbc_gate(self):
        """When require_wbc_store_evidence=False, WBC gate is bypassed."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
                require_wbc_store_evidence=False,
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="wbc-ref-bypass",
        )
        # Even though synthetic, WBC gate is bypassed
        assert decision.result.verdict == ActionGateVerdict.AUTHORIZED

    def test_wbc_evidence_kind_values_are_distinct(self):
        """All WbcEvidenceKind values are distinct and not aliased."""
        from arnold_pipelines.megaplan.custody.action_gate import WbcEvidenceKind
        values = [m.value for m in WbcEvidenceKind]
        assert len(values) == len(set(values)), "duplicate enum values"

    def test_synthetic_takes_precedence_over_missing(self):
        """A wbc-ref-* reference is SYNTHETIC, not MISSING."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            WbcEvidenceKind,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            wbc_store_provider=lambda ref: _make_store_reservation(),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            wbc_attempt_reference="wbc-ref-anything",
        )
        # Even though provider exists, wbc-ref- prefix → SYNTHETIC
        assert decision.result.wbc_evidence.kind == WbcEvidenceKind.SYNTHETIC


# ── Step 12C: enforcement staging by action family ──────────────────────────


class TestStep12CEnforcementStaging:
    """Step 12C: enforcement is independently toggled per action family."""

    def test_default_config_enforces_nothing(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGateConfig,
            ActionFamily,
        )
        config = ActionGateConfig()
        for fam in ActionFamily:
            assert not config.is_enforced(fam)

    def test_independent_family_enablement(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGateConfig,
            ActionFamily,
        )
        config = ActionGateConfig(
            enforced_families=frozenset({ActionFamily.GIT}),
        )
        assert config.is_enforced(ActionFamily.GIT)
        assert not config.is_enforced(ActionFamily.CLOUD)
        assert not config.is_enforced(ActionFamily.CUSTODY)

    def test_all_families_can_be_enforced(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGateConfig,
            ActionFamily,
        )
        all_families = frozenset(ActionFamily)
        config = ActionGateConfig(enforced_families=all_families)
        for fam in ActionFamily:
            assert config.is_enforced(fam)

    def test_action_family_values_are_distinct(self):
        from arnold_pipelines.megaplan.custody.action_gate import ActionFamily
        values = [m.value for m in ActionFamily]
        assert len(values) == len(set(values))

    def test_diagnostics_preserved_in_decision(self):
        """ActionGateResult.diagnostics contains the gate schema version."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
        )
        gate = ActionGate(config=ActionGateConfig())
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
        )
        diag = decision.result.diagnostics
        assert diag["action_family"] == "git"
        assert diag["action_target"] == "pr_merge"
        assert diag["gate_schema_version"] == "m10-action-gate-v1"
        assert "enforcement_enabled" in diag

    def test_enforcement_flag_reflected_in_diagnostics(self):
        """The diagnostics enforcement_enabled matches the config."""
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.CLOUD}),
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.CLOUD,
            action_target="deploy",
        )
        assert decision.result.enforcement_enabled is True
        assert decision.result.diagnostics["enforcement_enabled"] is True

    def test_decision_has_timestamp(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
        )
        gate = ActionGate(config=ActionGateConfig())
        decision = gate.evaluate(
            action_family=ActionFamily.NATIVE,
            action_target="run",
        )
        assert decision.timestamp
        assert "T" in decision.timestamp  # ISO format

    def test_authorized_property_only_true_for_authorized_verdict(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
                require_wbc_store_evidence=False,
            ),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
        )
        assert decision.result.verdict == ActionGateVerdict.AUTHORIZED
        assert decision.authorized is True
        assert decision.result.is_authorized is True


# ── evaluate_action_gate functional API ─────────────────────────────────────


class TestEvaluateActionGateFunction:
    """Tests for the one-shot evaluate_action_gate() function."""

    def test_functional_api_shadow_mode(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            evaluate_action_gate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        decision = evaluate_action_gate(
            config=ActionGateConfig(),
            action_family=ActionFamily.GIT,
            action_target="test",
        )
        assert decision.result.verdict == ActionGateVerdict.SHADOW_AUTHORIZED

    def test_functional_api_enforced_with_store_evidence(self):
        from arnold_pipelines.megaplan.custody.action_gate import (
            evaluate_action_gate,
            ActionGateConfig,
            ActionFamily,
            ActionGateVerdict,
        )
        decision = evaluate_action_gate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            action_family=ActionFamily.GIT,
            action_target="test",
            wbc_store_provider=lambda ref: _make_store_reservation(),
            wbc_attempt_reference="att-500",
        )
        assert decision.result.verdict == ActionGateVerdict.AUTHORIZED
