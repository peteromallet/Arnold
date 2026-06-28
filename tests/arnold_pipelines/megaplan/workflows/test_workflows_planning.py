"""Golden/parity tests for the M4 Megaplan planning workflow.

These tests compile the canonical explicit-node pipeline and fake-run it
through :func:`arnold.execution.run` with a configurable backend.  Each
test exercises one gate transition family and asserts the expected node
sequence and terminal state.

Branch selections in the fake backend must use the compiled manifest edge
IDs.  In particular the ``abort`` and ``suspend`` gate routes share the
``halt`` target and have edge IDs ``gate:halt`` and ``gate:suspend``.
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.kernel import read_event_journal
from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
from tests.arnold.execution.conftest import FakeBackend


class _BranchSequenceBackend(FakeBackend):
    """FakeBackend that pops branch edge IDs from per-node sequences."""

    def __init__(
        self,
        *,
        sequences: dict[str, list[str]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._sequences = {node_id: list(edge_ids) for node_id, edge_ids in sequences.items()}

    def _select_branch(
        self,
        coordinate,
        node,
        edges,
        context,
    ):
        seq = self._sequences.get(node.id)
        if seq:
            return seq.pop(0)
        return super()._select_branch(coordinate, node, edges, context)


def _completed_node_refs(tmp_path: Any) -> list[str]:
    return [
        event.payload["node_ref"]
        for event in read_event_journal(tmp_path)
        if event.kind == "node_completed" and event.payload.get("child_key") is None
    ]


def _branch_selections(tmp_path: Any) -> dict[str, str]:
    return {
        event.payload["node_ref"]: event.payload["edge_id"]
        for event in read_event_journal(tmp_path)
        if event.kind == "branch_selected"
    }


@pytest.fixture
def manifest():
    return build_and_compile_pipeline()


class TestExplicitNodeCoverage:
    def test_all_canonical_stages_present(self) -> None:
        pipeline = build_pipeline()
        step_ids = [step.id for step in pipeline.steps]
        for required in (
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
        ):
            assert required in step_ids

    def test_gate_transition_families_are_encoded(self) -> None:
        pipeline = build_pipeline()
        gate_edges = {edge.label: edge for edge in pipeline.routes if edge.source == "gate"}
        for label in (
            "proceed",
            "iterate",
            "tiebreaker",
            "escalate",
            "abort",
            "suspend",
            "blocked_preflight",
            "force_proceed",
        ):
            assert label in gate_edges, f"missing gate transition family: {label}"

    def test_tiebreaker_can_loop_at_least_twice(self) -> None:
        pipeline = build_pipeline()
        # A path exists from tiebreaker_decide -> critique -> gate -> tiebreaker_run.
        edge_ids = {edge.id for edge in pipeline.routes}
        assert "tiebreaker_decide:critique" in edge_ids
        assert "critique:gate" in edge_ids
        assert "gate:tiebreaker" in edge_ids
        assert "tiebreaker_run:decide" in edge_ids


class TestFakeRunRoutingFamilies:
    def test_happy_path_proceeds_to_completion(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:finalize"]})

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert completed == [
            "prep",
            "plan",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_iterate_route_reaches_revise(self, tmp_path, manifest) -> None:
        """The iterate family routes gate -> revise.

        Because the runtime does not re-execute already-completed nodes in the
        same scope, the loop back to ``critique`` is a topology cycle; this
        test proves the cycle starts at ``revise`` and the branch is selected.
        """
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:revise"],
                "revise": ["revise:critique"],
            }
        )

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert completed == ["prep", "plan", "critique", "gate", "revise"]
        selections = _branch_selections(tmp_path)
        assert selections.get("gate") == "gate:revise"
        assert selections.get("revise") == "revise:critique"

    def test_tiebreaker_once_then_proceed(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:tiebreaker"],
                "tiebreaker_decide": ["tiebreaker_decide:finalize"],
            }
        )

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert completed == [
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

    def test_escalate_to_override_then_force_proceed(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:override"],
                "override": ["override:finalize"],
            }
        )

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert "override" in completed
        assert completed[-3:] == ["execute", "review", "halt"]

    def test_blocked_preflight_routes_to_override_then_abort(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:blocked"],
                "override": ["override:halt"],
            }
        )

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert completed == ["prep", "plan", "critique", "gate", "override", "halt"]

    def test_force_proceed_bypasses_override(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:force_proceed"]})

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert "override" not in completed
        assert completed[-3:] == ["execute", "review", "halt"]

    def test_abort_terminates_at_halt(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:halt"]})

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert completed == ["prep", "plan", "critique", "gate", "halt"]

    def test_human_gate_suspends_with_resume_cursor(self, tmp_path, manifest) -> None:
        backend = FakeBackend(
            node_behaviors={
                "gate": NodeOutcome(
                    state=NodeState.SUSPENDED,
                    suspension_route_id="gate:human",
                ),
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
        assert any(
            event.kind == "node_suspended" and event.payload.get("route_id") == "gate:human"
            for event in events
        )

    def test_resume_from_human_gate_proceeds(self, tmp_path, manifest) -> None:
        suspend_backend = FakeBackend(
            node_behaviors={
                "gate": NodeOutcome(
                    state=NodeState.SUSPENDED,
                    suspension_route_id="gate:human",
                ),
            }
        )
        first = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=suspend_backend,
        )
        assert first.state is ExecutionState.SUSPENDED

        resume_backend = _BranchSequenceBackend(
            run_id="run:resume",
            reentry_id="resume",
            sequences={"gate": ["gate:finalize"]},
        )
        second = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=resume_backend,
            resume_cursor=first.resume_cursor,
        )

        assert second.state is ExecutionState.COMPLETED
        events = read_event_journal(tmp_path)
        assert any(event.kind == "node_resumed" for event in events)

    def test_review_rework_route_reaches_revise(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:finalize"],
                "review": ["review:revise"],
                "revise": ["revise:critique"],
            }
        )

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        completed = _completed_node_refs(tmp_path)
        assert "review" in completed
        assert "revise" in completed
        selections = _branch_selections(tmp_path)
        assert selections.get("review") == "review:revise"

    def test_human_review_suspends(self, tmp_path, manifest) -> None:
        backend = _BranchSequenceBackend(
            sequences={"gate": ["gate:finalize"]},
            node_behaviors={
                "review": NodeOutcome(
                    state=NodeState.SUSPENDED,
                    suspension_route_id="review:human",
                ),
            },
        )

        result = run(
            manifest,
            artifact_root=tmp_path,
            registries=ExecutionRegistries(),
            backend=backend,
        )

        assert result.state is ExecutionState.SUSPENDED
        assert result.resume_cursor is not None
        assert result.resume_cursor.node.id == "review"


class TestCompileAndTopology:
    def test_compiled_manifest_is_stable(self) -> None:
        first = build_and_compile_pipeline()
        second = build_and_compile_pipeline()
        assert first.manifest_hash == second.manifest_hash
        assert first.topology_hash == second.topology_hash

    def test_manifest_contains_locked_m2_behavioral_steps(self) -> None:
        manifest = build_and_compile_pipeline()
        node_ids = {node.id for node in manifest.nodes}
        for step in ("prep", "plan", "critique", "gate", "revise", "finalize", "execute", "review"):
            assert step in node_ids, f"missing locked M2 behavioral step: {step}"
