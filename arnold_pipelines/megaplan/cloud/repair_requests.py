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
    owner_metadata_path,
)
from arnold_pipelines.megaplan.cloud.repair_recurrence import (
    ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS,
    EXTENDED_PROBLEM_SIGNATURE_FIELDS,
    PROBLEM_SIGNATURE_FIELDS,
    build_acceptance_predicate_signature,
)

QUEUE_DIR_NAME = "repair-queue"
REQUESTS_DIR_NAME = "requests"
DECISIONS_DIR_NAME = "decisions"
ATTEMPTS_DIR_NAME = "attempts"
ACTIVE_CLAIMS_DIR_NAME = "active-claims"
CURRENT_SCHEMA_VERSION = 1

DecisionKind = Literal[
    "accepted",
    "coalesced",
    "stale",
    "superseded",
    "malformed",
    "dispatched",
    "claim_retry",
    "claim_alert",
]
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


def repair_queue_dir(marker_dir: str | Path) -> Path:
    """Return the central queue adjacent to the cloud-session marker directory."""

    marker_root = Path(marker_dir).resolve()
    megaplan_root = (
        marker_root.parent
        if marker_root.parent.name == ".megaplan"
        else marker_root.parent / ".megaplan"
    )
    return validate_queue_root(megaplan_root / QUEUE_DIR_NAME)


def requests_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / REQUESTS_DIR_NAME


def decisions_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / DECISIONS_DIR_NAME


def attempts_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / ATTEMPTS_DIR_NAME


def active_claims_dir(queue_dir: str | Path) -> Path:
    return validate_queue_root(queue_dir) / ACTIVE_CLAIMS_DIR_NAME


def active_repair_claim_lock_dir(queue_dir: str | Path, blocker_id: str) -> Path:
    """Return the blocker-scoped active repair claim lock directory."""

    normalized = _normalize_claim_identity(blocker_id, "blocker_id")
    return active_claims_dir(queue_dir) / f"{_claim_path_token(normalized)}.lock"


def normalize_problem_signature(
    problem_signature: Mapping[str, Any],
    *,
    extra_fields: tuple[str, ...] = (),
) -> dict[str, str]:
    """Return canonical signature fields, normalized for identity.

    When *extra_fields* is provided the result also includes those keys
    (e.g. :data:`~arnold_pipelines.megaplan.cloud.repair_recurrence.ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS`)
    so acceptance predicate failures produce distinct repair identities.
    """

    result = {
        field: str(problem_signature.get(field) or "").strip()
        for field in PROBLEM_SIGNATURE_FIELDS
    }
    for field in extra_fields:
        result[field] = str(problem_signature.get(field) or "").strip()
    return result


def problem_signature_key(
    problem_signature: Mapping[str, Any],
    *,
    extra_fields: tuple[str, ...] = (),
) -> str:
    normalized = normalize_problem_signature(problem_signature, extra_fields=extra_fields)
    fields = PROBLEM_SIGNATURE_FIELDS + extra_fields
    return _sha256_json([normalized[field] for field in fields])


def redacted_hint_hash(root_cause_hint: Any) -> str:
    """Hash the redacted root-cause hint without exposing the raw hint."""

    redacted = redact_payload(root_cause_hint)
    return _sha256_json(redacted)


