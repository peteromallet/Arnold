"""T9 parity test: projection-based `workflow_next` / `workflow_transition`
/ `workflow_includes_step` must match the legacy fold across 20 configs ×
all states × 8 conditions.
"""

from __future__ import annotations

import itertools

import pytest

from megaplan._core.workflow import (
    _STEP_CONTEXT_STATES,
    _transition_matches,
    _workflow_for_robustness,
    workflow_includes_step,
    workflow_next,
    workflow_transition,
)
from megaplan._core.workflow_data import Transition

ROBUSTNESS_LEVELS = ("extreme", "thorough", "full", "light", "bare")
FLAG_COMBOS = (
    {"creative": False, "with_prep": False, "with_feedback": False},
    {"creative": True, "with_prep": False, "with_feedback": False},
    {"creative": False, "with_prep": True, "with_feedback": False},
    {"creative": False, "with_prep": False, "with_feedback": True},
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


def _state_for_condition(condition: str, current_state: str, robustness: str,
                          *, creative: bool, with_prep: bool, with_feedback: bool) -> dict:
    """Build a synthetic PlanState whose `_transition_matches` returns True
    for `condition` (and is otherwise deterministic).
    """
    gate: dict = {}
    if condition == "always":
        gate = {}
    elif condition == "gate_unset":
        gate = {"recommendation": None}
    elif condition == "gate_iterate":
        gate = {"recommendation": "ITERATE"}
    elif condition == "gate_escalate":
        gate = {"recommendation": "ESCALATE"}
    elif condition == "gate_tiebreaker":
        gate = {"recommendation": "TIEBREAKER"}
    elif condition == "gate_proceed_agent_availability_blocked":
        gate = {
            "recommendation": "PROCEED",
            "passed": False,
            "preflight_results": {"claude_available": False, "codex_available": True},
        }
    elif condition == "gate_proceed_blocked":
        gate = {"recommendation": "PROCEED", "passed": False, "preflight_results": {}}
    elif condition == "gate_proceed":
        gate = {"recommendation": "PROCEED", "passed": True}

    config = {"robustness": robustness, "with_prep": with_prep, "with_feedback": with_feedback}
    if creative:
        config["mode"] = "creative"
    return {"current_state": current_state, "config": config, "last_gate": gate}


def _legacy_next(workflow: dict, state: dict) -> list[str]:
    current = state["current_state"]
    out = [
        t.next_step
        for t in workflow.get(current, [])
        if _transition_matches(state, t.condition)
    ]
    if current in _STEP_CONTEXT_STATES:
        out.append("step")
    return out


def _legacy_transition(workflow: dict, state: dict, step: str):
    current = state["current_state"]
    for t in workflow.get(current, []):
        if t.next_step == step and _transition_matches(state, t.condition):
            return t
    return None


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
@pytest.mark.parametrize("flags", FLAG_COMBOS)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_workflow_next_parity(robustness, flags, condition):
    workflow = _workflow_for_robustness(robustness, **flags)
    for current in workflow.keys():
        state = _state_for_condition(condition, current, robustness, **flags)
        assert workflow_next(state) == _legacy_next(workflow, state), (
            f"mismatch at robustness={robustness} flags={flags} "
            f"state={current} condition={condition}"
        )


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
@pytest.mark.parametrize("flags", FLAG_COMBOS)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_workflow_transition_parity(robustness, flags, condition):
    workflow = _workflow_for_robustness(robustness, **flags)
    candidate_steps = {t.next_step for ts in workflow.values() for t in ts}
    for current in workflow.keys():
        state = _state_for_condition(condition, current, robustness, **flags)
        for step in candidate_steps:
            got = workflow_transition(state, step)
            expected = _legacy_transition(workflow, state, step)
            assert got == expected, (
                f"mismatch at robustness={robustness} flags={flags} "
                f"state={current} condition={condition} step={step}: "
                f"got={got} expected={expected}"
            )


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
@pytest.mark.parametrize("flags", FLAG_COMBOS)
def test_workflow_includes_step_parity(robustness, flags):
    # "step" always synthesized.
    assert workflow_includes_step(robustness, "step", with_prep=flags["with_prep"],
                                   with_feedback=flags["with_feedback"]) is True
    # Non-creative path is what the public API exposes
    # (workflow_includes_step doesn't take `creative`).
    workflow = _workflow_for_robustness(
        robustness,
        creative=False,
        with_prep=flags["with_prep"],
        with_feedback=flags["with_feedback"],
    )
    legacy_steps = {t.next_step for ts in workflow.values() for t in ts}
    for step in legacy_steps:
        assert workflow_includes_step(
            robustness, step,
            with_prep=flags["with_prep"],
            with_feedback=flags["with_feedback"],
        ) is True
    # A definitely-absent label
    assert workflow_includes_step(
        robustness, "definitely-not-a-real-step",
        with_prep=flags["with_prep"],
        with_feedback=flags["with_feedback"],
    ) is False


def test_step_context_states_synthetic_append():
    """Synthetic `"step"` append still fires for every state in
    `_STEP_CONTEXT_STATES` regardless of condition."""
    for current in _STEP_CONTEXT_STATES:
        state = {"current_state": current, "config": {"robustness": "extreme"},
                 "last_gate": {}}
        assert "step" in workflow_next(state)


def test_signatures_unchanged():
    """Lock the public signatures the rewire promised to preserve."""
    import inspect

    sig_next = inspect.signature(workflow_next)
    assert list(sig_next.parameters) == ["state"]

    sig_tr = inspect.signature(workflow_transition)
    assert list(sig_tr.parameters) == ["state", "step"]

    sig_inc = inspect.signature(workflow_includes_step)
    params = list(sig_inc.parameters.items())
    assert [n for n, _ in params] == ["robustness", "step", "with_prep", "with_feedback"]
    assert sig_inc.parameters["with_prep"].default is False
    assert sig_inc.parameters["with_feedback"].default is False
