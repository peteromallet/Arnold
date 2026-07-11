"""Immutable failure-triggered repair request queue markers."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.cloud.repair_lock import (
    RepairLockResult,
    acquire_repair_lock,
    inspect_repair_lock,
    release_repair_lock,
)
from arnold_pipelines.megaplan.cloud.repair_recurrence import PROBLEM_SIGNATURE_FIELDS

QUEUE_DIR_NAME = "repair-queue"
REQUESTS_DIR_NAME = "requests"
DECISIONS_DIR_NAME = "decisions"
ACTIVE_CLAIMS_DIR_NAME = "active-claims"
CURRENT_SCHEMA_VERSION = 1

DecisionKind = Literal["accepted", "coalesced", "stale", "superseded", "malformed", "dispatched", "migrated"]
ActiveRepairClaimStatus = Literal["claimed", "already_claimed", "busy", "stale"]


@dataclass(frozen=True)
class ActiveRepairClaimResult:
    status: ActiveRepairClaimStatus
    lock_dir: Path
    owner: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None

    @property
    def claimed(self) -> bool:
        return self.status == "claimed"

    @property
    def already_claimed(self) -> bool:
        return self.status == "already_claimed"

    @property
    def busy(self) -> bool:
        return self.status == "busy"

    @property
    def stale(self) -> bool:
        return self.status == "stale"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_queue_root(queue_root: str | Path) -> Path:
    """Return the canonical central repair queue root or reject it.

    Queue custody is intentionally structural and explicit: the only accepted
    shape is an absolute ``<workspace>/.megaplan/repair-queue`` path.  A path
    beneath ``.megaplan/plans`` is never central, even if a nested directory is
    named ``.megaplan/repair-queue``.
    """

    raw_root = Path(queue_root)
    if not raw_root.is_absolute():
        raise ValueError("repair queue root must be an absolute path")
    root = raw_root.resolve(strict=False)
    parts = root.parts
    if any(
        part == ".megaplan" and index + 1 < len(parts) and parts[index + 1] == "plans"
        for index, part in enumerate(parts)
    ):
        raise ValueError("repair queue root cannot be inside .megaplan/plans")
    if root.name != QUEUE_DIR_NAME or root.parent.name != ".megaplan":
        raise ValueError(
            "repair queue root must be the central <workspace>/.megaplan/repair-queue directory"
        )
    return root


def requests_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / REQUESTS_DIR_NAME


def decisions_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / DECISIONS_DIR_NAME


def active_claims_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / ACTIVE_CLAIMS_DIR_NAME


def migrate_stranded_split_queue(
    queue_root: str | Path,
    *,
    max_requests: int = 100,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Copy stranded split-queue request markers into the central queue.

    The legacy split queue lives under ``<workspace>/.megaplan/cloud-sessions``.
    Migration is intentionally bounded, preserves the original files in place,
    and writes a central decision record for every examined request marker.
    """

    if max_requests <= 0:
        raise ValueError("max_requests must be positive")

    queue_root = validate_queue_root(queue_root)
    legacy_root = queue_root.parent / "cloud-sessions" / QUEUE_DIR_NAME
    legacy_request_dir = legacy_root / REQUESTS_DIR_NAME
    result = {
        "legacy_root": str(legacy_root),
        "processed": 0,
        "migrated": 0,
        "coalesced": 0,
        "malformed": 0,
        "truncated": False,
        "decisions": [],
    }
    if not legacy_request_dir.exists():
        return result

    request_paths = sorted(legacy_request_dir.glob("*.json"), key=lambda item: item.name)
    for path in request_paths[:max_requests]:
        result["processed"] += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            result["malformed"] += 1
            result["decisions"].append(record_malformed_file(queue_root, path, str(exc)))
            continue
        if not isinstance(payload, dict):
            result["malformed"] += 1
            result["decisions"].append(
                record_malformed_file(queue_root, path, "request marker is not a JSON object")
            )
            continue
        request_id = str(payload.get("request_id") or "").strip()
        if payload.get("kind") != "repair_request" or not request_id:
            result["malformed"] += 1
            result["decisions"].append(
                record_malformed_file(queue_root, path, "request marker has invalid shape")
            )
            continue

        central_request_path = requests_dir(queue_root) / f"{request_id}.json"
        copied = _write_once_json(central_request_path, payload)
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="migrated" if copied else "coalesced",
            reason=(
                f"migrated stranded split-queue request from {path}"
                if copied
                else f"stranded split-queue request already present in central queue: {path}"
            ),
            related_request_id=request_id if not copied else "",
            created_at=created_at,
        )
        result["decisions"].append(decision)
        if copied:
            result["migrated"] += 1
        else:
            result["coalesced"] += 1

    result["truncated"] = len(request_paths) > max_requests
    return result


