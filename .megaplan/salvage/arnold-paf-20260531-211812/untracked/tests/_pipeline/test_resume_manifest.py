"""Tests for ResumeCursor manifest_hash plumbing (M5a T10).

Four contract units:
1. flag-OFF parity: load() returns cursor unchanged (no resume_policy key).
2. flag-ON match: current_manifest equals stored hash → no refuse.
3. flag-ON mismatch: current_manifest differs from stored hash → refuse.
4. flag-ON + current_manifest=None: identical behaviour to flag-OFF.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._pipeline.resume import ResumeCursor


def _write_state(plan_dir: Path, manifest_hash: str | None = None) -> None:
    cursor: dict = {"phase": "execute"}
    if manifest_hash is not None:
        cursor["manifest_hash"] = manifest_hash
    (plan_dir / "state.json").write_text(json.dumps({"resume_cursor": cursor}))


# ── 1. flag-OFF parity ────────────────────────────────────────────────────


def test_flag_off_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH unset, load() is behaviourally identical
    to the pre-T10 implementation — no resume_policy key inserted, manifest_hash
    preserved on the cursor, existing payload passed through unchanged."""
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    _write_state(tmp_path, manifest_hash="abc123")

    cursor = ResumeCursor.load(tmp_path, current_manifest="different-hash")

    assert cursor is not None
    assert cursor.stage == "execute"
    assert cursor.manifest_hash == "abc123"
    assert "resume_policy" not in cursor.payload


# ── 2. flag-ON match ──────────────────────────────────────────────────────


def test_flag_on_match_no_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH=1, if current_manifest equals the stored
    manifest_hash, no resume_policy='refuse' is injected."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    _write_state(tmp_path, manifest_hash="abc123")

    cursor = ResumeCursor.load(tmp_path, current_manifest="abc123")

    assert cursor is not None
    assert cursor.stage == "execute"
    assert cursor.manifest_hash == "abc123"
    assert "resume_policy" not in cursor.payload


# ── 3. flag-ON mismatch ───────────────────────────────────────────────────


def test_flag_on_mismatch_sets_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH=1, if current_manifest differs from the
    stored manifest_hash, payload['resume_policy'] is set to 'refuse'."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    _write_state(tmp_path, manifest_hash="old-hash")

    cursor = ResumeCursor.load(tmp_path, current_manifest="new-hash")

    assert cursor is not None
    assert cursor.stage == "execute"
    assert cursor.manifest_hash == "old-hash"
    assert cursor.payload.get("resume_policy") == "refuse"


# ── 4. flag-ON + current_manifest=None ───────────────────────────────────


def test_flag_on_current_manifest_none_is_identical_to_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With MEGAPLAN_UNIFIED_DISPATCH=1, passing current_manifest=None must NOT
    set resume_policy='refuse' — identical outcome to flag-OFF."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    _write_state(tmp_path, manifest_hash="abc123")

    cursor = ResumeCursor.load(tmp_path, current_manifest=None)

    assert cursor is not None
    assert cursor.stage == "execute"
    assert cursor.manifest_hash == "abc123"
    assert "resume_policy" not in cursor.payload
