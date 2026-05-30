"""Parity tests for `build_topology` vs `_workflow_for_robustness`.

The realized-graph (`megaplan._core.topology`) must reproduce the legacy
fold's edge set across all 20 (robustness × flag) combos. For every
config, `successors(state)` must equal the legacy fold's list at that
state (same edge data, same order — the order encodes gate priority).
"""

from __future__ import annotations

import itertools

import pytest

from megaplan._core.topology import (
    CONDITIONS,
    Edge,
    Graph,
    RunTopologyConfig,
    build_topology,
    has_edge,
    predecessors,
    successors,
)
from megaplan._core.workflow import _workflow_for_robustness
from megaplan._core.workflow_data import Transition

ROBUSTNESS_LEVELS = ("extreme", "thorough", "full", "light", "bare")
FLAG_COMBOS = (
    {"creative": False, "with_prep": False, "with_feedback": False},
    {"creative": False, "with_prep": True, "with_feedback": False},
    {"creative": False, "with_prep": False, "with_feedback": True},
    {"creative": True, "with_prep": False, "with_feedback": False},
)


def _all_configs() -> list[RunTopologyConfig]:
    configs = []
    for r, flags in itertools.product(ROBUSTNESS_LEVELS, FLAG_COMBOS):
        configs.append(RunTopologyConfig(robustness=r, **flags))
    return configs


def test_config_matrix_is_20() -> None:
    assert len(_all_configs()) == 20


def test_conditions_set_has_8_predicates() -> None:
    # Pins the 8-predicate contract from the executor note.
    assert len(CONDITIONS) == 8
    expected = {
        "always",
        "gate_unset",
        "gate_iterate",
        "gate_escalate",
        "gate_tiebreaker",
        "gate_proceed_agent_availability_blocked",
        "gate_proceed_blocked",
        "gate_proceed",
    }
    assert CONDITIONS == expected


@pytest.mark.parametrize("config", _all_configs(), ids=lambda c: f"{c.robustness}-cr{int(c.creative)}-prep{int(c.with_prep)}-fb{int(c.with_feedback)}")
def test_successors_match_legacy_fold(config: RunTopologyConfig) -> None:
    graph = build_topology(config)
    workflow = _workflow_for_robustness(
        config.robustness,
        creative=config.creative,
        with_prep=config.with_prep,
        with_feedback=config.with_feedback,
    )
    for state, transitions in workflow.items():
        succ = graph.successors(state)
        assert len(succ) == len(transitions), f"{config}@{state} edge count"
        for edge, t in zip(succ, transitions):
            assert isinstance(edge, Edge)
            assert edge.src == state
            assert edge.dst == t.next_state
            assert edge.step == t.next_step
            assert edge.condition == t.condition


@pytest.mark.parametrize("config", _all_configs())
def test_nodes_cover_workflow_states(config: RunTopologyConfig) -> None:
    graph = build_topology(config)
    workflow = _workflow_for_robustness(
        config.robustness,
        creative=config.creative,
        with_prep=config.with_prep,
        with_feedback=config.with_feedback,
    )
    for state, transitions in workflow.items():
        assert state in graph.nodes
        for t in transitions:
            assert t.next_state in graph.nodes


@pytest.mark.parametrize("config", _all_configs())
def test_predecessors_match_reverse_legacy(config: RunTopologyConfig) -> None:
    graph = build_topology(config)
    workflow = _workflow_for_robustness(
        config.robustness,
        creative=config.creative,
        with_prep=config.with_prep,
        with_feedback=config.with_feedback,
    )
    # Build legacy reverse adjacency for parity.
    expected: dict[str, list[Transition]] = {}
    for src, transitions in workflow.items():
        for t in transitions:
            expected.setdefault(t.next_state, []).append(
                Transition(next_step=t.next_step, next_state=src, condition=t.condition)
            )
    for state in graph.nodes:
        preds = graph.predecessors(state)
        expected_preds = expected.get(state, [])
        assert len(preds) == len(expected_preds), f"{config}@{state} pred count"
        # The legacy walk order is deterministic (dict insertion order).
        for edge, exp in zip(preds, expected_preds):
            assert edge.dst == state
            assert edge.src == exp.next_state  # `next_state` here is reversed src
            assert edge.step == exp.next_step
            assert edge.condition == exp.condition


def test_successors_condition_filter() -> None:
    graph = build_topology(RunTopologyConfig(robustness="extreme"))
    # STATE_CRITIQUED has all 6 gate conditions.
    from megaplan.types import STATE_CRITIQUED

    gate_proceed_edges = graph.successors(STATE_CRITIQUED, condition="gate_proceed")
    assert len(gate_proceed_edges) == 1
    assert gate_proceed_edges[0].step == "gate"


def test_has_edge_step_and_condition_filter() -> None:
    graph = build_topology(RunTopologyConfig(robustness="extreme"))
    from megaplan.types import STATE_CRITIQUED, STATE_GATED

    assert has_edge(graph, STATE_CRITIQUED, STATE_GATED, condition="gate_proceed")
    assert has_edge(graph, STATE_CRITIQUED, STATE_GATED, step="gate")
    assert not has_edge(graph, STATE_CRITIQUED, STATE_GATED, condition="gate_iterate")


def test_module_level_helpers_match_method_calls() -> None:
    graph = build_topology(RunTopologyConfig(robustness="extreme"))
    from megaplan.types import STATE_PLANNED

    assert successors(graph, STATE_PLANNED) == graph.successors(STATE_PLANNED)
    assert predecessors(graph, STATE_PLANNED) == graph.predecessors(STATE_PLANNED)


def test_re_invocable_same_config_gives_equal_graph() -> None:
    cfg = RunTopologyConfig(robustness="thorough", with_prep=True)
    g1 = build_topology(cfg)
    g2 = build_topology(cfg)
    assert g1 == g2


def test_re_invocable_different_robustness_gives_different_graph() -> None:
    g_full = build_topology(RunTopologyConfig(robustness="full"))
    g_bare = build_topology(RunTopologyConfig(robustness="bare"))
    assert g_full != g_bare


def test_graph_is_frozen() -> None:
    graph = build_topology(RunTopologyConfig())
    with pytest.raises((AttributeError, TypeError, Exception)):
        graph.nodes = frozenset()  # type: ignore[misc]


def test_every_edge_condition_is_in_canonical_set() -> None:
    for config in _all_configs():
        graph = build_topology(config)
        for e in graph.edges:
            assert e.condition in CONDITIONS, f"{config} edge {e} has unknown condition"
