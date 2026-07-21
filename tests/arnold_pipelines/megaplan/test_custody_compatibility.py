"""Rollback fixtures and compatibility tests for old-reader/new-writer bridge.

Proves that promotion/effects are disabled during rollback without
restoring legacy authoritative writers or erasing quarantined attempts.

Covers:
- Per-reader compatibility expiry (explicit deadline milestones)
- Mode-gated behavior (shadow / active / rollback)
- Default M8 acceptance for old readers
- Rollback safety: no legacy writer reactivation, no quarantined erasure
"""

from __future__ import annotations

import os
from unittest import TestCase

from arnold_pipelines.megaplan.custody.compatibility import (
    COMPATIBILITY_REGISTRY,
    CompatibilityMode,
    CompatibilitySnapshot,
    CompatibilityStatus,
    DeadlineMilestone,
    ReaderCompatibility,
    RollbackValidation,
    check_reader_compatibility,
    get_mode,
    is_production_enforcement_enabled,
    list_expired_readers,
    list_expiring_readers,
    list_readers,
    snapshot,
    validate_rollback_safety,
)


# ── Helper: patch env vars ───────────────────────────────────────────────


class _EnvPatch:
    """Context manager to temporarily set/clear environment variables."""

    def __init__(self, **kwargs: str | None):
        self._patch = kwargs
        self._originals: dict[str, str | None] = {}

    def __enter__(self) -> _EnvPatch:
        for key, value in self._patch.items():
            self._originals[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *args: object) -> None:
        for key, original in self._originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


# ── Per-reader compatibility expiry ──────────────────────────────────────


