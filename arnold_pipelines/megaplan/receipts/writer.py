"""Best-effort receipt persistence."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from arnold.workflow.boundary_evidence import BoundaryReceipt
from arnold_pipelines.megaplan._core import atomic_write_json

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


def write_boundary_receipt(
    plan_dir: Path,
    receipt: BoundaryReceipt,
    *,
    project_dir: str | Path | None = None,
) -> None:
    """Write a durable boundary receipt without raising.

    Persists ``plan_dir/boundary_receipts/{boundary_id}.json`` atomically
    and appends a JSONL audit record.  This function is intentionally
    best-effort and must never alter state transitions or route decisions.
    It does not affect existing step receipt behavior.
    """
    try:
        payload = receipt.to_dict()
        boundary_id = receipt.boundary_id
        target_dir = plan_dir / "boundary_receipts"
        atomic_write_json(target_dir / f"{boundary_id}.json", payload)

        audit_dir = Path(os.environ.get("MEGAPLAN_AUDIT_DIR") or (Path.home() / ".megaplan" / "audit"))
        _append_jsonl(audit_dir / "boundary_receipts.jsonl", payload)

        if project_dir is not None:
            repo_audit_dir = Path(project_dir) / ".megaplan" / "audit"
            should_mirror = os.environ.get("MEGAPLAN_REPO_AUDIT_MIRROR") == "1" or repo_audit_dir.exists()
            if should_mirror:
                _append_jsonl(repo_audit_dir / "boundary_receipts.jsonl", payload)
    except Exception as exc:
        log.warning("boundary receipt write failed: %s", exc, exc_info=True)
        return
