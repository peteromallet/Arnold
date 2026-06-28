"""Tests for Megaplan workflow authoring components."""

from __future__ import annotations

import importlib
import sys

from arnold.workflow.authoring import ComponentKind, PolicyComponent, PromptComponent, StepComponent

from arnold_pipelines.megaplan import workflows
from arnold_pipelines.megaplan.workflows import planning


class TestWorkflowComponents:
    def test_all_exports_are_step_or_prompt_components(self) -> None:
        for component in workflows.ALL_STEP_COMPONENTS:
            assert isinstance(component, StepComponent)
            assert component.kind == ComponentKind.STEP
        for prompt in workflows.PROMPT_COMPONENTS:
            assert isinstance(prompt, PromptComponent)
            assert prompt.kind == ComponentKind.PROMPT
        for policy in workflows.POLICY_COMPONENTS:
            assert isinstance(policy, PolicyComponent)
            assert policy.kind == ComponentKind.POLICY

    def test_step_ids_are_stable(self) -> None:
        assert [c.id.removeprefix("megaplan:") for c in workflows.ALL_STEP_COMPONENTS] == [
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
            "tiebreaker_run",
            "tiebreaker_decide",
            "finalize",
            "execute",
            "review",
            "halt",
            "override",
        ]

    def test_lookup_by_step_id(self) -> None:
        assert workflows.STEP_COMPONENTS_BY_ID["gate"].label == "Megaplan gate"
        assert workflows.STEP_COMPONENTS_BY_ID["halt"].metadata["terminal"] is True

    def test_handler_refs_point_to_megaplan_handlers(self) -> None:
        for component in workflows.ALL_STEP_COMPONENTS:
            handler_ref = component.metadata.get("handler_ref")
            if handler_ref is None:
                assert component.id == "megaplan:halt", "only halt lacks a handler"
                continue
            assert handler_ref.startswith("arnold_pipelines.megaplan.handlers:"), handler_ref

    def test_prompt_components_reference_resolver_not_strings(self) -> None:
        for prompt in workflows.PROMPT_COMPONENTS:
            assert prompt.provenance.qualname == "create_prompt"
            assert prompt.metadata["resolver_ref"] == "arnold_pipelines.megaplan.prompts:create_prompt"
            assert "builder_family_refs" in prompt.metadata
            assert prompt.template is None, "prompt strings are rendered by create_prompt, not copied"

    def test_capability_requirements_match_runtime(self) -> None:
        assert workflows.CAPABILITY_REQUIREMENTS == {
            "megaplan:planning": {"route": "default", "required": True},
            "human:gate": {"route": "default", "required": False},
            "human:review": {"route": "default", "required": False},
        }
        pipeline = planning.build_pipeline()
        assert workflows.CAPABILITY_REQUIREMENTS == {
            capability.id: {"route": capability.route, "required": capability.required}
            for capability in pipeline.capabilities
        }

    def test_step_route_bindings_match_explicit_reference(self) -> None:
        pipeline = planning.build_pipeline()
        routes_by_source: dict[str, list[dict[str, str]]] = {}
        for route in pipeline.routes:
            binding = {
                "id": route.id,
                "label": route.label,
                "target_ref": route.target,
            }
            if route.condition_ref is not None:
                binding["condition_ref"] = route.condition_ref
            routes_by_source.setdefault(route.source, []).append(binding)

        for component in workflows.ALL_STEP_COMPONENTS:
            step_id = component.id.removeprefix("megaplan:")
            assert tuple(dict(binding) for binding in component.metadata["route_bindings"]) == tuple(
                routes_by_source.get(step_id, ())
            )

    def test_step_capability_metadata_matches_explicit_policy_reference(self) -> None:
        pipeline = planning.build_pipeline()
        capabilities_by_id = {
            capability.id: {"route": capability.route, "required": capability.required}
            for capability in pipeline.capabilities
        }

        for component in workflows.ALL_STEP_COMPONENTS:
            capability_requirements = component.metadata["capability_requirements"]
            policy = next(
                step.policy
                for step in pipeline.steps
                if step.id == component.id.removeprefix("megaplan:")
            )
            suspension_capabilities = {
                route.capability_id for route in policy.suspension_routes if route.capability_id is not None
            }
            assert {requirement["id"] for requirement in capability_requirements} == suspension_capabilities
            for requirement in capability_requirements:
                assert {
                    "route": requirement["route"],
                    "required": requirement["required"],
                } == capabilities_by_id[requirement["id"]]

    def test_policy_components_preserve_explicit_reference_metadata(self) -> None:
        pipeline = planning.build_pipeline()
        steps_by_id = {step.id: step for step in pipeline.steps}
        policies_by_id = {policy.id: policy for policy in workflows.POLICY_COMPONENTS}
        assert set(policies_by_id) == {
            "megaplan:default",
            "megaplan:gate",
            "megaplan:revise-loop",
            "megaplan:tiebreaker",
            "megaplan:review",
            "megaplan:override",
        }

        for component in workflows.ALL_STEP_COMPONENTS:
            assert component.policy is policies_by_id[component.metadata["policy_id"]]
            assert component.id.removeprefix("megaplan:") in component.policy.metadata["canonical_carriers"]

        for policy in workflows.POLICY_COMPONENTS:
            explicit_policies = [
                steps_by_id[carrier].policy for carrier in policy.metadata["canonical_carriers"]
            ]
            assert all(explicit.timing is not None for explicit in explicit_policies)
            assert policy.config["timeout_seconds_ref"] == "build_pipeline.timeout_seconds"
            if "suspension_routes" in policy.config:
                assert tuple(
                    {
                        key: value
                        for key, value in {
                            "route_id": route.route_id,
                            "capability_id": route.capability_id,
                            "reentry_id": route.reentry_id,
                        }.items()
                        if value is not None
                    }
                    for explicit in explicit_policies
                    for route in explicit.suspension_routes
                ) == policy.config["suspension_routes"]
            if "control_transitions" in policy.config:
                assert tuple(
                    {
                        "transition_id": transition.transition_id,
                        "transition_type": transition.transition_type,
                        "trigger_ref": transition.trigger_ref,
                        "target_ref": transition.target_ref,
                        "policy_ref": transition.policy_ref,
                    }
                    for explicit in explicit_policies
                    for transition in explicit.control_transitions
                ) == policy.config["control_transitions"]
            if "until_ref" in policy.config:
                assert tuple(explicit.loop.until_ref for explicit in explicit_policies) == (
                    policy.config["until_ref"],
                )

    def test_runtime_branch_vocabulary_is_declared(self) -> None:
        gate = workflows.STEP_COMPONENTS_BY_ID["gate"]
        assert gate.metadata["runtime_branch_vocabulary"] == (
            "proceed",
            "iterate",
            "tiebreaker",
            "escalate",
            "abort",
            "suspend",
            "blocked_preflight",
            "force_proceed",
        )
        assert workflows.STEP_COMPONENTS_BY_ID["review"].metadata["runtime_branch_vocabulary"] == (
            "pass",
            "rework",
        )

    def test_importing_components_does_not_load_legacy_package(self) -> None:
        before = set(sys.modules.keys())
        importlib.reload(workflows)
        loaded = {m for m in set(sys.modules.keys()) - before if m.startswith("arnold.pipelines.megaplan.")}
        assert loaded == set(), f"components import loaded legacy modules: {loaded}"

    def test_components_do_not_invoke_handlers_or_render_prompts(self) -> None:
        # The components module must contain only static metadata; no runtime
        # function calls that execute handlers, render prompts, or touch plan
        # state.  Handler references are allowed as literal strings.
        source = workflows.components.__file__
        text = open(source, encoding="utf-8").read()
        banned_calls = ["create_prompt(", "load_plan(", "PlanState(", "emit("]
        for token in banned_calls:
            assert token not in text, f"components source contains runtime call: {token}"
