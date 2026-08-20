# GPT-5.6 Sol-high implementation — T1.1 raw-evidence admission

Implement T1.1 in the fresh clean worktree
`/private/tmp/arnold-critique-recovery-t1-1-admission-20260802`, based on exact
recovery ancestor `6787d6363e8fc0603092913ae877db14f3b9fff8`. This is a 🔥 VERY
HARD task. Do not use dirty/diverged main as code ancestry.

Read completely before editing:

- T1.1, the authority/dependency table, invariants F01/F05/F06/F07/F11/F12,
  evidence contract, named regression list, and R1/R2/R4 requirements in
  `/Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`;
- accepted immutable T0.2 evidence and verification under
  `/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.2/`;
- the incident target only as an offline fixture, never as mutable runtime state;
- Luna's preparation artifact when it appears at
  `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-sol-preparation-luna-result.md`.

Verified starting gaps at `6787d636`:

1. `chain/source_admission.py` validates brief/source hashes only; it has no raw
   CL1 evidence predicate.
2. `supervisor/chain_runner.py::_admit_chain_materialization` invokes that weak
   check before `prepare_plan`, but legacy/default `chain/__init__.py::run_chain`
   calls `_init_plan` directly. `run_chain_cli` chooses the supervisor only when
   `MEGAPLAN_SUPERVISOR_TIER=1`, whose default is false.
3. `_init_plan` launches installed `python -P -m arnold_pipelines.megaplan init`
   without deterministic `--name`; `handlers/init.py` timestamp-names and checks
   only `plan_dir.exists()`. There is no atomic owner reservation/CAS.
4. `ChainState` has no revision; `save_chain_state` is fixed-temp-plus-replace;
   projection failures fail open.
5. Run Authority contains immutable contracts/pure reducer/current-source but no
   durable admission writer/store/CAS. Existing journal CAS is read-then-write
   without an interprocess lock and is not authority for two initializers.
6. Chain YAML has `depends_on` only, no typed machine predicate. Do not invent an
   incident-specific or filename-shaped shadow schema.

Required end state:

1. Define a versioned, allowlisted, canonical machine-prerequisite contract that
   derives a typed admission decision from raw, content-addressed CL1 evidence.
   Bind evidence object hash, manifest/receipt, predicate version/digest, exact
   target tuple, source/spec/brief/chain identities, intended plan identity,
   runtime generation, authority revision/fence, and expiry where applicable.
   False, missing, stale, wrong-target, unknown-version, duplicate/extra field,
   corrupt, unreadable, throwing, or unverifiable predicates reject closed.
   Model prose, summaries, auto-approval, and mutable projections have zero
   prerequisite authority.
2. Add a single durable owner admission/reservation boundary under Run Authority
   with a real atomic compare-and-swap, revision, fence, nonce/idempotency, and
   exact already-committed reconciliation. Two processes initializing the same
   target must converge on one decision and one deterministic plan identity;
   distinct/forked evidence or intent must conflict, never overwrite/adopt.
   Crash/response loss stays typed indeterminate unless backend-authoritative
   proof establishes the exact committed record.
3. Re-evaluate the raw predicate and current authority fence immediately before
   plan-directory creation. Reserve deterministic plan identity before any
   directory, worktree, branch, process, provider call, or downstream effect.
   Pass that identity explicitly through installed CLI/API (`--name` or an exact
   typed equivalent); no timestamp identity or exists-check may mint authority.
4. Route supervisor, legacy/default chain, resume/retry/replan/finalize and every
   direct/materialized wrapper through the same boundary, or hard-fail them.
   Environment flags cannot select a weaker path. A projection may be rebuilt
   from owner records but may not admit work or fail open.
5. Keep the boundary platform-wide: generic raw-evidence predicate and
   owner-reservation contracts belong outside Megaplan policy where appropriate;
   Megaplan supplies its typed adapter. Inventory non-Megaplan pipelines and
   prove no direct plan/workspace/runner constructor bypasses admission.
6. Production constructors must require an owner-installed backend and trust
   root. Test/local filesystem implementations must be visibly non-production,
   hermetic, concurrency/crash safe, and impossible to install as production
   merely via imports, monkeypatch, environment, paths, labels, or local receipts.
   When owners are absent, installed CLI/API fail closed before mutation.

Adversarial proof must cover: true/false/missing/stale/wrong-target/unknown/
throwing predicates; raw bytes versus summary/projection disagreement; manifest
and receipt substitution; hash collision-shaped aliases; symlink/partial/read
error/ENOSPC; two threads and two processes; crash before/after reservation and
directory creation; stale fence/revision; response loss; exact replay versus
conflicting replay; deterministic identity across restart; legacy/supervisor/
resume/retry/direct/wrapper/environment bypasses; 200 observers; installed wheel
and materialized parity; and non-Megaplan bypass inventory. Prove zero plan,
workspace, branch, process, or provider side effects on every rejection and at
most one plan creation on accepted concurrent initialization.

Run focused, dependency-closure, process/concurrency/crash/fault, installed
entrypoint, wheel/materialized parity, static/diff/compile, and bypass tests.
Do not contact cloud/providers, deploy, contain, launch, edit incident markers,
or resolve owner decisions. Commit only scoped work, leave the worktree clean,
and write exact commit/tree/files/tests/limitations to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-sol-implementation-result.md`.

Do not mark T1.1 formally complete without independent Sol review and accepted
owner/integration receipts.
