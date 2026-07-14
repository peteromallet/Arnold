---
type: brief
slug: m10-safe-retry-recovery-and-effects
title: Effect-safe retry, recovery, replay, restart, and independent verification
epic: custody-control-plane
created_at: '2026-07-13T00:00:00+00:00'
---

# M10 — Safe retry, recovery, and effects

## Outcome

Make retry, fallback, repair, restart/replay, publication, delivery, and provider
effects safe under crashes, partial persistence, and ambiguous outcomes: one
current fenced claim/effect, reconciliation before retry, authoritative reread
after mutation, exact live failure-signature validation, event-driven recovery
with p95 accepted repair or typed escalation under five minutes, and independent
evidence before terminal recovery. The six-hour pass remains a missed-event
reconciliation backstop. The
milestone is bounded to two weeks.

## In scope

- Execute batch/worker retry, model/provider fallback, watchdog/L1/L2/L3 repair,
  queue/locks/leases/requests, source/install/retrigger, chain/PR/publication,
  resident completion/ordinary/scheduled delivery, provider effects, restart/
  replay, delayed verification, recurrence, and cloud/resident divergence.
- Use WBC effect intents/outcomes and Run Authority decisions/fences; add only
  residual reconciliation and custody adapters from M6.
- Consume durable block/process-exit events through one deduplicated trigger.
  Validate environment/session, chain, plan revision, phase/task, attempt,
  normalized failure kind, blocker/phase-result hash, managed-worker identity,
  and fence immediately before claim and effect.
- Terminalize request, claim, lease, attempt, decision, worker link, and custody
  index on success, failure, cancellation, supersession, timeout, or escalation;
  disallow simultaneous accepted repair and executor grants for one attempt.
- Preserve hourly scanning and the deterministic six-hour Maintenance pass only
  for missed-event reconciliation, delayed verification, and audit.
- Fault injection between intent, dispatch/effect, durable outcome, projection,
  authoritative reread, verification, and closure.

## Out of scope

New autonomous repair classes, force-proceed, profile redesign, unapproved real
Git/provider/notification/destructive effects, final legacy deletion, or
allowing the daily auditor to become a mutator.

## Locked decisions

Effect intent is durable before execution. Unknown outcomes reconcile against
the target/provider before retry. Post-mutation retry requires current authority
and fence. Swallowed fallback is a visible terminal failure. Repair actors
cannot self-verify; closure requires a later independent negative control and
resumed authoritative progress.

## Open questions

- What is the approved repair/effect allowlist, lease/grace/retry budget, and
  recurrence window per effect class?
- Which ambiguous external outcomes are queryable, and what safe manual gate
  applies where reconciliation is impossible?
- Who owns independent verification, canary promotion, kill switch, rollback,
  and notification parent/child aggregation policy?
- Which non-compensable effect scenarios can be proven entirely with fakes and
  which need separate operational approval after milestone completion?

## Constraints

Production effects and mutating repair remain action-off unless separately
authorized. No success inference from PID/tmux, commit, green test, activity,
child completion, delivery prose, or mutable status. Rollback preserves causal
evidence, reconciliation, and verification.

## Done criteria

- Crash/fault injection at every in-scope edge causes neither duplicate effect
  nor false success/closure; ambiguity remains visible and bounded.
- Duplicate dispatch and stale/reclaimed fences are rejected; dead worker leases
  expire without erasing attempts or granting the replacement implicit success.
- Fallback failures, post-mutation retries, partial persistence, restart/replay,
  and cloud/resident divergence reconcile deterministically.
- Parent-owned delivery and scheduled/ordinary outboxes prove at-most-once
  target effects under crash/reclaim while retaining unknown-outcome evidence.
- Only an independent verifier can close recovery after negative control and
  resumed authoritative progress; recurrence reopens with lineage.
- Captured T7/T12 fixtures cannot cross-bind; duplicate, late, lost, and out-of-
  order triggers launch at most one current managed repair or remain visibly
  pending for reconciliation.
- Shadow and repair/worker canary measurements prove p95 from durable eligible
  blocker event to accepted repair or typed escalation is under five minutes.
  A deliberately missed event is recovered by the six-hour backstop.
- One genuine supported blocked-run acceptance candidate is prepared with
  allowlist, kill switch, runtime provenance, independent 5m/1h/6h verifier,
  and no mocked status as a substitute; M11 owns controlled execution/acceptance.

## Touchpoints

WBC effect ledger/interfaces, Run Authority fences/views, fallback chains,
execute batches/workers, watchdog/repair/meta-repair/locks/requests,
source/install/retrigger, chain publication/PR/provider adapters, resident
managed/ordinary/scheduled delivery, cloud wrappers, verifier/auditor, and tests.

## Anti-scope

Do not blind-replay or compensate a non-compensable effect, treat liveness as
recovery, let an actor self-record fixed, or introduce a parallel repair/effect
ledger. Do not authorize real external effects with fixture evidence.

## Stop and rollback conditions

Stop on signature/fence drift, duplicate launch/effect, open terminal custody,
self-verification, false resumed progress, p95 SLO breach without a typed
escalation, or a missed event unrecoverable by reconciliation. Rollback disables
triggered effects and promotion but preserves events, open custody, independent
verification, and the scan/six-hour backstop; it cannot blind-retry or restore
sidecar authority.

## Handoff and dependencies

Dependency: M9 rebuildable views and pure-observer evidence. Handoff to M11:
effect/reconciliation registry, exhaustive crash matrix, replay/restart receipts,
event-driven SLO and missed-event proof, exact-signature and terminal-custody
evidence, independent verification and recurrence evidence, repair/worker
canary/kill-switch/rollback proof, genuine-block candidate, and the evidence-
backed list of legacy paths eligible for retirement.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. Unsafe retries and recovery
are timing-dependent, non-local, and can duplicate irreversible effects or
declare false success while ordinary tests remain green.
