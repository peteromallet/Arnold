"""T33: scenario tests for reusable fixture shapes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.execution.state import RouteCoordinate
from arnold.kernel import (
    ControlBinding,
    ControlTarget,
    ControlTransition,
    ControlTransitionType,
    EventFamily,
)
from arnold.kernel.journal import read_event_journal
from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
from tests.arnold.execution import fixtures

GOLDEN_RUNTIME_ROOT = Path("tests/fixtures/golden/workflow_manifest_runtime")


class RecordingEffectHandler:
    """Neutral effect handler that records each execution."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: dict[str, Any],
        idempotency_key: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del route, payload, idempotency_key, context
        self.calls.append(effect_id)
        return {"effect_id": effect_id}


class OverrideControlHandler:
    """Neutral control handler for fixture overlays."""

    def apply(
        self,
        transition_id: str,
        *,
        transition_type: str,
        binding: ControlBinding,
        context: dict[str, Any],
    ) -> ControlTransition:
        del transition_type
        return ControlTransition(
            transition_type=ControlTransitionType.OVERRIDE,
            source=ControlTarget(node_ref=context["source_node"]),
            target=binding.target,
            trigger=transition_id,
            payload_schema_hash="sha256:" + "0" * 64,
            policy_ref=binding.policy_ref,
            idempotency_key=f"idem-{transition_id}",
        )


def _node_refs(events: list[Any]) -> set[str]:
    return {
        e.payload["node_ref"]
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }


def test_m1_added_fixture_payload_keeps_route_fields_compatible() -> None:
    data = json.loads((GOLDEN_RUNTIME_ROOT / "human-suspension.json").read_text(encoding="utf-8"))

    assert data["schema_version"] == "workflow-manifest-runtime.golden.v1"
    assert data["coverage_origin"] == "m1-added"
    assert "source_golden" not in data
    assert data["routes"] == ["suspend", "operator-reentry", "resume"]
    assert "seed" not in data["normalization"]

    manifest_contract = data["manifest_contract"]
    assert manifest_contract["id"] == "human-suspension"
    assert manifest_contract["schema_version"] == "arnold.workflow.manifest.v1"

    route_metadata = [
        item["route_metadata"]
        for item in manifest_contract["nodes"] + manifest_contract["edges"]
        if "route_metadata" in item
    ]
    assert {metadata["behavioral_step"] for metadata in route_metadata} == set(data["routes"])
    assert {
        metadata["route_semantics"]
        for metadata in route_metadata
        if "route_semantics" in metadata
    } >= {
        "pauses execution for external human decision",
        "operator payload resumes the suspended node through a stable reentry id",
        "resume continuation after validated human payload",
    }


def test_linear_fixture_completes_in_order(tmp_path: Path, fake_backend_factory) -> None:
    manifest = fixtures.linear_manifest()
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    completed = [e.payload["node_ref"] for e in events if e.kind == "node_completed"]
    assert completed == ["a", "b", "c"]


