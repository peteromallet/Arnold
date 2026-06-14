"""Tests for ``arnold.runtime.resume`` (T3 / SC3)."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from arnold.runtime.resume import (
    TRUST_QUARANTINED_MANIFEST_MISMATCH,
    TRUST_TRUSTED,
    TRUST_UNKNOWN,
    ResumeCursorRef,
    TrustTransition,
    migrate_legacy_resume,
)


_CURRENT_HASH = "sha256:current-manifest"


def _malformed_states() -> list[object]:
    """Enumerate the malformed-state cases the contract must absorb."""
    return [
        # Non-mapping inputs
        None,
        "",
        "not-a-mapping",
        123,
        [],
        # Mapping missing identifiers
        {},
        {"plugin_id": "p"},  # missing run_id
        {"run_id": "r"},  # missing plugin_id
        # Non-string identifiers
        {"plugin_id": 5, "run_id": "r", "manifest_hash": _CURRENT_HASH},
        {"plugin_id": "p", "run_id": None, "manifest_hash": _CURRENT_HASH},
        # Empty-string identifiers
        {"plugin_id": "", "run_id": "r", "manifest_hash": _CURRENT_HASH},
        {"plugin_id": "p", "run_id": "", "manifest_hash": _CURRENT_HASH},
        # Missing manifest hash entirely (and no alias)
        {"plugin_id": "p", "run_id": "r"},
        # Non-string manifest hash
        {"plugin_id": "p", "run_id": "r", "manifest_hash": 12345},
    ]


class TestMalformedReturnsUnknownUnknown:
    @pytest.mark.parametrize("legacy", _malformed_states())
    def test_malformed_returns_none_and_unknown_unknown(self, legacy: object) -> None:
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is None
        assert transition == TrustTransition(TRUST_UNKNOWN, TRUST_UNKNOWN)
        assert transition.before == "unknown"
        assert transition.after == "unknown"


class TestLegacyKeyAcceptance:
    def test_accepts_legacy_phase_key(self) -> None:
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_hash": _CURRENT_HASH,
            "phase": "some-phase-name",
            "user_data": {"x": 1},
        }
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is not None
        assert isinstance(cursor, ResumeCursorRef)
        assert cursor.plugin_id == "p-1"
        assert cursor.run_id == "r-1"
        # Excluded from payload
        assert "phase" not in cursor.cursor
        # Non-step-identifier data preserved
        assert cursor.cursor["user_data"] == {"x": 1}
        assert transition == TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED)

    def test_accepts_legacy_stage_key(self) -> None:
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_hash": _CURRENT_HASH,
            "stage": "some-stage-name",
            "user_data": {"y": 2},
        }
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is not None
        assert "stage" not in cursor.cursor
        assert cursor.cursor["user_data"] == {"y": 2}
        assert transition.after == TRUST_TRUSTED

    def test_accepts_both_phase_and_stage_keys(self) -> None:
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_hash": _CURRENT_HASH,
            "phase": "p-name",
            "stage": "s-name",
            "user_data": {"z": 3},
        }
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is not None
        assert "phase" not in cursor.cursor
        assert "stage" not in cursor.cursor
        assert cursor.cursor["user_data"] == {"z": 3}
        assert transition.after == TRUST_TRUSTED


class TestManifestHashMismatchEmitsQuarantine:
    def test_manifest_hash_mismatch_emits_quarantined_manifest_mismatch(self) -> None:
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_hash": "sha256:stale",
            "phase": "any",
            "user_data": {"k": "v"},
        }
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is not None
        assert transition.before == TRUST_UNKNOWN
        assert transition.after == TRUST_QUARANTINED_MANIFEST_MISMATCH
        assert transition.after == "quarantined-manifest-mismatch"

    def test_alias_manifest_sha256_accepted(self) -> None:
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_sha256": _CURRENT_HASH,
            "stage": "x",
        }
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is not None
        assert transition.after == TRUST_TRUSTED


class TestIdempotentOnAlreadyMigratedState:
    def test_idempotent_when_runtime_envelope_block_present(self) -> None:
        legacy = {
            "runtime_envelope": {
                "plugin_id": "p-1",
                "run_id": "r-1",
                "resume_cursor": {"step": "x", "offset": 7},
            },
            # Stale top-level data the function should ignore
            "phase": "legacy-name",
            "stage": "legacy-stage",
        }
        cursor, transition = migrate_legacy_resume(
            legacy, current_manifest_hash=_CURRENT_HASH
        )
        assert cursor is not None
        assert cursor.plugin_id == "p-1"
        assert cursor.run_id == "r-1"
        assert cursor.cursor == {"step": "x", "offset": 7}
        assert transition.after == TRUST_TRUSTED

    def test_idempotent_call_twice_same_result(self) -> None:
        legacy = {
            "runtime_envelope": {
                "plugin_id": "p-1",
                "run_id": "r-1",
                "resume_cursor": {"offset": 0},
            },
        }
        first = migrate_legacy_resume(legacy, current_manifest_hash=_CURRENT_HASH)
        second = migrate_legacy_resume(legacy, current_manifest_hash=_CURRENT_HASH)
        assert first == second


class TestNeverWritesState:
    def test_pure_function_does_not_mutate_input(self) -> None:
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_hash": _CURRENT_HASH,
            "phase": "x",
            "user_data": {"k": "v"},
        }
        snapshot = deepcopy(legacy)
        migrate_legacy_resume(legacy, current_manifest_hash=_CURRENT_HASH)
        assert legacy == snapshot

    def test_pure_function_does_not_write_state_file(self, tmp_path) -> None:
        # The function takes a dict, not a path; assert there are no
        # filesystem side-effects by writing a fixture and confirming
        # mtime does not change after the call.
        state_path = tmp_path / "state.json"
        legacy = {
            "plugin_id": "p-1",
            "run_id": "r-1",
            "manifest_hash": _CURRENT_HASH,
            "phase": "x",
        }
        state_path.write_text(json.dumps(legacy))
        mtime_before = state_path.stat().st_mtime_ns

        # Load fresh and pass dict — the function never touches the file
        loaded = json.loads(state_path.read_text())
        migrate_legacy_resume(loaded, current_manifest_hash=_CURRENT_HASH)

        mtime_after = state_path.stat().st_mtime_ns
        assert mtime_before == mtime_after
