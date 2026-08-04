# Introspect reset-prefix incident: evidence log and root-fix brief

**Date:** 2026-08-04  
**Affected session:** `critique-ledger-accountability-v3-r5-20260803`  
**Affected plan:** `cl2-wbc-backed-ledger-20260803-1357`  
**Affected workspace:** `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`  
**Runtime patch under review:** `657b336edc` (`fix(megaplan): recover introspection from reset event prefixes`)

## Executive finding

The visible failure was an observer crash:

```text
EventCheckpointError:
non-monotonic event seq beyond checkpoint: 0 <= 9
```

The deeper failure was an unversioned lifecycle reset. A forced fresh reset
deleted the plan-local directory and sequence sidecar while retaining the
external Store event stream. The same plan ID then started a new logical run at
sequence zero. Event transaction IDs were derived from `(plan_id, phase, seq)`,
so the two run epochs collided. A compatibility projection later exposed both
epochs as one journal, and the strict checkpoint reader stopped on the reset.

This is a split-ownership/identity failure, not merely a bad parser. The
current patch makes the observer recover and report degradation, but does not
yet make reset/relaunch of the same plan ID safe by construction.

## What happened

1. The first launch wrote sequence `0..9` between approximately
   `13:57:11` and `13:57:18 UTC`.
2. The chain log records a forced reset at approximately `13:57:22 UTC` with
   `reason=forced`, removing chain state and the plan directory.
3. The durable FileStore event stream lives outside that plan directory, so it
   survived the deletion. The plan-local `.events.seq` counter did not.
4. The second launch recreated the same plan ID and emitted a genuinely new
   sequence `0..9` between approximately `13:57:32` and `13:57:35 UTC`.
5. The two prefixes share deterministic transaction IDs but have different
   timestamps, session IDs, and state payloads. They are not safe to treat as
   identical copies.
6. The resulting `events.ndjson` contained 5,913 valid records: a duplicated
   `0..9` prefix followed by records through sequence `5903`.
7. `introspect` attempted a strict monotonic fold and failed with
   `0 <= 9`. This made the observer unavailable even though the underlying
   plan evidence remained readable.
8. The plan is currently blocked with no live worker; it was not restarted as
   part of this investigation.

## Evidence

### Live journal shape

The first 20 compact envelopes showed:

```text
rows 0..9:  seq 0..9, timestamps 13:57:11..18
rows 10..19: seq 0..9, timestamps 13:57:32..35
row 20+:    seq 10 onward
last seq:   5903
record count: 5913
```

The second prefix reused transaction IDs such as `520c2894191e2779`, but the
corresponding state/session payloads differed. This proves a new lifecycle
epoch, not a harmless byte-for-byte migration copy.

### Reset evidence

The chain log records a forced reset that removed the chain state and plan
directory. The Store event files are held outside that directory. This is the
boundary at which lifecycle state and event identity diverged.

### Dead generation fence

`event_checkpoint.py` reads `.events.restore-generation` when validating a
checkpoint, but repository search found no reset/restore path that increments
or writes it. The intended generation fence therefore does not protect a
fresh reset.

### MultiStore amplification

`MultiStore.events_for_plan()` currently concatenates FileStore and DBStore
streams and sorts them. The surrounding MultiStore contract describes a home
backend, but this read path does not enforce that ownership or an explicit
migration lineage. Cross-backend copies can therefore become a second source
of duplicate sequence rows.

### Observer behavior

`introspect` consumes the compatibility `events.ndjson` projection directly.
The native Arnold journal/quarantine path and the watchdog/current-target
typed observation path are not a single facade. Other observers can therefore
classify the same projection error differently or swallow it into an empty
event list.

## What the current patch changed

Commit `657b336edc` adds:

- cold rebuild tolerance for reset/non-monotonic prefixes;
- a bounded `sequence_anomaly_count` and anomaly sample in the receipt;
- warm-fold failure fallback to one cold rebuild;
- retained-journal sequence floor recovery when `.events.seq` is missing;
- transaction identity propagation into Store-neutral events;
- projection-level duplicate suppression;
- regression tests for the reader, projection, sequence floor, and
  `build_introspect_payload`.

The patch was tested against the actual cloud journal in an isolated source
checkout. It returned:

```json
{"mode":"cold_rebuild","degraded":true,
 "sequence_anomaly_count":10,"last_seq":5903}
```

That test created only a non-authoritative supervision checkpoint; it did not
rewrite events, state, or run execution.

## Limits of the current patch

The patch is recovery hardening, not the final root fix.

Most importantly, suppressing rows solely by `(transaction_id, seq)` is unsafe
while transaction IDs are themselves derived from `(plan_id, phase, seq)`.
Two genuinely different reset epochs can have the same values. Same identity
with different canonical bytes must be reported as a divergence/quarantine,
never silently first-wins deduplication.

