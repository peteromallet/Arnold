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
        for component in workflows.WORKFLOW_COMPONENTS:
            assert component.kind == ComponentKind.WORKFLOW
            assert component.metadata["input_names"]
            assert component.metadata["output_names"]
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
            "blocked",
            "force_proceeded",
            "deferred_human",
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


class TestSubworkflowSchemaDeclarations:
    """Verify that subworkflow boundaries declare M0 input/output schemas."""

    def test_all_step_components_have_input_or_are_entry(self) -> None:
        """Every StepComponent in ALL_STEP_COMPONENTS must have an input_schema unless it is an entry point."""
        # PREP and HALT are entry/terminal points that may not have input schemas
        entry_points = {"megaplan:prep", "megaplan:halt"}
        for component in workflows.ALL_STEP_COMPONENTS:
            if component.id in entry_points:
                continue
            assert component.input_schema is not None, (
                f"{component.id} must declare input_schema"
            )

    def test_all_step_components_have_output_schema(self) -> None:
        """Every StepComponent must have an output_schema."""
        for component in workflows.ALL_STEP_COMPONENTS:
            assert component.output_schema is not None, (
                f"{component.id} must declare output_schema"
            )

    def test_schema_ids_are_stable(self) -> None:
        """Schema IDs follow the megaplan:schema:{step}:{direction} pattern."""
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        expected_ids = [
            f"megaplan:schema:{stem}"
            for stem in [
                "prep:input", "prep:output",
                "plan:input", "plan:output",
                "critique:input", "critique:output",
                "gate:input", "gate:output",
                "revise:input", "revise:output",
                "tiebreaker_run:input", "tiebreaker_run:output",
                "tiebreaker_decide:input", "tiebreaker_decide:output",
                "finalize:input", "finalize:output",
                "execute:input", "execute:output",
                "review:input", "review:output",
                "halt:output",
                "override:input", "override:output",
                "suspend:output",
            ]
        ]
        actual_ids = [s.id for s in SCHEMA_COMPONENTS]
        assert actual_ids == expected_ids, f"Schema IDs mismatch:\n  got: {actual_ids}\n  expected: {expected_ids}"

    def test_schema_count_is_24(self) -> None:
        """There are 24 schema components: 11 input + 13 output (HALT and SUSPEND have no input)."""
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        assert len(SCHEMA_COMPONENTS) == 24, (
            f"Expected 24 schema components, got {len(SCHEMA_COMPONENTS)}"
        )

    def test_schema_types_are_input_or_output(self) -> None:
        """Every schema has schema_type of 'input' or 'output'."""
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        for schema in SCHEMA_COMPONENTS:
            assert schema.schema_type in ("input", "output"), (
                f"{schema.id} has unexpected schema_type: {schema.schema_type}"
            )

    def test_input_schemas_declare_expected_fields(self) -> None:
        """Input schemas declare field names matching the component's inputs metadata."""
        for component in workflows.ALL_STEP_COMPONENTS:
            input_schema = component.input_schema
            if input_schema is None:
                continue
            schema_fields = set(input_schema.schema.keys())
            component_inputs = {inp["name"] for inp in component.metadata.get("inputs", ())}
            # Schema fields must cover at least the component's declared inputs
            for inp_name in component_inputs:
                assert inp_name in schema_fields, (
                    f"{component.id} input schema missing field '{inp_name}'; "
                    f"schema has: {sorted(schema_fields)}"
                )

    def test_output_schemas_declare_expected_fields(self) -> None:
        """Output schemas declare field names matching the component's outputs metadata."""
        for component in workflows.ALL_STEP_COMPONENTS:
            output_schema = component.output_schema
            assert output_schema is not None
            schema_fields = set(output_schema.schema.keys())
            component_outputs = {out["name"] for out in component.metadata.get("outputs", ())}
            for out_name in component_outputs:
                assert out_name in schema_fields, (
                    f"{component.id} output schema missing field '{out_name}'; "
                    f"schema has: {sorted(schema_fields)}"
                )

    def test_schema_fields_have_type_and_description(self) -> None:
        """Every schema field must have 'type' and 'description' keys."""
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        for schema in SCHEMA_COMPONENTS:
            for field_name, field_spec in schema.schema.items():
                assert "type" in field_spec, (
                    f"{schema.id}.{field_name} missing 'type'"
                )
                assert "description" in field_spec, (
                    f"{schema.id}.{field_name} missing 'description'"
                )

    def test_schemas_are_frozen_schema_components(self) -> None:
        """All schema components are SchemaComponent instances with SCHEMA kind."""
        from arnold.workflow.authoring import ComponentKind, SchemaComponent
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        for schema in SCHEMA_COMPONENTS:
            assert isinstance(schema, SchemaComponent), (
                f"{schema.id} is not a SchemaComponent"
            )
            assert schema.kind == ComponentKind.SCHEMA, (
                f"{schema.id} has kind {schema.kind}, expected SCHEMA"
            )


