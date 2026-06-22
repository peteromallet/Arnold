"""Megaplan planning pipeline — Arnold plugin.

This package is the canonical home for the Megaplan planning pipeline
implementation.  Registry discovery scans ``arnold/pipelines`` before
``megaplan/pipelines``, so this plugin wins deduplication.

Modules:

* ``pipeline.py`` — canonical ``build_pipeline()`` and ``build_and_compile_pipeline()``.
* ``routing.py`` — planning decision literals and routing helpers.
* ``handlers/`` — handler bridge modules (M5a/M5b deferred).
* ``stages/`` — stage implementation classes.

Operation dispatch lives at ``arnold_pipelines.megaplan.planning.operations``
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
supported_modes: tuple[str, ...] = ("code", "doc", "creative", "joke", "plan")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("megaplan", "planning")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning", "execution", "review")


def build_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Return the canonical Megaplan planning pipeline."""

    module = import_module("arnold_pipelines.megaplan.pipeline")
    return module.build_pipeline(*args, **kwargs)



_SYMBOL_EXPORTS = {
    # Arnold plugin exports (canonical pipeline constructors)
    "build_pipeline": "arnold_pipelines.megaplan.pipeline",
    "build_and_compile_pipeline": "arnold_pipelines.megaplan.pipeline",

    "operation_registry": "arnold_pipelines.megaplan.planning.operations",
    "override_catalog": "arnold_pipelines.megaplan.planning.operations",
    # Types
    "PlanState": "arnold_pipelines.megaplan.types",
    "PlanConfig": "arnold_pipelines.megaplan.types",
    "PlanMeta": "arnold_pipelines.megaplan.types",
    "FlagRecord": "arnold_pipelines.megaplan.types",
    "StepResponse": "arnold_pipelines.megaplan.types",
    "ArtifactRequest": "arnold_pipelines.megaplan.control_interface",
    "ControlBinding": "arnold_pipelines.megaplan.control_interface",
    "ControlInterfaceTarget": "arnold_pipelines.megaplan.control_interface",
    "ControlProjection": "arnold_pipelines.megaplan.control_interface",
    "ControlTargetRef": "arnold_pipelines.megaplan.control_interface",
    "ControlTransition": "arnold_pipelines.megaplan.control_interface",
    "ControlTransitionConflict": "arnold_pipelines.megaplan.control_interface",
    "ControlTransitionRequest": "arnold_pipelines.megaplan.control_interface",
    "ControlTransitionResult": "arnold_pipelines.megaplan.control_interface",
    "RunOutcome": "arnold_pipelines.megaplan.run_outcome",
    "RunResultMetadata": "arnold_pipelines.megaplan.run_outcome",
    "RunStateView": "arnold_pipelines.megaplan.control_interface",
    "AuditStatus": "arnold_pipelines.megaplan.model_seam",
    "BudgetStatus": "arnold_pipelines.megaplan.model_seam",
    "CaptureOutcome": "arnold_pipelines.megaplan.model_seam",
    "ModelSeamTelemetry": "arnold_pipelines.megaplan.model_seam",
    "ModelStepInvocationAdapter": "arnold_pipelines.megaplan.model_seam",
    "ModelTier": "arnold_pipelines.megaplan.model_seam",
    "RenderedStepMessage": "arnold_pipelines.megaplan.model_seam",
    "TerminalStatus": "arnold_pipelines.megaplan.model_seam",
    "TierMetadata": "arnold_pipelines.megaplan.model_seam",
    "capture_step_output": "arnold_pipelines.megaplan.model_seam",
    "install_model_step_adapter": "arnold_pipelines.megaplan.model_seam",
    "render_step_message": "arnold_pipelines.megaplan.model_seam",
    # State constants
    "STATE_INITIALIZED": "arnold_pipelines.megaplan.planning.state",
    "STATE_PLANNED": "arnold_pipelines.megaplan.planning.state",
    "STATE_CRITIQUED": "arnold_pipelines.megaplan.planning.state",
    "STATE_GATED": "arnold_pipelines.megaplan.planning.state",
    "STATE_FINALIZED": "arnold_pipelines.megaplan.planning.state",
    "STATE_EXECUTED": "arnold_pipelines.megaplan.planning.state",
    "STATE_REVIEWED": "arnold_pipelines.megaplan.planning.state",
    "STATE_DONE": "arnold_pipelines.megaplan.planning.state",
    "STATE_ABORTED": "arnold_pipelines.megaplan.planning.state",
    "STATE_FAILED": "arnold_pipelines.megaplan.planning.state",
    "STATE_BLOCKED": "arnold_pipelines.megaplan.planning.state",
    "STATE_PAUSED": "arnold_pipelines.megaplan.planning.state",
    "STATE_CANCELLED": "arnold_pipelines.megaplan.planning.state",
    "TERMINAL_STATES": "arnold_pipelines.megaplan.planning.state",
    "MOCK_ENV_VAR": "arnold_pipelines.megaplan.types",
    "ROBUSTNESS_LEVELS": "arnold_pipelines.megaplan.profiles.policy",
    # Error and result types
    "CliError": "arnold_pipelines.megaplan.types",
    "CommandResult": "arnold_pipelines.megaplan.workers",
    "WorkerResult": "arnold_pipelines.megaplan.workers",
    # Handlers
    "handle_init": "arnold_pipelines.megaplan.handlers",
    "handle_plan": "arnold_pipelines.megaplan.handlers",
    "handle_critique": "arnold_pipelines.megaplan.handlers",
    "handle_revise": "arnold_pipelines.megaplan.handlers",
    "handle_gate": "arnold_pipelines.megaplan.handlers",
    "handle_finalize": "arnold_pipelines.megaplan.handlers",
    "handle_execute": "arnold_pipelines.megaplan.handlers",
    "handle_review": "arnold_pipelines.megaplan.handlers",
    "handle_step": "arnold_pipelines.megaplan.execute.step_edit",
    "handle_status": "arnold_pipelines.megaplan.cli",
    "handle_audit": "arnold_pipelines.megaplan.cli",
    "handle_progress": "arnold_pipelines.megaplan.cli",
    "handle_list": "arnold_pipelines.megaplan.cli",
    "handle_override": "arnold_pipelines.megaplan.handlers",
    "handle_setup": "arnold_pipelines.megaplan.cli",
    "handle_setup_global": "arnold_pipelines.megaplan.cli",
    "handle_config": "arnold_pipelines.megaplan.cli",
    # Key utilities
    "slugify": "arnold_pipelines.megaplan._core",
    "build_gate_signals": "arnold_pipelines.megaplan.orchestration.gate_signals",
    "mock_worker_output": "arnold_pipelines.megaplan.workers",
    "build_orchestrator_guidance": "arnold_pipelines.megaplan.orchestration.gate_checks",
    "compute_plan_delta_percent": "arnold_pipelines.megaplan.orchestration.gate_signals",
    "compute_recurring_critiques": "arnold_pipelines.megaplan.orchestration.gate_signals",
    "flag_weight": "arnold_pipelines.megaplan.orchestration.gate_signals",
    "infer_next_steps": "arnold_pipelines.megaplan._core",
    "resume_plan": "arnold_pipelines.megaplan._core",
    "workflow_includes_step": "arnold_pipelines.megaplan._core",
    "workflow_next": "arnold_pipelines.megaplan._core",
    "normalize_flag_record": "arnold_pipelines.megaplan.flags",
    "update_flags_after_critique": "arnold_pipelines.megaplan.flags",
    "update_flags_after_revise": "arnold_pipelines.megaplan.flags",
    "apply_transition": "arnold_pipelines.megaplan.control_interface",
    "read_valid_targets": "arnold_pipelines.megaplan.control_interface",
    "synthesize_artifacts": "arnold_pipelines.megaplan.control_interface",
    "run_metadata_from_batch_outcome": "arnold_pipelines.megaplan.run_outcome",
    "run_outcome_from_batch_outcome": "arnold_pipelines.megaplan.run_outcome",
    "unresolved_significant_flags": "arnold_pipelines.megaplan._core",
    "config_dir": "arnold_pipelines.megaplan._core",
    "load_config": "arnold_pipelines.megaplan._core",
    "save_config": "arnold_pipelines.megaplan._core",
    "plans_root": "arnold_pipelines.megaplan._core",
    "main": "arnold_pipelines.megaplan.cli",
    "cli_entry": "arnold_pipelines.megaplan.cli",
}

