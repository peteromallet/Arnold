"""Supervisor progress snapshots built from persisted native trace and audit data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    NativePersistenceBackend,
    NativePersistenceScope,
    OrderedPersistenceRow,
    bind_legacy_artifact_root,
)

__all__ = [
    "ProgressClassification",
    "ProgressSnapshot",
    "ProgressSignal",
    "ProgressUsage",
    "ProgressWindows",
    "build_progress_snapshot",
    "build_progress_snapshot_for_artifact_root",
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _ensure_timedelta(value: timedelta, *, field_name: str) -> timedelta:
    if value <= timedelta(0):
        raise ValueError(f"{field_name} must be positive")
    return value


def _max_timestamp(*values: datetime | None) -> datetime | None:
    timestamps = [value for value in values if value is not None]
    return max(timestamps) if timestamps else None


def _event_trace(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    trace = payload.get("trace")
    return trace if isinstance(trace, Mapping) else None


def _event_path(payload: Mapping[str, Any]) -> str | None:
    trace = _event_trace(payload)
    if trace is not None:
        path = trace.get("path") or trace.get("step_path") or trace.get("run_path")
        if isinstance(path, str) and path:
            return path
    for key in ("step_path", "run_path", "path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


@dataclass(frozen=True)
class ProgressSignal:
    """One persisted progress-related observation."""

    source: str
    observed_at: datetime | None = None
    sequence: int | None = None
    kind: str | None = None
    status: str | None = None
    path: str | None = None
    stage: str | None = None

    @property
    def present(self) -> bool:
        return (
            self.observed_at is not None
            or self.sequence is not None
            or self.kind is not None
            or self.status is not None
            or self.path is not None
            or self.stage is not None
        )


@dataclass(frozen=True)
class ProgressUsage:
    """Optional token/cost deltas observed from provider metadata."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: float | None = None
    cost_status: str | None = None
    cost_source: str | None = None
    model: str | None = None

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
            + self.reasoning_tokens
        )

    @property
    def present(self) -> bool:
        return self.total_tokens > 0 or self.estimated_cost_usd is not None


class ProgressClassification(StrEnum):
    HEALTHY = "healthy"
    SLOW_PROGRESSING = "slow_progressing"
    IDLE = "idle"
    DEAD = "dead"
    STUCK_BUT_ALIVE = "stuck_but_alive"


@dataclass(frozen=True)
class ProgressWindows:
    """Configurable time windows for progress classification."""

    healthy_progress_window: timedelta = timedelta(minutes=5)
    slow_signal_window: timedelta = timedelta(minutes=15)
    stuck_progress_window: timedelta = timedelta(minutes=30)
    stuck_liveness_window: timedelta = timedelta(minutes=15)
    idle_signal_window: timedelta = timedelta(hours=1)
    dead_signal_window: timedelta = timedelta(hours=2)

    def __post_init__(self) -> None:
        _ensure_timedelta(
            self.healthy_progress_window,
            field_name="healthy_progress_window",
        )
        _ensure_timedelta(self.slow_signal_window, field_name="slow_signal_window")
        _ensure_timedelta(
            self.stuck_progress_window,
            field_name="stuck_progress_window",
        )
        _ensure_timedelta(
            self.stuck_liveness_window,
            field_name="stuck_liveness_window",
        )
        _ensure_timedelta(
            self.idle_signal_window,
            field_name="idle_signal_window",
        )
        _ensure_timedelta(
            self.dead_signal_window,
            field_name="dead_signal_window",
        )
        if self.dead_signal_window < self.idle_signal_window:
            raise ValueError("dead_signal_window must be >= idle_signal_window")


@dataclass(frozen=True)
class ProgressSnapshot:
    """Externally queryable native-run progress summary for one persistence scope."""

    scope: NativePersistenceScope
    observed_at: datetime
    classification: ProgressClassification
    current_path: str | None
    current_stage: str | None
    checkpoint_status: str | None
    terminal_status: str | None
    latest_event: ProgressSignal
    latest_stage: ProgressSignal
    latest_audit: ProgressSignal
    latest_checkpoint: ProgressSignal
    latest_usage: ProgressSignal
    usage_delta: ProgressUsage
    last_signal_at: datetime | None
    last_progress_at: datetime | None
    windows: ProgressWindows

    @property
    def signal_age(self) -> timedelta | None:
        if self.last_signal_at is None:
            return None
        return self.observed_at - self.last_signal_at

    @property
    def progress_age(self) -> timedelta | None:
        if self.last_progress_at is None:
            return None
        return self.observed_at - self.last_progress_at


