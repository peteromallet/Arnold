# S4 - Execute DAG, Approval, Resume

## Objective

Extract execute dependency batching, approval gates, blocked-task recovery,
partial resume, and no-review terminal behavior into source-visible structure.

## Legacy 10-Sprint Source Mapping

- Absorbs `m6-execute-batching-approval-resume.md`.

## Scope

In scope:

- deterministic batching over finalized task list;
- stable child checkpoint paths keyed by task ID and batch index;
- recomputation of ready batches if blocked tasks mutate dependencies;
- destructive/user approval gates;
- no-review terminal routing for bare/light robustness;
- blocked-task retry and recover-blocked resume;
- partial failure resume;
- boundary contracts for batch checkpoints, approval/denial authority records,
  blocked/resume anchors, side-effect evidence, retry writes, and reducer
  promotion of aggregate execute results;
- cancellation/await/orphan semantics for parallel children when fallback runs
  sequentially.

Out of scope:

- true concurrent DAG execution as a platform optimization. Deterministic
  batching is enough if source/policy visible and resume-stable.

## Work Required

- Make execute batching source/policy visible and testable as a pure function
  over finalized tasks.
- Keep batch command execution phase-local; route only through typed outcomes.
- Add stable checkpoint contract tests.
- Make blocked/partial-failure/resume routes explicit loop branches.
- Preserve idempotence for artifacts, debt records, and retry-after-partial
  writes.
- Emit or verify receipts for each execute batch and aggregate promotion so a
  stale checkpoint, missing side-effect ref, missing approval authority, or
  reducer-without-child-evidence is a semantic-health failure.
- Delete or quarantine old execute component topology and handler-owned route
  decisions for implemented rows.

## Verifiable Completion Criterion

- Scenarios pass:
  - destructive execution denied suspends, approval proceeds;
  - batch 2 of 4 blocks non-retryably, recover-blocked resumes from batch 2
    with identical checkpoint paths;
  - bare/light no-review terminal route works.
- Checker rejects handler-owned execute route decisions and hidden scheduler
  branches.
- Installed-package execution follows the same source-derived execute topology.
- Boundary tests cover child output without reducer promotion, reducer
  promotion without required child evidence, and approval/resume records that
  are stale or missing.

## Do Not Close If

- Batch ordering depends on dict order, timestamps, or non-stable child paths.
- Auto-drive or a handler independently decides the next execute route.
- Boundary/checkpoint records become a second scheduler or route table.
