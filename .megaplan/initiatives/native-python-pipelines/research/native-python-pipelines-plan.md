# Native Python expression of planning pipelines — integration & migration plan

## Source

Ticket: `.megaplan/tickets/01KVAT54FGFCFKP0G6JFG78RP0-native-python-expression-of-planning-pipelines.md`

## Goal

Add a native-Python **authoring layer** for Arnold pipelines. The existing graph executor continues to run the show; the native layer is authoring sugar that compiles to the existing `Pipeline` graph. This migration must not lose runtime guarantees:

- typed contracts / handoff validation
- checkpoint / resume
- override injection before decision phases
- subloops and nested pipelines
- artifact + state persistence
- graph introspection for `arnold pipelines check/list/describe` and observability tools

## Current state

After the directory-unification work, every runnable pipeline lives as a top-level package under `arnold/pipelines/`. There are two existing authoring planes:

1. **Neutral graph plane** — `arnold.pipeline.builder.PipelineBuilder`, `Stage`, `Port`, `Edge`. Used by `vibecomfy_executor` (and converted to Megaplan types at build time).
2. **Megaplan graph plane** — `arnold.pipelines.megaplan._pipeline.builder.PipelineBuilder`, `AgentStep`, `PanelReviewerStep`, `HumanDecisionStep`, pattern helpers. Used by `megaplan`, `creative`, `doc`, `epic_blitz`, `writing_panel_strict`, etc.

What does **not** exist yet is a decorator-based native-function authoring plane that compiles into either graph builder while still feeding the existing CLI executor unchanged.

## Proposed authoring shape

```python
from arnold.pipeline.native import pipeline, phase, decision, PhaseContext

@pipeline("my-pipeline", description="...")
def run_my_pipeline(ctx: PhaseContext):
    draft = ctx.inputs["draft"]

    prep = yield from phase("prep", handle_prep, ctx, draft)
    plan = yield from phase("plan", handle_plan, ctx, prep)

    while not loop_should_halt(ctx):
        critique = yield from phase("critique", handle_critique, ctx, plan, revise)
        verdict = yield from decision("gate", handle_gate, ctx, critique)

        if verdict == "proceed":
            break
        if verdict == "escalate":
            ...
        if verdict == "tiebreaker":
            ...

        revise = yield from phase("revise", handle_revise, ctx, critique)

    finalize = yield from phase("finalize", ctx, plan, critique)
    execute  = yield from phase("execute", ctx, finalize)
    review   = yield from phase("review", ctx, execute)
```

Decorators capture `consumes` / `produces` / `branches` metadata; control flow stays ordinary Python. At build time the bridge lowers this into a normal `Pipeline` graph; at run time the existing executor walks it.

## High-level migration path

### Phase 1 — Decorators + bridge + tests (no existing pipeline changes)

Create `arnold.pipeline.native` (or equivalent) containing:

- `@pipeline`, `@phase`, `@decision` decorators.
- `PhaseContext` carrying `plan_dir`, `profile`, `iteration`, typed payloads, and inputs.
- A **graph bridge**: `native_to_pipeline(native_fn)` that derives `Stage`/`Edge` objects from decorator metadata (+ AST where needed) and returns a normal `Pipeline`. The bridge output must be assertable against a hand-built reference graph.
- An **AST-to-graph verifier** that, for every supported native construct, compares the bridge output to a reference graph so drift is caught in CI.

Deliverable: a new module with tests, including:
- a test-only native pipeline;
- a test that the bridge graph matches a hand-built reference graph;
- a synthetic run test that passes the bridge graph through the **existing** executor and proves stage sequence + state shape are correct.

No real pipeline behavior changes.

### Phase 2 — Pilot on `vibecomfy_executor`

Convert `arnold/pipelines/vibecomfy_executor/pipelines.py` to the native shape:

- Rewrite `build_pipeline()` as a `@pipeline` function.
- Keep the existing step classes, adapting them to accept `PhaseContext` and return typed payloads.
- Continue returning a Megaplan-compatible `Pipeline` via the bridge so the CLI is unaffected.
- Validate: `arnold pipelines check vibecomfy-executor` passes; existing tests pass.

