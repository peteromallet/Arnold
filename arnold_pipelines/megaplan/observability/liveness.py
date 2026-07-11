"""Shared, phase-scoped LLM liveness correlation.

An unmatched LLM start is evidence of progress only for the active step that
emitted it.  A previous phase can lose its end event when a provider stream
dies; letting that stale record keep a later phase alive masks real stalls.
"""

from __future__ import annotations

from typing import Any, Callable


def _call_identity(event: dict[str, Any]) -> str | None:
    payload = event.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    for value in (
        payload.get("call_transaction_id"),
        payload.get("request_id"),
    ):
        if value not in (None, ""):
            return str(value)
    return None


def unmatched_llm_starts(
    events: list[dict[str, Any]],
    *,
    start_kind: str = "llm_call_start",
    end_kind: str = "llm_call_end",
) -> list[dict[str, Any]]:
    """Return starts not closed by a later call-identity or phase match.

    New telemetry carries ``call_transaction_id``.  Legacy telemetry often
    learned a provider request id only at completion, so it falls back to
    closing the oldest requestless start in the same phase.  Sequential legacy
    calls therefore cannot leave every historical call falsely in flight.
    """
    pending: list[dict[str, Any]] = []
    for event in events:
        kind = event.get("kind")
        if kind == start_kind:
            pending.append(event)
            continue
        if kind not in {end_kind, "llm_call_error"}:
            continue
        identity = _call_identity(event)
        match: int | None = None
        if identity is not None:
            for index, start in enumerate(pending):
                if _call_identity(start) == identity:
                    match = index
                    break
        if match is None:
            for index, start in enumerate(pending):
                if _call_identity(start) is None and start.get("phase") == event.get("phase"):
                    match = index
                    break
        if match is not None:
            pending.pop(match)
    return pending


def _active_identity(state: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(state, dict):
        return None, None
    active = state.get("active_step")
    if not isinstance(active, dict):
        return None, None
    phase = active.get("phase") or active.get("step")
    model = active.get("model")
    return (
        phase.strip() if isinstance(phase, str) and phase.strip() else None,
        model.strip() if isinstance(model, str) and model.strip() else None,
    )


def has_active_in_flight_llm(
    events: list[dict[str, Any]],
    state: dict[str, Any] | None,
    now_ts: float,
    *,
    parse_timestamp: Callable[[str], float | None],
    start_kind: str = "llm_call_start",
    end_kind: str = "llm_call_end",
    max_age_seconds: float = 7200,
) -> bool:
    """Whether an unmatched recent LLM call belongs to the active phase/model.

    The active phase and model are both part of the correlation key.  Missing
    identity is deliberately not treated as evidence of current progress:
    otherwise a legacy or prior-run telemetry record can indefinitely hide a
    stalled active worker.
    """
    active_phase, active_model = _active_identity(state)
    if active_phase is None or active_model is None:
        return False

    for event in unmatched_llm_starts(events, start_kind=start_kind, end_kind=end_kind):
        payload = event.get("payload", {})
        if event.get("phase") != active_phase or payload.get("model") != active_model:
            continue
        start_ts = parse_timestamp(str(event.get("ts_utc", "")))
        if start_ts is not None and 0 <= now_ts - start_ts < max_age_seconds:
            return True
    return False
