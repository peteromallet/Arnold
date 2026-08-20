"""Focused tests for T-0101e: operator-only exact-occurrence join + fenced claim.

Covers the happy path (exact join, fenced claim, receipt, relational
identity) and the refusals (wrong occurrence, unexpired foreign lease,
non-operator actor, not-paused/not-blocked chain) with zero-mutation checks.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
import threading

import pytest

from arnold_pipelines.megaplan.chain.occurrence_join import (
    join_exact_occurrence,
    occurrence_claim_attempt_id,
    occurrence_join_lease_id,
)
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, save_chain_state
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.custody.contracts import (
    normalize_repair_occurrence_key,
    process_birth_identity,
)
from arnold_pipelines.megaplan.custody.lease_store import open_lease_store
from arnold_pipelines.megaplan.types import CliError

from tests.cloud.repair_identity_fixtures import repair_identity

SESSION = "chain-session-1"
CLAIM_ID = "operator-claim-0001"


@pytest.fixture(autouse=True)
def _align_repair_queue_root(tmp_path: Path) -> Iterator[None]:
    """T-0640 D1: occurrence-join resolves the queue root from
    ARNOLD_REPAIR_QUEUE_ROOT (else the marker-adjacent box-central queue —
    never project_dir).  Pin it to this test's tmp queue so every direct and
    CLI join reads the queue ``_enqueue`` wrote.  Set directly on
    os.environ (restored in teardown) so a test's ``monkeypatch.undo()``
    cannot silently reset it to the box-central default."""
    prior = os.environ.get("ARNOLD_REPAIR_QUEUE_ROOT")
    os.environ["ARNOLD_REPAIR_QUEUE_ROOT"] = str(
        tmp_path / ".megaplan" / "repair-queue"
    )
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("ARNOLD_REPAIR_QUEUE_ROOT", None)
        else:
            os.environ["ARNOLD_REPAIR_QUEUE_ROOT"] = prior


def _chain(tmp_path: Path, *, plan_state: str = "blocked", chain_last_state: str = "blocked") -> tuple[Path, Path]:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    brief = initiative / "brief.md"
    brief.write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\n"
        "milestones:\n  - label: M1\n    idea: brief.md\n"
    )
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="demo-plan",
        last_state=chain_last_state,
        completed=[],
    )
    save_chain_state(spec, state)
    return spec, plan


def _identity() -> dict[str, object]:
    return dict(
        repair_identity(
            session=SESSION,
            plan="demo-plan",
            failure_kind="deterministic_phase_failure",
            phase="gate",
            task="phase:gate",
            environment=str(Path("/workspace") / SESSION),
        )
    )


def _plan_payload(identity: dict[str, object], *, current_state: str = "blocked") -> dict[str, object]:
    return {
        "current_state": current_state,
        "phase": "gate",
        "iteration": 1,
        "latest_failure": {
            "kind": "deterministic_phase_failure",
            "phase": "gate",
            "recorded_at": "2026-08-12T00:00:00Z",
            "message": "blocked_no_lease: no current custody lease for the gate boundary",
            "metadata": {"blocked_no_lease": "gate", "repair_identity": identity},
        },
        "resume_cursor": {
            "phase": "gate",
            "retry_strategy": "repair_phase_contract",
        },
        "meta": {"repair_identity": identity, "kept": True},
    }


def _write_plan_state(plan: Path, payload: dict[str, object]) -> None:
    (plan / "state.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _enqueue(tmp_path: Path, identity: dict[str, object]) -> dict[str, object]:
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    result = repair_requests.enqueue_occurrence_bound_repair_request(
        queue_root=queue_root,
        session=SESSION,
        source="lifecycle_failure",
        workspace=tmp_path,
        run_kind="chain",
        marker_dir=tmp_path / ".megaplan" / "plans" / "demo-plan",
        target={
            "plan_dir": str(tmp_path / ".megaplan" / "plans" / "demo-plan"),
            "plan_name": "demo-plan",
            "workspace_path": str(tmp_path),
            "retry_strategy": "repair_phase_contract",
        },
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "gate",
            "milestone_or_plan": "demo-plan",
            "gate_recommendation": "repair gate contract",
            "blocked_task_id": "phase:gate",
        },
        root_cause_hint="blocked_no_lease: gate boundary lease unavailable",
        occurrence_identity=identity,
    )
    assert result["status"] == "queued", result
    return result


def _plan_dir(tmp_path: Path) -> Path:
    return tmp_path / ".megaplan" / "plans" / "demo-plan"


def _evidence_receipt(tmp_path: Path, name: str = "occurrence-join-receipt.json") -> Path:
    """A valid receipt destination under the plan evidence root."""
    return _plan_dir(tmp_path) / "evidence" / name


def _join_kwargs(tmp_path: Path, spec: Path, result: dict[str, object], **overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "spec_path": spec,
        "project_dir": tmp_path,
        "session": SESSION,
        "occurrence_id": result["request"]["repair_identity_key"],
        "request_id": result["request"]["request_id"],
        "decision_id": result["decision"]["decision_id"],
        "claim_id": CLAIM_ID,
        "reason": "T-0101 operator join",
        "actor": "operator",
        "receipt_path": _evidence_receipt(tmp_path),
    }
    kwargs.update(overrides)
    return kwargs


def _f01_digest(result: dict[str, object]) -> str:
    normalized = repair_requests.normalize_repair_identity(result["request"]["repair_identity"])
    assert normalized is not None
    occurrence = normalize_repair_occurrence_key(normalized["occurrence"])
    assert occurrence is not None
    return occurrence.occurrence_digest


def _snapshot_state(tmp_path: Path) -> dict[str, bytes]:
    """Snapshot EVERY plan-side file: plan state.json, the chain spec
    (chain.yaml + briefs), the immutable repair-queue request/decision
    records, plan markers/manifests, the WBC attempt ledger (plus WAL/SHM
    sidecars) and the custody lease store.  The snapshot is taken
    recursively over the whole ``.megaplan`` tree so no plan-side file can
    silently escape coverage."""
    payload: dict[str, bytes] = {}
    root = tmp_path / ".megaplan"
    if root.is_dir():
        for child in sorted(root.rglob("*")):
            if child.is_file():
                payload[str(child)] = child.read_bytes()
    return payload


def _is_allowed_provisioning(path: str) -> bool:
    """The ONLY permitted side effects of a refusal: the request-scoped
    decision/admission advisory flock file ``<sha256(request_id)>.lock``
    under ``<queue root>/decision-admission-locks/`` and the
    occurrence-scoped advisory flock file ``occurrence-<sha256>.lock`` under
    ``<plan dir>/custody/leases/`` (both created on entering their
    respective locks, intentionally never removed).  Idempotent WBC schema
    DDL on an ALREADY-EXISTING database is a byte no-op on the current
    schema, so it never appears as a new or changed file here."""
    p = Path(path)
    if not p.name.endswith(".lock"):
        return False
    parts = p.parts
    if "decision-admission-locks" in parts:
        # <queue root>/decision-admission-locks/<sha256(request_id)>.lock
        return True
    return (
        p.name.startswith("occurrence-")
        and "custody" in parts
        and "leases" in parts
    )


def _is_sqlite_sidecar(path: str) -> bool:
    """WAL-mode ``-wal``/``-shm`` sidecars of an ALREADY-EXISTING WBC
    database.  SQLite rewrites the shared-memory index on every connection
    open (even pure reads) and may materialize the sidecars when a
    pre-existing non-WAL database is first opened in WAL mode, so their bytes
    are not a sound zero-mutation oracle.  The main ``.sqlite3`` database
    bytes ARE compared (verified byte-stable across read-only reopens)."""
    return path.endswith(".sqlite3-wal") or path.endswith(".sqlite3-shm")


def _assert_no_join_mutation(tmp_path: Path, before: dict[str, bytes], receipt_path: Path) -> None:
    after = _snapshot_state(tmp_path)
    before_filtered = {
        k: v
        for k, v in before.items()
        if not _is_allowed_provisioning(k) and not _is_sqlite_sidecar(k)
    }
    after_filtered = {
        k: v
        for k, v in after.items()
        if not _is_allowed_provisioning(k) and not _is_sqlite_sidecar(k)
    }
    assert after_filtered == before_filtered, (
        "join refusal must leave every plan-side file byte-identical "
        "(state.json, chain.yaml, queue records, markers/manifests, WBC "
        "ledger, custody lease store)"
    )
    # Only the allowed lock provisioning may be NEW after a refusal (a WAL
    # sidecar may additionally appear beside a database that already existed,
    # as part of the permitted schema provisioning on an older database).
    new_files = set(after) - set(before)
    assert all(
        _is_allowed_provisioning(p)
        or (_is_sqlite_sidecar(p) and p.removesuffix("-wal").removesuffix("-shm") in before)
        for p in new_files
    ), f"refusal created unexpected files: {sorted(new_files)}"
    assert not receipt_path.exists(), "no receipt may be emitted on refusal"
    # A refusal must never CREATE the WBC ledger (schema DDL provisioning is
    # only permitted on an ALREADY-EXISTING database, whose bytes the
    # byte-identical check above already pins).
    wbc_path = tmp_path / ".megaplan" / "plans" / "demo-plan" / ".phase_wbc_attempts.sqlite3"
    if str(wbc_path) not in before:
        assert not wbc_path.exists(), "refusal must not create the WBC ledger"


def _setup(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    spec, plan = _chain(tmp_path)
    identity = _identity()
    _write_plan_state(plan, _plan_payload(identity))
    result = _enqueue(tmp_path, identity)
    return spec, plan, result


# ── Happy path ────────────────────────────────────────────────────────────


def test_join_acquires_fenced_claim_and_emits_receipt(tmp_path: Path) -> None:
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.execution_attempt_ledger import AttemptEventType

    spec, plan, result = _setup(tmp_path)
    chain_state_before = load_chain_state(spec).to_dict()
    queue_before = _snapshot_state(tmp_path / ".megaplan" / "repair-queue")
    receipt_path = _evidence_receipt(tmp_path)

    payload = join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))

    assert payload["status"] == "claimed"
    assert payload["request_id"] == result["request"]["request_id"]
    assert payload["occurrence"] == result["request"]["repair_identity_key"]
    assert payload["decision_id"] == result["decision"]["decision_id"]
    assert payload["claim_id"] == CLAIM_ID
    assert payload["receipt_path"] == str(receipt_path.resolve())

    # Durable receipt with all four IDs + the relational identity.
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema"] == "arnold.megaplan.occurrence-join.v1"
    assert receipt["session"] == SESSION
    assert receipt["request_id"] == result["request"]["request_id"]
    assert receipt["decision_id"] == result["decision"]["decision_id"]
    assert receipt["claim_id"] == CLAIM_ID
    assert receipt["attempt_id"] == payload["attempt_id"]
    relation = receipt["relation"]
    assert relation["request_id"] == result["request"]["request_id"]
    assert relation["decision_request_id"] == result["request"]["request_id"]
    assert relation["claim_request_id"] == result["request"]["request_id"]
    assert relation["attempt_request_id"] == result["request"]["request_id"]
    assert relation["request_occurrence"] == result["request"]["repair_identity_key"]
    assert relation["claim_occurrence_id"] == result["request"]["repair_identity_key"]
    assert relation["attempt_occurrence_id"] == result["request"]["repair_identity_key"]
    assert relation["attempt_claim_id"] == CLAIM_ID
    assert relation["attempt_decision_id"] == result["decision"]["decision_id"]
    assert relation["attempt_lease_id"] == payload["lease_id"]

    # Fence/epoch carry (T-0101e): the lease, the receipt and the WBC STARTED
    # event all record the occurrence's AUTHORITATIVE fence token + attempt
    # identity (from the normalized repair identity), never a fabricated 0/1.
    normalized = repair_requests.normalize_repair_identity(result["request"]["repair_identity"])
    assert normalized is not None
    occurrence_key = normalize_repair_occurrence_key(normalized["occurrence"])
    assert occurrence_key is not None
    assert occurrence_key.fence_token == 1
    assert normalized["custody_epoch"] == 1

    # Durable receipt carries the fence + attempt identity in the occurrence
    # block and the lease's coordinator fence in the lease block.
    assert receipt["occurrence"]["fence_token"] == occurrence_key.fence_token
    assert receipt["occurrence"]["coordinator_attempt_id"] == occurrence_key.coordinator_attempt_id
    assert receipt["occurrence"]["wbc_attempt_reference"] == occurrence_key.wbc_attempt_reference
    assert receipt["lease"]["coordinator_fence_token"] == occurrence_key.fence_token

    # WBC claim attempt (the claim record) is durably started with the exact
    # relational identity embedded in its payload.
    attempt_id = occurrence_claim_attempt_id(plan, CLAIM_ID)
    assert payload["attempt_id"] == attempt_id
    store = SqliteAttemptLedgerStore(plan / ".phase_wbc_attempts.sqlite3")
    events = store.read_events(attempt_id)
    assert len(events) == 1
    assert events[0].event_type == AttemptEventType.STARTED
    assert not store.has_terminal_event(attempt_id)
    started_payload = events[0].payload
    assert started_payload["kind"] == "occurrence_join"
    assert started_payload["claim_id"] == CLAIM_ID
    assert started_payload["request_id"] == result["request"]["request_id"]
    assert started_payload["decision_id"] == result["decision"]["decision_id"]
    assert started_payload["occurrence_id"] == result["request"]["repair_identity_key"]
    assert started_payload["lease_id"] == payload["lease_id"]

    # WBC STARTED payload carries the fence + coordinator attempt reference.
    assert started_payload["fence_token"] == occurrence_key.fence_token
    assert started_payload["coordinator_attempt_id"] == occurrence_key.coordinator_attempt_id
    assert started_payload["wbc_attempt_reference"] == occurrence_key.wbc_attempt_reference

    # Custody lease is acquired with fence semantics (owner + occurrence digest + TTL).
    lease_store = open_lease_store(plan / "custody" / "leases")
    lease = lease_store.current_lease(payload["lease_id"])
    assert lease is not None
    assert not lease.is_expired
    owner = process_birth_identity()
    assert lease.owner_host == owner["host"]
    assert lease.owner_pid == owner["pid"]
    assert lease.occurrence_key.occurrence_digest == _f01_digest(result)

    # The lease carries the occurrence's authoritative fence token and a
    # custody epoch seeded from the recorded identity (never 0/1 fabrications).
    assert lease.coordinator_fence_token == 1
    assert lease.custody_epoch == 1

    # Requirement 5: chain state + immutable queue records are untouched.
    assert load_chain_state(spec).to_dict() == chain_state_before
    assert _snapshot_state(tmp_path / ".megaplan" / "repair-queue") == queue_before


def test_join_accepts_durably_paused_chain(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.chain.operator_pause import AUTHORITY_KEY, AUTHORITY_SCHEMA

    spec, plan, result = _setup(tmp_path)
    _write_plan_state(plan, _plan_payload(_identity(), current_state="paused"))
    state = load_chain_state(spec)
    state.metadata[AUTHORITY_KEY] = {
        "schema_version": AUTHORITY_SCHEMA,
        "active": True,
        "paused_at": "2026-08-12T00:00:00Z",
        "actor": "operator",
        "reason": "T-0101 pauses first",
    }
    state.last_state = "paused"
    save_chain_state(spec, state)

    payload = join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))
    assert payload["status"] == "claimed"
    assert payload["paused"] is True
    # The paused gate admits the join even when the plan is not stopped-blocked.
    assert payload["stopped_blocked"] is False


def test_join_is_idempotent_for_the_same_claim(tmp_path: Path) -> None:
    spec, plan, result = _setup(tmp_path)
    kwargs = _join_kwargs(tmp_path, spec, result)
    first = join_exact_occurrence(**kwargs)
    second = join_exact_occurrence(**kwargs)

    assert first["status"] == "claimed"
    assert second["status"] == "already_claimed"
    assert second["attempt_id"] == first["attempt_id"]
    assert second["lease_id"] == first["lease_id"]
    receipt = json.loads(Path(second["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "already_claimed"
    assert receipt["relation"] == first["receipt"]["relation"]


def test_join_is_idempotent_across_process_restart(tmp_path: Path) -> None:
    spec, plan, result = _setup(tmp_path)
    kwargs = _join_kwargs(tmp_path, spec, result)
    first = join_exact_occurrence(**kwargs)
    lease_id = first["lease_id"]
    owner = first["receipt"]["lease"]["owner"]

    # Simulate a process restart: the recorded lease owner is now a different
    # host/pid/boot (the restarted process's identity) while the claim tuple
    # stays relationally exact (acquire payload + WBC record unchanged).
    lease_store = open_lease_store(plan / "custody" / "leases")
    lease_store.transfer(
        lease_id=lease_id,
        owner_host=owner["host"],
        owner_pid=owner["pid"],
        owner_boot_id=owner["boot_id"],
        new_owner_host="restarted-host",
        new_owner_pid="98765",
        new_owner_boot_id="restarted-boot",
        custody_epoch=2,
    )
    lease = lease_store.current_lease(lease_id)
    assert lease is not None
    assert lease.owner_pid == "98765"
    assert not lease.is_expired

    # An identical CLI retry from the "new" process must succeed as an
    # idempotent re-join (NOT lease_owned_elsewhere) with the same claim ids
    # and a regenerated receipt.
    second = join_exact_occurrence(**kwargs)
    assert second["status"] == "already_claimed"
    assert second["attempt_id"] == first["attempt_id"]
    assert second["lease_id"] == lease_id
    assert second["claim_id"] == CLAIM_ID
    assert second["request_id"] == result["request"]["request_id"]
    assert second["decision_id"] == result["decision"]["decision_id"]
    receipt = json.loads(Path(second["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "already_claimed"
    assert receipt["relation"] == first["receipt"]["relation"]
    # The regenerated receipt reflects the ACTUAL recorded lease owner (the
    # restarted process), not this invocation's identity.
    assert receipt["lease"]["owner"]["pid"] == "98765"


def test_join_reclaims_relationally_exact_lease_without_wbc(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.execution_attempt_ledger import AttemptEventType

    spec, plan, result = _setup(tmp_path)
    kwargs = _join_kwargs(tmp_path, spec, result)
    attempt_id = occurrence_claim_attempt_id(plan, CLAIM_ID)
    lease_id = occurrence_join_lease_id(CLAIM_ID)
    f01_digest = _f01_digest(result)
    normalized = repair_requests.normalize_repair_identity(result["request"]["repair_identity"])
    assert normalized is not None
    occurrence_key = normalize_repair_occurrence_key(normalized["occurrence"])
    assert occurrence_key is not None

    # A crashed first invocation acquired the lease but died before writing
    # the WBC claim + receipt: the lease is relationally exact (same tuple)
    # yet owned by the dead process.
    lease_store = open_lease_store(plan / "custody" / "leases")
    lease_store.acquire(
        lease_id=lease_id,
        owner_host="crashed-host",
        owner_pid="111",
        owner_boot_id="crashed-boot",
        run_authority_grant_id=str(result["request"]["request_id"]),
        coordinator_fence_token=0,
        wbc_attempt_reference=attempt_id,
        occurrence_digest=f01_digest,
        custody_epoch=1,
        expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        payload={
            "kind": "occurrence_join",
            "occurrence_key": occurrence_key.to_dict(),
            "occurrence_id": result["request"]["repair_identity_key"],
            "claim_id": CLAIM_ID,
            "request_id": result["request"]["request_id"],
            "decision_id": result["decision"]["decision_id"],
            "session": SESSION,
            "actor": "operator",
            "reason": "T-0101 operator join",
        },
    )

    payload = join_exact_occurrence(**kwargs)
    assert payload["status"] == "claimed"
    assert payload["attempt_id"] == attempt_id
    assert payload["lease_id"] == lease_id
    assert payload["claim_id"] == CLAIM_ID
    assert payload["request_id"] == result["request"]["request_id"]
    assert payload["decision_id"] == result["decision"]["decision_id"]
    receipt = json.loads(Path(payload["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["claim_id"] == CLAIM_ID
    assert receipt["attempt_id"] == attempt_id
    assert receipt["request_id"] == result["request"]["request_id"]
    assert receipt["decision_id"] == result["decision"]["decision_id"]

    # The WBC claim was durably started by this re-join.
    store = SqliteAttemptLedgerStore(plan / ".phase_wbc_attempts.sqlite3")
    events = store.read_events(attempt_id)
    assert len(events) == 1
    assert events[0].event_type == AttemptEventType.STARTED
    assert events[0].payload["claim_id"] == CLAIM_ID


def test_join_reclaims_ttl_expired_lease_without_terminal_event(tmp_path: Path) -> None:
    import time
    from datetime import datetime, timedelta, timezone

    spec, plan, result = _setup(tmp_path)
    kwargs = _join_kwargs(tmp_path, spec, result)
    attempt_id = occurrence_claim_attempt_id(plan, CLAIM_ID)
    lease_id = occurrence_join_lease_id(CLAIM_ID)
    f01_digest = _f01_digest(result)
    normalized = repair_requests.normalize_repair_identity(result["request"]["repair_identity"])
    assert normalized is not None
    occurrence_key = normalize_repair_occurrence_key(normalized["occurrence"])
    assert occurrence_key is not None

    # A prior join's lease lapses (TTL fence backstop) without ever being
    # released: the last lifecycle event is still "acquire" but the expiry
    # passes.  A re-join must reclaim it rather than be stranded.
    lease_store = open_lease_store(plan / "custody" / "leases")
    lease_store.acquire(
        lease_id=lease_id,
        owner_host="stale-host",
        owner_pid="555",
        owner_boot_id="stale-boot",
        run_authority_grant_id=str(result["request"]["request_id"]),
        coordinator_fence_token=0,
        wbc_attempt_reference=attempt_id,
        occurrence_digest=f01_digest,
        custody_epoch=1,
        expires_at=(
            datetime.now(timezone.utc) + timedelta(seconds=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        payload={
            "kind": "occurrence_join",
            "occurrence_key": occurrence_key.to_dict(),
            "occurrence_id": result["request"]["repair_identity_key"],
            "claim_id": CLAIM_ID,
            "request_id": result["request"]["request_id"],
            "decision_id": result["decision"]["decision_id"],
            "session": SESSION,
            "actor": "operator",
            "reason": "T-0101 operator join",
        },
    )
    time.sleep(2)
    assert lease_store.current_lease(lease_id).is_expired

    payload = join_exact_occurrence(**kwargs)
    assert payload["status"] == "claimed"
    assert payload["attempt_id"] == attempt_id
    assert payload["lease_id"] == lease_id
    lease = lease_store.current_lease(lease_id)
    assert lease is not None
    assert not lease.is_expired
    owner = process_birth_identity()
    assert lease.owner_pid == owner["pid"]
    receipt = json.loads(Path(payload["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["claim_id"] == CLAIM_ID
    assert receipt["attempt_id"] == attempt_id


def test_join_receipt_write_failure_rolls_back_and_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.execution_attempt_ledger import AttemptEventType

    spec, plan, result = _setup(tmp_path)
    kwargs = _join_kwargs(tmp_path, spec, result)
    attempt_id = occurrence_claim_attempt_id(plan, CLAIM_ID)
    lease_id = occurrence_join_lease_id(CLAIM_ID)

    import os as _os

    receipt_path = _evidence_receipt(tmp_path)

    resolved_receipt = str(receipt_path.resolve())
    real_replace = _os.replace

    def _raise_oserror(src: str | bytes | Path, dst: str | bytes | Path, *_: object) -> None:
        # Only the RECEIPT rename fails; lease-store renames (the rollback
        # release) must keep working.
        if str(dst) == resolved_receipt:
            raise OSError("simulated receipt write failure")
        return real_replace(src, dst)

    monkeypatch.setattr(_os, "replace", _raise_oserror)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**kwargs)
    assert excinfo.value.code == "receipt_write_failed"

    # The custody lease was rolled back (terminal release) so the occurrence
    # is not stranded behind a foreign-owner fence.
    lease_store = open_lease_store(plan / "custody" / "leases")
    lease = lease_store.current_lease(lease_id)
    assert lease is not None
    assert lease_store.load_history(lease_id)[-1].event_type == "release"

    # The WBC claim attempt remains as the re-join anchor (append-only ledger).
    store = SqliteAttemptLedgerStore(plan / ".phase_wbc_attempts.sqlite3")
    events = store.read_events(attempt_id)
    assert len(events) == 1
    assert events[0].event_type == AttemptEventType.STARTED
    assert not store.has_terminal_event(attempt_id)

    # An identical re-join (same claim id) reclaims the lease and completes
    # the receipt.
    monkeypatch.undo()
    retry = join_exact_occurrence(**kwargs)
    assert retry["status"] == "already_claimed"
    assert retry["attempt_id"] == attempt_id
    assert retry["lease_id"] == lease_id
    receipt = json.loads(Path(retry["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "already_claimed"
    assert receipt["claim_id"] == CLAIM_ID
    assert receipt["request_id"] == result["request"]["request_id"]
    assert receipt["decision_id"] == result["decision"]["decision_id"]
    # The re-join re-acquired the lease fresh (not the terminal record).
    reacquired = lease_store.current_lease(lease_id)
    assert reacquired is not None
    assert not reacquired.is_expired


# ── Refusals (zero mutation) ──────────────────────────────────────────────


def test_join_refuses_wrong_occurrence_id_with_zero_mutation(tmp_path: Path) -> None:
    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)
    before = _snapshot_state(tmp_path)
    kwargs = _join_kwargs(tmp_path, spec, result, occurrence_id="deadbeef" * 8)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**kwargs)
    assert excinfo.value.code == "occurrence_mismatch"

    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_refuses_wrong_request_and_decision_ids(tmp_path: Path) -> None:
    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)

    before = _snapshot_state(tmp_path)
    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result, request_id="not-a-request"))
    assert excinfo.value.code == "request_not_found"
    _assert_no_join_mutation(tmp_path, before, receipt_path)

    before = _snapshot_state(tmp_path)
    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result, decision_id="not-a-decision"))
    assert excinfo.value.code == "decision_not_found"
    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_refuses_existing_unexpired_foreign_lease(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)

    # A foreign, unexpired custody lease covers the same occurrence digest.
    foreign_lease_id = occurrence_join_lease_id("some-other-operator-claim")
    assert foreign_lease_id != occurrence_join_lease_id(CLAIM_ID)
    lease_store = open_lease_store(plan / "custody" / "leases")
    f01_digest = _f01_digest(result)
    normalized = repair_requests.normalize_repair_identity(result["request"]["repair_identity"])
    assert normalized is not None
    occurrence_key = normalize_repair_occurrence_key(normalized["occurrence"])
    assert occurrence_key is not None
    lease_store.acquire(
        lease_id=foreign_lease_id,
        owner_host="other-host",
        owner_pid="4242",
        owner_boot_id="other-boot",
        run_authority_grant_id="foreign-grant",
        coordinator_fence_token=0,
        wbc_attempt_reference="foreign-wbc",
        occurrence_digest=f01_digest,
        custody_epoch=1,
        expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        payload={"occurrence_key": occurrence_key.to_dict(), "kind": "occurrence_join"},
    )
    # Zero-mutation baseline INCLUDES the pre-seeded foreign lease.
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))
    assert excinfo.value.code == "unexpired_foreign_lease"
    assert "foreign" in excinfo.value.message

    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_refuses_foreign_lease_with_different_relational_tuple(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)
    attempt_id = occurrence_claim_attempt_id(plan, CLAIM_ID)
    lease_id = occurrence_join_lease_id(CLAIM_ID)
    f01_digest = _f01_digest(result)
    normalized = repair_requests.normalize_repair_identity(result["request"]["repair_identity"])
    assert normalized is not None
    occurrence_key = normalize_repair_occurrence_key(normalized["occurrence"])
    assert occurrence_key is not None

    # Same deterministic lease id, but the recorded claim tuple differs
    # (different decision id) → a genuinely different claim → refuse.
    lease_store = open_lease_store(plan / "custody" / "leases")
    lease_store.acquire(
        lease_id=lease_id,
        owner_host="other-host",
        owner_pid="4242",
        owner_boot_id="other-boot",
        run_authority_grant_id=str(result["request"]["request_id"]),
        coordinator_fence_token=0,
        wbc_attempt_reference=attempt_id,
        occurrence_digest=f01_digest,
        custody_epoch=1,
        expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        payload={
            "kind": "occurrence_join",
            "occurrence_key": occurrence_key.to_dict(),
            "occurrence_id": result["request"]["repair_identity_key"],
            "claim_id": CLAIM_ID,
            "request_id": result["request"]["request_id"],
            "decision_id": "a-different-decision-id",
            "session": SESSION,
            "actor": "operator",
            "reason": "T-0101 operator join",
        },
    )
    # Zero-mutation baseline INCLUDES the pre-seeded lease.
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))
    assert excinfo.value.code == "lease_owned_elsewhere"

    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_refuses_non_operator_actor(tmp_path: Path) -> None:
    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result, actor="repair-owner"))
    assert excinfo.value.code == "actor_forbidden"

    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_refuses_chain_that_is_neither_paused_nor_blocked(tmp_path: Path) -> None:
    spec, plan, result = _setup(tmp_path)
    _write_plan_state(plan, _plan_payload(_identity(), current_state="planned"))
    state = load_chain_state(spec)
    state.last_state = "planned"
    save_chain_state(spec, state)
    receipt_path = _evidence_receipt(tmp_path)
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))
    assert excinfo.value.code == "chain_not_paused_or_blocked"

    _assert_no_join_mutation(tmp_path, before, receipt_path)


# ── Decision admission (T-0101e): only the LATEST 'accepted' decision admits ─


def test_join_refuses_every_non_accepted_decision_kind_with_zero_mutation(tmp_path: Path) -> None:
    """Every non-accepted DecisionKind is refused with a typed error and zero
    mutation, even when the decision is bound to the exact request."""
    from arnold_pipelines.megaplan.cloud.repair_requests import write_decision

    non_accepted_kinds = (
        "coalesced",
        "stale",
        "superseded",
        "malformed",
        "dispatched",
        "claim_retry",
        "claim_alert",
    )
    for kind in non_accepted_kinds:
        root = tmp_path / kind
        root.mkdir(parents=True)
        # T-0640 D1: each sub-tree carries its own aligned queue root.
        os.environ["ARNOLD_REPAIR_QUEUE_ROOT"] = str(
            root / ".megaplan" / "repair-queue"
        )
        spec, plan, result = _setup(root)
        queue_root = root / ".megaplan" / "repair-queue"
        receipt_path = _evidence_receipt(root)
        decision = write_decision(
            queue_root,
            request_id=str(result["request"]["request_id"]),
            decision=kind,  # type: ignore[arg-type]
            reason=f"test {kind} decision",
        )
        before = _snapshot_state(root)

        with pytest.raises(CliError) as excinfo:
            join_exact_occurrence(
                **_join_kwargs(root, spec, result, decision_id=decision["decision_id"])
            )
        assert excinfo.value.code == "decision_not_accepted", kind
        assert excinfo.value.extra["decision_kind"] == kind, kind
        _assert_no_join_mutation(root, before, receipt_path)


def test_join_refuses_superseded_accepted_decision_with_zero_mutation(tmp_path: Path) -> None:
    """An 'accepted' decision that is no longer the LATEST decision for the
    request (a newer decision superseded it) is stale and cannot authorize a
    claim."""
    from arnold_pipelines.megaplan.cloud.repair_requests import write_decision

    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)
    accepted_id = str(result["decision"]["decision_id"])
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    superseding = write_decision(
        queue_root,
        request_id=str(result["request"]["request_id"]),
        decision="superseded",
        reason="test supersession",
        # created_at has second granularity and iter_repair_decisions ties
        # on (created_at, decision_id): an explicit, clearly-later timestamp
        # makes the supersession deterministic regardless of hash order.
        created_at="2099-01-01T00:00:00Z",
    )
    assert superseding["decision_id"] != accepted_id

    # Passing the (now stale) accepted decision → decision_superseded.
    before = _snapshot_state(tmp_path)
    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(** _join_kwargs(tmp_path, spec, result, decision_id=accepted_id))
    assert excinfo.value.code == "decision_superseded"
    assert excinfo.value.extra["latest_decision_id"] == superseding["decision_id"]
    _assert_no_join_mutation(tmp_path, before, receipt_path)

    # Passing the superseding (non-accepted) decision → decision_not_accepted.
    before = _snapshot_state(tmp_path)
    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(
            **_join_kwargs(tmp_path, spec, result, decision_id=superseding["decision_id"])
        )
    assert excinfo.value.code == "decision_not_accepted"
    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_refuses_ambiguous_same_second_decisions_with_zero_mutation(tmp_path: Path) -> None:
    """T-0101h round-4 blocker 4: two decisions for the same request sharing
    the same second-resolution ``created_at`` have NO provable latest (the
    queue stores no monotonic sequence and sorts ties by content-hash
    decision id, which is not chronological evidence).  The join must refuse
    with a typed ``ambiguous_decision`` and zero mutation instead of guessing,
    so a same-second supersession can never authorize a stale acceptance."""
    from arnold_pipelines.megaplan.cloud.repair_requests import write_decision

    spec, plan, result = _setup(tmp_path)
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    accepted_id = str(result["decision"]["decision_id"])
    same_second = str(result["decision"]["created_at"])
    tie = write_decision(
        queue_root,
        request_id=str(result["request"]["request_id"]),
        decision="superseded",
        reason="same-second supersession",
        created_at=same_second,
    )
    assert tie["decision_id"] != accepted_id
    assert tie["created_at"] == same_second

    receipt_path = tmp_path / "occurrence-join-receipt.json"
    before = _snapshot_state(tmp_path)
    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(
            **_join_kwargs(tmp_path, spec, result, decision_id=accepted_id)
        )
    assert excinfo.value.code == "ambiguous_decision"
    assert excinfo.value.extra["request_id"] == str(result["request"]["request_id"])
    assert accepted_id in excinfo.value.extra["decision_ids"]
    assert tie["decision_id"] in excinfo.value.extra["decision_ids"]
    _assert_no_join_mutation(tmp_path, before, receipt_path)


def test_join_supersession_under_decision_lock_leaves_wbc_absent_and_custody_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-0101h round-5 blockers 1+2: the AUTHORITATIVE latest-decision check
    runs under the shared decision/admission lock BEFORE any lease/WBC
    effect.  A superseding decision that lands between the outer fast
    pre-check and the authoritative check is refused (``decision_superseded``)
    with ZERO mutation: the WBC database is NEVER created and the custody
    tree stays byte-identical — no lease acquire, no release append (the
    round-4 behavior of rolling back a just-acquired lease is gone)."""
    import hashlib
    import json as _json

    from arnold_pipelines.megaplan.chain import occurrence_join as oj

    spec, plan, result = _setup(tmp_path)
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    receipt_path = _evidence_receipt(tmp_path)
    requested = str(result["decision"]["decision_id"])
    request_id = str(result["request"]["request_id"])

    calls = {"n": 0}
    real_latest = oj._latest_decision_for_request
    superseding_path: Path | None = None

    def supersede_on_second_call(queue_root_path: Path, request_id_arg: str) -> dict[str, object] | None:
        nonlocal superseding_path
        calls["n"] += 1
        if calls["n"] == 2:
            # First call = outer fast pre-check (sees the accepted decision
            # only).  Second call = the AUTHORITATIVE check under the shared
            # decision lock.  A real write_decision cannot interleave here
            # (it would block on the very lock the join holds), so write the
            # record directly to simulate the decision landing in between —
            # the defensive check must still catch it, with zero mutation.
            identity = {
                "request_id": request_id_arg,
                "decision": "superseded",
                "reason": "appended between the pre-check and the authoritative check",
                "related_request_id": "",
                "created_at": "2099-01-01T00:00:01Z",
            }
            digest = hashlib.sha256(
                _json.dumps(
                    identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            record = {
                "schema_version": 1,
                "kind": "repair_request_decision",
                "decision_id": digest,
                "request_id": request_id_arg,
                "decision": "superseded",
                "reason": identity["reason"],
                "related_request_id": "",
                "created_at": identity["created_at"],
            }
            superseding_path = repair_requests.decisions_dir(queue_root_path) / (
                f"{identity['created_at'].replace(':', '').replace('-', '')}-{digest}.json"
            )
            superseding_path.write_text(_json.dumps(record, sort_keys=True), encoding="utf-8")
        return real_latest(queue_root_path, request_id_arg)

    monkeypatch.setattr(oj, "_latest_decision_for_request", supersede_on_second_call)

    before = _snapshot_state(tmp_path)
    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))
    assert excinfo.value.code == "decision_superseded"
    assert excinfo.value.extra["latest_decision_id"] != requested
    assert superseding_path is not None

    # Blockers 1+2 regression: no receipt, WBC database NEVER created, custody
    # tree byte-identical (no lease acquire, no release append).  The ONLY new
    # files are the test-hook's own superseding decision record; every other
    # plan-side byte is unchanged.
    assert not receipt_path.exists()
    wbc_path = plan / ".phase_wbc_attempts.sqlite3"
    assert not wbc_path.exists(), "refusal must not create the WBC database"
    lease_dir = plan / "custody" / "leases"
    assert not list(lease_dir.glob("*")), (
        "refusal must leave the custody tree byte-identical (no lease files)"
    )
    after = _snapshot_state(tmp_path)
    new_files = set(after) - set(before)
    assert new_files == {str(superseding_path)}, (
        f"refusal created unexpected files: {sorted(new_files)}"
    )
    for key, value in before.items():
        assert after[key] == value, f"refusal mutated {key}"


