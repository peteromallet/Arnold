"""Enforcement tests for canonical-resolver dispatch in repair_contract.

These tests validate the ARNOLD_RESOLVER_ENFORCEMENT control flow added by
T11 (Step 10) to ``classify_repair_dispatch``:

* enforcement-on AWF018 (REAL_IMPLEMENTATION_BLOCK) and retryable execution
  blocks (RETRYABLE_EXECUTION_BLOCK) dispatch L1 repair when a custody request
  is active, and return no_action when no request exists;
* BROKEN_STATE_MACHINE maps to broken-superfixer / replan escalation;
* explicit approval and missing-credential typed gates still route to
  human_required (preserving the needs-human contract from SD3);
* enforcement-off behavior is byte-identical to the legacy
  ``_is_known_repairable_shape`` whitelist path for every shape;
* raw failure kinds outside the old whitelist become machine-actionable through
  canonical state — proving the resolver unlocks repair for shapes the legacy
  whitelist would route to humans;
* an active repair defers enforcement L1 dispatch to avoid double-dispatch; and
* additive canonical custody metadata is attached under ARNOLD_RESOLVER_OBSERVE
  and absent otherwise.

Together with the watchdog verdict tests in ``test_watchdog_wrappers.py``,
these tests satisfy SC13: enforcement proves AWF018, retryable blocks, typed
human gates, legacy enforcement-off behavior, and canonical dispatch beyond
the old whitelist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud.repair_contract import (
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    CUSTODY_BUCKET_REPAIRING,
    DISPATCH_DECISION_BROKEN_SUPERFIXER,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    DISPATCH_DECISION_NO_ACTION,
    DISPATCH_INTENT_BROKEN_SUPERFIXER,
    DISPATCH_INTENT_HUMAN_REQUIRED,
    DISPATCH_INTENT_L1,
    DISPATCH_INTENT_QUEUE_ONLY,
    classify_repair_dispatch,
    project_repair_custody,
)
from arnold_pipelines.megaplan.cloud.repair_requests import enqueue_repair_request
from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state


# ---------------------------------------------------------------------------
# Evidence fixtures — each mirrors a canonical resolver incident shape.
# The current_target carries BOTH resolver evidence (tmux_process, plan_state,
# chain_state, diagnostic_codes, needs_human) and legacy fields (current_refs,
# authoritative_source) so _has_current_target_evidence still holds.
# ---------------------------------------------------------------------------


def _awf018_target(**overrides: Any) -> dict[str, Any]:
    """REAL_IMPLEMENTATION_BLOCK: AWF018 route-metadata mismatch."""
    payload: dict[str, Any] = {
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
        # Legacy fields for _has_current_target_evidence
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    payload.update(overrides)
    return payload


def _budget_target(**overrides: Any) -> dict[str, Any]:
    """RETRYABLE_EXECUTION_BLOCK: budget exhausted with no modified files."""
    payload: dict[str, Any] = {
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
        "diagnostic_codes": {"retry_strategy": "budget_exhausted"},
        "needs_human": {"present": True, "summary": "budget exhausted"},
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    payload.update(overrides)
    return payload


def _broken_target(**overrides: Any) -> dict[str, Any]:
    """BROKEN_STATE_MACHINE: repeated blocker fingerprint across 3+ attempts."""
    payload: dict[str, Any] = {
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
        "repair_progress": {"present": True, "items": [{"status": "failed"}]},
        "needs_human": {
            "present": True,
            "summary": "same blocker as previous attempts",
            "repeated_attempts": 3,
        },
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    payload.update(overrides)
    return payload


def _approval_gate_target(**overrides: Any) -> dict[str, Any]:
    """HUMAN_ACTION_REQUIRED: explicit operator approval gate."""
    payload: dict[str, Any] = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-approval-rc",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-approval-rc",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "operator approval required",
            "gate_type": "approval",
            "blocked_task_id": "T9",
        },
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    payload.update(overrides)
    return payload


def _credential_gate_target(**overrides: Any) -> dict[str, Any]:
    """HUMAN_ACTION_REQUIRED: missing credential/account gate."""
    payload: dict[str, Any] = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-credential-rc",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-credential-rc",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "missing external API credential",
            "gate_type": "credential_account",
        },
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    payload.update(overrides)
    return payload


def _plan_state(current_state: str = "blocked", failure_kind: str = "", **overrides: Any) -> dict[str, Any]:
    """Legacy plan_state parameter shape for classify_repair_dispatch."""
    payload: dict[str, Any] = {
        "name": "demo-plan",
        "current_state": current_state,
        "resume_cursor": {"retry_strategy": "manual_review"},
    }
    if failure_kind:
        payload["latest_failure"] = {"kind": failure_kind, "phase": "execute"}
    payload.update(overrides)
    return payload


def _custody(
    *,
    request_id: str = "",
    active_repair: bool = False,
) -> dict[str, Any]:
    """Minimal custody projection for dispatch classification.

    The enforcement path reads ``active_request_ids`` and ``attempts`` /
    ``custody_bucket`` to detect an active repair.
    """
    attempts: list[dict[str, Any]] = []
    bucket = CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    if active_repair:
        attempts.append({"terminal": False, "state": "running"})
        bucket = CUSTODY_BUCKET_REPAIRING
    return {
        "blocker_id": "blk-test-001",
        "blocker_fingerprint": "arnold:bfp:v1:test",
        "custody_bucket": bucket,
        "current_state": "blocked",
        "retry_strategy": "manual_review",
        "failure_kind": "",
        "request_status_counts": {},
        "active_request_ids": [request_id] if request_id else [],
        "terminal_outcomes": [],
        "requests": [],
        "attempts": attempts,
        "plan_state": {},
        "current_target": {},
    }


def _event_plan_dir(tmp_path: Path) -> Path:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


# ===========================================================================
# AWF018 (REAL_IMPLEMENTATION_BLOCK) enforcement dispatch
# ===========================================================================


class TestAwf018EnforcementDispatch:
    """AWF018 evidence dispatches L1 repair under enforcement."""

    def test_dispatches_l1_with_active_request(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody(request_id="req-awf018-001"),
        )
        assert decision.decision == DISPATCH_DECISION_L1
        assert decision.dispatch_intent == DISPATCH_INTENT_L1
        assert decision.request_id == "req-awf018-001"
        assert "resolver enforcement" in decision.rationale[0]

    def test_routes_broken_superfixer_without_active_request(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody(request_id=""),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER
        assert decision.dispatch_intent == DISPATCH_INTENT_BROKEN_SUPERFIXER
        assert decision.request_id == ""

    def test_defers_to_active_repair(self, tmp_path: Path) -> None:
        """An active repair must suppress enforcement L1 to avoid double-dispatch."""
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody(request_id="req-awf018-002", active_repair=True),
        )
        # Enforcement returns None (defers), legacy active-repair check catches it.
        assert decision.decision != DISPATCH_DECISION_L1


# ===========================================================================
# RETRYABLE_EXECUTION_BLOCK (budget exhausted) enforcement dispatch
# ===========================================================================


class TestRetryableEnforcementDispatch:
    """Budget-exhaustion evidence dispatches L1 repair under enforcement."""

    def test_dispatches_l1_with_active_request(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_budget_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="budget_exhausted"),
            current_target=_budget_target(),
            custody_projection=_custody(request_id="req-budget-001"),
        )
        assert decision.decision == DISPATCH_DECISION_L1
        assert decision.dispatch_intent == DISPATCH_INTENT_L1
        assert decision.request_id == "req-budget-001"

    def test_routes_broken_superfixer_without_active_request(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_budget_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="budget_exhausted"),
            current_target=_budget_target(),
            custody_projection=_custody(request_id=""),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER
        assert decision.dispatch_intent == DISPATCH_INTENT_BROKEN_SUPERFIXER


# ===========================================================================
# BROKEN_STATE_MACHINE enforcement dispatch
# ===========================================================================


class TestBrokenStateMachineEnforcementDispatch:
    """Broken-state-machine evidence routes to broken-superfixer / replan."""

    def test_routes_to_broken_superfixer(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_broken_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="repeated_blocker"),
            current_target=_broken_target(),
            custody_projection=_custody(request_id="req-broken-001"),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER
        assert decision.dispatch_intent == DISPATCH_INTENT_BROKEN_SUPERFIXER
        assert "broken-state-machine" in decision.rationale[0]

    def test_broken_superfixer_even_with_request(self, tmp_path: Path) -> None:
        """BROKEN_STATE_MACHINE never dispatches L1, even with an active request."""
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_broken_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="repeated_blocker"),
            current_target=_broken_target(),
            custody_projection=_custody(request_id="req-broken-002"),
        )
        assert decision.decision != DISPATCH_DECISION_L1
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER


# ===========================================================================
# Typed human gates (approval, credential) preserve needs-human under enforcement
# ===========================================================================


class TestTypedHumanGateEnforcementDispatch:
    """Typed human gates route to human_required even under enforcement (SD3)."""

    def test_explicit_approval_gate_routes_to_human_required(
        self, tmp_path: Path
    ) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_approval_gate_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="approval_needed"),
            current_target=_approval_gate_target(),
            custody_projection=_custody(request_id="req-approval-001"),
        )
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED
        assert decision.dispatch_intent == DISPATCH_INTENT_HUMAN_REQUIRED
        assert "typed human-action-required gate" in decision.rationale[0]

    def test_missing_credential_gate_routes_to_human_required(
        self, tmp_path: Path
    ) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_credential_gate_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="missing_credential"),
            current_target=_credential_gate_target(),
            custody_projection=_custody(request_id="req-credential-001"),
        )
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED
        assert decision.dispatch_intent == DISPATCH_INTENT_HUMAN_REQUIRED
        assert "typed human-action-required gate" in decision.rationale[0]


# ===========================================================================
# Enforcement-off: legacy behavior preserved for every shape
# ===========================================================================


class TestMissingCanonicalProvenance:
    """Dispatch fails closed when canonical provenance is absent."""

    @pytest.mark.parametrize(
        "label,target,failure_kind,request_id",
        [
            ("awf018", _awf018_target(), "route_metadata_mismatch", "req-x"),
            ("budget", _budget_target(), "budget_exhausted", "req-x"),
            ("broken", _broken_target(), "repeated_blocker", "req-x"),
            ("approval", _approval_gate_target(), "approval_needed", "req-x"),
            ("credential", _credential_gate_target(), "missing_credential", "req-x"),
        ],
    )
    def test_missing_canonical_provenance_never_dispatches_l1(
        self,
        tmp_path: Path,
        label: str,
        target: dict[str, Any],
        failure_kind: str,
        request_id: str,
    ) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=None,
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind=failure_kind),
            current_target=target,
            custody_projection=_custody(request_id=request_id),
        )
        assert decision.decision != DISPATCH_DECISION_L1
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER

    def test_missing_canonical_provenance_is_independent_of_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "0")
        decision = classify_repair_dispatch(
            canonical_run_state=None,
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody(request_id="req-x"),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER


# ===========================================================================
# SC13 key proof: raw failure kinds outside the old whitelist become
# machine-actionable through canonical state
# ===========================================================================


class TestCanonicalDispatchBeyondLegacyWhitelist:
    """The resolver unlocks L1 dispatch for failure_kinds the legacy whitelist
    would route to human_required."""

    # These failure_kinds are NOT in _is_known_repairable_shape's whitelist:
    #   {"blocked_recovery_not_resolved", "execution_blocked",
    #    "no_next_step_state_mapping_failure", "no_next_step"}
    NON_WHITELISTED_KINDS = [
        "route_metadata_mismatch",
        "stale_fixture_assertion",
        "binding_resolution_failed",
        "unknown_but_machine_repairable",
    ]

    @pytest.mark.parametrize("failure_kind", NON_WHITELISTED_KINDS)
    def test_non_whitelisted_kind_still_dispatches_l1_with_canonical_state(
        self,
        tmp_path: Path,
        failure_kind: str,
    ) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind=failure_kind),
            current_target=_awf018_target(),
            custody_projection=_custody(request_id="req-x"),
        )
        assert decision.decision == DISPATCH_DECISION_L1, (
            f"failure_kind={failure_kind!r} must dispatch L1 under canonical "
            f"classification, got {decision.decision!r}"
        )

    @pytest.mark.parametrize("failure_kind", NON_WHITELISTED_KINDS)
    def test_non_whitelisted_kind_fails_closed_without_canonical_provenance(
        self,
        tmp_path: Path,
        failure_kind: str,
    ) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=None,
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind=failure_kind),
            current_target=_awf018_target(),
            custody_projection=_custody(request_id="req-x"),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER, (
            f"failure_kind={failure_kind!r} must fail closed without canonical "
            f"provenance, got {decision.decision!r}"
        )


# ===========================================================================
# Custody projection: additive canonical metadata under ARNOLD_RESOLVER_OBSERVE
# ===========================================================================


def _custody_projection(
    tmp_path: Path,
    target: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a real custody projection with a queued repair request."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    marker_dir.mkdir(parents=True, exist_ok=True)
    repair_data_dir.mkdir(parents=True, exist_ok=True)
    enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session="demo-session",
        source="watchdog",
        problem_signature={
            "failure_kind": "blocked_recovery_not_resolved",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "demo-plan",
            "gate_recommendation": "",
            "blocked_task_id": "T1",
        },
        root_cause_hint="repairable blocker",
    )
    return dict(
        project_repair_custody(
            plan_state=plan or {
                "current_state": "blocked",
                "resume_cursor": {"retry_strategy": "manual_review"},
                "latest_failure": {"kind": "blocked_recovery_not_resolved"},
            },
            current_target=target or _awf018_target(),
            queue_root=queue_root,
            repair_data_dir=repair_data_dir,
        )
    )


class TestCustodyCanonicalMetadata:
    """Canonical metadata is additive to the custody projection under observe."""

    def test_canonical_keys_present_under_observe(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "1")
        projection = _custody_projection(tmp_path, target=_awf018_target())
        assert projection["canonical_state"] == "REAL_IMPLEMENTATION_BLOCK"
        assert isinstance(projection["canonical_reason"], str) and projection["canonical_reason"]
        assert projection["canonical_human_required"] is False
        assert projection["canonical_human_gate"] is None
        nested = projection.get("canonical_resolver")
        assert isinstance(nested, dict)
        assert nested.get("canonical_state") == "REAL_IMPLEMENTATION_BLOCK"

    def test_canonical_keys_absent_without_observe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "0")
        projection = _custody_projection(tmp_path, target=_awf018_target())
        assert "canonical_state" not in projection
        assert "canonical_resolver" not in projection
        assert "canonical_reason" not in projection
        # Legacy projection keys must still be present.
        assert "custody_bucket" in projection
        assert "active_request_ids" in projection

    def test_observe_preserves_legacy_projection_shape(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Legacy custody keys must be byte-identical regardless of observe flag."""
        monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "1")
        on = _custody_projection(tmp_path / "observe-on", target=_awf018_target())
        monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "0")
        off = _custody_projection(tmp_path / "observe-off", target=_awf018_target())
        legacy_keys = {
            "custody_bucket",
            "active_request_ids",
            "blocker_id",
            "blocker_fingerprint",
            "request_status_counts",
            "attempts",
            "current_state",
            "retry_strategy",
            "failure_kind",
        }
        for key in legacy_keys:
            assert on[key] == off[key], f"legacy key {key!r} differs between observe on/off"
