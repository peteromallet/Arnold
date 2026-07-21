"""Shared repair-data JSON contract helpers for cloud repair artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, TypeAlias, TypedDict, cast

from arnold.runtime.state_persistence import atomic_write_json as _atomic_write_json
from arnold_pipelines.megaplan.custody.contracts import normalize_repair_occurrence_key
from arnold_pipelines.megaplan.cloud.redact import redact_payload as canonical_redact_payload
from arnold_pipelines.megaplan.observability.events import EventKind, emit
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState, CanonicalState

CURRENT_SCHEMA_VERSION = 1

ADDITIVE_FIELD_DEFAULTS: dict[str, Any] = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "target": {},
    "incident_id": "",
    "attempt_ids": [],
    "verification": {},
    "discord_escalation": {},
    "known_prior_issue_refs": [],
}

_LIST_FIELDS = {
    "attempt_ids",
    "attempts",
    "iterations",
    "known_prior_issue_refs",
}
_DICT_FIELDS = {
    "current_advancement_snapshot",
    "current_recurrence",
    "current_signature",
    "discord_escalation",
    "initial_facts",
    "target",
    "verification",
}
_INDEX_TOP_LEVEL_KEYS = ("sessions", "incidents")
_INDEX_REF_KEYS = ("latest-attempt", "latest-outcome", "unresolved-escalation")
_ACTIVE_SESSION_STATUSES = frozenset(
    {"active", "running", "repairing", "in_progress", "pending"}
)
_RESOLVED_RECORD_STATES = frozenset(
    {
        "accepted_blocked",
        "closed",
        "complete",
        "completed",
        "delivered",
        "resolved",
        "satisfied",
        "waived",
    }
)
_UNRESOLVED_RECORD_STATES = frozenset(
    {"active", "awaiting_human", "needs_human", "open", "pending", "unresolved"}
)
_RETENTION_WINDOWS_DAYS = {
    "attempts": 14,
    "incidents": 30,
    "escalations": 90,
    "meta": 90,
    "audit_reports": 30,
}
_SNAPSHOT_RETENTION_DAYS = 30
_MIN_ATTEMPTS_PER_SESSION = 20

REPAIR_EVIDENCE_REF_SCHEMA = "arnold-repair-evidence-ref-v1"
REPAIR_EVIDENCE_COMPACTION_SCHEMA = "arnold-repair-evidence-compaction-v1"
MAX_REPAIR_DATA_BYTES = 4 * 1024 * 1024
_EVIDENCE_EXTERNALIZE_THRESHOLD_BYTES = 16 * 1024
_CURRENT_FAILURE_CONTEXT_MAX_BYTES = 512 * 1024
_ATTEMPT_EVIDENCE_FIELDS = (
    "failure_context",
    "post_launch_failure_context",
    "post_kimi_failure_context",
    "execute_attempt_context",
)


BLOCKER_FINGERPRINT_VERSION = 1
BLOCKER_FINGERPRINT_V1_PREFIX = "repair-blocker-fingerprint/v1"
BLOCKER_ID_V1_PREFIX = "blocker:v1:"

BLOCKER_FINGERPRINT_V2_VERSION = 2
BLOCKER_FINGERPRINT_V2_PREFIX = "repair-blocker-fingerprint/v2"
BLOCKER_ID_V2_PREFIX = "blocker:v2:"

RepairRequestStatus: TypeAlias = Literal[
    "accepted",
    "coalesced",
    "stale",
    "superseded",
    "dispatched",
]
REQUEST_STATUS_ACCEPTED: RepairRequestStatus = "accepted"
REQUEST_STATUS_COALESCED: RepairRequestStatus = "coalesced"
REQUEST_STATUS_STALE: RepairRequestStatus = "stale"
REQUEST_STATUS_SUPERSEDED: RepairRequestStatus = "superseded"
REQUEST_STATUS_DISPATCHED: RepairRequestStatus = "dispatched"
REPAIR_REQUEST_STATUSES: frozenset[RepairRequestStatus] = frozenset(
    {
        REQUEST_STATUS_ACCEPTED,
        REQUEST_STATUS_COALESCED,
        REQUEST_STATUS_STALE,
        REQUEST_STATUS_SUPERSEDED,
        REQUEST_STATUS_DISPATCHED,
    }
)

RepairAttemptState: TypeAlias = Literal[
    "claimed",
    "running",
    "succeeded",
    "failed",
    "cancelled",
]
ATTEMPT_STATE_CLAIMED: RepairAttemptState = "claimed"
ATTEMPT_STATE_RUNNING: RepairAttemptState = "running"
ATTEMPT_STATE_SUCCEEDED: RepairAttemptState = "succeeded"
ATTEMPT_STATE_FAILED: RepairAttemptState = "failed"
ATTEMPT_STATE_CANCELLED: RepairAttemptState = "cancelled"
REPAIR_ATTEMPT_STATES: frozenset[RepairAttemptState] = frozenset(
    {
        ATTEMPT_STATE_CLAIMED,
        ATTEMPT_STATE_RUNNING,
        ATTEMPT_STATE_SUCCEEDED,
        ATTEMPT_STATE_FAILED,
        ATTEMPT_STATE_CANCELLED,
    }
)

RepairCustodyBucket: TypeAlias = Literal[
    "repairing",
    "repairable_not_repairing",
    "human_required",
    "paused",
    "broken_superfixer",
]
CUSTODY_BUCKET_REPAIRING: RepairCustodyBucket = "repairing"
CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING: RepairCustodyBucket = "repairable_not_repairing"
CUSTODY_BUCKET_HUMAN_REQUIRED: RepairCustodyBucket = "human_required"
CUSTODY_BUCKET_PAUSED: RepairCustodyBucket = "paused"
CUSTODY_BUCKET_BROKEN_SUPERFIXER: RepairCustodyBucket = "broken_superfixer"
REPAIR_CUSTODY_BUCKETS: frozenset[RepairCustodyBucket] = frozenset(
    {
        CUSTODY_BUCKET_REPAIRING,
        CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
        CUSTODY_BUCKET_HUMAN_REQUIRED,
        CUSTODY_BUCKET_PAUSED,
        CUSTODY_BUCKET_BROKEN_SUPERFIXER,
    }
)

RepairDispatchIntent: TypeAlias = Literal[
    "dispatch_l1",
    "queue_only",
    "human_required",
    "broken_superfixer",
]
DISPATCH_INTENT_L1: RepairDispatchIntent = "dispatch_l1"
DISPATCH_INTENT_QUEUE_ONLY: RepairDispatchIntent = "queue_only"
DISPATCH_INTENT_HUMAN_REQUIRED: RepairDispatchIntent = "human_required"
DISPATCH_INTENT_BROKEN_SUPERFIXER: RepairDispatchIntent = "broken_superfixer"
REPAIR_DISPATCH_INTENTS: frozenset[RepairDispatchIntent] = frozenset(
    {
        DISPATCH_INTENT_L1,
        DISPATCH_INTENT_QUEUE_ONLY,
        DISPATCH_INTENT_HUMAN_REQUIRED,
        DISPATCH_INTENT_BROKEN_SUPERFIXER,
    }
)


class BlockerFingerprintV1(TypedDict):
    """Canonical blocker identity payload shared across custody consumers."""

    schema_version: Literal[1]
    current_state: str
    retry_strategy: str
    failure_kind: str
    phase_or_step: str
    milestone_or_plan: str
    blocked_task_id: str
    target_fingerprint: str


_BLOCKER_FINGERPRINT_V1_FIELDS = (
    "current_state",
    "retry_strategy",
    "failure_kind",
    "phase_or_step",
    "milestone_or_plan",
    "blocked_task_id",
    "target_fingerprint",
)


def normalize_blocker_fingerprint_v1(
    payload: Mapping[str, Any] | None,
) -> BlockerFingerprintV1 | None:
    """Return a canonical v1 blocker fingerprint or ``None`` for unsafe inputs."""

    if not isinstance(payload, Mapping):
        return None
    schema_version = payload.get("schema_version")
    if schema_version != BLOCKER_FINGERPRINT_VERSION:
        return None

    normalized: dict[str, Any] = {"schema_version": BLOCKER_FINGERPRINT_VERSION}
    for field in _BLOCKER_FINGERPRINT_V1_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        normalized[field] = cleaned
    return cast(BlockerFingerprintV1, normalized)


def blocker_id_for_fingerprint(payload: Mapping[str, Any] | None) -> str | None:
    """Return a deterministic blocker id for a canonical v1 or v2 fingerprint."""

    # Try V2 first, then fall back to V1.
    normalized_v2 = normalize_blocker_fingerprint_v2(payload)
    if normalized_v2 is not None:
        prefix = BLOCKER_FINGERPRINT_V2_PREFIX
        id_prefix = BLOCKER_ID_V2_PREFIX
        canonical_payload = {
            "prefix": prefix,
            "fingerprint": normalized_v2,
        }
        digest = sha256(
            json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"{id_prefix}{digest}"

    normalized = normalize_blocker_fingerprint_v1(payload)
    if normalized is None:
        return None
    canonical_payload = {
        "prefix": BLOCKER_FINGERPRINT_V1_PREFIX,
        "fingerprint": normalized,
    }
    digest = sha256(
        json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{BLOCKER_ID_V1_PREFIX}{digest}"


def _normalize_repair_identity(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    normalized = normalize_repair_occurrence_key(payload)
    return normalized.to_dict() if normalized is not None else None


def _repair_identity_key(payload: Mapping[str, Any] | None) -> str:
    normalized = normalize_repair_occurrence_key(payload)
    return normalized.key if normalized is not None else ""


# ---------------------------------------------------------------------------
# BlockerFingerprintV2 — extended repair identity with acceptance context
# ---------------------------------------------------------------------------


class BlockerFingerprintV2(TypedDict, total=False):
    """Canonical blocker identity payload with acceptance-transaction context.

    Schema version 2 extends V1 with the full acceptance transaction, predicate
    kind, expected/observed hashes, runtime identity, custody ownership, retry
    state, and causal predecessor so distinct failures never collapse into the
    same repair recurrence.

    All V1 fields are **required** and must be non-empty strings.
    V2 extension fields are **optional** and carry empty-string defaults.
    """

    # ── V1 identity fields (required) ────────────────────────────────────────
    schema_version: Literal[2]
    current_state: str
    retry_strategy: str
    failure_kind: str
    phase_or_step: str
    milestone_or_plan: str
    blocked_task_id: str
    target_fingerprint: str

    # ── V2 acceptance-transaction fields (optional) ──────────────────────────
    acceptance_transaction_id: str
    acceptance_snapshot_hash: str

    # ── V2 predicate fields (optional) ───────────────────────────────────────
    predicate_kind: str
    predicate_evidence_kind: str
    predicate_summary: str
    evidence_refs: str
    safe_recovery_action: str
    recovery_action: str

    # ── V2 hash fields (optional) ────────────────────────────────────────────
    expected_hash: str
    observed_hash: str

    # ── V2 runtime fields (optional) ─────────────────────────────────────────
    runtime_identity: str
    source_commit_ref: str

    # ── V2 custody fields (optional) ─────────────────────────────────────────
    custody_owner: str
    custody_epoch: str

    # ── V2 retry fields (optional) ───────────────────────────────────────────
    retry_count: str
    retry_cap: str

    # ── V2 predecessor fields (optional) ─────────────────────────────────────
    predecessor_blocker_id: str
    predecessor_fingerprint_hash: str


#: Required V1 fields that must always be non-empty strings in V2.
_BLOCKER_FINGERPRINT_V2_REQUIRED_FIELDS: tuple[str, ...] = (
    "current_state",
    "retry_strategy",
    "failure_kind",
    "phase_or_step",
    "milestone_or_plan",
    "blocked_task_id",
    "target_fingerprint",
)

#: Optional V2 extension fields — may be empty strings when not available.
_BLOCKER_FINGERPRINT_V2_OPTIONAL_FIELDS: tuple[str, ...] = (
    "acceptance_transaction_id",
    "acceptance_snapshot_hash",
    "predicate_kind",
    "predicate_evidence_kind",
    "predicate_summary",
    "evidence_refs",
    "safe_recovery_action",
    "recovery_action",
    "expected_hash",
    "observed_hash",
    "runtime_identity",
    "source_commit_ref",
    "custody_owner",
    "custody_epoch",
    "retry_count",
    "retry_cap",
    "predecessor_blocker_id",
    "predecessor_fingerprint_hash",
)

#: All V2 fields in canonical order (required first, then optional).
_BLOCKER_FINGERPRINT_V2_ALL_FIELDS: tuple[str, ...] = (
    _BLOCKER_FINGERPRINT_V2_REQUIRED_FIELDS + _BLOCKER_FINGERPRINT_V2_OPTIONAL_FIELDS
)


def normalize_blocker_fingerprint_v2(
    payload: Mapping[str, Any] | None,
) -> BlockerFingerprintV2 | None:
    """Return a canonical v2 blocker fingerprint or ``None`` for unsafe inputs.

    V1 payloads (``schema_version == 1``) are **upgraded** to V2 by copying the
    seven required V1 fields and leaving all extension fields as empty strings.
    This guarantees V1 normalization is preserved byte-for-byte while producing
    a V2-shaped fingerprint.

    V2 payloads are validated the same way: every required V1 field must be a
    non-empty string; optional extension fields default to ``""`` when missing.
    """
    if not isinstance(payload, Mapping):
        return None
    schema_version = payload.get("schema_version")
    if schema_version not in (BLOCKER_FINGERPRINT_VERSION, BLOCKER_FINGERPRINT_V2_VERSION):
        return None

    normalized: dict[str, Any] = {"schema_version": BLOCKER_FINGERPRINT_V2_VERSION}
    for field in _BLOCKER_FINGERPRINT_V2_REQUIRED_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        normalized[field] = cleaned

    # Optional V2 fields: present → stripped string, absent → ""
    for field in _BLOCKER_FINGERPRINT_V2_OPTIONAL_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            normalized[field] = value.strip()
        else:
            normalized[field] = ""

    return cast(BlockerFingerprintV2, normalized)


def blocker_fingerprint_from_acceptance(
    *,
    v1_fingerprint: BlockerFingerprintV1 | None = None,
    acceptance_transaction_id: str = "",
    acceptance_snapshot_hash: str = "",
    predicate_kind: str = "",
    predicate_evidence_kind: str = "",
    predicate_summary: str = "",
    evidence_refs: str = "",
    safe_recovery_action: str = "",
    recovery_action: str = "",
    expected_hash: str = "",
    observed_hash: str = "",
    runtime_identity: str = "",
    source_commit_ref: str = "",
    custody_owner: str = "",
    custody_epoch: str = "",
    retry_count: str = "",
    retry_cap: str = "",
    predecessor_blocker_id: str = "",
    predecessor_fingerprint_hash: str = "",
) -> BlockerFingerprintV2 | None:
    """Build a V2 fingerprint from an existing V1 fingerprint plus acceptance context.

    Returns ``None`` when the V1 fingerprint is ``None`` (no identity to extend).
    All extension fields default to ``""`` so callers that only have a V1
    fingerprint get a valid V2 shape with empty extension slots.
    """
    if v1_fingerprint is None:
        return None

    payload: dict[str, Any] = {
        "schema_version": BLOCKER_FINGERPRINT_V2_VERSION,
        "current_state": v1_fingerprint.get("current_state", ""),
        "retry_strategy": v1_fingerprint.get("retry_strategy", ""),
        "failure_kind": v1_fingerprint.get("failure_kind", ""),
        "phase_or_step": v1_fingerprint.get("phase_or_step", ""),
        "milestone_or_plan": v1_fingerprint.get("milestone_or_plan", ""),
        "blocked_task_id": v1_fingerprint.get("blocked_task_id", ""),
        "target_fingerprint": v1_fingerprint.get("target_fingerprint", ""),
        "acceptance_transaction_id": acceptance_transaction_id,
        "acceptance_snapshot_hash": acceptance_snapshot_hash,
        "predicate_kind": predicate_kind,
        "predicate_evidence_kind": predicate_evidence_kind,
        "predicate_summary": predicate_summary,
        "evidence_refs": evidence_refs,
        "safe_recovery_action": safe_recovery_action,
        "recovery_action": recovery_action,
        "expected_hash": expected_hash,
        "observed_hash": observed_hash,
        "runtime_identity": runtime_identity,
        "source_commit_ref": source_commit_ref,
        "custody_owner": custody_owner,
        "custody_epoch": custody_epoch,
        "retry_count": retry_count,
        "retry_cap": retry_cap,
        "predecessor_blocker_id": predecessor_blocker_id,
        "predecessor_fingerprint_hash": predecessor_fingerprint_hash,
    }
    return normalize_blocker_fingerprint_v2(payload)


class RepairRequestDecisionRecord(TypedDict):
    decision_id: str
    request_id: str
    decision: RepairRequestStatus | str
    reason: str
    related_request_id: str
    created_at: str
    path: str


class RepairCustodyRequestRecord(TypedDict):
    request_id: str
    session: str
    source: str
    path: str
    blocker_id: str
    blocker_fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None
    problem_signature: dict[str, Any]
    target: dict[str, Any]
    status: RepairRequestStatus | str
    active: bool
    decision: RepairRequestDecisionRecord | None
    decision_history: list[RepairRequestDecisionRecord]


class RepairCustodyAttemptRecord(TypedDict):
    attempt_id: str
    session: str
    source: str
    path: str
    blocker_id: str
    blocker_fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None
    request_id: str
    state: RepairAttemptState
    outcome: str
    terminal: bool
    recorded_at: str
    raw: dict[str, Any]


class RepairCustodyProjection(TypedDict):
    blocker_id: str
    blocker_fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None
    custody_bucket: RepairCustodyBucket
    current_state: str
    retry_strategy: str
    failure_kind: str
    request_status_counts: dict[str, int]
    claim_retry_counts: dict[str, int]
    claim_alert_request_ids: list[str]
    active_request_ids: list[str]
    active_claim_request_ids: list[str]
    accepted_unclaimed_request_ids: list[str]
    request_count: int
    claim_count: int
    attempt_count: int
    retry_budget: dict[str, Any]
    evidence_cursor: dict[str, Any]
    terminal_outcomes: list[str]
    requests: list[RepairCustodyRequestRecord]
    attempts: list[RepairCustodyAttemptRecord]
    plan_state: dict[str, Any]
    current_target: dict[str, Any]


RepairDispatchDecisionKind: TypeAlias = Literal[
    "dispatch_l1_repair",
    "repairing",
    "human_required",
    "broken_superfixer",
    "no_action",
    "terminal",
]
DISPATCH_DECISION_L1: RepairDispatchDecisionKind = "dispatch_l1_repair"
DISPATCH_DECISION_REPAIRING: RepairDispatchDecisionKind = "repairing"
DISPATCH_DECISION_HUMAN_REQUIRED: RepairDispatchDecisionKind = "human_required"
DISPATCH_DECISION_BROKEN_SUPERFIXER: RepairDispatchDecisionKind = "broken_superfixer"
DISPATCH_DECISION_NO_ACTION: RepairDispatchDecisionKind = "no_action"
DISPATCH_DECISION_TERMINAL: RepairDispatchDecisionKind = "terminal"
REPAIR_DISPATCH_DECISION_KINDS: frozenset[RepairDispatchDecisionKind] = frozenset(
    {
        DISPATCH_DECISION_L1,
        DISPATCH_DECISION_REPAIRING,
        DISPATCH_DECISION_HUMAN_REQUIRED,
        DISPATCH_DECISION_BROKEN_SUPERFIXER,
        DISPATCH_DECISION_NO_ACTION,
        DISPATCH_DECISION_TERMINAL,
    }
)


@dataclass(frozen=True)
class RepairDispatchDecision:
    """Shared classifier result for watchdog/trigger repair dispatch."""

    decision: RepairDispatchDecisionKind
    dispatch_intent: RepairDispatchIntent
    rationale: tuple[str, ...] = field(default_factory=tuple)
    blocker_id: str = ""
    request_id: str = ""
    custody_bucket: str = ""
    current_state: str = ""
    retry_strategy: str = ""
    failure_kind: str = ""


def blocker_fingerprint_from_evidence(
    *,
    plan_state: Mapping[str, Any] | None = None,
    current_target: Mapping[str, Any] | None = None,
    problem_signature: Mapping[str, Any] | None = None,
) -> BlockerFingerprintV1 | None:
    """Build a canonical blocker fingerprint from existing compatibility artifacts."""

    plan_payload = _as_mapping(plan_state)
    target_payload = _as_mapping(current_target)
    signature = _as_mapping(problem_signature)
    resume_cursor = _as_mapping(plan_payload.get("resume_cursor"))
    latest_failure = _as_mapping(plan_payload.get("latest_failure"))
    latest_failure_meta = _as_mapping(latest_failure.get("metadata"))
    target_plan_state = _as_mapping(target_payload.get("plan_state"))
    target_current_refs = _as_mapping(target_payload.get("current_refs"))
    target_event_cursors = _as_mapping(target_payload.get("event_cursors"))

    payload: dict[str, Any] = {
        "schema_version": BLOCKER_FINGERPRINT_VERSION,
        "current_state": _first_non_empty(
            _as_text(plan_payload.get("current_state")),
            _as_text(target_current_refs.get("plan_current_state")),
            _as_text(signature.get("current_state")),
        ),
        "retry_strategy": _first_non_empty(
            _as_text(resume_cursor.get("retry_strategy")),
            _as_text(target_event_cursors.get("resume_retry_strategy")),
            _as_text(signature.get("retry_strategy")),
        ),
        "failure_kind": _first_non_empty(
            _as_text(latest_failure.get("kind")),
            _as_text(signature.get("failure_kind")),
        ),
        "phase_or_step": _first_non_empty(
            _as_text(latest_failure.get("phase")),
            _as_text(plan_payload.get("phase")),
            _as_text(signature.get("phase_or_step")),
        ),
        "milestone_or_plan": _first_non_empty(
            _as_text(plan_payload.get("name")),
            _as_text(target_current_refs.get("current_plan_name")),
            _as_text(target_current_refs.get("chain_current_plan_name")),
            _as_text(signature.get("milestone_or_plan")),
        ),
        "blocked_task_id": _first_non_empty(
            _as_text(latest_failure.get("blocked_task_id")),
            _as_text(latest_failure.get("task_id")),
            _as_text(latest_failure_meta.get("blocked_task_id")),
            _as_text(latest_failure_meta.get("task_id")),
            _blocked_task_id_from_failure(latest_failure, latest_failure_meta),
            _as_text(signature.get("blocked_task_id")),
        ),
        "target_fingerprint": _first_non_empty(
            _as_text(target_plan_state.get("fingerprint")),
            _as_text(_as_mapping(target_payload.get("chain_state")).get("fingerprint")),
            _as_text(signature.get("target_fingerprint")),
        ),
    }
    return normalize_blocker_fingerprint_v1(payload)


def _blocked_task_id_from_failure(
    latest_failure: Mapping[str, Any],
    latest_failure_meta: Mapping[str, Any],
) -> str:
    for key in ("blocked_task_ids", "task_ids"):
        values = _as_list(latest_failure_meta.get(key))
        for value in values:
            task_id = _as_scalar_text(value)
            if task_id:
                return task_id

    candidate_texts = [
        _as_text(latest_failure.get("message")),
        _as_text(latest_failure_meta.get("blocking_reason")),
    ]
    candidate_texts.extend(_as_text(value) for value in _as_list(latest_failure_meta.get("blocking_reasons")))
    for text in candidate_texts:
        match = re.search(r"\btask\s+([A-Z]+[0-9]+)\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return ""


def project_repair_custody(
    *,
    plan_state: Mapping[str, Any] | None = None,
    current_target: Mapping[str, Any] | None = None,
    canonical_run_state: CanonicalRunState | None = None,
    queue_root: str | Path | None = None,
    marker_dir: str | Path | None = None,
    queue_dir: str | Path | None = None,
    repair_data_dir: str | Path | None = None,
    sidecar_dir: str | Path | None = None,
) -> RepairCustodyProjection:
    """Project plan, queue, and repair-data artifacts into one custody view."""

    from arnold_pipelines.megaplan.cloud import repair_requests
    from arnold_pipelines.megaplan.cloud.feature_flags import resolver_observe_enabled
    from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state

    plan_payload = _as_mapping(plan_state)
    target_payload = _as_mapping(current_target)
    queue_candidates = [
        Path(value)
        for value in (queue_root, queue_dir)
        if value is not None
    ]
    if marker_dir is not None:
        queue_candidates.append(repair_requests.repair_queue_dir(marker_dir))
    validated_queue_root: Path | None = None
    if queue_candidates:
        validated_candidates = {
            repair_requests.validate_queue_root(candidate)
            for candidate in queue_candidates
        }
        if len(validated_candidates) != 1:
            raise ValueError("conflicting repair queue roots")
        validated_queue_root = validated_candidates.pop()

    queue_requests = (
        repair_requests.iter_repair_requests(validated_queue_root)
        if validated_queue_root is not None
        else []
    )
    queue_decisions = (
        repair_requests.iter_repair_decisions(validated_queue_root)
        if validated_queue_root is not None
        else []
    )
    decision_history = _decision_history_by_request(queue_decisions)

    fingerprint = blocker_fingerprint_from_evidence(plan_state=plan_payload, current_target=target_payload)
    blocker_id = blocker_id_for_fingerprint(fingerprint)
    target_session = _first_non_empty(
        _as_text(target_payload.get("target_session")),
        _as_text(_as_mapping(target_payload.get("marker")).get("session")),
        _as_text(target_payload.get("session")),
    )
    target_current_refs = _as_mapping(target_payload.get("current_refs"))
    current_plan_identity = _first_non_empty(
        _as_text(target_current_refs.get("current_plan_name")),
        _as_text(target_current_refs.get("chain_current_plan_name")),
        _as_text(target_current_refs.get("marker_plan_name")),
    )
    current_repair_identity = repair_requests.derive_repair_identity(
        session=target_session,
        plan_state=plan_payload,
        current_target=target_payload,
        blocker_id=blocker_id or "",
        blocker_fingerprint=fingerprint,
    )
    current_repair_identity_key = repair_requests.repair_identity_key(current_repair_identity)
    exact_identity_required = repair_requests.exact_repair_identity_available(
        plan_state=plan_payload,
        current_target=target_payload,
    )

    requests: list[RepairCustodyRequestRecord] = []
    for record in queue_requests:
        request_session = _as_text(record.get("session"))
        if target_session and request_session and request_session != target_session:
            continue
        problem_signature = _stable_mapping(_as_mapping(record.get("problem_signature")))
        request_target = deepcopy(target_payload)
        request_target_refs = _stable_mapping(_as_mapping(request_target.get("current_refs")))
        request_target_record = _stable_mapping(_as_mapping(record.get("target")))
        request_plan_identity = _first_non_empty(
            _as_text(request_target_record.get("plan_name")),
            _as_text(problem_signature.get("milestone_or_plan")),
        )
        if request_plan_identity:
            request_target_refs["current_plan_name"] = request_plan_identity
            request_target_refs["chain_current_plan_name"] = request_plan_identity
        signature_state = _as_text(problem_signature.get("current_state"))
        if signature_state:
            request_target_refs["plan_current_state"] = signature_state
        request_target["current_refs"] = request_target_refs
        request_plan_state: dict[str, Any] = {}
        if request_plan_identity:
            request_plan_state["name"] = request_plan_identity
        if signature_state:
            request_plan_state["current_state"] = signature_state
        signature_retry_strategy = _as_text(problem_signature.get("retry_strategy"))
        if signature_retry_strategy:
            request_plan_state["resume_cursor"] = {"retry_strategy": signature_retry_strategy}
        signature_failure_kind = _as_text(problem_signature.get("failure_kind"))
        signature_phase = _as_text(problem_signature.get("phase_or_step"))
        signature_blocked_task_id = _as_text(problem_signature.get("blocked_task_id"))
        if signature_failure_kind or signature_phase or signature_blocked_task_id:
            request_plan_state["latest_failure"] = {
                "kind": signature_failure_kind,
                "phase": signature_phase,
                "metadata": {"blocked_task_id": signature_blocked_task_id},
            }
        request_fingerprint = blocker_fingerprint_from_evidence(
            plan_state=request_plan_state,
            current_target=request_target,
            problem_signature=problem_signature,
        )
        request_blocker_id = blocker_id_for_fingerprint(request_fingerprint) or ""
        request_repair_identity = repair_requests.normalize_repair_identity(
            _as_mapping(record.get("repair_identity"))
        )
        request_repair_identity_key = repair_requests.repair_identity_key(request_repair_identity)
        if (
            exact_identity_required
            and current_repair_identity_key
            and request_repair_identity_key != current_repair_identity_key
        ):
            continue
        if blocker_id and request_blocker_id and request_blocker_id != blocker_id:
            continue
        if not blocker_id and current_plan_identity and request_plan_identity and request_plan_identity != current_plan_identity:
            continue
        if blocker_id is None and request_blocker_id and blocker_id != request_blocker_id:
            blocker_id = request_blocker_id
            fingerprint = request_fingerprint
        history = decision_history.get(str(record.get("request_id") or ""), [])
        latest_decision = _effective_request_decision(history)
        status = (
            str(latest_decision["decision"])
            if latest_decision is not None
            else REQUEST_STATUS_ACCEPTED
        )
        requests.append(
            {
                "request_id": _as_text(record.get("request_id")),
                "session": _as_text(record.get("session")),
                "source": _as_text(record.get("source")),
                "path": _as_text(record.get("_path")),
                "blocker_id": request_blocker_id,
                "blocker_fingerprint": request_fingerprint,
                "problem_signature": problem_signature,
                "target": _stable_mapping(_as_mapping(record.get("target"))),
                "repair_identity": request_repair_identity or {},
                "repair_identity_key": request_repair_identity_key,
                "status": status,
                "active": status in {REQUEST_STATUS_ACCEPTED, REQUEST_STATUS_DISPATCHED},
                "decision": latest_decision,
                "decision_history": history,
            }
        )

    attempts = _collect_custody_attempts(
        repair_data_dir=repair_data_dir,
        sidecar_dir=sidecar_dir,
        blocker_id=blocker_id or "",
        fingerprint=fingerprint,
        target_session=target_session,
    )

    active_request_ids = sorted(
        request["request_id"] for request in requests if request["active"] and request["request_id"]
    )
    if validated_queue_root is not None:
        for record in repair_requests.iter_repair_attempts(validated_queue_root):
            request_id = _as_text(record.get("request_id"))
            record_blocker_id = _as_text(record.get("blocker_id"))
            if request_id not in active_request_ids:
                continue
            if blocker_id and record_blocker_id != blocker_id:
                continue
            state, outcome, recorded_at, raw = _queue_dispatch_attempt_observation(record)
            attempts.append(
                _build_attempt_record(
                    attempt_id=_as_text(record.get("attempt_id")),
                    session=target_session,
                    source="repair_queue_dispatch_attempt",
                    path=_as_text(record.get("_path")),
                    blocker_id=record_blocker_id,
                    fingerprint=fingerprint,
                    request_id=request_id,
                    state=state,
                    outcome=outcome,
                    recorded_at=recorded_at,
                    raw=raw,
                    repair_identity=_as_mapping(record.get("repair_identity")),
                )
            )
    active_claim_request_ids: list[str] = []
    if validated_queue_root is not None and blocker_id:
        claim_path = repair_requests.active_repair_claim_lock_dir(
            validated_queue_root, blocker_id
        ) / "owner.json"
        claim_owner = load_json(claim_path, default={})
        if isinstance(claim_owner, Mapping):
            claim_owner_identity_key = _as_text(claim_owner.get("repair_identity_key"))
            claim_request_id = _as_text(claim_owner.get("request_id"))
            if claim_request_id and (
                not exact_identity_required
                or not current_repair_identity_key
                or claim_owner_identity_key == current_repair_identity_key
            ):
                active_claim_request_ids.append(claim_request_id)
    attempts = [
        attempt
        for attempt in attempts
        if _attempt_has_current_custody(
            attempt,
            active_request_ids=set(active_request_ids),
            blocker_id=blocker_id or "",
            repair_identity_key=current_repair_identity_key,
            exact_identity_required=exact_identity_required,
        )
    ]
    attempted_request_ids = {
        attempt["request_id"] for attempt in attempts if attempt["request_id"]
    }
    accepted_unclaimed_request_ids = sorted(
        request_id
        for request_id in active_request_ids
        if request_id not in attempted_request_ids
        and request_id not in active_claim_request_ids
    )
    request_status_counts: dict[str, int] = {}
    for request in requests:
        status = str(request["status"])
        request_status_counts[status] = int(request_status_counts.get(status, 0)) + 1
    claim_retry_counts = {
        request_id: sum(item["decision"] == "claim_retry" for item in history)
        for request_id, history in decision_history.items()
        if any(item["decision"] == "claim_retry" for item in history)
    }
    claim_alert_request_ids = sorted(
        request_id
        for request_id, history in decision_history.items()
        if any(item["decision"] == "claim_alert" for item in history)
    )
    terminal_outcomes = sorted(
        {
            attempt["outcome"]
            for attempt in attempts
            if attempt["terminal"] and attempt["outcome"]
        }
    )

    has_active_custody = durable_repair_active(
        {
            "attempts": attempts,
            "active_request_ids": active_request_ids,
            "active_claim_request_ids": active_claim_request_ids,
        }
    )
    if has_active_custody:
        bucket = CUSTODY_BUCKET_REPAIRING
    elif active_request_ids:
        bucket = CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    elif canonical_run_state is not None:
        bucket = _custody_bucket_from_canonical_state(canonical_run_state)
    else:
        current_state = _as_text(plan_payload.get("current_state"))
        retry_strategy = _as_text(_as_mapping(plan_payload.get("resume_cursor")).get("retry_strategy"))
        if current_state == "blocked" and retry_strategy == "manual_review":
            bucket = CUSTODY_BUCKET_HUMAN_REQUIRED
        else:
            bucket = CUSTODY_BUCKET_BROKEN_SUPERFIXER

    failure_payload = _as_mapping(plan_payload.get("latest_failure"))
    failure_kind = _as_text(failure_payload.get("kind"))
    max_attempts = 1 if failure_kind in {
        "quality_gate_blocked",
        "deterministic_quality_blocked",
    } else 3
    used_attempts = len(attempts)
    remaining_attempts = max(0, max_attempts - used_attempts)
    evidence_cursor = _as_mapping(failure_payload.get("evidence_cursor"))
    if not evidence_cursor:
        evidence_cursor = _as_mapping(
            _as_mapping(failure_payload.get("metadata")).get("evidence_cursor")
        )

    projection: dict[str, Any] = {
        "blocker_id": blocker_id or "",
        "blocker_fingerprint": fingerprint,
        "custody_bucket": bucket,
        "current_state": _as_text(plan_payload.get("current_state")),
        "retry_strategy": _as_text(_as_mapping(plan_payload.get("resume_cursor")).get("retry_strategy")),
        "failure_kind": failure_kind,
        "request_status_counts": request_status_counts,
        "claim_retry_counts": claim_retry_counts,
        "claim_alert_request_ids": claim_alert_request_ids,
        "active_request_ids": active_request_ids,
        "active_claim_request_ids": active_claim_request_ids,
        "accepted_unclaimed_request_ids": accepted_unclaimed_request_ids,
        "request_count": len(requests),
        "claim_count": len(active_claim_request_ids),
        "attempt_count": len(attempts),
        "retry_budget": {
            "max_attempts": max_attempts,
            "used_attempts": used_attempts,
            "remaining_attempts": remaining_attempts,
            "retryable": bool(accepted_unclaimed_request_ids and remaining_attempts > 0),
            "alert_required": bool(accepted_unclaimed_request_ids and remaining_attempts == 0),
            "claim_max_retries": 3,
            "claim_retries_used": max(
                (claim_retry_counts.get(request_id, 0) for request_id in active_request_ids),
                default=0,
            ),
            "claim_alerted": any(
                request_id in claim_alert_request_ids for request_id in active_request_ids
            ),
        },
        "evidence_cursor": dict(evidence_cursor),
        "terminal_outcomes": terminal_outcomes,
        "requests": requests,
        "attempts": attempts,
        "plan_state": dict(plan_payload),
        "current_target": dict(target_payload),
    }

    observed_canonical = canonical_run_state
    if observed_canonical is None and resolver_observe_enabled() and target_payload:
        observed_canonical = resolve_run_state(target_payload)
    if resolver_observe_enabled() and observed_canonical is not None:
        projection["canonical_state"] = observed_canonical.canonical_state.name
        projection["canonical_reason"] = observed_canonical.reason
        projection["canonical_human_required"] = observed_canonical.human_required
        projection["canonical_human_gate"] = (
            observed_canonical.human_gate.name if observed_canonical.human_gate is not None else None
        )
        projection["canonical_resolver"] = observed_canonical.to_dict()

    return projection


def _custody_bucket_from_canonical_state(
    canonical_run_state: CanonicalRunState,
) -> RepairCustodyBucket:
    state = canonical_run_state.canonical_state
    if state is CanonicalState.REPAIRING:
        # The resolver's REPAIRING state can be derived from an advisory legacy
        # sidecar.  Only a current, durable attempt projected above owns repair
        # custody; canonical classification alone must never advertise a launch.
        return CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    if state in {
        CanonicalState.REAL_IMPLEMENTATION_BLOCK,
        CanonicalState.RETRYABLE_EXECUTION_BLOCK,
    }:
        return CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING
    if state is CanonicalState.HUMAN_ACTION_REQUIRED:
        return CUSTODY_BUCKET_HUMAN_REQUIRED
    if state is CanonicalState.PAUSED:
        return CUSTODY_BUCKET_PAUSED
    return CUSTODY_BUCKET_BROKEN_SUPERFIXER


def classify_repair_dispatch(
    *,
    canonical_run_state: CanonicalRunState | None = None,
    event_plan_dir: Path | None = None,
    plan_state: Mapping[str, Any] | None = None,
    retry_strategy: str = "",
    latest_failure: Mapping[str, Any] | None = None,
    current_target: Mapping[str, Any] | None = None,
    human_blocker_classification: Any = None,
    lock_evidence: Any = None,
    process_evidence: Mapping[str, Any] | None = None,
    custody_projection: Mapping[str, Any] | None = None,
    recovery_view: Mapping[str, Any] | None = None,
    semantic_findings: list[Any] | None = None,
) -> RepairDispatchDecision:
    """Classify one repair dispatch decision from shared custody evidence.

    When *recovery_view* is provided (as a ``MegaplanRecoveryView`` dict or
    compatible mapping), its custody-bucket and permitted-action classification
    is preferred.  Legacy *custody_projection* remains a fallback and drift
    diagnostics are emitted when the two disagree.

    When *semantic_findings* is provided and ``latest_failure`` is absent,
    semantic-health findings are used as a fallback to decide whether a
    repairable issue exists.  This enables dispatch for boundary-evidence
    gaps that do not manifest as a plan-level failure.

    Conservative defaults apply: unknown or ambiguous blocker shapes never
    auto-dispatch. L1 dispatch is reserved for blocked/manual_review states
    whose failure kind is known to be implementation-repairable.
    """

    plan_payload = _as_mapping(plan_state)
    failure_payload = _as_mapping(latest_failure or plan_payload.get("latest_failure"))
    target_payload = _as_mapping(current_target)
    custody = _as_mapping(custody_projection)
    recovery = _as_mapping(recovery_view)

    normalized_retry_strategy = _first_non_empty(
        _as_text(retry_strategy),
        _as_text(_as_mapping(plan_payload.get("resume_cursor")).get("retry_strategy")),
        _as_text(_as_mapping(custody.get("plan_state")).get("resume_cursor")),
    )
    current_state = _first_non_empty(
        _as_text(plan_payload.get("current_state")),
        _as_text(_as_mapping(custody.get("plan_state")).get("current_state")),
    )
    failure_kind = _first_non_empty(
        _as_text(failure_payload.get("kind")),
        _as_text(custody.get("failure_kind")),
    )
    blocker_id = _as_text(custody.get("blocker_id"))
    active_request_ids = [
        value for value in (_as_list(custody.get("active_request_ids")) if custody else []) if _as_text(value)
    ]
    request_id = _as_text(active_request_ids[0]) if active_request_ids else ""
    custody_bucket = _as_text(custody.get("custody_bucket"))
    terminal_outcomes = [
        value for value in (_as_list(custody.get("terminal_outcomes")) if custody else []) if _as_text(value)
    ]

    # --- recovery-view preferred path -----------------------------------------
    if recovery:
        recovery_decision = _classify_from_recovery_view(
            recovery=recovery,
            custody=custody,
            custody_bucket=custody_bucket,
            blocker_id=blocker_id,
            request_id=request_id,
            current_state=current_state,
            retry_strategy=normalized_retry_strategy,
            failure_kind=failure_kind,
            event_plan_dir=event_plan_dir,
            target_payload=target_payload,
            human_blocker_classification=human_blocker_classification,
            lock_evidence=lock_evidence,
            process_evidence=process_evidence,
            terminal_outcomes=terminal_outcomes,
            semantic_findings=semantic_findings,
        )
        # cross-check: if canonical_run_state is also present and disagrees,
        # emit a drift diagnostic capturing recovery-vs-canonical divergence.
        if canonical_run_state is not None and event_plan_dir is not None:
            canonical_decision = _classify_repair_dispatch_canonical(
                canonical_run_state=canonical_run_state,
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=normalized_retry_strategy,
                failure_kind=failure_kind,
                lock_evidence=lock_evidence,
                process_evidence=process_evidence,
                custody=custody,
                current_target=target_payload,
                semantic_findings=semantic_findings,
            )
            _emit_dispatch_drift_detected(
                event_plan_dir=event_plan_dir,
                canonical_run_state=canonical_run_state,
                canonical_decision=canonical_decision,
                legacy_decision=recovery_decision,
            )
        return recovery_decision

    if canonical_run_state is not None:
        canonical_decision = _classify_repair_dispatch_canonical(
            canonical_run_state=canonical_run_state,
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=normalized_retry_strategy,
            failure_kind=failure_kind,
            lock_evidence=lock_evidence,
            process_evidence=process_evidence,
            custody=custody,
            current_target=target_payload,
            semantic_findings=semantic_findings,
        )
        if event_plan_dir is not None:
            legacy_decision = _classify_repair_dispatch_legacy(
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=normalized_retry_strategy,
                failure_kind=failure_kind,
                current_target=target_payload,
                human_blocker_classification=human_blocker_classification,
                lock_evidence=lock_evidence,
                process_evidence=process_evidence,
                custody=custody,
                terminal_outcomes=terminal_outcomes,
                semantic_findings=semantic_findings,
            )
            _emit_dispatch_drift_detected(
                event_plan_dir=event_plan_dir,
                canonical_run_state=canonical_run_state,
                canonical_decision=canonical_decision,
                legacy_decision=legacy_decision,
            )
        return canonical_decision

    if event_plan_dir is not None:
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_BROKEN_SUPERFIXER,
            dispatch_intent=DISPATCH_INTENT_BROKEN_SUPERFIXER,
            rationale=("canonical provenance missing; refusing legacy dispatch fallback",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=normalized_retry_strategy,
            failure_kind=failure_kind,
        )

    return _classify_repair_dispatch_legacy(
        blocker_id=blocker_id,
        request_id=request_id,
        custody_bucket=custody_bucket,
        current_state=current_state,
        retry_strategy=normalized_retry_strategy,
        failure_kind=failure_kind,
        current_target=target_payload,
        human_blocker_classification=human_blocker_classification,
        lock_evidence=lock_evidence,
        process_evidence=process_evidence,
        custody=custody,
        terminal_outcomes=terminal_outcomes,
        semantic_findings=semantic_findings,
    )


def _make_dispatch_decision(
    *,
    decision: RepairDispatchDecisionKind,
    dispatch_intent: RepairDispatchIntent,
    rationale: tuple[str, ...],
    blocker_id: str,
    request_id: str,
    custody_bucket: str,
    current_state: str,
    retry_strategy: str,
    failure_kind: str,
) -> RepairDispatchDecision:
    return RepairDispatchDecision(
        decision=decision,
        dispatch_intent=dispatch_intent,
        rationale=rationale,
        blocker_id=blocker_id,
        request_id=request_id,
        custody_bucket=custody_bucket,
        current_state=current_state,
        retry_strategy=retry_strategy,
        failure_kind=failure_kind,
    )


def _classify_repair_dispatch_canonical(
    *,
    canonical_run_state: CanonicalRunState,
    blocker_id: str,
    request_id: str,
    custody_bucket: str,
    current_state: str,
    retry_strategy: str,
    failure_kind: str,
    lock_evidence: Any,
    process_evidence: Mapping[str, Any] | None,
    custody: Mapping[str, Any],
    current_target: Mapping[str, Any],
    semantic_findings: list[Any] | None = None,
) -> RepairDispatchDecision:
    state = canonical_run_state.canonical_state
    # Derived/canonical completion must never hide current contradictory
    # ground truth (the exact finalized+active and complete+incomplete cases).
    if _has_terminality_contradiction(current_target):
        if _has_active_repair(lock_evidence=lock_evidence, process_evidence=process_evidence, custody=custody):
            return _make_dispatch_decision(
                decision=DISPATCH_DECISION_REPAIRING,
                dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
                rationale=("terminality contradiction has active repair custody",),
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=retry_strategy,
                failure_kind=failure_kind,
            )
        if request_id:
            return _make_dispatch_decision(
                decision=DISPATCH_DECISION_L1,
                dispatch_intent=DISPATCH_INTENT_L1,
                rationale=("terminality contradiction reopens repair custody",),
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=retry_strategy,
                failure_kind=failure_kind,
            )
    if state is CanonicalState.COMPLETED:
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_TERMINAL,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=("resolver enforcement: canonical completed state",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state is CanonicalState.PAUSED:
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_NO_ACTION,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=("resolver enforcement: durable operator pause forbids recovery",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state is CanonicalState.RUNNING:
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_NO_ACTION,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=("resolver enforcement: canonical running state",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state is CanonicalState.REPAIRING:
        if durable_repair_active(custody):
            return _make_dispatch_decision(
                decision=DISPATCH_DECISION_REPAIRING,
                dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
                rationale=("resolver enforcement: canonical repairing state with durable custody",),
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=retry_strategy,
                failure_kind=failure_kind,
            )
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_NO_ACTION,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=("resolver repairing label has no durable repair custody",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state is CanonicalState.HUMAN_ACTION_REQUIRED:
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_HUMAN_REQUIRED,
            dispatch_intent=DISPATCH_INTENT_HUMAN_REQUIRED,
            rationale=("resolver enforcement: typed human-action-required gate",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state in {
        CanonicalState.REAL_IMPLEMENTATION_BLOCK,
        CanonicalState.RETRYABLE_EXECUTION_BLOCK,
    }:
        if _has_active_repair(lock_evidence=lock_evidence, process_evidence=process_evidence, custody=custody):
            return _make_dispatch_decision(
                decision=DISPATCH_DECISION_REPAIRING,
                dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
                rationale=("active repair ownership or runtime evidence already exists",),
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=retry_strategy,
                failure_kind=failure_kind,
            )
        if request_id:
            return _make_dispatch_decision(
                decision=DISPATCH_DECISION_L1,
                dispatch_intent=DISPATCH_INTENT_L1,
                rationale=("resolver enforcement: canonical machine-actionable block",),
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=retry_strategy,
                failure_kind=failure_kind,
            )
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_NO_ACTION,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=("resolver enforcement: canonical machine-actionable block without active request",),
            blocker_id=blocker_id,
            request_id="",
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state is CanonicalState.UNKNOWN:
        if _is_known_repairable_shape(
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
            current_target=current_target,
            semantic_findings=semantic_findings,
        ):
            if _has_active_repair(lock_evidence=lock_evidence, process_evidence=process_evidence, custody=custody):
                return _make_dispatch_decision(
                    decision=DISPATCH_DECISION_REPAIRING,
                    dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
                    rationale=(
                        "resolver enforcement: canonical unknown but known repairable shape already has active repair",
                    ),
                    blocker_id=blocker_id,
                    request_id=request_id,
                    custody_bucket=custody_bucket,
                    current_state=current_state,
                    retry_strategy=retry_strategy,
                    failure_kind=failure_kind,
                )
            if request_id:
                return _make_dispatch_decision(
                    decision=DISPATCH_DECISION_L1,
                    dispatch_intent=DISPATCH_INTENT_L1,
                    rationale=(
                        "resolver enforcement: canonical unknown but legacy evidence proves known repairable shape",
                    ),
                    blocker_id=blocker_id,
                    request_id=request_id,
                    custody_bucket=custody_bucket,
                    current_state=current_state,
                    retry_strategy=retry_strategy,
                    failure_kind=failure_kind,
                )
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_BROKEN_SUPERFIXER,
            dispatch_intent=DISPATCH_INTENT_BROKEN_SUPERFIXER,
            rationale=("resolver enforcement: canonical unknown escalation",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if state in {
        CanonicalState.BROKEN_STATE_MACHINE,
        CanonicalState.STALE_DERIVED_STATE,
    }:
        state_label = state.name.lower().replace("_", "-")
        return _make_dispatch_decision(
            decision=DISPATCH_DECISION_BROKEN_SUPERFIXER,
            dispatch_intent=DISPATCH_INTENT_BROKEN_SUPERFIXER,
            rationale=(f"resolver enforcement: canonical {state_label} escalation",),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    return _make_dispatch_decision(
        decision=DISPATCH_DECISION_BROKEN_SUPERFIXER,
        dispatch_intent=DISPATCH_INTENT_BROKEN_SUPERFIXER,
        rationale=("resolver enforcement: unrecognized canonical state",),
        blocker_id=blocker_id,
        request_id=request_id,
        custody_bucket=custody_bucket,
        current_state=current_state,
        retry_strategy=retry_strategy,
        failure_kind=failure_kind,
    )


def _classify_repair_dispatch_legacy(
    *,
    blocker_id: str,
    request_id: str,
    custody_bucket: str,
    current_state: str,
    retry_strategy: str,
    failure_kind: str,
    current_target: Mapping[str, Any],
    human_blocker_classification: Any,
    lock_evidence: Any,
    process_evidence: Mapping[str, Any] | None,
    custody: Mapping[str, Any],
    terminal_outcomes: list[Any],
    semantic_findings: list[Any] | None = None,
) -> RepairDispatchDecision:
    known_repairable = _is_known_repairable_shape(
        current_state=current_state,
        retry_strategy=retry_strategy,
        failure_kind=failure_kind,
        current_target=current_target,
        semantic_findings=semantic_findings,
    )

    rationale: list[str] = []

    if _is_terminal_dispatch_state(current_state, terminal_outcomes) and not known_repairable:
        rationale.append("plan or repair evidence is terminal")
        return RepairDispatchDecision(
            decision=DISPATCH_DECISION_TERMINAL,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=tuple(rationale),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )

    human_gate = _human_blocker_dispatch_gate(human_blocker_classification)
    if human_gate == DISPATCH_INTENT_HUMAN_REQUIRED:
        rationale.append("human-blocker classification gates repair dispatch")
        return RepairDispatchDecision(
            decision=DISPATCH_DECISION_HUMAN_REQUIRED,
            dispatch_intent=DISPATCH_INTENT_HUMAN_REQUIRED,
            rationale=tuple(rationale),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )
    if human_gate == DISPATCH_INTENT_BROKEN_SUPERFIXER:
        rationale.append("mechanical or contradictory needs-human evidence blocks dispatch")
        return RepairDispatchDecision(
            decision=DISPATCH_DECISION_BROKEN_SUPERFIXER,
            dispatch_intent=DISPATCH_INTENT_BROKEN_SUPERFIXER,
            rationale=tuple(rationale),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )

    if _has_active_repair(lock_evidence=lock_evidence, process_evidence=process_evidence, custody=custody):
        rationale.append("active repair ownership or runtime evidence already exists")
        return RepairDispatchDecision(
            decision=DISPATCH_DECISION_REPAIRING,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=tuple(rationale),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )

    if known_repairable:
        if request_id:
            rationale.append("known repairable blocker has active custody and no competing owner")
            return RepairDispatchDecision(
                decision=DISPATCH_DECISION_L1,
                dispatch_intent=DISPATCH_INTENT_L1,
                rationale=tuple(rationale),
                blocker_id=blocker_id,
                request_id=request_id,
                custody_bucket=custody_bucket,
                current_state=current_state,
                retry_strategy=retry_strategy,
                failure_kind=failure_kind,
            )
        rationale.append("known repairable blocker lacks an active request to dispatch")
        return RepairDispatchDecision(
            decision=DISPATCH_DECISION_NO_ACTION,
            dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY,
            rationale=tuple(rationale),
            blocker_id=blocker_id,
            request_id="",
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )

    if current_state == "blocked" or retry_strategy == "manual_review":
        rationale.append("blocked or manual-review state is not a whitelisted repairable shape")
        return RepairDispatchDecision(
            decision=DISPATCH_DECISION_HUMAN_REQUIRED,
            dispatch_intent=DISPATCH_INTENT_HUMAN_REQUIRED,
            rationale=tuple(rationale),
            blocker_id=blocker_id,
            request_id=request_id,
            custody_bucket=custody_bucket,
            current_state=current_state,
            retry_strategy=retry_strategy,
            failure_kind=failure_kind,
        )

    rationale.append("state and evidence do not map to a safe repair dispatch policy")
    return RepairDispatchDecision(
        decision=DISPATCH_DECISION_BROKEN_SUPERFIXER,
        dispatch_intent=DISPATCH_INTENT_BROKEN_SUPERFIXER,
        rationale=tuple(rationale),
        blocker_id=blocker_id,
        request_id=request_id,
        custody_bucket=custody_bucket,
        current_state=current_state,
        retry_strategy=retry_strategy,
        failure_kind=failure_kind,
    )


def _emit_dispatch_drift_detected(
    *,
    event_plan_dir: Path,
    canonical_run_state: CanonicalRunState,
    canonical_decision: RepairDispatchDecision,
    legacy_decision: RepairDispatchDecision,
) -> None:
    if (
        canonical_decision.decision == legacy_decision.decision
        and canonical_decision.dispatch_intent == legacy_decision.dispatch_intent
    ):
        return
    payload = {
        "what": "repair_contract.dispatch_decision",
        "expected": canonical_decision.decision,
        "actual": legacy_decision.decision,
        "canonical_state": canonical_run_state.canonical_state.name,
        "legacy_label": legacy_decision.decision,
        "canonical_dispatch_intent": canonical_decision.dispatch_intent,
        "legacy_dispatch_intent": legacy_decision.dispatch_intent,
        "stale_sources": list(canonical_run_state.stale_sources),
    }
    try:
        emit(EventKind.DRIFT_DETECTED, event_plan_dir, payload=payload)
    except Exception:
        return


def _classify_from_recovery_view(
    *,
    recovery: Mapping[str, Any],
    custody: Mapping[str, Any],
    custody_bucket: str,
    blocker_id: str,
    request_id: str,
    current_state: str,
    retry_strategy: str,
    failure_kind: str,
    event_plan_dir: Path | None,
    target_payload: Mapping[str, Any],
    human_blocker_classification: Any,
    lock_evidence: Any,
    process_evidence: Mapping[str, Any] | None,
    terminal_outcomes: list[Any],
    semantic_findings: list[Any] | None = None,
) -> RepairDispatchDecision:
    """Derive dispatch from a recovery-view dict, preferring its custody and
    permitted actions over raw legacy projection fields.

    Recovery-view custody and permitted-action classification is the preferred
    input.  Legacy custody is consulted only for drift diagnostics and field
    fallback when the recovery view omits a value.
    """

    recovery_custody_bucket = _as_text(recovery.get("custody_bucket")) or custody_bucket
    recovery_status = _as_text(recovery.get("status")) or "unknown"
    recovery_needed = bool(recovery.get("recovery_needed", True))
    permitted_actions_raw = recovery.get("permitted_actions")
    if not isinstance(permitted_actions_raw, (list, tuple)):
        permitted_actions_raw = ()
    permitted_actions: list[dict[str, Any]] = [
        _as_mapping(item) for item in permitted_actions_raw if isinstance(item, Mapping)
    ]
    recovery_diagnostics_raw = recovery.get("diagnostics")
    if not isinstance(recovery_diagnostics_raw, (list, tuple)):
        recovery_diagnostics_raw = ()

    # --- drift diagnostic: legacy custody bucket vs recovery-view custody -----
    if custody and custody_bucket and recovery_custody_bucket != custody_bucket:
        if event_plan_dir is not None:
            _emit_recovery_legacy_custody_drift(
                event_plan_dir=event_plan_dir,
                legacy_custody_bucket=custody_bucket,
                recovery_custody_bucket=recovery_custody_bucket,
                recovery_status=recovery_status,
            )

    # --- map recovery-view custody to dispatch decision -----------------------
    rationale: list[str] = []
    # Prefer recovery-view custody bucket for dispatch derivation.
    if recovery_custody_bucket == "repairing":
        decision = DISPATCH_DECISION_REPAIRING
        dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
        rationale.append("recovery view: repair already in progress")
    elif recovery_custody_bucket == "repairable" or recovery_custody_bucket == "repairable_not_repairing":
        if request_id and not blocker_id:
            decision = DISPATCH_DECISION_BROKEN_SUPERFIXER
            dispatch_intent = DISPATCH_INTENT_BROKEN_SUPERFIXER
            rationale.append(
                "recovery view: active request/blocker identity is incomplete; refusing L1"
            )
        # Check active repair using lock/process evidence only (NOT legacy custody,
        # which may disagree with the recovery view).  The recovery view already
        # classified this as repairable; do not let a stale legacy custody bucket
        # override that classification.
        elif lock_evidence is not None or process_evidence is not None:
            if _has_active_repair(
                lock_evidence=lock_evidence,
                process_evidence=process_evidence,
                custody=custody,
            ):
                decision = DISPATCH_DECISION_REPAIRING
                dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
                rationale.append("recovery view: repairable but active repair ownership exists")
            elif request_id:
                decision = DISPATCH_DECISION_L1
                dispatch_intent = DISPATCH_INTENT_L1
                rationale.append("recovery view: repairable custody with active request")
            else:
                decision = DISPATCH_DECISION_NO_ACTION
                dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
                rationale.append("recovery view: repairable but no active repair request")
        elif request_id:
            decision = DISPATCH_DECISION_L1
            dispatch_intent = DISPATCH_INTENT_L1
            rationale.append("recovery view: repairable custody with active request")
        else:
            decision = DISPATCH_DECISION_NO_ACTION
            dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
            rationale.append("recovery view: repairable but no active repair request")
    elif recovery_custody_bucket == "human_required":
        decision = DISPATCH_DECISION_HUMAN_REQUIRED
        dispatch_intent = DISPATCH_INTENT_HUMAN_REQUIRED
        rationale.append("recovery view: human intervention required")
    elif recovery_custody_bucket == "broken_superfixer":
        decision = DISPATCH_DECISION_BROKEN_SUPERFIXER
        dispatch_intent = DISPATCH_INTENT_BROKEN_SUPERFIXER
        rationale.append("recovery view: superfixer is broken")
    elif recovery_custody_bucket == "healthy":
        if _is_terminal_dispatch_state(current_state, terminal_outcomes):
            decision = DISPATCH_DECISION_TERMINAL
            dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
            rationale.append("recovery view: healthy and terminal")
        else:
            decision = DISPATCH_DECISION_NO_ACTION
            dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
            rationale.append("recovery view: healthy; no recovery needed")
    elif recovery_custody_bucket == "blocked":
        if recovery_needed:
            decision = DISPATCH_DECISION_BROKEN_SUPERFIXER
            dispatch_intent = DISPATCH_INTENT_BROKEN_SUPERFIXER
            rationale.append(
                "recovery view: blocked without typed human authority; superfixer investigation required"
            )
        else:
            decision = DISPATCH_DECISION_NO_ACTION
            dispatch_intent = DISPATCH_INTENT_QUEUE_ONLY
            rationale.append("recovery view: blocked but recovery not needed")
    else:
        # unknown or unrecognized — fall back conservatively
        decision = DISPATCH_DECISION_BROKEN_SUPERFIXER
        dispatch_intent = DISPATCH_INTENT_BROKEN_SUPERFIXER
        rationale.append(
            f"recovery view: unrecognized custody bucket {recovery_custody_bucket!r}; "
            "escalating to superfixer"
        )

    # --- incorporate permitted-action hints from the recovery view ------------
    if permitted_actions:
        action_types = {_as_text(item.get("action_type")) for item in permitted_actions}
        # If recovery view explicitly permits repair_dispatch, upgrade
        # queue_only → dispatch_l1 when we have a request_id.
        if "repair_dispatch" in action_types and decision == DISPATCH_DECISION_NO_ACTION and request_id:
            decision = DISPATCH_DECISION_L1
            dispatch_intent = DISPATCH_INTENT_L1
            rationale.append("recovery view: permitted repair_dispatch overrides no_action")
        if "human_escalation" in action_types and decision not in {
            DISPATCH_DECISION_HUMAN_REQUIRED,
            DISPATCH_DECISION_BROKEN_SUPERFIXER,
        }:
            # human_escalation permitted but not yet the decision: keep as
            # diagnostic but do not downgrade an L1 dispatch.
            if decision != DISPATCH_DECISION_L1:
                rationale.append("recovery view: human_escalation also permitted")
        if "investigate_superfixer" in action_types:
            if decision not in {
                DISPATCH_DECISION_BROKEN_SUPERFIXER,
                DISPATCH_DECISION_HUMAN_REQUIRED,
            }:
                rationale.append("recovery view: superfixer investigation recommended")

    # --- append recovery diagnostics to rationale when informative ------------
    recovery_diag_codes = {
        _as_text(_as_mapping(item).get("code"))
        for item in recovery_diagnostics_raw
        if isinstance(item, Mapping)
    }
    if recovery_diag_codes:
        rationale.append(
            "recovery view diagnostics: " + ", ".join(sorted(recovery_diag_codes))
        )

    return _make_dispatch_decision(
        decision=decision,
        dispatch_intent=dispatch_intent,
        rationale=tuple(rationale),
        blocker_id=blocker_id,
        request_id=request_id,
        custody_bucket=recovery_custody_bucket,
        current_state=current_state,
        retry_strategy=retry_strategy,
        failure_kind=failure_kind,
    )


def _emit_recovery_legacy_custody_drift(
    *,
    event_plan_dir: Path,
    legacy_custody_bucket: str,
    recovery_custody_bucket: str,
    recovery_status: str,
) -> None:
    """Emit a drift event when legacy custody disagrees with recovery view."""
    payload = {
        "what": "repair_contract.recovery_vs_legacy_custody_drift",
        "legacy_custody_bucket": legacy_custody_bucket,
        "recovery_custody_bucket": recovery_custody_bucket,
        "recovery_status": recovery_status,
    }
    try:
        emit(EventKind.DRIFT_DETECTED, event_plan_dir, payload=payload)
    except Exception:
        return


def load_json(path: str | Path, *, default: Any | None = None) -> Any:
    """Load JSON from *path*, returning *default* for missing or invalid files."""

    target = Path(path)
    fallback = {} if default is None else deepcopy(default)
    try:
        return validate_repair_data(target)
    except ValueError:
        return fallback


def atomic_write_json(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    include_resident_provenance: bool = True,
) -> None:
    """Atomically write JSON using the shared fsync/replace runtime primitive.

    Resident provenance is additive for durable repair evidence, but callers
    that persist an identity token (for example a lock owner record) must opt
    out so the on-disk value remains byte-for-byte equivalent to the identity
    they later use for guarded release.
    """

    prepared = dict(payload)
    if include_resident_provenance:
        from arnold_pipelines.megaplan.resident.provenance import safe_provenance_projection

        resident_delegation = safe_provenance_projection()
        if resident_delegation is not None:
            prepared.setdefault("resident_delegation", resident_delegation)
    _atomic_write_json(Path(path), prepared)


def read_repair_index(path: str | Path) -> dict[str, Any]:
    """Strictly read and validate a repair index JSON file."""

    return validate_repair_index(path)


def load_repair_index(path: str | Path, *, default: Any | None = None) -> dict[str, Any]:
    """Load a repair index JSON file, returning *default* when unreadable."""

    fallback = _normalize_repair_index(default or {})
    try:
        return validate_repair_index(path)
    except ValueError:
        return fallback


def validate_repair_data(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Validate repair-data payloads while preserving legacy keys and shapes."""

    payload = _coerce_payload(payload_or_path)
    validated = deepcopy(payload)
    schema_version = validated.get("schema_version", 0)
    if not isinstance(schema_version, int) or schema_version < 0:
        raise ValueError("repair-data schema_version must be a non-negative integer")
    for field in _LIST_FIELDS:
        if field in validated and not isinstance(validated[field], list):
            raise ValueError(f"repair-data field {field!r} must be a list")
    for field in _DICT_FIELDS:
        if field in validated and not isinstance(validated[field], dict):
            raise ValueError(f"repair-data field {field!r} must be an object")
    if "outcome" in validated and not isinstance(validated["outcome"], str):
        raise ValueError("repair-data field 'outcome' must be a string")
    return validated


