"""Immutable failure-triggered repair request queue markers."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal, Mapping

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.cloud.repair_lock import (
    RepairLockResult,
    acquire_repair_lock,
    decision_admission_lock,
    decision_admission_lock_dir,
    inspect_repair_lock,
    occurrence_scoped_lock_dir,
    owner_metadata_path,
    process_owner_identity,
    release_repair_lock,
)
from arnold_pipelines.megaplan.cloud.repair_recurrence import (
    ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS,
    PROBLEM_SIGNATURE_FIELDS,
)
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
    RepairOccurrenceKey,
    F01_REPAIR_OCCURRENCE_FIELDS,
    build_custody_target_key,
    build_repair_occurrence_key,
    normalize_custody_target_key,
    normalize_repair_occurrence_key,
    process_birth_identity,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    open_lease_store,
    StaleSequenceError,
    LeaseIdempotencyConflict,
)
from arnold_pipelines.megaplan.run_state.model import NormalizedFailureToken
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.run_authority.contracts import ContractError

QUEUE_DIR_NAME = "repair-queue"
REQUESTS_DIR_NAME = "requests"
DECISIONS_DIR_NAME = "decisions"
ATTEMPTS_DIR_NAME = "attempts"
ACTIVE_CLAIMS_DIR_NAME = "active-claims"
OCCURRENCE_CLAIMS_DIR_NAME = "occurrence-claims"
CURRENT_SCHEMA_VERSION = 1
REPAIR_IDENTITY_SCHEMA_VERSION = "megaplan-repair-identity-v1"
# T-0101e': the scoped owner-boundary adoption identity subtype.  It is a
# SEPARATE envelope from v1: it carries the occurrence facts + full CAS
# vector + six runtime roots + the deterministic adoption authority block,
# and it must NEVER carry historical v1 fields (run_incarnation_id,
# coordinator_attempt_id, lease_id, custody_epoch).
OWNER_ADOPTION_IDENTITY_SCHEMA = "megaplan-repair-identity-owner-adoption-v1"
OWNER_ADOPTION_IDENTITY_KIND = "owner_boundary_adoption"
OWNER_ADOPTED_OCCURRENCE_CONTRACT = "owner_adopted_blocked_occurrence"
OWNER_ADOPTION_SOURCE = "owner_boundary_occurrence_adoption"
#: Restricted authority scope: the v2 adoption identity is claimable ONLY by
#: the exact-occurrence join; generic repair dispatch/effects must reject it.
OWNER_ADOPTION_SCOPE = frozenset({"enqueue_exact_occurrence", "occurrence_join"})
ADOPTION_RUN_PREFIX = "repair-adoption:"
ADOPTION_ATTEMPT_PREFIX = "owner-adoption-attempt:"
OWNER_ADOPTION_OCCURRENCE_FIELDS = (
    "contract_type",
    "schema_version",
    "chain_session",
    "plan_name",
    "phase",
    "failure_kind",
    "failure_code",
    "failure_recorded_at",
    "resume_phase",
    "retry_strategy",
    "subject_occurrence_digest",
)
OWNER_ADOPTION_CAS_FIELDS = (
    "chain_spec_sha256",
    "chain_state_sha256",
    "plan_state_sha256",
    "latest_failure_sha256",
    "resume_cursor_sha256",
    "pause_authority_sha256",
    "runtime_manifest_sha256",
    "marker_sha256",
    "runtime_provenance_receipt_sha256",
    "runtime_roots_sha256",
)
OWNER_ADOPTION_ROOT_FIELDS = (
    "chain_execution_root",
    "recorded_engine_root",
    "manifest_runtime_root",
    "marker_runtime_root",
    "independent_import_root",
    "candidate_root",
)
OWNER_ADOPTION_AUTHORITY_FIELDS = (
    "kind",
    "owner",
    "actor",
    "scope",
    "historical_authority_status",
    "adoption_record_id",
    "adoption_run_id",
    "adoption_run_revision",
    "adoption_run_incarnation_id",
    "adoption_attempt_id",
    "adoption_fence_token",
    "adoption_grant_id",
    "wbc_attempt_reference",
)
#: Historical v1 fields that are FORBIDDEN inside the adoption envelope —
#: their absence is part of the identity contract (no fabricated history).
OWNER_ADOPTION_FORBIDDEN_FIELDS = (
    "run_incarnation_id",
    "coordinator_attempt_id",
    "lease_id",
    "custody_epoch",
)


def build_normalized_repair_identity(
    *,
    target: CustodyTargetKey,
    run_id: str,
    run_revision: str,
    run_incarnation_id: str,
    coordinator_attempt_id: str,
    fence_token: int,
    wbc_attempt_reference: str,
    run_authority_grant_id: str,
    lease_id: str,
    custody_epoch: int,
) -> dict[str, Any] | None:
    """Build the canonical repair identity without provider/model trivia."""
    occurrence = build_repair_occurrence_key(
        target=target,
        run_id=run_id,
        run_revision=run_revision,
        coordinator_attempt_id=coordinator_attempt_id,
        fence_token=fence_token,
        wbc_attempt_reference=wbc_attempt_reference,
    )
    if occurrence is None:
        return None
    return normalize_repair_identity(
        {
            "schema_version": REPAIR_IDENTITY_SCHEMA_VERSION,
            "occurrence": occurrence.to_dict(),
            "run_incarnation_id": run_incarnation_id,
            "run_authority_grant_id": run_authority_grant_id,
            "lease_id": lease_id,
            "custody_epoch": custody_epoch,
        }
    )


def normalize_repair_identity(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the one authority-bearing repair identity envelope.

    The predecessor ten-field/F01 mapping remains readable elsewhere for
    diagnosis, but it is deliberately not normalized here: F01 alone does
    not identify the run incarnation, coordinator attempt, or current
    custody lease.  Positive enqueue/claim/mutation boundaries consume only
    this current envelope.
    """
    if not isinstance(payload, Mapping):
        return None

    occurrence_raw = payload.get("occurrence")
    occurrence: RepairOccurrenceKey | None = None
    if isinstance(occurrence_raw, Mapping):
        # Require the current nested occurrence contract.  The compatibility
        # constructor also understands predecessor shapes, so explicitly
        # reject those at this authority boundary.
        if (
            occurrence_raw.get("contract_type") == "repair_occurrence_key"
            and isinstance(occurrence_raw.get("target"), Mapping)
        ):
            occurrence = normalize_repair_occurrence_key(occurrence_raw)
    elif isinstance(payload.get("target"), Mapping):
        occurrence = normalize_repair_occurrence_key(payload)
    elif all(field in payload for field in F01_REPAIR_OCCURRENCE_FIELDS):
        target_payload = {
            field: payload.get(field) for field in F01_REPAIR_OCCURRENCE_FIELDS
        }
        target_payload["chain_identity"] = payload.get("chain_identity")
        target = normalize_custody_target_key(target_payload)
        try:
            fence_token = int(payload.get("fence_token"))
        except (TypeError, ValueError):
            fence_token = -1
        if target is not None and fence_token >= 0:
            occurrence = build_repair_occurrence_key(
                target=target,
                run_id=str(payload.get("run_id") or "").strip(),
                run_revision=str(payload.get("run_revision") or "").strip(),
                coordinator_attempt_id=str(
                    payload.get("coordinator_attempt_id") or ""
                ).strip(),
                fence_token=fence_token,
                wbc_attempt_reference=str(
                    payload.get("wbc_attempt_reference") or ""
                ).strip(),
            )
    if occurrence is None:
        return None

    required_text = {
        "run_incarnation_id": payload.get("run_incarnation_id"),
        "run_authority_grant_id": payload.get("run_authority_grant_id"),
        "lease_id": payload.get("lease_id"),
    }
    normalized_text = {
        name: str(value or "").strip() for name, value in required_text.items()
    }
    if not all(normalized_text.values()):
        return None
    custody_epoch = _positive_int(payload.get("custody_epoch"))
    if custody_epoch is None:
        return None
    return {
        "schema_version": REPAIR_IDENTITY_SCHEMA_VERSION,
        "occurrence": occurrence.to_dict(),
        **normalized_text,
        "custody_epoch": custody_epoch,
    }


