"""Structured normalization for quality-status families.

Parser loss cannot hide blockers.  This module normalizes quality-status
families such as ``fail``, ``failed``, ``failed: <detail>``, ``error: <detail>``
at the shared classifier/projection seam while preserving original commands,
criterion IDs, hashes, and exact occurrence identity.

Design rules
------------
* Normalization is structural — it maps a family variant to a canonical family
  name, but never discards the original.
* Every normalized entry retains: original command, criterion_id (when
  present), content hash, and occurrence timestamp.
* Unrecognized families are passed through with family="unknown" — they are
  never silently collapsed into "pass" or "success".
* The output is deterministic: same input → same output, including sort order.
* This module is consumed by the run-state classifier, status projection,
  introspect payload, and repair-facing projections.

Covered families
----------------
- fail / failed / failure
- error / errored
- timeout / timed_out
- skip / skipped
- pass / passed / success / ok
- warn / warning
- unknown (catch-all for unrecognized)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple


# ── Canonical quality families ────────────────────────────────────────────


class QualityFamily(Enum):
    """Canonical quality-status families.

    Every quality-status string normalizes to exactly one of these.
    The original string is always preserved alongside the canonical family.
    """

    FAIL = "fail"
    """Hard failure — criterion was not met, command exited non-zero, assertion failed."""

    ERROR = "error"
    """Infrastructure error — criterion could not be evaluated (timeout, crash, OOM)."""

    TIMEOUT = "timeout"
    """Evaluation timed out before a result could be determined."""

    SKIP = "skip"
    """Criterion was deliberately skipped (e.g. conditional, not applicable)."""

    PASS = "pass"
    """Criterion passed — no failure detected."""

    WARN = "warn"
    """Warning — criterion passed but with caveats."""

    UNKNOWN = "unknown"
    """Unrecognized quality status — passed through, never collapsed to pass."""


# ── Family normalization table ────────────────────────────────────────────


# Mapping from lowercase original status to canonical family.
# Patterns are matched by prefix so "failed: assertion error" → FAIL.
_FAMILY_PREFIX_MAP: Tuple[Tuple[str, QualityFamily], ...] = (
    ("failed:", QualityFamily.FAIL),
    ("failed", QualityFamily.FAIL),
    ("fail:", QualityFamily.FAIL),
    ("fail", QualityFamily.FAIL),
    ("failure:", QualityFamily.FAIL),
    ("failure", QualityFamily.FAIL),
    ("error:", QualityFamily.ERROR),
    ("error", QualityFamily.ERROR),
    ("errored:", QualityFamily.ERROR),
    ("errored", QualityFamily.ERROR),
    ("timeout:", QualityFamily.TIMEOUT),
    ("timeout", QualityFamily.TIMEOUT),
    ("timed_out:", QualityFamily.TIMEOUT),
    ("timed_out", QualityFamily.TIMEOUT),
    ("timed-out:", QualityFamily.TIMEOUT),
    ("timed-out", QualityFamily.TIMEOUT),
    ("skip:", QualityFamily.SKIP),
    ("skip", QualityFamily.SKIP),
    ("skipped:", QualityFamily.SKIP),
    ("skipped", QualityFamily.SKIP),
    ("pass:", QualityFamily.PASS),
    ("pass", QualityFamily.PASS),
    ("passed:", QualityFamily.PASS),
    ("passed", QualityFamily.PASS),
    ("success:", QualityFamily.PASS),
    ("success", QualityFamily.PASS),
    ("ok:", QualityFamily.PASS),
    ("ok", QualityFamily.PASS),
    ("succeeded:", QualityFamily.PASS),
    ("succeeded", QualityFamily.PASS),
    ("warn:", QualityFamily.WARN),
    ("warn", QualityFamily.WARN),
    ("warning:", QualityFamily.WARN),
    ("warning", QualityFamily.WARN),
)


def normalize_quality_family(raw_status: str) -> QualityFamily:
    """Normalize a raw quality-status string to its canonical family.

    Args:
        raw_status: The original status string (e.g. ``"failed: assertion error"``).

    Returns:
        The canonical QualityFamily.  Unrecognized strings return ``UNKNOWN``
        — they are never collapsed to ``PASS``.
    """
    if not raw_status or not isinstance(raw_status, str):
        return QualityFamily.UNKNOWN

    lowered = raw_status.strip().lower()
    if not lowered:
        return QualityFamily.UNKNOWN

    for prefix, family in _FAMILY_PREFIX_MAP:
        if lowered.startswith(prefix):
            return family

    return QualityFamily.UNKNOWN


# ── Quality occurrence (preserves exact identity) ────────────────────────


@dataclass(frozen=True)
class QualityOccurrence:
    """A single quality-status occurrence with exact identity preserved.

    Normalization maps the status to a canonical family but preserves:
    * original_status — the exact string before normalization
    * command — the command that produced this occurrence
    * criterion_id — the criterion identifier (when available)
    * content_hash — sha256 of (original_status, command, criterion_id) for integrity
    * occurred_at — ISO-8601 timestamp when the occurrence was recorded
    """

    original_status: str
    """The exact original status string, preserved verbatim."""

    family: QualityFamily
    """The canonical family after normalization."""

    command: str = ""
    """The command that produced this occurrence (e.g. 'pytest', 'shellcheck')."""

    criterion_id: str = ""
    """The criterion identifier (e.g. 'T3', 'lint/ruff')."""

    content_hash: str = field(init=False)
    """sha256 of (original_status, command, criterion_id) — integrity check."""

    occurred_at: str = ""
    """ISO-8601 timestamp when this occurrence was recorded."""

    exit_code: Optional[int] = None
    """Exit code of the command, when available."""

    detail: str = ""
    """Additional detail from the original status (e.g. the part after 'failed: ')."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = f"{self.original_status}\x00{self.command}\x00{self.criterion_id}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "content_hash", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

        # Extract detail from original_status if not explicitly provided
        if not self.detail:
            lowered = self.original_status.strip().lower()
            for prefix in ("failed: ", "fail: ", "error: ", "timeout: ", "skip: ", "pass: ", "warn: "):
                if lowered.startswith(prefix):
                    detail_part = self.original_status.strip()[len(prefix):].strip()
                    if detail_part:
                        object.__setattr__(self, "detail", detail_part)
                    break

    @property
    def is_blocking(self) -> bool:
        """True when this occurrence blocks progress (FAIL, ERROR, TIMEOUT)."""
        return self.family in (QualityFamily.FAIL, QualityFamily.ERROR, QualityFamily.TIMEOUT)

    @property
    def is_pass(self) -> bool:
        """True when this occurrence is a pass/success."""
        return self.family == QualityFamily.PASS

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "original_status": self.original_status,
            "family": self.family.value,
            "criterion_id": self.criterion_id,
            "content_hash": self.content_hash,
            "occurred_at": self.occurred_at,
            "is_blocking": self.is_blocking,
            "_non_authoritative": self._non_authoritative,
        }
        if self.command:
            result["command"] = self.command
        if self.exit_code is not None:
            result["exit_code"] = self.exit_code
        if self.detail:
            result["detail"] = self.detail
        return result

    @classmethod
    def from_status(
        cls,
        original_status: str,
        *,
        command: str = "",
        criterion_id: str = "",
        occurred_at: str = "",
        exit_code: Optional[int] = None,
        detail: str = "",
    ) -> "QualityOccurrence":
        """Create a QualityOccurrence from a raw status string."""
        family = normalize_quality_family(original_status)
        return cls(
            original_status=original_status,
            family=family,
            command=command,
            criterion_id=criterion_id,
            occurred_at=occurred_at,
            exit_code=exit_code,
            detail=detail,
        )


