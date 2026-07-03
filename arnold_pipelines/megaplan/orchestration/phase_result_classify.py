from __future__ import annotations

import re
from typing import Any


def _extract_status_code(exc: Exception, message: str) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    for pattern in (
        r"\bstatus code[:\s]+(\d{3})\b",
        r"\bhttp[:\s]+(\d{3})\b",
        r"\berror code[:\s]+(\d{3})\b",
        r"\b(401|402|403|429|500|502|503|504)\b",
    ):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_retry_after(message: str) -> float | None:
    match = re.search(r"\bretry[-_\s]?after[:=\s]+(\d+(?:\.\d+)?)\b", message)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_request_id(message: str) -> str | None:
    for pattern in (
        r"\brequest[-_ ]?id[:=\s]+([a-z0-9_-]+)\b",
        r"\bx-request-id[:=\s]+([a-z0-9_-]+)\b",
    ):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def classify_external_error_payload(
    exc: Exception,
    *,
    provider: str = "unknown",
) -> dict[str, Any] | None:
    """Return a plain payload for known provider/API failures."""
    extra = getattr(exc, "extra", None)
    if isinstance(extra, dict):
        raw = extra.get("_external_error") or extra.get("external_error")
        if isinstance(raw, dict):
            return dict(raw)

    exc_name = type(exc).__name__
    message = str(exc)
    combined = f"{exc_name} {message}".lower()

    status_code = _extract_status_code(exc, message)
    code = getattr(exc, "code", None)
    if code in {"quota_exceeded", "quota", "billing"} or re.search(
        r"\b(usage limit|quota_exceeded|quota limit|quota reached)\b",
        combined,
    ):
        inferred_provider = provider
        if inferred_provider == "unknown" and "codex" in combined:
            inferred_provider = "codex"
        return {
            "provider": inferred_provider,
            "error_kind": "quota",
            "message": message[:500],
            "status_code": status_code,
            "retry_after_s": _extract_retry_after(combined),
            "request_id": _extract_request_id(combined),
            "provider_error_code": str(code or "quota_exceeded"),
            "error_layer": "provider_quota",
        }
    if code == "worker_stall" or "stalled stream" in combined:
        inferred_provider = provider
        if inferred_provider == "unknown":
            if "claude" in combined:
                inferred_provider = "claude"
            elif "shannon" in combined:
                inferred_provider = "shannon"
        return {
            "provider": inferred_provider,
            "error_kind": "stalled_stream",
            "message": message[:500],
            "status_code": status_code,
            "provider_error_code": "timeout",
            "error_layer": "worker_stream_stall",
        }
    error_kind: str | None = None
    if status_code == 429 or re.search(
        r"\b(rate[-_\s]?limit(?:ed)?|too many requests)\b", combined
    ):
        error_kind = "rate_limit"
    elif status_code == 402 or re.search(
        r"\b(payment required|insufficient (?:balance|credits?)|"
        r"balance|quota (?:exceeded|exhausted)|limit exhausted)\b",
        combined,
    ):
        error_kind = "balance"
    elif status_code in (401, 403) or re.search(
        r"(\b(unauthori[sz]ed|forbidden|invalid api[_ -]?key|bad api[_ -]?key|"
        r"api[_ -]?key|authentication|permission denied|missing credentials?)\b|"
        r"\b(?:openrouter|openai)_api_key\b.*\bnot set\b)",
        combined,
    ):
        error_kind = "auth"
    elif status_code in (500, 502, 503, 504) or re.search(
        r"\b(server error|internal server|bad gateway|service unavailable|"
        r"gateway timeout)\b",
        combined,
    ):
        error_kind = "provider_failure"
    elif re.search(
        r"\b(timeout|timed out|connection (?:refused|reset|aborted)|"
        r"network|dns|resolve(?:d|r)?|unreachable)\b",
        combined,
    ):
        error_kind = "network"

    if error_kind is None:
        return None

    timeout_like = bool(
        re.search(r"\b(timeout|timed out)\b", combined)
        or exc_name.lower().endswith("timeouterror")
    )

    payload: dict[str, Any] = {
        "provider": provider,
        "error_kind": error_kind,
        "message": message[:500],
        "status_code": status_code,
        "retry_after_s": _extract_retry_after(combined),
        "request_id": _extract_request_id(combined),
    }
    if timeout_like:
        payload["provider_error_code"] = "timeout"
        payload["error_layer"] = "transport_timeout"
    return payload


def classify_external_error_chain(exc: Exception) -> dict[str, Any] | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        payload = classify_external_error_payload(current)
        if payload is not None:
            return payload
        current = current.__cause__ or current.__context__
    return None


__all__ = [
    "classify_external_error_payload",
    "classify_external_error_chain",
]
