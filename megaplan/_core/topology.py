"""Realized-graph topology (M3 Step 4).

`build_topology(RunTopologyConfig) -> Graph` performs, on graph edges, the
same ordered cumulative fold over `WORKFLOW` + `_ROBUSTNESS_OVERRIDES`
that `_workflow_for_robustness` performs on the dict — and exposes the
result through queryable `successors` / `predecessors` / `has_edge` APIs.

`workflow_next` projects from the same source on demand (the projection
filters edges by the 8 `_transition_matches` conditions); reverse-recovery
(`_BLOCKED_RECOVERY_STATES`, `_RESUME_ACTIVE_STATES`) is derived via
`predecessors(state)` rather than persisted as a separate copy.

This module is read-only with respect to the workflow data — it imports
`_workflow_for_robustness` and re-folds; no new edge data is invented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from megaplan._core.workflow import _workflow_for_robustness
from megaplan._core.workflow_data import Transition


# Frozen set of the 8 condition predicates evaluated by
# `megaplan._core.workflow._transition_matches`. Edges carry their
# condition string as metadata; the projection layer filters on it.
CONDITIONS: frozenset[str] = frozenset(
    {
        "always",
        "gate_unset",
        "gate_iterate",
        "gate_escalate",
        "gate_tiebreaker",
        "gate_proceed_agent_availability_blocked",
        "gate_proceed_blocked",
        "gate_proceed",
    }
)


@dataclass(frozen=True)
class Edge:
    """An edge in the realized graph.

    `src` / `dst` are PlanStates. `step` is the next_step label, and
    `condition` is one of the 8 predicates in :data:`CONDITIONS`.
    """

    src: str
    dst: str
    step: str
    condition: str = "always"


@dataclass(frozen=True)
class RunTopologyConfig:
    """The inputs that determine the realized graph for a run."""

    robustness: str = "extreme"
    creative: bool = False
    with_prep: bool = False
    with_feedback: bool = False


@dataclass(frozen=True)
class Graph:
    """Realized state-machine graph: nodes are PlanStates, edges carry
    a condition predicate plus the step name that produced them.
    """

    nodes: frozenset[str]
    edges: tuple[Edge, ...] = field(default=())

    def successors(self, state: str, condition: str | None = None) -> tuple[Edge, ...]:
        """Edges leaving `state`, optionally filtered by condition.

        Returns edges in the same order as the underlying
        `_workflow_for_robustness(...)[state]` list (the order encodes
        the gate priority in `_transition_matches`).
        """
        out = tuple(e for e in self.edges if e.src == state)
        if condition is not None:
            out = tuple(e for e in out if e.condition == condition)
        return out

    def predecessors(self, state: str, condition: str | None = None) -> tuple[Edge, ...]:
        """Edges entering `state` — the on-demand reverse-recovery query.

        Replaces the persisted `_BLOCKED_RECOVERY_STATES` /
        `_RESUME_ACTIVE_STATES` lookups; recovery callers ask the graph,
        not a sidecar table.
        """
        out = tuple(e for e in self.edges if e.dst == state)
        if condition is not None:
            out = tuple(e for e in out if e.condition == condition)
        return out

    def has_edge(
        self,
        src: str,
        dst: str,
        *,
        condition: str | None = None,
        step: str | None = None,
    ) -> bool:
        for e in self.edges:
            if e.src != src or e.dst != dst:
                continue
            if condition is not None and e.condition != condition:
                continue
            if step is not None and e.step != step:
                continue
            return True
        return False


def _edges_from_workflow(
    workflow: dict[str, list[Transition]],
) -> tuple[tuple[Edge, ...], frozenset[str]]:
    edges: list[Edge] = []
    nodes: set[str] = set()
    for src, transitions in workflow.items():
        nodes.add(src)
        for t in transitions:
            nodes.add(t.next_state)
            edges.append(
                Edge(src=src, dst=t.next_state, step=t.next_step, condition=t.condition)
            )
    return tuple(edges), frozenset(nodes)


def build_topology(config: RunTopologyConfig) -> Graph:
    """Realize the run's graph by folding `_ROBUSTNESS_OVERRIDES`.

    Re-invocable mid-run: a fresh `RunTopologyConfig` rebuilds the graph
    from scratch; the resume cursor remains a state name and stays valid
    because state identity is preserved across the rewrite.
    """
    workflow = _workflow_for_robustness(
        config.robustness,
        creative=config.creative,
        with_prep=config.with_prep,
        with_feedback=config.with_feedback,
    )
    edges, nodes = _edges_from_workflow(workflow)
    return Graph(nodes=nodes, edges=edges)


def successors(graph: Graph, state: str, condition: str | None = None) -> tuple[Edge, ...]:
    return graph.successors(state, condition)


_RECOVERY_POLICIES: frozenset[str] = frozenset({"recovery", "resume"})

# Probe configs (in priority order) used to derive the per-stage "active"
# source state from the realized graph. Together these cover every phase in
# the legacy `_BLOCKED_RECOVERY_STATES` / `_RESUME_ACTIVE_STATES` tables:
# - `full + with_prep=False + with_feedback=True` yields the canonical
#   linear chain initialized→planned→critiqued→…→reviewed→done (covering
#   plan/critique/gate/revise/finalize/execute/review/feedback);
# - `extreme + with_prep=True` yields the prep edge initialized→prepped.
_STAGE_PROBE_CONFIGS: tuple[RunTopologyConfig, ...] = (
    RunTopologyConfig(robustness="full", with_prep=False, with_feedback=True),
    RunTopologyConfig(robustness="extreme", with_prep=True, with_feedback=True),
)


def _stage_predecessor(stage: str, policy: str) -> str | None:
    if policy not in _RECOVERY_POLICIES:
        raise ValueError(
            f"unknown predecessors policy: {policy!r}; expected one of {sorted(_RECOVERY_POLICIES)}"
        )
    for cfg in _STAGE_PROBE_CONFIGS:
        graph = build_topology(cfg)
        for e in graph.edges:
            # Skip self-loops (e.g. planned→planned for replan) — the
            # canonical "active" source is a forward edge.
            if e.step == stage and e.src != e.dst:
                return e.src
    return None


def predecessors(
    graph_or_stage,  # type: ignore[no-untyped-def]
    state: str | None = None,
    condition: str | None = None,
    *,
    policy: str | None = None,
):
    """Two call shapes:

    * ``predecessors(graph, state, condition=None) -> tuple[Edge, ...]`` —
      the existing graph-query helper (used by parity tests / oracles).
    * ``predecessors(stage, *, policy='recovery'|'resume') -> str | None`` —
      the realized-graph projection that replaces the legacy
      ``_BLOCKED_RECOVERY_STATES`` / ``_RESUME_ACTIVE_STATES`` dict lookups
      in override.py and _core/workflow.py.
    """

    if policy is not None:
        if not isinstance(graph_or_stage, str):
            raise TypeError(
                "predecessors(..., policy=...) expects the stage name (a str)"
            )
        return _stage_predecessor(graph_or_stage, policy)
    if not isinstance(graph_or_stage, Graph) or state is None:
        raise TypeError(
            "predecessors(graph, state, condition=None) requires a Graph and a state"
        )
    return graph_or_stage.predecessors(state, condition)


def has_edge(
    graph: Graph,
    src: str,
    dst: str,
    *,
    condition: str | None = None,
    step: str | None = None,
) -> bool:
    return graph.has_edge(src, dst, condition=condition, step=step)


__all__ = [
    "CONDITIONS",
    "Edge",
    "Graph",
    "RunTopologyConfig",
    "build_topology",
    "successors",
    "predecessors",
    "has_edge",
]