The patch also does not:

- atomically version a reset with the Store stream;
- repair the existing 10 historical anomalies;
- make `MultiStore` ownership deterministic during migration;
- make all observers consume the same typed degraded/error signal;
- make the native journal the single canonical event source.

## Structures already present but not being used coherently

1. **Native journal contract:** `arnold.kernel.journal.NDJsonEventJournal` and
   `arnold.kernel.events.EventEnvelope` define canonical records, lineage, and
   quarantine behavior (`docs/arnold/event-journal-spec.md`).
2. **Store/WAL/outbox/idempotency patterns:** the FileStore framed WAL and the
   M10 effect/outbox contracts provide exactly-once and divergence patterns,
   but EventWriter's counter → Store → projection sequence is not one atomic
   operation.
3. **Generation/restore fencing:** `.events.restore-generation` is validated
   but not maintained by destructive reset/rematerialization paths.
4. **Projection/source-cursor contracts:** `ProjectionCursor`,
   `ProjectionRegistry`, and `SourceCursorVector` exist, but introspect and
   watchdog do not share one typed observation facade.
5. **Runtime/observer contracts:** current-target and watchdog signal bundles
   correlate worker identity, heartbeat, WBC, and projection errors more
   precisely than the ad hoc introspect joins.

## Root-fix requirements

The recommendation must satisfy these invariants:

1. Every event has a stable identity independent of sequence: at minimum
   `(plan_id, generation, event_id)`; sequence is an ordered cursor, not
   identity.
2. A fresh reset is a guarded `begin_new_generation` operation. It must fence
   live writers, close/archive the prior generation, persist the new generation
   in the authoritative Store, and only then recreate plan-local files.
3. The generation is present in event envelopes, transaction/idempotency keys,
   sidecars, projection cursors, and checkpoints.
4. Same stable identity + same canonical bytes is an idempotent no-op. Same
   identity + different bytes is a typed divergence/quarantine. Different
   identities at the same `(generation, seq)` are rejected or quarantined.
5. MultiStore reads one authoritative home backend. During migration, only
   exact, lineage-proven copies may collapse; an indefinite raw union is not a
   valid logical stream.
6. Projection rebuilds are deterministic, bounded, non-authoritative, and
   carry explicit source cursors and degradation/error receipts.
7. All observers use one `PlanObservation`/current-target facade. Missing or
   corrupt evidence becomes `unknown`/`incoherent`/`degraded`, never an empty
   healthy view.
8. Every destructive reset, restore, rematerialization, and import path must
   invoke the generation API and emit an auditable receipt.

## Required acceptance tests

- Forced fresh reset with retained Store events and the same plan ID.
- Crash at every reset/generation boundary; restart converges to one active
  generation.
- Concurrent fresh resets; exactly one wins the generation CAS.
- Missing/corrupt counter with a retained Store stream; no implicit sequence 0.
- Exact FileStore/DBStore migration copy; one projected event.
- Same transaction/sequence with divergent payload/session; quarantine, no
  silent dedupe.
- Fault injection between sequence allocation, Store commit, and projection
  append; replay yields one canonical event and eventual projection.
- Restore/rematerialize/export/import preserves or explicitly increments the
  generation and invalidates stale checkpoints.
- `introspect`, watchdog, current-target, and status agree on degraded evidence.
- Repeated polling creates one repair claim and one notification, not a loop.

## Questions for the GPT-5.6 Sol review

Please independently decide:

1. Which existing structure should become the canonical event authority now:
   native journal, Store, or a staged combination?
2. What is the minimum safe generation/event-identity design that prevents this
   reset class without a broad rewrite?
3. Where must the reset transaction own cleanup/archival so a partial crash
   cannot split plan-local and Store lifecycles?
4. How should migration duplicates and divergent same-sequence events be
   represented and surfaced?
5. What exact order of implementation, repair, test, runtime cutover, and
   relaunch gives the shortest safe path to resuming the critique epic?

The requested output is an opinionated root-cause decision, a minimal design,
an implementation sequence, and explicit conditions under which the epic may
be relaunched.

## Independent GPT-5.6 Sol review

**Reviewer:** GPT-5.6 Sol, reasoning `high`  
**Invocation:** read-only Codex subagent against this log and the cited checkout  
**Date:** 2026-08-04

### Decision

This is a lifecycle-authority bug, not a checkpoint-parser bug. Commit
`657b336edc` is useful containment, but it is not safe to relaunch against by
itself. The canonical authority should be a Store-backed `PlanEventStream`.
Exactly one home backend must own generation state, sequence allocation, event
append, idempotency, and divergence decisions. The native `EventEnvelope` and
canonical-JSON ideas are useful schema concepts, but the current plan-local
NDJSON journal should not become the authority: it relies on a deletable
sidecar, has no generation CAS, and advances its counter before the append.
`events.ndjson` should remain a rebuildable compatibility projection.

