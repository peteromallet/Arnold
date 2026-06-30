# M4 - Durable Substrate And Checkpoint Backend

## Objective

Make checkpoint, trace, audit, and resume storage backend-swappable and deliver
one real DB-backed durable execution backend path. The composition model must
not change when persistence moves from file-backed cursors to Postgres/DBOS or
an equivalent backend.

## Files To Change And Instructions

- `arnold/pipeline/native/checkpoint.py`
  Extract checkpoint persistence behind an interface that supports file-backed
  and DB-backed implementations.
- `arnold/pipeline/native/runtime.py`
  Depend on the checkpoint/audit/durable-execution interfaces rather than
  hardcoded files. The interface must cover more than CRUD: durable human waits,
  resume/reattach, retry state, and child-workflow start/continuation hooks.
- `arnold/pipeline/native/audit.py`
  Support append-only audit storage with lifecycle separate from operational
  checkpoints.
- New backend module
  Add a real DB-backed backend, preferably Postgres/DBOS or a documented
  equivalent, for checkpoints, trace indexes, audit skeleton/content refs, and
  project partitioning.
- DBOS/Postgres decision note
  Record whether DBOS is adopted now, deferred behind the interface, or replaced
  by an equivalent durable backend. The decision must address the
  repeatable-not-deterministic contract, transaction boundaries, operational
  ownership, local development behavior, migration/rollback, and backup/restore.
- Tests
  Run the same resume/trace/audit/human-gate conformance suite against the file
  backend and the DB-backed backend.

## Verifiable Completion Criterion

- Native runtime persistence and durable execution primitives are
  backend-swappable through a tested interface.
- File-backed behavior remains green.
- A real DB-backed backend proves the runtime does not depend on file paths for
  core semantics.
- Human-gate suspension survives process death and can be reattached by a
  restarted process.
- The DBOS/Postgres adoption decision is documented with tradeoffs and explicit
  unresolved risks.
- The DB-backed backend has a documented local-dev mode and rollback path; it is
  not only a production-only configuration that cannot be exercised in tests.

## Risks And Blockers

- Do not rewrite the composition model to fit a persistence backend.
- DBOS's determinism framing must be reconciled with Arnold's replay-by-default
  and possible future re-decide semantics before adoption.
- Do not split leases, checkpoints, trace indexes, and audit storage across
  unrelated persistence abstractions if they need shared transactional
  semantics.

## Dependencies

- Depends on M1, M2, and M3.
