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

    accepted_output_delta: int | None = None
    """Delta in accepted-output bytes (or lines) produced by this event."""

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
        d["accepted_output_delta"] = self.accepted_output_delta

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
            "accepted_output_delta": self.accepted_output_delta,
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
        contract_issues = validate_producer_contract(event)
        if contract_issues:
            issues.extend(contract_issues)
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
# Producer contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProducerContract:
    """Concrete producer contract for a work class.

    Every work class must have at least one producer contract specifying:
    - which module/function emits it
    - what measures are expected (and which are always unavailable)
    - the required unavailable_reason when measures are missing
    """

    work_class: WorkClass
    producer_module: str
    producer_function: str
    always_unavailable: tuple[str, ...] = ()
    """Measures that are always unavailable for this work class."""
    required_measures: tuple[str, ...] = ()
    """Measures that MUST be present (not None) for this contract."""


PRODUCER_CONTRACTS: dict[WorkClass, ProducerContract] = {
    WorkClass.PRODUCTIVE: ProducerContract(
        work_class=WorkClass.PRODUCTIVE,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_productive",
        always_unavailable=(),
        required_measures=(),
    ),
    WorkClass.REVIEW_PROOF: ProducerContract(
        work_class=WorkClass.REVIEW_PROOF,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_review_proof",
        always_unavailable=(),
        required_measures=(),
    ),
    WorkClass.QUEUE_IDLE: ProducerContract(
        work_class=WorkClass.QUEUE_IDLE,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_queue_idle",
        always_unavailable=(),
        required_measures=("elapsed_ms",),
    ),
    WorkClass.RETRY_WAIT: ProducerContract(
        work_class=WorkClass.RETRY_WAIT,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_retry_wait",
        always_unavailable=(),
        required_measures=("elapsed_ms",),
    ),
    WorkClass.COMPACTION: ProducerContract(
        work_class=WorkClass.COMPACTION,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_compaction",
        always_unavailable=(),
        required_measures=(),
    ),
    WorkClass.VALIDATION: ProducerContract(
        work_class=WorkClass.VALIDATION,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_validation",
        always_unavailable=(),
        required_measures=("elapsed_ms",),
    ),
    WorkClass.REPAIR_VERIFICATION: ProducerContract(
        work_class=WorkClass.REPAIR_VERIFICATION,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_repair_verification",
        always_unavailable=(),
        required_measures=("elapsed_ms",),
    ),
    WorkClass.REPLAY: ProducerContract(
        work_class=WorkClass.REPLAY,
        producer_module="arnold_pipelines.megaplan.observability.work_ledger",
        producer_function="emit_replay",
        always_unavailable=(),
        required_measures=(),
    ),
}


def validate_producer_contract(event: WorkLedgerEvent) -> list[str]:
    """Validate that *event* satisfies its producer contract.

    Returns a list of issues (empty = valid).  A missing contract is a
    warning, not a failure — unregistered work classes are still emitted.
    """
    issues: list[str] = []
    contract = PRODUCER_CONTRACTS.get(event.work_class)
    if contract is None:
        return issues  # no contract = no extra validation

    for measure_name in contract.always_unavailable:
        value = getattr(event, measure_name, None)
        if value is not None:
            issues.append(
                f"WorkLedgerEvent {event.work_class.value}: "
                f"{measure_name}={value} but contract declares it always_unavailable"
            )

    for measure_name in contract.required_measures:
        value = getattr(event, measure_name, None)
        if value is None:
            issues.append(
                f"WorkLedgerEvent {event.work_class.value}: "
                f"{measure_name} is None but contract requires it"
            )

    return issues


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
    accepted_output_delta: int | None = None,
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
        accepted_output_delta=accepted_output_delta,
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
    accepted_output_delta: int | None = None,
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
        accepted_output_delta=accepted_output_delta,
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
        unavailable_reason=unavailable_reason or "queue_idle_no_model_no_output_delta",
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
        unavailable_reason=unavailable_reason or "retry_wait_no_model_no_output_delta",
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
    accepted_output_delta: int | None = None,
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
        accepted_output_delta=accepted_output_delta,
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
    accepted_output_delta: int | None = None,
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
        accepted_output_delta=accepted_output_delta,
        unavailable_reason=unavailable_reason,
        metadata=dict(metadata or {}),
    )
    emit_work_ledger_event(plan_dir, event)


# ---------------------------------------------------------------------------
# Natural-boundary producers
# ---------------------------------------------------------------------------


def _positive_int(value: Any) -> int | None:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced > 0 else None


def _nonnegative_int(value: Any) -> int | None:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced >= 0 else None


def _positive_float(value: Any) -> float | None:
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced > 0 else None


