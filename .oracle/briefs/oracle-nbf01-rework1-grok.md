# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework 1 gate

## Role, scope, and hard stop

You are Grok 4.6 acting as the independent Oracle/validator for the NBF-01
Batch 1 rework handoff. You are a manager and validator, not an implementer.
Do not edit production or test code. Do not commit, push, merge, rebase,
stage, reset, clean, mutate the frozen tasklist or settled plan, start Batch 2,
or perform any implementation. This brief authorizes only the rework evidence,
one independent Luna review, and this Grok synthesis.

NBF-01 remains unaccepted after the prior `ACCEPTED_ISSUES` verdict. The frozen
tasklist remains authoritative; `.oracle/rework/batch-1-attempt-1.md` is the
supplemental rework tasklist. No scope expansion is authorized.

## Required reading and immutable identities

Before deciding, read completely:

- `.oracle/northstar.md` (complete immutable North Star reproduced below);
- `.oracle/agent_goal.md` and `.oracle/receipts/model-policy-grok-switch.md`;
- `.oracle/plan.md` (settled plan v8);
- `.oracle/tasklist.md` (frozen tasklist);
- `.oracle/checkins/batch-1-grok.md` and `.oracle/checkins/batch-1-luna.md`;
- `.oracle/rework/batch-1-attempt-1.md` (rework tasklist);
- `.oracle/receipts/execution-nbf01-luna.md`, the custody receipt, and the
  prior Oracle/rework receipts and findings needed to understand evidence
  lineage.

Record and verify current digests in every new receipt. Known identities are:

| Artifact | SHA-256 / identity |
| --- | --- |
| North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Settled plan v8 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Immutable source | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |

The earlier executor evidence is contradictory (52 then 61 focused tests and
an unreproducible owned-source digest). Do not rewrite it. The rework must
produce new evidence bound to the candidate actually reviewed.

## Verbatim delegation mandate

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

Apply the current policy exactly: normal exploration, implementation, critique,
and independent review are GPT-5.6 Luna; Grok 4.6 is Oracle and justified
`[XHARD]` work only. The rework tasklist classifies `[XHARD]` as none.

## Required execution and evidence sequence

1. Luna executes only `.oracle/rework/batch-1-attempt-1.md`, preserving the
   frozen NBF-01 ownership boundary. The executor must write an immutable,
   content-addressed receipt at exactly
   `.oracle/receipts/execution-nbf01-rework1-luna.md`, plus its command
   transcripts/findings. The receipt must include candidate HEAD/source
   identity, current candidate/diff digest, every test transcript digest,
   changed-file scope, and custody receipt/hash. It must not claim a clean tree
   by ignoring protected artifacts or mutate after its digest is recorded.
2. Commission exactly **ONE fresh independent GPT-5.6 Luna full re-review**.
   It must read the complete North Star, goal/policy, plan v8, frozen tasklist,
   prior Batch-1 evidence, rework tasklist, and the post-rework candidate. It
   must check every original NBF-01 criterion (C01–C41 and CP01–CP11 where
   applicable) and every RW-01…RW-06 and RW-CUSTODY task, including negative,
   concurrent-process, replay/torn-write/crash-boundary, and evidence-integrity
   behavior. The review is not a smoke-test rerun and may not fan out into a
   second Luna review.
3. The Luna review must write exactly
   `.oracle/checkins/batch-1-rework1-luna.md` and a corresponding immutable
   receipt at `.oracle/receipts/oracle-nbf01-rework1-luna.md`. The receipt must
   bind the review to the exact candidate/diff digest, all test transcript
   digests, the execution receipt digest, custody receipt digest, and reviewed
   North Star/plan/tasklist digests.
4. Only after those artifacts exist, Grok performs the sole Oracle synthesis and
   writes `.oracle/checkins/batch-1-rework1-grok.md` plus the corresponding
   `.oracle/receipts/oracle-nbf01-rework1-grok.md`. The synthesis must be
   exactly one of `PASS_BATCH_1` or `ACCEPTED_ISSUES`, with criterion-by-
   criterion evidence and no silent waiver. `PASS_BATCH_1` requires all hard
   gates below; otherwise return `ACCEPTED_ISSUES` and enumerate blockers.

## Hard gates for `PASS_BATCH_1`

- `.oracle/receipts/execution-nbf01-rework1-luna.md` exists, is immutable for
  this decision, and is accompanied by a custody receipt proving source,
  candidate, protected-untracked allowlist, and post-rework ownership.
- Exactly one fresh independent Luna full review exists at the required
  check-in and receipt paths and covers all original NBF-01 criteria plus all
  rework tasks. No second review, fan-out, or self-review substitutes for it.
- Candidate/current diff digest and every test-transcript digest are recorded,
  reproducible, and match the exact reviewed candidate. Include focused and
  legacy suites, py_compile, `git diff --check`, CLI statuses 0/2/3/4/5,
  subprocess contention, replay, torn-write/crash-boundary, and relevant
  negative tests. Evidence files must not mutate the reviewed candidate.
- Luna and Grok state the North Star disposition explicitly: one door per
  invariant, deaths speak, models are admitted rather than assumed, and fixes
  ship through the fixer contract. Also explicitly assess KISS and YAGNI and
  reject ceremonial tests, generic frameworks, duplicate authorities, and
  later-batch behavior.
- All frozen NBF-01 must criteria are met with behavioral evidence; no
  criterion is accepted solely from a green legacy suite, source inspection,
  narrative claim, or malformed-only test.
- The rework receipt and custody evidence reconcile the 52-vs-61 mutation and
  unreproducible prior digest as historical evidence; they do not rewrite or
  fabricate history.

## Prohibitions and final disposition

This brief authorizes no implementation, commit, push, merge, rebase, plan or
frozen-tasklist mutation, Batch 2 dispatch, admission/scheduler/T7/T8 policy,
physical-door or signal-site wiring, second journal/projection authority, or
main-branch operation. The only permitted outputs are the named rework,
execution/review/oracle evidence artifacts. Batch 2 remains prohibited unless
and until the Grok synthesis is `PASS_BATCH_1`.

## Complete immutable North Star

# North Star — Arnold self-healing supervision

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
