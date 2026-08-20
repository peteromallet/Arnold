# T1.8 GEN-DEPLOY — bounded GPT-5.6 Sol-high repair pass 4

This is Stage-A critical and 🔥 VERY HARD. Work only in
`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802` from exact
clean HARD-FAIL head `26d240339e0911a0e7347fc7849c8e151ab92111`, tree
`b8e5e1bc50f04942d21d71458260d94594e11e69`.

Read the independent pass-4 report:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass4-sol-result.md`

Full-file SHA-256:
`8cef8bb86ec12bb88eb79f9bf37a936bb4aeba2c1ef42449a64daa17e25ff54b`.

Fix the single reproduced blocker only. Do not broaden release architecture,
generic storage, cloud supervision, or production adapters.

## Required correction

- A rollback RecoveryDecision/RecoveryResolution binding target
  `hermetic:control-plane` must reject before any manifest materialization,
  runtime activation, selector CAS, store resolution, or other effect when the
  restored GenerationVector or canonical backup state names any different
  target (the reproduced `hermetic:wrong-target` case).
- Bind the authoritative target identity through contract validation,
  pre-effect executor validation, reconciliation, persisted intent/receipt and
  independent verification. Do not self-compare by passing the restored
  generation's own target into live observation.
- Exact replay and response loss remain idempotent. A wrong target is typed
  fail-closed with zero mutation, including fresh-process replay and coherent,
  owner-signed/digest-recomputed material.
- Preserve the already accepted closures: exact generation/manifest/migration
  recomputation, durable pre-CAS displaced-writer lineage, crash cuts, selector
  fencing, installed source/minimum/locked parity, and production fail-closed.

## Mandatory finite evidence

1. Add the reviewer's exact signed, digest-coherent wrong-target rollback probe
   as a committed regression; assert no selector/runtime/store resolution or
   other external effect occurred.
2. Cover initial execution, reconcile, exact replay, response loss and fresh
   process; wrong target must never become an accepted receipt.
3. Run the exact blocker slice, full release-authority suite, 84 import/CLI/
   wrapper closure suite, and the 11-test installed-wheel parity suite
   single-flight.
4. Run ruff/compile/diff/dependency checks appropriate to changed files.

Do not touch cloud/provider/production owner state, selectors, markers, plans,
checklist or git outside this worktree. Commit scoped code/tests, leave clean,
and write exact commit/tree/parent/tests/limitations to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-repair-pass4-sol-result.md`

No T1.8 completion claim without a new independent Sol-high review and later
installed production owner receipts.
