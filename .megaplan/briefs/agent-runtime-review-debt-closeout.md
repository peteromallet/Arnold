# Agent Runtime Review Debt Closeout

## Outcome

Close the concrete review debt left by `elegant-agent-runtime-integration` so the agent-runtime integration work can be considered cleanly reviewable. The finished work should remove the review-reported test regressions and package-readiness gaps without reopening the broader architecture.

## Context

The plan `elegant-agent-runtime-integration` reached `done`, but review force-proceeded after max rework cycles and left four actionable issues:

1. Two review tests fail because test scaffolds do not create `.megaplan/schemas/review.json` before `run_parallel_review()` reads it.
2. The AST-based fanout boundary guardrail file required by the plan is missing.
3. `megaplan/py.typed` is missing.
4. Obsolete prep helpers remain in `megaplan/orchestration/prep_research.py`: `scatter_over_worker_step` and `scatter_over_worker_step_process`.

Treat those four findings as the complete scope unless a focused test proves a directly related breakage.

## Locked Decisions

- Do not redesign the agent runtime or worker fanout architecture.
- Keep the migrated `WorkerUnit` / `scatter_worker_units` paths as the sanctioned fanout path.
- Remove or retire obsolete prep helper code only if no production caller remains.
- The test scaffold fix should create the missing schema fixture or mock the schema lookup narrowly; do not bypass schema validation in production.
- The AST guardrail should enforce the boundary without flagging runtime implementation modules that are intentionally allowed to own process/thread/Hermes details.

## Scope In

- Fix the two review test scaffold failures:
  - `tests/test_parallel_review.py::test_run_parallel_review_supports_zero_checks_with_criteria_side_unit`
  - `tests/test_review_parallel.py::test_run_parallel_review_passes_prior_flags_to_prompt`
- Add `tests/characterization/test_agent_fanout_boundaries.py` or equivalent AST-based guardrail coverage.
- Add `megaplan/py.typed`.
- Remove `scatter_over_worker_step` and `scatter_over_worker_step_process` from `megaplan/orchestration/prep_research.py` if they have no production callers, and update tests accordingly.
- Run focused tests covering prep research, parallel review, worker fanout, Hermes worker option compatibility, import surface, and the new guardrail.

## Scope Out

- Do not start the external-user package polish sprint.
- Do not change model routing, profile semantics, critique/gate logic, or the public API beyond `py.typed`.
- Do not refactor unrelated review, prep, or worker code.
- Do not delete legacy functions outside the two obsolete prep helpers unless a focused test demonstrates they are part of the same debt.
- Do not hide failures with broad skips or try/except wrappers.

## Touchpoints

- `megaplan/orchestration/prep_research.py`
- `tests/test_prep_research.py`
- `tests/test_parallel_review.py`
- `tests/test_review_parallel.py`
- `tests/characterization/test_agent_fanout_boundaries.py`
- `tests/characterization/test_import_surface.py`
- `megaplan/py.typed`

## Done Criteria

Must:

- The two review tests named above pass.
- The new AST guardrail test fails on prohibited phase-level raw fanout/concurrency/Hermes imports and passes for the current tree.
- `megaplan/py.typed` exists in the package root.
- `scatter_over_worker_step` and `scatter_over_worker_step_process` are removed or explicitly justified if a production caller remains.
- Focused test suite passes, including:
  - `tests/test_prep_research.py`
  - `tests/test_parallel_review.py`
  - `tests/test_review_parallel.py`
  - `tests/test_worker_fanout.py`
  - `tests/test_workers_hermes.py`
  - `tests/characterization/test_import_surface.py`
  - new guardrail test

Should:

- Keep changes small and easy to review.
- Preserve the already-completed `elegant-agent-runtime-integration` implementation.

## Anti-Scope

- Do not revisit the previous plan's broader vendoring/API decisions.
- Do not launch another external-polish sprint until this closeout is clean.
- Do not accept review-placeholder or no-inspection outputs as success.
