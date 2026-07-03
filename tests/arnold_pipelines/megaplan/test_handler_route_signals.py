from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "plan.py"
GATE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "gate.py"
FORBIDDEN_TRANSITION_HELPERS = {"workflow_transition", "workflow_next", "_next_progress_step"}
FORBIDDEN_GATE_TARGETS = {"finalize", "revise", "tiebreaker_run", "override", "halt", "gate"}


def _function_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
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
        assert {"blocked_preflight", "escalate", "retry_gate"} <= strings
        assert FORBIDDEN_GATE_TARGETS.isdisjoint(strings)