def test_concurrent_decision_write_during_admission_is_serialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-0101h round-5 blocker 1 race test: a concurrent ``write_decision``
    for the same request CANNOT land between the authoritative latest-decision
    check and the WBC admission commit.  A writer that attempts mid-admission
    blocks on the shared decision/admission flock until the admission
    commits; the claim is admitted against the then-latest decision and the
    superseding decision is recorded only AFTER — exactly one consistent
    winner, never a stale acceptance with the admission committed after the
    new decision."""
    import time

    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold_pipelines.megaplan.cloud.repair_requests import write_decision
    from arnold_pipelines.megaplan.chain import occurrence_join as oj

    spec, plan, result = _setup(tmp_path)
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    receipt_path = _evidence_receipt(tmp_path)
    request_id = str(result["request"]["request_id"])
    accepted_id = str(result["decision"]["decision_id"])
    attempt_id = occurrence_claim_attempt_id(plan, CLAIM_ID)

    join_holds_lock = threading.Event()
    writer_started = threading.Event()
    writer_done = threading.Event()
    errors: list[BaseException] = []

    calls = {"n": 0}
    real_verify = oj._verify_decision_still_latest

    def hooked_verify(
        queue_root_path: Path, request_id_arg: str, decision_id_arg: str
    ) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            # The authoritative check runs under the decision lock the join
            # now holds.  Start the writer here: it MUST block on the flock
            # until the admission commits.  If the lock were broken, the
            # writer would complete within the grace window and this
            # assertion fails (stale-acceptance bug detected).
            join_holds_lock.set()
            assert writer_started.wait(timeout=30), "writer never started"
            time.sleep(0.25)
            assert not writer_done.is_set(), (
                "writer completed while the join held the decision lock — a "
                "superseding decision landed between check and commit"
            )
        real_verify(queue_root_path, request_id_arg, decision_id_arg)

    monkeypatch.setattr(oj, "_verify_decision_still_latest", hooked_verify)

    def writer() -> None:
        try:
            write_decision(
                queue_root,
                request_id=request_id,
                decision="superseded",
                reason="concurrent supersession during admission",
                created_at="2099-01-01T00:00:01Z",
            )
        except BaseException as exc:  # pragma: no cover - failure reporting
            errors.append(exc)
        finally:
            writer_done.set()

    results: dict[str, object] = {}

    def joiner() -> None:
        try:
            results["payload"] = join_exact_occurrence(
                **_join_kwargs(tmp_path, spec, result)
            )
        except BaseException as exc:  # pragma: no cover - failure reporting
            errors.append(exc)

    t_join = threading.Thread(target=joiner, daemon=True)
    t_join.start()
    assert join_holds_lock.wait(timeout=30), "join never reached the authoritative check"
    t_writer = threading.Thread(target=writer, daemon=True)
    t_writer.start()
    writer_started.set()
    t_join.join(timeout=60)
    t_writer.join(timeout=60)
    assert not t_join.is_alive() and not t_writer.is_alive(), "race test deadlocked"
    assert errors == [], errors

    # Exactly one consistent winner: the admission committed with the
    # then-latest (accepted) decision, and the superseding decision was
    # recorded only AFTER the commit (the writer was provably blocked while
    # the join held the lock through the WBC append).
    payload = results["payload"]
    assert payload["status"] == "claimed"
    assert payload["decision_id"] == accepted_id
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["decision_id"] == accepted_id

    store = SqliteAttemptLedgerStore(plan / ".phase_wbc_attempts.sqlite3")
    events = store.read_events(attempt_id)
    assert len(events) == 1
    started_payload = events[0].payload if isinstance(events[0].payload, dict) else {}
    assert started_payload.get("decision_id") == accepted_id

    superseding = [
        record
        for record in repair_requests.iter_repair_decisions(queue_root)
        if record.get("request_id") == request_id
        and record.get("decision") == "superseded"
    ]
    assert len(superseding) == 1
    assert superseding[0]["decision_id"] != accepted_id
    assert writer_done.is_set()


def test_join_refuses_second_claim_for_same_occurrence_with_zero_mutation(tmp_path: Path) -> None:
    """A SECOND claim id for the SAME occurrence must be refused (occurrence
    already live-claimed): no lease, no reservation, no admission, no STARTED
    for the loser."""
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore

    spec, plan, result = _setup(tmp_path)
    first = join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))
    assert first["status"] == "claimed"

    loser_claim = "second-operator-claim"
    loser_attempt = occurrence_claim_attempt_id(plan, loser_claim)
    loser_lease = occurrence_join_lease_id(loser_claim)
    receipt_path = _evidence_receipt(tmp_path, "second-receipt.json")
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(
            **_join_kwargs(
                tmp_path,
                spec,
                result,
                claim_id=loser_claim,
                receipt_path=receipt_path,
            )
        )
    assert excinfo.value.code == "another_live_claim"

    # Zero mutation for the loser across EVERY plan-side file: no receipt,
    # no new/changed lease history/state (beyond the allowed occurrence lock,
    # which the winner already created), no WBC events, no reservation, no
    # admission row beyond the winner's.
    _assert_no_join_mutation(tmp_path, before, receipt_path)
    lease_store = open_lease_store(plan / "custody" / "leases")
    assert lease_store.current_lease(loser_lease) is None
    assert lease_store.load_history(loser_lease) == ()
    store = SqliteAttemptLedgerStore(plan / ".phase_wbc_attempts.sqlite3")
    assert store.read_events(loser_attempt) == []
    assert store.get_reservation(loser_attempt) is None
    rows = store.conn.execute(
        "SELECT attempt_id FROM occurrence_claim_admissions"
    ).fetchall()
    assert rows == [(first["attempt_id"],)]


def test_join_two_claims_same_occurrence_exactly_one_winner(tmp_path: Path) -> None:
    """Two concurrent claims for the SAME occurrence serialize on the
    occurrence-digest flock: EXACTLY ONE wins; the loser refuses with a typed
    error and zero mutation."""
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore

    spec, plan, result = _setup(tmp_path)
    barrier = threading.Barrier(2)
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    errors_lock = threading.Lock()

    def _join(claim_id: str) -> None:
        barrier.wait()
        try:
            payload = join_exact_occurrence(
                **_join_kwargs(
                    tmp_path,
                    spec,
                    result,
                    claim_id=claim_id,
                    receipt_path=_evidence_receipt(tmp_path, f"receipt-{claim_id}.json"),
                )
            )
            results.append({"claim_id": claim_id, "status": payload["status"]})
        except CliError as exc:
            with errors_lock:
                errors.append({"claim_id": claim_id, "code": exc.code})

    threads = [
        threading.Thread(target=_join, args=("claim-a",)),
        threading.Thread(target=_join, args=("claim-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Exactly one winner and exactly one typed loser.
    assert len(results) == 1, results
    assert len(errors) == 1, errors
    assert results[0]["status"] == "claimed"
    assert errors[0]["code"] == "another_live_claim", errors

    # The WBC ledger has exactly ONE occurrence-join STARTED (the winner's)
    # and the admission table holds exactly one row.
    from arnold.workflow.execution_attempt_ledger import AttemptEventType

    store = SqliteAttemptLedgerStore(plan / ".phase_wbc_attempts.sqlite3")
    live = [
        event
        for attempt_id in store.list_in_flight_attempts()
        for event in store.read_events(attempt_id)
        if event.event_type == AttemptEventType.STARTED
        and isinstance(event.payload, dict)
        and event.payload.get("kind") == "occurrence_join"
    ]
    assert len(live) == 1
    admission_rows = store.conn.execute(
        "SELECT attempt_id FROM occurrence_claim_admissions"
    ).fetchall()
    assert len(admission_rows) == 1
    assert admission_rows[0][0] == live[0].identity.attempt_id
    # The loser left no events and no reservation behind.
    loser_attempt = occurrence_claim_attempt_id(plan, str(errors[0]["claim_id"]))
    assert store.read_events(loser_attempt) == []
    assert store.get_reservation(loser_attempt) is None


# ── CLI surface ───────────────────────────────────────────────────────────


def _run_cli(root: Path, tmp_path: Path, result: dict[str, object], **overrides: object) -> tuple[int, str]:
    import argparse

    from arnold_pipelines.megaplan.chain import run_chain_cli

    spec = tmp_path / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    args = argparse.Namespace(
        chain_action="occurrence-join",
        spec=str(spec),
        project_dir=str(tmp_path),
        session=SESSION,
        occurrence=str(result["request"]["repair_identity_key"]),
        request=str(result["request"]["request_id"]),
        decision=str(result["decision"]["decision_id"]),
        claim=CLAIM_ID,
        reason="T-0101 operator join",
        actor="operator",
        receipt=str(_evidence_receipt(tmp_path, "cli-receipt.json")),
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return run_chain_cli(root, args)


def test_cli_occurrence_join_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec, plan, result = _setup(tmp_path)
    exit_code = _run_cli(tmp_path, tmp_path, result)
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["success"] is True
    assert payload["status"] == "claimed"
    assert payload["claim_id"] == CLAIM_ID
    assert _evidence_receipt(tmp_path, "cli-receipt.json").exists()


def test_cli_occurrence_join_refusal_returns_error_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec, plan, result = _setup(tmp_path)
    exit_code = _run_cli(tmp_path, tmp_path, result, actor="robot")
    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["success"] is False
    assert payload["error"] == "actor_forbidden"
    assert not _evidence_receipt(tmp_path, "cli-receipt.json").exists()


# ── Receipt hardening (T-0101h blocker 5): evidence-root constraint ───────


def test_join_refuses_receipt_outside_evidence_root_with_zero_mutation(tmp_path: Path) -> None:
    """A receipt path that resolves OUTSIDE <plan dir>/evidence/ is refused
    before any write, even when the join itself would succeed."""
    spec, plan, result = _setup(tmp_path)
    outside = tmp_path / "occurrence-join-receipt.json"
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result, receipt_path=outside))
    assert excinfo.value.code == "receipt_outside_evidence_root"
    assert str(excinfo.value.extra["receipt_path"]) == str(outside.resolve())
    assert "evidence" in excinfo.value.message

    _assert_no_join_mutation(tmp_path, before, outside)


def test_join_refuses_receipt_aliasing_protected_plan_side_files(tmp_path: Path) -> None:
    """--receipt must never alias protected plan-side state: state.json,
    chain.yaml, queue request/decision records, a plan marker or a manifest.
    Every alias resolves outside the evidence root and is refused with the
    protected file left byte-identical."""
    from arnold_pipelines.megaplan.chain.occurrence_join import EVIDENCE_DIRNAME

    spec, plan, result = _setup(tmp_path)
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    request_record = queue_root / "requests" / f"{result['request']['request_id']}.json"
    decision_record = Path(result["decision"]["_path"])
    assert decision_record.exists(), decision_record
    marker = plan / "marker.json"
    marker.write_text('{"marker": true}\n', encoding="utf-8")
    manifest = plan / "manifest.json"
    manifest.write_text('{"manifest": true}\n', encoding="utf-8")

    protected = [
        plan / "state.json",
        spec,  # chain.yaml
        request_record,
        decision_record,
        marker,
        manifest,
    ]
    assert all(p.exists() for p in protected), protected
    assert (plan / EVIDENCE_DIRNAME).resolve() not in [p.resolve() for p in protected]

    for path in protected:
        bytes_before = path.read_bytes()
        before = _snapshot_state(tmp_path)
        with pytest.raises(CliError) as excinfo:
            join_exact_occurrence(
                **_join_kwargs(tmp_path, spec, result, receipt_path=path)
            )
        assert excinfo.value.code == "receipt_outside_evidence_root", path
        assert path.read_bytes() == bytes_before, f"{path} must be byte-identical"
        _assert_no_join_mutation(tmp_path, before, tmp_path / "never-emitted-receipt.json")


def test_join_refuses_receipt_path_that_is_a_symlink_to_protected_state(tmp_path: Path) -> None:
    """A PRE-SEEDED symlink at the receipt path pointing at state.json is
    caught by path validation: resolve() follows the link, the alias lands
    outside the evidence root, and the join refuses with zero mutation."""
    spec, plan, result = _setup(tmp_path)
    state_path = plan / "state.json"
    state_before = state_path.read_bytes()
    alias = _evidence_receipt(tmp_path, "aliased-receipt.json")
    alias.parent.mkdir(parents=True, exist_ok=True)
    alias.symlink_to(state_path)
    before = _snapshot_state(tmp_path)

    with pytest.raises(CliError) as excinfo:
        join_exact_occurrence(**_join_kwargs(tmp_path, spec, result, receipt_path=alias))
    assert excinfo.value.code == "receipt_outside_evidence_root"
    assert state_path.read_bytes() == state_before
    # The pre-seeded symlink itself is untouched and no receipt was emitted.
    assert alias.is_symlink()
    assert os.readlink(alias) == str(state_path)
    _assert_no_join_mutation(tmp_path, before, tmp_path / "never-emitted-receipt.json")


# ── Receipt hardening: hardened atomic creation (O_EXCL|O_NOFOLLOW + fsync) ─


def test_join_pre_seeded_predictable_tmp_symlink_cannot_clobber_state(tmp_path: Path) -> None:
    """The old predictable ``<receipt>.tmp`` write is gone: a pre-seeded
    symlink at that name (pointing at state.json) is never opened, never
    followed, and state.json stays byte-identical while the join succeeds."""
    import os

    spec, plan, result = _setup(tmp_path)
    receipt_path = _evidence_receipt(tmp_path)
    state_path = plan / "state.json"
    state_before = state_path.read_bytes()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    old_tmp = receipt_path.with_name(receipt_path.name + ".tmp")
    old_tmp.symlink_to(state_path)

    payload = join_exact_occurrence(**_join_kwargs(tmp_path, spec, result))

    assert payload["status"] == "claimed"
    assert state_path.read_bytes() == state_before, "state.json must be byte-identical"
    # The real receipt landed at the evidence-root path...
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["claim_id"] == CLAIM_ID
    # ...and the predictable tmp symlink was NEVER written through (it still
    # points at state.json and carries no receipt bytes).
    assert old_tmp.is_symlink()
    assert os.readlink(old_tmp) == str(state_path)
    assert json.loads(state_path.read_text(encoding="utf-8"))["current_state"] == "blocked"
    # No stray temp files remain after the hardened write (the pre-seeded
    # symlink we planted is the ONLY .tmp-named entry).
    leftovers = [
        p.name for p in receipt_path.parent.iterdir()
        if ".tmp" in p.name and p.name != old_tmp.name
    ]
    assert leftovers == [], leftovers


def test_receipt_write_replaces_pre_seeded_final_symlink_without_following(tmp_path: Path) -> None:
    """Unit-level: a pre-seeded symlink AT the final receipt path is replaced
    by os.replace (the directory entry is swapped), never followed, so the
    symlink target stays byte-identical."""
    import os

    from arnold_pipelines.megaplan.chain.occurrence_join import _write_receipt_durably

    plan = _plan_dir(tmp_path)
    evidence = plan / "evidence"
    evidence.mkdir(parents=True)
    state = plan / "state.json"
    state.write_text("PROTECTED", encoding="utf-8")
    receipt = evidence / "receipt.json"
    receipt.symlink_to(state)

    _write_receipt_durably(receipt, {"k": "v"})

    assert state.read_text(encoding="utf-8") == "PROTECTED"
    assert not receipt.is_symlink()
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"k": "v"}
    assert os.path.lexists(receipt)


def test_receipt_write_fsyncs_file_and_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The hardened write fsyncs the temp file BEFORE the rename and the
    parent directory AFTER the rename (exactly two fsync calls)."""
    import os

    from arnold_pipelines.megaplan.chain.occurrence_join import _write_receipt_durably

    calls: list[int] = []
    real_fsync = os.fsync

    def spy_fsync(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    evidence = _plan_dir(tmp_path) / "evidence"
    receipt = evidence / "fsync-receipt.json"

    _write_receipt_durably(receipt, {"k": "v"})

    assert len(calls) == 2, f"expected file fsync + directory fsync, saw {len(calls)}"
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"k": "v"}
    # No predictable .tmp residue.
    assert [p.name for p in evidence.iterdir()] == ["fsync-receipt.json"]


def test_receipt_validation_rejects_exact_protected_alias(tmp_path: Path) -> None:
    """Unit-level defense-in-depth: even a protected path that resolves
    INSIDE the evidence root is refused with receipt_aliases_protected_state
    (the explicit equality check beyond root containment)."""
    from arnold_pipelines.megaplan.chain.occurrence_join import (
        EVIDENCE_DIRNAME,
        _validate_receipt_destination,
    )

    plan = _plan_dir(tmp_path)
    evidence = plan / EVIDENCE_DIRNAME
    evidence.mkdir(parents=True)
    protected = evidence / "state.json"  # contrived: protected file under evidence

    with pytest.raises(CliError) as excinfo:
        _validate_receipt_destination(
            protected, plan_dir=plan, protected_paths=[protected]
        )
    assert excinfo.value.code == "receipt_aliases_protected_state"
    assert str(excinfo.value.extra["protected_path"]) == str(protected)
