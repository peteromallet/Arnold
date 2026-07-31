"""Verify-only repair adoption decision — evidence-only, not authority.

Provides a pure decision function that compares an M7 :class:`RepairReceipt`
against the *current* Run Authority grant/fence, current Custody lease/epoch,
revision, task contract, tree/commit, tests/result hash, required WBC
attempt/evidence reference, and coordinator fence.

Principles
----------
* **Verify-only** — The function compares receipt fields to current context.
  It does NOT authorize any mutation, grant, lease, or status change.
  The receipt is evidence; the decision output is a recommendation.
* **Exact match** — Every compared field must match exactly.  A single
  mismatch quarantines the receipt and recommends normal execution.
* **Pure** — The function takes all context as arguments.  It does NOT
  reach into any store, outbox, or environment variable.  Callers are
  responsible for rereading current boundary conditions before calling.
* **North Star** — A receipt is not a grant.  The adoption decision is a
  deterministic comparison; it never substitutes for an authoritative
  action-boundary validation.

All production gates and mutating effects remain disabled in M8A;
this module runs in shadow/report-only mode until canary promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar, Mapping, Optional

from arnold_pipelines.megaplan.custody.repair_receipt import (
    RepairReceipt,
    normalize_repair_receipt,
)

# ── Schema version constant ────────────────────────────────────────────────
REPAIR_ADOPTION_SCHEMA_VERSION = 1

# ── Adoption outcomes ──────────────────────────────────────────────────────


class AdoptionOutcome(StrEnum):
    """Outcome of a verify-only repair adoption decision."""

    ADOPT = "adopt"
    """Every compared field matches — the receipt evidence is current.
    The caller MAY skip replay and record verify-only adoption evidence."""

    QUARANTINE = "quarantine"
    """At least one compared field does not match — the receipt is
    evidence from a different context.  The caller MUST quarantine
    the receipt and continue normal execution WITHOUT rewriting
    immutable attempts."""

    INVALID = "invalid"
    """The receipt or context is malformed — the decision cannot
    be computed.  The caller MUST treat this as a quarantine and
    continue normal execution."""


# ── Field mismatch record ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AdoptionFieldMismatch:
    """Record of a single field mismatch in an adoption comparison."""

    field: str
    receipt_value: str
    current_value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "receipt_value": self.receipt_value,
            "current_value": self.current_value,
        }


# ── Adoption decision ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AdoptionDecision:
    """Result of a verify-only repair adoption comparison.

    Fields
    ------
    outcome
        The adoption outcome (:class:`AdoptionOutcome`).
    receipt_digest
        The content digest of the receipt that was compared.
    mismatches
        Tuple of :class:`AdoptionFieldMismatch` records for every
        field that did not match.  Empty when ``outcome`` is ``ADOPT``.
    compared_at
        ISO-8601 timestamp when the comparison was performed.
    diagnostics
        Additional human/machine-readable diagnostics.
    """

    outcome: AdoptionOutcome
    receipt_digest: str
    mismatches: tuple[AdoptionFieldMismatch, ...] = ()
    compared_at: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    contract_type: ClassVar[str] = "adoption_decision"
    schema_version: ClassVar[int] = REPAIR_ADOPTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, AdoptionOutcome):
            raise TypeError("outcome must be an AdoptionOutcome")
        if not isinstance(self.receipt_digest, str):
            raise ValueError("receipt_digest must be a string")
        # receipt_digest may be empty for INVALID outcomes where the
        # receipt could not be normalized — the digest does not exist.
        if not self.compared_at:
            object.__setattr__(
                self,
                "compared_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

    @property
    def is_adoptable(self) -> bool:
        """Return True when the receipt can be adopted (skip replay)."""
        return self.outcome == AdoptionOutcome.ADOPT

    @property
    def is_quarantined(self) -> bool:
        """Return True when the receipt must be quarantined."""
        return self.outcome in (AdoptionOutcome.QUARANTINE, AdoptionOutcome.INVALID)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "outcome": str(self.outcome),
            "receipt_digest": self.receipt_digest,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "compared_at": self.compared_at,
            "diagnostics": dict(self.diagnostics),
        }


# ── Context required for adoption comparison ───────────────────────────────


@dataclass(frozen=True)
class AdoptionContext:
    """Current context required for verify-only repair adoption.

    Every field represents a current boundary condition that must
    match the corresponding field in the repair receipt.  The caller
    MUST reread these values immediately before calling
    :func:`adopt_repair_receipt` — stale context can produce false
    adoptions or false quarantines.

    Fields
    ------
    run_authority_grant_id
        The current Run Authority grant ID.
    coordinator_fence_token
        The current coordinator fence token.
    custody_lease_id
        The current Custody lease identifier.
    custody_epoch
        The current Custody epoch.
    wbc_attempt_reference
        The current required WBC attempt reference (may be empty).
    plan_revision
        The current plan revision.
    task_contract
        The current task contract identifier.
    tree_commit
        The current git tree/commit SHA.
    test_result_hash
        The SHA-256 digest of the current test results (canonical JSON).
    blocker_hash
        The current blocker fingerprint hash (may be empty).
    """

    run_authority_grant_id: str
    coordinator_fence_token: int
    custody_lease_id: str
    custody_epoch: int
    wbc_attempt_reference: str
    plan_revision: str
    task_contract: str
    tree_commit: str
    test_result_hash: str
    blocker_hash: str = ""

    def __post_init__(self) -> None:
        _require_str(self.run_authority_grant_id, "run_authority_grant_id")
        _require_int(self.coordinator_fence_token, "coordinator_fence_token", 0)
        if not isinstance(self.custody_lease_id, str):
            raise ValueError("custody_lease_id must be a string")
        _require_int(self.custody_epoch, "custody_epoch", 1)
        if not isinstance(self.wbc_attempt_reference, str):
            raise ValueError("wbc_attempt_reference must be a string")
        _require_str(self.plan_revision, "plan_revision")
        _require_str(self.task_contract, "task_contract")
        _require_str(self.tree_commit, "tree_commit")
        _require_str(self.test_result_hash, "test_result_hash")
        if not isinstance(self.blocker_hash, str):
            raise ValueError("blocker_hash must be a string")


# ── Internal helpers ───────────────────────────────────────────────────────


def _require_str(value: str, name: str) -> None:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_int(value: int, name: str, minimum: int | None = None) -> None:
    """Validate a required integer field."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _compare_field(
    field: str,
    receipt_value: str,
    current_value: str,
    mismatches: list[AdoptionFieldMismatch],
) -> None:
    """Compare a single field and record a mismatch if they differ."""
    if receipt_value != current_value:
        mismatches.append(
            AdoptionFieldMismatch(
                field=field,
                receipt_value=str(receipt_value),
                current_value=str(current_value),
            )
        )


