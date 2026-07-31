"""Signed, content-addressed repair receipt — evidence-only, not authority.

Each receipt captures the full context of a single repair attempt:
- current Run Authority grant identity
- plan revision
- phase/task contract
- subject attempt reference
- WBC attempt reference
- tree/commit snapshot
- test results
- blocker hash
- coordinator fence token
- custody lease identity and epoch

Receipts are content-addressed (SHA-256 over canonical JSON) so that
review/rework cycles that produce byte-identical attempt evidence are
identified as the same receipt — no second lease is created.

Principles
----------
* **Content-addressed** — The receipt digest is a deterministic SHA-256
  hash over every field.  Two receipts with identical evidence produce
  the same digest, regardless of when or by whom they were generated.
* **Byte-identical review/rework** — If a review or rework cycle reproduces
  the exact same attempt evidence, the receipt is idempotent; it does not
  create a second lease.
* **Not authority** — Receipts are terminal proof artefacts.  They do not
  authorize any mutation, grant, or lease.  Authority decisions must
  be made by :mod:`arnold_pipelines.megaplan.custody.action_validator`
  and persisted through :mod:`arnold_pipelines.megaplan.custody.lease_store`.
* **Immutable** — Once created, a receipt is frozen.  Updates go through
  a new receipt with a causal predecessor reference.

All production gates and mutating effects remain disabled in M7;
this module runs in shadow/report-only mode.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Optional

from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyTargetKey,
    RepairOccurrenceKey,
    normalize_custody_lease,
    normalize_custody_target_key,
    normalize_repair_occurrence_key,
)
from arnold_pipelines.run_authority.contracts import (
    Contract,
    ContractError,
    canonical_json,
    payload_digest,
)

# ── Schema version constant ────────────────────────────────────────────────
REPAIR_RECEIPT_SCHEMA_VERSION = 1


# ── Receipt status enum ─────────────────────────────────────────────────────

class RepairReceiptStatus(StrEnum):
    """Lifecycle status of a repair receipt."""

    ATTEMPT = "attempt"
    """An attempt was made — the receipt captures what was observed."""

    REVIEW = "review"
    """The attempt is under review; evidence is unchanged."""

    REWORK = "rework"
    """Rework was triggered; the predecessor receipt is preserved."""

    ACCEPTED = "accepted"
    """The repair attempt evidence was accepted."""

    REJECTED = "rejected"
    """The repair attempt evidence was rejected."""

    SUPERSEDED = "superseded"
    """A later receipt supersedes this one (e.g., after rework)."""


# ── Repair receipt ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepairReceipt(Contract):
    """Signed, content-addressed repair attempt receipt.

    Every receipt captures the full context of a single repair attempt
    and is referenced by its deterministic content digest.  Review and
    rework cycles that reproduce byte-identical evidence produce the
    same digest — the receipt store detects the idempotent match and
    does not create a duplicate lease.

    Fields
    ------
    receipt_id
        Unique receipt identifier (UUID v4).
    receipt_digest
        Deterministic SHA-256 digest over all evidence fields.
        Computed during ``__post_init__``.
    status
        Receipt lifecycle status (:class:`RepairReceiptStatus`).
    target
        The :class:`CustodyTargetKey` identifying the repair target.
    occurrence_key
        The :class:`RepairOccurrenceKey` identifying this occurrence.
    run_authority_grant_id
        The Run Authority grant that authorizes the repair.
    plan_revision
        The plan revision active during this attempt.
    phase
        The phase being repaired.
    task_contract
        The task contract identifier.
    subject_attempt
        The subject attempt reference (which attempt this receipt
        describes).
    wbc_attempt_reference
        The WBC attempt reference (may be empty if WBC is not yet
        operational).
    tree_commit
        The git tree/commit SHA observed during the attempt.
    test_results
        Free-form test results payload (immutable after creation).
    blocker_hash
        The blocker fingerprint hash at the time of the attempt.
    coordinator_fence_token
        The coordinator fence token at acquisition.
    custody_lease_id
        The custody lease identifier under which this attempt ran.
    custody_epoch
        The custody epoch during this attempt.
    causal_predecessor
        Receipt ID of the predecessor receipt (empty for initial attempt).
        Set during rework/review cycles to preserve the chain.
    occurred_at
        ISO-8601 timestamp when the attempt was recorded.
    recorded_by
        Identity of the recording process (host, pid, boot_id).
    """

    contract_type: ClassVar[str] = "repair_receipt"
    schema_version: ClassVar[int] = REPAIR_RECEIPT_SCHEMA_VERSION

    receipt_id: str
    status: RepairReceiptStatus
    target: CustodyTargetKey
    occurrence_key: RepairOccurrenceKey
    run_authority_grant_id: str
    plan_revision: str
    phase: str
    task_contract: str
    subject_attempt: str
    wbc_attempt_reference: str
    tree_commit: str
    test_results: Mapping[str, Any] = field(default_factory=dict)
    blocker_hash: str = ""
    coordinator_fence_token: int = 0
    custody_lease_id: str = ""
    custody_epoch: int = 0
    causal_predecessor: str = ""
    occurred_at: str = ""
    recorded_by: Mapping[str, str] = field(default_factory=dict)
    payload_hash: str = field(init=False)
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        """Validate required fields and compute deterministic digest."""
        # Validate required string fields
        _required_str(self.receipt_id, "receipt_id")
        if self.status not in _RECEIPT_STATUSES:
            raise ContractError(f"unknown status {self.status!r}")
        _required_str(self.run_authority_grant_id, "run_authority_grant_id")
        _required_str(self.plan_revision, "plan_revision")
        _required_str(self.phase, "phase")
        _required_str(self.task_contract, "task_contract")
        _required_str(self.subject_attempt, "subject_attempt")
        if not isinstance(self.wbc_attempt_reference, str):
            raise ContractError("wbc_attempt_reference must be a string")
        _required_str(self.tree_commit, "tree_commit")
        if not isinstance(self.blocker_hash, str):
            raise ContractError("blocker_hash must be a string")
        if not isinstance(self.coordinator_fence_token, int) or isinstance(self.coordinator_fence_token, bool):
            raise ContractError("coordinator_fence_token must be an integer")
        if self.coordinator_fence_token < 0:
            raise ContractError("coordinator_fence_token must be non-negative")
        _required_str(self.custody_lease_id, "custody_lease_id")
        if not isinstance(self.custody_epoch, int) or isinstance(self.custody_epoch, bool):
            raise ContractError("custody_epoch must be an integer")
        if self.custody_epoch < 1:
            raise ContractError("custody_epoch must be positive")
        if not isinstance(self.causal_predecessor, str):
            raise ContractError("causal_predecessor must be a string")
        _required_str(self.occurred_at, "occurred_at")
        # Validate ISO-8601 timestamp
        try:
            datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ContractError(f"invalid ISO-8601 occurred_at: {exc}") from exc

        # Freeze and hash test_results payload
        frozen_payload = _freeze_json_sorted(self.test_results)
        if not isinstance(frozen_payload, Mapping):
            raise ContractError("test_results must be an object")
        object.__setattr__(self, "test_results", frozen_payload)

        # Freeze recorded_by
        frozen_recorded = _freeze_json_sorted(self.recorded_by)
        if not isinstance(frozen_recorded, Mapping):
            raise ContractError("recorded_by must be an object")
        object.__setattr__(self, "recorded_by", frozen_recorded)

        # Compute payload_hash over the test_results
        object.__setattr__(self, "payload_hash", payload_digest(frozen_payload))

        # Compute receipt_digest — the deterministic content address
        object.__setattr__(self, "receipt_digest", compute_receipt_digest(self))

    def to_dict(self) -> dict[str, Any]:
        """Return a canonical serializable dict."""
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "receipt_digest": self.receipt_digest,
            "status": str(self.status),
            "target": self.target.to_dict(),
            "occurrence_key": self.occurrence_key.to_dict(),
            "run_authority_grant_id": self.run_authority_grant_id,
            "plan_revision": self.plan_revision,
            "phase": self.phase,
            "task_contract": self.task_contract,
            "subject_attempt": self.subject_attempt,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "tree_commit": self.tree_commit,
            "test_results": _thaw_sorted(self.test_results),
            "blocker_hash": self.blocker_hash,
            "coordinator_fence_token": self.coordinator_fence_token,
            "custody_lease_id": self.custody_lease_id,
            "custody_epoch": self.custody_epoch,
            "causal_predecessor": self.causal_predecessor,
            "occurred_at": self.occurred_at,
            "recorded_by": _thaw_sorted(self.recorded_by),
            "payload_hash": self.payload_hash,
        }

    @property
    def evidence_tuple(self) -> tuple:
        """Return the evidence fields as a content-addressable tuple.

        This tuple captures every field that contributes to the receipt
        digest.  Two receipts with identical evidence tuples have the
        same ``receipt_digest``.
        """
        return (
            self.run_authority_grant_id,
            self.plan_revision,
            self.phase,
            self.task_contract,
            self.subject_attempt,
            self.wbc_attempt_reference,
            self.tree_commit,
            # test_results is captured via payload_hash
            self.payload_hash,
            self.blocker_hash,
            self.coordinator_fence_token,
            self.custody_lease_id,
            self.custody_epoch,
            self.target.target_digest,
            self.occurrence_key.occurrence_digest,
        )

    def is_evidence_identical(self, other: RepairReceipt) -> bool:
        """Return True if two receipts have byte-identical attempt evidence.

        This is the idempotency check for review/rework cycles:
        if the evidence is identical, no new lease is needed.
        """
        if not isinstance(other, RepairReceipt):
            return False
        return self.receipt_digest == other.receipt_digest

    def with_status(self, new_status: RepairReceiptStatus) -> RepairReceipt:
        """Return a new receipt with updated status, preserving all evidence.

        The receipt ID and occurred_at are updated; all evidence fields
        are byte-identical.  This is used for review/rework transitions
        that do not change attempt evidence.
        """
        return RepairReceipt(
            receipt_id=_new_receipt_id(),
            status=new_status,
            target=self.target,
            occurrence_key=self.occurrence_key,
            run_authority_grant_id=self.run_authority_grant_id,
            plan_revision=self.plan_revision,
            phase=self.phase,
            task_contract=self.task_contract,
            subject_attempt=self.subject_attempt,
            wbc_attempt_reference=self.wbc_attempt_reference,
            tree_commit=self.tree_commit,
            test_results=_thaw_sorted(self.test_results),
            blocker_hash=self.blocker_hash,
            coordinator_fence_token=self.coordinator_fence_token,
            custody_lease_id=self.custody_lease_id,
            custody_epoch=self.custody_epoch,
            causal_predecessor=self.receipt_id,
            occurred_at=_utc_now_iso(),
            recorded_by=_thaw_sorted(self.recorded_by),
        )


# ── Internal helpers ────────────────────────────────────────────────────────

_RECEIPT_STATUSES: frozenset[RepairReceiptStatus] = frozenset(
    {
        RepairReceiptStatus.ATTEMPT,
        RepairReceiptStatus.REVIEW,
        RepairReceiptStatus.REWORK,
        RepairReceiptStatus.ACCEPTED,
        RepairReceiptStatus.REJECTED,
        RepairReceiptStatus.SUPERSEDED,
    }
)


def _required_str(value: str, name: str) -> str:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _new_receipt_id() -> str:
    """Generate a new UUID v4 receipt identifier."""
    return str(uuid.uuid4())


# ── JSON freezing (mirrors contracts module patterns) ──────────────────────


def _freeze_json_sorted(value: Any, path: str = "payload") -> Any:
    """Freeze a JSON-compatible value, sorting dict keys deterministically."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        import math

        if not math.isfinite(value):
            raise ContractError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ContractError(f"{path} keys must be strings")
            frozen[key] = _freeze_json_sorted(value[key], f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_sorted(item, f"{path}[]") for item in value)
    raise ContractError(f"{path} contains unsupported value {type(value).__name__}")


