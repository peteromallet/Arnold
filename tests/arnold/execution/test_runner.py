"""Execution-runner scenario tests for T19-T28."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState
from arnold.execution.backend import (
    ArtifactSpec,
    LocalJournalBackend,
    NodeOutcome,
    NodeState,
)
from arnold.execution.state import RouteCoordinate
from arnold.kernel import (
    BudgetReservation,
    EventFamily,
    GovernorBudget,
    read_event_journal,
)
from arnold.kernel.journal import NDJsonEventJournal
from arnold.manifest import (
    BudgetPolicy,
    FanoutPolicy,
    LoopPolicy,
    RetryPolicy,
    SubpipelineRef,
    TimingPolicy,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)


def _manifest(
    *nodes: WorkflowNode,
    edges: tuple[WorkflowEdge, ...] = (),
    policy: WorkflowPolicy | None = None,
) -> WorkflowManifest:
    return WorkflowManifest(id="demo", nodes=nodes, edges=edges, policy=policy)


def _kinds(tmp_path: Path) -> list[str]:
    return [e.kind for e in read_event_journal(tmp_path)]


def _payloads(tmp_path: Path) -> list[dict[str, Any]]:
    return [dict(e.payload) for e in read_event_journal(tmp_path)]


# ---------------------------------------------------------------------------
# T19: linear execution loop
# ---------------------------------------------------------------------------


def test_linear_run_journals_required_lifecycle_events(tmp_path: Path) -> None:
    manifest = _manifest(
        WorkflowNode(id="start", kind="noop"),
        WorkflowNode(id="end", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="start", target="end"),),
    )
    backend = LocalJournalBackend()

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    kinds = _kinds(tmp_path)
    assert kinds[0] == "manifest_loaded"
    assert kinds[1] == "manifest_validated"
    assert "node_started" in kinds
    assert "node_completed" in kinds
    assert "budget_reserved" in kinds
    assert "budget_settled" in kinds
    assert kinds[-1] == "run_completed"


def test_linear_run_produces_outputs_for_completed_nodes(tmp_path: Path) -> None:
    manifest = _manifest(
        WorkflowNode(id="a", kind="noop"),
        WorkflowNode(id="b", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="a", target="b"),),
    )
    backend = LocalJournalBackend()

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.outputs == {"a": {}, "b": {}}


# ---------------------------------------------------------------------------
# T21/T22: routing families
# ---------------------------------------------------------------------------


def test_retry_exhaustion_then_completion(tmp_path: Path, fake_backend_factory) -> None:
    attempts: list[int] = []

    def behavior(coordinate: RouteCoordinate, node: WorkflowNode, context: Any) -> NodeOutcome:
        attempts.append(coordinate.attempt)
        if coordinate.attempt < 3:
            return NodeOutcome(state=NodeState.FAILED, error="boom")
        return NodeOutcome(state=NodeState.COMPLETED, outputs={"ok": True})

    manifest = _manifest(
        WorkflowNode(
            id="fragile",
            kind="task",
            policy=WorkflowPolicy(retry=RetryPolicy(max_attempts=3)),
        ),
    )
    backend = fake_backend_factory(node_behaviors={"fragile": behavior})

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    assert attempts == [1, 2, 3]
    failed_events = [e for e in read_event_journal(tmp_path) if e.kind == "node_failed"]
    assert len(failed_events) == 2
    completed = [e for e in read_event_journal(tmp_path) if e.kind == "node_completed"]
    assert len(completed) == 1
    assert completed[0].payload["attempt"] == 3


def test_retry_exhaustion_fails_when_max_attempts_reached(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fragile",
            kind="task",
            policy=WorkflowPolicy(retry=RetryPolicy(max_attempts=2)),
        ),
    )
    backend = fake_backend_factory(
        node_behaviors={"fragile": NodeOutcome(state=NodeState.FAILED, error="boom")}
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.FAILED
    failed = [e for e in read_event_journal(tmp_path) if e.kind == "node_failed"]
    assert len(failed) == 2


def test_branch_selection_journals_branch_selected_and_routes_target(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(id="gate", kind="branch"),
        WorkflowNode(id="left", kind="noop"),
        WorkflowNode(id="right", kind="noop"),
        edges=(
            WorkflowEdge(id="e-left", source="gate", target="left", condition_ref="cond-left"),
            WorkflowEdge(id="e-right", source="gate", target="right", condition_ref="cond-right"),
        ),
    )
    backend = fake_backend_factory(branch_selections={"gate": "e-right"})

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    branch_events = [e for e in read_event_journal(tmp_path) if e.kind == "branch_selected"]
    assert len(branch_events) == 1
    assert branch_events[0].payload["edge_id"] == "e-right"
    completed = {e.payload["node_ref"] for e in read_event_journal(tmp_path) if e.kind == "node_completed"}
    assert "right" in completed
    assert "left" not in completed


def test_loop_respects_bounded_limit(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="loop",
            kind="loop",
            policy=WorkflowPolicy(loop=LoopPolicy(max_iterations=3)),
        ),
    )
    backend = fake_backend_factory()

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    iterations = [e.payload["iteration"] for e in read_event_journal(tmp_path) if e.kind == "loop_iteration"]
    assert iterations == [1, 2, 3]
    completed = [e for e in read_event_journal(tmp_path) if e.kind == "node_completed"]
    assert len(completed) == 3


def test_fanout_reducer_order_and_inputs(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="fan",
            kind="fanout",
            policy=WorkflowPolicy(fanout=FanoutPolicy(width=2, reducer_ref="reducer.concat")),
        ),
    )
    backend = fake_backend_factory(
        child_behaviors={
            "fan:child:0": {"value": "a"},
            "fan:child:1": {"value": "b"},
        },
        reducer_results={"reducer.concat": {"joined": "ab"}},
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    reducer_events = [e for e in read_event_journal(tmp_path) if e.kind == "reducer_completed"]
    assert len(reducer_events) == 1
    assert reducer_events[0].payload["outputs"] == {"joined": "ab"}
    completed = {(e.payload.get("node_ref"), e.payload.get("child_key")) for e in read_event_journal(tmp_path) if e.kind == "node_completed"}
    assert {("fan", None), ("fan", "fan:child:0"), ("fan", "fan:child:1"), ("fan:reducer", None)} <= completed


# ---------------------------------------------------------------------------
# T22: budget interactions
# ---------------------------------------------------------------------------


def test_budget_cap_blocks_additional_nodes(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(id="cheap", kind="task"),
        WorkflowNode(id="expensive", kind="task"),
        edges=(WorkflowEdge(id="e1", source="cheap", target="expensive"),),
        policy=WorkflowPolicy(budget=BudgetPolicy(max_cost=1.0)),
    )
    backend = fake_backend_factory(
        budgets={
            "cheap": BudgetReservation(node_ref="cheap", cost=0.6),
            "expensive": BudgetReservation(node_ref="expensive", cost=0.6),
        }
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.FAILED
    assert result.diagnostics[0].code == "budget_exceeded"
    completed = {e.payload["node_ref"] for e in read_event_journal(tmp_path) if e.kind == "node_completed"}
    assert "cheap" in completed
    assert "expensive" not in completed


# ---------------------------------------------------------------------------
# T23/T24: subpipeline scopes
# ---------------------------------------------------------------------------


def test_subpipeline_enter_exit_and_child_scope_events(tmp_path: Path, fake_backend_factory) -> None:
    parent_hash = "sha256:" + "p" * 64

    def child_scope(
        backend: LocalJournalBackend,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        child_manifest: WorkflowManifest | None,
        context: Any,
    ) -> NodeOutcome:
        child_scope_stack = coordinate.scope_stack + (node.subpipeline.manifest_hash,)
        backend._append(
            EventFamily.NODE_LIFECYCLE,
            "node_started",
            {"node_ref": "child1"},
            scope_stack=child_scope_stack,
        )
        backend._append(
            EventFamily.NODE_LIFECYCLE,
            "node_completed",
            {"node_ref": "child1"},
            scope_stack=child_scope_stack,
        )
        return NodeOutcome(state=NodeState.COMPLETED)

    manifest = _manifest(
        WorkflowNode(
            id="parent",
            kind="subpipeline",
            subpipeline=SubpipelineRef(manifest_hash=parent_hash, alias="child"),
        ),
    )
    backend = fake_backend_factory(subpipeline_results={"parent": child_scope})

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "subpipeline_entered" for e in events)
    assert any(e.kind == "subpipeline_exited" for e in events)
    child_started = [e for e in events if e.kind == "node_started" and e.scope_stack == (parent_hash,)]
    assert len(child_started) == 1
    assert child_started[0].payload["node_ref"] == "child1"


def test_subpipeline_artifact_provenance_across_scopes(tmp_path: Path, fake_backend_factory) -> None:
    parent_hash = "sha256:" + "p" * 64

    def child_scope(
        backend: LocalJournalBackend,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        child_manifest: WorkflowManifest | None,
        context: Any,
    ) -> NodeOutcome:
        child_scope_stack = coordinate.scope_stack + (node.subpipeline.manifest_hash,)
        child_coord = RouteCoordinate(node_ref="child1", scope_stack=child_scope_stack)
        backend._write_artifact(
            child_coord,
            ArtifactSpec(
                artifact_id="child.out",
                content=b"child",
                content_type_id="text/plain",
                extension="txt",
            ),
        )
        return NodeOutcome(state=NodeState.COMPLETED)

    manifest = _manifest(
        WorkflowNode(
            id="parent",
            kind="subpipeline",
            subpipeline=SubpipelineRef(manifest_hash=parent_hash, alias="child"),
        ),
    )
    backend = fake_backend_factory(
        node_behaviors={
            "parent": NodeOutcome(
                state=NodeState.COMPLETED,
                artifacts=(
                    ArtifactSpec(
                        artifact_id="parent.out",
                        content=b"parent",
                        content_type_id="text/plain",
                        extension="txt",
                    ),
                ),
            )
        },
        subpipeline_results={"parent": child_scope},
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    artifact_events = [e for e in read_event_journal(tmp_path) if e.kind == "artifact_written"]
    assert len(artifact_events) == 2
    scope_stacks = [e.scope_stack for e in artifact_events]
    assert () in scope_stacks
    assert (parent_hash,) in scope_stacks


# ---------------------------------------------------------------------------
# T25/T26: suspension and resume
# ---------------------------------------------------------------------------


def test_clean_suspension_exits_with_suspended_state_and_event(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(id="ask", kind="human"),
        WorkflowNode(id="after", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="ask", target="after"),),
    )
    backend = fake_backend_factory(
        node_behaviors={"ask": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")}
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.SUSPENDED
    assert result.resume_cursor is not None
    suspended = [e for e in read_event_journal(tmp_path) if e.kind == "node_suspended"]
    assert len(suspended) == 1
    assert suspended[0].payload["route_id"] == "operator"


def test_resume_after_suspension_completes_workflow(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(id="ask", kind="human"),
        WorkflowNode(id="after", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="ask", target="after"),),
    )
    backend = fake_backend_factory(
        node_behaviors={"ask": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")}
    )

    suspended_result = backend.run_manifest(
        manifest, artifact_root=tmp_path, registries=ExecutionRegistries()
    )
    assert suspended_result.state is ExecutionState.SUSPENDED
    resume_cursor = suspended_result.resume_cursor
    assert resume_cursor is not None

    # Resume: the suspended node re-executes and completes.
    resume_backend = fake_backend_factory(
        node_behaviors={"ask": NodeOutcome(state=NodeState.COMPLETED, outputs={"answer": 42})},
        run_id=backend._run_id,
    )
    resumed_result = resume_backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        resume_cursor=resume_cursor,
    )

    assert resumed_result.state is ExecutionState.COMPLETED
    resumed_events = [e for e in read_event_journal(tmp_path) if e.kind == "node_resumed"]
    assert len(resumed_events) == 1
    completed = {e.payload["node_ref"] for e in read_event_journal(tmp_path) if e.kind == "node_completed"}
    assert "ask" in completed
    assert "after" in completed


# ---------------------------------------------------------------------------
# T27/T28: authority, cancellation, timeout, deadline, TTL
# ---------------------------------------------------------------------------


def test_authority_failure_quarantines_resume(tmp_path: Path, fake_backend_factory) -> None:
    from arnold.manifest import AuthorityRequirement

    manifest = _manifest(
        WorkflowNode(id="ask", kind="human"),
        policy=WorkflowPolicy(
            authority=(AuthorityRequirement(authority_id="auth.operator", action="resume"),)
        ),
    )
    backend = fake_backend_factory(
        node_behaviors={"ask": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")},
        authority_results={"resume": False},
    )

    suspended = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())
    assert suspended.state is ExecutionState.SUSPENDED
    resume_cursor = suspended.resume_cursor
    assert resume_cursor is not None

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        resume_cursor=resume_cursor,
    )

    assert result.state is ExecutionState.QUARANTINED
    assert any(e.kind == "resume_rejected" for e in read_event_journal(tmp_path))


def test_authority_gated_resume_succeeds(tmp_path: Path, fake_backend_factory) -> None:
    from arnold.manifest import AuthorityRequirement

    manifest = _manifest(
        WorkflowNode(id="ask", kind="human"),
        policy=WorkflowPolicy(
            authority=(AuthorityRequirement(authority_id="auth.operator", action="resume"),)
        ),
    )
    backend = fake_backend_factory(
        node_behaviors={"ask": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")},
        authority_results={"resume": True},
    )

    suspended = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())
    resume_cursor = suspended.resume_cursor
    assert resume_cursor is not None

    resume_backend = fake_backend_factory(
        node_behaviors={"ask": NodeOutcome(state=NodeState.COMPLETED, outputs={"answer": 42})},
        authority_results={"resume": True},
        run_id=backend._run_id,
    )
    result = resume_backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        resume_cursor=resume_cursor,
    )

    assert result.state is ExecutionState.COMPLETED
    assert any(e.kind == "node_resumed" for e in read_event_journal(tmp_path))


def test_cancellation_terminal_state(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(id="stop", kind="cancel"),
        WorkflowNode(id="after", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="stop", target="after"),),
    )
    backend = fake_backend_factory(
        node_behaviors={"stop": NodeOutcome(state=NodeState.CANCELLED)}
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.CANCELLED
    assert any(e.kind == "node_cancelled" for e in read_event_journal(tmp_path))
    assert not any(e.payload.get("node_ref") == "after" for e in read_event_journal(tmp_path) if e.kind == "node_started")


def test_node_timeout_journals_timeout_and_fails_node(tmp_path: Path, fake_backend_factory) -> None:
    manifest = _manifest(
        WorkflowNode(
            id="slow",
            kind="task",
            policy=WorkflowPolicy(timing=TimingPolicy(timeout_seconds=0.5)),
        ),
    )
    backend = fake_backend_factory(
        node_behaviors={"slow": NodeOutcome(state=NodeState.COMPLETED)},
        monotonic_sequence=[0.0, 1.0],
    )

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.FAILED
    assert any(e.kind == "node_timeout" for e in read_event_journal(tmp_path))
    assert any(e.kind == "node_failed" for e in read_event_journal(tmp_path))


def test_manifest_deadline_fails_run(tmp_path: Path, fake_backend_factory, deterministic_now) -> None:
    manifest = _manifest(
        WorkflowNode(id="a", kind="noop"),
        policy=WorkflowPolicy(timing=TimingPolicy(deadline_ref=deterministic_now.isoformat())),
    )
    # Move now past the deadline.
    past = deterministic_now.replace(second=1)
    backend = fake_backend_factory(now=past)

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.FAILED
    assert any(e.kind == "manifest_deadline" for e in read_event_journal(tmp_path))


def test_ttl_expiry_fails_run(tmp_path: Path, fake_backend_factory, deterministic_now) -> None:
    manifest = _manifest(
        WorkflowNode(id="a", kind="noop"),
        policy=WorkflowPolicy(timing=TimingPolicy(ttl_seconds=1.0)),
    )
    later = deterministic_now.replace(second=2)
    backend = fake_backend_factory(now=later, init_ts=deterministic_now)

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.FAILED
    assert any(e.kind == "ttl_expired" for e in read_event_journal(tmp_path))
