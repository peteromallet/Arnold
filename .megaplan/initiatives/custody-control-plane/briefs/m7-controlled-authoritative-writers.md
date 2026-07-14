---
type: brief
slug: m7-controlled-authoritative-writers
title: Controlled authoritative writers and fenced projection boundary
epic: custody-control-plane
created_at: '2026-07-13T00:00:00+00:00'
---

# M7 — Controlled authoritative writers

## Outcome

Route every residual authority-increasing write through the landed Run
Authority decision/fence contract and WBC attempt/effect ledger, with a
registered controlled-writer boundary and downstream projection adapters.
No accepted mutation remains authoritative only in mutable JSON, a marker,
process fact, log, receipt, or sidecar. Scope is no more than two weeks.

## In scope

- Implement the M6 residual controlled-writer registry and enforcement gate.
- Bind plan/chain transitions, overrides/user actions, custody/repair claims,
  publication/delivery decisions, and remaining effect intents/outcomes to the
  prerequisite-owned exact identities without changing their semantics.
- Add fence/lease, idempotency, sequence/CAS, atomic/outbox, partial-persistence,
  dead-letter, reconciliation, and post-write authoritative-reread behavior.
- Make execution, batch, review/rework, repair, and verification evidence
  immutable and attempt-scoped. Current aliases are downstream projections and
  cannot overwrite prior attempts.
- Define the exact attempt-bound repair signature and a signed/content-addressed
  repair receipt containing current grant, plan revision, phase/task contract,
  attempt, tree/commit, tests/results, blocker hash, and fence. Run Authority
  accepts or quarantines it; repair custody remains the dispatch owner.
- Replace projection full-file heartbeat rewrites with cursor-checked append and
  atomic rebuild behavior, preserving the previous complete projection during
  recovery and recording bytes/time for M9.
- Make `state.json`, chain JSON, repair data, status/marker files, and compatible
  journals downstream projections or evidence adapters only.
- Prove old-reader/new-writer compatibility with explicit versions and expiry.

## Out of scope

Creating/replacing the Run Authority kernel, WBC ledger, boundary contracts,
payload store, semantic findings, or lifecycle writer; full reader/UI cutover;
production-wide enablement; destructive effects; broad legacy deletion.

## Locked decisions

Authoritative intent precedes dispatch; durable outcome precedes success; stale
fences reject; persistence ambiguity blocks advancement; projections update
only after accepted authority and remain rebuildable. Late facts append or
reconcile through the owned contract; history is never rewritten.

## Open questions

- Which residual write seams require a transaction versus durable outbox and
  deterministic reconciliation?
- Which payloads remain references under WBC retention/redaction policy?
- What is the compatibility expiry per old reader, and how is direct-write
  rejection staged without restoring dual authority during rollback?
- Which writer enablement cohorts remain shadow-only until M8/M10 proof?

## Constraints

Consume the exact M6-pinned Run Authority/WBC versions. Preserve WBC schemas,
Run Authority acceptance semantics, native topology ownership, and historical
read-only adapters. All production enforcement and mutating effects stay off.

## Done criteria

- The generated residual writer inventory has zero unregistered
  authority-increasing writer; static and runtime bypass attempts fail closed.
- Fault injection at each intent/append/outbox/projection/reread boundary yields
  replayable pending/unknown state, never false success or authority advance.
- Concurrent duplicate dispatch/effect/transition/claim accepts exactly one
  current fenced idempotency identity; stale actors cannot act.
- Replaying prerequisite events plus immutable evidence rebuilds affected
  plan/chain/custody projections deterministically.
- Two review cycles preserve byte-identical attempt 1; a stale T7 repair
  signature cannot bind to T12; every request/claim/attempt/decision/index
  terminal path is joinable without mutable alias inference.
- A 10,000-heartbeat projection stress run produces exactly ordered events, one
  rebuild in the nominal benchmark, monotonic valid concurrent reads, and zero
  false-stall classifications. An idle pinned-runtime canary proves installed
  source provenance before broader projection promotion.
- Old-reader/new-writer fixtures expose version and uncertainty explicitly;
  rollback disables promotion/effects without restoring legacy write authority.

## Touchpoints

Run Authority decisions/views, WBC ledger/effect interfaces, control bindings,
plan and chain state writers, overrides/actions, effect enforcement, repair
claims/leases/data, resident manifests/outbox, publication/delivery adapters,
native persistence, wrappers, compatibility projections, and tests.

## Anti-scope

Do not make the resolver or status projection a writer. Do not introduce a
parallel journal/history, queue, route engine, transition writer, or best-effort
authority append. Do not broaden WBC-owned producer implementation.

## Stop and rollback conditions

Stop on duplicate acceptance/effect, attempt overwrite, stale-fence action,
unjoinable custody, append loss, partial projection visibility, or a second
writer/ledger owner. Rollback disables writer/projection promotion while keeping
append, dead-letter, reconciliation, and evidence readable; it never restores a
legacy authoritative writer or erases a quarantined attempt.

## Handoff and dependencies

Dependency: accepted M6 proof/ownership bundle and approval record. Handoff to
M8: controlled-writer/adaptor registry, fence/idempotency/partial-persistence
conformance, immutable attempt and repair-receipt contracts, projection append/
atomic-rebuild and idle-canary proof, compatibility expiry map, reconciliation
runbook, and proof that no new authority/lifecycle owner was introduced.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. Writer ordering, fencing,
and partial persistence are production-incident-class risks that can duplicate
irreversible effects or advance global state while localized tests remain green.
