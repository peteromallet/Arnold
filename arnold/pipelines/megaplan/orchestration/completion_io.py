"""Atomic read/write of ``completion_verdict.json`` in the plan dir.

Reuses the project's ``atomic_write_json`` (write .tmp → fsync → rename) so a
partially-written verdict is never observed. Read is fail-soft: a missing or
corrupt file returns ``None``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from arnold.pipelines.megaplan.orchestration.completion_contract import CompletionVerdict

log = logging.getLogger("megaplan.orchestration.completion_io")

COMPLETION_VERDICT_FILENAME = "completion_verdict.json"


def write_completion_verdict(plan_dir: Path, verdict: CompletionVerdict) -> Path:
    """Atomically write *verdict* to ``<plan_dir>/completion_verdict.json``.

    Returns the path written. Raises only if the underlying atomic write fails;
    callers in shadow mode wrap this in try/except (fail-open).
    """
    from arnold.pipelines.megaplan._core.io import atomic_write_json

    path = plan_dir / COMPLETION_VERDICT_FILENAME
    atomic_write_json(path, verdict.to_dict())
    return path


def read_completion_verdict(plan_dir: Path) -> dict | None:
    """Read the raw verdict dict, or ``None`` if absent/corrupt."""
    path = plan_dir / COMPLETION_VERDICT_FILENAME
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("could not read %s: %s", path, exc)
        return None


def read_typed_completion_verdict(plan_dir: Path) -> CompletionVerdict | None:
    """Read and deserialize a verdict, or ``None`` if absent/corrupt/untyped."""
    payload = read_completion_verdict(plan_dir)
    if not isinstance(payload, dict):
        return None
    try:
        return CompletionVerdict.from_dict(payload)
    except Exception as exc:
        log.debug("could not deserialize typed verdict in %s: %s", plan_dir, exc)
        return None
