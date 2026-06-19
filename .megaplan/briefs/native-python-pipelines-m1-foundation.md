# Milestone 1 — Native Python pipeline runtime foundation

## Outcome

A feature-flagged native Python pipeline runtime skeleton that can compile a toy `@pipeline` function into a resumable state-machine program, derive an equivalent `Pipeline` graph for validation/observability, and prove end-to-end execution + resume parity against the existing graph executor.

## Scope (IN)

- `arnold.pipeline.native` package with:
  - `@pipeline`, `@phase`, `@decision` decorators capturing metadata.
  - `arnold.pipeline.native.compiler` — AST/source-to-resumable-program lowering.
  - `arnold.pipeline.native.runtime` — execution loop, phase dispatch, resume.
  - `arnold.pipeline.native.context` — `NativeRunContext`, frame stack, artifact roots.
  - `arnold.pipeline.native.checkpoint` — checkpoint serialization and cursor I/O.
  - `arnold.pipeline.native.contracts` — bridge to existing `Port`/`PortRef` and `evaluate_step_io_handoff()`.
  - `arnold.pipeline.native.graph` — derived `Pipeline` projection from decorators + AST.
- A test-only native pipeline (not user-facing) covering:
  - sequential phases,
  - one typed producer/consumer handoff,
  - one decision vocabulary,
  - one guarded loop,
  - one resume from a native checkpoint.
- Reference-graph tests asserting the derived `Pipeline` matches a hand-built graph.
- Feature-flag wiring so no real pipeline is forced onto the native runtime.

## Scope (OUT)

- No conversion of real pipelines (including `vibecomfy_executor`, `folder_audit`, `jokes`, or `megaplan`).
- No Megaplan-specific semantics: overrides, state merge modes, envelope joining, subloops, policy/governor, human gates.
- No `parallel(...)` primitive.
- No change to existing `state.json`, `events.ndjson`, `resume_cursor.json`, or artifact formats.
- No removal or deprecation of the graph executor or graph builders.

## Locked decisions

- Native Python is the authoring source of truth; the `Pipeline` graph becomes a derived view.
- CPython frames will not be pickled; the runtime lowers functions to a resumable state machine.
- Existing `Port`/`PortRef` vocabulary and `evaluate_step_io_handoff()` are reused for contract enforcement.
- The existing graph executor remains the production runtime for all real pipelines during this milestone.

## Open questions

- Should the first real pilot after this milestone be `vibecomfy_executor` (neutral builder, simplest) or a small Megaplan-backed pipeline like `folder_audit`/`jokes` (to prove Megaplan semantics earlier)? Prep must answer and write a handoff for milestone 2.
- What is the exact native checkpoint cursor schema (frame stack, loop counters, branch IDs, local-variable refs) that remains compatible with existing `resume_cursor.json` readers?
- Which Python constructs are allowed across checkpoints? Need an explicit grammar.

## Constraints

- Must not break existing tests, `arnold pipelines check`, or in-flight plans.
- Must run behind a feature flag.
- Must produce byte-compatible persistence shapes where exercised (test-only pipeline).

## Done criteria

- `arnold.pipeline.native` modules exist and are importable.
- Test-only native pipeline compiles, validates, runs through the native runtime, and resumes from a native checkpoint.
- Derived graph matches a hand-built reference graph.
- A synthetic run through the existing graph executor using the derived graph produces the same stage sequence and state shape as the native runtime run.
- All existing tests still pass.
- Milestone 2 handoff document exists with the chosen first real pilot and a narrowed scope.

## Touchpoints

- `arnold/pipeline/native/` (new package)
- `arnold/pipeline/types.py` — `Pipeline`, `Stage`, `Port`, `PortRef`
- `arnold/pipeline/executor.py` — reference execution behavior
- `arnold/pipeline/validator.py` — validation of derived graph
- `arnold/pipeline/step_io_handoff.py` — contract enforcement reuse
- `arnold/runtime/envelope.py` — `RuntimeEnvelope`
- `arnold/runtime/wal_fold.py` — event journal fold
- `tests/arnold/pipeline/native/` (new tests)

## Anti-scope

- Do not touch `arnold/pipelines/megaplan/pipeline.py`.
- Do not change `arnold pipelines check` CLI behavior.
- Do not remove `PipelineBuilder` or `Stage`/`Edge` types.
