"""Megaplan — stateful orchestration CLI for high-rigor planning loops."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.23.0"

_SYMBOL_EXPORTS = {
    # Types
    "PlanState": "megaplan.types",
    "PlanConfig": "megaplan.types",
    "PlanMeta": "megaplan.types",
    "FlagRecord": "megaplan.types",
    "StepResponse": "megaplan.types",
    # State constants
    "STATE_INITIALIZED": "megaplan.types",
    "STATE_PLANNED": "megaplan.types",
    "STATE_CRITIQUED": "megaplan.types",
    "STATE_GATED": "megaplan.types",
    "STATE_FINALIZED": "megaplan.types",
    "STATE_EXECUTED": "megaplan.types",
    "STATE_REVIEWED": "megaplan.types",
    "STATE_DONE": "megaplan.types",
    "STATE_ABORTED": "megaplan.types",
    "STATE_FAILED": "megaplan.types",
    "STATE_BLOCKED": "megaplan.types",
    "STATE_PAUSED": "megaplan.types",
    "STATE_CANCELLED": "megaplan.types",
    "TERMINAL_STATES": "megaplan.types",
    "MOCK_ENV_VAR": "megaplan.types",
    "ROBUSTNESS_LEVELS": "megaplan.types",
    # Error and result types
    "CliError": "megaplan.types",
    "CommandResult": "megaplan.workers",
    "WorkerResult": "megaplan.workers",
    # Handlers
    "handle_init": "megaplan.handlers",
    "handle_plan": "megaplan.handlers",
    "handle_critique": "megaplan.handlers",
    "handle_revise": "megaplan.handlers",
    "handle_gate": "megaplan.handlers",
    "handle_finalize": "megaplan.handlers",
    "handle_execute": "megaplan.handlers",
    "handle_review": "megaplan.handlers",
    "handle_step": "megaplan.execute.step_edit",
    "handle_status": "megaplan.cli",
    "handle_audit": "megaplan.cli",
    "handle_progress": "megaplan.cli",
    "handle_list": "megaplan.cli",
    "handle_override": "megaplan.handlers",
    "handle_setup": "megaplan.cli",
    "handle_setup_global": "megaplan.cli",
    "handle_config": "megaplan.cli",
    # Key utilities
    "slugify": "megaplan._core",
    "build_gate_signals": "megaplan.orchestration.evaluation",
    "mock_worker_output": "megaplan.workers",
    "build_orchestrator_guidance": "megaplan.orchestration.evaluation",
    "compute_plan_delta_percent": "megaplan.orchestration.evaluation",
    "compute_recurring_critiques": "megaplan.orchestration.evaluation",
    "flag_weight": "megaplan.orchestration.evaluation",
    "infer_next_steps": "megaplan._core",
    "resume_plan": "megaplan._core",
    "workflow_includes_step": "megaplan._core",
    "workflow_next": "megaplan._core",
    "normalize_flag_record": "megaplan.flags",
    "update_flags_after_critique": "megaplan.flags",
    "update_flags_after_revise": "megaplan.flags",
    "unresolved_significant_flags": "megaplan._core",
    "config_dir": "megaplan._core",
    "load_config": "megaplan._core",
    "save_config": "megaplan._core",
    "plans_root": "megaplan._core",
    "main": "megaplan.cli",
    "cli_entry": "megaplan.cli",
}

__all__ = [
    # Types
    "PlanState", "PlanConfig", "PlanMeta", "FlagRecord", "StepResponse",
    # State constants
    "STATE_INITIALIZED", "STATE_PLANNED", "STATE_CRITIQUED",
    "STATE_GATED", "STATE_FINALIZED", "STATE_EXECUTED", "STATE_REVIEWED", "STATE_DONE", "STATE_ABORTED",
    "STATE_FAILED", "STATE_BLOCKED", "STATE_PAUSED", "STATE_CANCELLED",
    "TERMINAL_STATES", "MOCK_ENV_VAR", "ROBUSTNESS_LEVELS",
    # Error and result types
    "CliError", "CommandResult", "WorkerResult",
    # Handlers
    "handle_init", "handle_plan", "handle_critique",
    "handle_revise", "handle_gate", "handle_finalize", "handle_execute",
    "handle_review", "handle_step", "handle_status", "handle_audit", "handle_progress", "handle_list",
    "handle_override", "handle_setup", "handle_setup_global", "handle_config",
    # Key utilities
    "slugify", "build_gate_signals", "mock_worker_output",
    "build_orchestrator_guidance",
    "compute_plan_delta_percent", "compute_recurring_critiques", "flag_weight",
    "infer_next_steps", "resume_plan", "workflow_includes_step", "workflow_next", "normalize_flag_record",
    "update_flags_after_critique", "update_flags_after_revise",
    "unresolved_significant_flags",
    "config_dir", "load_config", "save_config", "plans_root",
    "main", "cli_entry",
]


def __getattr__(name: str) -> Any:
    if name in _SYMBOL_EXPORTS:
        module = import_module(_SYMBOL_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
