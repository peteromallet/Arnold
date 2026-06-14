"""Sampled channel-shadow execution hooks."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import arnold.pipelines.megaplan.workers as worker_module
from arnold.pipelines.megaplan._core import read_json
from arnold.pipelines.megaplan.bakeoff.state import (
    CHANNEL_SHADOW_SCHEMA_VERSION,
    ChannelShadowDecision,
    ChannelShadowGate,
    ChannelShadowRecord,
    ChannelShadowState,
    channel_shadow_path,
    save_channel_shadow_state,
)
from arnold.pipelines.megaplan.orchestration.channel_parity import compare_channel_parity
from arnold.pipelines.megaplan.model_seam import ModelStructuralAuditError, audit_step_payload
from arnold.pipelines.megaplan.types import CliError, PlanState
from arnold.pipelines.megaplan.workers import WorkerResult

DEFAULT_CHANNEL_SHADOW_SAMPLE_RATE = 0.10
CHANNEL_SHADOW_GATE_THRESHOLD = 5
CHANNEL_SHADOW_HOOK_PROVENANCE_SOURCE = "channel_shadow_hook"


def channel_shadow_sample_rate() -> float:
    raw = os.getenv("MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE")
    if raw is None:
        return DEFAULT_CHANNEL_SHADOW_SAMPLE_RATE
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return DEFAULT_CHANNEL_SHADOW_SAMPLE_RATE


def _sampled(sample_key: str, sample_rate: float) -> bool:
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    digest = hashlib.sha256(sample_key.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
    return bucket < sample_rate


def _decision(
    *,
    sample_key: str,
    sample_rate: float,
    sampled: bool,
    skip_reason: str | None,
) -> ChannelShadowDecision:
    return {
        "sampled": sampled,
        "skipped": skip_reason is not None,
        "skip_reason": skip_reason,
        "sample_rate": sample_rate,
        "sample_key": sample_key,
    }


def _load_or_empty_state(root: Path, experiment_id: str) -> ChannelShadowState:
    path = channel_shadow_path(root, experiment_id)
    if path.exists():
        return read_json(path)
    return {
        "schema_version": CHANNEL_SHADOW_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "records": [],
        "real_parity_success_count": 0,
        "gate": _empty_gate(),
    }


def _is_real_shadow_record(record: ChannelShadowRecord) -> bool:
    provenance = record.get("provenance") or {}
    return (
        provenance.get("source") == CHANNEL_SHADOW_HOOK_PROVENANCE_SOURCE
        and provenance.get("fixture") is not True
    )


def _is_stream_tmux_pair(channel_pair: dict[str, Any] | None) -> bool:
    if not channel_pair:
        return False
    channels = {
        channel_pair.get("primary_worker_channel"),
        channel_pair.get("shadow_worker_channel"),
    }
    return channels == {"shannon_tmux", "shannon_stream"}


def _is_subscription_pair(channel_pair: dict[str, Any] | None) -> bool:
    if not channel_pair:
        return False
    return (
        channel_pair.get("primary_auth_channel") == "subscription"
        and channel_pair.get("shadow_auth_channel") == "subscription"
    )


def _record_counts_for_gate(records: list[ChannelShadowRecord]) -> dict[str, Any]:
    success_count = 0
    failure_count = 0
    skipped_count = 0
    fixture_count = 0
    latest_real_pair: dict[str, Any] | None = None
    latest_real_provenance: dict[str, Any] | None = None
    non_subscription_pair = False
    non_stream_tmux_pair = False

    for record in records:
        decision = record.get("decision") or {}
        if decision.get("skipped"):
            skipped_count += 1
            continue
        if not _is_real_shadow_record(record):
            fixture_count += 1
            continue
        channel_pair = record.get("channel_pair")
        if not _is_stream_tmux_pair(channel_pair):
            non_stream_tmux_pair = True
        if not _is_subscription_pair(channel_pair):
            non_subscription_pair = True
        latest_real_pair = channel_pair
        latest_real_provenance = record.get("provenance") or {}
        parity_result = record.get("parity_result")
        if parity_result and parity_result.get("passed") is True:
            success_count += 1
        else:
            failure_count += 1

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_count": skipped_count,
        "fixture_count": fixture_count,
        "latest_real_pair": latest_real_pair,
        "latest_real_provenance": latest_real_provenance,
        "non_subscription_pair": non_subscription_pair,
        "non_stream_tmux_pair": non_stream_tmux_pair,
    }


def _api_proof_blockers(root: Path) -> list[str]:
    proof_path = root / "docs" / "shannon-stream-api-proof-record.json"
    if not proof_path.exists():
        return ["api_proof_missing"]
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["api_proof_unreadable"]
    if proof.get("live_api_phase_completed") is True and proof.get("proof_kind") == "live":
        return []
    return ["api_proof_not_live"]


def _empty_gate(*, evaluated_at: str | None = None) -> ChannelShadowGate:
    return {
        "greenlight": False,
        "threshold": CHANNEL_SHADOW_GATE_THRESHOLD,
        "real_parity_success_count": 0,
        "real_parity_failure_count": 0,
        "skipped_count": 0,
        "fixture_count": 0,
        "blockers": ["insufficient_real_parity_successes"],
        "channel_pair": None,
        "provenance": {},
        "evaluated_at": evaluated_at or datetime.now(timezone.utc).isoformat(),
        "api_channel_greenlight": False,
        "api_channel_blockers": ["api_proof_missing"],
    }


def evaluate_channel_shadow_gate(root: Path, state: ChannelShadowState) -> ChannelShadowGate:
    counts = _record_counts_for_gate(list(state.get("records", [])))
    blockers: list[str] = []
    if counts["success_count"] < CHANNEL_SHADOW_GATE_THRESHOLD:
        blockers.append("insufficient_real_parity_successes")
    if counts["failure_count"]:
        blockers.append("real_parity_failures_present")
    if counts["non_stream_tmux_pair"]:
        blockers.append("non_stream_tmux_channel_pair_present")
    if counts["non_subscription_pair"]:
        blockers.append("non_subscription_channel_pair_present")
    api_blockers = _api_proof_blockers(root)
    return {
        "greenlight": not blockers,
        "threshold": CHANNEL_SHADOW_GATE_THRESHOLD,
        "real_parity_success_count": counts["success_count"],
        "real_parity_failure_count": counts["failure_count"],
        "skipped_count": counts["skipped_count"],
        "fixture_count": counts["fixture_count"],
        "blockers": blockers,
        "channel_pair": counts["latest_real_pair"],
        "provenance": counts["latest_real_provenance"] or {},
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "api_channel_greenlight": not api_blockers,
        "api_channel_blockers": api_blockers,
    }


def _append_record(root: Path, experiment_id: str, record: ChannelShadowRecord) -> None:
    state = _load_or_empty_state(root, experiment_id)
    records = list(state.get("records", []))
    records.append(record)
    state["records"] = records
    gate = evaluate_channel_shadow_gate(root, state)
    state["real_parity_success_count"] = gate["real_parity_success_count"]
    state["gate"] = gate
    record["real_parity_success_count"] = gate["real_parity_success_count"]
    save_channel_shadow_state(root, state)


def _payload_schema_valid(step: str, payload: dict[str, Any]) -> bool:
    try:
        audit_step_payload(step, payload)
    except (CliError, ModelStructuralAuditError):
        return False
    return True


def receipt_summary(
    *,
    worker: WorkerResult,
    step: str,
    state: PlanState,
    exit_kind: str,
    receipt_path: str | None = None,
) -> dict[str, Any]:
    payload = worker.payload if isinstance(worker.payload, dict) else {}
    return {
        "receipt_path": receipt_path,
        "worker_channel": worker.worker_channel or "unknown",
        "auth_channel": worker.auth_channel,
        "phase": step,
        "plan_id": str(state.get("name") or ""),
        "exit_kind": exit_kind,
        "payload_schema_valid": _payload_schema_valid(step, payload),
        "landed_diff": payload.get("landed_diff"),
        "worker_did_work": payload.get("worker_did_work"),
        "latency_ms": int(worker.duration_ms or 0),
        "cost_usd": float(worker.cost_usd or 0.0),
        "metadata": {
            "prompt_tokens": int(worker.prompt_tokens or 0),
            "completion_tokens": int(worker.completion_tokens or 0),
            "total_tokens": int(worker.total_tokens or 0),
            "session_id": worker.session_id,
        },
    }


def latency_cost_drift(
    primary: dict[str, Any],
    shadow: dict[str, Any],
) -> dict[str, Any]:
    primary_latency = primary.get("latency_ms")
    shadow_latency = shadow.get("latency_ms")
    primary_cost = primary.get("cost_usd")
    shadow_cost = shadow.get("cost_usd")
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
    return {
        "primary_latency_ms": primary_latency,
        "shadow_latency_ms": shadow_latency,
        "latency_drift_ms": latency_drift,
        "latency_drift_ratio": (
            latency_drift / primary_latency
            if isinstance(primary_latency, int) and primary_latency > 0 and latency_drift is not None
            else None
        ),
        "primary_cost_usd": primary_cost,
        "shadow_cost_usd": shadow_cost,
        "cost_drift_usd": cost_drift,
        "cost_drift_ratio": (
            cost_drift / float(primary_cost)
            if primary_cost not in (None, 0) and cost_drift is not None
            else None
        ),
    }


def _pressure_skip(worker: WorkerResult) -> str | None:
    if os.getenv("MEGAPLAN_CHANNEL_SHADOW_PRESSURE", "").strip().lower() in {"1", "true", "on", "yes"}:
        return "cap_pressure"
    if worker.rate_limit:
        return "rate_limited"
    return None


@contextmanager
def _shadow_channel_env(primary_worker_channel: str | None) -> Iterator[None]:
    original = os.environ.get("MEGAPLAN_SHANNON_STREAM_WORKER")
    if primary_worker_channel == "shannon_stream":
        os.environ["MEGAPLAN_SHANNON_STREAM_WORKER"] = "0"
    else:
        os.environ["MEGAPLAN_SHANNON_STREAM_WORKER"] = "1"
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("MEGAPLAN_SHANNON_STREAM_WORKER", None)
        else:
            os.environ["MEGAPLAN_SHANNON_STREAM_WORKER"] = original


def maybe_run_channel_shadow(
    *,
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: Any,
    step: str,
    primary_worker: WorkerResult,
    primary_agent: str,
    prompt_override: str | None,
    sample_key: str,
    resolved: Any,
) -> None:
    """Best-effort additive channel shadow; never changes the primary result."""
    if os.getenv("MEGAPLAN_CHANNEL_SHADOW", "1").strip().lower() in {"0", "false", "off", "no"}:
        return
    if primary_agent not in {"claude", "shannon"}:
        return

    experiment_id = str(state.get("name") or plan_dir.name)
    sample_rate = channel_shadow_sample_rate()
    sampled = _sampled(sample_key, sample_rate)
    provenance = {
        "source": CHANNEL_SHADOW_HOOK_PROVENANCE_SOURCE,
        "fixture": False,
        "sample_key": sample_key,
        "plan_id": experiment_id,
        "phase": step,
    }
    primary_summary = receipt_summary(
        worker=primary_worker,
        step=step,
        state=state,
        exit_kind="success",
    )
    channel_pair = {
        "primary_worker_channel": primary_worker.worker_channel or "unknown",
        "primary_auth_channel": primary_worker.auth_channel,
        "shadow_worker_channel": (
            "shannon_tmux" if primary_worker.worker_channel == "shannon_stream" else "shannon_stream"
        ),
        "shadow_auth_channel": primary_worker.auth_channel,
    }

    skip_reason = None if sampled else "not_sampled"
    if skip_reason is None:
        skip_reason = _pressure_skip(primary_worker)
    if skip_reason is not None:
        _append_record(
            root,
            experiment_id,
            {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "real_parity_success_count": 0,
                "channel_pair": channel_pair,
                "provenance": provenance,
                "decision": _decision(
                    sample_key=sample_key,
                    sample_rate=sample_rate,
                    sampled=sampled,
                    skip_reason=skip_reason,
                ),
                "primary_receipt": primary_summary,
                "shadow_receipt": None,
                "drift": None,
                "parity_result": None,
            },
        )
        return

    shadow_state = copy.deepcopy(state)
    try:
        with _shadow_channel_env(primary_worker.worker_channel):
            shadow_worker, _shadow_agent, _shadow_mode, _shadow_refreshed = worker_module.run_step_with_worker(
                step,
                shadow_state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_override=prompt_override,
            )
    except CliError as error:
        if error.code == "rate_limit" and error.extra.get("source") == "host_turn_cap":
            reason = "cap_pressure"
        else:
            reason = "shadow_unavailable"
        _append_record(
            root,
            experiment_id,
            {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "real_parity_success_count": 0,
                "channel_pair": channel_pair,
                "provenance": provenance,
                "decision": _decision(
                    sample_key=sample_key,
                    sample_rate=sample_rate,
                    sampled=True,
                    skip_reason=reason,
                ),
                "primary_receipt": primary_summary,
                "shadow_receipt": None,
                "drift": None,
                "parity_result": None,
            },
        )
        return

    shadow_summary = receipt_summary(
        worker=shadow_worker,
        step=step,
        state=state,
        exit_kind="success",
    )
    channel_pair["shadow_worker_channel"] = shadow_worker.worker_channel or channel_pair["shadow_worker_channel"]
    channel_pair["shadow_auth_channel"] = shadow_worker.auth_channel
    parity_result = compare_channel_parity(primary_summary, shadow_summary)
    _append_record(
        root,
        experiment_id,
        {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "real_parity_success_count": 0,
            "channel_pair": channel_pair,
            "provenance": provenance,
            "decision": _decision(
                sample_key=sample_key,
                sample_rate=sample_rate,
                sampled=True,
                skip_reason=None,
            ),
            "primary_receipt": primary_summary,
            "shadow_receipt": shadow_summary,
            "drift": latency_cost_drift(primary_summary, shadow_summary),
            "parity_result": parity_result,
        },
    )
