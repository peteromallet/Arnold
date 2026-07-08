"""Tests for the Megaplan manifest backend adapter."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

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

    def test_canonical_tiebreaker_decision_dispatches_through_handler_nodes(
        self,
        tmp_path: Path,
        monkeypatch: Any,
    ) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        plan_dir = tmp_path / "plans" / "test"
        plan_dir.mkdir(parents=True)
        fake = FakeHandler(response={"success": True, "route_signal": "proceed", "decision": "proceed"})
        backend = MegaplanManifestBackend(plan_dir=plan_dir)
        monkeypatch.setattr(backend, "_resolve_handler", lambda _node_id: fake)

        node = make_node("tiebreaker_decision")
        ctx = make_context("tiebreaker_decision")
        outcome = backend._execute_node_payload(ctx.coordinate, node, ctx)

        assert outcome.state == NodeState.COMPLETED
        assert outcome.branch_edge_id == "tiebreaker_decision:finalize"
        assert fake.calls[0][1].node_id == "tiebreaker_decision"

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

    def test_branch_edge_from_route_signal(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        assert backend._branch_edge_id("gate", {"route_signal": "blocked_preflight"}) == "gate:blocked"

    def test_tiebreaker_branch_edge_from_route_signal(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        assert backend._branch_edge_id("tiebreaker_decision", {"route_signal": "proceed"}) == "tiebreaker_decision:finalize"
        assert backend._branch_edge_id("tiebreaker_decision", {"route_signal": "iterate"}) == "tiebreaker_decision:critique"
        assert backend._branch_edge_id("tiebreaker_decision", {"route_signal": "escalate"}) == "tiebreaker_decision:override"

    def test_legacy_tiebreaker_alias_uses_canonical_source_routes(self, tmp_path: Path, monkeypatch: Any) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
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
                else ()
            ),
        )

        assert backend._branch_edge_id("tiebreaker_decide", {"route_signal": "proceed"}) == "tiebreaker_decision:finalize"
        control_signals = backend._build_control_signals("tiebreaker_decide", {"route_signal": "proceed"})
        assert len(control_signals) == 1
        assert control_signals[0].target.node_ref == "finalize"

    def test_review_and_finalize_route_signals_use_quarantined_adapter_bindings(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend
        from arnold_pipelines.megaplan.workflows import components

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")

        finalize_quarantine = components.FINALIZE.metadata["compatibility_quarantine"]
        assert finalize_quarantine["kind"] == "non_authoritative_adapter_metadata"
        assert "FINALIZE_POLICY.metadata.route_surface" in finalize_quarantine["canonical_refs"]
        assert "route_bindings" in finalize_quarantine["preserved_fields"]
        assert backend._branch_edge_id("finalize", {"route_signal": "revise"}) == "finalize:revise"
        finalize_signals = backend._build_control_signals("finalize", {"route_signal": "revise"})
        assert len(finalize_signals) == 1
        assert finalize_signals[0].target.node_ref == "revise"

        review_quarantine = components.REVIEW.metadata["compatibility_quarantine"]
        assert review_quarantine["kind"] == "non_authoritative_adapter_metadata"
        assert "REVIEW_POLICY.metadata.route_surface" in review_quarantine["canonical_refs"]
        assert "route_bindings" in review_quarantine["preserved_fields"]
        assert backend._branch_edge_id("review", {"route_signal": "rework"}) == "review:revise"
        review_signals = backend._build_control_signals("review", {"route_signal": "rework"})
        assert len(review_signals) == 1
        assert review_signals[0].target.node_ref == "execute"

    def test_suspension_route_for_human_state(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend

        backend = MegaplanManifestBackend(plan_dir=tmp_path / "plan")
        assert backend._suspension_route_id("gate", {"state": "awaiting_human"}) == "gate:human"