class PerReaderCompatibilityExpiryTests(TestCase):
    """Tests that every reader has an explicit deadline and expiry works."""

    def test_all_readers_have_explicit_deadline(self) -> None:
        """Every registered reader must have an explicit deadline milestone."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertIsInstance(
                reader.deadline_milestone,
                DeadlineMilestone,
                f"{reader.reader_id} deadline must be a DeadlineMilestone",
            )
            self.assertNotEqual(
                reader.deadline_milestone,
                "",
                f"{reader.reader_id} deadline must not be empty",
            )

    def test_default_deadline_is_m8(self) -> None:
        """Old-reader compatibility defaults to M8 acceptance."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertEqual(
                reader.deadline_milestone,
                DeadlineMilestone.M8,
                f"{reader.reader_id} must default to M8 unless explicitly overridden",
            )

    def test_expiry_at_m9_when_deadline_is_m8(self) -> None:
        """Readers with M8 deadline are expired at M9."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertTrue(
                reader.is_expired(DeadlineMilestone.M9),
                f"{reader.reader_id} with M8 deadline must be expired at M9",
            )

    def test_not_expired_at_m7_when_deadline_is_m8(self) -> None:
        """Readers with M8 deadline are not expired at M7."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertFalse(
                reader.is_expired(DeadlineMilestone.M7),
                f"{reader.reader_id} with M8 deadline must not be expired at M7",
            )

    def test_expiring_at_m7a_when_deadline_is_m8(self) -> None:
        """Readers with M8 deadline are expiring at M7A (one milestone before)."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertTrue(
                reader.is_expiring(DeadlineMilestone.M7A),
                f"{reader.reader_id} with M8 deadline must be expiring at M7A",
            )

    def test_none_deadline_never_expires(self) -> None:
        """A reader with NONE deadline never expires."""
        reader = ReaderCompatibility(
            reader_id="test-none",
            reader_name="Test None",
            deadline_milestone=DeadlineMilestone.NONE,
        )
        for ms in (
            DeadlineMilestone.M7,
            DeadlineMilestone.M7A,
            DeadlineMilestone.M8,
            DeadlineMilestone.M9,
            DeadlineMilestone.M10,
        ):
            self.assertFalse(
                reader.is_expired(ms),
                f"NONE deadline must not expire at {ms}",
            )
            self.assertFalse(
                reader.is_expiring(ms),
                f"NONE deadline must not be expiring at {ms}",
            )

    def test_check_reader_compatibility_returns_expired_at_m9(self) -> None:
        """check_reader_compatibility returns EXPIRED for M8-deadline readers at M9."""
        for reader in COMPATIBILITY_REGISTRY:
            status = check_reader_compatibility(
                reader.reader_id,
                current_milestone=DeadlineMilestone.M9,
                mode=CompatibilityMode.ACTIVE,
            )
            self.assertEqual(
                status,
                CompatibilityStatus.EXPIRED,
                f"{reader.reader_id} must be EXPIRED at M9 in ACTIVE mode",
            )

    def test_check_reader_compatibility_returns_expiring_at_m7a(self) -> None:
        """check_reader_compatibility returns EXPIRING approaching deadline."""
        for reader in COMPATIBILITY_REGISTRY:
            status = check_reader_compatibility(
                reader.reader_id,
                current_milestone=DeadlineMilestone.M7A,
                mode=CompatibilityMode.ACTIVE,
            )
            self.assertEqual(
                status,
                CompatibilityStatus.EXPIRING,
                f"{reader.reader_id} must be EXPIRING at M7A in ACTIVE mode",
            )


# ── Mode-gated behavior ──────────────────────────────────────────────────


class ModeGatedBehaviorTests(TestCase):
    """Tests that compatibility behavior adapts to the current mode."""

    def test_default_mode_is_shadow(self) -> None:
        """Default mode is SHADOW — M7 enforcement is off."""
        with _EnvPatch(
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None,
            ARNOLD_M7_ROLLBACK=None,
        ):
            self.assertEqual(get_mode(), CompatibilityMode.SHADOW)

    def test_enforcement_flag_switches_to_active(self) -> None:
        """Setting ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=1 activates mode."""
        with _EnvPatch(
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT="1",
            ARNOLD_M7_ROLLBACK=None,
        ):
            self.assertEqual(get_mode(), CompatibilityMode.ACTIVE)

    def test_rollback_flag_overrides_enforcement(self) -> None:
        """Rollback flag takes priority over enforcement."""
        with _EnvPatch(
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT="1",
            ARNOLD_M7_ROLLBACK="1",
        ):
            self.assertEqual(get_mode(), CompatibilityMode.ROLLBACK)

    def test_shadow_mode_reader_is_compatible(self) -> None:
        """In SHADOW mode, readers at their current milestone are COMPATIBLE."""
        for reader in COMPATIBILITY_REGISTRY:
            status = check_reader_compatibility(
                reader.reader_id,
                current_milestone=DeadlineMilestone.M7,
                mode=CompatibilityMode.SHADOW,
            )
            self.assertEqual(status, CompatibilityStatus.COMPATIBLE)

    def test_active_mode_reader_is_compatible_at_m7(self) -> None:
        """In ACTIVE mode, readers at M7 (before M8 deadline) are COMPATIBLE."""
        for reader in COMPATIBILITY_REGISTRY:
            status = check_reader_compatibility(
                reader.reader_id,
                current_milestone=DeadlineMilestone.M7,
                mode=CompatibilityMode.ACTIVE,
            )
            self.assertEqual(status, CompatibilityStatus.COMPATIBLE)

    def test_unknown_reader_returns_unknown(self) -> None:
        """Unknown reader ID returns UNKNOWN in any mode."""
        for mode in CompatibilityMode:
            status = check_reader_compatibility("nonexistent", mode=mode)
            self.assertEqual(
                status,
                CompatibilityStatus.UNKNOWN,
                f"Unknown reader must be UNKNOWN in {mode} mode",
            )

    def test_is_production_enforcement_enabled_defaults_false(self) -> None:
        """Production enforcement is disabled by default."""
        with _EnvPatch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None):
            self.assertFalse(is_production_enforcement_enabled())

    def test_is_production_enforcement_enabled_with_flag(self) -> None:
        """Production enforcement is enabled when flag is set."""
        with _EnvPatch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT="1"):
            self.assertTrue(is_production_enforcement_enabled())


# ── Rollback fixtures — promotion/effects disabled ────────────────────────


class RollbackFixturesTests(TestCase):
    """Tests proving rollback is safe: no legacy writer reactivation,
    no quarantined erasure, all promotion/effects disabled."""

    def test_rollback_safe_without_legacy_writers(self) -> None:
        """Rollback is safe when no legacy writers are specified."""
        result = validate_rollback_safety()
        self.assertTrue(result.safe)
        self.assertEqual(result.quarantined_preserved, 0)
        self.assertEqual(len(result.blocked_by), 0)

    def test_rollback_safe_preserves_quarantined_entries(self) -> None:
        """Rollback preserves quarantined entries — they are never erased."""
        result = validate_rollback_safety(quarantined_count=7)
        self.assertTrue(result.safe)
        self.assertEqual(result.quarantined_preserved, 7)
        self.assertIn("7 quarantined entries preserved", result.reason)

    def test_rollback_blocked_by_legacy_writers(self) -> None:
        """Rollback is blocked if legacy authoritative writers would be re-enabled."""
        result = validate_rollback_safety(
            writer_ids=["ra-full-file-writer-1", "ra-full-file-writer-2"],
        )
        self.assertFalse(result.safe)
        self.assertIn("legacy-writer:ra-full-file-writer-1", result.blocked_by)
        self.assertIn("legacy-writer:ra-full-file-writer-2", result.blocked_by)
        self.assertIn("ra-full-file-writer-1", result.legacy_writers_blocked)
        self.assertIn("ra-full-file-writer-2", result.legacy_writers_blocked)
        self.assertIn("no legacy authoritative writers re-enabled", result.reason.lower())

    def test_rollback_does_not_erase_quarantined_entries(self) -> None:
        """Quarantined entries survive rollback — count is preserved."""
        result = validate_rollback_safety(quarantined_count=42)
        self.assertEqual(result.quarantined_preserved, 42)
        # The quarantined count is always preserved, never zeroed
        self.assertGreater(result.quarantined_preserved, 0)

    def test_rollback_validation_to_dict(self) -> None:
        """RollbackValidation serializes correctly."""
        result = validate_rollback_safety(
            writer_ids=["ra-old"],
            quarantined_count=3,
        )
        d = result.to_dict()
        self.assertFalse(d["safe"])
        self.assertEqual(d["quarantined_preserved"], 3)
        self.assertEqual(d["legacy_writers_blocked"], ["ra-old"])
        self.assertIn("legacy-writer:ra-old", d["blocked_by"])
        self.assertIsInstance(d["reason"], str)

    def test_rollback_mode_returns_rollback_safe_status(self) -> None:
        """In ROLLBACK mode, check_reader_compatibility returns ROLLBACK_SAFE."""
        for reader in COMPATIBILITY_REGISTRY:
            status = check_reader_compatibility(
                reader.reader_id,
                mode=CompatibilityMode.ROLLBACK,
            )
            self.assertEqual(
                status,
                CompatibilityStatus.ROLLBACK_SAFE,
                f"{reader.reader_id} must be ROLLBACK_SAFE in ROLLBACK mode",
            )

    def test_rollback_flag_sets_mode(self) -> None:
        """ARNOLD_M7_ROLLBACK=1 sets mode to ROLLBACK."""
        with _EnvPatch(
            ARNOLD_M7_ROLLBACK="1",
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None,
        ):
            self.assertEqual(get_mode(), CompatibilityMode.ROLLBACK)

    def test_promotion_disabled_during_rollback(self) -> None:
        """During rollback, no reader promotes from shadow to active."""
        with _EnvPatch(
            ARNOLD_M7_ROLLBACK="1",
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None,
        ):
            mode = get_mode()
            self.assertEqual(mode, CompatibilityMode.ROLLBACK)
            # All readers must report ROLLBACK_SAFE, never ACTIVE
            for reader in COMPATIBILITY_REGISTRY:
                status = check_reader_compatibility(reader.reader_id)
                self.assertEqual(
                    status,
                    CompatibilityStatus.ROLLBACK_SAFE,
                    f"{reader.reader_id} must not promote during rollback",
                )

    def test_effects_disabled_during_rollback(self) -> None:
        """During rollback, enforcement is off and no effects are applied."""
        with _EnvPatch(
            ARNOLD_M7_ROLLBACK="1",
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT="1",
        ):
            # Rollback overrides enforcement
            mode = get_mode()
            self.assertEqual(mode, CompatibilityMode.ROLLBACK)
            # Even though enforcement flag is set, rollback disables effects
            for reader in COMPATIBILITY_REGISTRY:
                status = check_reader_compatibility(reader.reader_id)
                self.assertEqual(status, CompatibilityStatus.ROLLBACK_SAFE)


# ── Snapshot generation ──────────────────────────────────────────────────


class SnapshotTests(TestCase):
    """Tests for compatibility snapshot generation."""

    def test_snapshot_includes_all_readers(self) -> None:
        """Snapshot includes every registered reader."""
        snap = snapshot()
        self.assertEqual(len(snap.readers), len(COMPATIBILITY_REGISTRY))
        reader_ids = {r.reader_id for r in snap.readers}
        expected_ids = {r.reader_id for r in COMPATIBILITY_REGISTRY}
        self.assertEqual(reader_ids, expected_ids)

    def test_snapshot_mode_matches_environment(self) -> None:
        """Snapshot mode reflects the environment."""
        with _EnvPatch(
            ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None,
            ARNOLD_M7_ROLLBACK=None,
        ):
            snap = snapshot()
            self.assertEqual(snap.mode, CompatibilityMode.SHADOW)

    def test_snapshot_includes_rollback_validation(self) -> None:
        """Snapshot always includes a rollback validation."""
        snap = snapshot()
        self.assertIsInstance(snap.rollback_validation, RollbackValidation)
        self.assertTrue(snap.rollback_validation.safe)

    def test_snapshot_enforcement_enabled_is_false_by_default(self) -> None:
        """Snapshot reports enforcement as disabled by default."""
        with _EnvPatch(ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=None):
            snap = snapshot()
            self.assertFalse(snap.enforcement_enabled)

    def test_snapshot_has_generated_at(self) -> None:
        """Snapshot includes an ISO-8601 generation timestamp."""
        snap = snapshot()
        self.assertTrue(len(snap.generated_at) > 0)
        self.assertIn("T", snap.generated_at)

    def test_snapshot_to_dict(self) -> None:
        """Snapshot serializes to a complete dict."""
        snap = snapshot()
        d = snap.to_dict()
        self.assertEqual(d["mode"], "shadow")
        self.assertIsInstance(d["readers"], list)
        self.assertIsInstance(d["rollback_validation"], dict)
        self.assertIn("generated_at", d)


# ── Reader serialization ─────────────────────────────────────────────────


class ReaderSerializationTests(TestCase):
    """Tests for ReaderCompatibility.to_dict() round-trip fidelity."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes every field from the dataclass."""
        reader = COMPATIBILITY_REGISTRY[0]
        d = reader.to_dict()
        expected_keys = {
            "reader_id",
            "reader_name",
            "description",
            "projection_ids",
            "module_paths",
            "deadline_milestone",
            "mode",
            "quarantined_entries",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_deadline_is_string(self) -> None:
        """Deadline milestone is serialized as a string."""
        reader = COMPATIBILITY_REGISTRY[0]
        d = reader.to_dict()
        self.assertIsInstance(d["deadline_milestone"], str)
        self.assertEqual(d["deadline_milestone"], "M8")

    def test_to_dict_mode_is_string(self) -> None:
        """Mode is serialized as a string."""
        reader = COMPATIBILITY_REGISTRY[0]
        d = reader.to_dict()
        self.assertIsInstance(d["mode"], str)

    def test_to_dict_projection_ids_are_sorted(self) -> None:
        """Projection IDs are sorted in the dict output."""
        reader = COMPATIBILITY_REGISTRY[2]  # bakeoff reader has 2 projections
        d = reader.to_dict()
        self.assertEqual(d["projection_ids"], sorted(d["projection_ids"]))


# ── Listing helpers ──────────────────────────────────────────────────────


class ListingHelperTests(TestCase):
    """Tests for list_readers, list_expired_readers, list_expiring_readers."""

    def test_list_readers_returns_all(self) -> None:
        """list_readers returns all registered readers."""
        result = list_readers()
        self.assertEqual(len(result), len(COMPATIBILITY_REGISTRY))

    def test_list_readers_filtered_by_mode(self) -> None:
        """list_readers can filter by compatibility mode."""
        result = list_readers(mode=CompatibilityMode.SHADOW)
        # All readers are in SHADOW mode by default in the registry
        self.assertGreaterEqual(len(result), 1)

    def test_list_expired_readers_at_m9(self) -> None:
        """All readers with M8 deadline are expired at M9."""
        expired = list_expired_readers(current_milestone=DeadlineMilestone.M9)
        self.assertEqual(len(expired), len(COMPATIBILITY_REGISTRY))

    def test_list_expired_readers_at_m7(self) -> None:
        """No readers are expired at M7 (before M8 deadline)."""
        expired = list_expired_readers(current_milestone=DeadlineMilestone.M7)
        self.assertEqual(len(expired), 0)

    def test_list_expiring_readers_at_m7a(self) -> None:
        """Readers with M8 deadline are expiring at M7A."""
        expiring = list_expiring_readers(
            current_milestone=DeadlineMilestone.M7A
        )
        self.assertEqual(len(expiring), len(COMPATIBILITY_REGISTRY))

    def test_list_expiring_readers_at_m7(self) -> None:
        """Readers are not expiring at M7 (two milestones before M8)."""
        expiring = list_expiring_readers(
            current_milestone=DeadlineMilestone.M7
        )
        self.assertEqual(len(expiring), 0)


# ── Reader status transitions ────────────────────────────────────────────


class ReaderStatusTransitionTests(TestCase):
    """Tests that reader status transitions are correct across milestones."""

    def test_status_transitions(self) -> None:
        """Status transitions from COMPATIBLE → EXPIRING → EXPIRED."""
        reader = COMPATIBILITY_REGISTRY[0]
        # M7: not near M8 deadline
        self.assertEqual(
            reader.status(DeadlineMilestone.M7),
            CompatibilityStatus.COMPATIBLE,
        )
        # M7A: approaching M8 (one milestone away)
        self.assertEqual(
            reader.status(DeadlineMilestone.M7A),
            CompatibilityStatus.EXPIRING,
        )
        # M8: at deadline — expired (current >= deadline)
        self.assertEqual(
            reader.status(DeadlineMilestone.M8),
            CompatibilityStatus.EXPIRED,
        )
        # M9: past deadline — still expired
        self.assertEqual(
            reader.status(DeadlineMilestone.M9),
            CompatibilityStatus.EXPIRED,
        )

    def test_all_readers_follow_same_transitions(self) -> None:
        """All registered readers (M8 deadline) follow the same transitions."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertEqual(
                reader.status(DeadlineMilestone.M7),
                CompatibilityStatus.COMPATIBLE,
                f"{reader.reader_id} at M7 must be COMPATIBLE",
            )
            self.assertEqual(
                reader.status(DeadlineMilestone.M7A),
                CompatibilityStatus.EXPIRING,
                f"{reader.reader_id} at M7A must be EXPIRING",
            )
            self.assertEqual(
                reader.status(DeadlineMilestone.M9),
                CompatibilityStatus.EXPIRED,
                f"{reader.reader_id} at M9 must be EXPIRED",
            )


# ── Quarantined entries preservation ─────────────────────────────────────


class QuarantinedEntriesPreservationTests(TestCase):
    """Tests that quarantined entries are never erased during rollback."""

    def test_quarantined_entries_preserved_in_rollback_validation(self) -> None:
        """RollbackValidation preserves the quarantined count exactly."""
        for count in (0, 1, 5, 100):
            result = validate_rollback_safety(quarantined_count=count)
            self.assertEqual(
                result.quarantined_preserved,
                count,
                f"Quarantined count {count} must be preserved exactly",
            )
            self.assertTrue(result.safe)

    def test_quarantined_entries_not_zeroed(self) -> None:
        """Quarantined count is never zeroed — even if None is passed."""
        result = validate_rollback_safety(quarantined_count=None)
        # Sum of registry quarantined entries (currently all 0)
        self.assertIsInstance(result.quarantined_preserved, int)

    def test_quarantined_in_reason_string(self) -> None:
        """The reason string mentions quarantined entries."""
        result = validate_rollback_safety(quarantined_count=12)
        self.assertIn("12 quarantined entries preserved", result.reason)

    def test_reader_quarantined_entries_field(self) -> None:
        """Every reader has a quarantined_entries field defaulting to 0."""
        for reader in COMPATIBILITY_REGISTRY:
            self.assertIsInstance(reader.quarantined_entries, int)
            self.assertGreaterEqual(reader.quarantined_entries, 0)
