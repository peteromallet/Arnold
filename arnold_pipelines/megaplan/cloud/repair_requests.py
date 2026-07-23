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
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLeaseEvent,
    CustodyTargetKey,
    RepairOccurrenceKey,
    build_custody_target_key,
    build_repair_occurrence_key,
    process_birth_identity,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    open_lease_store,
    StaleSequenceError,
    LeaseIdempotencyConflict,
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


def _default_retry_strategy(
    problem_signature: Mapping[str, Any],
    target: Mapping[str, Any],
) -> str:
    explicit = str(
        problem_signature.get("retry_strategy")
        or target.get("retry_strategy")
        or ""
    ).strip()
    if explicit:
        return explicit
    return {
        "deterministic_phase_failure": "repair_phase_contract",
        "human_gate": "human_decision",
        "awaiting_pr_merge": "reconcile_pr_merge",
        "blocked_recovery_not_resolved": "manual_review",
    }.get(str(problem_signature.get("failure_kind") or "").strip(), "repair_request")


def _canonicalize_blocked_task_id(problem_signature: dict[str, Any]) -> None:
    if str(problem_signature.get("blocked_task_id") or "").strip():
        return
    phase = str(problem_signature.get("phase_or_step") or "").strip()
    milestone = str(problem_signature.get("milestone_or_plan") or "").strip()
    if phase:
        problem_signature["blocked_task_id"] = f"phase:{phase}"
    elif milestone:
        problem_signature["blocked_task_id"] = f"plan:{milestone}"


