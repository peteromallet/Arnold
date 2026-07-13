"""Receipt construction helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.fallback_chains import (
    configured_fallback_chain_for_phase,
    fallback_observability_fields,
)
from arnold_pipelines.megaplan.observability.routing_ledger import format_selected_spec
from arnold_pipelines.megaplan.receipts.canonical import CANONICALIZATION_VERSION, hash_prompts
from arnold_pipelines.megaplan.receipts.extractors import extract_for_phase, load_and_extract
from arnold_pipelines.megaplan.receipts.schema import Receipt, upstream_artifact_hashes


def _configured_chain_for_phase(phase: str, args: Any) -> tuple[str, ...] | None:
    chain = configured_fallback_chain_for_phase(getattr(args, "phase_model", None), phase)
    return chain.specs if chain is not None else None


def _worker_selected_spec(worker: Any) -> str | None:
    configured = getattr(worker, "configured_specs", None)
    if not configured:
        return None
    try:
        index = int(getattr(worker, "attempt_index", 0) or 0)
    except (TypeError, ValueError):
        index = 0
    if index < 0 or index >= len(configured):
        index = 0
    selected = configured[index]
    return selected if isinstance(selected, str) and selected else None


def _configured_model_for_phase(phase: str, args: Any, agent: str, worker: Any) -> str | None:
    selected_from_worker = _worker_selected_spec(worker)
    if selected_from_worker is not None:
        return selected_from_worker
    configured_chain = _configured_chain_for_phase(phase, args)
    if configured_chain:
        return configured_chain[0]
    hermes_model = getattr(args, "hermes", None)
    if agent == "hermes" and isinstance(hermes_model, str) and hermes_model:
        return hermes_model
    explicit_agent = getattr(args, "agent", None)
    if isinstance(explicit_agent, str) and explicit_agent:
        return explicit_agent
    return None


def build_receipt(
    *,
    phase: str,
    state: dict[str, Any],
    plan_dir: Path,
    args: Any,
    worker: Any,
    agent: str,
    mode: str,
    output_file: str,
    artifact_hash: str,
    verdict: str | None,
    drift: Any = None,
) -> Receipt:
    del output_file, artifact_hash
    import arnold_pipelines.megaplan as megaplan

    project_dir = Path(state["config"]["project_dir"])
    plan_id = state["name"]
    rendered_prompt = getattr(worker, "rendered_prompt", None)
    if rendered_prompt is not None:
        prompt_hash_raw, prompt_hash_canonical = hash_prompts(
            rendered_prompt,
            project_dir=project_dir,
            plan_dir=plan_dir,
            plan_id=plan_id,
        )
    else:
        prompt_hash_raw = None
        prompt_hash_canonical = None

    metrics_override = getattr(worker, "receipt_metrics", None)
    if isinstance(metrics_override, dict):
        metrics = metrics_override
    elif phase == "prep":
        metrics = load_and_extract(plan_dir, phase, int(state.get("iteration", 0)), drift_report=drift)
    else:
        metrics = extract_for_phase(phase, getattr(worker, "payload", {}), drift_report=drift)
    profile_name = state.get("meta", {}).get("profile_name") or getattr(args, "profile", None)
    if profile_name is None:
        profile_name = state.get("config", {}).get("profile")
    agent_mode = "persistent" if mode == "persistent" else "oneshot"
    configured_specs = (
        getattr(worker, "configured_specs", None)
        or _configured_chain_for_phase(phase, args)
        or (_configured_model_for_phase(phase, args, agent, worker) or format_selected_spec(agent, None) or agent,)
    )
    fallback_fields = fallback_observability_fields(
        configured_specs,
        attempt_index=int(getattr(worker, "attempt_index", 0) or 0),
        attempted_specs=getattr(worker, "attempted_specs", None),
        failed_attempt_reasons=getattr(worker, "failed_attempt_reasons", None),
        fallback_trigger=getattr(worker, "fallback_trigger", None),
    )

    return {
        "receipt_id": str(uuid.uuid4()),
        "plan_id": plan_id,
        "phase": phase,
        "iteration": int(state.get("iteration", 0)),
        "attempt": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "profile_name": profile_name,
        "agent": agent,
        "agent_mode": agent_mode,
        "model_configured": _configured_model_for_phase(phase, args, agent, worker),
        "model_actual": getattr(worker, "model_actual", None),
        **fallback_fields,
        "session_id": getattr(worker, "session_id", None),
        "megaplan_version": getattr(megaplan, "__version__", "unknown"),
        "schema_version": 1,
        "prompt_hash_raw": prompt_hash_raw,
        "prompt_hash_canonical": prompt_hash_canonical,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "upstream_artifact_hashes": upstream_artifact_hashes(plan_dir, phase, int(state.get("iteration", 0))),
        "cost_usd": float(getattr(worker, "cost_usd", 0.0) or 0.0),
        "cost_pricing": getattr(worker, "cost_pricing", None),
        "duration_ms": int(getattr(worker, "duration_ms", 0) or 0),
        "prompt_tokens": int(getattr(worker, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(worker, "completion_tokens", 0) or 0),
        "verdict": verdict,
        "metrics": metrics,
        "scope_drift_severity": drift.severity if phase == "execute" and drift is not None else None,
        "shannon_plan": getattr(worker, "shannon_plan", None),
        "worker_channel": getattr(worker, "worker_channel", None),
        "auth_channel": getattr(worker, "auth_channel", None),
        "auth_metadata": getattr(worker, "auth_metadata", None),
    }
