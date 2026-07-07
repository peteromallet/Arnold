"""Focused public-API tests for resolver enforcement behavior.

This file intentionally exercises current public interfaces only:

* ``resolve_run_state`` for canonical-state classification;
* ``classify_repair_dispatch`` for enforcement-on/off dispatch behavior;
* ``project_repair_custody`` for additive observe-only canonical metadata; and
* ``resolver_enforcement_enabled`` for env-flag parsing semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud.feature_flags import resolver_enforcement_enabled
from arnold_pipelines.megaplan.cloud.repair_contract import (
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    DISPATCH_DECISION_BROKEN_SUPERFIXER,
    DISPATCH_DECISION_HUMAN_REQUIRED,
    DISPATCH_DECISION_L1,
    DISPATCH_DECISION_NO_ACTION,
    classify_repair_dispatch,
    project_repair_custody,
)
from arnold_pipelines.megaplan.cloud.repair_requests import enqueue_repair_request
from arnold_pipelines.megaplan.run_state.model import CanonicalState, TypedHumanGate
from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state


def _awf018_target(**overrides: Any) -> dict[str, Any]:
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
            "event_signature_labels": ["authority_divergence/route_metadata_mismatch x293"],
        },
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    payload.update(overrides)
    return payload


def _budget_target(**overrides: Any) -> dict[str, Any]:
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


def _plan_state(failure_kind: str = "", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "demo-plan",
        "current_state": "blocked",
        "resume_cursor": {"retry_strategy": "manual_review"},
    }
    if failure_kind:
        payload["latest_failure"] = {"kind": failure_kind, "phase": "execute"}
    payload.update(overrides)
    return payload


def _custody(request_id: str = "", active_repair: bool = False) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    bucket = "repairable_not_repairing"
    if active_repair:
        attempts.append({"terminal": False, "state": "running"})
        bucket = "repairing"
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


def _real_custody_projection(
    tmp_path: Path,
    target: dict[str, Any],
    *,
    canonical_run_state=None,
) -> dict[str, Any]:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir(parents=True, exist_ok=True)
    repair_data_dir.mkdir(parents=True, exist_ok=True)
    enqueue_repair_request(
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
            plan_state={
                "current_state": "blocked",
                "resume_cursor": {"retry_strategy": "manual_review"},
                "latest_failure": {"kind": "blocked_recovery_not_resolved"},
            },
            current_target=target,
            canonical_run_state=canonical_run_state,
            marker_dir=marker_dir,
            repair_data_dir=repair_data_dir,
        )
    )


class TestResolverStates:
    def test_awf018_is_real_implementation_block(self) -> None:
        result = resolve_run_state(_awf018_target())
        assert result.canonical_state is CanonicalState.REAL_IMPLEMENTATION_BLOCK
        assert result.human_required is False

    def test_budget_is_retryable_execution_block(self) -> None:
        result = resolve_run_state(_budget_target())
        assert result.canonical_state is CanonicalState.RETRYABLE_EXECUTION_BLOCK
        assert result.human_required is False

    def test_broken_repeat_is_broken_state_machine(self) -> None:
        result = resolve_run_state(_broken_target())
        assert result.canonical_state is CanonicalState.BROKEN_STATE_MACHINE

    def test_typed_human_gate_is_preserved(self) -> None:
        result = resolve_run_state(_approval_gate_target())
        assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
        assert result.human_gate is TypedHumanGate.EXPLICIT_APPROVAL


class TestDispatchEnforcement:
    def test_awf018_dispatches_l1_with_active_request(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody("req-awf018-001"),
        )
        assert decision.decision == DISPATCH_DECISION_L1

    def test_budget_dispatches_l1_with_active_request(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_budget_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="budget_exhausted"),
            current_target=_budget_target(),
            custody_projection=_custody("req-budget-001"),
        )
        assert decision.decision == DISPATCH_DECISION_L1

    def test_broken_state_machine_routes_to_broken_superfixer(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_broken_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="repeated_blocker"),
            current_target=_broken_target(),
            custody_projection=_custody("req-broken-001"),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER

    def test_typed_human_gate_routes_to_human_required(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_approval_gate_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="approval_needed"),
            current_target=_approval_gate_target(),
            custody_projection=_custody("req-approval-001"),
        )
        assert decision.decision == DISPATCH_DECISION_HUMAN_REQUIRED

    def test_active_repair_suppresses_double_dispatch(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody("req-awf018-002", active_repair=True),
        )
        assert decision.decision != DISPATCH_DECISION_L1

    def test_missing_canonical_provenance_fails_closed(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=None,
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody("req-awf018-003"),
        )
        assert decision.decision == DISPATCH_DECISION_BROKEN_SUPERFIXER

    def test_machine_actionable_canonical_state_without_request_returns_no_action(self, tmp_path: Path) -> None:
        decision = classify_repair_dispatch(
            canonical_run_state=resolve_run_state(_awf018_target()),
            event_plan_dir=_event_plan_dir(tmp_path),
            plan_state=_plan_state(failure_kind="route_metadata_mismatch"),
            current_target=_awf018_target(),
            custody_projection=_custody(),
        )
        assert decision.decision == DISPATCH_DECISION_NO_ACTION


class TestCustodyObserveMetadata:
    def test_canonical_machine_actionable_state_keeps_repairable_bucket(self, tmp_path: Path) -> None:
        projection = _real_custody_projection(
            tmp_path,
            _awf018_target(),
            canonical_run_state=resolve_run_state(_awf018_target()),
        )
        assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING

    def test_canonical_machine_actionable_state_ignores_legacy_needs_human_metadata(
        self, tmp_path: Path
    ) -> None:
        projection = _real_custody_projection(
            tmp_path,
            _awf018_target(needs_human={"present": True, "summary": "legacy blocker metadata"}),
            canonical_run_state=resolve_run_state(_awf018_target()),
        )
        assert projection["custody_bucket"] == CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING

    def test_observe_adds_canonical_metadata(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "1")
        projection = _real_custody_projection(tmp_path, _awf018_target())
        assert projection["canonical_state"] == "REAL_IMPLEMENTATION_BLOCK"
        assert projection["canonical_human_required"] is False
        assert isinstance(projection["canonical_resolver"], dict)

    def test_observe_off_keeps_legacy_projection(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "0")
        projection = _real_custody_projection(tmp_path, _awf018_target())
        assert "canonical_state" not in projection
        assert "canonical_resolver" not in projection


class TestEnforcementFlag:
    def test_unknown_value_is_truthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "maybe")
        assert resolver_enforcement_enabled() is True

    def test_explicit_off_value_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_RESOLVER_ENFORCEMENT", "off")
        assert resolver_enforcement_enabled() is False
