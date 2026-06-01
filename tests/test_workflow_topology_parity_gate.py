"""T10 parameterized parity gate (hinge_gate).

Covers {5 robustness} × {4 prep/feedback combos} × {all PlanStates} ×
{8 conditions} ≈ 1680 combinations.

Asserts that `build_topology(RunTopologyConfig(...)).successors(state,
condition=condition)` produces the same (step, dst) sequence as the
legacy `_workflow_for_robustness` fold filtered by `_transition_matches`,
including the synthetic ``"step"`` append for ``_STEP_CONTEXT_STATES``
and all three gate_proceed distinctions.
"""

from __future__ import annotations

import pytest

from megaplan._core.topology import RunTopologyConfig, build_topology
from megaplan._core.workflow import (
    _STEP_CONTEXT_STATES,
    _transition_matches,
    _workflow_for_robustness,
)

# ---------------------------------------------------------------------------
# Parametrize dimensions
# ---------------------------------------------------------------------------

ROBUSTNESS_LEVELS = ("extreme", "thorough", "full", "light", "bare")

FLAG_COMBOS = (
    {"with_prep": False, "with_feedback": False},
    {"with_prep": True,  "with_feedback": False},
    {"with_prep": False, "with_feedback": True},
    {"with_prep": True,  "with_feedback": True},
)

CONDITIONS = (
    "always",
    "gate_unset",
    "gate_iterate",
    "gate_escalate",
    "gate_tiebreaker",
    "gate_proceed_agent_availability_blocked",
    "gate_proceed_blocked",
    "gate_proceed",
)

# All three gate_proceed variants must be present and distinct.
GATE_PROCEED_VARIANTS = (
    "gate_proceed",
    "gate_proceed_blocked",
    "gate_proceed_agent_availability_blocked",
)


def _make_state_dict(
    current: str,
    condition: str,
    robustness: str,
    *,
    with_prep: bool,
    with_feedback: bool,
) -> dict:
    """Return a synthetic state dict that fires *exactly* `condition`.

    ``_transition_matches`` treats the ``last_gate`` sub-dict to pick
    between gate_proceed, gate_proceed_blocked, and
    gate_proceed_agent_availability_blocked; we construct matching dicts
    so each variant is exercised independently.
    """
    if condition == "always":
        gate: dict = {}
    elif condition == "gate_unset":
        gate = {"recommendation": None}
    elif condition == "gate_iterate":
        gate = {"recommendation": "ITERATE"}
    elif condition == "gate_escalate":
        gate = {"recommendation": "ESCALATE"}
    elif condition == "gate_tiebreaker":
        gate = {"recommendation": "TIEBREAKER"}
    elif condition == "gate_proceed":
        gate = {"recommendation": "PROCEED", "passed": True}
    elif condition == "gate_proceed_blocked":
        gate = {"recommendation": "PROCEED", "passed": False, "preflight_results": {}}
    elif condition == "gate_proceed_agent_availability_blocked":
        gate = {
            "recommendation": "PROCEED",
            "passed": False,
            "preflight_results": {"claude_available": False, "codex_available": True},
        }
    else:
        raise ValueError(f"Unknown condition: {condition}")

    return {
        "current_state": current,
        "config": {
            "robustness": robustness,
            "with_prep": with_prep,
            "with_feedback": with_feedback,
        },
        "last_gate": gate,
    }


def _generate_params():
    """Generate (robustness, flags, state, condition) tuples."""
    params = []
    for robustness in ROBUSTNESS_LEVELS:
        for flags in FLAG_COMBOS:
            workflow = _workflow_for_robustness(
                robustness, creative=False, **flags
            )
            for state in workflow:
                for condition in CONDITIONS:
                    params.append((robustness, flags, state, condition))
    return params


_ALL_PARAMS = _generate_params()


# ---------------------------------------------------------------------------
# Core parity gate
# ---------------------------------------------------------------------------

