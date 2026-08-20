# T1.5 bounded repair pass 3

You are the mutation-authorized Sol-high implementer for one bounded follow-up
repair. Work only in:
`/private/tmp/arnold-critique-recovery-simple-fixer-20260802`

Frozen input identity:

- exact clean commit `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`
- tree `5077ceff4e9ccd8958051acd999fb86172233f8f`
- independent HARD FAIL report:
  `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-independent-review-pass2-luna-result.md`
- report SHA-256:
  `9f393b1760ecdf047de7cb8129b6d4db4fa23e1dfaf1fda8b94b8611323ccee4`

Read the full report and the prior implementation result before editing. Preserve
the repairs that independently passed: B1 owner authority, B3/B4/B5 point-of-use
retirement, and B6 separate fix-the-fixer/provenance behavior. Fix only the
remaining B2/B7 closure:

1. Coordinated result + receipt substitution must not make `_stored_result`
   replay a forged result projection. Bind replay to immutable owner truth and
   the canonical intent/attempt/occurrence/authorization/effect identities, not
   merely mutually consistent caller- or store-selected keys. Missing,
   substituted, corrupt, or cross-occurrence data must be typed UNKNOWN and
   never redispatch.
2. Dynamic inventory must discover an ordinary imported Megaplan recovery
   function that calls `subprocess.Popen` (and equivalent direct effect aliases),
   even when its module is otherwise classified as Megaplan/canonical. Do not
   fix this with another static allowlist or filename list. Canonical owner
   surfaces may be exempt only by exact structural proof.
3. Restore meaningful per-subject retirement negatives for the 28 historical
   modules / 674 functions / 741 cases. Do not satisfy them all through one
   generic helper or blanket parametrization that never exercises the original
   subject. Each collected case must invoke or inspect its original seam and
   prove typed retirement/no side effect/no launch. A mechanical shared assertion
   is fine only after the original subject-specific path has actually executed.

Add the exact hostile regressions from the review. Run focused tests first, then
the dynamic inventory and honest collection checks. Run the full cloud and wheel
suites single-flight only after focused closure; disk is tight. Do not touch
cloud/provider/production owner/checklists/main worktree or unrelated code. Do
not weaken or delete test cases to make them pass.

Commit the bounded repair, verify exact commit/tree and clean worktree, and write
an implementation result to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-repair-pass3-sol-result.md`

Return only exact commit, tree, validation summary, report path and full-file
SHA-256. Do not claim acceptance; a fresh independent review follows.