# ── Occurrence set (deterministic ordering) ──────────────────────────────


@dataclass(frozen=True)
class QualityOccurrenceSet:
    """A deterministic set of quality occurrences.

    Occurrences are sorted by (criterion_id, content_hash) for deterministic
    output.  Duplicates (same criterion_id + content_hash) are removed.
    """

    occurrences: Tuple[QualityOccurrence, ...]
    """All occurrences in deterministic order."""

    set_digest: str = field(init=False)
    """sha256 over all occurrence content_hashes in order."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        # Deduplicate by (criterion_id, content_hash)
        seen: set[Tuple[str, str]] = set()
        deduped: List[QualityOccurrence] = []
        for occ in self.occurrences:
            key = (occ.criterion_id, occ.content_hash)
            if key not in seen:
                seen.add(key)
                deduped.append(occ)

        # Sort by criterion_id then content_hash for determinism
        deduped.sort(key=lambda o: (o.criterion_id, o.content_hash))
        object.__setattr__(self, "occurrences", tuple(deduped))

        # Set digest
        parts = "\x00".join(o.content_hash for o in deduped)
        set_digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "set_digest", f"sha256:{set_digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def blocking_count(self) -> int:
        """Number of blocking occurrences (FAIL, ERROR, TIMEOUT)."""
        return sum(1 for o in self.occurrences if o.is_blocking)

    @property
    def pass_count(self) -> int:
        """Number of passing occurrences."""
        return sum(1 for o in self.occurrences if o.is_pass)

    @property
    def total_count(self) -> int:
        """Total number of occurrences (after dedup)."""
        return len(self.occurrences)

    @property
    def families_present(self) -> Tuple[str, ...]:
        """Canonical family names present in this set (sorted)."""
        return tuple(sorted(set(o.family.value for o in self.occurrences)))

    @property
    def has_blocking(self) -> bool:
        """True when any occurrence is blocking."""
        return self.blocking_count > 0

    @property
    def all_pass(self) -> bool:
        """True when all occurrences are PASS (and set is non-empty)."""
        return self.total_count > 0 and self.blocking_count == 0 and all(o.is_pass for o in self.occurrences)

    def by_family(self, family: QualityFamily) -> Tuple[QualityOccurrence, ...]:
        """Return occurrences of a specific family."""
        return tuple(o for o in self.occurrences if o.family == family)

    def by_criterion(self, criterion_id: str) -> Tuple[QualityOccurrence, ...]:
        """Return occurrences for a specific criterion."""
        return tuple(o for o in self.occurrences if o.criterion_id == criterion_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "occurrences": [o.to_dict() for o in self.occurrences],
            "set_digest": self.set_digest,
            "blocking_count": self.blocking_count,
            "pass_count": self.pass_count,
            "total_count": self.total_count,
            "families_present": list(self.families_present),
            "has_blocking": self.has_blocking,
            "all_pass": self.all_pass,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_occurrences(cls, *occurrences: QualityOccurrence) -> "QualityOccurrenceSet":
        """Build a set from individual occurrences."""
        return cls(occurrences=tuple(occurrences))

    @classmethod
    def from_status_list(
        cls,
        statuses: Sequence[str],
        *,
        command: str = "",
        criterion_id_prefix: str = "",
        occurred_at: str = "",
    ) -> "QualityOccurrenceSet":
        """Build a set from a list of raw status strings.

        Each status gets an auto-generated criterion_id from its position.
        """
        occurrences: List[QualityOccurrence] = []
        for i, status in enumerate(statuses):
            cid = f"{criterion_id_prefix}{i}" if criterion_id_prefix else str(i)
            occurrences.append(
                QualityOccurrence.from_status(
                    status,
                    command=command,
                    criterion_id=cid,
                    occurred_at=occurred_at,
                )
            )
        return cls(occurrences=tuple(occurrences))


# ── Aggregate summary (for projection consumers) ─────────────────────────


@dataclass(frozen=True)
class QualitySummary:
    """Aggregate quality summary for projection consumers.

    Normalizes a collection of quality occurrences into a structured summary
    that consumers can use for display, blocking, and diagnostics.  Every
    original occurrence is preserved in the detail set.
    """

    occurrence_set: QualityOccurrenceSet
    """The full set of quality occurrences."""

    summary_family: QualityFamily = field(init=False)
    """The worst family present (FAIL > ERROR > TIMEOUT > WARN > SKIP > PASS > UNKNOWN)."""

    summary_text: str = field(init=False)
    """Human-readable summary of the aggregate quality."""

    _non_authoritative: bool = field(default=True, init=False)

    _FAMILY_SEVERITY: Tuple[QualityFamily, ...] = (
        QualityFamily.FAIL,
        QualityFamily.ERROR,
        QualityFamily.TIMEOUT,
        QualityFamily.WARN,
        QualityFamily.SKIP,
        QualityFamily.PASS,
        QualityFamily.UNKNOWN,
    )

    def __post_init__(self) -> None:
        # Determine worst family
        present = set(o.family for o in self.occurrence_set.occurrences)
        worst = QualityFamily.UNKNOWN
        for family in self._FAMILY_SEVERITY:
            if family in present:
                worst = family
                break
        object.__setattr__(self, "summary_family", worst)

        # Build summary text
        total = self.occurrence_set.total_count
        blocking = self.occurrence_set.blocking_count
        passing = self.occurrence_set.pass_count
        parts = [f"{total} occurrence(s)"]
        if blocking:
            parts.append(f"{blocking} blocking")
        if passing:
            parts.append(f"{passing} passing")
        parts.append(f"worst={worst.value}")
        object.__setattr__(self, "summary_text", "; ".join(parts))
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "occurrence_set": self.occurrence_set.to_dict(),
            "summary_family": self.summary_family.value,
            "summary_text": self.summary_text,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_occurrences(cls, *occurrences: QualityOccurrence) -> "QualitySummary":
        """Build a summary from individual occurrences."""
        return cls(occurrence_set=QualityOccurrenceSet.from_occurrences(*occurrences))

    @classmethod
    def from_status_list(
        cls,
        statuses: Sequence[str],
        *,
        command: str = "",
        criterion_id_prefix: str = "",
        occurred_at: str = "",
    ) -> "QualitySummary":
        """Build a summary from a list of raw status strings."""
        return cls(
            occurrence_set=QualityOccurrenceSet.from_status_list(
                statuses,
                command=command,
                criterion_id_prefix=criterion_id_prefix,
                occurred_at=occurred_at,
            )
        )


__all__ = [
    # ── Types ──
    "QualityFamily",
    # ── Normalization ──
    "normalize_quality_family",
    # ── Occurrences ──
    "QualityOccurrence",
    "QualityOccurrenceSet",
    "QualitySummary",
]
