"""Best-effort receipt persistence."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from megaplan._core import atomic_write_json

log = logging.getLogger(__name__)


def _append_jsonl(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(json.dumps(receipt, sort_keys=True).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_receipt(
    plan_dir: Path,
    receipt: dict[str, Any],
    *,
    project_dir: str | Path | None = None,
) -> None:
    """Write a receipt copy and append it to audit logs without raising."""
    try:
        phase = receipt["phase"]
        iteration = receipt["iteration"]
        atomic_write_json(plan_dir / f"step_receipt_{phase}_v{iteration}.json", receipt)

        audit_dir = Path(os.environ.get("MEGAPLAN_AUDIT_DIR") or (Path.home() / ".megaplan" / "audit"))
        _append_jsonl(audit_dir / "receipts.jsonl", receipt)

        if project_dir is not None:
            repo_audit_dir = Path(project_dir) / ".megaplan" / "audit"
            should_mirror = os.environ.get("MEGAPLAN_REPO_AUDIT_MIRROR") == "1" or repo_audit_dir.exists()
            if should_mirror:
                _append_jsonl(repo_audit_dir / "receipts.jsonl", receipt)
    except Exception as exc:
        log.warning("receipt write failed: %s", exc, exc_info=True)
        return
