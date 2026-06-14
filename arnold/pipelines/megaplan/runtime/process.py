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
)


def megaplan_engine_root() -> Path:
    """Return the repository root for the currently imported Arnold engine."""
    return Path(__file__).resolve().parents[4]


def megaplan_engine_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return an env that resolves this engine before the target project."""
    env = dict(base or os.environ)
    engine_root = str(megaplan_engine_root())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        engine_root if not existing else os.pathsep.join([engine_root, existing])
    )
    return env
