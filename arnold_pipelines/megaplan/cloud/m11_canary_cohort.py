"""Bounded coordinator for the twenty-sample M11 live-canary cohort."""

from __future__ import annotations

import fcntl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.m11_live_canary import (
    CANARY_BASE,
    CanarySafetyError,
    _atomic_json,
    _load_hashed_json,
    _occurrence,
    run_isolated_relaunch,
    validate_canary_root,
)
from arnold_pipelines.megaplan.custody.contracts import RepairOccurrenceKey
from arnold_pipelines.megaplan.custody.lease_store import open_lease_store
from arnold_pipelines.megaplan.custody.outbox import (
    OutboxRecord,
    OutboxRecordStatus,
    OutboxRecordType,
    open_outbox,
)
from arnold_pipelines.megaplan.wbc_adapter import WbcAttemptRef, WbcBoundaryEvidence
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence, Decision
from arnold_pipelines.megaplan.cloud.repair_revalidation import (
    LatencyLedgerRow,
    generate_latency_ledger,
)

COHORT_SIZE = 20
SCHEMA = "arnold.megaplan.m11_canary_cohort.v1"


def provision_private_authority(
    *,
    root: str | Path,
    occurrence_payload: Mapping[str, Any],
    index: int,
    base_root: str | Path = CANARY_BASE,
) -> dict[str, Any]:
    """Provision one isolated canonical RA/Custody/WBC authority fixture."""

    private_root = validate_canary_root(root, base_root=base_root)
    authority_root = private_root / "authority"
    authority_root.mkdir(parents=True, exist_ok=True)
    occurrence = _occurrence(occurrence_payload)
    grant = CapabilityGrant(
        grant_id=f"canary-grant-{index}",
        run_id=f"canary-run-{index}",
        run_revision=f"canary-revision-{index}",
        coordinator_attempt_id=f"canary-coordinator-{index}",
        fence_token=index,
        subject_ids=(occurrence.target.subject_id,),
        capabilities=("repair",),
        evidence_ids=(f"canary-evidence-{index}",),
    )
    fence = CoordinatorFence(
        grant.run_id,
        grant.run_revision,
        grant.coordinator_attempt_id,
        grant.fence_token,
    )
    decision = Decision(
        decision_id=f"canary-decision-{index}",
        run_id=grant.run_id,
        run_revision=grant.run_revision,
        subject_id=occurrence.target.subject_id,
        attempt_id=occurrence.target.attempt,
        grant_id=grant.grant_id,
        coordinator_attempt_id=grant.coordinator_attempt_id,
        fence_token=fence.token,
        claim_id=f"canary-claim-{index}",
        outcome="accepted",
        evidence_ids=(f"canary-evidence-{index}",),
        idempotency_key=f"canary-decision-{index}",
        payload={},
    )
    grant_path = authority_root / "capability-grant.json"
    fence_path = authority_root / "coordinator-fence.json"
    decision_path = authority_root / "decision.json"
    _atomic_json(grant_path, grant.to_dict(), exclusive=True)
    _atomic_json(fence_path, fence.to_dict(), exclusive=True)
    _atomic_json(decision_path, decision.to_dict(), exclusive=True)
    attempt_ref = f"canary-wbc-{index}"
    wbc_version = f"wbc-v{index}"
    repair_key = RepairOccurrenceKey(
        target=occurrence.target,
        run_id=grant.run_id,
        run_revision=grant.run_revision,
        coordinator_attempt_id=grant.coordinator_attempt_id,
        fence_token=fence.token,
        wbc_attempt_reference=attempt_ref,
    )
    lease_id = f"canary-lease-{index}"
    owner = (f"canary-host-{index}", str(10_000 + index), f"canary-boot-{index}")
    lease_dir = authority_root / "custody" / "leases"
    outbox_dir = authority_root / "custody" / "outbox"
    open_lease_store(lease_dir).acquire(
        lease_id=lease_id,
        owner_host=owner[0],
        owner_pid=owner[1],
        owner_boot_id=owner[2],
        run_authority_grant_id=grant.grant_id,
        coordinator_fence_token=fence.token,
        wbc_attempt_reference=attempt_ref,
        occurrence_digest=repair_key.occurrence_digest,
        custody_epoch=1,
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    open_outbox(outbox_dir).write_record(
        OutboxRecord(
            outbox_id=f"canary-outbox-{index}",
            lease_id=lease_id,
            record_type=OutboxRecordType.CROSS_OWNER_ATTEMPT,
            status=OutboxRecordStatus.PENDING,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            idempotency_key=f"canary-outbox-{index}",
            wbc_attempt_reference=attempt_ref,
            run_authority_grant_id=grant.grant_id,
            coordinator_fence_token=fence.token,
            occurrence_digest=repair_key.occurrence_digest,
            custody_epoch=1,
            payload={"schema_version": wbc_version},
        )
    )
    wbc_path = authority_root / "wbc-boundary-evidence.json"
    _atomic_json(
        wbc_path,
        WbcBoundaryEvidence.verified(
            WbcAttemptRef.exact(attempt_ref, wbc_version, kind="repair"),
            start_event_digest=f"sha256:start-{index}",
            terminal_event_digest=f"sha256:terminal-{index}",
            last_sequence=2,
            source_cursor_digest=f"sha256:cursor-{index}",
        ).to_dict(),
        exclusive=True,
    )
    return {
        "capability_grant_path": str(grant_path),
        "coordinator_fence_path": str(fence_path),
        "decision_path": str(decision_path),
        "run_authority_grant_id": grant.grant_id,
        "coordinator_fence_token": fence.token,
        "custody_lease_id": lease_id,
        "custody_epoch": 1,
        "wbc_attempt_reference": attempt_ref,
        "owner_host": owner[0],
        "owner_pid": owner[1],
        "owner_boot_id": owner[2],
        "required_capability": "repair",
        "required_wbc_evidence_version": wbc_version,
        "wbc_evidence_path": str(wbc_path),
        "lease_store_dir": str(lease_dir),
        "outbox_dir": str(outbox_dir),
    }


def run_singleton_mutation(
    config: Mapping[str, Any],
    *,
    base_root: str | Path = CANARY_BASE,
    runner: Callable[..., dict[str, Any]] = run_isolated_relaunch,
) -> dict[str, Any]:
    """Run one mutation while holding the cohort-wide singleton lock."""

    base = Path(base_root).resolve(strict=False)
    root = validate_canary_root(config["root"], base_root=base)
    base.mkdir(parents=True, exist_ok=True)
    lock_path = base / ".cohort-mutation.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CanarySafetyError("another cohort repair mutation is active") from exc
        return runner(base_root=base, **{**dict(config), "root": root})


def fanout_delayed_verifiers(
    jobs: Sequence[Callable[[], dict[str, Any]]],
    *,
    max_workers: int = COHORT_SIZE,
) -> list[dict[str, Any]]:
    """Run read-only delayed verifier jobs concurrently."""

    if len(jobs) > COHORT_SIZE:
        raise CanarySafetyError("verifier fanout exceeds bounded cohort size")
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(jobs)))) as pool:
        return list(pool.map(lambda job: job(), jobs))