def _canonical_request_blocker_identity(
    *,
    session: str,
    workspace: str | Path | None,
    target: Mapping[str, Any],
    problem_signature: Mapping[str, Any],
    signature_key: str,
) -> tuple[dict[str, Any], str]:
    session_identity = str(session or "").strip()
    milestone_or_plan = str(
        problem_signature.get("milestone_or_plan")
        or target.get("plan_name")
        or target.get("plan")
        or target.get("pipeline_name")
        or session_identity
    ).strip()
    required = {
        "session": session_identity,
        "current_state": str(problem_signature.get("current_state") or "").strip(),
        "failure_kind": str(problem_signature.get("failure_kind") or "").strip(),
        "phase_or_step": str(problem_signature.get("phase_or_step") or "").strip(),
        "milestone_or_plan": milestone_or_plan,
        "blocked_task_id": str(problem_signature.get("blocked_task_id") or "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(
            "repair request cannot allocate canonical blocker identity; missing "
            + ", ".join(missing)
        )
    target_identity = {
        "session": session_identity,
        "workspace": str(
            workspace
            or target.get("workspace_path")
            or target.get("workspace")
            or ""
        ),
        "plan": milestone_or_plan,
        "plan_dir": str(target.get("plan_dir") or ""),
        "pipeline": str(target.get("pipeline_name") or ""),
        "problem_signature_key": signature_key,
    }
    fingerprint = repair_contract.normalize_blocker_fingerprint_v1(
        {
            "schema_version": repair_contract.BLOCKER_FINGERPRINT_VERSION,
            "current_state": required["current_state"],
            "retry_strategy": _default_retry_strategy(problem_signature, target),
            "failure_kind": required["failure_kind"],
            "phase_or_step": required["phase_or_step"],
            "milestone_or_plan": milestone_or_plan,
            "blocked_task_id": required["blocked_task_id"],
            "target_fingerprint": "repair-target:v1:" + _sha256_json(target_identity),
        }
    )
    blocker_id = repair_contract.blocker_id_for_fingerprint(fingerprint)
    if fingerprint is None or blocker_id is None:
        raise ValueError("repair request canonical blocker identity is invalid")
    return dict(fingerprint), blocker_id


def repair_request_contract_violations(request: Mapping[str, Any]) -> list[str]:
    """Return typed reasons an immutable request is unsafe to claim."""

    violations: list[str] = []
    raw_fingerprint = request.get("blocker_fingerprint")
    fingerprint = (
        repair_contract.normalize_blocker_fingerprint_v1(raw_fingerprint)
        or repair_contract.normalize_blocker_fingerprint_v2(raw_fingerprint)
    )
    if not repair_contract.blocker_id_matches_fingerprint(
        str(request.get("blocker_id") or ""), fingerprint
    ):
        violations.append("invalid_blocker_identity")
    source = str(request.get("source") or "").strip()
    session = str(request.get("session") or "").strip()
    provenance = request.get("provenance")
    if (
        not source
        or not session
        or not isinstance(provenance, Mapping)
        or str(provenance.get("producer") or "").strip() != source
        or str(provenance.get("session") or "").strip() != session
    ):
        violations.append("invalid_provenance")
    problem_signature = request.get("problem_signature")
    evidence_refs = request.get("evidence_refs")
    if not isinstance(problem_signature, Mapping) or not isinstance(evidence_refs, list):
        violations.append("invalid_problem_signature_evidence")
        problem_signature = {}
        evidence_refs = []
    else:
        expected_digest = _sha256_json(problem_signature)
        if not any(
            isinstance(item, Mapping)
            and item.get("kind") == "problem_signature_digest"
            and item.get("sha256") == expected_digest
            for item in evidence_refs
        ):
            violations.append("invalid_problem_signature_evidence")

    if (
        isinstance(problem_signature, Mapping)
        and problem_signature.get("failure_kind")
        == "completed_repair_without_cursor_advance"
    ):
        target = request.get("target")
        if not isinstance(target, Mapping):
            violations.append("missing_recovery_contract")
        else:
            recovery = target.get("recovery_contract")
            if not str(target.get("configured_profile") or "").strip():
                violations.append("missing_configured_profile")
            if not isinstance(recovery, Mapping):
                violations.append("missing_recovery_contract")
            else:
                if recovery.get("preserve_configured_profile") is not True:
                    violations.append("missing_preserve_configured_profile")
                if recovery.get("required_cursor_advance") is not True:
                    violations.append("missing_required_cursor_advance")
                if recovery.get("forbid_standalone_completion") is not True:
                    violations.append("missing_forbid_standalone_completion")
                if not str(recovery.get("success_requires") or "").strip():
                    violations.append("missing_success_requires")
    return violations


def has_claimable_repair_request_contract(request: Mapping[str, Any]) -> bool:
    """Return whether an immutable request is safe to claim at an effect boundary."""

    return not repair_request_contract_violations(request)


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
    lease_store_dir: str | Path | None = None,
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
    source_identity = str(source or "").strip()
    if not source_identity:
        raise ValueError("repair request provenance source is required")

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

    _canonicalize_blocked_task_id(extended_signature)
    normalized_signature = normalize_problem_signature(
        extended_signature, extra_fields=extra_fields
    )
    signature_key = problem_signature_key(
        normalized_signature, extra_fields=extra_fields
    )
    stable_target = _stable_mapping(target or {})
    blocker_fingerprint, blocker_id = _canonical_request_blocker_identity(
        session=session,
        workspace=workspace,
        target=stable_target,
        problem_signature=extended_signature,
        signature_key=signature_key,
    )
    hint_hash = redacted_hint_hash(root_cause_hint)
    request_id = request_id_for(
        session=session,
        problem_signature=extended_signature,
        root_cause_hint=root_cause_hint,
        extra_signature_fields=extra_fields,
    )
    request_path = requests_dir(queue_root) / f"{request_id}.json"
    predecessor_request_id = ""
    if request_path.exists():
        try:
            existing_request = json.loads(request_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            existing_request = {}
        if not isinstance(existing_request, Mapping) or not has_claimable_repair_request_contract(
            existing_request
        ):
            predecessor_request_id = request_id
            request_id = _sha256_json(
                {
                    "schema_version": "claimable-repair-request-successor-v1",
                    "predecessor_request_id": predecessor_request_id,
                    "blocker_id": blocker_id,
                }
            )
            request_path = requests_dir(queue_root) / f"{request_id}.json"
    record = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": "repair_request",
        "request_id": request_id,
        "created_at": created_at or utc_now(),
        "source": source_identity,
        "session": str(session or "").strip(),
        "workspace": str(workspace or ""),
        "run_kind": str(run_kind or "").strip(),
        "marker_dir": str(Path(marker_dir)) if marker_dir is not None else "",
        "queue_dir": str(queue_root),
        "target": stable_target,
        "problem_signature": normalized_signature,
        "problem_signature_key": signature_key,
        "blocker_fingerprint": blocker_fingerprint,
        "blocker_id": blocker_id,
        "predecessor_request_id": predecessor_request_id,
        "provenance": {
            "producer": source_identity,
            "session": str(session or "").strip(),
            "run_kind": str(run_kind or "").strip(),
        },
        "evidence_refs": [
            {
                "kind": "problem_signature_digest",
                "sha256": _sha256_json(normalized_signature),
            },
            {
                "kind": "redacted_root_cause_hint_digest",
                "sha256": hint_hash,
            },
        ],
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
        queue_root,
        normalized_signature,
        extra_fields=extra_fields,
        session=str(session or "").strip(),
        blocker_id=blocker_id,
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
    result: dict[str, Any] = {
        "status": "queued",
        "request": record,
        "path": str(request_path),
        "decision": decision,
    }
    # ── M7: shadow custody lease acquisition ──
    lease_store = _open_custody_lease_store(lease_store_dir)
    if lease_store is not None:
        custody_target = _build_custody_target_from_repair_context(
            session=session,
            problem_signature=problem_signature,
            target=target,
        )
        identity = process_birth_identity()
        lease_result = _shadow_acquire_custody_lease(
            lease_store=lease_store,
            lease_id=f"repair-req-{request_id}",
            target=custody_target,
            owner_host=identity.get("host", _hostname()),
            owner_pid=identity.get("pid", str(os.getpid())),
            owner_boot_id=identity.get("boot_id", ""),
            run_authority_grant_id=record.get("request_id", ""),
            payload_extra={
                "source": source,
                "request_id": request_id,
                "queue_dir": str(queue_root),
            },
        )
        result["m7_custody_lease"] = lease_result
    return result


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
    session: str = "",
    blocker_id: str = "",
) -> dict[str, Any] | None:
    key = problem_signature_key(problem_signature, extra_fields=extra_fields)
    decided = _decided_request_ids(queue_dir)
    for record in iter_repair_requests(queue_dir):
        if record.get("request_id") in decided:
            continue
        if not has_claimable_repair_request_contract(record):
            continue
        if session and str(record.get("session") or "").strip() != session:
            continue
        if blocker_id and str(record.get("blocker_id") or "").strip() != blocker_id:
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

    if decision == "accepted":
        request_path = requests_dir(queue_dir) / f"{str(request_id or '').strip()}.json"
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "accepted repair request requires persisted canonical blocker identity, provenance, and evidence"
            ) from exc
        if not isinstance(request, Mapping) or not has_claimable_repair_request_contract(request):
            raise ValueError(
                "accepted repair request requires persisted canonical blocker identity, provenance, and evidence"
            )

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
    lease_store_dir: str | Path | None = None,
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
    claim_result = _claim_result_from_lock(
        result,
        blocker_id=normalized_blocker_id,
        request_id=normalized_request_id,
    )
    # ── M7: shadow custody lease acquisition on successful claim ──
    if claim_result.claimed:
        lease_store = _open_custody_lease_store(lease_store_dir)
        if lease_store is not None:
            custody_target = _build_custody_target_from_repair_context(
                session=normalized_session,
                problem_signature=blocker_fingerprint or {},
            )
            identity = process_birth_identity()
            lease_result = _shadow_acquire_custody_lease(
                lease_store=lease_store,
                lease_id=f"repair-claim-{normalized_blocker_id}",
                target=custody_target,
                run_id=normalized_actor,
                run_authority_grant_id=normalized_request_id,
                owner_host=hostname or _hostname(),
                owner_pid=str(pid) if pid is not None else identity.get("pid", "0"),
                owner_boot_id=identity.get("boot_id", ""),
                payload_extra={
                    "actor": normalized_actor,
                    "request_id": normalized_request_id,
                    "blocker_id": normalized_blocker_id,
                    "queue_dir": str(queue_dir),
                },
            )
            # Store lease result alongside claim (ActiveRepairClaimResult is frozen,
            # so we cannot attach it directly — callers should read the lease store)
            object.__setattr__(claim_result, "_m7_custody_lease", lease_result)
    return claim_result


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
    lease_store_dir: str | Path | None = None,
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
        # ── M7: shadow custody lease record on successful bind ──
        lease_store = _open_custody_lease_store(lease_store_dir)
        if lease_store is not None:
            custody_target = _build_custody_target_from_repair_context(
                session=str(owner.get("session", "")),
                problem_signature=owner.get("blocker_fingerprint"),
            )
            identity = process_birth_identity()
            _shadow_acquire_custody_lease(
                lease_store=lease_store,
                lease_id=f"repair-bind-{normalized_blocker_id}",
                target=custody_target,
                run_id=normalized_run_id,
                run_authority_grant_id=normalized_request_id,
                coordinator_fence_token=owner.get("fence_token", 0),
                owner_host=_hostname(),
                owner_pid=str(new_owner_pid),
                owner_boot_id=identity.get("boot_id", ""),
                payload_extra={
                    "managed_run_id": normalized_run_id,
                    "managed_manifest_path": str(managed_manifest_path),
                    "request_id": normalized_request_id,
                    "blocker_id": normalized_blocker_id,
                    "queue_dir": str(queue_dir),
                },
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
        if decision in {"stale", "superseded"}:
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


# ── M7 Custody lease shadow integration ────────────────────────────────────


def _shadow_acquire_custody_lease(
    *,
    lease_store: CustodyLeaseStore | None,
    lease_id: str,
    target: CustodyTargetKey | None,
    run_authority_grant_id: str = "",
    coordinator_fence_token: int = 0,
    wbc_attempt_reference: str = "",
    run_id: str = "",
    run_revision: str = "",
    coordinator_attempt_id: str = "",
    owner_host: str = "",
    owner_pid: str = "",
    owner_boot_id: str = "",
    causal_predecessor: str = "",
    expires_at: str = "",
    payload_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attempt to shadow-acquire a Custody lease for a repair operation.

    In M7 shadow mode, this records a CustodyLeaseEvent (acquire) in the
    lease store alongside the existing mkdir/PID lock mechanism.  The lease
    store becomes the authoritative source of truth; the mkdir lock is
    admission/projection evidence only.

    Returns a dict with ``m7_lease_status`` (``'acquired'``, ``'not_owner'``,
    ``'idempotent'``, ``'unavailable'``, ``'error'``) and diagnostic fields.
    Failures never block the existing repair flow — they are captured as
    typed non-owner outcomes.
    """
    result: dict[str, Any] = {
        "m7_lease_status": "unavailable",
        "m7_lease_event_id": "",
        "m7_lease_epoch": 0,
    }

    if lease_store is None:
        result["m7_lease_status"] = "unavailable"
        result["m7_lease_detail"] = "no lease store provided"
        return result

    if target is None:
        result["m7_lease_status"] = "error"
        result["m7_lease_detail"] = "cannot build CustodyTargetKey from available context"
        return result

    try:
        # Build the RepairOccurrenceKey
        occ_key = build_repair_occurrence_key(
            target=target,
            run_id=run_id or f"repair-run-{lease_id[:12]}",
            run_revision=run_revision or "m7-shadow",
            coordinator_attempt_id=coordinator_attempt_id or f"coord-{lease_id[:12]}",
            fence_token=coordinator_fence_token,
            wbc_attempt_reference=wbc_attempt_reference or f"wbc-ref-{lease_id[:12]}",
        )
        if occ_key is None:
            result["m7_lease_status"] = "error"
            result["m7_lease_detail"] = "failed to construct RepairOccurrenceKey"
            return result

        # Build the event payload
        payload: dict[str, Any] = {"m7_shadow": True}
        if payload_extra:
            payload.update(dict(payload_extra))

        event = CustodyLeaseEvent(
            event_id=f"acquire-{lease_id[:32]}",
            lease_id=lease_id,
            sequence=1,
            event_type="acquire",
            occurred_at=utc_now(),
            custody_epoch=1,
            owner_host=owner_host or "unknown",
            owner_pid=owner_pid or "0",
            owner_boot_id=owner_boot_id or "",
            run_authority_grant_id=run_authority_grant_id or f"grant-{lease_id[:12]}",
            coordinator_fence_token=coordinator_fence_token,
            wbc_attempt_reference=wbc_attempt_reference or f"wbc-ref-{lease_id[:12]}",
            occurrence_digest=occ_key.occurrence_digest,
            idempotency_key=f"idem-{lease_id}",
            causal_predecessor=causal_predecessor,
            payload=payload,
        )

        recorded = lease_store.record_event(event)
        result["m7_lease_status"] = "acquired"
        result["m7_lease_event_id"] = recorded.event_id
        result["m7_lease_epoch"] = recorded.custody_epoch
        result["m7_lease_digest"] = recorded.occurrence_digest
        return result

    except LeaseIdempotencyConflict:
        result["m7_lease_status"] = "idempotent"
        result["m7_lease_detail"] = "lease already exists with matching idempotency key"
        return result
    except StaleSequenceError:
        result["m7_lease_status"] = "not_owner"
        result["m7_lease_detail"] = "lease sequence conflict — another owner holds the lease"
        return result
    except Exception as exc:
        result["m7_lease_status"] = "error"
        result["m7_lease_detail"] = f"{type(exc).__name__}: {exc}"
        return result


def _build_custody_target_from_repair_context(
    *,
    session: str = "",
    problem_signature: Mapping[str, Any] | None = None,
    target: Mapping[str, Any] | None = None,
) -> CustodyTargetKey | None:
    """Build a CustodyTargetKey from repair request context fields.

    Extracts F01 tuple fields from problem_signature and target dicts
    where available.  Returns None when insufficient fields are present.
    """
    sig = dict(problem_signature or {})
    tgt = dict(target or {})

    environment = _as_text(
        tgt.get("environment") or sig.get("environment") or ""
    )
    session_val = _as_text(session or sig.get("session") or "")
    chain = _as_text(
        tgt.get("chain") or sig.get("chain") or ""
    )
    plan_revision = _as_text(
        tgt.get("plan_revision") or sig.get("plan_revision") or ""
    )
    phase = _as_text(
        tgt.get("phase") or sig.get("phase_or_step") or sig.get("phase") or ""
    )
    task = _as_text(
        tgt.get("task") or sig.get("blocked_task_id") or sig.get("task") or ""
    )
    attempt = _as_text(
        tgt.get("attempt") or sig.get("attempt") or ""
    )
    normalized_failure_kind = _as_text(
        tgt.get("failure_kind") or sig.get("failure_kind") or ""
    )
    blocker_or_phase_result_hash = _as_text(
        tgt.get("blocker_hash") or sig.get("target_fingerprint") or ""
    )
    fence = _as_text(
        tgt.get("fence") or sig.get("fence") or ""
    )

    return build_custody_target_key(
        environment=environment or "unknown",
        session=session_val or "unknown",
        chain=chain or "unknown",
        plan_revision=plan_revision or "unknown",
        phase=phase or "unknown",
        task=task or "unknown",
        attempt=attempt or "1",
        normalized_failure_kind=normalized_failure_kind or "unknown",
        blocker_or_phase_result_hash=blocker_or_phase_result_hash or "unknown",
        fence=fence or "0",
        chain_identity="",
    )


def _as_text(value: Any) -> str:
    """Coerce a value to stripped text or return empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _open_custody_lease_store(
    lease_store_dir: str | Path | None,
) -> CustodyLeaseStore | None:
    """Open a custody lease store from a directory path, or return None."""
    if lease_store_dir is None:
        return None
    try:
        return open_lease_store(Path(lease_store_dir), flock=False)
    except Exception:
        return None


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
    "has_claimable_repair_request_contract",
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
    "repair_request_contract_violations",
    "request_id_for",
    "validate_queue_root",
    "write_decision",
    "write_dispatch_attempt",
    "write_repair_verdict_decision",
]