def build_progress_snapshot(
    backend: NativePersistenceBackend,
    scope: NativePersistenceScope,
    *,
    now: datetime | None = None,
    windows: ProgressWindows | None = None,
) -> ProgressSnapshot:
    """Read persisted native signals and classify one run's progress."""

    observed_at = now.astimezone(UTC) if now is not None else _utc_now()
    windows = windows or ProgressWindows()

    events = backend.read_events(scope)
    audits = backend.read_audit_records(scope)
    checkpoint_payload = backend.read_trace_artifact(scope, name="checkpoint.json")

    latest_event = _latest_event_signal(events)
    latest_stage = _latest_stage_signal(events)
    latest_audit = _latest_audit_signal(audits)
    latest_checkpoint = _checkpoint_signal(events, checkpoint_payload)
    latest_usage, usage_delta = _latest_usage_signal(events)

    current_path = _current_path(
        latest_checkpoint,
        latest_event,
        latest_audit,
        latest_usage,
    )
    current_stage = _current_stage(latest_checkpoint, latest_stage)
    checkpoint_status = _mapping_str(checkpoint_payload, "status")
    terminal_status = checkpoint_status or latest_audit.status
    last_signal_at = _max_timestamp(
        latest_event.observed_at,
        latest_audit.observed_at,
        latest_checkpoint.observed_at,
    )
    last_progress_at = _max_timestamp(
        latest_stage.observed_at,
        latest_audit.observed_at,
        latest_checkpoint.observed_at,
        latest_usage.observed_at if usage_delta.present else None,
    )
    classification = _classify_progress(
        observed_at=observed_at,
        last_signal_at=last_signal_at,
        last_progress_at=last_progress_at,
        windows=windows,
    )

    return ProgressSnapshot(
        scope=scope,
        observed_at=observed_at,
        classification=classification,
        current_path=current_path,
        current_stage=current_stage,
        checkpoint_status=checkpoint_status,
        terminal_status=terminal_status,
        latest_event=latest_event,
        latest_stage=latest_stage,
        latest_audit=latest_audit,
        latest_checkpoint=latest_checkpoint,
        latest_usage=latest_usage,
        usage_delta=usage_delta,
        last_signal_at=last_signal_at,
        last_progress_at=last_progress_at,
        windows=windows,
    )


def build_progress_snapshot_for_artifact_root(
    artifact_root: str | Path,
    *,
    project_id: str = "native-file-compat",
    now: datetime | None = None,
    windows: ProgressWindows | None = None,
) -> ProgressSnapshot:
    """Build a progress snapshot directly from a legacy artifact root."""

    binding = bind_legacy_artifact_root(artifact_root, project_id=project_id)
    backend = FileNativePersistenceBackend(
        lambda scope: binding.artifact_root
        if scope == binding.scope
        else (_ for _ in ()).throw(KeyError(scope))
    )
    return build_progress_snapshot(
        backend,
        binding.scope,
        now=now,
        windows=windows,
    )


def _mapping_str(payload: Any, key: str) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _latest_event_signal(events: list[OrderedPersistenceRow]) -> ProgressSignal:
    if not events:
        return ProgressSignal(source="event")
    row = events[-1]
    payload = row.payload
    return ProgressSignal(
        source="event",
        observed_at=_parse_timestamp(payload.get("ts_utc")),
        sequence=row.sequence,
        kind=row.kind,
        status=_mapping_str(payload.get("payload"), "status")
        if isinstance(payload.get("payload"), Mapping)
        else None,
        path=_event_path(payload.get("payload"))
        if isinstance(payload.get("payload"), Mapping)
        else None,
    )


def _latest_stage_signal(events: list[OrderedPersistenceRow]) -> ProgressSignal:
    for row in reversed(events):
        if row.kind != "stage.complete":
            continue
        payload = row.payload
        event_payload = payload.get("payload")
        if not isinstance(event_payload, Mapping):
            event_payload = {}
        return ProgressSignal(
            source="stage",
            observed_at=_parse_timestamp(payload.get("ts_utc")),
            sequence=row.sequence,
            kind=row.kind,
            path=_event_path(event_payload),
            stage=_mapping_str(event_payload, "stage"),
        )
    return ProgressSignal(source="stage")


