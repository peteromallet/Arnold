"""Best-effort receipt persistence."""

from __future__ import annotations

import json
import logging
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar, cast

from arnold.workflow.boundary_evidence import BoundaryReceipt
from arnold_pipelines.megaplan._core import atomic_write_json
from arnold_pipelines.megaplan.receipts.schema import (
    AutomaticDispatchReceipt,
    DispatchMutationFacts,
    DispatchOutcome,
)

log = logging.getLogger(__name__)
_ProcessT = TypeVar("_ProcessT")


class DispatchReceiptError(RuntimeError):
    """An authoritative dispatch receipt could not be persisted.

    ``receipt`` is the truthful in-memory state callers must surface.  In
    particular, errors after launch carry ``subprocess_started=True`` and an
    ``indeterminate`` outcome even when storage itself is unavailable.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        receipt: AutomaticDispatchReceipt,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.receipt = deepcopy(receipt)


class DispatchInitializationError(DispatchReceiptError):
    """Initialization failed; the associated subprocess must not launch."""


class DispatchFinalizationError(DispatchReceiptError):
    """A post-launch transition could not be durably certified."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_dispatch_id(dispatch_id: str) -> str:
    candidate = str(dispatch_id).strip()
    if not candidate or candidate in {".", ".."} or Path(candidate).name != candidate:
        raise ValueError("dispatch_id must be a non-empty path-safe identity")
    return candidate


def prepare_dispatch_receipt(
    *,
    action: str,
    configured_model: str | None,
    dispatch_id: str | None = None,
    created_at_utc: str | None = None,
) -> AutomaticDispatchReceipt:
    """Prepare a stable dispatch identity without performing any I/O."""
    identity = _validate_dispatch_id(dispatch_id or str(uuid.uuid4()))
    action_name = str(action).strip()
    if not action_name:
        raise ValueError("action must be non-empty")
    created = created_at_utc or _utc_now()
    return {
        "schema_version": 1,
        "dispatch_id": identity,
        "action": action_name,
        "configured_model": configured_model,
        "resolved_runtime_model": None,
        "subprocess_started": False,
        "outcome": "initialized",
        "mutation_facts": {"state": False, "source": False, "commit": False, "push": False},
        "created_at_utc": created,
        "updated_at_utc": created,
        "sequence": 0,
        "failure_stage": None,
        "detail": None,
    }


def dispatch_receipt_path(plan_dir: Path, dispatch_id: str) -> Path:
    """Return the canonical snapshot path for a dispatch identity."""
    return Path(plan_dir) / "dispatch_receipts" / f"{_validate_dispatch_id(dispatch_id)}.json"


def _dispatch_journal_path(plan_dir: Path) -> Path:
    return Path(plan_dir) / "dispatch_receipts" / "lifecycle.jsonl"


def _persist_dispatch_transition(
    plan_dir: Path,
    receipt: AutomaticDispatchReceipt,
) -> None:
    """Durably append a transition, then replace its current snapshot.

    The append-only lifecycle is the source of truth.  A snapshot failure can
    therefore never erase an already durable transition.
    """
    _append_authoritative_jsonl(_dispatch_journal_path(plan_dir), dict(receipt))
    atomic_write_json(dispatch_receipt_path(plan_dir, receipt["dispatch_id"]), receipt)


