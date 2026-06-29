"""Pure path-validation primitives for sandboxing tool calls.

This module provides the boundary-neutral layer:

* ``SANDBOX_CWD`` ContextVar — set by the activation context.
* ``get_sandbox_cwd()`` — read the active sandbox root.
* ``SandboxViolation`` — raised when a path escapes the active root.
* ``validate_terminal_command`` — strip safe leading cd, refuse escaping ones.
* ``validate_write_path`` — resolve a write path; raise if it escapes root.
* ``validate_v4a_patch`` — validate all file directives in a patch string.

Tool wrapper installation (registry integration) lives in the plugin layer
and is not part of this module.
"""

from __future__ import annotations

import os
import re
from contextvars import ContextVar
from pathlib import Path

from arnold.runtime.errors import ArnoldError

# Tool names we sandbox.
SANDBOXED_EXEC_TOOLS = ("terminal",)
SANDBOXED_WRITE_TOOLS = ("write_file", "patch")

# Match a leading ``cd <path> && ...`` so we can inspect the target directory.
_LEADING_CD_RE = re.compile(
    r"""^\s*cd\s+
        (?:
            "(?P<dq>[^"]+)"      # double-quoted path
          | '(?P<sq>[^']+)'      # single-quoted path
          | (?P<bare>[^\s&|;]+)  # unquoted path
        )
        \s*&&\s*
        (?P<rest>.+)$
    """,
    re.VERBOSE | re.DOTALL,
)

# V4A patch directives that name a file.
_V4A_FILE_DIRECTIVES = re.compile(
    r"^\s*\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Context-local sandbox CWD
# ---------------------------------------------------------------------------

SANDBOX_CWD: ContextVar[Path | None] = ContextVar("sandbox_cwd", default=None)


def get_sandbox_cwd() -> Path | None:
    """Return the active sandbox project_dir, or None if no sandbox active."""
    return SANDBOX_CWD.get()


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class SandboxViolation(ArnoldError):
    """Raised when a tool call escapes the project_dir sandbox."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__("sandbox_violation", message, exit_code=exit_code)


# ---------------------------------------------------------------------------
# Pure path helpers
# ---------------------------------------------------------------------------


def _normalize(path: Path) -> Path:
    """Resolve symlinks where possible; fall back to absolute form."""
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path.absolute()


def _is_within(candidate: Path, root: Path) -> bool:
    """Return True iff ``candidate`` is ``root`` or a descendant."""
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _coerce_path(raw: str, project_dir: Path) -> Path:
    """Resolve a user-supplied path against project_dir, expanding ``~``."""
    expanded = os.path.expanduser(raw)
    p = Path(expanded)
    if not p.is_absolute():
        p = project_dir / p
    return _normalize(p)


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------


def validate_terminal_command(command: str, project_dir: Path) -> str:
    """Return a command safe to run with cwd=project_dir, or raise.

    Strips a leading ``cd <project_dir-or-child> && ...`` prefix and refuses
    any leading ``cd <path>`` whose target escapes ``project_dir``.
    """
    if not isinstance(command, str):
        raise SandboxViolation("terminal command must be a string")

    project_dir = _normalize(project_dir)
    match = _LEADING_CD_RE.match(command)
    if not match:
        return command

    target_raw = match.group("dq") or match.group("sq") or match.group("bare")
    rest = match.group("rest")
    target = _coerce_path(target_raw, project_dir)

    if not _is_within(target, project_dir):
        raise SandboxViolation(
            f"refusing terminal command: leading `cd {target_raw}` targets "
            f"{target}, which is outside the sandbox root/project directory {project_dir}. "
            "Run commands relative to the project directory; do not `cd` to "
            "an absolute path outside the worktree."
        )

    if target == project_dir:
        return rest
    rel = target.relative_to(project_dir)
    return f"cd {rel} && {rest}" if str(rel) != "." else rest


def validate_write_path(raw_path: str, project_dir: Path) -> str:
    """Return a write path inside ``project_dir``, or raise."""
    if not raw_path or not isinstance(raw_path, str):
        raise SandboxViolation("write path must be a non-empty string")

    project_dir = _normalize(project_dir)
    target = _coerce_path(raw_path, project_dir)
    if not _is_within(target, project_dir):
        raise SandboxViolation(
            f"refusing write to {raw_path}: resolves to {target}, which is "
            f"outside the sandbox root/project directory {project_dir}. Use a path "
            "relative to the project directory or an absolute path within it."
        )
    return str(target)


def validate_v4a_patch(patch_content: str, project_dir: Path) -> None:
    """Raise if any *** {Update,Add,Delete} File: directive escapes project_dir."""
    if not isinstance(patch_content, str):
        raise SandboxViolation("patch content must be a string")
    project_dir = _normalize(project_dir)
    for match in _V4A_FILE_DIRECTIVES.finditer(patch_content):
        validate_write_path(match.group(1), project_dir)


__all__ = [
    "SANDBOX_CWD",
    "SANDBOXED_EXEC_TOOLS",
    "SANDBOXED_WRITE_TOOLS",
    "SandboxViolation",
    "get_sandbox_cwd",
    "validate_terminal_command",
    "validate_write_path",
    "validate_v4a_patch",
]
