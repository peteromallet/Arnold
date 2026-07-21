"""M9 work-class ledger for task/batch/attempt resource accounting.

Each event classifies elapsed time, model calls, tokens, and cost into
an explicit :class:`WorkClass`.  Missing measures are recorded with an
``unavailable_reason`` — they are **never** silently emitted as zero or
``waste``.

Write path: ``emit_work_ledger_event()`` → ``work_ledger.jsonl``
"""

from __future__ import annotations

import enum
import fcntl
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("megaplan")

LEDGER_FILE = "work_ledger.jsonl"
_LOCK_FILE = ".work_ledger.lock"


# ---------------------------------------------------------------------------
# Work classes
# ---------------------------------------------------------------------------


class WorkClass(str, enum.Enum):
    """Explicit classification for every ledger event."""

    PRODUCTIVE = "productive"
    """Task execution that produced an output (code, doc, artifact)."""

    REVIEW_PROOF = "review_proof"
    """Review / proof task that produced a verdict or evidence check."""

    QUEUE_IDLE = "queue_idle"
    """Time spent waiting in queue before a worker picked up the task."""

    RETRY_WAIT = "retry_wait"
    """Time spent between retry attempts (backoff / circuit wait)."""

    COMPACTION = "compaction"
    """Session compaction (context window management, summarisation)."""

    VALIDATION = "validation"
    """Deterministic (subprocess, no-model) validation job execution."""

    REPAIR_VERIFICATION = "repair_verification"
    """Read-only repair receipt verification against current custody state."""

    REPLAY = "replay"
    """Replay / rerun of previously executed work for audit or canary."""


# ---------------------------------------------------------------------------
# Ledger event
# ---------------------------------------------------------------------------


@dataclass
class WorkLedgerEvent:
    """One row in the work ledger.

    Every numeric measure is optional; when ``None`` the event **must**
    carry an ``unavailable_reason``.  Zero is never used as a sentinel
    for missing data.
    """

    work_class: WorkClass
    """Explicit work classification."""

    task_id: str | None = None
    """The task this event is scoped to, if any."""

    batch_id: str | None = None
    """The batch this event is scoped to, if any."""

    attempt_id: str | None = None
    """The attempt (invocation / run) this event is scoped to, if any."""

    # -- resource measures ---------------------------------------------------

    elapsed_ms: int | None = None
    """Wall-clock elapsed time in milliseconds."""

    model_calls: int | None = None
    """Number of model (LLM) calls made."""

    prompt_tokens: int | None = None
    """Prompt / input token count."""

    completion_tokens: int | None = None
    """Completion / output token count."""

    total_tokens: int | None = None
    """Total token count (prompt + completion)."""

    cost_usd: float | None = None
    """Cost in USD (provider-reported or computed)."""

    # -- availability --------------------------------------------------------

    unavailable_reason: str | None = None
    """When any resource measure is ``None``, this explains why.

    Examples: ``"worker_did_not_report_tokens"``,
    ``"subprocess_validation_no_model"``, ``"provider_api_did_not_return_usage"``.
    """

    # -- metadata ------------------------------------------------------------

    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary extra context (provider, model, phase, …)."""

    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (suitable for JSONL write)."""
        d: dict[str, Any] = {
            "ts": self.ts,
            "work_class": self.work_class.value,
        }
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.batch_id is not None:
            d["batch_id"] = self.batch_id
        if self.attempt_id is not None:
            d["attempt_id"] = self.attempt_id

        # Resource measures — preserve None so the reader can distinguish
        # "explicitly zero" from "unavailable".
        d["elapsed_ms"] = self.elapsed_ms
        d["model_calls"] = self.model_calls
        d["prompt_tokens"] = self.prompt_tokens
        d["completion_tokens"] = self.completion_tokens
        d["total_tokens"] = self.total_tokens
        d["cost_usd"] = self.cost_usd

        if self.unavailable_reason is not None:
            d["unavailable_reason"] = self.unavailable_reason
        if self.metadata:
            d["metadata"] = self.metadata

        return d

    def validate(self) -> list[str]:
        """Return a list of validation issues (empty = valid).

        Rules enforced:
        - ``unavailable_reason`` must be set when any measure is ``None``.
        - Zero values for measures are allowed but must be intentional
          (caller's responsibility — we only warn in log).
        """
        issues: list[str] = []
        measures: dict[str, Any] = {
            "elapsed_ms": self.elapsed_ms,
            "model_calls": self.model_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
        }
        missing = [k for k, v in measures.items() if v is None]
        if missing and not self.unavailable_reason:
            issues.append(
                f"WorkLedgerEvent measures {missing} are None but "
                f"unavailable_reason is not set"
            )
        return issues


