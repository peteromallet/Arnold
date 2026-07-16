---
type: brief
slug: m2-trigger-lifecycle
title: Durable Cursors, Jobs, Leases, and Trigger Lifecycle
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M2 — Durable Cursors, Jobs, Leases, and Trigger Lifecycle

## Outcome

Build the durable eligibility and checkpoint lifecycle on M1's exact source
ranges: threshold and terminal triggers, atomic successful cursors, idempotent
jobs/leases/attempts, restart recovery, and status diagnostics that remain
harmless to the managed session.

## In scope

- Consume the M1 identity/position API without inventing a second source model.
- Persist last-successful range, eligibility, job, lease, attempt, trigger kind,
  compiler/schema generation, failure, and retry state.
- Trigger at roughly 100,000 newly persisted tokens and on completed, failed,
  cancelled, and superseded transitions even below threshold.
- Reserve optional idle policy as disabled by default; implement only through
  the same eligibility/idempotency path.
- Derive deterministic idempotency keys and atomic claim/commit behavior for
  concurrent sweeps, duplicate delivery, restart, and partial failure.
- Advance the successful cursor only after an entire checkpoint transaction is
  accepted; failed attempts remain visible and retryable.
- Expose eligible, queued, claimed, compiling, failed, retryable, and successful
  diagnostics plus bounded operator retry.
- Produce `docs/session-knowledge-compiler/handoffs/m2-checkpoint-commit.md`.

## Out of scope

LLM invocation, four derived record schemas, semantic validation, synthesis,
search, promotion, backlog consolidation, and broad rollout.

## Locked decisions

- Threshold means new persisted tokens since the last successful checkpoint.
- Terminal eligibility is mandatory below threshold.
- Checkpoints/source ranges are immutable; cursor and accepted checkpoint form
  one atomic logical commit.
- Compiler failure never changes or delays primary-session terminal delivery.
- Duplicate triggers and retries must be harmless.

## Open questions

- Can existing scheduler leases satisfy crash/expiry semantics without a queue?
- What transaction boundary works identically across file and DB stores?
- How are late-arriving events after terminal eligibility represented?
- Is the idle schema-only reservation preferable to an implemented disabled job?

## Constraints

- Use existing Store transaction/migration patterns; no unmanaged ledger.
- Fail closed on cursor ambiguity and preserve failed-attempt evidence.
- No external network in concurrency/restart tests.
- Backward-compatible loading for sessions with no compiler lifecycle state.

## Done criteria

- Tests prove one threshold trigger, no trigger below threshold, and all locked
  terminal triggers below threshold.
- Restart, duplicate, concurrent sweep, lease expiry, partial write, retry,
  out-of-order persistence, and token reset tests skip/double-count no range.
- Forced compiler-job failure leaves session result/delivery unchanged and the
  successful cursor stationary.
- M2 handoff documents the transaction M3 must join when persisting records.

## Touchpoints

M1 contracts, resident scheduler/runtime/subagent paths, managed-agent lifecycle,
Store file/DB transactions and migrations, diagnostics, and focused concurrency,
resident, store, and managed-agent tests.

## Anti-scope

Do not add extraction prompts, derived content, search, tickets, generalized
scheduler replacement, transcript deletion, or unrelated Run Authority changes.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m1-capture-contract.md`,
landed schema/migrations, backend fixtures, and passing identity/range tests.
M1 supplies identities and positions; M2 alone owns lifecycle state.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`;
directed prep enabled. Transaction ordering and concurrency bugs can look correct
locally while permanently consuming or duplicating evidence.
