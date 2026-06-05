"""Megaplan planning pipeline — Arnold plugin.

This package is the canonical home for the Megaplan planning pipeline
implementation.  Registry discovery scans ``arnold/pipelines`` before
``megaplan/pipelines``, so this plugin wins deduplication.

Modules:

* ``pipeline.py`` — canonical ``build_pipeline()`` and ``compile_planning_pipeline``.
* ``routing.py`` — planning decision literals and routing helpers.
* ``handlers/`` — handler bridge modules (M5a/M5b deferred).
* ``stages/`` — stage implementation classes.

Operation dispatch lives at ``arnold.pipelines.megaplan.planning.operations``
(canonical) — the old ``operations.py`` adapter has been removed.

**Import note:** Top-level symbols are loaded lazily via ``__getattr__``
to prevent circular imports when orchestration/audit/execute/review
facades import from this package during handler initialization (SD2).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

name: str = "megaplan"
description: str = (
    "Canonical Megaplan planning pipeline: prep, plan, critique, gate, "
    "revise, finalize, execute, review, and tiebreaker."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("code", "doc", "creative", "joke")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("megaplan", "planning")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning", "execution", "review")


def build_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Return the canonical Megaplan planning pipeline."""

    module = import_module("arnold.pipelines.megaplan.pipeline")
    return module.build_pipeline(*args, **kwargs)


