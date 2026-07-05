# M6 - Execute Batching Approval Resume

## Objective

Extract execute dependency batching, approval gates, blocked-task recovery, and
partial resume semantics into source-visible structure.

## Scope

In scope:

- deterministic dependency batching over finalized task list;
- stable child checkpoint paths keyed by task ID and batch index;
- destructive/user approval gates;
- no-review terminal routing;
- blocked-task retry and recover-blocked resume;
- partial failure resume.

Out of scope:

- true concurrent DAG execution as a platform optimization.

## Verifiable Completion Criterion

- Execute batching is source/policy visible and deterministic.
- Blocked/partial-failure/resume routes are visible loop branches.
- Scenarios pass:
  - destructive execution denied vs approved;
  - batch 2 of 4 blocks, recover-blocked resumes from batch 2;
  - bare/light no-review terminal route.
- Old execute `components.py` topology contracts and handler-owned route
  decisions are deleted or quarantined for implemented rows.

