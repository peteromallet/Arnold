from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

import pytest

from arnold.execution.backend import ExecutionContext, NodeState
from arnold.execution.state import RouteCoordinate
from arnold.manifest import WorkflowNode


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTE_DISPATCH_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "route_dispatch.py"
SHARED_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "shared.py"
CONTROL_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "control.py"


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


class FakeHandler:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def __call__(self, _root: Path, _args: argparse.Namespace) -> dict[str, Any]:
        return dict(self.response)


def _make_node(node_id: str) -> WorkflowNode:
    return WorkflowNode(id=node_id, kind="megaplan:test")


def _make_context(node_ref: str) -> ExecutionContext:
    return ExecutionContext(
        coordinate=RouteCoordinate(node_ref=node_ref),
        scope_stack=(),
        outputs={},
    )


def test_route_dispatch_private_binding_helpers_are_deleted() -> None:
    import arnold_pipelines.megaplan.route_dispatch as route_dispatch

    assert not hasattr(route_dispatch, "_component_route_bindings_for_step")
    assert not hasattr(route_dispatch, "_declared_route_bindings_for_step")


def test_route_dispatch_requires_explicit_legacy_opt_in_for_resolution() -> None:
    from arnold_pipelines.megaplan.route_dispatch import (
        LegacyRouteDispatchDisabled,
        resolve_route_binding_for_signal,
        resolve_route_target_for_signal,
    )

    with pytest.raises(LegacyRouteDispatchDisabled):
        resolve_route_target_for_signal("gate", "proceed")
    with pytest.raises(LegacyRouteDispatchDisabled):
        resolve_route_binding_for_signal("gate", "proceed")

    binding = resolve_route_binding_for_signal("gate", "proceed", allow_legacy=True)
    assert binding is not None
    assert binding["target_ref"] == "finalize"
    assert resolve_route_target_for_signal("tiebreaker_decide", "proceed", allow_legacy=True) == "finalize"


def test_route_dispatch_no_longer_reads_component_metadata() -> None:
    source = ROUTE_DISPATCH_PATH.read_text(encoding="utf-8")

    assert "STEP_COMPONENTS_BY_ID" not in source
    assert ".metadata" not in source
    assert "lowered_route_bindings_by_step" in source


def test_live_finish_step_projects_source_routes_without_route_dispatch_helper() -> None:
    calls = _called_names(_function_node(SHARED_PATH, "_finish_step"))

    assert "resolve_lowered_route_target_for_signal" in calls
    assert "resolve_route_target_for_signal" not in calls


def test_control_gate_adapters_no_longer_branch_to_handler_route_translators() -> None:
    source = CONTROL_PATH.read_text(encoding="utf-8")

    assert "control_interface_routing_on" not in source
    assert "handle_override" not in source
    assert "build_override_transition_request" in source


def test_manifest_backend_keeps_handler_route_fields_output_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

    plan_dir = tmp_path / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    backend = MegaplanManifestBackend(plan_dir=plan_dir)
    fake = FakeHandler(
        {
            "success": True,
            "route_signal": "proceed",
            "next_step": "legacy-target",
            "recommendation": "PROCEED",
        }
    )
    monkeypatch.setattr(backend, "_resolve_handler", lambda _node_id: fake)

    outcome = backend._execute_node_payload(
        _make_context("gate").coordinate,
        _make_node("gate"),
        _make_context("gate"),
    )

    assert outcome.state == NodeState.COMPLETED
    assert outcome.branch_edge_id is None
    assert outcome.control_signals == ()
    assert outcome.outputs["route_signal"] == "proceed"
    assert outcome.outputs["next_step"] == "legacy-target"


def test_cli_progress_drops_handler_next_step_route_hints() -> None:
    import arnold_pipelines.megaplan.cli.__init__ as cli_module

    captured: dict[str, Any] = {}

    class Recorder:
        def phase_end(self, *args, **kwargs) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

        def plan_done(self, *args, **kwargs) -> None:
            captured["done"] = (args, kwargs)

        def plan_failed(self, *args, **kwargs) -> None:
            captured["failed"] = (args, kwargs)

        def execution_blocked(self, *args, **kwargs) -> None:
            captured["blocked"] = (args, kwargs)

    cli_module._emit_response_progress(
        "execute",
        {
            "success": True,
            "step": "execute",
            "state": "blocked",
            "result": {"status": "noop"},
            "next_step": "revise",
        },
        Recorder(),
    )

    assert captured["kwargs"]["next_step"] is None
    assert "blocked" in captured


def test_status_payload_does_not_smuggle_force_proceed_from_gate_preflight(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

    payload = _build_status_payload(
        tmp_path,
        {
            "name": "demo",
            "current_state": "blocked",
            "iteration": 1,
            "config": {"mode": "code"},
            "meta": {},
            "history": [],
            "sessions": {},
            "plan_versions": [],
            "last_gate": {
                "recommendation": "PROCEED",
                "passed": False,
                "preflight_results": {
                    "claude_available": False,
                    "codex_available": False,
                },
            },
        },
    )

    assert payload["next_step"] is None
    assert payload["valid_next"] == []
    assert payload["legacy_route_hints"] == {
        "authority": "display_only_non_authoritative",
        "next_step": None,
        "valid_next": [],
    }


def test_cli_list_fences_inferred_next_steps_as_legacy_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arnold_pipelines.megaplan.cli.__init__ as cli_module

    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"demo","idea":"ship it","current_state":"prepped","iteration":2}',
        encoding="utf-8",
    )

    monkeypatch.setattr(cli_module, "_collect_megaplan_roots", lambda *args, **kwargs: [tmp_path])

    response = cli_module.handle_list(
        tmp_path,
        argparse.Namespace(
            list_target=None,
            filter_status=None,
            no_tree=False,
            include_done=False,
            summary=False,
            all=False,
        ),
    )

    plan = response["plans"][0]
    assert plan["observed_phase"] == "prepped"
    assert plan["legacy_route_hints"]["next_step"] == plan["next_step"]
    assert plan["legacy_route_hints"]["valid_next"] == ["plan"]
