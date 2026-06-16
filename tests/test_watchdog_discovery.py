"""Tests for watchdog plan discovery."""

from __future__ import annotations

import json

from arnold.pipelines.megaplan.watchdog.discovery import DEFAULT_SCAN_ROOTS, discover_plans


def test_scanner_discovers_plans_across_all_roots(tmp_path):
    # Simulate multiple roots, including overlapping /tmp and /private/tmp.
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_private = tmp_path / "private"
    root_public = root_private / "tmp"  # symlink-like overlap

    for plan_dir in (
        root_a / ".megaplan" / "plans" / "plan-a",
        root_b / ".megaplan" / "plans" / "plan-b",
        root_public / ".megaplan" / "plans" / "plan-c",
    ):
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(json.dumps({"current_state": "planned"}))

    # Also create a non-state directory that should be ignored.
    (root_a / ".megaplan" / "plans" / "empty").mkdir(parents=True)

    roots = (
        str(root_a),
        str(root_b),
        str(root_public),
        str(root_private / "tmp"),  # same as root_public after resolve
    )
    plans = discover_plans(roots)
    names = {p.name for p in plans}
    assert names == {"plan-a", "plan-b", "plan-c"}


def test_default_scan_roots_is_five_entries():
    assert len(DEFAULT_SCAN_ROOTS) == 5
    assert "~/Documents" in DEFAULT_SCAN_ROOTS
    assert "/tmp" in DEFAULT_SCAN_ROOTS
    assert "/private/tmp" in DEFAULT_SCAN_ROOTS


def test_missing_root_skipped_silently(tmp_path):
    roots = (str(tmp_path / "does-not-exist"),)
    assert discover_plans(roots) == ()
