"""Shared, phase-scoped LLM liveness correlation.

An unmatched LLM start is evidence of progress only for the active step that
emitted it.  A previous phase can lose its end event when a provider stream
dies; letting that stale record keep a later phase alive masks real stalls.
"""

from __future__ import annotations

from typing import Any, Callable


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

    ended_ids: set[str] = set()
    for event in events:
        if event.get("kind") == end_kind:
            request_id = event.get("payload", {}).get("request_id")
            if request_id:
                ended_ids.add(str(request_id))

    for event in events:
        if event.get("kind") != start_kind:
            continue
        payload = event.get("payload", {})
        request_id = payload.get("request_id")
        if request_id and str(request_id) in ended_ids:
            continue
        if event.get("phase") != active_phase or payload.get("model") != active_model:
            continue
        start_ts = parse_timestamp(str(event.get("ts_utc", "")))
        if start_ts is not None and 0 <= now_ts - start_ts < max_age_seconds:
            return True
    return False
