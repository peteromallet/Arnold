# M4: Native Persistence Backend — Decision Record

**Decision**: DEFER DBOS — use raw Postgres (psycopg3) as the first DB-backed
persistence path. DBOS is ruled out for M4 because its output-replay model
conflicts with Arnold's repeatable-not-model-deterministic re-execute-on-resume
contract.

**Date**: 2026-07-04

## 1. DBOS Deferral

DBOS guarantees exactly-once execution by caching step outputs and replaying from
cache on resume. Arnold requires phases to *re-execute* on resume with
potentially different model outputs — the system may produce a different result
on each replay, and that non-determinism is an explicit property of the contract.

| Concern | DBOS behavior | Arnold requirement |
| --- | --- | --- |
| Resume semantics | Replay cached output | Re-execute phase body |
| Output determinism | Guaranteed same output | Repeatable, not model-deterministic |
| Side-effect model | Output caching, side-effect dedup | Idempotency-key fencing, reconcile-on-resume |
| Storage opinion | Owns output cache + workflow state | Backend is passive durable store; runtime owns control flow |

This is a fundamental philosophical mismatch, not a configuration or adapter
problem. DBOS remains a documented candidate for future adoption if Arnold later
adopts output-caching semantics, but M4 must prove the backend boundary works
with a backend that does not impose replay opinions.

### Revisit Trigger

Revisit DBOS when **all** of:
1. Arnold adds an explicit output-caching or memoization policy slot;
2. The re-execute-on-resume contract is relaxed to allow cached-replay through a
   declared policy;
3. A conformance suite proves DBOS caching does not change resume surface
   precedence, corrupt-cursor fail-closed behavior, or human-gate lifecycle.

## 2. Why Raw Postgres Preserves Re-Execute-On-Resume

Postgres (via psycopg3) is used as a passive durable store:

- It persists checkpoint cursors, human-gate state, composite cursors, trace
  artifacts, audit records, and ordered events under explicit project/run/artifact
  partition keys.
- It does **not** interpret cursor payloads, decide which phase to resume, or
  enforce output-caching semantics.
- The runtime (`run_native_pipeline()`) reads persisted state on resume and
  re-enters the phase body at the recorded program counter, re-executing the
  phase with fresh model calls.
- The five-source resume surface precedence chain (`state_resume_cursor` >
  `typed_contract` > `composite_resume_cursor` > `awaiting_user` > `resume_cursor`)
  is resolved identically through file and Postgres backends because the backend
  only supplies raw payload bytes; classification and precedence remain owned by
  `arnold/pipeline/resume.py` and its `classify_resume_cursor_payload()` helper.

The backend contract (`NativePersistenceBackend` protocol in
`arnold/pipeline/native/persistence.py`) intentionally exposes stable
project/run/artifact identifiers rather than raw filesystem paths. This prevents
DB behavior from leaking through the interface boundary.

## 3. Transaction Boundaries

The Postgres backend (`arnold/pipeline/native/postgres_persistence.py`) applies
transaction boundaries as follows:

| Operation group | Transaction strategy | Rationale |
| --- | --- | --- |
| Resume cursor write/delete | Explicit psycopg transaction | Atomic upsert/delete for reattach safety |
| Human gate write/delete | Explicit psycopg transaction | Paired write/read/clear for suspension lifecycle |
| Composite cursor write/delete | Explicit psycopg transaction | Parent-child artifact consistency |
| Trace artifact write | Explicit psycopg transaction | ON CONFLICT upsert within artifact scope |
| Audit record append | Implicit autocommit (independent INSERT) | Append-only; must never roll back with cursor ops |
| Event emit | Explicit psycopg transaction around sequence fetch + INSERT | Monotonic ordering via `arnold_native_event_sequence` |

Audit and cursor mutations are never in the same transaction. This preserves the
append-only audit contract: an audit record is written even if the subsequent
cursor write fails, and a failed audit write does not roll back the cursor.

The migration application (`apply_migrations()`) also runs inside a single
transaction: all SQL files in `arnold/pipeline/native/migrations/` are applied
idempotently, each tracked by a row in `arnold_native_schema_migrations`.

## 4. Operational Ownership

