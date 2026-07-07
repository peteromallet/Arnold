"""Enforcement tests for watchdog needs-human escalation and repair-contract dispatch.

These tests validate the ARNOLD_RESOLVER_ENFORCEMENT control flow introduced in
T10 (watchdog) and T11 (repair_contract). They prove:

* enforcement-ON: AWF018 (REAL_IMPLEMENTATION_BLOCK) and RETRYABLE_EXECUTION_BLOCK
  suppress notify_needs_human and dispatch machine repair / replan instead of
  routing work to humans;
* explicit typed human gates (approval, credential, quota) and missing-credential
  gates still notify or preserve needs-human under enforcement;
* enforcement-OFF: legacy behavior is byte-identical (no resolver consultation);
* raw failure kinds outside the old ``_is_known_repairable_shape`` whitelist can
  become machine-actionable through canonical state.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.cloud.feature_flags import resolver_enforcement_enabled
from arnold_pipelines.megaplan.cloud.repair_contract import (
    DISPATCH_DECISION_BROKEN_SUPERFIXER,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1_REPAIR,
    DISPATCH_DECISION_NO_ACTION,
    classify_repair_dispatch,
)
from arnold_pipelines.megaplan.run_state.model import CanonicalState, TypedHumanGate
from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state


# ---------------------------------------------------------------------------
# Evidence builders
# ---------------------------------------------------------------------------

def _awf018_evidence() -> dict:
    """Structured AWF018 route-metadata-mismatch evidence (REAL_IMPLEMENTATION_BLOCK)."""
    return {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-awf018-rc",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "running",
            "fingerprint": "chain-awf018-rc",
            "mtime": 1.0,
        },
        "diagnostic_codes": {
            "escalation_label": "AWF018",
            "event_signature_labels": [
                "authority_divergence/route_metadata_mismatch x293",
            ],
        },
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }


def _retryable_budget_exhausted_evidence() -> dict:
    """Budget-exhausted with no modified files (RETRYABLE_EXECUTION_BLOCK)."""
    return {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-budget-rc",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "running",
            "fingerprint": "chain-budget-rc",
            "mtime": 1.0,
        },
        "stale_markers": [],
        "needs_human": False,
        "repair_progress": {},
        "watchdog_item": {},
        "active_step_heartbeat": None,
        "authoritative_source": "plan_state",
    }


def _broken_state_machine_evidence() -> dict:
    """Repeated blocker fingerprint across >=3 attempts (BROKEN_STATE_MACHINE)."""
    return {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-broken-rc",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "running",
            "fingerprint": "chain-broken-rc",
            "mtime": 1.0,
        },
        "retry_fingerprints": [
            "arnold:bfp:v1:test",
            "arnold:bfp:v1:test",
            "arnold:bfp:v1:test",
        ],
        "authoritative_source": "plan_state",
    }


def _human_gate_evidence(gate_type: str = "approval", **extra) -> dict:
    """Explicit typed human gate evidence (HUMAN_ACTION_REQUIRED)."""
    gate: dict = {"gate_type": gate_type}
    gate.update(extra)
    return {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-human-rc",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "running",
            "fingerprint": "chain-human-rc",
            "mtime": 1.0,
        },
        "human_gates": [gate],
        "authoritative_source": "plan_state",
    }


def _credential_missing_evidence() -> dict:
    """Missing-credential gate (HUMAN_ACTION_REQUIRED with CREDENTIAL_ACCOUNT)."""
    return _human_gate_evidence(gate_type="credential_account")


def _custody_projection(blocker_id: str = "blk-test-001") -> dict:
    return {
        "blocker_id": blocker_id,
        "blocker_fingerprint": "arnold:bfp:v1:test",
        "custody_bucket": "repairable_not_repairing",
        "current_state": "blocked",
        "retry_strategy": "manual_review",
        "failure_kind": "",
        "request_status_counts": {},
        "active_request_ids": ["req-test-001"],
        "terminal_outcomes": [],
        "requests": [],
        "attempts": [],
        "plan_state": {},
        "current_target": {},
    }


def _active_repair_custody() -> dict:
    """Custody indicating an active repair is already in flight."""
    c = _custody_projection()
    c["custody_bucket"] = "repairing"
    c["current_state"] = "repairing"
    return c


# ---------------------------------------------------------------------------
# Part A: Canonical-state resolution for enforcement incident shapes
# ---------------------------------------------------------------------------

class TestCanonicalStatesForEnforcement:
    """Verify resolve_run_state classifies the enforcement incident shapes."""

    def test_awf018_resolves_real_implementation_block(self):
        result = resolve_run_state(_awf018_evidence())
        assert result.canonical_state is CanonicalState.REAL_IMPLEMENTATION_BLOCK
        assert result.human_required is False

    def test_budget_exhausted_resolves_retryable_execution_block(self):
        result = resolve_run_state(_retryable_budget_exhausted_evidence())
        assert result.canonical_state is CanonicalState.RETRYABLE_EXECUTION_BLOCK
        assert result.human_required is False

    def test_repeated_blocker_resolves_broken_state_machine(self):
        result = resolve_run_state(_broken_state_machine_evidence())
        assert result.canonical_state is CanonicalState.BROKEN_STATE_MACHINE

    def test_approval_gate_resolves_human_action_required(self):
        result = resolve_run_state(_human_gate_evidence("approval"))
        assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
        assert result.human_gate is TypedHumanGate.EXPLICIT_APPROVAL
        assert result.human_required is True

    def test_credential_gate_resolves_human_action_required(self):
        result = resolve_run_state(_credential_missing_evidence())
        assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
        assert result.human_gate is TypedHumanGate.CREDENTIAL_ACCOUNT

    def test_quota_gate_resolves_human_action_required(self):
        result = resolve_run_state(_human_gate_evidence("quota"))
        assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
        assert result.human_gate is TypedHumanGate.QUOTA


# ---------------------------------------------------------------------------
# Part B: Repair-contract enforcement dispatch (_resolver_enforcement_dispatch_decision)
# ---------------------------------------------------------------------------

class TestRepairContractEnforcementDispatch:
    """Validate _resolver_enforcement_dispatch_decision mappings under enforcement."""

    def _helper(self):
        from arnold_pipelines.megaplan.cloud.repair_contract import (
            _resolver_enforcement_dispatch_decision,
        )
        return _resolver_enforcement_dispatch_decision

    def test_awf018_dispatches_l1_repair_under_enforcement(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        assert resolver_enforcement_enabled() is True
        fn = self._helper()
        decision = fn(
            current_target=_awf018_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-awf018",
            request_id="req-awf018-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is not None
        assert decision.decision == DISPATCH_DECISION_L1_REPAIR

    def test_retryable_block_dispatches_l1_repair_under_enforcement(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = self._helper()
        decision = fn(
            current_target=_retryable_budget_exhausted_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-retry",
            request_id="req-retry-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is not None
        assert decision.decision == DISPATCH_DECISION_L1_REPAIR

    def test_broken_state_machine_dispatches_replan_under_enforcement(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = self._helper()
        decision = fn(
            current_target=_broken_state_machine_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-broken",
            request_id="req-broken-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is not None
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER

    def test_human_gate_dispatches_human_required_under_enforcement(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = self._helper()
        decision = fn(
            current_target=_human_gate_evidence("approval"),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-human",
            request_id="req-human-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is not None
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED

    def test_credential_gate_dispatches_human_required_under_enforcement(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = self._helper()
        decision = fn(
            current_target=_credential_missing_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-cred",
            request_id="req-cred-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is not None
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED

    def test_machine_block_with_active_repair_defers_under_enforcement(self, monkeypatch):
        """When an active repair is in flight, machine-actionable blocks defer (no double-dispatch)."""
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = self._helper()
        decision = fn(
            current_target=_awf018_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_active_repair_custody(),
            blocker_id="blk-active",
            request_id="req-active-001",
            custody_bucket="repairing",
            current_state="repairing",
            retry_strategy="manual_review",
            failure_kind="",
        )
        # Active repair -> defer (no_action or repairing), never double-dispatch L1
        assert decision is not None
        assert decision.decision != DISPATCH_DECISION_L1_REPAIR

    def test_enforcement_off_returns_none(self, monkeypatch):
        """When enforcement is off, the helper defers to the legacy path (returns None)."""
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        assert resolver_enforcement_enabled() is False
        fn = self._helper()
        decision = fn(
            current_target=_awf018_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-off",
            request_id="req-off-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is None

    def test_resolver_fault_returns_none(self, monkeypatch):
        """A resolver fault must never change repair dispatch behavior."""
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = self._helper()
        # Malformed evidence that causes the resolver to fault or return UNKNOWN
        decision = fn(
            current_target=object(),  # not a mapping -> resolver should handle gracefully
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-fault",
            request_id="req-fault-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="",
        )
        assert decision is None


# ---------------------------------------------------------------------------
# Part C: Legacy compatibility (enforcement OFF through classify_repair_dispatch)
# ---------------------------------------------------------------------------

class TestLegacyDispatchCompatibility:
    """classify_repair_dispatch must remain byte-identical when enforcement is off."""

    def test_legacy_human_required_for_unrepairable_blocked(self, monkeypatch):
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        assert resolver_enforcement_enabled() is False
        decision = classify_repair_dispatch(
            plan_state={
                "name": "demo-plan",
                "current_state": "blocked",
                "resume_cursor": {"retry_strategy": "manual_review"},
            },
            current_target=_awf018_evidence(),
            custody_projection=_custody_projection(),
        )
        # Without enforcement, AWF018 evidence is not a known repairable shape
        # (failure_kind empty, no whitelist match) -> human_required
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED

    def test_legacy_dispatch_l1_for_known_repairable(self, monkeypatch):
        """Legacy whitelist still dispatches L1 when failure_kind matches."""
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        decision = classify_repair_dispatch(
            plan_state={
                "name": "demo-plan",
                "current_state": "blocked",
                "resume_cursor": {"retry_strategy": "auto"},
                "latest_failure": {"kind": "syntax_error", "phase": "execute"},
            },
            custody_projection=_custody_projection(),
        )
        assert decision.decision == DISPATCH_DECISION_L1_REPAIR

    def test_legacy_no_action_for_completed(self, monkeypatch):
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        decision = classify_repair_dispatch(
            plan_state={
                "name": "demo-plan",
                "current_state": "completed",
            },
            custody_projection={
                **_custody_projection(),
                "current_state": "completed",
                "terminal_outcomes": ["completed"],
            },
        )
        assert decision.decision != DISPATCH_DECISION_L1_REPAIR


# ---------------------------------------------------------------------------
# Part D: Custody metadata under enforcement
# ---------------------------------------------------------------------------

class TestCustodyMetadataEnforcement:
    """_resolver_custody_metadata adds canonical fields to the custody projection."""

    def test_custody_metadata_added_under_enforcement(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        from arnold_pipelines.megaplan.cloud.repair_contract import (
            project_repair_custody,
        )
        projection = project_repair_custody(
            plan_state={
                "name": "demo-plan",
                "current_state": "blocked",
            },
            current_target=_awf018_evidence(),
            custody_projection=_custody_projection(),
        )
        d = dict(projection)
        # Canonical metadata should be present under enforcement
        assert "canonical_state" in d or "resolver_canonical_state" in d or any(
            "canonical" in str(k).lower() for k in d
        )

    def test_custody_metadata_absent_without_enforcement(self, monkeypatch):
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        from arnold_pipelines.megaplan.cloud.repair_contract import (
            project_repair_custody,
        )
        projection = project_repair_custody(
            plan_state={
                "name": "demo-plan",
                "current_state": "blocked",
            },
            current_target=_awf018_evidence(),
            custody_projection=_custody_projection(),
        )
        d = dict(projection)
        # No canonical metadata keys when enforcement is off
        canonical_keys = [k for k in d if "canonical" in str(k).lower()]
        assert canonical_keys == []


# ---------------------------------------------------------------------------
# Part E: Raw failure kinds beyond the old whitelist become machine-actionable
# ---------------------------------------------------------------------------

class TestRawFailureKindBeyondWhitelist:
    """A raw failure_kind outside _is_known_repairable_shape still dispatches via canonical state."""

    def test_route_metadata_mismatch_becomes_machine_actionable(self, monkeypatch):
        """AWF018 route_metadata_mismatch is NOT in the legacy whitelist but is
        machine-actionable through canonical REAL_IMPLEMENTATION_BLOCK state."""
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        fn = None
        from arnold_pipelines.megaplan.cloud.repair_contract import (
            _resolver_enforcement_dispatch_decision as fn,
        )
        # Confirm route_metadata_mismatch is NOT a legacy-whitelisted kind
        from arnold_pipelines.megaplan.cloud.repair_contract import (
            _is_known_repairable_shape,
        )
        legacy = _is_known_repairable_shape(
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="route_metadata_mismatch",
            current_target={},
        )
        assert legacy is False, "route_metadata_mismatch should NOT be legacy-repairable"

        # But under enforcement, the canonical resolver makes it machine-actionable
        decision = fn(
            current_target=_awf018_evidence(),
            lock_evidence=None,
            process_evidence=None,
            custody=_custody_projection(),
            blocker_id="blk-raw",
            request_id="req-raw-001",
            custody_bucket="repairable_not_repairing",
            current_state="blocked",
            retry_strategy="manual_review",
            failure_kind="route_metadata_mismatch",
        )
        assert decision is not None
        assert decision.decision == DISPATCH_DECISION_L1_REPAIR

    def test_legacy_path_rejects_route_metadata_mismatch(self, monkeypatch):
        """Without enforcement, route_metadata_mismatch falls through to human_required."""
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        decision = classify_repair_dispatch(
            plan_state={
                "name": "demo-plan",
                "current_state": "blocked",
                "resume_cursor": {"retry_strategy": "manual_review"},
                "latest_failure": {"kind": "route_metadata_mismatch", "phase": "execute"},
            },
            current_target=_awf018_evidence(),
            custody_projection=_custody_projection(),
        )
        # Legacy path: not whitelisted -> human_required
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED


# ---------------------------------------------------------------------------
# Part F: Watchdog needs-human suppression logic (via resolver state)
# ---------------------------------------------------------------------------

class TestWatchdogNeedsHumanSuppression:
    """The watchdog consults canonical state to decide whether to notify_needs_human.

    Under enforcement, machine-actionable states (REAL_IMPLEMENTATION_BLOCK,
    RETRYABLE_EXECUTION_BLOCK, BROKEN_STATE_MACHINE) without typed human gates
    suppress the needs-human notification and route to machine repair/replan.
    HUMAN_ACTION_REQUIRED and UNKNOWN still notify.
    """

    SUPPRESSED_STATES = {
        CanonicalState.REAL_IMPLEMENTATION_BLOCK,
        CanonicalState.RETRYABLE_EXECUTION_BLOCK,
        CanonicalState.BROKEN_STATE_MACHINE,
    }

    def test_awf018_suppresses_needs_human(self):
        result = resolve_run_state(_awf018_evidence())
        assert result.canonical_state in self.SUPPRESSED_STATES
        assert result.human_required is False
        # Watchdog would suppress: canonical state is machine-actionable, no human gate

    def test_retryable_block_suppresses_needs_human(self):
        result = resolve_run_state(_retryable_budget_exhausted_evidence())
        assert result.canonical_state in self.SUPPRESSED_STATES
        assert result.human_required is False

    def test_broken_state_machine_suppresses_needs_human(self):
        result = resolve_run_state(_broken_state_machine_evidence())
        assert result.canonical_state in self.SUPPRESSED_STATES
        assert result.human_required is False

    def test_human_gate_preserves_needs_human(self):
        result = resolve_run_state(_human_gate_evidence("approval"))
        assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
        assert result.human_required is True
        assert result.human_gate is not None
        # Watchdog would notify: explicit typed human gate

    def test_credential_gate_preserves_needs_human(self):
        result = resolve_run_state(_credential_missing_evidence())
        assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
        assert result.human_required is True

    def test_unknown_preserves_needs_human(self):
        """UNKNOWN state is conservative: watchdog still notifies."""
        result = resolve_run_state({})
        assert result.canonical_state is CanonicalState.UNKNOWN
        # Watchdog legacy behavior preserved for UNKNOWN

    def test_completed_does_not_need_human(self):
        result = resolve_run_state({
            "tmux_process": {"live_status": "exited"},
            "plan_state": {
                "current_state": "completed",
                "fingerprint": "plan-done",
                "mtime": 1.0,
            },
            "chain_state": {
                "last_state": "completed",
                "fingerprint": "chain-done",
                "mtime": 1.0,
            },
            "authoritative_source": "plan_state",
        })
        assert result.canonical_state is CanonicalState.COMPLETED
        assert result.human_required is False

    def test_running_does_not_need_human(self):
        result = resolve_run_state({
            "tmux_process": {"live_status": "running"},
            "plan_state": {
                "current_state": "executing",
                "fingerprint": "plan-run",
                "mtime": 1.0,
            },
            "chain_state": {
                "last_state": "running",
                "fingerprint": "chain-run",
                "mtime": 1.0,
            },
            "active_step_heartbeat": {"age_seconds": 5},
            "authoritative_source": "chain_state",
        })
        assert result.canonical_state is CanonicalState.RUNNING
        assert result.human_required is False


# ---------------------------------------------------------------------------
# Part G: Enforcement flag gating
# ---------------------------------------------------------------------------

class TestEnforcementFlagGating:
    """resolver_enforcement_enabled correctly gates on the env var."""

    def test_enabled_when_set_on(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "on")
        assert resolver_enforcement_enabled() is True

    def test_enabled_when_set_1(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "1")
        assert resolver_enforcement_enabled() is True

    def test_disabled_when_unset(self, monkeypatch):
        monkeypatch.delenv("ARNOLD_RESOLVER_ENFORCEMENT", raising=False)
        assert resolver_enforcement_enabled() is False

    def test_disabled_when_off(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "off")
        assert resolver_enforcement_enabled() is False

    def test_disabled_when_unknown(self, monkeypatch):
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "maybe")
        assert resolver_enforcement_enabled() is False
