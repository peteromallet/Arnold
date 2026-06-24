"""Reusable parity fixtures for native pipeline tests.

Provides a toy native pipeline covering:
* Sequential phases (setup, cleanup)
* Typed producer/consumer (producer → consumer via Port/PortRef)
* Decision branch (branch → left_path / right_path)
* Guarded loop (should_loop → body, 2 iterations)
* Forced resume support (via max_phases suspension)

Plus a matching hand-built reference graph using
``arnold.pipeline.types.Pipeline`` / ``Stage`` / ``Edge``.

All fixtures are assertion-free — they construct data only.
Consumers import the fixtures and run their own assertions.
"""

from __future__ import annotations

from typing import Any, Callable

from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    phase,
    pipeline,
)
from arnold.pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)

# ═══════════════════════════════════════════════════════════════════════
# Shared Port declarations for typed producer/consumer
# ═══════════════════════════════════════════════════════════════════════

_DATA_PORT = Port(name="data", content_type="text/plain")
_DATA_PORT_REF = PortRef(port_name="data", content_type="text/plain")

# ═══════════════════════════════════════════════════════════════════════
# Counter used by the guarded loop — module-level to survive re-compiles
# ═══════════════════════════════════════════════════════════════════════

_loop_counter: dict[str, int] = {"count": 0}


def _reset_loop_counter() -> None:
    """Reset the loop counter between test runs."""
    _loop_counter["count"] = 0


# ═══════════════════════════════════════════════════════════════════════
# Toy native pipeline phases, decisions, and the pipeline itself
# ═══════════════════════════════════════════════════════════════════════


@phase(name="setup")
def setup(ctx: dict) -> dict:
    """First phase — signals readiness."""
    return {"ready": True}


@phase(name="producer", produces=(_DATA_PORT,))
def producer(ctx: dict) -> dict:
    """Typed producer phase — emits a ``data`` port."""
    return {"data": "hello"}


@phase(name="consumer", consumes=(_DATA_PORT_REF,))
def consumer(ctx: dict) -> dict:
    """Typed consumer phase — reads the ``data`` port from state."""
    received: str = ""
    state = ctx.get("state", {})
    if isinstance(state, dict):
        received = state.get("data", "")
    # Also check inputs dict (matching graph executor context shape)
    inputs = ctx.get("inputs", {})
    if isinstance(inputs, dict) and not received:
        received = inputs.get("data", "")
    return {"consumed": received}


@phase(name="left_path")
def left_path(ctx: dict) -> dict:
    """Phase on the left branch of the decision."""
    return {"path": "left"}


@phase(name="right_path")
def right_path(ctx: dict) -> dict:
    """Phase on the right branch of the decision."""
    return {"path": "right"}


@decision(name="branch", vocabulary={"left", "right"})
def branch(ctx: dict) -> str:
    """Decision that picks a branch path."""
    return "right"


@phase(name="body")
def loop_body(ctx: dict) -> dict:
    """Phase inside the guarded loop — increments a counter."""
    _loop_counter["count"] += 1
    return {"count": _loop_counter["count"]}


@decision(name="should_loop", vocabulary={"yes", "no"})
def should_loop(ctx: dict) -> str:
    """Guard decision — continue looping while count < 2."""
    current = _loop_counter["count"]
    return "yes" if current < 2 else "no"


@phase(name="cleanup")
def cleanup(ctx: dict) -> dict:
    """Final phase — marks pipeline complete."""
    return {"done": True}


@pipeline(name="toy_pipeline", description="Toy native pipeline for parity testing")
def toy_pipeline_func(ctx: dict) -> dict:
    """Toy native pipeline covering sequential phases, typed handoff,
    decision branching, guarded loop, and forced resume.

    Structure:
        setup → producer → consumer → [branch: left_path | right_path]
        → while should_loop → body → cleanup
    """
    s = yield setup(ctx)
    s = yield producer(ctx)
    s = yield consumer(ctx)
    if branch(ctx) == "left":
        s = yield left_path(ctx)
    else:
        s = yield right_path(ctx)
    while should_loop(ctx) == "yes":
        s = yield loop_body(ctx)
    s = yield cleanup(ctx)
    return s