# ── Public API ─────────────────────────────────────────────────────────────


def adopt_repair_receipt(
    receipt: RepairReceipt | Mapping[str, Any] | None,
    context: AdoptionContext,
) -> AdoptionDecision:
    """Decide whether a repair receipt can be adopted (skip replay).

    Compares every evidence field in *receipt* against the *current*
    boundary conditions in *context*.  Returns an :class:`AdoptionDecision`
    with outcome ``ADOPT`` only when ALL compared fields match exactly.

    The compared fields are:

    * ``run_authority_grant_id`` — Run Authority grant identity
    * ``coordinator_fence_token`` — Coordinator fence token
    * ``custody_lease_id`` — Custody lease identifier
    * ``custody_epoch`` — Custody epoch
    * ``wbc_attempt_reference`` — Required WBC attempt reference
    * ``plan_revision`` — Plan revision
    * ``task_contract`` — Task contract identifier
    * ``tree_commit`` — Git tree/commit SHA
    * ``test_result_hash`` — SHA-256 digest of test results (compared
      against receipt's ``payload_hash``)
    * ``blocker_hash`` — Blocker fingerprint hash

    Parameters
    ----------
    receipt:
        The repair receipt to evaluate.  May be a :class:`RepairReceipt`
        instance, a dict payload, or ``None``.  Invalid/missing receipts
        produce ``INVALID`` outcomes.
    context:
        The current boundary conditions, freshly reread by the caller.

    Returns
    -------
    AdoptionDecision
        The adoption decision.  The caller:

        * On ``ADOPT``: MAY skip replay and emit adoption evidence plus
          a ``repair_verify`` work-class event.
        * On ``QUARANTINE``: MUST quarantine the receipt (store the
          mismatches as evidence) and continue normal execution WITHOUT
          rewriting immutable attempts.
        * On ``INVALID``: MUST treat identically to ``QUARANTINE``.

    Notes
    -----
    This function is **pure** — it performs comparisons only and does
    not reach into any store, outbox, or environment.  It is the
    caller's responsibility to reread current values from the Run
    Authority, Custody, and WBC sources immediately before calling.

    The receipt is evidence, NOT authority.  Even on ``ADOPT``, the
    caller SHOULD still pass through the action-boundary validator
    (:mod:`action_validator.validate_action_boundary`) before dispatch.
    """
    # ── Normalize the receipt ──────────────────────────────────────────
    if receipt is None:
        return AdoptionDecision(
            outcome=AdoptionOutcome.INVALID,
            receipt_digest="",
            diagnostics={
                "error": "receipt is None",
                "schema_version": REPAIR_ADOPTION_SCHEMA_VERSION,
            },
        )

    if isinstance(receipt, Mapping):
        normalized = normalize_repair_receipt(receipt)
        if normalized is None:
            return AdoptionDecision(
                outcome=AdoptionOutcome.INVALID,
                receipt_digest="",
                diagnostics={
                    "error": "receipt payload could not be normalized to RepairReceipt",
                    "schema_version": REPAIR_ADOPTION_SCHEMA_VERSION,
                },
            )
        receipt = normalized

    if not isinstance(receipt, RepairReceipt):
        return AdoptionDecision(
            outcome=AdoptionOutcome.INVALID,
            receipt_digest="",
            diagnostics={
                "error": f"receipt must be a RepairReceipt, got {type(receipt).__name__}",
                "schema_version": REPAIR_ADOPTION_SCHEMA_VERSION,
            },
        )

    # ── Compare every evidence field ───────────────────────────────────
    mismatches: list[AdoptionFieldMismatch] = []

    # Run Authority grant
    _compare_field(
        "run_authority_grant_id",
        receipt.run_authority_grant_id,
        context.run_authority_grant_id,
        mismatches,
    )

    # Coordinator fence token
    _compare_field(
        "coordinator_fence_token",
        str(receipt.coordinator_fence_token),
        str(context.coordinator_fence_token),
        mismatches,
    )

    # Custody lease
    _compare_field(
        "custody_lease_id",
        receipt.custody_lease_id,
        context.custody_lease_id,
        mismatches,
    )

    # Custody epoch
    _compare_field(
        "custody_epoch",
        str(receipt.custody_epoch),
        str(context.custody_epoch),
        mismatches,
    )

    # WBC attempt reference
    _compare_field(
        "wbc_attempt_reference",
        receipt.wbc_attempt_reference,
        context.wbc_attempt_reference,
        mismatches,
    )

    # Plan revision
    _compare_field(
        "plan_revision",
        receipt.plan_revision,
        context.plan_revision,
        mismatches,
    )

    # Task contract
    _compare_field(
        "task_contract",
        receipt.task_contract,
        context.task_contract,
        mismatches,
    )

    # Tree/commit
    _compare_field(
        "tree_commit",
        receipt.tree_commit,
        context.tree_commit,
        mismatches,
    )

    # Test result hash (receipt.payload_hash vs context.test_result_hash)
    _compare_field(
        "test_result_hash",
        receipt.payload_hash,
        context.test_result_hash,
        mismatches,
    )

    # Blocker hash
    _compare_field(
        "blocker_hash",
        receipt.blocker_hash,
        context.blocker_hash,
        mismatches,
    )

    # ── Compute outcome ────────────────────────────────────────────────
    if mismatches:
        return AdoptionDecision(
            outcome=AdoptionOutcome.QUARANTINE,
            receipt_digest=receipt.receipt_digest,
            mismatches=tuple(mismatches),
            diagnostics={
                "mismatch_count": len(mismatches),
                "schema_version": REPAIR_ADOPTION_SCHEMA_VERSION,
            },
        )

    return AdoptionDecision(
        outcome=AdoptionOutcome.ADOPT,
        receipt_digest=receipt.receipt_digest,
        mismatches=(),
        diagnostics={
            "schema_version": REPAIR_ADOPTION_SCHEMA_VERSION,
        },
    )


# ── Public API ─────────────────────────────────────────────────────────────

__all__ = [
    "REPAIR_ADOPTION_SCHEMA_VERSION",
    "AdoptionContext",
    "AdoptionDecision",
    "AdoptionFieldMismatch",
    "AdoptionOutcome",
    "adopt_repair_receipt",
]
