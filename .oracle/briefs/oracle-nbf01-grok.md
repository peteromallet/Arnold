# Oracle brief — NBF-01 / Batch 1 (Grok 4.6)

## Assignment and hard start gate

You are the independent Batch 1 Oracle, pinned to Grok 4.6 by the latest
authoritative model-policy update in `.oracle/agent_goal.md` and
`.oracle/receipts/model-policy-grok-switch.md`. You are a manager and validator,
not an implementer. Do not edit production or test code, do not repair findings,
and do not commit, push, merge, or alter `main`.

Do not begin the verdict until the Batch 1 executor receipt exists. The required
executor receipt is expected at:

    .oracle/receipts/execution-nbf01-luna.md

If that receipt is absent, stale, or does not identify the executor result,
return a blocked/accepted-issues report naming the missing evidence; do not infer
success from the working tree.

The immutable source base is `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
The candidate branch is `megado-nbf-guard-0826`. The frozen tasklist digest is
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
The settled plan-v8 digest is
`0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`.
The North Star digest is
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
The review is for NBF-01 only; later batches and unrelated dirty artifacts are
not Batch 1 acceptance evidence.

## Required independent review delegation

Commission exactly ONE fresh, independent GPT-5.6 Luna review pass. Write a
temporary or durable review brief under `.oracle/briefs/` and invoke it with the
required launcher, for example:

    PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
      --model="codex:gpt-5.6-luna" \
      --toolsets="file,web,terminal" \
      --query-file=.oracle/briefs/oracle-nbf01-luna-review.md \
      --project-dir="$PWD"

Give Luna the complete contract and evidence set: `.oracle/northstar.md`,
`.oracle/agent_goal.md`, `.oracle/plan.md`, frozen `.oracle/tasklist.md`,
`.oracle/custody.md`, the executor receipt, the executor's exact diff from the
source base/checkpoint, every focused-test command and output named by the
receipt, and any relevant evidence/receipt paths. Luna must assess all NBF-01
acceptance criteria and North Star alignment, not merely the latest patch. Do
not fan out reviewers or commission a second pass unless the exact exception in
the mandate below is satisfied and documented; routine Batch 1 requires exactly
one pass.

Store the immutable Luna result at:

    .oracle/checkins/batch-1-luna.md

Store this Grok Oracle verdict at:

    .oracle/checkins/batch-1-grok.md

Record the Luna invocation/result receipt at:

    .oracle/receipts/oracle-nbf01-luna.md

Record this Oracle invocation/decision receipt at:

    .oracle/receipts/oracle-nbf01-grok.md

## Verbatim delegation mandate

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

## Oracle review contract

Read the complete North Star below, then the complete goal, plan v8, frozen
tasklist, execution brief, custody, executor receipt, diff, and tests. Verify
NBF-01 against the frozen acceptance in the tasklist and the detailed contracts
in the execution brief. Check that no excluded later-task behavior or file was
changed, and that the candidate is evaluated against the stated source base.

Explicitly report evidence-cited dispositions for:

- every NBF-01 acceptance criterion, including strict schemas, lossless
  `worker_disposition` mapping, single ledger transaction/CAS, changed
  preconditions, keyed provider replay, reconciliation, two-scan confirmation,
  receipt derivation, fail-closed behavior, and CLI contracts;
- the North Star's four enduring principles and each anti-pattern;
- KISS/YAGNI/scope creep: identify speculative abstractions, duplicate doors,
  ceremonial validation, or behavior belonging to later batches;
- source base, candidate branch, executor receipt, Luna review receipt, test
  outputs, diff/checkpoint, and this check-in path.

The verdict must be binary and exactly one of:

    PASS_BATCH_1

or

    ACCEPTED_ISSUES

For `ACCEPTED_ISSUES`, list each issue with severity, exact file/symbol or
acceptance criterion, concrete evidence, and the smallest required correction.
Do not implement corrections. A missing, contradictory, stale, or unreviewed
piece of evidence is an issue, not permission to assume.

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

## Boundaries

This is a review-only gate. Do not edit `.oracle/tasklist.md`, plans, receipts,
custody files, the North Star, agent goal, or implementation files. No commit,
push, merge, rebasing, or main-branch mutation is authorized by this brief.
The only output is the evidence-backed binary verdict and its receipt/check-in
artifacts. The executor remains GPT-5.6 Luna under the frozen tasklist; the
latest Grok switch changes Oracle ownership only and does not rewrite the frozen
tasklist or NBF-01 scope.
