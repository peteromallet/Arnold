# Batch 1 check-in — independent review pass (GPT-5.6 Luna)

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: GPT-5.6 Luna. Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate.

You are the INDEPENDENT REVIEW PASS for Batch 1 of a megado run. Read-only; do not edit. Worktree: `/Users/peteromalley/Documents/arnold-oracle`.

Read:
- `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/tasklist.md` (frozen — Batch 1: T1 normal, T3 [XHARD])
- The batch delta: `git -C /Users/peteromalley/Documents/arnold-oracle diff 796961cd9c..9224f52ce2` (arnold.md reflow + parity test in tests/agentbox/test_resident_profile.py)

Batch 1 acceptance (from the frozen tasklist):
- T1: installed package exposes `arnold`; `~/.bun/bin/agent list` and `agent run arnold "State your name and rules."` succeed from repo root; installed copy byte-identical to packaged source; no alternate runtime added.
- T3: raw body is exactly `system_prompt().encode() + b"\n"`; omp-parsed (trimmed) body byte-equals `system_prompt().encode()`; parity test fails on content/wrapping/trailing-LF/blank-separator drift; semantic changes require both surfaces + version bump (documented in test).
- Known pre-existing env gap (NOT a batch defect): 6 resident-runtime tests fail at `canonical runtime launch seed is required but missing` (attestation env); Batch 5 T8 resolves it.

## Your verdict
Verify the delta against the acceptance criteria and the North Star (raw parity, one identity seam, no compat renames, no omp changes, elegance). Check: does the reflow preserve the prompt semantics? Is the parity test correctly modeling omp's `parseFrontmatter` (first `\n---` after offset 3, trim, CRLF→LF)? Is anything overengineered or under-tested?

Output: verdict line `PASS` or `ISSUES`, then numbered findings (each: blocking/advisory, evidence, one-line fix). Bias toward elegance. Under 250 words.
