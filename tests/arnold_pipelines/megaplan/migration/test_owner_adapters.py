"""Focused tests for canonical owner adapter boundaries."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from arnold.workflow.attempt_ledger_store import GlobalEffectReservation, SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey, RepairOccurrenceKey
from arnold_pipelines.megaplan.custody.lease_store import CustodyLeaseStore
from arnold_pipelines.megaplan.migration import (
    AttemptLedgerWbcOwner,
    ChildSelector,
    CustodyLeaseStoreOwner,
    MigrationCoordinator,
    IndependentChildRequired,
    OwnerUnavailable,
    RunAuthorityJournalOwner,
    WbcReservation,
)
from arnold_pipelines.run_authority.reducer import RunAuthorityView


def _effect() -> GlobalEffectIdentity:
    return GlobalEffectIdentity(
        environment_id="env",
        action_target="occurrence-child-migration",
        action_version="v1",
        effect_family="arnold.megaplan.occurrence_child_migration.v1",
        provider_target="child",
        canonical_request_identity="request",
        boundary_schema_hash="schema",
    )


def test_missing_run_authority_journal_fails_closed() -> None:
    with pytest.raises(OwnerUnavailable, match="old r5 owner records are absent"):
        RunAuthorityJournalOwner(None)


def test_incomplete_run_authority_journal_fails_closed() -> None:
    class Incomplete:
        def snapshot(self, *_args):
            return None

    with pytest.raises(OwnerUnavailable, match="incomplete"):
        RunAuthorityJournalOwner(Incomplete())


def test_wbc_adapter_uses_one_canonical_attempt_ledger(tmp_path) -> None:
    store = SqliteAttemptLedgerStore(tmp_path / "attempt-ledger.sqlite3")
    owner = AttemptLedgerWbcOwner(store)
    effect = _effect()
    reserved = owner.reserve_child(
        attempt_id="11111111-1111-4111-8111-111111111111",
        effect_identity=effect,
        migration_idempotency_key="migration-key",
    )
    reread = owner.read_reservation(reserved.attempt_id, reserved.glek)
    assert reread is not None
    assert reread.attempt_id == reserved.attempt_id
    assert reread.glek == reserved.glek
    assert reread.reservation.effect_identity == reserved.reservation.effect_identity
    assert reserved.glek == effect.global_logical_effect_key


def test_custody_adapter_uses_canonical_lease_store(tmp_path) -> None:
    target = CustodyTargetKey(
        environment="env",
        session="session",
        chain="chain",
        plan_revision="child-rev",
        phase="execute",
        task="task",
        attempt="child-attempt",
        normalized_failure_kind="stalled",
        blocker_or_phase_result_hash="blocker",
        fence="9",
        chain_identity="chain",
    )
    occurrence = RepairOccurrenceKey(
        target=target,
        run_id="child-run",
        run_revision="child-rev",
        coordinator_attempt_id="child-coordinator",
        fence_token=9,
        wbc_attempt_reference="child-wbc",
    )
    authority = SimpleNamespace(
        grant=SimpleNamespace(grant_id="child-grant"),
        fence=SimpleNamespace(token=9),
    )
    wbc_effect = _effect()
    wbc = WbcReservation(
        attempt_id="child-wbc",
        reservation=GlobalEffectReservation(
            attempt_id="child-wbc",
            effect_identity=wbc_effect,
            global_logical_effect_key=wbc_effect.global_logical_effect_key,
            first_reserved_ns=1,
            reservation_count=1,
            is_new=True,
        ),
    )
    owner = CustodyLeaseStoreOwner(
        CustodyLeaseStore(tmp_path / "leases"),
        owner_host="host",
        owner_pid="1",
        owner_boot_id="boot",
    )
    lease = owner.acquire_child(
        lease_id="child-lease",
        occurrence=occurrence,
        authority=authority,
        wbc=wbc,
        idempotency_key="migration-key",
    )
    assert owner.read_lease("child-lease") == lease
    assert lease.occurrence_key.occurrence_digest == occurrence.occurrence_digest


def test_prepare_rejects_r5_projection_without_authority_records() -> None:
    empty_view = RunAuthorityView(
        schema_version=1,
        run_id="run",
        run_revision="rev",
        journal_cursor=0,
        evidence_set_digest="none",
        evidence=(),
        observations=(),
        fences=(),
        grants=(),
        attempts=(),
        claims=(),
        decisions=(),
        quarantines=(),
        diagnostics=(),
        view_hash="view",
    )
    parent = SimpleNamespace(
        occurrence=SimpleNamespace(
            occurrence_digest="sha256:legacy-parent",
            run_id="legacy-run",
            target=SimpleNamespace(environment="env"),
        ),
        authority=SimpleNamespace(view=empty_view),
    )
    coordinator = MigrationCoordinator(run_authority=None, wbc=None, custody=None)  # type: ignore[arg-type]
    with pytest.raises(IndependentChildRequired) as exc_info:
        coordinator.prepare(parent, ChildSelector("child-rev", {"task": "repair"}))
    assert exc_info.value.disposition.action == "start_fresh_independent_child"
    assert exc_info.value.disposition.requires_human_approval is True
