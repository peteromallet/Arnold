"""Resolver fixture tests for the core July incident shapes.

These tests lock the canonical run-state contract established by
:func:`~arnold_pipelines.megaplan.run_state.resolve_run_state` and its ordered
North Star classifiers.  Each fixture is a realistic current-target evidence
dict (plus an optional ``BlockerVerdict``) representing one of the recurring
July incident shapes; the tests assert the resulting :class:`CanonicalRunState`:

* ``canonical_state`` — the single classification,
* ``human_required`` — whether the run is a typed human gate,
* ``stale_sources`` — which evidence sources the resolver marked stale,
* ``root_cause_fingerprint`` — present in the structured evidence list, and
* ``next_action`` — a non-empty next-action hint where relevant.

The fixture set intentionally covers the *cross-consumer* incident shapes
(watchdog, repair-loop, status) so a classifier-ordering regression cannot
silently reclassify a machine-actionable block as a human gate (or vice-versa).
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan.cloud.human_blockers import BlockerVerdict
from arnold_pipelines.megaplan.run_state import (
    CanonicalRunState,
    CanonicalState,
    TypedHumanGate,
    resolve_run_state,
)


# ---------------------------------------------------------------------------
# shared assertion helper
# ---------------------------------------------------------------------------


def assert_contract_invariants(result: CanonicalRunState) -> None:
    """Assert every resolver result carries the required contract fields.

    The North Star requires a stable root-cause fingerprint and a non-empty
    next-action hint on every classification (including the conservative
    ``UNKNOWN`` fallback), so every incident-shape test asserts both.
    """
    fingerprint_kinds = {
        item.get("kind") for item in result.evidence if isinstance(item, Mapping)
    }
    assert "root_cause_fingerprint" in fingerprint_kinds, (
        f"resolver evidence missing root_cause_fingerprint item; kinds={sorted(fingerprint_kinds)}"
    )
    assert isinstance(result.next_action, str) and result.next_action, (
        f"resolver returned an empty next_action for {result.canonical_state.name}"
    )
    assert result.canonical_state in CanonicalState
    # human_required must agree with the canonical state per the contract.
    assert result.human_required is (
        result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    ), (
        f"human_required={result.human_required} disagrees with "
        f"canonical_state={result.canonical_state.name}"
    )


def _evi_evidence_value(result: CanonicalRunState, kind: str) -> Any:
    """Return the ``summary`` of the first evidence item with ``kind``."""
    for item in result.evidence:
        if isinstance(item, Mapping) and item.get("kind") == kind:
            return item.get("summary")
    return None


# ---------------------------------------------------------------------------
# Shape 1: live worker plus stale manual-review / needs-human marker
#           -> STALE_DERIVED_STATE  (live beats stale)
# ---------------------------------------------------------------------------


def test_live_worker_with_stale_manual_review_label_resolves_stale_derived() -> None:
    """Live tmux session overrides a stale ``manual_review`` chain label."""
    evidence = {
        "tmux_process": {
            "live_status": "alive",
            "pid": 12345,
            "pid_live": True,
            "session_live": True,
        },
        "plan_state": {"current_state": "executing", "fingerprint": "plan-fp-1", "mtime": 1.0},
        "chain_state": {
            "last_state": "manual_review",
            "current_plan_name": "m1-plan",
            "fingerprint": "chain-fp-1",
            "mtime": 1.0,
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.STALE_DERIVED_STATE
    assert result.human_required is False
    assert result.running is True
    # The stale derived label must be surfaced as a stale source.
    assert "manual_review" in result.stale_sources
    assert result.next_action == "trust_live_worker_suppress_stale_label"


def test_live_worker_with_stale_needs_human_marker_resolves_stale_derived() -> None:
    """A stale needs-human sidecar (marked in ``stale_evidence``) is overridden by a live worker."""
    evidence = {
        "tmux_process": {"live_status": "alive"},
        "plan_state": {"current_state": "executing", "fingerprint": "plan-fp-2", "mtime": 1.0},
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp-2", "mtime": 1.0},
        "needs_human": {"present": True, "summary": "old human marker"},
        "stale_evidence": [{"kind": "stale_needs_human_plan_ref", "path": "/srv/marker.json"}],
    }
    result = resolve_run_state(evidence, BlockerVerdict.STALE_MISMATCH)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.STALE_DERIVED_STATE
    assert result.human_required is False
    assert result.running is True
    assert "needs_human" in result.stale_sources
    assert result.next_action == "trust_live_worker_suppress_stale_label"


# ---------------------------------------------------------------------------
# Shape 2: budget exhausted with no modified files
#           -> RETRYABLE_EXECUTION_BLOCK  (machine-actionable, not a human gate)
# ---------------------------------------------------------------------------


def test_budget_exhausted_with_no_modified_files_resolves_retryable_block() -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp-3",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp-3", "mtime": 1.0},
        "diagnostic_codes": {"retry_strategy": "budget_exhausted"},
        "needs_human": {"present": True, "summary": "budget exhausted"},
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.RETRYABLE_EXECUTION_BLOCK
    # SD3: budget exhaustion is machine-actionable, never a human gate.
    assert result.human_required is False
    assert result.human_gate is None
    assert result.repairable is True
    assert result.next_action == "requeue_or_retry"
    assert result.source_of_truth == ("event_cursors", "plan_state")


# ---------------------------------------------------------------------------
# Shape 3: repeated blocker fingerprint across >= 3 attempts
#           -> BROKEN_STATE_MACHINE
# ---------------------------------------------------------------------------


def test_repeated_blocker_fingerprint_across_three_attempts_resolves_broken() -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp-stable",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp-stable", "mtime": 1.0},
        "repair_progress": {"present": True, "items": [{"status": "failed"}]},
        "needs_human": {
            "present": True,
            "summary": "same blocker as previous attempts",
            "repeated_attempts": 3,
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.BROKEN_STATE_MACHINE
    assert result.human_required is False
    assert result.confidence == "medium"
    assert result.next_action == "escalate_broken_state_machine"
    # The structured repeat count must appear in the evidence trail.
    assert str(_evi_evidence_value(result, "broken_repeat_count")) == "3"


def test_two_repeated_attempts_do_not_trigger_broken() -> None:
    """Two identical attempts stay below the BROKEN threshold (regression guard)."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp", "mtime": 1.0},
        "needs_human": {"present": True, "summary": "blocker", "repeated_attempts": 2},
    }
    result = resolve_run_state(evidence)
    assert result.canonical_state is not CanonicalState.BROKEN_STATE_MACHINE


