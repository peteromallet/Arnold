"""Centralized application logging through the Store port."""

from __future__ import annotations

from typing import Any

from agent_kit.ports import Store


_REDACTED_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "service_key",
    "supabase_service_key",
    "token",
}


def log(
    store: Store,
    level: str,
    category: str,
    event_type: str,
    message: str,
    **context: Any,
) -> dict[str, Any]:
    """Write one structured log row through the configured Store."""

    turn_id = context.pop("turn_id", None)
    epic_id = context.pop("epic_id", None)
    return store.log_system_event(
        level=level,
        category=category,
        event_type=event_type,
        message=message,
        details=_redact(context),
        turn_id=turn_id,
        epic_id=epic_id,
    )


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if str(key).lower() in _REDACTED_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value
