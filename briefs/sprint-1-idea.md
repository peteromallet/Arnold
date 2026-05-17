# Sprint 1 — Primitive shape + fan-out judges demo

This is Sprint 1 of the megaplan decomposition refactor. The full source
plan is at `briefs/megaplan-decomposition.md` (v2, hardened by three
parallel critiques). Read it for context, prior art, leaks, and acceptance
tests; this file is the Sprint-1-scoped subset.

## What ships in Sprint 1

1. `megaplan/_pipeline/types.py` — concrete dataclasses + protocol for:
   - `StepContext` (plan_dir, state, profile, mode, inputs, budget)
   - `StepResult` (outputs, verdict, next-edge, state_patch)
   - `Step` protocol (`name`, `kind` ∈ {produce, judge, decide, subloop,
     override}, `prompt_key`, `slot`, `run(ctx)`)
   - `Edge`, `Stage`, `Pipeline`, `Overlay`
   - `Verdict` typed struct
   - `ParallelStage` for fan-out + barrier-join
2. `megaplan/_pipeline/executor.py` — minimal pipeline executor: walks
   stages, calls `Step.run`, applies `state_patch`, follows `next-edge`,
   writes artifacts via `phase_result_guard`-equivalent. NOT integrated
   into `auto.py` yet (Sprint 2 does that); standalone runtime for the
   prototype.
3. `megaplan/_pipeline/demo_judges.py` — fan-out judge + synthesis
   pipeline. Three judges critique the same fixture document in parallel;
   a synthesis stage merges verdicts; gate decides on synthesis. Uses
   ONLY the new types and executor.
4. `tests/test_pipeline_compose.py` — acceptance test #2 (compose a
   4-stage pipeline `prep → 2× critique → finalize` in ≤50 lines of
   Python using only public primitives, run on a fixture doc, assert
   artifacts).
5. `tests/test_pipeline_demo_judges.py` — acceptance test #3 (fan-out
   judges pipeline runs end-to-end on a fixture doc, asserts 3 judge
   artifacts + 1 synthesis artifact land in expected paths).
6. `docs/pipeline-resume.md` — worked example of how `resume_cursor.phase`
   maps to a stage in a composed pipeline (design doc, no code).

## Out of scope for Sprint 1

- Porting any existing handler to a Step (that is Sprint 2).
- Modifying `auto.py`, `_core/workflow.py`, or any current handler.
- Modifying profile TOMLs.
- The doc-critique 3x-loop demo (Sprint 2 acceptance test).
- Tiebreaker as Subloop, override as escape edge — leave Step protocol
  stubs but don't implement.

## Constraints

- Type interfaces (Step, Stage, Pipeline, Edge, StepContext, StepResult)
  must be frozen at end of Sprint 1. Sprint 2 builds on them without
  changing them. If Sprint 2 reveals an interface flaw, file a revision
  note in `briefs/megaplan-decomposition.md`.
- All new code under `megaplan/_pipeline/`; do not touch any existing
  module except adding the new package.
- Tests under `tests/` named `test_pipeline_*.py`. Must pass under the
  existing test runner (`pytest tests/test_pipeline_*.py`).
- No regression in any existing test (`pytest tests/` from scratch must
  stay green).

## Acceptance for Sprint 1

- `pytest tests/test_pipeline_compose.py tests/test_pipeline_demo_judges.py`
  passes.
- `pytest tests/` (full suite) stays green.
- `python -c "from megaplan._pipeline import Pipeline, Stage, Step,
  StepContext, StepResult, Edge, Overlay"` succeeds.
- The fan-out demo can be invoked via a small script and writes 3 judge
  artifacts + 1 synthesis artifact under `.megaplan/demos/judges/<run>/`.

## Operating principles

- No human review or approval. Self-validating tests are the only gate.
- Blockers get overcome via fallback paths; if stuck >2 attempts, write
  `BLOCKER-<n>.md` to record state and keep going.
- Live megaplan must keep working: the system venv at
  `/Users/peteromalley/Documents/megaplan/.venv` and binary at
  `/Users/peteromalley/.local/bin/megaplan` must keep resolving to the
  main checkout. Verify after each commit with `cd /tmp &&
  /Users/peteromalley/Documents/megaplan/.venv/bin/python -c "import
  megaplan; print(megaplan.__file__)"` — must print the
  `Documents/megaplan/megaplan/__init__.py` path, not the worktree.
- All commits land on the `decomp/main` branch in this worktree.