def _latest_audit_signal(audits: list[OrderedPersistenceRow]) -> ProgressSignal:
    for row in reversed(audits):
        payload = row.payload
        if "attempt_id" not in payload:
            continue
        observed_at = _parse_timestamp(payload.get("ended_at")) or _parse_timestamp(
            payload.get("started_at")
        )
        return ProgressSignal(
            source="audit",
            observed_at=observed_at,
            sequence=row.sequence,
            kind=row.kind,
            status=_mapping_str(payload, "status"),
            path=_mapping_str(payload, "step_path") or _mapping_str(payload, "run_path"),
        )
    return ProgressSignal(source="audit")


def _checkpoint_signal(
    events: list[OrderedPersistenceRow],
    checkpoint_payload: Any,
) -> ProgressSignal:
    observed_at = None
    sequence = None
    for row in reversed(events):
        if row.kind != "checkpoint":
            continue
        observed_at = _parse_timestamp(row.payload.get("ts_utc"))
        sequence = row.sequence
        break
    return ProgressSignal(
        source="checkpoint",
        observed_at=observed_at,
        sequence=sequence,
        kind="checkpoint" if checkpoint_payload is not None else None,
        status=_mapping_str(checkpoint_payload, "status"),
        path=(
            _mapping_str(checkpoint_payload, "step_path")
            or _mapping_str(checkpoint_payload, "run_path")
        ),
        stage=_mapping_str(checkpoint_payload, "cursor_stage"),
    )


def _int_delta(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    return 0


def _latest_usage_signal(
    events: list[OrderedPersistenceRow],
) -> tuple[ProgressSignal, ProgressUsage]:
    for row in reversed(events):
        if row.kind != "token_progress":
            continue
        event_payload = row.payload.get("payload")
        if not isinstance(event_payload, Mapping):
            event_payload = {}
        cost = event_payload.get("estimated_cost_usd")
        estimated_cost_usd = float(cost) if isinstance(cost, (int, float)) else None
        usage = ProgressUsage(
            input_tokens=_int_delta(event_payload, "input_tokens"),
            output_tokens=_int_delta(event_payload, "output_tokens"),
            cache_read_tokens=_int_delta(event_payload, "cache_read_tokens"),
            cache_write_tokens=_int_delta(event_payload, "cache_write_tokens"),
            reasoning_tokens=_int_delta(event_payload, "reasoning_tokens"),
            estimated_cost_usd=estimated_cost_usd,
            cost_status=_mapping_str(event_payload, "cost_status"),
            cost_source=_mapping_str(event_payload, "cost_source"),
            model=_mapping_str(event_payload, "model"),
        )
        return (
            ProgressSignal(
                source="usage",
                observed_at=_parse_timestamp(row.payload.get("ts_utc")),
                sequence=row.sequence,
                kind=row.kind,
                path=_event_path(event_payload),
            ),
            usage,
        )
    return ProgressSignal(source="usage"), ProgressUsage()


def _current_path(
    latest_checkpoint: ProgressSignal,
    latest_event: ProgressSignal,
    latest_audit: ProgressSignal,
    latest_usage: ProgressSignal,
) -> str | None:
    candidates = [
        signal
        for signal in (latest_checkpoint, latest_event, latest_audit, latest_usage)
        if signal.path
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda signal: (
            signal.observed_at is not None,
            signal.observed_at or datetime.min.replace(tzinfo=UTC),
            signal.sequence or -1,
        ),
    )
    return candidates[-1].path


def _current_stage(
    latest_checkpoint: ProgressSignal,
    latest_stage: ProgressSignal,
) -> str | None:
    candidates = [
        signal for signal in (latest_checkpoint, latest_stage) if signal.stage
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda signal: (
            signal.observed_at is not None,
            signal.observed_at or datetime.min.replace(tzinfo=UTC),
            signal.sequence or -1,
        ),
    )
    return candidates[-1].stage


def _classify_progress(
    *,
    observed_at: datetime,
    last_signal_at: datetime | None,
    last_progress_at: datetime | None,
    windows: ProgressWindows,
) -> ProgressClassification:
    if last_signal_at is None:
        return ProgressClassification.DEAD

    signal_age = observed_at - last_signal_at
    if signal_age > windows.dead_signal_window:
        return ProgressClassification.DEAD

    if last_progress_at is not None:
        progress_age = observed_at - last_progress_at
        if progress_age <= windows.healthy_progress_window:
            return ProgressClassification.HEALTHY
        if (
            progress_age > windows.stuck_progress_window
            and signal_age <= windows.stuck_liveness_window
        ):
            return ProgressClassification.STUCK_BUT_ALIVE
    if signal_age <= windows.slow_signal_window:
        return ProgressClassification.SLOW_PROGRESSING
    if signal_age <= windows.idle_signal_window:
        return ProgressClassification.IDLE
    return ProgressClassification.DEAD