def repair_identity_key(payload: Mapping[str, Any] | None) -> str:
    """Return the deterministic key for a normalized repair occurrence."""
    normalized = normalize_repair_identity(payload)
    if normalized is None:
        return ""
    return "sha256:" + hashlib.sha256(
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha256_digest_text(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(char in "0123456789abcdef" for char in value[7:])
    )


def _owner_adoption_scope_valid(scope: Any) -> bool:
    if not isinstance(scope, (list, tuple, set)):
        return False
    values = {str(item).strip() for item in scope if isinstance(item, str)}
    if not values:
        return False
    if "occurrence_join" not in values:
        return False
    return values.issubset(OWNER_ADOPTION_SCOPE)


def normalize_owner_adoption_identity(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the canonical owner-boundary adoption identity envelope.

    Strictly validates the v2 shape: the scoped schema/identity_kind, the
    owner-adopted occurrence contract with its subject digest, the complete
    ten-field CAS vector, the six runtime roots, and the deterministic
    adoption authority block (kind/owner/actor/scope/absent history + the
    adoption_record_id/run/revision/incarnation/attempt/fence/grant/WBC
    references).  Historical v1 fields (run_incarnation_id,
    coordinator_attempt_id, lease_id, custody_epoch) are FORBIDDEN — their
    absence is part of the identity contract.

    Returns ``None`` for anything that does not satisfy the exact shape, so
    generic v1 machinery (``normalize_repair_identity``, enqueue, claim,
    dispatch) can never mistake an adoption identity for ordinary v1
    authority.
    """
    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("schema_version") or "") != OWNER_ADOPTION_IDENTITY_SCHEMA:
        return None
    if str(payload.get("identity_kind") or "") != OWNER_ADOPTION_IDENTITY_KIND:
        return None
    for forbidden in OWNER_ADOPTION_FORBIDDEN_FIELDS:
        if payload.get(forbidden) is not None:
            return None

    occurrence = payload.get("occurrence")
    if not isinstance(occurrence, Mapping):
        return None
    if str(occurrence.get("contract_type") or "") != OWNER_ADOPTED_OCCURRENCE_CONTRACT:
        return None
    if any(
        not str(occurrence.get(field) or "").strip()
        for field in OWNER_ADOPTION_OCCURRENCE_FIELDS
    ):
        return None
    if not _sha256_digest_text(
        str(occurrence.get("subject_occurrence_digest") or "").strip()
    ):
        return None

    cas = payload.get("cas")
    if not isinstance(cas, Mapping):
        return None
    if any(
        not _sha256_digest_text(str(cas.get(field) or "").strip())
        for field in OWNER_ADOPTION_CAS_FIELDS
    ):
        return None

    runtime_roots = payload.get("runtime_roots")
    if not isinstance(runtime_roots, Mapping):
        return None
    if any(
        not str(runtime_roots.get(field) or "").strip()
        for field in OWNER_ADOPTION_ROOT_FIELDS
    ):
        return None

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        return None
    if any(field not in authority for field in OWNER_ADOPTION_AUTHORITY_FIELDS):
        return None
    if str(authority.get("kind") or "") != "operator_owner_boundary_adoption":
        return None
    if str(authority.get("owner") or "") != "megaplan.chain":
        return None
    if not str(authority.get("actor") or "").strip():
        return None
    if str(authority.get("historical_authority_status") or "") != "absent":
        return None
    if not _owner_adoption_scope_valid(authority.get("scope")):
        return None
    if not _sha256_digest_text(
        str(authority.get("adoption_record_id") or "").strip()
    ):
        return None
    if not str(authority.get("adoption_run_id") or "").startswith(
        ADOPTION_RUN_PREFIX
    ):
        return None
    for field in (
        "adoption_run_revision",
        "adoption_run_incarnation_id",
        "adoption_grant_id",
    ):
        if not _sha256_digest_text(str(authority.get(field) or "").strip()):
            return None
    if not str(authority.get("adoption_attempt_id") or "").startswith(
        ADOPTION_ATTEMPT_PREFIX
    ):
        return None
    if (
        str(authority.get("wbc_attempt_reference") or "").strip()
        != str(authority.get("adoption_attempt_id") or "").strip()
    ):
        return None
    try:
        fence_token = int(authority.get("adoption_fence_token"))
    except (TypeError, ValueError):
        return None
    if fence_token != 1:
        return None

    # Canonical rebuild: identical shapes normalize to identical dicts.
    return {
        "schema_version": OWNER_ADOPTION_IDENTITY_SCHEMA,
        "identity_kind": OWNER_ADOPTION_IDENTITY_KIND,
        "occurrence": {
            field: occurrence.get(field) for field in OWNER_ADOPTION_OCCURRENCE_FIELDS
        },
        "cas": {field: str(cas.get(field)) for field in OWNER_ADOPTION_CAS_FIELDS},
        "runtime_roots": {
            field: str(runtime_roots.get(field))
            for field in OWNER_ADOPTION_ROOT_FIELDS
        },
        "authority": {
            "kind": str(authority.get("kind")),
            "owner": str(authority.get("owner")),
            "actor": str(authority.get("actor")),
            "scope": sorted(
                str(item) for item in authority.get("scope", []) if isinstance(item, str)
            ),
            "historical_authority_status": str(
                authority.get("historical_authority_status")
            ),
            "adoption_record_id": str(authority.get("adoption_record_id")),
            "adoption_run_id": str(authority.get("adoption_run_id")),
            "adoption_run_revision": str(authority.get("adoption_run_revision")),
            "adoption_run_incarnation_id": str(
                authority.get("adoption_run_incarnation_id")
            ),
            "adoption_attempt_id": str(authority.get("adoption_attempt_id")),
            "adoption_fence_token": fence_token,
            "adoption_grant_id": str(authority.get("adoption_grant_id")),
            "wbc_attempt_reference": str(authority.get("wbc_attempt_reference")),
        },
    }


def owner_adoption_identity_key(payload: Mapping[str, Any] | None) -> str:
    """Return the deterministic key for a normalized adoption identity."""
    normalized = normalize_owner_adoption_identity(payload)
    if normalized is None:
        return ""
    return "sha256:" + _sha256_json(normalized)


def _identity_for_request_key(
    repair_identity: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    """Return whichever normalized identity binds a request id (v1 or v2)."""
    normalized = normalize_repair_identity(repair_identity)
    if normalized is not None:
        return normalized
    return normalize_owner_adoption_identity(repair_identity)


def plan_state_has_repair_identity(plan_state: Mapping[str, Any] | None) -> bool:
    """Return True when an authoritative plan-side identity location is filled.

    Mirrors ``derive_repair_identity``'s candidate locations (plan state,
    plan meta, current target, current refs) plus the recorded
    ``repair_identity_key`` spellings.  Used by the owner-adoption join to
    prove the adopted occurrence is STILL identity-less.
    """
    if not isinstance(plan_state, Mapping):
        return False
    meta = _mapping(plan_state.get("meta"))
    current_target = _mapping(plan_state.get("current_target"))
    current_refs = _mapping(current_target.get("current_refs"))
    candidates = (
        plan_state.get("repair_identity"),
        plan_state.get("repair_identity_key"),
        meta.get("repair_identity"),
        meta.get("repair_identity_key"),
        current_target.get("repair_identity"),
        current_refs.get("repair_identity"),
    )
    for value in candidates:
        if str(value or "").strip():
            return True
    return derive_repair_identity(plan_state=plan_state) is not None


def owner_adopted_repair_request_contract_violations(
    request: Mapping[str, Any],
) -> list[str]:
    """Return typed reasons an immutable adoption request is unsafe to claim.

    The v2 request carries the owner-boundary adoption identity; only the
    exact-occurrence join (``chain occurrence-join``) may consume it.  The
    generic claimable contract deliberately does NOT accept it, so generic
    repair dispatch/effects keep rejecting it.
    """
    violations: list[str] = []
    identity = normalize_owner_adoption_identity(request.get("repair_identity"))
    if identity is None:
        violations.append("invalid_owner_adoption_identity")
    else:
        if str(request.get("repair_identity_key") or "") != owner_adoption_identity_key(
            identity
        ):
            violations.append("invalid_owner_adoption_identity_key")
        authority = identity.get("authority") or {}
        adoption_record_id = str(authority.get("adoption_record_id") or "").strip()
        target = request.get("target")
        if not isinstance(target, Mapping) or str(
            target.get("adoption_record_id") or ""
        ).strip() != adoption_record_id:
            violations.append("missing_adoption_record_id")
    source = str(request.get("source") or "").strip()
    session = str(request.get("session") or "").strip()
    provenance = request.get("provenance")
    if (
        not source
        or not session
        or source != OWNER_ADOPTION_SOURCE
        or not isinstance(provenance, Mapping)
        or str(provenance.get("producer") or "").strip() != source
        or str(provenance.get("session") or "").strip() != session
    ):
        violations.append("invalid_provenance")
    return violations


def has_owner_adopted_repair_request_contract(request: Mapping[str, Any]) -> bool:
    """Return whether an immutable adoption request is safe to join."""
    return not owner_adopted_repair_request_contract_violations(request)


def _find_accepted_decision(
    queue_dir: str | Path, request_id: str
) -> dict[str, Any] | None:
    """Return the recorded 'accepted' decision for *request_id*, if any."""
    for candidate in iter_repair_decisions(queue_dir):
        if (
            str(candidate.get("request_id") or "").strip() == str(request_id or "").strip()
            and str(candidate.get("decision") or "").strip() == "accepted"
        ):
            return dict(candidate)
    return None


@contextmanager
def _owner_adoption_enqueue_lock(
    queue_root: str | Path, request_id: str
) -> Iterator[None]:
    """Serialize owner-adoption read→verify→write→accept for ONE request.

    A SEPARATE request-scoped flock from
    :func:`repair_lock.decision_admission_lock`: the adoption wrapper holds
    it across its whole cycle (including the request marker write and the
    ``write_decision`` accept, which takes the decision/admission flock
    itself).  The lock ORDER is always owner-adoption lock OUTER, decision/
    admission lock INNER, so the join (which takes only the decision/
    admission lock) can never deadlock against an adopter.  The sidecar is
    intentionally never removed (unlinking it while another waiter blocks on
    the same inode would split the fence).
    """
    request_id = str(request_id or "").strip()
    if not request_id:
        raise ValueError("request_id is required")
    lock_dir = decision_admission_lock_dir(queue_root)
    lock_dir.mkdir(parents=True, exist_ok=True)
    token = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    lock_path = lock_dir / f"{token}.owner-adoption.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def build_owned_lifecycle_repair_identity(
    *,
    environment: str,
    session: str,
    chain: str,
    plan_revision: str,
    phase: str,
    task: str,
    attempt: str,
    normalized_failure_kind: str,
    blocker_or_phase_result_hash: str,
    active_step: Mapping[str, Any] | None,
    live_runner_lease: Mapping[str, Any] | None,
    coordinator_attempt_id: str,
) -> dict[str, Any] | None:
    """Mint repair authority only at the live lifecycle-failure owner boundary.

    This is the ordinary positive producer.  It consumes the persisted active
    step plus a fresh reread of the exact runner lease.  Labels, mtimes, PIDs,
    or a stale active-step projection cannot independently create authority.
    The resulting grant and repair-custody lease identifiers are
    content-addressed records of that already-authoritative boundary.
    """
    active = _mapping(active_step)
    recorded_lease = _mapping(active.get("runner_lease"))
    live_lease = _mapping(live_runner_lease)
    incarnation = _mapping(active.get("runner_incarnation"))
    orphan_fence = _mapping(active.get("orphan_fence"))
    required_incarnation = (
        incarnation.get("host_id"),
        incarnation.get("pid_namespace_id"),
        incarnation.get("worker_pid"),
        incarnation.get("worker_process_start_identity"),
    )
    run_id = str(active.get("run_id") or "").strip()
    coordinator_attempt = str(coordinator_attempt_id or "").strip()
    if (
        not run_id
        or not coordinator_attempt
        or not all(str(value or "").strip() for value in required_incarnation)
        or str(orphan_fence.get("run_id") or "").strip() != run_id
        or str(orphan_fence.get("invocation_id") or "").strip()
        != coordinator_attempt
    ):
        return None

    lease_fields = ("lease_id", "runner_fence", "marker_binding")
    if not all(str(live_lease.get(field) or "").strip() for field in lease_fields):
        return None
    if any(
        str(recorded_lease.get(field) or "").strip()
        != str(live_lease.get(field) or "").strip()
        for field in lease_fields
    ):
        return None
    try:
        fence_token = int(live_lease.get("runner_fence"))
    except (TypeError, ValueError):
        return None
    if fence_token < 0:
        return None

    target = build_custody_target_key(
        environment=environment,
        session=session,
        chain=chain,
        plan_revision=plan_revision,
        phase=phase,
        task=task,
        attempt=attempt,
        normalized_failure_kind=normalized_failure_kind,
        blocker_or_phase_result_hash=blocker_or_phase_result_hash,
        fence=f"runner-fence:{fence_token}",
        chain_identity=str(live_lease.get("marker_binding") or ""),
    )
    if target is None:
        return None

    incarnation_id = "sha256:" + hashlib.sha256(
        json.dumps(
            dict(incarnation), sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    ).hexdigest()
    authority_basis = {
        "target": target.to_dict(),
        "run_id": run_id,
        "run_revision": str(plan_revision or "").strip(),
        "run_incarnation_id": incarnation_id,
        "coordinator_attempt_id": coordinator_attempt,
        "fence_token": fence_token,
        "wbc_attempt_reference": coordinator_attempt,
        "runner_lease_id": str(live_lease.get("lease_id") or ""),
        "runner_marker_binding": str(live_lease.get("marker_binding") or ""),
    }
    authority_digest = hashlib.sha256(
        json.dumps(
            authority_basis, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    ).hexdigest()
    return build_normalized_repair_identity(
        target=target,
        run_id=run_id,
        run_revision=str(plan_revision or "").strip(),
        run_incarnation_id=incarnation_id,
        coordinator_attempt_id=coordinator_attempt,
        fence_token=fence_token,
        wbc_attempt_reference=coordinator_attempt,
        run_authority_grant_id=f"repair-grant:{authority_digest}",
        lease_id=f"repair-custody:{authority_digest}",
        custody_epoch=1,
    )


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def derive_repair_identity(
    *,
    session: str = "",
    problem_signature: Mapping[str, Any] | None = None,
    target: Mapping[str, Any] | None = None,
    plan_state: Mapping[str, Any] | None = None,
    current_target: Mapping[str, Any] | None = None,
    blocker_id: str = "",
    blocker_fingerprint: Mapping[str, Any] | None = None,
    repair_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return only explicitly persisted current repair authority.

    Labels, liveness, failure summaries, and rebuildable projections remain
    useful diagnostic evidence, but they may not mint a run incarnation,
    coordinator attempt, fence, or custody epoch.  Producers must persist the
    normalized envelope at the source or explicitly reacquire it.
    """
    del session, problem_signature, blocker_id, blocker_fingerprint
    candidates = (
        repair_identity,
        _mapping(target).get("repair_identity"),
        _mapping(plan_state).get("repair_identity"),
        _mapping(_mapping(plan_state).get("meta")).get("repair_identity"),
        _mapping(current_target).get("repair_identity"),
        _mapping(_mapping(current_target).get("current_refs")).get(
            "repair_identity"
        ),
    )
    for candidate in candidates:
        normalized = normalize_repair_identity(_mapping(candidate))
        if normalized is not None:
            return normalized
    return None


def exact_repair_identity_available(
    *,
    target: Mapping[str, Any] | None = None,
    plan_state: Mapping[str, Any] | None = None,
    current_target: Mapping[str, Any] | None = None,
) -> bool:
    """Whether explicit current evidence carries the complete identity."""
    return derive_repair_identity(
        target=target,
        plan_state=plan_state,
        current_target=current_target,
    ) is not None

REPAIR_ACTION_REPAIR = "repair"
REPAIR_ACTION_RETRY = "retry"
REPAIR_ACTION_ESCALATION = "escalation"
REPAIR_ACTION_CANCELLATION = "cancellation"
REPAIR_ACTION_ADOPTION = "adoption"
REPAIR_ACTION_KINDS: frozenset[str] = frozenset(
    {
        REPAIR_ACTION_REPAIR,
        REPAIR_ACTION_RETRY,
        REPAIR_ACTION_ESCALATION,
        REPAIR_ACTION_CANCELLATION,
        REPAIR_ACTION_ADOPTION,
    }
)


@dataclass(frozen=True)
class RepairDispatchIdentity:
    """Exact, read-only occurrence tuple used to revalidate repair dispatch."""

    environment_id: str
    session_id: str
    chain_id: str
    plan_revision: str
    phase: str
    task_id: str
    attempt_number: int
    normalized_failure_kind: str
    dispatch_digest_kind: str
    dispatch_digest: str
    coordinator_fence_token: str
    source_reread_at: str = ""
    source_digest: str = ""
    raw_failure_kind: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "session_id": self.session_id,
            "chain_id": self.chain_id,
            "plan_revision": self.plan_revision,
            "phase": self.phase,
            "task_id": self.task_id,
            "attempt_number": self.attempt_number,
            "normalized_failure_kind": self.normalized_failure_kind,
            "dispatch_digest_kind": self.dispatch_digest_kind,
            "dispatch_digest": self.dispatch_digest,
            "coordinator_fence_token": self.coordinator_fence_token,
            "source_reread_at": self.source_reread_at,
            "source_digest": self.source_digest,
            "raw_failure_kind": self.raw_failure_kind,
            "authority": "evidence_extracted_non_authoritative",
        }


