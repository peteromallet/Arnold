"""Tests for ``save_state_merge_meta`` — the merge-on-save fix that prevents
silent data loss when ``override`` commands append to ``meta.notes`` /
``meta.overrides`` while a workflow phase holds the plan lock.

See ``megaplan/_core/state.py`` for the implementation and the long-form
explanation of the race condition this guards against.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from megaplan._core.io import atomic_write_json
from megaplan._core.state import save_state, save_state_merge_meta


def _read_state(plan_dir: Path) -> dict[str, Any]:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def _base_state() -> dict[str, Any]:
    return {
        "name": "plan-x",
        "current_state": "planned",
        "iteration": 1,
        "config": {"project_dir": "/tmp/proj"},
        "meta": {
            "notes": [],
            "overrides": [],
        },
        "history": [],
        "sessions": {},
        "plan_versions": [],
        "last_gate": {},
        "active_step": None,
    }


def _note(ts: str, body: str) -> dict[str, str]:
    return {"timestamp": ts, "note": body}


def _override(ts: str, action: str, *, note: str = "", reason: str = "") -> dict[str, str]:
    return {"timestamp": ts, "action": action, "note": note, "reason": reason}


def test_save_state_merge_preserves_concurrent_notes(tmp_path: Path) -> None:
    """Reproduces the race: phase loads state, override appends a note, phase
    saves with stale in-memory state. The override's note must survive."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    # Phase loads the in-memory state (no notes).
    in_memory = _base_state()
    in_memory["meta"]["notes"] = []
    save_state(plan_dir, in_memory)

    phase_snapshot = copy.deepcopy(in_memory)
    # Phase mutates non-meta state during its run.
    phase_snapshot["current_state"] = "critiqued"

    # Concurrently, an override appends a note directly to disk.
    on_disk = _read_state(plan_dir)
    concurrent_note = _note("2026-04-24T22:43:00Z", "operator note added during phase")
    on_disk["meta"]["notes"].append(concurrent_note)
    atomic_write_json(plan_dir / "state.json", on_disk)

    # Phase finishes and saves its stale snapshot. Without merge, the
    # concurrent note would be silently clobbered.
    save_state_merge_meta(plan_dir, phase_snapshot)

    final = _read_state(plan_dir)
    assert concurrent_note in final["meta"]["notes"], (
        "concurrent override note must survive merge-on-save"
    )
    assert final["current_state"] == "critiqued", (
        "non-merge fields should reflect in-memory phase state"
    )


def test_save_state_merge_preserves_concurrent_overrides(tmp_path: Path) -> None:
    """``meta.overrides`` is also append-only and must survive."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    in_memory = _base_state()
    save_state(plan_dir, in_memory)

    phase_snapshot = copy.deepcopy(in_memory)

    on_disk = _read_state(plan_dir)
    concurrent_override = _override(
        "2026-04-24T22:43:05Z", "add-note", note="appended mid-phase"
    )
    on_disk["meta"]["overrides"].append(concurrent_override)
    atomic_write_json(plan_dir / "state.json", on_disk)

    save_state_merge_meta(plan_dir, phase_snapshot)

    final = _read_state(plan_dir)
    assert concurrent_override in final["meta"]["overrides"]


def test_save_state_merge_dedupes_identical_notes(tmp_path: Path) -> None:
    """If the same note appears on disk and in memory, the merged list must
    contain it exactly once."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    duplicate = _note("2026-04-24T10:00:00Z", "shared note")

    on_disk_state = _base_state()
    on_disk_state["meta"]["notes"] = [duplicate]
    atomic_write_json(plan_dir / "state.json", on_disk_state)

    in_memory = _base_state()
    in_memory["meta"]["notes"] = [duplicate]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    assert final["meta"]["notes"] == [duplicate]