### Minimum safe identity and append contract

The Store must persist `plan_id`, `home_backend`, `current_generation_id`,
generation status (`PREPARING`, `ACTIVE`, or `CLOSED`), a plan-wide
never-reused `next_seq`, the previous generation, and the reset receipt. Each
event must carry `plan_id`, `generation_id`, a UUID/ULID `event_id` created
before retryable work, the Store-allocated sequence, canonical bytes, and a
canonical digest. Identity is `(plan_id, generation_id, event_id)`; sequence is
ordering, not identity. `run_id` and session IDs remain correlation fields.

One Store transaction must validate the active generation, detect an existing
event ID, allocate the next sequence, append the canonical envelope, advance
the high-water mark, and enqueue the projection/outbox effect. Same identity
and same digest is an idempotent replay; same identity with different bytes is
a durable divergence/quarantine; a stale generation is rejected; and a
projection failure after commit is replayed rather than creating a second
canonical event. Keeping sequence plan-wide is an additional defense against
reset-induced regressions.

### Crash-safe reset ordering

Replace inline deletion with an idempotent
`begin_new_generation(plan_id, expected_generation, reset_id, reason, actor)`:

1. Stop the known runner as containment; process death is not the fence.
2. In the authoritative Store transaction, serialize against appends, close
   the old generation, create `PREPARING`, retain the sequence high-water mark,
   and persist the reset intent/receipt.
3. Only after that commit, atomically rename the old plan directory and chain
   state into a reset archive. Never delete first.
4. Materialize a fresh directory via temp-write/fsync/rename with the committed
   generation token and projection cursor.
5. Persist materialization, then CAS `PREPARING` to `ACTIVE`.
6. Launch the worker bound to that exact generation; every append revalidates it.
7. Delete archives later as idempotent retention cleanup.

Crashes before the Store commit make no lifecycle change; crashes afterward
leave a fenced, resumable reset. Concurrent resets are resolved by one
generation CAS winner.

### Migration, observers, and notifications

Canonical reads must use the home backend only. Migration should fence and
cursor the source, copy stable identity/generation/sequence/canonical bytes,
verify lineage and digests, CAS the home pointer, and retain the source as
audit evidence. Dual-read is diagnostic only. Exact copies may collapse only
when identity *and canonical bytes* match; divergent same-identity records must
block cutover.

The current incident should be preserved as raw 5,913-row evidence. Import its
physical order into explicit legacy generations A and B with new stable event
IDs and a plan-wide sequence, retaining source sequence, row position, and the
reset evidence in an adoption manifest. Do not silently delete either `0..9`
prefix. Start a fresh generation C after the imported high-water mark and
rebuild projections.

All introspection, watchdog, current-target, status, completion, and repair
admission should consume one generation-aware `PlanObservation` facade with
`healthy`, `degraded`, `incoherent`, and `unknown` states. An exception must
never become an empty healthy event list. `degraded` is displayable but cannot
authorize completion or repair; `incoherent`/`unknown` cannot suppress a worker.
Repair claims and notifications should be occurrence-deduped by
`(plan_id, generation_id, condition_code, authority_head, evidence_digest)` and
emit once on entry (optionally once on resolution), not once per poll.

### Sol's shortest safe route and relaunch gate

1. Keep the critique epic stopped and disable first-wins projection dedupe.
2. Implement Store generation metadata and atomic append in both backends.
3. Make `MultiStore` home-only for canonical event reads.
4. Bind `EventWriter` to Store generation allocation; demote sidecars to hints.
5. Route reset/restore/rematerialize/import through the generation coordinator.
6. Add the unified observation and notification occurrence-dedup behavior.
7. Pass append-fault, reset-crash-boundary, concurrent-reset, stale-writer,
   migration-divergence, observer-agreement, and notification tests.
8. Adopt the affected stream, deploy a pinned runtime, and run a disposable
   same-plan-ID forced-reset/restart canary.

Relaunch is **GO** only when one home backend and one `ACTIVE` generation are
unambiguous; stale writers cannot append; sequence allocation and canonical
append are atomic and never reuse a cursor; the affected history has an
auditable adoption/divergence receipt; all reset/concurrency/append-fault
tests pass; all observers agree; repeated polling creates one repair claim and
notification; and a pinned-runtime same-ID reset canary remains monotonic.

It is **NO-GO** while relaunch depends on `657b336edc` alone, raw `rmtree`, a
local generation sidecar, `MultiStore` union reads, first-wins dedupe, or a
degraded projection influencing control decisions.
