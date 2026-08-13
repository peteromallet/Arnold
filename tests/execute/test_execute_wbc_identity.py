from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import AttemptEventType
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    TASK_RESULT_CAPABILITY,
)
from arnold_pipelines.megaplan.custody.action_validator import GateResult
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey
from arnold_pipelines.megaplan.custody.lease_store import open_lease_store
from arnold_pipelines.megaplan.custody.wbc_runtime import ActionBoundaryDeniedError
from arnold_pipelines.megaplan.execute.wbc import build_execute_batch_dispatch_spec


def _dispatch(*, coordinator_attempt_id: str, fence_token: int) -> DispatchIdentity:
    return DispatchIdentity.create(
        dispatch_id="run-1:execute:batch:1:tasks",
        run_id="run-1",
        run_revision="revision-1",
        coordinator_attempt_id=coordinator_attempt_id,
        fence_token=fence_token,
        subject_ids=("T1",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="prereq-1",
        worker_id="worker-1",
    )


def _spec(tmp_path: Path, dispatch: DispatchIdentity):
    return build_execute_batch_dispatch_spec(
        plan_dir=tmp_path,
        state={},  # type: ignore[arg-type]
        dispatch_identity=dispatch,
        batch_number=1,
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
    )


def test_execute_wbc_attempt_identity_is_fenced_and_replayable(tmp_path: Path) -> None:
    first = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    replay = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    next_fence = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-2", fence_token=2))

    assert first.attempt_id == replay.attempt_id
    assert first.start_event.idempotency_key == replay.start_event.idempotency_key
    assert first.start_event.identity.invocation_id == "coord-1"
    assert first.start_event.identity.attempt_ordinal == 1
    assert next_fence.attempt_id != first.attempt_id
    assert next_fence.start_event.idempotency_key != first.start_event.idempotency_key
    assert next_fence.start_event.identity.invocation_id == "coord-2"
    assert next_fence.start_event.identity.attempt_ordinal == 2


def test_execute_wbc_is_enforced_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P7 regression: the execute facade must be ENFORCED under default env,
    matching the canonical production_enforcement_enabled() gate, and carry
    real lease/outbox stores (never the None-wired stubs)."""
    monkeypatch.delenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", raising=False)
    spec = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    assert spec.facade._enforcement_enabled is True
    assert spec.facade._lease_store is not None
    assert spec.facade._outbox is not None


def test_execute_wbc_real_builder_acquires_custody_and_is_authorized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P7 regression: the REAL production builder path (no hand-wired fake
    stores) must acquire custody leases + outbox records for every boundary
    action type and yield an AUTHORIZED boundary under default enforcement."""
    monkeypatch.delenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", raising=False)
    spec = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))

    # The production facade carries real stores, not the None-wired stubs.
    assert spec.facade._lease_store is not None
    assert spec.facade._outbox is not None
    # Every boundary action type has an active lease owned by this runtime.
    for ctx in (
        spec.start_action_context,
        spec.success_action_context,
        spec.failure_action_context,
    ):
        lease = spec.facade._lease_store.current_lease(
            f"custody-lease-{ctx.target.target_digest[:16]}"
        )
        assert lease is not None
        assert lease.is_expired is False
        assert lease.owner_host == ctx.owner_host
        assert lease.owner_pid == ctx.owner_pid
        assert lease.owner_boot_id == ctx.owner_boot_id

    result = spec.run(lambda _start: {"success": True})

    assert result.reserve.action_boundary is not None
    assert result.reserve.action_boundary.gate_result == GateResult.AUTHORIZED
    assert result.reserve.action_boundary.enforcement_enabled is True
    assert result.reserve.action_boundary.is_shadow is False
    assert [event.event_type for event in spec.facade._ledger_store.read_events(spec.attempt_id)] == [
        AttemptEventType.STARTED,
        AttemptEventType.COMPLETED,
    ]
    # The execute facade's three boundary contexts share one target digest
    # (the target key does not embed action_type), so the idempotent custody
    # acquisition yields ONE lease + ONE outbox record that covers every
    # boundary: the validator derives the same lease id and rereads the same
    # wbc_attempt_reference for dispatch/completion/repair alike.
    assert len({ctx.target.target_digest for ctx in (
        spec.start_action_context,
        spec.success_action_context,
        spec.failure_action_context,
    )}) == 1
    records = spec.facade._outbox.list_records()
    assert len([r for r in records if r.wbc_attempt_reference == spec.attempt_id]) == 1
    # The custody tree lives under the plan dir, shared with the other facades.
    assert (tmp_path / "custody" / "leases").is_dir()
    assert (tmp_path / "custody" / "outbox").is_dir()


