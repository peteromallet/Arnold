"""Versioned immutable acceptance transaction models and deterministic content hashing.

Acceptance snapshots are content-addressed, frozen evidence records that back
atomic milestone completion.  The contract is:

* Snapshots are **immutable** after construction — there is no ``set_*`` or update API.
* Content hashing is **deterministic** and **byte-stable**: identical semantic
  input always produces the same SHA-256 digest regardless of dict key iteration
  order, whitespace, or platform.
* Required identity fields (transaction ID, chain run ID, milestone label, etc.)
  are validated at construction time and rejected with a clear error.
* ``AcceptanceReceipt`` is a lightweight pointer that lives in
  ``ChainState.completed`` records while the full snapshot is stored as a
  separate content-addressed artifact (SD2).

Schema version is pinned at 1 and must remain backward-compatible for all
serialized snapshots.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

ACCEPTANCE_SNAPSHOT_SCHEMA = "megaplan.acceptance_snapshot"
ACCEPTANCE_SNAPSHOT_SCHEMA_VERSION = 1

ACCEPTANCE_TRANSACTION_SCHEMA = "megaplan.acceptance_transaction"
ACCEPTANCE_TRANSACTION_SCHEMA_VERSION = 1

ACCEPTANCE_RECEIPT_SCHEMA = "megaplan.acceptance_receipt"
ACCEPTANCE_RECEIPT_SCHEMA_VERSION = 1

ACCEPTANCE_BOUNDARY_RESULT_SCHEMA = "megaplan.acceptance_boundary_result"
ACCEPTANCE_BOUNDARY_RESULT_SCHEMA_VERSION = 1

# Canonical JSON encoder used for deterministic content hashing.
# sort_keys=True + separators with no whitespace guarantee byte-stable output
# for equivalent JSON payloads across Python versions and platforms.
_CANONICAL_JSON_KWARGS: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonical_json_bytes(obj: Any) -> bytes:
    """Serialize *obj* to canonical (sorted-key, compact) JSON bytes."""
    return json.dumps(obj, **_CANONICAL_JSON_KWARGS).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Return ``sha256:...`` hex digest for *data*."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _required_str(value: Any, field_name: str) -> str:
    """Return a non-empty string, raising :class:`ValueError` if missing."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"acceptance_transaction: {field_name} is required and must be a non-empty string")
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# AcceptanceSnapshot — immutable content-addressed evidence container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcceptanceSnapshot:
    """Immutable content-addressed snapshot of acceptance evidence.

    The snapshot is a **value object**: once constructed it cannot change.
    Its cryptographic identity is derived from the canonical JSON
    serialization of its non-hash fields, making it suitable for CAS
    storage and cryptographic comparison.

    Required fields
    ---------------
    * ``transaction_id`` — unique identity of the acceptance transaction.
    * ``chain_run_id`` — identity of the chain run this snapshot belongs to.
    * ``milestone_label`` — chain-spec milestone label (e.g. "m5a").
    * ``milestone_index`` — zero-based index in the chain spec.
    * ``plan_name`` — megaplan plan name that executed the milestone.
    * ``source_commit_ref`` — git commit/tree ref at the time evidence was collected.
    * ``runtime_identity`` — identifier for the runtime that produced this evidence.
    * ``evidence`` — tuple of :class:`EvidenceRef` (imported lazily to avoid cycles).

    The ``content_hash`` is computed once at construction and frozen.
    """

    transaction_id: str
    chain_run_id: str
    milestone_label: str
    milestone_index: int
    plan_name: str
    source_commit_ref: str
    runtime_identity: str
    evidence: tuple[Any, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    base_sha: str | None = None
    tip_sha: str | None = None
    branch_head: str | None = None
    pr_head: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    observed_at: str = field(default_factory=_now_iso)
    schema: str = ACCEPTANCE_SNAPSHOT_SCHEMA
    schema_version: int = ACCEPTANCE_SNAPSHOT_SCHEMA_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        """Validate required fields and freeze the content hash.

        Uses :func:`object.__setattr__` because the dataclass is frozen.
        """
        # Validate required identity fields
        _required_str(self.transaction_id, "transaction_id")
        _required_str(self.chain_run_id, "chain_run_id")
        _required_str(self.milestone_label, "milestone_label")
        _required_str(self.plan_name, "plan_name")
        _required_str(self.source_commit_ref, "source_commit_ref")
        _required_str(self.runtime_identity, "runtime_identity")

        if self.milestone_index < 0:
            raise ValueError(
                f"acceptance_transaction: milestone_index must be >= 0, got {self.milestone_index}"
            )

        # Compute content hash from the canonical serialization of all fields
        # *except* content_hash itself.
        payload = self._content_payload()
        digest = _sha256_hex(_canonical_json_bytes(payload))
        object.__setattr__(self, "content_hash", digest)

    def _content_payload(self) -> dict[str, Any]:
        """Return the canonical dict used for content hashing.

        Excludes ``content_hash`` itself and uses sorted evidence for
        deterministic output.
        """
        from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceRef

        evidence_dicts: list[dict[str, Any]] = []
        for ref in self.evidence:
            if isinstance(ref, EvidenceRef):
                evidence_dicts.append(ref.to_dict())
            elif isinstance(ref, dict):
                evidence_dicts.append(dict(ref))
            else:
                evidence_dicts.append({"value": str(ref)})
        # Sort by kind then status for deterministic ordering
        evidence_dicts.sort(key=lambda e: (str(e.get("kind", "")), str(e.get("status", ""))))

        payload: dict[str, Any] = {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "chain_run_id": self.chain_run_id,
            "milestone_label": self.milestone_label,
            "milestone_index": self.milestone_index,
            "plan_name": self.plan_name,
            "source_commit_ref": self.source_commit_ref,
            "runtime_identity": self.runtime_identity,
            "evidence": evidence_dicts,
            "evidence_refs": sorted(self.evidence_refs),
        }
        if self.base_sha is not None:
            payload["base_sha"] = self.base_sha
        if self.tip_sha is not None:
            payload["tip_sha"] = self.tip_sha
        if self.branch_head is not None:
            payload["branch_head"] = self.branch_head
        if self.pr_head is not None:
            payload["pr_head"] = self.pr_head
        if self.pr_number is not None:
            payload["pr_number"] = self.pr_number
        if self.pr_state is not None:
            payload["pr_state"] = self.pr_state
        return payload

    def to_dict(self) -> dict[str, Any]:
        """Serialize the snapshot including its content hash."""
        from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceRef

        evidence_dicts: list[dict[str, Any]] = []
        for ref in self.evidence:
            if isinstance(ref, EvidenceRef):
                evidence_dicts.append(ref.to_dict())
            elif isinstance(ref, dict):
                evidence_dicts.append(dict(ref))
            else:
                evidence_dicts.append({"value": str(ref)})

        d: dict[str, Any] = {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "chain_run_id": self.chain_run_id,
            "milestone_label": self.milestone_label,
            "milestone_index": self.milestone_index,
            "plan_name": self.plan_name,
            "source_commit_ref": self.source_commit_ref,
            "runtime_identity": self.runtime_identity,
            "evidence": evidence_dicts,
            "evidence_refs": list(self.evidence_refs),
            "observed_at": self.observed_at,
            "content_hash": self.content_hash,
        }
        if self.base_sha is not None:
            d["base_sha"] = self.base_sha
        if self.tip_sha is not None:
            d["tip_sha"] = self.tip_sha
        if self.branch_head is not None:
            d["branch_head"] = self.branch_head
        if self.pr_head is not None:
            d["pr_head"] = self.pr_head
        if self.pr_number is not None:
            d["pr_number"] = self.pr_number
        if self.pr_state is not None:
            d["pr_state"] = self.pr_state
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AcceptanceSnapshot":
        """Deserialize from a dict, re-computing the content hash.

        The content hash from the serialized form is validated against
        a fresh computation.  A mismatch raises :class:`ValueError`.
        """
        from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceRef

        raw_evidence = d.get("evidence", ())
        if not isinstance(raw_evidence, (list, tuple)):
            raw_evidence = ()
        evidence = tuple(
            EvidenceRef.from_dict(item)
            for item in raw_evidence
            if isinstance(item, dict)
        )

        evidence_refs_raw = d.get("evidence_refs", ())
        if not isinstance(evidence_refs_raw, (list, tuple)):
            evidence_refs_raw = ()

        stored_hash = d.get("content_hash", "")

        snapshot = cls(
            transaction_id=str(d.get("transaction_id", "")),
            chain_run_id=str(d.get("chain_run_id", "")),
            milestone_label=str(d.get("milestone_label", "")),
            milestone_index=int(d.get("milestone_index", -1)),
            plan_name=str(d.get("plan_name", "")),
            source_commit_ref=str(d.get("source_commit_ref", "")),
            runtime_identity=str(d.get("runtime_identity", "")),
            evidence=evidence,
            evidence_refs=tuple(str(ref) for ref in evidence_refs_raw),
            base_sha=_optional_str(d.get("base_sha")),
            tip_sha=_optional_str(d.get("tip_sha")),
            branch_head=_optional_str(d.get("branch_head")),
            pr_head=_optional_str(d.get("pr_head")),
            pr_number=_optional_int(d.get("pr_number")),
            pr_state=_optional_str(d.get("pr_state")),
            observed_at=str(d.get("observed_at", _now_iso())),
            schema=str(d.get("schema", ACCEPTANCE_SNAPSHOT_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")) or ACCEPTANCE_SNAPSHOT_SCHEMA_VERSION,
        )

        # Validate that the stored hash matches the fresh computation
        if stored_hash and snapshot.content_hash != stored_hash:
            raise ValueError(
                f"acceptance_transaction: content hash mismatch — "
                f"stored={stored_hash} computed={snapshot.content_hash}"
            )

        return snapshot

    def with_receipt(self) -> "AcceptanceReceipt":
        """Create a lightweight receipt pointing at this snapshot."""
        return AcceptanceReceipt(
            transaction_id=self.transaction_id,
            snapshot_hash=self.content_hash,
            milestone_label=self.milestone_label,
            milestone_index=self.milestone_index,
            plan_name=self.plan_name,
        )


# ---------------------------------------------------------------------------
# AcceptanceTransaction — links snapshot to a completion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcceptanceTransaction:
    """A completed acceptance transaction linking a snapshot to its outcome.

    This is the durable record produced after an acceptance boundary run
    succeeds.  It carries the snapshot hash, the resulting verdict, and
    metadata about the runtime/tested commit identity.
    """

    transaction_id: str
    snapshot_hash: str
    accepted: bool
    mode: str  # "shadow" | "atomic" | "enforce"
    tested_commit_ref: str
    tested_runtime_identity: str
    verdict_ref: str | None = None
    failure_reasons: tuple[str, ...] = ()
    completed_at: str = field(default_factory=_now_iso)
    schema: str = ACCEPTANCE_TRANSACTION_SCHEMA
    schema_version: int = ACCEPTANCE_TRANSACTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _required_str(self.transaction_id, "transaction_id")
        _required_str(self.snapshot_hash, "snapshot_hash")
        _required_str(self.mode, "mode")
        _required_str(self.tested_commit_ref, "tested_commit_ref")
        _required_str(self.tested_runtime_identity, "tested_runtime_identity")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "snapshot_hash": self.snapshot_hash,
            "accepted": self.accepted,
            "mode": self.mode,
            "tested_commit_ref": self.tested_commit_ref,
            "tested_runtime_identity": self.tested_runtime_identity,
            "failure_reasons": list(self.failure_reasons),
            "completed_at": self.completed_at,
        }
        if self.verdict_ref is not None:
            d["verdict_ref"] = self.verdict_ref
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AcceptanceTransaction":
        failures = d.get("failure_reasons", ())
        if not isinstance(failures, (list, tuple)):
            failures = ()
        return cls(
            transaction_id=str(d.get("transaction_id", "")),
            snapshot_hash=str(d.get("snapshot_hash", "")),
            accepted=bool(d.get("accepted", False)),
            mode=str(d.get("mode", "shadow")),
            tested_commit_ref=str(d.get("tested_commit_ref", "")),
            tested_runtime_identity=str(d.get("tested_runtime_identity", "")),
            verdict_ref=_optional_str(d.get("verdict_ref")),
            failure_reasons=tuple(str(item) for item in failures),
            completed_at=str(d.get("completed_at", _now_iso())),
            schema=str(d.get("schema", ACCEPTANCE_TRANSACTION_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")) or ACCEPTANCE_TRANSACTION_SCHEMA_VERSION,
        )


# ---------------------------------------------------------------------------
# AcceptanceReceipt — lightweight pointer stored in ChainState.completed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcceptanceReceipt:
    """Lightweight pointer to an acceptance snapshot for ChainState.completed.

    Per SD2, only transaction IDs and snapshot hashes are stored in
    ``ChainState.completed`` records.  The full snapshot is stored as a
    separate content-addressed artifact.
    """

    transaction_id: str
    snapshot_hash: str
    milestone_label: str
    milestone_index: int
    plan_name: str
    schema: str = ACCEPTANCE_RECEIPT_SCHEMA
    schema_version: int = ACCEPTANCE_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _required_str(self.transaction_id, "transaction_id")
        _required_str(self.snapshot_hash, "snapshot_hash")
        _required_str(self.milestone_label, "milestone_label")
        _required_str(self.plan_name, "plan_name")
        if self.milestone_index < 0:
            raise ValueError(
                f"acceptance_transaction: milestone_index must be >= 0, got {self.milestone_index}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "snapshot_hash": self.snapshot_hash,
            "milestone_label": self.milestone_label,
            "milestone_index": self.milestone_index,
            "plan_name": self.plan_name,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AcceptanceReceipt":
        return cls(
            transaction_id=str(d.get("transaction_id", "")),
            snapshot_hash=str(d.get("snapshot_hash", "")),
            milestone_label=str(d.get("milestone_label", "")),
            milestone_index=int(d.get("milestone_index", -1)),
            plan_name=str(d.get("plan_name", "")),
            schema=str(d.get("schema", ACCEPTANCE_RECEIPT_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")) or ACCEPTANCE_RECEIPT_SCHEMA_VERSION,
        )


# ---------------------------------------------------------------------------
# Acceptance boundary runner — validates source/runtime identity, runs the
# declared suite, collects raw execution evidence, and calls the predicate
# providers WITHOUT committing any chain state.  The caller decides whether to
# commit an acceptance transaction based on ``result.accepted``.
#
# Design notes (T9 / M5A fail-closed milestone):
#
# * Identity is validated FIRST.  An unbound identity (short SHA, mutable
#   alias, shadow placeholder) short-circuits the run — the suite is never
#   executed against an unbound commit, and no provider is invoked.  This
#   prevents a skipped or reordered validation from granting false completion
#   authority.
# * The runner collects raw commands, log paths + digests, exit codes,
#   timestamps, suite identity (run_id), commit/tree identity (code_hash),
#   and artifact digests before computing ``accepted``.
# * ``accepted = identity_valid AND suite_passed AND verdict.accepted``.
# * No chain state (ChainState, journal transactions, completion records,
#   cursor) is written by the runner.  Suite-run evidence may be appended to
#   the append-only suite-run log (evidence collection, not chain authority)
#   so downstream providers can freshness-skip a re-run; this is configurable.
# ---------------------------------------------------------------------------


def _read_json_file(path: Path) -> dict[str, Any] | None:
    """Best-effort JSON read; returns ``None`` on any error or non-object."""
    try:
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _compute_file_digest(path: Any) -> str | None:
    """SHA-256 digest of a file's bytes (``sha256:...``); ``None`` if unreadable."""
    try:
        p = Path(path)
        if not p.is_file():
            return None
        digest = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except OSError:
        return None


def _suite_result_to_record(result: Any) -> dict[str, Any]:
    """Serialize a ``SuiteRunResult`` to a stable record dict.

    Mirrors the fields persisted by :func:`append_suite_run` so that a
    serialized boundary result is self-contained and round-trips back through
    :func:`_record_to_result`.
    """
    if result is None:
        return {}
    return {
        "run_id": getattr(result, "run_id", ""),
        "phase": getattr(result, "phase", ""),
        "command": getattr(result, "command", ""),
        "duration": getattr(result, "duration", 0.0),
        "collected": getattr(result, "collected", 0),
        "collected_ids": list(getattr(result, "collected_ids", []) or []),
        "failures": list(getattr(result, "failures", []) or []),
        "passes": list(getattr(result, "passes", []) or []),
        "status": getattr(result, "status", ""),
        "exit_code": getattr(result, "exit_code", None),
        "code_hash": getattr(result, "code_hash", ""),
        "raw_log_path": str(getattr(result, "raw_log_path", "") or ""),
        "collections_parse_ok": bool(getattr(result, "collections_parse_ok", False)),
        "collection_errors": list(getattr(result, "collection_errors", []) or []),
        "timeout_reason": getattr(result, "timeout_reason", None),
    }


@dataclass(frozen=True)
class CandidateInvalidation:
    """Record of a candidate acceptance transaction that was invalidated.

    This is a lightweight, serializable record suitable for storage in
    ``ChainState.candidate_invalidation``.  It captures the identity of the
    invalidated candidate and the reason for invalidation.

    Required fields
    ---------------
    * ``transaction_id`` — the transaction ID of the invalidated candidate.
    * ``reason`` — machine-readable reason tag (e.g. ``"stale-evidence"``,
      ``"repair-result"``, ``"content-hash-mismatch"``).
    * ``superseded_by`` — transaction ID of the new candidate that triggered
      the invalidation (or ``None`` for a discard with no successor).
    """

    transaction_id: str
    reason: str
    superseded_by: str | None = None
    invalidated_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        _required_str(self.transaction_id, "transaction_id")
        _required_str(self.reason, "reason")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "transaction_id": self.transaction_id,
            "reason": self.reason,
            "superseded_by": self.superseded_by,
            "invalidated_at": self.invalidated_at,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CandidateInvalidation":
        return cls(
            transaction_id=str(d.get("transaction_id", "")),
            reason=str(d.get("reason", "")),
            superseded_by=_optional_str(d.get("superseded_by")),
            invalidated_at=str(d.get("invalidated_at", _now_iso())),
        )


def check_and_invalidate_stale_candidates(
    snapshot: AcceptanceSnapshot,
    *,
    plan_dir: Path,
    prior_candidates: dict[str, Any] | None = None,
) -> tuple[CandidateInvalidation, ...]:
    """Check for prior uncommitted candidates and invalidate any whose evidence differs.

    This implements the fail-closed candidate invalidation semantics (T10):
    any repair or evidence change that produces a new snapshot with a different
    content hash from a prior uncommitted candidate invalidates the prior
    candidate.  The caller must then commit the new snapshot via a fresh full
    boundary run — old candidate snapshots cannot be reused.

    Parameters
    ----------
    snapshot
        The new acceptance snapshot intended to replace any stale candidates.
    plan_dir
        Megaplan storage area where prepare files are staged.
    prior_candidates
        Optional pre-fetched dict of uncommitted candidates (from
        :func:`~arnold_pipelines.megaplan.orchestration.completion_io.list_uncommitted_acceptance_candidates`).
        When ``None`` the candidates are loaded from *plan_dir*.

    Returns
    -------
    tuple[CandidateInvalidation, ...]
        Invalidation records for every prior uncommitted candidate whose
        snapshot hash differs from *snapshot.content_hash*.  Empty tuple when
        there are no stale candidates to invalidate.
    """
    from arnold_pipelines.megaplan.orchestration.completion_io import (
        list_uncommitted_acceptance_candidates,
    )

    candidates = prior_candidates
    if candidates is None:
        candidates = list_uncommitted_acceptance_candidates(plan_dir)

    invalidations: list[CandidateInvalidation] = []

    for tx_id, candidate in candidates.items():
        candidate_hash = getattr(candidate, "snapshot_hash", None)
        if not isinstance(candidate_hash, str) or not candidate_hash:
            # Malformed candidate without a hash — invalidate it.
            invalidations.append(
                CandidateInvalidation(
                    transaction_id=tx_id,
                    reason="malformed-candidate",
                    superseded_by=snapshot.transaction_id,
                )
            )
            continue

        if candidate_hash != snapshot.content_hash:
            # Evidence changed — the prior candidate is stale.
            invalidations.append(
                CandidateInvalidation(
                    transaction_id=tx_id,
                    reason="stale-evidence",
                    superseded_by=snapshot.transaction_id,
                )
            )

    return tuple(invalidations)


@dataclass(frozen=True)
class AcceptanceBoundaryResult:
    """Outcome of running the acceptance boundary for one snapshot.

    Captures identity validation, raw suite-execution evidence, and the
    predicate-provider verdict.  The runner NEVER commits chain state — it
    writes no ChainState, journal transaction, completion record, or cursor.
    The caller is responsible for committing an
    :class:`AcceptanceTransaction` (or discarding the candidate) based on
    ``accepted``.
    """

    snapshot: AcceptanceSnapshot
    identity_valid: bool
    identity_failures: tuple[str, ...]
    suite_run: Any | None  # SuiteRunResult | None
    verdict: Any | None  # CompletionVerdict | None
    commands: tuple[str, ...]
    exit_codes: tuple[int | None, ...]
    log_paths: tuple[str, ...]
    log_digests: tuple[str | None, ...]
    started_at: str
    completed_at: str
    suite_identity: str | None  # suite run_id
    commit_tree: str | None  # code_hash (tested tree identity)
    artifact_digests: dict[str, str]
    suite_status: str | None
    accepted: bool
    duration_seconds: float
    failure_reasons: tuple[str, ...]
    mode: str
    invalidated_candidates: tuple[Any, ...] = ()  # tuple[CandidateInvalidation, ...]
    schema: str = ACCEPTANCE_BOUNDARY_RESULT_SCHEMA
    schema_version: int = ACCEPTANCE_BOUNDARY_RESULT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            CompletionVerdict,
        )

        verdict_obj = self.verdict
        if isinstance(verdict_obj, CompletionVerdict):
            verdict_dict: Any = verdict_obj.to_dict()
        elif isinstance(verdict_obj, dict):
            verdict_dict = verdict_obj
        else:
            verdict_dict = None
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "snapshot": self.snapshot.to_dict(),
            "identity_valid": self.identity_valid,
            "identity_failures": list(self.identity_failures),
            "suite_run": (
                _suite_result_to_record(self.suite_run)
                if self.suite_run is not None
                else None
            ),
            "verdict": verdict_dict,
            "commands": list(self.commands),
            "exit_codes": list(self.exit_codes),
            "log_paths": list(self.log_paths),
            "log_digests": list(self.log_digests),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "suite_identity": self.suite_identity,
            "commit_tree": self.commit_tree,
            "artifact_digests": dict(self.artifact_digests),
            "suite_status": self.suite_status,
            "accepted": self.accepted,
            "duration_seconds": self.duration_seconds,
            "failure_reasons": list(self.failure_reasons),
            "mode": self.mode,
            "invalidated_candidates": [
                inv.to_dict() if hasattr(inv, "to_dict") else inv
                for inv in self.invalidated_candidates
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AcceptanceBoundaryResult":
        snapshot_raw = d.get("snapshot")
        snapshot: Any = (
            AcceptanceSnapshot.from_dict(snapshot_raw)
            if isinstance(snapshot_raw, dict)
            else snapshot_raw
        )

        suite_run_raw = d.get("suite_run")
        suite_run: Any | None = None
        if isinstance(suite_run_raw, dict) and suite_run_raw:
            try:
                from arnold_pipelines.megaplan.orchestration.suite_runs_log import (
                    _record_to_result,
                )

                suite_run = _record_to_result(suite_run_raw)
            except Exception:
                suite_run = suite_run_raw

        verdict_raw = d.get("verdict")
        verdict_obj: Any | None = None
        if isinstance(verdict_raw, dict) and verdict_raw:
            try:
                from arnold_pipelines.megaplan.orchestration.completion_contract import (
                    CompletionVerdict,
                )

                verdict_obj = CompletionVerdict.from_dict(verdict_raw)
            except Exception:
                verdict_obj = verdict_raw

        return cls(
            snapshot=snapshot,
            identity_valid=bool(d.get("identity_valid", False)),
            identity_failures=tuple(str(x) for x in d.get("identity_failures", [])),
            suite_run=suite_run,
            verdict=verdict_obj,
            commands=tuple(str(x) for x in d.get("commands", [])),
            exit_codes=tuple(x for x in d.get("exit_codes", [])),
            log_paths=tuple(str(x) for x in d.get("log_paths", [])),
            log_digests=tuple(
                (str(x) if x is not None else None) for x in d.get("log_digests", [])
            ),
            started_at=str(d.get("started_at", "")),
            completed_at=str(d.get("completed_at", "")),
            suite_identity=d.get("suite_identity"),
            commit_tree=d.get("commit_tree"),
            artifact_digests=dict(d.get("artifact_digests", {}) or {}),
            suite_status=d.get("suite_status"),
            accepted=bool(d.get("accepted", False)),
            duration_seconds=float(d.get("duration_seconds", 0.0) or 0.0),
            failure_reasons=tuple(str(x) for x in d.get("failure_reasons", [])),
            mode=str(d.get("mode", "atomic")),
            invalidated_candidates=tuple(
                CandidateInvalidation.from_dict(inv)
                if isinstance(inv, dict)
                else inv
                for inv in (d.get("invalidated_candidates") or [])
                if isinstance(inv, (dict, CandidateInvalidation))
            ),
            schema=str(d.get("schema", ACCEPTANCE_BOUNDARY_RESULT_SCHEMA)),
            schema_version=(
                _optional_int(d.get("schema_version"))
                or ACCEPTANCE_BOUNDARY_RESULT_SCHEMA_VERSION
            ),
        )


def _validate_acceptance_identity(
    snapshot: AcceptanceSnapshot,
) -> tuple[bool, tuple[str, ...]]:
    """Validate source commit ref and runtime identity (fail-closed).

    Uses the canonical validators from :class:`CommitRuntimeProvider` so the
    acceptance boundary and the completion contract share one identity rule
    set.  Mutable aliases (branch names, HEAD, PR refs), short SHAs, and
    shadow/warning placeholders are rejected.
    """
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        CommitRuntimeProvider,
    )

    failures: list[str] = []
    commit_check = CommitRuntimeProvider._validate_commit_ref(snapshot.source_commit_ref)
    if not commit_check.get("valid"):
        failures.append(
            f"source_commit_ref {snapshot.source_commit_ref!r} rejected: "
            f"{commit_check.get('reason', 'invalid')} "
            f"(kind={commit_check.get('kind', 'unknown')})"
        )
    runtime_check = CommitRuntimeProvider._validate_runtime_identity(
        snapshot.runtime_identity
    )
    if not runtime_check.get("valid"):
        failures.append(
            f"runtime_identity {snapshot.runtime_identity!r} rejected: "
            f"{runtime_check.get('reason', 'invalid')} "
            f"(kind={runtime_check.get('kind', 'unknown')})"
        )
    return (not failures), tuple(failures)


def _resolve_acceptance_suite_config(
    state: dict[str, Any],
    plan_dir: Path,
    suite_config: dict[str, Any] | None,
    *,
    require_full_boundary: bool = False,
) -> dict[str, Any]:
    """Resolve the suite config, mirroring ``GreenSuiteProvider``.

    Caller-supplied ``suite_config`` wins; otherwise the config is read from
    ``state['config']`` and the test command is resolved from
    ``finalize.json`` (baseline command, then test-selection override).

    When *require_full_boundary* is ``True`` (T14), the test-selection
    ``command_override`` is ignored — only the ``baseline_test_command`` is
    used.  This ensures that focused/scoped selector success cannot satisfy
    acceptance after a repair; the full boundary runner is always required.
    """
    if suite_config is not None:
        config = dict(suite_config)
        # T14: when full boundary is required and the caller-supplied
        # suite_config already has a test_command, still prefer the
        # baseline_test_command from finalize.json to prevent focused
        # selector success from masquerading as acceptance.
        if require_full_boundary:
            finalize = _read_json_file(plan_dir / "finalize.json")
            if isinstance(finalize, dict):
                baseline = finalize.get("baseline_test_command")
                if isinstance(baseline, str) and baseline.strip():
                    config["test_command"] = baseline.strip()
    else:
        raw = state.get("config", {}) if isinstance(state, dict) else {}
        config = dict(raw) if isinstance(raw, dict) else {}
    config["plan_dir"] = str(plan_dir)
    if not config.get("test_command"):
        finalize = _read_json_file(plan_dir / "finalize.json")
        if isinstance(finalize, dict):
            baseline_command = finalize.get("baseline_test_command")
            test_selection = finalize.get("test_selection")
            selected = (
                test_selection.get("command_override")
                if isinstance(test_selection, dict)
                else None
            )
            # T14: when full boundary is required, skip the test-selection
            # command_override (which may be a focused/scoped selector) and
            # use only the baseline_test_command.
            candidates = [baseline_command]
            if not require_full_boundary:
                candidates.append(selected)
            for candidate in candidates:
                if isinstance(candidate, str) and candidate.strip():
                    config["test_command"] = candidate.strip()
                    break
    return config


def _execute_declared_suite(
    *,
    project_dir: Path,
    plan_dir: Path,
    state: dict[str, Any],
    suite_config: dict[str, Any] | None,
    deadline_seconds: float | None,
    idle_seconds: float | None,
    suite_runner: Any,
    record_suite_run: bool,
    require_full_boundary: bool = False,
) -> tuple[Any | None, dict[str, Any]]:
    """Run the declared suite once and gather raw execution evidence.

    Returns ``(suite_run_result_or_None, evidence_dict)``.  When no test
    command is configured the suite is treated as not-applicable (vacuously
    passed) and no subprocess is spawned.

    When *require_full_boundary* is ``True`` (T14), only the
    ``baseline_test_command`` is used — the test-selection
    ``command_override`` (which may be a focused/scoped selector) is
    ignored so that focused selector success cannot satisfy acceptance.
    """
    config = _resolve_acceptance_suite_config(
        state, plan_dir, suite_config,
        require_full_boundary=require_full_boundary,
    )
    command = config.get("test_command")
    no_command = not (isinstance(command, str) and command.strip())

    not_applicable: dict[str, Any] = {
        "commands": [],
        "exit_codes": [],
        "log_paths": [],
        "log_digests": [],
        "artifact_digests": {},
        "suite_identity": None,
        "commit_tree": None,
        "suite_status": "not_applicable" if no_command else None,
        "suite_passed": True,
    }
    if no_command:
        return None, not_applicable

    # Resolve timeouts (mirror GreenSuiteProvider defaults).
    timeout = config.get("test_baseline_timeout", 900)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        timeout = 900
    if deadline_seconds is None:
        deadline_seconds = time.monotonic() + float(timeout)
    if idle_seconds is None:
        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            _resolve_test_idle_timeout,
        )

        idle_seconds = _resolve_test_idle_timeout(config)

    runner = suite_runner
    if runner is None:
        from arnold_pipelines.megaplan.orchestration.suite_runner import run_suite

        runner = run_suite

    result = runner(
        project_dir,
        config,
        phase="verification",
        deadline_seconds=deadline_seconds,
        idle_seconds=idle_seconds,
    )

    # Append to the suite-run log so downstream providers can freshness-skip a
    # re-run of the same code hash.  Best-effort: never let evidence logging
    # block or break the boundary.
    if record_suite_run and result is not None:
        try:
            from arnold_pipelines.megaplan.orchestration.suite_runs_log import (
                append_suite_run,
            )

            append_suite_run(plan_dir, result)
        except Exception:
            pass

    command_str = getattr(result, "command", "") or ""
    raw_log_path = getattr(result, "raw_log_path", None)
    log_path_str = str(raw_log_path) if raw_log_path else ""
    exit_code = getattr(result, "exit_code", None)
    run_id = getattr(result, "run_id", None)
    code_hash = getattr(result, "code_hash", None)
    status = getattr(result, "status", None)

    log_digest = _compute_file_digest(raw_log_path) if raw_log_path else None

    artifact_digests: dict[str, str] = {}
    if log_path_str and log_digest:
        artifact_digests[log_path_str] = log_digest

    suite_passed = status in {"passed", "not_applicable"} if status is not None else False

    evidence: dict[str, Any] = {
        "commands": [command_str] if command_str else [],
        "exit_codes": [exit_code],
        "log_paths": [log_path_str] if log_path_str else [],
        "log_digests": [log_digest] if log_digest is not None else [],
        "artifact_digests": artifact_digests,
        "suite_identity": run_id,
        "commit_tree": code_hash,
        "suite_status": status,
        "suite_passed": suite_passed,
    }
    return result, evidence


def _compute_boundary_verdict(
    *,
    snapshot: AcceptanceSnapshot,
    plan_dir: Path,
    project_dir: Path,
    state: Any,
    mode: str,
    providers: Any,
    git_base_ref: str | None,
    subject: Any,
) -> Any:
    """Call :func:`compute_verdict` with the predicate providers."""
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        CompletionSubject,
        compute_verdict,
    )

    if subject is None:
        subject = CompletionSubject(
            kind="milestone",
            name=snapshot.milestone_label,
            to_state="done",
            plan_name=snapshot.plan_name,
            milestone_label=snapshot.milestone_label,
        )

    chain_state = state if isinstance(state, dict) else {}
    kwargs: dict[str, Any] = dict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=chain_state,
        subject=subject,
        mode=mode,
        git_base_ref=git_base_ref,
    )
    if providers is not None:
        kwargs["providers"] = providers
    return compute_verdict(**kwargs)


def run_acceptance_boundary(
    snapshot: AcceptanceSnapshot,
    *,
    project_dir: Path,
    plan_dir: Path,
    state: dict[str, Any] | None = None,
    suite_config: dict[str, Any] | None = None,
    mode: str = "atomic",
    providers: Any = None,
    verdict: Any = None,
    deadline_seconds: float | None = None,
    idle_seconds: float | None = None,
    git_base_ref: str | None = None,
    subject: Any = None,
    suite_runner: Any = None,
    record_suite_run: bool = True,
    invalidate_prior_candidates: bool = True,
    prior_candidates: dict[str, Any] | None = None,
    require_full_boundary: bool = False,
) -> AcceptanceBoundaryResult:
    """Run the acceptance boundary for ``snapshot`` without committing state.

    Strict fail-closed validation order:

    0. **(T10) Invalidate stale prior candidates.**  Before any validation,
       check for uncommitted candidate transactions in *plan_dir* whose
       snapshot hash differs from *snapshot.content_hash*.  Any prior
       candidate with different evidence is invalidated; those invalidations
       are recorded in the result and the caller should propagate them to
       ``ChainState.candidate_invalidation``.  This ensures that repaired work
       never reuses a previously failed candidate snapshot — a newly built
       snapshot PLUS a full fresh boundary run is always required.
    1. **Validate source/runtime identity.**  If identity is unbound (short
       SHA, mutable alias, shadow placeholder, ...), the runner
       short-circuits: the suite is not run and no providers are invoked.
       ``accepted`` is ``False`` and the reason is in ``identity_failures``.
    2. **Run the declared suite**, collecting raw commands, log paths +
       digests, exit codes, timestamps, suite identity (run_id), commit/tree
       identity (code_hash), and artifact digests.  When
       *require_full_boundary* is ``True`` (T14), only the
       ``baseline_test_command`` is used — the test-selection
       ``command_override`` (focused/scoped selector) is ignored so that
       focused selector success cannot satisfy acceptance.
    3. **Call the predicate providers** via :func:`compute_verdict` (unless a
       pre-computed ``verdict`` is supplied) to obtain the structured
       completion verdict.
    4. ``accepted = identity_valid AND suite_passed AND verdict.accepted``.

    No chain state is committed.  Suite-run evidence may be appended to the
    append-only suite-run log (evidence collection, not chain authority) so
    downstream providers freshness-skip a duplicate run; disable with
    ``record_suite_run=False``.

    Parameters
    ----------
    snapshot
        The immutable acceptance snapshot to validate.
    project_dir
        Repository working tree the suite executes against.
    plan_dir
        Megaplan storage area (finalize.json, verification logs).
    state
        Chain state dict (read-only from the runner's perspective).
    suite_config
        Optional explicit suite config; otherwise resolved from
        ``state['config']`` / ``finalize.json``.
    mode
        Completion contract mode (``"atomic"``/``"enforce"`` fail closed;
        ``"shadow"``/``"warn"``/``"off"`` fail open).
    providers
        Optional tuple of :class:`EvidenceProvider`; defaults to
        ``DEFAULT_PROVIDERS`` inside :func:`compute_verdict`.
    verdict
        Optional pre-computed :class:`CompletionVerdict`.  When supplied, the
        providers are not invoked (testing/override path).
    deadline_seconds, idle_seconds
        Suite timeout controls; default to the resolved config values.
    git_base_ref
        Optional base ref for diff evidence.
    subject
        Optional :class:`CompletionSubject`; built from the snapshot if absent.
    suite_runner
        Optional callable replacing the real :func:`run_suite` (testing).  It
        must accept ``(project_dir, config, *, phase, deadline_seconds,
        idle_seconds)``.
    record_suite_run
        When ``True`` (default) the suite run is appended to the suite-run log
        so downstream providers freshness-skip a duplicate run.
    invalidate_prior_candidates
        When ``True`` (default), checks for and invalidates prior uncommitted
        candidates whose evidence differs from *snapshot*.  Set to ``False``
        only for test or bootstrap paths where no prior candidates exist.
    prior_candidates
        Optional pre-fetched dict of uncommitted candidates.  When ``None`` and
        *invalidate_prior_candidates* is ``True``, candidates are loaded from
        *plan_dir*.
    require_full_boundary
        When ``True`` (T14), the acceptance boundary must use the full
        ``baseline_test_command`` — focused/scoped test-selection overrides
        are ignored.  This ensures that after a repair, focused selector
        success cannot satisfy acceptance.  Default ``False``.
    """
    started_at = _now_iso()
    t0 = time.monotonic()

    # Step 0 (T10) — invalidate stale prior candidates so repaired work never
    # reuses a previously failed candidate snapshot.
    invalidated_candidates: tuple[CandidateInvalidation, ...] = ()
    if invalidate_prior_candidates:
        invalidated_candidates = check_and_invalidate_stale_candidates(
            snapshot,
            plan_dir=plan_dir,
            prior_candidates=prior_candidates,
        )

    # Step 1 — validate identity FIRST (fail-closed: never run tests against
    # an unbound commit, never grant authority to unbound evidence).
    identity_valid, identity_failures = _validate_acceptance_identity(snapshot)

    commands: list[str] = []
    exit_codes: list[int | None] = []
    log_paths: list[str] = []
    log_digests: list[str | None] = []
    artifact_digests: dict[str, str] = {}
    suite_run: Any | None = None
    suite_identity: str | None = None
    commit_tree: str | None = None
    suite_status: str | None = None
    suite_passed = True
    verdict_obj: Any | None = None
    failure_reasons: list[str] = list(identity_failures)

    if identity_valid:
        # Step 2 — run the declared suite and gather raw execution evidence.
        suite_run, evidence = _execute_declared_suite(
            project_dir=project_dir,
            plan_dir=plan_dir,
            state=state if isinstance(state, dict) else {},
            suite_config=suite_config,
            deadline_seconds=deadline_seconds,
            idle_seconds=idle_seconds,
            suite_runner=suite_runner,
            record_suite_run=record_suite_run,
            require_full_boundary=require_full_boundary,
        )
        commands = evidence["commands"]
        exit_codes = evidence["exit_codes"]
        log_paths = evidence["log_paths"]
        log_digests = evidence["log_digests"]
        artifact_digests = evidence["artifact_digests"]
        suite_identity = evidence["suite_identity"]
        commit_tree = evidence["commit_tree"]
        suite_status = evidence["suite_status"]
        suite_passed = evidence["suite_passed"]
        if not suite_passed:
            failure_reasons.append(
                f"acceptance suite did not pass (status={suite_status})"
            )

        # Step 3 — call the predicate providers.
        if verdict is not None:
            verdict_obj = verdict
        else:
            verdict_obj = _compute_boundary_verdict(
                snapshot=snapshot,
                plan_dir=plan_dir,
                project_dir=project_dir,
                state=state,
                mode=mode,
                providers=providers,
                git_base_ref=git_base_ref,
                subject=subject,
            )
        if verdict_obj is not None and not getattr(verdict_obj, "accepted", False):
            for reason in getattr(verdict_obj, "failures", ()):
                failure_reasons.append(str(reason))

    accepted = (
        identity_valid
        and suite_passed
        and (verdict_obj is not None and getattr(verdict_obj, "accepted", False))
    )

    completed_at = _now_iso()
    duration_seconds = time.monotonic() - t0

    return AcceptanceBoundaryResult(
        snapshot=snapshot,
        identity_valid=identity_valid,
        identity_failures=identity_failures,
        suite_run=suite_run,
        verdict=verdict_obj,
        commands=tuple(commands),
        exit_codes=tuple(exit_codes),
        log_paths=tuple(log_paths),
        log_digests=tuple(log_digests),
        started_at=started_at,
        completed_at=completed_at,
        suite_identity=suite_identity,
        commit_tree=commit_tree,
        artifact_digests=dict(artifact_digests),
        suite_status=suite_status,
        accepted=accepted,
        duration_seconds=duration_seconds,
        failure_reasons=tuple(failure_reasons),
        mode=mode,
        invalidated_candidates=invalidated_candidates,
    )


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "ACCEPTANCE_BOUNDARY_RESULT_SCHEMA",
    "ACCEPTANCE_BOUNDARY_RESULT_SCHEMA_VERSION",
    "ACCEPTANCE_RECEIPT_SCHEMA",
    "ACCEPTANCE_RECEIPT_SCHEMA_VERSION",
    "ACCEPTANCE_SNAPSHOT_SCHEMA",
    "ACCEPTANCE_SNAPSHOT_SCHEMA_VERSION",
    "ACCEPTANCE_TRANSACTION_SCHEMA",
    "ACCEPTANCE_TRANSACTION_SCHEMA_VERSION",
    "AcceptanceBoundaryResult",
    "AcceptanceReceipt",
    "AcceptanceSnapshot",
    "AcceptanceTransaction",
    "CandidateInvalidation",
    "check_and_invalidate_stale_candidates",
    "run_acceptance_boundary",
]