class TestPolicyPlacement:
    """Verify policies are correctly placed on subworkflow boundary components."""

    def test_gate_has_gate_policy(self) -> None:
        """GATE component must use GATE_POLICY."""
        assert workflows.GATE.policy is workflows.GATE_POLICY

    def test_revise_has_loop_policy(self) -> None:
        """REVISE component must use REVISE_LOOP_POLICY."""
        assert workflows.REVISE.policy is workflows.REVISE_LOOP_POLICY

    def test_tiebreaker_decide_has_tiebreaker_policy(self) -> None:
        """TIEBREAKER_DECIDE component must use TIEBREAKER_POLICY."""
        assert workflows.TIEBREAKER_DECIDE.policy is workflows.TIEBREAKER_POLICY

    def test_review_has_review_policy(self) -> None:
        """REVIEW component must use REVIEW_POLICY."""
        assert workflows.REVIEW.policy is workflows.REVIEW_POLICY

    def test_override_has_override_policy(self) -> None:
        """OVERRIDE component must use OVERRIDE_POLICY."""
        assert workflows.OVERRIDE.policy is workflows.OVERRIDE_POLICY

    def test_default_policy_components(self) -> None:
        """Components without special policy must use DEFAULT_POLICY."""
        default_policy_ids = {
            "megaplan:prep", "megaplan:plan", "megaplan:critique",
            "megaplan:tiebreaker_run", "megaplan:finalize", "megaplan:execute",
            "megaplan:halt",
        }
        for component in workflows.ALL_STEP_COMPONENTS:
            if component.id in default_policy_ids:
                assert component.policy is workflows.DEFAULT_POLICY, (
                    f"{component.id} should use DEFAULT_POLICY, got {component.policy}"
                )

    def test_suspend_has_suspension_policy(self) -> None:
        """SUSPEND component must use SUSPENSION_POLICY."""
        from arnold_pipelines.megaplan.workflows.components import SUSPEND, SUSPENSION_POLICY
        assert SUSPEND.policy is SUSPENSION_POLICY

    def test_all_step_components_have_policy(self) -> None:
        """Every step component must have a policy assigned."""
        for component in workflows.ALL_STEP_COMPONENTS:
            assert component.policy is not None, (
                f"{component.id} must have a policy"
            )


class TestLegacyAliases:
    """Verify legacy aliases for profile slots, override targets, status payloads, and cursors."""

    def test_legacy_aliases_defined(self) -> None:
        """LEGACY_ALIASES mapping is present and non-empty."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES
        assert len(LEGACY_ALIASES) > 0, "LEGACY_ALIASES must be non-empty"

    def test_profile_slot_aliases_present(self) -> None:
        """Profile slot aliases are preserved."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES

        profile_keys = [
            "profile:default_routing",
            "profile:loader",
            "profile:robustness_levels",
            "profile:robustness_accepted",
            "profile:robustness_normalizer",
            "profile:phase_model_override",
        ]
        for key in profile_keys:
            assert key in LEGACY_ALIASES, f"Missing profile alias: {key}"

    def test_override_target_aliases_present(self) -> None:
        """Override target aliases are preserved."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES

        override_keys = [
            "override:abort",
            "override:force_proceed",
            "override:replan",
            "override:set_robustness",
            "override:add_note",
        ]
        for key in override_keys:
            assert key in LEGACY_ALIASES, f"Missing override alias: {key}"

    def test_status_payload_aliases_present(self) -> None:
        """Status payload aliases are preserved."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES

        status_keys = ["status:halt", "status:terminal"]
        for key in status_keys:
            assert key in LEGACY_ALIASES, f"Missing status alias: {key}"

    def test_cursor_aliases_present(self) -> None:
        """Cursor aliases for suspension and reentry are preserved."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES

        cursor_keys = [
            "cursor:suspension",
            "cursor:resume_contract",
            "cursor:reentry:gate",
            "cursor:reentry:review",
            "cursor:reentry:revise_loop",
            "cursor:reentry:tiebreaker_loop",
        ]
        for key in cursor_keys:
            assert key in LEGACY_ALIASES, f"Missing cursor alias: {key}"

    def test_legacy_aliases_has_expected_count(self) -> None:
        """LEGACY_ALIASES must have exactly 19 entries."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES
        assert len(LEGACY_ALIASES) == 19, (
            f"Expected 19 legacy aliases, got {len(LEGACY_ALIASES)}: {list(LEGACY_ALIASES.keys())}"
        )

    def test_all_legacy_alias_values_are_strings(self) -> None:
        """Every alias value must be a non-empty string."""
        from arnold_pipelines.megaplan.workflows import LEGACY_ALIASES
        for key, value in LEGACY_ALIASES.items():
            assert isinstance(value, str), f"Alias '{key}' value is not a string: {type(value)}"
            assert value, f"Alias '{key}' value is empty"


