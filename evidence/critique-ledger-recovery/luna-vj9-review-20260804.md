# Luna review of current VJ9 failure — 2026-08-04

## Verdict

VJ9 is related to the earlier VJ8/provider incidents, but it is not the same
defect. The missing DeepSeek credential was a cloud launch-environment failure:
the pinned runtime was started without sourcing `/workspace/.cloud-hot-env`.
VJ9 is a deterministic adapter-layer contract failure observed after a real
worker reached validation.

The shared category is control-plane weakness: stale tests/contracts and
inconsistent runtime/source/evidence lineage were allowed to surface as a
blocked run without one authoritative failure record.

## Exact VJ9 evidence

- Validation command: `tests/arnold/adapters/test_ledger_store_adapter.py`
  plus `tests/arnold/workflow/test_attempt_ledger_store.py`.
- Result: `164 passed, 1 failed`.
- Failure: `TestIdempotencyThroughAdapter::test_duplicate_idempotency_key_returns_existing`.
- The test first writes `STARTED`, sequence `1`, key `my-key`, then writes a
  different `COMPLETED`, sequence `2` event with the same key and still expects
  silent deduplication.

Under the newer content-safe idempotency contract, those are not the same
event. An exact canonical retry returns `is_duplicate=True`; divergent reuse
of a key must raise `IdempotencyConflictError` and leave one durable row.
The adapter simply delegates to the store and retries only transient SQLite
locks, so propagating that conflict is correct. The adapter itself is not
silently swallowing or manufacturing the failure.

## Important lineage caveat

Luna found that the clean local v3 snapshot still contains the older
silent-dedup store implementation, while the captured r5 source contains the
new content-safe implementation. Before accepting any repair, prove the exact
imported source revision, worktree, runtime hash, and test command. A test and
implementation split across revisions would otherwise create a false repair.

## Smallest safe repair order

1. Preserve the VJ9 occurrence; do not clear it or create a replacement chain.
2. Verify source/runtime/worktree identity under the pinned interpreter.
3. Update the adapter test to cover both exact retry deduplication and
   divergent same-key rejection, including one-row/no-open-transaction checks.
4. Finish and verify the shared canonical serializer and outbox path, then run
   the exact VJ9 command plus ledger/outbox/static-negative suites together.
5. Recover only through occurrence-scoped typed recovery. Do not force-proceed;
   U1/quality blockers remain authoritative.

## Shared fixes required beyond VJ9

Use one immutable execution envelope carrying session, plan, job, occurrence
fingerprint, source/runtime identity, provider route, lease identity, and
evidence generation. Enforce that `state.latest_failure` outranks stale phase
results; validation failures are hard blocks with an occurrence; recovery
matches that occurrence and repair identity; dispatch publishes `executing`
only after a fresh lease-bound process is verified; observers classify dead or
unknown processes as stale/blocked rather than running; and terminal/block
transitions quarantine unmatched in-flight telemetry.

## Acceptance tests

1. Exact adapter retry deduplicates; divergent same-key retry raises and does
   not insert a second row.
2. Plain-store and outbox paths use identical canonical serialization and
   conflict semantics.
3. A stale phase result cannot override a newer VJ9 failure occurrence.
4. Provider-preflight or lease failure produces no executing state or success
   marker.
5. Dead-PID, marker-only, stale-snapshot, and unmatched-telemetry cases report
   blocked/stale, never ready/running.
