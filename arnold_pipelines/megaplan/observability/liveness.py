"""Shared, phase-scoped LLM liveness correlation.

An unmatched LLM start is evidence of progress only for the active step that
emitted it.  A previous phase can lose its end event when a provider stream
dies; letting that stale record keep a later phase alive masks real stalls.
"""

from __future__ import annotations

from typing import Any, Callable


def unmatched_llm_starts(
    events: list[dict[str, Any]],
    *,
    start_kind: str = "llm_call_start",
    end_kind: str = "llm_call_end",
) -> list[dict[str, Any]]:
    """Return LLM starts that have no later matching completion event.

    Some providers do not know their request id when the start event is
    emitted, but do include it on the end event.  In that case request-id-only
    correlation leaves every historical start looking in-flight forever.
    Match exact ids when possible, then pair an end with the oldest unkeyed
    start in the same phase.  The latter preserves the conservative count of
    concurrent calls without turning completed sequential calls into wedges.
    """
    pending: list[dict[str, Any]] = []
    for event in events:
        kind = event.get("kind")
        if kind == start_kind:
            pending.append(event)
            continue
        if kind != end_kind:
            continue

        payload = event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        request_id = payload.get("request_id")
        match_index: int | None = None
        if request_id:
            request_id = str(request_id)
            for index, start in enumerate(pending):
                start_payload = start.get("payload")
                start_payload = start_payload if isinstance(start_payload, dict) else {}
                if str(start_payload.get("request_id") or "") == request_id:
                    match_index = index
                    break

        if match_index is None:
            phase = event.get("phase")
            for index, start in enumerate(pending):
                start_payload = start.get("payload")
                start_payload = start_payload if isinstance(start_payload, dict) else {}
                if start_payload.get("request_id"):
                    continue
                if start.get("phase") == phase:
                    match_index = index
                    break

        if match_index is not None:
            pending.pop(match_index)

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

    for event in unmatched_llm_starts(
        events,
        start_kind=start_kind,
        end_kind=end_kind,
    ):
        payload = event.get("payload", {})
        if event.get("phase") != active_phase or payload.get("model") != active_model:
            continue
        start_ts = parse_timestamp(str(event.get("ts_utc", "")))
        if start_ts is not None and 0 <= now_ts - start_ts < max_age_seconds:
            return True
    return False