def test_execute_wbc_replay_joins_same_lease_with_full_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0205: rebuilding the same execute dispatch (same dispatch identity)
    joins the SAME custody lease — one acquire event, idempotent keep — and
    the replayed lease's occurrence key reconstructs the FULL acquisition
    target (digest join is stable across builds)."""
    monkeypatch.delenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", raising=False)
    dispatch = _dispatch(coordinator_attempt_id="coord-1", fence_token=1)
    first = _spec(tmp_path, dispatch)
    replay = _spec(tmp_path, dispatch)
    assert first.attempt_id == replay.attempt_id

    ctx = first.start_action_context
    lease_id = f"custody-lease-{ctx.target.target_digest[:16]}"
    store = replay.facade._lease_store
    lease = store.current_lease(lease_id)
    assert lease is not None
    # The lease history contains exactly one acquire — the replay idempotently
    # kept the same lease rather than appending a second event.
    assert len(store.load_history(lease_id)) == 1
    # The replayed occurrence key joins the full target used at acquisition:
    # replaying the acquire payload reconstructs the same digest.
    assert lease.occurrence_key.target.target_digest == ctx.target.target_digest
    assert lease.wbc_attempt_reference == first.attempt_id


def test_execute_wbc_denies_when_custody_is_contended(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under default enforcement, an execute dispatch whose custody lease is
    held by another runtime is denied at spec build — the lease is never
    stolen, and no STARTED event is appended."""
    monkeypatch.delenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", raising=False)
    dispatch = _dispatch(coordinator_attempt_id="coord-1", fence_token=1)
    # Pre-seed a lease for the start boundary target owned by a DIFFERENT
    # runtime, so the production builder's idempotent acquisition must deny.
    # The digest is derived exactly as the builder/validator derive it: the
    # legacy six-field CustodyTargetKey over the execute dispatch target.
    start_target = CustodyTargetKey(
        "execute_batch",
        dispatch.dispatch_id,
        "dispatch",
        "batch",
        "1",
        "execute_batch_checkpoint",
    )
    foreign_digest = start_target.target_digest
    foreign_lease_id = f"custody-lease-{foreign_digest[:16]}"
    open_lease_store(tmp_path / "custody" / "leases").acquire(
        lease_id=foreign_lease_id,
        owner_host="foreign-host",
        owner_pid="999999",
        owner_boot_id="foreign-boot",
        run_authority_grant_id="foreign-grant",
        coordinator_fence_token=0,
        wbc_attempt_reference="foreign-attempt",
        occurrence_digest=foreign_digest,
        custody_epoch=1,
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        idempotency_key="foreign-seed",
    )
    with pytest.raises(ActionBoundaryDeniedError, match="not authorized"):
        _spec(tmp_path, dispatch)
    # No event may have been appended by the denied build.
    store = SqliteAttemptLedgerStore(tmp_path / ".execute_wbc_attempts.sqlite3")
    try:
        (count,) = store.conn.execute("SELECT COUNT(1) FROM attempt_events").fetchone()
        assert count == 0
    finally:
        store.close()


def test_execute_wbc_is_shadow_only_when_explicitly_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shadow mode is reachable only via the explicit disable switch (env or
    explicit parameter); the facade must be constructed with enforcement OFF
    then, while still acquiring custody."""
    monkeypatch.setenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", "0")
    spec = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    assert spec.facade._enforcement_enabled is False
    assert spec.facade._lease_store is not None
    assert spec.facade._outbox is not None

    monkeypatch.delenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", raising=False)
    explicit = build_execute_batch_dispatch_spec(
        plan_dir=tmp_path / "explicit",
        state={},  # type: ignore[arg-type]
        dispatch_identity=_dispatch(coordinator_attempt_id="coord-2", fence_token=2),
        batch_number=1,
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        enforcement_enabled=False,
    )
    assert explicit.facade._enforcement_enabled is False


def test_execute_wbc_shadow_mode_is_denied_with_no_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-0013 deny-by-default lock: ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=0
    puts the execute builder in functional shadow mode (SHADOW_PASS
    boundaries), but SHADOW_PASS NEVER authorizes a WBC effect — the dispatch
    is DENIED at the reserve boundary and no ledger event is appended.  The
    previous Option-A behavior of accepting SHADOW_PASS boundaries end to end
    blessed the unsafe path and is locked out here; observation-only rereads
    remain available."""
    monkeypatch.setenv("ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT", "0")
    spec = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    assert spec.facade._enforcement_enabled is False

    with pytest.raises(ActionBoundaryDeniedError, match="not authorized: shadow_pass"):
        spec.run(lambda _start: {"success": True})

    # Fail-closed: the denied dispatch appended no WBC events.  (Custody
    # leases/outbox records are acquired at spec build, before any boundary
    # validation, and are unchanged — the SHADOW_PASS boundary itself never
    # admits an effect.)
    assert spec.facade._ledger_store.read_events(spec.attempt_id) == []
