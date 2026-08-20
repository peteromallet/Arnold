# GPT-5.6 Sol-high implementation — T1.7 owner-local durable storage

Start only when a mutating-lane slot and sufficient disk headroom are available.
Use a fresh isolated worktree from exact accepted recovery ancestor
`6787d6363e8fc0603092913ae877db14f3b9fff8`; do not base on dirty/diverged main.
This is a 🔥 VERY HARD task.

Read the complete T1.7, F01/F03/F04/F10/F11/F12, evidence, regression, and
integration requirements in the recovery plan. Treat the incident only as an
offline fixture; do not contact cloud/providers or mutate live owner state.

Verified starting facts at `6787d636`:

- `SqliteAttemptLedgerStore` (`arnold/workflow/attempt_ledger_store.py`) uses WAL
  and `BEGIN IMMEDIATE` retries and is the strongest landed local primitive, but
  plan-local phase/worker WBC facades are `ACTION_OFF`/enforcement-disabled and
  are not canonical critique occurrence custody.
- Critique truth is split across plan-local `critique_vN.json`, raw producer/
  evaluator files, receipts, `faults.json`, custody/clearance files, boundary/WBC
  records and later chain state. Publication is a multi-file saga with torn
  crash states; nominally immutable custody receipts use overwrite-capable
  `atomic_write_json`; registry read-modify-write is unlocked.
- Canonical epic events use framed `events.jsonl`; `events.ndjson`, `.events.seq`,
  cursors and generic projection histories are mutable derived files. Several
  readers silently truncate/skip malformed, oversized, undecodable or corrupt
  records; event sequence corruption becomes `-1`; strict source digest is
  optional; one atomic projection writer omits parent-directory fsync.
- Critique artifacts/projections/WBC stores are co-located in the plan directory
  and rely on the persistent volume. They do not use `Store.write_plan_artifact`
  or DB/MultiStore replication. Direct module entrypoints/imports can bypass CLI
  locks; scratch `critique_output.json` is an alternate ingestion surface.
- Cloud runtime can combine an installed package, independently selected repo/
  ref, and supervisor source, allowing provenance skew.

Required end state:

1. Build a generic owner-local transactional store outside Megaplan-specific
   policy, with typed adapters for critique and other pipelines. Canonical
   occurrence, immutable input/object references, revision/fence/epoch, attempt
   intent/result/ambiguity, semantic disposition, publication outbox, and
   visibility transition must commit in one serializable transaction or a
   rigorously reconciled durable outbox protocol. Projection/log/artifact writes
   never mint or advance authority.
2. Use a process-safe durable backend with WAL, explicit schema/version,
   monotonic revisions, exact CAS/idempotency, foreign/unique constraints,
   checksums/hash chain where needed, bounded transactions, busy handling,
   durability settings, file+parent fsync, and stable owner-root identity.
   Read/open/parse/checksum/schema errors are typed errors, never empty history,
   valid-prefix success, sequence reset, or rebuild-from-projection.
3. Store immutable/content-addressed receipts and object references. A supposedly
   immutable receipt cannot be overwritten, relinked, path-aliased, symlinked,
   or coherently replaced with its artifact. Large raw/artifact bytes may live
   in a separate content-addressed object area, but reservation precedes write,
   byte+inode quotas are enforced, and the owner transaction binds exact digest,
   length, locator, generation and commit status.
4. Make every current plan-local JSON/JSONL/SQLite side file a rebuildable,
   bounded projection or retire it. Rebuild only from canonical transactions;
   verify source digest/revision/count, atomically replace with parent fsync, and
   refuse corrupt canonical input. Projection deletion/corruption/staleness or
   200 observers cannot change owner truth or trigger an effect.
5. Route all installed CLI/module/direct-import/runtime paths through the owner
   store or fail closed. Remove scratch-file ingestion authority and direct
   registry/event append authority. Bind installed source/runtime generation;
   no `PYTHONPATH`, env flag, editable checkout, import alias, or source skew can
   select a second canonical store/writer.
6. Define migration from legacy local files as an idempotent, fenced, audited
   transaction: inventory/hash/freeze old input; import once; independently
   verify counts/digests/semantics; switch readers/writers atomically; keep old
   files read-only evidence; reject late legacy writers. Backup/restore must be
   executable and byte/state verified, with compatible rollback or signed
   forward migration.
7. Inventory non-Megaplan pipelines and make the shared owner store reusable.
   Prove none can bypass canonical storage/effect custody through their own JSON,
   queue, registry, local lock, or convenience writer.

Adversarial proof must include: two threads and two processes; crash/power-loss
simulation at each transaction/outbox/object/fsync/projection/migration boundary;
WAL checkpoint/recovery; ENOSPC and inode exhaustion; permission/read/I/O error;
truncated/corrupt/oversized/duplicate/out-of-order/forked records; stale revision/
fence/epoch; exact replay and conflicting replay; receipt/artifact coordinated
replacement; symlink/hardlink/path/ancestor rename; large journal and bounded
rebuild; deleted/corrupt projections; 200 observers; legacy/direct/env/module/
scratch bypasses; installed wheel/materialized runtime parity; backup damage and
real restore; late old writer rejection; and non-Megaplan conformance. Prove one
canonical result, no lost accepted write, no authority rollback, and no effect
from a projection or corrupt/ambiguous state.

Run focused, dependency-closure, concurrency/crash/fault, migration/rebuild,
installed-wheel/materialized, static/diff/compile, and bypass suites. Large tests
are single-flight; delete only reproducible scratch after evidence capture.

Commit scoped work, leave the worktree clean, and write exact commit/tree/files,
tests, migration limitations and production-owner prerequisites to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.7/t1-7-sol-implementation-result.md`.
Do not deploy, mutate cloud/owner state, check T1.7, or claim formal completion
without an independent Sol review and accepted storage/migration receipts.
