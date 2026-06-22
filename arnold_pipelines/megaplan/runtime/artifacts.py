"""Megaplan-specific versioned-artifact helpers.

These helpers are independent of any particular Step class — they resolve
the next version number in a stage directory. They are used by AgentStep /
PanelReviewerStep / GateStep / HumanDecisionStep and by the run_cli
human-gate resume path.

Rehomed from ``arnold_pipelines.megaplan._pipeline.step_helpers`` during M3
burn-down (T15).  Arnold's :mod:`arnold.pipeline.artifacts` has a different
signature for ``next_version`` (``ctx, stage, label, suffix`` vs a plain
``Path``), so these Megaplan-specific helpers stay in a Megaplan-owned
responsibility-named module.
"""

from __future__ import annotations

from pathlib import Path


def latest_artifact(stage_dir: Path) -> Path | None:
    """Return the highest-versioned artifact in *stage_dir*, or None."""
    if not stage_dir.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for child in stage_dir.iterdir():
        if child.is_file() and child.name.startswith("v"):
            stem = child.stem
            if stem[1:].isdigit():
                candidates.append((int(stem[1:]), child))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def next_version(output_dir: Path) -> int:
    """Return the next version number for *output_dir*."""
    if not output_dir.is_dir():
        return 1
    max_v = 0
    for child in output_dir.iterdir():
        if child.is_file() and child.name.startswith("v"):
            stem = child.stem
            if stem[1:].isdigit():
                max_v = max(max_v, int(stem[1:]))
    return max_v + 1