def _thaw_sorted(value: Any) -> Any:
    """Convert frozen values to plain Python with deterministic key ordering."""
    if isinstance(value, Mapping):
        return {key: _thaw_sorted(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_thaw_sorted(item) for item in value]
    return value


# ── Digest computation ──────────────────────────────────────────────────────


def compute_receipt_digest(receipt: RepairReceipt) -> str:
    """Compute the deterministic SHA-256 content address of a receipt.

    The digest covers every evidence field.  Two receipts with identical
    attempt evidence produce the same digest — this is the idempotency
    mechanism that prevents duplicate leases during review/rework cycles.
    """
    # Build the canonical evidence payload in sorted-key order
    evidence: dict[str, Any] = {
        "run_authority_grant_id": receipt.run_authority_grant_id,
        "plan_revision": receipt.plan_revision,
        "phase": receipt.phase,
        "task_contract": receipt.task_contract,
        "subject_attempt": receipt.subject_attempt,
        "wbc_attempt_reference": receipt.wbc_attempt_reference,
        "tree_commit": receipt.tree_commit,
        "test_results": _thaw_sorted(receipt.test_results),
        "blocker_hash": receipt.blocker_hash,
        "coordinator_fence_token": receipt.coordinator_fence_token,
        "custody_lease_id": receipt.custody_lease_id,
        "custody_epoch": receipt.custody_epoch,
        "target_digest": receipt.target.target_digest,
        "occurrence_digest": receipt.occurrence_key.key,
    }
    plain = json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(plain.encode("utf-8")).hexdigest()


# ── Builder ─────────────────────────────────────────────────────────────────


def build_repair_receipt(
    *,
    target: CustodyTargetKey,
    occurrence_key: RepairOccurrenceKey,
    run_authority_grant_id: str,
    plan_revision: str,
    phase: str,
    task_contract: str,
    subject_attempt: str,
    wbc_attempt_reference: str = "",
    tree_commit: str,
    test_results: Mapping[str, Any] | None = None,
    blocker_hash: str = "",
    coordinator_fence_token: int = 0,
    custody_lease_id: str = "",
    custody_epoch: int = 0,
    causal_predecessor: str = "",
    status: RepairReceiptStatus = RepairReceiptStatus.ATTEMPT,
    recorded_by: Mapping[str, str] | None = None,
) -> RepairReceipt | None:
    """Build a repair receipt from keyword arguments.

    Returns ``None`` if any required field is missing or invalid.
    """
    try:
        return RepairReceipt(
            receipt_id=_new_receipt_id(),
            status=status,
            target=target,
            occurrence_key=occurrence_key,
            run_authority_grant_id=run_authority_grant_id,
            plan_revision=plan_revision,
            phase=phase,
            task_contract=task_contract,
            subject_attempt=subject_attempt,
            wbc_attempt_reference=wbc_attempt_reference,
            tree_commit=tree_commit,
            test_results=test_results or {},
            blocker_hash=blocker_hash,
            coordinator_fence_token=coordinator_fence_token,
            custody_lease_id=custody_lease_id,
            custody_epoch=custody_epoch,
            causal_predecessor=causal_predecessor,
            occurred_at=_utc_now_iso(),
            recorded_by=recorded_by or {},
        )
    except (ContractError, TypeError):
        return None


# ── Normalizer ──────────────────────────────────────────────────────────────


def normalize_repair_receipt(
    payload: Mapping[str, Any] | None,
) -> RepairReceipt | None:
    """Return a canonical RepairReceipt or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None

    target_raw = payload.get("target")
    target = normalize_custody_target_key(target_raw)
    if target is None:
        return None

    occurrence_raw = payload.get("occurrence_key")
    occurrence_key = normalize_repair_occurrence_key(occurrence_raw)
    if occurrence_key is None:
        return None

    try:
        status_raw = payload.get("status", "attempt")
        status = RepairReceiptStatus(status_raw) if status_raw in _RECEIPT_STATUSES else None
        if status is None:
            return None

        return RepairReceipt(
            receipt_id=payload.get("receipt_id", ""),
            status=status,
            target=target,
            occurrence_key=occurrence_key,
            run_authority_grant_id=payload.get("run_authority_grant_id", ""),
            plan_revision=payload.get("plan_revision", ""),
            phase=payload.get("phase", ""),
            task_contract=payload.get("task_contract", ""),
            subject_attempt=payload.get("subject_attempt", ""),
            wbc_attempt_reference=payload.get("wbc_attempt_reference", ""),
            tree_commit=payload.get("tree_commit", ""),
            test_results=payload.get("test_results") or {},
            blocker_hash=payload.get("blocker_hash", ""),
            coordinator_fence_token=payload.get("coordinator_fence_token", 0),
            custody_lease_id=payload.get("custody_lease_id", ""),
            custody_epoch=payload.get("custody_epoch", 0),
            causal_predecessor=payload.get("causal_predecessor", ""),
            occurred_at=payload.get("occurred_at", ""),
            recorded_by=payload.get("recorded_by") or {},
        )
    except (ContractError, TypeError):
        return None


# ── Review/rework helpers ───────────────────────────────────────────────────


def review_receipt(
    receipt: RepairReceipt,
    *,
    accepted: bool,
) -> RepairReceipt:
    """Transition a receipt through review without altering attempt evidence.

    The returned receipt has a new ``receipt_id`` and updated ``occurred_at``,
    but all evidence fields are byte-identical to the original.  The
    ``causal_predecessor`` is set to the original receipt ID.

    No second lease is created — the evidence digest is identical and the
    lease store's idempotency check will detect this.
    """
    new_status = RepairReceiptStatus.ACCEPTED if accepted else RepairReceiptStatus.REJECTED
    return receipt.with_status(new_status)


def rework_receipt(
    receipt: RepairReceipt,
    *,
    new_tree_commit: str = "",
    new_test_results: Mapping[str, Any] | None = None,
    new_blocker_hash: str = "",
) -> RepairReceipt:
    """Create a rework receipt with updated evidence.

    The returned receipt has a new ``receipt_id`` and references the
    original as ``causal_predecessor``.  All other evidence fields are
    carried forward from the predecessor.

    If the rework produces evidence that is byte-identical to the
    predecessor (e.g., the tree commit, test results, and blocker
    hash are unchanged), the new receipt will have the same
    ``receipt_digest`` — the store should treat this as idempotent
    and not create a new lease.
    """
    return RepairReceipt(
        receipt_id=_new_receipt_id(),
        status=RepairReceiptStatus.REWORK,
        target=receipt.target,
        occurrence_key=receipt.occurrence_key,
        run_authority_grant_id=receipt.run_authority_grant_id,
        plan_revision=receipt.plan_revision,
        phase=receipt.phase,
        task_contract=receipt.task_contract,
        subject_attempt=receipt.subject_attempt,
        wbc_attempt_reference=receipt.wbc_attempt_reference,
        tree_commit=new_tree_commit or receipt.tree_commit,
        test_results=new_test_results or _thaw_sorted(receipt.test_results),
        blocker_hash=new_blocker_hash or receipt.blocker_hash,
        coordinator_fence_token=receipt.coordinator_fence_token,
        custody_lease_id=receipt.custody_lease_id,
        custody_epoch=receipt.custody_epoch,
        causal_predecessor=receipt.receipt_id,
        occurred_at=_utc_now_iso(),
        recorded_by=_thaw_sorted(receipt.recorded_by),
    )


def supersede_receipt(receipt: RepairReceipt) -> RepairReceipt:
    """Mark a receipt as superseded by a later one.

    This is a terminal status — the receipt evidence is preserved
    but the receipt is no longer the active one for the occurrence.
    """
    return receipt.with_status(RepairReceiptStatus.SUPERSEDED)


def is_same_attempt_evidence(a: RepairReceipt, b: RepairReceipt) -> bool:
    """Return True if two receipts carry byte-identical attempt evidence.

    This is the primary guard against duplicate leases during review/rework
    cycles.  If the evidence has not changed, the receipt digest is identical,
    and no new lease acquisition should be triggered.
    """
    return a.receipt_digest == b.receipt_digest


# ── Public API ──────────────────────────────────────────────────────────────

__all__ = [
    "RepairReceipt",
    "RepairReceiptStatus",
    "REPAIR_RECEIPT_SCHEMA_VERSION",
    "build_repair_receipt",
    "normalize_repair_receipt",
    "compute_receipt_digest",
    "review_receipt",
    "rework_receipt",
    "supersede_receipt",
    "is_same_attempt_evidence",
]
