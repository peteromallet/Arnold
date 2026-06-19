# Native Python runtime migration — execution plan

## Goal

Move the Megaplan pipeline system from a graph-executor model to a **native-Python-runtime model**. In the end state:

- A pipeline is an ordinary `async def` Python function decorated with `@pipeline`.
- Phases are ordinary `async def` functions decorated with `@phase` or `@decision`.
- The runtime executes the Python function directly, intercepting phase calls as checkpoint boundaries.
- Typed contracts, override injection, subloops, event journaling, resume, and observability are handled by the runtime.
- The `Pipeline` graph becomes a **derived view** for `arnold pipelines check`, dashboards, capsules, and external hosts — not the execution engine.
- Existing in-flight plans remain resumable, either on the legacy graph executor or through a compatible cursor migration.

This is the final architecture implied by **Option C**: prove parity via graph projection first, then move execution under the native state-machine runtime while continuing to derive graph views.

## End-to-end execution plan

### Phase 0 — Foundation

Build the native authoring and runtime skeleton:

- `arnold.pipeline.native.decorators`: `@pipeline`, `@phase`, `@decision`.
- `arnold.pipeline.native.compiler`: AST/source-to-resumable-program lowering.
- `arnold.pipeline.native.runtime`: execution loop, resume, phase dispatch.
- `arnold.pipeline.native.context`: `NativeRunContext`, frame stack, artifact roots.
- `arnold.pipeline.native.checkpoint`: checkpoint serialization and cursor I/O.
- `arnold.pipeline.native.contracts`: bridge to existing `Port`/`PortRef` and `evaluate_step_io_handoff()`.
- `arnold.pipeline.native.graph`: derived `Pipeline` projection.
- Feature-flag support so no real pipeline is forced onto the native runtime.

Deliverable: a test-only native pipeline compiles, validates, runs, and resumes through the native runtime.

### Phase 1 — Parity corpus

Capture current Megaplan behavior as golden traces:

- stage sequences,
- `state.json` snapshots,
- `events.ndjson` folds,
- `resume_cursor.json` shapes,
- artifact layouts,
- topology hashes.

These traces become the acceptance tests for the native runtime.

### Phase 2 — Small pipeline pilot

Convert one small Megaplan-executor pipeline (e.g., `folder_audit` or `jokes`) to the native runtime:

- express it as a native Python function,
- run it behind the feature flag,
- assert trace/state/event/artifact parity against the old graph-driven version,
- prove resume from a native checkpoint.

Deliverable: one production pipeline running natively, with parity tests.

### Phase 3 — Megaplan-specific runtime hooks

Implement the Megaplan semantics inside the native runtime:

- state merge (`executor-key-merge`, `_state_meta` CAS),
- override injection from `state["meta"]["overrides"]` and the operation catalog,
- Megaplan step-IO policy adapter,
- envelope joining and trust-state handling,
- subloop promotion and suspension-lift semantics,
- loop-condition guards.

Deliverable: native runtime can run a Megaplan-shaped toy pipeline with loops, decisions, overrides, and subloops.

### Phase 4 — Main Megaplan pipeline conversion

Rewrite `arnold/pipelines/megaplan/pipeline.py` as a native Python function:

- preserve existing handlers and contracts,
- run both graph and native versions side by side behind a flag,
- require full trace parity before allowing native as default,
- keep `build_pipeline() -> Pipeline` exported via graph projection.

Deliverable: `megaplan` runs natively, behavior unchanged, all existing tests pass.

### Phase 5 — Parallel / human-gate support

Add native primitives for:

- `parallel(...)` fan-out/fan-in,
- panel composition,
- human-gate suspension/resume.

Then convert `epic_blitz`, `writing_panel_strict`, and `select_tournament`.

### Phase 6 — Remaining pipeline migrations

Convert the rest of the smaller pipelines (`creative`, `doc`, `simplify_writing`, `live_supervisor`, etc.) one by one, each with parity tests.

### Phase 7 — Flip the default

Once all pipelines run natively and in-flight plans can migrate or finish on the legacy executor:

- make native execution the default for new runs,
- keep the graph executor as a read-only fallback for old plans,
- deprecate the hand-built graph builders.

### Phase 8 — Cleanup

Remove graph-builder scaffolding, update docs/skills, and make the derived graph the only graph path.



## Acceptance criteria for the end state

- A native `@pipeline` function can express the full Megaplan planning flow.
- The native runtime produces byte-compatible `state.json`, `events.ndjson`, `resume_cursor.json`, and artifacts for every converted pipeline.
- Existing in-flight plans either finish on the legacy executor or migrate safely.
- `arnold pipelines check`, dashboards, and capsules see a derived graph equivalent to the old hand-built graph.
- Overrides, decision vocabularies, fallback edges, and subloop promotion behave identically.
- Agent-authored pipelines are constrained to a safe, resumable, inspectable subset of Python.

## Biggest risks

| Risk | Mitigation |
|---|---|
| Resumable Python locals are hard to get right | AST state-machine lowering, strict serializable-locals check, no frame pickling. |
| Semantic drift from graph executor | Per-pipeline parity corpus; compare every boundary and WAL fold. |
| Graph projection lies | Separate static possible graph from observed runtime graph; projection failure blocks deployment. |
| Override ordering changes | Intercept before `@decision` body and route through `verdict.override` with existing resolver priority. |
| Subloop suspension loss | Frame-stack cursors and composite cursor writer. |
| Scope explosion | Strict phase gating; no real conversion until pilots pass. |
