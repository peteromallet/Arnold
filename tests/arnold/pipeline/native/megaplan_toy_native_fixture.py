"""Native toy pipeline fixture mirroring the Megaplan graph-executor toy.

Mirrors the scenario in ``megaplan_toy_fixture.py`` using native decorators
(``@phase``, ``@decision``, ``@pipeline``) and :class:`MegaplanNativeRuntimeHooks`.

Covers:
* Catalog override — a decision stage with ``override_vocabulary`` whose
  ``__control_override__`` can be injected via ``on_step_start``.
* Guarded loop — a ``while`` construct that cycles a body phase until the
  guard returns falsy.
* Nested subpipeline simulation — a phase that simulates child pipeline
  execution and produces ``subloop:<name>:state`` and
  ``subloop:<name>:recommendation`` promotion keys.
* Completed child promotion — the subloop keys are merged into parent state.
* Child artifact persistence — artifacts are written under the plan dir.
* Suspension/resume — ``max_phases`` triggers suspension with resume cursor;
  a subsequent call with ``resume=True`` continues from the saved point.

Usage::

    from tests.arnold.pipeline.native.megaplan_toy_native_fixture import (
        get_megaplan_native_toy_program,
        run_megaplan_native_toy,
    )

    program = get_megaplan_native_toy_program()
    result = run_megaplan_native_toy(program, plan_dir="/tmp/toy")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline.native import (
    NativeExecutionResult,
    NativeProgram,
    compile_pipeline,
    decision,
    phase,
    pipeline,
    run_native_pipeline,
    loop_guard,
)
from arnold.pipelines.megaplan.native_hooks import MegaplanNativeRuntimeHooks
from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

# ═══════════════════════════════════════════════════════════════════════
# Module-level counter for the guarded loop
# ═══════════════════════════════════════════════════════════════════════

_loop_counter: dict[str, int] = {"count": 0}


def _reset_loop_counter() -> None:
    """Reset the loop counter between test runs."""
    _loop_counter["count"] = 0


# ═══════════════════════════════════════════════════════════════════════
# Native phases, decisions, and loop guard
# ═══════════════════════════════════════════════════════════════════════


@phase(name="setup")
def native_setup(ctx: dict) -> dict:
    """First phase — signals readiness and initialises counter."""
    _reset_loop_counter()
    return {"ready": True, "counter": 0}


@phase(name="override_target")
def native_override_target(ctx: dict) -> dict:
    """Phase on the override branch."""
    return {"branch": "override"}


@phase(name="normal_target")
def native_normal_target(ctx: dict) -> dict:
    """Phase on the normal (non-overridden) branch."""
    return {"branch": "normal"}


@phase(name="loop_body")
def native_loop_body(ctx: dict) -> dict:
    """Phase inside the guarded loop — increments a counter."""
    state = ctx.get("state", {})
    counter = state.get("counter", 0) + 1
    return {"counter": counter}


@phase(name="nested_subpipeline")
def native_nested_subpipeline(ctx: dict) -> dict:
    """Simulate a nested subpipeline — produces subloop promotion keys.

    Returns ``subloop:<name>:state`` and ``subloop:<name>:recommendation``
    so downstream consumers see the same shape as
    :meth:`MegaplanNativeRuntimeHooks.completed_subloop`.
    """
    name = "child"
    child_state = {"child_key": "child_value_a", "child_key2": "child_value_b"}
    return {
        f"subloop:{name}:state": child_state,
        f"subloop:{name}:recommendation": "force-proceed",
    }


@phase(name="cleanup")
def native_cleanup(ctx: dict) -> dict:
    """Final phase — marks pipeline complete."""
    return {"done": True}


@decision(name="override_decision", vocabulary=frozenset({"normal", "override"}))
def native_override_decision(ctx: dict) -> str:
    """Decision that checks for override in state metadata.

    Returns ``"override"`` when ``state.meta.overrides`` contains an
    entry whose ``action`` is one of ``abort``, ``force-proceed``, or
    ``replan``.  Returns ``"normal"`` otherwise.

    This mirrors :func:`megaplan_toy_fixture._override_decision` but uses
    a 2-way branch suitable for the native compiler's ``if/else``.
    """
    state = ctx.get("state", {})
    meta = state.get("meta", {})
    overrides = meta.get("overrides", [])
    if overrides:
        for entry in overrides:
            if isinstance(entry, dict):
                action = entry.get("action", "")
                if action in ("abort", "force-proceed", "replan"):
                    return "override"
    return "normal"


@decision(name="loop_guard", vocabulary=frozenset({"yes", "no"}))
def native_loop_guard(ctx: dict) -> str:
    """Loop guard — continue while counter < 3.

    Mirrors :func:`megaplan_toy_fixture._loop_guard`.
    """
    state = ctx.get("state", {})
    counter = state.get("counter", 0)
    return "yes" if counter < 3 else "no"


# ═══════════════════════════════════════════════════════════════════════
# Native pipeline definition
# ═══════════════════════════════════════════════════════════════════════


@pipeline(
    name="megaplan_native_toy",
    description="Megaplan-shaped native toy pipeline for parity testing",
)
def megaplan_native_toy_pipeline(ctx: dict) -> dict:
    """Native toy pipeline mirroring the graph-executor Megaplan toy.

    Structure::

        setup → override_decision → [override_target | normal_target]
              → while loop_guard → [loop_body → loop_guard | nested_subpipeline]
              → cleanup → halt
    """
    s = yield native_setup(ctx)
    if native_override_decision(ctx) == "override":
        s = yield native_override_target(ctx)
    else:
        s = yield native_normal_target(ctx)
    while native_loop_guard(ctx) == "yes":
        s = yield native_loop_body(ctx)
    s = yield native_nested_subpipeline(ctx)
    s = yield native_cleanup(ctx)
    return s


# ═══════════════════════════════════════════════════════════════════════
# Convenience: pre-compiled program
# ═══════════════════════════════════════════════════════════════════════


def get_megaplan_native_toy_program() -> NativeProgram:
    """Return the compiled :class:`NativeProgram` for the Megaplan native toy.

    Each call re-compiles from source so caller modifications to the
    counter or environment are reflected.
    """
    return compile_pipeline(megaplan_native_toy_pipeline)


# ═══════════════════════════════════════════════════════════════════════
# Runner: execute with MegaplanNativeRuntimeHooks
# ═══════════════════════════════════════════════════════════════════════


def run_megaplan_native_toy(
    program: NativeProgram | None = None,
    *,
    initial_state: dict[str, Any] | None = None,
    plan_dir: str | Path | None = None,
    max_phases: int | None = None,
    resume: bool = False,
    artifact_root: str | Path | None = None,
) -> NativeExecutionResult:
    """Run the Megaplan native toy with :class:`MegaplanNativeRuntimeHooks`.

    Args:
        program: Optional pre-compiled :class:`NativeProgram` (uses
            ``get_megaplan_native_toy_program()`` when ``None``).
        initial_state: Override the default initial state (default: ``{}``).
        plan_dir: Plan directory for state persistence, artifact writes,
            and override event emission (default: an auto-created temp dir).
        max_phases: Maximum number of phase instructions to execute
            before suspending (``None`` → no limit).
        resume: If ``True``, attempt to read a cursor from *artifact_root*
            and resume from the saved pc and state.
        artifact_root: Root directory for cursor persistence
            (default: same as *plan_dir*).

    Returns:
        :class:`NativeExecutionResult` with final state, completed stages,
        current pc, suspension status, and accumulated envelope.
    """
    if program is None:
        program = get_megaplan_native_toy_program()

    if plan_dir is None:
        import tempfile

        plan_dir = tempfile.mkdtemp(prefix="megaplan_native_toy_")

    plan_dir = Path(plan_dir)
    plan_dir.mkdir(parents=True, exist_ok=True)

    if initial_state is None:
        initial_state = {}

    if artifact_root is None:
        artifact_root = str(plan_dir)

    # Write initial state to plan_dir so on_stage_complete can merge against it
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps(initial_state, indent=2), encoding="utf-8")

    # Build the initial envelope — matches the graph reference pattern
    initial_envelope = RuntimeEnvelope(
        artifact_root=str(plan_dir),
        cross_cutting=RunEnvelope(taint="clean"),
    )

    hooks = MegaplanNativeRuntimeHooks(plan_dir=str(plan_dir))

    return run_native_pipeline(
        program,
        artifact_root=artifact_root,
        initial_state=initial_state,
        max_phases=max_phases,
        resume=resume,
        hooks=hooks,
        initial_envelope=initial_envelope,
    )


# ═══════════════════════════════════════════════════════════════════════
# Convenience: read final state from disk (matches graph reference)
# ═══════════════════════════════════════════════════════════════════════


def read_native_toy_state(plan_dir: str | Path) -> dict[str, Any]:
    """Read the final state from ``<plan_dir>/state.json``.

    Mirrors the graph reference's pattern of reading back state after
    a pipeline run completes.
    """
    state_path = Path(plan_dir) / "state.json"
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}