def aggregate_cohort(
    roots: Sequence[str | Path],
    *,
    destination: str | Path,
    base_root: str | Path = CANARY_BASE,
) -> dict[str, Any]:
    """Aggregate exactly twenty isolated one-row manifests into one p95 ledger."""

    if len(roots) != COHORT_SIZE:
        raise CanarySafetyError(f"cohort requires exactly {COHORT_SIZE} roots")
    base = Path(base_root).resolve(strict=False)
    normalized = [validate_canary_root(root, base_root=base) for root in roots]
    if len(set(normalized)) != COHORT_SIZE:
        raise CanarySafetyError("cohort roots must be distinct")
    rows: list[LatencyLedgerRow] = []
    fingerprints: set[str] = set()
    for root in normalized:
        manifest = _load_hashed_json(root / "manifest.json")
        ledger = _load_hashed_json(root / "latency-ledger.json")
        fingerprint = str(manifest.get("occurrence_fingerprint") or "")
        ledger_rows = ledger.get("latency_ledger_rows")
        if (
            manifest.get("complete") is not True
            or not fingerprint
            or not isinstance(ledger_rows, list)
            or len(ledger_rows) != 1
            or ledger_rows[0].get("occurrence_fingerprint") != fingerprint
        ):
            raise CanarySafetyError(f"incomplete cohort sample: {root}")
        if fingerprint in fingerprints:
            raise CanarySafetyError("cohort occurrence fingerprints must be distinct")
        fingerprints.add(fingerprint)
        rows.append(LatencyLedgerRow(**ledger_rows[0]))
    ledger_payload = generate_latency_ledger(rows=rows).to_dict()
    destination_path = Path(destination).resolve(strict=False)
    if destination_path.parent != base:
        raise CanarySafetyError("cohort aggregate must stay directly below canary base")
    result = {
        "schema": SCHEMA,
        "sample_roots": [str(root) for root in normalized],
        "occurrence_fingerprints": sorted(fingerprints),
        "ledger": ledger_payload,
        "complete": ledger_payload["sample_count"] == COHORT_SIZE,
        "slo_met": ledger_payload["slo_met"],
    }
    from arnold_pipelines.megaplan.cloud.m11_live_canary import _digest

    result["content_sha256"] = _digest(result)
    _atomic_json(destination_path, result, exclusive=True)
    return result
