# Batch 2 attempt 18 — cumulative evidence seal

Sealed `2026-08-31T03:05:17Z` on branch `reconcile/nbf-attempt4-2297`, before
the checkpoint commit.  The candidate is the full reviewed dirty tree against
`HEAD 2297fb330cdb375b4e5bd048f0d5c37d0e06db30`; source base remains
`origin/main@798c50619204010ed3f4297fbb57988fe9381924`.

## Custody and frozen inputs

Gate4 is the custody-reconciled cumulative branch from `2297`.  Source bytes
are preserved.  The checkpoint commit contains cumulative reviewed Batch 1 +
Batch 2 state because the original Batch 1 checkpoint ancestry was not
imported.  The frozen inputs were not edited:

| artifact | SHA-256 |
|---|---|
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/rework/batch-2-attempt-18.md` | `7ce4d864e168375d53623fc4b0eb489c84e212a2298150687558d47f1047b38e` |

## Candidate bytes

The source/test candidate is 24 tracked paths plus three new physical-door
tests.  Hashes are computed against the pre-commit `HEAD` and include tracked
diff bytes plus `git diff --no-index /dev/null` bytes for the three untracked
source/test files:

- tracked source/test diff: `a2657a6a23a451c115d50e6c838a0b6bd17ea159293289fe4b20dd9483822a06`
- full tracked + untracked source/test diff: `a2e9f838c60bd49fe66fa7826d1a751cb98b8f5e4f7884cf789d4e1c3f479fbf`
- sorted source/test path manifest: `36c475cbfd56fb1c894cd8b1122a0163af97c639dd7a8f9e66c50e1a31ef2301`

## Review disposition

Five independent Luna reviews converged on acceptance of the cumulative
candidate: ambiguous reopen `PASS`; contract `PASS`; focused regression
`PASS` with broader results unclassified; expanded review 4 `PASS` (439
passes, documented baselines only); review 5 `PASS_BATCH_2`.  The final local
evidence was 27 lifecycle/reconciliation passes, 59 physical/handler/phase
passes, 166 focused Batch-2 passes, 48 bounded OMP-adapter passes, checker
`ok: true`, targeted compile pass, and `git diff --check` pass.

Documented exceptions are the historical provider-credit/balance blocks and
the previously recorded baseline-only failures (tiered execute provider
fallback, resident runner, and two babysitter routing/managed-spec cases);
they are not candidate-caused Batch-2 failures.  No broad unclassified result
is treated as a pass.

The controlling Sol scope is unchanged: one earlier Sol ruling only; no second
Sol, no second managed WBC authority, and no Batch-3/provider-policy,
scheduler, journal, network, or taxonomy redesign.
