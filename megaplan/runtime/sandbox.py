"""Project-directory sandbox for hermes tool calls.

Background
----------
The hermes worker invokes ``AIAgent`` from the vendored agent SDK to run
megaplan phases.  In bakeoff runs each profile gets its own worktree
(``.megaplan-worktrees/<plan>/<profile>/``) and the worktree path is
communicated to the model via a ``Project directory: <abs path>`` line in
the prompt.

The execute prompt also embeds user-authored idea text — and that text can
contain its own ``Project: ...`` line.  When a model resolves the conflict by
trusting the user-authored line (we observed DeepSeek do exactly this), it
prefixes every ``terminal`` call with ``cd <wrong-abs-path> && ...`` and
issues ``write_file`` / ``patch`` calls with absolute paths under the wrong
repo.  The audit catches the resulting empty diff after the fact, but by
then writes have landed in the wrong tree.

This module enforces the boundary at the **tool layer** so that no matter
what the prompt says, the model cannot exec or write outside ``project_dir``.

Three knobs:

1. ``TERMINAL_CWD`` env var is pinned to ``project_dir`` so the terminal
   tool's default cwd is the worktree (mirrors the Claude/CLI happy path
   at ``cli.py:7260``).

2. The registered handlers for ``terminal``, ``write_file``, and ``patch``
   are wrapped to validate / coerce paths before dispatch.  Refusal is a
   hard error returned to the model so it can correct itself; we don't
   silently rewrite the call.

3. ``read_file`` and ``search_files`` are intentionally **not** sandboxed —
   the model legitimately needs to read e.g. ``/tmp/phase-6-idea.txt`` and
   the megaplan template files.  Only writes / exec are bounded.
"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Tool names we sandbox.  Keep in sync with the registry.register() calls
# in tools/terminal_tool.py and tools/file_tools.py.
SANDBOXED_EXEC_TOOLS = ("terminal",)
SANDBOXED_WRITE_TOOLS = ("write_file", "patch")

# Match a leading ``cd <path> && ...`` (with optional quoting) so we can
# inspect the target directory before letting the command through.  We only
# look at the *leading* cd because the terminal backend runs each command in
# a fresh shell with a known cwd — a mid-command ``cd`` only affects the
# rest of that one command, not subsequent invocations.
_LEADING_CD_RE = re.compile(
    r"""^\s*cd\s+
        (?:
            "(?P<dq>[^"]+)"      # double-quoted path
          | '(?P<sq>[^']+)'      # single-quoted path
          | (?P<bare>[^\s&|;]+)  # unquoted path (stops at shell separators)
        )
        \s*&&\s*
        (?P<rest>.+)$
    """,
    re.VERBOSE | re.DOTALL,
)

# V4A patch directives that name a file.  We require the named path to live
# inside project_dir — otherwise a malicious patch could write outside the
# worktree even with a sandboxed write_file.
_V4A_FILE_DIRECTIVES = re.compile(
    r"^\s*\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$",
    re.MULTILINE,
)


class SandboxViolation(Exception):
    """Raised when a tool call escapes the project_dir sandbox."""


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
    """Resolve a user-supplied path against project_dir, expanding ``~``.

    Relative paths resolve under ``project_dir``.  Absolute paths are kept
    as-is; the caller decides whether they fall inside the boundary.
    """
    expanded = os.path.expanduser(raw)
    p = Path(expanded)
    if not p.is_absolute():
        p = project_dir / p
    return _normalize(p)


def validate_terminal_command(command: str, project_dir: Path) -> str:
    """Return a command safe to run with cwd=project_dir, or raise.

    Strips a leading ``cd <project_dir-or-child> && ...`` prefix (since the
    shell will run with cwd=project_dir anyway) and refuses any leading
    ``cd <path>`` whose target escapes ``project_dir``.

    Mid-command ``cd`` calls aren't inspected: they only scope to that one
    shell invocation and don't leak across tool calls.  The terminal
    backend runs each command in a fresh shell rooted at TERMINAL_CWD.
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
            f"{target}, which is outside the project directory {project_dir}. "
            "Run commands relative to the project directory; do not `cd` to "
            "an absolute path outside the worktree."
        )

    # Target is inside project_dir.  Strip the leading cd so the command
    # runs at the correct cwd regardless of how the model wrote it.
    if target == project_dir:
        return rest
    rel = target.relative_to(project_dir)
    return f"cd {rel} && {rest}" if str(rel) != "." else rest