@dataclass(frozen=True)
class SourceRereadVerdict:
    action: str
    permitted: bool
    reason: str
    current_fence_token: str = ""
    fresh_fence_token: str = ""
    current_tuple_digest: str = ""
    fresh_tuple_digest: str = ""


def derive_dispatch_identity_from_source_reread(
    *,
    environment_id: str,
    session_id: str,
    chain_id: str,
    plan_revision: str,
    phase: str,
    task_id: str,
    attempt_number: int,
    raw_failure_kind: str,
    blocker_digest: str = "",
    phase_result_digest: str = "",
    coordinator_fence_token: str,
    source_reread_at: str,
    source_digest: str,
) -> RepairDispatchIdentity | None:
    required = (
        environment_id,
        session_id,
        chain_id,
        plan_revision,
        phase,
        coordinator_fence_token,
        source_reread_at,
        source_digest,
    )
    if not all(required):
        return None
    try:
        attempt = int(attempt_number)
    except (TypeError, ValueError):
        return None
    if attempt <= 0:
        return None
    digest_kind = "phase_result" if phase_result_digest else "blocker"
    dispatch_digest = phase_result_digest or blocker_digest
    if not dispatch_digest:
        return None
    token = NormalizedFailureToken.normalize(raw_failure_kind or "")
    return RepairDispatchIdentity(
        environment_id=environment_id,
        session_id=session_id,
        chain_id=chain_id,
        plan_revision=plan_revision,
        phase=phase,
        task_id=task_id or "",
        attempt_number=attempt,
        normalized_failure_kind=token.canonical,
        dispatch_digest_kind=digest_kind,
        dispatch_digest=dispatch_digest,
        coordinator_fence_token=coordinator_fence_token,
        source_reread_at=source_reread_at,
        source_digest=source_digest,
        raw_failure_kind=token.raw,
    )


