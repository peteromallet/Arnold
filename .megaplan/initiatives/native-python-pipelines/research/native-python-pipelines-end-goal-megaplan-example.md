# End goal: the Megaplan pipeline as ordinary Python

This is what the main planning pipeline could look like at the very end of the native-Python migration, assuming a full native runtime (Option B).

```python
from __future__ import annotations

from dataclasses import dataclass

from arnold.pipeline.native import pipeline, phase, run_subpipeline


@dataclass
class Draft: ...
@dataclass
class Plan: ...
@dataclass
class Critique: ...
@dataclass
class Verdict: ...
@dataclass
class Revision: ...
@dataclass
class FinalPlan: ...
@dataclass
class ExecutionResult: ...
@dataclass
class ReviewResult: ...


@phase
async def prep(inputs: PlanningInputs) -> Draft:
    """Gather and validate inputs into a draft."""
    return _prepare_draft(inputs)


@phase
async def plan(draft: Draft) -> Plan:
    """Produce the initial plan."""
    return _generate_plan(draft)


@phase
async def critique_phase(plan: Plan, last_revision: Revision | None) -> Critique:
    """Critique the current plan."""
    return _critique(plan, last_revision)


@phase
async def gate(critique: Critique) -> Verdict:
    """Decide whether to proceed, revise, escalate, or call a tiebreaker.

    The runtime injects overrides before this phase body runs.
    """
    return _model_gate(critique)


@phase
async def revise_phase(critique: Critique) -> Revision:
    """Revise the plan based on the critique."""
    return _revise(critique)


@phase
async def finalize(plan: Plan, critique: Critique) -> FinalPlan:
    return _finalize(plan, critique)


@phase
async def execute(final_plan: FinalPlan) -> ExecutionResult:
    return _execute_plan(final_plan)


@phase
async def review(result: ExecutionResult) -> ReviewResult:
    return _review_result(result)


@pipeline("megaplan")
async def megaplan(inputs: PlanningInputs) -> ReviewResult:
    """End-to-end planning pipeline."""
    draft = await prep(inputs)
    plan = await plan(draft)

    revision: Revision | None = None
    while True:
        critique = await critique_phase(plan, revision)
        verdict = await gate(critique)

        if verdict.recommendation == "proceed":
            break

        if verdict.recommendation == "escalate":
            await _escalate(critique)
            raise PlanningEscalation(critique)

        if verdict.recommendation == "tiebreaker":
            tiebreaker_plan = await run_subpipeline(
                tiebreaker_pipeline,
                TiebreakerInputs(plan=plan, critique=critique),
            )
            plan = _merge_tiebreaker(plan, tiebreaker_plan)
            revision = None
            continue

        revision = await revise_phase(critique)
        plan = _apply_revision(plan, revision)

        if _loop_should_halt(plan, critique, revision):
            break

    final_plan = await finalize(plan, critique)
    execution_result = await execute(final_plan)
    return await review(execution_result)
```

## Why this is the end goal

- **It is just Python.** Variables, `while`, `if`, `break`, `continue`, function calls, exceptions.
- **No hand-written graph.** The structure emerges from the code.
- **Phases are ordinary async functions.** They are `@phase`-decorated only so the runtime knows which calls are checkpoint boundaries.
- **Subloops are ordinary function calls.** `run_subpipeline(tiebreaker_pipeline, ...)` runs another `@pipeline` function in its own checkpoint scope.
- **Overrides are invisible to the author.** The runtime intercepts `await gate(...)` and applies any active override before the model runs.
- **Contracts come from types.** `Draft`, `Plan`, `Critique`, etc. are dataclasses or Pydantic models whose schemas are registered with the runtime.

## What the runtime is doing

Every `await` of a `@phase` function is a checkpoint:

1. The runtime persists the current local-variable snapshot.
2. It records the phase call in the event journal.
3. It validates the typed handoff against the registered schema.
4. It runs the phase body.
5. It stores the result and resumes the pipeline.

If the process restarts, the runtime reloads the snapshot, fast-forwards to the last completed phase, and continues from the next `await`.

## What this is not

This is not the first step. To get here safely, the current plan proposes:

1. Build the bridge so native functions compile to the existing graph executor.
2. Convert real pipelines and prove parity.
3. Only then build the native runtime underneath and switch hot-path execution to it.

This file shows the destination, not the route.
