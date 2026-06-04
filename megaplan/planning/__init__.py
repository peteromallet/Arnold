"""Planning-specific control bindings, lifecycle state, and profile-policy exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_SYMBOL_EXPORTS = {
    "AUTOMATION_TERMINAL_STATES": "megaplan.planning.state",
    "CANONICAL_PLAN_STATES": "megaplan.planning.state",
    "DEFAULT_AGENT_ROUTING": "megaplan.profiles.policy",
    "KNOWN_AGENTS": "megaplan.profiles.policy",
    "PlanCurrentState": "megaplan.planning.state",
    "PlanningControlBinding": "megaplan.planning.control_binding",
    "ROBUSTNESS_ACCEPTED": "megaplan.profiles.policy",
    "ROBUSTNESS_LEVELS": "megaplan.profiles.policy",
    "STATE_ABORTED": "megaplan.planning.state",
    "STATE_AWAITING_HUMAN": "megaplan.planning.state",
    "STATE_AWAITING_HUMAN_VERIFY": "megaplan.planning.state",
    "STATE_AWAITING_PR_MERGE": "megaplan.planning.state",
    "STATE_BLOCKED": "megaplan.planning.state",
    "STATE_CANCELLED": "megaplan.planning.state",
    "STATE_CRITIQUED": "megaplan.planning.state",
    "STATE_DONE": "megaplan.planning.state",
    "STATE_EXECUTED": "megaplan.planning.state",
    "STATE_FAILED": "megaplan.planning.state",
    "STATE_FINALIZED": "megaplan.planning.state",
    "STATE_GATED": "megaplan.planning.state",
    "STATE_INITIALIZED": "megaplan.planning.state",
    "STATE_PAUSED": "megaplan.planning.state",
    "STATE_PLANNED": "megaplan.planning.state",
    "STATE_PREPPED": "megaplan.planning.state",
    "STATE_REVIEWED": "megaplan.planning.state",
    "STATE_TIEBREAKER_PENDING": "megaplan.planning.state",
    "STATE_TIEBREAKER_READY": "megaplan.planning.state",
    "SYSTEM_DEFAULT_PROFILE": "megaplan.profiles.policy",
    "TERMINAL_STATES": "megaplan.planning.state",
    "VALID_PHASE_KEYS": "megaplan.profiles.policy",
    "normalize_robustness": "megaplan.profiles.policy",
    "planning_control_binding": "megaplan.planning.control_binding",
    "planning_run_state_view": "megaplan.planning.control_binding",
    "planning_supervisor_run_state_view": "megaplan.planning.control_binding",
    "validate_plan_current_state": "megaplan.planning.state",
}

__all__ = list(_SYMBOL_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _SYMBOL_EXPORTS:
        module = import_module(_SYMBOL_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