class TestStableIdsAuthoritative:
    """Verify that stable IDs are the authoritative identity for components."""

    def test_step_ids_follow_pattern(self) -> None:
        """All step component IDs follow the megaplan:{id} pattern."""
        for component in workflows.ALL_STEP_COMPONENTS:
            assert component.id.startswith("megaplan:"), (
                f"{component.id} must start with 'megaplan:'"
            )
            step_id = component.id.removeprefix("megaplan:")
            assert step_id, f"{component.id} has empty step_id suffix"

    def test_step_ids_are_stable_across_reloads(self) -> None:
        """Step IDs must be identical after module reload."""
        import importlib
        reloaded = importlib.reload(workflows)
        original_ids = [c.id for c in workflows.ALL_STEP_COMPONENTS]
        reloaded_ids = [c.id for c in reloaded.ALL_STEP_COMPONENTS]
        assert original_ids == reloaded_ids, "Step IDs changed after reload"

    def test_schema_ids_reference_correct_steps(self) -> None:
        """Schema IDs reference the correct step components."""
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        for schema in SCHEMA_COMPONENTS:
            # Schema id format: megaplan:schema:{step_id}:{direction}
            parts = schema.id.removeprefix("megaplan:schema:").rsplit(":", 1)
            assert len(parts) == 2, f"Unexpected schema id format: {schema.id}"
            step_id, direction = parts
            assert direction in ("input", "output"), (
                f"Schema {schema.id} has unexpected direction: {direction}"
            )
            # HALT and SUSPEND only have output schemas
            if step_id in ("halt", "suspend"):
                assert direction == "output", (
                    f"{step_id} should only have output schema, got {direction}"
                )

    def test_component_ids_are_unique(self) -> None:
        """All step component IDs must be unique."""
        ids = [c.id for c in workflows.ALL_STEP_COMPONENTS]
        assert len(ids) == len(set(ids)), f"Duplicate step IDs: {ids}"

    def test_source_components_share_ids_with_primary(self) -> None:
        """SOURCE_* components share IDs with ALL_STEP_COMPONENTS (by design — alternative declarations)."""
        all_ids = {c.id for c in workflows.ALL_STEP_COMPONENTS}
        source_id_mappings = {}
        for name in sorted(dir(workflows.components)):
            if name.startswith("SOURCE_"):
                source_comp = getattr(workflows.components, name)
                if not isinstance(source_comp, StepComponent):
                    continue
                step_id = name.removeprefix("SOURCE_").lower()
                source_id_mappings[name] = (source_comp.id, step_id)
        # Each SOURCE_ component should have an id matching megaplan:{step_id}
        for comp_name, (comp_id, step_id) in source_id_mappings.items():
            assert comp_id == f"megaplan:{step_id}", (
                f"{comp_name} has id {comp_id}, expected megaplan:{step_id}"
            )
            assert comp_id in all_ids, (
                f"{comp_name} id {comp_id} not found in ALL_STEP_COMPONENTS"
            )
