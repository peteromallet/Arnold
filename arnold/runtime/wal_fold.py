"""Stub for arnold.runtime.wal_fold — restored for import compatibility.

The deliberation pipeline was archived and restored; its WAL-fold dependency
no longer exists in the current runtime. This stub provides the minimal surface
needed to keep restored deliberation tests importable.
"""

from __future__ import annotations

from typing import Any


def fold_journal(*args: Any, **kwargs: Any) -> Any:
    """Stub: WAL journal fold (not available in current runtime)."""
    return {}


def last_state_snapshot_projector(*args: Any, **kwargs: Any) -> Any:
    """Stub: snapshot projector (not available in current runtime)."""
    return lambda state: state
