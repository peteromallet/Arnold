"""Filesystem plan discovery for the live watchdog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "~/Documents",
    "~/Documents/.megaplan-worktrees",
    "~/.megaplan-worktrees",
    "/tmp",
    "/private/tmp",
)


def _resolve_roots(roots: Iterable[str]) -> list[Path]:
    """Expand user dirs and dedupe by canonical path (handles /tmp ↔ /private/tmp)."""
    seen: set[Path] = set()
    result: list[Path] = []
    for root in roots:
        path = Path(root).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _state_path_to_plan_dir(state_path: Path) -> Path:
    return state_path.parent


def discover_plans(roots: Iterable[str] | None = None) -> tuple[Path, ...]:
    """Find ``.megaplan/plans/*/state.json`` recursively under the configured roots.

    Missing roots are silently skipped. Overlapping roots are deduplicated by
    canonical resolved path.
    """
    if roots is None:
        roots = DEFAULT_SCAN_ROOTS

    resolved = _resolve_roots(roots)
    seen: set[Path] = set()
    plans: list[Path] = []

    for root in resolved:
        if not root.exists():
            continue
        for state_file in root.glob("**/.megaplan/plans/*/state.json"):
            plan_dir = state_file.parent
            canonical = plan_dir.resolve()
            if canonical in seen:
                continue
            seen.add(canonical)
            plans.append(canonical)

    return tuple(plans)


def read_plan_state(plan_dir: Path) -> dict | None:
    """Read a plan's ``state.json`` directly, returning None if unreadable."""
    state_file = plan_dir / "state.json"
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None


__all__ = [
    "DEFAULT_SCAN_ROOTS",
    "discover_plans",
    "read_plan_state",
]
