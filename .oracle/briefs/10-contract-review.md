# Pre-execution contract review brief — GPT-5.6 Luna (independent review pass)

You are an independent reviewer performing the pre-execution contract check for a megado run. Read-only: do not edit files. Worktree: `/Users/peteromalley/Documents/arnold-oracle`.

Read these artifacts in order:
- `.oracle/northstar.md` — durable end state, principles, anti-patterns
- `.oracle/agent_goal.md` — frozen run contract (scope, authorization, model policy, done criteria, validation, sync policy)
- `.oracle/plan.md` — the final 11-task plan (Sol)
- `.oracle/tasklist.md` — the batched tasklist (7 batches, checkpoints, classifications) proposed by Sol
- `.oracle/custody.md` — baseline + verified facts
- `.oracle/findings/*.txt` — exploration evidence (skim)

## What to verify (operational completeness against agent_goal.md)
1. Every agent-goal done criterion and validation command is covered by some task/batch in the tasklist — list any uncovered criterion explicitly.
2. Batch ordering is dependency-correct (parity before generator, seam before external loading, attestation before launcher wiring); checkpoints are verifiable one-liners.
3. Authorizations: the run mutates only the worktree, commits per batch, pushes only `oracle-run` at the end, never `main`; `.oracle` artifact commit policy matches the goal.
4. Model policy: normal → GPT-5.6 Luna, [XHARD]/oracle → GPT-5.6 Sol, as declared; tasklist classifications (T1,T2,T4,T6,T9,T11 normal; T3,T5,T7,T8,T10 [XHARD]) are sensible.
5. Non-goals are respected by the tasklist: no purge work, no compat-surface renames, no omp source changes, no Discord tool-catalog changes, no attestation bypass/counterfeiting.

## What to verify (directional alignment against northstar.md)
6. The plan advances the named-agent platform end state (one runtime, markdown identity, cross-repo reproducibility) and does not reproduce any named anti-pattern.

## Output
- Verdict line: `CONTRACT OK` or `CONTRACT ISSUES`
- Numbered findings: each with severity (blocking / advisory), the artifact+section it refers to, and a one-line suggested fix. Bias toward elegance (KISS/YAGNI) — flag overengineering too.
- Under 350 words. No fan-out, no duplicate passes.
