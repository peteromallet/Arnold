from __future__ import annotations

import ast
from pathlib import Path

from arnold_pipelines.megaplan.route_dispatch import resolve_route_target_for_signal
from arnold_pipelines.megaplan.workflows.components import STEP_COMPONENTS_BY_ID

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "plan.py"
GATE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "gate.py"
TIEBREAKER_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "_tiebreaker_impl.py"
TIEBREAKER_RUNTIME_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "orchestration" / "tiebreaker_runtime.py"
REVIEW_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "review.py"
OVERRIDE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "override.py"
CRITIQUE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "critique.py"
SHARED_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "shared.py"
ROUTE_DISPATCH_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "route_dispatch.py"
FORBIDDEN_TRANSITION_HELPERS = {"workflow_transition", "workflow_next", "_next_progress_step"}
FORBIDDEN_CRITIQUE_HELPERS = {"run_parallel_critique"}
FORBIDDEN_GATE_TARGETS = {"finalize", "revise", "tiebreaker_run", "override", "halt", "gate"}
FORBIDDEN_TIEBREAKER_TARGETS = {"finalize", "critique", "override"}
FORBIDDEN_REVIEW_TARGETS = {"execute", "review", "halt", "finalize", "revise"}
FORBIDDEN_OVERRIDE_TARGETS = {"finalize", "revise", "halt"}


def _function_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _dict_literal_strings(path: Path, name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Dict):
                    values: set[str] = set()
                    for value in node.value.values:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            values.add(value.value)
                    return values
    raise AssertionError(f"{name} not found in {path}")


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            names.add(child.func.attr)
    return names


def _string_constants(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


class TestPrepSignals:
    def test_handle_prep_does_not_pass_explicit_next_step(self) -> None:
        func = _function_node(PLAN_PATH, "handle_prep")
        finish_calls = [
            call for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_finish_step"
        ]
        assert finish_calls, "handle_prep must call _finish_step"
        assert all(
            keyword.arg != "next_step" for call in finish_calls for keyword in call.keywords
        )

    def test_handle_prep_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(PLAN_PATH, "handle_prep"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)


class TestGateSignals:
    def test_handle_gate_does_not_pass_explicit_next_step(self) -> None:
        func = _function_node(GATE_PATH, "handle_gate")
        finish_calls = [
            call for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_finish_step"
        ]
        assert finish_calls, "handle_gate must call _finish_step"
        assert all(
            keyword.arg != "next_step" for call in finish_calls for keyword in call.keywords
        )

    def test_handle_gate_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(GATE_PATH, "handle_gate"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_gate_route_signal_helper_uses_route_labels_not_targets(self) -> None:
        func = _function_node(GATE_PATH, "_build_gate_route_signal")
        strings = _string_constants(func)
        assert {"blocked_preflight", "escalate"} <= strings
        assert FORBIDDEN_GATE_TARGETS.isdisjoint(strings)


class TestCritiqueSignals:
    def test_handle_critique_avoids_transition_and_fanout_helpers(self) -> None:
        calls = _called_names(_function_node(CRITIQUE_PATH, "handle_critique"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS | FORBIDDEN_CRITIQUE_HELPERS)

    def test_handle_revise_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(CRITIQUE_PATH, "handle_revise"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)


class TestTiebreakerSignals:
    def test_handle_tiebreaker_decide_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(TIEBREAKER_PATH, "handle_tiebreaker_decide"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_tiebreaker_route_signal_helper_uses_route_labels_not_targets(self) -> None:
        func = _function_node(TIEBREAKER_RUNTIME_PATH, "_route_signal_for_tiebreaker_action")
        strings = _string_constants(func)
        assert {"proceed", "iterate", "escalate"} <= strings
        assert FORBIDDEN_TIEBREAKER_TARGETS.isdisjoint(strings)

    def test_runtime_decide_phase_body_emits_labels_not_parent_targets(self) -> None:
        func = _function_node(TIEBREAKER_RUNTIME_PATH, "handle_tiebreaker_decide")
        strings = _string_constants(func)
        assert {"route_signal", "decision"} <= strings
        assert {"finalize", "critique", "override add-note"}.isdisjoint(strings)


class TestReviewSignals:
    def test_handle_review_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(REVIEW_PATH, "handle_review"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_review_route_signal_helper_uses_route_labels_not_targets(self) -> None:
        func = _function_node(REVIEW_PATH, "_resolve_review_outcome")
        strings = {
            call.args[2].value
            for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "ReviewRouteDecision"
            and len(call.args) >= 3
            and isinstance(call.args[2], ast.Constant)
            and isinstance(call.args[2].value, str)
        }
        assert {"pass", "rework", "blocked", "force_proceeded", "deferred_human"} <= strings
        assert FORBIDDEN_REVIEW_TARGETS.isdisjoint(strings)


class TestOverrideSignals:
    def test_handle_override_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(OVERRIDE_PATH, "handle_override"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_override_action_output_uses_matrix_route_labels_not_targets(self) -> None:
        from arnold_pipelines.megaplan.workflows.override_matrix import ROUTE_SIGNAL_BY_ACTION

        strings = set(ROUTE_SIGNAL_BY_ACTION.values())
        assert {
            "abort",
            "adopt_execution",
            "force_proceed",
            "replan",
            "recover_blocked",
            "resume_clarify",
            "add_note",
            "set_robustness",
            "set_profile",
            "set_model",
            "set_vendor",
        } <= strings
        assert FORBIDDEN_OVERRIDE_TARGETS.isdisjoint(strings)


class TestSharedRouteHelpers:
    def test_shared_finish_step_avoids_transition_mutation_helpers(self) -> None:
        calls = _called_names(_function_node(SHARED_PATH, "_finish_step"))
        assert "workflow_transition" not in calls

    def test_shared_finish_step_uses_workflow_route_dispatch_helper(self) -> None:
        calls = _called_names(_function_node(SHARED_PATH, "_finish_step"))
        assert "resolve_route_target_for_signal" in calls

    def test_workflow_route_dispatch_helper_reads_declared_route_bindings(self) -> None:
        source = ROUTE_DISPATCH_PATH.read_text(encoding="utf-8")
        assert "STEP_COMPONENTS_BY_ID" in source
        assert "route_bindings" in source

    def test_front_half_route_dispatch_ignores_component_route_metadata_mutation(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.route_dispatch._component_route_bindings_for_step",
            lambda step: (
                (
                    {
                        "id": "gate:proceed",
                        "label": "proceed",
                        "target_ref": "halt",
                        "condition_ref": "mutated",
                    },
                )
                if step == "gate"
                else tuple(STEP_COMPONENTS_BY_ID[step].metadata.get("route_bindings", ()))
            ),
        )

        assert resolve_route_target_for_signal("gate", "proceed") == "finalize"

    def test_tiebreaker_alias_route_dispatch_ignores_legacy_component_metadata(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.route_dispatch._component_route_bindings_for_step",
            lambda step: (
                (
                    {
                        "id": "tiebreaker_decide:proceed",
                        "label": "proceed",
                        "target_ref": "halt",
                        "condition_ref": "mutated",
                    },
                )
                if step == "tiebreaker_decide"
                else tuple(STEP_COMPONENTS_BY_ID[step].metadata.get("route_bindings", ()))
            ),
        )

        assert resolve_route_target_for_signal("tiebreaker_decide", "proceed") == "finalize"
