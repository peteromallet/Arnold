# RA-CONTAIN adversarial review pass 6

Perform a fresh READ-ONLY adversarial review of exact commit:

`611321c79c70d3ec75cf6f7be6ba3df275eb5e81`

in worktree:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Use GPT-5.6 Luna high reasoning. Do not edit, commit, push, deploy, mutate cloud state,
or trust prior reviewers/tests. You may run tests and ephemeral local fault scripts.

## Intended contract

This is a minimal Run Authority containment primitive used to deny
`resume/repair/execute/publish/notify/deployment` for one exact tuple while preserving
read-only observation. Production authority must be an externally owner-controlled,
monotonic anchor/capability—not an adjacent file or caller-provided secret. Mutation
requests must be authenticated, strictly bound, CAS-fenced, replay-safe, and auditable.
Storage ambiguity must fail closed and require explicit signed reconciliation.

## Re-test all prior failures

1. rolling back/truncating/replacing journal state must not resurrect authority;
2. rolling back both local journal and adjacent local metadata must not resurrect it;
3. same decision/operation ID with divergent content must never be accepted;
4. malformed receipts, TTLs, booleans-as-ints, NaN/Infinity, unknown fields, and invalid
   semantic relationships must fail closed;
5. CLI errors must be traceback-free and machine-readable;
6. crash/exception after durable append or anchor commit must not be reported/retried as
   ordinary success or duplicate an effect;
7. pending/committed anchor writes must survive partial/torn writes without destroying the
   last committed owner head;
8. reconciliation must not tear/corrupt the canonical journal and must only adopt the exact
   fully authenticated candidate;
9. owner identity must enforce the actual signing capability; no public bearer token, raw
   secret attribute, compare-excluded secret, argv secret, env fallback, or same-owner
   wrong-key acceptance;
10. authenticated head and journal semantic relationships must be complete, including
    genesis/cursor/revision/operation/candidate/receipt relationships;
11. concurrency across threads/processes must produce one valid state history;
12. TTL and revoke behavior must be deterministic across restart/clock boundaries.

## Additional main-agent concerns

- Inspect the CLI `check` command: it must accept and enforce the requested effect, not
  silently hard-code `observe`; denied effect queries are part of the installed contract.
- Determine whether there is any usable production construction/adapter path. A library
  that only works with test-local/in-memory backends and a CLI that always rejects
  production does not by itself satisfy T0.0, even if it is a sound substrate. Clearly
  separate code correctness from deployability/authority availability.
- Verify changing the prior independence test to allow `pathlib` and `sqlite` does not
  violate the Run Authority architecture boundary or merely weaken a binding test.
- Verify the external backend cannot equivocate, roll back, fork, or accept a caller-chosen
  domain/trust bundle/provisioning envelope that self-authorizes.
- Verify status/check do not trust unauthenticated local projections over the owner anchor.
- Verify signed-envelope replay semantics across restarts and different journal paths.

## Deliverable

Write the review to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass6-result.md`

Start with exactly `PASS` or `FAIL`. A PASS means no correctness/security defect was found
in the local primitive; it must still state whether formal T0.0 is incomplete because no
accepted production owner backend/deployment/decision exists. For every failure, include
severity, exact file/function/line, a concrete reproduction or reasoning chain, and the
minimum root fix. Include exact commands/tests run. Do not give credit for tests that only
assert the implementation's own assumptions.