def test_save_state_merge_dedupes_identical_overrides(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    duplicate = _override(
        "2026-04-24T10:00:00Z", "abort", note="dup", reason="dup"
    )

    on_disk_state = _base_state()
    on_disk_state["meta"]["overrides"] = [duplicate]
    atomic_write_json(plan_dir / "state.json", on_disk_state)

    in_memory = _base_state()
    in_memory["meta"]["overrides"] = [duplicate]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    assert final["meta"]["overrides"] == [duplicate]


def test_save_state_merge_sorts_by_timestamp(tmp_path: Path) -> None:
    """Mixed-order notes from disk + memory must come out chronological."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    n1 = _note("2026-04-24T10:00:00Z", "first")
    n2 = _note("2026-04-24T11:00:00Z", "second")
    n3 = _note("2026-04-24T12:00:00Z", "third")
    n4 = _note("2026-04-24T13:00:00Z", "fourth")

    # Disk has n2 and n4; memory has n1 and n3 — interleaved.
    on_disk_state = _base_state()
    on_disk_state["meta"]["notes"] = [n4, n2]
    atomic_write_json(plan_dir / "state.json", on_disk_state)

    in_memory = _base_state()
    in_memory["meta"]["notes"] = [n3, n1]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    assert final["meta"]["notes"] == [n1, n2, n3, n4]


def test_save_state_preserves_non_merge_fields(tmp_path: Path) -> None:
    """Only ``meta.notes`` and ``meta.overrides`` are merged. Every other
    field — including other entries inside ``meta`` — must reflect the
    in-memory value."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    on_disk_state = _base_state()
    on_disk_state["current_state"] = "planned"
    on_disk_state["iteration"] = 1
    on_disk_state["meta"]["robustness"] = "standard"
    on_disk_state["meta"]["imported_decisions"] = ["disk-only"]
    on_disk_state["meta"]["notes"] = [_note("2026-04-24T08:00:00Z", "disk note")]
    atomic_write_json(plan_dir / "state.json", on_disk_state)

    in_memory = _base_state()
    in_memory["current_state"] = "critiqued"
    in_memory["iteration"] = 2
    in_memory["meta"]["robustness"] = "thorough"
    in_memory["meta"]["imported_decisions"] = ["memory-only"]
    in_memory["meta"]["notes"] = [_note("2026-04-24T09:00:00Z", "memory note")]
    in_memory["history"] = [{"step": "critique"}]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    # Non-merge fields take in-memory values.
    assert final["current_state"] == "critiqued"
    assert final["iteration"] == 2
    assert final["meta"]["robustness"] == "thorough"
    assert final["meta"]["imported_decisions"] == ["memory-only"]
    assert final["history"] == [{"step": "critique"}]
    # Merge fields are unioned.
    assert len(final["meta"]["notes"]) == 2
    note_bodies = {entry["note"] for entry in final["meta"]["notes"]}
    assert note_bodies == {"disk note", "memory note"}


def test_save_state_merge_handles_missing_state_file(tmp_path: Path) -> None:
    """First save (no on-disk state) must just write the in-memory copy."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    in_memory = _base_state()
    in_memory["meta"]["notes"] = [_note("2026-04-24T10:00:00Z", "first")]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    assert final["meta"]["notes"] == in_memory["meta"]["notes"]


def test_save_state_merge_handles_missing_meta_field(tmp_path: Path) -> None:
    """If on-disk state lacks ``meta.notes`` entirely, merge must not fail."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    on_disk_state = _base_state()
    on_disk_state["meta"].pop("notes", None)
    atomic_write_json(plan_dir / "state.json", on_disk_state)

    in_memory = _base_state()
    note = _note("2026-04-24T10:00:00Z", "added")
    in_memory["meta"]["notes"] = [note]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    assert final["meta"]["notes"] == [note]


def test_save_state_merge_distinguishes_same_timestamp_different_bodies(tmp_path: Path) -> None:
    """Two notes that share a timestamp but have different bodies must both
    survive the merge — the dedup key includes a hash of the body."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    ts = "2026-04-24T10:00:00Z"
    a = _note(ts, "first body")
    b = _note(ts, "second body")

    on_disk_state = _base_state()
    on_disk_state["meta"]["notes"] = [a]
    atomic_write_json(plan_dir / "state.json", on_disk_state)

    in_memory = _base_state()
    in_memory["meta"]["notes"] = [b]

    save_state_merge_meta(plan_dir, in_memory)

    final = _read_state(plan_dir)
    bodies = sorted(entry["note"] for entry in final["meta"]["notes"])
    assert bodies == ["first body", "second body"]
