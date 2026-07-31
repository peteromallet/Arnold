---
id: 01KYMWFKQ93BY6FVRT64272HQC
title: Contain post-M11 launch and fixer custody until platform adoption
status: open
source: human
tags:
- bug
- superfixer
- custody
- recovery
- observability
- quality-gate
- managed-invocation
- post-m11
- native-platform-consumer
- containment
- do-not-wait-for-platform
codebase_id: null
created_at: '2026-07-28T17:31:11.978059+00:00'
last_edited_at: '2026-07-30T15:28:19.598177+00:00'
epics: []
---

## Scope: post-M11 containment only

This ticket stops the current custody/fixer bleeding. Native platformization
owns the reusable process, lease, invocation, broker, and fleet abstractions.

## Immediate work after the custody epic

- Make supervisor, simple fixer, operator resume, and force-proceed consume the
  same existing repair occurrence and custody epoch.
- Ensure deterministic phase-contract failures such as
  `rework_wave_exceeds_ceiling` produce one claimable repair request; prove the
  singleton fixer either performs the legal recovery or records a typed
  non-action reason.
- Treat dead worker plus live tmux, stale heartbeat, PID reuse, and stopped
  runner as repairable broken state, never healthy execution.
- Bind repair to the exact session, newest nonaccepted plan, plan revision,
  editable runtime, and legal `recover_via`; wrong-target M10 evidence cannot
  satisfy M11 recovery.
- Require one fresh runner plus accepted same-target progress before declaring
  success. Bookkeeping, event growth, or milestone movement is insufficient.
- Preserve secret values outside markers/tickets/prompts and check only named
  credential/config availability.
- Reconcile current runtime hot fixes into the custody release branch and keep
  one singleton mutation-authorized fixer during the transition.

## Platform handoff

Native platform M2/M4/M5 owns broker-held credential handles, durable
invocation/event storage, process birth identity, worker leases and handoff,
exit events, adoption, cancellation, and fleet supervision. This ticket must
leave only a narrow Megaplan adapter over those mechanisms: repair-occurrence
identity, legal recovery selection, fixer prompt/policy, force-proceed
reconciliation, and proof that the blocker cleared.

## Acceptance

1. Replay the M11 unconsumed deterministic failure and prove one occurrence,
   one fixer claim, one recovery action, one runner, and accepted progress.
2. Duplicate receipts do not create duplicate fixers or runners.
3. Dead PID/live tmux and PID-reuse fixtures classify consistently everywhere.
4. Runtime/config mismatch fails closed without revealing credentials.
5. Every mutation and relaunch has a durable receipt tied to the same target.

## Non-goals

- A second control plane, lease system, worker supervisor, credential broker,
  or repair queue.
- Implementing platform M2/M4/M5 inside Megaplan.
- Reopening M11.

## M11 recurrence 2026-07-30

The live plan was `blocked`, with no worker and a current repairable quality-circuit receipt, while cloud status classified the custody chain `complete`. The three-hour fixer therefore had no truthful target to claim. After legal recovery, `chain start` consumed a full CPU core recomputing the 57k-event accepted-attempt projection for minutes and did not dispatch execute; direct legal `execute` through the same pinned runtime started attempt 67 immediately.

Containment must make newest nonaccepted plan state outrank chain-complete projections, enqueue one occurrence on this disagreement, and bound/cache authority projection by source cursor so supervision never performs an unbounded O(events x attempts) recomputation before dispatch. Acceptance must replay this exact blocked-plan/complete-chain contradiction and prove automatic fixer claim plus worker start.
