"""Sandbox wrapper installation machinery for the tool registry.

Installs path-validation wrappers on terminal, write_file, and patch handlers
so that no model call can write or execute outside the active project_dir.

The boundary-neutral primitives (SANDBOX_CWD, SandboxViolation, validate_*)
live in arnold.runtime.sandbox; this module adds the tool-registry integration
(wrapper factories + install_sandbox context manager).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from arnold.runtime.sandbox import (
    SANDBOX_CWD,
    SandboxViolation,
    get_sandbox_cwd,
    validate_terminal_command,
    validate_v4a_patch,
    validate_write_path,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Private path helpers used by the tool wrappers below.
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
# Wrapper installation guard (idempotent with lock + marker attributes)
# ---------------------------------------------------------------------------

_wrappers_installed = False
_wrappers_lock = threading.Lock()
_wrapped_originals: dict[str, object] = {}


def _ensure_wrappers_installed():
    """Install sandbox wrappers on tool registry handlers exactly once.

    Idempotent — safe to call from any thread at any time.  Uses a
    module-level lock to avoid races during first installation.
    """
    global _wrappers_installed
    if _wrappers_installed:
        return
    with _wrappers_lock:
        if _wrappers_installed:
            return
        try:
            from arnold.agent.tools.registry import registry as _registry  # type: ignore
        except Exception as exc:
            logger.debug(
                "sandbox: tool registry unavailable, wrapper installation skipped: %s",
                exc,
            )
            _wrappers_installed = True
            return

        for name, wrapper_factory in _WRAPPERS.items():
            entry = _registry._tools.get(name)
            if entry is None:
                continue
            if name in _wrapped_originals:
                continue
            original = entry.handler
            entry.handler = wrapper_factory(original)
            _wrapped_originals[name] = original
        _wrappers_installed = True


def _unwrap_all_for_tests():
    """Remove sandbox wrappers from all registered tool handlers.

    This is a test helper.  It reverts handlers to their originals stored
    in the ``_sandbox_original`` marker attribute and clears the
    ``_sandbox_wrapped`` flag so tests that monkeypatch fake registries
    don't carry stale wrapped state between tests.
    """
    global _wrappers_installed
    try:
        from arnold.agent.tools.registry import registry as _registry  # type: ignore
    except Exception:
        _wrappers_installed = False
        _wrapped_originals.clear()
        return
    for name in _WRAPPERS:
        entry = _registry._tools.get(name)
        if entry is None:
            continue
        original = _wrapped_originals.get(name)
        if original is not None:
            entry.handler = original
    _wrapped_originals.clear()
    _wrappers_installed = False


# --------------------------------------------------------------------------
# Handler wrappers (active only when sandbox cwd is set)
# --------------------------------------------------------------------------


def _refusal(tool: str, message: str) -> str:
    logger.warning("sandbox refused %s: %s", tool, message)
    return json.dumps({"error": f"sandbox: {message}"}, ensure_ascii=False)


def _wrap_terminal(handler):
    """Wrap a terminal handler so it validates commands against the active
    sandbox cwd.  If no sandbox cwd is active, delegates to the original
    handler unchanged.
    """
    def wrapper(args, **kw):
        project_dir = get_sandbox_cwd()
        if project_dir is None:
            return handler(args, **kw)
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

    # Store the original so tests can unwrap
    wrapper._sandbox_original = handler
    return wrapper


def _wrap_write_file(handler):
    """Wrap a write_file handler to validate paths against the active
    sandbox cwd.  Delegates unchanged when no sandbox is active.
    """
    def wrapper(args, **kw):
        project_dir = get_sandbox_cwd()
        if project_dir is None:
            return handler(args, **kw)
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

    wrapper._sandbox_original = handler
    return wrapper


def _wrap_patch(handler):
    """Wrap a patch handler to validate paths against the active sandbox
    cwd.  Delegates unchanged when no sandbox is active.
    """
    def wrapper(args, **kw):
        project_dir = get_sandbox_cwd()
        if project_dir is None:
            return handler(args, **kw)
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

    wrapper._sandbox_original = handler
    return wrapper


_WRAPPERS = {
    "terminal": _wrap_terminal,
    "write_file": _wrap_write_file,
    "patch": _wrap_patch,
}


@contextmanager
def install_sandbox(project_dir: Path) -> Iterator[None]:
    """Pin tool calls to ``project_dir`` for the duration of the with-block.

    Sets the ``SANDBOX_CWD`` ContextVar so that tool wrappers (installed
    once at first use) validate/coerce paths against the given project_dir.

    Wrappers are installed once (idempotent with lock + markers) and
    remain permanently installed across sandbox activations.  When no
    sandbox is active (ContextVar is None), wrappers delegate unchanged
    to the original handlers.

    This design is concurrent-safe: multiple threads can call
    ``install_sandbox`` with different ``project_dir`` values and each
    thread's wrappers will see only its own ContextVar value.
    """
    project_dir = _normalize(Path(project_dir))
    if not project_dir.exists():
        raise ValueError(
            f"sandbox project_dir does not exist: {project_dir}. "
            "Refusing to install sandbox against a missing directory."
        )

    # Install wrappers once, idempotently.
    _ensure_wrappers_installed()

    # Set the ContextVar for this context (thread-safe).
    token = SANDBOX_CWD.set(project_dir)
    try:
        yield
    finally:
        SANDBOX_CWD.reset(token)
