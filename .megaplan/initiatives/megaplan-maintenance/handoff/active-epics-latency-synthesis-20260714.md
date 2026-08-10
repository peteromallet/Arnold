# Active epics latency synthesis

Snapshot: **July 14, 2026 at 10:34:17 UTC (+00:00)**

Auditable runs:

- Transaction Spine contributor: `subagent-20260714-101356-39ea719f`
- Strategy Roadmap contributor: `subagent-20260714-101356-fc5f6cae`
- Synthesis owner: `subagent-20260714-101421-463e5e9c`

## Verified outcome

Both contributor manifests reached `completed`, and their durable results and
evidence reports were consumed. At the snapshot, the canonical display state
for both active plans was `executing`; neither plan was restarted or killed.

Transaction Spine attempt 4 had a fresh active-step start at 10:33:58 and
activity at 10:34:02. Strategy Roadmap attempt 2 had activity at 10:34:13 and
introspection reported a one-second-old event. Transaction introspection
nevertheless reported `stalled` from a 990-second-old event. This contradicts
the active-step evidence and reproduces the non-atomic compatibility-journal
race found by the Transaction Spine investigation. An earlier Strategy read at
10:28:07 produced the same false-stall shape while its journal, state, and token
heartbeats were updating. Canonical `display_state` plus direct activity
evidence therefore governs this snapshot; raw liveness is degraded until the
projection fix is deployed.

## Consolidated causal model

### Legitimate workload

- Strategy M4 produced 8,327 additions and 41 deletions across 20 files. Its
  2h03m17s first execute was 99.6% enclosed by 15 worker calls; this was mostly
  real implementation rather than queue idle. The 7m56s review found five
  deterministic defects missed by scoped passing tests and should remain.
- Transaction Spine's stopped attempts also produced real implementation and
  two useful repairs. The three stopped execute attempts consumed 3h27m40s,
  $3.12684, and 40.7M input tokens, but that total must not be labelled waste.

### Instance-specific avoidable latency

- Transaction Spine admitted a 30-task, 29-edge serial chain. Complexity-7 T7
  and T12 each exhausted the same 90-iteration ceiling after implementing the
  core change but before required proof tests. Four later complexity-8/9 tasks
  remain recurrence risks. Hourly detection added 1h38m44s, and non-adoptable
  repair results forced at least about 65 minutes and $1.3234 of duplicate
  executor workflow. A stale T7 repair request was paired with the T12 blocker.
- Strategy Roadmap lost 2h09m before the first successful runtime refresh to an
  invalid `editible-install` ref and dirty-source retries. M4's finalized DAG
  serialized all 15 tasks, including three validation-only model calls totaling
  6m31s. One GLM turn lasted 50m20s and included at least 10m of streaming
  timeout wait, repeated invalid summary-model requests, and target/runtime
  import confusion. Six rework tasks were dispatched together despite a
  five-task ceiling, and mutable legacy aliases overwrote attempt history.

### Shared systemic roots

1. Planning admits fully serial DAGs and high-complexity contracts without a
   critical-path/turn-budget feasibility gate.
2. Execution couples implementation, proof, and repeated mechanical validation
   into expensive model turns; repair receipts cannot become verified task
   checkpoints.
3. Retry, timeout, compaction, and provider failover budgets do not bound waste.
4. Recovery is scan-driven, repair identity is not revalidated against the live
   failure signature, and request/claim/attempt custody is not reliably closed.
5. Current state is projected independently into plan, chain, cloud, repair,
   and introspection views; stale `finalized`/`between_milestones` values coexist
   with live execution.
6. Attempt artifacts are mutable aliases rather than append-only evidence.
7. Every heartbeat rewrites a growing compatibility journal non-atomically,
   adding quadratic write amplification and allowing readers to see partial
   history and falsely classify live work as stalled.

### Inference and measurement limits

- Full-journal writes likely add I/O contention, but no production timer assigns
  exact latency to them.
- Strategy compaction/import churn and the productive fraction of the 50-minute
  GLM turn are not separately timed.
- Productive versus replayed Transaction tokens are inferred conservatively;
  no authoritative per-task cost ledger exists.
- Repair/developer-model tokens and costs, immutable attempt terminal times,
  provider-internal attempts, and some review costs are absent.

## Safe fixes and verification

The isolated branch `fix/transaction-spine-event-projection-20260714`, based on
the active chain runtime revision, contains:

- `3221870c965f086691610321b41b126f4aff3266`: replace full-journal heartbeat
  rewrites with cursor-checked appends and atomic rebuild recovery.
- `0a31d539ca`: deterministic regression proving a rebuild leaves the previous
  complete destination visible until atomic replacement.

Synthesis verification:

- 19 focused projection/concurrency/liveness/doctor tests passed.
- All 15 observability tests passed; `compileall` and `git diff --check` passed.
- A 10,000-heartbeat benchmark produced exactly sequences 0..9999, one rebuild,
  cursor 9999, and a valid 6,867,780-byte projection in 21.329s.
