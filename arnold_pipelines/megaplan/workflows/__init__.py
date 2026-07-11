"""Megaplan Python-shaped workflow authoring components."""

from __future__ import annotations

from pathlib import Path
from typing import MutableSequence


def _runtime_target_workflows_path(package_file: Path) -> Path | None:
    """Locate target-authored workflows beside an isolated runtime mirror.

    Cloud chains execute Megaplan from ``.megaplan/runtime/editable-engine`` so
    target changes cannot mutate the running harness.  When the target repo is
    Arnold itself, that isolation also hides *new* workflow modules which do
    not exist in the pinned engine package.  Expose only the target workflow
    directory as a fallback package location; engine-owned modules keep
    precedence because the mirror path remains first.
    """

    resolved = package_file.resolve()
    for parent in resolved.parents:
        if (
            parent.name == "editable-engine"
            and parent.parent.name == "runtime"
            and parent.parent.parent.name == ".megaplan"
        ):
            project_root = parent.parent.parent.parent
            candidate = project_root / "arnold_pipelines" / "megaplan" / "workflows"
            if candidate.is_dir() and candidate.resolve() != resolved.parent:
                return candidate.resolve()
            return None
    return None


def _extend_runtime_workflow_path(
    package_paths: MutableSequence[str], package_file: Path
) -> bool:
    candidate = _runtime_target_workflows_path(package_file)
    if candidate is None:
        return False
    rendered = str(candidate)
    if rendered not in package_paths:
        package_paths.append(rendered)
    return True


_extend_runtime_workflow_path(__path__, Path(__file__))

from .components import (
    ALL_STEP_COMPONENTS,
    ARTIFACT_CONTRACT_POLICY,
    BLAST_RADIUS_POLICY,
    CAPABILITY_REQUIREMENTS,
    CRITIQUE,
    CRITIQUE_INPUT_SCHEMA,
    CRITIQUE_OUTPUT_SCHEMA,
    DEFAULT_POLICY,
    EXECUTE_POLICY,
    EXECUTE,
    EXECUTE_INPUT_SCHEMA,
    EXECUTE_OUTPUT_SCHEMA,
    FINALIZE,
    FINALIZE_INPUT_SCHEMA,
    FINALIZE_OUTPUT_SCHEMA,
    FINALIZE_POLICY,
    GATE,
    GATE_INPUT_SCHEMA,
    GATE_OUTPUT_SCHEMA,
    GATE_POLICY,
    HALT,
    HALT_OUTPUT_SCHEMA,
    M4_LOOP_MAX_ITERATIONS,
    MODEL_ROUTING_POLICY,
    OVERRIDE,
    OVERRIDE_INPUT_SCHEMA,
    OVERRIDE_OUTPUT_SCHEMA,
    OVERRIDE_POLICY,
    PLAN,
    PLAN_INPUT_SCHEMA,
    PLAN_OUTPUT_SCHEMA,
    POLICY_COMPONENTS,
    PREP,
    PREP_CLARIFY_POLICY,
    PREP_INPUT_SCHEMA,
    PREP_OUTPUT_SCHEMA,
    PROMPT_COMPONENTS,
    REVIEW,
    REVIEW_INPUT_SCHEMA,
    REVIEW_OUTPUT_SCHEMA,
    REVIEW_POLICY,
    REVISE,
    REVISE_INPUT_SCHEMA,
    REVISE_LOOP_POLICY,
    REVISE_OUTPUT_SCHEMA,
    ROBUSTNESS_POLICY,
    RUNTIME_BRANCH_VOCABULARY,
    check_outcome_vocabulary_parity,
    SCHEMA_COMPONENTS,
    STEP_COMPONENTS_BY_ID,
    SUSPEND,
    SUSPEND_OUTPUT_SCHEMA,
    SUSPENSION_POLICY,
    SOURCE_CRITIQUE_PANEL_WORKFLOW,
    SOURCE_EXECUTE_BATCH_WORKFLOW,
    SOURCE_REVIEW_PANEL_WORKFLOW,
    SOURCE_TIEBREAKER_WORKFLOW,
    TIEBREAKER_CHALLENGER,
    TIEBREAKER_CHALLENGER_PROMPT,
    TIEBREAKER_DECIDE,
    TIEBREAKER_DECIDE_INPUT_SCHEMA,
    TIEBREAKER_DECIDE_OUTPUT_SCHEMA,
    TIEBREAKER_DECISION,
    TIEBREAKER_DECISION_PROMPT,
    TIEBREAKER_POLICY,
    TIEBREAKER_RESEARCHER,
    TIEBREAKER_RESEARCHER_PROMPT,
    TIEBREAKER_RUN,
    TIEBREAKER_RUN_INPUT_SCHEMA,
    TIEBREAKER_RUN_OUTPUT_SCHEMA,
    TIEBREAKER_SYNTHESIS,
    TIEBREAKER_SYNTHESIS_PROMPT,
    WORKFLOW_COMPONENTS,
)
from .planning import (
    declared_fan_in_contract,
    declared_fanout_contract,
    declared_handler_binding,
    declared_route_surface,
    declared_step_capabilities,
    declared_step_interface,
    declared_step_policy_refs,
    declared_step_route_bindings,
    declared_workflow_topology_contract,
    FRONT_HALF_ROUTING_STEP_IDS,
    lowered_route_bindings_by_step,
    lowered_workflow_topology,
    resolve_lowered_route_target_for_signal,
)
from .events import (
    WorkflowCursor,
    WorkflowEvent,
    resolve_workflow_phase,
    resolve_workflow_source_phase,
    workflow_cursor,
    workflow_dispatch_phase_names,
    workflow_events,
    workflow_phase_aliases,
)