def ensure_additive_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a validated copy with the additive M1 contract fields present."""

    updated = validate_repair_data(payload)
    for field, default in ADDITIVE_FIELD_DEFAULTS.items():
        if field not in updated:
            updated[field] = deepcopy(default)
    return updated


def merge_additive_fields(payload: Mapping[str, Any], **updates: Any) -> dict[str, Any]:
    """Merge supported additive fields without disturbing legacy contract keys."""

    unsupported = sorted(set(updates) - set(ADDITIVE_FIELD_DEFAULTS))
    if unsupported:
        raise ValueError(f"unsupported additive repair-data fields: {', '.join(unsupported)}")
    merged = ensure_additive_fields(payload)
    for field, value in updates.items():
        merged[field] = deepcopy(value)
    return validate_repair_data(merged)


def redact_repair_data(
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Recursively redact string values using the supplied hook."""

    validated = validate_repair_data(payload)
    if redactor is None:
        return canonical_redact_payload(validated)
    return _redact_value(validated, redactor)


def _encoded_json(value: Any, *, pretty: bool = False) -> bytes:
    if pretty:
        return (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode(
            "utf-8"
        )
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _is_repair_evidence_ref(value: object) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("schema_version") == REPAIR_EVIDENCE_REF_SCHEMA
        and value.get("kind") == "content_addressed_repair_evidence"
    )


