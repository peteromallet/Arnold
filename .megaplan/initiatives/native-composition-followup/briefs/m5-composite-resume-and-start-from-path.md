# M5 - Composite Resume And Start From Path

## Objective

Make resume work through nested workflows and loops using path as the primary
address. A run suspended inside a child workflow must resume at the child path
with parent context restored. Tooling should support replay-injection and
start-from-path using real prior run history.

## Files To Change And Instructions

- `arnold/pipeline/native/checkpoint.py`
  Extend cursor shape for composite parent/child frames while preserving
  fail-closed native cursor validation. Path is the primary resume locator; PC
  is a validation/fallback detail, not the only address.
- `arnold/pipeline/native/runtime.py`
  Restore parent and child execution context from composite cursors. Resume from
  inside child workflows and loops without re-running completed steps. Check a
  default no-op cancellation sentinel between step boundaries so graceful cancel
  can be threaded in later without rewriting parent/child execution.
- `arnold/pipeline/native/trace.py`
  Mark suspension and resume events at the path where they occur.
- `arnold/pipeline/resume.py`
  Route native path-based resume through the native runtime contract. Preserve
  or migrate existing Megaplan resume file surfaces: `state.json::resume_cursor`,
  `resume_cursor.json`, `composite_resume_cursor.json`, `awaiting_user.json`,
  typed suspended `contract_result`, and fail-soft extraction.
- `tests/arnold/pipeline/native/`
  Add kill/suspend/resume tests for child workflows, loops inside child
  workflows, repeated child call sites, depth-3 nested resume, and loop
  iteration paths.
- `tests/arnold/pipelines/megaplan/`
  Prove Megaplan can resume from inside its compositional critique/revise,
  tiebreaker, execute/review, and human-gated paths. Include backward-compatible
  tests for every existing Megaplan cursor source and for human-gate continue
  repointing the primary input to the latest edited artifact.

## Verifiable Completion Criterion

- Resume from inside a nested workflow succeeds without duplicating completed
  side effects.
- Resume from inside a loop inside a nested workflow succeeds, with loop frames
  scoped by path rather than bare loop name.
- `kill -9` / process interruption during a child workflow phase can be resumed
  with parent and child context restored.
- Start-from-path using real prior run recorded results works for at least one
  nested Megaplan path and one neutral native fixture.
- Existing Megaplan resume file surfaces either continue to work through
  `arnold.pipeline.resume` or fail closed with a migration diagnostic; no
  existing cursor file is silently ignored or interpreted as a different path.
- Human-gated continue preserves the current behavior of resuming from the
  user's latest edited artifact rather than stale pre-gate input.
- Synthetic injection remains clearly marked as test/debug-only and validates
  supplied state against declared interfaces where available.
- Replay-consistency CI covers at least one nested loop: run uninterrupted, run
  with interruption/resume, and assert equivalent final structure/state.

## Risks And Blockers

- Side effects do not replay. This milestone must test idempotency expectations
  for side-effecting steps, but full git/worktree reconcile belongs to the
  platform follow-up epic.
- A path-addressed cursor that cannot be validated must fail closed, not fall
  back to a different execution engine.
- Repeatable-not-deterministic remains replay-by-default in this epic. Any
  future re-decide mechanism must be explicit and excluded from structural
  golden equality.

## Dependencies

- Depends on M3 and M4.