Deliverable: `vibecomfy_executor` becomes the canonical reference for native authoring on the neutral executor.

### Phase 3 — Pilot on a small Megaplan-executor pipeline

Before touching the main planning loop, convert one small Megaplan-executor-backed pipeline (e.g., `jokes` or `folder_audit`) as a **parity proving ground**:

- Rewrite `build_pipeline()` as a native function.
- Prove that the generated graph and the resulting run emit the same stage sequence, state shape, event journal, artifacts, and resume cursor behavior as the old graph-driven version for the same inputs.

Deliverable: one small native pipeline with graph + trace parity tests.

### Phase 4 — Convert the main Megaplan planning pipeline

This is the highest-impact migration.

- Wrap existing handlers (`handle_prep`, `handle_plan`, `handle_critique`, `handle_gate`, `handle_revise`, `handle_finalize`, `handle_execute`, `handle_review`, `handle_tiebreaker`) as `@phase` or `@decision` functions. Most are already pure phase functions; the wrapping is mainly contract metadata.
- Rewrite `arnold/pipelines/megaplan/pipeline.py` as a native `@pipeline` function with ordinary `while` loops for the critique/gate/revise cycle and tiebreaker subloop.
- Preserve the typed contracts from `arnold/pipelines/megaplan/pipeline_contracts.py`.
- Preserve override vocabulary, fallback edges, and decision routing.
- Keep `build_pipeline()` returning a `Pipeline` via the bridge for CLI compatibility.

Deliverable: `megaplan` expressed natively, behavior unchanged, all existing tests pass.

### Phase 5 — Convert remaining smaller graph-driven pipelines

In rough order of simplicity:

1. `folder_audit` (if not used in Phase 3)
2. `doc`
3. `creative`
4. `simplify_writing`
5. `live_supervisor`
6. `jokes` (if not used in Phase 3)

For each:

- Rewrite `build_pipeline()` as a native function.
- Reuse step implementations where possible.
- Run `arnold pipelines check <name>` and the targeted test file.

### Phase 6 — Convert parallel / human-gate pipelines

These are more complex because they rely on `ParallelStage`, panels, and human gates:

- `epic_blitz`
- `writing_panel_strict`
- `select_tournament`

Wait until the native authoring layer supports:

- fan-out (parallel phase calls),
- panel composition,
- human-gate suspension/resume.

They can stay graph-driven during Phases 1–5 without blocking anything.

### Phase 7 — Tooling, docs, and cleanup

- Update `arnold pipelines new` to scaffold a native `@pipeline` function by default.
- Update the `new arnold pipeline` skill and `docs/arnold/creating-a-new-pipeline.md`.
- Keep `arnold pipelines check` using the bridge path; document it as the canonical introspection path.
- Update observability/graph introspection to derive stage/edge views from decorators + AST.
- Once all pipelines are native-authored and the old Megaplan graph builder is unused, deprecate or remove it.

## Execution model — decision

**Native Python is authoring sugar that compiles to the existing graph.** The bridge produces a normal `Pipeline`; the existing executor walks it; checkpoint/resume, event journals, artifacts, and observability are unchanged.

A future **native runtime** (executing the Python function directly as a state machine) is not part of this plan. It can be explored later as R&D, but only after a parity corpus proves it can replay old graph semantics byte-for-byte where it matters. Until then, the authoring layer must be compatible with the existing executor.

## Acceptance criteria

- A native `@pipeline` function can express the full Megaplan planning flow (`prep → plan → critique → gate → [revise loop | tiebreaker | escalate] → finalize → execute → review`).
- The bridge-generated `Pipeline` is equivalent to the old hand-built graph: same stages, edges, contracts, decision vocabulary, and subloop structure.
- Because the existing executor runs the bridge graph, pause/resume, overrides, fallback edges, and subloop promotion continue to work unchanged.
- Existing handlers and artifacts are reused unchanged.
- Graph introspection produces an equivalent stage/edge view for observability tools.
- `arnold pipelines check` passes for every converted pipeline.
- Existing `arnold run` behavior and output artifacts are unchanged for end users.

