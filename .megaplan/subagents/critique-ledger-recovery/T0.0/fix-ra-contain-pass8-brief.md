# RA-CONTAIN repair — pass 9 from pass-8 blockers

You are GPT-5.6 Luna at high reasoning. Repair exactly the two independently
confirmed blockers in candidate commit:

`48648b485aa3dc8fc4c5fe9552c31a3df37c61d7`

Worktree:
`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Read the full review first:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass8-result.md`

Required corrections:

1. Reconciliation must be bound before any reservation or mutation to the exact
   tuple of the unresolved transition and to the exact tuple of any adopted
   active/terminated result. Persist an authenticated exact tuple or target
   digest in pending/indeterminate owner state, validate the signed reconcile
   target against it before reserving the nonce or performing either CAS, and
   validate durable/adopted results before any mutation. Cover unresolved issue,
   unresolved terminate, durable reconcile recovery, response-loss retry, wrong
   target, and result mismatch. A post-CAS check is not acceptable.

2. Provisioning must require an exact type/operation pair. A signed
   `envelope_type="provision"` carrying `operation="issue"` (or any non-provision
   operation) must be rejected without anchor/journal/nonce mutation. Prefer one
   canonical type-to-operation validation map so future envelope types cannot
   drift. Add the reviewer's reproduction and every wrong-operation variant.

Preserve all pass-7 fixes and the existing fail-closed production boundary.
Audit state-specific head schemas after adding tuple/digest fields: exact field
sets, revisions, receipts, replay, response-loss adoption, and predecessor rules
must remain strict. Run the focused containment tests, dependency-closure tests,
new probes, formatting/static checks, and `git diff --check`.

When and only when all evidence passes, create one new commit on the existing
branch and leave the worktree clean. Write a concise result with commit SHA,
tests, and remaining limitations to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-pass8-repair-result.md`

Do not deploy, SSH, mutate cloud state, edit the master checklist, or claim
formal T0.0 completion. This produces only another local review candidate.
