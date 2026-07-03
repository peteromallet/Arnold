"""Tests for the canonical Megaplan authored workflow source."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import yaml

from arnold.workflow import check_workflow_source
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline

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


def _called_names(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            calls.add(child.func.id)
    return calls


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


class TestAuthoredWorkflow:
    def test_authored_source_has_zero_compiler_diagnostics(self) -> None:
        result = check_workflow_source(
            planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"),
            source_path=planning.AUTHORING_SOURCE_PATH,
        )

        assert result.ok is True
        assert result.diagnostics == ()

    def test_authoring_source_path_points_to_committed_workflow(self) -> None:
        assert planning.AUTHORING_SOURCE_PATH.name == "workflow.py"
        assert planning.AUTHORING_SOURCE_PATH.is_file()

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
            "tiebreaker_run",
            "tiebreaker_decide",
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
            ("revise", "default"),
            ("tiebreaker_run", "default"),
            ("tiebreaker_decide", "iterate"),
            ("tiebreaker_decide", "proceed"),
            ("tiebreaker_decide", "escalate"),
            ("finalize", "default"),
            ("execute", "default"),
            ("review", "default"),
            ("review", "rework"),
            ("override", "abort"),
            ("override", "force_proceed"),
            ("override", "replan"),
        }
        assert route_labels == expected
        loop_routes = {
            route.id: (route.source, route.target, route.label, route.condition_ref)
            for route in pipeline.routes
            if route.id in {"revise:critique", "tiebreaker_decide:critique"}
        }
        assert loop_routes == {
            "revise:critique": ("revise", "critique", "default", "revise:loop"),
            "tiebreaker_decide:critique": (
                "tiebreaker_decide",
                "critique",
                "iterate",
                "tiebreaker:loop",
            ),
        }

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
        assert step_ids == component_ids

    def test_tiebreaker_component_declares_visible_iterate_proceed_escalate_routes(self) -> None:
        bindings = {
            binding["label"]: binding["target_ref"]
            for binding in planning.AUTHOR_TIEBREAKER_DECIDE.metadata["route_bindings"]
        }
        assert bindings == {"iterate": "critique"}
        compiled = next(
            step for step in workflows.ALL_STEP_COMPONENTS if step.id == "megaplan:tiebreaker_decide"
        )
        route_labels = {binding["label"] for binding in compiled.metadata["route_bindings"]}
        assert {"iterate", "proceed", "escalate"} <= route_labels


class TestPlanningSubworkflowSourceShape:
    def test_planning_spine_names_declared_interfaces(self) -> None:
        func = _function_node("planning_workflow")
        assert {"SOURCE_PREP", "SOURCE_PLAN"} <= _called_names(func)

    def test_critique_gate_revise_spine_uses_parallel_map_and_loop_cursor(self) -> None:
        func = _function_node("planning_workflow")
        assert {
            "SOURCE_CRITIQUE",
            "SOURCE_CRITIQUE_PANEL_WORKFLOW",
            "SOURCE_GATE",
            "SOURCE_REVISE",
            "loop",
            "parallel_map",
        } <= _called_names(func)
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

    def test_tiebreaker_branch_invokes_nested_child_workflow(self) -> None:
        func = _function_node("planning_workflow")
        assert {"SOURCE_TIEBREAKER_WORKFLOW"} <= _called_names(func)
        assert "decision" in _branch_names(func)
        assert _call_ids(func, "SOURCE_TIEBREAKER_WORKFLOW") == {"tiebreaker"}
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

    def test_finalize_execute_review_spine_uses_parallel_maps(self) -> None:
        func = _function_node("planning_workflow")
        assert {
            "SOURCE_FINALIZE",
            "SOURCE_EXECUTE",
            "SOURCE_EXECUTE_BATCH_WORKFLOW",
            "SOURCE_REVIEW",
            "SOURCE_REVIEW_PANEL_WORKFLOW",
            "SOURCE_HALT",
            "SOURCE_REVISE",
            "parallel_map",
        } <= _called_names(func)
        assert "review_route_signal" in _branch_names(func)
        assert {"halt", "review_halt"} <= _call_ids(func, "SOURCE_HALT")
        assert "review_revise" in _call_ids(func, "SOURCE_REVISE")

    def test_override_escalation_spine_names_declared_interfaces(self) -> None:
        func = _function_node("planning_workflow")
        assert {
            "SOURCE_OVERRIDE",
            "SOURCE_HALT",
            "SOURCE_FINALIZE",
            "SOURCE_EXECUTE",
            "SOURCE_REVISE",
        } <= _called_names(func)
        assert "override_result" in _branch_names(func)
        assert {"override_halt", "override_unknown"} <= _call_ids(func, "SOURCE_HALT")
        assert "override_revise" in _call_ids(func, "SOURCE_REVISE")

    def test_parent_visible_suspension_points_remain_on_top_level_spine(self) -> None:
        func = _function_node("planning_workflow")
        assert "gate_suspend" in _call_ids(func, "SOURCE_HALT")
        assert "SOURCE_SUSPEND" not in _called_names(func)
        source = planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8")
        assert "V1 source compiler lowers only the decorated workflow body" in source