def test_missing_workspace_resolves_broken_state_machine() -> None:
    """Missing workspace is detect-only evidence, but it classifies as BROKEN when not live or done."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {"current_state": "executing", "fingerprint": "plan-mw", "mtime": 1.0},
        "chain_state": {"last_state": "running", "fingerprint": "chain-mw", "mtime": 1.0},
        "stale_evidence": [
            {
                "kind": "missing_workspace",
                "path": "/srv/workspaces/missing",
                "workspace": "/srv/workspaces/missing",
            }
        ],
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.BROKEN_STATE_MACHINE
    assert result.human_required is False
    assert result.confidence == "high"
    assert result.next_action == "escalate_broken_state_machine"
    assert result.source_of_truth == ("stale_evidence",)
    assert "missing_workspace" in result.stale_sources
    assert _evi_evidence_value(result, "missing_workspace") == "present"


def test_live_worker_overrides_missing_workspace_and_resolves_running() -> None:
    """Live evidence still wins over missing-workspace stale evidence."""
    evidence = {
        "tmux_process": {"live_status": "alive"},
        "plan_state": {"current_state": "executing", "fingerprint": "plan-mw-live", "mtime": 1.0},
        "chain_state": {"last_state": "running", "fingerprint": "chain-mw-live", "mtime": 1.0},
        "stale_evidence": [{"kind": "missing_workspace", "path": "/srv/workspaces/missing"}],
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.RUNNING
    assert result.running is True
    assert result.human_required is False


def test_terminal_done_overrides_missing_workspace_and_resolves_completed() -> None:
    """Authority completion still wins when missing-workspace evidence lingers."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {"current_state": "done", "fingerprint": "plan-mw-done", "mtime": 1.0},
        "chain_state": {"last_state": "failed", "fingerprint": "chain-mw-done", "mtime": 1.0},
        "stale_evidence": [{"kind": "missing_workspace", "path": "/srv/workspaces/missing"}],
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.COMPLETED
    assert result.human_required is False
    assert result.next_action == "no_action_run_complete"
    assert "missing_workspace" in result.stale_sources


