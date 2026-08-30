# Sol Oracle fallback v2 — Batch 2

Grok 4.6 is unavailable: the attempted Grok 4.6 Batch-2 gate failed with HTTP 402 `Grok Build usage balance exhausted`. The user explicitly ordered autonomous continuation, so perform this gate as GPT-5.6 Sol and record that fallback honestly. Do not claim Grok performed it.

You are the Oracle/validator, not an executor. Candidate `/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch `megado-nbf-guard-0826`, Batch-1 passed at `878a9b2980f0eab6642ed51c30e687903a7213b9`, current Batch-2 candidate at `19deab5bb407273e7e82d40a66fc06d17af93ad4` plus current dirty implementation/test files. Read complete `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/plan.md`, Batch-2 sections of `.oracle/tasklist.md`, Batch-1 PASS gate, and current Luna execution finding/receipt. Commission exactly one fresh independent GPT-5.6 Luna high-reasoning review of the current candidate against every NBF-02/NBF-03 criterion. Luna must write only `.oracle/checkins/batch-2-luna.md` and `.oracle/receipts/oracle-nbf02-nbf03-luna.md`. Then independently inspect/probe and write only `.oracle/checkins/batch-2-sol-fallback-v2.md` and `.oracle/receipts/oracle-nbf02-nbf03-sol-fallback-v2.md`. Return exactly `PASS_BATCH_2` or `ACCEPTED_ISSUES`. Do not implement, commit, stage, push, merge, rebase, reset, clean, alter frozen planning artifacts, or start Batch 3.

The prior Luna execution had a collection blocker because its required new test modules were absent; the current tree may now contain those modules from the corrected continuation. Run the exact frozen NBF-02 and NBF-03 pytest commands now; missing modules are no longer an acceptable blocker if they can be created within the frozen task scope. Also run the authority checker, raw-symbol scan, compile, and focused existing regressions. Treat known legacy babysitter failures honestly and only block on new/in-scope failures. Rehash all artifact identities, bind review to exact current candidate state, and give a binary criterion table, smallest rework if needed, North Star/KISS/YAGNI assessment, and preservation proof. No source-only claim substitutes for tests.

## North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.

## Delegation mandate

You are manager/validator, not worker. Delegate the one independent review to GPT-5.6 Luna using `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>`. Do not commission a second reviewer. Bias toward KISS/YAGNI and reject scope expansion.