def request_id_for(
    *,
    session: str,
    problem_signature: Mapping[str, Any],
    root_cause_hint: Any = "",
    extra_signature_fields: tuple[str, ...] = (),
) -> str:
    """Return a stable request id unaffected by timestamps or raw hint text.

    When *extra_signature_fields* is provided (e.g.
    :data:`~arnold_pipelines.megaplan.cloud.repair_recurrence.ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS`)
    the problem signature is normalized with those additional keys so
    acceptance predicate failures produce distinct request ids.
    """

    return _sha256_json(
        {
            "session": str(session or "").strip(),
            "problem_signature": normalize_problem_signature(
                problem_signature, extra_fields=extra_signature_fields
            ),
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
    acceptance_predicate_failure: Mapping[str, Any] | None = None,
    acceptance_transaction_id: str = "",
    acceptance_snapshot_hash: str = "",
) -> dict[str, Any]:
    """Write a request marker once, recording any rejection/coalescing separately.

    When *acceptance_predicate_failure* is provided the acceptance predicate
    fields (kind, evidence_kind, summary) plus *acceptance_transaction_id*
    and *acceptance_snapshot_hash* are appended to the problem signature so
    atomic completion predicate failures produce repair identities distinct
    from fixer-infrastructure failures.  Existing callers that omit these
    parameters continue to produce legacy 7-field signatures.
    """

    queue_root = validate_queue_root(queue_root)

    # ── Merge acceptance predicate fields into the problem signature ──────
    extended_signature = dict(problem_signature)
    extra_fields: tuple[str, ...] = ()
    if acceptance_predicate_failure is not None:
        extra_fields = ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS
        acc = dict(acceptance_predicate_failure) if isinstance(acceptance_predicate_failure, dict) else {}
        details = acc.get("details")
        details = dict(details) if isinstance(details, dict) else {}
        raw_evidence_refs = details.get("evidence_refs")
        if isinstance(raw_evidence_refs, list):
            evidence_refs = ",".join(
                str(item).strip() for item in raw_evidence_refs if str(item).strip()
            )
        else:
            evidence_refs = str(raw_evidence_refs or "").strip()
        extended_signature.update(
            {
                "acceptance_predicate_kind": str(acc.get("kind") or "").strip(),
                "acceptance_predicate_evidence_kind": str(
                    acc.get("evidence_kind") or ""
                ).strip(),
                "acceptance_predicate_summary": str(acc.get("summary") or "").strip(),
                "acceptance_transaction_id": str(
                    acceptance_transaction_id or ""
                ).strip(),
                "acceptance_snapshot_hash": str(
                    acceptance_snapshot_hash or ""
                ).strip(),
                "acceptance_evidence_refs": evidence_refs,
                "safe_recovery_action": str(
                    details.get("safe_recovery_action") or ""
                ).strip(),
                "recovery_action": str(details.get("recovery_action") or "").strip(),
            }
        )

    normalized_signature = normalize_problem_signature(
        extended_signature, extra_fields=extra_fields
    )
    hint_hash = redacted_hint_hash(root_cause_hint)
    request_id = request_id_for(
        session=session,
        problem_signature=extended_signature,
        root_cause_hint=root_cause_hint,
        extra_signature_fields=extra_fields,
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
        "problem_signature_key": problem_signature_key(
            normalized_signature, extra_fields=extra_fields
        ),
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

    existing = find_pending_by_signature(
        queue_root, normalized_signature, extra_fields=extra_fields
    )
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


def iter_repair_attempts(
    queue_root: str | Path,
    *,
    include_malformed: bool = False,
) -> list[dict[str, Any]]:
    """Return immutable managed-dispatch attempts in deterministic order."""

    queue_root = validate_queue_root(queue_root)
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for path in sorted(attempts_dir(queue_root).glob("*.json"), key=lambda item: item.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            malformed.append(_malformed_attempt(path, exc))
            continue
        if not isinstance(payload, dict):
            malformed.append(_malformed_attempt(path, ValueError("attempt record is not a JSON object")))
            continue
        required = {
            "schema_version",
            "kind",
            "attempt_id",
            "request_id",
            "blocker_id",
            "created_at",
        }
        if not required.issubset(payload) or payload.get("kind") != "repair_request_attempt":
            malformed.append(_malformed_attempt(path, ValueError("attempt record has invalid shape")))
            continue
        payload = dict(payload)
        payload["_path"] = str(path)
        records.append(payload)
    records.sort(key=_attempt_sort_key)
    if include_malformed:
        records.extend(sorted(malformed, key=lambda item: item["path"]))
    return records


def find_pending_by_signature(
    queue_dir: str | Path,
    problem_signature: Mapping[str, Any],
    *,
    extra_fields: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    key = problem_signature_key(problem_signature, extra_fields=extra_fields)
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


def write_dispatch_attempt(
    queue_dir: str | Path,
    *,
    request_id: str,
    blocker_id: str,
    actor: str,
    repair_layer: str,
    command: str,
    child_pid: int,
    managed_run_id: str,
    managed_manifest_path: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Write immutable proof that a claimed request launched a managed child."""

    when = created_at or utc_now()
    record = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": "repair_request_attempt",
        "attempt_id": _sha256_json(
            {
                "request_id": request_id,
                "blocker_id": blocker_id,
                "actor": actor,
                "repair_layer": repair_layer,
                "command": command,
                "child_pid": child_pid,
                "managed_run_id": managed_run_id,
                "managed_manifest_path": managed_manifest_path,
                "created_at": when,
            }
        ),
        "request_id": str(request_id or "").strip(),
        "blocker_id": str(blocker_id or "").strip(),
        "actor": str(actor or "").strip(),
        "repair_layer": str(repair_layer or "").strip(),
        "command": str(command or "").strip(),
        "child_pid": int(child_pid),
        "managed_run_id": str(managed_run_id or "").strip(),
        "managed_manifest_path": str(managed_manifest_path or "").strip(),
        "status": "launched",
        "created_at": when,
    }
    for field in (
        "request_id",
        "blocker_id",
        "actor",
        "repair_layer",
        "command",
        "managed_run_id",
        "managed_manifest_path",
    ):
        if not record[field]:
            raise ValueError(f"{field} is required")
    if record["child_pid"] <= 0:
        raise ValueError("child_pid must be positive")
    path = attempts_dir(queue_dir) / f"{when.replace(':', '').replace('-', '')}-{record['attempt_id']}.json"
    _write_once_json(path, record)
    return {**record, "_path": str(path)}


def record_unclaimed_request_failure(
    queue_dir: str | Path,
    *,
    request_id: str,
    reason: str,
    max_retries: int = 3,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Durably bound failed claim handoffs and alert once at exhaustion."""

    if max_retries < 1:
        raise ValueError("max_retries must be positive")
    history = [
        item
        for item in iter_repair_decisions(queue_dir)
        if item.get("request_id") == request_id
    ]
    existing_alert = next(
        (item for item in history if item.get("decision") == "claim_alert"),
        None,
    )
    retry_count = sum(item.get("decision") == "claim_retry" for item in history)
    if existing_alert is not None:
        return {
            "status": "alerted",
            "retry_count": retry_count,
            "max_retries": max_retries,
            "alert": existing_alert,
        }

    attempt_number = retry_count + 1
    retry = write_decision(
        queue_dir,
        request_id=request_id,
        decision="claim_retry",
        reason=f"claim handoff {attempt_number}/{max_retries}: {reason}",
        created_at=created_at,
    )
    alert = None
    if attempt_number >= max_retries:
        alert = write_decision(
            queue_dir,
            request_id=request_id,
            decision="claim_alert",
            reason=(
                f"accepted request remained unclaimed after {max_retries} bounded handoffs: {reason}"
            ),
            created_at=created_at,
        )
    return {
        "status": "alerted" if alert is not None else "retryable",
        "retry_count": attempt_number,
        "max_retries": max_retries,
        "retry": retry,
        "alert": alert,
    }


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


def bind_managed_run_to_active_claim(
    queue_dir: str | Path,
    *,
    blocker_id: str,
    request_id: str,
    managed_run_id: str,
    managed_manifest_path: str,
    expected_owner_pid: int | None,
    new_owner_pid: int,
) -> bool:
    """Fence an already-authorized claim to the process that really executes it.

    The watchdog remains the authority that wins the blocker-scoped mkdir
    claim.  Immediately before the managed supervisor launches the worker, it
    transfers PID custody and adds the durable run identity.  All identity
    fields are checked under a claim-local flock, so an observer or duplicate
    dispatcher cannot attach a different run to the accepted request.
    """

    normalized_blocker_id = _normalize_claim_identity(blocker_id, "blocker_id")
    normalized_request_id = _normalize_claim_identity(request_id, "request_id")
    normalized_run_id = _normalize_claim_identity(managed_run_id, "managed_run_id")
    lock_dir = active_repair_claim_lock_dir(queue_dir, normalized_blocker_id)
    owner_path = owner_metadata_path(lock_dir)
    bind_lock = lock_dir.with_name(lock_dir.name + ".managed-run-bind")
    try:
        handle = bind_lock.open("a+b")
    except OSError:
        return False
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        owner = repair_contract.load_json(owner_path, default={})
        if not isinstance(owner, dict):
            return False
        if str(owner.get("request_id") or "") != normalized_request_id:
            return False
        if str(owner.get("blocker_id") or "") != normalized_blocker_id:
            return False
        owner_run_id = str(owner.get("managed_agent_run_id") or "")
        if owner_run_id and owner_run_id != normalized_run_id:
            return False
        if expected_owner_pid is not None and owner.get("pid") not in {
            expected_owner_pid,
            new_owner_pid,
        }:
            return False
        owner.update(
            {
                "pid": int(new_owner_pid),
                "managed_agent_run_id": normalized_run_id,
                "managed_manifest_path": str(managed_manifest_path),
                "managed_agent_bound_at": utc_now(),
            }
        )
        repair_contract.atomic_write_json(
            owner_path,
            owner,
            include_resident_provenance=False,
        )
        return True
    finally:
        handle.close()


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


def _attempt_sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("created_at") or ""), str(record.get("attempt_id") or ""))


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


def _malformed_attempt(path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "kind": "malformed_repair_attempt",
        "path": str(path),
        "reason": str(exc),
    }
def write_repair_verdict_decision(
    queue_dir: str | Path,
    *,
    request_id: str,
    verdict_kind: str,
    verdict_path: str = "",
    blocker_id: str = "",
    reason: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Write an immutable decision record linking a repair verdict to a request.

    This is a specialized wrapper around ``write_decision`` that records the
    verdict kind, verdict artifact path, and blocker identity alongside the
    standard request decision flow.  The decision kind is always ``dispatched``
    because the verdict itself carries the outcome semantics.
    """
    return write_decision(
        queue_dir,
        request_id=request_id,
        decision="dispatched",
        reason=(
            f"repair_verdict: {verdict_kind}"
            f"{' blocker=' + blocker_id if blocker_id else ''}"
            f"{' path=' + verdict_path if verdict_path else ''}"
            f"{'; ' + reason if reason else ''}"
        ),
        related_request_id="",
        created_at=created_at,
    )


__all__ = [
    "ACTIVE_CLAIMS_DIR_NAME",
    "ATTEMPTS_DIR_NAME",
    "PROBLEM_SIGNATURE_FIELDS",
    "QUEUE_DIR_NAME",
    "ActiveRepairClaimResult",
    "ActiveRepairClaimStatus",
    "DecisionKind",
    "active_claims_dir",
    "active_repair_claim_lock_dir",
    "attempts_dir",
    "claim_active_repair_request",
    "bind_managed_run_to_active_claim",
    "enqueue_human_gate_repair_request",
    "enqueue_repair_request",
    "find_pending_by_signature",
    "iter_repair_decisions",
    "iter_repair_attempts",
    "iter_repair_requests",
    "normalize_problem_signature",
    "problem_signature_key",
    "record_malformed_file",
    "redacted_hint_hash",
    "repair_queue_dir",
    "record_unclaimed_request_failure",
    "release_active_repair_request_claim",
    "request_id_for",
    "validate_queue_root",
    "write_decision",
    "write_dispatch_attempt",
    "write_repair_verdict_decision",
]