def _emit_event(plan_dir: Path, kind: str, *, phase: str | None, payload: dict[str, Any]) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import emit

        emit(kind, plan_dir=plan_dir, phase=phase, payload=payload)
    except Exception:
        log.debug("Work ledger companion event emission skipped", exc_info=True)


def _missing_reason(measures: dict[str, Any], fallback: str) -> str | None:
    missing = [name for name, value in measures.items() if value is None]
    if not missing:
        return None
    return f"{fallback}: {','.join(missing)}"


def _duration_seconds(elapsed_ms: int | None) -> float | None:
    if elapsed_ms is None:
        return None
    return elapsed_ms / 1000.0


def _attempt_id_from_worker(worker: Any, fallback: str | None = None) -> str | None:
    auth_metadata = getattr(worker, "auth_metadata", None)
    if isinstance(auth_metadata, dict):
        wbc_dispatch = auth_metadata.get("wbc_dispatch")
        if isinstance(wbc_dispatch, dict):
            attempt_id = wbc_dispatch.get("attempt_id")
            if isinstance(attempt_id, str) and attempt_id:
                return attempt_id
    return fallback


def _worker_measurements(
    worker: Any,
    *,
    model_calls: int,
    accepted_output_delta: int | None,
) -> dict[str, Any]:
    return {
        "elapsed_ms": _positive_int(getattr(worker, "duration_ms", None)),
        "model_calls": model_calls,
        "prompt_tokens": _positive_int(getattr(worker, "prompt_tokens", None)),
        "completion_tokens": _positive_int(getattr(worker, "completion_tokens", None)),
        "total_tokens": _positive_int(getattr(worker, "total_tokens", None)),
        "cost_usd": _positive_float(getattr(worker, "cost_usd", None)),
        "accepted_output_delta": accepted_output_delta,
    }


