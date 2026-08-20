# GPT-5.6 Sol-high implementation — GEN-DEPLOY repair pass 2

Repair exact clean candidate `dae901e9bf2ecf289ad0aa201c50116f8bf1f899`
in `/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`.
This is a 🔥 VERY HARD mutation lane. Start only when a mutating slot is free.

Read the full T1.8 plan requirements, pass-1 implementation result, and the
complete independent hard-fail report:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass2-sol-result.md`.
Preserve every already-proven authority, custody, exact-vector, response-loss,
wheel, and fail-closed property. Fix both blockers at their roots:

1. **Stable exclusion identity across ancestor replacement.** A new store or
   process must not derive a fresh lock domain from a pathname whose ancestor can
   be displaced while another holder remains live. Design a hermetic owner-root
   capability/descriptor identity whose namespace cannot silently split for the
   complete transaction. Detect replacement before every irreversible boundary;
   abort/fence without overlapping effects. Production must still require the
   privileged owner executor/descriptor custody and may not mistake the local
   defense for production authority. Cover ancestor, lock parent, lock file,
   database, selector, target, symlink/mount-shaped, rename/recreate, process,
   crash/restart, and stale-descriptor cases.
2. **Executable backup/restore and real recovery.** Replace digest-only recovery
   labels with a durable, fenced transaction that actually creates/verifies a
   backup, damages/restores only in hermetic tests, compares restored bytes/state/
   schema/vector to the signed expectation, and derives receipts from observed
   results. Rollback must materialize and verify an exact compatible prior
   generation; incompatible state must use a separately signed, materialized,
   migrated, verified forward-fix generation. Recovery must handle a damaged
   accepted active generation, not only an indeterminate deployment. Preserve
   intent-before-effect, exact idempotency, response-loss indeterminacy,
   no-redispatch, selector CAS, writer fence, runtime start, and independent
   observation across every restore/forward-fix boundary.

Implement the exact tests named in the hard-fail report plus: two-process overlap
under ancestor replacement; crash at every backup/read/write/fsync/CAS/start/
receipt edge; missing/corrupt/truncated/substituted/non-restorable backup;
wrong bytes/schema/state/vector/runtime; compatible rollback; incompatible
forward-fix; accepted-active damage; response loss and replay; installed-wheel
CLI/API at minimum and locked dependencies; detached archive/source-wheel byte
parity; materialized wrapper parity; production-owner absence and constructor
forgery; and broad dependency/bypass suites. Large wheel validation must be
single-flight and its reproducible scratch removed after capturing results.

Do not contact cloud/providers, deploy, switch a real generation, or mutate owner
state. Commit only scoped changes, leave the worktree clean, and write exact
commit/tree/files/tests/limitations to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-repair-pass2-sol-result.md`.
Do not claim formal T1.8 completion; owner-installed production adapters,
generation selection/cutover, and accepted receipts remain external.
