# Oracle re-review brief — NBF-01 Batch 1 rework 6

## Mission and binary gate

You are Grok 4.6, the Oracle for the NBF-01 Batch 1 re-review after attempt 6.
Read the sealed Luna execution evidence and current candidate source/tests,
commission exactly one fresh independent GPT-5.6 Luna review at high reasoning,
then independently inspect, probe, and synthesize the final full Batch-1 gate.
This is an Oracle review, not implementation.

Return exactly one binary token: `PASS_BATCH_1` or `ACCEPTED_ISSUES`. If any
must criterion remains unproven, return `ACCEPTED_ISSUES` and identify the
smallest concrete next action without widening the frozen tasklist. Batch 2 is
prohibited unless this gate returns `PASS_BATCH_1`.

## Candidate and sealed bindings

Candidate repository:
`/Users/peteromalley/Documents/Arnold-oracle-nbf`

- branch: `megado-nbf-guard-0826`
- bound HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- source/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- attempt-5 production baseline SHA-256:
  `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
- attempt-6 production diff SHA-256:
  `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`
- attempt-6 completion manifest SHA-256:
  `c602969e318ca705f240cd1fcd90c2017f791110d92c7f163378852d0648b2ef`

Attempt-6 sealed evidence:

- packet `.oracle/rework/batch-1-attempt-6.md`, SHA-256
  `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83`
- triage receipt `.oracle/receipts/rework-triage-batch-1-attempt-6-grok.md`,
  SHA-256 `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8`
- execution brief `.oracle/briefs/execution-nbf01-rework6-luna.md`, SHA-256
  `c193077b92f94b55e3dc8f4bf3353ec5318e7e745d0e6aff950c373472e96fb6`
- executor finding `.oracle/findings/execution-nbf01-rework6-luna.md`,
  SHA-256 `a28a0ff726cccbc00806a44c7f8c7d305019491cf37656b6ad91769250806c44`
- executor receipt `.oracle/receipts/execution-nbf01-rework6-luna.md`,
  SHA-256 `48d3988675ad1002000f193b915470391c83632bfc815fff2c35d8bd50a937e6`

Attempt-5 gate context, immutable and ending in `ACCEPTED_ISSUES`:

- Luna check-in SHA-256
  `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6`
- Luna receipt SHA-256
  `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143`
- Grok check-in SHA-256
  `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6`
- Grok receipt SHA-256
  `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef`
- attempt-5 production diff SHA-256
  `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`

Rehash every bound path and report actual candidate HEAD, branch, source/base,
dirty state, production diff, completion manifest, and all output identities.
Do not rewrite any historical artifact.

## Exactly-one independent review

Read in full `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`,
frozen `.oracle/tasklist.md`, settled plan, all attempt-5/6 packets and
receipts, the sealed executor finding/receipt, and current source/tests.

Commission **EXACTLY ONE** fresh independent reviewer: GPT-5.6 Luna at high
reasoning, with the full Batch-1 criteria and current attempt-6 tree. No second
reviewer, fanout, helper review, tiebreaker, or replacement is allowed. Luna
must write exactly:

- `.oracle/checkins/batch-1-rework6-luna.md`
- `.oracle/receipts/oracle-nbf01-rework6-luna.md`

Grok must independently inspect/probe and synthesize, but must not implement or
edit source/tests, frozen/history/status/goal/custody/North Star artifacts. Grok
must write exactly:

- `.oracle/checkins/batch-1-rework6-grok.md`
- `.oracle/receipts/oracle-nbf01-rework6-grok.md`

Record actual model specs/reasoning, launcher commands, UTC timestamps, cwd,
exit codes, complete transcripts, path/hash checks, and separate stdout,
stderr, and transcript SHA-256 digests for both review and gate. Validate all
four output paths and hashes after writing.

## Full Batch-1 review obligations

Re-review every frozen C01–C41 and CP01–CP11 criterion against source and
behavioral evidence. Test counts are observations, not waivers. In particular:

### RW6-01 / C02 / C13

Verify the final named tests use structurally complete `DispatchOutcome` and
terminal records, not partial dictionaries. Confirm every one of the six
incompatible payload combinations is exercised through:

1. direct construction;
2. `from_dict` decode;
3. `validate_nbf_event`; and
4. real public locked `append_terminal_outcome` and `append_disposition`.

Assert the intended payload-family error or scheduling-terminal error, not an
incidental missing-field/unknown-field failure. Confirm complete typed worker,
observed-death, and non-worker identity mismatch coverage at every applicable
door, including missing, fabricated, bare-string, wrong-version, incomplete,
wrong-type, non-positive PID, mismatched host/PID/boot identity, victim/killer,
subject/cause, and lifecycle cases. Confirm legal OOM, unknown-death,
non-worker, worker-disposition, no-launch, unresolved, success, ordinary, and
provider-positive records remain legal.

Do not accept a source-only probe as named proof. Ensure the tests fail on the
attempt-5 candidate for the old gap and pass on attempt 6. Confirm any
production change was strictly necessary for a correctly shaped case; reject
speculative validator changes or scope expansion.

### Closed obligations that must remain closed

Recheck, without reopening or weakening:

- C19–C21/RW5-01 coherent changed-precondition forgery rejection at decode,
  validation, private/canonical append, projection, and `reserve()`, while a
  legitimate reason-specific reader still supports valid replay and consume
  once;
- C39/RW5-03 confirmation equality, including wrong/omitted evidence digest,
  restart, replacement, expiry, and one-consumer semantics;
- keyed provider streak and recovery/probe lease isolation;
- terminal linkage race, composite pre/post-append crash/reopen and replay;
- C41 CLI status 0/2/3/4/5 and typed dispositions;
- one journal/lock and all prior C/CP MET results.

Do not reopen C36–C38, C01 overweight `PhaseResult.from_dict`, C40 cache
matrix, T8 policy, admission/scheduler/physical doors, signal/fallback/family
leases/rotators, broad missing modules, custody, historical evidence, second
store/journal/projection, or Batch 2. Any broad-suite missing-module result is
authoritative `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` context, not a waiver or
implementation issue; prefer no broad rerun unless a truly new in-scope reason
is documented.

## North Star and KISS/YAGNI assessment

Evaluate the candidate against the complete North Star below. Explicitly assess
one door per invariant, typed deaths/evidence, live admission boundaries as
deferred scope, and no identical-fingerprint redispatch without changed
precondition. Flag incidental test proof, duplicate preflights, speculative
authority/framework machinery, second stores, and any unnecessary production
surface under KISS/YAGNI.

## Gate artifact requirements

The Luna receipt must contain full review commands/results, candidate and
artifact identities, exact transcripts/digests, and all criterion dispositions.
The Grok check-in must begin with exactly `PASS_BATCH_1` or
`ACCEPTED_ISSUES`, then give independent probes, Luna comparison, full C/CP
dispositions, North Star/KISS/YAGNI assessment, preservation proof, and the
smallest next action if blocked. The Grok receipt must record every actual
command/model/timestamp/exit/path/hash/stream digest and explicitly state no
source/test/history/frozen/status mutation, no commit, and no Batch 2.

## North Star — Arnold self-healing supervision (verbatim)

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

## Megado delegation mandate (verbatim)

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.
