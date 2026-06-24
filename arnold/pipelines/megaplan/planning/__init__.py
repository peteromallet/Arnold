"""Planning-specific control bindings, lifecycle state, and profile-policy exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_SYMBOL_EXPORTS = {
    "AUTOMATION_TERMINAL_STATES": "arnold.pipelines.megaplan.planning.state",
    "CANONICAL_PLAN_STATES": "arnold.pipelines.megaplan.planning.state",
    "DEFAULT_AGENT_ROUTING": "arnold.pipelines.megaplan.profiles.policy",
    "KNOWN_AGENTS": "arnold.pipelines.megaplan.profiles.policy",
    "PlanCurrentState": "arnold.pipelines.megaplan.planning.state",
    "PlanningControlBinding": "arnold.pipelines.megaplan.planning.control_binding",
    "ROBUSTNESS_ACCEPTED": "arnold.pipelines.megaplan.profiles.policy",
    "ROBUSTNESS_LEVELS": "arnold.pipelines.megaplan.profiles.policy",
    "STATE_ABORTED": "arnold.pipelines.megaplan.planning.state",
    "STATE_AWAITING_HUMAN": "arnold.pipelines.megaplan.planning.state",
    "STATE_AWAITING_HUMAN_VERIFY": "arnold.pipelines.megaplan.planning.state",
    "STATE_AWAITING_PR_MERGE": "arnold.pipelines.megaplan.planning.state",
    "STATE_BLOCKED": "arnold.pipelines.megaplan.planning.state",
    "STATE_CANCELLED": "arnold.pipelines.megaplan.planning.state",
    "STATE_CRITIQUED": "arnold.pipelines.megaplan.planning.state",
    "STATE_DONE": "arnold.pipelines.megaplan.planning.state",
    "STATE_EXECUTED": "arnold.pipelines.megaplan.planning.state",
    "STATE_FAILED": "arnold.pipelines.megaplan.planning.state",
    "STATE_FINALIZED": "arnold.pipelines.megaplan.planning.state",
    "STATE_GATED": "arnold.pipelines.megaplan.planning.state",
    "STATE_INITIALIZED": "arnold.pipelines.megaplan.planning.state",
    "STATE_PAUSED": "arnold.pipelines.megaplan.planning.state",
    "STATE_PLANNED": "arnold.pipelines.megaplan.planning.state",
    "STATE_PREPPED": "arnold.pipelines.megaplan.planning.state",
    "STATE_REVIEWED": "arnold.pipelines.megaplan.planning.state",
    "STATE_TIEBREAKER_PENDING": "arnold.pipelines.megaplan.planning.state",
    "STATE_TIEBREAKER_READY": "arnold.pipelines.megaplan.planning.state",
    "SYSTEM_DEFAULT_PROFILE": "arnold.pipelines.megaplan.profiles.policy",
    "TERMINAL_STATES": "arnold.pipelines.megaplan.planning.state",
    "VALID_PHASE_KEYS": "arnold.pipelines.megaplan.profiles.policy",
    "normalize_robustness": "arnold.pipelines.megaplan.profiles.policy",
    "planning_control_binding": "arnold.pipelines.megaplan.planning.control_binding",
    "planning_run_state_view": "arnold.pipelines.megaplan.planning.control_binding",
    "planning_supervisor_run_state_view": "arnold.pipelines.megaplan.planning.control_binding",
    "validate_plan_current_state": "arnold.pipelines.megaplan.planning.state",
}

__all__ = list(_SYMBOL_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _SYMBOL_EXPORTS:
        module = import_module(_SYMBOL_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