def compile_planning_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Return the canonical Megaplan planning pipeline."""

    module = import_module("arnold.pipelines.megaplan.pipeline")
    return module.compile_planning_pipeline(*args, **kwargs)


_SYMBOL_EXPORTS = {
    # Arnold plugin exports (canonical pipeline constructors)
    "build_pipeline": "arnold.pipelines.megaplan.pipeline",
    "compile_planning_pipeline": "arnold.pipelines.megaplan.pipeline",
    "operation_registry": "arnold.pipelines.megaplan.planning.operations",
    "override_catalog": "arnold.pipelines.megaplan.planning.operations",
    # Types
    "PlanState": "arnold.pipelines.megaplan.types",
    "PlanConfig": "arnold.pipelines.megaplan.types",
    "PlanMeta": "arnold.pipelines.megaplan.types",
    "FlagRecord": "arnold.pipelines.megaplan.types",
    "StepResponse": "arnold.pipelines.megaplan.types",
    "ArtifactRequest": "arnold.pipelines.megaplan.control_interface",
    "ControlBinding": "arnold.pipelines.megaplan.control_interface",
    "ControlInterfaceTarget": "arnold.pipelines.megaplan.control_interface",
    "ControlProjection": "arnold.pipelines.megaplan.control_interface",
    "ControlTargetRef": "arnold.pipelines.megaplan.control_interface",
    "ControlTransition": "arnold.pipelines.megaplan.control_interface",
    "ControlTransitionConflict": "arnold.pipelines.megaplan.control_interface",
    "ControlTransitionRequest": "arnold.pipelines.megaplan.control_interface",
    "ControlTransitionResult": "arnold.pipelines.megaplan.control_interface",
    "RunOutcome": "arnold.pipelines.megaplan.run_outcome",
    "RunResultMetadata": "arnold.pipelines.megaplan.run_outcome",
    "RunStateView": "arnold.pipelines.megaplan.control_interface",
    # State constants
    "STATE_INITIALIZED": "arnold.pipelines.megaplan.planning.state",
    "STATE_PLANNED": "arnold.pipelines.megaplan.planning.state",
    "STATE_CRITIQUED": "arnold.pipelines.megaplan.planning.state",
    "STATE_GATED": "arnold.pipelines.megaplan.planning.state",
    "STATE_FINALIZED": "arnold.pipelines.megaplan.planning.state",
    "STATE_EXECUTED": "arnold.pipelines.megaplan.planning.state",
    "STATE_REVIEWED": "arnold.pipelines.megaplan.planning.state",
    "STATE_DONE": "arnold.pipelines.megaplan.planning.state",
    "STATE_ABORTED": "arnold.pipelines.megaplan.planning.state",
    "STATE_FAILED": "arnold.pipelines.megaplan.planning.state",
    "STATE_BLOCKED": "arnold.pipelines.megaplan.planning.state",
    "STATE_PAUSED": "arnold.pipelines.megaplan.planning.state",
    "STATE_CANCELLED": "arnold.pipelines.megaplan.planning.state",
    "TERMINAL_STATES": "arnold.pipelines.megaplan.planning.state",
    "MOCK_ENV_VAR": "arnold.pipelines.megaplan.types",
    "ROBUSTNESS_LEVELS": "arnold.pipelines.megaplan.profiles.policy",
    # Error and result types
    "CliError": "arnold.pipelines.megaplan.types",
    "CommandResult": "arnold.pipelines.megaplan.workers",
    "WorkerResult": "arnold.pipelines.megaplan.workers",
    # Handlers
    "handle_init": "arnold.pipelines.megaplan.handlers",
    "handle_plan": "arnold.pipelines.megaplan.handlers",
    "handle_critique": "arnold.pipelines.megaplan.handlers",
    "handle_revise": "arnold.pipelines.megaplan.handlers",
    "handle_gate": "arnold.pipelines.megaplan.handlers",
    "handle_finalize": "arnold.pipelines.megaplan.handlers",
    "handle_execute": "arnold.pipelines.megaplan.handlers",
    "handle_review": "arnold.pipelines.megaplan.handlers",
    "handle_step": "arnold.pipelines.megaplan.execute.step_edit",
    "handle_status": "arnold.pipelines.megaplan.cli",
    "handle_audit": "arnold.pipelines.megaplan.cli",
    "handle_progress": "arnold.pipelines.megaplan.cli",
    "handle_list": "arnold.pipelines.megaplan.cli",
    "handle_override": "arnold.pipelines.megaplan.handlers",
    "handle_setup": "arnold.pipelines.megaplan.cli",
    "handle_setup_global": "arnold.pipelines.megaplan.cli",
    "handle_config": "arnold.pipelines.megaplan.cli",
    # Key utilities
    "slugify": "arnold.pipelines.megaplan._core",
    "build_gate_signals": "arnold.pipelines.megaplan.orchestration.gate_signals",
    "mock_worker_output": "arnold.pipelines.megaplan.workers",
    "build_orchestrator_guidance": "arnold.pipelines.megaplan.orchestration.gate_checks",
    "compute_plan_delta_percent": "arnold.pipelines.megaplan.orchestration.gate_signals",
    "compute_recurring_critiques": "arnold.pipelines.megaplan.orchestration.gate_signals",
    "flag_weight": "arnold.pipelines.megaplan.orchestration.gate_signals",
    "infer_next_steps": "arnold.pipelines.megaplan._core",
    "resume_plan": "arnold.pipelines.megaplan._core",
    "workflow_includes_step": "arnold.pipelines.megaplan._core",
    "workflow_next": "arnold.pipelines.megaplan._core",
    "normalize_flag_record": "arnold.pipelines.megaplan.flags",
    "update_flags_after_critique": "arnold.pipelines.megaplan.flags",
    "update_flags_after_revise": "arnold.pipelines.megaplan.flags",
    "apply_transition": "arnold.pipelines.megaplan.control_interface",
    "read_valid_targets": "arnold.pipelines.megaplan.control_interface",
    "synthesize_artifacts": "arnold.pipelines.megaplan.control_interface",
    "run_metadata_from_batch_outcome": "arnold.pipelines.megaplan.run_outcome",
    "run_outcome_from_batch_outcome": "arnold.pipelines.megaplan.run_outcome",
    "unresolved_significant_flags": "arnold.pipelines.megaplan._core",
    "config_dir": "arnold.pipelines.megaplan._core",
    "load_config": "arnold.pipelines.megaplan._core",
    "save_config": "arnold.pipelines.megaplan._core",
    "plans_root": "arnold.pipelines.megaplan._core",
    "main": "arnold.pipelines.megaplan.cli",
    "cli_entry": "arnold.pipelines.megaplan.cli",
}

__all__ = [
    # Arnold plugin exports
    "build_pipeline", "compile_planning_pipeline",
    "operation_registry", "override_catalog",
    # Types
    "PlanState", "PlanConfig", "PlanMeta", "FlagRecord", "StepResponse",
    "ArtifactRequest", "ControlBinding", "ControlInterfaceTarget", "ControlProjection", "ControlTargetRef",
    "ControlTransition", "ControlTransitionConflict", "ControlTransitionRequest", "ControlTransitionResult",
    "RunOutcome", "RunResultMetadata", "RunStateView",
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
    "apply_transition", "read_valid_targets", "synthesize_artifacts",
    "run_metadata_from_batch_outcome", "run_outcome_from_batch_outcome",
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
