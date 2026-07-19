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
current double-fenced claim/effect, reconciliation before retry, authoritative
source reread after mutation, exact repair-occurrence validation, cross-host
lease transfer/reclaim safety, event-driven recovery
with p95 accepted repair or typed escalation under five minutes, and independent
evidence before terminal recovery. The six-hour pass remains a missed-event
reconciliation backstop. The
milestone is bounded to two weeks.

This milestone also supplies the exhaustive failure-injection and replay proof
for M6A's transactional WBC store and M8's universal producer adoption.

## In scope

- Execute batch/worker retry, model/provider fallback, watchdog/L1/L2/L3 repair,
  queue/locks/leases/requests, source/install/retrigger, chain/PR/publication,
  resident completion/ordinary/scheduled delivery, provider effects, restart/
  replay, delayed verification, recurrence, and cloud/resident divergence.
- Use WBC effect intents/outcomes and Run Authority decisions/coordinator fences;
  use the M7 custody occurrence/lease/epoch contract for exclusivity. Add no
  second effect, authority, or custody ledger.
- Consume durable block/process-exit events through one deduplicated trigger.
  Validate environment/session, chain, plan revision, phase/task, attempt,
  normalized failure kind, blocker/phase-result hash, managed-worker identity,
  Run Authority grant/fence, lease owner/host/process-birth identity, and custody
  epoch immediately before claim and effect.
- Admit explicitly approved deterministic quality-block families, including the
  captured review-budget-exhausted occurrence, through the same exact-signature
  repair allowlist. If classification or L1 launch fails, persist that failed
  launch as an occurrence and route it to bounded meta-repair/reconciliation;
  “L1 never launched” may not disappear before the six-hour backstop.
- Exercise cross-host acquisition, renewal, orderly transfer, expired-owner
  reclaim, network delay, host death, and restarted process/PID reuse. The old
  epoch must be durably fenced before the new host can perform an effect.
- Terminalize request, claim, lease, attempt, decision, worker link, and custody
  index on success, failure, cancellation, supersession, timeout, or escalation;
  disallow simultaneous accepted repair and executor grants for one attempt.
- Preserve hourly scanning and the deterministic six-hour Maintenance pass only
  for missed-event reconciliation, delayed verification, and audit.
- Fault injection between intent, dispatch/effect, durable outcome, projection,
  authoritative reread, verification, and closure.
- Inject faults before/after WBC reservation, start append, each phase emission,
  effect prepare/commit, outbox handoff, terminal append, payload/reference
  write, migration checkpoint, query, and reconciliation. Cover process kill,
  torn/corrupt record, duplicate/out-of-order event, storage full/permission,
  lost acknowledgement, and mixed-version restart.
- Replay success, validation failure before dispatch, provider/process failure,
  partial fanout, reducer failure, tiebreaker, review/rework, finalize fallback,
  cancellation, suspension/resume, retry, repair, publication and delivery from
  captured WBC traces. Every accepted attempt must remain joinable and reach
  exactly one terminal or explicit indeterminate state.

## Out of scope

New autonomous repair classes, force-proceed, profile redesign, unapproved real
Git/provider/notification/destructive effects, final legacy deletion, or
allowing the daily auditor to become a mutator.

## Locked decisions

Effect intent is durable before execution. Unknown outcomes reconcile against
the target/provider before retry. Post-mutation retry requires current authority
grant/fence and current custody lease/epoch. Swallowed fallback is a visible terminal failure. Repair actors
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
- The generated WBC inventory's failure/replay cases all pass against the exact
  installed runtime. No required writer swallows persistence error, no dispatch
  lacks a durable start, no terminal is lost/duplicated, and reconciliation
  deterministically converges or stays typed indeterminate.
- Migration replay across every supported stored version preserves attempt and
  causal identity, explicit unknowns, retention/legal-hold/encryption metadata
  and effect idempotency; interruption resumes without fabricated success.
- Duplicate dispatch and stale/reclaimed fences are rejected; dead worker leases
  expire without erasing attempts or granting the replacement implicit success.
- Cross-host handoff and reclaim accept exactly one custody epoch; the previous
  host/process cannot renew, complete, cancel, publish, or deliver after transfer.
- Fallback failures, post-mutation retries, partial persistence, restart/replay,
  and cloud/resident divergence reconcile deterministically.
- Parent-owned delivery and scheduled/ordinary outboxes prove at-most-once
  target effects under crash/reclaim while retaining unknown-outcome evidence.
- Only an independent verifier can close recovery after negative control and
  resumed authoritative progress; recurrence reopens with lineage.
- Captured T7/T12 and same-basename fixtures cannot cross-bind; duplicate, late, lost, and out-of-
  order triggers launch at most one current managed repair or remain visibly
  pending for reconciliation.
- The captured M5 `failed: <detail>` review block launches at most one approved
  L1 attempt with machine provenance. Parser loss, dispatch incompatibility,
  and launcher failure each produce a durable failed occurrence that reaches
  bounded L2 or typed human escalation; no layer may report success merely
  because the child process was absent.
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

Dependency: M9 rebuildable views/pure-observer evidence, M6A transactional and
migration substrate, and M8 producer trace inventory. Handoff to M11:
effect/reconciliation registry, exhaustive crash matrix, replay/restart receipts,
event-driven SLO and missed-event proof, exact-signature and terminal-custody
evidence, independent verification and recurrence evidence, repair/worker
canary/kill-switch/rollback proof, genuine-block candidate, and the evidence-
backed list of legacy paths eligible for retirement.

## F01–F17 amendment contract

This milestone supplies end-to-end acceptance for F01, F02, F04, F15, and F16
under failure/replay, plus the effect/recovery portions of R1 and R3. It consumes
the owned M6A/M7/M8/M9 contracts and creates no parallel ledger or queue.

- **Prerequisite:** accepted M9 views/joined ledger, M8 exact producer traces,
  M7 occurrence/lease/epoch/terminal contract, and M6A durable history.
- **First safe action:** produce and run
  `evidence/m10-f01-f17-fault-matrix.json` entirely action-off with fakes,
  covering every persistence, trigger, retry, handoff, verification, and replay
  edge before any separately approved canary.
- **Deliverables:** exhaustive fault/replay receipts, event→request→claim→terminal
  SLO join, terminal-custody closure report, cross-host transfer/reclaim proof,
  exact-signature isolation, independent verification/recurrence evidence,
  missed-event reconciliation, kill switch, rollback, and genuine-block
  candidate package.
- **Acceptance evidence:** no duplicate effect/false closure, one current actor,
  every outcome terminal or typed indeterminate, T7/T12 and same-basename
  isolation, denominated p95 <5m or typed escalation, six-hour recovery of a
  missed event, and no self-verification.
- **Component-versus-wiring safeguard:** enqueue hooks, watchdogs, requests,
  leases, typed reasons, and focused tests do not prove recovery. Acceptance
  requires the exact installed runtime and joined occurrence lifecycle; real
  effects remain unauthorized unless separately approved.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. Unsafe retries and recovery
are timing-dependent, non-local, and can duplicate irreversible effects or
declare false success while ordinary tests remain green.
