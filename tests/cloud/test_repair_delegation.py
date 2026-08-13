"""Tests for the typed repair-delegation shim (Step 38).

Covers:

* delegation contract requires exact F01 tuple (no label/liveness/WBC
  receipt/rebuildable-projection authority).
* typed outcomes form a closed vocabulary.
* successful delegation to ``simple_fixer`` through the canonical runner.
* zero-authority rejection when the exact F01 tuple cannot be satisfied.
* no-child-agent rejection at the delegation layer.
* invalid-caller rejection for bad caller kind/id.
* delegation failure when the singleton claim is contended.
* the ``emit_zero_authority_rejection`` helper produces typed results
  without any mutation or child spawn.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.simple_fixer import (
    SimpleFixerOccurrence,
    guard_no_child_agent,
)
from arnold_pipelines.megaplan.cloud.wrappers import repair_delegation as rd
from arnold_pipelines.megaplan.custody.contracts import ContractError, CustodyTargetKey

# ── helpers ─────────────────────────────────────────────────────────────────

_DEFAULT_TARGET = {
    "environment": "/workspace/demo",
    "session": "demo",
    "chain": "/workspace/demo/chain.yaml",
    "plan_revision": "sha256:plan-rev-1",
    "phase": "execute",
    "task": "T1",
    "attempt": "1",
    "normalized_failure_kind": "blocked_step",
    "blocker_or_phase_result_hash": "sha256:blocker-1",
    "fence": "fence-1",
}


def _target(**overrides) -> CustodyTargetKey:
    fields = dict(_DEFAULT_TARGET)
    fields.update(overrides)
    return CustodyTargetKey(**fields)


def _delegation(caller_kind="wrapper", caller_id="wrapper-1", **target_overrides):
    target = _target(**target_overrides)
    identity = repair_requests.build_normalized_repair_identity(
        target=target,
        run_id="demo",
        run_revision="sha256:plan-rev-1",
        run_incarnation_id="run-incarnation-1",
        coordinator_attempt_id="coordinator:1",
        fence_token=7,
        wbc_attempt_reference="wbc:1",
        run_authority_grant_id="grant-1",
        lease_id="lease-1",
        custody_epoch=1,
    )
    return rd.RepairDelegation(
        caller_kind=caller_kind,
        caller_id=caller_id,
        target=target,
        repair_identity=identity,
    )


def _queue_dir(tmp_path):
    """A valid central queue root shape."""
    return str(tmp_path / ".megaplan" / "repair-queue")


# ═══════════════════════════════════════════════════════════════════════════
# Delegation contract — exact F01 tuple required
# ═══════════════════════════════════════════════════════════════════════════


def test_delegation_requires_exact_f01_tuple():
    """A delegation MUST carry the exact F01 tuple; partial tuples are rejected."""
    # A complete tuple constructs successfully.
    d = _delegation()
    assert d.caller_kind == "wrapper"
    assert d.caller_id == "wrapper-1"
    assert isinstance(d.target, CustodyTargetKey)
    assert isinstance(d.occurrence, SimpleFixerOccurrence)
    fp = d.occurrence.occurrence_fingerprint
    assert fp.startswith("sha256:")

    # Every F01 field is load-bearing: an empty field is rejected at
    # construction.  Authority cannot derive from a label, liveness
    # signal, WBC receipt, or rebuildable projection.
    for field_name in (
        "environment", "session", "chain", "plan_revision", "phase",
        "task", "attempt", "normalized_failure_kind",
        "blocker_or_phase_result_hash", "fence",
    ):
        with pytest.raises(ContractError):
            _delegation(**{field_name: ""})
        with pytest.raises(ContractError):
            _delegation(**{field_name: "   "})

    # The builder returns None for invalid identity rather than raising.
    assert rd.build_repair_delegation("wrapper", "w1", None) is None
    assert (
        rd.build_repair_delegation("wrapper", "w1", {"environment": "only-a-label"})
        is None
    )
    assert (
        rd.build_repair_delegation(
            "wrapper", "w1", {**_DEFAULT_TARGET, "session": ""}
        )
        is None
    )
    # A mapping with only F01 remains a read-only diagnostic delegation.
    built = rd.build_repair_delegation("wrapper", "w1", _DEFAULT_TARGET)
    assert isinstance(built, rd.RepairDelegation)
    assert built.repair_identity is None
    assert built.occurrence.occurrence_fingerprint != fp


def test_delegation_requires_valid_caller_kind_and_id():
    """Caller kind must be in the closed vocabulary; caller_id must be non-empty."""
    # Unknown caller kind.
    with pytest.raises(ContractError):
        rd.RepairDelegation(
            caller_kind="not-a-real-kind",
            caller_id="x",
            target=_target(),
        )
    # Empty caller kind.
    assert rd.build_repair_delegation("", "x", _DEFAULT_TARGET) is None
    # Empty caller id.
    with pytest.raises(ContractError):
        rd.RepairDelegation(caller_kind="wrapper", caller_id="", target=_target())
    with pytest.raises(ContractError):
        rd.RepairDelegation(caller_kind="wrapper", caller_id="   ", target=_target())
    # Builder returns None for empty caller id.
    assert rd.build_repair_delegation("wrapper", "", _DEFAULT_TARGET) is None
    assert rd.build_repair_delegation("wrapper", "   ", _DEFAULT_TARGET) is None


def test_delegation_rejects_non_custody_target():
    """A non-CustodyTargetKey target is rejected at construction."""
    with pytest.raises(ContractError):
        rd.RepairDelegation(
            caller_kind="wrapper",
            caller_id="w1",
            target="not-a-key",  # type: ignore[arg-type]
        )


# ═══════════════════════════════════════════════════════════════════════════
# Typed outcomes
# ═══════════════════════════════════════════════════════════════════════════


def test_delegation_outcomes_form_closed_vocabulary():
    """Every outcome is within the closed set."""
    expected = {
        "delegated",
        "zero_authority_rejected",
        "no_child_agent_rejected",
        "delegation_failed",
        "invalid_caller",
    }
    assert set(rd.REPAIR_DELEGATION_OUTCOMES) == expected
    # Results validate their outcome against the vocabulary.
    with pytest.raises(ContractError):
        rd.RepairDelegationResult(outcome="not-a-real-outcome")


def test_caller_kinds_form_closed_vocabulary():
    """Every caller kind is within the closed set."""
    expected = {
        "wrapper",
        "controller",
        "terminal_audit",
        "live_watchdog",
        "enqueue_producer",
        "operator_trigger",
        "materializer",
    }
    assert set(rd.CALLER_KINDS) == expected


# ═══════════════════════════════════════════════════════════════════════════
# Zero-authority rejection
# ═══════════════════════════════════════════════════════════════════════════


def test_zero_authority_rejection_is_typed_and_noop():
    """emit_zero_authority_rejection returns a typed result with no side effects."""
    result = rd.emit_zero_authority_rejection(
        "wrapper", "w1", reason="only have a label, not an exact occurrence"
    )
    assert result.outcome == "zero_authority_rejected"
    assert result.delegated is False
    assert result.rejected is True
    assert result.delegation is None
    assert result.occurrence_fingerprint == ""
    assert result.simple_fixer_outcome == ""
    assert result.evidence is not None
    assert result.evidence["reason"] == "only have a label, not an exact occurrence"
    assert result.evidence["caller_kind"] == "wrapper"
    assert result.evidence["caller_id"] == "w1"


def test_zero_authority_rejection_default_reason():
    """When no reason is given a default is supplied."""
    result = rd.emit_zero_authority_rejection("controller", "ctrl-1")
    assert result.outcome == "zero_authority_rejected"
    assert "insufficient authority" in result.evidence["reason"]


def test_delegate_to_simple_fixer_rejects_non_delegation():
    """Passing a non-RepairDelegation returns invalid_caller."""
    result = rd.delegate_to_simple_fixer(
        "not-a-delegation",  # type: ignore[arg-type]
        queue_dir="/tmp/nonexistent",
        mutate=lambda occ: occ.occurrence_fingerprint,
    )
    assert result.outcome == "invalid_caller"
    assert result.delegated is False


# ═══════════════════════════════════════════════════════════════════════════
# No-child-agent rejection
# ═══════════════════════════════════════════════════════════════════════════


def test_delegation_no_child_agent_gate(tmp_path):
    """The delegation shim rejects on behalf of the no-child-agent guard.

    The guard is tested at the delegation layer as a gate that runs
    before any occurrence construction or claim attempt.
    """
    queue_dir = _queue_dir(tmp_path)
    delegation = _delegation()

    # The guard is currently stateless (child_agent_count defaults to 0,
    # requests_child_agent defaults to False), so it passes by default.
    # This test proves the gate is wired and that a successful delegation
    # can proceed. The gate's rejection logic is tested in the
    # simple_fixer tests (test_no_child_agent_gate_rejects_fanout).
    assert guard_no_child_agent() is None

    result = rd.delegate_to_simple_fixer(
        delegation,
        queue_dir=queue_dir,
        mutate=lambda occ: occ.occurrence_fingerprint,
    )
    # With a fresh queue, claim succeeds and delegation proceeds.
    assert result.outcome in ("delegated", "delegation_failed")
    # A no-op is not an authorization and must not become delegated.
    assert result.outcome == "delegation_failed"
    assert result.delegated is False
    assert result.simple_fixer_outcome == "unchanged"


# ═══════════════════════════════════════════════════════════════════════════
# Successful delegation to simple_fixer
# ═══════════════════════════════════════════════════════════════════════════


def test_successful_delegation_through_canonical_runner(tmp_path):
    """A valid delegation flows through claim → run → release → typed result."""
    queue_dir = _queue_dir(tmp_path)
    delegation = _delegation()
    fp = delegation.occurrence.occurrence_fingerprint

    # A mutation that changes the fingerprint.
    call_count = [0]

    def productive_mutate(occ):
        call_count[0] += 1
        return "sha256:mutated-fingerprint"

    result = rd.delegate_to_simple_fixer(
        delegation,
        queue_dir=queue_dir,
        mutate=productive_mutate,
        actor="test-actor",
        request_id="req-test-1",
        session_id="sess-test-1",
        kind="immediate_trigger",
        verifier_slot="five_minute",
    )

    assert result.outcome == "delegated"
    assert result.delegated is True
    assert result.rejected is False
    assert result.occurrence_fingerprint == fp
    assert result.simple_fixer_outcome == "attempted"
    assert result.evidence is not None
    assert result.evidence["simple_fixer_outcome"] == "attempted"
    assert result.evidence["receipt"] is not None
    assert call_count[0] == 1

    # The occurrence was released after the run (best-effort).
    # A fresh claim can now succeed.
    claim2 = __import__(
        "arnold_pipelines.megaplan.cloud.simple_fixer", fromlist=["claim_singleton_occurrence"]
    ).claim_singleton_occurrence(
        queue_dir,
        delegation.occurrence,
        actor="test-actor-2",
        request_id="req-test-2",
        session="sess-test-2",
    )
    assert claim2.outcome == "claimed"


def test_delegation_with_explicit_runner_and_kind(tmp_path):
    """Delegation accepts explicit kind and verifier_slot parameters."""
    queue_dir = _queue_dir(tmp_path)
    delegation = _delegation()

    result = rd.delegate_to_simple_fixer(
        delegation,
        queue_dir=queue_dir,
        mutate=lambda occ: "sha256:reconciled",
        kind="reconciliation",
        verifier_slot="next_three_hour",
    )
    assert result.outcome == "delegated"
    assert result.simple_fixer_outcome == "attempted"
    assert result.evidence["receipt"]["kind"] == "reconciliation"
    assert result.evidence["receipt"]["verifier_slot"] == "next_three_hour"


# ═══════════════════════════════════════════════════════════════════════════
# Claim contention → delegation_failed
# ═══════════════════════════════════════════════════════════════════════════


def test_delegation_fails_when_claim_contended(tmp_path):
    """When another owner holds the singleton claim, delegation fails cleanly."""
    queue_dir = _queue_dir(tmp_path)
    delegation = _delegation()

    # Pre-claim the occurrence from a different actor.
    from arnold_pipelines.megaplan.cloud.simple_fixer import (
        claim_singleton_occurrence,
        release_singleton_occurrence_claim,
    )

    pre_claim = claim_singleton_occurrence(
        queue_dir,
        delegation.occurrence,
        actor="other-actor",
        request_id="req-other",
        session="sess-other",
    )
    assert pre_claim.outcome == "claimed"

    # Now delegate — it should fail because the claim is busy.
    result = rd.delegate_to_simple_fixer(
        delegation,
        queue_dir=queue_dir,
        mutate=lambda occ: occ.occurrence_fingerprint,
    )
    assert result.outcome == "delegation_failed"
    assert result.delegated is False
    assert result.simple_fixer_outcome == "busy"
    assert result.evidence["reason"] == "claim outcome: busy"

    # Clean up so the test dir can be removed.
    release_singleton_occurrence_claim(queue_dir, delegation.occurrence)


# ═══════════════════════════════════════════════════════════════════════════
# All caller kinds are accepted
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("caller_kind", [
    "wrapper",
    "controller",
    "terminal_audit",
    "live_watchdog",
    "enqueue_producer",
    "operator_trigger",
    "materializer",
])
def test_all_caller_kinds_accepted(caller_kind):
    """Every caller kind in the closed vocabulary constructs a valid delegation."""
    d = rd.RepairDelegation(
        caller_kind=caller_kind,
        caller_id=f"{caller_kind}-1",
        target=_target(),
    )
    assert d.caller_kind == caller_kind
    assert isinstance(d.occurrence, SimpleFixerOccurrence)


# ═══════════════════════════════════════════════════════════════════════════
# Delegation serialization
# ═══════════════════════════════════════════════════════════════════════════


def test_delegation_to_dict_includes_all_fields():
    """Serialization round-trips the key fields."""
    d = _delegation(caller_kind="controller", caller_id="ctrl-99")
    payload = d.to_dict()
    assert payload["contract_type"] == "repair_delegation"
    assert payload["schema_version"] == 1
    assert payload["caller_kind"] == "controller"
    assert payload["caller_id"] == "ctrl-99"
    assert isinstance(payload["target"], dict)
    assert payload["target"]["environment"] == _DEFAULT_TARGET["environment"]


def test_delegation_result_to_dict():
    """Result serialization includes all typed fields."""
    result = rd.emit_zero_authority_rejection("live_watchdog", "wd-1", reason="test")
    payload = result.to_dict()
    assert payload["outcome"] == "zero_authority_rejected"
    assert payload["delegated"] is False
    assert payload["occurrence_fingerprint"] == ""
    assert payload["simple_fixer_outcome"] == ""
    assert isinstance(payload["evidence"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# DelegationResult.delegated / .rejected convenience properties
# ═══════════════════════════════════════════════════════════════════════════


def test_delegation_result_properties():
    """delegated and rejected are complementary."""
    d = _delegation()
    ok = rd.RepairDelegationResult(
        outcome="delegated",
        delegation=d,
        occurrence_fingerprint="sha256:abc",
        simple_fixer_outcome="attempted",
    )
    assert ok.delegated is True
    assert ok.rejected is False

    fail = rd.RepairDelegationResult(
        outcome="delegation_failed",
        delegation=d,
        occurrence_fingerprint="sha256:abc",
        simple_fixer_outcome="busy",
    )
    assert fail.delegated is False
    assert fail.rejected is True


# ═══════════════════════════════════════════════════════════════════════════
# Owner-adoption exact-occurrence consumer (T-0640 D2 / G14 round 3)
# ═══════════════════════════════════════════════════════════════════════════
#
# The owner-boundary-adoption identity carries NO F01 tuple: its authority is
# the operator's LIVE occurrence-join claim.  The consumer re-verifies the
# claim read-only (fail closed), claims through the SAME queue-root mkdir
# primitive keyed by the JOIN claim id (never the F01 singleton key), and
# runs the mutation through the SAME canonical runner.  Every negative must
# fail closed with zero_authority_rejected and MUST NOT enter the mutation.


def _owner_adoption_envelope(
    tmp_path: Path, *, session: str, plan_name: str = "adopt-plan"
) -> dict[str, object]:
    """Enqueue ONE owner-adoption request with an accepted decision."""
    from arnold_pipelines.megaplan.chain.occurrence_adopt import (
        build_adoption_identity,
    )

    built = build_adoption_identity(
        session=session,
        plan_name=plan_name,
        phase="gate",
        failure_kind="deterministic_phase_failure",
        failure_code="blocked_no_lease",
        failure_recorded_at="2026-08-11T07:35:34Z",
        resume_phase="gate",
        retry_strategy="repair_phase_contract",
        cas={
            field: "sha256:" + "a" * 64
            for field in repair_requests.OWNER_ADOPTION_CAS_FIELDS
        },
        runtime_roots={
            field: "/workspace/runtime-candidates/arnold-test"
            for field in repair_requests.OWNER_ADOPTION_ROOT_FIELDS
        },
    )
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    enqueued = repair_requests.enqueue_owner_adopted_repair_request(
        queue_root=queue_root,
        session=session,
        source="owner_boundary_occurrence_adoption",
        marker_dir=tmp_path,
        target={
            "plan_dir": str(tmp_path),
            "plan_name": plan_name,
            "retry_strategy": "repair_phase_contract",
            "adoption_record_id": built["adoption_record_id"],
        },
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "gate",
            "milestone_or_plan": plan_name,
            "gate_recommendation": "repair gate contract",
            "blocked_task_id": "phase:gate",
        },
        root_cause_hint="owner adoption of identity-less blocked occurrence",
        repair_identity=built["identity"],
        workspace=str(tmp_path),
        run_kind="chain",
    )
    assert enqueued["status"] == "queued", enqueued
    return {
        "built": built,
        "request": enqueued["request"],
        "decision": enqueued["decision"],
        "queue_root": queue_root,
        "identity": built["identity"],
        "repair_identity_key": built["repair_identity_key"],
        "request_id": str(enqueued["request"]["request_id"]),
        "decision_id": str(enqueued["decision"]["decision_id"]),
    }


def _write_join_claim(
    plan_dir: Path,
    *,
    occurrence_id: str,
    request_id: str,
    decision_id: str,
    expires_in_seconds: int = 3600,
    kind: str = "occurrence_join",
    write_wbc: bool = True,
    write_lease: bool = True,
    wbc_occurrence_id: str | None = None,
    lease_occurrence_id: str | None = None,
) -> tuple[str, str]:
    """Write a REAL live occurrence-join claim (WBC STARTED + custody lease).

    Mirrors the durable claim occurrence_join writes.  Returns
    ``(claim_id, lease_id)``.  The optional ``*_occurrence_id`` overrides
    let negatives write a claim that does NOT cover the target occurrence.
    """
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.execution_attempt_ledger import (
        AdapterKind,
        AttemptEventType,
        AttemptIdentity,
        AttemptProvenance,
        GrantRef,
        LedgerEvent,
        RuntimeAdapter,
        VersionSet,
    )
    from arnold_pipelines.megaplan.custody.lease_store import open_lease_store

    plan_dir.mkdir(parents=True, exist_ok=True)
    attempt_id = str(uuid4())
    claim_id = "t0101-owner-adoption:delegation-test"
    lease_id = (
        "occurrence-join-" + hashlib.sha256(claim_id.encode("utf-8")).hexdigest()[:16]
    )
    occurred_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = LedgerEvent(
        idempotency_key=f"{attempt_id}:started",
        event_type=AttemptEventType.STARTED,
        identity=AttemptIdentity(
            workflow_id="megaplan-occurrence-join",
            run_id="watchdog-delegation-test",
            graph_revision=(occurrence_id or "0")[:32] or "0",
            step_id="occurrence-join",
            invocation_id=claim_id,
            attempt_ordinal=1,
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(
            actor_id="operator", tool_id="megaplan.occurrence_join"
        ),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="1"
        ),
        versions=VersionSet(code_version="occurrence-join.v1"),
        grant_ref=GrantRef(grant_id=request_id, decision_id=decision_id),
        sequence=1,
        causal_predecessor_sequence=0,
        append_position=1,
        occurred_at=occurred_at,
        observed_at=occurred_at,
        payload={
            "kind": kind,
            "occurrence_id": occurrence_id if wbc_occurrence_id is None else wbc_occurrence_id,
            "occurrence_digest": "sha256:" + "b" * 64,
            "claim_id": claim_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "lease_id": lease_id,
            "session": "watchdog-delegation-test",
            "actor": "operator",
            "reason": "T-0640 D2 consumer test",
        },
    )
    if write_wbc:
        wbc_path = plan_dir / ".phase_wbc_attempts.sqlite3"
        store = SqliteAttemptLedgerStore(wbc_path)
        store.append_started(attempt_id, started)

    if write_lease:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        lease_store = open_lease_store(plan_dir / "custody" / "leases")
        lease_store.acquire(
            lease_id=lease_id,
            owner_host="test-host",
            owner_pid="1234",
            owner_boot_id="test-boot",
            run_authority_grant_id=request_id,
            coordinator_fence_token=1,
            wbc_attempt_reference=attempt_id,
            occurrence_digest="sha256:" + "b" * 64,
            custody_epoch=1,
            expires_at=expires_at,
            payload={
                "kind": kind,
                "occurrence_id": (
                    occurrence_id if lease_occurrence_id is None else lease_occurrence_id
                ),
                "claim_id": claim_id,
                "request_id": request_id,
                "decision_id": decision_id,
                "session": "watchdog-delegation-test",
                "actor": "operator",
                "reason": "T-0640 D2 consumer test",
            },
        )
    return claim_id, lease_id


def _delegate_owner_adopted(
    tmp_path: Path,
    envelope: dict[str, object],
    *,
    identity: dict | None = None,
    mutate=None,
    plan_name: str = "adopt-plan",
    **kwargs,
) -> tuple[rd.RepairDelegationResult, Path]:
    """Call the owner-adoption consumer with a marker-writing mutate."""
    marker = tmp_path / "mutate-ran.marker"

    def default_mutate(occ):
        marker.write_text(
            json.dumps({"fingerprint": occ.occurrence_fingerprint}), encoding="utf-8"
        )
        return occ.occurrence_fingerprint + ":ran"

    result = rd.delegate_owner_adopted_occurrence(
        envelope["identity"] if identity is None else identity,
        queue_dir=envelope["queue_root"],
        workspace=tmp_path,
        plan_name=plan_name,
        mutate=default_mutate if mutate is None else mutate,
        actor="arnold-watchdog",
        request_id=envelope["request_id"],
        session_id="sess-owner-adoption",
        decision_id=envelope["decision_id"],
        blocker_id="phase:gate",
        kind="owner_adoption_dispatch",
        **kwargs,
    )
    return result, marker


def test_owner_adopted_occurrence_delegation_runs_under_live_join_claim(
    tmp_path: Path,
) -> None:
    """A live join claim + accepted owner-adoption request + matching key is
    ALREADY-AUTHORIZED custody: the consumer ACTUALLY enters the canonical
    runner, runs the mutation, and reports delegated.  This is the real-bind
    test: if the path were rewired to the generic F01 delegate (which must
    keep rejecting the adoption envelope) or to a typed reroute, this FAILS
    because the outcome would not be delegated and the mutation marker would
    not exist."""
    session = "consumer-positive"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, _lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
    )

    result, marker = _delegate_owner_adopted(tmp_path, envelope)

    assert result.outcome == "delegated", result.to_dict()
    assert result.delegated is True
    assert result.occurrence_fingerprint == envelope["repair_identity_key"]
    assert result.simple_fixer_outcome == "attempted"
    assert result.evidence is not None
    assert result.evidence["consumer_entered"] is True
    assert result.evidence["claim_id"] == _claim_id
    assert result.evidence["lease_id"] == _lease_id
    assert str(result.evidence["post_mutation_fingerprint"]).endswith(":ran")
    # The mutation ran (the repair action was invoked).
    assert marker.exists(), "mutation was not entered"

    # The lease-derived claim was released: a fresh claim on the same key
    # (the JOIN claim key, never the F01 fingerprint key) succeeds.
    from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        singleton_occurrence_claim_lock_dir,
    )

    claim_key = f"owner-adoption:{_lease_id}"
    lock_dir = singleton_occurrence_claim_lock_dir(envelope["queue_root"], claim_key)
    recheck = acquire_repair_lock(lock_dir, session="recheck-owner")
    assert recheck.acquired, recheck.status
    from arnold_pipelines.megaplan.cloud.repair_lock import release_repair_lock

    release_repair_lock(lock_dir, owner=recheck.owner)


def test_owner_adoption_identity_cannot_run_through_generic_f01_path(
    tmp_path: Path,
) -> None:
    """The generic F01 delegation path keeps rejecting the adoption envelope:
    build_repair_delegation returns None and delegate_to_simple_fixer never
    fabricates an F01 tuple for it (the deliberate boundary stays intact)."""
    session = "generic-reject"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    assert (
        rd.build_repair_delegation(
            "operator_trigger", "request-x", envelope["identity"]
        )
        is None
    )
    result = rd.delegate_to_simple_fixer(  # type: ignore[arg-type]
        envelope["identity"],
        queue_dir=envelope["queue_root"],
        mutate=lambda occ: occ.occurrence_fingerprint,
    )
    assert result.outcome == "invalid_caller"


def test_owner_adopted_delegation_fails_closed_without_lease(tmp_path: Path) -> None:
    """No lease in the plan-scoped lease store: fail closed, no mutation."""
    session = "neg-no-lease"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, _lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
        write_lease=False,
    )
    result, marker = _delegate_owner_adopted(tmp_path, envelope)
    assert result.outcome == "zero_authority_rejected", result.to_dict()
    assert "custody lease" in str(result.evidence["reason"])
    assert not marker.exists()


def test_owner_adopted_delegation_fails_closed_on_expired_lease(tmp_path: Path) -> None:
    """An EXPIRED lease is not live custody: fail closed, no mutation."""
    import time

    session = "neg-expired-lease"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, _lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
        expires_in_seconds=1,
    )
    # Let the TTL lapse: the lease must be expired by consumer time (no
    # repair under an expired claim).
    time.sleep(2)
    result, marker = _delegate_owner_adopted(tmp_path, envelope)
    assert result.outcome == "zero_authority_rejected", result.to_dict()
    assert "custody lease" in str(result.evidence["reason"])
    assert not marker.exists()


def test_owner_adopted_delegation_fails_closed_on_non_join_wbc_kind(
    tmp_path: Path,
) -> None:
    """A WBC STARTED whose kind is NOT occurrence_join is not the join claim:
    fail closed, no mutation."""
    session = "neg-wbc-kind"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, _lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
        kind="phase_rerun",
    )
    result, marker = _delegate_owner_adopted(tmp_path, envelope)
    assert result.outcome == "zero_authority_rejected", result.to_dict()
    assert "occurrence_join" in str(result.evidence["reason"])
    assert not marker.exists()


def test_owner_adopted_delegation_fails_closed_when_decision_not_latest_accepted(
    tmp_path: Path,
) -> None:
    """A later non-accepted decision supersedes the acceptance: the latest
    decision must be accepted, otherwise fail closed with no mutation."""
    session = "neg-decision"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, _lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
    )
    # A later (strictly newer) decision overrides the acceptance.
    repair_requests.write_decision(
        envelope["queue_root"],
        request_id=str(envelope["request_id"]),
        decision="rejected",
        reason="later override",
        created_at="2099-01-01T00:00:00Z",
    )
    result, marker = _delegate_owner_adopted(tmp_path, envelope)
    assert result.outcome == "zero_authority_rejected", result.to_dict()
    assert "latest owner-adoption decision is not accepted" in str(
        result.evidence["reason"]
    )
    assert not marker.exists()


def test_owner_adopted_delegation_fails_closed_on_identity_key_mismatch(
    tmp_path: Path,
) -> None:
    """A passed identity whose digest key does not match the recorded request
    key is not the accepted occurrence: fail closed, no mutation."""
    session = "neg-key-mismatch"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, _lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
    )
    # Build a DIFFERENT adoption identity (different failure_code ⇒ key).
    from arnold_pipelines.megaplan.chain.occurrence_adopt import (
        build_adoption_identity,
    )

    other = build_adoption_identity(
        session=session,
        plan_name="adopt-plan",
        phase="gate",
        failure_kind="deterministic_phase_failure",
        failure_code="other_code",
        failure_recorded_at="2026-08-11T07:35:34Z",
        resume_phase="gate",
        retry_strategy="repair_phase_contract",
        cas={
            field: "sha256:" + "a" * 64
            for field in repair_requests.OWNER_ADOPTION_CAS_FIELDS
        },
        runtime_roots={
            field: "/workspace/runtime-candidates/arnold-test"
            for field in repair_requests.OWNER_ADOPTION_ROOT_FIELDS
        },
    )
    result, marker = _delegate_owner_adopted(
        tmp_path, envelope, identity=other["identity"]
    )
    assert result.outcome == "zero_authority_rejected", result.to_dict()
    assert "identity key mismatch" in str(result.evidence["reason"])
    assert not marker.exists()


def test_owner_adopted_delegation_fails_closed_when_claim_contended(
    tmp_path: Path,
) -> None:
    """A concurrent owner on the lease-derived claim key refuses the
    delegation (fail closed, no mutation; no auto-seize)."""
    session = "neg-contended"
    envelope = _owner_adoption_envelope(tmp_path, session=session)
    plan_dir = tmp_path / ".megaplan" / "plans" / "adopt-plan"
    _claim_id, lease_id = _write_join_claim(
        plan_dir,
        occurrence_id=str(envelope["repair_identity_key"]),
        request_id=str(envelope["request_id"]),
        decision_id=str(envelope["decision_id"]),
    )
    from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        singleton_occurrence_claim_lock_dir,
    )

    claim_key = f"owner-adoption:{lease_id}"
    lock_dir = singleton_occurrence_claim_lock_dir(envelope["queue_root"], claim_key)
    pre = acquire_repair_lock(lock_dir, session="other-owner")
    assert pre.acquired, pre.status
    try:
        result, marker = _delegate_owner_adopted(tmp_path, envelope)
        assert result.outcome == "delegation_failed", result.to_dict()
        assert "claim outcome" in str(result.evidence["reason"])
        assert not marker.exists()
    finally:
        from arnold_pipelines.megaplan.cloud.repair_lock import release_repair_lock

        release_repair_lock(lock_dir, owner=pre.owner)


def test_owner_adopted_delegation_rejects_non_adoption_identity(
    tmp_path: Path,
) -> None:
    """A non-owner-adoption identity (e.g. an F01 repair identity) can never
    run through the owner-adoption consumer: fail closed."""
    result = rd.delegate_owner_adopted_occurrence(
        {"identity_kind": "run_custody", "schema_version": "megaplan-repair-identity-v1"},
        queue_dir=tmp_path / ".megaplan" / "repair-queue",
        workspace=tmp_path,
        plan_name="adopt-plan",
        mutate=lambda occ: "sha256:x",
    )
    assert result.outcome == "zero_authority_rejected", result.to_dict()
    assert "owner_boundary_adoption" in str(result.evidence["reason"])