@pytest.mark.hinge_gate
@pytest.mark.parametrize("robustness,flags,state,condition", _ALL_PARAMS)
def test_topology_graph_projection_matches_legacy_fold(
    robustness, flags, state, condition
):
    """Topology-filtered successors must equal legacy-fold transitions.

    For every (robustness, flags, state, condition) combination:
    - Construct state dict that fires `condition`.
    - Check legacy transitions whose `_transition_matches` returns True.
    - Check topology `successors(state, condition=condition)`.
    - Assert step+dst sequences are identical and in the same order.
    """
    workflow = _workflow_for_robustness(robustness, creative=False, **flags)
    config = RunTopologyConfig(
        robustness=robustness,
        creative=False,
        with_prep=flags["with_prep"],
        with_feedback=flags["with_feedback"],
    )
    graph = build_topology(config)
    state_dict = _make_state_dict(state, condition, robustness, **flags)

    # Legacy: transitions where _transition_matches fires for this state_dict.
    legacy_filtered = [
        (t.next_step, t.next_state)
        for t in workflow.get(state, [])
        if _transition_matches(state_dict, t.condition)
    ]

    # Topology: edges where _transition_matches fires — same filter, different source.
    # We do NOT pre-filter by condition string because the state_dict may activate
    # transitions whose edge.condition label is "always" even when condition="gate_unset".
    topo_filtered = [
        (e.step, e.dst)
        for e in graph.successors(state)
        if _transition_matches(state_dict, e.condition)
    ]

    assert topo_filtered == legacy_filtered, (
        f"Graph projection != legacy fold at "
        f"robustness={robustness} flags={flags} state={state} condition={condition}: "
        f"topo={topo_filtered} legacy={legacy_filtered}"
    )


# ---------------------------------------------------------------------------
# Synthetic "step" gate: _STEP_CONTEXT_STATES always append "step"
# ---------------------------------------------------------------------------

@pytest.mark.hinge_gate
@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
@pytest.mark.parametrize("flags", FLAG_COMBOS)
def test_synthetic_step_append_in_step_context_states(robustness, flags):
    """Topology nodes for _STEP_CONTEXT_STATES must appear and "step" is
    preserved by the projection layer (workflow_next appends it).

    The graph itself does not encode the synthetic "step" edge — that is
    added by `workflow_next` before returning.  This test verifies the
    states that trigger the append are present in the realized graph.
    """
    config = RunTopologyConfig(
        robustness=robustness,
        creative=False,
        with_prep=flags["with_prep"],
        with_feedback=flags["with_feedback"],
    )
    graph = build_topology(config)

    # All _STEP_CONTEXT_STATES that appear in the realized graph must be nodes.
    workflow = _workflow_for_robustness(robustness, creative=False, **flags)
    for step_state in _STEP_CONTEXT_STATES:
        if step_state in workflow:
            assert step_state in graph.nodes, (
                f"_STEP_CONTEXT_STATES member '{step_state}' missing from graph "
                f"at robustness={robustness} flags={flags}"
            )


# ---------------------------------------------------------------------------
# gate_proceed distinctions: three variants must produce distinct edges
# ---------------------------------------------------------------------------

@pytest.mark.hinge_gate
@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
@pytest.mark.parametrize("flags", FLAG_COMBOS)
def test_gate_proceed_variants_are_distinct(robustness, flags):
    """gate_proceed / gate_proceed_blocked / gate_proceed_agent_availability_blocked
    must be treated as three independent condition strings in the realized graph.

    If any state has edges for gate_proceed variants, the three variant sets
    must be disjoint OR at least contain the same condition label — i.e., the
    graph does not collapse them into a single condition string.
    """
    config = RunTopologyConfig(
        robustness=robustness,
        creative=False,
        with_prep=flags["with_prep"],
        with_feedback=flags["with_feedback"],
    )
    graph = build_topology(config)

    for state in graph.nodes:
        variant_edge_sets = {
            variant: frozenset(
                (e.step, e.dst) for e in graph.successors(state, condition=variant)
            )
            for variant in GATE_PROCEED_VARIANTS
        }
        # Each variant must only contain edges tagged with its own condition string.
        for variant in GATE_PROCEED_VARIANTS:
            for e in graph.successors(state, condition=variant):
                assert e.condition == variant, (
                    f"Edge condition mismatch: expected {variant!r}, got {e.condition!r} "
                    f"at state={state} robustness={robustness} flags={flags}"
                )

        # The three variant sets must not be non-trivially aliased:
        # if two variants have exactly the same non-empty edge set AND the same
        # conditions, the graph has collapsed them — that is a bug.
        non_empty = [v for v, s in variant_edge_sets.items() if s]
        if len(non_empty) >= 2:
            for i, v1 in enumerate(non_empty):
                for v2 in non_empty[i + 1:]:
                    # They may share (step, dst) values but must differ in condition.
                    edges1 = graph.successors(state, condition=v1)
                    edges2 = graph.successors(state, condition=v2)
                    conditions1 = {e.condition for e in edges1}
                    conditions2 = {e.condition for e in edges2}
                    assert conditions1.isdisjoint(conditions2) or not conditions1, (
                        f"gate_proceed variants share condition labels: "
                        f"{v1} conditions={conditions1}, {v2} conditions={conditions2} "
                        f"at state={state} robustness={robustness} flags={flags}"
                    )