def _persist_repair_evidence(
    target: Path,
    value: Any,
    *,
    field: str,
) -> dict[str, Any]:
    """Persist expanding history once and return an immutable typed pointer."""

    encoded = _encoded_json(value, pretty=True)
    digest = sha256(encoded).hexdigest()
    evidence_dir = target.parent / f"{target.stem}.evidence"
    evidence_path = evidence_dir / f"sha256-{digest}.json"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if evidence_path.exists():
        observed = evidence_path.read_bytes()
        if len(observed) != len(encoded) or sha256(observed).hexdigest() != digest:
            raise ValueError(
                f"content-addressed repair evidence disagrees: {evidence_path}"
            )
    else:
        fd, temporary_raw = tempfile.mkstemp(
            prefix=f".{evidence_path.name}.", suffix=".tmp", dir=evidence_dir
        )
        temporary = Path(temporary_raw)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, evidence_path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    return {
        "schema_version": REPAIR_EVIDENCE_REF_SCHEMA,
        "kind": "content_addressed_repair_evidence",
        "field": field,
        "path": str(evidence_path.resolve()),
        "sha256": digest,
        "size_bytes": len(encoded),
    }


def load_repair_evidence_reference(value: Mapping[str, Any]) -> Any:
    """Load a compacted evidence reference only after size and digest checks."""

    if not _is_repair_evidence_ref(value):
        raise ValueError("repair evidence reference schema is invalid")
    path = Path(str(value.get("path") or ""))
    expected_size = value.get("size_bytes")
    expected_digest = str(value.get("sha256") or "")
    if not path.is_absolute() or not isinstance(expected_size, int) or expected_size <= 0:
        raise ValueError("repair evidence reference identity is incomplete")
    encoded = path.read_bytes()
    if len(encoded) != expected_size or sha256(encoded).hexdigest() != expected_digest:
        raise ValueError("repair evidence reference content disagrees")
    return json.loads(encoded)


