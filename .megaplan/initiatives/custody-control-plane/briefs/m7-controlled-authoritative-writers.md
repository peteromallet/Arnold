---
type: brief
slug: m7-controlled-authoritative-writers
title: Controlled authoritative writers and fenced projection boundary
epic: custody-control-plane
created_at: '2026-07-13T00:00:00+00:00'
---

# M7 — Controlled authoritative writers

## Outcome

Consume M6A's operational WBC store/API, define the custody-specific action-
target, repair-occurrence, and renewable lease contract, then
route every residual authority-increasing write through a conjunctive gate over
the landed Run Authority grant/coordinator-fence contract and the current
Custody lease/custody epoch. Required WBC attempt/effect evidence is validated
at the declared boundary, with a registered controlled-writer boundary and
downstream projection adapters.
No accepted mutation remains authoritative only in mutable JSON, a marker,
process fact, log, receipt, or sidecar. Scope is no more than two weeks.

## In scope

- Implement the M6 residual controlled-writer registry and enforcement gate;
  reference WBC attempts/events through M6A's exact API and never duplicate
  their storage in Custody records.
- Add canonical `CustodyTargetKey`, repair-specialized `RepairOccurrenceKey`,
  `CustodyLease`, and append-only `CustodyLeaseEvent` schemas. The lease record
  includes lease ID, exact target/occurrence digest,
  owner/host/process-birth identity, referenced Run Authority
  grant/coordinator fence, monotonic custody epoch, acquisition/expiry,
  idempotency key, and causal predecessor. Events cover acquire, renew,
  transfer, release, expire, fence, conflict, and reconcile.
- Merge existing repair queue request/claim/managed-run binding into this
  lifecycle as admission mechanics: a claim must culminate in one lease or a
  typed non-owner outcome. Queue locks, PIDs, and custody projections never
  become the lease source of truth.
- Bind plan/chain transitions, overrides/user actions, custody/repair claims,
  publication/delivery decisions, and remaining effect intents/outcomes to the
  prerequisite-owned exact identities without changing their semantics. Their
  required WBC writes remain producer scope in M8, not a Custody side channel.
- Require the shared action validator to reread current Run Authority and
  Custody source records immediately before dispatch, repair, completion,
  cancellation, publication, or delivery. It must reject if either fence/epoch
  is stale, missing, expired, transferred, cross-run, or cross-occurrence.
- Add idempotency, sequence/CAS, atomic/outbox, partial-persistence,
  dead-letter, reconciliation, and post-write authoritative-reread behavior.
- Make execution, batch, review/rework, repair, and verification evidence
  immutable and attempt-scoped. Current aliases are downstream projections and
  cannot overwrite prior attempts.
- Define the exact attempt-bound repair occurrence and a signed/content-addressed
  repair receipt containing current grant, plan revision, phase/task contract,
  subject attempt, WBC ledger attempt, tree/commit, tests/results, blocker hash,
  coordinator fence, custody lease, and custody epoch. Run Authority accepts or
  quarantines the claim; Custody remains the lease/dispatch owner; WBC records
  the attempt/effect facts.
- Replace projection full-file heartbeat rewrites with cursor-checked append and
  atomic rebuild behavior, preserving the previous complete projection during
  recovery and recording bytes/time for M9.
- Make `state.json`, chain JSON, repair data, status/marker files, and compatible
  journals downstream projections or evidence adapters only.
- Prove old-reader/new-writer compatibility with explicit versions and expiry.

## Out of scope

Creating/replacing the Run Authority kernel, WBC ledger/API, boundary contracts,
payload store, semantic findings, or lifecycle writer; adding renewable leases
to Run Authority or authority decisions to WBC; full reader/UI cutover;
production-wide enablement; destructive effects; broad legacy deletion.

## Locked decisions

Authoritative intent precedes dispatch; durable outcome precedes success; the
Run Authority coordinator fence and Custody epoch are independent and both must
be current; persistence ambiguity blocks advancement; projections update only
after accepted source records and remain rebuildable. Late facts append or
reconcile through the owned contract; history is never rewritten.

## Open questions

- Which residual write seams require a transaction versus durable outbox and
  deterministic reconciliation?
- Which payloads remain references under WBC retention/redaction policy?
- What is the compatibility expiry per old reader, and how is direct-write
  rejection staged without restoring dual authority during rollback?
- Which writer enablement cohorts remain shadow-only until M8/M10 proof?

## Constraints

Consume the exact M6-pinned Run Authority/WBC versions and M6A transactional
API/migrations. Preserve WBC schemas,
Run Authority acceptance semantics, native topology ownership, and historical
read-only adapters. All production enforcement and mutating effects stay off.

## Done criteria

- The generated residual writer inventory has zero unregistered
  authority-increasing writer; static and runtime bypass attempts fail closed.
- Schema round-trip and relationship tests prove the occurrence identity cannot
  omit or reinterpret any tuple member; leases renew monotonically, transfer or
  reclaim increments the custody epoch, and release/expiry never erases history.
- Fault injection at each intent/append/outbox/projection/reread boundary yields
  replayable pending/unknown state, never false success or authority advance.
- Concurrent duplicate dispatch/effect/transition/claim accepts exactly one
  current double-fenced idempotency identity; stale Run Authority fences,
  expired/transferred Custody epochs, and old-host actors cannot act.
- Replaying prerequisite events plus immutable lease history/evidence rebuilds affected
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

Dependency: accepted M6 proof/ownership bundle, completed M6A substrate, and
machine-verifiable ownership-decision record. Handoff to
M8: controlled-writer/adaptor registry, fence/idempotency/partial-persistence
conformance, immutable attempt and repair-receipt contracts, projection append/
atomic-rebuild and idle-canary proof, compatibility expiry map, reconciliation
runbook, and proof that no new authority/lifecycle owner was introduced.

## F01–F17 amendment contract

This milestone is the primary implementation owner for F01 and F15, adopts the
F06 projection-writer boundary, binds F03 receipt identity, and supplies R1's
Custody half. M10 owns effect/recovery acceptance; M9 owns projection consumers.

- **Prerequisite:** accepted M6A store/API, migrations, exact-version queries,
  and empty substrate-blocker list at the protected M6 vector.
- **First safe action:** keep gates/effects off and generate
  `evidence/m7-occurrence-writer-terminal-map.json` from the controlled-writer
  registry, showing every F01 occurrence field, F15 terminal/outbox edge, F06
  writer/reader provenance, and current Run Authority/Custody reread boundary.
- **Deliverables:** versioned occurrence/lease/epoch schemas, shared action
  validator, immutable repair receipt, controlled-writer and terminal maps,
  append/atomic-rebuild adapter, compatibility expiry map, and reconciliation
  runbook.
- **Acceptance evidence:** T7/T12 cross-binding rejection, one-actor concurrent
  fault matrix, all terminal outcomes joinable, stale fence/epoch and old-host
  rejection, deterministic rebuild, and 10,000-heartbeat concurrent-reader
  proof at an exact installed revision.
- **Component-versus-wiring safeguard:** existing repair IDs, claims, grants,
  custody events, and projection code are precursors. No row is accepted until
  the shared validator and terminal transaction are wired across every
  registered M7 writer; M8 still owns universal producer adoption.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. Writer ordering, fencing,
and partial persistence are production-incident-class risks that can duplicate
irreversible effects or advance global state while localized tests remain green.
