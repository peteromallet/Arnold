"""Reusable fake-backend fixtures for execution scenario tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from arnold.execution.backend import (
    ArtifactSpec,
    LocalJournalBackend,
    NodeOutcome,
    NodeState,
)
from arnold.kernel import (
    BudgetReservation,
    ContentTypeRegistration,
    ContentTypeRegistry,
    FileBackedArtifactStore,
    GeneratedArtifactProvenance,
    RetentionPolicy,
    schema_hash,
)
from arnold.manifest import WorkflowEdge, WorkflowManifest, WorkflowNode


_NODE_BEHAVIOR = Callable[["RouteCoordinate", WorkflowNode, Any], NodeOutcome]


class FakeBackend(LocalJournalBackend):
    """Deterministic test backend with configurable per-node behavior."""

    def __init__(
        self,
        *,
        node_behaviors: Mapping[str, NodeOutcome | _NODE_BEHAVIOR | Mapping[str, Any]] | None = None,
        budgets: Mapping[str, BudgetReservation] | None = None,
        branch_selections: Mapping[str, str | None] | None = None,
        child_behaviors: Mapping[str, NodeOutcome | Mapping[str, Any]] | None = None,
        reducer_results: Mapping[str, Mapping[str, Any]] | None = None,
        authority_results: Mapping[str, bool] | None = None,
        subpipeline_results: Mapping[str, NodeOutcome] | None = None,
        child_manifests: Mapping[str, WorkflowManifest] | None = None,
        now: datetime | None = None,
        monotonic_sequence: list[float] | None = None,
        initial_scope_stack: tuple[str, ...] | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("initial_scope_stack", initial_scope_stack)
        super().__init__(**kwargs)
        self.node_behaviors = dict(node_behaviors or {})
        self.budgets = dict(budgets or {})
        self.branch_selections = dict(branch_selections or {})
        self.child_behaviors = dict(child_behaviors or {})
        self.reducer_results = dict(reducer_results or {})
        self.authority_results = dict(authority_results or {})
        self.subpipeline_results = dict(subpipeline_results or {})
        self.child_manifests = dict(child_manifests or {})
        self._now_value = now
        self._monotonic_sequence = list(monotonic_sequence or [])
        self._monotonic_index = 0
        self._text_plain = ContentTypeRegistration(
            type_id="text/plain",
            schema_version="1",
            schema_hash=schema_hash({"type": "string"}),
            retention_policy=RetentionPolicy.RUN,
        )
        self._content_types = ContentTypeRegistry()
        self._content_types.register(self._text_plain)

    def _now(self) -> datetime:
        if self._now_value is not None:
            return self._now_value
        return super()._now()

    def _monotonic(self) -> float:
        if self._monotonic_sequence:
            value = self._monotonic_sequence[self._monotonic_index]
            self._monotonic_index = min(self._monotonic_index + 1, len(self._monotonic_sequence) - 1)
            return value
        return super()._monotonic()

    def _create_artifact_store(self, root: Path) -> FileBackedArtifactStore:
        return FileBackedArtifactStore(root, content_type_registry=self._content_types)

    def _budget_for_node(
        self, coordinate: "RouteCoordinate", node: WorkflowNode
    ) -> BudgetReservation:
        if node.id in self.budgets:
            base = self.budgets[node.id]
            return BudgetReservation(
                node_ref=coordinate.node_ref,
                cost=base.cost,
                seconds=base.seconds,
                tokens=base.tokens,
            )
        return BudgetReservation(node_ref=coordinate.node_ref, cost=0.0, seconds=0.0, tokens=0)

    def _execute_node_payload(
        self, coordinate: "RouteCoordinate", node: WorkflowNode, context: Any
    ) -> NodeOutcome:
        behavior = self.node_behaviors.get(node.id)
        if behavior is None:
            behavior = self.node_behaviors.get(node.kind)
        if callable(behavior):
            outcome = behavior(coordinate, node, context)
        elif isinstance(behavior, NodeOutcome):
            outcome = behavior
        elif isinstance(behavior, Mapping):
            outcome = NodeOutcome(state=NodeState.COMPLETED, outputs=dict(behavior))
        else:
            outcome = NodeOutcome(state=NodeState.COMPLETED)

        budget = self.budgets.get(node.id)
        if budget is not None:
            outcome.actual_cost = budget.cost
            outcome.actual_seconds = budget.seconds
            outcome.actual_tokens = budget.tokens
        return outcome

    def _select_branch(
        self,
        coordinate: "RouteCoordinate",
        node: WorkflowNode,
        edges: tuple[WorkflowEdge, ...],
        context: Any,
    ) -> str | None:
        if node.id in self.branch_selections:
            return self.branch_selections[node.id]
        return super()._select_branch(coordinate, node, edges, context)

    def _execute_fanout_child(
        self,
        coordinate: "RouteCoordinate",
        parent_node: WorkflowNode,
        context: Any,
    ) -> NodeOutcome:
        key = coordinate.child_key or ""
        behavior = self.child_behaviors.get(key)
        if behavior is None:
            behavior = self.child_behaviors.get(parent_node.id)
        if behavior is None:
            return NodeOutcome(
                state=NodeState.COMPLETED,
                outputs={"child_key": key},
            )
        if isinstance(behavior, NodeOutcome):
            return behavior
        if isinstance(behavior, Mapping):
            return NodeOutcome(state=NodeState.COMPLETED, outputs=dict(behavior))
        raise TypeError(f"unsupported child behavior for {key}: {behavior!r}")

    def _reduce(
        self,
        coordinate: "RouteCoordinate",
        reducer_ref: str,
        inputs: tuple[Mapping[str, Any], ...],
        context: Any,
    ) -> Mapping[str, Any]:
        if reducer_ref in self.reducer_results:
            return dict(self.reducer_results[reducer_ref])
        return {"reducer_ref": reducer_ref, "inputs": [dict(i) for i in inputs]}

    def _check_authority(self, action: str, evidence: Mapping[str, Any]) -> bool:
        return self.authority_results.get(action, True)

    def _load_subpipeline_manifest(self, node: WorkflowNode) -> WorkflowManifest | None:
        return self.child_manifests.get(node.id)

    def _execute_subpipeline_scope(
        self,
        coordinate: "RouteCoordinate",
        node: WorkflowNode,
        child_manifest: WorkflowManifest | None,
        context: Any,
    ) -> NodeOutcome:
        behavior = self.subpipeline_results.get(node.id)
        if behavior is not None:
            if callable(behavior):
                return behavior(self, coordinate, node, child_manifest, context)
            return behavior
        # Default: succeed with no child-side events. Subclasses/tests can
        # override to simulate child scopes without launching a nested backend.
        return NodeOutcome(state=NodeState.COMPLETED)


@pytest.fixture
def fake_backend_factory():
    """Return a factory for :class:`FakeBackend` instances."""

    def _factory(**kwargs: Any) -> FakeBackend:
        return FakeBackend(**kwargs)

    return _factory


@pytest.fixture
def deterministic_now() -> datetime:
    return datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
