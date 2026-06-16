"""Tests for watchdog orphan-process detection."""

from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan.watchdog.correlate import Correlation
from arnold.pipelines.megaplan.watchdog.orphans import find_orphan_processes


def _proc(pid: int, ppid: int, elapsed: float, category: str, cmdline: str = ""):
    class _P:
        pass

    p = _P()
    p.pid = pid
    p.ppid = ppid
    p.elapsed_seconds = elapsed
    p.category = category
    p.cmdline = cmdline
    return p


def test_find_orphan_when_parent_is_init():
    processes = (_proc(100, 1, 7200, "tmux", "tmux new-session -d -s s1"),)
    correlations = (Correlation(Path("/tmp/.megaplan/plans/p1"), 100, "cmdline_plan_path"),)
    result = find_orphan_processes(processes, correlations)
    assert len(result[Path("/tmp/.megaplan/plans/p1")]) == 1
    assert result[Path("/tmp/.megaplan/plans/p1")][0].pid == 100


def test_find_orphan_when_parent_missing():
    processes = (_proc(200, 99999, 7200, "shannon"),)
    correlations = (Correlation(Path("/tmp/.megaplan/plans/p1"), 200, "cwd_match"),)
    result = find_orphan_processes(processes, correlations)
    assert len(result[Path("/tmp/.megaplan/plans/p1")]) == 1
    assert result[Path("/tmp/.megaplan/plans/p1")][0].pid == 200


def test_no_orphan_when_parent_alive():
    # tmux server pid 100 is supervised by pid 50 (alive); child shannon is fine.
    processes = (
        _proc(50, 1, 7200, "launchd"),
        _proc(100, 50, 7200, "tmux"),
        _proc(200, 100, 7200, "shannon"),
    )
    correlations = (Correlation(Path("/tmp/.megaplan/plans/p1"), 200, "cwd_match"),)
    result = find_orphan_processes(processes, correlations)
    assert Path("/tmp/.megaplan/plans/p1") not in result


def test_no_orphan_when_too_young():
    processes = (_proc(100, 1, 60, "tmux"),)
    correlations = (Correlation(Path("/tmp/.megaplan/plans/p1"), 100, "cmdline_plan_path"),)
    result = find_orphan_processes(processes, correlations, min_age_seconds=3600)
    assert Path("/tmp/.megaplan/plans/p1") not in result


def test_orphan_ancestor_tmux_server():
    # tmux server pid 100 is detached (ppid=1) and old; child shannon pid 200 is trapped.
    processes = (
        _proc(100, 1, 7200, "tmux", "tmux new-session -d -s s1"),
        _proc(200, 100, 7200, "shannon"),
    )
    correlations = (Correlation(Path("/tmp/.megaplan/plans/p1"), 200, "cmdline_plan_path"),)
    result = find_orphan_processes(processes, correlations)
    orphans = result[Path("/tmp/.megaplan/plans/p1")]
    assert len(orphans) == 1
    assert orphans[0].pid == 200
    assert "ancestor tmux server" in orphans[0].reason
