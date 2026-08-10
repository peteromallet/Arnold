# Milestone 4 — Main Megaplan pipeline conversion

## Outcome

`arnold/pipelines/megaplan/pipeline.py` is expressed as a native `@pipeline` async function, can run side-by-side with the graph executor behind a flag, and reaches full trace/state/event/artifact parity before native execution is allowed as default.

## Scope (IN)

- Rewrite `arnold/pipelines/megaplan/pipeline.py` as a native Python function decorated with `@pipeline("megaplan")`.
  - Preserve existing handlers and contracts.
  - Declare `consumes`/`produces` ports on every `@phase` and `@decision` to match current binding semantics.
  - Use `@decision` for gate/tiebreaker/escalate vocabulary and override vocabulary.
  - Express the current nine-stage layout as native control flow: `prep → plan → critique → gate → revise/finalize/tiebreaker/escalate → execute → review`.
  - Use `run_subpipeline(...)` where the current graph uses nested subloops.
- Side-by-side execution:
  - Per-run feature flag or envelope marker chooses graph vs. native.
  - Existing graph executor remains the default.
  - New native runs can be opted in for testing.
- Parity validation:
  - Capture golden traces from the current graph executor for representative plan inputs.
  - Run the same inputs through the native function and assert byte-compatible stage sequence, `state.json`, `events.ndjson` fold, `resume_cursor.json`, artifacts, and topology hash.
  - Prove resume from a native checkpoint for a multi-stage Megaplan run.
- Derived graph:
  - `build_pipeline()` continues to return a `Pipeline` object, now derived from the native function via `arnold.pipeline.native.graph.derive_pipeline()`.
  - The derived graph must pass `validator.validate_control_flow()` and produce the same topology hash as the current hand-built graph.
- Test coverage for all major branches: revise loop, finalize, tiebreaker, escalate, override paths, suspension/resume.

## Scope (OUT)

- Other pipelines (they are handled in Milestones 5 and 6).
- `parallel(...)` primitive and panel/human-gate conversions (Milestone 5).
- Flipping the default execution mode to native (Milestone 7).
- Removing the graph executor or graph builders (Milestone 7).

## Locked decisions

- The native `megaplan` function must produce byte-compatible persistence shapes before it is allowed as default.
- `build_pipeline()` is still the public API; its returned `Pipeline` is derived from the native function.
- The graph executor remains the default for production runs during this milestone.
- All existing tests must pass with the graph executor unchanged.

## Open questions

- Which representative plan inputs cover all nine stages and the major decision branches?
- How are graph-born in-flight plans identified so they continue to resume on the graph executor?
- Does the native function need access to current `ctx` (memory, model profile, trust tier) and how is it injected?
- Are there any hand-built graph edges or fallback edges that cannot be expressed in the supported Python subset?

## Constraints

- Must not break existing tests, `arnold pipelines check`, or in-flight plans.
- Must run behind a feature flag.
- Must reuse Milestone 3 Megaplan hooks for state merge, overrides, step-IO policy, envelope join, and subloops.
- Must not change persistence formats.

## Done criteria

- Native `megaplan` pipeline function exists and compiles.
- Derived graph passes validation and matches the current topology hash.
- Native and graph runs produce parity-equivalent traces for representative inputs.
- Native resume from checkpoint works for a multi-stage run.
- Existing graph-executor tests still pass.
- No real plan is forced onto native execution by default.
- Milestone 5 handoff identifies which panel/tournament pipelines to convert first and any `parallel(...)` API gaps.

## Touchpoints

- `arnold/pipelines/megaplan/pipeline.py` (rewrite)
- `arnold/pipelines/megaplan/build_pipeline.py` or equivalent (derived graph export)
- `arnold/pipeline/native/` (runtime, compiler, graph derivation)
- `arnold/pipelines/megaplan/native_hooks.py` (Milestone 3)
- `arnold/pipeline/executor.py` (reference behavior)
- `arnold/pipeline/validator.py` (derived graph validation)
- `arnold/pipeline/types.py` (`Pipeline`, `Stage`, `Port`, `PortRef`)
- `tests/arnold/pipelines/megaplan/test_native_parity.py` (new)

## Anti-scope

- Do not flip the default execution mode.
- Do not remove or deprecate the graph executor.
- Do not add `parallel(...)` here unless required by the main pipeline.
- Do not convert other pipelines.