- A forced cursor-mismatch stress run with a concurrent reader produced 2,000
  events, 17,966 read samples, monotonic counts, and zero failures.

The branch is local only. It was not pushed, merged, deployed, hot-loaded, or
used to restart a chain. The dirty resident checkout and live project trees were
preserved.

## Prioritized prevention and acceptance plan

### P0: current recovery and correctness

1. **Observability owner — event projection.** Review and land `3221870c` plus
   `0a31d539ca`; canary on an idle runtime before controlled deployment.
   Acceptance: 10k heartbeats cause one rebuild plus O(event-size) appends;
   concurrent reads remain valid and monotonic; no live plan is falsely stalled.
2. **Cloud repair owner — exact incident custody.** Dispatch only when session,
   plan revision, task, normalized failure kind, and phase-result hash match the
   live blocker. Supersede stale requests and terminalize request, claim, attempt,
   decision, and index records. Acceptance: a T7 request cannot bind to T12;
   every terminal path has one closed custody chain and `attempt_ids` entry.
3. **Operator/control owner — event-driven unblock.** Emit a durable repair
   trigger on blocked/process-exit events; keep hourly scans only as reconciliation.
   Acceptance: p95 block-to-accepted-repair <5m, deduplicated delivery, and a
   missed-event fixture recovered by the scan.
4. **Worker owner — current Strategy hazards.** Resolve a valid summary model,
   sanitize target worker imports, fail over after one repeated 300s timeout,
   and split six-task rework to the configured ceiling. Acceptance: empty-model,
   divergent-checkout, timeout, and six-task fixtures converge without repeated
   compaction, target/runtime import leakage, or oversized dispatch.

### P1: plan and execution hardening

5. **Planner/finalizer owner — semantic DAG and feasibility gate.** Require a
   reason on every dependency, separate `routing_group` from `depends_on`, report
   critical-path seriality, and reject unexplained 100% serialization for eight
   or more tasks. Complexity >=7 must split implementation from proof or receive
   an explicit larger turn budget. Acceptance: replaying both finalized plans
   flags the serial chains and produces safe independent waves.
6. **Executor owner — verification deduplication and circuit breaker.** Convert
   no-file validation-only tasks to harness jobs. Normalize
   `worker_budget_exhausted` across task IDs and open a plan circuit after two
   occurrences; split or raise budget explicitly rather than replay. Acceptance:
   Strategy T10/T12/T15 cause no model calls, and Transaction T7+T12 opens the
   circuit before a third blind retry.
7. **Evidence owner — immutable attempts and adoptable repairs.** Write
   attempt-scoped batch/execution/review artifacts and signed repair receipts
   containing plan revision, task contract, commit, and tests. Use a verify-only
   adoption path; mismatch falls back to normal execution. Acceptance: two
   review cycles preserve byte-identical attempt 1, and valid repaired work is
   not fully replayed.
8. **Launcher owner — startup circuit breaker.** Validate a remote ref once,
   suggest a valid ref, and stop after a bounded retry count; prove detached
   runtime revision before installation. Acceptance: an invalid ref cannot
   consume hours or trigger repeated starts.

### P2: canonical architecture, telemetry, and proof

9. **State-authority owner — one reducer.** Derive plan, chain, cloud, repair,
   and introspection status from one attempt-aware authoritative reducer where a
   live active phase supersedes stale terminal projections. Acceptance: review
   rework is `executing attempt 2` everywhere, with 100% projection agreement.
10. **Telemetry owner — latency ledger.** Emit task/batch/attempt IDs and separate
    queue, session-start, inference, tool, test, retry-wait, compaction, git,
    transition, repair, verify, and replay time plus calls/tokens/dollars and
    source/runtime revisions. Initial SLOs: transition p95 <30s; retry wait <=10%
    of execute; context compactions <=1/turn; artifact overwrites 0; no zero-cost
    phase without an explicit unavailable reason.
11. **Auditor owner — deterministic reasons.** Add exact-match reasons for
    consecutive normalized blocks, signature drift, unclosed custody, index
    mismatch, detection-SLO breach, executor/repair overlap, cross-session joins,
    projection amplification, full seriality, oversized rework, and invalid
    summary models. Acceptance: fixed fixtures fire once with exact evidence IDs
    and never match a same-basename unrelated session.

Rollout order: append-only evidence and telemetry in shadow; deterministic replay
tests using both captured plans; projection idle canary; worker/rework canary;
controlled runtime deployment with recorded source and wrapper SHAs; then one
real blocked-run acceptance. Compare before/after critical-path calls, replayed
tokens, retry/compaction time, detection delay, projection bytes, artifact hashes,
and cross-view state agreement before enabling planner/recovery gates.