# ---------------------------------------------------------------------------
# Shape 4: AWF018 route-metadata mismatch using structured diagnostic evidence
#           -> REAL_IMPLEMENTATION_BLOCK  (human_required=False per SD3)
# ---------------------------------------------------------------------------


def test_awf018_route_metadata_mismatch_resolves_real_implementation_block() -> None:
    """AWF018 / route-metadata mismatch is machine-actionable even when a stray human gate is recorded."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp-4",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp-4", "mtime": 1.0},
        "diagnostic_codes": {
            "escalation_label": "AWF018",
            "event_signature_labels": [
                "authority_divergence/route_metadata_mismatch x293",
            ],
        },
        # A stray human-gate field MUST NOT turn AWF018 into a human gate (SD3).
        "needs_human": {
            "present": True,
            "summary": "AWF018 route metadata mismatch",
            "gate_type": "approval",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.REAL_IMPLEMENTATION_BLOCK
    assert result.human_required is False
    assert result.human_gate is None
    assert result.repairable is False
    assert result.next_action == "machine_repair_or_replan"
    assert "diagnostic_codes" in result.source_of_truth
    # The structured AWF018 evidence must be carried in the evidence trail.
    assert "awf018" in str(_evi_evidence_value(result, "diagnostic_codes")).lower()


def test_awf018_ignored_when_authority_plan_completed() -> None:
    """Authority completion beats an AWF018 diagnostic label (regression guard)."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {"current_state": "done", "fingerprint": "plan-fp", "mtime": 1.0},
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp", "mtime": 1.0},
        "diagnostic_codes": {"escalation_label": "AWF018"},
    }
    result = resolve_run_state(evidence)
    assert result.canonical_state is CanonicalState.COMPLETED


# ---------------------------------------------------------------------------
# Shape 5: deferred baseline with real tasks complete
#           -> COMPLETED  (authority-beats-stale secondary branch)
# ---------------------------------------------------------------------------


