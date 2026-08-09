---
type: brief
slug: l2-resident-automatic-dual-record
title: Resident and Automatic-Run V2/V3 Dual Recording
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# L2 — Resident and Automatic-Run V2/V3 Dual Recording

## Outcome

Adapt resident delegated agents and automatic watchdog/repair/meta-repair/
auditor/fixer/research workers to emit v3 lifecycle evidence alongside their
existing v2 and delivery contracts. Prove parity, restart adoption, deterministic
compiler roles, no duplicate start/delivery, and one-seam rollback without
moving any permission, repair, conversation, or delivery decision.

## Source and prerequisite

Require an accepted `docs/managed-agents/handoffs/l1-lifecycle-contract.json`
whose hashes and G1-G5 decisions match the implementation revision. Reconcile
project source with the selected resident runtime before edits; preserve runtime-
only context routing, provenance, prompt limits, successor/follow-up, custody,
and terminal-delivery behavior unless an explicitly approved compatible change
supersedes them.

## In scope

- Map resident launch, sealed task/provenance, exact-session follow-up,
  cancellation, process adoption, result persistence, completion verification,
  aggregation/delivery ownership, durable outbox claim/send/receipt, and recovery.
- Map watchdog, repair trigger/queue/loop, meta-repair, progress auditor, goal
  operator, legacy fixer/root-cause/research controller and reasoning-worker
  boundaries; classify authoritative facts versus projections.
- Emit v3 launch/events/projections after the same provider/process start and
  durable source writes used by v2. Dual recording never starts another worker.
- Preserve v2 manifests/readers and existing delivery records. Cross-link v2/v3
  evidence by immutable source identity and `projection_of` rather than copying
  mutable latest paths.
- Assign stable origin/role and compiler policy for primary work, internal
  contributors, synthesis/delivery owners, repair workers, controllers,
  observers, auditors, compiler workers, delivery verifiers, and projections.
- Backfill only verified v2 facts. Missing tokens, ancestry, authority/privacy,
  session, delivery, or evidence range becomes explicit unknown/gap.
- Add a parity reconciler comparing task/caller digest, run/attempt/process/
  provider session, configured/actual route, token/cost confidence, result and
  evidence digests, terminal state, lineage, authority/privacy, delivery owner,
  and provider delivery receipt.
- Add per-origin/per-run-kind flags for old+shadow, v3+dual record, and old-only
  rollback. Routing/profile and lifecycle flags remain separate.
- Emit content-safe parity/anomaly, duplicate suppression, follow-up binding,
  cancellation, adoption, terminal coverage, compiler exclusion, and delivery
  latency diagnostics.

## Out of scope

- Megaplan phase-worker migration (L3).
- Replacing Discord ingress/outbox, changing resident conversation synthesis,
  or letting internal workers deliver.
- Changing repair/watchdog policy, creating a new repair queue, or making
  status/auditor prose authoritative.
- Production enablement, service restart, old-path retirement, or C1-C5 work.

## Locked decisions

- Discord retains inbound/outbound custody; the lifecycle only records opaque
  transport refs and delivery state for the declared delivery owner.
- Resident root conversation and terminal-delivery verification are excluded
  from per-managed-agent semantic compilation.
- Actual repair work is eligible; queue/watchdog/controller/auditor/meta-observer
  prose is excluded. Operational lifecycle events remain visible.
- Same objective follow-up retains run/task identity; changed objective creates
  a linked run. Exact provider-session capability is never guessed.
- Restart/reconciliation adopts one attempt; it never relaunches because a
  projection is missing or stale.
- Rollback preserves v3 evidence and never rewinds a compiler cursor.

## Open questions for the planner

- Which current wrapper rows are controllers, primary repair workers, nested
  contributors, or projections based on source behavior? Record unknown rows and
  require owner adjudication; do not infer from names or prompts.
- Where can dual record join the existing result/outbox transaction safely under
  G2, and where must it be an asynchronous projection with anomaly evidence?
- Which v2 fields have immutable digests today versus only mutable path hints?
- Does each provider support exact follow-up/cancel, and how should explicit
  unsupported status surface without breaking current callers?

## Constraints

- One original execution, one result, and at most one root/user delivery.
- No authorization, work-intent, repair, retry, aggregation, or delivery-owner
  expansion. Child authority/audience only narrows.
- V3 recording failure before cutover is nonfatal and diagnosable; source v2
  result/delivery remains unchanged.
- Tests must use deterministic fakes or sealed fixtures and avoid external sends.

## Touchpoints

Resident `subagent.py`, worker, runtime, agent loop, scheduler, profile,
provenance, query-relationship/currently-running and Discord/outbox surfaces;
`managed_agent.py`; watchdog and repair/meta-repair/auditor controllers/wrappers;
Store/result/delivery transactions; and resident launch/follow-up/cancel/
delivery, repair custody/restart, parity, exclusion, and rollback tests.

## Measurable done criteria

- Representative resident launch/follow-up/cancel/terminal/delivery and every
  automatic managed-run class dual-record once with cross-linked v2/v3 evidence.
- Concurrency/crash/restart tests prove no duplicate provider start, result,
  repair mutation, outbox claim, or user delivery; adoption binds the same attempt.
- V2/v3 parity has no unexplained mismatch for required fields; explicit
  capability gaps and legacy unknowns are durable, referenced anomalies.
- Root-only Discord delivery and non-Discord `not_applicable` delivery remain
  byte- or semantically equivalent; lifecycle/recorder failure cannot block them.
- Every role/exclusion row has source evidence and positive/negative compiler
  classification tests; compiler/auditor/controller/delivery recursion is zero.
- Old-only rollback is one seam flag, leaves accepted v3 evidence readable, and
  passes a rehearsal without duplicate effects.
- `docs/managed-agents/handoffs/l2-v2-v3-parity.json` satisfies the epic handoff
  schema and is reviewed for L3.

## Anti-scope

Do not rewrite resident/Discord delivery, make the worker post to Discord,
change repair admission/authority, infer truth from status/PID/log/prose, launch
twice for parity, or retire v2/start paths.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. Dual-write and
restart behavior can appear correct while duplicating a provider start, repair,
or user delivery.
