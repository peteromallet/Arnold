# Sprint 2 — Port planning to the Pipeline + doc-critique demo

This is Sprint 2 of the megaplan decomposition refactor. The full source
plan is at `.megaplan/briefs/megaplan-decomposition.md` (v2). Sprint 1 shipped the
primitive types + fan-out judges demo + executor (`megaplan/_pipeline/`).
Sprint 2 ports the existing planning flow onto those primitives and
ships the secondary demo (doc-critique 3x loop).

## What ships in Sprint 2

1. Port each existing handler into a `Step` under `megaplan/_pipeline/stages/`:
   - `prep.py` (Produce), `plan.py` (Produce), `critique.py` (Judge),
     `gate.py` (Decide), `revise.py` (Produce), `finalize.py` (Produce),
     `execute.py` (Produce), `review.py` (Judge),
     `tiebreaker.py` (Subloop), `override.py` (Override).
2. Each handler CLI entrypoint in `megaplan/handlers/*.py` becomes a thin
   adapter: parses args, builds a single-stage Pipeline, runs it via the
   executor. Behavior must be byte-identical.
3. Compile `WORKFLOW` + `_ROBUSTNESS_OVERRIDES` + `_with_prep_from_state` +
   `_with_feedback_from_state` + mode dispatch into `Pipeline` instances
   and `Overlay` objects under `megaplan/_pipeline/planning.py`. One
   pipeline per top-level mode (code/doc/joke/creative); overlays apply
   robustness, with_prep, with_feedback.
4. Update `megaplan/auto.py` to walk the Pipeline (not the `WORKFLOW`
   dict). Preserve every existing flag, stall detection, cost cap,
   context-retry, escalate policy.
5. **Delete** `WORKFLOW` and `_ROBUSTNESS_OVERRIDES` from
   `megaplan/_core/workflow.py`. The Pipeline is the single source of
   truth. Keep helper functions (`is_valid_transition`,
   `_RESUME_ACTIVE_STATES`) as wrappers that read from the Pipeline.
6. Ship the doc-critique 3x loop demo at
   `megaplan/_pipeline/demos/doc_critique.py`: critique → revise loop
   with iteration count = 3, on a fixture markdown doc.

## Acceptance tests (all 7 must pass)

1. `tests/test_pipeline_parity.py` — byte-identical artifacts on a
   fixture idea pre/post refactor.
2. `tests/test_pipeline_compose.py` — shipped in Sprint 1, must still
   pass.
3. `tests/test_pipeline_demo_judges.py` — shipped in Sprint 1, must
   still pass and run via the unified Pipeline executor (not the
   prototype runtime).
4. `tests/test_pipeline_doc_critique.py` — 3x critique→revise loop runs
   to completion, iteration count = 3, final doc differs from input.
5. `tests/test_pipeline_resume.py` — kill `megaplan auto` mid-run,
   resume, assert final artifacts identical to uninterrupted run.
6. `tests/test_legacy_phase_cli_compat.py` — `megaplan
   plan/critique/gate/finalize/execute/review` standalone subcommands
   behave unchanged on a fixture plan dir.
7. `tests/test_legacy_profile_compat.py` — every existing profile TOML
   loads + a stage from each slot resolves through the Pipeline without
   error.

## Constraints

- Profile TOML keys unchanged. Primitives bind to slots by name.
- `state.json` schema unchanged. `resume_cursor.phase` continues to name
  the stage.
- All CLI subcommands keep their flag surface.
- The full existing test suite (`pytest tests/`) must stay green.
- `WORKFLOW` dict and `_ROBUSTNESS_OVERRIDES` literally deleted from
  source (single source of truth = Pipeline).
- The system `megaplan` binary (`/Users/peteromalley/.local/bin/megaplan`)
  keeps resolving to the main checkout, not this worktree.

## Out of scope

- Cloud/`megaplan/cloud/` changes.
- Hermes/chain runtime changes.
- Resident scheduler.
- Profile TOML schema (slot names locked).

## Operating principles

Same as Sprint 1. No human review/approval. Self-validating tests.
Blockers via fallback paths; >2 attempts → `BLOCKER-<n>.md`.

## Hard scope limit

If type interfaces from Sprint 1 turn out to be flawed during the port,
extend Sprint 2 by ≤1 week and document the interface change in
`.megaplan/briefs/megaplan-decomposition.md`. Beyond that, write a follow-up brief.