def repair_dispatch_identity_key(identity: RepairDispatchIdentity | None) -> str:
    if identity is None:
        return ""
    payload = {
        "environment_id": identity.environment_id,
        "session_id": identity.session_id,
        "chain_id": identity.chain_id,
        "plan_revision": identity.plan_revision,
        "phase": identity.phase,
        "task_id": identity.task_id,
        "attempt_number": identity.attempt_number,
        "normalized_failure_kind": identity.normalized_failure_kind,
        "dispatch_digest_kind": identity.dispatch_digest_kind,
        "dispatch_digest": identity.dispatch_digest,
        "coordinator_fence_token": identity.coordinator_fence_token,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def require_source_reread_for_action(
    action: str,
    *,
    current_identity: RepairDispatchIdentity | None,
    fresh_identity: RepairDispatchIdentity | None,
) -> SourceRereadVerdict:
    if action not in REPAIR_ACTION_KINDS:
        return SourceRereadVerdict(
            action, False, f"unknown repair action kind: {action!r}"
        )
    if fresh_identity is None:
        return SourceRereadVerdict(
            action, False, "no fresh source reread supplied for dispatch action"
        )
    if current_identity is None:
        return SourceRereadVerdict(
            action, False, "no current occurrence tuple to bind dispatch action against"
        )
    current_key = repair_dispatch_identity_key(current_identity)
    fresh_key = repair_dispatch_identity_key(fresh_identity)
    evidence = {
        "current_fence_token": current_identity.coordinator_fence_token,
        "fresh_fence_token": fresh_identity.coordinator_fence_token,
        "current_tuple_digest": current_key,
        "fresh_tuple_digest": fresh_key,
    }
    if current_key != fresh_key:
        return SourceRereadVerdict(
            action,
            False,
            "fresh source reread occurrence tuple disagrees with current tuple",
            **evidence,
        )
    if fresh_identity.source_reread_at < current_identity.source_reread_at:
        return SourceRereadVerdict(
            action, False, "fresh source reread predates the current reread (stale)", **evidence
        )
    return SourceRereadVerdict(
        action, True, "fresh source reread occurrence tuple matches current tuple", **evidence
    )

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


def occurrence_claims_dir(queue_dir: str | Path) -> Path:
    """Return the exact-occurrence claims directory beneath the queue root."""

    return validate_queue_root(queue_dir) / OCCURRENCE_CLAIMS_DIR_NAME


def singleton_occurrence_claim_lock_dir(
    queue_dir: str | Path,
    occurrence_fingerprint: str,
) -> Path:
    """Return the singleton exact-occurrence claim lock directory.

    Built on the same queue-root validation and ``mkdir`` lock primitive as
    the plural repair queue claim API (:func:`active_repair_claim_lock_dir`),
    but keyed by the deterministic occurrence fingerprint so that only one
    exact occurrence is active at a time.  The fingerprint MUST come from the
    canonical occurrence tuple (the F01 repair-occurrence fields) — never
    from a label, liveness signal, WBC receipt, or rebuildable projection.
    """

    normalized = _normalize_claim_identity(occurrence_fingerprint, "occurrence_fingerprint")
    return occurrence_scoped_lock_dir(occurrence_claims_dir(queue_dir), normalized)


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
    repair_identity: Mapping[str, Any] | None = None,
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
            "repair_identity": _identity_for_request_key(repair_identity),
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
    normalized_identity = normalize_repair_identity(
        _mapping(request.get("repair_identity"))
    )
    if normalized_identity is None:
        violations.append("invalid_repair_identity")
    elif request.get("repair_identity_key") != repair_identity_key(
        normalized_identity
    ):
        violations.append("invalid_repair_identity_key")
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
    repair_identity: Mapping[str, Any] | None = None,
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
    if normalize_owner_adoption_identity(repair_identity) is not None:
        # T-0101e' scope restriction: the v2 adoption identity is claimable
        # ONLY by the exact-occurrence join.  Generic enqueue can neither
        # coalesce nor dispatch it.
        return {
            "status": "zero_authority_rejected",
            "outcome": "zero_authority_rejected",
            "evidence": {
                "reason": (
                    "owner_boundary_adoption identities have restricted scope "
                    "(enqueue_exact_occurrence, occurrence_join); generic "
                    "enqueue cannot claim or dispatch them — use "
                    "enqueue_owner_adopted_repair_request"
                ),
                "source": source_identity,
                "identity_kind": OWNER_ADOPTION_IDENTITY_KIND,
            },
        }
    normalized_identity = normalize_repair_identity(repair_identity)
    if normalized_identity is None:
        return {
            "status": "zero_authority_rejected",
            "outcome": "zero_authority_rejected",
            "evidence": {
                "reason": (
                    "enqueue requires the current normalized repair identity "
                    "(exact occurrence, run incarnation, grant, lease, and "
                    "custody epoch)"
                ),
                "source": source_identity,
                "legacy_identity_read_only": bool(repair_identity),
            },
        }

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
        repair_identity=normalized_identity,
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
    if not predecessor_request_id:
        # Preserve migration lineage without treating an identity-free record
        # as authority.  Old requests used an identity-independent request ID,
        # so a current exact-identity successor will not naturally collide at
        # ``request_path``.  A deterministic diagnostic scan is safe here: it
        # only records the predecessor and never makes the legacy record
        # claimable or eligible for coalescing.
        for candidate in reversed(iter_repair_requests(queue_root)):
            if has_claimable_repair_request_contract(candidate):
                continue
            if str(candidate.get("session") or "").strip() != str(session or "").strip():
                continue
            if candidate.get("problem_signature_key") != signature_key:
                continue
            predecessor_request_id = str(candidate.get("request_id") or "").strip()
            if predecessor_request_id:
                break
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

    record["repair_identity"] = normalized_identity
    record["repair_identity_key"] = repair_identity_key(normalized_identity)

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
        repair_identity=normalized_identity,
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
        occurrence = _mapping(normalized_identity.get("occurrence"))
        custody_target = normalize_custody_target_key(
            _mapping(occurrence.get("target"))
        )
        identity = process_birth_identity()
        lease_result = _shadow_acquire_custody_lease(
            lease_store=lease_store,
            lease_id=f"repair-req-{request_id}",
            target=custody_target,
            owner_host=str(identity.get("host") or _hostname()),
            owner_pid=str(identity.get("pid") or os.getpid()),
            owner_boot_id=str(identity.get("boot_id") or ""),
            run_id=str(occurrence.get("run_id") or ""),
            run_revision=str(occurrence.get("run_revision") or ""),
            coordinator_attempt_id=str(
                occurrence.get("coordinator_attempt_id") or ""
            ),
            run_authority_grant_id=str(
                normalized_identity.get("run_authority_grant_id") or ""
            ),
            coordinator_fence_token=int(occurrence.get("fence_token") or 0),
            wbc_attempt_reference=str(
                occurrence.get("wbc_attempt_reference") or ""
            ),
            custody_epoch=int(normalized_identity.get("custody_epoch") or 0),
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
    # ── Current normalized identity for human-gate enqueue ──
    occurrence_identity: Mapping[str, Any] | None = None,
    evidence_cursor_digest: str = "",
    terminal_receipt_expectations: list[str] | None = None,
) -> dict[str, Any] | None:
    """Megaplan-owned hook used by the neutral human-gate step.

    Converts human-gate enqueue to occurrence-compatible requests or typed
    zero-authority rejection.  F01 alone is diagnostic: positive enqueue
    requires the same normalized run/custody identity as every other source.
    """

    from arnold_pipelines.megaplan.cloud.feature_flags import repair_request_queue_enabled
    from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
        emit_zero_authority_rejection,
    )
    if not repair_request_queue_enabled():
        return None

    # ── Build custody evidence payload for rejection outcomes ──────────
    custody_evidence: dict[str, Any] = {
        "plan_name": plan_name,
        "pipeline_name": pipeline_name,
        "artifact_stage": artifact_stage,
        "step_name": step_name,
        "session": str(session or "").strip(),
        "workspace": str(workspace),
        "marker_dir": str(marker_dir),
        "run_kind": str(run_kind or "").strip(),
    }

    # ── Validate and normalize occurrence identity ─────────────────────
    if occurrence_identity:
        normalized_identity = normalize_repair_identity(occurrence_identity)
        if normalized_identity is not None:
            return enqueue_occurrence_bound_repair_request(
                queue_root=queue_root,
                session=session,
                problem_signature={
                    "failure_kind": "human_gate",
                    "current_state": pipeline_name,
                    "phase_or_step": artifact_stage,
                    "milestone_or_plan": step_name,
                    "gate_recommendation": "",
                    "blocked_task_id": "",
                },
                root_cause_hint=prompt,
                source="human_gate",
                marker_dir=marker_dir,
                target={
                    "plan_dir": str(marker_dir),
                    "plan_name": plan_name,
                    "pipeline_name": pipeline_name,
                    "workspace_path": str(workspace),
                },
                workspace=workspace,
                run_kind=run_kind,
                occurrence_identity=normalized_identity,
                evidence_cursor_digest=evidence_cursor_digest,
                terminal_receipt_expectations=terminal_receipt_expectations,
            )

        rejection = emit_zero_authority_rejection(
            "enqueue_producer",
            "human_gate",
            reason=(
                "human-gate enqueue requires the complete normalized "
                "run/custody identity; F01-only evidence is read-only"
            ),
        )
        return {
            "status": "zero_authority_rejected",
            "outcome": "zero_authority_rejected",
            "evidence": {
                **custody_evidence,
                **(rejection.evidence or {}),
            },
        }

    # A human-gate label, suspension, or liveness observation is not repair
    # authority.  Producers that cannot supply the normalized run/custody identity
    # must fail closed instead of creating even a coalescible legacy request.
    rejection = emit_zero_authority_rejection(
        "enqueue_producer",
        "human_gate",
        reason=(
            "manual/liveness context cannot become repair authority without "
            "the complete normalized run/custody identity"
        ),
    )
    return {
        "status": "zero_authority_rejected",
        "outcome": "zero_authority_rejected",
        "evidence": {
            **custody_evidence,
            **(rejection.evidence or {}),
        },
    }


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
    repair_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    key = problem_signature_key(problem_signature, extra_fields=extra_fields)
    identity_key = repair_identity_key(repair_identity)
    if not identity_key:
        return None
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
            if str(record.get("repair_identity_key") or "") != identity_key:
                continue
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
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write an immutable decision record separate from request markers.

    T-0101h blocker 1: the write is serialized per request with the shared
    decision/admission flock (:func:`repair_lock.decision_admission_lock`),
    the SAME lock occurrence-join holds from its authoritative latest-decision
    check through the atomic WBC commit, so a claim admission can never
    interleave between its check and the admission — a decision appended here
    is always observed before the next admission, never between an
    admission's check and its commit.
    """

    with decision_admission_lock(queue_dir, str(request_id or "").strip()):
        if decision == "accepted":
            request_path = requests_dir(queue_dir) / f"{str(request_id or '').strip()}.json"
            try:
                request = json.loads(request_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "accepted repair request requires persisted canonical blocker identity, provenance, and evidence"
                ) from exc
            # T-0101e': the accepted decision for an owner-boundary adoption
            # request is written through the SAME shared decision/admission
            # flock the join holds, so admission-vs-decision serialization is
            # unchanged.  The v2 adoption request contract is accepted here
            # ONLY by the narrow adoption wrapper (the request carries the
            # restricted-scope adoption identity).
            if not isinstance(request, Mapping) or not (
                has_claimable_repair_request_contract(request)
                or has_owner_adopted_repair_request_contract(request)
            ):
                raise ValueError(
                    "accepted repair request requires persisted canonical blocker identity, provenance, and evidence"
                )

        when = created_at or utc_now()
        decision_identity: dict[str, Any] = {
            "request_id": request_id,
            "decision": decision,
            "reason": reason,
            "related_request_id": related_request_id,
            "created_at": when,
        }
        if evidence is not None:
            decision_identity["evidence"] = dict(evidence)
        record = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "kind": "repair_request_decision",
            "decision_id": _sha256_json(decision_identity),
            "request_id": str(request_id or "").strip(),
            "decision": decision,
            "reason": str(reason or "").strip(),
            "related_request_id": str(related_request_id or "").strip(),
            "created_at": when,
        }
        if evidence is not None:
            record["evidence"] = dict(evidence)
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
    repair_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write immutable proof that a claimed request launched a managed child."""

    if normalize_owner_adoption_identity(repair_identity) is not None:
        # T-0101e' scope restriction: adoption identities cannot authorize
        # generic managed dispatch.
        raise ValueError(
            "owner_boundary_adoption identities have restricted scope "
            "(enqueue_exact_occurrence, occurrence_join); generic dispatch "
            "attempts are refused"
        )
    normalized_identity = normalize_repair_identity(repair_identity)
    if normalized_identity is None:
        raise ValueError("dispatch attempt requires current normalized repair identity")
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
        "repair_identity": normalized_identity,
        "repair_identity_key": repair_identity_key(normalized_identity),
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
    repair_identity: Mapping[str, Any] | None = None,
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
    if normalize_owner_adoption_identity(repair_identity) is not None:
        # T-0101e' scope restriction: the v2 adoption identity is claimable
        # ONLY by the exact-occurrence join; generic active-claim dispatch
        # must reject it (zero mutation — no lock acquired, no owner written).
        return ActiveRepairClaimResult(
            status="stale",
            lock_dir=active_repair_claim_lock_dir(
                queue_dir, normalized_blocker_id
            ),
            evidence={
                "reason": (
                    "owner_boundary_adoption identities have restricted scope "
                    "(enqueue_exact_occurrence, occurrence_join); generic "
                    "active-claim dispatch cannot claim them"
                ),
                "identity_kind": OWNER_ADOPTION_IDENTITY_KIND,
                "request_id": normalized_request_id,
            },
        )
    normalized_repair_identity = normalize_repair_identity(repair_identity)
    normalized_repair_identity_key = repair_identity_key(
        normalized_repair_identity
    )
    claim_lock_dir = active_repair_claim_lock_dir(queue_dir, normalized_blocker_id)
    request_path = requests_dir(queue_dir) / f"{normalized_request_id}.json"
    try:
        request_record = json.loads(request_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        request_record = None
    observed_identity_key = (
        str(request_record.get("repair_identity_key") or "")
        if isinstance(request_record, Mapping)
        else ""
    )
    if (
        normalized_repair_identity is None
        or not isinstance(request_record, Mapping)
        or not has_claimable_repair_request_contract(request_record)
        or observed_identity_key != normalized_repair_identity_key
    ):
        return ActiveRepairClaimResult(
            status="stale",
            lock_dir=claim_lock_dir,
            evidence={
                "reason": "repair_identity_unclaimable",
                "request_id": normalized_request_id,
                "expected_repair_identity_key": observed_identity_key,
                "observed_repair_identity_key": normalized_repair_identity_key,
                "migration": (
                    "legacy or partial records are read-only; explicitly "
                    "reacquire and enqueue a current normalized identity"
                ),
            },
        )
    metadata = {
        "kind": "active_repair_request_claim",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "actor": normalized_actor,
        "session": normalized_session,
        "request_id": normalized_request_id,
        "blocker_id": normalized_blocker_id,
        "blocker_fingerprint": dict(blocker_fingerprint or {}),
        "repair_identity": normalized_repair_identity or {},
        "repair_identity_key": normalized_repair_identity_key,
    }
    if extra:
        metadata.update(dict(extra))

    result = acquire_repair_lock(
        claim_lock_dir,
        session=normalized_session,
        target_id=normalized_blocker_id,
        repair_identity=normalized_repair_identity,
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
    repair_identity: Mapping[str, Any] | None = None,
    expected_repair_identity_key: str = "",
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
    if normalize_owner_adoption_identity(repair_identity) is not None:
        # T-0101e' scope restriction: adoption identities cannot authorize
        # generic managed-run binding.
        return False
    normalized_repair_identity_key = (
        str(expected_repair_identity_key or "").strip()
        or repair_identity_key(repair_identity)
    )
    if (
        normalize_repair_identity(repair_identity) is None
        or not normalized_repair_identity_key
    ):
        return False
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
        if (
            normalized_repair_identity_key
            and str(owner.get("repair_identity_key") or "")
            != normalized_repair_identity_key
        ):
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
                **process_owner_identity(int(new_owner_pid)),
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
    transient_owner_reasons = {
        ("owner_metadata_missing",),
        ("owner_metadata_invalid",),
    }
    if result.status not in {"stale", "unknown"} or tuple(reasons or ()) not in transient_owner_reasons:
        return result
    # The mkdir winner can be descheduled before its atomic owner write while
    # many same-process contenders are inspecting the new directory.  Allow a
    # full second for that bounded write race before classifying it as stale.
    for _ in range(100):
        time.sleep(0.01)
        inspected = inspect_repair_lock(result.lock_dir, now=now, is_pid_live=is_pid_live)
        inspected_reasons = (inspected.stale_evidence or {}).get("reasons")
        if (
            inspected.status not in {"stale", "unknown"}
            or tuple(inspected_reasons or ()) not in transient_owner_reasons
        ):
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
    reasons = set((result.stale_evidence or {}).get("reasons") or ())
    if not reasons.intersection({"owner_pid_not_live", "owner_process_mismatch"}):
        # Timeout/identity/projection drift is not proof that the current owner
        # is gone.  Only namespace-bound process-incarnation evidence may enter
        # the stale-claim release path.
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
    custody_epoch: int = 0,
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

    # ── Step 13A: remove synthetic WBC / grant / fence / occurrence defaults ──
    # A shadow lease must bind *exact* repair identity (occurrence, host/process
    # birth, grant/fence, WBC attempt, lease, epoch).  Previously this function
    # fabricated ``repair-run-*``, ``m7-shadow``, ``coord-*``, ``wbc-ref-*`` and
    # ``grant-*`` placeholders when the caller omitted them, which let a
    # pre-dispatch enqueue mint a lease whose occurrence/WBC/grant identity did
    # not correspond to any real dispatched run.  Those synthetic defaults are
    # removed; when the required identity is absent the request is recorded as
    # ``pending`` (queued, not yet bound to a dispatched managed run) rather
    # than authorizing a fabricated lease.
    required_identity = (
        run_id,
        run_revision,
        coordinator_attempt_id,
        wbc_attempt_reference,
        run_authority_grant_id,
        custody_epoch,
    )
    if not all(str(value).strip() for value in required_identity):
        result["m7_lease_status"] = "pending"
        result["m7_lease_detail"] = (
            "repair identity incomplete (run_id/run_revision/coordinator_attempt_id/"
            "wbc_attempt_reference/run_authority_grant_id); lease not bound until "
            "dispatch supplies exact occurrence, grant/fence, and WBC identity"
        )
        return result

    try:
        # Build the RepairOccurrenceKey from the *exact* caller-supplied identity.
        occ_key = build_repair_occurrence_key(
            target=target,
            run_id=run_id,
            run_revision=run_revision,
            coordinator_attempt_id=coordinator_attempt_id,
            fence_token=coordinator_fence_token,
            wbc_attempt_reference=wbc_attempt_reference,
        )
        if occ_key is None:
            result["m7_lease_status"] = "error"
            result["m7_lease_detail"] = "failed to construct RepairOccurrenceKey"
            return result

        # Build the event payload
        payload: dict[str, Any] = {"m7_shadow": True}
        if payload_extra:
            payload.update(dict(payload_extra))
        if not owner_boot_id:
            result["m7_lease_status"] = "pending"
            result["m7_lease_detail"] = "owner boot identity is unavailable"
            return result
        try:
            owner_incarnation = process_owner_identity(int(owner_pid))
        except (TypeError, ValueError):
            owner_incarnation = {}
        owner_pid_namespace = str(
            owner_incarnation.get("pid_namespace") or ""
        )
        owner_process_start = str(
            owner_incarnation.get("process_start_ticks") or ""
        )
        if not owner_pid_namespace or not owner_process_start:
            result["m7_lease_status"] = "pending"
            result["m7_lease_detail"] = (
                "owner PID namespace/process-start identity is unavailable"
            )
            return result
        payload.update(
            {
                "owner_pid_namespace": owner_pid_namespace,
                "owner_process_start_ticks": owner_process_start,
            }
        )

        # Step 11A: route the lifecycle caller through the blessed lease
        # helper instead of constructing a raw CustodyLeaseEvent and calling
        # record_event directly, so owner/process-birth identity, monotonic
        # epoch, TTL ceiling, terminal rejection, and old-epoch fencing are
        # enforced at the store boundary.
        recorded = lease_store.acquire(
            lease_id=lease_id,
            owner_host=owner_host or "unknown",
            owner_pid=owner_pid or "0",
            owner_boot_id=owner_boot_id or "",
            run_authority_grant_id=run_authority_grant_id,
            coordinator_fence_token=coordinator_fence_token,
            wbc_attempt_reference=wbc_attempt_reference,
            occurrence_digest=occ_key.occurrence_digest,
            custody_epoch=custody_epoch,
            sequence=1,
            idempotency_key=f"idem-{lease_id}",
            causal_predecessor=causal_predecessor,
            expires_at=expires_at or None,
            payload=payload,
        )
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


# ── Step 15A: Persist classification, launcher, parser, and missing-child failures ──


def persist_failure_occurrence(
    *,
    queue_dir: str | Path,
    session: str,
    failure_kind: str,
    phase_or_step: str = "",
    detail: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Step 15A: Persist a failed occurrence that may later trigger repair.

    Covers parser loss, classification incompatibility, launcher failure,
    and missing-child failures.  Each persisted occurrence carries exact
    identity so the six-hour reconciliation backstop and recovery event
    joins can bind it to a repair request.
    """
    from arnold_pipelines.megaplan.cloud.recovery_events import (
        RecoveryEventBuilder,
    )

    ts = created_at or utc_now()

    # Map failure_kind to builder method
    builders: dict[str, Any] = {
        "parser_loss": lambda: RecoveryEventBuilder.parser_loss(
            session=session, phase_or_step=phase_or_step, detail=detail,
        ),
        "classification_incompatible": lambda: RecoveryEventBuilder.classification_incompatible(
            session=session, phase_or_step=phase_or_step, observed=detail,
        ),
        "launcher_failure": lambda: RecoveryEventBuilder.launcher_failure(
            session=session, launcher_name=phase_or_step, detail=detail,
        ),
        "missing_child": lambda: RecoveryEventBuilder.missing_child(
            session=session, child_id=phase_or_step, detail=detail,
        ),
    }

    builder = builders.get(failure_kind)
    if builder is None:
        raise ValueError(
            f"Unknown Step 15A failure kind: {failure_kind!r}. "
            f"Supported: {list(builders.keys())}"
        )

    event = builder()

    # Write the failure occurrence as a durable decision in the repair queue
    decision = write_decision(
        queue_dir,
        request_id=event.event_id,
        decision="malformed",
        reason=f"Step 15A {failure_kind}: {detail}",
        created_at=ts,
        evidence={
            "step_15a": True,
            "failure_kind": failure_kind,
            "session": session,
            "phase_or_step": phase_or_step,
            "denominator_group": event.denominator_group,
            "occurred_at": event.occurred_at,
        },
    )

    return {
        "status": "persisted",
        "event_id": event.event_id,
        "failure_kind": failure_kind,
        "denominator_group": event.denominator_group,
        "decision": decision,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 39 (T25) — Occurrence-bound enqueue for lifecycle & supervise producers
# ═══════════════════════════════════════════════════════════════════════════


def enqueue_occurrence_bound_repair_request(
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
    # ── Occurrence identity fields (F01 tuple) ──
    occurrence_identity: Mapping[str, Any] | None = None,
    evidence_cursor_digest: str = "",
    terminal_receipt_expectations: list[str] | None = None,
) -> dict[str, Any]:
    """Enqueue a repair request bound to an exact occurrence identity.

    This is the canonical enqueue path for lifecycle failure and
    supervised-run-exhausted producers.  It accepts the full F01 tuple
    fields through *occurrence_identity*, an *evidence_cursor_digest*,
    and *terminal_receipt_expectations*, then funnels them into
    :func:`enqueue_repair_request` as ``repair_identity`` so later
    recovery joins bind the same exact occurrence.

    A producer that cannot supply the full F01 tuple emits
    ``zero_authority_rejected`` instead of enqueuing a request with
    partial identity (which would be indistinguishable from an
    authority derived from a label, liveness signal, WBC receipt, or
    rebuildable projection).

    Returns the same result shape as :func:`enqueue_repair_request` on
    success, or a typed rejection dict on identity failure.
    """
    from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
        emit_zero_authority_rejection,
    )

    if normalize_owner_adoption_identity(occurrence_identity) is not None:
        # T-0101e' scope restriction: adoption identities are claimable only
        # by occurrence-join; the occurrence-bound enqueue (a generic
        # lifecycle producer path) must reject them.
        rejection = emit_zero_authority_rejection(
            "enqueue_producer",
            source,
            reason=(
                "owner_boundary_adoption identities have restricted scope "
                "(enqueue_exact_occurrence, occurrence_join); the generic "
                "occurrence-bound enqueue cannot claim or dispatch them — "
                "use enqueue_owner_adopted_repair_request"
            ),
        )
        return {
            "status": "zero_authority_rejected",
            "outcome": "zero_authority_rejected",
            "evidence": {
                **(rejection.evidence or {}),
                "identity_kind": OWNER_ADOPTION_IDENTITY_KIND,
            },
        }
    normalized_identity = normalize_repair_identity(occurrence_identity)
    if normalized_identity is None:
        rejection = emit_zero_authority_rejection(
            "enqueue_producer",
            source,
            reason=(
                "the current normalized repair identity is required: exact "
                "F01 occurrence plus run revision/incarnation, coordinator "
                "attempt, fence, lease, grant, and custody epoch"
            ),
        )
        return {
            "status": "zero_authority_rejected",
            "outcome": "zero_authority_rejected",
            "evidence": rejection.evidence,
        }

    return enqueue_repair_request(
        queue_root=queue_root,
        session=session,
        problem_signature=problem_signature,
        root_cause_hint=root_cause_hint,
        source=source,
        marker_dir=marker_dir,
        target=target,
        workspace=workspace,
        run_kind=run_kind,
        created_at=created_at,
        stale_reason=stale_reason,
        superseded_by=superseded_by,
        acceptance_predicate_failure=acceptance_predicate_failure,
        acceptance_transaction_id=acceptance_transaction_id,
        acceptance_snapshot_hash=acceptance_snapshot_hash,
        lease_store_dir=lease_store_dir,
        repair_identity=normalized_identity,
    )


# ═══════════════════════════════════════════════════════════════════════════
# T-0101e' — Owner-boundary adoption enqueue (narrow wrapper)
# ═══════════════════════════════════════════════════════════════════════════


def enqueue_owner_adopted_repair_request(
    *,
    queue_root: str | Path,
    session: str,
    problem_signature: Mapping[str, Any],
    root_cause_hint: Any = "",
    source: str = OWNER_ADOPTION_SOURCE,
    marker_dir: str | Path | None = None,
    target: Mapping[str, Any] | None = None,
    workspace: str | Path | None = None,
    run_kind: str = "",
    created_at: str | None = None,
    repair_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue ONE deterministic owner-adoption request + ONE accepted decision.

    Unlike ordinary :func:`enqueue_repair_request`, an exact retry NEVER
    appends a ``coalesced`` decision that invalidates the accepted decision:

    * the request id is deterministic (the normalized v2 identity binds it);
    * the request marker is written once (claim-locked, atomic);
    * exactly one ``accepted`` decision is recorded, under the shared
      decision/admission flock — the SAME lock ``occurrence-join`` holds
      across its authoritative latest-decision check and the WBC commit;
    * an EXACT retry returns the SAME persisted request + accepted decision
      (idempotent, zero new writes);
    * a byte-divergent existing record at the same request id REFUSES with
      zero mutation (typed ``adoption_request_mismatch`` CliError);
    * the v2 adoption identity is never routed through the generic
      coalesce-on-retry path.
    """
    normalized_identity = normalize_owner_adoption_identity(repair_identity)
    if normalized_identity is None:
        return {
            "status": "zero_authority_rejected",
            "outcome": "zero_authority_rejected",
            "evidence": {
                "reason": (
                    "owner-adoption enqueue requires the normalized "
                    "owner_boundary_adoption identity envelope"
                ),
                "source": str(source or "").strip(),
            },
        }
    queue_root = validate_queue_root(queue_root)
    source_identity = str(source or "").strip()
    if source_identity != OWNER_ADOPTION_SOURCE:
        raise ValueError(
            "owner-adoption enqueue provenance source is fixed to "
            "owner_boundary_occurrence_adoption"
        )

    extended_signature = dict(problem_signature)
    _canonicalize_blocked_task_id(extended_signature)
    normalized_signature = normalize_problem_signature(extended_signature)
    signature_key = problem_signature_key(normalized_signature)
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
        repair_identity=normalized_identity,
    )
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
        "predecessor_request_id": "",
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
        "repair_identity": normalized_identity,
        "repair_identity_key": owner_adoption_identity_key(normalized_identity),
    }
    request_path = requests_dir(queue_root) / f"{request_id}.json"

    def _matches(existing: Mapping[str, Any], fresh: Mapping[str, Any]) -> bool:
        # ``created_at`` is the only time-dependent field in the immutable
        # record; an exact retry at a later wall-clock time must still be
        # byte-equivalent on every AUTHORITATIVE field (identity, signature,
        # target, provenance, evidence).  Any other divergence — a tampered
        # signature, a different adoption identity, a different target — is a
        # hard refusal.
        existing_cmp = {key: value for key, value in existing.items() if key != "created_at"}
        fresh_cmp = {key: value for key, value in fresh.items() if key != "created_at"}
        return existing_cmp == fresh_cmp

    # The whole read → verify → write → accept cycle is serialized under a
    # dedicated request-scoped owner-adoption flock (a SEPARATE file from the
    # decision/admission flock write_decision takes internally, so there is
    # no self-deadlock; the adoption lock is always acquired first, so a
    # concurrent occurrence-join holding the decision/admission lock can
    # never deadlock against an adopter).  Exactly one request marker and
    # exactly one accepted decision can ever be recorded.
    with _owner_adoption_enqueue_lock(queue_root, request_id):
        existing: dict[str, Any] | None = None
        if request_path.exists():
            try:
                existing = json.loads(request_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CliError(
                    "adoption_request_corrupt",
                    f"persisted owner-adoption request {request_id} is corrupt: {exc}",
                ) from exc
            if not isinstance(existing, Mapping):
                raise CliError(
                    "adoption_request_mismatch",
                    f"persisted owner-adoption request {request_id} is not an "
                    "object; refusing instead of overwriting",
                )
            if not _matches(existing, record):
                raise CliError(
                    "adoption_request_mismatch",
                    f"a byte-divergent request already exists at the "
                    f"deterministic id {request_id}; refusing with zero "
                    "mutation instead of overwriting",
                )
            accepted = _find_accepted_decision(queue_root, request_id)
            if accepted is not None:
                return {
                    "status": "already_accepted",
                    "request": existing,
                    "decision": accepted,
                }
        else:
            wrote = _write_once_json(request_path, record)
            if not wrote:
                # A concurrent identical adopter won the request write race:
                # re-read, verify byte equality, and continue to the accept.
                try:
                    existing = json.loads(request_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise CliError(
                        "adoption_request_corrupt",
                        f"persisted owner-adoption request {request_id} is corrupt: {exc}",
                    ) from exc
                if not isinstance(existing, Mapping) or not _matches(existing, record):
                    raise CliError(
                        "adoption_request_mismatch",
                        f"a byte-divergent request won the race at the "
                        f"deterministic id {request_id}; refusing with zero "
                        "mutation",
                    )
                accepted = _find_accepted_decision(queue_root, request_id)
                if accepted is not None:
                    return {
                        "status": "already_accepted",
                        "request": existing,
                        "decision": accepted,
                    }
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="accepted",
            reason="owner boundary adoption queued",
        )
        return {"status": "queued", "request": record, "decision": decision}


__all__ = [
    "ACTIVE_CLAIMS_DIR_NAME",
    "ADOPTION_ATTEMPT_PREFIX",
    "ADOPTION_RUN_PREFIX",
    "ATTEMPTS_DIR_NAME",
    "CURRENT_SCHEMA_VERSION",
    "OWNER_ADOPTED_OCCURRENCE_CONTRACT",
    "OWNER_ADOPTION_AUTHORITY_FIELDS",
    "OWNER_ADOPTION_CAS_FIELDS",
    "OWNER_ADOPTION_FORBIDDEN_FIELDS",
    "OWNER_ADOPTION_IDENTITY_KIND",
    "OWNER_ADOPTION_IDENTITY_SCHEMA",
    "OWNER_ADOPTION_OCCURRENCE_FIELDS",
    "OWNER_ADOPTION_ROOT_FIELDS",
    "OWNER_ADOPTION_SCOPE",
    "OWNER_ADOPTION_SOURCE",
    "REPAIR_IDENTITY_SCHEMA_VERSION",
    "DECISIONS_DIR_NAME",
    "PROBLEM_SIGNATURE_FIELDS",
    "QUEUE_DIR_NAME",
    "OCCURRENCE_CLAIMS_DIR_NAME",
    "ActiveRepairClaimResult",
    "ActiveRepairClaimStatus",
    "DecisionKind",
    "active_claims_dir",
    "active_repair_claim_lock_dir",
    "attempts_dir",
    "claim_active_repair_request",
    "bind_managed_run_to_active_claim",
    "build_owned_lifecycle_repair_identity",
    "build_normalized_repair_identity",
    "derive_repair_identity",
    "enqueue_human_gate_repair_request",
    "enqueue_occurrence_bound_repair_request",
    "enqueue_owner_adopted_repair_request",
    "enqueue_repair_request",
    "find_pending_by_signature",
    "has_claimable_repair_request_contract",
    "has_owner_adopted_repair_request_contract",
    "iter_repair_decisions",
    "iter_repair_attempts",
    "iter_repair_requests",
    "normalize_owner_adoption_identity",
    "normalize_problem_signature",
    "normalize_repair_identity",
    "owner_adopted_repair_request_contract_violations",
    "owner_adoption_identity_key",
    "persist_failure_occurrence",
    "plan_state_has_repair_identity",
    "problem_signature_key",
    "occurrence_claims_dir",
    "record_malformed_file",
    "redacted_hint_hash",
    "repair_queue_dir",
    "repair_identity_key",
    "record_unclaimed_request_failure",
    "release_active_repair_request_claim",
    "singleton_occurrence_claim_lock_dir",
    "repair_request_contract_violations",
    "request_id_for",
    "validate_queue_root",
    "write_decision",
    "write_dispatch_attempt",
    "write_repair_verdict_decision",
]
