# T1.8 GEN-DEPLOY bounded repair pass 3 — GPT-5.6 Sol-high

This is a 🔥 VERY HARD implementation task. Work only in
`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802` from exact
clean commit `148465a109ade4318e4cb9ae13a83645a4bf2934`, tree
`505b8104ba4fc5298e8efde384551e2310ec81e4`.

Read the independent pass-3 report at
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass3-sol-result.md`,
SHA-256 `bff46dc2b888e989ae9099d6270f4a4dac0c37dbdaf80e1fd1eba43fdf9b887a`.

Fix exactly the two authoritative semantic blockers and close the independent
installed-evidence gap. Do not reopen the already-passing namespace architecture
or broaden the authority model.

## A. Bind rollback verification to the exact signed live generation

- Every compatible-rollback execution, receipt, reconciliation and independent
  verification must recompute the observed installed generation/vector/manifest
  digest and compare it to the owner-signed expected generation digest.
- Never trust the `available` mapping key, selector string, attested-generation
  string, cached receipt, or an internally consistent substituted manifest.
- Bind source commit, artifacts, schemas, services, role/process vector, target,
  state lineage and manifest bytes to the recomputed digest.
- Missing, corrupt, truncated, relinked, or coherently substituted generation +
  manifest must return a typed fail-closed/UNKNOWN result as appropriate, never
  affirmative verification.
- Make any forward migration material executable and independently observable,
  or explicitly fail closed until a signed materialized migration artifact is
  available; a bare `migration_digest` must not imply execution.

Required exact regression: reproduce pass-3 counterexample A by replacing the
rolled-back generation source commit with forty zeroes and rewriting a matching
canonical manifest under the signed digest key. Verification must reject it and
identify the signed-vs-observed digest mismatch.

## B. Persist pre-effect displaced-writer lineage across crash/replay

- Capture the exact pre-CAS selector/generation/revision and displaced writer
  identities in durable operation intent before any target mutation.
- Bind that observation into the signed/owner-authorized operation subject and
  final canonical receipt. It must survive response loss, store reopen and fresh
  adapter/process replay.
- After `after-recovery-selector-cas` or any later crash, reconciliation must
  adopt the already-applied effect from durable observed evidence and must not
  redispatch or recompute displaced writers from the newly active runtime.
- Reject exactly the original displaced writers, never current newly started
  writers. Verification must prove the rejected identities equal the durable
  pre-effect set and differ appropriately from current running identities.
- Exact replay returns the same complete canonical receipt; conflicting replay,
  stale fence/revision/nonce and incomplete lineage fail closed.

Required exact regression: extend the pass-3 counterexample B so a crash at
`after-recovery-selector-cas`, fresh store/adapter replay and verification prove
the original writer lineage is preserved, the new current writers are not marked
displaced/rejected, and no second effect occurs.

## C. Bounded evidence matrix

Retain and rerun:

- full `tests/arnold_pipelines/release_authority` suite;
- the 84-test import/CLI/bypass suite;
- the installed wheel/minimum/locked entrypoint suite single-flight;
- exact accepted-active rollback/forward-fix, response-loss, backup damage,
  ancestor replacement, two-process, production-fail-closed and byte-parity tests;
- static, compile, dependency and diff checks.

Add no unrelated redesign. Use existing package caches or record an exact external
environment limitation; do not weaken the installed test. Delete only explicit
inactive reproducible scratch after evidence capture. Do not touch cloud/provider/
production owner state, git outside this worktree, or checklist state.

Commit scoped changes, leave the worktree clean, and write exact commit/tree/
parent/files/tests/limitations to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-repair-pass3-sol-result.md`.

No formal T1.8/release/deploy completion claim is allowed without a new independent
Sol-high review and later owner/deployed evidence.