def emit_session_start(
    plan_dir: Path,
    *,
    phase: str | None,
    session_id: str | None,
    agent: str | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit the companion session-start event for work-ledger joins."""

    if not session_id:
        return
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind
    except Exception:
        return
    payload = {
        "session_id": session_id,
        "agent": agent,
        "model": model,
    }
    payload.update(dict(metadata or {}))
    _emit_event(plan_dir, EventKind.SESSION_START, phase=phase, payload=payload)


def emit_worker_inference(
    plan_dir: Path,
    *,
    phase: str,
    worker: Any,
    work_class: WorkClass,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    agent: str | None = None,
    model_calls: int = 1,
    accepted_output_delta: int | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit joined session, inference, and work-ledger rows for a worker call."""

    resolved_attempt_id = _attempt_id_from_worker(worker, attempt_id)
    model_actual = getattr(worker, "model_actual", None)
    session_id = getattr(worker, "session_id", None)
    emit_session_start(
        plan_dir,
        phase=phase,
        session_id=session_id,
        agent=agent,
        model=model_actual,
        metadata={"attempt_id": resolved_attempt_id},
    )
    measures = _worker_measurements(
        worker,
        model_calls=model_calls,
        accepted_output_delta=accepted_output_delta,
    )
    reason = unavailable_reason or _missing_reason(
        measures,
        "worker_measurement_unavailable",
    )
    companion_payload = {
        "phase": phase,
        "task_id": task_id,
        "batch_id": batch_id,
        "attempt_id": resolved_attempt_id,
        "session_id": session_id,
        "agent": agent,
        "model": model_actual,
        "model_calls": model_calls,
        "tokens_in": measures["prompt_tokens"],
        "tokens_out": measures["completion_tokens"],
        "total_tokens": measures["total_tokens"],
        "cost_usd": measures["cost_usd"],
        "duration_ms": measures["elapsed_ms"],
        "duration_s": _duration_seconds(measures["elapsed_ms"]),
        "accepted_output_delta": accepted_output_delta,
        "unavailable_reason": reason,
    }
    companion_payload.update(dict(metadata or {}))
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind

        _emit_event(plan_dir, EventKind.INFERENCE, phase=phase, payload=companion_payload)
    except Exception:
        log.debug("Work ledger inference companion event skipped", exc_info=True)

    emit_fn = emit_productive if work_class is WorkClass.PRODUCTIVE else emit_review_proof
    emit_fn(
        plan_dir,
        task_id=task_id,
        batch_id=batch_id,
        attempt_id=resolved_attempt_id,
        elapsed_ms=measures["elapsed_ms"],
        model_calls=model_calls,
        prompt_tokens=measures["prompt_tokens"],
        completion_tokens=measures["completion_tokens"],
        total_tokens=measures["total_tokens"],
        cost_usd=measures["cost_usd"],
        accepted_output_delta=accepted_output_delta,
        unavailable_reason=reason,
        metadata=companion_payload,
    )


def emit_tool_activity(
    plan_dir: Path,
    *,
    phase: str,
    tool_name: str,
    work_class: WorkClass = WorkClass.VALIDATION,
    elapsed_ms: int | None = None,
    task_id: str | None = None,
    batch_id: str | None = None,
    attempt_id: str | None = None,
    unavailable_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a non-model tool boundary as an event plus ledger row."""

    try:
        from arnold_pipelines.megaplan.observability.events import EventKind

        _emit_event(
            plan_dir,
            EventKind.TOOL,
            phase=phase,
            payload={
                "phase": phase,
                "tool_name": tool_name,
                "work_class": work_class.value,
                "elapsed_ms": elapsed_ms,
                "duration_s": _duration_seconds(elapsed_ms),
                "task_id": task_id,
                "batch_id": batch_id,
                "attempt_id": attempt_id,
                **dict(metadata or {}),
            },
        )
    except Exception:
        log.debug("Work ledger tool companion event skipped", exc_info=True)

    if work_class is WorkClass.REPAIR_VERIFICATION:
        emit_repair_verification(
            plan_dir,
            task_id=task_id,
            batch_id=batch_id,
            attempt_id=attempt_id,
            elapsed_ms=elapsed_ms,
            unavailable_reason=unavailable_reason,
            metadata={"phase": phase, "tool_name": tool_name, **dict(metadata or {})},
        )
    else:
        emit_validation(
            plan_dir,
            task_id=task_id,
            batch_id=batch_id,
            attempt_id=attempt_id,
            elapsed_ms=elapsed_ms,
            metadata={"phase": phase, "tool_name": tool_name, **dict(metadata or {})},
        )


def emit_git_activity(
    plan_dir: Path,
    *,
    phase: str,
    operation: str,
    argv: list[str] | tuple[str, ...] | None = None,
    elapsed_ms: int | None = None,
    returncode: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a Git boundary without making Git output authoritative."""

    payload = {
        "phase": phase,
        "operation": operation,
        "argv": list(argv or ()),
        "elapsed_ms": elapsed_ms,
        "duration_s": _duration_seconds(elapsed_ms),
        "returncode": returncode,
        **dict(metadata or {}),
    }
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind

        _emit_event(plan_dir, EventKind.GIT, phase=phase, payload=payload)
    except Exception:
        log.debug("Work ledger git companion event skipped", exc_info=True)
    emit_tool_activity(
        plan_dir,
        phase=phase,
        tool_name=f"git:{operation}",
        elapsed_ms=elapsed_ms,
        metadata=payload,
    )


def emit_transition_activity(
    plan_dir: Path,
    *,
    phase: str | None,
    transition: str,
    from_state: str | None = None,
    to_state: str | None = None,
    elapsed_ms: int | None = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a workflow transition companion event and zero-model ledger row."""

    payload = {
        "transition": transition,
        "from": from_state,
        "to": to_state,
        "elapsed_ms": elapsed_ms,
        "duration_s": _duration_seconds(elapsed_ms),
        **dict(metadata or {}),
    }
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind

        _emit_event(plan_dir, EventKind.TRANSITION, phase=phase, payload=payload)
    except Exception:
        log.debug("Work ledger transition companion event skipped", exc_info=True)
    emit_tool_activity(
        plan_dir,
        phase=phase or "transition",
        tool_name=f"transition:{transition}",
        elapsed_ms=elapsed_ms,
        metadata=payload,
    )


def emit_strategy_m4_baseline_events(plan_dir: Path) -> None:
    """Preserve the known Strategy M4 work split as productive/proof evidence."""

    emit_productive(
        plan_dir,
        elapsed_ms=7_397_000,
        unavailable_reason="strategy_m4_historical_usage_unavailable",
        metadata={
            "phase": "execute",
            "boundary": "strategy_m4_historical_baseline",
            "duration_label": "2h03m17s",
            "classification_guard": "productive_implementation_not_waste",
        },
    )
    emit_review_proof(
        plan_dir,
        unavailable_reason="strategy_m4_historical_review_usage_unavailable",
        metadata={
            "phase": "review",
            "boundary": "strategy_m4_historical_baseline",
            "classification_guard": "required_review_not_waste",
        },
    )


# ---------------------------------------------------------------------------
# Re-export for convenience
# ---------------------------------------------------------------------------

__all__ = [
    "WorkClass",
    "WorkLedgerEvent",
    "ProducerContract",
    "PRODUCER_CONTRACTS",
    "validate_producer_contract",
    "emit_work_ledger_event",
    "emit_productive",
    "emit_review_proof",
    "emit_queue_idle",
    "emit_retry_wait",
    "emit_compaction",
    "emit_validation",
    "emit_repair_verification",
    "emit_replay",
    "emit_session_start",
    "emit_worker_inference",
    "emit_tool_activity",
    "emit_git_activity",
    "emit_transition_activity",
    "emit_strategy_m4_baseline_events",
]
