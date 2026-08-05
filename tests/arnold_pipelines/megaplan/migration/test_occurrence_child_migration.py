"""Contract tests for the C116 occurrence-child migration coordinator."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from arnold.workflow.attempt_ledger_store import GlobalEffectReservation
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyTargetKey,
    RepairOccurrenceKey,
)
from arnold_pipelines.megaplan.migration.occurrence_child_migration import (
    ChildAuthority,
    ChildSelector,
    MigrationConflict,
    MigrationCoordinator,
    MigrationError,
    MigrationIndeterminate,
    MigrationStatus,
    ParentAuthoritySnapshot,
    ParentCommitReceipt,
    ParentEvidence,
    SelectorDrift,
    WbcReservation,
)
from arnold_pipelines.run_authority.contracts import (
    CapabilityGrant,
    Claim,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    QuarantineRecord,
    SubjectAttempt,
)
from arnold_pipelines.run_authority.current_source import CurrentSourceRequest
from arnold_pipelines.run_authority.current_source import evaluate_current_source
from arnold_pipelines.run_authority.reducer import RunAuthorityView


def _effect(identity: str) -> GlobalEffectIdentity:
    return GlobalEffectIdentity(
        environment_id="env",
        action_target=f"target:{identity}",
        action_version="v1",
        effect_family="test.effect",
        provider_target=identity,
        canonical_request_identity=f"request:{identity}",
        boundary_schema_hash="schema-hash",
    )


def _lease(
    *,
    lease_id: str,
    occurrence: RepairOccurrenceKey,
    grant_id: str,
    fence_token: int,
    wbc_attempt: str,
) -> CustodyLease:
    return CustodyLease(
        lease_id=lease_id,
        occurrence_key=occurrence,
        owner_host="test-host",
        owner_pid="1",
        owner_boot_id="boot",
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        wbc_attempt_reference=wbc_attempt,
        custody_epoch=1,
        acquired_at="2026-08-05T00:00:00Z",
        expires_at="2026-08-05T01:00:00Z",
        idempotency_key=f"lease:{lease_id}",
    )


class FakeOwners:
    """Tiny owner adapters: no synthetic record is created by the coordinator."""

    def __init__(self, parent: ParentEvidence) -> None:
        self.parent = parent
        self.parent_commits: dict[str, ParentCommitReceipt] = {}
        self.children: dict[str, ChildAuthority] = {}
        self.wbc: dict[tuple[str, str], WbcReservation] = {}
        self.wbc[(parent.wbc.attempt_id, parent.wbc.glek)] = parent.wbc
        self.leases: dict[str, CustodyLease] = {"parent-lease": parent.custody_lease}
        self.calls: dict[str, int] = {"parent": 0, "child": 0, "wbc": 0, "custody": 0}
        self.provider_calls = 0

    def read_parent(self, run_id: str, run_revision: str) -> ParentAuthoritySnapshot:
        return self.parent.authority

    def read_parent_commit(self, key: str) -> ParentCommitReceipt | None:
        return self.parent_commits.get(key)

    def commit_parent(self, *, expected: Any, migration_idempotency_key: str, quarantine: QuarantineRecord) -> ParentCommitReceipt:
        self.calls["parent"] += 1
        if expected.expected_cursor != self.parent.authority.journal_cursor:
            raise MigrationIndeterminate("stale fake parent")
        receipt = ParentCommitReceipt(
            migration_idempotency_key=migration_idempotency_key,
            parent_cursor=self.parent.authority.journal_cursor + 1,
            quarantine=quarantine,
        )
        self.parent_commits[migration_idempotency_key] = receipt
        view = replace(
            self.parent.authority.view,
            journal_cursor=receipt.parent_cursor,
            quarantines=self.parent.authority.view.quarantines + (quarantine,),
        )
        self.parent = replace(
            self.parent,
            authority=ParentAuthoritySnapshot(view=view),
        )
        return receipt

    def read_child(self, key: str) -> ChildAuthority | None:
        return self.children.get(key)

    def allocate_child(self, *, identity: Any, parent: ParentEvidence, migration_idempotency_key: str) -> ChildAuthority:
        self.calls["child"] += 1
        fence = CoordinatorFence(
            run_id=identity.child_run_id,
            run_revision=identity.child_revision,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            token=99,
        )
        evidence = EvidenceEnvelope(
            evidence_id="child-evidence",
            run_id=identity.child_run_id,
            run_revision=identity.child_revision,
            evidence_type="child",
            source="test",
            payload={"migration": migration_idempotency_key},
        )
        grant = CapabilityGrant(
            grant_id="child-grant",
            run_id=identity.child_run_id,
            run_revision=identity.child_revision,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            fence_token=99,
            subject_ids=("child-subject",),
            capabilities=("execute",),
            evidence_ids=(evidence.evidence_id,),
        )
        attempt = SubjectAttempt(
            attempt_id=identity.subject_attempt_id,
            run_id=identity.child_run_id,
            run_revision=identity.child_revision,
            subject_id="child-subject",
            grant_id=grant.grant_id,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            fence_token=99,
            ordinal=1,
        )
        claim = Claim(
            claim_id="child-claim",
            run_id=identity.child_run_id,
            run_revision=identity.child_revision,
            subject_id="child-subject",
            attempt_id=attempt.attempt_id,
            grant_id=grant.grant_id,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            fence_token=99,
            claim_type="child",
            evidence_ids=(evidence.evidence_id,),
            idempotency_key=migration_idempotency_key,
            payload={"child": identity.child_run_id},
        )
        decision = Decision(
            decision_id="child-decision",
            run_id=identity.child_run_id,
            run_revision=identity.child_revision,
            subject_id="child-subject",
            attempt_id=attempt.attempt_id,
            grant_id=grant.grant_id,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            fence_token=99,
            claim_id=claim.claim_id,
            outcome="accepted",
            evidence_ids=(evidence.evidence_id,),
            idempotency_key=f"decision:{migration_idempotency_key}",
            payload={"child": identity.child_run_id},
        )
        authority = ChildAuthority(fence, grant, attempt, claim, (evidence,), decision)
        self.children[migration_idempotency_key] = authority
        return authority

    def read_reservation(self, attempt_id: str, glek: str) -> WbcReservation | None:
        return self.wbc.get((attempt_id, glek))

    def reserve_child(self, *, attempt_id: str, effect_identity: GlobalEffectIdentity, migration_idempotency_key: str) -> WbcReservation:
        self.calls["wbc"] += 1
        reservation = GlobalEffectReservation(
            attempt_id=attempt_id,
            effect_identity=effect_identity,
            global_logical_effect_key=effect_identity.global_logical_effect_key,
            first_reserved_ns=1,
            reservation_count=1,
            is_new=True,
        )
        result = WbcReservation(attempt_id, reservation)
        self.wbc[(attempt_id, result.glek)] = result
        return result

    def read_lease(self, lease_id: str) -> CustodyLease | None:
        return self.leases.get(lease_id)

    def acquire_child(self, *, lease_id: str, occurrence: RepairOccurrenceKey, authority: ChildAuthority, wbc: WbcReservation, idempotency_key: str) -> CustodyLease:
        self.calls["custody"] += 1
        result = _lease(
            lease_id=lease_id,
            occurrence=occurrence,
            grant_id=authority.grant.grant_id,
            fence_token=authority.fence.token,
            wbc_attempt=wbc.attempt_id,
        )
        self.leases[lease_id] = result
        return result


def _parent_evidence() -> ParentEvidence:
    fence = CoordinatorFence("run-parent", "rev-parent", "coordinator-parent", 7)
    evidence = EvidenceEnvelope("parent-evidence", "run-parent", "rev-parent", "parent", "test", {"ok": True})
    grant = CapabilityGrant("parent-grant", "run-parent", "rev-parent", "coordinator-parent", 7, ("subject-parent",), ("execute",), (evidence.evidence_id,))
    attempt = SubjectAttempt("attempt-parent", "run-parent", "rev-parent", "subject-parent", "parent-grant", "coordinator-parent", 7, 1)
    claim = Claim("claim-parent", "run-parent", "rev-parent", "subject-parent", "attempt-parent", "parent-grant", "coordinator-parent", 7, "repair", (evidence.evidence_id,), "parent-claim", {"ok": True})
    decision = Decision("decision-parent", "run-parent", "rev-parent", "subject-parent", "attempt-parent", "parent-grant", "coordinator-parent", 7, "claim-parent", "accepted", (evidence.evidence_id,), "parent-decision", {"ok": True})
    view = RunAuthorityView(
        schema_version=1,
        run_id="run-parent",
        run_revision="rev-parent",
        journal_cursor=10,
        evidence_set_digest="evidence-set",
        evidence=(evidence,),
        observations=(),
        fences=(fence,),
        grants=(grant,),
        attempts=(attempt,),
        claims=(claim,),
        decisions=(decision,),
        quarantines=(),
        diagnostics=(),
        view_hash="view-parent",
    )
    target = CustodyTargetKey(
        environment="env", session="session", chain="chain", plan_revision="rev-parent",
        phase="execute", task="task", attempt="1", normalized_failure_kind="stalled",
        blocker_or_phase_result_hash="blocker", fence="7", chain_identity="chain",
    )
    occurrence = RepairOccurrenceKey(
        target=target,
        run_id="run-parent",
        run_revision="rev-parent",
        coordinator_attempt_id="coordinator-parent",
        fence_token=7,
        wbc_attempt_reference="attempt-parent",
    )
    parent_effect = _effect("parent")
    reservation = GlobalEffectReservation(
        attempt_id="attempt-parent",
        effect_identity=parent_effect,
        global_logical_effect_key=parent_effect.global_logical_effect_key,
        first_reserved_ns=1,
        reservation_count=1,
        is_new=False,
    )
    custody = _lease(
        lease_id="parent-lease",
        occurrence=occurrence,
        grant_id="parent-grant",
        fence_token=7,
        wbc_attempt="attempt-parent",
    )
    return ParentEvidence(
        occurrence=occurrence,
        authority=ParentAuthoritySnapshot(view),
        source_request=CurrentSourceRequest(
            run_id="run-parent", run_revision="rev-parent", coordinator_attempt_id="coordinator-parent",
            grant_id="parent-grant", fence_token=7, subject_attempt_id="attempt-parent", decision_id="decision-parent",
        ),
        custody_lease=custody,
        wbc=WbcReservation("attempt-parent", reservation),
    )


def test_prepare_is_provider_free_and_deterministic() -> None:
    parent = _parent_evidence()
    owners = FakeOwners(parent)
    coordinator = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners)
    selector = ChildSelector("rev-child", {"task": "repair", "models": ["glm"]})
    prepared = coordinator.prepare(parent, selector)
    repeated = coordinator.prepare(parent, selector)
    assert prepared.child == repeated.child
    assert prepared.child.glek.startswith("glek:")
    assert not prepared.child.glek.startswith("wbc-ref-")
    assert owners.calls == {"parent": 0, "child": 0, "wbc": 0, "custody": 0}
    assert owners.provider_calls == 0


def test_commit_replay_is_idempotent_and_has_one_child() -> None:
    parent = _parent_evidence()
    owners = FakeOwners(parent)
    coordinator = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners)
    prepared = coordinator.prepare(parent, ChildSelector("rev-child", {"task": "repair"}))
    first = coordinator.commit(prepared)
    second = coordinator.commit(prepared)
    assert first.status is MigrationStatus.COMMITTED
    assert second.child == first.child
    assert owners.calls == {"parent": 1, "child": 1, "wbc": 1, "custody": 1}
    assert len(owners.parent_commits) == 1
    assert len(owners.children) == 1
    assert len(owners.wbc) == 2  # parent evidence + exactly one child reservation
    assert sum(1 for attempt_id, _ in owners.wbc if attempt_id != "attempt-parent") == 1
    assert len(owners.leases) == 2
    assert first.parent_commit.quarantine.reason == "occurrence_migrated_to_child"
    denied = evaluate_current_source(
        owners.parent.authority.view,
        parent.source_request,
    )
    assert not denied.status.is_satisfied


def test_tampered_prepared_selector_is_rejected() -> None:
    parent = _parent_evidence()
    owners = FakeOwners(parent)
    coordinator = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners)
    prepared = coordinator.prepare(parent, ChildSelector("rev-child", {"task": "repair"}))
    tampered = replace(prepared, selector=ChildSelector("rev-child", {"task": "different"}))
    with pytest.raises(SelectorDrift):
        coordinator.commit(tampered)
    assert owners.calls == {"parent": 0, "child": 0, "wbc": 0, "custody": 0}


def test_existing_child_with_divergent_owner_identity_is_conflict() -> None:
    parent = _parent_evidence()
    owners = FakeOwners(parent)
    coordinator = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners)
    prepared = coordinator.prepare(parent, ChildSelector("rev-child", {"task": "repair"}))
    coordinator.commit(prepared)
    existing = owners.children[prepared.migration_idempotency_key]
    owners.children[prepared.migration_idempotency_key] = replace(
        existing,
        fence=replace(existing.fence, run_id="different-child"),
    )
    with pytest.raises(MigrationConflict, match="divergent run"):
        coordinator.commit(prepared)
    assert owners.calls == {"parent": 1, "child": 1, "wbc": 1, "custody": 1}


def test_crash_after_parent_and_child_steps_recovers_without_provider() -> None:
    parent = _parent_evidence()
    owners = FakeOwners(parent)
    crashed = {"done": False}

    def crash_once(step: str) -> None:
        if step == "child_authority_allocated" and not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("simulated process crash")

    coordinator = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners, after_step=crash_once)
    prepared = coordinator.prepare(parent, ChildSelector("rev-child", {"task": "repair"}))
    with pytest.raises(RuntimeError):
        coordinator.commit(prepared)
    recovered = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners).recover(prepared)
    assert recovered.status is MigrationStatus.COMMITTED
    assert owners.calls == {"parent": 1, "child": 1, "wbc": 1, "custody": 1}
    assert owners.provider_calls == 0


def test_stale_owner_cursor_fails_closed_before_parent_mutation() -> None:
    parent = _parent_evidence()
    owners = FakeOwners(parent)
    coordinator = MigrationCoordinator(run_authority=owners, wbc=owners, custody=owners)
    prepared = coordinator.prepare(parent, ChildSelector("rev-child", {"task": "repair"}))
    owners.parent = replace(owners.parent, authority=ParentAuthoritySnapshot(replace(parent.authority.view, journal_cursor=11)))
    with pytest.raises(MigrationError):
        coordinator.commit(prepared)
    assert owners.calls["parent"] == 0
