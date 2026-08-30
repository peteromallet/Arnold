# Oracle re-review brief — NBF-01 Batch 1 rework 5

## Mission and binary gate

You are Grok 4.6, the Oracle for the NBF-01 Batch 1 re-review after attempt 5.
Read the complete sealed Luna execution evidence and current candidate source,
then commission exactly one fresh independent GPT-5.6 Luna review at high
reasoning. Independently inspect and probe the strongest risks yourself,
synthesize the full Batch-1 decision, and write the required Luna and Grok
artifacts. This is an Oracle gate, not implementation.

Return exactly one binary token as the Oracle decision:
`PASS_BATCH_1` or `ACCEPTED_ISSUES`. If issues remain, name the smallest
concrete next triage action without widening the frozen scope. Batch 2 remains
prohibited unless and until this gate returns `PASS_BATCH_1`.

## Candidate and immutable bindings

Candidate repository:
`/Users/peteromalley/Documents/Arnold-oracle-nbf`

- branch: `megado-nbf-guard-0826`
- bound HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- source/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- frozen tasklist `.oracle/tasklist.md` SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star `.oracle/northstar.md` SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`

Attempt-5 sealed execution bindings:

- packet `.oracle/rework/batch-1-attempt-5.md`, SHA-256
  `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7`
- triage receipt `.oracle/receipts/rework-triage-batch-1-attempt-5-grok.md`,
  SHA-256 `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a`
- execution brief `.oracle/briefs/execution-nbf01-rework5-luna.md`, SHA-256
  `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a`
- Luna finding `.oracle/findings/execution-nbf01-rework5-luna.md`, SHA-256
  `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197`
- Luna receipt `.oracle/receipts/execution-nbf01-rework5-luna.md`, SHA-256
  `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160`
- post-attempt-5 production diff SHA-256:
  `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
- attempt-4 reviewed production diff SHA-256, historical baseline:
  `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

Re-check every identity against bytes and the live candidate before deciding;
the bound HEAD and diff are expected starting identities, not permission to
skip identity capture. Report actual HEAD, branch, source/merge-base, dirty
tree state, and final production diff.

## Historical attempt-4 accepted-issues context

Attempt 4 ended in `ACCEPTED_ISSUES`; preserve it as immutable history and
verify its claims only as context for the re-review:

- `.oracle/checkins/batch-1-rework4-luna.md` SHA-256
  `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`
- `.oracle/receipts/oracle-nbf01-rework4-luna.md` SHA-256
  `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee`
- `.oracle/checkins/batch-1-rework4-grok.md` SHA-256
  `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf`
- `.oracle/receipts/oracle-nbf01-rework4-grok.md` SHA-256
  `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607`
- attempt-4 packet SHA-256
  `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- attempt-4 triage receipt SHA-256
  `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- attempt-4 executor finding SHA-256
  `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- attempt-4 executor receipt SHA-256
  `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`

Do not edit any attempt-4 or earlier evidence. Keep historical attempt-1/2/3
digests, the start-gate 52→61 observation, unreproducible and failed-handoff
records, and all prior accepted/MET results labeled historical.

## Required reading and exactly-one review

Read in full before launching the one reviewer or writing either gate output:

- `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`;
- frozen `.oracle/tasklist.md`, settled plan v8, and tasklist-freeze evidence;
- all attempt packets, triage receipts, executor findings/receipts, and
  attempt-4 Luna/Grok check-ins/receipts;
- current source and test diff, including all owned NBF modules and tests;
- the complete attempt-5 packet, triage receipt, execution brief, finding, and
  receipt, including all transcript/stream digests and broad-sweep output.

Commission **EXACTLY ONE** fresh independent reviewer: GPT-5.6 Luna at high
reasoning. Give Luna the complete current candidate and the sealed attempt-5
evidence. Luna must independently review all Batch-1 criteria and write exactly:

- `.oracle/checkins/batch-1-rework5-luna.md`
- `.oracle/receipts/oracle-nbf01-rework5-luna.md`

No second reviewer, fan-out, parallel reviewer, tiebreaker, or replacement is
permitted. The exactly-one review requirement is satisfied only by that single
fresh Luna review. Grok remains the Oracle synthesizer: independently inspect
and probe the current code and evidence, reconcile disagreements, and write:

- `.oracle/checkins/batch-1-rework5-grok.md`
- `.oracle/receipts/oracle-nbf01-rework5-grok.md`

