"""Content-addressed prompt store for the Evaluand Ledger (M5-eval).

Prompts are stored at ``<plan_dir>/evaluand_prompts/<prompt_hash>.json``
using atomic-rename writes protected by an fcntl flock, mirroring the
pattern in ``megaplan/observability/events.py``.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from megaplan.store.snapshot import canonical_json_dumps


def write_prompt_bytes(
    plan_dir: Path,
    prompt_hash: str,
    *,
    raw: Optional[bytes],
    canonical: Optional[bytes],
    model_identity: str,
    params: Any,
) -> Path:
    """Write a prompt record into ``<plan_dir>/evaluand_prompts/<prompt_hash>.json``.

    Idempotent: if the file already exists the write is a no-op (same content
    wins; we don't overwrite).  Uses atomic temp-file + rename so readers never
    see a partial write.
    """
    store_dir = Path(plan_dir) / "evaluand_prompts"
    store_dir.mkdir(parents=True, exist_ok=True)

    target = store_dir / f"{prompt_hash}.json"
    if target.exists():
        return target

    payload = {
        "prompt_hash": prompt_hash,
        "raw": raw.decode("utf-8", errors="replace") if raw is not None else None,
        "canonical": canonical.decode("utf-8", errors="replace") if canonical is not None else None,
        "model_identity": model_identity,
        "params": params,
    }
    serialized = canonical_json_dumps(payload).encode("utf-8")

    lock_path = store_dir / ".prompt_cache.lock"
    lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if not target.exists():
            tmp_fd, tmp_path = tempfile.mkstemp(dir=store_dir, suffix=".tmp")
            try:
                os.write(tmp_fd, serialized)
                os.fsync(tmp_fd)
                os.close(tmp_fd)
                os.rename(tmp_path, str(target))
            except Exception:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)

    return target


def read_prompt_bytes(plan_dir: Path, prompt_hash: str) -> Optional[dict]:
    """Return the stored prompt record for *prompt_hash*, or ``None`` if absent."""
    target = Path(plan_dir) / "evaluand_prompts" / f"{prompt_hash}.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_bytes())
    except (json.JSONDecodeError, OSError):
        return None
