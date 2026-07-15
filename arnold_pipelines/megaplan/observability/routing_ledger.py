"""Best-effort per-plan routing ledger for model invocations."""

from __future__ import annotations

import fcntl
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.fallback_chains import fallback_observability_fields
from arnold_pipelines.megaplan.types import AgentSpec, format_agent_spec

log = logging.getLogger("megaplan")

LEDGER_FILE = "routing_ledger.jsonl"
_LOCK_FILE = ".routing_ledger.lock"


def normalize_routing_phase(step: str) -> str:
    if step.startswith("tiebreaker_"):
        return step
    if step.startswith("prep"):
        return "prep"
    if step == "loop_plan":
        return "plan"
    if step == "loop_execute":
        return "execute"
    return step


def format_selected_spec(agent: str | None, model: str | None, effort: str | None = None) -> str | None:
    if not agent:
        return None
    return format_agent_spec(AgentSpec(agent, model=model, effort=effort))


def strip_provider_prefix(model: str | None) -> str | None:
    if not isinstance(model, str) or not model.strip():
        return None
    value = model.strip()
    provider, sep, bare = value.partition(":")
    known_prefixes = {
        "anthropic",
        "claude",
        "codex",
        "deepseek",
        "fireworks",
        "hermes",
        "local",
        "minimax",
        "nous",
        "openai",
        "openrouter",
        "zhipu",
    }
    if sep and provider.lower() in known_prefixes and bare:
        return bare
    return value


def is_codex_gpt5_family(model: str | None) -> bool:
    bare = strip_provider_prefix(model)
    return isinstance(bare, str) and bare.lower().startswith("gpt-5")


def models_match(selected: str | None, actual: str | None) -> bool:
    if not selected or not actual:
        return True
    if selected == actual or strip_provider_prefix(selected) == strip_provider_prefix(actual):
        return True
    if is_codex_gpt5_family(selected) and is_codex_gpt5_family(actual):
        return True
    return False


def record_step_routing(
    plan_dir: Path,
    *,
    phase: str,
    step_label: str,
    agent: str | None,
    selected_spec: str | None,
    resolved_model: str | None,
    actual_model: str | None,
    tier: int | None = None,
    complexity: int | None = None,
    tier_routing_active: bool = False,
    configured_specs: list[str] | tuple[str, ...] | str | None = None,
    attempt_index: int = 0,
    attempted_specs: list[str] | tuple[str, ...] | str | None = None,
    failed_attempt_reasons: list[str] | tuple[str, ...] | None = None,
    fallback_trigger: str | None = None,
    mutation_safety: dict[str, Any] | None = None,
) -> None:
    """Append one routing ledger row; never raise to phase control flow."""
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": normalize_routing_phase(phase),
            "step_label": step_label,
            "agent": agent,
            "selected_spec": selected_spec,
            "resolved_model": resolved_model,
            "actual_model": actual_model,
            "tier": tier if tier_routing_active else None,
            "complexity": complexity,
            "tier_routing_active": bool(tier_routing_active),
        }
        record.update(
            fallback_observability_fields(
                configured_specs or selected_spec,
                attempt_index=attempt_index,
                attempted_specs=attempted_specs,
                failed_attempt_reasons=failed_attempt_reasons,
                fallback_trigger=fallback_trigger,
            )
        )
        if mutation_safety is not None:
            record["mutation_safety"] = dict(mutation_safety)
        lock_path = plan_dir / _LOCK_FILE
        ledger_path = plan_dir / LEDGER_FILE
        if not plan_dir.is_dir():
            log.debug(
                "Skipping routing ledger write for missing plan directory %s (%s/%s)",
                plan_dir,
                phase,
                step_label,
            )
            return
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                with ledger_path.open("a", encoding="utf-8") as ledger:
                    ledger.write(line)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

        if resolved_model and actual_model is None:
            log.warning(
                "Routing ledger actual model missing for %s/%s",
                record["phase"],
                step_label,
            )
        if not models_match(resolved_model, actual_model):
            _emit_routing_degradation(plan_dir, record)
    except Exception:
        log.warning("Routing ledger write failed for %s/%s", phase, step_label, exc_info=True)


def _emit_routing_degradation(plan_dir: Path, record: dict[str, Any]) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind, emit

        emit(
            EventKind.ROUTING_DEGRADATION,
            plan_dir=plan_dir,
            phase=record["phase"],
            payload={
                "step_label": record["step_label"],
                "degradations": [
                    f"selected model {record.get('resolved_model')} but provider reported {record.get('actual_model')}"
                ],
                "routing": dict(record),
            },
        )
    except Exception:
        log.warning("Routing degradation event emission failed", exc_info=True)
