## Handoff artifacts

- `parallel(...)` contract: static cardinality rules, branch-isolation semantics, reducer vocabulary, and any temporary graph-executor lowering notes.
- Panel-composition helper notes showing how `select-tournament` and `epic-blitz` express their joins on top of the landed `parallel(...)` primitive.
- Derived-graph/projection evidence for parallel branches and joins, including topology-hash expectations and any validation caveats.
- Parity and resume evidence locations for `select-tournament` and `epic-blitz`.
- Explicit M5B handoff listing only remaining human-gate work, so suspend/resume parity does not need to rediscover the parallel surface.

## No-go conditions

- M4 handoff has not proven main-Megaplan parity and stable native-to-projected-graph export.
- `parallel(...)` scope is widening into generic async/runtime redesign or unbounded dynamic fan-out.
- Human-gate suspend/resume work is leaking into M5A beyond keeping existing tests compiling.
- Reduction semantics for `select-tournament` or `epic-blitz` are still undecided when implementation starts.

# Milestone 5A — Parallel primitives and panel pipelines

## Outcome

The native runtime supports bounded `parallel(...)` fan-out/fan-in plus panel composition, and the first real parallel/panel pipelines (`select-tournament` and `epic-blitz`) run natively with parity.

## Scope (IN)

- Native `parallel(...)` primitive:
  - Declared, statically bounded branch cardinality.
  - Isolated branch execution and checkpoint scope.
  - Deterministic fan-in barrier that reduces branch outputs to one downstream payload.
  - Reversible flag-gated implementation path if an initial bridge through existing graph-executor parallel machinery is needed.
- Panel-composition helpers that express fixed reviewer/judge sets on top of `parallel(...)` with explicit join policies.
- Derived graph / projection support for `parallel(...)` and panel joins so `arnold pipelines check` and dashboards see the correct possible topology.
- Pipeline conversions:
  - Convert CLI-visible `select-tournament` (`arnold/pipelines/megaplan/pipelines/select-tournament/`) to a native `@pipeline`.
  - Convert CLI-visible `epic-blitz` (`arnold/pipelines/megaplan/pipelines/epic_blitz.py`) to a native `@pipeline`.
  - Capture graph-executor golden traces and assert native parity for stage sequence, `state.json`, `events.ndjson` fold, `resume_cursor.json`, artifacts, and topology hash.
  - Prove checkpoint resume across the fan-out/fan-in boundary for each converted pipeline.

## Scope (OUT)

- Human-gate suspend/resume parity and `writing-panel-strict` (handled in M5B).
- `deliberation` unless it is explicitly pulled forward in M5B as the optional second human-gate pipeline.
- Remaining graph-backed pipeline migrations (`creative`, `doc`, `jokes`, `live_supervisor`, etc.).
- Flipping the default execution mode.
- Graph-builder removal.

## Locked decisions

- `parallel(...)` cardinality must be statically bounded; unbounded dynamic fan-out is rejected by the compiler.
- Panel composition is built on top of the single native `parallel(...)` surface; there is no second bespoke panel execution engine.
- Derived graph export uses the real native surfaces (`compile_pipeline(...)` plus `graph_projection.project_graph(...)`), not a separate `graph.py` layer.
- Each fan-out branch is checkpoint-isolated and joins reduce outputs deterministically before control advances.

## Open questions

- Should the first implementation lower through existing `ParallelStage` behavior behind a flag, or schedule native branches directly from day one?
- What reducer semantics are canonical for `select-tournament` and `epic-blitz`?
- How should projected topology represent non-winning or short-circuited panel branches for validation and dashboards?
- Is resume proof required from inside an active branch, or is barrier-edge resume sufficient for this milestone?

## Constraints

- Must not break existing tests or in-flight plans.
- Must run behind the existing feature flag.
- Must produce byte-compatible persistence shapes where exercised.
- Must keep the chain settings locked to `partnered-5` / `codex` / `thorough` / `high`.
- Must not let human-gate or default-flip work leak into this milestone.

## Done criteria

- `parallel(...)` compiles, runs, and resumes correctly in native tests.
- Derived graphs containing parallel/panel topology validate and produce the expected topology hashes.
- `select-tournament` and `epic-blitz` each have a native implementation.
- Each converted pipeline passes parity tests against graph-executor golden traces.
- Resume from a fan-out/fan-in checkpoint works for each converted pipeline.
- All existing tests still pass.
- M5B handoff lists only remaining human-gate requirements and confirms there are no additional parallel-surface blockers.

## Touchpoints

- `arnold/pipeline/native/runtime.py` (parallel dispatch and barrier join)
- `arnold/pipeline/native/compiler.py` (parallel lowering and static-cardinality validation)
- `arnold/pipeline/native/graph_projection.py` (parallel/panel topology projection)
- `arnold/pipeline/native/ir.py` (instruction and metadata shapes carried into projection/runtime)
- `arnold/pipeline/native/hooks.py` (parallel-aware hook seams if checkpoint/join callbacks need extension through the frozen surface)
- `arnold/pipelines/megaplan/pipelines/select-tournament/` (conversion)
- `arnold/pipelines/megaplan/pipelines/epic_blitz.py` (conversion)
- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py` (new)
- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py` (new)

## Anti-scope

- Do not add human-gate primitives here.
- Do not convert `writing-panel-strict` or `deliberation` here.
- Do not flip the default execution mode.
- Do not introduce open-ended remaining-pipeline inventory.
- Do not introduce unbounded dynamic fan-out.
