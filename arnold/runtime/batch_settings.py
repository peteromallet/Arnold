"""Batch runtime settings normalization.

Provides :func:`build_batch_runtime_settings` which normalizes
resolved runtime settings into a :class:`~arnold.runtime.batch.BatchRuntimeSettings`
carrier.  The normalizer never parses ``RunEnvelope.deadline``
or ``RunEnvelope.cancellation`` — those are envelope metadata
only (SD1, SD2).

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.runtime.batch import BatchRuntimeSettings

__all__ = ["build_batch_runtime_settings"]


def build_batch_runtime_settings(
    effective: Mapping[str, Any] | None = None,
    *,
    max_workers: int = 1,
    wall_timeout_s: float | None = None,
    deadline_epoch_s: float | None = None,
    cancellation_requested: bool = False,
    idle_timeout_s: float | None = None,
    heartbeat_interval_s: float | None = None,
    poll_cadence_s: float | None = None,
    cost_cap_usd: float | None = None,
) -> BatchRuntimeSettings:
    """Build a normalized :class:`BatchRuntimeSettings` from resolved values.

    When *effective* is provided it is treated as a dict of key → value
    (e.g. the ``effective`` dict of a
    :class:`~arnold.runtime.settings_resolver.ResolvedSettings`).
    Individual keyword arguments can override or supplement the dict;
    explicit keywords always win.

    The normalizer does **not** parse deadline or cancellation strings
    from any envelope — only numeric ``deadline_epoch_s`` and boolean
    ``cancellation_requested`` are canonical (SD1, SD2).
    """
    # Keywords override dict values per "explicit keywords always win".
    # Start with the effective dict as base, then layer keywords on top.
    merged: dict[str, Any] = dict(effective) if effective else {}

    # Apply keyword overrides — only when the keyword is explicitly not the
    # default (since defaults are sentinel-ish we compare by identity where
    # possible).  For boolean and None defaults we can't distinguish "caller
    # passed default" from "caller omitted", so keywords always win over dict.
    if max_workers != 1 or "max_workers" not in merged:
        merged["max_workers"] = max_workers
    if wall_timeout_s is not None or "wall_timeout_s" not in merged:
        merged["wall_timeout_s"] = wall_timeout_s
    if deadline_epoch_s is not None or "deadline_epoch_s" not in merged:
        merged["deadline_epoch_s"] = deadline_epoch_s
    if cancellation_requested or "cancellation_requested" not in merged:
        merged["cancellation_requested"] = cancellation_requested
    if idle_timeout_s is not None or "idle_timeout_s" not in merged:
        merged["idle_timeout_s"] = idle_timeout_s
    if heartbeat_interval_s is not None or "heartbeat_interval_s" not in merged:
        merged["heartbeat_interval_s"] = heartbeat_interval_s
    if poll_cadence_s is not None or "poll_cadence_s" not in merged:
        merged["poll_cadence_s"] = poll_cadence_s
    if cost_cap_usd is not None or "cost_cap_usd" not in merged:
        merged["cost_cap_usd"] = cost_cap_usd

    def _get_num(key: str) -> float | None:
        v = merged.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _get_bool(key: str) -> bool:
        v = merged.get(key)
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    def _get_int(key: str, fallback: int = 1) -> int:
        v = merged.get(key)
        if v is None:
            return fallback
        try:
            return int(v)
        except (TypeError, ValueError):
            return fallback

    resolved_max: int = _get_int("max_workers", max_workers)
    resolved_wall: float | None = _get_num("wall_timeout_s")
    resolved_deadline: float | None = _get_num("deadline_epoch_s")
    resolved_cancellation: bool = _get_bool("cancellation_requested")
    resolved_idle: float | None = _get_num("idle_timeout_s")
    resolved_heartbeat: float | None = _get_num("heartbeat_interval_s")
    resolved_poll: float | None = _get_num("poll_cadence_s")
    resolved_cost_cap: float | None = _get_num("cost_cap_usd")

    return BatchRuntimeSettings(
        max_workers=max(1, resolved_max),
        wall_timeout_s=resolved_wall,
        deadline_epoch_s=resolved_deadline,
        cancellation_requested=resolved_cancellation,
        idle_timeout_s=resolved_idle,
        heartbeat_interval_s=resolved_heartbeat,
        poll_cadence_s=resolved_poll,
        cost_cap_usd=resolved_cost_cap,
    )
