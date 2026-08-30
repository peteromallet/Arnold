# Sol fallback Oracle gate — Batch 2

Grok 4.6 was attempted as the pinned Batch-2 Oracle at 2026-08-30 and failed immediately with provider error `402 Payment Required: Grok Build usage balance exhausted` (receipt in the parent process output; no gate artifact was produced). The user explicitly ordered autonomous end-to-end completion without waiting for confirmation. You are therefore the temporary Oracle fallback, and must record this exact reason and model-policy exception in your receipt. Do not silently claim Grok performed this gate.

Repository `/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch `megado-nbf-guard-0826`, current candidate checkpoint `19deab5bb407273e7e82d40a66fc06d17af93ad4`, passed Batch-1 checkpoint `878a9b2980f0eab6642ed51c30e687903a7213b9`, merge-base `origin/main@798c50619204010ed3f4297fbb57988fe9381924`. Read `.oracle/agent_goal.md`, `.oracle/plan.md`, full `.oracle/tasklist.md` NBF-02/NBF-03 and the Batch-2 Luna executor evidence. Commission exactly one fresh independent GPT-5.6 Luna high-reasoning review, then independently inspect/probe and write the binary gate. Write only `.oracle/checkins/batch-2-luna.md`, `.oracle/receipts/oracle-nbf02-nbf03-luna.md`, `.oracle/checkins/batch-2-sol-fallback.md`, and `.oracle/receipts/oracle-nbf02-nbf03-sol-fallback.md`. Do not implement, commit, stage, push, merge, rebase, reset, clean, mutate frozen goal/plan/tasklist/North Star, or begin Batch 3.

Return exactly `PASS_BATCH_2` or `ACCEPTED_ISSUES`. Gate every NBF-02 and NBF-03 criterion, and treat the executor's absent-new-test collection blocker and four known legacy babysitter failures honestly. Rehash all identities, bind both reviews and evidence to the exact current checkpoint, preserve Batch-1 contracts, and give smallest actionable rework if blocked. Do not accept source-only claims or PID liveness as proof.

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

You are a manager and validator, not a worker. Delegate the one independent review to GPT-5.6 Luna using `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>`. Optimize for KISS/YAGNI and do not commission a second reviewer. Do not implement except impossible tiny orchestration.
