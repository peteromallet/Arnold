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
            "tiebreaker_run",  # bridge-only: legacy carrier
            "tiebreaker_decide",  # bridge-only: legacy carrier
            "tiebreaker_researcher",
            "tiebreaker_challenger",
            "tiebreaker_synthesis",
            "tiebreaker_decision",
            "finalize",
            "execute",
            "review",
            "halt",
            "override",
        ]

    def test_lookup_by_step_id(self) -> None:
        assert workflows.STEP_COMPONENTS_BY_ID["gate"].label == "Megaplan gate"
        assert workflows.STEP_COMPONENTS_BY_ID["halt"].metadata["terminal"] is True

    def test_front_half_compatibility_exports_are_quarantined(self) -> None:
        for name, canonical in (
            ("SOURCE_PREP", workflows.PREP),
            ("SOURCE_PLAN", workflows.PLAN),
            ("SOURCE_CRITIQUE", workflows.CRITIQUE),
            ("SOURCE_GATE", workflows.GATE),
            ("SOURCE_REVISE", workflows.REVISE),
            ("AUTHORING_PREP", workflows.PREP),
            ("AUTHORING_PLAN", workflows.PLAN),
            ("AUTHORING_CRITIQUE", workflows.CRITIQUE),
            ("AUTHORING_GATE", workflows.GATE),
            ("AUTHORING_REVISE", workflows.REVISE),
        ):
            compatibility = getattr(workflows.components, name)
            assert compatibility.id == canonical.id
            assert compatibility is not canonical
            assert compatibility.metadata.get("route_bindings", ()) == ()
            assert compatibility.metadata["compatibility_quarantine"]["kind"] == "route_metadata_removed"

    def test_handler_refs_point_to_megaplan_handlers(self) -> None:
        for component in workflows.ALL_STEP_COMPONENTS:
            step_id = component.id.removeprefix("megaplan:")
            handler_ref = planning.declared_handler_binding(step_id) or component.metadata.get("handler_ref")
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

    # Steps whose route authority is declared in the workflow.pypeline or
    # named policy constructs (EXECUTE_POLICY.route_surface) rather than
    # in component-level ``route_bindings``.
    _POLICY_ROUTED_STEP_IDS: frozenset[str] = frozenset({"execute", "review", "override"})
    _BRIDGE_ONLY_STEP_IDS: frozenset[str] = frozenset({"tiebreaker_run", "tiebreaker_decide"})

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

        front_half_sources = {
            route.source for route in pipeline.routes if route.source in planning.FRONT_HALF_ROUTING_STEP_IDS
        }
        assert front_half_sources == planning.FRONT_HALF_ROUTING_STEP_IDS - {"revise"}

        for component in workflows.ALL_STEP_COMPONENTS:
            step_id = component.id.removeprefix("megaplan:")
            if step_id in planning.FRONT_HALF_ROUTING_STEP_IDS:
                continue
            if step_id in self._POLICY_ROUTED_STEP_IDS:
                continue
            if step_id in self._BRIDGE_ONLY_STEP_IDS:
                continue
            bindings = planning.declared_step_route_bindings(step_id) or component.metadata["route_bindings"]
            actual = {tuple(sorted(dict(binding).items())) for binding in bindings}
            expected = {
                tuple(sorted(binding.items()))
                for binding in routes_by_source.get(step_id, ())
            }
            assert expected <= actual

    def test_execute_route_authority_comes_from_policy_not_component_bindings(self) -> None:
        """Execute route authority lives in EXECUTE_POLICY.route_surface and
        the workflow.pypeline, not in component-level ``route_bindings``."""
        execute_component = workflows.STEP_COMPONENTS_BY_ID["execute"]
        assert execute_component.metadata.get("route_bindings", ()) == (), (
            "EXECUTE component must not carry authoritative route_bindings; "
            "route authority lives in EXECUTE_POLICY.route_surface or workflow.pypeline"
        )
        policy_by_id = {p.id: p for p in workflows.POLICY_COMPONENTS}
        execute_policy = policy_by_id["megaplan:execute"]
        route_surface = execute_policy.metadata["route_surface"]
        assert "branch_surface_ref" in route_surface, (
            "EXECUTE_POLICY.route_surface must declare branch_surface_ref to the "
            "typed EXECUTE_BRANCH_SURFACE authority"
        )
        assert "batch_continuation" in route_surface
        assert "review_handoff" in route_surface
        assert "aggregate_promotion" in route_surface
        # Verify the pipeline still carries the execute→review route (derived
        # from the pypeline, not from component bindings).
        pipeline = planning.build_pipeline()
        execute_routes = [r for r in pipeline.routes if r.source == "execute"]
        assert len(execute_routes) == 1
        assert execute_routes[0].target == "review"
        assert execute_routes[0].id == "execute:review"

    def test_step_capability_metadata_matches_explicit_policy_reference(self) -> None:
        pipeline = planning.build_pipeline()
        capabilities_by_id = {
            capability.id: {"route": capability.route, "required": capability.required}
            for capability in pipeline.capabilities
        }

        for component in workflows.ALL_STEP_COMPONENTS:
            step_id = component.id.removeprefix("megaplan:")
            declared_capabilities = planning.declared_step_capabilities(step_id)
            policy = next(
                (
                    step.policy
                    for step in pipeline.steps
                    if step.id == step_id
                ),
                None,
            )
            if policy is None:
                assert component.id in {"megaplan:tiebreaker_run", "megaplan:tiebreaker_decide"}
                continue
            suspension_capabilities = {
                route.capability_id for route in policy.suspension_routes if route.capability_id is not None
            }
            assert {capability.id for capability in declared_capabilities} == suspension_capabilities
            for capability in declared_capabilities:
                assert {
                    "route": capability.route,
                    "required": capability.required,
                } == capabilities_by_id[capability.id]

    def test_policy_components_preserve_explicit_reference_metadata(self) -> None:
        pipeline = planning.build_pipeline()
        steps_by_id = {step.id: step for step in pipeline.steps}
        policies_by_id = {policy.id: policy for policy in workflows.POLICY_COMPONENTS}
        assert set(policies_by_id) == {
            "megaplan:default",
            "megaplan:gate",
            "megaplan:revise-loop",
            "megaplan:tiebreaker",
            "megaplan:finalize",
            "megaplan:review",
            "megaplan:execute",
            "megaplan:override",
            "megaplan:model-routing",
            "megaplan:robustness",
            "megaplan:artifact-contract",
            "megaplan:suspension",
            "megaplan:prep-clarify",
            "megaplan:blast-radius",
        }

        for component in workflows.ALL_STEP_COMPONENTS:
            assert component.policy is policies_by_id[component.metadata["policy_id"]]
            assert component.id.removeprefix("megaplan:") in component.policy.metadata["canonical_carriers"]

        for policy in workflows.POLICY_COMPONENTS:
            carriers = tuple(policy.metadata.get("canonical_carriers", ()))
            if not carriers:
                assert policy.metadata.get("authoring_surface") is True
                continue
            explicit_policies = [
                steps_by_id[carrier].policy
                for carrier in carriers
                if carrier in steps_by_id
            ]
            if not explicit_policies:
                assert set(carriers) <= {"tiebreaker_run", "tiebreaker_decide"}
                continue
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
                            "payload_schema_hash": route.payload_schema_hash,
                            "resume_schema_hash": route.resume_schema_hash,
                            "resume_schema_ref": route.resume_schema_ref,
                            "resume_payload_ref": route.resume_payload_ref,
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
            if "retry" in policy.config:
                assert all(explicit.retry is not None for explicit in explicit_policies)
                assert explicit_policies[0].retry.max_attempts == policy.config["retry"]["max_attempts"]
            if "escalation" in policy.config:
                assert all(explicit.escalation is not None for explicit in explicit_policies)

    def test_runtime_branch_vocabulary_is_declared(self) -> None:
        prep = workflows.STEP_COMPONENTS_BY_ID["prep"]
        assert prep.metadata["runtime_branch_vocabulary"] == (
            "continue",
            "awaiting_human",
        )
        critique = workflows.STEP_COMPONENTS_BY_ID["critique"]
        assert critique.metadata["runtime_branch_vocabulary"] == (
            "completed",
        )
        revise = workflows.STEP_COMPONENTS_BY_ID["revise"]
        assert revise.metadata["runtime_branch_vocabulary"] == (
            "completed",
        )
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
            "retry_gate",
            "reprompt_downgrade",
        )
        assert workflows.STEP_COMPONENTS_BY_ID["review"].metadata["runtime_branch_vocabulary"] == (
            "pass",
            "rework",
            "blocked",
            "force_proceeded",
            "deferred_human",
        )

    def test_outcome_vocabulary_parity(self) -> None:
        """Every outcome enum value must match its RUNTIME_BRANCH_VOCABULARY entry."""
        from arnold_pipelines.megaplan.outcomes import (
            OUTCOME_CLASS_BY_VOCABULARY_KEY,
        )
        from arnold_pipelines.megaplan.workflows.components import (
            RUNTIME_BRANCH_VOCABULARY,
        )

        for key, enum_cls in OUTCOME_CLASS_BY_VOCABULARY_KEY.items():
            expected = tuple(member.value for member in enum_cls.__members__.values())
            actual = RUNTIME_BRANCH_VOCABULARY.get(key)
            assert actual is not None, (
                f"Outcome key '{key}' has enum {enum_cls.__name__} "
                f"but is missing from RUNTIME_BRANCH_VOCABULARY"
            )
            assert set(expected) == set(actual), (
                f"Vocabulary mismatch for '{key}': "
                f"enum values {expected!r} != RUNTIME_BRANCH_VOCABULARY {actual!r}"
            )

        # Every RUNTIME_BRANCH_VOCABULARY key must have an outcome enum
        covered = set(OUTCOME_CLASS_BY_VOCABULARY_KEY)
        actual_keys = set(RUNTIME_BRANCH_VOCABULARY)
        uncovered = actual_keys - covered
        assert not uncovered, (
            f"RUNTIME_BRANCH_VOCABULARY keys without outcome enum: {sorted(uncovered)}"
        )

    def test_gate_policy_metadata_exposes_handler_free_route_surface(self) -> None:
        route_surface = workflows.GATE_POLICY.metadata["route_surface"]
        assert route_surface["route_groups"] == {
            "finalize": ("proceed", "force_proceed"),
            "revise": ("iterate", "retry_gate", "reprompt_downgrade"),
            "tiebreaker": ("tiebreaker",),
            "override": ("escalate", "blocked_preflight"),
            "halt": ("abort", "suspend"),
        }
        assert route_surface["fallback_route_signals"] == {
            "blocking_flag_reprompt": "retry_gate",
            "reprompt_downgrade": "reprompt_downgrade",
            "preflight_failed": "blocked_preflight",
            "unknown_recommendation": "escalate",
            "critique_cap": "force_proceed",
        }
        assert route_surface["severity_policy"] == {
            "blocking_statuses": ("open", "addressed", "disputed"),
            "significant_severities": ("significant", "likely-significant"),
            "cosmetic_severities": ("minor", "likely-minor", "trivial", "cosmetic", "low", "nit"),
            "critical_categories": ("correctness", "security"),
        }
        assert route_surface["normalization_policy"] == {
            "invalid_recommendation": {
                "owner": "gate",
                "effect": "normalize_to_inferred_recommendation",
                "fallback_recommendations": {
                    "blocking_flags_present": "ITERATE",
                    "preflight_failed": "ESCALATE",
                    "clear_to_proceed": "PROCEED",
                },
            },
            "empty_payload": {
                "owner": "gate",
                "effect": "normalize_to_inferred_recommendation",
            },
        }
        assert route_surface["debt_visibility"] == {
            "owner": "gate",
            "effect": "publish_debt_payload_on_proceed",
            "payload_fields": ("recommendation", "entries_added", "accepted_tradeoffs"),
        }
        assert route_surface["reprompt_policy"] == {
            "downgrade_on_unresolved_blockers": {
                "route_signal": "reprompt_downgrade",
                "recommendation": "ITERATE",
                "passed": False,
                "fallback_kind": "reprompt_downgrade",
            }
        }
        assert route_surface["critique_gate_diagnostics"] == {
            "bare_skip": {
                "owner": "critique-fanout",
                "effect": "skip_empty_or_bare_findings",
            },
            "evaluator_retry": {
                "owner": "critique-fanout",
                "effect": "retry_unverifiable_or_unavailable_evaluators",
            },
            "malformed_payload": {
                "owner": "gate",
                "effect": "normalize_to_inferred_recommendation",
                "fallback_recommendations": {
                    "blocking_flags_present": "ITERATE",
                    "preflight_failed": "ESCALATE",
                    "clear_to_proceed": "PROCEED",
                },
            },
            "empty_payload": {
                "owner": "gate",
                "effect": "normalize_to_inferred_recommendation",
            },
            "worker_unavailable": {
                "owner": "gate",
                "effect": "escalate_or_retry_via_preflight_policy",
            },
            "debt_recorded": {
                "owner": "gate",
                "effect": "publish_debt_payload_on_proceed",
                "payload_fields": ("recommendation", "entries_added", "accepted_tradeoffs"),
            },
        }

    def test_revise_loop_policy_exposes_bounded_gate_revise_surface(self) -> None:
        loop_surface = workflows.REVISE_LOOP_POLICY.metadata["loop_surface"]

        assert loop_surface["loop_id"] == "critique-gate-revise"
        assert loop_surface["max_iterations"] == workflows.M4_LOOP_MAX_ITERATIONS
        assert loop_surface["max_iterations_ref"] == "M4_LOOP_MAX_ITERATIONS"
        assert loop_surface["reentry"] == {
            "route_id": "revise:loop",
            "reentry_id": "critique",
            "target_ref": "critique-fanout",
        }
        assert loop_surface["until_exits"] == {
            "proceed": "finalize",
            "force_proceed": "finalize",
        }
        assert loop_surface["unless_exits"] == {
            "escalate": "override",
            "abort": "halt",
            "blocked_preflight": "override",
            "suspend": "halt",
        }
        assert loop_surface["revise_reentries"] == {
            "iterate": "revise",
            "retry_gate": "gate_retry_revise",
            "reprompt_downgrade": "gate_reprompt_revise",
        }
        assert loop_surface["cap_outcomes"] == {
            "critical_or_security_blockers": "escalate",
            "cosmetic_only": "force_proceed",
            "no_progress_with_blockers": "escalate",
        }
        assert loop_surface["termination_policy"] == {
            "iteration_caps": {
                "default_config_key": "max_critique_iterations",
                "robust_config_key": "max_robust_critique_iterations",
                "robustness_overrides": {
                    "light": {"max_value": 2},
                },
            },
            "no_progress_cap": {
                "config_scope": "execution",
                "config_key": "max_critique_no_progress",
            },
            "severity_policy": {
                "blocking_statuses": ("open", "addressed", "disputed"),
                "significant_severities": ("significant", "likely-significant"),
                "cosmetic_severities": ("minor", "likely-minor", "trivial", "cosmetic", "low", "nit"),
                "critical_categories": ("correctness", "security"),
            },
            "cap_outcomes": {
                "critical_or_security_blockers": "escalate",
                "cosmetic_only": "force_proceed",
                "no_progress_with_blockers": "escalate",
            },
            "debt_visibility": {
                "owner": "gate",
                "effect": "publish_debt_payload_on_proceed",
                "payload_fields": ("recommendation", "entries_added", "accepted_tradeoffs"),
            },
        }
        assert loop_surface["gate_route_signals"] == workflows.RUNTIME_BRANCH_VOCABULARY["gate"]
        assert loop_surface["suspension"] == {
            "route_signal": "suspend",
            "route_id": "gate:human",
            "reentry_id": "revise:loop",
            "resume_target_ref": "gate",
        }
        assert loop_surface["tiebreaker"] == {
            "call_ref": "TIEBREAKER_WORKFLOW",
            "call_id": "tiebreaker",
            "inputs": ("gate_payload",),
            "rejoin": {
                "proceed": "finalize",
                "iterate": "revise",
                "escalate": "override",
                "fallback": "override",
            },
            "internals": "delegated",
        }

    def test_default_policy_metadata_exposes_critique_fanout_and_external_call_surface(self) -> None:
        critique_surface = workflows.DEFAULT_POLICY.metadata["critique_surface"]
        assert critique_surface["fanout_contract"] == {
            "parallel_map_id": "critique-fanout",
            "fanout_ref": "megaplan.policy.critique_lenses",
            "step_ref": "SOURCE_CRITIQUE_PANEL_WORKFLOW",
            "reducer_ref": "SOURCE_CRITIQUE",
            "path_template": "critique/{item_id}",
            "route_signal": "critique_payload",
            "lens_cardinality": {
                "minimum": 0,
                "maximum_ref": "len(megaplan.policy.critique_lenses)",
            },
            "typed_reducer_outcomes": {
                "critique": ("completed",),
                "gate": (
                    "proceed",
                    "iterate",
                    "tiebreaker",
                    "escalate",
                    "abort",
                    "suspend",
                    "blocked_preflight",
                    "force_proceed",
                    "retry_gate",
                    "reprompt_downgrade",
                ),
            },
        }
        assert critique_surface["selection_policy"] == {
            "skip": {
                "when": "robustness == bare",
                "route_signal": "skip_to_finalize",
            },
            "static": {
                "when": "adaptive critique disabled or creative mode enabled",
                "lens_source": "megaplan.policy.critique_lenses",
            },
            "adaptive": {
                "when": "adaptive critique enabled and creative mode disabled",
                "phase": "critique_evaluator",
                "fallback": "static",
            },
        }
        assert critique_surface["retry_policy"] == {
            "phase": "critique_evaluator",
            "max_attempts": 2,
            "on_exhausted": "blocked",
            "recovery_artifact": "critique_output.json",
            "promote_to": "critique_v{iteration}.json",
        }
        assert critique_surface["evidence_contract"] == {
            "skip": {
                "construct_type": "critique",
                "selection_mode": "skip",
                "route_signal": "skip_to_finalize",
            },
            "static": {
                "construct_type": "critique",
                "selection_mode": "static",
                "lens_source": "megaplan.policy.critique_lenses",
            },
            "adaptive": {
                "construct_type": "critique",
                "selection_mode": "adaptive",
                "phase": "critique_evaluator",
                "fallback": "static",
            },
            "retry_exhausted": {
                "construct_type": "gate",
                "phase": "critique_evaluator",
                "route_signal": "blocked",
            },
        }
        assert critique_surface["skip_and_retry_policy"] == {
            "bare_robustness": {
                "route_signal": "skip_to_finalize",
                "effect": "workflow_handles_plan_to_finalize_without_handler_fanout",
            },
            "evaluator_retry": {
                "phase": "critique_evaluator",
                "max_attempts": 2,
                "on_exhausted": "blocked",
            },
            "payload_recovery": {
                "scratch_ref": "critique_output.json",
                "promote_to": "critique_v{iteration}.json",
            },
        }
        assert critique_surface["external_call_wrapping"] == {
            "runtime_wrapper_ref": "arnold_pipelines.megaplan.orchestration.critique_runtime",
            "retained_handler_ref": "arnold_pipelines.megaplan.handlers.critique:handle_critique",
            "worker_phase": "critique",
            "evaluator_phase": "critique_evaluator",
        }

    def test_critique_panel_workflow_metadata_exposes_fanout_skip_retry_and_wrapping(self) -> None:
        contract = workflows.SOURCE_CRITIQUE_PANEL_WORKFLOW.metadata["topology_contract"]
        assert contract == {
            "kind": "critique_fanout",
            "fanout_ref": "megaplan.policy.critique_lenses",
            "parallel_map_id": "critique-fanout",
            "path_template": "critique/{item_id}",
            "route_signal": "critique_payload",
            "lens_cardinality": {
                "minimum": 0,
                "maximum_ref": "len(megaplan.policy.critique_lenses)",
            },
            "typed_reducer_outcomes": {
                "critique": ("completed",),
                "gate": (
                    "proceed",
                    "iterate",
                    "tiebreaker",
                    "escalate",
                    "abort",
                    "suspend",
                    "blocked_preflight",
                    "force_proceed",
                    "retry_gate",
                    "reprompt_downgrade",
                ),
            },
            "selection_policy": {
                "skip": {
                    "when": "robustness == bare",
                    "route_signal": "skip_to_finalize",
                },
                "static": {
                    "when": "adaptive critique disabled or creative mode enabled",
                    "lens_source": "megaplan.policy.critique_lenses",
                },
                "adaptive": {
                    "when": "adaptive critique enabled and creative mode disabled",
                    "phase": "critique_evaluator",
                    "fallback": "static",
                },
            },
            "retry_policy": {
                "phase": "critique_evaluator",
                "max_attempts": 2,
                "on_exhausted": "blocked",
                "recovery_artifact": "critique_output.json",
                "promote_to": "critique_v{iteration}.json",
            },
            "evidence_contract": {
                "skip": {
                    "construct_type": "critique",
                    "selection_mode": "skip",
                    "route_signal": "skip_to_finalize",
                },
                "static": {
                    "construct_type": "critique",
                    "selection_mode": "static",
                    "lens_source": "megaplan.policy.critique_lenses",
                },
                "adaptive": {
                    "construct_type": "critique",
                    "selection_mode": "adaptive",
                    "phase": "critique_evaluator",
                    "fallback": "static",
                },
                "retry_exhausted": {
                    "construct_type": "gate",
                    "phase": "critique_evaluator",
                    "route_signal": "blocked",
                },
            },
            "skip_and_retry_policy": {
                "bare_robustness": "skip_to_finalize",
                "evaluator_retry_attempts": 2,
                "on_exhausted": "blocked",
                "payload_recovery_ref": "critique_output.json",
            },
            "external_call_wrapping": {
                "runtime_wrapper_ref": "arnold_pipelines.megaplan.orchestration.critique_runtime",
                "retained_handler_ref": "arnold_pipelines.megaplan.handlers.critique:handle_critique",
                "worker_phase": "critique",
                "evaluator_phase": "critique_evaluator",
            },
        }

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
                "tiebreaker_run:input", "tiebreaker_run:output",  # bridge-only
                "tiebreaker_decide:input", "tiebreaker_decide:output",  # bridge-only
                "tiebreaker_researcher:input", "tiebreaker_researcher:output",
                "tiebreaker_challenger:input", "tiebreaker_challenger:output",
                "tiebreaker_synthesis:input", "tiebreaker_synthesis:output",
                "tiebreaker_decision:input", "tiebreaker_decision:output",
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

    def test_schema_count_is_32(self) -> None:
        """There are 32 schema components: 15 input + 17 output (HALT and SUSPEND have no input)."""
        from arnold_pipelines.megaplan.workflows import SCHEMA_COMPONENTS

        assert len(SCHEMA_COMPONENTS) == 32, (
            f"Expected 32 schema components, got {len(SCHEMA_COMPONENTS)}"
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
        route_surface = workflows.OVERRIDE_POLICY.metadata["route_surface"]
        assert route_surface["matrix_ref"].endswith("override_matrix:OVERRIDE_ACTION_MATRIX")
        assert {
            action["action"] for action in route_surface["actions"]
        } == set(planning.declared_step_interface("override")["override_actions"])

    def test_execute_has_execute_policy(self) -> None:
        """EXECUTE component must use EXECUTE_POLICY."""
        assert workflows.EXECUTE.policy is workflows.EXECUTE_POLICY

    def test_default_policy_components(self) -> None:
        """Components without special policy must use DEFAULT_POLICY."""
        default_policy_ids = {
            "megaplan:prep", "megaplan:plan", "megaplan:critique",
            "megaplan:tiebreaker_run", "megaplan:finalize",
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

    def test_execute_review_and_override_declare_policy_refs(self) -> None:
        assert planning.declared_step_policy_refs("execute") == (
            "megaplan:execute",
            "megaplan:model-routing",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        )
        assert planning.declared_step_policy_refs("review") == (
            "megaplan:review",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        )
        assert planning.declared_step_policy_refs("override") == (
            "megaplan:override",
            "megaplan:model-routing",
        )

    def test_tiebreaker_and_finalize_policy_metadata_expose_route_surface(self) -> None:
        assert planning.declared_step_policy_refs("finalize") == (
            "megaplan:default",
            "megaplan:finalize",
            "megaplan:artifact-contract",
        )
        assert workflows.TIEBREAKER_POLICY.metadata["route_surface"] == {
            "run_completion_route": {
                "route_signal": "default",
                "target_ref": "tiebreaker_decision",
                "failure_behavior": "complete_decision_cycle_with_recorded_artifacts",
            },
            "decision_routes": {
                "pick": {"route_signal": "proceed", "target_ref": "finalize"},
                "replan": {"route_signal": "replan", "target_ref": "revise"},
                "reiterate": {"route_signal": "iterate", "target_ref": "critique-fanout"},
                "escalate": {"route_signal": "escalate", "target_ref": "override"},
            },
            "fallback_route_signal": "escalate",
        }
        assert workflows.FINALIZE_POLICY.metadata["route_surface"] == {
            "success_route": {
                "route_signal": "default",
                "target_ref": "execute",
                "artifact_effect_id": "artifact.finalize.plan",
                "artifact_policy_ref": "megaplan:artifact-contract",
                "projection_route_ref": "finalize:execute",
                "state_ref": "finalized",
            },
            "fallback_routes": {
                "plan_contract_revise_needed": {
                    "route_signal": "revise",
                    "target_ref": "revise",
                    "reason": "missing_scoped_baseline_test_contract",
                    "projection_route_ref": "finalize:revise",
                    "phase_ref": "revise",
                },
            },
            "skip_review_routes": {
                "no_review": {
                    "route_signal": "no_review",
                    "target_ref": "halt",
                    "terminal_state": "done",
                    "branch_ref": "execute:no-review-terminal-done",
                    "projected_status_ref": "status:terminal",
                    "history_entry": "execute_no_review_terminal",
                },
                "deferred_human": {
                    "route_signal": "deferred_human",
                    "target_ref": "halt",
                    "terminal_state": "awaiting_human_verify",
                    "branch_ref": "execute:no-review-terminal-awaiting-human",
                    "projected_status_ref": "status:terminal",
                    "resume_cursor_ref": "cursor:suspension",
                    "history_entry": "execute_no_review_terminal",
                },
            },
            "canonical_artifacts": {
                "finalize_plan": {
                    "effect_id": "artifact.finalize.plan",
                    "payload_ref": "finalize.finalize_payload",
                    "policy_ref": "megaplan:artifact-contract",
                    "idempotency_key_ref": "artifact_contract.finalize",
                },
            },
            "final_projection_routes": {
                "execute": {
                    "route_signal": "default",
                    "target_ref": "execute",
                    "state_ref": "finalized",
                    "artifact_ref": "artifact.finalize.plan",
                    "projected_phase": "execute",
                },
                "revise_fallback": {
                    "route_signal": "revise",
                    "target_ref": "revise",
                    "projected_phase": "revise",
                    "reason": "missing_scoped_baseline_test_contract",
                },
                "no_review_done": {
                    "route_signal": "no_review",
                    "target_ref": "halt",
                    "terminal_state": "done",
                    "projected_status_ref": "status:terminal",
                },
                "no_review_deferred_human": {
                    "route_signal": "deferred_human",
                    "target_ref": "halt",
                    "terminal_state": "awaiting_human_verify",
                    "projected_status_ref": "status:terminal",
                    "resume_cursor_ref": "cursor:suspension",
                },
            },
        }
        assert workflows.FINALIZE_POLICY.metadata["authoring_surface"] is True
        assert workflows.FINALIZE_POLICY.metadata["carrier_step_ref"] == "finalize"

    def test_execute_policy_metadata_exposes_gates_fanout_retry_and_recovery(self) -> None:
        route_surface = workflows.EXECUTE_POLICY.metadata["route_surface"]
        assert route_surface["approval_gates"]["destructive_confirmation"] == {
            "required_unless": "prose_mode",
            "signal_ref": "args.confirm_destructive",
            "failure_code": "missing_confirmation",
        }
        assert route_surface["approval_gates"]["operator_approval"] == {
            "required_unless": "state.config.auto_approve",
            "signal_ref": "state.meta.user_approved_gate",
            "grant_signal_ref": "args.user_approved",
            "failure_code": "missing_approval",
        }
        assert route_surface["fanout_contract"] == {
            "parallel_map_id": "execute-batches",
            "fanout_ref": "megaplan.execute.batches",
            "step_ref": "SOURCE_EXECUTE_BATCH_WORKFLOW",
            "reducer_ref": "SOURCE_EXECUTE",
            "path_template": "execute/{index}",
            "route_signal": "execute_payload",
        }
        assert route_surface["retry_and_reentry"] == {
            "review_rework_reexecution": {
                "detect_ref": "last review history result needs_rework",
                "effect": "force_fresh_execute_session",
            },
            "blocked_retry": {
                "detect_ref": "last execute history result blocked",
                "effect": "force_fresh_execute_session",
            },
            "blocked_route": {
                "route_signal": "blocked",
                "target_ref": "override",
                "recoverable_state": "blocked",
                "resume_cursor": {
                    "phase": "execute",
                    "retry_strategy": "fresh_session",
                },
            },
        }

    def test_review_policy_metadata_exposes_rework_cap_recovery_and_escalation(self) -> None:
        route_surface = workflows.REVIEW_POLICY.metadata["route_surface"]
        assert route_surface["fan_in_contract"] == {
            "parallel_map_id": "review-fan-in",
            "fan_in_ref": "review.checks",
            "step_ref": "SOURCE_REVIEW_PANEL_WORKFLOW",
            "reducer_ref": "SOURCE_REVIEW",
            "path_template": "review/{item_id}",
            "route_signal": "review_route_signal",
        }
        assert route_surface["route_groups"] == {
            "halt": ("pass", "force_proceeded", "deferred_human"),
            "rework": ("rework",),
            "recoverable_block": ("blocked",),
        }
        assert route_surface["retry_and_cap"]["infrastructure_retry"] == {
            "route_signal": "blocked",
            "target_ref": "review",
            "state_ref": "executed",
            "retry_on": (
                "review_incomplete",
                "review_process_error",
                "missing_reviewer_evidence",
            ),
        }
        assert route_surface["retry_and_cap"]["cap_exhausted_with_blockers"] == {
            "route_signal": "blocked",
            "target_ref": "override",
            "state_ref": "blocked",
            "resume_cursor": {
                "phase": "review",
                "retry_strategy": "manual_review",
            },
        }
        assert route_surface["escalation"] == {
            "policy_ref": "megaplan:override",
            "route_signal": "blocked",
            "actions": ("recover-blocked", "force-proceed"),
        }

    def test_execute_and_review_child_workflows_expose_route_contracts(self) -> None:
        execute_contract = planning.declared_workflow_topology_contract("execute_batch")
        review_contract = planning.declared_workflow_topology_contract("review_panel")

        assert execute_contract["approval_gates"] == workflows.EXECUTE_POLICY.metadata["route_surface"]["approval_gates"]
        assert execute_contract["fanout_contract"] == workflows.EXECUTE_POLICY.metadata["route_surface"]["fanout_contract"]
        assert execute_contract["retry_and_reentry"] == {
            "review_rework_reexecution": "force_fresh_execute_session",
            "blocked_retry": "force_fresh_execute_session",
            "blocked_route": {
                "route_signal": "blocked",
                "recoverable_state": "blocked",
                "resume_phase": "execute",
            },
        }
        assert review_contract["fan_in_contract"] == workflows.REVIEW_POLICY.metadata["route_surface"]["fan_in_contract"]
        assert review_contract["rework_cycle"] == {
            "route_signal": "rework",
            "target_ref": "execute",
            "fresh_execute_session": True,
        }
        assert review_contract["retry_and_cap"] == {
            "infrastructure_retry": "review",
            "cap_exhausted_non_blocking": "force_proceeded",
            "cap_exhausted_with_blockers": "recoverable_block",
        }

    def test_live_step_metadata_is_quarantined_behind_declared_interfaces(self) -> None:
        expected = {
            "prep": ("declared_step_interface_bridge", {"handler_ref", "route_bindings"}),
            "plan": ("declared_step_interface_bridge", {"handler_ref", "route_bindings"}),
            "critique": ("declared_step_interface_bridge", {"handler_ref", "route_bindings"}),
            (
                "gate"
            ): ("declared_step_interface_bridge", {"handler_ref", "route_bindings", "capability_requirements"}),
            (
                "revise"
            ): ("declared_step_interface_bridge", {"handler_ref", "route_bindings", "capability_requirements"}),
            (
                "tiebreaker_researcher"
            ): ("declared_step_interface_bridge", {"handler_ref", "route_bindings"}),
            (
                "tiebreaker_challenger"
            ): ("declared_step_interface_bridge", {"handler_ref", "route_bindings"}),
            (
                "tiebreaker_synthesis"
            ): ("declared_step_interface_bridge", {"handler_ref", "route_bindings"}),
            (
                "tiebreaker_decision"
            ): ("declared_step_interface_bridge", {"handler_ref", "route_bindings", "capability_requirements"}),
            "finalize": ("non_authoritative_adapter_metadata", {"handler_ref", "policy_refs", "route_bindings"}),
            "execute": ("declared_step_interface_bridge", {"handler_ref", "policy_refs", "capability_requirements"}),
            (
                "review"
            ): (
                "non_authoritative_adapter_metadata",
                {"handler_ref", "policy_refs", "route_bindings", "runtime_branch_vocabulary"},
            ),
            "override": ("declared_step_interface_bridge", {"handler_ref", "route_bindings", "policy_refs", "override_actions"}),
        }
        for step_id, (expected_kind, preserved_fields) in expected.items():
            component = workflows.STEP_COMPONENTS_BY_ID[step_id]
            quarantine = component.metadata["compatibility_quarantine"]
            assert quarantine["kind"] == expected_kind
            assert set(quarantine["preserved_fields"]) == preserved_fields
            if expected_kind == "declared_step_interface_bridge":
                assert quarantine["canonical_refs"] == (
                    f"arnold_pipelines.megaplan.workflows.workflow.pypeline:{step_id}",
                    f"arnold_pipelines.megaplan.workflows.planning:declared_step_interface({step_id})",
                )

    def test_child_workflow_topology_metadata_is_quarantined_behind_declared_contracts(self) -> None:
        expected = {
            "SOURCE_EXECUTE_BATCH_WORKFLOW": ("execute_batch", {"policy_refs", "topology_contract"}),
            "SOURCE_REVIEW_PANEL_WORKFLOW": (
                "review_panel",
                {"fan_in_ref", "policy_refs", "topology_contract"},
            ),
            "SOURCE_TIEBREAKER_WORKFLOW": ("tiebreaker_child", {"policy_refs", "topology_contract"}),
        }
        for export_name, (workflow_id, preserved_fields) in expected.items():
            component = getattr(workflows.components, export_name)
            quarantine = component.metadata["compatibility_quarantine"]
            assert quarantine["kind"] in {
                "declared_topology_contract_bridge",
                "non_authoritative_adapter_metadata",
            }
            assert set(quarantine["preserved_fields"]) == preserved_fields
            assert (
                f"arnold_pipelines.megaplan.workflows.planning:declared_workflow_topology_contract({workflow_id})"
                in quarantine["canonical_refs"]
            )


class TestCompatibilityQuarantine:
    """Verify compatibility exports are explicit quarantine bridges, not authority."""

    def test_legacy_aliases_are_not_exported(self) -> None:
        assert not hasattr(workflows, "LEGACY_ALIASES")
        assert "LEGACY_ALIASES" not in workflows.__all__

    def test_retained_source_pure_body_carriers_are_quarantined(self) -> None:
        expected = {
            "SOURCE_TIEBREAKER_RUN": (
                "arnold_pipelines.megaplan.workflows.workflow.pypeline:tiebreaker_researcher",
                "arnold_pipelines.megaplan.workflows.planning:declared_step_interface(tiebreaker_researcher)",
                "arnold_pipelines.megaplan.workflows.planning:declared_workflow_topology_contract(tiebreaker_child)",
            ),
            "SOURCE_TIEBREAKER_DECIDE": (
                "arnold_pipelines.megaplan.workflows.workflow.pypeline:tiebreaker_decision",
                "arnold_pipelines.megaplan.workflows.planning:declared_step_interface(tiebreaker_decision)",
                "TIEBREAKER_POLICY.metadata.route_surface",
            ),
            "SOURCE_EXECUTE": (
                "arnold_pipelines.megaplan.workflows.workflow.pypeline:execute",
                "arnold_pipelines.megaplan.workflows.planning:declared_step_interface(execute)",
                "EXECUTE_POLICY.metadata.route_surface",
            ),
            "SOURCE_OVERRIDE": (
                "arnold_pipelines.megaplan.workflows.workflow.pypeline:override",
                "arnold_pipelines.megaplan.workflows.planning:declared_step_interface(override)",
                "OVERRIDE_POLICY.metadata.route_surface",
            ),
        }

        for export_name, canonical_refs in expected.items():
            compatibility = getattr(workflows.components, export_name)
            quarantine = compatibility.metadata["compatibility_quarantine"]
            assert compatibility.metadata.get("route_bindings", ()) == ()
            assert quarantine["kind"] == "pure_body_component_metadata_bridge"
            assert quarantine["canonical_refs"] == canonical_refs
            assert quarantine["sunset_condition"] == "typed_interfaces_replace_component_metadata"
            assert "handler_ref" in quarantine["preserved_fields"]


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