## Per-pipeline migration checklist

Before merging the conversion PR for any existing pipeline:

1. The bridge-derived graph matches a hand-built reference graph.
2. Manifest hash is unchanged between the old graph-driven run and the native run on identical inputs.
3. `runtime_envelope` block in `state.json` is byte-equivalent (excluding timestamps).
4. Top-level state keys (`_pipeline_name`, `_inputs`, `_inputs_original`, `_state_meta`, `schema_version`) are preserved.
5. `events.ndjson` replays through `fold_journal` to the same final state.
6. Per-stage artifact directories and file naming conventions match.
7. A live `state.json` paused mid-pipeline resumes correctly after conversion (executor is unchanged, so this validates graph equivalence).
8. `arnold pipelines check <name>` passes on the bridge-derived graph.
9. End-to-end `arnold run` output artifacts are identical to the graph-driven version.
10. `build_pipeline() -> Pipeline` remains exported.

## Key risks

| Risk | Mitigation |
|---|---|
| Bridge-derived graph diverges from author intent | Make decorator metadata authoritative; keep the supported authoring grammar narrow; require reference-graph tests for every native pipeline. |
| AST-based branch inference becomes brittle | Use AST only as a fallback/proof; prefer decorator-declared branches and vocabulary. |
| Typed contract parity lost | Reuse the existing contract/port types inside `@phase`/`@decision` metadata; validate at runtime the same way the graph validator does. |
| Override injection ordering changes | Explicitly inject overrides before the decorated `@decision` call, preserving current gate/tiebreaker semantics. |
| CLI backward compatibility breaks | Always keep a `build_pipeline()` returning a `Pipeline` via the bridge during the transition. |
| Scope explodes | Pilot on `vibecomfy_executor`, then one small Megaplan-executor pipeline, then the main Megaplan loop; defer parallel/human-gate pipelines until the authoring layer supports them. |

## Suggested first commit

A minimal PR that adds `arnold.pipeline.native`, a `@pipeline`/`@phase`/`@decision` API, and a conversion bridge that produces a valid `Pipeline` graph. Include:

- a single test-only native pipeline (not a user-facing one);
- a test that asserts the bridge-derived graph matches a hand-built reference graph;
- a tiny synthetic run test that passes the bridge graph through the **existing** executor.

Do not convert any real pipeline, do not implement a native-only executor, and do not change persistence formats in that first PR.

## Load-bearing questions and predicted answers

These are the low-level design questions that will determine whether the native layer actually works in practice, together with the current best guess at the answer and the perspective each question belongs to.

### 1. How does a phase function declare what it reads and writes?
**Predicted answer:** Explicit decorator metadata is the source of truth — `@phase(consumes=..., produces=...)`. Reuse the existing `Port`/`PortRef` vocabulary rather than inventing a new one; authors can use contract helpers like `plan_contract.consumer_port("plan_payload")` for readability. Type hints on the function signature are useful IDE ergonomics but must not be required for runtime validation.

*Perspective:* authoring / human interaction.

### 2. How are typed contracts enforced at runtime?
**Predicted answer:** Enforcement is unchanged: the bridge emits the same `Stage`/`Port`/`PortRef` metadata the current graph uses, and the existing executor calls the same `evaluate_step_io_handoff()` / `resolve_step_io_policy()` paths. The native layer does not add a new enforcement path.

*Perspective:* correctness / external contracts.

### 3. How does checkpoint/resume work inside a `while` loop or nested subloop?
**Predicted answer:** Checkpoint/resume uses the existing executor and cursor mechanism unchanged. The bridge must generate a `Pipeline` graph with the same stage names, loop conditions, and subloop structure as the old hand-built version, so cursors and resume behavior line up exactly.

*Perspective:* runtime / resumability.

