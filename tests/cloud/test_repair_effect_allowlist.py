"""Tests for repair_effect_allowlist — repair effect-class admission gate."""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.cloud.repair_effect_allowlist import (
    ALLOWLIST,
    AllowlistCheckResult,
    AllowlistVerdict,
    EffectClassEntry,
    ReconciliationCapability,
    RepairEffectClass,
    RepairFamily,
    action_off_reason,
    check_effect_class,
    is_repair_eligible,
    known_effect_classes,
)
from arnold_pipelines.megaplan.cloud.repair_contract import (
    admit_repair_effect_class,
)


# ── Allowlist structure tests ──────────────────────────────────────────────


def test_allowlist_is_non_empty() -> None:
    """The allowlist contains entries for all known effect classes."""
    assert len(ALLOWLIST) > 0
    assert len(ALLOWLIST) >= 7


def test_known_effect_classes_covers_all_entries() -> None:
    """known_effect_classes() returns exactly the classes in ALLOWLIST."""
    known = known_effect_classes()
    for entry in ALLOWLIST:
        assert entry.effect_class in known
    assert len(known) == len(ALLOWLIST)


def test_all_entries_have_reason() -> None:
    """Every allowlist entry has a non-empty reason."""
    for entry in ALLOWLIST:
        assert entry.reason, f"Entry {entry.effect_class.value!r} has empty reason"


# ── Positive checks (known classes) ────────────────────────────────────────


def test_write_class_is_known() -> None:
    result = check_effect_class(RepairEffectClass.WRITE)
    assert result.verdict != AllowlistVerdict.ACTION_OFF


def test_mutate_class_is_known() -> None:
    result = check_effect_class(RepairEffectClass.MUTATE)
    assert result.verdict != AllowlistVerdict.ACTION_OFF


def test_publish_class_is_known() -> None:
    result = check_effect_class(RepairEffectClass.PUBLISH)
    assert result.verdict != AllowlistVerdict.ACTION_OFF


def test_deliver_class_is_known() -> None:
    result = check_effect_class(RepairEffectClass.DELIVER)
    assert result.verdict != AllowlistVerdict.ACTION_OFF


def test_compensate_class_is_known() -> None:
    result = check_effect_class(RepairEffectClass.COMPENSATE)
    assert result.verdict != AllowlistVerdict.ACTION_OFF


def test_revert_class_is_known() -> None:
    result = check_effect_class(RepairEffectClass.REVERT)
    assert result.verdict != AllowlistVerdict.ACTION_OFF


def test_delete_class_is_action_off() -> None:
    """DELETE is non-queryable and non-idempotent — always action-off."""
    result = check_effect_class(RepairEffectClass.DELETE)
    assert result.verdict == AllowlistVerdict.ACTION_OFF


# ── Negative checks (unknown classes) ──────────────────────────────────────


def test_unknown_class_action_off() -> None:
    """An unknown effect class string produces ACTION_OFF."""
    result = check_effect_class("nonexistent_class")
    assert result.verdict == AllowlistVerdict.ACTION_OFF
    assert "Unknown" in result.reason


def test_unknown_class_with_allow_unknown_escalated() -> None:
    """With allow_unknown=True, unknown classes escalate instead of action-off."""
    result = check_effect_class("custom_effect", allow_unknown=True)
    assert result.verdict == AllowlistVerdict.ESCALATED
    assert "escalation" in result.reason.lower() or "escalated" in result.reason.lower()


def test_unknown_class_as_str_produces_unknown_reason() -> None:
    """String that doesn't match an enum value produces ACTION_OFF."""
    result = check_effect_class("not_a_valid_class")
    assert result.verdict == AllowlistVerdict.ACTION_OFF


# ── is_repair_eligible ─────────────────────────────────────────────────────


def test_is_repair_eligible_false_for_all_classes_in_m10() -> None:
    """In M10, all effect classes are action-off or escalated."""
    for effect_class in RepairEffectClass:
        if effect_class == RepairEffectClass.UNKNOWN:
            continue
        assert not is_repair_eligible(effect_class), (
            f"{effect_class.value!r} should not be repair-eligible in M10"
        )


