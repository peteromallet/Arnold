"""T-0101e: operator-only exact-occurrence join with a fenced claim.

``chain occurrence-join`` binds an operator to the EXACT blocked repair
occurrence already recorded for a chain's current plan and acquires a NEW
current claim/lease for that occurrence.  It is the narrow supported command
behind T-0101's "create/join the exact blocked occurrence, obtain a current
fenced claim" requirement.

Guards (all fail closed, zero mutation on mismatch):

* Operator-only: ``--actor`` must be ``operator``.
* The chain must be durably paused (``operator_pause`` authority) OR
  stopped-blocked (chain ``last_state`` or plan ``current_state`` is
  ``blocked``/``failed``).  The T-0101 flow pauses first.
* Exact-occurrence CAS: ``--session``, ``--occurrence``, ``--request`` and
  ``--decision`` must match the values durably recorded in the central
  repair queue (request record, its ``session`` + ``repair_identity_key``,
  and the decision record bound to the request).  Nothing is minted: there
  is no ``--fresh`` and no ``--force``.
* Claim CAS + fences: the claim attempt is written to the existing WBC
  attempt ledger (``<plan dir>/.phase_wbc_attempts.sqlite3``) under a
  deterministic attempt id derived from ``--claim``, and a custody lease is
  acquired in the plan-scoped lease store (``<plan dir>/custody/leases``).
  The join refuses when another live in-flight claim already holds the
  occurrence or when an unexpired foreign custody lease covers the same
  occurrence digest.  A second join with the same claim id and request is
  idempotent — in the same process (the claim lease is already ours) and
  across process restarts (an unexpired lease whose recorded
  occurrence/request/decision/claim tuple is relationally exact is treated
  as the SAME claim, not as a foreign lease, so an identical CLI retry from
  a new PID succeeds instead of failing with ``lease_owned_elsewhere``).

  The durable receipt is (re)generated atomically on every successful join,
  including re-joins.  If the receipt write fails on a FIRST claim, the
  custody lease is rolled back best-effort (terminal release) and the WBC
  claim attempt is retained as the re-join anchor, so the occurrence is
  never left "claimed but no receipt and no way to re-join": an identical
  re-join with the same claim id re-acquires the released lease and
  completes the receipt.

Writes on success only: the claim/lease stores and the durable receipt JSON
at the caller-supplied ``--receipt`` path.  Chain state.json and the
immutable repair-queue request/decision records are never modified.

Receipt path safety (T-0101h): ``--receipt`` is constrained to the plan's
dedicated evidence root ``<plan dir>/evidence/`` — any resolved path outside
that root is refused, as is any path equal to a protected plan-side file
(``state.json``, the chain spec ``chain.yaml``, or a queue request/decision
record directory).  The receipt is written atomically with hardened
semantics: an unpredictable sibling temp name opened with
``O_CREAT|O_EXCL|O_NOFOLLOW`` (a pre-seeded symlink cannot be followed into
protected state), the file is ``fsync``-ed before ``os.replace`` to the final
path, and the parent directory is ``fsync``-ed after the rename.

Zero-mutation refusal contract (T-0101h): a REFUSAL changes no plan-side
state file — ``state.json``, ``chain.yaml``, the immutable repair-queue
request/decision records, plan markers/manifests, the WBC attempt ledger and
the custody lease store are all byte-identical after any refusal.  Three
provisioning side effects are EXPLICITLY allowed and excluded from that
guarantee: (1) the request-scoped decision/admission advisory flock file
``<queue root>/decision-admission-locks/<sha256(request_id)>.lock`` created
on entering the shared decision/admission lock (intentionally never removed,
like the occurrence lock file — see ``repair_lock.decision_admission_lock``),
(2) the occurrence-scoped advisory flock file
``<plan dir>/custody/leases/occurrence-<sha256>.lock`` created on entering
the occurrence lock (intentionally never removed — unlinking it while
another waiter blocks on the same inode would split the fence), and (3)
idempotent ``CREATE ... IF NOT EXISTS`` schema DDL applied when an ALREADY
EXISTING WBC database is opened (a no-op on a current-schema database).  A
refusal NEVER creates the WBC database and never touches the custody lease
store: the authoritative decision check runs under the shared lock BEFORE
any lease/WBC effect.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from typing import Any, Mapping, Sequence

from arnold.workflow.attempt_ledger_store import (
    AttemptLedgerError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)

from arnold_pipelines.megaplan._core.state import resolve_plan_dir
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.operator_pause import is_paused
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_lock import decision_admission_lock
from arnold_pipelines.megaplan.custody.contracts import (
    normalize_repair_occurrence_key,
    process_birth_identity,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    LeaseStoreError,
    open_lease_store,
)
from arnold_pipelines.megaplan.custody.phase_wbc import PHASE_WBC_LEDGER_FILENAME
from arnold_pipelines.megaplan.types import CliError

SCHEMA = "arnold.megaplan.occurrence-join.v1"
CLAIM_KIND = "occurrence_join"
OPERATOR_ACTOR = "operator"
#: Default TTL for the operator claim lease (24h).  The T-0101 repair flow
#: releases the claim when it is done; the TTL is a fence backstop only.
DEFAULT_LEASE_TTL_SECONDS = 24 * 60 * 60
#: Blocked states accepted by the paused-or-stopped-blocked gate.
_STOPPED_BLOCKED_STATES = frozenset({"blocked", "failed"})
#: Plan-scoped evidence root: the ONLY directory occurrence-join receipts may
#: be written into.  Protected plan-side state (state.json, chain.yaml, queue
#: request/decision records, markers, manifests) never lives under it, so a
#: receipt can never alias plan-side state.
EVIDENCE_DIRNAME = "evidence"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _required(value: str, flag: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CliError("invalid_args", f"{flag} is required")
    return normalized


def occurrence_claim_attempt_id(plan_dir: str | Path, claim_id: str) -> str:
    """Return the deterministic WBC attempt id for an operator claim.

    The attempt id is derived from the exact plan directory and the
    caller-supplied claim id so a re-join with the same claim id resolves to
    the same attempt stream (the claim/attempt relational identity is stable
    and provable from the receipt).
    """
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"occurrence-join::{Path(plan_dir).resolve()}::{str(claim_id).strip()}",
        )
    )


def occurrence_join_lease_id(claim_id: str) -> str:
    """Return the deterministic custody lease id derived from the claim id."""
    digest = hashlib.sha256(str(claim_id or "").strip().encode("utf-8")).hexdigest()
    return f"occurrence-join-{digest[:16]}"


def _load_request_record(queue_root: Path, request_id: str) -> dict[str, Any]:
    request_path = repair_requests.requests_dir(queue_root) / f"{request_id}.json"
    try:
        record = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        record = None
    if (
        not isinstance(record, Mapping)
        or not repair_requests.has_claimable_repair_request_contract(record)
    ):
        raise CliError(
            "request_not_found",
            f"repair request {request_id!r} is not recorded as a claimable "
            "request in the central repair queue",
        )
    return dict(record)


def _load_decision_record(queue_root: Path, decision_id: str) -> dict[str, Any]:
    for candidate in repair_requests.iter_repair_decisions(queue_root):
        if str(candidate.get("decision_id") or "").strip() == decision_id:
            return dict(candidate)
    raise CliError(
        "decision_not_found",
        f"repair decision {decision_id!r} is not recorded in the central repair queue",
    )


def _validate_receipt_destination(
    receipt_path: Path | None,
    *,
    plan_dir: Path,
    protected_paths: Sequence[Path],
) -> Path | None:
    """Constrain a caller-supplied receipt path to the plan evidence root.

    Refuses (typed ``CliError``, zero mutation — read-only):

    * ``receipt_outside_evidence_root``: any resolved path OUTSIDE
      ``<plan dir>/evidence/`` (this is the primary defense — protected
      plan-side files like ``state.json``, ``chain.yaml``, queue
      request/decision records, markers and manifests never live under the
      evidence root, so an alias can never resolve inside it); and
    * ``receipt_aliases_protected_state``: any resolved path EQUAL to a
      protected plan-side file/dir in *protected_paths* (defense in depth
      for exotic layouts where a protected path resolves under the evidence
      root).

    Returns the resolved receipt path (or ``None`` when the caller supplied
    no receipt).
    """
    if receipt_path is None:
        return None
    receipt = Path(receipt_path).expanduser().resolve()
    evidence_root = (plan_dir / EVIDENCE_DIRNAME).resolve()
    try:
        receipt.relative_to(evidence_root)
    except ValueError:
        raise CliError(
            "receipt_outside_evidence_root",
            f"receipt path {receipt} is outside the plan evidence root "
            f"{evidence_root}; occurrence-join receipts must be written under "
            f"<plan dir>/{EVIDENCE_DIRNAME}/",
            extra={
                "receipt_path": str(receipt),
                "evidence_root": str(evidence_root),
            },
        ) from None
    for protected in protected_paths:
        try:
            if receipt == Path(protected).expanduser().resolve():
                raise CliError(
                    "receipt_aliases_protected_state",
                    f"receipt path {receipt} aliases protected plan-side state "
                    f"{protected}",
                    extra={
                        "receipt_path": str(receipt),
                        "protected_path": str(protected),
                    },
                )
        except OSError:
            # Unresolvable protected path (e.g. dangling symlink): nothing to
            # alias, keep validating the rest.
            continue
    return receipt


def _write_receipt_durably(receipt_path: Path, receipt: Mapping[str, Any]) -> None:
    """Atomically create *receipt_path* with hardened durability semantics.

    * The payload is written to an UNPREDICTABLE sibling temp name
      (``.<name>.<random-hex>.tmp``) opened with
      ``O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW``, so a pre-seeded symlink (e.g. a
      stale predictable ``<receipt>.tmp`` pointing at ``state.json``) can
      never be followed into protected state — a collision fails closed with
      ``EEXIST`` instead of writing through the link.
    * The file is ``os.fsync``-ed BEFORE ``os.replace`` to the final path and
      the parent directory is ``os.fsync``-ed AFTER the rename, so the
      receipt is durable across power loss.  ``os.replace`` replaces the
      final directory entry itself, so a pre-seeded symlink AT the final
      path is replaced, never followed.
    """
    parent = receipt_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{receipt_path.name}.{uuid.uuid4().hex}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, receipt_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _latest_decision_for_request(
    queue_root: Path, request_id: str
) -> dict[str, Any] | None:
    """Return the most recently recorded repair decision for *request_id*.

    Decisions carry second-resolution ``created_at`` timestamps and the
    repair queue provides NO monotonic sequence/rowid:
    ``iter_repair_decisions`` breaks same-second ties by content-hash
    ``decision_id``, which is NOT chronological evidence.  When two
    decisions for the same request share the same ``created_at`` the
    "latest" is ambiguous — this helper raises a typed
    ``ambiguous_decision`` error (fail closed, zero mutation) instead of
    guessing by content hash, so a same-second supersession can never
    authorize a stale acceptance.
    """
    candidates = [
        dict(candidate)
        for candidate in repair_requests.iter_repair_decisions(queue_root)
        if str(candidate.get("request_id") or "").strip() == request_id
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda record: (
            str(record.get("created_at") or ""),
            str(record.get("decision_id") or ""),
        )
    )
    latest_created_at = str(candidates[-1].get("created_at") or "").strip()
    tied = [
        candidate
        for candidate in candidates
        if str(candidate.get("created_at") or "").strip() == latest_created_at
    ]
    if len(tied) > 1:
        raise CliError(
            "ambiguous_decision",
            f"the latest repair decision for request {request_id!r} is "
            f"ambiguous: {len(tied)} decisions share the same second-"
            f"resolution created_at {latest_created_at!r} and the queue "
            "records no monotonic sequence, so no decision can be proven "
            "latest; refusing instead of guessing by content hash",
            extra={
                "request_id": request_id,
                "created_at": latest_created_at,
                "decision_ids": sorted(
                    str(candidate.get("decision_id") or "") for candidate in tied
                ),
            },
        )
    return tied[0]


def _verify_decision_still_latest(
    queue_root: Path, request_id: str, decision_id: str
) -> None:
    """Fail closed when *decision_id* is no longer the latest for the request.

    The outer admission gate (a fast pre-check) runs before the shared
    decision/admission lock is entered; the AUTHORITATIVE re-verification is
    called under that lock (``repair_lock.decision_admission_lock``) BEFORE
    any lease/WBC effect, and the lock is held through the atomic WBC STARTED
    commit — ``write_decision`` takes the same lock, so a superseding
    decision can never land between this check and the admission (T-0101h
    blocker 1).  A refusal here is zero-mutation by construction: no WBC
    open, no lease acquire, no release append (blocker 2).  Raises
    ``decision_superseded`` (or ``ambiguous_decision`` via the tie check)
    when the authority has changed.
    """
    latest = _latest_decision_for_request(queue_root, request_id)
    latest_id = str(latest.get("decision_id") or "").strip() if latest is not None else ""
    if latest_id != decision_id:
        raise CliError(
            "decision_superseded",
            f"repair decision {decision_id!r} is no longer the latest decision "
            f"for request {request_id!r} (latest={latest_id!r}, kind="
            f"{str(latest.get('decision') or '') if latest is not None else ''!r}); "
            "a stale or superseded decision cannot authorize a new claim",
            extra={
                "expected_decision": decision_id,
                "latest_decision_id": latest_id,
                "latest_decision_kind": (
                    str(latest.get("decision") or "") if latest is not None else ""
                ),
                "request_id": request_id,
            },
        )


def _plan_latest_failure_summary(plan_state: Mapping[str, Any]) -> dict[str, Any]:
    failure = plan_state.get("latest_failure")
    if not isinstance(failure, Mapping):
        return {}
    summary: dict[str, Any] = {}
    for key in ("kind", "phase", "recorded_at", "message", "suggested_action"):
        value = failure.get(key)
        if isinstance(value, str) and value.strip():
            summary[key] = value.strip()
    metadata = failure.get("metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("blocked_no_lease"), str):
        summary["blocked_no_lease"] = metadata["blocked_no_lease"]
    return summary


def _live_claim_records(store: SqliteAttemptLedgerStore, occurrence_id: str) -> list[dict[str, Any]]:
    """Return in-flight claim records (STARTED, no terminal) for an occurrence."""
    live: list[dict[str, Any]] = []
    for attempt_id in store.list_in_flight_attempts():
        events = store.read_events(attempt_id)
        started = next(
            (event for event in events if event.event_type == AttemptEventType.STARTED),
            None,
        )
        if started is None:
            continue
        payload = started.payload if isinstance(started.payload, dict) else {}
        if str(payload.get("occurrence_id") or "").strip() != occurrence_id:
            continue
        if str(payload.get("kind") or "").strip() != CLAIM_KIND:
            continue
        live.append(
            {
                "attempt_id": attempt_id,
                "claim_id": str(payload.get("claim_id") or "").strip(),
                "request_id": str(payload.get("request_id") or "").strip(),
                "lease_id": str(payload.get("lease_id") or "").strip(),
            }
        )
    return live


def _lease_covers_occurrence(
    lease_store: Any,
    lease_id: str,
    *,
    f01_digest: str,
    occurrence_id: str,
) -> bool:
    """Return whether a custody lease covers the exact occurrence.

    The lease state carries a reconstructed ``occurrence_key``; leases whose
    acquire payload embedded the full occurrence contract are matched on the
    exact F01 digest.  Legacy leases that only recorded the opaque
    ``occurrence_id`` are matched on the event payload instead.
    """
    lease = lease_store.current_lease(lease_id)
    if lease is None:
        return False
    try:
        lease_digest = str(lease.occurrence_key.occurrence_digest or "").strip()
    except Exception:  # noqa: BLE001 - synthetic/legacy leases may lack keys
        lease_digest = ""
    if lease_digest and f01_digest and lease_digest == f01_digest:
        return True
    for event in lease_store.load_history(lease_id):
        payload = event.payload if isinstance(event.payload, dict) else {}
        if str(payload.get("occurrence_id") or "").strip() == occurrence_id:
            return True
    return False


def _foreign_active_leases(
    lease_store: Any,
    *,
    own_lease_id: str,
    f01_digest: str,
    occurrence_id: str,
) -> list[dict[str, Any]]:
    """Return active (non-expired) foreign leases covering the occurrence."""
    base_dir = Path(lease_store.base_dir)
    if not base_dir.is_dir():
        return []
    foreign: list[dict[str, Any]] = []
    for history in sorted(base_dir.glob("*.history.jsonl")):
        candidate_id = history.name.removesuffix(".history.jsonl")
        if candidate_id == own_lease_id:
            continue
        candidate = lease_store.current_lease(candidate_id)
        if candidate is None:
            continue
        if candidate.is_expired:
            continue
        if not _lease_covers_occurrence(
            lease_store,
            candidate_id,
            f01_digest=f01_digest,
            occurrence_id=occurrence_id,
        ):
            continue
        foreign.append(
            {
                "lease_id": candidate_id,
                "owner_host": str(candidate.owner_host or ""),
                "owner_pid": str(candidate.owner_pid or ""),
                "owner_boot_id": str(candidate.owner_boot_id or ""),
                "expires_at": str(candidate.expires_at or ""),
            }
        )
    return foreign


def _lease_acquire_payload(lease_store: Any, lease_id: str) -> dict[str, Any]:
    """Return the payload of the acquire event that created the current lease.

    ``CustodyLease`` itself does not carry the acquire payload; the
    relational claim tuple is recovered from the most recent ``acquire``
    event in the lease history.  (The event payload is a frozen
    ``Mapping``, not a plain ``dict``, after replay.)
    """
    for event in reversed(lease_store.load_history(lease_id)):
        if getattr(event, "event_type", None) == "acquire":
            payload = event.payload if isinstance(event.payload, Mapping) else {}
            return dict(payload)
    return {}


def _lease_is_terminal(lease_store: Any, lease_id: str) -> bool:
    """Return whether the recorded lease's last lifecycle event is terminal.

    ``CustodyLease.is_expired`` is not reliable as a terminality test: a
    released lease's ``expires_at`` is advanced only one second past
    acquisition, so it can read as unexpired within that window.  The lease
    history's last lifecycle event is the authoritative terminal marker.
    """
    for event in reversed(lease_store.load_history(lease_id)):
        event_type = str(getattr(event, "event_type", "") or "")
        if event_type == "conflict":
            # Conflict events do not mutate lifecycle state; keep scanning.
            continue
        return event_type in ("release", "expire", "fence")
    return False


def _lease_is_relational_rejoin(
    lease_store: Any,
    lease: Any,
    *,
    lease_id: str,
    attempt_id: str,
    f01_digest: str,
    occurrence_id: str,
    claim_id: str,
    request_id: str,
    decision_id: str,
    session: str,
) -> bool:
    """Return whether an unexpired lease is a relationally-exact re-join.

    Cross-process idempotency proof: the earlier (possibly crashed or
    restarted) invocation that holds this lease recorded the EXACT same
    claim tuple — same WBC attempt (deterministic from the claim id and plan
    dir), same run-authority grant (request id), same occurrence digest, and
    the same claim/request/decision/occurrence/session ids in the acquire
    payload.  A lease that matches is THIS claim, so the re-join proceeds
    idempotently; anything else remains a foreign-lease refusal.
    """
    if lease.is_expired:
        return False
    if str(lease.run_authority_grant_id or "").strip() != request_id:
        return False
    if str(lease.wbc_attempt_reference or "").strip() != attempt_id:
        return False
    try:
        lease_digest = str(lease.occurrence_key.occurrence_digest or "").strip()
    except Exception:  # noqa: BLE001 - synthetic/legacy leases may lack keys
        lease_digest = ""
    if lease_digest != f01_digest:
        return False
    payload = _lease_acquire_payload(lease_store, lease_id)
    if not payload:
        return False
    return (
        str(payload.get("claim_id") or "").strip() == claim_id
        and str(payload.get("request_id") or "").strip() == request_id
        and str(payload.get("decision_id") or "").strip() == decision_id
        and str(payload.get("occurrence_id") or "").strip() == occurrence_id
        and str(payload.get("session") or "").strip() == session
    )


def _started_event(
    *,
    attempt_id: str,
    session: str,
    occurrence_id: str,
    f01_digest: str,
    claim_id: str,
    request_id: str,
    decision_id: str,
    lease_id: str,
    fence_token: int,
    coordinator_attempt_id: str,
    wbc_attempt_reference: str,
    actor: str,
    reason: str,
    plan_name: str,
    spec_path: str,
    occurred_at: str,
) -> LedgerEvent:
    return LedgerEvent(
        idempotency_key=f"{attempt_id}:started",
        event_type=AttemptEventType.STARTED,
        identity=AttemptIdentity(
            workflow_id="megaplan-occurrence-join",
            run_id=session,
            graph_revision=occurrence_id[:32] or "0",
            step_id="occurrence-join",
            invocation_id=claim_id,
            attempt_ordinal=1,
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(actor_id=actor, tool_id="megaplan.occurrence_join"),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="1"),
        versions=VersionSet(
            code_version=SCHEMA,
            config_version="occurrence-join.v1",
            template_version="occurrence-join.v1",
        ),
        grant_ref=GrantRef(grant_id=request_id, decision_id=decision_id),
        sequence=1,
        causal_predecessor_sequence=0,
        append_position=1,
        occurred_at=occurred_at,
        observed_at=occurred_at,
        persistence_status=PersistenceStatus.DURABLE,
        outcome=None,
        payload={
            "kind": CLAIM_KIND,
            "occurrence_id": occurrence_id,
            "occurrence_digest": f01_digest,
            "claim_id": claim_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "lease_id": lease_id,
            "fence_token": fence_token,
            "coordinator_attempt_id": coordinator_attempt_id,
            "wbc_attempt_reference": wbc_attempt_reference,
            "session": session,
            "actor": actor,
            "reason": reason,
            "plan_name": plan_name,
            "spec_path": spec_path,
        },
    )


def join_exact_occurrence(
    *,
    spec_path: Path,
    project_dir: Path,
    session: str,
    occurrence_id: str,
    request_id: str,
    decision_id: str,
    claim_id: str,
    reason: str,
    actor: str,
    receipt_path: str | Path | None = None,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> dict[str, Any]:
    """Join the exact blocked occurrence and acquire a fenced claim for it.

    Raises :class:`~arnold_pipelines.megaplan.types.CliError` on any guard
    violation.  All guards run before any write; on success the only writes
    are the WBC claim attempt (``.phase_wbc_attempts.sqlite3``), the plan
    custody lease store (``<plan dir>/custody/leases``), and the durable
    receipt JSON at *receipt_path*.

    *receipt_path* (when given) MUST resolve under the plan evidence root
    ``<plan dir>/evidence/`` and must not alias protected plan-side state;
    any other destination is refused with ``receipt_outside_evidence_root``
    / ``receipt_aliases_protected_state`` before any write.  The receipt is
    written with hardened atomic semantics (unpredictable temp name with
    ``O_EXCL|O_NOFOLLOW``, file ``fsync`` before ``os.replace``, directory
    ``fsync`` after), so a pre-seeded symlink can never redirect the write
    into protected state.

    Re-joins are idempotent both in-process and across process restarts:
    an unexpired lease whose recorded occurrence/request/decision/claim tuple
    is relationally exact is treated as the same claim, and the receipt is
    (re)generated.  If the receipt write fails on a FIRST claim, the lease is
    rolled back best-effort and a ``receipt_write_failed`` error is raised;
    the WBC claim attempt remains as the re-join anchor so an identical
    re-join with the same claim id can reclaim and complete the receipt.
    """
    actor_n = _required(actor, "--actor")
    if actor_n != OPERATOR_ACTOR:
        raise CliError(
            "actor_forbidden",
            "occurrence-join is operator-only: --actor must be 'operator'",
        )
    session_n = _required(session, "--session")
    occurrence_id_n = _required(occurrence_id, "--occurrence")
    request_id_n = _required(request_id, "--request")
    decision_id_n = _required(decision_id, "--decision")
    claim_id_n = _required(claim_id, "--claim")
    reason_n = _required(reason, "--reason")

    spec_path = Path(spec_path).expanduser().resolve()
    project_dir = Path(project_dir).expanduser().resolve()
    receipt_path = (
        Path(receipt_path).expanduser()
        if receipt_path is not None
        else None
    )
    if lease_ttl_seconds < 1:
        raise CliError("invalid_args", "lease_ttl_seconds must be positive")

    # ── Chain state (observe-only; never rewritten) ──────────────────────
    chain_state = chain_spec.load_chain_state(
        spec_path,
        verify_execution_binding=False,
    )
    paused = is_paused(chain_state)
    plan_name = str(chain_state.current_plan_name or "").strip()
    if not plan_name:
        raise CliError(
            "no_current_plan",
            "chain has no current plan; there is no blocked occurrence to join",
        )
    try:
        plan_dir = resolve_plan_dir(project_dir, plan_name)
    except CliError:
        plan_dir = project_dir / ".megaplan" / "plans" / plan_name
        if not plan_dir.exists():
            raise CliError(
                "plan_dir_unavailable",
                f"plan directory for {plan_name!r} is unavailable under {project_dir}",
            )
    state_path = plan_dir / "state.json"
    if not state_path.exists():
        raise CliError(
            "plan_state_unavailable",
            f"plan state.json is unavailable for {plan_name!r} at {state_path}",
        )
    try:
        plan_state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(
            "plan_state_unreadable",
            f"plan state.json for {plan_name!r} is unreadable: {exc}",
        ) from exc
    if not isinstance(plan_state, Mapping):
        raise CliError("plan_state_unreadable", f"plan state.json for {plan_name!r} is not an object")

    # ── Paused-or-stopped-blocked gate ────────────────────────────────────
    chain_last_state = str(chain_state.last_state or "").strip()
    plan_current_state = str(plan_state.get("current_state") or "").strip()
    stopped_blocked = (
        chain_last_state in _STOPPED_BLOCKED_STATES
        or plan_current_state in _STOPPED_BLOCKED_STATES
    )
    if not (paused or stopped_blocked):
        raise CliError(
            "chain_not_paused_or_blocked",
            "occurrence-join requires a durably paused or stopped-blocked "
            "chain (the T-0101 flow pauses first); observed "
            f"chain last_state={chain_last_state!r} plan "
            f"current_state={plan_current_state!r}",
        )

    # ── Queue identity (the recorded authority; read-only) ────────────────
    queue_root = repair_requests.validate_queue_root(
        project_dir / ".megaplan" / "repair-queue"
    )
    # ── Receipt destination guard (read-only; fail closed before ANY write).
    #    --receipt must resolve under <plan dir>/evidence/ and never alias
    #    protected plan-side state (state.json, chain.yaml, queue records).
    receipt_path = _validate_receipt_destination(
        receipt_path,
        plan_dir=plan_dir,
        protected_paths=[
            state_path,
            spec_path,
            repair_requests.requests_dir(queue_root),
            repair_requests.decisions_dir(queue_root),
        ],
    )
    request_record = _load_request_record(queue_root, request_id_n)
    recorded_session = str(request_record.get("session") or "").strip()
    if recorded_session != session_n:
        raise CliError(
            "session_mismatch",
            f"session {session_n!r} does not match the recorded request session "
            f"{recorded_session!r}",
            extra={
                "expected_session": session_n,
                "recorded_session": recorded_session,
                "request_id": request_id_n,
            },
        )
    recorded_occurrence = str(request_record.get("repair_identity_key") or "").strip()
    if not recorded_occurrence:
        raise CliError(
            "occurrence_not_recorded",
            f"repair request {request_id_n!r} carries no recorded occurrence "
            "identity (legacy zero-authority record); reacquire a current "
            "normalized identity before joining",
        )
    if recorded_occurrence != occurrence_id_n:
        raise CliError(
            "occurrence_mismatch",
            f"occurrence {occurrence_id_n!r} does not match the recorded "
            f"occurrence {recorded_occurrence!r} for request {request_id_n!r}",
            extra={
                "expected_occurrence": occurrence_id_n,
                "recorded_occurrence": recorded_occurrence,
                "request_id": request_id_n,
            },
        )
    normalized_identity = repair_requests.normalize_repair_identity(
        request_record.get("repair_identity")
    )
    if normalized_identity is None:
        raise CliError(
            "occurrence_not_recorded",
            f"repair request {request_id_n!r} carries no normalized repair identity",
        )
    occurrence_raw = normalized_identity.get("occurrence")
    occurrence_key = (
        normalize_repair_occurrence_key(occurrence_raw)
        if isinstance(occurrence_raw, Mapping)
        else None
    )
    if occurrence_key is None:
        raise CliError(
            "occurrence_not_recorded",
            f"repair request {request_id_n!r} occurrence contract is invalid",
        )
    f01_digest = str(occurrence_key.occurrence_digest or "").strip()

    # Plan-side occurrence cross-check (only when the plan persisted identity).
    plan_meta = plan_state.get("meta") if isinstance(plan_state, Mapping) else {}
    plan_identity_raw = plan_meta.get("repair_identity") if isinstance(plan_meta, Mapping) else None
    if plan_identity_raw is not None:
        plan_identity = repair_requests.normalize_repair_identity(plan_identity_raw)
        if (
            plan_identity is None
            or repair_requests.repair_identity_key(plan_identity) != occurrence_id_n
        ):
            raise CliError(
                "occurrence_mismatch",
                "plan-state repair identity disagrees with the requested occurrence",
                extra={
                    "expected_occurrence": occurrence_id_n,
                    "plan_occurrence_key": (
                        repair_requests.repair_identity_key(plan_identity)
                        if plan_identity is not None
                        else ""
                    ),
                },
            )

    decision_record = _load_decision_record(queue_root, decision_id_n)
    decision_request_id = str(decision_record.get("request_id") or "").strip()
    if decision_request_id != request_id_n:
        raise CliError(
            "decision_mismatch",
            f"repair decision {decision_id_n!r} is recorded for request "
            f"{decision_request_id!r}, not {request_id_n!r}",
            extra={
                "expected_decision": decision_id_n,
                "decision_request_id": decision_request_id,
                "expected_request_id": request_id_n,
            },
        )

    # ── Decision admission gate (fast pre-check, fail closed, no writes) ──
    # Only the LATEST 'accepted' decision for the request may authorize a
    # claim.  A coalesced/stale/superseded/dispatched/claim_retry/
    # claim_alert/malformed decision is not an acceptance authority
    # (DecisionKind, repair_requests.py:556-566), and even an 'accepted'
    # decision that has since been superseded by a newer decision for the
    # same request is stale (repair_requests.py treats stale/superseded as
    # terminal).  Same-second ties fail closed with a typed
    # ``ambiguous_decision`` instead of guessing by content-hash order.  This
    # gate is a read-only fast pre-check; the AUTHORITATIVE re-verification
    # runs again under the shared decision/admission lock before any
    # lease/WBC effect, so a refusal here or there is zero-mutation by
    # construction.
    decision_kind = str(decision_record.get("decision") or "").strip()
    if decision_kind != "accepted":
        raise CliError(
            "decision_not_accepted",
            f"repair decision {decision_id_n!r} for request {request_id_n!r} "
            f"has kind {decision_kind!r}; only an 'accepted' decision may "
            "authorize an occurrence claim",
            extra={
                "expected_decision": decision_id_n,
                "decision_kind": decision_kind,
                "request_id": request_id_n,
            },
        )
    _verify_decision_still_latest(queue_root, request_id_n, decision_id_n)

    # ── Authoritative fence + custody epoch (carried from the recorded
    #    occurrence identity; never fabricated per-claim) ──────────────────
    fence_token = int(occurrence_key.fence_token or 0)
    coordinator_attempt_id = str(occurrence_key.coordinator_attempt_id or "").strip()
    wbc_attempt_reference = str(occurrence_key.wbc_attempt_reference or "").strip()
    identity_custody_epoch = int(normalized_identity.get("custody_epoch") or 0)
    seed_custody_epoch = max(identity_custody_epoch, 1)

    # ── Claim identity + fences (read-only until acquisition) ─────────────
    attempt_id = occurrence_claim_attempt_id(plan_dir, claim_id_n)
    lease_id = occurrence_join_lease_id(claim_id_n)

    wbc_path = plan_dir / PHASE_WBC_LEDGER_FILENAME
    lease_store = open_lease_store(plan_dir / "custody" / "leases")

    # ── Shared decision/admission lock (T-0101h blockers 1+2) ─────────────
    # write_decision() and claim admission share ONE request-scoped advisory
    # flock (repair_lock.decision_admission_lock), held from the AUTHORITATIVE
    # latest-decision check through the atomic WBC STARTED commit, so a
    # superseding decision can never land between the check and the admission
    # (blocker 1 — the outer gate above is only a fast pre-check).  The
    # authoritative check runs BEFORE any lease/WBC effect, keeping a refusal
    # zero-mutation (blocker 2): a refused join leaves the WBC file ABSENT
    # (never created) and the custody tree byte-identical — no lease acquire,
    # no release append.  Only the ``decision-admission-locks`` sidecar (an
    # allowed provisioning side effect, like the occurrence flock file) may
    # remain.
    with decision_admission_lock(queue_root, request_id_n):
        _verify_decision_still_latest(queue_root, request_id_n, decision_id_n)

        # ── Occurrence-scoped serialization (T-0101e) ─────────────────────
        # The custody lease is keyed by the CLAIM id
        # (occurrence_join_lease_id), so two distinct claims for the SAME
        # occurrence share zero serialization — two independent leases could
        # both win.  The occurrence-digest flock is held across every
        # occurrence guard and the WBC STARTED append so exactly one
        # contender wins; the loser re-scans INSIDE the lock and refuses with
        # a typed error and zero mutation.  The WBC ledger's
        # UNIQUE(occurrence_id) admission CAS — enforced inside the single
        # ``_append_tx`` transaction of ``append_started``, atomically with
        # the STARTED insert — is the final backstop for any race that slips
        # past the flocks.
        with lease_store.occurrence_claim_lock(f01_digest):
            wbc_store: SqliteAttemptLedgerStore | None = (
                SqliteAttemptLedgerStore(wbc_path) if wbc_path.exists() else None
            )

            claim_already_started = False
            if wbc_store is not None:
                events = wbc_store.read_events(attempt_id)
                if events:
                    started = events[0]
                    if started.event_type != AttemptEventType.STARTED:
                        raise CliError(
                            "claim_invalid",
                            f"claim attempt {attempt_id} has an invalid event stream",
                        )
                    started_payload = (
                        started.payload if isinstance(started.payload, dict) else {}
                    )
                    recorded_claim_id = str(started_payload.get("claim_id") or "").strip()
                    recorded_request_id = str(started_payload.get("request_id") or "").strip()
                    recorded_decision_id = str(started_payload.get("decision_id") or "").strip()
                    recorded_occurrence_id = str(started_payload.get("occurrence_id") or "").strip()
                    recorded_lease_id = str(started_payload.get("lease_id") or "").strip()
                    if (
                        recorded_claim_id != claim_id_n
                        or recorded_request_id != request_id_n
                        or recorded_decision_id != decision_id_n
                        or recorded_occurrence_id != occurrence_id_n
                        or recorded_lease_id != lease_id
                    ):
                        raise CliError(
                            "claim_id_mismatch",
                            f"claim {claim_id_n!r} is already recorded for a different "
                            f"request/occurrence (recorded claim={recorded_claim_id!r} "
                            f"request={recorded_request_id!r} "
                            f"decision={recorded_decision_id!r} "
                            f"occurrence={recorded_occurrence_id!r})",
                            extra={
                                "expected_claim_id": claim_id_n,
                                "recorded_claim_id": recorded_claim_id,
                                "recorded_request_id": recorded_request_id,
                                "recorded_decision_id": recorded_decision_id,
                                "recorded_occurrence_id": recorded_occurrence_id,
                                "recorded_lease_id": recorded_lease_id,
                                "attempt_id": attempt_id,
                            },
                        )
                    if wbc_store.has_terminal_event(attempt_id):
                        raise CliError(
                            "claim_terminal",
                            f"claim {claim_id_n!r} is already recorded with a terminal "
                            "outcome; a new claim id is required",
                        )
                    claim_already_started = True

                # Occurrence fence: no OTHER live claim may hold the occurrence.
                foreign_claims = _live_claim_records(wbc_store, occurrence_id_n)
                for claim in foreign_claims:
                    if claim["attempt_id"] == attempt_id:
                        continue
                    raise CliError(
                        "another_live_claim",
                        f"occurrence {occurrence_id_n[:16]}… is already held by live "
                        f"claim {claim['claim_id']!r} (request {claim['request_id']!r})",
                        extra={"live_claim": claim, "occurrence_id": occurrence_id_n},
                    )

            foreign_leases = _foreign_active_leases(
                lease_store,
                own_lease_id=lease_id,
                f01_digest=f01_digest,
                occurrence_id=occurrence_id_n,
            )
            if foreign_leases:
                first = foreign_leases[0]
                raise CliError(
                    "unexpired_foreign_lease",
                    f"occurrence {occurrence_id_n[:16]}… is covered by an unexpired "
                    f"foreign custody lease {first['lease_id']!r} owned by "
                    f"({first['owner_host']!r},{first['owner_pid']!r})",
                    extra={"foreign_leases": foreign_leases, "occurrence_id": occurrence_id_n},
                )

            # ── Fenced acquisition ────────────────────────────────────────────
            owner = process_birth_identity()
            owner_tuple = (
                str(owner.get("host") or ""),
                str(owner.get("pid") or ""),
                str(owner.get("boot_id") or ""),
            )
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=lease_ttl_seconds)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            occurred_at = _utc_now()

            claim_payload = {
                "kind": CLAIM_KIND,
                "occurrence_key": occurrence_key.to_dict(),
                "occurrence_id": occurrence_id_n,
                "claim_id": claim_id_n,
                "request_id": request_id_n,
                "decision_id": decision_id_n,
                # Authoritative fence carry: the lease, the WBC STARTED event and
                # the receipt all record the occurrence's OWN fence/attempt
                # identity instead of a fabricated 0/1 per-claim value.
                "fence_token": fence_token,
                "coordinator_attempt_id": coordinator_attempt_id,
                "wbc_attempt_reference": wbc_attempt_reference,
                "session": session_n,
                "actor": actor_n,
                "reason": reason_n,
            }

            def _winner_or_denied(exc: LeaseStoreError) -> Any:
                """Accept a concurrent winner holding the exact same claim, else deny."""
                winner = lease_store.current_lease(lease_id)
                if (
                    winner is not None
                    and (
                        (
                            str(winner.owner_host or "") == owner_tuple[0]
                            and str(winner.owner_pid or "") == owner_tuple[1]
                        )
                        or _lease_is_relational_rejoin(
                            lease_store,
                            winner,
                            lease_id=lease_id,
                            attempt_id=attempt_id,
                            f01_digest=f01_digest,
                            occurrence_id=occurrence_id_n,
                            claim_id=claim_id_n,
                            request_id=request_id_n,
                            decision_id=decision_id_n,
                            session=session_n,
                        )
                    )
                ):
                    # A concurrent re-join won first with the exact same claim (same
                    # owner identity or a relationally-exact record).
                    return None
                raise CliError(
                    "lease_denied",
                    f"custody lease acquisition for claim {claim_id_n!r} failed: {exc}",
                    extra={"lease_id": lease_id},
                ) from exc

            def _acquire_lease() -> Any:
                """Acquire the claim lease for a fresh (no-record) claim."""
                try:
                    return lease_store.acquire(
                        lease_id=lease_id,
                        owner_host=owner_tuple[0],
                        owner_pid=owner_tuple[1],
                        owner_boot_id=owner_tuple[2],
                        run_authority_grant_id=request_id_n,
                        coordinator_fence_token=fence_token,
                        wbc_attempt_reference=attempt_id,
                        occurrence_digest=f01_digest,
                        custody_epoch=seed_custody_epoch,
                        expires_at=expires_at,
                        payload=claim_payload,
                    )
                except LeaseStoreError as exc:
                    return _winner_or_denied(exc)

            def _reclaim_lease(previous: Any) -> Any:
                """Re-acquire a lease whose prior lifecycle ended (terminal or lapsed).

                The custody epoch is seeded from the RECORDED occurrence identity
                and never moves backward vs the recorded store: a reclaim carries
                ``max(identity_epoch, previous_epoch + 1)`` so the store's
                monotonic-epoch invariant is always satisfied.
                """
                try:
                    return lease_store.reclaim(
                        lease_id=lease_id,
                        owner_host=owner_tuple[0],
                        owner_pid=owner_tuple[1],
                        owner_boot_id=owner_tuple[2],
                        run_authority_grant_id=request_id_n,
                        coordinator_fence_token=fence_token,
                        wbc_attempt_reference=attempt_id,
                        occurrence_digest=f01_digest,
                        custody_epoch=max(
                            seed_custody_epoch,
                            int(getattr(previous, "custody_epoch", 0) or 0) + 1,
                        ),
                        expires_at=expires_at,
                        payload=claim_payload,
                    )
                except LeaseStoreError as exc:
                    return _winner_or_denied(exc)

            current = lease_store.current_lease(lease_id)
            lease_event: Any = None
            if current is None:
                lease_event = _acquire_lease()
            elif _lease_is_terminal(lease_store, lease_id) or current.is_expired:
                # Terminal or TTL-expired lease record (released/expired/fenced):
                # the prior fence lapsed or its lifecycle ended.  This is the
                # recovery path after a rolled-back receipt write (lease released,
                # WBC claim retained as the re-join anchor) and after
                # fence-backstop expiry.
                if current.is_expired and not _lease_is_terminal(lease_store, lease_id):
                    # TTL lapsed without a terminal event: record the system-driven
                    # expiry so the blessed reclaim (which requires a terminal last
                    # lifecycle event) is permitted.
                    try:
                        lease_store.expire(lease_id=lease_id)
                    except LeaseStoreError as exc:
                        raise CliError(
                            "lease_denied",
                            f"custody lease expiry for claim {claim_id_n!r} failed: {exc}",
                            extra={"lease_id": lease_id},
                        ) from exc
                    current = lease_store.current_lease(lease_id)
                lease_event = _reclaim_lease(current)
            elif (
                str(current.owner_host or "") == owner_tuple[0]
                and str(current.owner_pid or "") == owner_tuple[1]
                and (
                    not owner_tuple[2]
                    or not str(current.owner_boot_id or "")
                    or str(current.owner_boot_id or "") == owner_tuple[2]
                )
            ):
                # Idempotent re-join: the claim lease is already ours.
                pass
            elif _lease_is_relational_rejoin(
                lease_store,
                current,
                lease_id=lease_id,
                attempt_id=attempt_id,
                f01_digest=f01_digest,
                occurrence_id=occurrence_id_n,
                claim_id=claim_id_n,
                request_id=request_id_n,
                decision_id=decision_id_n,
                session=session_n,
            ):
                # Cross-process re-join: an identical earlier invocation from a
                # different process (crash/restart) left an unexpired,
                # relationally exact lease for this claim.  Treat it as an
                # idempotent re-join and (re)generate the receipt below;
                # ownership is left as recorded.
                pass
            else:
                raise CliError(
                    "lease_owned_elsewhere",
                    f"claim lease {lease_id!r} is already owned by "
                    f"({current.owner_host!r},{current.owner_pid!r})",
                    extra={"lease_id": lease_id, "owner": owner_tuple},
                )

            # Post-acquisition occurrence fence re-check (closes the
            # scan/acquire race; now serialized under the occurrence flock).
            if wbc_store is None:
                wbc_store = SqliteAttemptLedgerStore(wbc_path)
            foreign_claims_after = _live_claim_records(wbc_store, occurrence_id_n)
            for claim in foreign_claims_after:
                if claim["attempt_id"] == attempt_id:
                    continue
                if not claim_already_started:
                    _release_lease_best_effort(lease_store, lease_id, owner_tuple)
                raise CliError(
                    "another_live_claim",
                    f"occurrence {occurrence_id_n[:16]}… was claimed concurrently by "
                    f"live claim {claim['claim_id']!r} (request {claim['request_id']!r})",
                    extra={"live_claim": claim, "occurrence_id": occurrence_id_n},
                )

            # Durable WBC claim attempt (idempotent when already started).
            # T-0101h round-4 blocker 3: the occurrence admission CAS, the
            # attempt reservation and the STARTED insert all happen inside the
            # SINGLE ``_append_tx`` transaction of ``append_started`` — a crash
            # before STARTED leaves no stranded admission row, and a losing
            # contender's append rolls back as a whole (typed claim_denied,
            # zero mutation).  Decision authority was verified under the shared
            # decision/admission lock BEFORE any lease/WBC effect above, and
            # that lock is still held here — write_decision takes the same
            # lock, so no superseding decision can have landed in between
            # (T-0101h blockers 1+2); there is no in-flock re-check to fail
            # after the lease is acquired, so a refusal can never mutate.
            if not claim_already_started:
                started = _started_event(
                    attempt_id=attempt_id,
                    session=session_n,
                    occurrence_id=occurrence_id_n,
                    f01_digest=f01_digest,
                    claim_id=claim_id_n,
                    request_id=request_id_n,
                    decision_id=decision_id_n,
                    lease_id=lease_id,
                    fence_token=fence_token,
                    coordinator_attempt_id=coordinator_attempt_id,
                    wbc_attempt_reference=wbc_attempt_reference,
                    actor=actor_n,
                    reason=reason_n,
                    plan_name=plan_name,
                    spec_path=str(spec_path),
                    occurred_at=occurred_at,
                )
                try:
                    wbc_store.append_started(attempt_id, started)
                except AttemptLedgerError as exc:
                    _release_lease_best_effort(lease_store, lease_id, owner_tuple)
                    raise CliError(
                        "claim_denied",
                        f"durable claim acquisition for claim {claim_id_n!r} failed: {exc}",
                        extra={"attempt_id": attempt_id, "lease_id": lease_id},
                    ) from exc

    lease_record = lease_store.current_lease(lease_id)
    status = "claimed" if not claim_already_started else "already_claimed"

    receipt = {
        "schema": SCHEMA,
        "status": status,
        "recorded_at": _utc_now(),
        "spec": str(spec_path),
        "project_dir": str(project_dir),
        "plan": plan_name,
        "plan_dir": str(plan_dir),
        "chain": {
            "last_state": chain_last_state,
            "paused": paused,
            "stopped_blocked": stopped_blocked,
        },
        "occurrence": {
            "id": occurrence_id_n,
            "f01_digest": f01_digest,
            "fence_token": fence_token,
            "coordinator_attempt_id": coordinator_attempt_id,
            "wbc_attempt_reference": wbc_attempt_reference,
            "latest_failure": _plan_latest_failure_summary(plan_state),
        },
        "session": session_n,
        "request_id": request_id_n,
        "decision_id": decision_id_n,
        "claim_id": claim_id_n,
        "attempt_id": attempt_id,
        "lease": {
            "lease_id": lease_id,
            "event_id": str(getattr(lease_event, "event_id", "") or ""),
            "coordinator_fence_token": (
                int(getattr(lease_record, "coordinator_fence_token", 0) or 0)
                if lease_record is not None
                else fence_token
            ),
            "custody_epoch": (
                int(getattr(lease_record, "custody_epoch", 0) or 0)
                if lease_record is not None
                else 1
            ),
            "expires_at": (
                str(getattr(lease_record, "expires_at", "") or "")
                if lease_record is not None
                else expires_at
            ),
            "owner": {
                "host": (
                    str(getattr(lease_record, "owner_host", "") or "")
                    if lease_record is not None
                    else ""
                )
                or owner_tuple[0],
                "pid": (
                    str(getattr(lease_record, "owner_pid", "") or "")
                    if lease_record is not None
                    else ""
                )
                or owner_tuple[1],
                "boot_id": (
                    str(getattr(lease_record, "owner_boot_id", "") or "")
                    if lease_record is not None
                    else ""
                )
                or owner_tuple[2],
            },
        },
        "relation": {
            # request -> decision -> claim -> attempt relational equality:
            # every record binds the SAME request id and the SAME occurrence.
            "request_id": request_id_n,
            "decision_request_id": decision_request_id,
            "claim_request_id": request_id_n,
            "attempt_request_id": request_id_n,
            "request_session": recorded_session,
            "request_occurrence": recorded_occurrence,
            "claim_occurrence_id": occurrence_id_n,
            "attempt_occurrence_id": occurrence_id_n,
            "attempt_claim_id": claim_id_n,
            "attempt_decision_id": decision_id_n,
            "attempt_lease_id": lease_id,
        },
        "reason": reason_n,
        "actor": actor_n,
    }

    receipt_out = None
    if receipt_path is not None:
        try:
            _write_receipt_durably(receipt_path, receipt)
            receipt_out = str(receipt_path)
        except OSError as exc:
            if not claim_already_started:
                # FIRST claim: roll the custody lease back (best-effort,
                # terminal release) so the occurrence is not stranded behind a
                # foreign-owner fence.  The WBC claim attempt is intentionally
                # retained as the re-join anchor (the ledger is append-only):
                # an identical re-join with the same claim id sees the claim
                # already started, re-acquires the released lease, and
                # completes the receipt.
                _release_lease_best_effort(lease_store, lease_id, owner_tuple)
            raise CliError(
                "receipt_write_failed",
                f"durable receipt write for claim {claim_id_n!r} failed: {exc}; "
                "the claim is recoverable — re-run occurrence-join with the "
                "same claim id to regenerate the receipt",
                extra={
                    "claim_id": claim_id_n,
                    "attempt_id": attempt_id,
                    "lease_id": lease_id,
                    "receipt_path": str(receipt_path),
                    "rolled_back_lease": not claim_already_started,
                },
            ) from exc

    return {
        "status": status,
        "paused": paused,
        "stopped_blocked": stopped_blocked,
        "plan": plan_name,
        "plan_dir": str(plan_dir),
        "session": session_n,
        "occurrence": occurrence_id_n,
        "request_id": request_id_n,
        "decision_id": decision_id_n,
        "claim_id": claim_id_n,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "receipt_path": receipt_out,
        "receipt": receipt,
    }


def _release_lease_best_effort(
    lease_store: Any,
    lease_id: str,
    owner_tuple: tuple[str, str, str],
) -> None:
    """Best-effort terminal release of a lease we just acquired."""
    try:
        lease_store.release(
            lease_id=lease_id,
            owner_host=owner_tuple[0],
            owner_pid=owner_tuple[1],
            owner_boot_id=owner_tuple[2],
        )
    except Exception:  # noqa: BLE001 - release is best-effort cleanup
        pass


__all__ = [
    "CLAIM_KIND",
    "DEFAULT_LEASE_TTL_SECONDS",
    "EVIDENCE_DIRNAME",
    "OPERATOR_ACTOR",
    "SCHEMA",
    "_validate_receipt_destination",
    "_write_receipt_durably",
    "join_exact_occurrence",
    "occurrence_claim_attempt_id",
    "occurrence_join_lease_id",
]
