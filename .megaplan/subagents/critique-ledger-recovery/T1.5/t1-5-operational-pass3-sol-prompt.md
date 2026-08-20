# T1.5 operational pass 3 — authenticated effect receipt only

You are the sole mutation-authorized Sol-high implementer for the operational
relaunch gate. Work only in the clean worktree:
`/private/tmp/arnold-critique-recovery-t1-5-operational-pass3-20260802`

Frozen base:

- commit `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`
- tree `5077ceff4e9ccd8958051acd999fb86172233f8f`

Read the T1.5 pass-2 independent report and the current durable state. The base
already passes the operational provenance, exact-occurrence, one-attempt,
point-of-use retirement and notification-quiet-path checks. Preserve those.

## Sole code objective

Fix the coordinated result/receipt replay defect without changing inventory or
historical tests. The SQLite attempt/result/claim/effect tables are mutable
projections, not authority. A successful replay must require an independently
authenticated effect-owner/WBC receipt whose authentication material is not in
that SQLite database.

The receipt must bind at least: occurrence, attempt, canonical intent digest,
claim ID/epoch/fence, authority/owner revision/fence, WBC GLEK, effect request
digest, outcome and provider/effect ID. Missing, corrupt, transplanted,
unverifiable or unavailable proof is typed UNKNOWN/INDETERMINATE and never
success or redispatch. Fresh-process replay must verify the same external/keyed
proof.

For the test-only owner, an HMAC-SHA256 receipt with an explicit test-only key
injected at construction/reopen is acceptable: the key must never be stored in
the SQLite database or exposed by a production caller surface. Production
continues to rely on the authenticated fixed owner service; do not invent a
caller-minted key or authority envelope.

Required exact hostile test:

1. Start with `after_effect_ambiguity_commit`, so the attempt is
   `EFFECT_POSSIBLY_APPLIED` and `_simulate_effect()` never ran.
2. In one SQLite transaction fabricate mutually consistent
   `simulated_effects`, `attempts` success result/receipt and released claim,
   using all public deterministic fields/helpers.
3. Reopen a fresh test owner with the unchanged legitimate key/owner record.
4. Reconciliation must reject/return UNKNOWN and the effect count remains zero.

Also prove valid success and exact replay across a fresh process, wrong-key and
cross-occurrence transplant rejection, deletion/corruption => UNKNOWN, and no
second effect/attempt. Use focused tests only.

## Hard scope limit

Allowed source/test files are only:

- `arnold/recovery/simple_fixer.py`
- `tests/cloud/test_simple_fixer.py`

Do not edit `bypass_inventory.py`, retirement contracts, any of the 28
historical test modules, wrappers, packaging, cloud/runtime code, or any other
file. Do not restore 741 tests, scan the whole platform, spawn/delegate another
agent, or run broad/cloud/wheel suites. Generic B7 debt is in the follow-up
epic.

Run the focused simple-fixer test module plus exact new hostile cases, lint/
compile/diff check for the two allowed files, commit cleanly, and write the
implementation result to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-operational-pass3-sol-result.md`

Return exact commit/tree, tests, report path and SHA-256. Do not claim
acceptance; an independent reviewer follows.
