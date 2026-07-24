---
type: decision
slug: m10-m11-structural-conformance-closure-20260723
title: M10/M11 structural conformance closure and exact-launch amendment
epic: custody-control-plane
created_at: '2026-07-23T00:00:00+00:00'
---

# M10/M11 structural conformance closure

## Decision

The July 22–23 recovery incidents are structural conformance failures, not a
collection of isolated operational mistakes. M10 must close every action-path
and recovery-path violation below before it can be accepted. M11 must prove
cross-runtime conformance and zero legacy authority before any retirement.

No existing M10 cursor may resume from changed source or seed documents by
implication. A guarded source/seed/runtime rebind or a fresh M10
materialization must preserve the old history, invalidate stale gate evidence,
and produce one exact launch manifest. The M10 target checkout itself, not only
an editable installation, must descend from the final convergence revision.

## Settled Decisions

- **C01-C03** — M10 may launch only after a guarded source, seed, runtime, marker, and supervisor rebind makes the target checkout and every executable consumer attest to one exact content-addressed revision; changed seed material requires a fresh plan epoch with the superseded epoch archived. _load_bearing: true_
  Rationale: This prevents a new editable runtime from executing an old target checkout or stale materialized plan.

- **C04-C20** — M10 and M11 treat schema, authority, occurrence identity, recovery, effects, projection truth, evidence, replay, and retirement as one structural conformance contract; missing or contradictory evidence is indeterminate and cannot authorize progress. _load_bearing: true_
  Rationale: The July 22–23 failures crossed these boundaries and cannot be closed safely as isolated operational patches.

## Exact launch and seed custody

`C01` **One content-addressed launch seed.** Before a worker starts, generate an
immutable manifest binding:

- final Git source commit, clean target root and target `HEAD`, target branch,
  base ancestry, advertised remote ref, and intended initiative revision;
- `chain.yaml`, `NORTHSTAR.md`, M10 and M11 briefs, the F01–F17 amendment, this
  decision, and the July 23 consolidation plan by path, Git blob, SHA-256, and
  semantic hash;
- the materialized M10 idea snapshot, plan revision, gate revision, chain
  bundle/cursor, and source-binding receipt;
- interpreter executable/hash/prefix, venv, import roots for every loaded
  Arnold module, distribution/direct-URL metadata, every active `.pth` file and
  executable line, wrapper hashes, supervisor receipt/fingerprint, hot
  environment, marker, resident/watchdog processes, and chain runtime binding.

Every consumer validates the same manifest. Missing, ambiguous, partial, stale,
or mixed identity blocks before model/provider dispatch. A PID, heartbeat,
editable install, branch name, or status label is not proof.

`C02` **Guarded rebind and rollback.** Source, seed, runtime, marker, and
supervisor changes are fenced, CAS-guarded, append-receipted operations. M10 is
paused and drained first. A→B and B→A must work from immutable clean roots and
independently verified interpreters. Faults after install, marker replacement,
supervisor restart, child spawn, or first state read leave M10 paused, effects
off, and history intact.

`C03` **Fresh plan semantics.** If any load-bearing seed hash changes, preserve
the old M10 snapshot and cursor as history, bind the new snapshot, invalidate
old gate/finalize/review evidence, and run a fresh gate. Since the interrupted
M10 produced no accepted execution work, a fresh M10 materialization on the
same chain milestone is preferred to pretending the old plan consumed the new
brief.

## Producer/consumer contract conformance

`C04` **One strict schema at every seam.** Prompt, materialized schema, scratch
promotion, parser, capture audit, handler, receipt, and replay use the same
content-addressed strict schema. Unknown fields fail; required fields and
recommendations are never fabricated, defaulted, inferred, stripped, or
reconstructed. A schema hash/version is recorded on invocation and receipt.

`C05` **Explicit decisions only.** A repair request without an immutable
accepted decision bound to its exact request digest is pending/unknown and
unclaimable. Marker-before-decision crash replay cannot dispatch.

`C06` **Authoritative conjunctive gate.** Every effect or authority-increasing
transition rereads the real Run Authority grant/fence, Custody lease/epoch, and
WBC attempt/effect record joined on the complete occurrence. Syntactic IDs,
outbox flags, shadow checks, projections, process facts, or receipts cannot
authorize. Validation and effect reservation are one fenced protocol.

`C07` **Append/CAS history.** Lease, chain, request, attempt, decision, and
effect sequence allocation plus append happen under one CAS/lock. Projections
and caches carry a validated history cursor/digest. A gap, malformed/torn
record, conflicting candidate, or failed required projection append is
`UNKNOWN/INCOHERENT`, never skipped or warning-only.

`C08` **Complete occurrence identity.** Digests and joins include every run,
revision, coordinator attempt, WBC attempt, chain, plan, phase/task, failure,
fence, lease, epoch, host/process-birth, and target field. V1/V2 adapters
preserve explicit legacy identity/unknowns; they do not fill new identity with
empty strings.

