"""Tmux session / orphan enrichment for the live watchdog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.runtime.process import TmuxSession, detect_orphans


@dataclass(frozen=True)
class TmuxInfo:
    session_names: tuple[str, ...]
    orphans: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_names": list(self.session_names),
            "orphans": list(self.orphans),
        }


def _plan_session_patterns(plan_dir: Path) -> list[str]:
    """Generate likely tmux session patterns for a plan directory."""
    name = plan_dir.name
    return [name, f"{name}*", f"*{name}*"]


def enrich_with_tmux(
    processes: tuple[Any, ...],
    plan_dirs: tuple[Path, ...],
) -> dict[Path, TmuxInfo]:
    """Discover tmux sessions and orphans associated with each plan directory.

    Returns a mapping from plan directory to ``TmuxInfo``. The implementation
    gracefully degrades when tmux is not installed.
    """
    result: dict[Path, TmuxInfo] = {}
    for plan_dir in plan_dirs:
        sessions: list[str] = []
        orphans: list[str] = []
        for pattern in _plan_session_patterns(plan_dir):
            try:
                orphan_matches = detect_orphans(pattern)
            except Exception:
                orphan_matches = []
            for session_name in orphan_matches:
                if session_name not in sessions and session_name not in orphans:
                    try:
                        if TmuxSession(session_name).exists():
                            sessions.append(session_name)
                        else:
                            orphans.append(session_name)
                    except Exception:
                        orphans.append(session_name)
        result[plan_dir] = TmuxInfo(
            session_names=tuple(sessions),
            orphans=tuple(orphans),
        )
    return result


__all__ = [
    "TmuxInfo",
    "enrich_with_tmux",
]