def active_repair_claim_lock_dir(queue_dir: str | Path, blocker_id: str) -> Path:
    """Return the blocker-scoped active repair claim lock directory."""

    normalized = _normalize_claim_identity(blocker_id, "blocker_id")
    return active_claims_dir(queue_dir) / f"{_claim_path_token(normalized)}.lock"


def normalize_problem_signature(problem_signature: Mapping[str, Any]) -> dict[str, str]:
    """Return only the canonical signature fields, normalized for identity."""

    return {
        field: str(problem_signature.get(field) or "").strip()
        for field in PROBLEM_SIGNATURE_FIELDS
    }


def problem_signature_key(problem_signature: Mapping[str, Any]) -> str:
    normalized = normalize_problem_signature(problem_signature)
    return _sha256_json([normalized[field] for field in PROBLEM_SIGNATURE_FIELDS])


def redacted_hint_hash(root_cause_hint: Any) -> str:
    """Hash the redacted root-cause hint without exposing the raw hint."""

    redacted = redact_payload(root_cause_hint)
    return _sha256_json(redacted)


def request_id_for(
    *,
    session: str,
    problem_signature: Mapping[str, Any],
    root_cause_hint: Any = "",
) -> str:
    """Return a stable request id unaffected by timestamps or raw hint text."""

    return _sha256_json(
        {
            "session": str(session or "").strip(),
            "problem_signature": normalize_problem_signature(problem_signature),
            "root_cause_hint_hash": redacted_hint_hash(root_cause_hint),
        }
    )


def enqueue_repair_request(
    *,
    queue_root: str | Path,
    session: str,
    problem_signature: Mapping[str, Any],
    root_cause_hint: Any = "",
    source: str,
    marker_dir: str | Path | None = None,
    target: Mapping[str, Any] | None = None,
    workspace: str | Path | None = None,
    run_kind: str = "",
    created_at: str | None = None,
    stale_reason: str = "",
    superseded_by: str = "",
) -> dict[str, Any]:
    """Write a request marker once, recording any rejection/coalescing separately."""

    queue_root = validate_queue_root(queue_root)
    normalized_signature = normalize_problem_signature(problem_signature)
    hint_hash = redacted_hint_hash(root_cause_hint)
    request_id = request_id_for(
        session=session,
        problem_signature=normalized_signature,
        root_cause_hint=root_cause_hint,
    )
    request_path = requests_dir(queue_root) / f"{request_id}.json"
    record = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": "repair_request",
        "request_id": request_id,
        "created_at": created_at or utc_now(),
        "source": str(source or "").strip(),
        "session": str(session or "").strip(),
        "workspace": str(workspace or ""),
        "run_kind": str(run_kind or "").strip(),
        "marker_dir": str(Path(marker_dir)) if marker_dir is not None else "",
        "queue_dir": str(queue_root),
        "target": _stable_mapping(target or {}),
        "problem_signature": normalized_signature,
        "problem_signature_key": problem_signature_key(normalized_signature),
        "root_cause_hint_hash": hint_hash,
        "root_cause_hint_hash_algorithm": "sha256(redact_payload(root_cause_hint))",
    }

    if stale_reason:
        _write_once_json(request_path, record)
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="stale",
            reason=stale_reason,
            related_request_id="",
        )
        return {"status": "stale", "request": record, "path": str(request_path), "decision": decision}
    if superseded_by:
        _write_once_json(request_path, record)
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="superseded",
            reason="superseded by newer live repair target",
            related_request_id=superseded_by,
        )
        return {"status": "superseded", "request": record, "path": str(request_path), "decision": decision}

    existing = find_pending_by_signature(queue_root, normalized_signature)
    if existing is not None and existing["request_id"] != request_id:
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="coalesced",
            reason="matching problem signature already queued",
            related_request_id=existing["request_id"],
        )
        return {"status": "coalesced", "request": record, "path": str(request_path), "decision": decision}

    wrote = _write_once_json(request_path, record)
    if not wrote:
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="coalesced",
            reason="request marker already exists",
            related_request_id=request_id,
        )
        return {"status": "coalesced", "request": record, "path": str(request_path), "decision": decision}

    decision = write_decision(
        queue_root,
        request_id=request_id,
        decision="accepted",
        reason="queued",
        related_request_id="",
    )
    return {"status": "queued", "request": record, "path": str(request_path), "decision": decision}


