"""Repair effect-class allowlist gate.

Maps supported effect classes to approved repair families, reconciliation
capabilities, and evidence predicates.  Unknown, non-queryable, or
non-idempotent ambiguous effect classes remain action-off and produce typed
escalation.

All production effects are action-off in M10; this module defines the
classification policy so that repair admission can gate on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Mapping


class RepairEffectClass(StrEnum):
    """Effect classes relevant to repair admission."""

    WRITE = "write"
    MUTATE = "mutate"
    DELETE = "delete"
    PUBLISH = "publish"
    DELIVER = "deliver"
    COMPENSATE = "compensate"
    REVERT = "revert"
    UNKNOWN = "unknown"


class RepairFamily(StrEnum):
    """Repair family identifiers for effect classes."""

    IDEMPOTENT_MUTATE = "idempotent_mutate"
    IDEMPOTENT_DELIVER = "idempotent_deliver"
    COMPENSATABLE_WRITE = "compensatable_write"
    REVERTIBLE_MUTATE = "revertible_mutate"
    NONE = "none"


class ReconciliationCapability(StrEnum):
    """Provider reconciliation capability."""

    QUERYABLE = "queryable"
    NON_QUERYABLE = "non_queryable"
    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"


class AllowlistVerdict(StrEnum):
    """Verdict for an effect class checked against the allowlist."""

    APPROVED = "approved"
    ACTION_OFF = "action_off"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class EffectClassEntry:
    """A single allowlist entry mapping an effect class to its policy."""

    effect_class: RepairEffectClass
    repair_family: RepairFamily
    reconciliation: ReconciliationCapability
    idempotent: bool
    queryable: bool
    approved_for_repair: bool
    reason: str = ""


@dataclass
class AllowlistCheckResult:
    """Result of checking an effect class against the allowlist."""

    effect_class: RepairEffectClass
    verdict: AllowlistVerdict
    reason: str = ""
    escalation_kind: str = ""


# ── Allowlist definition ────────────────────────────────────────────────────

ALLOWLIST: tuple[EffectClassEntry, ...] = (
    EffectClassEntry(
        effect_class=RepairEffectClass.WRITE,
        repair_family=RepairFamily.COMPENSATABLE_WRITE,
        reconciliation=ReconciliationCapability.QUERYABLE,
        idempotent=True,
        queryable=True,
        approved_for_repair=False,
        reason="M10: write effects remain action-off; enable in M11",
    ),
    EffectClassEntry(
        effect_class=RepairEffectClass.MUTATE,
        repair_family=RepairFamily.IDEMPOTENT_MUTATE,
        reconciliation=ReconciliationCapability.QUERYABLE,
        idempotent=True,
        queryable=True,
        approved_for_repair=False,
        reason="M10: mutate effects remain action-off; enable in M11",
    ),
    EffectClassEntry(
        effect_class=RepairEffectClass.DELETE,
        repair_family=RepairFamily.NONE,
        reconciliation=ReconciliationCapability.NON_QUERYABLE,
        idempotent=False,
        queryable=False,
        approved_for_repair=False,
        reason="M10: delete effects are non-repairable and action-off",
    ),
    EffectClassEntry(
        effect_class=RepairEffectClass.PUBLISH,
        repair_family=RepairFamily.IDEMPOTENT_DELIVER,
        reconciliation=ReconciliationCapability.QUERYABLE,
        idempotent=True,
        queryable=True,
        approved_for_repair=False,
        reason="M10: publish effects remain action-off; enable in M11",
    ),
    EffectClassEntry(
        effect_class=RepairEffectClass.DELIVER,
        repair_family=RepairFamily.IDEMPOTENT_DELIVER,
        reconciliation=ReconciliationCapability.QUERYABLE,
        idempotent=True,
        queryable=True,
        approved_for_repair=False,
        reason="M10: delivery effects remain action-off; enable in M11",
    ),
    EffectClassEntry(
        effect_class=RepairEffectClass.COMPENSATE,
        repair_family=RepairFamily.COMPENSATABLE_WRITE,
        reconciliation=ReconciliationCapability.QUERYABLE,
        idempotent=True,
        queryable=True,
        approved_for_repair=False,
        reason="M10: compensation effects remain action-off; enable in M11",
    ),
    EffectClassEntry(
        effect_class=RepairEffectClass.REVERT,
        repair_family=RepairFamily.REVERTIBLE_MUTATE,
        reconciliation=ReconciliationCapability.QUERYABLE,
        idempotent=True,
        queryable=True,
        approved_for_repair=False,
        reason="M10: revert effects remain action-off; enable in M11",
    ),
)


def _lookup(effect_class: RepairEffectClass | str) -> EffectClassEntry | None:
    """Return the allowlist entry for *effect_class*, or None."""
    if isinstance(effect_class, str):
        try:
            effect_class = RepairEffectClass(effect_class)
        except ValueError:
            return None
    for entry in ALLOWLIST:
        if entry.effect_class == effect_class:
            return entry
    return None


def check_effect_class(
    effect_class: RepairEffectClass | str,
    *,
    allow_unknown: bool = False,
) -> AllowlistCheckResult:
    """Check *effect_class* against the repair effect allowlist.

    Args:
        effect_class: The effect class to check.
        allow_unknown: If False (default), unknown effect classes produce
            ``ACTION_OFF`` with an escalation reason.

    Returns:
        An :class:`AllowlistCheckResult` with the verdict.
    """
    if isinstance(effect_class, str):
        try:
            effect_class = RepairEffectClass(effect_class)
        except ValueError:
            if allow_unknown:
                return AllowlistCheckResult(
                    effect_class=RepairEffectClass.UNKNOWN,
                    verdict=AllowlistVerdict.ESCALATED,
                    reason=f"Effect class {effect_class!r} is not in the allowlist and requires escalation.",
                    escalation_kind="missing_allowlist_entry",
                )
            return AllowlistCheckResult(
                effect_class=RepairEffectClass.UNKNOWN,
                verdict=AllowlistVerdict.ACTION_OFF,
                reason=f"Unknown effect class {effect_class!r} is not in the allowlist.",
                escalation_kind="unknown_effect_class",
            )

    entry = _lookup(effect_class)
    if entry is None:
        if allow_unknown:
            return AllowlistCheckResult(
                effect_class=effect_class,
                verdict=AllowlistVerdict.ESCALATED,
                reason=f"Effect class {effect_class.value!r} is not in the allowlist and requires escalation.",
                escalation_kind="missing_allowlist_entry",
            )
        return AllowlistCheckResult(
            effect_class=effect_class,
            verdict=AllowlistVerdict.ACTION_OFF,
            reason=f"Effect class {effect_class.value!r} is not in the allowlist.",
            escalation_kind="unknown_effect_class",
        )

    if entry.approved_for_repair:
        return AllowlistCheckResult(
            effect_class=entry.effect_class,
            verdict=AllowlistVerdict.APPROVED,
            reason=entry.reason or "Approved for repair.",
        )

    if not entry.queryable:
        return AllowlistCheckResult(
            effect_class=entry.effect_class,
            verdict=AllowlistVerdict.ACTION_OFF,
            reason=f"Effect class {entry.effect_class.value!r} is non-queryable: {entry.reason}",
            escalation_kind="non_queryable_effect",
        )

    if not entry.idempotent:
        return AllowlistCheckResult(
            effect_class=entry.effect_class,
            verdict=AllowlistVerdict.ACTION_OFF,
            reason=f"Effect class {entry.effect_class.value!r} is non-idempotent: {entry.reason}",
            escalation_kind="non_idempotent_effect",
        )

    # Known, queryable, idempotent, but not approved — escalate
    return AllowlistCheckResult(
        effect_class=entry.effect_class,
        verdict=AllowlistVerdict.ESCALATED,
        reason=f"Effect class {entry.effect_class.value!r} is known but not approved for repair: {entry.reason}",
        escalation_kind="not_approved_for_repair",
    )


def is_repair_eligible(
    effect_class: RepairEffectClass | str,
) -> bool:
    """Return True when *effect_class* is eligible for repair dispatch."""
    result = check_effect_class(effect_class)
    return result.verdict == AllowlistVerdict.APPROVED


def action_off_reason(
    effect_class: RepairEffectClass | str,
) -> str:
    """Return the action-off reason for *effect_class*, or empty string."""
    result = check_effect_class(effect_class)
    if result.verdict == AllowlistVerdict.ACTION_OFF:
        return result.reason
    return ""


def known_effect_classes() -> frozenset[RepairEffectClass]:
    """Return the set of known effect classes in the allowlist."""
    return frozenset(entry.effect_class for entry in ALLOWLIST)


__all__ = [
    "ALLOWLIST",
    "AllowlistCheckResult",
    "AllowlistVerdict",
    "EffectClassEntry",
    "ReconciliationCapability",
    "RepairEffectClass",
    "RepairFamily",
    "action_off_reason",
    "check_effect_class",
    "is_repair_eligible",
    "known_effect_classes",
]