def _bounded_current_failure_context(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the current decision fields inline while moving an oversized blob aside."""

    allowed = (
        "failure_classification",
        "stale_state",
        "state_mismatch",
        "raw_failure_signals",
        "plan_latest_failure",
        "chain_state_summary",
        "plan_runtime_state",
        "last_gate",
        "user_action_context",
        "resolver_output",
        "chain_log_path",
        "run_log_path",
        "plan_events_path",
        "mechanical_log_path",
    )
    return {key: deepcopy(value[key]) for key in allowed if key in value}


def compact_repair_data_evidence(
    path: str | Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Externalize repeated expanding contexts without discarding their custody."""

    target = Path(path)
    compacted = deepcopy(dict(payload))
    source_bytes = len(_encoded_json(compacted))
    if source_bytes <= _EVIDENCE_EXTERNALIZE_THRESHOLD_BYTES:
        return compacted
    externalized = 0
    unique_refs: set[str] = set()

    def replace_large(container: dict[str, Any], field: str, *, force: bool = False) -> None:
        nonlocal externalized
        value = container.get(field)
        if value in (None, "", [], {}) or _is_repair_evidence_ref(value):
            return
        if not force and len(_encoded_json(value)) <= _EVIDENCE_EXTERNALIZE_THRESHOLD_BYTES:
            return
        ref = _persist_repair_evidence(target, value, field=field)
        container[field] = ref
        externalized += 1
        unique_refs.add(str(ref["sha256"]))

    initial = compacted.get("initial_facts")
    if isinstance(initial, dict):
        for field in (
            "failure_context",
            "execute_attempt_context",
            "semantic_health",
            "semantic_context",
            "custody_projection",
        ):
            replace_large(initial, field)

    for collection_name in ("attempts", "iterations"):
        collection = compacted.get(collection_name)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            for field in _ATTEMPT_EVIDENCE_FIELDS:
                replace_large(item, field)

    current = compacted.get("current_failure_context")
    if (
        isinstance(current, Mapping)
        and len(_encoded_json(current)) > _CURRENT_FAILURE_CONTEXT_MAX_BYTES
    ):
        ref = _persist_repair_evidence(
            target, current, field="current_failure_context"
        )
        summary = _bounded_current_failure_context(current)
        summary["evidence_ref"] = ref
        compacted["current_failure_context"] = summary
        externalized += 1
        unique_refs.add(str(ref["sha256"]))

    compacted["evidence_compaction"] = {
        "schema_version": REPAIR_EVIDENCE_COMPACTION_SCHEMA,
        "source_size_bytes": source_bytes,
        "externalized_field_count": externalized,
        "unique_evidence_count": len(unique_refs),
    }
    persisted_bytes = 0
    for _ in range(3):
        persisted_bytes = len(_encoded_json(compacted))
        compacted["evidence_compaction"]["persisted_size_bytes"] = persisted_bytes
    if persisted_bytes > MAX_REPAIR_DATA_BYTES:
        raise ValueError(
            "repair-data remains above 4 MiB after evidence compaction; refusing expansion"
        )
    return compacted


def save_repair_data(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Validate, optionally redact, and atomically persist repair-data JSON.

    When the repair-data event signature has changed meaningfully (or this is
    the first write), an incident-ledger event is appended via
    :mod:`arnold_pipelines.megaplan.cloud.incident_bridge`.  No-op saves
    do **not** produce duplicate events. Repeated repair attempts with the
    same outcome still emit a fresh ledger event when their attempt identity
    changes. When *root* is omitted, the payload workspace is used as the
    incident-ledger root before falling back to the current working directory.
    """

    target = Path(path)
    prepared = compact_repair_data_evidence(
        target,
        redact_repair_data(payload, redactor=redactor),
    )

    # ------------------------------------------------------------------
    # Snapshot the previous payload *before* overwriting so we can
    # decide whether this is a meaningful transition.
    # ------------------------------------------------------------------
    previous_event_signature = _read_previous_event_signature(target)

    atomic_write_json(target, prepared)
    _update_session_index_from_repair_data(target, prepared, redactor=redactor)

    current_event_signature = _event_signature(prepared)
    if previous_event_signature is None or previous_event_signature != current_event_signature:
        workspace_root = root
        if workspace_root is None:
            candidate_root = str(prepared.get("workspace") or "").strip()
            workspace_root = candidate_root or None
        _emit_incident_bridge_event(prepared, root=workspace_root)

    return prepared


def redact_repair_index(
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Recursively redact repair index values using the supplied hook."""

    validated = validate_repair_index(payload)
    if redactor is None:
        return canonical_redact_payload(validated)
    return _redact_value(validated, redactor)


def atomic_write_repair_index(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Validate, redact, and atomically persist a repair index JSON file."""

    prepared = redact_repair_index(payload, redactor=redactor)
    atomic_write_json(path, prepared)
    return prepared


def update_repair_index(
    path: str | Path,
    updater: Callable[[dict[str, Any]], Mapping[str, Any]],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Atomically read-modify-write a repair index, creating it when missing."""

    current = _read_or_initialize_repair_index(path)
    updated = updater(deepcopy(current))
    if not isinstance(updated, Mapping):
        raise ValueError("repair index updater must return a mapping")
    return atomic_write_repair_index(path, dict(updated), redactor=redactor)


def update_session_index(
    path: str | Path,
    session_id: str,
    entry_updates: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Merge *entry_updates* into the indexed session entry for *session_id*."""

    return update_repair_index(
        path,
        lambda payload: _update_index_entry(payload, "sessions", session_id, entry_updates),
        redactor=redactor,
    )


def update_incident_index(
    path: str | Path,
    incident_id: str,
    entry_updates: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Merge *entry_updates* into the indexed incident entry for *incident_id*."""

    return update_repair_index(
        path,
        lambda payload: _update_index_entry(payload, "incidents", incident_id, entry_updates),
        redactor=redactor,
    )


def _coerce_payload(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    return _coerce_json_object(payload_or_path, kind="repair-data payload", path_label="repair-data file")


def validate_repair_index(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Validate the repair index JSON shape used by cleanup/auditor flows."""

    payload = _coerce_json_object(
        payload_or_path,
        kind="repair index payload",
        path_label="repair index file",
    )
    return _normalize_repair_index(payload)


def _coerce_json_object(
    payload_or_path: Mapping[str, Any] | str | Path,
    *,
    kind: str,
    path_label: str,
) -> dict[str, Any]:
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{path_label} missing: {path}") from exc
    except OSError as exc:
        raise ValueError(f"{path_label} unreadable: {path}") from exc
    except Exception as exc:
        raise ValueError(f"{path_label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{kind} must be a JSON object")
    return payload


def _normalize_repair_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = set(_INDEX_TOP_LEVEL_KEYS) | {"resident_delegation"}
    extras = sorted(set(payload) - allowed_keys)
    if extras:
        raise ValueError(
            "repair index only supports top-level keys: "
            "sessions, incidents, resident_delegation"
        )

    normalized = {bucket: {} for bucket in _INDEX_TOP_LEVEL_KEYS}
    resident_delegation = payload.get("resident_delegation")
    if resident_delegation is not None:
        if not isinstance(resident_delegation, dict):
            raise ValueError("repair index field 'resident_delegation' must be an object")
        normalized["resident_delegation"] = deepcopy(resident_delegation)
    for bucket in _INDEX_TOP_LEVEL_KEYS:
        source = payload.get(bucket, {})
        if not isinstance(source, dict):
            raise ValueError(f"repair index field {bucket!r} must be an object")
        normalized[bucket] = {}
        for entry_id, entry in source.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"repair index entry {bucket}.{entry_id!s} must be an object"
                )
            entry_copy = deepcopy(entry)
            refs = entry_copy.get("refs", {})
            if refs is None:
                refs = {}
            if not isinstance(refs, dict):
                raise ValueError(
                    f"repair index entry {bucket}.{entry_id!s}.refs must be an object"
                )
            unsupported_refs = sorted(set(refs) - set(_INDEX_REF_KEYS))
            if unsupported_refs:
                raise ValueError(
                    "repair index refs only support: "
                    + ", ".join(_INDEX_REF_KEYS)
                )
            entry_copy["refs"] = {}
            for ref_key in _INDEX_REF_KEYS:
                if ref_key not in refs:
                    continue
                ref_value = refs[ref_key]
                if ref_value is not None and not isinstance(ref_value, dict):
                    raise ValueError(
                        f"repair index ref {bucket}.{entry_id!s}.refs.{ref_key} "
                        "must be an object or null"
                    )
                entry_copy["refs"][ref_key] = deepcopy(ref_value)
            normalized[bucket][str(entry_id)] = entry_copy
    return normalized


def _read_or_initialize_repair_index(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return _normalize_repair_index({})
    return read_repair_index(target)


def _update_index_entry(
    payload: dict[str, Any],
    bucket: str,
    entry_id: str,
    entry_updates: Mapping[str, Any],
) -> dict[str, Any]:
    if bucket not in _INDEX_TOP_LEVEL_KEYS:
        raise ValueError(f"unsupported repair index bucket: {bucket}")
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("repair index entry id must be a non-empty string")
    if not isinstance(entry_updates, Mapping):
        raise ValueError("repair index entry updates must be a mapping")

    normalized = _normalize_repair_index(payload)
    current_entry = normalized[bucket].get(entry_id, {"refs": {}})
    merged = deepcopy(current_entry)
    for key, value in entry_updates.items():
        if key == "refs":
            if not isinstance(value, Mapping):
                raise ValueError("repair index entry refs updates must be a mapping")
            merged_refs = dict(merged.get("refs", {}))
            for ref_key, ref_value in value.items():
                if ref_key not in _INDEX_REF_KEYS:
                    raise ValueError(
                        "repair index refs only support: "
                        + ", ".join(_INDEX_REF_KEYS)
                    )
                if ref_value is not None and not isinstance(ref_value, Mapping):
                    raise ValueError(
                        f"repair index ref {bucket}.{entry_id}.refs.{ref_key} "
                        "must be a mapping or null"
                    )
                merged_refs[ref_key] = deepcopy(ref_value)
            merged["refs"] = merged_refs
            continue
        merged[key] = deepcopy(value)
    normalized[bucket][entry_id] = merged
    return normalized


def _redact_value(value: Any, redactor: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return redactor(value)
    if isinstance(value, dict):
        return {key: _redact_value(item, redactor) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, redactor) for item in value]
    return deepcopy(value)


# ---------------------------------------------------------------------------
# Repair verification outcome lattice and budget helpers
# ---------------------------------------------------------------------------

# -- outcome constants -------------------------------------------------------
COMPLETE = "complete"
PROGRESSED = "progressed"
LIVE_WITH_FRESH_ACTIVITY = "live_with_fresh_activity"
TRUE_HUMAN_BLOCKER = "true_human_blocker"
PARTIAL_LIVENESS = "partial_liveness"
REPAIRING = "repairing"
RETRY_PENDING = "recurring_retry_pending"
RECOVERY_VERIFIED = "verified_recovered"
RECOVERY_PROVISIONAL = "provisional"
RECOVERY_UNKNOWN = "unknown"
RECOVERY_UNKNOWN_TYPES: frozenset[str] = frozenset(
    {"missing", "stale", "partial", "contradictory"}
)
REPAIR_TIMEOUT = "repair_timeout"
REPAIR_EXHAUSTED = "repair_exhausted"
NEEDS_HUMAN = "needs_human"
DISCORD_ESCALATED = "discord_escalated"  # legacy non-success — preserved for compatibility
ENVIRONMENT_GONE = "environment_gone"  # wiped workspace/spec — ops concern, not repairable

SUCCESS_OUTCOMES: frozenset[str] = frozenset(
    {COMPLETE, PROGRESSED, TRUE_HUMAN_BLOCKER}
)

NON_SUCCESS_OUTCOMES: frozenset[str] = frozenset(
    {
        LIVE_WITH_FRESH_ACTIVITY,
        PARTIAL_LIVENESS,
        REPAIRING,
        RETRY_PENDING,
        REPAIR_TIMEOUT,
        REPAIR_EXHAUSTED,
        NEEDS_HUMAN,
        DISCORD_ESCALATED,
        ENVIRONMENT_GONE,
    }
)

ALL_OUTCOMES: frozenset[str] = SUCCESS_OUTCOMES | NON_SUCCESS_OUTCOMES
NON_TERMINAL_OUTCOMES: frozenset[str] = frozenset(
    {REPAIRING, RETRY_PENDING, PARTIAL_LIVENESS, LIVE_WITH_FRESH_ACTIVITY}
)


def is_success_outcome(outcome: str) -> bool:
    """Return True when *outcome* is a terminal repair success.

    Only ``complete``, ``progressed``, and ``true_human_blocker`` are
    considered success. Liveness/activity-only outcomes are explicitly
    excluded because they do not prove the original blocker cleared.
    """
    return outcome in SUCCESS_OUTCOMES


def is_terminal_outcome(outcome: str) -> bool:
    """Return True when *outcome* is terminal (success or non-success).

    Repairing, retry-pending, and liveness-only outcomes retain durable custody.
    None may close the semantic repair goal.
    """
    return outcome not in NON_TERMINAL_OUTCOMES


# -- one-hour budget helpers ------------------------------------------------

DEFAULT_REPAIR_BUDGET_SECS: int = 3600


def compute_deadline(
    start_time: datetime,
    budget_secs: int = DEFAULT_REPAIR_BUDGET_SECS,
) -> datetime:
    """Return the wall-clock deadline computed from *start_time* + *budget_secs*."""
    from datetime import timedelta

    return start_time + timedelta(seconds=budget_secs)


def remaining_budget_secs(
    deadline: datetime,
    now: datetime | None = None,
) -> float:
    """Return the number of seconds remaining before *deadline* (never negative)."""
    if now is None:
        now = datetime.now(timezone.utc)
    delta = (deadline - now).total_seconds()
    return max(0.0, delta)


def is_budget_exhausted(
    deadline: datetime,
    now: datetime | None = None,
) -> bool:
    """Return True when no budget remains before *deadline*."""
    return remaining_budget_secs(deadline, now) <= 0.0


# -- verification outcome classification ------------------------------------


def classify_verification_outcome(
    *,
    is_complete: bool = False,
    has_progressed: bool = False,
    has_fresh_activity: bool = False,
    has_true_human_blocker: bool = False,
    is_live: bool = False,
    pre_snapshot: Mapping[str, Any] | None = None,
    post_snapshot: Mapping[str, Any] | None = None,
) -> str:
    """Classify a repair verification outcome from explicit evidence flags.

    The outcome lattice (first match wins):

    1. *is_complete* → :data:`COMPLETE` (terminal success)
    2. *has_progressed* → :data:`PROGRESSED` (terminal success)
    3. *has_fresh_activity* → :data:`PARTIAL_LIVENESS` (terminal non-success)
    4. *has_true_human_blocker* → :data:`TRUE_HUMAN_BLOCKER` (terminal success)
    5. *is_live* with no progress/fresh-activity/blocker → :data:`PARTIAL_LIVENESS` (terminal non-success)
    6. Otherwise → :data:`REPAIRING` (non-terminal)

    *pre_snapshot* and *post_snapshot* are accepted for forward compatibility
    with snapshot-driven delta detection but are not compared here; callers
    should compute the explicit flags before calling this function.
    """
    if is_complete:
        return COMPLETE
    if has_progressed:
        return PROGRESSED
    if has_fresh_activity:
        return PARTIAL_LIVENESS
    if has_true_human_blocker:
        return TRUE_HUMAN_BLOCKER
    if is_live:
        return PARTIAL_LIVENESS
    return REPAIRING


def _verification_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _blocker_identity(value: Mapping[str, Any] | None) -> str:
    if not isinstance(value, Mapping):
        return ""
    for key in ("blocker_id", "blocker_fingerprint", "fingerprint"):
        identity = str(value.get(key) or "").strip()
        if identity:
            return identity
    return ""


def classify_recovery_verification(
    *,
    original_blocker: Mapping[str, Any] | None,
    observation: Mapping[str, Any] | None,
    repair_completed_at: datetime | str | None,
) -> dict[str, Any]:
    """Classify whether a later observation proves the original blocker cleared."""

    def unknown(kind: str, reason: str) -> dict[str, Any]:
        return {
            "status": RECOVERY_UNKNOWN,
            "unknown_type": kind,
            "recovery_verified": False,
            "authorizes_verified_recovered": False,
            "reason": reason,
        }

    if not isinstance(observation, Mapping) or not observation:
        return unknown("missing", "independent post-repair observation is absent")

    evidence_state = observation.get("evidence_state")
    if isinstance(evidence_state, Mapping):
        unknown_type = str(evidence_state.get("unknown_type") or "").strip().lower()
        if unknown_type in RECOVERY_UNKNOWN_TYPES:
            return unknown(unknown_type, f"observation evidence is {unknown_type}")
    if observation.get("contradictory") is True:
        return unknown("contradictory", "observation contains contradictory evidence")

    observation_kind = str(observation.get("kind") or "").strip().lower()
    has_provisional_signal = observation_kind in {
        "pid", "process", "heartbeat", "liveness", "partial_liveness", "subprocess_success"
    } or any(
        observation.get(key) is True
        for key in (
            "pid_alive", "process_alive", "heartbeat_active", "is_live",
            "has_fresh_activity", "subprocess_succeeded",
        )
    )
    if observation.get("returncode") == 0:
        has_provisional_signal = True

    original_identity = _blocker_identity(original_blocker)
    observed_identity = _blocker_identity(observation)
    direct_fields_present = any(
        key in observation
        for key in (
            "blocker_cleared", "directly_observed", "independent", "blocker_id",
            "blocker_fingerprint", "fingerprint",
        )
    )
    if has_provisional_signal and not direct_fields_present:
        return {
            "status": RECOVERY_PROVISIONAL,
            "unknown_type": "",
            "recovery_verified": False,
            "authorizes_verified_recovered": False,
            "reason": "process, heartbeat, liveness, or subprocess success is provisional only",
        }

    if not original_identity or not observed_identity:
        return unknown("partial", "blocker-specific identity is incomplete")
    if original_identity != observed_identity:
        return unknown("contradictory", "observation refers to a different blocker")
    if observation.get("blocker_cleared") is not True:
        if observation.get("blocker_cleared") is False:
            return unknown("contradictory", "observation says the original blocker remains")
        return unknown("partial", "observation does not directly say the blocker cleared")
    if observation.get("directly_observed") is not True:
        return unknown("partial", "blocker clearance was not directly observed")
    if observation.get("independent") is not True:
        return unknown("partial", "blocker clearance observation is not independent")
    if observation.get("canonical_runner_live") is not True:
        return unknown(
            "contradictory"
            if observation.get("canonical_runner_live") is False
            else "partial",
            "the exact canonical runner is not independently proven live",
        )
    if observation.get("fresh_progress_beyond_checkpoint") is not True:
        return unknown(
            "contradictory"
            if observation.get("fresh_progress_beyond_checkpoint") is False
            else "partial",
            "fresh authoritative progress beyond the pre-repair checkpoint is not proven",
        )
    if observation.get("continued_progress") is not True:
        return unknown(
            "contradictory"
            if observation.get("continued_progress") is False
            else "partial",
            "bounded follow-up observation did not prove continued progress",
        )

    completed_at = _verification_timestamp(repair_completed_at)
    first_progress_at = _verification_timestamp(
        observation.get("first_progress_observed_at")
    )
    observed_at = _verification_timestamp(observation.get("observed_at"))
    if completed_at is None or first_progress_at is None or observed_at is None:
        return unknown("partial", "verification timestamps are incomplete")
    if first_progress_at <= completed_at:
        return unknown(
            "stale", "initial recovery observation is not later than repair completion"
        )
    if observed_at <= first_progress_at:
        return unknown(
            "stale", "follow-up observation is not later than initial recovery progress"
        )

    return {
        "status": RECOVERY_VERIFIED,
        "unknown_type": "",
        "recovery_verified": True,
        "authorizes_verified_recovered": True,
        "reason": (
            "two later independent observations prove blocker clearance, a live canonical "
            "runner, beyond-checkpoint progress, and continued progress"
        ),
        "blocker_identity": original_identity,
        "repair_completed_at": completed_at.isoformat(),
        "first_progress_observed_at": first_progress_at.isoformat(),
        "observed_at": observed_at.isoformat(),
    }


def build_verification_record(
    outcome: str,
    *,
    pre_snapshot: Mapping[str, Any] | None = None,
    post_snapshot: Mapping[str, Any] | None = None,
    original_blocker: Mapping[str, Any] | None = None,
    observation: Mapping[str, Any] | None = None,
    repair_completed_at: datetime | str | None = None,
    delta_summary: str = "",
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Return a structured verification record suitable for repair-data persistence.

    Args:
        outcome: One of the outcome lattice constants (e.g. :data:`COMPLETE`).
        pre_snapshot: Optional pre-relaunch resolver snapshot.
        post_snapshot: Optional post-relaunch resolver snapshot.
        delta_summary: Human-readable description of what changed (or didn't).
        recorded_at: Timestamp for the record (defaults to now).
    """
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc)
    recovery_verification = classify_recovery_verification(
        original_blocker=original_blocker,
        observation=observation,
        repair_completed_at=repair_completed_at,
    )
    return {
        "outcome": outcome,
        "is_success": is_success_outcome(outcome),
        "is_terminal": is_terminal_outcome(outcome),
        "recovery_verified": recovery_verification["recovery_verified"],
        "authorizes_verified_recovered": recovery_verification[
            "authorizes_verified_recovered"
        ],
        "recorded_at": recorded_at.isoformat(),
        "pre_snapshot": dict(pre_snapshot) if pre_snapshot is not None else None,
        "post_snapshot": dict(post_snapshot) if post_snapshot is not None else None,
        "original_blocker": (
            dict(original_blocker) if original_blocker is not None else None
        ),
        "observation": dict(observation) if observation is not None else None,
        "repair_completed_at": (
            repair_completed_at.isoformat()
            if isinstance(repair_completed_at, datetime)
            else repair_completed_at
        ),
        "recovery_verification": recovery_verification,
        "delta_summary": delta_summary,
    }


# ---------------------------------------------------------------------------
# JSONL / NDJSON sidecar helpers (append-only, atomic)
# ---------------------------------------------------------------------------

_SIDECAR_KINDS = ("events", "incidents", "attempts", "escalations", "cleanup")
_SIDECAR_FILENAME = {
    "events": "events.jsonl",
    "incidents": "incidents.jsonl",
    "attempts": "attempts.jsonl",
    "escalations": "escalations.jsonl",
    "cleanup": "cleanup.jsonl",
}


def _fsync_dir(path: Path) -> None:
    """fsync the directory containing *path* so renames are durable."""
    directory = path if path.is_dir() else path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    """Atomically append *record* as a JSON line to the JSONL file at *path*.

    Uses read-modify-write with temp-file/fsync/replace so readers never
    see a partial or truncated file.  Parent directories are created as
    needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    new_line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"

    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception:
            existing = ""

    full_content = (existing + new_line).encode("utf-8")

    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(full_content)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    _fsync_dir(path.parent)


def read_jsonl_records(
    path: str | Path,
    *,
    skip_parse_errors: bool = False,
) -> list[dict[str, Any]]:
    """Read all valid records from a JSONL / NDJSON file.

    Args:
        path: Path to the ``.jsonl`` file.
        skip_parse_errors: When *True*, malformed lines are silently
            skipped.  When *False* (default), the first unparseable line
            raises :exc:`ValueError`.

    Returns:
        A list of parsed record dicts, in file order.

    Raises:
        ValueError: If *skip_parse_errors* is *False* and any line cannot
            be parsed as JSON, or if the file does not exist.
    """
    target = Path(path)
    if not target.exists():
        if skip_parse_errors:
            return []
        raise ValueError(f"JSONL file missing: {target}")

    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if skip_parse_errors:
                continue
            raise ValueError(
                f"JSONL parse error at {target}:{lineno}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            if skip_parse_errors:
                continue
            raise ValueError(
                f"JSONL record at {target}:{lineno} is not a JSON object"
            )
        records.append(record)
    return records


def validate_jsonl_summary(path: str | Path) -> dict[str, Any]:
    """Return a validation summary for a JSONL sidecar file.

    The returned dict contains:

    * ``file`` — absolute path to the inspected file.
    * ``total_lines`` — number of non-empty lines.
    * ``valid_records`` — number of successfully parsed object records.
    * ``parse_errors`` — list of ``{line, error}`` dicts for malformed lines.
    * ``non_object_lines`` — count of lines that parsed as non-object JSON.
    * ``first_record`` — the first valid record (or *None*).
    * ``last_record`` — the last valid record (or *None*).
    * ``ordered`` — *True* if every record carries a ``_sequence`` field that
      is strictly increasing, *False* otherwise (or *None* when there are
      fewer than two records).
    """
    target = Path(path)
    summary: dict[str, Any] = {
        "file": str(target.resolve()),
        "total_lines": 0,
        "valid_records": 0,
        "parse_errors": [],
        "non_object_lines": 0,
        "first_record": None,
        "last_record": None,
        "ordered": None,
    }

    if not target.exists():
        return summary

    sequences: list[int] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        summary["total_lines"] += 1
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            summary["parse_errors"].append({"line": lineno, "error": str(exc)})
            continue
        if not isinstance(record, dict):
            summary["non_object_lines"] += 1
            continue
        summary["valid_records"] += 1
        if summary["first_record"] is None:
            summary["first_record"] = record
        summary["last_record"] = record
        seq = record.get("_sequence")
        if isinstance(seq, int):
            sequences.append(seq)

    if len(sequences) >= 2:
        summary["ordered"] = all(
            sequences[i] < sequences[i + 1] for i in range(len(sequences) - 1)
        )
    return summary


def _sidecar_jsonl_path(sidecar_dir: str | Path, kind: str) -> Path:
    """Return the canonical JSONL path for a sidecar *kind*."""
    if kind not in _SIDECAR_KINDS:
        raise ValueError(
            f"Unknown sidecar kind {kind!r}; expected one of {_SIDECAR_KINDS}"
        )
    base = Path(sidecar_dir)
    return base / kind / _SIDECAR_FILENAME[kind]


def append_jsonl_record(
    sidecar_dir: str | Path,
    kind: str,
    record: Mapping[str, Any],
    *,
    auto_sequence: bool = True,
) -> Path:
    """Append *record* to the typed JSONL sidecar under *sidecar_dir*.

    Args:
        sidecar_dir: Root directory for sidecar files (e.g. ``repair-data.d``).
        kind: One of ``"events"``, ``"incidents"``, ``"attempts"``.
        record: The JSON-serializable record to append.
        auto_sequence: When *True* (default), a ``_sequence`` field is
            injected with the next available integer.

    Returns:
        The :class:`Path` to the JSONL file that was appended to.
    """
    if not isinstance(record, Mapping):
        raise ValueError("JSONL record must be a mapping")

    target = _sidecar_jsonl_path(sidecar_dir, kind)
    enriched: dict[str, Any] = dict(record)

    if auto_sequence:
        existing = read_jsonl_records(target, skip_parse_errors=True)
        enriched["_sequence"] = len(existing) + 1

    if "_timestamp" not in enriched:
        enriched["_timestamp"] = datetime.now(timezone.utc).isoformat()

    _atomic_append_jsonl(target, enriched)
    return target


def append_repair_event(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append a repair event record to the ``events`` sidecar."""
    return append_jsonl_record(sidecar_dir, "events", record, **kwargs)


def append_incident_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append an incident record to the ``incidents`` sidecar."""
    return append_jsonl_record(sidecar_dir, "incidents", record, **kwargs)


def append_attempt_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append an attempt record to the ``attempts`` sidecar."""
    return append_jsonl_record(sidecar_dir, "attempts", record, **kwargs)


def append_escalation_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append an escalation lifecycle record to the ``escalations`` sidecar."""
    return append_jsonl_record(sidecar_dir, "escalations", record, **kwargs)


def append_cleanup_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append a retention/cleanup lifecycle record to the ``cleanup`` sidecar."""
    return append_jsonl_record(sidecar_dir, "cleanup", record, **kwargs)


def cleanup_repair_data_retention(
    repair_data_dir: str | Path,
    *,
    sidecar_dir: str | Path | None = None,
    audit_report_dir: str | Path | None = None,
    index_path: str | Path | None = None,
    now: datetime | None = None,
    active_session_ids: set[str] | None = None,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Prune stale repair artifacts while preserving protected evidence."""

    if now is None:
        now = datetime.now(timezone.utc)

    repair_root = Path(repair_data_dir)
    cleanup_sidecar_dir = Path(sidecar_dir) if sidecar_dir is not None else repair_root.with_name(f"{repair_root.name}.d")
    audit_root = Path(audit_report_dir) if audit_report_dir is not None else None
    effective_index_path = Path(index_path) if index_path is not None else repair_root / "index.json"

    index_before = load_repair_index(effective_index_path)
    active_sessions = set(active_session_ids or set())
    active_sessions.update(_active_sessions_from_index(index_before))
    referenced_audit_reports = _collect_referenced_audit_reports(
        repair_root,
        index_before,
        audit_root,
    )

    summary: dict[str, Any] = {
        "cleanup_type": "retention",
        "repair_data_dir": str(repair_root),
        "pruned_counts": {},
        "pruned_paths": {},
        "preserved_counts": {},
        "preserved_reasons": {},
        "index_snapshots": {"before": redact_repair_index(index_before, redactor=redactor), "after": {}},
    }

    for path in sorted(repair_root.glob("*.repair-data.json")):
        session_id = path.name[: -len(".repair-data.json")]
        preserve = session_id in active_sessions or _is_within_days(path, now, _SNAPSHOT_RETENTION_DAYS)
        if preserve:
            _record_preserved(summary, "snapshots", "active_session_snapshot" if session_id in active_sessions else "recent_snapshot")
            continue
        _prune_path(path, summary, "snapshots")

    _cleanup_attempt_records(repair_root / "attempts", now, summary)
    _cleanup_json_record_dir(
        repair_root / "incidents",
        now,
        summary,
        category="incidents",
        retention_days=_RETENTION_WINDOWS_DAYS["incidents"],
        preserve_predicate=_is_unresolved_record,
        preserve_reason="unresolved_incident",
    )
    _cleanup_json_record_dir(
        repair_root / "escalations",
        now,
        summary,
        category="escalations",
        retention_days=_RETENTION_WINDOWS_DAYS["escalations"],
        preserve_predicate=_is_unresolved_record,
        preserve_reason="unresolved_escalation",
    )
    _cleanup_json_record_dir(
        repair_root / "meta",
        now,
        summary,
        category="meta",
        retention_days=_RETENTION_WINDOWS_DAYS["meta"],
    )
    if audit_root is not None:
        _cleanup_audit_reports(audit_root, now, referenced_audit_reports, summary)

    index_after = _reconcile_repair_index_after_cleanup(
        index_before,
        repair_root=repair_root,
        active_sessions=active_sessions,
    )
    atomic_write_repair_index(effective_index_path, index_after, redactor=redactor)
    summary["index_snapshots"]["after"] = redact_repair_index(index_after, redactor=redactor)

    cleanup_id = f"cleanup-{now.strftime('%Y%m%dT%H%M%SZ')}"
    record = {
        "cleanup_id": cleanup_id,
        "pruned_counts": summary["pruned_counts"],
        "pruned_paths": summary["pruned_paths"],
        "preserved_counts": summary["preserved_counts"],
        "preserved_reasons": summary["preserved_reasons"],
        "index_snapshots": summary["index_snapshots"],
    }
    cleanup_path = append_cleanup_record(cleanup_sidecar_dir, record)
    summary["cleanup_id"] = cleanup_id
    summary["cleanup_record_path"] = str(cleanup_path)
    return summary


def _cleanup_attempt_records(attempts_dir: Path, now: datetime, summary: dict[str, Any]) -> None:
    if not attempts_dir.exists():
        return

    grouped: dict[str, list[tuple[Path, datetime]]] = {}
    for path in sorted(attempts_dir.glob("*.json")):
        payload = load_json(path, default={})
        session_id = _record_session_id(payload, path)
        grouped.setdefault(session_id, []).append((path, _path_mtime(path)))

    for entries in grouped.values():
        entries.sort(key=lambda item: item[1], reverse=True)
        protected = {path for path, _ in entries[:_MIN_ATTEMPTS_PER_SESSION]}
        for path, _ in entries:
            if path in protected:
                _record_preserved(summary, "attempts", "recent_attempt_floor")
                continue
            if _is_within_days(path, now, _RETENTION_WINDOWS_DAYS["attempts"]):
                _record_preserved(summary, "attempts", "recent_attempt")
                continue
            _prune_path(path, summary, "attempts")


def _cleanup_json_record_dir(
    directory: Path,
    now: datetime,
    summary: dict[str, Any],
    *,
    category: str,
    retention_days: int,
    preserve_predicate: Callable[[Mapping[str, Any]], bool] | None = None,
    preserve_reason: str | None = None,
) -> None:
    if not directory.exists():
        return

    for path in sorted(directory.glob("*.json")):
        payload = load_json(path, default={})
        if preserve_predicate is not None and preserve_predicate(payload):
            _record_preserved(summary, category, preserve_reason or f"{category}_preserved")
            continue
        if _is_within_days(path, now, retention_days):
            _record_preserved(summary, category, f"recent_{category[:-1] if category.endswith('s') else category}")
            continue
        _prune_path(path, summary, category)


def _cleanup_audit_reports(
    audit_dir: Path,
    now: datetime,
    referenced_reports: set[Path],
    summary: dict[str, Any],
) -> None:
    if not audit_dir.exists():
        return

    for path in sorted(audit_dir.glob("*-audit.*")):
        if path.suffix not in {".json", ".md"}:
            continue
        if path.resolve() in referenced_reports:
            _record_preserved(summary, "audit_reports", "referenced_audit_report")
            continue
        if _is_within_days(path, now, _RETENTION_WINDOWS_DAYS["audit_reports"]):
            _record_preserved(summary, "audit_reports", "recent_audit_report")
            continue
        _prune_path(path, summary, "audit_reports")


def _active_sessions_from_index(index_payload: Mapping[str, Any]) -> set[str]:
    active: set[str] = set()
    for session_id, entry in index_payload.get("sessions", {}).items():
        if not isinstance(entry, Mapping):
            continue
        status = str(entry.get("status", "")).strip().lower()
        if status in _ACTIVE_SESSION_STATUSES:
            active.add(str(session_id))
            continue
        refs = entry.get("refs")
        if isinstance(refs, Mapping):
            latest_outcome = refs.get("latest-outcome")
            if isinstance(latest_outcome, Mapping):
                if str(latest_outcome.get("outcome", "")).strip().lower() == REPAIRING:
                    active.add(str(session_id))
    return active


def _read_previous_payload(target: Path) -> dict[str, Any] | None:
    """Return the previous repair-data payload, or *None* when unavailable."""
    try:
        if not target.exists():
            return None
        previous = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(previous, dict):
        return None
    return previous


def _repair_attempt_marker(payload: Mapping[str, Any]) -> str:
    """Return a stable marker for distinguishing repeated repair attempts."""

    for key in ("current_attempt_id", "repair_run_count"):
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        marker = str(value).strip()
        if marker:
            return marker

    attempt_ids = payload.get("attempt_ids")
    if isinstance(attempt_ids, list) and attempt_ids:
        marker = "|".join(str(item).strip() for item in attempt_ids if str(item).strip())
        if marker:
            return marker
    return ""


def _event_signature(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    """Return the dedupe signature for repair-data incident emission."""

    outcome = str(payload.get("outcome") or REPAIRING).strip() or REPAIRING
    marker = _repair_attempt_marker(payload)
    if is_success_outcome(outcome):
        recovery = _payload_recovery_verification(payload)
        if recovery.get("authorizes_verified_recovered") is True:
            return ("verified_recovered", outcome, marker)
        projected_outcome = (
            RECOVERY_PROVISIONAL
            if recovery.get("status") == RECOVERY_PROVISIONAL
            else f"unknown_{recovery.get('unknown_type') or 'missing'}"
        )
        return ("repair_attempt", projected_outcome, marker)
    if outcome == REPAIRING:
        return ("repair_attempt", "attempted", marker)
    return ("repair_attempt", outcome, marker)


def _repair_attempt_event_id(payload: Mapping[str, Any], *, session_id: str | None) -> str:
    """Return the incident-bridge attempt_id for repair attempt events."""

    outcome = str(payload.get("outcome") or REPAIRING).strip() or REPAIRING
    normalized_outcome = "attempted" if outcome == REPAIRING else outcome
    marker = _repair_attempt_marker(payload)
    base = f"{session_id or 'unknown'}-{normalized_outcome}"
    if marker:
        return f"{base}-{marker}"
    return base


def _read_previous_event_signature(target: Path) -> tuple[str, str, str] | None:
    """Return the previous incident-event signature, or *None* if unavailable."""

    previous = _read_previous_payload(target)
    if previous is None:
        return None
    return _event_signature(previous)


def _emit_incident_bridge_event(
    payload: Mapping[str, Any],
    *,
    root: Path | str | None = None,
) -> None:
    """Map repair-data transitions to incident-bridge events.

    This is intentionally a best-effort side effect: if the bridge or
    ledger is unavailable the repair-data save still succeeds.
    """
    session_id = str(payload.get("session") or "").strip() or None
    incident_id = str(payload.get("incident_id") or "").strip() or None
    if not incident_id:
        return

    outcome = str(payload.get("outcome") or REPAIRING).strip() or REPAIRING
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        plan_name = str(payload.get("plan_name") or "").strip()
        run_kind = str(payload.get("run_kind") or "").strip()
        workspace = str(payload.get("workspace") or "").strip()
        summary = f"repair-data outcome={outcome}"
        if plan_name:
            summary += f" plan={plan_name}"
        if run_kind:
            summary += f" kind={run_kind}"
        if workspace:
            summary += f" workspace={workspace}"

    evidence: list[Any] = []
    verification = payload.get("verification")
    if isinstance(verification, dict):
        evidence.append({"kind": "verification_record", "data": verification})
    attempt_ids = payload.get("attempt_ids")
    if isinstance(attempt_ids, list) and attempt_ids:
        evidence.append({"kind": "attempt_ids", "ids": list(attempt_ids)})

    try:
        from arnold_pipelines.megaplan.cloud.incident_bridge import (
            append_immediate_repair_attempt,
            append_recovery_observation,
        )

        if outcome == REPAIRING:
            append_immediate_repair_attempt(
                incident_id=incident_id,
                summary=summary,
                attempt_id=_repair_attempt_event_id(payload, session_id=session_id),
                outcome="attempted",
                evidence=evidence,
                session_id=session_id,
                root=root,
            )
        elif is_success_outcome(outcome):
            append_recovery_observation(
                incident_id=incident_id,
                summary=summary,
                recovery_verification=(
                    dict(verification) if isinstance(verification, Mapping) else {}
                ),
                evidence=evidence,
                session_id=session_id,
                root=root,
            )
        else:
            # Terminal non-success outcomes (repair_timeout, repair_exhausted,
            # needs_human, partial_liveness, discord_escalated, etc.)
            append_immediate_repair_attempt(
                incident_id=incident_id,
                summary=summary,
                attempt_id=_repair_attempt_event_id(payload, session_id=session_id),
                outcome=outcome,
                evidence=evidence,
                session_id=session_id,
                root=root,
            )
    except Exception:
        # Bridge event emission is best-effort; never let it fail the save.
        pass


def _payload_recovery_verification(payload: Mapping[str, Any]) -> dict[str, Any]:
    verification = payload.get("verification")
    if not isinstance(verification, Mapping):
        verification = {}
    original_blocker = verification.get("original_blocker")
    if not isinstance(original_blocker, Mapping):
        original_blocker = payload.get("original_blocker")
    observation = verification.get("observation")
    repair_completed_at = verification.get("repair_completed_at")
    return classify_recovery_verification(
        original_blocker=original_blocker if isinstance(original_blocker, Mapping) else None,
        observation=observation if isinstance(observation, Mapping) else None,
        repair_completed_at=repair_completed_at,
    )


def _update_session_index_from_repair_data(
    path: Path,
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> None:
    session_id = str(payload.get("session") or "").strip()
    if not session_id and path.name.endswith(".repair-data.json"):
        session_id = path.name[: -len(".repair-data.json")]
    if not session_id:
        return

    recorded_at = _repair_data_recorded_at(payload)
    outcome = str(payload.get("outcome") or REPAIRING).strip() or REPAIRING
    incident_id = str(payload.get("incident_id") or "").strip()
    latest_outcome_ref: dict[str, Any] = {
        "outcome": outcome,
        "recorded_at": recorded_at,
        "path": str(path),
    }
    if incident_id:
        latest_outcome_ref["incident_id"] = incident_id

    entry_updates: dict[str, Any] = {
        "session": session_id,
        "status": outcome,
        "updated_at": recorded_at,
        "workspace": str(payload.get("workspace") or ""),
        "run_kind": str(payload.get("run_kind") or ""),
        "plan_name": str(payload.get("plan_name") or ""),
        "incident_id": incident_id,
        "refs": {"latest-outcome": latest_outcome_ref},
    }
    if isinstance(payload.get("attempt_ids"), list):
        entry_updates["attempt_ids"] = deepcopy(payload.get("attempt_ids"))

    update_session_index(path.parent / "index.json", session_id, entry_updates, redactor=redactor)


def _repair_data_recorded_at(payload: Mapping[str, Any]) -> str:
    verification = payload.get("verification")
    if isinstance(verification, Mapping):
        recorded_at = str(verification.get("recorded_at") or "").strip()
        if recorded_at:
            return recorded_at
    for field in ("updated_at", "recorded_at", "created_at"):
        recorded_at = str(payload.get(field) or "").strip()
        if recorded_at:
            return recorded_at
    return datetime.now(timezone.utc).isoformat()


def _reconcile_repair_index_after_cleanup(
    index_payload: Mapping[str, Any],
    *,
    repair_root: Path,
    active_sessions: set[str],
) -> dict[str, Any]:
    normalized = _normalize_repair_index(index_payload)
    reconciled = _normalize_repair_index({})

    for session_id, entry in normalized["sessions"].items():
        snapshot_path = repair_root / f"{session_id}.repair-data.json"
        if not snapshot_path.exists() and session_id not in active_sessions:
            continue
        entry_copy = deepcopy(entry)
        meta_path = str(entry_copy.get("latest_meta_record_path") or "").strip()
        if meta_path and not Path(meta_path).exists():
            entry_copy["latest_meta_record_path"] = ""
            entry_copy["latest_meta_repair_id"] = ""
            entry_copy["latest_meta_outcome"] = ""
            entry_copy["latest_meta_recorded_at"] = ""
        reconciled["sessions"][session_id] = entry_copy

    for incident_id, entry in normalized["incidents"].items():
        incident_path = repair_root / "incidents" / f"{incident_id}.json"
        if incident_path.exists():
            reconciled["incidents"][incident_id] = deepcopy(entry)

    return reconciled


def _collect_referenced_audit_reports(
    repair_root: Path,
    index_payload: Mapping[str, Any],
    audit_root: Path | None,
) -> set[Path]:
    referenced: set[Path] = set()
    for path in sorted((repair_root / "incidents").glob("*.json")):
        payload = load_json(path, default={})
        if _is_unresolved_record(payload):
            referenced.update(_extract_audit_report_paths(payload, audit_root))
    for entry in index_payload.get("incidents", {}).values():
        if isinstance(entry, Mapping) and _is_unresolved_record(entry):
            referenced.update(_extract_audit_report_paths(entry, audit_root))
    return referenced


def _extract_audit_report_paths(value: Any, audit_root: Path | None) -> set[Path]:
    matches: set[Path] = set()
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return matches
        path = Path(candidate)
        if _looks_like_audit_report(path, audit_root):
            matches.add(path.resolve())
        return matches
    if isinstance(value, Mapping):
        for item in value.values():
            matches.update(_extract_audit_report_paths(item, audit_root))
        return matches
    if isinstance(value, list):
        for item in value:
            matches.update(_extract_audit_report_paths(item, audit_root))
    return matches


def _looks_like_audit_report(path: Path, audit_root: Path | None) -> bool:
    name = path.name
    if name.endswith("-audit.json") or name.endswith("-audit.md"):
        return True
    if audit_root is not None:
        try:
            path.resolve().relative_to(audit_root.resolve())
            return path.suffix in {".json", ".md"}
        except ValueError:
            return False
    return False


def _record_session_id(payload: Mapping[str, Any], path: Path) -> str:
    session_id = payload.get("session_id") or payload.get("session")
    if isinstance(session_id, str) and session_id.strip():
        return session_id
    return path.stem


def _is_unresolved_record(payload: Mapping[str, Any]) -> bool:
    for key in ("resolved_at", "closed_at", "completed_at"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return False
    for key in ("resolved", "closed", "completed"):
        if payload.get(key) is True:
            return False

    for key in ("state", "status", "resolution_state", "lifecycle"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        normalized = value.strip().lower()
        if normalized in _RESOLVED_RECORD_STATES:
            return False
        if normalized in _UNRESOLVED_RECORD_STATES:
            return True
    return True


def _is_within_days(path: Path, now: datetime, days: int) -> bool:
    cutoff = now.timestamp() - (days * 86400)
    return path.stat().st_mtime >= cutoff


def _path_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _prune_path(path: Path, summary: dict[str, Any], category: str) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    summary["pruned_counts"][category] = int(summary["pruned_counts"].get(category, 0)) + 1
    summary["pruned_paths"].setdefault(category, []).append(str(path))


def _record_preserved(summary: dict[str, Any], category: str, reason: str) -> None:
    summary["preserved_counts"][category] = int(summary["preserved_counts"].get(category, 0)) + 1
    summary["preserved_reasons"][reason] = int(summary["preserved_reasons"].get(reason, 0)) + 1


def _decision_history_by_request(
    records: list[Mapping[str, Any]],
) -> dict[str, list[RepairRequestDecisionRecord]]:
    history: dict[str, list[RepairRequestDecisionRecord]] = {}
    for record in records:
        request_id = _as_text(record.get("request_id"))
        if not request_id:
            continue
        history.setdefault(request_id, []).append(
            {
                "decision_id": _as_text(record.get("decision_id")),
                "request_id": request_id,
                "decision": _as_text(record.get("decision")),
                "reason": _as_text(record.get("reason")),
                "related_request_id": _as_text(record.get("related_request_id")),
                "created_at": _as_text(record.get("created_at")),
                "path": _as_text(record.get("_path")),
            }
        )
    return history


def _effective_request_decision(
    history: list[RepairRequestDecisionRecord],
) -> RepairRequestDecisionRecord | None:
    if not history:
        return None
    priority = {
        REQUEST_STATUS_SUPERSEDED: 5,
        REQUEST_STATUS_STALE: 4,
        REQUEST_STATUS_DISPATCHED: 3,
        REQUEST_STATUS_COALESCED: 2,
        REQUEST_STATUS_ACCEPTED: 1,
    }
    return max(
        history,
        key=lambda item: (
            int(priority.get(str(item["decision"]), 0)),
            str(item["created_at"]),
            str(item["decision_id"]),
        ),
    )


def _collect_custody_attempts(
    *,
    repair_data_dir: str | Path | None,
    sidecar_dir: str | Path | None,
    blocker_id: str,
    fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None,
    target_session: str = "",
) -> list[RepairCustodyAttemptRecord]:
    attempts: list[RepairCustodyAttemptRecord] = []
    snapshot_request_ids = _collect_snapshot_request_ids(repair_data_dir)
    if repair_data_dir is not None:
        for path in sorted(Path(repair_data_dir).glob("*.repair-data.json")):
            payload = load_json(path, default={})
            if not isinstance(payload, Mapping):
                continue
            if target_session and _record_session_id(payload, path) != target_session:
                continue
            attempts.extend(
                _attempts_from_snapshot(
                    path=path,
                    payload=payload,
                    blocker_id=blocker_id,
                    fingerprint=fingerprint,
                )
            )
    if sidecar_dir is not None:
        attempts.extend(
            _attempts_from_sidecar(
                sidecar_dir=Path(sidecar_dir),
                blocker_id=blocker_id,
                fingerprint=fingerprint,
                snapshot_request_ids=snapshot_request_ids,
                target_session=target_session,
            )
        )
    attempts.sort(key=lambda item: (item["recorded_at"], item["attempt_id"], item["path"]))
    return attempts


def _attempt_has_current_custody(
    attempt: Mapping[str, Any],
    *,
    active_request_ids: set[str],
    blocker_id: str,
    repair_identity_key: str,
    exact_identity_required: bool,
) -> bool:
    """Reject identity-free legacy attempts that cannot own the current target."""

    request_id = _as_text(attempt.get("request_id"))
    attempt_identity_key = _as_text(attempt.get("repair_identity_key"))
    if exact_identity_required and repair_identity_key and attempt_identity_key != repair_identity_key:
        return False
    if request_id:
        return request_id in active_request_ids
    raw = _as_mapping(attempt.get("raw"))
    raw_blocker_id = _as_text(raw.get("blocker_id"))
    if blocker_id and raw_blocker_id:
        return raw_blocker_id == blocker_id
    signature = (
        raw.get("problem_signature")
        or raw.get("current_signature")
        or _as_mapping(raw.get("current_recurrence")).get("problem_signature")
    )
    return bool(signature) and _problem_signature_matches_fingerprint(
        signature, _as_mapping(attempt.get("blocker_fingerprint"))
    )


def durable_repair_active(custody: Mapping[str, Any] | None) -> bool:
    """Return true only for durable ownership/launch evidence, never labels.

    A custody bucket, resolver classification, or legacy progress sidecar is a
    derived observation.  Active repair requires either a blocker-scoped claim
    tied to a current request or a target-matched nonterminal attempt with an
    immutable identity and source path.
    """

    payload = _as_mapping(custody)
    active_request_ids = {
        _as_text(value)
        for value in _as_list(payload.get("active_request_ids"))
        if _as_text(value)
    }
    active_claim_ids = {
        _as_text(value)
        for value in _as_list(payload.get("active_claim_request_ids"))
        if _as_text(value)
    }
    if active_request_ids & active_claim_ids:
        return True
    terminal_by_request: dict[str, datetime] = {}
    for value in _as_list(payload.get("attempts")):
        attempt = _as_mapping(value)
        request_id = _as_text(attempt.get("request_id"))
        if not request_id or attempt.get("terminal") is not True:
            continue
        recorded_at = _verification_timestamp(attempt.get("recorded_at"))
        if recorded_at is not None and recorded_at > terminal_by_request.get(
            request_id, datetime.min.replace(tzinfo=timezone.utc)
        ):
            terminal_by_request[request_id] = recorded_at
    for value in _as_list(payload.get("attempts")):
        attempt = _as_mapping(value)
        if attempt.get("terminal") is not False:
            continue
        if not _as_text(attempt.get("attempt_id")) or not _as_text(attempt.get("path")):
            continue
        request_id = _as_text(attempt.get("request_id"))
        recorded_at = _verification_timestamp(attempt.get("recorded_at"))
        if (
            request_id in terminal_by_request
            and recorded_at is not None
            and terminal_by_request[request_id] >= recorded_at
        ):
            continue
        if request_id and request_id in active_request_ids:
            return True
        if (
            _as_text(attempt.get("source")) == "repair_queue_dispatch_attempt"
            and _as_text(attempt.get("blocker_id"))
        ):
            return True
    return False


def _collect_snapshot_request_ids(
    repair_data_dir: str | Path | None,
) -> set[tuple[str, str]]:
    request_ids: set[tuple[str, str]] = set()
    if repair_data_dir is None:
        return request_ids
    for path in sorted(Path(repair_data_dir).glob("*.repair-data.json")):
        payload = load_json(path, default={})
        if not isinstance(payload, Mapping):
            continue
        session = _record_session_id(payload, path)
        for attempt in _as_list(payload.get("attempts")):
            request_id = _as_scalar_text(_as_mapping(attempt).get("request_id"))
            attempt_id = _as_scalar_text(_as_mapping(attempt).get("attempt_id"))
            if request_id and attempt_id:
                request_ids.add((session, attempt_id))
    return request_ids


def _attempts_from_snapshot(
    *,
    path: Path,
    payload: Mapping[str, Any],
    blocker_id: str,
    fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None,
) -> list[RepairCustodyAttemptRecord]:
    session = _record_session_id(payload, path)
    snapshot_outcome = _as_text(payload.get("outcome")) or REPAIRING
    attempts: list[RepairCustodyAttemptRecord] = []
    for attempt in _as_list(payload.get("attempts")):
        record = _as_mapping(attempt)
        attempt_id = _as_scalar_text(record.get("attempt_id"))
        if not attempt_id:
            continue
        if not _problem_signature_matches_fingerprint(record.get("problem_signature"), fingerprint):
            continue
        attempts.append(
            _build_attempt_record(
                attempt_id=attempt_id,
                session=session,
                source="repair_data_snapshot",
                path=str(path),
                blocker_id=blocker_id,
                fingerprint=fingerprint,
                request_id=_as_scalar_text(record.get("request_id")),
                state=_attempt_state_from_snapshot(payload, record),
                outcome=snapshot_outcome,
                recorded_at=_repair_data_recorded_at(payload),
                raw=record,
            )
        )
    managed_attempts = _managed_attempts_from_snapshot(
        path=path,
        payload=payload,
        session=session,
        blocker_id=blocker_id,
        fingerprint=fingerprint,
    )
    if attempts:
        return attempts + managed_attempts
    current_attempt_id = _as_scalar_text(payload.get("current_attempt_id"))
    if current_attempt_id:
        snapshot_signature = (
            payload.get("problem_signature")
            or payload.get("current_signature")
            or (
                _as_mapping(payload.get("current_recurrence")).get("problem_signature")
                if isinstance(payload.get("current_recurrence"), Mapping)
                else None
            )
        )
        if not _problem_signature_matches_fingerprint(snapshot_signature, fingerprint):
            return attempts
        payload_request_id = _as_scalar_text(
            payload.get("request_id")
        ) or _as_scalar_text(
            (payload.get("current_recurrence") or {}).get("request_id")
            if isinstance(payload.get("current_recurrence"), Mapping)
            else None
        )
        attempts.append(
            _build_attempt_record(
                attempt_id=current_attempt_id,
                session=session,
                source="repair_data_snapshot",
                path=str(path),
                blocker_id=blocker_id,
                fingerprint=fingerprint,
                request_id=payload_request_id,
                state=_attempt_state_from_snapshot(payload, {}),
                outcome=snapshot_outcome,
                recorded_at=_repair_data_recorded_at(payload),
                raw=dict(payload),
            )
        )
    return attempts + managed_attempts


def _managed_attempts_from_snapshot(
    *,
    path: Path,
    payload: Mapping[str, Any],
    session: str,
    blocker_id: str,
    fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None,
) -> list[RepairCustodyAttemptRecord]:
    """Project real managed-run evidence without fabricating legacy attempts."""

    from arnold_pipelines.megaplan.managed_agent import (
        is_managed_manifest,
        observed_status,
        validate_automatic_managed_manifest,
    )

    projected: list[RepairCustodyAttemptRecord] = []
    for value in _as_list(payload.get("managed_agent_runs")):
        reference = _as_mapping(value)
        run_id = _as_scalar_text(reference.get("run_id"))
        manifest_text = _as_scalar_text(reference.get("manifest_path"))
        if not run_id or not manifest_text:
            continue
        reference_blocker_id = _as_scalar_text(reference.get("blocker_id"))
        if blocker_id and reference_blocker_id and reference_blocker_id != blocker_id:
            continue

        manifest_path = Path(manifest_text)
        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest_payload = {}
        manifest = _as_mapping(manifest_payload)
        if not is_managed_manifest(manifest) or _as_scalar_text(manifest.get("run_id")) != run_id:
            # A missing or invalid manifest is not execution evidence.  Keep the
            # compatibility reference in the raw repair snapshot, but do not
            # turn it into a formal claim or attempt.
            continue

        run_kind = _as_scalar_text(manifest.get("run_kind")) or ""
        if run_kind.startswith("automatic_"):
            try:
                validate_automatic_managed_manifest(
                    manifest,
                    manifest_path=manifest_path,
                )
            except (TypeError, ValueError):
                continue

        links = _as_mapping(manifest.get("links"))
        manifest_blocker_id = _as_scalar_text(links.get("blocker_id"))
        if blocker_id and manifest_blocker_id and manifest_blocker_id != blocker_id:
            continue
        reference_request_id = _as_scalar_text(reference.get("repair_request_id"))
        manifest_request_id = _as_scalar_text(links.get("repair_request_id"))
        if reference_request_id and manifest_request_id != reference_request_id:
            continue
        status, live = observed_status(manifest, manifest_path)
        if status in {"reserved", "launching"}:
            state = ATTEMPT_STATE_CLAIMED
        elif status in {"running", "adopting"}:
            state = ATTEMPT_STATE_RUNNING
        elif status == "completed":
            state = ATTEMPT_STATE_SUCCEEDED
        elif status in {"cancelled", "superseded"}:
            state = ATTEMPT_STATE_CANCELLED
        else:
            state = ATTEMPT_STATE_FAILED
        outcome = _as_text(manifest.get("terminal_outcome"))
        if state in {ATTEMPT_STATE_CLAIMED, ATTEMPT_STATE_RUNNING}:
            outcome = REPAIRING
        elif not outcome:
            outcome = status
        raw = {
            "managed_agent_reference": dict(reference),
            "managed_agent_manifest": dict(manifest),
            "observed_status": status,
            "observed_live": live,
        }
        projected.append(
            _build_attempt_record(
                attempt_id=run_id,
                session=session,
                source="managed_agent_execution",
                path=str(manifest_path),
                blocker_id=manifest_blocker_id or reference_blocker_id or blocker_id,
                fingerprint=fingerprint,
                request_id=_as_scalar_text(links.get("repair_request_id"))
                or _as_scalar_text(reference.get("repair_request_id")),
                state=state,
                outcome=outcome,
                recorded_at=_as_text(manifest.get("updated_at"))
                or _as_text(manifest.get("created_at")),
                raw=raw,
            )
        )
    return projected


def _attempts_from_sidecar(
    *,
    sidecar_dir: Path,
    blocker_id: str,
    fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None,
    snapshot_request_ids: set[tuple[str, str]],
    target_session: str = "",
) -> list[RepairCustodyAttemptRecord]:
    path = _sidecar_jsonl_path(sidecar_dir, "attempts")
    records = read_jsonl_records(path, skip_parse_errors=True)
    attempts: list[RepairCustodyAttemptRecord] = []
    for record in records:
        session = _as_scalar_text(record.get("session_id"))
        attempt_id = _as_scalar_text(record.get("attempt_id"))
        if not session or not attempt_id or (session, attempt_id) in snapshot_request_ids:
            continue
        if target_session and session != target_session:
            continue
        if not _problem_signature_matches_fingerprint(record.get("problem_signature"), fingerprint):
            continue
        attempts.append(
            _build_attempt_record(
                attempt_id=attempt_id,
                session=session,
                source="attempt_sidecar",
                path=str(path),
                blocker_id=blocker_id,
                fingerprint=fingerprint,
                request_id=_as_scalar_text(record.get("request_id")),
                state=_attempt_state_from_sidecar(record),
                outcome=_as_text(record.get("outcome")),
                recorded_at=_as_text(record.get("_timestamp")),
                raw=record,
            )
        )
    return attempts


def _build_attempt_record(
    *,
    attempt_id: str,
    session: str,
    source: str,
    path: str,
    blocker_id: str,
    fingerprint: BlockerFingerprintV1 | BlockerFingerprintV2 | None,
    request_id: str,
    state: RepairAttemptState,
    outcome: str,
    recorded_at: str,
    raw: Mapping[str, Any],
    repair_identity: Mapping[str, Any] | None = None,
) -> RepairCustodyAttemptRecord:
    normalized_outcome = outcome or (REPAIRING if state in {ATTEMPT_STATE_CLAIMED, ATTEMPT_STATE_RUNNING} else "")
    normalized_repair_identity = (
        _normalize_repair_identity(repair_identity)
        if repair_identity is not None
        else _normalize_repair_identity(_as_mapping(raw.get("repair_identity")))
    )
    return {
        "attempt_id": attempt_id,
        "session": session,
        "source": source,
        "path": path,
        "blocker_id": blocker_id,
        "blocker_fingerprint": fingerprint,
        "repair_identity": normalized_repair_identity or {},
        "repair_identity_key": _repair_identity_key(normalized_repair_identity),
        "request_id": request_id,
        "state": state,
        "outcome": normalized_outcome,
        "terminal": normalized_outcome != "" and is_terminal_outcome(normalized_outcome),
        "recorded_at": recorded_at,
        "raw": dict(raw),
    }


def _queue_dispatch_attempt_observation(
    record: Mapping[str, Any],
) -> tuple[RepairAttemptState, str, str, Mapping[str, Any]]:
    """Reconcile an immutable launch receipt with its managed-run manifest."""

    default = (
        ATTEMPT_STATE_RUNNING,
        REPAIRING,
        _as_text(record.get("created_at")),
        record,
    )
    run_id = _as_text(record.get("managed_run_id"))
    manifest_text = _as_text(record.get("managed_manifest_path"))
    if not run_id or not manifest_text:
        return default

    from arnold_pipelines.megaplan.managed_agent import is_managed_manifest, observed_status

    manifest_path = Path(manifest_text)
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest_payload = {}
    manifest = _as_mapping(manifest_payload)
    if not isinstance(manifest, Mapping) or not is_managed_manifest(manifest):
        return default
    if _as_text(manifest.get("run_id")) != run_id:
        return default
    links = _as_mapping(manifest.get("links"))
    for record_key, link_key in (
        ("request_id", "repair_request_id"),
        ("blocker_id", "blocker_id"),
    ):
        expected = _as_text(record.get(record_key))
        observed = _as_text(links.get(link_key))
        if expected and observed != expected:
            return default

    status, live = observed_status(manifest, manifest_path)
    if status in {"reserved", "launching"}:
        state = ATTEMPT_STATE_CLAIMED
    elif status in {"running", "adopting"}:
        state = ATTEMPT_STATE_RUNNING
    elif status == "completed":
        state = ATTEMPT_STATE_SUCCEEDED
    elif status in {"cancelled", "superseded"}:
        state = ATTEMPT_STATE_CANCELLED
    else:
        state = ATTEMPT_STATE_FAILED
    outcome = _as_text(manifest.get("terminal_outcome"))
    if state in {ATTEMPT_STATE_CLAIMED, ATTEMPT_STATE_RUNNING}:
        outcome = REPAIRING
    elif not outcome:
        outcome = status
    raw = {
        "dispatch_attempt": dict(record),
        "managed_agent_manifest": dict(manifest),
        "observed_status": status,
        "observed_live": live,
    }
    recorded_at = (
        _as_text(manifest.get("updated_at"))
        or _as_text(manifest.get("finished_at"))
        or _as_text(record.get("created_at"))
    )
    return state, outcome, recorded_at, raw


def _problem_signature_matches_fingerprint(
    problem_signature: Any,
    fingerprint: Mapping[str, Any] | None,
) -> bool:
    signature = _as_mapping(problem_signature)
    if not signature:
        return True
    current = _as_mapping(fingerprint)
    if not current:
        return False
    comparable = (
        ("current_state", "current_state"),
        ("failure_kind", "failure_kind"),
        ("phase_or_step", "phase_or_step"),
        ("milestone_or_plan", "milestone_or_plan"),
        ("blocked_task_id", "blocked_task_id"),
    )
    matched_identity = False
    for sig_key, current_key in comparable:
        sig_value = _as_text(signature.get(sig_key))
        current_value = _as_text(current.get(current_key))
        if sig_value and current_value and sig_value != current_value:
            return False
        if sig_value and current_value:
            matched_identity = True
    # A structurally present but identity-free legacy sidecar cannot own a
    # newer blocker merely because every comparison was skipped.
    return matched_identity


def _attempt_state_from_snapshot(
    payload: Mapping[str, Any],
    record: Mapping[str, Any],
) -> RepairAttemptState:
    outcome = _as_text(payload.get("outcome")) or REPAIRING
    if not is_terminal_outcome(outcome):
        if _attempt_record_is_running(record):
            return ATTEMPT_STATE_RUNNING
        return ATTEMPT_STATE_CLAIMED
    if is_success_outcome(outcome):
        return ATTEMPT_STATE_SUCCEEDED
    if outcome in {"cancelled", "canceled"}:
        return ATTEMPT_STATE_CANCELLED
    return ATTEMPT_STATE_FAILED


def _attempt_state_from_sidecar(record: Mapping[str, Any]) -> RepairAttemptState:
    outcome = _as_text(record.get("outcome"))
    if outcome:
        if not is_terminal_outcome(outcome):
            return ATTEMPT_STATE_RUNNING
        if is_success_outcome(outcome):
            return ATTEMPT_STATE_SUCCEEDED
        if outcome in {"cancelled", "canceled"}:
            return ATTEMPT_STATE_CANCELLED
        return ATTEMPT_STATE_FAILED
    status = _as_text(record.get("status")).lower()
    if status in {"claimed", "queued"}:
        return ATTEMPT_STATE_CLAIMED
    if status in {"running", "active", "repairing", "in_progress"}:
        return ATTEMPT_STATE_RUNNING
    if status in {"succeeded", "complete", "completed"}:
        return ATTEMPT_STATE_SUCCEEDED
    if status in {"cancelled", "canceled"}:
        return ATTEMPT_STATE_CANCELLED
    return ATTEMPT_STATE_FAILED


def _attempt_record_is_running(record: Mapping[str, Any]) -> bool:
    for key in ("mechanical_launch", "kimi_launch"):
        if _as_text(record.get(key)) == "running":
            return True
    return False


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_scalar_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _stable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value[key] for key in sorted(value)}


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def _is_terminal_dispatch_state(current_state: str, terminal_outcomes: list[Any]) -> bool:
    if terminal_outcomes:
        return True
    return current_state in {
        "aborted",
        "cancelled",
        "complete",
        "completed",
        "done",
        "error",
        "failed",
        "resolved",
        "succeeded",
        "success",
    }


def _human_blocker_dispatch_gate(classification: Any) -> RepairDispatchIntent | None:
    if classification is None:
        return None
    from arnold_pipelines.megaplan.cloud.human_blockers import dispatch_gate_for_human_blocker

    return dispatch_gate_for_human_blocker(classification)


def _has_active_repair(
    *,
    lock_evidence: Any,
    process_evidence: Mapping[str, Any] | None,
    custody: Mapping[str, Any],
) -> bool:
    if durable_repair_active(custody):
        return True

    # A compatibility lock can corroborate custody, but it cannot manufacture
    # the request/blocker identity that custody requires.
    blocker_id = _as_text(custody.get("blocker_id"))
    active_request_ids = {
        _as_text(value)
        for value in _as_list(custody.get("active_request_ids"))
        if _as_text(value)
    }
    if not blocker_id or not active_request_ids:
        return False

    lock_status = _as_text(getattr(lock_evidence, "status", ""))
    if not lock_status and isinstance(lock_evidence, Mapping):
        lock_status = _as_text(lock_evidence.get("status"))
    if lock_status in {"acquired", "busy", "claimed", "already_claimed"}:
        return True

    # Process liveness is provisional transport evidence.  Without a durable
    # blocker-scoped claim or lock it must not suppress a fresh repair owner.
    return False


def _is_known_repairable_shape(
    *,
    current_state: str,
    retry_strategy: str,
    failure_kind: str,
    current_target: Mapping[str, Any],
    semantic_findings: list[Any] | None = None,
) -> bool:
    if _has_terminality_contradiction(current_target):
        return True
    # The executor detected that the persisted cursor and control projection
    # disagree.  This is a mechanical state-machine contradiction: it must be
    # handed to L1 with current-target evidence, never converted into a human
    # gate or terminal outcome.
    if (
        current_state == "blocked"
        and failure_kind == "workflow_cursor_mismatch"
        and _has_current_target_evidence(current_target)
    ):
        return True
    # --- primary: latest_failure-based classification --------------------
    if current_state == "failed" and retry_strategy == "repair_state" and failure_kind == "no_next_step":
        return _has_current_target_evidence(current_target)
    resume_authority_failure = _as_mapping(
        _as_mapping(current_target.get("event_cursors", {})).get("resume_authority_failure", {})
    )
    if (
        current_state == "failed"
        and retry_strategy == "rerun_phase"
        and failure_kind in {"phase_failed", "execution_blocked"}
        and _as_text(resume_authority_failure.get("code")) == "resume_execute_authority_blocked"
        and _as_text(resume_authority_failure.get("reason")) == "execute_authority_diverged"
    ):
        return _has_current_target_evidence(current_target)
    if current_state == "blocked" and retry_strategy == "manual_review" and failure_kind in {
        "blocked_recovery_not_resolved",
        "execution_blocked",
        "no_next_step_state_mapping_failure",
    }:
        return _has_current_target_evidence(current_target)

    # --- fallback: semantic findings indicate repairable issues ----------
    if not failure_kind and current_state in {"blocked", "failed", ""}:
        if semantic_findings is not None and len(semantic_findings) > 0:
            classified = _classify_repairable_from_findings(semantic_findings)
            if classified["has_repairable"]:
                return _has_current_target_evidence(current_target)

    return False


def _has_terminality_contradiction(current_target: Mapping[str, Any]) -> bool:
    """Return true for states that must reopen custody despite a success label."""
    target = _as_mapping(current_target)
    active_step = _as_mapping(target.get("active_step_heartbeat"))
    if (
        (bool(active_step.get("active")) or _as_text(active_step.get("worker_pid")))
        and active_step.get("pid_live") is not True
    ):
        return _has_current_target_evidence(target)
    stale_kinds = {
        _as_text(_as_mapping(item).get("kind"))
        for item in _as_list(target.get("stale_evidence"))
        if isinstance(item, Mapping)
    }
    if "stale_active_step_dead_pid" in stale_kinds:
        return _has_current_target_evidence(target)
    chain = _as_mapping(target.get("chain_state"))
    try:
        total = int(chain.get("milestone_total"))
        completed = int(chain.get("completed_count") or 0)
    except (TypeError, ValueError):
        return False
    return total > 0 and completed < total and _has_current_target_evidence(target)


def _has_current_target_evidence(current_target: Mapping[str, Any]) -> bool:
    target_payload = _as_mapping(current_target)
    current_refs = _as_mapping(target_payload.get("current_refs"))
    plan_state = _as_mapping(target_payload.get("plan_state"))
    chain_state = _as_mapping(target_payload.get("chain_state"))
    authoritative_source = _as_text(target_payload.get("authoritative_source"))
    if _as_text(plan_state.get("fingerprint")):
        return True
    if _as_text(chain_state.get("fingerprint")):
        return True
    if authoritative_source and authoritative_source != "marker" and _as_text(
        current_refs.get("current_plan_name")
    ):
        return True
    return bool(plan_state.get("present")) or bool(chain_state.get("present"))


# ---- ordinary repair completion verdict evidence -----------------------------

_ORDINARY_REPAIR_COMPLETION_BOUNDARY_ID = "ordinary_repair_completion"
_ORDINARY_REPAIR_COMPLETION_ROW_ID = "repair.ordinary_complete.1"

RepairVerdictKind = Literal["cleared", "no_fix", "escalated", "stale", "no_verdict"]
REPAIR_VERDICT_CLEARED: RepairVerdictKind = "cleared"
REPAIR_VERDICT_NO_FIX: RepairVerdictKind = "no_fix"
REPAIR_VERDICT_ESCALATED: RepairVerdictKind = "escalated"
REPAIR_VERDICT_STALE: RepairVerdictKind = "stale"
REPAIR_VERDICT_NO_VERDICT: RepairVerdictKind = "no_verdict"
REPAIR_VERDICT_KINDS: frozenset[RepairVerdictKind] = frozenset(
    {
        REPAIR_VERDICT_CLEARED,
        REPAIR_VERDICT_NO_FIX,
        REPAIR_VERDICT_ESCALATED,
        REPAIR_VERDICT_STALE,
        REPAIR_VERDICT_NO_VERDICT,
    }
)

# Outcomes that correspond to each verdict kind when building verdicts from
# existing repair-data outcomes.
_OUTCOME_TO_VERDICT_KIND: dict[str, RepairVerdictKind] = {
    COMPLETE: REPAIR_VERDICT_CLEARED,
    PROGRESSED: REPAIR_VERDICT_CLEARED,
    TRUE_HUMAN_BLOCKER: REPAIR_VERDICT_ESCALATED,
    NEEDS_HUMAN: REPAIR_VERDICT_ESCALATED,
    REPAIR_EXHAUSTED: REPAIR_VERDICT_NO_FIX,
    REPAIR_TIMEOUT: REPAIR_VERDICT_NO_FIX,
    PARTIAL_LIVENESS: REPAIR_VERDICT_NO_VERDICT,
    "live_with_fresh_activity": REPAIR_VERDICT_NO_VERDICT,
    "recurring_retry_pending": REPAIR_VERDICT_NO_FIX,
    "deterministic_failure": REPAIR_VERDICT_NO_FIX,
    "discord_escalated": REPAIR_VERDICT_ESCALATED,
}

# Maximum age for repair data before it is considered stale.
_DEFAULT_REPAIR_DATA_STALE_SECS: int = 86400  # 24 hours


@dataclass(frozen=True)
class RepairVerdict:
    """Structured ordinary repair completion verdict evidence.

    Carries the original finding/blocker identity, attempted actions,
    before/after evidence refs, the verdict kind, and durable refs so
    downstream consumers (auditor, custody, status) can decide whether
    a liveness-only outcome is trustworthy.
    """

    verdict_kind: RepairVerdictKind
    blocker_id: str
    attempted_actions: tuple[str, ...] = ()
    before_evidence_refs: tuple[str, ...] = ()
    after_evidence_refs: tuple[str, ...] = ()
    durable_refs: tuple[str, ...] = ()
    evidence_timestamp: str = ""
    contract_id: str = _ORDINARY_REPAIR_COMPLETION_ROW_ID
    boundary_id: str = _ORDINARY_REPAIR_COMPLETION_BOUNDARY_ID
    session: str = ""
    request_id: str = ""
    outcome: str = ""
    stale_detected: bool = False
    no_verdict_detected: bool = False
    stale_reason: str = ""
    no_verdict_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict_kind": self.verdict_kind,
            "blocker_id": self.blocker_id,
            "attempted_actions": list(self.attempted_actions),
            "before_evidence_refs": list(self.before_evidence_refs),
            "after_evidence_refs": list(self.after_evidence_refs),
            "durable_refs": list(self.durable_refs),
            "evidence_timestamp": self.evidence_timestamp,
            "contract_id": self.contract_id,
            "boundary_id": self.boundary_id,
            "session": self.session,
            "request_id": self.request_id,
            "outcome": self.outcome,
            "stale_detected": self.stale_detected,
            "no_verdict_detected": self.no_verdict_detected,
            "stale_reason": self.stale_reason,
            "no_verdict_reason": self.no_verdict_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RepairVerdict":
        verdict_kind = _as_text(payload.get("verdict_kind"))
        if verdict_kind not in REPAIR_VERDICT_KINDS:
            verdict_kind = REPAIR_VERDICT_NO_VERDICT
        return cls(
            verdict_kind=cast(RepairVerdictKind, verdict_kind),
            blocker_id=_as_text(payload.get("blocker_id")),
            attempted_actions=tuple(
                _as_text(item) for item in _as_list(payload.get("attempted_actions")) if _as_text(item)
            ),
            before_evidence_refs=tuple(
                _as_text(item) for item in _as_list(payload.get("before_evidence_refs")) if _as_text(item)
            ),
            after_evidence_refs=tuple(
                _as_text(item) for item in _as_list(payload.get("after_evidence_refs")) if _as_text(item)
            ),
            durable_refs=tuple(
                _as_text(item) for item in _as_list(payload.get("durable_refs")) if _as_text(item)
            ),
            evidence_timestamp=_as_text(payload.get("evidence_timestamp")),
            contract_id=_as_text(payload.get("contract_id")) or _ORDINARY_REPAIR_COMPLETION_ROW_ID,
            boundary_id=_as_text(payload.get("boundary_id")) or _ORDINARY_REPAIR_COMPLETION_BOUNDARY_ID,
            session=_as_text(payload.get("session")),
            request_id=_as_text(payload.get("request_id")),
            outcome=_as_text(payload.get("outcome")),
            stale_detected=bool(payload.get("stale_detected")),
            no_verdict_detected=bool(payload.get("no_verdict_detected")),
            stale_reason=_as_text(payload.get("stale_reason")),
            no_verdict_reason=_as_text(payload.get("no_verdict_reason")),
        )


def build_ordinary_repair_verdict(
    *,
    repair_data_payload: Mapping[str, Any] | None = None,
    session: str = "",
    request_id: str = "",
    blocker_id: str = "",
    attempted_actions: tuple[str, ...] | None = None,
    before_evidence_refs: tuple[str, ...] | None = None,
    after_evidence_refs: tuple[str, ...] | None = None,
    durable_refs: tuple[str, ...] | None = None,
    repair_goal_status_override: str = "",
    timestamp: str | None = None,
) -> RepairVerdict:
    """Build a structured ordinary repair completion verdict from available evidence.

    When *repair_data_payload* is provided, the outcome is mapped to a verdict kind
    via the canonical outcome-to-verdict table. When it is absent or the outcome is
    unrecognized, the verdict defaults to ``no_verdict``.

    Staleness and no-verdict detection are run against the payload and appended
    as structured flags.
    """
    payload = _as_mapping(repair_data_payload)
    outcome = _as_text(payload.get("outcome"))
    verdict_kind = _OUTCOME_TO_VERDICT_KIND.get(outcome, REPAIR_VERDICT_NO_VERDICT)

    # A repair process/result is not the semantic completion authority when a
    # durable repair goal is linked.  Fail closed unless that goal itself has
    # authoritative progress or an explicit approval gate.
    repair_goal = _as_mapping(payload.get("repair_goal"))
    repair_goal_path = _as_text(repair_goal.get("goal_path"))
    repair_goal_status = ""
    if repair_goal_path:
        try:
            goal_payload = json.loads(Path(repair_goal_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            goal_payload = {}
        if isinstance(goal_payload, Mapping):
            repair_goal_status = _as_text(goal_payload.get("status"))
        override = _as_text(repair_goal_status_override)
        expected_override = {
            "progressed": "progressed",
            "true_human_blocker": "approval_required",
        }.get(outcome, "")
        if override and override == expected_override:
            # The goal evaluator's returned terminal status is authoritative
            # for this outcome.  Carry it across the verdict write so a
            # concurrent stale goal-file writer cannot turn a verified
            # terminal result back into no-verdict.
            repair_goal_status = override
        if repair_goal_status not in {"progressed", "approval_required"}:
            verdict_kind = REPAIR_VERDICT_NO_VERDICT

    stale_detected = False
    stale_reason = ""
    if payload:
        stale_detected, stale_reason = detect_stale_repair_data(payload)

    no_verdict_detected = False
    no_verdict_reason = ""
    if verdict_kind == REPAIR_VERDICT_NO_VERDICT or not outcome:
        no_verdict_detected, no_verdict_reason = detect_no_verdict_artifact(payload)
        if repair_goal_path and repair_goal_status not in {"progressed", "approval_required"}:
            no_verdict_detected = True
            no_verdict_reason = (
                "durable repair goal remains active at the captured frozen checkpoint"
            )

    evidence_ts = timestamp or _as_text(payload.get("evidence_timestamp") or payload.get("completed_at") or "")
    if not evidence_ts:
        evidence_ts = utc_now_iso()

    return RepairVerdict(
        verdict_kind=verdict_kind,
        blocker_id=blocker_id or _as_text(payload.get("blocker_id")),
        attempted_actions=attempted_actions or (),
        before_evidence_refs=before_evidence_refs or (),
        after_evidence_refs=after_evidence_refs or (),
        durable_refs=durable_refs or (),
        evidence_timestamp=evidence_ts,
        contract_id=_ORDINARY_REPAIR_COMPLETION_ROW_ID,
        boundary_id=_ORDINARY_REPAIR_COMPLETION_BOUNDARY_ID,
        session=session or _as_text(payload.get("session")),
        request_id=request_id or _as_text(payload.get("request_id")),
        outcome=outcome,
        stale_detected=stale_detected,
        no_verdict_detected=no_verdict_detected,
        stale_reason=stale_reason,
        no_verdict_reason=no_verdict_reason,
    )


def detect_stale_repair_data(
    payload: Mapping[str, Any],
    *,
    stale_threshold_secs: int = _DEFAULT_REPAIR_DATA_STALE_SECS,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Return ``(True, reason)`` when *payload* is stale, else ``(False, "")``.

    Staleness is detected by comparing the latest completed-at / last-success-at
    timestamp against *stale_threshold_secs*.  A payload with no timestamp is
    considered stale with an appropriate reason.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    completed_at = _as_text(payload.get("completed_at"))
    last_success_at = _as_text(payload.get("last_success_at"))
    timestamp_text = completed_at or last_success_at

    if not timestamp_text:
        return True, "repair data has no completion or success timestamp"

    try:
        ts = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True, f"unparseable timestamp: {timestamp_text!r}"

    age_secs = (now - ts).total_seconds()
    if age_secs > stale_threshold_secs:
        return True, (
            f"repair data age {age_secs:.0f}s exceeds stale threshold "
            f"{stale_threshold_secs}s (timestamp={timestamp_text})"
        )

    return False, ""


def detect_no_verdict_artifact(
    payload: Mapping[str, Any],
) -> tuple[bool, str]:
    """Return ``(True, reason)`` when *payload* has no meaningful verdict evidence.

    A verdict is absent when there is no outcome or the outcome is liveness-only
    (``partial_liveness`` / ``live_with_fresh_activity``) and no before/after
    evidence refs exist.
    """
    outcome = _as_text(payload.get("outcome"))
    if not outcome:
        return True, "repair data payload has no outcome field"

    liveness_outcomes = {PARTIAL_LIVENESS, "live_with_fresh_activity"}
    if outcome in liveness_outcomes:
        before = _as_list(payload.get("before_evidence_refs") or payload.get("before_evidence") or [])
        after = _as_list(payload.get("after_evidence_refs") or payload.get("after_evidence") or [])
        if not before and not after:
            return True, f"liveness-only outcome {outcome!r} with no before/after evidence refs"

    if outcome == REPAIRING:
        return True, "repair data is still in non-terminal repairing state"

    return False, ""


def save_repair_verdict(
    path: str | Path,
    verdict: RepairVerdict,
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Validate and atomically persist a repair verdict JSON artifact.

    The verdict is persisted alongside existing repair data so that downstream
    custody/auditor/status consumers can read it without recomputing the mapping.
    """
    prepared = verdict.to_dict()
    if redactor is not None:
        prepared = _redact_verdict_payload(prepared, redactor)
    atomic_write_json(path, prepared)
    return prepared


def validate_repair_verdict_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a repair verdict payload, raising ``ValueError`` on bad input."""
    if not isinstance(payload, Mapping):
        raise ValueError("repair verdict must be a JSON object")
    verdict_kind = _as_text(payload.get("verdict_kind"))
    if not verdict_kind:
        raise ValueError("repair verdict missing required field 'verdict_kind'")
    if verdict_kind not in REPAIR_VERDICT_KINDS:
        raise ValueError(
            f"unknown repair verdict kind {verdict_kind!r}; "
            f"expected one of {sorted(REPAIR_VERDICT_KINDS)}"
        )
    return dict(payload)


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_verdict_payload(
    payload: dict[str, Any],
    redactor: Callable[[str], str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            result[key] = redactor(value)
        elif isinstance(value, list):
            result[key] = [redactor(item) if isinstance(item, str) else item for item in value]
        else:
            result[key] = value
    return result


# ---- cloud custody classification evidence ----------------------------------

# Stable contract IDs from the boundary-contracts registry.
_CUSTODY_MANAGED_RUNNING_ROW_ID = "custody.managed_running.1"
_CUSTODY_COMPLETE_ROW_ID = "custody.complete.1"
_CUSTODY_UNMANAGED_WARNING_ROW_ID = "custody.unmanaged_warning.1"
_CUSTODY_BLOCKED_RELAUNCH_ROW_ID = "custody.blocked_relaunch.1"
_CUSTODY_ESCALATED_UNCHANGED_ROW_ID = "custody.escalated_unchanged.1"

_CUSTODY_MANAGED_RUNNING_BOUNDARY_ID = "cloud_custody_managed_running"
_CUSTODY_COMPLETE_BOUNDARY_ID = "cloud_custody_complete"
_CUSTODY_UNMANAGED_WARNING_BOUNDARY_ID = "cloud_custody_unmanaged_running_warning"
_CUSTODY_BLOCKED_RELAUNCH_BOUNDARY_ID = "cloud_custody_blocked_relaunch_failure"
_CUSTODY_ESCALATED_UNCHANGED_BOUNDARY_ID = "cloud_custody_escalated_repeated_unchanged"

CloudCustodyKind = Literal[
    "managed-running",
    "complete",
    "unmanaged-running-with-warning",
    "blocked-relaunch-failure",
    "escalated-repeated-unchanged-findings",
]
CUSTODY_MANAGED_RUNNING: CloudCustodyKind = "managed-running"
CUSTODY_COMPLETE: CloudCustodyKind = "complete"
CUSTODY_UNMANAGED_WARNING: CloudCustodyKind = "unmanaged-running-with-warning"
CUSTODY_BLOCKED_RELAUNCH: CloudCustodyKind = "blocked-relaunch-failure"
CUSTODY_ESCALATED_UNCHANGED: CloudCustodyKind = "escalated-repeated-unchanged-findings"
CLOUD_CUSTODY_KINDS: frozenset[CloudCustodyKind] = frozenset(
    {
        CUSTODY_MANAGED_RUNNING,
        CUSTODY_COMPLETE,
        CUSTODY_UNMANAGED_WARNING,
        CUSTODY_BLOCKED_RELAUNCH,
        CUSTODY_ESCALATED_UNCHANGED,
    }
)

# Map custody kind -> (row_id, boundary_id).
_CUSTODY_KIND_TO_CONTRACT_IDS: dict[CloudCustodyKind, tuple[str, str]] = {
    CUSTODY_MANAGED_RUNNING: (_CUSTODY_MANAGED_RUNNING_ROW_ID, _CUSTODY_MANAGED_RUNNING_BOUNDARY_ID),
    CUSTODY_COMPLETE: (_CUSTODY_COMPLETE_ROW_ID, _CUSTODY_COMPLETE_BOUNDARY_ID),
    CUSTODY_UNMANAGED_WARNING: (_CUSTODY_UNMANAGED_WARNING_ROW_ID, _CUSTODY_UNMANAGED_WARNING_BOUNDARY_ID),
    CUSTODY_BLOCKED_RELAUNCH: (_CUSTODY_BLOCKED_RELAUNCH_ROW_ID, _CUSTODY_BLOCKED_RELAUNCH_BOUNDARY_ID),
    CUSTODY_ESCALATED_UNCHANGED: (_CUSTODY_ESCALATED_UNCHANGED_ROW_ID, _CUSTODY_ESCALATED_UNCHANGED_BOUNDARY_ID),
}


@dataclass(frozen=True)
class CloudCustodyClassification:
    """Structured cloud custody classification evidence.

    Captures the custody determination for a cloud session — whether it is
    under managed supervision, complete, running but unmanaged, blocked with
    failed relaunch, or escalated due to repeated unchanged findings.

    Every field is evidence-backed: tmux/session identity, supervisor identity,
    live process fingerprints, active-step worker PID liveness, relaunch
    commands, and failure reasons all contribute to the classification.
    """

    custody_kind: CloudCustodyKind
    session_id: str = ""
    supervisor_identity: str = ""
    live_process_fingerprints: tuple[str, ...] = ()
    active_step_worker_pid_liveness: bool = False
    relaunch_command: str = ""
    relaunch_command_available: bool = False
    failure_reasons: tuple[str, ...] = ()
    evidence_timestamp: str = ""
    contract_id: str = ""
    boundary_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        contract_id, boundary_id = _CUSTODY_KIND_TO_CONTRACT_IDS.get(
            self.custody_kind, ("", "")
        )
        return {
            "custody_kind": self.custody_kind,
            "session_id": self.session_id,
            "supervisor_identity": self.supervisor_identity,
            "live_process_fingerprints": list(self.live_process_fingerprints),
            "active_step_worker_pid_liveness": self.active_step_worker_pid_liveness,
            "relaunch_command": self.relaunch_command,
            "relaunch_command_available": self.relaunch_command_available,
            "failure_reasons": list(self.failure_reasons),
            "evidence_timestamp": self.evidence_timestamp,
            "contract_id": self.contract_id or contract_id,
            "boundary_id": self.boundary_id or boundary_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CloudCustodyClassification":
        custody_kind = _as_text(payload.get("custody_kind"))
        if custody_kind not in CLOUD_CUSTODY_KINDS:
            custody_kind = CUSTODY_ESCALATED_UNCHANGED
        return cls(
            custody_kind=cast(CloudCustodyKind, custody_kind),
            session_id=_as_text(payload.get("session_id")),
            supervisor_identity=_as_text(payload.get("supervisor_identity")),
            live_process_fingerprints=tuple(
                _as_text(item) for item in _as_list(payload.get("live_process_fingerprints"))
                if _as_text(item)
            ),
            active_step_worker_pid_liveness=bool(
                payload.get("active_step_worker_pid_liveness")
            ),
            relaunch_command=_as_text(payload.get("relaunch_command")),
            relaunch_command_available=bool(payload.get("relaunch_command_available")),
            failure_reasons=tuple(
                _as_text(item) for item in _as_list(payload.get("failure_reasons"))
                if _as_text(item)
            ),
            evidence_timestamp=_as_text(payload.get("evidence_timestamp")),
            contract_id=_as_text(payload.get("contract_id")),
            boundary_id=_as_text(payload.get("boundary_id")),
        )


def build_cloud_custody_classification(
    *,
    custody_kind: CloudCustodyKind,
    session_id: str = "",
    supervisor_identity: str = "",
    live_process_fingerprints: tuple[str, ...] | None = None,
    active_step_worker_pid_liveness: bool = False,
    relaunch_command: str = "",
    relaunch_command_available: bool = False,
    failure_reasons: tuple[str, ...] | None = None,
    evidence_timestamp: str | None = None,
) -> CloudCustodyClassification:
    """Build a structured cloud custody classification from available evidence.

    The *custody_kind* is the primary classification; all other fields are
    evidence supporting that determination.  Contract IDs are derived
    automatically from the custody kind via the boundary-contracts registry
    mapping.
    """
    contract_id, boundary_id = _CUSTODY_KIND_TO_CONTRACT_IDS.get(
        custody_kind, ("", "")
    )
    ts = evidence_timestamp or utc_now_iso()
    return CloudCustodyClassification(
        custody_kind=custody_kind,
        session_id=session_id,
        supervisor_identity=supervisor_identity,
        live_process_fingerprints=live_process_fingerprints or (),
        active_step_worker_pid_liveness=active_step_worker_pid_liveness,
        relaunch_command=relaunch_command,
        relaunch_command_available=relaunch_command_available or bool(relaunch_command),
        failure_reasons=failure_reasons or (),
        evidence_timestamp=ts,
        contract_id=contract_id,
        boundary_id=boundary_id,
    )


def classify_cloud_custody(
    *,
    session_id: str = "",
    supervisor_identity: str = "",
    tmux_live: bool = False,
    process_live: bool = False,
    active_step_worker_pid_liveness: bool = False,
    watchdog_status: str = "",
    chain_complete: bool = False,
    relaunch_command: str = "",
    relaunch_command_available: bool = False,
    needs_human: bool = False,
    repair_active: bool = False,
    failure_reasons: tuple[str, ...] | None = None,
    previous_classification: CloudCustodyKind | None = None,
    finding_unchanged_count: int = 0,
) -> CloudCustodyClassification:
    """Classify cloud custody from session evidence.

    This is the canonical classification function that all custody producers
    should call.  It produces one of the five accepted custody outcomes based
    on the evidence provided, applying the precedence rules:

    1. **complete** — chain is complete (watchdog confirms) and no live process.
    2. **managed-running** — tmux session is live OR a process with a known
       fingerprint is running, and the session is under managed supervision.
    3. **unmanaged-running-with-warning** — process is live but not through a
       managed tmux session (orphan process, detached runner, etc.).
    4. **blocked-relaunch-failure** — session needs relaunch but the relaunch
       command is unavailable or has failed.
    5. **escalated-repeated-unchanged-findings** — repeated findings with no
       change in classification over multiple sweeps.

    The caller is responsible for providing accurate evidence; this function
    applies the decision rules without performing its own I/O.
    """
    reasons: list[str] = list(failure_reasons or [])

    # ── 1. Complete takes precedence ──────────────────────────────────────
    if chain_complete:
        return build_cloud_custody_classification(
            custody_kind=CUSTODY_COMPLETE,
            session_id=session_id,
            supervisor_identity=supervisor_identity,
            live_process_fingerprints=(),
            active_step_worker_pid_liveness=False,
            relaunch_command=relaunch_command,
            relaunch_command_available=relaunch_command_available,
            failure_reasons=("chain complete; no runner expected",),
        )

    # ── 2. Managed running: tmux session is live ──────────────────────────
    if tmux_live:
        return build_cloud_custody_classification(
            custody_kind=CUSTODY_MANAGED_RUNNING,
            session_id=session_id,
            supervisor_identity=supervisor_identity,
            live_process_fingerprints=(f"tmux:{session_id}",),
            active_step_worker_pid_liveness=active_step_worker_pid_liveness,
            relaunch_command=relaunch_command,
            relaunch_command_available=relaunch_command_available,
            failure_reasons=(),
        )

    # ── 3. Managed running: process is live via known fingerprint ─────────
    if process_live and tmux_live is False:
        # When process is live but not through tmux, classify based on
        # whether there is a known supervisor identity.
        if supervisor_identity:
            return build_cloud_custody_classification(
                custody_kind=CUSTODY_MANAGED_RUNNING,
                session_id=session_id,
                supervisor_identity=supervisor_identity,
                live_process_fingerprints=(f"process:{session_id}",),
                active_step_worker_pid_liveness=active_step_worker_pid_liveness,
                relaunch_command=relaunch_command,
                relaunch_command_available=relaunch_command_available,
                failure_reasons=(),
            )
        # Process is live but unmanaged — tmux session missing.
        unmanaged_reasons: list[str] = [
            "process is live but no managed tmux session found",
        ]
        if not supervisor_identity:
            unmanaged_reasons.append("supervisor identity unknown")
        return build_cloud_custody_classification(
            custody_kind=CUSTODY_UNMANAGED_WARNING,
            session_id=session_id,
            supervisor_identity=supervisor_identity,
            live_process_fingerprints=(f"process:{session_id}",),
            active_step_worker_pid_liveness=active_step_worker_pid_liveness,
            relaunch_command=relaunch_command,
            relaunch_command_available=relaunch_command_available,
            failure_reasons=tuple(unmanaged_reasons),
        )

    # ── 4. No live process: blocked or escalated ──────────────────────────
    if watchdog_status in {"needs_human", "restarted", "reaped", "stalled"}:
        reasons.append(f"watchdog status: {watchdog_status}")

    if needs_human and not repair_active:
        reasons.append("needs-human marker present, no active repair")

    # 4a. Blocked relaunch failure: relaunch is needed but unavailable/failed.
    if not relaunch_command_available or not relaunch_command:
        if not chain_complete:
            reasons.append("relaunch command unavailable or empty")
            return build_cloud_custody_classification(
                custody_kind=CUSTODY_BLOCKED_RELAUNCH,
                session_id=session_id,
                supervisor_identity=supervisor_identity,
                live_process_fingerprints=(),
                active_step_worker_pid_liveness=False,
                relaunch_command=relaunch_command,
                relaunch_command_available=False,
                failure_reasons=tuple(reasons),
            )

    # 4b. Escalated repeated unchanged findings: same classification persists.
    if (
        previous_classification is not None
        and previous_classification != CUSTODY_COMPLETE
        and previous_classification != CUSTODY_MANAGED_RUNNING
        and finding_unchanged_count >= 2
    ):
        reasons.append(
            f"finding unchanged for {finding_unchanged_count} consecutive sweeps "
            f"(previous: {previous_classification})"
        )
        return build_cloud_custody_classification(
            custody_kind=CUSTODY_ESCALATED_UNCHANGED,
            session_id=session_id,
            supervisor_identity=supervisor_identity,
            live_process_fingerprints=(),
            active_step_worker_pid_liveness=False,
            relaunch_command=relaunch_command,
            relaunch_command_available=relaunch_command_available,
            failure_reasons=tuple(reasons),
        )

    # 4c. Default when no live process and no escalation: blocked.
    if not reasons:
        reasons.append("no live process and no clear failure reason")
    return build_cloud_custody_classification(
        custody_kind=CUSTODY_BLOCKED_RELAUNCH,
        session_id=session_id,
        supervisor_identity=supervisor_identity,
        live_process_fingerprints=(),
        active_step_worker_pid_liveness=False,
        relaunch_command=relaunch_command,
        relaunch_command_available=relaunch_command_available,
        failure_reasons=tuple(reasons),
    )


def save_cloud_custody_classification(
    path: str | Path,
    classification: CloudCustodyClassification,
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Validate and atomically persist a cloud custody classification artifact.

    The classification is persisted alongside session data so that downstream
    custody/auditor/status consumers can read it without recomputing.
    """
    prepared = classification.to_dict()
    if redactor is not None:
        prepared = _redact_verdict_payload(prepared, redactor)
    atomic_write_json(path, prepared)
    return prepared


def validate_cloud_custody_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a cloud custody payload, raising ``ValueError`` on bad input."""
    if not isinstance(payload, Mapping):
        raise ValueError("cloud custody classification must be a JSON object")
    custody_kind = _as_text(payload.get("custody_kind"))
    if not custody_kind:
        raise ValueError(
            "cloud custody classification missing required field 'custody_kind'"
        )
    if custody_kind not in CLOUD_CUSTODY_KINDS:
        raise ValueError(
            f"unknown cloud custody kind {custody_kind!r}; "
            f"expected one of {sorted(CLOUD_CUSTODY_KINDS)}"
        )
    return dict(payload)


# ── S4: semantic-health projection for repair initial facts ─────────────


def build_repair_semantic_context(
    *,
    plan_dir: Path | None = None,
    session_id: str = "",
    findings: list[Any] | None = None,
    cloud_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a semantic-health + custody projection for repair initial facts.

    When *plan_dir* is provided, calls :func:`inspect_semantic_health` and
    projects findings through :func:`cloud_counts_summary`.  When *findings*
    is provided directly (e.g. from a pre-computed inspection), uses those
    findings instead of re-inspecting.

    The returned payload is suitable for embedding directly into
    ``initial_facts`` under ``semantic_context`` or ``semantic_health``.

    Returns a dict with:

    * ``semantic_counts`` — cloud_counts_summary projection
    * ``has_repairable`` — bool indicating whether any findings are repairable
    * ``repairable_details`` — list of compact repairable finding summaries
    * ``custody_projection`` — custody classification hints derived from findings
    """
    result: dict[str, Any] = {
        "schema": "arnold.workflow.repair_semantic_context.v1",
        "session_id": session_id,
        "semantic_counts": {},
        "has_repairable": False,
        "repairable_details": [],
        "custody_projection": {},
    }

    resolved_findings: list[Any]
    if findings is not None:
        resolved_findings = list(findings)
    elif plan_dir is not None and plan_dir.is_dir():
        try:
            from arnold_pipelines.megaplan.cloud.semantic_findings import (
                cloud_counts_summary,
            )
            from arnold_pipelines.megaplan.semantic_health import (
                inspect_semantic_health,
            )

            resolved_findings = inspect_semantic_health(plan_dir)
            result["semantic_counts"] = cloud_counts_summary(
                resolved_findings, session_id=session_id
            )
        except Exception:
            return result
    else:
        return result

    # Apply cloud_meta regardless of whether findings are empty
    if isinstance(cloud_meta, Mapping):
        target = cloud_meta.get("target")
        if target is not None:
            result["cloud_target"] = str(target)
        provider = cloud_meta.get("provider")
        if provider is not None:
            result["cloud_provider"] = str(provider)

    if not resolved_findings:
        return result

    # If semantic_counts wasn't populated (findings provided directly), compute it
    if not result["semantic_counts"]:
        try:
            from arnold_pipelines.megaplan.cloud.semantic_findings import (
                cloud_counts_summary,
            )

            result["semantic_counts"] = cloud_counts_summary(
                resolved_findings, session_id=session_id
            )
        except Exception:
            pass

    repairable = _classify_repairable_from_findings(resolved_findings)
    result["has_repairable"] = repairable["has_repairable"]
    result["repairable_details"] = repairable["details"]
    result["custody_projection"] = repairable.get("custody_projection", {})

    return result


_REPAIRABLE_DIAGNOSTIC_CODES: frozenset[str] = frozenset(
    {
        "AWF246_BOUNDARY_CONTRACT_MISSING",
        "AWF247_BOUNDARY_EVIDENCE_MISSING",
        "AWF248_BOUNDARY_EVIDENCE_WITHOUT_SOURCE",
        "AWF249_BOUNDARY_EVIDENCE_STALE",
        "AWF250_UNKNOWN_OUTCOME_TYPE",
        "AWF003_MISSING_WORKFLOW_DECLARATION",
        "AWF022_MISSING_PROMPT_DEPENDENCY",
        "AWF023_MISSING_RESOURCE_DEPENDENCY",
        "AWF245_ROW_EVIDENCE_INSUFFICIENCY",
    }
)

_ERROR_SEVERITY_VALUES: frozenset[str] = frozenset({"error", "ERROR"})


def _classify_repairable_from_findings(
    findings: list[Any],
) -> dict[str, Any]:
    """Classify whether a set of semantic findings contains repairable issues.

    Returns a dict with ``has_repairable``, ``details``, and
    ``custody_projection`` fields derived from the finding severities and
    diagnostic codes.
    """
    repairable_details: list[dict[str, Any]] = []
    custody_kinds: set[str] = set()

    for finding in findings:
        severity = (
            getattr(finding, "severity", None)
            if hasattr(finding, "severity")
            else (finding.get("severity") if isinstance(finding, Mapping) else None)
        )
        severity_value = (
            severity.value if hasattr(severity, "value") else str(severity or "")
        )
        diagnostic_code = (
            getattr(finding, "diagnostic_code", None)
            if hasattr(finding, "diagnostic_code")
            else (
                finding.get("diagnostic_code")
                if isinstance(finding, Mapping)
                else None
            )
        )
        diagnostic_value = (
            diagnostic_code.value
            if hasattr(diagnostic_code, "value")
            else str(diagnostic_code or "")
        )

        if severity_value not in _ERROR_SEVERITY_VALUES:
            continue

        if diagnostic_value in _REPAIRABLE_DIAGNOSTIC_CODES:
            custody_kinds.add("boundary_evidence_repairable")

        finding_id = (
            getattr(finding, "finding_id", "")
            if hasattr(finding, "finding_id")
            else (finding.get("finding_id", "") if isinstance(finding, Mapping) else "")
        )
        boundary_id = (
            getattr(finding, "boundary_id", "")
            if hasattr(finding, "boundary_id")
            else (
                finding.get("boundary_id", "") if isinstance(finding, Mapping) else ""
            )
        )
        description = (
            getattr(finding, "description", "")
            if hasattr(finding, "description")
            else (
                finding.get("description", "") if isinstance(finding, Mapping) else ""
            )
        )

        repairable_details.append(
            {
                "finding_id": str(finding_id),
                "boundary_id": str(boundary_id),
                "severity": severity_value,
                "diagnostic_code": diagnostic_value,
                "description": str(description)[:200],
            }
        )

    custody_projection: dict[str, Any] = {}
    if custody_kinds:
        custody_projection["repair_domains"] = sorted(custody_kinds)
        if "boundary_evidence_repairable" in custody_kinds:
            custody_projection["suggested_custody_bucket"] = "repairable_not_repairing"

    return {
        "has_repairable": len(repairable_details) > 0,
        "details": repairable_details,
        "custody_projection": custody_projection,
    }


def has_repairable_semantic_finding(
    findings: list[Any],
) -> dict[str, Any]:
    """Check whether a set of semantic findings contains repairable issues.

    This is the public entry point for dispatch consumers that need to
    decide whether to proceed with prompt/context generation when
    ``latest_failure`` is absent.

    Returns a dict with:

    * ``has_repairable`` — bool
    * ``count`` — number of repairable findings
    * ``finding_ids`` — list of repairable finding IDs
    * ``diagnostic_codes`` — list of diagnostic codes for repairable findings
    """
    classified = _classify_repairable_from_findings(findings)
    return {
        "has_repairable": classified["has_repairable"],
        "count": len(classified["details"]),
        "finding_ids": [d["finding_id"] for d in classified["details"]],
        "diagnostic_codes": [d["diagnostic_code"] for d in classified["details"]],
        "custody_projection": classified.get("custody_projection", {}),
    }


__all__ = [
    "ADDITIVE_FIELD_DEFAULTS",
    "ATTEMPT_STATE_CLAIMED",
    "ATTEMPT_STATE_RUNNING",
    "ATTEMPT_STATE_SUCCEEDED",
    "ATTEMPT_STATE_FAILED",
    "ATTEMPT_STATE_CANCELLED",
    "ALL_OUTCOMES",
    "BLOCKER_FINGERPRINT_V1_PREFIX",
    "BLOCKER_FINGERPRINT_V2_PREFIX",
    "BLOCKER_FINGERPRINT_VERSION",
    "BLOCKER_FINGERPRINT_V2_VERSION",
    "BLOCKER_ID_V1_PREFIX",
    "BLOCKER_ID_V2_PREFIX",
    "BlockerFingerprintV1",
    "BlockerFingerprintV2",
    "blocker_fingerprint_from_acceptance",
    "COMPLETE",
    "CUSTODY_BUCKET_BROKEN_SUPERFIXER",
    "CUSTODY_BUCKET_HUMAN_REQUIRED",
    "CUSTODY_BUCKET_PAUSED",
    "CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING",
    "CUSTODY_BUCKET_REPAIRING",
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_REPAIR_BUDGET_SECS",
    "DISPATCH_DECISION_BROKEN_SUPERFIXER",
    "DISPATCH_DECISION_HUMAN_REQUIRED",
    "DISPATCH_DECISION_L1",
    "DISPATCH_DECISION_NO_ACTION",
    "DISPATCH_DECISION_REPAIRING",
    "DISPATCH_DECISION_TERMINAL",
    "DISPATCH_INTENT_BROKEN_SUPERFIXER",
    "DISPATCH_INTENT_HUMAN_REQUIRED",
    "DISPATCH_INTENT_L1",
    "DISPATCH_INTENT_QUEUE_ONLY",
    "DISCORD_ESCALATED",
    "ENVIRONMENT_GONE",
    "LIVE_WITH_FRESH_ACTIVITY",
    "NEEDS_HUMAN",
    "NON_TERMINAL_OUTCOMES",
    "NON_SUCCESS_OUTCOMES",
    "PARTIAL_LIVENESS",
    "PROGRESSED",
    "REPAIR_EXHAUSTED",
    "REPAIR_TIMEOUT",
    "REPAIRING",
    "RETRY_PENDING",
    "RECOVERY_PROVISIONAL",
    "RECOVERY_UNKNOWN",
    "RECOVERY_UNKNOWN_TYPES",
    "RECOVERY_VERIFIED",
    "SUCCESS_OUTCOMES",
    "TRUE_HUMAN_BLOCKER",
    "append_attempt_record",
    "append_cleanup_record",
    "append_escalation_record",
    "append_incident_record",
    "append_jsonl_record",
    "append_repair_event",
    "atomic_write_json",
    "atomic_write_repair_index",
    "blocker_fingerprint_from_evidence",
    "blocker_id_for_fingerprint",
    "build_verification_record",
    "classify_repair_dispatch",
    "classify_recovery_verification",
    "durable_repair_active",
    "classify_verification_outcome",
    "cleanup_repair_data_retention",
    "compute_deadline",
    "ensure_additive_fields",
    "is_budget_exhausted",
    "is_success_outcome",
    "is_terminal_outcome",
    "load_json",
    "load_repair_index",
    "merge_additive_fields",
    "normalize_blocker_fingerprint_v1",
    "normalize_blocker_fingerprint_v2",
    "project_repair_custody",
    "RepairDispatchDecision",
    "RepairDispatchDecisionKind",
    "read_repair_index",
    "read_jsonl_records",
    "redact_repair_index",
    "redact_repair_data",
    "remaining_budget_secs",
    "save_repair_data",
    "update_incident_index",
    "update_repair_index",
    "update_session_index",
    "validate_jsonl_summary",
    "validate_repair_index",
    "validate_repair_data",
    # ── repair verdict evidence ────────────────────────────────────
    "RepairVerdict",
    "RepairVerdictKind",
    "REPAIR_VERDICT_CLEARED",
    "REPAIR_VERDICT_NO_FIX",
    "REPAIR_VERDICT_ESCALATED",
    "REPAIR_VERDICT_STALE",
    "REPAIR_VERDICT_NO_VERDICT",
    "REPAIR_VERDICT_KINDS",
    "build_ordinary_repair_verdict",
    "detect_stale_repair_data",
    "detect_no_verdict_artifact",
    "save_repair_verdict",
    "validate_repair_verdict_payload",
    "utc_now_iso",
    # ── cloud custody classification evidence ──────────────────────
    "CloudCustodyClassification",
    "CloudCustodyKind",
    "CUSTODY_MANAGED_RUNNING",
    "CUSTODY_COMPLETE",
    "CUSTODY_UNMANAGED_WARNING",
    "CUSTODY_BLOCKED_RELAUNCH",
    "CUSTODY_ESCALATED_UNCHANGED",
    "CLOUD_CUSTODY_KINDS",
    "build_cloud_custody_classification",
    "classify_cloud_custody",
    "save_cloud_custody_classification",
    "validate_cloud_custody_payload",
    # ── S4: semantic-health projection for repair initial facts ──────
    "build_repair_semantic_context",
    "has_repairable_semantic_finding",
]


# ──────────────────────────────────────────────────────────────────────
# T18 / Step 11 — re-export the canonical repair dispatch identity contract.
#
# Re-export is performed *lazily* via a module-level ``__getattr__``
# (PEP 562) rather than an eager ``from repair_requests import (...)``.
# An eager import — whether at module top *or* module end — creates a
# hard circular-import failure whenever ``repair_requests`` (or
# ``repair_revalidation``, which imports repair_requests) is imported
# *first*: repair_requests line 15 imports repair_contract, which then
# tries to re-import the still-partially-initialized repair_requests
# before repair_requests has finished binding its symbols
# (``ImportError: cannot import name 'REPAIR_ACTION_ADOPTION' from
# partially initialized module …``). That breaks ``python -c "import
# …repair_requests"`` and any test file that imports repair_requests
# first — i.e. it breaks standalone recovery/repair imports.
#
# Lazy resolution breaks the cycle unconditionally while preserving the
# public surface: ``from …repair_contract import RepairDispatchIdentity``
# and ``hasattr(repair_contract, "RepairDispatchIdentity")`` both still
# work, and ``dir(repair_contract)`` lists the re-exported names.
# repair_contract itself never references these symbols internally — the
# block is pure API convenience — so deferred resolution is safe.
# ──────────────────────────────────────────────────────────────────────
_REPAIR_DISPATCH_IDENTITY_REEXPORTS = frozenset(
    {
        "REPAIR_ACTION_ADOPTION",
        "REPAIR_ACTION_CANCELLATION",
        "REPAIR_ACTION_ESCALATION",
        "REPAIR_ACTION_KINDS",
        "REPAIR_ACTION_REPAIR",
        "REPAIR_ACTION_RETRY",
        "RepairDispatchIdentity",
        "SourceRereadVerdict",
        "derive_dispatch_identity_from_source_reread",
        "repair_dispatch_identity_key",
        "require_source_reread_for_action",
    }
)


def __getattr__(name):  # noqa: D401  (PEP 562 module-level lazy attribute)
    if name in _REPAIR_DISPATCH_IDENTITY_REEXPORTS:
        from arnold_pipelines.megaplan.cloud import repair_requests

        try:
            value = getattr(repair_requests, name)
        except AttributeError as exc:  # pragma: no cover - defensive
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from exc
        # Cache in module dict so subsequent accesses bypass __getattr__.
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    module_names = list(globals().keys())
    return sorted(set(module_names) | set(_REPAIR_DISPATCH_IDENTITY_REEXPORTS))
