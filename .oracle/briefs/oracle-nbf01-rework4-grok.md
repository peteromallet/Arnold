# Oracle gate brief — NBF-01 Batch 1 rework 4

## Mission and binary decision

Act as the Grok 4.6 Oracle gate for NBF-01 Batch 1 rework 4. Read every bound
artifact, the completed executor evidence, and the relevant current source and
tests. Independently inspect and probe the strongest remaining risks, then
synthesize the final Oracle verdict. This brief commissions exactly one fresh
independent GPT-5.6 Luna review; Grok is the synthesizer and validator, not an
implementer.

The only permitted decision tokens are `PASS_BATCH_1` and
`ACCEPTED_ISSUES`. Write the required Luna and Grok artifacts below. If issues
remain, identify the smallest concrete attempt-5 triage action; do not invent
new scope.

## Candidate and immutable bindings

All evidence is for candidate repository
`/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch
`megado-nbf-guard-0826`, with source base
`origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
The observed candidate HEAD at brief authoring is
`922241d0bdb3e993c3b554cc69f19948adef7bc3`; re-check and report the actual
candidate HEAD at gate execution.

Required identities:

- frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- settled plan v8 SHA-256:
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- custody SHA-256:
  `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- agent goal SHA-256:
  `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- model-policy receipt SHA-256:
  `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064`
- tasklist-freeze receipt SHA-256:
  `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24`

Attempt-4 bindings:

- packet `.oracle/rework/batch-1-attempt-4.md`, SHA-256
  `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- triage brief `.oracle/briefs/oracle-nbf01-rework4-triage-grok.md`, SHA-256
  `d6c559d694c006d4fd310ae706779604ebe228f713a27a40669d6c5c1c040c0f`
- triage receipt `.oracle/receipts/rework-triage-batch-1-attempt-4-grok.md`,
  SHA-256 `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- execution brief `.oracle/briefs/execution-nbf01-rework4-luna.md`, SHA-256
  `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d`
- executor finding `.oracle/findings/execution-nbf01-rework4-luna.md`,
  SHA-256 `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- executor receipt `.oracle/receipts/execution-nbf01-rework4-luna.md`,
  SHA-256 `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`
- candidate production diff SHA-256:
  `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

Prior attempt-3 context is historical and must remain labeled historical:

- gate brief SHA-256
  `5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01`
- packet SHA-256 `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- triage receipt SHA-256
  `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- executor finding SHA-256
  `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f`
- executor receipt SHA-256
  `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f`
- Luna review check-in SHA-256
  `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd`
- Luna review receipt SHA-256
  `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425`
- Grok check-in SHA-256
  `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02`
- Grok receipt SHA-256
  `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30`
- attempt-3 production diff SHA-256
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`

The prior Grok gate timed out only while writing, after independent checks
confirmed Luna's coherent changed-precondition forgery blocker. Preserve that
as historical context, not as a substitute for fresh attempt-4 validation.

## Required reading and evidence sealing

Read and hash the full current North Star, frozen tasklist, agent goal, custody,
attempt-4 packet and triage artifacts, execution brief, executor finding and
receipt, current source/test diff, and the complete prior attempt-3 check-in and
receipt context. Validate that every referenced path exists, every recorded
SHA-256 matches its bytes, the candidate HEAD and source base are reported, and
the executor transcript is complete rather than summarized. Record stdout and
stderr digests separately wherever commands are run.

The attempt-4 packet's serial scope is RW4-01 → RW4-02 → RW4-03 → RW4-04 →
RW4-05 → RW4-06, followed by RW4-GATE. Validate the six accepted-issue themes:

1. C19–C21 authoritative producer and coherent-forgery resistance.
2. C02/C13/C14 strict payload and typed-identity validation.
3. C11/C32/C33/C34 keyed provider streak, recovery, and probe binding.
4. C09/C28 composite race, crash, and replay behavior.
5. C39/C41 confirmation full matrix and CLI regression behavior.
6. RW3-06/A3-08 evidence completeness.

Do not reopen C36–C38, overweight C01, expand C40, or pursue T8 policy,
environment repair, custody/history/admission/scheduler/physical-door/launch,
signal, fallback, or other excluded work.

## Exactly-one independent review contract

Commission exactly **ONE** fresh independent reviewer: GPT-5.6 Luna at high
reasoning. Give Luna the completed attempt-4 executor evidence and current
source/test tree, and require it to write exactly:

- `.oracle/checkins/batch-1-rework4-luna.md`
- `.oracle/receipts/oracle-nbf01-rework4-luna.md`

There must be no second reviewer, fan-out, parallel review, tiebreaker, or
replacement reviewer. Grok must wait for and validate this one review, then
independently inspect/probe the strongest risks and synthesize the final Oracle
decision. Grok must not implement fixes or edit production code, tests, frozen
artifacts, historical evidence, tasklist/status/agent_goal/custody files, or
any other source-controlled content.

The proven Grok wrapper pattern is:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework4-grok.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

For the commissioned Luna review, report the actual launcher command and model
specification used, including high reasoning, timestamps, exit status, and
artifact digests. Capture the full review transcript and receipt; do not claim
completion from a narrative alone.

## Independent probe checklist

Both Luna's evidence and Grok's independent synthesis must address, with exact
paths, commands, outputs, exit statuses, and digests where applicable:

- complete path/hash inventory and transcript/receipt integrity;
- direct and wire authorization boundaries, including authoritative producer
  provenance and protection against coherent changed-precondition forgery;
- strict payload shape and typed identity fields, including full-field
  confirmation semantics rather than partial or truthy checks;
- keyed provider streak behavior, recovery and probe binding, and cross-key
  contamination resistance;
- post-append crash durability, contention/race behavior, replay/idempotency,
  and composite failure handling;
- CLI statuses and exit codes 0/2/3/4/5, including regression coverage and
  truthful failure reporting;
- focused/adversarial and required legacy incident/phase test evidence, with
  command stdout/stderr and pass/fail results;
- alignment with the North Star and KISS/YAGNI: one door per invariant,
  typed deaths, live admission, and no speculative or redundant machinery.

Use the current code and test behavior to distinguish a real blocker from a
mere narrative concern. A passing test command is not sufficient if the
authorization boundary, provenance, full-field semantics, or crash/contention
invariant remains forgeable.

## Oracle output contract and prohibitions

Write exactly these two Grok-owned artifacts in addition to the one Luna review:

- `.oracle/checkins/batch-1-rework4-grok.md`
- `.oracle/receipts/oracle-nbf01-rework4-grok.md`

The check-in must begin with exactly one binary token, `PASS_BATCH_1` or
`ACCEPTED_ISSUES`, and explain evidence, residual risks, and (if needed) the
smallest attempt-5 triage action. The receipt must include candidate HEAD,
source/tasklist/North Star identities, all model names, actual commands,
timestamps, exit statuses, complete path/hash checks, test results, and
separate stdout/stderr/transcript digests.

Do not modify source or tests. Do not commit, stage, push, merge, launch Batch
2, mutate the frozen tasklist, change status/agent_goal/custody, rewrite
historical evidence, or issue an implementation patch. This is an Oracle gate
only.

## North Star — Arnold self-healing supervision

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

## Megado delegation mandate

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.