# ── convenience: pre-compiled program ─────────────────────────────────

def get_toy_program():
    """Return the compiled NativeProgram for the toy pipeline.

    Each call re-compiles from source so caller modifications to the
    counter or environment are reflected.
    """
    return compile_pipeline(toy_pipeline_func)


# ═══════════════════════════════════════════════════════════════════════
# Simple step adapters for the hand-built reference graph
# ═══════════════════════════════════════════════════════════════════════


class _FixturePhaseStep:
    """Minimal Step-compatible adapter wrapping a native-phase callable.

    Mirrors :class:`arnold.pipeline.native.graph_projection._NativePhaseStep`
    but is self-contained in the fixtures module.
    """

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        produces: tuple[Port, ...] = (),
        consumes: tuple[PortRef, ...] = (),
    ) -> None:
        self.name = name
        self.func = func
        self.kind = "native_phase"
        self.produces: tuple[Port, ...] = produces
        self.consumes: tuple[PortRef, ...] = consumes

    def run(self, ctx: StepContext) -> StepResult:
        result = self.func(ctx)
        if isinstance(result, dict):
            return StepResult(outputs=result, next="halt")
        if isinstance(result, StepResult):
            return result
        return StepResult(outputs={"value": result}, next="halt")


class _FixtureDecisionStep:
    """Minimal Step-compatible adapter wrapping a native-decision callable.

    Mirrors :class:`arnold.pipeline.native.graph_projection._NativeDecisionStep`
    but is self-contained in the fixtures module.
    """

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        decision_vocabulary: frozenset[str] | None = None,
        decision_routes: dict[str, str | None] | None = None,
    ) -> None:
        self.name = name
        self.func = func
        self.kind = "native_decision"
        self.produces: tuple[Port, ...] = ()
        self.consumes: tuple[PortRef, ...] = ()
        self.decision_vocabulary: frozenset[str] = (
            decision_vocabulary if decision_vocabulary is not None else frozenset()
        )
        self.decision_routes: dict[str, str | None] = (
            dict(decision_routes) if decision_routes is not None else {}
        )

    def run(self, ctx: StepContext) -> StepResult:
        result = self.func(ctx)
        next_label = str(result) if result else "__falsy__"
        return StepResult(next=next_label)


# ═══════════════════════════════════════════════════════════════════════
# Hand-built reference graph (matching the toy native pipeline)
# ═══════════════════════════════════════════════════════════════════════

# Stage names use a consistent prefix (matching native runtime convention)
_PREFIX = "toy_pipeline"


def _stage_name(name: str) -> str:
    """Return a stage name matching the native runtime convention."""
    return f"{_PREFIX}__{name}"


