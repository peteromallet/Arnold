# M2 - Routing Validator And Authoring Boundary

## Objective

Enforce the M0 authoring boundary early: arbitrary Python is allowed inside
steps, but workflow routing must remain deterministic, statically recoverable,
and safe to replay. This validator must gate Megaplan's compositional workflow
before general nesting, tree traces, or composite resume depend on it.

## Files To Change And Instructions

- `arnold/pipeline/native/compiler.py`
  Keep hard compile-time rejection for syntax that prevents structure recovery.
- `arnold/pipeline/native/validator.py` or an equivalent native validation home
  Add a routing validator that detects obvious nondeterminism and side effects
  in workflow bodies: clocks, random, filesystem IO, network calls, subprocess,
  dynamic dispatch, import-time routing tricks, and unsupported loop/routing
  constructs.
- `arnold/pipeline/native/decorators.py`
  Surface enough metadata for the validator to distinguish step bodies from
  workflow routing bodies.
- `arnold_pipelines/megaplan/workflows/workflow.py`
  Ensure the compositional Megaplan workflow validates under the new rules.
- `arnold/pipelines/_authoring.py`
  Surface validator diagnostics in authoring helpers.
- `tests/arnold/pipeline/native/`
  Cover accepted routing, rejected nondeterminism, rejected dynamic dispatch,
  allowed arbitrary code inside `@phase` / step bodies, loop guards over
  recorded state, and replay-consistency failure cases the validator cannot
  statically prove.
- `tests/arnold/pipelines/megaplan/`
  Ensure the compositional Megaplan workflow passes the validator.

## Verifiable Completion Criterion

- The validator catches common ways agent-generated workflow code leaks
  nondeterminism or side effects into routing.
- Diagnostics name the offending line and recommend moving the work into a
  step.
- Megaplan's compositional workflow validates cleanly.
- The validator is wired into package checks or CI for shipped native workflows.
- A replay-consistency fixture exists: run, interrupt, resume, and assert the
  resumed final structure/state is equivalent to an uninterrupted run.
- Source-invariant checks fail if report-owned decisions move back into
  handler-local `current_state`, `next_step`, `workflow_transition`,
  `run_parallel_*`, override action dispatch, or equivalent implicit state
  mutation.
- Generic Arnold coupling and semantic-vocabulary scans run against the current
  canonical source and fail if neutral native modules import Megaplan product
  semantics.

## Native Representation Alignment

- Matrix rows owned or affected: Bounded critique/gate/revise loop; Gate preflight and payload normalization; Gate signal building and reprompt; Gate flag/debt/fallback handling; Review infrastructure retry and cap outcomes; Override full action surface; Typed loop outcomes or break/continue; Handler topology extraction/purity audit.
- Expected status change: `enabled` rows gain enforceable validator/source-invariant proof; M1-owned semantics cannot close without these checks.
- Proof artifacts: routing validator tests, line-specific diagnostics, replay-consistency fixture, Megaplan validator pass, generic-coupling/semantic-vocabulary scans, and source-invariant scans for retained handlers.
- False-pass guard: a readable workflow that routes through hidden state mutation, nondeterministic calls, or handler-owned `next_step` changes must fail validation or conformance.
- Deferrals: static tree snapshots and path resume proofs remain M4/M5; production event replay and durability remain platform M4/M6.
- Canonical source paths/imports: validator wiring must run on shipped native workflows, including canonical Megaplan, not only on examples.

## Risks And Blockers

- Static validation cannot prove arbitrary Python purity. Scope the validator to
  strong, useful checks and fail safe on dynamic constructs.
- Overly broad rejection can make authoring unpleasant. Keep the recommended fix
  path obvious: move live work into a step and route on recorded output.
- The validator cannot by itself catch routing over nondeterministic step
  outputs. Replay-consistency tests are the backstop.

## Dependencies

- Depends on M0 and M1.
