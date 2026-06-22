"""Tests for the Megaplan manifest backend adapter."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from arnold.execution.backend import ExecutionContext, NodeState
from arnold.execution.registries import ExecutionRegistries
from arnold.execution.state import RouteCoordinate
from arnold.manifest import WorkflowNode


class FakeHandler:
    """Record of arguments passed to a fake handler."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[Path, argparse.Namespace]] = []
        self.response = response or {"success": True, "step": "fake"}

    def __call__(self, root: Path, args: argparse.Namespace) -> dict[str, Any]:
        self.calls.append((root, args))
        return dict(self.response)


def make_node(node_id: str) -> WorkflowNode:
    return WorkflowNode(id=node_id, kind="megaplan:test")


def make_context(node_ref: str = "prep") -> ExecutionContext:
    return ExecutionContext(
        coordinate=RouteCoordinate(node_ref=node_ref),
        scope_stack=(),
        outputs={},
    )


class TestManifestBackendDispatch:
    def test_unknown_node_returns_neutral_outcome(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        node = make_node("unknown")
        ctx = make_context("unknown")
        outcome = backend._execute_node_payload(ctx.coordinate, node, ctx)
        assert outcome.state == NodeState.COMPLETED
        assert outcome.outputs["node_id"] == "unknown"

    def test_dispatch_to_fake_handler(self, tmp_path: Path, monkeypatch: Any) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        plan_dir = tmp_path / "plans" / "test"
        plan_dir.mkdir(parents=True)
        fake = FakeHandler(response={"success": True, "next_step": "plan", "state": "prepped"})

        backend = MegaplanManifestBackend(plan_dir=plan_dir)
        monkeypatch.setattr(backend, "_resolve_handler", lambda _node_id: fake)

        node = make_node("prep")
        ctx = make_context("prep")
        outcome = backend._execute_node_payload(ctx.coordinate, node, ctx)
        assert outcome.state == NodeState.COMPLETED
        # ``prep`` has only an unconditional outgoing edge; no branch is selected.
        assert outcome.branch_edge_id is None
        assert outcome.outputs["next_step"] == "plan"
        assert fake.calls[0][0] == plan_dir.parent
        assert fake.calls[0][1].plan == "test"

    def test_failed_handler_returns_failed_outcome(self, tmp_path: Path, monkeypatch: Any) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        plan_dir = tmp_path / "plans" / "test"
        plan_dir.mkdir(parents=True)
        backend = MegaplanManifestBackend(plan_dir=plan_dir)

        def failing_handler(root: Path, args: argparse.Namespace) -> dict[str, Any]:
            raise RuntimeError("boom")

        monkeypatch.setattr(backend, "_resolve_handler", lambda _node_id: failing_handler)

        node = make_node("prep")
        ctx = make_context("prep")
        outcome = backend._execute_node_payload(ctx.coordinate, node, ctx)
        assert outcome.state == NodeState.FAILED
        assert "boom" in (outcome.error or "")

    def test_gate_recommendation_emits_control_transition(self, tmp_path: Path, monkeypatch: Any) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        plan_dir = tmp_path / "plans" / "test"
        plan_dir.mkdir(parents=True)
        backend = MegaplanManifestBackend(plan_dir=plan_dir)
        fake = FakeHandler(response={"success": True, "recommendation": "ITERATE"})
        monkeypatch.setattr(backend, "_resolve_handler", lambda _node_id: fake)

        node = make_node("gate")
        ctx = make_context("gate")
        outcome = backend._execute_node_payload(ctx.coordinate, node, ctx)
        assert outcome.branch_edge_id == "gate:revise"
        assert len(outcome.control_signals) == 1
        signal = outcome.control_signals[0]
        assert signal.target.node_ref == "revise"

    def test_build_megaplan_registries(self) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import build_megaplan_registries

        registries = build_megaplan_registries()
        assert isinstance(registries, ExecutionRegistries)


class TestBackendBranchSelection:
    def test_branch_edge_from_next_step(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        assert backend._branch_edge_id("gate", {"next_step": "revise"}) == "gate:revise"

    def test_branch_edge_from_recommendation(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        assert backend._branch_edge_id("gate", {"recommendation": "PROCEED"}) == "gate:finalize"

    def test_suspension_route_for_human_state(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        assert backend._suspension_route_id("gate", {"state": "awaiting_human"}) == "gate:human"
