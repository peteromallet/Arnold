"""Tests for the canonical Megaplan authored workflow source."""

from __future__ import annotations

import ast
import importlib
import sys
from ast import literal_eval
from pathlib import Path
from types import SimpleNamespace

import yaml

from arnold.workflow import authoring, check_workflow_source, diagnostics
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.workflows.override_matrix import OVERRIDE_ACTION_MATRIX

from arnold_pipelines.megaplan import pipeline as pipeline_facade
from arnold_pipelines.megaplan import workflows
from arnold_pipelines.megaplan.workflows import planning


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "megaplan_m4_topology.yaml"


def _workflow_tree() -> ast.Module:
    return ast.parse(planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"))


def _function_node(name: str) -> ast.FunctionDef:
    for node in _workflow_tree().body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {planning.AUTHORING_SOURCE_PATH}")


def _module_constant(name: str):
    for node in _workflow_tree().body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return literal_eval(node.value)
    raise AssertionError(f"{name} not found in {planning.AUTHORING_SOURCE_PATH}")


def _called_names(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            calls.add(child.func.id)
    return calls


def _referenced_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
    return names


def _branch_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Compare) or not isinstance(child.left, ast.Name):
            continue
        names.add(child.left.id)
    return names


def _call_ids(node: ast.AST, call_name: str) -> set[str]:
    ids: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Name):
            continue
        if child.func.id != call_name:
            continue
        for keyword in child.keywords:
            if keyword.arg == "id" and isinstance(keyword.value, ast.Constant):
                ids.add(str(keyword.value.value))
    return ids


def _clone_step_component_with_metadata(
    component: authoring.StepComponent,
    metadata: Mapping[str, object],
) -> authoring.StepComponent:
    return authoring.StepComponent(
        id=component.id,
        provenance=component.provenance,
        label=component.label,
        step_type=component.step_type,
        prompt=component.prompt,
        policy=component.policy,
        input_schema=component.input_schema,
        output_schema=component.output_schema,
        metadata=metadata,
    )


def _clone_workflow_component_with_metadata(
    component: authoring.ComponentContract,
    metadata: Mapping[str, object],
) -> authoring.ComponentContract:
    return authoring.ComponentContract(
        id=component.id,
        kind=component.kind,
        provenance=component.provenance,
        label=component.label,
        metadata=metadata,
    )