## Repair and recovery conformance

`C09` **Canonical advancement only.** Recurrence resets and recovery success
require a same-occurrence canonical plan/chain cursor delta. Activity, event
growth, liveness, Git/PR/CI movement, commits, or provider prose are
corroboration only.

`C10` **Fail-closed backstops.** L1/L2/L3 acceptance, recursion, provenance,
wrapper selection, and launch checks fail typed-indeterminate on nonzero,
missing, empty, or malformed output. They emit a durable event and launch no
child. A fallback wrapper must match the launch seed exactly.

`C11` **Identity-bound liveness and outcomes.** Missing session/process identity
is non-canonical. Terminal manifests never suppress inspection of a live
process. Every repair outcome is registered and explicitly terminal or
nonterminal; `repair_applied_reinvestigate` remains open for exactly one new
investigation and cannot acquire a fabricated `completed_at`.

`C12` **One custody transition receipt.** Each occurrence has an append-only
request→decision→claim→lease→attempt→effect→terminal/indeterminate→independent
verification lineage containing the launch seed and cursor before/after.

## Effect, retry, and replay conformance

`C13` **One effect protocol.** For a complete logical effect key, durable WBC
reservation/start and effect intent commit before any provider call. Exactly
one outcome closes the key: succeeded requires a provider-verifiable receipt
or authoritative target reread; failed requires definitive non-application;
otherwise it is visible terminal `INDETERMINATE`, never success or retryable
until reconciliation. Retries are causally linked child attempts.

`C14` **Universal writer registry.** A generated F01–F17 registry names every
provider/effect call, key, intent/outcome/reconcile writer, provider
query/idempotency capability, fault hook, and expected state. Provider fallback
may not retry an accepted/unknown request without reconciliation. Kernel effect
ledger, native hooks, observability journal, custody outbox, repair locks, and
provider adapters are migrated behind the WBC protocol or remain explicit
read-only historical adapters.

`C15` **Executable fault matrix.** Use a durable fake non-idempotent provider and
two hosts. Inject before/after reservation, start, intent, provider apply, ACK,
outcome, outbox, terminal, reconciliation, transfer, reclaim, restart, storage
failure, torn write, duplicate/out-of-order delivery, and mixed-version replay.
Assert at-most-one provider application, no false success, visible ambiguity,
old-owner rejection, and zero provider calls when intent persistence fails.

## Projection, status, and acceptance truth

`C16` **One validated acceptance adapter.** Status, watchdog, chain advancement,
successor admission, resident, and Discord consume a target-bound current chain
state plus validated acceptance evidence; receipt shape is not acceptance.
Terminal plan versus incomplete/blocked chain, operator pause, stale review,
stale watchdog completion, supersession, and terminal-manifest-plus-live-worker
are explicit contradictions/attention, never `done`.

Liveness requires a live identity-matched worker or formally held repair
custody. Heartbeat/activity alone is `activity_only`. Discord displays accepted
progress separately from plan bookkeeping.

## Migration and evidence conformance

`C17` **Version-gated expand/contract.** WBC store/outbox versions and migration
checksums are enforced. Applied migrations are a contiguous prefix.
Evidence-free legacy backfill, unknown schema versions, fabricated V2 fields,
or receipt lookup through an unhashed mutable legacy artifact are rejected.
Rollback never restores legacy write authority.

`C18` **Clean, candidate-bound evidence.** Acceptance uses clean baseline and
candidate clones/venvs with source injection disabled, identical collected test
sets, exact differential classification, and no collection/import/timeout/
unclassified failures. Repeat from an installed wheel with cwd outside the
repository and prove subprocess/wrapper/supervisor/resident identity. Scoped
tests, stale baseline failures, source-shadowed wheel tests, nominal manifests,
and narrative replay documents are insufficient.

`C19` **Operational replay.** Captured incidents become executable inputs with
forged/stale evidence negatives, repeated resume, A→B→A twice, projection
delete/rebuild, mixed-version restart, canary, forced rollback, and independent
5m/1h/6h checks.

`C20` **Retirement gate.** M11 may retire a path only after static call-site set
equality, captured runtime-trace equality, mixed-version/replay/rebuild/
rollback proof, zero authority readers/writers, and a generated per-path
deletion disposition. Historical adapters, legacy request/fingerprint formats,
state/event/checkpoint/cursor/trace artifacts, repair queue/lock/marker/
wrappers, old branches/worktrees/bundles, and runtime roots remain preserved or
read-only until that gate passes.

## Required launch verdict

The previous M10 resume is `NO-GO`. Relaunch becomes eligible only when C01–C04
and every other cutover-class prerequisite needed to make the new worker
truthful are implemented and their negative tests pass. Starting revised M10
is not M10 acceptance: it proves only that the exact final code and exact
latest seed set are durably executing under the new identity.
