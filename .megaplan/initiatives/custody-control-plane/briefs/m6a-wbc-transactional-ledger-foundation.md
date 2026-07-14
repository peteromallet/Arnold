---
type: brief
slug: m6a-wbc-transactional-ledger-foundation
title: WBC transactional attempt ledger and migration foundation
epic: custody-control-plane
created_at: '2026-07-14T00:00:00+00:00'
---

# M6A — WBC transactional ledger foundation

## Outcome

Turn the exact M6-pinned WBC contract revision into an operational WBC-owned
attempt/effect history: a durable transactional store and process-safe API that
can prove intent/start before dispatch, exactly one terminal outcome for every
accepted attempt, ordered phase/effect evidence, and explicit indeterminate
state after persistence ambiguity. This milestone supplies the substrate for
universal producer adoption in M8; it does not move grants, lifecycle mutation,
leases, repair policy, or status authority into WBC. Scope is no more than two
weeks.

The observed completed WBC candidate defines a schema-only
`ExecutionAttemptLedger`; its support manifest is not proof that production
runtime paths persist those events. M6A is therefore required and cannot be
waived by schema tests, declared support, or manually asserted coverage.

## In scope

- Implement a WBC-owned `AttemptLedgerStore`/service API over the exact landed
  schemas, with append/read/query/reconcile operations, stable attempt and
  event identity, monotonic ordering, cross-event idempotency uniqueness,
  exactly-one-terminal validation, and rejection of post-terminal events.
- Persist an accepted attempt reservation and `started` event before any
  worker/provider/process dispatch. The API must make “durable start exists” a
  precondition of dispatch rather than a best-effort afterthought.
- Persist `completed`, `failed`, `cancelled`, or explicit `indeterminate`
  outcome before any caller may report terminal success or advance a dependent
  boundary. Empty or non-terminal accepted attempts remain incomplete.
- Define the transaction boundary for lifecycle intent, WBC append, and
  external-effect intent. Where a single transaction is impossible, use a
  durable outbox or prepare/commit protocol with deterministic reconciliation;
  never silently skip a sequence gap or swallow an append failure.
- Provide process-safe adapters for Python and shell/wrapper seams, including
  signal/crash handling, so resident, cloud, repair, provider, and managed-agent
  paths can adopt one API rather than inventing local writers.
- Implement exact-version queries needed by consumers: attempt status,
  required boundary/effect evidence, gaps, persistence diagnostics,
  reconciliation state, and source cursor. Queries return typed
  `INDETERMINATE`/`INCOHERENT`, never optimistic defaults.
- Implement the WBC payload/reference policy rather than only validating its
  metadata: tenant/access checks, redaction, encryption-required enforcement,
  key/version audit references, retention/expiry, legal hold, tombstone and
  deletion evidence, and safe digest-only behavior. Encryption may not silently
  default to none for protected classes.
- Add a deterministic storage/schema migration and backfill framework with
  versioned migrations, checksums, crash-resume, mixed-version reads, rollback
  or forward-fix rules, and explicit classification of legacy records that
  cannot be reconstructed. Never synthesize successful history from old status
  files or logs.
- Emit machine-readable append/query/reconciliation traces keyed to the M6
  boundary inventory. These traces are evidence inputs; they are not authority
  or mutable support declarations.

## Out of scope

Run Authority grants/decisions/fences, lifecycle transition ownership, Custody
leases/epochs/transfer/recovery, repair scheduling, universal call-site
migration, status/UI cutover, production rollout, and legacy deletion. M8 owns
all producer adoption, M9 owns consumers, M10 owns the exhaustive crash/effect
matrix, and M11 owns integrated conformance and retirement.

## Locked decisions

- WBC remains the sole owner of its attempt/effect history, schemas, payload
  policy, and conformance. Custody consumes WBC references and must not create a
  competing ledger.
- A durable start is written before dispatch; a durable terminal or explicit
  indeterminate outcome is written before success/advancement. Required writes
  are never “evidence-only,” “without raising,” best-effort, or fail-open.
- Persistence ambiguity blocks advancement and produces joinable diagnostic and
  reconciliation evidence. It never becomes an empty receipt, inferred success,
  or a mutable status fallback.
- Every read and write binds the M6-pinned landed contract, code/config/adapter,
  run, attempt, tenant, and causal identity. `latest` is not a contract version.
