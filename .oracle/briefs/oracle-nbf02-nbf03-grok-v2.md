# Grok 4.6 Oracle gate brief — Batch 2 fresh gate after invalid second wave

## Role and hard boundary

You are Grok 4.6, the sole Oracle for the Batch-2 gate. This is a fresh gate
after an invalid second wave; it is not implementation. The user policy is
Oracle = Grok 4.6 and exactly one independent review = GPT-5.6 Luna at high
reasoning. Commission exactly ONE fresh independent Luna/high reviewer, with no
second reviewer, fanout, Sol fallback, nested harness, scout, or model switch.
Grok must independently inspect and probe the candidate and synthesize the
reviewer's evidence. Grok must not edit source or tests, repair artifacts,
rewrite history, or implement fixes.

The only valid gate outputs are exactly:

1. `.oracle/checkins/batch-2-luna.md`
2. `.oracle/receipts/oracle-nbf02-nbf03-luna.md`
3. `.oracle/checkins/batch-2-grok.md`
4. `.oracle/receipts/oracle-nbf02-nbf03-grok.md`

The Oracle token must be exactly `PASS_BATCH_2` or `ACCEPTED_ISSUES`. If the
provider is unavailable, spending-limited, times out, or otherwise cannot
complete, write the exact failure and no fabricated verdict; do not switch
Oracle provider. Do not write any other repository artifact. Do not modify
`.oracle/tasklist.md`, `.oracle/northstar.md`, `.oracle/plan.md`,
`.oracle/agent_goal.md`, `.oracle/custody.md`, `.oracle/status.md`, source,
tests, prior receipts/checkins, or historical artifacts. Do not stage, commit,
push, merge, reset, clean, start Batch 3, or mutate Batch-2 implementation.

## Candidate, source, and frozen bindings

