"""Product-local Megaplan workflow authoring components.

The neutral authoring dataclasses live in :mod:`arnold.workflow.authoring`.
This module binds those primitives to Megaplan's stable product contract:
handler refs, prompt resolver families, route vocabulary, capability
requirements, and terminal metadata. It intentionally references prompt
builders by family/ref only and does not copy prompt strings.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from arnold.workflow.authoring import ComponentProvenance, PromptComponent, StepComponent

PROMPT_RESOLVER_REF = "arnold_pipelines.megaplan.prompts:create_prompt"
PROMPT_COMPONENT_RESOLVER_REF = "arnold_pipelines.megaplan.prompts:create_prompt_components"
HANDLER_MODULE = "arnold_pipelines.megaplan.handlers"

CAPABILITY_REQUIREMENTS = MappingProxyType(
    {
        "megaplan:planning": {"route": "default", "required": True},
        "human:gate": {"route": "default", "required": False},
        "human:review": {"route": "default", "required": False},
    }
)

RUNTIME_BRANCH_VOCABULARY = MappingProxyType(
    {
        "gate": (
            "proceed",
            "iterate",
            "tiebreaker",
            "escalate",
            "abort",
            "suspend",
            "blocked_preflight",
            "force_proceed",
        ),
        "tiebreaker_decide": ("iterate", "proceed", "escalate"),
        "review": ("pass", "rework"),
        "override": ("abort", "force_proceed", "replan"),
    }
)


def _provenance(export_name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module=__name__,
        qualname=export_name,
        export_name=export_name,
    )


def _prompt(step_id: str) -> PromptComponent:
    return PromptComponent(
        id=f"megaplan:prompt:{step_id}",
        provenance=ComponentProvenance(
            module="arnold_pipelines.megaplan.prompts",
            qualname="create_prompt",
            export_name="create_prompt",
        ),
        label=f"Megaplan {step_id} prompt resolver",
        parameters=("agent", "step", "state", "plan_dir", "root"),
        metadata={
            "step_id": step_id,
            "resolver_ref": PROMPT_RESOLVER_REF,
            "component_resolver_ref": PROMPT_COMPONENT_RESOLVER_REF,
            "builder_family_refs": (
                "arnold_pipelines.megaplan.prompts:_CLAUDE_PROMPT_BUILDERS",
                "arnold_pipelines.megaplan.prompts:_CODEX_PROMPT_BUILDERS",
                "arnold_pipelines.megaplan.prompts:_HERMES_PROMPT_BUILDERS",
            ),
        },
    )


def _step(
    *,
    export_name: str,
    step_id: str,
    kind: str,
    prompt: PromptComponent | None = None,
    handler_ref: str | None = None,
    inputs: tuple[Mapping[str, str], ...] = (),
    outputs: tuple[Mapping[str, str], ...] = (),
    policy_id: str = "megaplan:default",
    route_bindings: tuple[Mapping[str, Any], ...] = (),
    capability_ids: tuple[str, ...] = (),
    terminal: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> StepComponent:
    component_metadata: dict[str, Any] = {
        "kind": kind,
        "inputs": inputs,
        "outputs": outputs,
        "policy_id": policy_id,
        "route_bindings": route_bindings,
        "capability_requirements": tuple(
            {
                "id": capability_id,
                **CAPABILITY_REQUIREMENTS[capability_id],
            }
            for capability_id in capability_ids
        ),
        "terminal": terminal,
    }
    if handler_ref is not None:
        component_metadata["handler_ref"] = handler_ref
    if step_id in RUNTIME_BRANCH_VOCABULARY:
        component_metadata["runtime_branch_vocabulary"] = RUNTIME_BRANCH_VOCABULARY[step_id]
    if metadata:
        component_metadata.update(metadata)
    return StepComponent(
        id=f"megaplan:{step_id}",
        provenance=_provenance(export_name),
        label=f"Megaplan {step_id}",
        step_type=kind,
        prompt=prompt,
        metadata=component_metadata,
    )


PREP_PROMPT = _prompt("prep")
PLAN_PROMPT = _prompt("plan")
CRITIQUE_PROMPT = _prompt("critique")
GATE_PROMPT = _prompt("gate")
REVISE_PROMPT = _prompt("revise")
FINALIZE_PROMPT = _prompt("finalize")
EXECUTE_PROMPT = _prompt("execute")
REVIEW_PROMPT = _prompt("review")

PREP = _step(
    export_name="PREP",
    step_id="prep",
    kind="megaplan:prep",
    prompt=PREP_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_prep",
    outputs=({"name": "prep_payload"},),
)
PLAN = _step(
    export_name="PLAN",
    step_id="plan",
    kind="megaplan:plan",
    prompt=PLAN_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_plan",
    inputs=({"name": "prep_payload", "value_ref": "prep.prep_payload"},),
    outputs=({"name": "plan_payload"},),
)
CRITIQUE = _step(
    export_name="CRITIQUE",
    step_id="critique",
    kind="megaplan:critique",
    prompt=CRITIQUE_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_critique",
    inputs=({"name": "plan_payload", "value_ref": "plan.plan_payload"},),
    outputs=({"name": "critique_payload"},),
)
GATE = _step(
    export_name="GATE",
    step_id="gate",
    kind="megaplan:gate",
    prompt=GATE_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_gate",
    inputs=({"name": "critique_payload", "value_ref": "critique.critique_payload"},),
    outputs=({"name": "gate_payload"}, {"name": "recommendation"}),
    policy_id="megaplan:gate",
    route_bindings=(
        {"id": "gate:finalize", "label": "proceed", "condition_ref": "proceed", "target_ref": "finalize"},
        {"id": "gate:revise", "label": "iterate", "condition_ref": "iterate", "target_ref": "revise"},
        {
            "id": "gate:tiebreaker",
            "label": "tiebreaker",
            "condition_ref": "tiebreaker",
            "target_ref": "tiebreaker_run",
        },
        {"id": "gate:override", "label": "escalate", "condition_ref": "escalate", "target_ref": "override"},
        {"id": "gate:halt", "label": "abort", "condition_ref": "abort", "target_ref": "halt"},
        {"id": "gate:suspend", "label": "suspend", "condition_ref": "suspend", "target_ref": "halt"},
        {
            "id": "gate:blocked",
            "label": "blocked_preflight",
            "condition_ref": "blocked",
            "target_ref": "override",
        },
        {
            "id": "gate:force_proceed",
            "label": "force_proceed",
            "condition_ref": "force_proceed",
            "target_ref": "finalize",
        },
    ),
    capability_ids=("human:gate",),
)
REVISE = _step(
    export_name="REVISE",
    step_id="revise",
    kind="megaplan:revise",
    prompt=REVISE_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_revise",
    inputs=({"name": "gate_payload", "value_ref": "gate.gate_payload"},),
    outputs=({"name": "revise_payload"},),
    policy_id="megaplan:revise-loop",
    route_bindings=(
        {"id": "revise:critique", "label": "default", "condition_ref": "revise:loop", "target_ref": "critique"},
    ),
    capability_ids=("megaplan:planning",),
    metadata={"loop_until_ref": "critique_gate_pass"},
)
TIEBREAKER_RUN = _step(
    export_name="TIEBREAKER_RUN",
    step_id="tiebreaker_run",
    kind="megaplan:tiebreaker_run",
    handler_ref=f"{HANDLER_MODULE}:handle_tiebreaker_run",
    inputs=({"name": "gate_payload", "value_ref": "gate.gate_payload"},),
    outputs=({"name": "tiebreaker_payload"},),
)
TIEBREAKER_DECIDE = _step(
    export_name="TIEBREAKER_DECIDE",
    step_id="tiebreaker_decide",
    kind="megaplan:tiebreaker_decide",
    handler_ref=f"{HANDLER_MODULE}:handle_tiebreaker_decide",
    inputs=({"name": "tiebreaker_payload", "value_ref": "tiebreaker_run.tiebreaker_payload"},),
    outputs=({"name": "decision"},),
    policy_id="megaplan:tiebreaker",
    route_bindings=(
        {
            "id": "tiebreaker_decide:critique",
            "label": "iterate",
            "condition_ref": "tiebreaker:loop",
            "target_ref": "critique",
        },
        {
            "id": "tiebreaker_decide:finalize",
            "label": "proceed",
            "condition_ref": "proceed",
            "target_ref": "finalize",
        },
        {
            "id": "tiebreaker_decide:override",
            "label": "escalate",
            "condition_ref": "escalate",
            "target_ref": "override",
        },
    ),
    capability_ids=("megaplan:planning",),
    metadata={"loop_until_ref": "tiebreaker_resolved"},
)
FINALIZE = _step(
    export_name="FINALIZE",
    step_id="finalize",
    kind="megaplan:finalize",
    prompt=FINALIZE_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_finalize",
    inputs=({"name": "gate_payload", "value_ref": "gate.gate_payload"},),
    outputs=({"name": "finalize_payload"},),
)
EXECUTE = _step(
    export_name="EXECUTE",
    step_id="execute",
    kind="megaplan:execute",
    prompt=EXECUTE_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_execute",
    inputs=({"name": "finalize_payload", "value_ref": "finalize.finalize_payload"},),
    outputs=({"name": "execute_payload"},),
)
REVIEW = _step(
    export_name="REVIEW",
    step_id="review",
    kind="megaplan:review",
    prompt=REVIEW_PROMPT,
    handler_ref=f"{HANDLER_MODULE}:handle_review",
    inputs=({"name": "execute_payload", "value_ref": "execute.execute_payload"},),
    outputs=({"name": "review_payload"},),
    policy_id="megaplan:review",
    route_bindings=(
        {"id": "review:halt", "label": "default", "condition_ref": "pass", "target_ref": "halt"},
        {"id": "review:revise", "label": "rework", "condition_ref": "rework", "target_ref": "revise"},
    ),
    capability_ids=("human:review",),
)
HALT = _step(
    export_name="HALT",
    step_id="halt",
    kind="megaplan:halt",
    outputs=({"name": "status"},),
    terminal=True,
)
OVERRIDE = _step(
    export_name="OVERRIDE",
    step_id="override",
    kind="megaplan:override",
    handler_ref=f"{HANDLER_MODULE}:handle_override",
    inputs=({"name": "gate_payload", "value_ref": "gate.gate_payload"},),
    outputs=({"name": "override_result"},),
    policy_id="megaplan:override",
    route_bindings=(
        {"id": "override:halt", "label": "abort", "condition_ref": "abort", "target_ref": "halt"},
        {
            "id": "override:finalize",
            "label": "force_proceed",
            "condition_ref": "force_proceed",
            "target_ref": "finalize",
        },
        {"id": "override:revise", "label": "replan", "condition_ref": "replan", "target_ref": "revise"},
    ),
)

ALL_STEP_COMPONENTS = (
    PREP,
    PLAN,
    CRITIQUE,
    GATE,
    REVISE,
    TIEBREAKER_RUN,
    TIEBREAKER_DECIDE,
    FINALIZE,
    EXECUTE,
    REVIEW,
    HALT,
    OVERRIDE,
)
STEP_COMPONENTS_BY_ID = MappingProxyType({component.id.removeprefix("megaplan:"): component for component in ALL_STEP_COMPONENTS})
PROMPT_COMPONENTS = (
    PREP_PROMPT,
    PLAN_PROMPT,
    CRITIQUE_PROMPT,
    GATE_PROMPT,
    REVISE_PROMPT,
    FINALIZE_PROMPT,
    EXECUTE_PROMPT,
    REVIEW_PROMPT,
)

__all__ = [
    "ALL_STEP_COMPONENTS",
    "CAPABILITY_REQUIREMENTS",
    "CRITIQUE",
    "CRITIQUE_PROMPT",
    "EXECUTE",
    "EXECUTE_PROMPT",
    "FINALIZE",
    "FINALIZE_PROMPT",
    "GATE",
    "GATE_PROMPT",
    "HALT",
    "OVERRIDE",
    "PLAN",
    "PLAN_PROMPT",
    "PREP",
    "PREP_PROMPT",
    "PROMPT_COMPONENTS",
    "REVIEW",
    "REVIEW_PROMPT",
    "REVISE",
    "REVISE_PROMPT",
    "RUNTIME_BRANCH_VOCABULARY",
    "STEP_COMPONENTS_BY_ID",
    "TIEBREAKER_DECIDE",
    "TIEBREAKER_RUN",
]