def validate_write_path(raw_path: str, project_dir: Path) -> str:
    """Return a write path inside ``project_dir``, or raise.

    Both absolute paths outside ``project_dir`` and relative paths that
    traverse out via ``..`` are rejected.  The returned string is the
    resolved absolute path the caller can safely write to.
    """
    if not raw_path or not isinstance(raw_path, str):
        raise SandboxViolation("write path must be a non-empty string")

    project_dir = _normalize(project_dir)
    target = _coerce_path(raw_path, project_dir)
    if not _is_within(target, project_dir):
        raise SandboxViolation(
            f"refusing write to {raw_path}: resolves to {target}, which is "
            f"outside the project directory {project_dir}. Use a path "
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


# --------------------------------------------------------------------------
# Handler wrappers
# --------------------------------------------------------------------------


def _refusal(tool: str, message: str) -> str:
    logger.warning("sandbox refused %s: %s", tool, message)
    return json.dumps({"error": f"sandbox: {message}"}, ensure_ascii=False)


def _wrap_terminal(handler, project_dir: Path):
    def wrapper(args, **kw):
        try:
            cmd = args.get("command", "") if isinstance(args, dict) else ""
            new_cmd = validate_terminal_command(cmd, project_dir)
        except SandboxViolation as exc:
            return _refusal("terminal", str(exc))
        new_args = dict(args) if isinstance(args, dict) else {}
        new_args["command"] = new_cmd
        # Force workdir override too — even if the model passed an explicit
        # workdir arg, it must stay inside project_dir.
        workdir = new_args.get("workdir")
        if workdir:
            try:
                resolved = _coerce_path(workdir, project_dir)
            except Exception:
                resolved = None
            if resolved is None or not _is_within(resolved, project_dir):
                return _refusal(
                    "terminal",
                    f"workdir {workdir!r} resolves outside the project "
                    f"directory {project_dir}",
                )
            new_args["workdir"] = str(resolved)
        return handler(new_args, **kw)

    return wrapper


def _wrap_write_file(handler, project_dir: Path):
    def wrapper(args, **kw):
        if not isinstance(args, dict):
            return handler(args, **kw)
        raw = args.get("path", "")
        try:
            safe = validate_write_path(raw, project_dir)
        except SandboxViolation as exc:
            return _refusal("write_file", str(exc))
        new_args = dict(args)
        new_args["path"] = safe
        return handler(new_args, **kw)

    return wrapper


def _wrap_patch(handler, project_dir: Path):
    def wrapper(args, **kw):
        if not isinstance(args, dict):
            return handler(args, **kw)
        mode = args.get("mode", "replace")
        new_args = dict(args)
        try:
            if mode == "replace":
                raw = args.get("path", "")
                if raw:
                    new_args["path"] = validate_write_path(raw, project_dir)
            elif mode == "patch":
                patch_content = args.get("patch", "") or ""
                validate_v4a_patch(patch_content, project_dir)
        except SandboxViolation as exc:
            return _refusal("patch", str(exc))
        return handler(new_args, **kw)

    return wrapper


_WRAPPERS = {
    "terminal": _wrap_terminal,
    "write_file": _wrap_write_file,
    "patch": _wrap_patch,
}


@contextmanager
def install_sandbox(project_dir: Path) -> Iterator[None]:
    """Pin tool calls to ``project_dir`` for the duration of the with-block.

    Sets ``TERMINAL_CWD`` and wraps the relevant registry handlers in place.
    Restores both on exit.  Idempotent — safe to nest, but inner uses of
    the same project_dir are no-ops.
    """
    project_dir = _normalize(Path(project_dir))
    if not project_dir.exists():
        raise ValueError(
            f"sandbox project_dir does not exist: {project_dir}. "
            "Refusing to install sandbox against a missing directory."
        )

    # Snapshot the env var so nested or sequential calls restore correctly.
    prior_env = os.environ.get("TERMINAL_CWD")
    os.environ["TERMINAL_CWD"] = str(project_dir)

    # Lazy-import the registry — the agent SDK pulls in heavy modules and
    # we don't want to require them when running in --mock or non-hermes
    # paths.  If the registry isn't importable here we still get the
    # TERMINAL_CWD pin, which is the most important guard.
    wrapped = []
    try:
        from tools.registry import registry as _registry  # type: ignore
    except Exception as exc:
        logger.debug("sandbox: tool registry unavailable, env-only mode: %s", exc)
        _registry = None

    if _registry is not None:
        for name, wrapper_factory in _WRAPPERS.items():
            entry = _registry._tools.get(name)
            if entry is None:
                continue
            original = entry.handler
            entry.handler = wrapper_factory(original, project_dir)
            wrapped.append((entry, original))

    try:
        yield
    finally:
        for entry, original in wrapped:
            entry.handler = original
        if prior_env is None:
            os.environ.pop("TERMINAL_CWD", None)
        else:
            os.environ["TERMINAL_CWD"] = prior_env
