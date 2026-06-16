# MiMo-only metaplan: duplicate distributed workflow attempts

## Outcome

Produce a design/migration plan for fixing duplicated long-running agent tasks in a distributed CI workflow. The plan must be concrete enough for a later code-mode implementation sprint: it should name the state model, ownership/fencing rules, supervisor reconciliation algorithm, migration steps, and tests.

## Problem

The system runs agent tasks in isolated worktrees. A supervisor polls task state every 30 seconds and may restart tasks that have not emitted progress for 10 minutes.

Each task writes:

- `events.jsonl` for heartbeat/progress events
- `result.json` as an atomic final output: write `result.json.tmp`, fsync, rename to `result.json`
- `state.json` with `status: running | succeeded | failed`

Observed incident:

1. About 1 in 80 long-running tasks is duplicated.
2. The duplicate usually starts 10-15 minutes after the original task began.
3. In duplicated cases, `events.jsonl` often contains heartbeat lines from the original task until seconds before the duplicate starts.
4. Sometimes both original and duplicate eventually write `result.json`. The later write wins, but it is not always from the duplicate.
5. `state.json` is occasionally left as `running` even when `result.json` exists.
6. There is no evidence of process crashes in OS logs.

A teammate proposes: "Increase the stale timeout from 10 minutes to 45 minutes and add a lock file named `task.lock`. A task creates the lock at startup and deletes it on exit. The supervisor should not restart if `task.lock` exists."

## Required Judgment

Reject or accept that proposed fix explicitly. If rejecting it, explain why it is insufficient and what minimal design should replace it.

The plan must address:

- Why observation 3 matters: recent heartbeats near duplicate start weaken a simplistic "task stopped heartbeating for 10 minutes" explanation.
- Stale-writer protection: an old/original attempt must not be able to overwrite or publish over a newer valid attempt.
- Attempt identity: every task attempt needs an identity that appears in heartbeats, state, and outputs.
- Fencing or compare-and-swap semantics: only the currently owned attempt may promote a terminal result.
- Recovery: if `result.json` or equivalent terminal output exists while `state.json` says `running`, supervisor reconciliation must converge without duplicating work.
- Cleanup: stale attempts/worktrees must be recoverable without orphaned lock files causing permanent hangs.

## Locked Decisions

- Do not solve this by only increasing stale timeouts.
- Do not use a bare create/delete lock file as the authority.
- Prefer attempt-scoped outputs or a promotion manifest over multiple attempts writing the same final `result.json` path directly.
- Treat `events.jsonl` as evidence, not sole authority.
- The deliverable for this run is a prose design document, not code changes.

## Done Criteria

The final document must include:

- Root-cause hypotheses with observations supporting or contradicting each.
- A ranked critique of the proposed timeout plus lock-file fix.
- A minimal replacement design with explicit invariants.
- File/schema sketch for attempt ownership, heartbeat, result promotion, and reconciled state.
- Supervisor algorithm pseudocode.
- Migration/rollout steps with backward compatibility for existing worktrees.
- Tests, including stale writer, supervisor crash, task crash between result and state update, concurrent supervisor poll, and heartbeat freshness edge cases.

## Anti-scope

- Do not implement the design in this sprint.
- Do not refactor unrelated megaplan pipeline code.
- Do not assume an external consensus service unless the plan explains why local filesystem fencing is insufficient.
