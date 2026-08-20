# RA-CONTAIN — Luna repair pass 9

Work only in `/private/tmp/arnold-critique-recovery-ra-contain-20260802` as the
GPT-5.6 Luna mutation-authorized implementer. Exact candidate is
`6ef77bebb3c3b9f0ec0aeb478945619b54c815f3`.

Read the complete independent FAIL report:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass9-result.md`

The pass-8 target-binding and provision-operation defects are fixed and must
remain fixed. Repair the remaining post-CAS reconciliation defect at root.

`reconcile()` must never durably commit the journal/owner head and then report
a repeatable failure because TTL/effect/status checks ran afterward. Make all
failure-capable result, receipt, TTL, policy, tuple, digest, revision, and state
checks deterministic and complete before the final owner CAS using one fixed
evaluation instant. After a successful final CAS, return the exact authenticated
durable result without any new failure-capable validation/read. If any genuinely
unavoidable post-CAS uncertainty remains, route it through the existing typed
indeterminate protocol and make exact replay/fresh signed reconcile converge to
an honest terminal response.

Add mandatory regressions for:

- issue final-CAS response loss followed by reconciliation after receipt expiry;
- successful reconcile final CAS followed by a transient status/read failure;
- exact replay after each boundary returning the same durable response;
- no response path that says failure while the owner head/journal are committed;
- all prior wrong-target, durable-result-tuple, provisioning-operation, lock/
  expiry, genesis, nonce, rollback/fork, race, and seven-effect invariants.

## Root correction after inspecting the interrupted first attempt

Do **not** make an expired but authenticated candidate receipt cause
reconciliation to refuse before mutation and leave the owner transition
permanently unresolved. Reconciliation establishes/adopts what durably happened;
policy evaluation determines what may happen next. Those are separate facts.

For an issue final-CAS response loss whose authentic active receipt has expired
by reconciliation time, reconciliation must still converge the owner head and
journal to the exact durable result and return that result honestly. Subsequent
`check()` calls must fail closed because the receipt is expired. It is acceptable
for a pre-CAS policy evaluation to compute/record the expected deny state, but
expiry is not a reconciliation failure and must not strand the transition.

The interrupted dirty patch currently has `_validate_reconcile_preflight()`
re-raising `PolicyRefusal` for an expired active receipt; correct that design.
Also scrutinize the new `verify_backend_receipt=False` preflight: it must validate
the complete candidate deterministically without pretending to verify an owner-
generated receipt that does not exist until CAS, and the post-CAS response-loss
path must still distinguish success, stale conflicting CAS, and uncertainty.

Run the focused and dependency-closure suites plus static/diff checks. Create
one new commit, leave the worktree clean, and write:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-repair-pass9-result.md`

Do not deploy, use SSH, mutate cloud state, edit the master checklist, or claim
formal T0.0. This produces only a candidate for fresh independent Luna review.
