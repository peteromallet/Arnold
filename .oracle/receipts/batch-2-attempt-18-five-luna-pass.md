# Batch 2 attempt 18 — five-Luna PASS receipt

- Branch: `reconcile/nbf-attempt4-2297`
- Pre-commit candidate HEAD: `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Bound executor brief: `.oracle/rework/batch-2-attempt-18.md`
  (`7ce4d864e168375d53623fc4b0eb489c84e212a2298150687558d47f1047b38e`)

## Verdict chain

The five independent Luna verdicts are: ambiguous `PASS`; contract `PASS`;
focused regression `PASS` with broader results unclassified; expanded review 4
`PASS` with 439 passes and documented baselines only; review 5
`PASS_BATCH_2`.  These accept Batch 2 tasks `NBF-02` and `NBF-03` after the
legacy ambiguous reopen hold was proven repeatable without new lifecycle or
launch effects.  The normal reservation lifecycle remains exactly
`not_started -> entered -> accepted -> closed`.

Evidence: 27 lifecycle/reconciliation, 59 physical/handler/phase, 166 focused
Batch-2, and 48 bounded OMP tests passed; checker, targeted compile, and diff
check passed.  Historical provider-credit blocks, environment notes, and
documented baseline-only failures remain exceptions, not candidate failures.

## Acceptance and custody

Batch 2 is `PASS`; checkpoint state transitions `pending -> committed` in the
checkpoint commit.  Strict progress is `3/7 = 42.9%`; batches are `2/5 = 40%`;
next is Batch 3.  Gate4 is the custody-reconciled cumulative branch from 2297;
the commit carries reviewed cumulative Batch 1 + Batch 2 source bytes because
the original Batch 1 checkpoint ancestry was not imported.  One controlling
Sol ruling was already used; no second Sol and no managed second-WBC authority
are permitted.  Frozen tasklist, North Star, plan, goal, and custody remain
unchanged.

Candidate hashes: tracked source/test diff
`a2657a6a23a451c115d50e6c838a0b6bd17ea159293289fe4b20dd9483822a06`; full
source/test diff `a2e9f838c60bd49fe66fa7826d1a751cb98b8f5e4f7884cf789d4e1c3f479fbf`;
path manifest `36c475cbfd56fb1c894cd8b1122a0163af97c639dd7a8f9e66c50e1a31ef2301`.
