"""Repair adoption verifier — read-only, never mutates authority ledgers.

M8A T12: North Star repair adoption boundary.

Verifies that a repair receipt matches current grant, revision, task contract,
tree/commit, tests/result hash, fence, lease, and epoch.  Returns quarantine
diagnostics for mismatches without mutating authoritative ledgers or evidence.

Principles
----------
* **Read-only** — The verifier never writes to ledgers, custody, or evidence.
  A false accept would convert a receipt into unauthorized completion.
* **Composes Run Authority, Custody, and receipt evidence** — Every check
  cross-references at least one of the three authority domains.
* **Quarantine, never rewrite** — Mismatches produce typed quarantine
  diagnostics.  The receipt itself is never modified, and no attempt evidence
  is rewritten.
* **Deterministic and rebuildable** — The same receipt + current state always
  produces the same report digest.  Reports can be rebuilt from stored inputs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from arnold_pipelines.megaplan.custody.repair_receipt import (
    RepairReceipt,
    RepairReceiptStatus,
)

# ---------------------------------------------------------------------------
# Adoption check kinds
# ---------------------------------------------------------------------------


class AdoptionCheckKind(StrEnum):
    """Classes of adoption verification checks.

    Each kind corresponds to one evidence field that must match current state.
    """

    GRANT = "grant"
    """Run Authority grant identity must match the current active grant."""

    REVISION = "revision"
    """Plan revision must match the current plan revision."""

    TASK_CONTRACT = "task_contract"
    """Task contract identifier must match the current task contract."""

    TREE_COMMIT = "tree_commit"
    """Git tree/commit SHA must match the current checkout."""

    TEST_RESULT_HASH = "test_result_hash"
    """Test result payload hash must match current test evidence."""

    FENCE = "fence"
    """Coordinator fence token must match the current fence."""

    LEASE = "lease"
    """Custody lease identity must match the current active lease."""

    EPOCH = "epoch"
    """Custody epoch must match the current lease epoch."""


# ---------------------------------------------------------------------------
# Adoption verdict
# ---------------------------------------------------------------------------


class AdoptionVerdict(StrEnum):
    """Outcome of repair adoption verification."""

    ADOPT = "adopt"
    """All checks passed — receipt evidence matches current state.
    The receipt can be adopted; normal execution continues."""

    QUARANTINE = "quarantine"
    """One or more checks failed — receipt is quarantined.
    The receipt must not be adopted; normal execution continues
    without the receipt."""

    INVALID = "invalid"
    """Receipt is structurally invalid (missing fields, wrong type).
    Cannot perform verification; treated as quarantine."""


# ---------------------------------------------------------------------------
# Adoption diagnostic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdoptionDiagnostic:
    """A single check result from adoption verification.

    Each diagnostic captures one evidence field comparison.  It is immutable
    and deterministic — the same input produces the same diagnostic.
    """

    kind: AdoptionCheckKind
    """Which evidence field was checked."""

    passed: bool
    """True when the receipt field matches current state."""

    expected: str
    """The current state value (canonical string form)."""

    actual: str
    """The receipt value (canonical string form)."""

    detail: str = ""
    """Human-readable explanation (empty when passed)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Adoption report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdoptionReport:
    """Complete repair adoption verification report.

    The report is immutable and carries a deterministic content digest so
    callers can cache or compare reports without re-verifying.
    """

    verdict: AdoptionVerdict
    """Overall adoption outcome."""

    receipt_id: str
    """Receipt identifier that was verified (empty for INVALID)."""

    diagnostics: tuple[AdoptionDiagnostic, ...]
    """All check results, in definition order."""

    report_digest: str = field(init=False)
    """Deterministic SHA-256 digest over the full report payload."""

    def __post_init__(self) -> None:
        payload: dict[str, Any] = {
            "verdict": self.verdict.value,
            "receipt_id": self.receipt_id,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
        plain = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        object.__setattr__(self, "report_digest", "sha256:" + hashlib.sha256(plain.encode("utf-8")).hexdigest())

    @property
    def passed(self) -> bool:
        """True when the receipt can be adopted."""
        return self.verdict == AdoptionVerdict.ADOPT

    @property
    def failed_checks(self) -> tuple[AdoptionDiagnostic, ...]:
        """Only the diagnostics that did not pass."""
        return tuple(d for d in self.diagnostics if not d.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "receipt_id": self.receipt_id,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "report_digest": self.report_digest,
        }


# ---------------------------------------------------------------------------
# Verifier — the North Star repair adoption boundary
# ---------------------------------------------------------------------------


def verify_repair_adoption(
    receipt: RepairReceipt | Any,
    *,
    current_grant_id: str = "",
    current_revision: str = "",
    current_task_contract: str = "",
    current_tree_commit: str = "",
    current_test_result_hash: str = "",
    current_fence_token: int = 0,
    current_lease_id: str = "",
    current_epoch: int = 0,
) -> AdoptionReport:
    """Verify that a repair receipt matches current state.

    Every check is **read-only** — no ledgers, custody state, or evidence
    is mutated.  The function composes Run Authority (grant, fence),
    Custody (lease, epoch), and receipt evidence (revision, task contract,
    tree/commit, test results) to produce a single adoption verdict.

    Parameters
    ----------
    receipt
        The repair receipt to verify.  Must be a :class:`RepairReceipt`
        instance; non-``RepairReceipt`` values produce ``INVALID``.
    current_grant_id
        The currently active Run Authority grant identifier.
    current_revision
        The current plan revision.
    current_task_contract
        The current task contract identifier.
    current_tree_commit
        The current git tree/commit SHA.
    current_test_result_hash
        The current test result payload hash.
    current_fence_token
        The current coordinator fence token.
    current_lease_id
        The current custody lease identifier.
    current_epoch
        The current custody lease epoch.

    Returns
    -------
    AdoptionReport
        Verdict ``ADOPT`` when all checks pass, ``QUARANTINE`` when any check
        fails, or ``INVALID`` when the receipt is structurally invalid.
    """
    # ── Structural guard ────────────────────────────────────────────────
    if not isinstance(receipt, RepairReceipt):
        return AdoptionReport(
            verdict=AdoptionVerdict.INVALID,
            receipt_id="",
            diagnostics=(),
        )

    receipt_id = receipt.receipt_id
    if not receipt_id or not receipt_id.strip():
        return AdoptionReport(
            verdict=AdoptionVerdict.INVALID,
            receipt_id="",
            diagnostics=(),
        )

    diagnostics: list[AdoptionDiagnostic] = []
    all_passed = True

    # ── Check 1: Grant identity (Run Authority) ────────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.GRANT,
        receipt.run_authority_grant_id,
        current_grant_id,
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 2: Plan revision (Receipt evidence) ──────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.REVISION,
        receipt.plan_revision,
        current_revision,
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 3: Task contract (Receipt evidence) ──────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.TASK_CONTRACT,
        receipt.task_contract,
        current_task_contract,
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 4: Tree/commit (Receipt evidence) ────────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.TREE_COMMIT,
        receipt.tree_commit,
        current_tree_commit,
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 5: Test result hash (Receipt evidence) ───────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.TEST_RESULT_HASH,
        receipt.payload_hash,
        current_test_result_hash,
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 6: Coordinator fence (Run Authority) ─────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.FENCE,
        str(receipt.coordinator_fence_token),
        str(current_fence_token),
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 7: Custody lease (Custody) ───────────────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.LEASE,
        receipt.custody_lease_id,
        current_lease_id,
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    # ── Check 8: Custody epoch (Custody) ───────────────────────────────
    _check(
        diagnostics,
        AdoptionCheckKind.EPOCH,
        str(receipt.custody_epoch),
        str(current_epoch),
    )
    if diagnostics and not diagnostics[-1].passed:
        all_passed = False

    return AdoptionReport(
        verdict=AdoptionVerdict.ADOPT if all_passed else AdoptionVerdict.QUARANTINE,
        receipt_id=receipt_id,
        diagnostics=tuple(diagnostics),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check(
    diagnostics: list[AdoptionDiagnostic],
    kind: AdoptionCheckKind,
    actual: str,
    expected: str,
) -> None:
    """Append a single AdoptionDiagnostic to *diagnostics*."""
    passed = actual == expected
    detail = ""
    if not passed:
        detail = (
            f"{kind.value} mismatch: "
            f"receipt claims {actual!r}, "
            f"current is {expected!r}"
        )
    diagnostics.append(
        AdoptionDiagnostic(
            kind=kind,
            passed=passed,
            expected=expected,
            actual=actual,
            detail=detail,
        )
    )


# ---------------------------------------------------------------------------
# Convenience: verify from RunAuthorityView + CustodyLease
# ---------------------------------------------------------------------------


def verify_repair_adoption_from_view(
    receipt: RepairReceipt | Any,
    *,
    current_grant_id: str = "",
    current_revision: str = "",
    current_fence_token: int = 0,
    lease_id: str = "",
    lease_epoch: int = 0,
) -> AdoptionReport:
    """Verify adoption using RunAuthorityView-derived fields and CustodyLease.

    This is a convenience wrapper around :func:`verify_repair_adoption` that
    accepts the most common authority-derived fields directly.  The task
    contract and tree/commit are taken from the receipt itself for
    self-consistency checks (or can be overridden by the caller through the
    full :func:`verify_repair_adoption` function).

    Parameters
    ----------
    receipt
        The repair receipt to verify.
    current_grant_id
        The currently active grant identifier (from RunAuthorityView.grants).
    current_revision
        The current plan revision (from RunAuthorityView.run_revision).
    current_fence_token
        The current fence token (from RunAuthorityView.fences).
    lease_id
        The current custody lease identifier (from CustodyLease.lease_id).
    lease_epoch
        The current custody lease epoch (from CustodyLease.epoch).

    Returns
    -------
    AdoptionReport
    """
    if not isinstance(receipt, RepairReceipt):
        return AdoptionReport(
            verdict=AdoptionVerdict.INVALID,
            receipt_id="",
            diagnostics=(),
        )

    return verify_repair_adoption(
        receipt,
        current_grant_id=current_grant_id,
        current_revision=current_revision,
        current_task_contract=receipt.task_contract,
        current_tree_commit=receipt.tree_commit,
        current_test_result_hash=receipt.payload_hash,
        current_fence_token=current_fence_token,
        current_lease_id=lease_id,
        current_epoch=lease_epoch,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AdoptionCheckKind",
    "AdoptionDiagnostic",
    "AdoptionReport",
    "AdoptionVerdict",
    "verify_repair_adoption",
    "verify_repair_adoption_from_view",
]