| Concern | Owner | Boundary |
| --- | --- | --- |
| Schema definition | `migrations/001_native_persistence.sql` | Arnold-owned tables with `arnold_native_` prefix |
| Connection lifecycle | `PostgresNativePersistenceBackend` | Caller supplies `conninfo` or existing `connection` |
| Migration application | `apply_migrations()` | Called at init when `apply_migrations=True` (default); production callers may apply separately |
| Cursor interpretation | `arnold/pipeline/resume.py` | Backend never classifies or routes on payload contents |
| Runtime control flow | `arnold/pipeline/native/runtime.py` | Backend supplies raw reads/writes; runtime owns all suspension/resume decisions |
| Table cleanup | Caller responsibility | No automatic DROP on teardown; test harness uses per-run `project_id` isolation |

The backend does **not** own:
- Routing decisions (`override_routes`, `instruction_branches`)
- Loop exits or cap thresholds
- Model routing policy
- Execute/review decisions
- Suspension semantics beyond durable store/retrieve

## 5. Local Development

### Option A: Docker Compose (recommended for local dev)

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: arnold
      POSTGRES_PASSWORD: arnold
      POSTGRES_DB: arnold_dev
    ports:
      - "5432:5432"
```

Connection string for the backend:
```
postgresql://arnold:arnold@localhost:5432/arnold_dev
```

### Option B: External URL

Set `ARNOLD_PG_CONNINFO` or pass `conninfo` directly:

```python
from arnold.pipeline.native import PostgresNativePersistenceBackend