Grok must not implement fixes or edit production/tests, tasklists, status,
agent_goal, custody, North Star, historical evidence, or any source-controlled
artifact other than the two Grok outputs above. Do not commit, stage, push,
merge, start Batch 2, or mutate the frozen pipeline.

For both models, capture actual model specification and reasoning level,
launcher command, UTC timestamps, cwd, exit status, complete transcript paths,
and full stdout/stderr/transcript SHA-256 digests. Validate all output paths
and hashes after writing.

## Full Batch-1 re-review contract

Re-review every frozen NBF-01 criterion C01–C41 and checkpoint CP01–CP11,
not merely the three attempt-5 obligations. Read the settled acceptance text,
classify every criterion as met/not met/unevidenced with source and behavioral
evidence, and check that prior-MET work was not regressed. A green aggregate
count never substitutes for a required behavioral door or complete evidence.

### RW5-01 / C19–C21 / RW4-01 / A3-03 — authority closure

Independently reproduce the prior coherent changed-precondition attack. Rebuild
all caller-visible serializable fields—including before/after snapshots,
content IDs, evidence digest, provider-failure keys, and event ID—then probe
`from_dict`, `validate_nbf_event`, canonical/private `_append_nbf` and locked
append, projection, and `reserve()` authorization. A coherent recomputation or
re-signing by an untrusted caller must not regain authority. Confirm that:

- every allowlisted reason-specific producer requires its typed authoritative
  source handle/reader;
- producer identity, reason, subject, source version, cited persisted evidence,
  evidence digest, canonical before/after content, and provider-key derivation
  are bound at every relevant decode/append/consume door;
- forged events neither persist/project nor authorize reservation;
- valid reason-specific reader events still append, project, replay as required,
  and consume exactly once under the existing journal lock.

This is the primary security gate. Reject content-address self-consistency as
proof of provenance. Verify no second authority store, signing framework,
generic bypass, or second journal was introduced.

### RW5-02 / C02/C13 / RW4-02 / A3-02 — complete matrix

Verify the existing named behavioral tests cover all six incompatible
outcome/payload kinds through direct construction, `from_dict`,
`validate_nbf_event`, and real public locked append doors, including public
`append_terminal_outcome` and `append_disposition`, rather than only a private
append or one worker-success pairing. Verify missing/fabricated typed worker,
observed-death, and non-worker identities at each applicable door, while legal
OOM, unknown-death, and non-worker positive paths remain valid. Confirm no
overweight C01 `PhaseResult.from_dict` expansion was smuggled in.

### RW5-03 / C39 / RW4-05 / A3-07 — confirmation evidence equality

Verify every required confirmation identity, timing, evidence, TTL/expiry,
scan separation, policy, and version field is persisted and compared. In
particular, independently test wrong and omitted `second_evidence`/
`second_evidence_digest`, not only PID/start/progress/incarnation/cause. Verify
restart, replacement, expiration, reopen, expiry-after-consume, and locked
one-consumer semantics remain intact. Re-run CLI statuses 0/2/3/4/5 only as a
regression; do not redesign the CLI.

### Preserved Batch-1 invariants and scope

Check keyed provider streak/recovery/probe lease behavior, non-latest key
isolation, terminal linkage race, post-append and pre-append composite crash
recovery, deterministic replay, one journal/lock, typed dispositions, no-launch
and unresolved distinctions, route-child wrapper deletion, and all prior-MET
C/CP behavior. Verify no admission/scheduler/physical-door/signal/T8/fallback/
family-lease/rotator/policy work entered the candidate. Broad missing-module
collection failures remain `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only if absent
on candidate and source; they are not a waiver or triage issue.

## KISS/YAGNI and North Star alignment

Evaluate whether the fix closes each invariant at one existing door, avoids
duplicate preflights and speculative abstractions, keeps typed deaths/evidence,
and blocks identical-fingerprint redispatch without a changed precondition.
Flag overengineering, second stores/journals, generic authority escapes,
ceremonial tests, and evidence claims unsupported by direct probes. Align every
verdict with the complete North Star below.

## Required evidence and gate outputs

The Luna receipt and Grok receipt must contain complete path/hash inventories,
candidate HEAD/source/tasklist/North Star identities, production diff identity,
actual model/commands/timestamps/exit statuses, full transcript and separate
stdout/stderr digests, exact test commands/results, and any broad collection
blocker classification. The Grok check-in must begin with exactly one binary
token and include criterion dispositions, independent probe results, prior-MET
preservation, KISS/YAGNI assessment, residual issues, and the smallest next
action if `ACCEPTED_ISSUES`. Do not use an Oracle token in the Luna check-in.

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