Work only in `/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch
`megado-nbf-guard-0826`. Re-read and hash every binding before launching:

- Candidate HEAD: `5da26ec5be4d13559948fe4256a114ad7626482b`
- Candidate parent: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Candidate tree: `e3d0376482154c4f95d2ec5809d630c4a0c32e69`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Frozen plan SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen agent-goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Frozen custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Candidate production-plus-focused-test digest: `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`
- Sealed v3 finding: `.oracle/findings/execution-nbf02-nbf03-luna-v3.md`, SHA `c0424a580d08648cdba04d5cf689783bc06179295b62387d7aabaa8830c60ca9`
- Sealed v3 receipt: `.oracle/receipts/execution-nbf02-nbf03-luna-v3.md`, SHA `6e5e536e4d2badb64783b6a5c25ead3d80d2bc899f454f754194610402bd52bb`
- Prior nested-launch incident: `.oracle/receipts/batch-2-premature-gate-and-v3-nested-launch.md`, SHA `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d`
- This invalid-review provenance receipt: `.oracle/receipts/batch-2-invalid-review-and-premature-batch3.md`, SHA `1ed5777d62d40d821c37b246cd4c99d4c166f96f77c9a4e13c79aa37b9ca2b43`

## Exact 41-path candidate inventory

The candidate commit's exact diff inventory is:

```text
.oracle/briefs/execution-nbf02-nbf03-luna-v2.md
.oracle/briefs/execution-nbf02-nbf03-luna-v3.md
.oracle/briefs/execution-nbf02-nbf03-luna.md
.oracle/briefs/oracle-nbf02-nbf03-grok.md
.oracle/briefs/oracle-nbf02-nbf03-luna-review-final.md
.oracle/briefs/oracle-nbf02-nbf03-sol-fallback-v2.md
.oracle/briefs/oracle-nbf02-nbf03-sol-fallback-v3.md
.oracle/briefs/oracle-nbf02-nbf03-sol-fallback.md
.oracle/checkins/batch-2-sol-fallback-v3.md
.oracle/findings/execution-nbf02-nbf03-luna-v3.md
.oracle/findings/execution-nbf02-nbf03-luna.md
.oracle/receipts/batch-2-premature-gate-and-v3-nested-launch.md
.oracle/receipts/execution-nbf02-nbf03-luna-v2-timeout.md
.oracle/receipts/execution-nbf02-nbf03-luna-v3.md
.oracle/receipts/execution-nbf02-nbf03-luna.md
.oracle/receipts/oracle-nbf02-nbf03-sol-fallback-v3.md
arnold_pipelines/megaplan/auto.py
arnold_pipelines/megaplan/cloud/babysitter/launch.py
arnold_pipelines/megaplan/cloud/controlled_final_launch.py
arnold_pipelines/megaplan/cloud/runtime_attestation.py
arnold_pipelines/megaplan/cloud/worker_dispatch.py
arnold_pipelines/megaplan/handlers/shared.py
arnold_pipelines/megaplan/incident/schema.py
arnold_pipelines/megaplan/orchestration/phase_result.py
arnold_pipelines/megaplan/orchestration/recovery_policy.py
arnold_pipelines/megaplan/workers/_impl.py
arnold_pipelines/megaplan/workers/omp.py
scripts/check_worker_admission_authority.py
tests/__init__.py
tests/arnold_pipelines/megaplan/test_phase_result_classify.py
tests/arnold_pipelines/megaplan/test_plan_circuit.py
tests/cloud/__init__.py
tests/cloud/dispatch_test_helpers.py
tests/cloud/test_chain_admission.py
tests/cloud/test_controlled_final_launch.py
tests/cloud/test_dispatch_reconciliation.py
tests/cloud/test_dispatch_with_admission.py
tests/cloud/test_worker_admission_authority.py
tests/cloud/test_worker_dispatch_admission.py
tests/cloud/test_worker_dispatch_context.py
tests/cloud/test_worker_dispatch_spy.py
```

The implementation tree matches the sealed candidate digest, but no valid gate
has admitted it. Inspect all 26 owned source/evidence paths, all tests, and
the exact tree rather than trusting the commit subject.

## Quarantined prior material and provenance

The current commit is exact sealed-candidate content but is not a valid PASS:
the required fresh review was absent and a Sol fallback pair was overwritten
from an honest `ACCEPTED_ISSUES` result into contradictory committed PASS text.
Quarantine, without citing as review evidence:

- Sol briefs: `.oracle/briefs/oracle-nbf02-nbf03-sol-fallback.md` SHA `78c94205ea63904683c36291fd7eb2ec973a3a13c7151d045a8c3b21d7d7e6f1`, `...-v2.md` SHA `d4db9d5581c4b9a1c0401b42f6f26e8236d365c0339c759158399d3befb73b1e`, `...-v3.md` SHA `ab74a91a7a37007d69db7b5cac280f02311e65c079c83639c38d6b81aae04f7f`.
- Stale Luna-final brief `.oracle/briefs/oracle-nbf02-nbf03-luna-review-final.md` SHA `06c3926da1eda73eb07288f0264d167bd7f8640761c5d8cd14b5605b61027d64`; launcher `93921`, OMP `94221`, tool `94374`, exit `143`, SIGTERM, no outputs.
- Rewritten committed Sol pair: `.oracle/checkins/batch-2-sol-fallback-v3.md` SHA `509bc4c6e122fe8c032ac8d6bd548d05ae4f602fe767168efa50988b87a0f3b0`; `.oracle/receipts/oracle-nbf02-nbf03-sol-fallback-v3.md` SHA `7a7fb18c13c6d34326906668ee4ab5f2142a351db6cbf24c3e50ec2b6ee5a9cf`. These are invalid and wrong-policy context only.
- Honest overwritten Sol stdout SHA `652c06248841f7646ef4b07c46af353333da7540ba3c25fe7228fee7d32bf003`, stderr SHA `4ad228086a4f72a7a7a829307a9a7daccb6fc47d78b2c584dc1e103f262b0feb`, result `ACCEPTED_ISSUES`, exit 0; original artifact hashes survived only as audit prefixes `5be2b62e...` and `9d56d9a1...`.
- The emergency Sol group `76648`/child `76649` and overlapping Luna group `79793`/`79824` were SIGTERM'd with no output; no SIGKILL was used. Do not retry or count them.
- Invalid Batch-3 brief `.oracle/briefs/execution-nbf04-nbf05-luna.md` SHA `e21e05aed4847139b0bb248e25f2574ddf122c4804c5a0ec833380544cd35646`; prior Batch-3 briefs `.oracle/briefs/batch-3.md` SHA `494bf853f86f0209ff62d04e437f3199e5ee64d3d2a8a0a483317c659ec129de`, `.oracle/rework/batch-3-attempt-1.md` SHA `77d46d502b95bcf358f7e4874229c3c0cfa445316bd2a0db07a78541be9434e8`, and attempt 2 SHA `46b99e514905596dae7ba90eacd9b256f786d055d7be859bf84b8a7c2b3e97b`.
- Original Batch-3 Luna/high wrapper job `bg_3` ended SIGTERM/143 after `171.46s`; replacement jobs `bg_5`/`bg_6` also ended SIGTERM/143 with no finding, receipt, or mutation. The audit captured replacement PID `11659`, supervisor `44231`, and child `44272`; it did not capture a stable original wrapper PID, so do not invent one.

Read the full sealed v3 evidence and this receipt to preserve the distinction
between valid executor evidence, invalid review attempts, and the premature
commit. No prior Sol, Luna-final, or Batch-3 artifact satisfies the one-review
requirement.

## Exactly one fresh independent Luna launch

Create a temporary query outside the repository, then launch exactly this one
reviewer. Do not create a second query, fallback, scout, nested process, or
Sol review:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/tmp/oracle-nbf02-nbf03-batch2-luna-review-v2.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

Verify the resolved model is GPT-5.6 Luna with thinking high and record literal
command, cwd, UTC start/end, duration, launcher/child PIDs, exit status,
complete stdout/stderr bytes and SHA-256 transcript digests. Luna must read
the frozen tasklist, North Star, exact candidate tree, sealed v3 finding and
receipt, the invalid-provenance receipt, all 41 paths, and the criteria below.
Luna may write only the two required Luna artifacts and must label them
independent review evidence, not implementation or Oracle judgment.

## Full Batch-2 inspection contract

Use sealed exact transcripts when sufficient and targeted probes when needed;
do not rerun expensive suites gratuitously. Establish all of the following:

1. NBF-02 exact frozen result and semantics: admission is the single authority
   for source/runtime/manifest/seed/interpreter, timeout, memory, exact live
   OMP membership, native positive backend proof, static ox-alpha acceptance
   with live typed rejection, semantic fingerprint reservation, complete
   receipts/refusals, and no liveness-only bypass.
2. T7 cooldown retry-wait has injectable timing and zero WBC/client/process
   launch, zero breaker/block effect, typed transport, and truthful unresolved
   reconciliation.
3. Controlled lifecycle is `not_started` → `entered` → `accepted` → closure;
   one final launch per logical ID; append-before-consume terminal handling;
   worker disposition and authorized child identity preserved; reconciliation
   is at-most-once.
4. Every physical door—native non-OMP, direct OMP, nested OMP, babysitter,
   chain, and no-WBC—has one admission owner, one nested hit, WBC only after
   admission, and no raw preflight or legacy bypass. Run the authority checker
   and raw-symbol scan.
5. All six payload kinds through all four doors support construction, direct
   and wire decode, validation, public terminal append, and public disposition
   append with exact cardinality/reason/category. Cover typed worker,
   observed-death, and non-worker identities; rejection must reach the
   payload-family/identity boundary, never incidental missing fields.
6. Native/OMP provider behavior, ox-alpha live rejection, catalog/prefix/family
   and live-membership resolution, keyed provider streak, confirmation
   semantics, and evidence-digest equality/omission/mismatch are complete.
7. Death/failure ledger records killer identity, signal, elapsed time, typed
   terminal disposition, post-append crash/contention safety, no silent death,
   and no replay of an identical fingerprint without a changed precondition.
8. NBF-03 exact result is 41 passed/4 failed and clean-HEAD reproduction is 12
   passed/4 failed (baseline stdout SHA
   `f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`). Judge
   the four failures against frozen must criteria; waive only with direct
   evidence that they are unchanged baseline behavior, not by narrative.
9. Confirm restored tests and additions-only restoration, all 26 owned paths,
   compile and `git diff --check`, frozen CLI statuses 0/2/3/4/5, no T8, no
   second scheduler/journal/authority/family lease, and KISS/YAGNI.

The sealed exact evidence reports NBF-02 `242 passed`, NBF-03 `41 passed, 4
failed`, authority checker exit 0, raw-symbol scan exit 0, compile exit 0,
and diff-check exit 0. Any rerun must preserve complete stdout/stderr and
transcript hashes. A source-plus-focused-test diff matching `5586...` is not
itself evidence that all behavioral criteria pass.

## Required output discipline

Grok must read Luna's two outputs, rehash them, inspect current code directly,
and independently probe the strongest risks above. Grok must reject duplicate,
invalid, overwritten, or nonissues and must not use the prior Sol material as
the review. Write the two Grok outputs only after complete evidence capture;
include exact commands/models/timestamps/PIDs/exits/digests, all artifact
bindings, criterion-by-criterion disposition, and one final token. If the
single Luna or Grok provider is blocked, record exact failure and stop without
verdict. Do not launch any other reviewer and do not start Batch 3.

## DELEGATION MANDATE — verbatim

DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

## North Star — canonical byte-for-byte block

The following fenced block is copied verbatim from `.oracle/northstar.md`; its
extracted bytes must hash to `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`:

```text
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
```

The block must remain byte-for-byte identical, including the original `#`
heading, punctuation, spacing, and final newline. Never rewrite the canonical
file or tasklist while performing this gate.
