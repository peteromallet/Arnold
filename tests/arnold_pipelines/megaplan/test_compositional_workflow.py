"""Behavioral scenarios for the canonical Megaplan workflow shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.kernel import read_event_journal
from arnold.workflow.compiler import compile_pipeline
from arnold_pipelines.megaplan.pipeline import build_pipeline
from tests.arnold.execution.conftest import FakeBackend


class _BranchSequenceBackend(FakeBackend):
    """Fake backend that chooses route IDs in the supplied order."""

    def __init__(self, *, sequences: dict[str, list[str]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sequences = {node_id: list(edge_ids) for node_id, edge_ids in sequences.items()}

    def _select_branch(self, coordinate, node, edges, context):
        sequence = self._sequences.get(node.id)
        if sequence:
            return sequence.pop(0)
        return super()._select_branch(coordinate, node, edges, context)


def _manifest():
    return compile_pipeline(build_pipeline())


def _completed_node_refs(tmp_path: Path) -> list[str]:
    return [
        event.payload["node_ref"]
        for event in read_event_journal(tmp_path)
        if event.kind == "node_completed" and event.payload.get("child_key") is None
    ]


def _branch_selections(tmp_path: Path) -> dict[str, str]:
    return {
        event.payload["node_ref"]: event.payload["edge_id"]
        for event in read_event_journal(tmp_path)
        if event.kind == "branch_selected"
    }


class TestCompositionalWorkflowScenarios:
    def test_proceed_path_reaches_review_and_done(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:finalize"]})

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_iterate_route_reaches_revise_before_looping(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:revise"],
                "revise": ["revise:critique"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == ["prep", "plan", "critique", "gate", "revise"]
        assert _branch_selections(tmp_path)["revise"] == "revise:critique"

    def test_tiebreaker_path_promotes_back_to_finalize(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:tiebreaker"],
                "tiebreaker_decide": ["tiebreaker_decide:finalize"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "tiebreaker_run",
            "tiebreaker_decide",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_escalation_path_routes_through_override_then_force_proceed(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:override"],
                "override": ["override:finalize"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "override",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_execute_review_rework_path_returns_to_revise(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:finalize"],
                "review": ["review:revise"],
                "revise": ["revise:critique"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
            "revise",
        ]

    def test_human_gate_continue_resumes_into_proceed_path(self, tmp_path: Path) -> None:
        suspend_backend = FakeBackend(
            node_behaviors={
                "gate": NodeOutcome(
                    state=NodeState.SUSPENDED,
                    suspension_route_id="gate:human",
                ),
            }
        )
        first = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=suspend_backend,
        )

        assert first.state is ExecutionState.SUSPENDED
        assert first.resume_cursor is not None

        resume_backend = _BranchSequenceBackend(
            run_id="run:resume",
            reentry_id="resume",
            sequences={"gate": ["gate:finalize"]},
        )
        second = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=resume_backend,
            resume_cursor=first.resume_cursor,
        )

        assert second.state is ExecutionState.COMPLETED
        assert any(event.kind == "node_resumed" for event in read_event_journal(tmp_path))
        assert _completed_node_refs(tmp_path)[-4:] == ["finalize", "execute", "review", "halt"]

    def test_abort_path_stops_at_halt(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:halt"]})

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == ["prep", "plan", "critique", "gate", "halt"]
