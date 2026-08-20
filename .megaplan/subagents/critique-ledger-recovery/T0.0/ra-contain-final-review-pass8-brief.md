# RA-CONTAIN independent final review — pass 8

You are GPT-5.6 Luna at high reasoning. Perform a fresh, adversarial,
read-only review of exact candidate commit:

`48648b485aa3dc8fc4c5fe9552c31a3df37c61d7`

Worktree:
`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Do not trust the implementer, prior tests, or prior review narratives. Do not
edit source code, amend commits, deploy, SSH, or mutate cloud state. You may
write only your review result to the path named below and may create disposable
test output outside the repository.

This is pass 8 because earlier reviews found real authority and recovery bugs.
Reproduce or refute every pass-7 finding against the exact candidate:

1. reconciliation's own final-CAS response loss could strand state;
2. signed requests could expire while waiting for the lock, then execute;
3. one-time provisioning genesis response loss could strand an anchor without
   a recoverable journal;
4. terminate ignored the signed exact target tuple;
5. sequence-zero and pending head schemas were too permissive.

Then attack the complete RA-CONTAIN boundary independently:

- production authority cannot be self-created, duck-typed, or replaced by a
  local shell/marker/file owner;
- provisioning is authenticated, one-time, exact-domain/path bound, and
  response-loss/replay safe;
- every mutating request is signed, canonical, fresh both before and after lock
  acquisition, nonce/idempotency safe, and exact-tuple/CAS bound;
- issue, terminate, and reconcile survive crash/response-loss at every durable
  boundary without duplicate mutation or permanent unresolvable state;
- the external owner head and local journal cannot roll back, fork, splice,
  truncate, or accept structurally invalid state;
- recursive reconciliation cannot recurse forever, reuse the wrong identity,
  or skip target/result validation;
- six effect classes are denied while reads remain available;
- CLI/installed package/public source path fail closed where production owner
  capability is unavailable;
- two processes and stale writers cannot both win.

Run the relevant existing tests plus your own targeted probes. Inspect the
exact diff from its base and source implementation, not just tests. A passing
test suite is not enough if the design permits an authority bypass.

Write the durable report to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass8-result.md`

The first line must be exactly `PASS` or `FAIL`. On PASS, enumerate the evidence
and commands. On FAIL, give minimal reproductions, affected files/lines, and the
required correction. State explicitly that this is only a local candidate
review and does not itself prove formal T0.0 or authorize cloud containment.