### 4. Where exactly do overrides get injected?
**Predicted answer:** The `@decision` decorator wraps the decision function and performs a **pre-invocation intercept**: before the handler body runs it checks the override catalog / operation registry (today's `state["meta"]["overrides"]` and `_OVERRIDE_CATALOG` in `arnold/pipelines/megaplan/planning/operations.py`) for an unprocessed override matching this decision label; if one exists it returns the override branch without invoking the model. This is not post-step edge routing — it preserves current gate/tiebreaker semantics and leaves the handler untouched.

*Perspective:* runtime / override policy.

### 5. How is the graph derived for `arnold pipelines check` and observability?
**Predicted answer:** The bridge derives a `Pipeline` graph from decorator metadata first, and uses a lightweight AST pass over the `@pipeline` function only to fill in conditional branches (e.g. discovering that `if verdict == "escalate": ...` creates an `escalate` edge). The decorator metadata is authoritative; the AST is a fallback/proof. To guard against drift, every native pipeline is tested against a hand-built reference graph that asserts the bridge output matches the expected `Stage`/`Edge` structure.

*Perspective:* tooling / observability / external consumers.

### 6. How do parallel panels and fan-out map to native Python?
**Predicted answer:** Add a single `parallel(...)` primitive usable inside `@pipeline` generators. Static panels pass named phases as kwargs (`yield from parallel(pessimist=..., optimist=..., join=merge_outputs)`); dynamic fan-outs pass a generator expression (`yield from parallel(for spec in specs: phase(spec.id, ...), join=concat)`). The primitive lowers to the existing `ParallelStage` so the executor handles concurrency/joining unchanged. Complex pipelines like `epic_blitz`, `writing_panel_strict`, and `select_tournament` should keep using the graph builder until this primitive exists and is tested.

*Perspective:* authoring / scaling / concurrency.

### 7. How does the CLI decide whether to run a native or graph pipeline?
**Predicted answer:** There is no separate path. Every pipeline still exposes `build_pipeline() -> Pipeline`; the native module’s `build_pipeline()` simply calls the bridge. The CLI, executor, and external hosts see a normal graph pipeline. A native-only runner is out of scope for this migration.

*Perspective:* CLI / external interface.

### 8. How do external hosts and capsules interact with native pipelines?
**Predicted answer:** They interact through the same neutral `arnold.pipeline.run_pipeline` API and `RuntimeEnvelope`. Because the bridge produces a normal `Pipeline`, capsules record the same static metadata and runtime topology hash they do today. The native authoring layer is invisible below the existing boundary.

*Perspective:* external usage / capsule compatibility.

### 9. How do subloops compose without leaking checkpoint scope?
**Predicted answer:** A subloop is a nested `@pipeline` function invoked via `yield from run_subpipeline(...)`. The bridge lowers it to the existing `SubloopStep` pattern: isolated artifact subdirectory, copied state dict, promotion-only boundary. The executor handles nested frames exactly as it does today.

*Perspective:* composability / runtime.

### 10. How do we avoid breaking in-flight plans when migrating an existing pipeline?
**Predicted answer:** Keep the executor unchanged and make the bridge generate an equivalent graph. Because `RuntimeEnvelope`, `state.json`, `events.ndjson`, artifact layout, and stage names stay the same, in-flight plans resume under the same executor semantics. Apply the per-pipeline migration checklist before merging any conversion PR.

*Perspective:* backwards compatibility / operational safety.

## High-level perspective summary

- **For authors:** the change makes pipelines look like ordinary Python functions. The learning curve drops from “graph builder API” to “write Python + add decorators,” which is especially valuable for new or small pipelines.
- **For operators:** nothing visible changes at the CLI. Runs still produce the same `state.json`, event journal, and artifacts. Resume and overrides keep working because the executor is unchanged.
- **For observability/debugging:** graph introspection is still a first-class view, but it is now derived from decorator metadata + AST rather than hand-built graph code. The derivation step must be reliable; if it drifts, dashboards and `arnold pipelines check` will lie.
- **For scaling/performance:** the big win is maintainability, not raw speed. The executor is unchanged, so throughput and concurrency characteristics are unchanged.
- **For external consumers / capsules:** the boundary stays exactly the same. The only new requirement is that static metadata must capture the native function’s contract surface, which the decorators are designed to do.
