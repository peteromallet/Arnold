"""Deterministic channel parity over normalized phase summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict


class ChannelParitySummary(TypedDict, total=False):
    exit_kind: str | None
    payload_schema_valid: bool | None
    landed_diff: str | None
    worker_did_work: str | None
    latency_ms: int | None
    cost_usd: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


def _exit_kind_class(exit_kind: str | None) -> str | None:
    if exit_kind is None:
        return None
    normalized = str(exit_kind).strip().lower()
    if normalized in {"success", "passed", "done", "completed", "partial"}:
        return "success"
    if normalized in {"blocked", "manual_required", "human_required"}:
        return "blocked"
    if normalized in {"timeout", "worker_timeout", "worker_stall"}:
        return "timeout"
    if normalized in {"external_error", "rate_limit", "connection_error", "auth_error"}:
        return "external_error"
    if normalized in {"failed", "failure", "error"}:
        return "failure"
    return normalized


def _drift(primary: ChannelParitySummary, shadow: ChannelParitySummary) -> dict[str, Any]:
    primary_latency = primary.get("latency_ms")
    shadow_latency = shadow.get("latency_ms")
    primary_cost = primary.get("cost_usd")
    shadow_cost = shadow.get("cost_usd")
    primary_tokens = primary.get("total_tokens")
    shadow_tokens = shadow.get("total_tokens")

    latency_drift = (
        shadow_latency - primary_latency
        if isinstance(primary_latency, int) and isinstance(shadow_latency, int)
        else None
    )
    cost_drift = (
        float(shadow_cost) - float(primary_cost)
        if primary_cost is not None and shadow_cost is not None
        else None
    )
    token_drift = (
        shadow_tokens - primary_tokens
        if isinstance(primary_tokens, int) and isinstance(shadow_tokens, int)
        else None
    )
    return {
        "primary_latency_ms": primary_latency,
        "shadow_latency_ms": shadow_latency,
        "latency_drift_ms": latency_drift,
        "primary_cost_usd": primary_cost,
        "shadow_cost_usd": shadow_cost,
        "cost_drift_usd": cost_drift,
        "primary_total_tokens": primary_tokens,
        "shadow_total_tokens": shadow_tokens,
        "total_token_drift": token_drift,
    }


def compare_channel_parity(
    primary: ChannelParitySummary,
    shadow: ChannelParitySummary,
    *,
    compared_at: str | None = None,
) -> dict[str, Any]:
    """Compare only semantic parity fields; return drift as non-failing metadata."""
    primary_exit_class = _exit_kind_class(primary.get("exit_kind"))
    shadow_exit_class = _exit_kind_class(shadow.get("exit_kind"))
    exit_kind_match = primary_exit_class == shadow_exit_class
    primary_schema_valid = primary.get("payload_schema_valid") is True
    shadow_schema_valid = shadow.get("payload_schema_valid") is True
    payload_schema_valid_match = primary_schema_valid and shadow_schema_valid
    landed_diff_match = primary.get("landed_diff") == shadow.get("landed_diff")
    worker_did_work_match = primary.get("worker_did_work") == shadow.get("worker_did_work")
    passed = all(
        (
            exit_kind_match,
            payload_schema_valid_match,
            landed_diff_match,
            worker_did_work_match,
        )
    )
    return {
        "passed": passed,
        "exit_kind_match": exit_kind_match,
        "payload_schema_valid_match": payload_schema_valid_match,
        "landed_diff_match": landed_diff_match,
        "worker_did_work_match": worker_did_work_match,
        "compared_at": compared_at or datetime.now(timezone.utc).isoformat(),
        "details": {
            "primary_exit_kind_class": primary_exit_class,
            "shadow_exit_kind_class": shadow_exit_class,
            "primary_payload_schema_valid": primary.get("payload_schema_valid"),
            "shadow_payload_schema_valid": shadow.get("payload_schema_valid"),
            "drift": _drift(primary, shadow),
        },
    }
