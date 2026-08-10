# Milestone 5 — Parallel primitives and human-gate support

## Outcome

The native runtime supports `parallel(...)` fan-out/fan-in, panel composition, and human-gate suspension/resume, and the first parallel/human-gate pipelines (`epic_blitz`, `writing_panel_strict`, `select_tournament`) run natively with parity.

## Scope (IN)

- Native `parallel(...)` primitive:
  - Typed collection contracts for fan-out units and fan-in result.
  - Bounded cardinality declared at compile time.
  - Each fan-out unit runs in isolation with its own checkpoint scope.
  - Fan-in barrier that collects `ContractResult`s and reduces them to a single producer payload.
  - During transition, may lower to existing `ParallelStage` or execute natively with `asyncio.gather`/barrier join; the choice must be flag-gated and reversible.
- Panel composition helpers for running a fixed set of phases/decisions in parallel and joining on a policy (all, any, majority, etc.).
- Human-gate suspension/resume:
  - Native `@decision` or `human_gate(...)` primitive that suspends with a resume input schema.
  - Persists a suspension cursor compatible with existing `resume_cursor.json` readers.
  - Resumes via override or supplied resume input.
- Pipeline conversions:
  - Convert `epic_blitz`, `writing_panel_strict`, and `select_tournament` to native `@pipeline` functions.
  - Assert trace/state/event/artifact parity against graph-executor golden traces.
  - Prove human-gate resume and parallel fan-out/fan-in resume.
- Derived graph support for `parallel` and human-gate stages so `arnold pipelines check` and dashboards see the correct possible topology.

## Scope (OUT)

- Remaining smaller pipelines (`creative`, `doc`, `simplify_writing`, `live_supervisor`, etc.).
- Main `megaplan` pipeline changes beyond keeping it working with the new primitives.
- Flipping the default execution mode.
- Graph-builder removal.

## Locked decisions

- `parallel(...)` cardinality must be statically bounded; dynamic fan-out is rejected by the compiler.
- Human-gate suspension uses the same interaction envelope and resume cursor shape as the graph executor.
- Each fan-out unit is checkpoint-isolated; failures and suspensions propagate according to the fan-in policy.
- These pipelines are converted only after the core runtime and main Megaplan pipeline are proven.

## Open questions

- Should `parallel(...)` lower to `ParallelStage` initially, or execute natively from the start?
- What is the correct reduction semantics for each converted pipeline (list, majority vote, structured synthesis)?
- How does a panel's derived graph represent optional human-gate branches?
- Are there existing tests or fixtures for these pipelines that can be reused for parity capture?

## Constraints

- Must not break existing tests or in-flight plans.
- Must run behind the existing feature flag.
- Must produce byte-compatible persistence shapes where exercised.
- Must not change the default execution mode.

## Done criteria

- `parallel(...)` primitive compiles, runs, and resumes correctly in native tests.
- Human-gate suspension/resume works end-to-end and produces compatible cursors.
- `epic_blitz`, `writing_panel_strict`, and `select_tournament` each have a native implementation.
- Each converted pipeline passes parity tests against graph-executor golden traces.
- Resume from suspension works for each converted pipeline.
- Derived graphs pass validation and produce expected topology hashes.
- All existing tests still pass.
- Milestone 6 handoff lists the remaining pipelines in priority order and any patterns that can be templated.

## Touchpoints

- `arnold/pipeline/native/runtime.py` (parallel and human-gate dispatch)
- `arnold/pipeline/native/compiler.py` (parallel lowering)
- `arnold/pipeline/native/graph.py` (parallel/human-gate topology)
- `arnold/pipeline/native/contracts.py` (collection port contracts)
- `arnold/pipelines/epic_blitz/` (conversion)
- `arnold/pipelines/writing_panel_strict/` (conversion)
- `arnold/pipelines/select_tournament/` (conversion)
- `tests/arnold/pipelines/epic_blitz/test_native_parity.py` (new)
- `tests/arnold/pipelines/writing_panel_strict/test_native_parity.py` (new)
- `tests/arnold/pipelines/select_tournament/test_native_parity.py` (new)

## Anti-scope

- Do not convert the remaining smaller pipelines here.
- Do not flip the default execution mode.
- Do not remove graph builders.
- Do not introduce unbounded dynamic fan-out.