backend = PostgresNativePersistenceBackend(
    conninfo="postgresql://user:pass@host:5432/arnold",
    apply_migrations=True,
)
```

### Option C: No Postgres (file backend default)

When no Postgres backend is supplied, `run_native_pipeline()` defaults to the
zero-dependency `FileNativePersistenceBackend`. All pipeline authoring and
testing works without a database.

### Test isolation

Tests use per-run `project_id` values (e.g., UUIDs) and clean owned tables in
teardown. The conformance suite (`_persistence_backend_conformance.py`) reuses
the same behavioral cases for file and Postgres backends so parity failures are
immediately visible.

## 6. Migration and Rollback

### Applying migrations

Migrations live in `arnold/pipeline/native/migrations/` as numbered SQL files
(`001_native_persistence.sql`, `002_*.sql`, ...). They are applied idempotently:

- The `arnold_native_schema_migrations` table tracks which versions have been
  applied.
- `PostgresNativePersistenceBackend(apply_migrations=True)` runs all unapplied
  `.sql` files inside one transaction on init.
- All schema objects use `IF NOT EXISTS` / `IF EXISTS` guards.

### Forward migration

1. Add a new numbered `.sql` file to `arnold/pipeline/native/migrations/`.
2. It is applied automatically on next init with `apply_migrations=True`.
3. For production, apply the SQL file manually and insert the version row.

### Rollback

- Schema rollback requires a manual down-migration (no automatic reverse).
- Cursor/gate/trace data is scoped by `(project_id, run_id, artifact_id)` —
  old runs are not affected by schema changes to new runs.
- Full database backup/restore is the safety net for schema mistakes (see §7).

### Migration format

All tables use explicit `(project_id, run_id, artifact_id)` partition columns,
not schema-per-project isolation. This keeps the logical partitioning inside
Arnold's control and avoids requiring database-level schema creation for each
new project.

## 7. Backup and Restore

### What to back up

All Arnold persistence data lives in seven tables:

| Table | Contents | Backup priority |
| --- | --- | --- |
| `arnold_native_resume_checkpoints` | Per-artifact resume cursors | High — needed for resume |
| `arnold_native_human_gates` | Awaiting-user state | High — needed for human-gate reattach |
| `arnold_native_composite_cursors` | Parent-child subpipeline cursors | High — needed for composite resume |
| `arnold_native_trace_artifacts` | state.json, events, stages, artifacts, checkpoints, tree | Medium — debugging, replay |
| `arnold_native_audit_records` | Append-only audit log | Medium — compliance, debugging |
| `arnold_native_ordered_events` | Runtime event journal | Low — derived from runtime; recoverable |
| `arnold_native_schema_migrations` | Migration version tracker | Low — regenerated by `apply_migrations()` |

### Backup strategy

- **pg_dump** the Arnold tables: `pg_dump -t 'arnold_native_*' arnold > arnold_backup.sql`
- **Point-in-time recovery**: Standard Postgres WAL archiving covers all Arnold
  data.
- **Per-project export**: `SELECT * FROM arnold_native_* WHERE project_id = $1`
  for scoped backup.

### Restore strategy

1. Restore the database from `pg_dump` or PITR.
2. On next backend init with `apply_migrations=True`, any missing migration
   versions are applied.
3. Resume reads the restored cursors; the runtime re-enters at the recorded
   program counter.

### File backend fallback

The file backend stores artifacts at the artifact root path. Standard filesystem
backup (rsync, snapshots) covers all file-backed persistence data.

## 8. Unresolved Risks

| Risk | Severity | Mitigation | Owner |
| --- | --- | --- | --- |
| Connection pool exhaustion under concurrent native runs | Medium | Each backend operation opens/closes its own connection; revisit with connection pooling for M5 worker fleet | M5 |
| Sequence gaps in `arnold_native_event_sequence` | Low | Gaps after failed transactions are accepted by the success criterion; monotonic uniqueness is preserved | M4 (verified) |
| Postgres unavailable at runtime init | Medium | File backend remains the zero-dependency default; `run_native_pipeline()` falls back gracefully | M4 (verified) |
| Schema migration conflict across concurrent deploys | Low | Migrations are idempotent and run inside a transaction; Postgres serializes concurrent DDL | M4 (design) |
| Large trace artifacts exceeding `jsonb` limits | Low | Current trace payloads are bounded by pipeline structure; monitor for compound artifact growth | M5/M6 |
| DBOS output cache leaking into future replay semantics | N/A | DBOS is deferred; if revisited, must pass re-execute-on-resume conformance suite | Future |
| Persistence becoming a hidden owner of native representation semantics | High | See §10 false-pass guard; structural conformance tests gate M6 closure | M6 |

## 9. Affected Native-Representation Alignment Rows

M4's durable persistence work affects the following rows from the
`docs/arnold/megaplan-native-representation-alignment-plan.md` traceability matrix.
M4 does not claim any row as `implemented` — it provides the durable substrate
that later epics consume. Rows that become `implemented` must still pass
structural conformance, handler-purity inventory, and mutation tests in
platform M6.

| Matrix row | M4 impact | Status after M4 |
| --- | --- | --- |
| Prep clarification gate | Human suspension now durably persists through Postgres; resume coordinates survive process death | `enabled` (composition owns visible branch) |
| Gate flag/debt/fallback handling | Flag/debt records survive across restart via DB-backed audit and trace | `enabled` (composition owns visible routes) |
| Human decision/suspension | Durable `awaiting_user` state through `write_human_gate`/`read_human_gate`/`delete_human_gate` with transaction-wrapped pairing | `enabled` (composition/Platform M2 own suspension points) |
| Execute approval/no-review/deferred-human gates | Approval-gate checkpoint storage is backend-swappable; process-death survival is proven | `enabled` (composition/Platform M2 own gate topology) |
| Review infrastructure retry and cap outcomes | Review state and cap counters persist through backend; reattach reads last known state | `enabled` (composition owns visible outcomes) |
| Timeout/deadline policy | Timeout state survives restart through durable backend | `enabled` (composition owns policy declaration) |
| Path-addressed checkpoints | Tree traces and checkpoint cursors are stored with stable path identity through both backends; `start_from_trace()` reads from DB-backed trace artifacts | `enabled` (composition/Platform M6 own path identity proof) |
| Auto-drive/event/liveness transitions | Ordered events with monotonic sequences (`arnold_native_ordered_events`) survive restart; event replay reproduces visible workflow path | `enabled` (composition/Platform M5/M6 own liveness policy) |
| Execute/review/rework loop | Composite parent-child cursors persist through `write_composite_resume_cursor` for subpipeline resume across process death | `enabled` (composition owns visible loop) |
| Golden trace regeneration guard | Trace artifacts are backend-swappable; re-generating goldens from DB-backed traces requires the same semantic diff review | `enabled` (Platform M6 owns final guard) |
| Behavior parity with existing Megaplan | File-backed behavior remains green under backend-swappable runtime; Postgres-backed behavior matches through shared conformance suite | `enabled` (composition/Platform M6 own full parity) |

## 10. False-Pass Guard: Persistence Is Not Proof of Native Representation

The most dangerous false pass for M4 is treating durable DB storage as proof
that native representation is preserved. It is not.

### The guard

Persistence is a *consumer* of the native composition model, not a validator of
it. A workflow could persist every checkpoint, trace, and audit record through
Postgres while still:

- Collapsing `critique` into a single handler-backed stage with invisible
  retry/fanout;
- Hiding `gate` routing decisions inside `handle_gate()` state mutations;
- Burying `tiebreaker` researcher/challenger split behind one opaque handler;
- Keeping `execute` as one node with richer internal logging;
- Routing `override` actions through generic dispatch rather than explicit
  product-owned decision paths.

In all these cases, persistence would "work" — cursors would save and restore,
traces would render, audits would append — but the native representation target
would not be met.

### Required proof before M6 close

Platform M6 must pass these gates before claiming native representation
preservation:

1. **Structural conformance**: Fails if `critique`, `gate`, `tiebreaker`,
   `execute`, `review`, or `override` are represented only as single
   handler-backed stages.
2. **Native-Python anti-wrapper check**: Fails if canonical `workflow.pypeline`
   expresses product control flow through `SOURCE_*`-style component calls,
   generic stage dispatch, route-label tables, or handler refs.
3. **Handler-purity inventory**: Scans retained handlers for `current_state`,
   `next_step`, `workflow_transition`, `run_parallel_*`, auto-loop dispatch,
   and override action dispatch.
4. **Mutation tests**: Move one visible branch, retry, fanout, or suspension
   route back into a handler and prove conformance fails.
5. **Post-platform preservation check**: Proves that DB durability, brokered
   credentials, workers, cancellation, and reconcile did not collapse product
   routes into runtime side effects.

### What M4 does prove

M4 proves that the *durable storage boundary* is correctly placed:

- The backend interface (`NativePersistenceBackend`) exposes stable identifiers,
  not filesystem paths.
- The file backend preserves existing artifact layout and all tests pass.
- The Postgres backend passes the same conformance suite with identical behavior.
- Resume surface precedence, corrupt-cursor fail-closed behavior, human-gate
  lifecycle, composite cursor CRUD, trace artifact round-trip, audit
  append/read, and event ordering are backend-transparent.
- The runtime (`run_native_pipeline()`) does not change control-flow semantics
  when the backend is swapped.

These are necessary conditions for native representation preservation. They are
not sufficient. M6 owns the sufficiency proof.

## Anchors

| Anchor | File:Line | What |
| --- | --- | --- |
| `NativePersistenceBackend` protocol | `arnold/pipeline/native/persistence.py:147` | 13-method protocol: resume cursors, human gates, composite cursors, trace artifacts, audit, events |
| `FileNativePersistenceBackend` | `arnold/pipeline/native/persistence.py:264` | File-backed implementation preserving current artifact layout |
| `PostgresNativePersistenceBackend` | `arnold/pipeline/native/postgres_persistence.py:40` | psycopg3 implementation with explicit project/run/artifact partition columns |
| Schema migrations | `arnold/pipeline/native/migrations/001_native_persistence.sql` | 7 tables + 1 sequence + 2 indexes |
| Five-source resume precedence | `arnold/pipeline/resume.py` | `resolve_resume_surface()` via backend; precedence owned by resume module |
| `classify_resume_cursor_payload` | `arnold/pipeline/resume.py:209` | Fail-closed corrupt native cursor detection |
| Runtime backend injection | `arnold/pipeline/native/runtime.py` | `run_native_pipeline(..., persistence_backend=...)` |
| Audit hooks backend sink | `arnold/pipeline/native/audit.py` | `AuditHooks` accepts backend while preserving `audit_dir` |
| Trace hooks backend sink | `arnold/pipeline/native/trace.py` | `NativeTraceHooks` writes trace artifacts through backend |
| `start_from_trace` backend reads | `arnold/pipeline/native/start_from_path.py` | Reads trace artifacts through backend |
| Event journal adapter | `arnold/runtime/event_journal.py` | Backend-backed event journal with monotonic sequences |
| DBOS/Arnold contract conflict | This document §1 | DBOS output-caching vs Arnold re-execute-on-resume |
| Native representation alignment plan | `docs/arnold/megaplan-native-representation-alignment-plan.md` | 31 traceability matrix rows; M4 affects 11 |
| Alignment validator | `tests/arnold_pipelines/megaplan/test_native_representation_alignment_artifacts.py` | Validates schema, 31 rows, 15 scenarios |
| Backend conformance suite | `tests/arnold/pipeline/native/_persistence_backend_conformance.py` | Shared behavioral cases for file and Postgres backends |
| Platform preservation guard | This document §10 | Persistence is not proof of native representation if routing becomes a side effect |