__all__ = [
    # Arnold plugin exports
    "build_pipeline", "build_and_compile_pipeline",
    "operation_registry", "override_catalog",
    # Types
    "PlanState", "PlanConfig", "PlanMeta", "FlagRecord", "StepResponse",
    "ArtifactRequest", "ControlBinding", "ControlInterfaceTarget", "ControlProjection", "ControlTargetRef",
    "ControlTransition", "ControlTransitionConflict", "ControlTransitionRequest", "ControlTransitionResult",
    "RunOutcome", "RunResultMetadata", "RunStateView",
    "AuditStatus", "BudgetStatus", "CaptureOutcome", "ModelSeamTelemetry",
    "ModelStepInvocationAdapter", "ModelTier", "RenderedStepMessage", "TerminalStatus", "TierMetadata",
    "capture_step_output", "install_model_step_adapter", "render_step_message",
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


# Register megaplan-specific content types with the generic Arnold registry.
# These are opinionated types that belong to the Megaplan plugin, not the
# neutral Arnold substrate.
def _register_megaplan_content_types() -> None:
    from arnold.pipeline.types import CONTENT_TYPES

    _MEGAPLAN_CONTENT_TYPES = (
        "application/x-evaluand-record+json",
        "application/x-routing-key+json",
        "application/x-verdict+json",
    )
    for _ct in _MEGAPLAN_CONTENT_TYPES:
        if _ct not in CONTENT_TYPES:
            CONTENT_TYPES.register(_ct, {"content_type": _ct})


_register_megaplan_content_types()


def _install_model_adapter_once() -> None:
    """Import megaplan model_seam first (registers hooks) then wire the adapter."""
    import arnold_pipelines.megaplan.model_seam as _ms  # noqa: F401 — side-effect: registers hooks
    from arnold.pipeline.step_invocation import get_default_adapter_registry
    from arnold_pipelines.megaplan.model_seam import install_model_step_adapter

    install_model_step_adapter(get_default_adapter_registry())


_model_adapter_installed: bool = False

if not _model_adapter_installed:
    _install_model_adapter_once()
    _model_adapter_installed = True