def get_reference_graph() -> Pipeline:
    """Return a hand-built :class:`Pipeline` matching the toy native pipeline.

    Builds stages manually with the same structure as
    ``project_graph(compile_pipeline(toy_pipeline_func))``.
    Returns a fully-constructed Pipeline that validates cleanly.
    """
    # ── Helper: build an Edge ──────────────────────────────────────
    _E = Edge  # short alias

    # ── Stage definitions (in pipeline order) ──────────────────────

    setup_stage = Stage(
        name=_stage_name("setup"),
        step=_FixturePhaseStep(name=_stage_name("setup"), func=setup),
        edges=(_E(label=_stage_name("producer"), target=_stage_name("producer")),),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    producer_stage = Stage(
        name=_stage_name("producer"),
        step=_FixturePhaseStep(
            name=_stage_name("producer"),
            func=producer,
            produces=(_DATA_PORT,),
        ),
        edges=(_E(label=_stage_name("consumer"), target=_stage_name("consumer")),),
        produces=(_DATA_PORT,),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    consumer_stage = Stage(
        name=_stage_name("consumer"),
        step=_FixturePhaseStep(
            name=_stage_name("consumer"),
            func=consumer,
            consumes=(_DATA_PORT_REF,),
        ),
        edges=(_E(label=_stage_name("branch"), target=_stage_name("branch")),),
        consumes=(_DATA_PORT_REF,),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    branch_stage = Stage(
        name=_stage_name("branch"),
        step=_FixtureDecisionStep(
            name=_stage_name("branch"),
            func=branch,
            decision_vocabulary=frozenset({"left", "right"}),
            decision_routes={"left": "left", "right": "right"},
        ),
        edges=(
            _E(label="left", target=_stage_name("left_path")),
            _E(label="right", target=_stage_name("right_path")),
        ),
        loop_condition=None,
        decision_vocabulary=frozenset({"left", "right"}),
        override_vocabulary=frozenset(),
        decision_routes={"left": "left", "right": "right"},
    )

    left_path_stage = Stage(
        name=_stage_name("left_path"),
        step=_FixturePhaseStep(name=_stage_name("left_path"), func=left_path),
        edges=(_E(label=_stage_name("should_loop"), target=_stage_name("should_loop")),),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    right_path_stage = Stage(
        name=_stage_name("right_path"),
        step=_FixturePhaseStep(name=_stage_name("right_path"), func=right_path),
        edges=(_E(label=_stage_name("should_loop"), target=_stage_name("should_loop")),),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    # Guard/loop: should_loop is a decision whose loop_condition is set
    should_loop_stage = Stage(
        name=_stage_name("should_loop"),
        step=_FixtureDecisionStep(
            name=_stage_name("should_loop"),
            func=should_loop,
            decision_vocabulary=frozenset({"yes", "no"}),
            decision_routes={"yes": "yes", "no": "no"},
        ),
        edges=(
            _E(label="yes", target=_stage_name("body")),
            _E(label="no", target=_stage_name("cleanup")),
        ),
        loop_condition=should_loop,  # marks this as a loop guard
        decision_vocabulary=frozenset({"yes", "no"}),
        override_vocabulary=frozenset(),
        decision_routes={"yes": "yes", "no": "no"},
    )

    body_stage = Stage(
        name=_stage_name("body"),
        step=_FixturePhaseStep(name=_stage_name("body"), func=loop_body),
        # Loop body jumps back to the guard for re-evaluation
        edges=(_E(label=_stage_name("should_loop"), target=_stage_name("should_loop")),),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    cleanup_stage = Stage(
        name=_stage_name("cleanup"),
        step=_FixturePhaseStep(name=_stage_name("cleanup"), func=cleanup),
        edges=(_E(label="halt", target="halt"),),
        loop_condition=None,
        decision_vocabulary=frozenset(),
        override_vocabulary=frozenset(),
        decision_routes={},
    )

    # ── Assemble stages dict ───────────────────────────────────────

    stages: dict[str, Stage] = {
        setup_stage.name: setup_stage,
        producer_stage.name: producer_stage,
        consumer_stage.name: consumer_stage,
        branch_stage.name: branch_stage,
        left_path_stage.name: left_path_stage,
        right_path_stage.name: right_path_stage,
        should_loop_stage.name: should_loop_stage,
        body_stage.name: body_stage,
        cleanup_stage.name: cleanup_stage,
    }

    # ── Derive binding map for typed ports ─────────────────────────

    edge_pairs: list[tuple[str, str]] = []
    for src_name, stage in stages.items():
        for edge in stage.edges:
            if edge.target != "halt" and edge.target in stages:
                edge_pairs.append((src_name, edge.target))

    from arnold.pipeline.declaration_lowering import derive_binding_map

    binding_map = derive_binding_map(stages, edge_pairs)

    return Pipeline(
        stages=stages,
        entry=_stage_name("setup"),
        binding_map=binding_map,
    )
