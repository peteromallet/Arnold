"""Gate preflight checks and guidance helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.schema_projection import (
    project_schema_owned_fields,
    require_schema_fields,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS, GateArtifact, GatePayload
from arnold_pipelines.megaplan.types import GateCheckResult, PlanState
from arnold_pipelines.megaplan._core import latest_plan_meta_path, load_flag_registry, read_json, unresolved_significant_flags


AGENT_AVAILABILITY_PREFLIGHT_CHECKS = frozenset({"claude_available", "codex_available"})
OPERATIONAL_UNVERIFIABLE_REASON_MARKERS = (
    "rate limit",
    "rate_limit",
    "quota",
    "capacity",
    "bwrap",
    "bubblewrap",
    "sandbox namespace",
    "no permissions to create new namespace",
    "shell/file access is blocked in this environment",
)
OPERATIONAL_UNVERIFIABLE_CAUSES = frozenset(
    {
        "provider_rate_limit",
        "provider_capacity",
        "sandbox_namespace",
    }
)
OPERATIONAL_UNVERIFIABLE_ERROR_KINDS = frozenset(
    {
        "rate_limit",
        "sandbox_namespace",
    }
)


def is_operational_unverifiable_check(check: dict[str, Any]) -> bool:
    """Return true when missing critique evidence is due to transient infrastructure."""
    cause = str(check.get("cause", "")).lower()
    if cause in OPERATIONAL_UNVERIFIABLE_CAUSES:
        return True
    error_kind = str(check.get("error_kind", "")).lower()
    if error_kind in OPERATIONAL_UNVERIFIABLE_ERROR_KINDS:
        return True
    reason = str(check.get("reason", "")).lower()
    return any(marker in reason for marker in OPERATIONAL_UNVERIFIABLE_REASON_MARKERS)


def has_high_complexity_unverifiable_checks(signals: dict[str, Any]) -> list[dict[str, Any]]:
    """Return high-complexity unverifiable checks that should block gate PROCEED."""
    unverifiable = signals.get("unverifiable_checks")
    if not isinstance(unverifiable, list):
        return []
    return [
        check
        for check in unverifiable
        if isinstance(check, dict) and check.get("attention") == "high_complexity_unverifiable"
        and not is_operational_unverifiable_check(check)
    ]


def run_gate_checks(
    plan_dir: Path,
    state: PlanState,
    *,
    command_lookup: Callable[[str], str | None] | None = None,
) -> GateCheckResult:
    project_dir = Path(state["config"]["project_dir"])
    meta = read_json(latest_plan_meta_path(plan_dir, state))
    flag_registry = load_flag_registry(plan_dir)
    unresolved = unresolved_significant_flags(flag_registry)
    lookup = command_lookup or (lambda name: None)
    configured_agent = state.get("config", {}).get("agent", "")
    checks: dict[str, bool] = {
        "project_dir_exists": project_dir.exists(),
        "project_dir_writable": os.access(project_dir, os.W_OK),
        "success_criteria_present": bool(meta.get("success_criteria")),
    }
    if configured_agent != "hermes":
        checks["claude_available"] = bool(lookup("claude"))
        checks["codex_available"] = bool(lookup("codex"))
    return {
        "passed": all(checks.values()),
        "criteria_check": {
            "count": len(meta.get("success_criteria", [])),
            "items": meta.get("success_criteria", []),
        },
        "preflight_results": checks,
        "unresolved_flags": unresolved,
    }


def failed_preflight_checks(preflight_results: dict[str, bool]) -> list[str]:
    return [name for name, passed in preflight_results.items() if not passed]


def only_agent_availability_preflight_failed(preflight_results: dict[str, bool]) -> bool:
    failed = set(failed_preflight_checks(preflight_results))
    return bool(failed) and failed <= AGENT_AVAILABILITY_PREFLIGHT_CHECKS


def build_gate_artifact(
    signals: dict[str, Any],
    gate_payload: GatePayload,
    *,
    override_forced: bool,
    orchestrator_guidance: str = "",
) -> GateArtifact:
    from arnold_pipelines.megaplan.north_star_actions import normalize_north_star_actions

    require_schema_fields(
        gate_payload,
        SCHEMAS["gate.json"],
        contract="gate artifact persistence",
    )
    preflight = signals["preflight_results"]
    recommendation = gate_payload["recommendation"]
    warnings = list(signals.get("warnings", [])) + list(gate_payload.get("warnings", []))
    raw_north_star = gate_payload["north_star_actions"]
    if not isinstance(raw_north_star, list):
        raise RuntimeError(
            "gate artifact persistence: north_star_actions must be a list; "
            "refusing to default an invalid required field"
        )
    north_star_actions = normalize_north_star_actions(raw_north_star)
    artifact: GateArtifact = {
        **project_schema_owned_fields(
            gate_payload,
            SCHEMAS["gate.json"],
            contract="gate artifact persistence",
        ),
        "passed": recommendation == "PROCEED" and all(preflight.values()),
        "criteria_check": signals["criteria_check"],
        "preflight_results": preflight,
        "unresolved_flags": signals["unresolved_flags"],
        "addressed_flags": list(signals["signals"].get("addressed_flags", [])),
        "recommendation": recommendation,
        "rationale": gate_payload["rationale"],
        "signals_assessment": gate_payload["signals_assessment"],
        "warnings": warnings,
        "settled_decisions": list(gate_payload.get("settled_decisions", [])),
        "override_forced": override_forced,
        "orchestrator_guidance": orchestrator_guidance,
        "robustness": signals.get("robustness"),
        "signals": signals["signals"],
        "flag_resolutions": list(gate_payload.get("flag_resolutions", [])),
        "resolved_flag_ids": list(gate_payload.get("resolved_flag_ids", [])),
        "resolution_summary": gate_payload.get("resolution_summary", ""),
        "north_star_actions": north_star_actions,
    }
    return artifact


def build_orchestrator_guidance(
    gate_payload: GatePayload,
    signals: dict[str, Any],
    preflight_passed: bool,
    preflight_results: dict[str, bool],
    robustness: str,
    plan_name: str,
    strict_notes: bool = False,
) -> str:
    """Return plain-language next-step guidance for the orchestrator."""
    recommendation = gate_payload["recommendation"]
    iteration = int(signals.get("iteration", 0))
    weighted_score = float(signals.get("weighted_score", 0.0))
    weighted_history = list(signals.get("weighted_history", []))
    recurring_critiques = list(signals.get("recurring_critiques", []))
    unresolved_flags = list(signals.get("unresolved_flags", []))
    scope_creep = list(signals.get("scope_creep_flags", []))
    previous_score = float(weighted_history[-1]) if weighted_history else None
    plateaued = previous_score is not None and weighted_score >= previous_score
    worsening = previous_score is not None and weighted_score > previous_score
    improving = previous_score is not None and weighted_score < previous_score

    if iteration == 1:
        guidance = f"First iteration; follow gate recommendation: {recommendation}."
    elif recommendation == "PROCEED" and preflight_passed:
        guidance = "Plan passed gate and preflight. Proceed to finalize."
    elif recommendation == "PROCEED":
        failing_checks = ", ".join(
            name for name, passed in preflight_results.items() if not passed
        )
        guidance = f"Gate says PROCEED but preflight blocked. Fix: {failing_checks}."
    elif recommendation == "ESCALATE":
        if strict_notes:
            guidance = (
                "STRICT: gate escalated. Stop and ask the user. "
                "Force-proceed requires --user-approved."
            )
        else:
            guidance = "Gate escalated. Ask the user: force-proceed, add-note, or abort."
    elif recommendation == "ITERATE" and plateaued and recurring_critiques:
        guidance = (
            "Score plateaued with recurring critiques the loop can't fix. Consider "
            f"force-proceeding: `megaplan override force-proceed --plan {plan_name}`"
        )
    elif recommendation == "ITERATE" and improving:
        guidance = f"Score improving ({previous_score} -> {weighted_score}). Continue to revise."
    elif recommendation == "ITERATE" and worsening:
        guidance = (
            f"Score worsening ({previous_score} -> {weighted_score}). "
            "Investigate; the loop may be diverging."
        )
    else:
        guidance = "Gate recommends another iteration. Revise the plan."

    hints: list[str] = []
    if unresolved_flags:
        hints.append("Verify unresolved flags against the plan and project code before accepting.")
    if recurring_critiques:
        critiques = ", ".join(recurring_critiques)
        hints.append(
            f"Recurring critiques ({critiques}); the loop likely can't fix these, so judge if they are real blockers."
        )
    if scope_creep:
        hints.append("Scope creep detected; compare the current plan against the original idea.")
    if robustness:
        del robustness

    return " ".join([guidance, *hints]).strip()