def _reserve_dispatch_identity(plan_dir: Path, dispatch_id: str) -> None:
    """Durably and exclusively reserve an identity before its first event."""
    target_dir = Path(plan_dir) / "dispatch_receipts"
    target_dir.mkdir(parents=True, exist_ok=True)
    claim_path = target_dir / f"{_validate_dispatch_id(dispatch_id)}.identity"
    fd = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (dispatch_id + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(target_dir, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def initialize_dispatch_receipt(
    plan_dir: Path,
    receipt: AutomaticDispatchReceipt,
) -> AutomaticDispatchReceipt:
    """Durably initialize ``receipt`` before its subprocess may be launched.

    Failures are authoritative and are deliberately not logged-and-swallowed.
    """
    initialized = deepcopy(receipt)
    if initialized["sequence"] != 0 or initialized["subprocess_started"]:
        raise ValueError("dispatch receipt is not in its prepared state")
    initialized["outcome"] = "initialized"
    initialized["updated_at_utc"] = _utc_now()
    initialized["sequence"] = 1
    try:
        _reserve_dispatch_identity(Path(plan_dir), initialized["dispatch_id"])
        _persist_dispatch_transition(Path(plan_dir), initialized)
    except Exception as exc:
        failed = deepcopy(initialized)
        failed["outcome"] = "blocked"
        failed["failure_stage"] = "initialization"
        failed["detail"] = str(exc)
        raise DispatchInitializationError(
            "dispatch receipt initialization failed; subprocess launch is forbidden",
            stage="initialization",
            receipt=failed,
        ) from exc
    return initialized


def _require_durable_current(
    plan_dir: Path,
    receipt: AutomaticDispatchReceipt,
) -> None:
    path = dispatch_receipt_path(plan_dir, receipt["dispatch_id"])
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("dispatch receipt has no readable durable snapshot") from exc
    if (
        current.get("dispatch_id") != receipt["dispatch_id"]
        or current.get("sequence") != receipt["sequence"]
    ):
        raise ValueError("dispatch receipt does not match its durable snapshot")


def record_dispatch_started(
    plan_dir: Path,
    receipt: AutomaticDispatchReceipt,
    *,
    resolved_runtime_model: str | None = None,
) -> AutomaticDispatchReceipt:
    """Record that launch returned a subprocess handle.

    Call this immediately after launch.  Persistence failure is returned as a
    post-launch indeterminate action and must be surfaced by the caller.
    """
    if receipt["outcome"] != "initialized" or receipt["subprocess_started"]:
        raise ValueError("dispatch receipt is not ready to record subprocess start")
    started = deepcopy(receipt)
    started["subprocess_started"] = True
    started["outcome"] = "running"
    started["resolved_runtime_model"] = resolved_runtime_model
    started["mutation_facts"] = {
        "state": None,
        "source": None,
        "commit": None,
        "push": None,
    }
    started["updated_at_utc"] = _utc_now()
    started["sequence"] += 1
    try:
        _require_durable_current(Path(plan_dir), receipt)
        _persist_dispatch_transition(Path(plan_dir), started)
    except Exception as exc:
        indeterminate = deepcopy(started)
        indeterminate["outcome"] = "indeterminate"
        indeterminate["failure_stage"] = "subprocess_started"
        indeterminate["detail"] = str(exc)
        raise DispatchFinalizationError(
            "subprocess started but its start transition could not be certified",
            stage="subprocess_started",
            receipt=indeterminate,
        ) from exc
    return started


def initialize_and_launch_dispatch(
    plan_dir: Path,
    receipt: AutomaticDispatchReceipt,
    launch: Callable[[], _ProcessT],
) -> tuple[AutomaticDispatchReceipt, _ProcessT]:
    """Initialize durably, launch once, then durably record the launch.

    This is the safe subprocess boundary for automatic actions: ``launch`` is
    never called when initialization fails.  If launch itself raises, a
    durable blocked final state is attempted and the launch error propagates.
    Any receipt failure after ``launch`` returns carries an explicit truthful
    ``subprocess_started=True`` indeterminate receipt.
    """
    initialized = initialize_dispatch_receipt(Path(plan_dir), receipt)
    try:
        process = launch()
    except Exception as exc:
        finalize_dispatch_receipt(
            Path(plan_dir),
            initialized,
            outcome="blocked",
            detail=f"subprocess launch failed: {exc}",
        )
        raise
    started = record_dispatch_started(
        Path(plan_dir),
        initialized,
    )
    return started, process


_FINAL_OUTCOMES: frozenset[DispatchOutcome] = frozenset(
    {"blocked", "succeeded", "failed", "indeterminate"}
)


def finalize_dispatch_receipt(
    plan_dir: Path,
    receipt: AutomaticDispatchReceipt,
    *,
    outcome: DispatchOutcome,
    resolved_runtime_model: str | None = None,
    mutation_facts: Mapping[str, bool | None] | None = None,
    detail: str | None = None,
) -> AutomaticDispatchReceipt:
    """Durably finalize an automatic dispatch or raise an explicit error."""
    if outcome not in _FINAL_OUTCOMES:
        raise ValueError(f"invalid final dispatch outcome: {outcome!r}")
    if receipt["outcome"] not in {"initialized", "running"}:
        raise ValueError("dispatch receipt is already final")
    if receipt["subprocess_started"] and outcome == "blocked":
        raise ValueError("a started subprocess cannot have a blocked outcome")
    if not receipt["subprocess_started"] and outcome in {"succeeded", "failed"}:
        raise ValueError("an unstarted subprocess cannot succeed or fail")
    if receipt["subprocess_started"] and mutation_facts is None:
        raise ValueError("a started dispatch requires explicit mutation facts at finalization")

    final = deepcopy(receipt)
    final["outcome"] = outcome
    if resolved_runtime_model is not None:
        final["resolved_runtime_model"] = resolved_runtime_model
    if outcome == "succeeded" and not final["resolved_runtime_model"]:
        raise ValueError("successful model-backed dispatch requires resolved runtime model evidence")
    if mutation_facts is not None:
        if any(value is not None and not isinstance(value, bool) for value in mutation_facts.values()):
            raise TypeError("mutation facts must contain boolean or unknown observations")
        facts = dict(final["mutation_facts"])
        facts.update(mutation_facts)
        final["mutation_facts"] = cast(DispatchMutationFacts, facts)
    final["detail"] = detail
    final["failure_stage"] = None
    final["updated_at_utc"] = _utc_now()
    final["sequence"] += 1
    try:
        _require_durable_current(Path(plan_dir), receipt)
        _persist_dispatch_transition(Path(plan_dir), final)
    except Exception as exc:
        indeterminate = deepcopy(final)
        indeterminate["outcome"] = "indeterminate"
        indeterminate["failure_stage"] = "finalization"
        indeterminate["detail"] = str(exc)
        raise DispatchFinalizationError(
            "dispatch finalization failed; action outcome is indeterminate",
            stage="finalization",
            receipt=indeterminate,
        ) from exc
    return final


def _append_authoritative_jsonl(path: Path, receipt: dict[str, Any]) -> None:
    """Append and fsync both a lifecycle record and its directory entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(json.dumps(receipt, sort_keys=True).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path.parent, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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