class TestAuthoredWorkflow:
    def test_authored_source_has_zero_compiler_diagnostics(self) -> None:
        result = check_workflow_source(
            planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"),
            source_path=planning.AUTHORING_SOURCE_PATH,
        )
        assert result.ok is False
        assert {
            diagnostic.code for diagnostic in result.diagnostics
        } == {diagnostics.DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY}

        lowered = lower_workflow_file(planning.AUTHORING_SOURCE_PATH)
        manifest = compile_pipeline(lowered)
        assert lowered.id == "megaplan"
        assert manifest.id == "megaplan"

    def test_authoring_source_path_points_to_committed_pypeline(self) -> None:
        assert planning.AUTHORING_SOURCE_PATH.name == "workflow.pypeline"
        assert planning.AUTHORING_SOURCE_PATH.is_file()

    def test_workflow_module_path_is_compatibility_glue_only(self) -> None:
        source = planning.WORKFLOW_MODULE_PATH.read_text(encoding="utf-8")

        assert planning.WORKFLOW_MODULE_PATH.name == "workflow.py"
        assert planning.WORKFLOW_MODULE_PATH.is_file()
        assert "workflow.pypeline" in source
        assert "planning_workflow" not in source
        assert "@workflow" not in source
        assert "SOURCE_CRITIQUE" not in source
        assert "SOURCE_EXECUTE" not in source

    def test_build_pipeline_returns_m3_pipeline(self) -> None:
        pipeline = planning.build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == "megaplan"
        assert pipeline.version == "m4-phase3"

    def test_step_order_matches_fixture(self) -> None:
        pipeline = planning.build_pipeline()
        step_ids = [step.id for step in pipeline.steps]
        assert step_ids == [
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
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

    def test_route_table_is_complete(self) -> None:
        pipeline = planning.build_pipeline()
        route_labels = {(r.source, r.label) for r in pipeline.routes}
        expected = {
            ("prep", "default"),
            ("plan", "default"),
            ("critique", "default"),
            ("gate", "proceed"),
            ("gate", "iterate"),
            ("gate", "tiebreaker"),
            ("gate", "escalate"),
            ("gate", "abort"),
            ("gate", "suspend"),
            ("gate", "blocked_preflight"),
            ("gate", "force_proceed"),
            ("tiebreaker_researcher", "default"),
            ("tiebreaker_challenger", "default"),
            ("tiebreaker_synthesis", "default"),
            ("tiebreaker_decision", "iterate"),
            ("tiebreaker_decision", "proceed"),
            ("tiebreaker_decision", "escalate"),
            ("tiebreaker_decision", "replan"),
            ("finalize", "default"),
            ("execute", "default"),
            ("override", "abort"),
            ("override", "force_proceed"),
            ("override", "replan"),
        }
        assert route_labels == expected
        loop_routes = {
            route.id: (route.source, route.target, route.label, route.condition_ref)
            for route in pipeline.routes
            if route.id in {"revise:critique", "tiebreaker_decision:critique"}
        }
        assert loop_routes == {
            "tiebreaker_decision:critique": (
                "tiebreaker_decision",
                "revise",
                "iterate",
                "tiebreaker:loop",
            ),
        }

    def test_prep_plan_route_is_loaded_from_lowered_source_not_component_metadata(
        self, monkeypatch
    ) -> None:
        stripped_components = []
        for component in planning.ALL_STEP_COMPONENTS:
            if component.id == "megaplan:prep":
                stripped_components.append(
                    SimpleNamespace(
                        id=component.id,
                        step_type=component.step_type,
                        policy=component.policy,
                        metadata={
                            key: value
                            for key, value in component.metadata.items()
                            if key != "route_bindings"
                        },
                    )
                )
            else:
                stripped_components.append(component)
        monkeypatch.setattr(planning, "ALL_STEP_COMPONENTS", tuple(stripped_components))

        pipeline = planning.build_pipeline()

        assert any(
            route.id == "prep:plan"
            and route.source == "prep"
            and route.target == "plan"
            for route in pipeline.routes
        )

    def test_facade_delegates_to_workflows_planning(self) -> None:
        assert pipeline_facade.build_pipeline is planning.build_pipeline

    def test_facade_compiled_output_matches_locked_topology(self) -> None:
        fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
        manifest = pipeline_facade.build_and_compile_pipeline()
        assert manifest.id == fixture["manifest_id"]
        assert manifest.manifest_hash == fixture["manifest_hash"]
        assert manifest.topology_hash == fixture["topology_hash"]

    def test_lowerer_matches_phase1_normalized_shape(self) -> None:
        """The authored workflow lowerer must be identical to the facade."""
        from_facade = pipeline_facade.build_pipeline(max_critique_iterations=7)
        from_workflow = planning.build_pipeline(max_critique_iterations=7)
        assert from_facade == from_workflow

    def test_importing_planning_does_not_load_legacy_package(self) -> None:
        before = set(sys.modules.keys())
        importlib.reload(planning)
        importlib.reload(pipeline_facade)
        loaded = {m for m in set(sys.modules.keys()) - before if m.startswith("arnold.pipelines.megaplan.")}
        assert loaded == set(), f"planning import loaded legacy modules: {loaded}"

    def test_prompt_provenance_in_components_not_manifest(self) -> None:
        """Prompt family refs are discoverable on components but must not leak
        into compiled manifest hash-participating fields.
        """
        pipeline = planning.build_pipeline()
        manifest = compile_pipeline(pipeline)
        # Topology hash equality with the locked fixture proves provenance did
        # not enter the topology. Also assert no step metadata carries prompt
        # resolver details, which would alter the manifest hash.
        for step in pipeline.steps:
            for key in step.metadata:
                assert "prompt" not in key.lower(), (
                    f"step {step.id} metadata key {key!r} may affect manifest hash"
                )
        fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert manifest.topology_hash == fixture["topology_hash"]

    def test_components_connect_to_workflow_steps(self) -> None:
        """Every authored DSL step has a matching product component."""
        pipeline = planning.build_pipeline()
        component_ids = {c.id.removeprefix("megaplan:") for c in workflows.ALL_STEP_COMPONENTS}
        step_ids = {step.id for step in pipeline.steps}
        assert step_ids == component_ids - {"tiebreaker_run", "tiebreaker_decide"}

    def test_rendered_pipeline_metadata_exposes_declared_policy_surface(self) -> None:
        pipeline = planning.build_pipeline()
        assert pipeline.metadata["policy_refs"] == (
            "megaplan:default",
            "megaplan:model-routing",
            "megaplan:robustness",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        )

        execute = next(step for step in pipeline.steps if step.id == "execute")
        review = next(step for step in pipeline.steps if step.id == "review")
        override = next(step for step in pipeline.steps if step.id == "override")

        assert execute.metadata["policy_refs"] == workflows.EXECUTE.metadata["policy_refs"]
        assert review.metadata["policy_refs"] == workflows.REVIEW.metadata["policy_refs"]
        assert override.metadata["override_actions"] == tuple(
            sorted(entry.action for entry in OVERRIDE_ACTION_MATRIX)
        )
        assert workflows.GATE_POLICY.metadata["route_surface"]["route_groups"] == {
            "finalize": ("proceed", "force_proceed"),
            "revise": ("iterate", "retry_gate", "reprompt_downgrade"),
            "tiebreaker": ("tiebreaker",),
            "override": ("escalate", "blocked_preflight"),
            "halt": ("abort", "suspend"),
        }
        assert workflows.GATE_POLICY.metadata["route_surface"]["fallback_route_signals"] == {
            "blocking_flag_reprompt": "retry_gate",
            "reprompt_downgrade": "iterate",
            "preflight_failed": "blocked_preflight",
            "unknown_recommendation": "escalate",
            "critique_cap": "force_proceed",
        }
        expected_diagnostics = {
            "bare_skip": {"owner": "critique-fanout", "effect": "skip_empty_or_bare_findings"},
            "evaluator_retry": {
                "owner": "critique-fanout",
                "effect": "retry_unverifiable_or_unavailable_evaluators",
            },
            "malformed_payload": {
                "owner": "gate",
                "effect": "normalize_to_inferred_recommendation",
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
            },
        }
        assert workflows.GATE_POLICY.metadata["route_surface"]["critique_gate_diagnostics"] == expected_diagnostics

    def test_declared_step_interfaces_survive_component_metadata_stripping(
        self, monkeypatch
    ) -> None:
        baseline_manifest = compile_pipeline(planning.build_pipeline())
        baseline_execute_contract = planning.declared_workflow_topology_contract("execute_batch")
        baseline_review_contract = planning.declared_workflow_topology_contract("review_panel")
        baseline_tiebreaker_contract = planning.declared_workflow_topology_contract("tiebreaker_child")

        stripped_components = []
        for component in planning.PIPELINE_STEP_COMPONENTS:
            step_id = component.id.removeprefix("megaplan:")
            if step_id in {"tiebreaker_run", "tiebreaker_decide"}:
                stripped_components.append(component)
                continue
            stripped_components.append(
                _clone_step_component_with_metadata(
                    component,
                    {
                        key: value
                        for key, value in component.metadata.items()
                        if key
                        not in {
                            "handler_ref",
                            "route_bindings",
                            "policy_refs",
                            "capability_requirements",
                            "override_actions",
                            "terminal",
                        }
                    },
                )
            )

        stripped_components = tuple(stripped_components)
        monkeypatch.setattr(planning, "PIPELINE_STEP_COMPONENTS", stripped_components)
        monkeypatch.setattr(
            planning,
            "PIPELINE_STEP_COMPONENTS_BY_ID",
            {component.id.removeprefix("megaplan:"): component for component in stripped_components},
        )
        for export_name in (
            "SOURCE_EXECUTE_BATCH_WORKFLOW",
            "SOURCE_REVIEW_PANEL_WORKFLOW",
            "SOURCE_TIEBREAKER_WORKFLOW",
        ):
            component = getattr(workflows.components, export_name)
            monkeypatch.setattr(
                workflows.components,
                export_name,
                _clone_workflow_component_with_metadata(
                    component,
                    {
                        key: value
                        for key, value in component.metadata.items()
                        if key not in {"topology_contract", "fan_in_ref", "policy_refs"}
                    },
                ),
            )

        pipeline = planning.build_pipeline()
        manifest = compile_pipeline(pipeline)
        steps = {step.id: step for step in pipeline.steps}

        assert steps["finalize"].metadata["handler_ref"] == planning.declared_handler_binding("finalize")
        assert steps["execute"].metadata["policy_refs"] == planning.declared_step_policy_refs("execute")
        assert steps["review"].metadata["policy_refs"] == planning.declared_step_policy_refs("review")
        assert steps["override"].metadata["override_actions"] == (
            planning.declared_step_interface("override")["override_actions"]
        )
        assert steps["halt"].metadata["terminal"] is True
        assert [(capability.id, capability.route, capability.required) for capability in planning.declared_step_capabilities("review")] == [("human:review", "default", False)]
        assert planning.declared_workflow_topology_contract("execute_batch") == baseline_execute_contract
        assert planning.declared_workflow_topology_contract("review_panel") == baseline_review_contract
        assert planning.declared_workflow_topology_contract("tiebreaker_child") == baseline_tiebreaker_contract
        assert manifest.to_json() == baseline_manifest.to_json()

    def test_declared_surface_readers_match_named_policy_and_topology_contracts(self) -> None:
        critique_surface = planning.declared_route_surface("critique")
        execute_surface = planning.declared_route_surface("execute")
        review_surface = planning.declared_route_surface("review")
        execute_contract = planning.declared_workflow_topology_contract("execute_batch")
        review_contract = planning.declared_workflow_topology_contract("review_panel")

        assert critique_surface["fanout_contract"]["parallel_map_id"] == "critique-fanout"
        assert execute_surface["fanout_contract"] == planning.declared_fanout_contract(step_id="execute")
        assert execute_contract["fanout_contract"] == planning.declared_fanout_contract(
            workflow_id="execute_batch"
        )
        assert execute_surface["fanout_contract"] == execute_contract["fanout_contract"]
        assert review_surface["fan_in_contract"] == planning.declared_fan_in_contract(step_id="review")
        assert review_contract["fan_in_contract"] == planning.declared_fan_in_contract(
            workflow_id="review_panel"
        )
        assert review_surface["fan_in_contract"] == review_contract["fan_in_contract"]

    def test_compiled_views_expose_review_override_execute_policy_surfaces(self) -> None:
        pipeline = planning.build_pipeline()
        manifest = compile_pipeline(pipeline)
        nodes = {node.id: node for node in manifest.nodes}

        execute = nodes["execute"]
        assert execute.policy.retry is not None
        assert execute.policy.retry.max_attempts == 2
        assert execute.policy.escalation is not None
        assert execute.policy.escalation.targets == ("override",)
        assert {overlay.overlay_id for overlay in execute.policy.topology_overlays} == {
            "execute:task-complexity-route"
        }
        assert {effect.effect_id for effect in execute.policy.effects} == {
            "artifact.execute.receipt",
            "artifact.execute.checkpoint",
        }
        assert {route.route_id for route in execute.policy.suspension_routes} == {"execute:resume"}

        review = nodes["review"]
        assert review.policy.retry is not None
        assert review.policy.retry.max_attempts == workflows.M4_LOOP_MAX_ITERATIONS
        assert review.policy.escalation is not None
        assert review.policy.escalation.policy_ref == "megaplan:override"
        assert {
            transition.transition_id for transition in review.policy.control_transitions
        } >= {
            "review:rework",
            "review:done",
            "review:blocked",
            "review:force_proceeded",
            "review:deferred_human",
        }
        assert {overlay.overlay_id for overlay in review.policy.topology_overlays} == {
            "review:cap-exhausted"
        }

        override = nodes["override"]
        assert {
            requirement.action for requirement in override.policy.authority
        } == {"apply", "resume"}
        route_surface = workflows.OVERRIDE_POLICY.metadata["route_surface"]
        assert route_surface["matrix_ref"].endswith("override_matrix:OVERRIDE_ACTION_MATRIX")
        assert {
            action["action"] for action in route_surface["actions"]
        } == {entry.action for entry in OVERRIDE_ACTION_MATRIX}
        assert {overlay.overlay_id for overlay in override.policy.topology_overlays} == {
            f"override:{entry.action}" for entry in OVERRIDE_ACTION_MATRIX
        }
        assert {effect.effect_id for effect in override.policy.effects} == {
            "override.add_note",
            "override.set_robustness",
            "override.set_profile",
            "override.set_model",
            "override.set_vendor",
        }

        assert {
            overlay.overlay_id for overlay in manifest.policy.topology_overlays
        } >= {
            "model-routing:phase",
            "model-routing:task-complexity",
            "suspension:gate-human",
            "suspension:review-human",
            "suspension:execute-resume",
        }
        assert {route.route_id for route in manifest.policy.suspension_routes} >= {
            "gate:human",
            "review:human",
            "revise:loop",
            "tiebreaker:loop",
            "execute:resume",
        }
        assert {effect.effect_id for effect in manifest.policy.effects} >= {
            "artifact.finalize.plan",
            "artifact.execute.receipt",
            "artifact.review.receipt",
        }

    def test_tiebreaker_component_declares_visible_iterate_proceed_escalate_routes(self) -> None:
        bindings = {
            binding["label"]: binding["target_ref"]
            for binding in planning.AUTHOR_TIEBREAKER_DECIDE.metadata["route_bindings"]
        }
        assert bindings == {"iterate": "critique"}
        route_labels = {
            binding["label"] for binding in planning.declared_step_route_bindings("tiebreaker_decision")
        }
        assert {"iterate", "proceed", "escalate", "replan"} <= route_labels


class TestPlanningSubworkflowSourceShape:
    def test_planning_spine_names_declared_interfaces(self) -> None:
        func = _function_node("planning_workflow")
        assert {"AUTHORING_PREP", "AUTHORING_PLAN"} <= _called_names(func)

    def test_critique_gate_revise_spine_uses_parallel_map_and_loop_cursor(self) -> None:
        func = _function_node("planning_workflow")
        assert {"AUTHORING_GATE", "AUTHORING_REVISE", "loop", "parallel_map"} <= _called_names(func)
        assert {"AUTHORING_CRITIQUE", "CRITIQUE_PANEL_WORKFLOW"} <= _referenced_names(func)
        loop_calls = [
            call
            for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "loop"
        ]
        assert len(loop_calls) == 1
        keywords = {keyword.arg: keyword.value for keyword in loop_calls[0].keywords}
        assert isinstance(keywords["reentry_id"], ast.Constant)
        assert keywords["reentry_id"].value == "critique"

    def test_workflow_branches_on_route_signal_outputs_not_payload_objects(self) -> None:
        func = _function_node("planning_workflow")
        branch_names = _branch_names(func)
        assert {"gate_route_signal", "review_route_signal", "decision", "override_result"} <= branch_names
        assert "gate_payload" not in branch_names
        assert "review_payload" not in branch_names

    def test_gate_route_surface_declares_retry_fallback_and_diagnostics(self) -> None:
        assert workflows.GATE_POLICY.metadata["route_surface"]["route_groups"] == {
            "finalize": ("proceed", "force_proceed"),
            "revise": ("iterate", "retry_gate", "reprompt_downgrade"),
            "tiebreaker": ("tiebreaker",),
            "override": ("escalate", "blocked_preflight"),
            "halt": ("abort", "suspend"),
        }
        assert workflows.GATE_POLICY.metadata["route_surface"]["fallback_route_signals"] == {
            "blocking_flag_reprompt": "retry_gate",
            "reprompt_downgrade": "iterate",
            "preflight_failed": "blocked_preflight",
            "unknown_recommendation": "escalate",
            "critique_cap": "force_proceed",
        }
        assert workflows.GATE_POLICY.metadata["route_surface"]["critique_gate_diagnostics"] == {
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
            },
        }

    def test_critique_route_surface_declares_fanout_skip_retry_and_wrapping(self) -> None:
        assert workflows.CRITIQUE.metadata["route_surface"]["fanout_contract"] == {
            "parallel_map_id": "critique-fanout",
            "fanout_ref": "megaplan.policy.critique_lenses",
            "step_ref": "SOURCE_CRITIQUE_PANEL_WORKFLOW",
            "reducer_ref": "SOURCE_CRITIQUE",
            "path_template": "critique/{item_id}",
            "route_signal": "critique_payload",
        }
        assert workflows.CRITIQUE.metadata["route_surface"]["skip_and_retry"] == {
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
        assert workflows.CRITIQUE.metadata["route_surface"]["external_call_surface"] == {
            "runtime_wrapper_ref": "arnold_pipelines.megaplan.orchestration.critique_runtime",
            "retained_handler_ref": "arnold_pipelines.megaplan.handlers.critique:handle_critique",
            "worker_phase": "critique",
            "evaluator_phase": "critique_evaluator",
        }
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
            "success_route": {"route_signal": "default", "target_ref": "execute"},
            "fallback_routes": {
                "plan_contract_revise_needed": {
                    "route_signal": "revise",
                    "target_ref": "revise",
                    "reason": "missing_scoped_baseline_test_contract",
                },
            },
        }

    def test_planning_workflow_branches_on_typed_outcomes(self) -> None:
        func = _function_node("planning_workflow")
        assert "GATE_ROUTE_GROUPS" not in _referenced_names(func)
        compared_outcomes = {
            f"{comparator.value.id}.{comparator.attr}"
            for node in ast.walk(func)
            if isinstance(node, ast.Compare)
            for comparator in node.comparators
            if isinstance(comparator, ast.Attribute)
            and isinstance(comparator.value, ast.Name)
        }
        assert {
            "GateOutcome.PROCEED",
            "GateOutcome.ITERATE",
            "GateOutcome.TIEBREAKER",
            "GateOutcome.ESCALATE",
            "GateOutcome.BLOCKED_PREFLIGHT",
            "GateOutcome.FORCE_PROCEED",
            "ReviewOutcome.PASS",
            "ReviewOutcome.REWORK",
            "TiebreakerOutcome.PROCEED",
            "OverrideOutcome.FORCE_PROCEED",
        } <= compared_outcomes

    def test_canonical_source_rejects_raw_string_route_branches(self) -> None:
        source = planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8").replace(
            "GateOutcome.PROCEED",
            '"proceed"',
            1,
        )

        result = check_workflow_source(source, source_path=planning.AUTHORING_SOURCE_PATH)

        assert result.ok is False
        assert diagnostics.DiagnosticCode.RAW_STRING_ROUTE_BRANCH in {
            diagnostic.code for diagnostic in result.diagnostics
        }

    def test_tiebreaker_branch_invokes_nested_child_workflow(self) -> None:
        func = _function_node("planning_workflow")
        assert {
            "TIEBREAKER_RESEARCHER",
            "TIEBREAKER_CHALLENGER",
            "TIEBREAKER_SYNTHESIS",
            "TIEBREAKER_DECISION",
        } <= _called_names(func)
        assert "decision" in _branch_names(func)
        loop_calls = [
            call
            for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "loop"
        ]
        assert len(loop_calls) == 1
        keywords = {keyword.arg: keyword.value for keyword in loop_calls[0].keywords}
        assert isinstance(keywords["reentry_id"], ast.Constant)
        assert keywords["reentry_id"].value == "critique"
        route_surface = workflows.TIEBREAKER_POLICY.metadata["route_surface"]
        assert route_surface == {
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
        topology_contract = workflows.SOURCE_TIEBREAKER_WORKFLOW.metadata["topology_contract"]
        assert topology_contract["canonical_run_completion_target_ref"] == route_surface[
            "run_completion_route"
        ]["target_ref"]
        assert topology_contract["fallback_route_signal"] == route_surface["fallback_route_signal"]

    def test_finalize_policy_declares_revise_fallback_outside_handler_control_flow(self) -> None:
        route_surface = workflows.FINALIZE_POLICY.metadata["route_surface"]
        assert route_surface["success_route"] == {"route_signal": "default", "target_ref": "execute"}
        assert route_surface["fallback_routes"]["plan_contract_revise_needed"] == {
            "route_signal": "revise",
            "target_ref": "revise",
            "reason": "missing_scoped_baseline_test_contract",
        }

    def test_execute_route_surface_declares_gates_fanout_retry_and_recovery(self) -> None:
        source_surface = workflows.EXECUTE_POLICY.metadata["route_surface"]
        policy_surface = workflows.EXECUTE_POLICY.metadata["route_surface"]
        child_contract = workflows.SOURCE_EXECUTE_BATCH_WORKFLOW.metadata["topology_contract"]

        assert policy_surface == source_surface
        assert source_surface["approval_gates"] == {
            "destructive_confirmation": {
                "required_unless": "prose_mode",
                "signal_ref": "args.confirm_destructive",
                "failure_code": "missing_confirmation",
            },
            "operator_approval": {
                "required_unless": "state.config.auto_approve",
                "signal_ref": "state.meta.user_approved_gate",
                "grant_signal_ref": "args.user_approved",
                "failure_code": "missing_approval",
            },
            "mutating_preflight": {
                "policy_ref": (
                    "arnold_pipelines.megaplan.runtime.execution_environment:"
                    "preflight_mutating_phase"
                ),
                "phase": "execute",
            },
        }
        assert source_surface["fanout_contract"] == {
            "parallel_map_id": "execute-batches",
            "fanout_ref": "megaplan.execute.batches",
            "step_ref": "SOURCE_EXECUTE_BATCH_WORKFLOW",
            "reducer_ref": "SOURCE_EXECUTE",
            "path_template": "execute/{index}",
            "route_signal": "execute_payload",
        }
        assert source_surface["retry_and_reentry"]["blocked_route"] == {
            "route_signal": "blocked",
            "target_ref": "override",
            "recoverable_state": "blocked",
            "resume_cursor": {
                "phase": "execute",
                "retry_strategy": "fresh_session",
            },
        }
        assert child_contract["fanout_contract"] == source_surface["fanout_contract"]
        assert child_contract["approval_gates"] == source_surface["approval_gates"]

    def test_review_route_surface_declares_rework_retry_cap_recovery_and_escalation(self) -> None:
        source_surface = workflows.REVIEW_POLICY.metadata["route_surface"]
        policy_surface = workflows.REVIEW_POLICY.metadata["route_surface"]
        child_contract = workflows.SOURCE_REVIEW_PANEL_WORKFLOW.metadata["topology_contract"]

        assert policy_surface == source_surface
        assert source_surface["fan_in_contract"] == {
            "parallel_map_id": "review-fan-in",
            "fan_in_ref": "review.checks",
            "step_ref": "SOURCE_REVIEW_PANEL_WORKFLOW",
            "reducer_ref": "SOURCE_REVIEW",
            "path_template": "review/{item_id}",
            "route_signal": "review_route_signal",
        }
        assert source_surface["route_groups"] == {
            "halt": ("pass", "force_proceeded", "deferred_human"),
            "rework": ("rework",),
            "recoverable_block": ("blocked",),
        }
        assert source_surface["rework_cycle"] == {
            "route_signal": "rework",
            "target_ref": "execute",
            "state_ref": "finalized",
            "fresh_execute_session": True,
        }
        assert source_surface["retry_and_cap"]["cap_exhausted_with_blockers"] == {
            "route_signal": "blocked",
            "target_ref": "override",
            "state_ref": "blocked",
            "resume_cursor": {
                "phase": "review",
                "retry_strategy": "manual_review",
            },
        }
        assert source_surface["escalation"] == {
            "policy_ref": "megaplan:override",
            "route_signal": "blocked",
            "actions": ("recover-blocked", "force-proceed"),
        }
        assert child_contract["fan_in_contract"] == source_surface["fan_in_contract"]
        assert child_contract["escalation"] == {
            "policy_ref": "megaplan:override",
            "actions": ("recover-blocked", "force-proceed"),
        }

    def test_review_component_rework_binding_matches_policy_cycle_target(self) -> None:
        bindings = {
            binding["label"]: binding["target_ref"]
            for binding in planning.declared_step_route_bindings("review")
        }

        assert bindings["rework"] == workflows.REVIEW_POLICY.metadata["route_surface"]["rework_cycle"][
            "target_ref"
        ]

    def test_lowered_review_rework_cycle_stays_inside_scoped_execute_review_loop(self) -> None:
        lowered = lower_workflow_file(planning.PYPELINE_AUTHORING_SOURCE_PATH)
        route_signatures = {
            (route.source, route.label, route.target)
            for route in lowered.routes
            if route.label != "else"
        }
        topology = planning.lowered_workflow_topology()
        bindings = planning.lowered_route_bindings_by_step(step_ids={"execute", "review"})

        assert ("review-fan-in", "rework", "review-rework-execute-batches") in route_signatures
        assert ("review-rework-execute-batches", "default", "review-rework-fan-in") in route_signatures
        assert "review-rework-execute-batches" in topology["step_aliases"]["execute"]
        assert "review-rework-fan-in" in topology["step_aliases"]["review"]
        assert {
            (binding["label"], binding["target_ref"])
            for binding in bindings["execute"]
        } >= {("default", "review")}
        assert {
            (binding["label"], binding["target_ref"])
            for binding in bindings["review"]
        } >= {("rework", "execute")}
        assert planning.resolve_lowered_route_target_for_signal("execute", "default") == "review"
        assert planning.resolve_lowered_route_target_for_signal("review", "rework") == "execute"

    def test_rework_rereview_split_outcomes_remain_source_visible(self) -> None:
        lowered = lower_workflow_file(planning.PYPELINE_AUTHORING_SOURCE_PATH)
        route_signatures = {
            (route.source, route.label, route.target)
            for route in lowered.routes
            if route.label != "else"
        }
        control_transitions = {
            (
                transition["transition_id"],
                transition["route_signal"],
                transition["target_ref"],
                transition["topology_ref"],
                transition["source_step_id"],
            )
            for transition in workflows.REVIEW_POLICY.metadata["route_surface"]["authored_topology"][
                "control_transitions"
            ]
        }

        assert ("review-fan-in", "rework", "review-rework-execute-batches") in route_signatures
        assert ("review-rework-execute-batches", "default", "review-rework-fan-in") in route_signatures
        assert {
            ("review-rework-fan-in", "pass", "review_rework_halt"),
            ("review-rework-fan-in", "blocked", "review_rework_override"),
            ("review-rework-fan-in", "deferred_human", "review_rework_deferred_human"),
        } <= route_signatures
        assert {
            ("review:blocked", "blocked", "override", "review-fan-in", "review_override"),
            (
                "review:force_proceeded",
                "force_proceeded",
                "halt",
                "review-fan-in",
                "review_halt",
            ),
            (
                "review:deferred_human",
                "deferred_human",
                "halt",
                "review-fan-in",
                "review_deferred_human",
            ),
            (
                "review_rework:blocked",
                "blocked",
                "override",
                "review-rework-fan-in",
                "review_rework_override",
            ),
            (
                "review_rework:force_proceeded",
                "force_proceeded",
                "halt",
                "review-rework-fan-in",
                "review_rework_halt",
            ),
            (
                "review_rework:deferred_human",
                "deferred_human",
                "halt",
                "review-rework-fan-in",
                "review_rework_deferred_human",
            ),
        } <= control_transitions

    def test_finalize_fallback_and_no_review_routing_have_visible_source_or_finalize_policy_carriers(
        self,
    ) -> None:
        lowered = lower_workflow_file(planning.PYPELINE_AUTHORING_SOURCE_PATH)
        route_signatures = {
            (route.source, route.label, route.target)
            for route in lowered.routes
            if route.label != "else"
        }
        finalize_surface = workflows.FINALIZE_POLICY.metadata["route_surface"]
        finalize_bindings = {
            binding["label"]: binding["target_ref"]
            for binding in planning.declared_step_route_bindings("finalize")
        }

        revise_fallback = finalize_surface["fallback_routes"]["plan_contract_revise_needed"]
        assert finalize_bindings.get("revise") == revise_fallback["target_ref"] or any(
            "finalize" in source
            and label == revise_fallback["route_signal"]
            and target == revise_fallback["target_ref"]
            for source, label, target in route_signatures
        )

        assert finalize_surface.get("skip_review_routes") == {
            "no_review": {"route_signal": "no_review", "target_ref": "halt"},
            "deferred_human": {"route_signal": "deferred_human", "target_ref": "halt"},
        } or {
            (label, target)
            for source, label, target in route_signatures
            if "execute" in source and label in {"no_review", "deferred_human"}
        } >= {
            ("no_review", "halt"),
            ("deferred_human", "halt"),
        }

    def test_finalize_execute_review_spine_uses_parallel_maps(self) -> None:
        func = _function_node("planning_workflow")
        assert {
            "AUTHORING_FINALIZE",
            "AUTHORING_EXECUTE",
            "AUTHORING_HALT",
            "AUTHORING_REVISE",
            "parallel_map",
        } <= _called_names(func)
        assert {
            "EXECUTE_BATCH_WORKFLOW",
            "AUTHORING_REVIEW",
            "REVIEW_PANEL_WORKFLOW",
        } <= _referenced_names(func)
        assert "review_route_signal" in _branch_names(func)
        assert {"halt", "review_halt"} <= _call_ids(func, "AUTHORING_HALT")
        assert "review_revise" in _call_ids(func, "AUTHORING_REVISE")

    def test_override_escalation_spine_names_declared_interfaces(self) -> None:
        func = _function_node("planning_workflow")
        assert {
            "AUTHORING_OVERRIDE",
            "AUTHORING_HALT",
            "AUTHORING_FINALIZE",
            "AUTHORING_EXECUTE",
            "AUTHORING_REVISE",
        } <= _called_names(func)
        assert "override_result" in _branch_names(func)
        assert {"override_halt", "override_unknown"} <= _call_ids(func, "AUTHORING_HALT")
        assert "override_revise" in _call_ids(func, "AUTHORING_REVISE")

    def test_parent_visible_suspension_points_remain_on_top_level_spine(self) -> None:
        func = _function_node("planning_workflow")
        assert "gate_suspend" in _call_ids(func, "AUTHORING_HALT")
        assert "AUTHORING_SUSPEND" not in _called_names(func)
        source = planning.WORKFLOW_MODULE_PATH.read_text(encoding="utf-8")
        assert "workflow.pypeline" in source


class TestCanonicalPypelineSource:
    def test_pypeline_source_exists_and_compiles(self) -> None:
        source_path = planning.PYPELINE_AUTHORING_SOURCE_PATH
        result = check_workflow_source(
            source_path.read_text(encoding="utf-8"),
            source_path=source_path,
        )

        assert source_path.name == "workflow.pypeline"
        assert source_path.is_file()
        assert result.ok is False
        assert {
            diagnostic.code for diagnostic in result.diagnostics
        } == {diagnostics.DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY}

        lowered = lower_workflow_file(source_path)
        manifest = compile_pipeline(lowered)

        assert lowered.id == "megaplan"
        assert lowered.version == "m4-phase3"
        assert manifest.id == "megaplan"
        assert manifest.version == "m4-phase3"
        assert all(step.source_span is not None for step in lowered.steps)
        assert {step.source_span.path for step in lowered.steps} == {str(source_path)}

    def test_pypeline_source_keeps_control_flow_visible_without_prohibited_wrappers(self) -> None:
        source_path = planning.PYPELINE_AUTHORING_SOURCE_PATH
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        func = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
        function_source = ast.get_source_segment(source, func) or ""

        assert "SOURCE_" not in function_source
        assert "handler_ref" not in function_source
        assert "route_bindings" not in function_source
        assert "manifest_hash" not in source
        assert "dispatch" not in source
        assert "build_manifest" not in source

        assert any(isinstance(node, ast.While) for node in ast.walk(func))
        assert sum(isinstance(node, ast.If) for node in ast.walk(func)) >= 4
        assert {
            "loop",
            "parallel_map",
            "TIEBREAKER_RESEARCHER",
            "TIEBREAKER_CHALLENGER",
            "TIEBREAKER_SYNTHESIS",
            "TIEBREAKER_DECISION",
        } <= _called_names(func)
        assert {"gate_route_signal", "review_route_signal", "decision", "override_result"} <= _branch_names(func)
        assert any(isinstance(node, ast.Return) for node in ast.walk(func))

    def test_pypeline_compiled_topology_matches_existing_fixture_evidence(self) -> None:
        fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
        lowered = lower_workflow_file(planning.PYPELINE_AUTHORING_SOURCE_PATH)
        manifest = compile_pipeline(lowered)

        assert manifest.id == fixture["manifest_id"]
        assert lowered.id == fixture["canonical_authoring"]["workflow_id"]
        assert lowered.version == fixture["canonical_authoring"]["workflow_version"]

        lowered_step_ids = {step.id for step in lowered.steps}
        assert {
            "prep",
            "plan",
            "critique-fanout",
            "gate",
            "revise",
            "tiebreaker_researcher",
            "tiebreaker_challenger",
            "tiebreaker_synthesis",
            "tiebreaker_decision",
            "finalize",
            "execute-batches",
            "review-fan-in",
            "review-rework-execute-batches",
            "review-rework-fan-in",
            "override",
            "halt",
        } <= lowered_step_ids
        assert {
            "blocked_override",
            "fallback_execute",
            "fallback_finalize",
            "force_execute",
            "force_finalize",
            "gate_abort",
            "gate_suspend",
            "override_finalize",
            "override_halt",
            "override_revise",
            "override_unknown",
            "review_halt",
            "review_revise",
            "tiebreaker_finalize",
            "tiebreaker_override",
        } <= lowered_step_ids

        lowered_gate_routes = {
            (route.label, route.target)
            for route in lowered.routes
            if route.source == "gate" and route.label != "else"
        }
        assert lowered_gate_routes == {
            ("abort", "gate_abort"),
            ("blocked_preflight", "blocked_override"),
            ("escalate", "override"),
            ("force_proceed", "force_finalize"),
            ("iterate", "revise"),
            ("proceed", "finalize"),
            ("reprompt_downgrade", "gate_reprompt_revise"),
            ("retry_gate", "gate_retry_revise"),
            ("suspend", "gate_suspend"),
            ("tiebreaker", "tiebreaker_researcher"),
        }

        dynamic_maps = {
            step.id: {
                "items_ref": step.metadata["items_ref"],
                "path_template": step.metadata["path_template"],
            }
            for step in lowered.steps
            if step.kind == "parallel_map"
        }
        assert dynamic_maps["critique-fanout"] == {
            "items_ref": "megaplan.policy.critique_lenses",
            "path_template": "critique/{item_id}",
        }
        assert dynamic_maps["execute-batches"] == {
            "items_ref": "megaplan.execute.batches",
            "path_template": "execute/{index}",
        }
        assert dynamic_maps["review-fan-in"] == {
            "items_ref": "execute_payload",
            "path_template": "review/{item_id}",
        }
        assert dynamic_maps["review-rework-execute-batches"] == {
            "items_ref": "megaplan.execute.batches",
            "path_template": "execute/{index}",
        }
        assert dynamic_maps["review-rework-fan-in"] == {
            "items_ref": "rework_execute_payload",
            "path_template": "review/{item_id}",
        }

        subpipelines = [step for step in lowered.steps if step.kind == "subpipeline"]
        assert subpipelines == []