def enqueue_human_gate_repair_request(
    *,
    queue_root: str | Path,
    marker_dir: str | Path,
    session: str,
    workspace: str | Path,
    run_kind: str,
    plan_name: str,
    pipeline_name: str,
    artifact_stage: str,
    step_name: str,
    prompt: str,
) -> dict[str, Any] | None:
    """Megaplan-owned hook used by the neutral human-gate step."""

    from arnold_pipelines.megaplan.cloud.feature_flags import repair_request_queue_enabled

    if not repair_request_queue_enabled():
        return None
    return enqueue_repair_request(
        queue_root=queue_root,
        marker_dir=marker_dir,
        session=session,
        source="human_gate",
        workspace=workspace,
        run_kind=run_kind,
        target={
            "plan_dir": str(marker_dir),
            "plan_name": plan_name,
            "pipeline_name": pipeline_name,
            "workspace_path": str(workspace),
        },
        problem_signature={
            "failure_kind": "human_gate",
            "current_state": pipeline_name,
            "phase_or_step": artifact_stage,
            "milestone_or_plan": step_name,
            "gate_recommendation": "",
            "blocked_task_id": "",
        },
        root_cause_hint=prompt,
    )


def iter_repair_requests(
    queue_root: str | Path,
    *,
    include_malformed: bool = False,
) -> list[dict[str, Any]]:
    """Return request records in deterministic order, tolerating bad files."""

    queue_root = validate_queue_root(queue_root)
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for path in sorted(requests_dir(queue_root).glob("*.json"), key=lambda item: item.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            malformed.append(_malformed_record(path, exc))
            continue
        if not isinstance(payload, dict):
            malformed.append(_malformed_record(path, ValueError("request marker is not a JSON object")))
            continue
        required = {"schema_version", "kind", "request_id", "problem_signature"}
        if not required.issubset(payload) or payload.get("kind") != "repair_request":
            malformed.append(_malformed_record(path, ValueError("request marker has invalid shape")))
            continue
        payload = dict(payload)
        payload["_path"] = str(path)
        records.append(payload)
    records.sort(key=_request_sort_key)
    if include_malformed:
        records.extend(sorted(malformed, key=lambda item: item["path"]))
    return records


def iter_repair_decisions(
    queue_root: str | Path,
    *,
    include_malformed: bool = False,
) -> list[dict[str, Any]]:
    """Return immutable decision records in deterministic order."""

    queue_root = validate_queue_root(queue_root)
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for path in sorted(decisions_dir(queue_root).glob("*.json"), key=lambda item: item.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            malformed.append(_malformed_decision(path, exc))
            continue
        if not isinstance(payload, dict):
            malformed.append(_malformed_decision(path, ValueError("decision record is not a JSON object")))
            continue
        required = {"schema_version", "kind", "decision_id", "request_id", "decision", "created_at"}
        if not required.issubset(payload) or payload.get("kind") != "repair_request_decision":
            malformed.append(_malformed_decision(path, ValueError("decision record has invalid shape")))
            continue
        payload = dict(payload)
        payload["_path"] = str(path)
        records.append(payload)
    records.sort(key=_decision_sort_key)
    if include_malformed:
        records.extend(sorted(malformed, key=lambda item: item["path"]))
    return records


def find_pending_by_signature(
    queue_dir: str | Path,
    problem_signature: Mapping[str, Any],
) -> dict[str, Any] | None:
    key = problem_signature_key(problem_signature)
    decided = _decided_request_ids(queue_dir)
    for record in iter_repair_requests(queue_dir):
        if record.get("request_id") in decided:
            continue
        if record.get("problem_signature_key") == key:
            return record
    return None


def write_decision(
    queue_dir: str | Path,
    *,
    request_id: str,
    decision: DecisionKind,
    reason: str,
    related_request_id: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Write an immutable decision record separate from request markers."""

    when = created_at or utc_now()
    record = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": "repair_request_decision",
        "decision_id": _sha256_json(
            {
                "request_id": request_id,
                "decision": decision,
                "reason": reason,
                "related_request_id": related_request_id,
                "created_at": when,
            }
        ),
        "request_id": str(request_id or "").strip(),
        "decision": decision,
        "reason": str(reason or "").strip(),
        "related_request_id": str(related_request_id or "").strip(),
        "created_at": when,
    }
    path = decisions_dir(queue_dir) / f"{when.replace(':', '').replace('-', '')}-{record['decision_id']}.json"
    _write_once_json(path, record)
    return {**record, "_path": str(path)}


def claim_active_repair_request(
    queue_dir: str | Path,
    *,
    blocker_id: str,
    request_id: str,
    actor: str,
    session: str,
    blocker_fingerprint: Mapping[str, Any] | None = None,
    pid: int | None = None,
    command: str | None = None,
    started_at: str | None = None,
    cwd: str | None = None,
    timeout_seconds: float | None = None,
    hostname: str | None = None,
    now: datetime | None = None,
    is_pid_live: Any | None = None,
    extra: Mapping[str, Any] | None = None,
) -> ActiveRepairClaimResult:
    """Atomically claim active repair ownership for one blocker.

    The mkdir lock is keyed by ``blocker_id`` so only one request can actively
    own the blocker at a time. The owner payload also records ``request_id`` so
    same-request contenders get a typed ``already_claimed`` result, while a
    different active request is reported as ``busy``.
    """

    normalized_blocker_id = _normalize_claim_identity(blocker_id, "blocker_id")
    normalized_request_id = _normalize_claim_identity(request_id, "request_id")
    normalized_actor = _normalize_claim_identity(actor, "actor")
    normalized_session = _normalize_claim_identity(session, "session")
    claim_lock_dir = active_repair_claim_lock_dir(queue_dir, normalized_blocker_id)
    metadata = {
        "kind": "active_repair_request_claim",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "actor": normalized_actor,
        "session": normalized_session,
        "request_id": normalized_request_id,
        "blocker_id": normalized_blocker_id,
        "blocker_fingerprint": dict(blocker_fingerprint or {}),
    }
    if extra:
        metadata.update(dict(extra))

    result = acquire_repair_lock(
        claim_lock_dir,
        session=normalized_session,
        target_id=normalized_blocker_id,
        pid=pid,
        command=command,
        started_at=started_at,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        hostname=hostname or _hostname(),
        extra=metadata,
        now=now,
        is_pid_live=is_pid_live,
    )
    result = _settle_owner_write_race(
        result,
        now=now,
        is_pid_live=is_pid_live,
    )
    # A stale claim is evidence for the operator/repair loop, not authority to
    # delete another worker's lock and seize it.  PID reuse and delayed writes
    # make automatic reclamation unsafe; a subsequent explicit recovery owns
    # any mutation after evaluating the captured evidence.
    return _claim_result_from_lock(
        result,
        blocker_id=normalized_blocker_id,
        request_id=normalized_request_id,
    )


def release_active_repair_request_claim(
    queue_dir: str | Path,
    *,
    blocker_id: str,
    owner: Mapping[str, Any] | None = None,
    expected_pid: int | None = None,
) -> bool:
    """Release an active repair claim if the owner expectation matches."""

    return release_repair_lock(
        active_repair_claim_lock_dir(queue_dir, blocker_id),
        owner=owner,
        expected_pid=expected_pid,
    )


def record_malformed_file(queue_dir: str | Path, path: str | Path, reason: str) -> dict[str, Any]:
    return write_decision(
        queue_dir,
        request_id=_sha256_json(str(Path(path))),
        decision="malformed",
        reason=reason,
        related_request_id=str(path),
    )


def _decided_request_ids(queue_dir: str | Path) -> set[str]:
    decided: set[str] = set()
    for path in sorted(decisions_dir(queue_dir).glob("*.json"), key=lambda item: item.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        decision = payload.get("decision")
        if decision in {"stale", "superseded", "dispatched"}:
            request_id = payload.get("request_id")
            if isinstance(request_id, str) and request_id:
                decided.add(request_id)
    return decided


def _write_once_json(path: Path, payload: Mapping[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".claim")
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.close(fd)
        if path.exists():
            return False
        repair_contract.atomic_write_json(path, payload)
        return True
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _claim_result_from_lock(
    result: RepairLockResult,
    *,
    blocker_id: str,
    request_id: str,
) -> ActiveRepairClaimResult:
    if result.acquired:
        return ActiveRepairClaimResult(status="claimed", lock_dir=result.lock_dir, owner=result.owner)
    if result.stale:
        return ActiveRepairClaimResult(
            status="stale",
            lock_dir=result.lock_dir,
            owner=result.owner,
            evidence={
                "kind": "active_repair_claim_stale",
                "blocker_id": blocker_id,
                "request_id": request_id,
                "lock_status": result.status,
                "stale_evidence": result.stale_evidence or {},
                "owner": result.owner or {},
            },
        )

    owner = result.owner or {}
    owner_request_id = str(owner.get("request_id") or "")
    status: ActiveRepairClaimStatus = "already_claimed" if owner_request_id == request_id else "busy"
    return ActiveRepairClaimResult(
        status=status,
        lock_dir=result.lock_dir,
        owner=result.owner,
        evidence={
            "kind": "active_repair_claim_contention",
            "status": status,
            "blocker_id": blocker_id,
            "request_id": request_id,
            "owner_request_id": owner_request_id,
            "owner_blocker_id": str(owner.get("blocker_id") or ""),
            "owner_actor": str(owner.get("actor") or ""),
            "owner_session": str(owner.get("session") or ""),
            "owner_pid": owner.get("pid"),
            "owner": owner,
        },
    )


def _settle_owner_write_race(
    result: RepairLockResult,
    *,
    now: datetime | None,
    is_pid_live: Any | None,
) -> RepairLockResult:
    evidence = result.stale_evidence or {}
    reasons = evidence.get("reasons")
    if not result.stale or reasons != ["owner_metadata_missing"]:
        return result
    for _ in range(20):
        time.sleep(0.01)
        inspected = inspect_repair_lock(result.lock_dir, now=now, is_pid_live=is_pid_live)
        inspected_reasons = (inspected.stale_evidence or {}).get("reasons")
        if inspected.status != "stale" or inspected_reasons != ["owner_metadata_missing"]:
            return inspected
    return result


def _reclaim_stale_claim(
    result: RepairLockResult,
    *,
    claim_lock_dir: Path,
    session: str,
    blocker_id: str,
    pid: int | None,
    command: str | None,
    started_at: str | None,
    cwd: str | None,
    timeout_seconds: float | None,
    hostname: str | None,
    extra: Mapping[str, Any] | None,
    now: datetime | None,
    is_pid_live: Any | None,
) -> RepairLockResult:
    if not result.stale:
        return result
    owner = result.owner if isinstance(result.owner, dict) else None
    expected_pid = owner.get("pid") if isinstance(owner, dict) and isinstance(owner.get("pid"), int) else None
    if not release_repair_lock(claim_lock_dir, owner=owner, expected_pid=expected_pid):
        return result
    reacquired = acquire_repair_lock(
        claim_lock_dir,
        session=session,
        target_id=blocker_id,
        pid=pid,
        command=command,
        started_at=started_at,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        hostname=hostname or _hostname(),
        extra=extra,
        now=now,
        is_pid_live=is_pid_live,
    )
    return _settle_owner_write_race(reacquired, now=now, is_pid_live=is_pid_live)


def _normalize_claim_identity(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _claim_path_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return ""


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value[key] for key in sorted(value)}


def _request_sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("created_at") or ""), str(record.get("request_id") or ""))


def _decision_sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("created_at") or ""), str(record.get("decision_id") or ""))


def _malformed_record(path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "kind": "malformed_repair_request",
        "path": str(path),
        "reason": str(exc),
    }


def _malformed_decision(path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "kind": "malformed_repair_decision",
        "path": str(path),
        "reason": str(exc),
    }


__all__ = [
    "ACTIVE_CLAIMS_DIR_NAME",
    "PROBLEM_SIGNATURE_FIELDS",
    "QUEUE_DIR_NAME",
    "ActiveRepairClaimResult",
    "ActiveRepairClaimStatus",
    "DecisionKind",
    "active_claims_dir",
    "active_repair_claim_lock_dir",
    "claim_active_repair_request",
    "enqueue_human_gate_repair_request",
    "enqueue_repair_request",
    "find_pending_by_signature",
    "iter_repair_decisions",
    "iter_repair_requests",
    "migrate_stranded_split_queue",
    "normalize_problem_signature",
    "problem_signature_key",
    "record_malformed_file",
    "redacted_hint_hash",
    "release_active_repair_request_claim",
    "request_id_for",
    "validate_queue_root",
    "write_decision",
]