def test_branch_fixture_routes_selected_target(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.branch_manifest()
    backend = fake_backend_factory(branch_selections={"gate": "e-right"})

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    completed = _node_refs(events)
    assert "gate" in completed
    assert "right" in completed
    assert "left" not in completed
    assert any(e.kind == "branch_selected" for e in events)


def test_loop_fixture_respects_iteration_limit(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.loop_manifest()
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    iterations = [e.payload["iteration"] for e in events if e.kind == "loop_iteration"]
    assert iterations == [1, 2, 3]
    assert sum(1 for e in events if e.kind == "node_completed") == 3


def test_fanout_fixture_spawns_children_and_reducer(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.fanout_manifest()
    backend = fake_backend_factory(
        child_behaviors={
            "fan:child:0": {"value": "a"},
            "fan:child:1": {"value": "b"},
            "fan:child:2": {"value": "c"},
        },
        reducer_results={"reducer.concat": {"joined": "abc"}},
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "reducer_completed" for e in events)
    child_completions = {
        e.payload.get("child_key")
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key")
    }
    assert child_completions == {"fan:child:0", "fan:child:1", "fan:child:2"}


def test_retry_fixture_succeeds_after_transient_failures(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.retry_manifest()
    attempts: list[int] = []

    def behavior(coordinate: RouteCoordinate, node: Any, context: Any) -> NodeOutcome:
        del node, context
        attempts.append(coordinate.attempt)
        if coordinate.attempt < 3:
            return NodeOutcome(state=NodeState.FAILED, error="boom")
        return NodeOutcome(state=NodeState.COMPLETED)

    backend = fake_backend_factory(node_behaviors={"fragile": behavior})

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    assert attempts == [1, 2, 3]


def test_subpipeline_fixture_enters_and_exits_child_scope(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    child_hash = "sha256:" + "c" * 64
    manifest = fixtures.subpipeline_manifest(child_hash)

    def child_scope(
        backend: Any,
        coordinate: RouteCoordinate,
        node: Any,
        child_manifest: Any,
        context: Any,
    ) -> NodeOutcome:
        del node, child_manifest, context
        child_scope_stack = coordinate.scope_stack + (child_hash,)
        backend._append(
            EventFamily.NODE_LIFECYCLE,
            "node_completed",
            {"node_ref": "child1"},
            scope_stack=child_scope_stack,
        )
        return NodeOutcome(state=NodeState.COMPLETED)

    backend = fake_backend_factory(subpipeline_results={"parent": child_scope})

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "subpipeline_entered" for e in events)
    assert any(e.kind == "subpipeline_exited" for e in events)


def test_external_effect_fixture_executes_through_registry(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.external_effect_manifest()
    handler = RecordingEffectHandler()
    registries = ExecutionRegistries(effects={"fx.write": handler})
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )

    assert result.state is ExecutionState.COMPLETED
    assert handler.calls == ["fx.write"]
    events = read_event_journal(tmp_path)
    assert any(e.kind == "effect_intent" for e in events)
    assert any(e.kind == "effect_fulfillment" for e in events)


def test_suspension_fixture_suspends_before_downstream_node(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.suspension_manifest()
    backend = fake_backend_factory(
        node_behaviors={
            "ask": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")
        }
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.SUSPENDED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "node_suspended" for e in events)
    assert not any(
        e.kind == "node_started" and e.payload.get("node_ref") == "after"
        for e in events
    )


def test_replay_fixture_effect_is_idempotent(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.replay_manifest()
    handler = RecordingEffectHandler()
    registries = ExecutionRegistries(effects={"fx.idempotent": handler})
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )

    assert result.state is ExecutionState.COMPLETED
    assert handler.calls == ["fx.idempotent"]
    events = read_event_journal(tmp_path)
    intents = [e for e in events if e.kind == "effect_intent"]
    assert len(intents) == 1


def test_control_transition_fixture_routes_overlay_target(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.control_transition_manifest()
    registries = ExecutionRegistries(controls={"ctrl.override": OverrideControlHandler()})
    backend = fake_backend_factory()

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "control_transition" for e in events)
    completed = _node_refs(events)
    assert "src" in completed
    assert "target" in completed


def test_compensation_fixture_runs_on_failure(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.compensation_manifest()
    handler = RecordingEffectHandler()
    registries = ExecutionRegistries(effects={"fx.release": handler})
    backend = fake_backend_factory(
        node_behaviors={"notify": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
    )

    assert result.state is ExecutionState.FAILED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "compensation_started" for e in events)
    assert any(e.kind == "compensation_completed" for e in events)
    assert handler.calls == ["fx.release"]


def test_escalation_fixture_routes_after_retry_exhaustion(
    tmp_path: Path,
    fake_backend_factory,
) -> None:
    manifest = fixtures.escalation_manifest()
    backend = fake_backend_factory(
        node_behaviors={"fragile": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.FAILED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "escalation_routed" for e in events)
    assert "escalation_target" in _node_refs(events)




@pytest.mark.parametrize(
    "selections,expected_nodes,terminal",
    [
        (
            {"gate": "gate:finalize"},
            {"prep", "plan", "critique", "gate", "finalize", "execute", "review", "halt"},
            ExecutionState.COMPLETED,
        ),
        (
            {"gate": "gate:tiebreaker", "tiebreaker_decide": "tiebreaker_decide:finalize"},
            {"prep", "plan", "critique", "gate", "tiebreaker_run", "tiebreaker_decide", "finalize", "execute", "review", "halt"},
            ExecutionState.COMPLETED,
        ),
        (
            {"gate": "gate:override", "override": "override:finalize"},
            {"prep", "plan", "critique", "gate", "override", "finalize", "execute", "review", "halt"},
            ExecutionState.COMPLETED,
        ),
        (
            {"gate": "gate:blocked", "override": "override:halt"},
            {"prep", "plan", "critique", "gate", "override", "halt"},
            ExecutionState.COMPLETED,
        ),
        (
            {"gate": "gate:force_proceed"},
            {"prep", "plan", "critique", "gate", "finalize", "execute", "review", "halt"},
            ExecutionState.COMPLETED,
        ),
        (
            {"gate": "gate:halt"},
            {"prep", "plan", "critique", "gate", "halt"},
            ExecutionState.COMPLETED,
        ),
    ],
)
def test_megaplan_gate_routing_family(
    tmp_path: Path,
    fake_backend_factory,
    selections: dict[str, str],
    expected_nodes: set[str],
    terminal: ExecutionState,
) -> None:
    manifest = build_and_compile_pipeline()
    backend = fake_backend_factory(branch_selections=selections)

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        backend=backend,
    )

    assert result.state is terminal
    events = read_event_journal(tmp_path)
    completed = {
        e.payload["node_ref"]
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }
    assert expected_nodes <= completed


def test_megaplan_human_gate_suspends(tmp_path: Path, fake_backend_factory) -> None:
    manifest = build_and_compile_pipeline()
    backend = fake_backend_factory(
        node_behaviors={
            "gate": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="gate:human")
        }
    )

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        backend=backend,
    )

    assert result.state is ExecutionState.SUSPENDED
    assert result.resume_cursor is not None
    assert result.resume_cursor.node.id == "gate"
    events = read_event_journal(tmp_path)
    assert any(e.kind == "node_suspended" for e in events)