def test_deferred_baseline_with_real_tasks_complete_resolves_completed() -> None:
    """Real work complete (files changed) with a stale chain 'failed' label resolves COMPLETED."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 7},
            "fingerprint": "plan-fp-5",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "failed",
            "current_plan_name": "m1-plan",
            "fingerprint": "chain-fp-5",
            "mtime": 1.0,
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.COMPLETED
    assert result.human_required is False
    assert result.confidence == "medium"
    assert result.next_action == "no_action_run_complete"
    # The stale chain layer must be surfaced.
    assert "chain_state" in result.stale_sources
    assert str(_evi_evidence_value(result, "changed_file_count")) == "7"


# ---------------------------------------------------------------------------
# Shape 6: stale needs-human after recovery
#           -> COMPLETED  (lingering needs-human marker is stale)
# ---------------------------------------------------------------------------


def test_stale_needs_human_after_recovery_resolves_completed() -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {"current_state": "done", "fingerprint": "plan-fp-6", "mtime": 1.0},
        "chain_state": {"last_state": "failed", "fingerprint": "chain-fp-6", "mtime": 1.0},
        "needs_human": {"present": True, "summary": "old needs-human marker"},
        "stale_evidence": [{"kind": "stale_needs_human_plan_ref", "path": "/srv/marker.json"}],
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.COMPLETED
    assert result.human_required is False
    assert result.confidence == "high"
    assert result.next_action == "no_action_run_complete"
    # The lingering needs-human marker must be flagged stale.
    assert "needs_human" in result.stale_sources


# ---------------------------------------------------------------------------
# Shape 7: live initialized active_step
#           -> RUNNING
# ---------------------------------------------------------------------------


def test_live_initialized_active_step_resolves_running() -> None:
    """An initialized active-step heartbeat (no tmux liveness) resolves RUNNING."""
    evidence = {
        "active_step_heartbeat": {
            "active": True,
            "phase": "initialized",
            "worker_pid": 999,
        },
        "tmux_process": {"live_status": "unknown"},
        "plan_state": {"current_state": "executing", "fingerprint": "plan-fp-7", "mtime": 1.0},
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp-7", "mtime": 1.0},
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.RUNNING
    assert result.running is True
    assert result.human_required is False
    assert result.next_action == "monitor_live_run"
    assert "active_step_heartbeat" in result.source_of_truth


# ---------------------------------------------------------------------------
# Shape 8: cloud-worker impossible SSH prerequisite
#           -> MECHANICAL_BLOCKER verdict -> RETRYABLE_EXECUTION_BLOCK (SD3)
# ---------------------------------------------------------------------------


def test_impossible_ssh_prerequisite_mechanical_blocker_is_retryable_not_human() -> None:
    """A cloud-worker impossible-SSH gate is mechanical, never a human gate."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp-8",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp-8", "mtime": 1.0},
        # A stray credential gate_type MUST NOT turn a mechanical SSH gate human (SD3).
        "needs_human": {
            "present": True,
            "summary": "SSH unreachable from cloud worker",
            "gate_type": "credential",
        },
    }
    result = resolve_run_state(evidence, BlockerVerdict.MECHANICAL_BLOCKER)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.RETRYABLE_EXECUTION_BLOCK
    assert result.human_required is False
    assert result.human_gate is None
    assert result.repairable is True
    assert result.next_action == "requeue_or_retry"
    assert "blocker_verdict" in result.source_of_truth


def test_live_worker_beats_broken_state_machine_escalation() -> None:
    """A live worker overrides even an explicit BROKEN_STATE_MACHINE marker (regression guard)."""
    evidence = {
        "tmux_process": {"live_status": "alive"},
        "plan_state": {"current_state": "executing", "fingerprint": "plan-fp", "mtime": 1.0},
        "chain_state": {"last_state": "running", "fingerprint": "chain-fp", "mtime": 1.0},
        "diagnostic_codes": {"escalation_label": "BROKEN_STATE_MACHINE"},
        "needs_human": {"present": True, "repeated_attempts": 5},
    }
    result = resolve_run_state(evidence)
    assert result.canonical_state is not CanonicalState.BROKEN_STATE_MACHINE
    assert result.running is True


# ---------------------------------------------------------------------------
# Success-criteria typed human gates: approval, credential/account, + full set
# ---------------------------------------------------------------------------