# ---------------------------------------------------------------------------
# Emission helpers
# ---------------------------------------------------------------------------


def _ensure_plan_dir(plan_dir: Path) -> None:
    """No-op guard — write will fail gracefully if dir missing."""
    if not plan_dir.is_dir():
        log.debug(
            "Skipping work ledger write: plan directory %s does not exist",
            plan_dir,
        )


def _write_ledger_line(plan_dir: Path, event: WorkLedgerEvent) -> None:
    """Append one event to the work ledger JSONL, best-effort."""
    try:
        issues = event.validate()
        if issues:
            log.warning("Work ledger event validation issues: %s", issues)

        lock_path = plan_dir / _LOCK_FILE
        ledger_path = plan_dir / LEDGER_FILE
        if not plan_dir.is_dir():
            return
        line = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                with ledger_path.open("a", encoding="utf-8") as ledger:
                    ledger.write(line)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except Exception:
        log.warning(
            "Work ledger write failed for class=%s task=%s batch=%s",
            event.work_class.value,
            event.task_id,
            event.batch_id,
            exc_info=True,
        )


def emit_work_ledger_event(plan_dir: Path, event: WorkLedgerEvent) -> None:
    """Emit a single work ledger event.

    Never raises — a failure to write the ledger must not affect the
    control flow of the plan.
    """
    _ensure_plan_dir(plan_dir)
    _write_ledger_line(plan_dir, event)


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------


def emit_productive(
    plan_dir: Path,
    *,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    elapsed_ms: int | None = None,
    model_calls: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *productive* work ledger event (task execution)."""
    event = WorkLedgerEvent(
        work_class=WorkClass.PRODUCTIVE,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=model_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_review_proof(
    plan_dir: Path,
    *,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    elapsed_ms: int | None = None,
    model_calls: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *review/proof* work ledger event."""
    event = WorkLedgerEvent(
        work_class=WorkClass.REVIEW_PROOF,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=model_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_queue_idle(
    plan_dir: Path,
    *,
    elapsed_ms: int | None = None,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *queue/idle* work ledger event."""
    event = WorkLedgerEvent(
        work_class=WorkClass.QUEUE_IDLE,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_retry_wait(
    plan_dir: Path,
    *,
    elapsed_ms: int | None = None,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *retry wait* work ledger event."""
    event = WorkLedgerEvent(
        work_class=WorkClass.RETRY_WAIT,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_compaction(
    plan_dir: Path,
    *,
    elapsed_ms: int | None = None,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    model_calls: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *compaction* work ledger event."""
    event = WorkLedgerEvent(
        work_class=WorkClass.COMPACTION,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=model_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_validation(
    plan_dir: Path,
    *,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    elapsed_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *validation* work ledger event (deterministic, no model)."""
    event = WorkLedgerEvent(
        work_class=WorkClass.VALIDATION,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        unavailable_reason="subprocess_validation_no_model",
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_repair_verification(
    plan_dir: Path,
    *,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    elapsed_ms: int | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *repair/verification* work ledger event."""
    event = WorkLedgerEvent(
        work_class=WorkClass.REPAIR_VERIFICATION,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        unavailable_reason=unavailable_reason or "read_only_verification_no_model",
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


def emit_replay(
    plan_dir: Path,
    *,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    elapsed_ms: int | None = None,
    model_calls: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a *replay* work ledger event."""
    event = WorkLedgerEvent(
        work_class=WorkClass.REPLAY,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=attempt_id,
        elapsed_ms=elapsed_ms,
        model_calls=model_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


# ---------------------------------------------------------------------------
# Re-export for convenience
# ---------------------------------------------------------------------------

__all__ = [
    "WorkClass",
    "WorkLedgerEvent",
    "emit_work_ledger_event",
    "emit_productive",
    "emit_review_proof",
    "emit_queue_idle",
    "emit_retry_wait",
    "emit_compaction",
    "emit_validation",
    "emit_repair_verification",
    "emit_replay",
]
