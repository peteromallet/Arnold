# Pre-execution review — Sol v7

## Verdict

**BLOCKED**

The proposed tasklist is correctly bound to settled plan v7 and preserves the
core product contracts, but it is not ready to freeze because four execution
and review contradictions remain.

## Evidence

1. **The mandatory fresh Luna v7 sense-check is missing.** Settled plan v7
   requires a fresh complete GPT-5.6 Luna settled-plan sense-check before
   freeze (`.oracle/plan.md:3164`). The tasklist instead makes a fresh
   GPT-5.6 Sol review sufficient (`.oracle/tasklist.md:1066`). The latest Luna
   receipt is bound to superseded plan v6 and returned BLOCKED
   (`.oracle/receipts/preexecution-review-luna-v6.md:13-19`).

2. **The external inventory digest is required before it is permitted to be
   recorded.** The tasklist says the inventory artifact SHA-256 is recorded
   only after the exact final candidate SHA is frozen
   (`.oracle/tasklist.md:580`), but the Batch 3 gate requires external inventory
   SHA-256 evidence before NBF-06 and NBF-07
   (`.oracle/tasklist.md:631-663`). Settled plan v7 contains the same conflict:
   `.oracle/plan.md:2533` defers the digest until candidate freeze while
   `.oracle/plan.md:2584-2586` requires it at the NBF-05 synchronization point.

3. **NBF-06 drops a required worker-disposition regression suite.** Settled
   plan v7 includes
   `tests/arnold_pipelines/megaplan/test_worker_disposition.py` in the NBF-06
   focused validation (`.oracle/plan.md:2731-2750`). The tasklist omits it from
   both the NBF-06 owned existing suites and focused command
   (`.oracle/tasklist.md:695-707`, `.oracle/tasklist.md:750-768`), even though
   NBF-06 edits disposition surfaces and gates disposition/streak
   interleavings.

4. **The final clean-tree proof is ambiguous against protected untracked
   custody.** The tasklist requires the worktree to be "exactly clean"
   (`.oracle/tasklist.md:911`) while `.oracle/custody.md:30-31` and settled plan
   v7 require protected untracked artifacts to survive. Settled plan v7's
   actual rule is tracked/index cleanliness plus an untracked-file check
   appropriate to custody (`.oracle/plan.md:1865-1866`). The tasklist must use
   that executable definition rather than an impossible literal-empty status.

## Minimal corrections

1. Add the plan-required fresh complete GPT-5.6 Luna review bound to the final
   corrected plan/tasklist digests, then run a fresh Sol freeze decision.
2. Defer the authoritative external inventory artifact SHA-256 to NBF-07 after
   candidate-SHA freeze. Remove it from the Batch 3 gate and correct the
   conflicting NBF-05 synchronization text in the settled plan, or explicitly
   distinguish a non-authoritative interim checksum from final evidence.
3. Add `tests/arnold_pipelines/megaplan/test_worker_disposition.py` to NBF-06's
   owned suites and focused validation command.
4. Define clean-tree proof as clean tracked and index state plus no unexpected
   untracked files, with the exact protected custody allowlist and its identity
   recorded in evidence.

## Preserved contracts

The remaining highlighted contracts are represented correctly: explicit
`DispatchOutcome(kind=worker_disposition)` maps once to the canonical
`worker_terminal_outcome` writer without coercion or duplicate disposition
append; `source_inputs_sha256` is non-circular; final integration is
commit-first and restarts validation/review after any mutation; T8 streaks are
formed only by accepted exhausted worker outcomes; dependencies and ownership
are ordered; delivery pushes the exact reviewed SHA; and no merge to `main` is
authorized.