- Keep the M6-pinned base-contract revision distinct from M6A's approved WBC
  substrate/API revision and every adopter/runtime revision. If store/API work
  requires a schema or contract change, obtain an explicit WBC-owner handoff and
  regenerate conformance/support evidence; do not mutate the pinned prerequisite
  under a Custody branch identity.
- WBC evidence never supplies a Run Authority grant or a Custody lease.

## Open questions

- Which repository-supported transactional backend is selected, and which
  lifecycle/effect joins require outbox or prepare/commit rather than one local
  transaction?
- What are the approved retention periods, privacy classes, encryption/key
  authority, legal-hold owner, deletion approver, and historical-read expiry?
- Which legacy records can be losslessly backfilled, which remain read-only
  `UNKNOWN`, and what migration reversibility is required per deployed cohort?
- Which process boundaries require a local daemon/service versus an embedded
  store without weakening cross-process ordering?

## Constraints

Start only after M6 has bound the exact final landed WBC revision, proven the
landed/source/editable/runtime identity current, generated the zero-exemption
inventory, and recorded accepted human approval. Do not infer that revision
from the topic-branch candidate alone: verify audited merge `24afce00…`, current
main containment, and the separately recorded runtime vector. Production
enforcement, deployment, restart, and external effects remain disabled.

## Done criteria

- The store survives process kill/restart and concurrent writers while
  preserving monotonic ordering, unique idempotency, exactly one terminal, and
  no accepted event after terminal.
- Dispatch cannot occur unless its durable attempt reservation/start is
  queryable; completion/advancement cannot occur unless a durable terminal or
  typed indeterminate outcome is queryable from the same exact-version stream.
- Fault injection at reserve, start, prepare, dispatch boundary, append,
  commit, outbox delivery, payload write, terminal, query, and reconciliation
  yields a replayable pending/indeterminate state and never false success or a
  duplicate external effect.
- Payload tests prove access isolation, redaction, encryption-required failure,
  key/version audit references, retention expiry, legal hold, tombstone,
  deletion evidence, and secret rejection against stored bytes—not metadata
  schemas alone.
- Migration tests cover empty/new stores, each supported legacy version,
  interrupted upgrade/resume, duplicate backfill, mixed old/new readers and
  writers, corrupt/partial records, downgrade/forward-fix policy, and records
  that must remain explicitly unknown.
- Static negative checks find no second WBC store/API and no required-write
  adapter that catches and suppresses persistence failure. Runtime tests prove
  the API emits content-addressed traces for every exercised inventory row.
- The M6 matrix rows for ledger/API/payload/migration are `implemented` with
  implementation commit, storage migration, fault-test, runtime-trace, and
  rollback evidence. A support manifest or unit schema suite alone cannot set
  them complete.
- The handoff records immutable base-contract revision, approved WBC substrate/
  API revision, implementation commit/tree, migration version and exact
  installed/editable/cloud/resident runtime vector as separate fields.

## Touchpoints

The landed WBC `arnold.workflow` contracts and Megaplan adapters; persistent
storage/migrations; process and wrapper adapters; lifecycle/outbox integration;
payload/reference storage, privacy/retention/encryption services; trace tooling;
legacy readers; generated inventory; and tests.

## Anti-scope

Do not fork or rename the WBC contract family, create a Custody-owned attempt
ledger, collapse lifecycle/authority/custody into the WBC transaction, or mark
all declared contracts adopted because the store exists. Do not backfill a
terminal success from prose, a marker, a receipt, or mutable state.

## Stop and rollback conditions

Stop on lost/reordered events, multiple terminals, post-terminal acceptance,
cross-tenant reads, unencrypted protected payload, non-resumable migration,
silent persistence loss, optimistic query fallback, or a second ledger owner.
Rollback disables new dispatch/promotion and preserves the new store,
diagnostics, outbox, and reconciliation state; it cannot restore a best-effort
writer or erase an ambiguous attempt.

## Handoff and dependencies

Dependencies: M6 exact landed WBC revision/runtime proof, generated boundary
inventory, accepted approval record, and unchanged ownership decision. Handoff
to M7/M8: explicit WBC-owner substrate handoff, versioned store/API and migrations, payload-policy implementation,
transaction/outbox contract, exact query semantics, process-safe adapters,
fault/replay evidence, runtime trace format, and an empty substrate-blocker list.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. Transaction ordering,
crash ambiguity, privacy, and migration faults are non-local and can make every
later adopter look conformant while evidence is missing or false.
