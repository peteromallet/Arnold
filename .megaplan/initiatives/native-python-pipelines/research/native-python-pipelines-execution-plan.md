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

<!-- BEGIN EXECUTION_QUESTIONS -->

## Execution load-bearing questions and predicted answers

These questions determine whether the migration can actually be executed. If you know the answers, the plan follows.

### 1. Do we build the native runtime first or prove graph parity first?
**Predicted answer:** Build them together. Start with a native runtime skeleton plus a graph-projection bridge in Phase 0, then use the bridge to validate the native runtime against the existing executor in Phase 1–2. Proving parity before converting real pipelines is non-negotiable.

### 2. How do we preserve resume for existing in-flight plans?
**Predicted answer:** Keep the legacy graph executor available as a read-only fallback. Graph-born plans resume with the graph executor. Native-born plans use native checkpoint cursors. Only after a cursor-migration path is proven do we allow graph-born plans to resume natively.

### 3. Which pipeline do we convert first?
**Predicted answer:** A toy pipeline first (to prove the architecture), then one small Megaplan-backed pipeline (`folder_audit` or `jokes`) to prove Megaplan semantics, then the main `megaplan` pipeline. Parallel/human-gate pipelines are deferred until `parallel(...)` and human-gate suspension are native-supported.

### 4. How do we prove parity between native and graph execution?
**Predicted answer:** Capture golden traces from the graph executor (stage sequence, `state.json`, `events.ndjson` fold, cursors, artifacts, topology hash) and assert the native runtime produces identical traces for the same inputs. This is per-pipeline, not blanket.

### 5. When do we flip the default execution mode to native?
**Predicted answer:** Only after the main Megaplan pipeline runs natively with full parity and in-flight compatibility is proven. The flip is Phase 7, not Phase 0.

### 6. How do we handle unsafe or unconvertible agent-authored constructs?
**Predicted answer:** Define a supported Python grammar. Static analysis and runtime sandboxing reject constructs that break resumability or graph derivation: dynamic phase calls, reflection, hidden global mutation, non-serializable locals across checkpoints. Graph projection failure blocks deployment.

### 7. How do we keep `arnold pipelines check` trustworthy?
**Predicted answer:** Produce two graphs: a static possible graph from AST + decorator metadata, and an observed runtime graph from traces. Static graph validates structure; observed graph validates what actually ran. Discrepancies are flagged.

### 8. What is the rollback strategy if the native runtime fails in production?
**Predicted answer:** Per-pipeline feature flags and per-run envelope markers. If a native run fails in a recoverable way, the system can fall back to the graph executor for graph-derived pipelines. New native-only constructs cannot roll back.

### 9. How do external hosts and capsules stay compatible?
**Predicted answer:** Keep the neutral `arnold.pipeline.run_pipeline` API and `RuntimeEnvelope` unchanged. Capsule topology hashes are derived from the native function via the graph projection, exactly as they are derived from hand-built graphs today.

### 10. How do we avoid the project exploding in scope?
**Predicted answer:** Strict phase gating. No real pipeline conversion until the toy and small pilots pass parity. No parallel/human-gate conversion until core runtime is proven. Each phase has explicit deliverables and acceptance tests.

<!-- END EXECUTION_QUESTIONS -->

<!-- BEGIN TECHNICAL_QUESTIONS -->

## Technical end-state load-bearing questions and predicted answers

These questions determine whether the native runtime can actually replace the graph executor while preserving every feature.

### 1. How does the runtime intercept phase calls?
**Predicted answer:** `@phase` registers metadata on the function. The compiler/lowering pass rewrites `await phase_fn(...)` inside a `@pipeline` function into `await runtime.dispatch_phase(phase_fn, args, checkpoint_id)`. At runtime, `dispatch_phase` handles checkpointing, contract validation, execution, and result assignment.

### 2. How is resume durable across process restarts?
**Predicted answer:** The pipeline function is lowered into a resumable state machine. The runtime persists a frame stack with loop counters, branch identifiers, and a snapshot of serializable local variables at every phase checkpoint. Resume reloads the frame stack, rehydrates contract/artifact refs, and jumps to the saved checkpoint.

### 3. How are typed contracts enforced at phase boundaries?
**Predicted answer:** Each `@phase` declares `consumes`/`produces` metadata, lowered to `Port`/`PortRef`. The phase return is normalized to a `ContractResult`. Before the result is assigned to the consumer, the runtime calls `evaluate_step_io_handoff()` with the resolved seam, producer port, consumer port, and policy.

### 4. Where exactly are overrides injected?
**Predicted answer:** Before the body of any `@decision` phase runs. The runtime inspects `state["meta"]["overrides"]` and the operation catalog; if an unprocessed override applies, it synthesizes a `Verdict` with the override action and skips the decision body.

### 5. How do subloops compose without leaking checkpoint scope?
**Predicted answer:** `run_subpipeline(child, inputs)` pushes a child frame with its own artifact subdirectory and a shallow-copied state dict. Only the promoted result crosses back to the parent. Suspended children cause the parent to suspend with a composite cursor.

### 6. How does event journaling and state persistence stay compatible?
**Predicted answer:** The native runtime writes the same file shapes: `state.json`, `events.ndjson`, `resume_cursor.json`, and per-stage artifacts. It uses existing helpers (`write_plan_state`, `fold_journal`, `last_state_snapshot_projector`) and emits the same `EventKind`s so WAL replay works unchanged.

### 7. How is the graph derived for observability?
**Predicted answer:** `arnold.pipeline.native.graph.derive_pipeline(native_def)` produces a `Pipeline` from decorator metadata and a lightweight AST pass. For dynamic branches, it combines the static possible graph with observed runtime traces. The derived graph must pass existing validation and produce the same topology hash as today.

### 8. How are loops and conditionals handled in the state machine?
**Predicted answer:** The compiler assigns stable checkpoint IDs that include loop names and branch IDs. Loop counters and the last-taken branch are stored in the frame. Conditionals are allowed, but the runtime records which branch was taken so the same path is replayed on resume.

### 9. How do parallel panels and fan-out work?
**Predicted answer:** A `parallel(...)` primitive is provided. It either lowers to the existing `ParallelStage` during transition or is executed natively with a `ThreadPoolExecutor`/asyncio gather plus a barrier join. Each fan-out unit runs in isolation with its own checkpoint scope.

### 10. How do we guarantee determinism and safe agent composition?
**Predicted answer:** Four rules: (a) only `await` on decorated phases, decisions, `parallel`, and `run_subpipeline` may cross checkpoints; (b) locals surviving checkpoints must be JSON-serializable or typed contract/artifact refs; (c) no hidden global state mutation across phases; (d) dynamic phase calls, reflection, and runtime-generated control flow are rejected. These rules make pipelines both resumable and understandable.

<!-- END TECHNICAL_QUESTIONS -->

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