__all__ = [
    "ALL_STEP_COMPONENTS",
    "ARTIFACT_CONTRACT_POLICY",
    "BLAST_RADIUS_POLICY",
    "CAPABILITY_REQUIREMENTS",
    "CRITIQUE",
    "CRITIQUE_INPUT_SCHEMA",
    "CRITIQUE_OUTPUT_SCHEMA",
    "DEFAULT_POLICY",
    "declared_fan_in_contract",
    "declared_fanout_contract",
    "declared_handler_binding",
    "declared_route_surface",
    "declared_step_capabilities",
    "declared_step_interface",
    "declared_step_policy_refs",
    "declared_step_route_bindings",
    "declared_workflow_topology_contract",
    "EXECUTE_POLICY",
    "EXECUTE",
    "EXECUTE_INPUT_SCHEMA",
    "EXECUTE_OUTPUT_SCHEMA",
    "FINALIZE",
    "FINALIZE_INPUT_SCHEMA",
    "FINALIZE_OUTPUT_SCHEMA",
    "FINALIZE_POLICY",
    "FRONT_HALF_ROUTING_STEP_IDS",
    "GATE",
    "GATE_INPUT_SCHEMA",
    "GATE_OUTPUT_SCHEMA",
    "GATE_POLICY",
    "HALT",
    "HALT_OUTPUT_SCHEMA",
    "M4_LOOP_MAX_ITERATIONS",
    "MODEL_ROUTING_POLICY",
    "OVERRIDE",
    "OVERRIDE_INPUT_SCHEMA",
    "OVERRIDE_OUTPUT_SCHEMA",
    "OVERRIDE_POLICY",
    "PLAN",
    "PLAN_INPUT_SCHEMA",
    "PLAN_OUTPUT_SCHEMA",
    "POLICY_COMPONENTS",
    "PREP",
    "PREP_CLARIFY_POLICY",
    "PREP_INPUT_SCHEMA",
    "PREP_OUTPUT_SCHEMA",
    "PROMPT_COMPONENTS",
    "REVIEW",
    "REVIEW_INPUT_SCHEMA",
    "REVIEW_OUTPUT_SCHEMA",
    "REVIEW_POLICY",
    "REVISE",
    "REVISE_INPUT_SCHEMA",
    "REVISE_LOOP_POLICY",
    "REVISE_OUTPUT_SCHEMA",
    "ROBUSTNESS_POLICY",
    "RUNTIME_BRANCH_VOCABULARY",
    "check_outcome_vocabulary_parity",
    "SCHEMA_COMPONENTS",
    "STEP_COMPONENTS_BY_ID",
    "SUSPEND",
    "SUSPEND_OUTPUT_SCHEMA",
    "SUSPENSION_POLICY",
    "SOURCE_CRITIQUE_PANEL_WORKFLOW",
    "SOURCE_EXECUTE_BATCH_WORKFLOW",
    "SOURCE_REVIEW_PANEL_WORKFLOW",
    "SOURCE_TIEBREAKER_WORKFLOW",
    "TIEBREAKER_CHALLENGER",
    "TIEBREAKER_CHALLENGER_PROMPT",
    "TIEBREAKER_DECIDE",
    "TIEBREAKER_DECIDE_INPUT_SCHEMA",
    "TIEBREAKER_DECIDE_OUTPUT_SCHEMA",
    "TIEBREAKER_DECISION",
    "TIEBREAKER_DECISION_PROMPT",
    "TIEBREAKER_POLICY",
    "TIEBREAKER_RESEARCHER",
    "TIEBREAKER_RESEARCHER_PROMPT",
    "TIEBREAKER_RUN",
    "TIEBREAKER_RUN_INPUT_SCHEMA",
    "TIEBREAKER_RUN_OUTPUT_SCHEMA",
    "TIEBREAKER_SYNTHESIS",
    "TIEBREAKER_SYNTHESIS_PROMPT",
    "WORKFLOW_COMPONENTS",
    "WorkflowCursor",
    "WorkflowEvent",
    "lowered_route_bindings_by_step",
    "lowered_workflow_topology",
    "resolve_workflow_phase",
    "resolve_workflow_source_phase",
    "resolve_lowered_route_target_for_signal",
    "workflow_cursor",
    "workflow_dispatch_phase_names",
    "workflow_events",
    "workflow_phase_aliases",
]
