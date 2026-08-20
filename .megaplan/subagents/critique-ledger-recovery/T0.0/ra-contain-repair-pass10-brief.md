# RA-CONTAIN — Luna repair pass 10

Continue in `/private/tmp/arnold-critique-recovery-ra-contain-20260802` from
exact clean candidate `fd038f3aab9da495dda0b59a448dd8ef78fe54ee` as the
GPT-5.6 Luna mutation-authorized implementer.

Read the complete pass-10 FAIL artifact:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass10-result.md`

Preserve every prior invariant, especially expired-candidate adoption followed
by fail-closed policy checks. Repair the two remaining protocol failures at root:

1. Never ignore the final `compare_and_swap()` response. Validate the returned
   owner head, owner/backend receipt, exact prepared candidate fields, revision,
   sequence, tuple, journal/result digests, and operation before returning
   success. A backend that returns the prior/unchanged head, a malformed head,
   or a different committed head must never yield success.
2. Handle `StaleCAS` separately. Read current owner state and accept only if it
   is the exact authenticated already-committed candidate for this request and
   durable record. Otherwise propagate a typed stale conflict without converting
   it into generic uncertainty or overwriting the conflicting head.
3. For response loss, malformed/unverifiable result after possible effect, or
   read failure while reconciling the result, record typed indeterminate state
   only when safe and make exact replay/fresh signed reconciliation converge.
   Never report categorical failure or success when effect truth is unknown.

Add mandatory regressions for no-op/unchanged CAS return, altered response,
malformed/missing receipt, exact already-committed `StaleCAS`, conflicting
`StaleCAS`, response loss, read-after-stale failure, and restart recovery. Assert
owner head/journal/nonce mutation boundaries and error types exactly. Retain all
48 focused and 79 dependency-closure prior tests.

Run focused, dependency-closure, compile, diff, and scoped static checks. Create
one new clean commit and write:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-repair-pass10-result.md`

Do not deploy, SSH, mutate cloud state, edit the master checklist, or claim
formal T0.0. This produces only a new candidate for another fresh review.