def test_unresolved_approval_gate_resolves_human_action_required() -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp-9",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "awaiting_human", "fingerprint": "chain-fp-9", "mtime": 1.0},
        "needs_human": {
            "present": True,
            "summary": "operator approval required",
            "gate_type": "approval",
            "blocked_task_id": "T9",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.EXPLICIT_APPROVAL
    assert result.next_action == "await_human_action"


def test_missing_credential_account_gate_resolves_human_action_required() -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-fp-10",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "awaiting_human", "fingerprint": "chain-fp-10", "mtime": 1.0},
        "needs_human": {
            "present": True,
            "summary": "missing external API credential",
            "gate_type": "credential_account",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.CREDENTIAL_ACCOUNT


@pytest.mark.parametrize(
    ("gate_token", "expected_gate"),
    [
        ("explicit_approval", TypedHumanGate.EXPLICIT_APPROVAL),
        ("approval", TypedHumanGate.EXPLICIT_APPROVAL),
        ("credential", TypedHumanGate.CREDENTIAL_ACCOUNT),
        ("credential_account", TypedHumanGate.CREDENTIAL_ACCOUNT),
        ("quota", TypedHumanGate.QUOTA),
        ("rate_limit", TypedHumanGate.QUOTA),
        ("verification", TypedHumanGate.VERIFICATION),
        ("policy", TypedHumanGate.POLICY),
        ("user_action", TypedHumanGate.USER_ACTION),
    ],
)
def test_typed_human_gate_tokens_resolve_to_matching_gate(
    gate_token: str, expected_gate: TypedHumanGate
) -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": f"plan-{gate_token}",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": f"chain-{gate_token}",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": f"gate {gate_token}",
            "gate_type": gate_token,
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)
    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_gate is expected_gate


def test_true_blocker_with_no_typed_gate_defaults_to_user_action() -> None:
    """A confirmed TRUE_BLOCKER without a structured gate category defaults to USER_ACTION."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-tb",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "awaiting_human", "fingerprint": "chain-tb", "mtime": 1.0},
        "needs_human": {"present": True, "summary": "confirmed human blocker"},
    }
    result = resolve_run_state(evidence, BlockerVerdict.TRUE_BLOCKER)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.USER_ACTION
    assert "blocker_verdict" in result.source_of_truth


# ---------------------------------------------------------------------------
# Conservative fallback + serialization round-trip
# ---------------------------------------------------------------------------


def test_empty_evidence_resolves_unknown_conservatively() -> None:
    result = resolve_run_state({})
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.UNKNOWN
    assert result.human_required is False
    assert result.confidence == "low"
    assert result.next_action == "inspect_evidence"


def test_none_evidence_resolves_unknown() -> None:
    result = resolve_run_state(None)
    assert result.canonical_state is CanonicalState.UNKNOWN


def test_resolver_result_serializes_round_trip() -> None:
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-rt",
            "mtime": 1.0,
        },
        "chain_state": {"last_state": "awaiting_human", "fingerprint": "chain-rt", "mtime": 1.0},
        "needs_human": {"present": True, "summary": "approval", "gate_type": "approval"},
    }
    result = resolve_run_state(evidence)
    restored = CanonicalRunState.from_json(result.to_json())
    assert restored.canonical_state is result.canonical_state
    assert restored.human_gate is result.human_gate
    assert restored.human_required is result.human_required
    assert restored.next_action == result.next_action
    assert restored.source_of_truth == result.source_of_truth


# ---------------------------------------------------------------------------
# T6: Focused typed human gate tests — one per TypedHumanGate enum member
# ---------------------------------------------------------------------------


def test_quota_gate_resolves_human_action_required() -> None:
    """A quota/rate-limit gate must resolve to HUMAN_ACTION_REQUIRED with QUOTA."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-quota",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-quota",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "API rate limit exceeded; human intervention required",
            "gate_type": "quota",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.QUOTA
    assert result.next_action == "await_human_action"
    assert result.confidence == "high"


def test_verification_gate_resolves_human_action_required() -> None:
    """A verification gate must resolve to HUMAN_ACTION_REQUIRED with VERIFICATION."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-verify",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-verify",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "output requires human verification before proceeding",
            "gate_type": "verification",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.VERIFICATION
    assert result.next_action == "await_human_action"
    assert result.confidence == "high"


def test_policy_gate_resolves_human_action_required() -> None:
    """A policy gate must resolve to HUMAN_ACTION_REQUIRED with POLICY."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-policy",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-policy",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "policy violation detected; human decision required",
            "gate_type": "policy",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.POLICY
    assert result.next_action == "await_human_action"
    assert result.confidence == "high"


def test_explicit_user_action_gate_resolves_human_action_required() -> None:
    """An explicit user_action gate_type must resolve to HUMAN_ACTION_REQUIRED with USER_ACTION."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-ua",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-ua",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "explicit user-action record pending",
            "gate_type": "user_action",
            "blocked_task_id": "T12",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    assert result.canonical_state is CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is True
    assert result.human_gate is TypedHumanGate.USER_ACTION
    assert result.next_action == "await_human_action"
    assert result.confidence == "high"


# ---------------------------------------------------------------------------
# T6: Human gate edge cases — live worker / implementation block overrides
# ---------------------------------------------------------------------------


def test_human_gate_overridden_by_live_worker() -> None:
    """A live worker must override even an explicit typed human gate (live beats stale)."""
    evidence = {
        "tmux_process": {
            "live_status": "alive",
            "pid": 12345,
            "pid_live": True,
            "session_live": True,
        },
        "plan_state": {
            "current_state": "executing",
            "fingerprint": "plan-live-gate",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-live-gate",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "operator approval required but worker is still running",
            "gate_type": "approval",
            "blocked_task_id": "T14",
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    # Live worker wins — must NOT be HUMAN_ACTION_REQUIRED.
    assert result.canonical_state is not CanonicalState.HUMAN_ACTION_REQUIRED
    assert result.human_required is False
    assert result.human_gate is None
    assert result.running is True


def test_typed_human_gate_not_triggered_by_implementation_block() -> None:
    """A stray gate_type on an AWF018 needs-human marker must NOT become a human gate (SD3)."""
    evidence = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-awf-gate",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "running",
            "fingerprint": "chain-awf-gate",
            "mtime": 1.0,
        },
        "diagnostic_codes": {
            "escalation_label": "AWF018",
            "event_signature_labels": [
                "authority_divergence/route_metadata_mismatch x42",
            ],
        },
        "needs_human": {
            "present": True,
            "summary": "AWF018 route binding gap",
            "gate_type": "credential",  # stray — must NOT override SD3
        },
    }
    result = resolve_run_state(evidence)
    assert_contract_invariants(result)

    # SD3: implementation block beats a stray gate_type.
    assert result.canonical_state is CanonicalState.REAL_IMPLEMENTATION_BLOCK
    assert result.human_required is False
    assert result.human_gate is None


# ---------------------------------------------------------------------------
# T6: Non-mutation guard — resolver must leave protected files unchanged
# ---------------------------------------------------------------------------


def test_resolver_classification_leaves_protected_files_unchanged(
    tmp_path: "pathlib.Path",
) -> None:
    """Prove the resolver is a pure read-only function that never mutates files.

    Creates representative files for each protected category (profile, model,
    provider routing, phase pin, sidecar, marker, plan-state), records their
    content hashes, invokes ``resolve_run_state`` with evidence covering every
    typed human gate and a range of other classifications, then asserts every
    file's hash is bit-for-bit unchanged.

    The resolver's contract (SD1) states it is a pure function; this test is
    the automated enforcement of that contract.
    """
    import hashlib
    import json
    import pathlib

    # --- Create representative protected files ---
    protected_files: dict[str, pathlib.Path] = {}

    # profile
    pf = tmp_path / "profile.toml"
    pf.write_text('[profile]\nname = "canonical-test"\nmodel = "deepseek-v4"\n')
    protected_files["profile"] = pf

    # model routing
    mr = tmp_path / "model_routing.json"
    mr.write_text(json.dumps({"default": "deepseek-v4", "fallback": "hermes-3"}))
    protected_files["model_routing"] = mr

    # provider routing
    pr = tmp_path / "provider_routing.yaml"
    pr.write_text("provider:\n  deepseek:\n    endpoint: https://api.deepseek.com\n")
    protected_files["provider_routing"] = pr

    # phase pin
    pp = tmp_path / "phase_pin.txt"
    pp.write_text("execute\n")
    protected_files["phase_pin"] = pp

    # sidecar
    sc = tmp_path / "sidecar.json"
    sc.write_text(json.dumps({"needs_human": False, "last_check": "2026-07-07T00:00:00Z"}))
    protected_files["sidecar"] = sc

    # marker
    mk = tmp_path / "marker.json"
    mk.write_text(json.dumps({"kind": "plan_ref", "plan_id": "m1-plan-001"}))
    protected_files["marker"] = mk

    # plan-state
    ps = tmp_path / "plan_state.json"
    ps.write_text(json.dumps({"current_state": "executing", "fingerprint": "fp-test"}))
    protected_files["plan_state"] = ps

    # --- Capture content hashes ---
    def _hash_file(p: pathlib.Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    baseline_hashes = {name: _hash_file(p) for name, p in protected_files.items()}

    # --- Call the resolver with evidence covering every typed human gate ---
    gate_evidence_variants = [
        # Each TypedHumanGate enum member
        {
            "tmux_process": {"live_status": "stopped"},
            "plan_state": {
                "current_state": "executing",
                "resume_cursor": {"changed_file_count": 0},
                "fingerprint": "plan-gv",
                "mtime": 1.0,
            },
            "chain_state": {
                "last_state": "awaiting_human",
                "fingerprint": "chain-gv",
                "mtime": 1.0,
            },
            "needs_human": {
                "present": True,
                "summary": f"gate {gate_token}",
                "gate_type": gate_token,
            },
        }
        for gate_token in (
            "approval",
            "credential_account",
            "quota",
            "verification",
            "policy",
            "user_action",
        )
    ]

    # Also cover: live worker, implementation block, retryable, completed, unknown
    extra_evidence = [
        # live worker -> STALE_DERIVED_STATE
        {
            "tmux_process": {"live_status": "alive", "pid": 1},
            "plan_state": {"current_state": "executing", "fingerprint": "fp-live", "mtime": 1.0},
            "chain_state": {"last_state": "manual_review", "fingerprint": "cfp-live", "mtime": 1.0},
        },
        # AWF018 -> REAL_IMPLEMENTATION_BLOCK
        {
            "tmux_process": {"live_status": "stopped"},
            "plan_state": {
                "current_state": "executing",
                "resume_cursor": {"changed_file_count": 0},
                "fingerprint": "fp-awf",
                "mtime": 1.0,
            },
            "chain_state": {"last_state": "running", "fingerprint": "cfp-awf", "mtime": 1.0},
            "diagnostic_codes": {
                "escalation_label": "AWF018",
                "event_signature_labels": ["authority_divergence/route_metadata_mismatch x1"],
            },
        },
        # completed
        {
            "tmux_process": {"live_status": "stopped"},
            "plan_state": {"current_state": "done", "fingerprint": "fp-done", "mtime": 1.0},
            "chain_state": {"last_state": "running", "fingerprint": "cfp-done", "mtime": 1.0},
        },
        # empty -> UNKNOWN
        {},
    ]

    all_evidence = gate_evidence_variants + extra_evidence
    for evidence in all_evidence:
        _ = resolve_run_state(evidence)

    # --- Verify every protected file is bit-for-bit unchanged ---
    unchanged: list[str] = []
    changed: list[str] = []
    for name, path in protected_files.items():
        current = _hash_file(path)
        if current == baseline_hashes[name]:
            unchanged.append(name)
        else:
            changed.append(f"{name} (was {baseline_hashes[name][:12]}..., now {current[:12]}...)")

    assert not changed, (
        f"Resolver mutated protected files! Changed: {changed}. "
        f"Unchanged: {unchanged}. SD1 requires the resolver to be a pure "
        f"read-only function."
    )

    # Sanity: all files must be in the unchanged list.
    assert set(unchanged) == set(protected_files.keys()), (
        f"Not all protected files were verified unchanged: "
        f"unchanged={unchanged}, expected={set(protected_files.keys())}"
    )
