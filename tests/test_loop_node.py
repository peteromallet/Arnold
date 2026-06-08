"""Tests for megaplan._pipeline.loop_node.LoopNode (T16).

Locks the four invariants of the explicit loop-control primitive:
    1. predicate is consulted (and its halt verdict is honored);
    2. cap fires at iteration >= max_iterations regardless of predicate;
    3. teardown runs on every exit path (normal halt, cap, exception,
       budget-exhausted);
    4. iterate_until's legacy callable+Stage surface and SubloopStep
       are still usable shims.
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan._pipeline.loop_node import LoopNode
from arnold.pipelines.megaplan._pipeline.pattern_stops import LoopState


def _ls(iteration: int = 0, state=None, last=None) -> LoopState:
    return LoopState(state=state or {}, last_fanout_results=last, iteration=iteration)


# ---- Construction invariants ----------------------------------------------


def test_max_iterations_is_required_positive() -> None:
    with pytest.raises(ValueError):
        LoopNode(predicate=lambda _: False, max_iterations=0)
    with pytest.raises(ValueError):
        LoopNode(predicate=lambda _: False, max_iterations=-1)


# ---- Predicate consultation ----------------------------------------------


def test_predicate_consulted_each_call_and_halts_when_true() -> None:
    seen: list[int] = []

    def pred(ls) -> bool:
        seen.append(ls.iteration)
        return ls.iteration == 2

    node = LoopNode(predicate=pred, max_iterations=10)
    assert node.should_halt(_ls(iteration=0)) is False
    assert node.should_halt(_ls(iteration=1)) is False
    assert node.should_halt(_ls(iteration=2)) is True
    assert seen == [0, 1, 2]
    assert node.last_halt_reason == "predicate"


def test_predicate_sees_budget_attr_on_extended_loopstate() -> None:
    captured: dict[str, object] = {}

    def pred(ls) -> bool:
        captured["budget"] = ls.budget
        captured["state"] = ls.state
        captured["last"] = ls.last_fanout_results
        captured["iter"] = ls.iteration
        return False

    probe = lambda: False
    node = LoopNode(predicate=pred, max_iterations=5, budget=probe)
    node.should_halt(_ls(iteration=1, state={"k": 1}, last=["a"]))
    assert captured == {"budget": probe, "state": {"k": 1}, "last": ["a"], "iter": 1}


# ---- Cap ----------------------------------------------


def test_cap_fires_regardless_of_predicate() -> None:
    pred_calls = 0

    def never(_ls) -> bool:
        nonlocal pred_calls
        pred_calls += 1
        return False

    node = LoopNode(predicate=never, max_iterations=3)
    assert node.should_halt(_ls(iteration=2)) is False
    assert node.should_halt(_ls(iteration=3)) is True
    assert node.last_halt_reason == "cap"
    # predicate not consulted on cap-hit iteration.
    assert pred_calls == 1


# ---- Budget ----------------------------------------------


def test_budget_halt_precedes_predicate() -> None:
    pred_calls = 0

    def pred(_ls) -> bool:
        nonlocal pred_calls
        pred_calls += 1
        return False

    flag = {"exhausted": False}
    node = LoopNode(
        predicate=pred,
        max_iterations=10,
        budget=lambda: flag["exhausted"],
    )
    assert node.should_halt(_ls(iteration=1)) is False
    assert pred_calls == 1

    flag["exhausted"] = True
    assert node.should_halt(_ls(iteration=2)) is True
    assert node.last_halt_reason == "budget"
    # Budget short-circuits before predicate is consulted.
    assert pred_calls == 1


# ---- Teardown on every exit path ----------------------------------------------


def test_teardown_on_normal_halt() -> None:
    torn: list[str] = []
    node = LoopNode(
        predicate=lambda ls: ls.iteration >= 1,
        max_iterations=10,
        teardown=lambda: torn.append("td"),
    )
    with node as n:
        assert n.should_halt(_ls(iteration=0)) is False
        assert n.should_halt(_ls(iteration=1)) is True
    assert torn == ["td"]


def test_teardown_on_cap() -> None:
    torn: list[str] = []
    node = LoopNode(
        predicate=lambda _ls: False,
        max_iterations=2,
        teardown=lambda: torn.append("td"),
    )
    with node as n:
        assert n.should_halt(_ls(iteration=2)) is True
        assert n.last_halt_reason == "cap"
    assert torn == ["td"]


def test_teardown_on_exception_propagates() -> None:
    torn: list[str] = []
    node = LoopNode(
        predicate=lambda _ls: False,
        max_iterations=10,
        teardown=lambda: torn.append("td"),
    )
    with pytest.raises(RuntimeError, match="boom"):
        with node:
            raise RuntimeError("boom")
    assert torn == ["td"]


def test_teardown_on_budget_exhaustion() -> None:
    torn: list[str] = []
    flag = {"x": True}
    node = LoopNode(
        predicate=lambda _ls: False,
        max_iterations=10,
        budget=lambda: flag["x"],
        teardown=lambda: torn.append("td"),
    )
    with node as n:
        assert n.should_halt(_ls(iteration=0)) is True
        assert n.last_halt_reason == "budget"
    assert torn == ["td"]


def test_teardown_idempotent() -> None:
    torn: list[str] = []
    node = LoopNode(
        predicate=lambda _ls: True,
        max_iterations=5,
        teardown=lambda: torn.append("td"),
    )
    node.run_teardown()
    node.run_teardown()
    with node:
        pass
    assert torn == ["td"]


def test_no_teardown_callable_is_safe() -> None:
    node = LoopNode(predicate=lambda _ls: False, max_iterations=3)
    with node:
        pass
    node.run_teardown()  # no-op, no exception.


# ---- Shims: iterate_until + SubloopStep still callable ----


def test_iterate_until_constructs_loopnode_under_the_hood() -> None:
    from arnold.pipelines.megaplan._pipeline.pattern_topology import iterate_until
    from arnold.pipelines.megaplan._pipeline.types import Edge, Stage, Step, StepContext, StepResult
    from dataclasses import dataclass, field

    @dataclass(frozen=True)
    class _NoOp:
        name: str = "x"
        kind: str = "step"
        prompt_key: str | None = None
        slot: str | None = None
        produces: tuple = field(default_factory=tuple)
        consumes: tuple = field(default_factory=tuple)

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(outputs={}, next="iterate")

    inner = Stage(name="x", step=_NoOp(), edges=(Edge(label="halt", target="halt"),))
    wrapped = iterate_until(inner, max_iterations=4)
    assert wrapped.loop_condition is not None
    # Default predicate => only the cap fires.
    assert wrapped.loop_condition(_ls(iteration=3)) is False
    assert wrapped.loop_condition(_ls(iteration=4)) is True
    # Self-loop + halt edges appended.
    labels = [e.label for e in wrapped.edges]
    assert "iterate" in labels and "halt" in labels


def test_iterate_until_custom_condition_still_works_as_callable() -> None:
    from arnold.pipelines.megaplan._pipeline.pattern_topology import iterate_until
    from arnold.pipelines.megaplan._pipeline.types import Edge, Stage, StepContext, StepResult
    from dataclasses import dataclass, field

    @dataclass(frozen=True)
    class _NoOp:
        name: str = "x"
        kind: str = "step"
        prompt_key: str | None = None
        slot: str | None = None
        produces: tuple = field(default_factory=tuple)
        consumes: tuple = field(default_factory=tuple)

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(outputs={}, next="iterate")

    cond = lambda ls: ls.state.get("done") is True
    inner = Stage(name="x", step=_NoOp(), edges=(Edge(label="halt", target="halt"),))
    wrapped = iterate_until(inner, condition=cond, max_iterations=8)
    assert wrapped.loop_condition(_ls(iteration=1, state={"done": False})) is False
    assert wrapped.loop_condition(_ls(iteration=1, state={"done": True})) is True


def test_subloopstep_shim_still_importable_and_constructible() -> None:
    from arnold.pipelines.megaplan._pipeline.subloop import SubloopStep

    step = SubloopStep(name="sub")
    # SubloopStep is a frozen dataclass; smoke-check that the surface is intact.
    assert step.name == "sub"
    assert step.kind == "subloop"
