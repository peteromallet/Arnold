# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework attempt 6 triage

## Mission and exact output boundary

You are Grok 4.6, the Oracle and manager/validator for NBF-01 Batch 1 rework
attempt 6. Attempt 5 closed RW5-01/C19–C21 and RW5-03/C39, but ended in
`ACCEPTED_ISSUES` because the RW5-02/C02/C13 named behavioral proof remains
incomplete. Read the sealed attempt-5 Luna/Grok check-ins and receipts,
independently inspect the current source/tests, sense-check the surviving hole,
reject duplicates and nonissues, and author the smallest supplemental packet.
This is triage only, not implementation or review commissioning.

Write exactly these two new immutable prose artifacts:

1. `.oracle/rework/batch-1-attempt-6.md`
2. `.oracle/receipts/rework-triage-batch-1-attempt-6-grok.md`

Do not edit production or test code. Do not dispatch Luna or any reviewer in
this triage turn; later execution and the exactly-one independent review are
separate phases. Do not stage, commit, push, merge, rebase, reset, clean,
mutate the frozen tasklist/plan/status/agent goal/custody/North Star, rewrite
history or prior evidence, issue a Batch-1 pass decision, or start Batch 2.

## Candidate and immutable identities

Bind the triage to candidate repository
`/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch
`megado-nbf-guard-0826`, candidate HEAD
`922241d0bdb3e993c3b554cc69f19948adef7bc3`, and source/merge-base
`origin/main@798c50619204010ed3f4297fbb57988fe9381924`. Re-check and report
the live HEAD before writing.

- frozen `.oracle/tasklist.md` SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- `.oracle/northstar.md` SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- attempt-5 owned production diff SHA-256:
  `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`

Attempt-5 gate artifacts to read, hash, and bind:

- Luna check-in `.oracle/checkins/batch-1-rework5-luna.md`, SHA-256
  `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6`
- Luna receipt `.oracle/receipts/oracle-nbf01-rework5-luna.md`, SHA-256
  `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143`
- Grok check-in `.oracle/checkins/batch-1-rework5-grok.md`, SHA-256
  `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6`
- Grok receipt `.oracle/receipts/oracle-nbf01-rework5-grok.md`, SHA-256
  `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef`

Also read and preserve the attempt-5 packet, triage receipt, execution brief,
executor finding, executor receipt, all attempt-4 accepted-issues artifacts,
`.oracle/agent_goal.md`, `.oracle/custody.md`, settled plan v8, and historical
evidence. No prior artifact may be rewritten. Keep current production identity
`7b46da5c…` separate from all historical attempt-4 and earlier digests.

## Required independent sense-check

Read the full frozen tasklist and acceptance wording for C01–C41 and CP01–CP11,
then inspect the actual current symbols and tests rather than copying the
attempt-5 narrative. The surviving issue is narrowly about evidence quality and
behavioral coverage for C02/C13; it is not permission to reopen closed behavior.

Verify whether correctly shaped records for all six payload kinds are tested
through each required door:

1. direct construction;
2. `from_dict` decode;
3. `validate_nbf_event`; and
4. real public locked `append_terminal_outcome` and `append_disposition`.

Verify complete typed worker, observed-death, and non-worker identity mismatch
coverage at those applicable doors. Ensure failures reach the intended
payload-family or identity checks, rather than being rejected incidentally by
missing `DispatchOutcome` fields or another earlier malformed-record error.
Confirm legal OOM, unknown-death, and non-worker positive cases remain valid.
Do not weaken the now-closed C19–C21 authority boundary or the now-complete C39
confirmation evidence-digest matrix.

Optional scout failures, including OpenRouter 402/credit failures, are
nonblocking context. Do not fan out or retry scouts unnecessarily; if any scout
was attempted, record its exact failure honestly and do not present it as
evidence. The Oracle's own source/test inspection is authoritative for triage.

## Exactly one accepted issue

The supplemental packet must contain exactly one implementation issue, RW6-01,
for C02/C13. Reject duplicates of RW5-01/C19–C21, RW5-03/C39, or any prior-MET
item. No fourth issue, broad cleanup, environment repair, policy expansion, or
evidence-normalization task is authorized.

### RW6-01 — complete the C02/C13 payload and typed-identity proof

Severity: major. Criteria: C02, C13, RW5-02, RW4-02, A3-02; preserve C03–C08,
C12, C14 and all other prior-MET behavior.

Affected seams are `DispatchOutcome.__post_init__` and `from_dict` in
`arnold_pipelines/megaplan/orchestration/phase_result.py`; six-kind decode and
classification paths; worker/observed-death/non-worker schemas and
`validate_nbf_event` in `incident/schema.py`; the real locked ledger append
doors in `incident/ledger.py`; and the existing named tests in
`test_scheduling_conditions.py`, `test_worker_disposition.py`, and
`test_terminal_outcomes.py`.

Narrow outcome: correctly shaped records for all six payload kinds must be
exercised through direct construction, decode, validation, public terminal
append, and public disposition append. Complete typed worker,
observed-death, and non-worker identity mismatch coverage must be exercised at
each applicable door, and each negative assertion must reach the intended
payload-family/identity validation rather than fail first on incidental
missing fields. Preserve legal positive OOM, unknown-death, non-worker, and
worker-disposition behavior.

Required acceptance criteria:

- The named matrix uses correctly shaped records for every six-kind illegal
  combination and drives all four doors, including public
  `append_terminal_outcome` and public `append_disposition`; private-only
  `_append_nbf` coverage is insufficient.
- The matrix includes the repaired `worker_disposition` + `success_payload`
  rejection and every incompatible payload family with complete required
  fields, so the observed error is the intended payload-family rejection.
- Missing, fabricated, bare-string, wrong-version, and mismatched typed worker,
  observed-death, and non-worker identities are each covered at direct,
  decode, validation, and applicable public append doors. Negative cases must
  reach identity checks, not incidental missing `DispatchOutcome` fields.
- Legal positive OOM and unknown-death paths, legal non-worker records,
  no-launch/unresolved distinction, lossless worker disposition, and prior
  C03–C08/C12/C14 semantics remain intact.
- Tests are deterministic behavioral regressions and fail against the current
  attempt-5 candidate for the named proof gap. Do not expand C01 by adding an
  overweight `PhaseResult.from_dict` round trip.
- No authority store, second journal, generic producer bypass, second
  projection, policy owner, or unrelated source/test scope is introduced.

Dependencies/order: RW6-01 is the sole serial task and follows completed
RW5-01 and RW5-03. Its implementation and tests are Normal / GPT-5.6 Luna.
One writer owns the overlapping schema/phase/ledger/test seams. Later fresh
executor evidence, exactly one independent Luna review, and a separate Grok
gate follow this packet; this triage turn dispatches none of them.

## Model classification and exceptional threshold

Classify RW6-01 **Normal / GPT-5.6 Luna**; `[XHARD]: none.` This is a
deterministic named behavioral-test and, only if needed, minimal validator
correction task. Importance, file span, prior incomplete attempts, or test
count do not meet the exceptional threshold. Decomposition is sufficient and
there is no irreducible judgment kernel. Any `[XHARD]` proposal must prove both
that decomposition is insufficient and that the Normal pool cannot reliably
execute the specific kernel; absent complete threshold evidence, reject the
proposal and retain Normal/Luna.

For RW6-01 record issue/criteria, severity, affected goal and North Star
principle, bounded outcome, dependencies/order, sole writer and owned files/
symbols, preserved behavior, prohibited scope, Normal/Luna rationale, exact
acceptance checks, and exact validation commands.

## Exact acceptance and validation commands

The packet must prescribe exact commands, not “run the tests.” At minimum use
these from repository root, recording the literal argv, cwd, timestamps, exit,
complete stdout/stderr, and SHA-256 stream/transcript digests:

```text
python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
git diff --check
```

The packet must require fresh targeted behavioral probes or named test cases
that demonstrate all four doors and intended error families. Preserve C41 CLI
0/2/3/4/5 as a regression only if execution evidence reruns it; do not redesign
the CLI. Preserve broad-suite collection evidence as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only if later execution runs the existing
single sweep; do not restore missing modules or create a broad task here.

## Explicit exclusions and preservation

Reject any task for C19–C21 authority (closed in attempt 5), C39 confirmation
equality (closed in attempt 5), keyed provider/recovery behavior, terminal race
or composite crash behavior, executor evidence protocol, C36–C38, C01
overweight round-trip, C40 cache mismatch, C41 CLI redesign, T8 policy,
admission/scheduler/physical doors, signal/fallback/family lease/rotator,
custody, environment repair, historical rewrite, second journal/store, or
Batch 2. Preserve the attempt-5 production diff and all prior-MET semantics.
If a contradiction is discovered, document it and stop rather than widening.

## Required output contents

The supplemental packet must include the single RW6-01 mapping, Normal/Luna
classification and threshold rationale, exact four-door/six-kind and complete
typed-identity acceptance wording, dependencies, exclusions, and literal
validation commands. The receipt must include actual candidate identities,
all four attempt-5 gate artifact hash matches, production diff hash, every
inspection command and stream digest, fresh source/test observations,
accepted/rejected/duplicate reasoning, output hashes, optional scout failures
if any, and an explicit no-mutation/no-dispatch statement.

Do not issue `PASS_BATCH_1` or `ACCEPTED_ISSUES` from this triage brief. The
outputs are a supplemental task packet for a later Normal/Luna execution.

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
