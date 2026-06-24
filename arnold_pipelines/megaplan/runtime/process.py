"""Centralised subprocess spawning and process-group reaping for megaplan.

Public surface
--------------
spawn(*args, **kw)               → subprocess.Popen
spawn_async(*args, **kw)         → asyncio.subprocess.Process  (coroutine)
kill_group(proc, *, grace_s, escalate, label) → None

Pure primitives are re-exported from arnold.runtime.process.
Megaplan-specific helpers (megaplan_engine_root, megaplan_engine_env) live here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Re-export pure primitives from the neutral runtime layer.
from arnold.runtime.process import (  # noqa: F401
    OrphanDetectedError,
    TmuxSession,
    detect_orphans,
    kill_group,
    pane_pids,
    spawn,
    spawn_async,
    tmux_socket_for,
)


def megaplan_engine_root() -> Path:
    """Return the repository root for the currently imported Arnold engine.

    Honors ``MEGAPLAN_ENGINE_ROOT`` when set, so local worktree runs can
    point the isolation machinery at the editable engine checkout even when
    Python imports ``arnold`` from the target worktree directory.
    """
    explicit = os.environ.get("MEGAPLAN_ENGINE_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "arnold_pipelines"
        ).is_dir():
            return candidate

    raise RuntimeError(
        "Could not infer MEGAPLAN_ENGINE_ROOT from arnold_pipelines package path"
    )


def megaplan_engine_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return an env that resolves this engine before the target project."""
    env = dict(base or os.environ)
    engine_root = str(megaplan_engine_root())
    env["MEGAPLAN_ENGINE_ROOT"] = engine_root
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        engine_root if not existing else os.pathsep.join([engine_root, existing])
    )
    return env
