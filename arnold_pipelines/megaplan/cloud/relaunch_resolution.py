"""Shared, fail-closed admission of persisted relaunch commands.

The command itself remains a shell-wrapper concern.  This module owns the
decision whether a command persisted in a session marker may be reused.
"""

from __future__ import annotations

from collections.abc import Mapping
import re


_STALE_MARKER_FRAGMENTS = (
    "source checkout dirty; using clean runtime mirror",
    "source checkout has local commits not contained in origin/",
    "attempting push",
    'git -C "$SRC" push origin',
    "pip install ",
    "pip3 install ",
    "python -m pip install ",
    "python3 -m pip install ",
    "git push ",
    "git pull ",
    "git fetch ",
    "git clone ",
    "git checkout ",
    "git switch ",
    "git reset ",
    "git merge ",
    "git rebase ",
    "git commit ",
    "rm ",
    "mv ",
    "cp ",
    "touch ",
    "mkdir ",
    "chmod ",
    "chown ",
    "tee ",
    "sed -i ",
    " >>",
    " >",
)


def is_stale_marker_relaunch_command(command: str) -> bool:
    """Return whether a persisted command must be regenerated."""
    value = str(command or "")
    if not value.strip():
        return True
    if any(fragment in value for fragment in _STALE_MARKER_FRAGMENTS):
        return True
    if "[megaplan-refresh] refusing editable install refresh:" in value:
        return True
    if re.search(
        r"git\s+(?:-C\s+\S+\s+)?(?:push|pull|fetch|clone|checkout|switch|reset|merge|rebase|commit)(?:\s|$)",
        value,
    ):
        return True
    return False


def relaunch_matches_runtime(
    command: str,
    identity: Mapping[str, object],
) -> bool:
    """Require a content-addressed relaunch command to name its bound runtime."""

    runtime_root = str(
        identity.get("import_root") or identity.get("editable_root") or ""
    ).strip()
    revision = str(
        identity.get("source_revision") or identity.get("editable_revision") or ""
    ).strip()
    if runtime_root and runtime_root not in command:
        return False
    if len(revision) == 40 and revision not in command:
        return False
    return True


def marker_relaunch_command(marker: Mapping[str, object]) -> str | None:
    """Return the marker command only when it is current and admissible."""
    command = str(
        marker.get("relaunch_command") or marker.get("launch_command") or ""
    ).strip()
    if is_stale_marker_relaunch_command(command):
        return None
    binding = marker.get("runtime_binding")
    identity = binding.get("current_identity") if isinstance(binding, Mapping) else None
    if isinstance(identity, Mapping) and not relaunch_matches_runtime(command, identity):
        # A content-addressed marker must relaunch the same immutable runtime.
        # Merely blacklist-checking the shell text admitted commands left over
        # from an earlier cutover.
        return None
    return command


__all__ = [
    "is_stale_marker_relaunch_command",
    "marker_relaunch_command",
    "relaunch_matches_runtime",
]