def test_is_repair_eligible_false_for_unknown() -> None:
    assert not is_repair_eligible("unknown_class")


# ── action_off_reason ──────────────────────────────────────────────────────


def test_action_off_reason_for_delete() -> None:
    reason = action_off_reason(RepairEffectClass.DELETE)
    assert reason
    assert "non-queryable" in reason.lower() or "delete" in reason.lower()


def test_action_off_reason_empty_for_known_not_action_off() -> None:
    """Known classes that aren't action-off have empty action_off_reason."""
    reason = action_off_reason(RepairEffectClass.WRITE)
    # WRITE is escalated (not approved, but known and idempotent/queryable)
    # so action_off_reason returns "" for non-ACTION_OFF verdicts
    assert reason == ""


# ── Repair contract integration ────────────────────────────────────────────


def test_admit_repair_effect_class_known_write() -> None:
    """admit_repair_effect_class returns (False, reason) for WRITE in M10."""
    admitted, reason = admit_repair_effect_class(RepairEffectClass.WRITE, source="test")
    assert not admitted
    assert "Repair not admitted" in reason
    assert "test" in reason


def test_admit_repair_effect_class_unknown() -> None:
    """admit_repair_effect_class returns (False, reason) for unknown class."""
    admitted, reason = admit_repair_effect_class("unknown_effect")
    assert not admitted
    assert "Repair not admitted" in reason


def test_admit_repair_effect_class_delete() -> None:
    """admit_repair_effect_class rejects DELETE."""
    admitted, reason = admit_repair_effect_class(RepairEffectClass.DELETE)
    assert not admitted
    assert "Repair not admitted" in reason


def test_admit_repair_effect_class_no_source() -> None:
    """admit_repair_effect_class works without source."""
    admitted, reason = admit_repair_effect_class(RepairEffectClass.MUTATE)
    assert not admitted
    assert "source:" not in reason.lower()


def test_admit_repair_effect_class_with_source() -> None:
    """admit_repair_effect_class includes source when provided."""
    admitted, reason = admit_repair_effect_class(
        RepairEffectClass.PUBLISH, source="github_sync.py:42"
    )
    assert not admitted
    assert "github_sync.py:42" in reason


# ── Allowlist entry structure ──────────────────────────────────────────────


def test_effect_class_entries_are_immutable() -> None:
    """EffectClassEntry is frozen (immutable)."""
    entry = ALLOWLIST[0]
    with pytest.raises(Exception):
        entry.reason = "modified"  # type: ignore[misc]


def test_allowlist_verdict_enum_values() -> None:
    """AllowlistVerdict has expected values."""
    assert AllowlistVerdict.APPROVED.value == "approved"
    assert AllowlistVerdict.ACTION_OFF.value == "action_off"
    assert AllowlistVerdict.ESCALATED.value == "escalated"


def test_reconciliation_capability_values() -> None:
    """ReconciliationCapability has expected values."""
    assert ReconciliationCapability.QUERYABLE.value == "queryable"
    assert ReconciliationCapability.NON_QUERYABLE.value == "non_queryable"
    assert ReconciliationCapability.IDEMPOTENT.value == "idempotent"
    assert ReconciliationCapability.NON_IDEMPOTENT.value == "non_idempotent"
    assert ReconciliationCapability.UNKNOWN.value == "unknown"


def test_repair_family_values() -> None:
    """RepairFamily has expected values."""
    assert RepairFamily.IDEMPOTENT_MUTATE.value == "idempotent_mutate"
    assert RepairFamily.IDEMPOTENT_DELIVER.value == "idempotent_deliver"
    assert RepairFamily.COMPENSATABLE_WRITE.value == "compensatable_write"
    assert RepairFamily.REVERTIBLE_MUTATE.value == "revertible_mutate"
    assert RepairFamily.NONE.value == "none"
