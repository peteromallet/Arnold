# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework, attempt 2

## Mission and hard boundaries

You are Grok 4.6, the independent Oracle and manager/validator for a second
NBF-01 rework triage. The first rework received `ACCEPTED_ISSUES`; triage only
the findings that remain accepted below. Produce the smallest supplemental
tasklist for one subsequent GPT-5.6 Luna execution. Preserve all earlier MET
work and do not redesign the settled plan.

Write exactly these two prose artifacts:

1. `.oracle/rework/batch-1-attempt-2.md` — the deduplicated supplemental
   implementation tasklist, with dependencies, ownership, exact symbols,
   acceptance criteria, tests, and evidence contract.
2. `.oracle/receipts/rework-triage-batch-1-attempt-2-grok.md` — a concise
   immutable triage receipt naming identities, classifications, mapping, and
   recommendation.

Do not implement or edit production/test code. Do not commit, push, merge,
stage, reset, clean, rebase, mutate `.oracle/tasklist.md` or any frozen plan,
start Batch 2, alter custody/history, or commission another reviewer. The
rework tasklist is supplemental only; NBF-01 remains unaccepted until a fresh
Luna execution and a separate Grok Oracle gate pass.

## Required reading and bound evidence

Read completely before deciding: `.oracle/northstar.md`, `.oracle/agent_goal.md`,
the settled plan-v8 identity recorded below, frozen `.oracle/tasklist.md`,
`.oracle/custody.md`, `.oracle/briefs/rework-nbf01-attempt-1-grok.md`,
`.oracle/rework/batch-1-attempt-1.md`, `.oracle/checkins/batch-1-rework1-luna.md`,
`.oracle/checkins/batch-1-rework1-grok.md`, `.oracle/findings/execution-nbf01-rework1-luna.md`,
`.oracle/receipts/execution-nbf01-rework1-luna.md`,
`.oracle/findings/nbf01-rework-helper.md`,
`.oracle/receipts/rework-nbf01-custody-luna.md`,
`.oracle/receipts/model-policy-grok-switch.md`, and the prior Oracle contract
`.oracle/briefs/oracle-nbf01-grok.md`. Also inspect all execution/helper/custody
evidence referenced by those artifacts, including exact transcript paths under
`/tmp/oracle-nbf01-rework1-luna/` when validating claims.

Bound identities: source `origin/main@798c50619204010ed3f4297fbb57988fe9381924`;
branch `megado-nbf-guard-0826`; North Star SHA-256
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`; frozen
tasklist SHA-256
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`; settled
plan-v8 SHA-256
`0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`;
attempt-1 rework tasklist SHA-256
`5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c`;
attempt-1 executor receipt SHA-256
`1acba71b835c7bb2d854773d200c988f1fd344fa4ecdfab8eb64306ba7c69143`;
attempt-1 executor finding SHA-256
`e7607cf15818e2c05b1fc997d92a06f133fe98e12d543e6d8555ddea96192f91`;
custody receipt SHA-256
`48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9`;
current `.oracle/custody.md` SHA-256
`94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`;
attempt-1 Grok check-in SHA-256
`cdc6cd9b0ecfc3097c0c2940bb9ce85b810a84ab81ceb777ead97dfdc86ec89b`.

The custody correction is already MET: `f8725af...` is historical and
`798c506...` is current. Do not request or perform another custody edit.
The historical 52-to-61 count mutation and unreproducible
`4aee815d...` digest remain historical evidence; current 78/78 results and
`e060f650...` are observations, not waivers or targets.

## Verbatim Megado delegation mandate

> DELEGATION MANDATE — You are a manager and validator of the normal execution pool, NOT a worker. Delegate as much as possible to the task's selected normal model: DeepSeek V4 Flash or GPT-5.6 Luna. Flash invocation: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800`; Luna invocation: `launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=<brief> --project-dir=<worktree>` (research-only briefs use read/search tools). Dispatch research, execution, and critique briefs to the selected model — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read delegated output against the acceptance criteria; do work yourself only when delegation is impossible — the selected normal model already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a normal-pool brief would cover it. It almost always would.

Apply policy exactly: all normal implementation, exploration, critique, and
independent review is GPT-5.6 Luna; Grok 4.6 is Oracle and `[XHARD]` only. The
accepted work is deterministic contract/test work, so `[XHARD]`: **none**.

## Still-accepted findings to triage

Deduplicate these seven findings into the minimum coherent task set, retaining
the exact frozen NBF-01 boundary and earlier passing work:

1. **Blocker — one-door CAS and reservation-bound context:**
   `IncidentLedger.reserve`, `append_terminal_outcome`,
   `reserve_provider_route_child`, `consume_changed_precondition`,
   `create_probe_lease`, `reconcile_reservation`, `_append_nbf`, and replay
   still have bypass/identity/atomicity holes. Bind persisted reservation,
   accepted-launch, terminal, reconciliation, authorizer, and schema/version
   evidence under the existing journal lock; reject invalid replay and prove
   OS-process contention, torn/crash boundaries, terminal races, and exact
   recovered-disposition linkage without duplicate append.
2. **Blocker — incomplete strict schema matrix:**
   `phase_result.py` outcome combinations and `validate_nbf_event` append-path
   validation still permit incompatible payloads or constructor bypasses.
   Close all six-kind matrices, identity/timing/version rules, positive OOM,
   and fabricated unknown-death rejection at decode and append.
3. **Blocker — caller-controlled changed-precondition authority:**
   `ChangedPrecondition.produce`, `__post_init__`,
   `IncidentLedger.append_changed_precondition`, and consumption still accept
   generic/caller-derived authoritative fields and forged coherent IDs. Use
   reason-specific source-reading producers, bind cited evidence and provider
   key before/after, and make consumption single-use and atomic.
4. **Major — keyed provider replay:**
   `IncidentLedger._project_records` and route-child mechanics omit complete
   projection/failure identity, reset broad same-base streams, mishandle
   authoritative key transitions, and fail to consume one recovery authorizer.
   Complete keyed streak/rekey/reset/break behavior, preserving probe and
   `provider_recovery_verified` streaks; do not implement T8 policy.
5. **Major — durable two-scan confirmation and CLI:**
   `observe_confirmation`, `consume_confirmation`, `expire_confirmation`,
   confirmation schemas, and `_record_cli` still allow omitted identity,
   timestamp-only proof, weak replacement/expiry/reopen, wrong validation
   ordering, or unproved status branches. Require durable PID/process-start,
   progress, incarnation, cause, evidence identity and locked one-consumer
   semantics; implement exact statuses 0/2/3/4/5 and named tests.
6. **Major — thin acceptance evidence:** add deterministic behavioral coverage
   for every absent frozen must criterion (multi-process races, torn composite,
   forged valid hashes, context mismatch, positive OOM/unknown death,
   replacement/incarnation/restart, CLI 4/5, keyed replay byte identity), and
   publish complete argv/cwd/exit/stdout/stderr plus per-command SHA-256 bound
   to the actual candidate. Never rewrite historical receipts.
7. **Minor — generic aliases/constructors:** remove or constrain
   `IncidentLedger.append_worker_disposition`, `write_terminal_outcome`,
   `reserve_admission`, `reconcile`, `replay_projection` and generic
   disposition constructors unless a frozen downstream symbol truly requires
   them; use explicit typed constructors. Treat as part of the relevant seam,
   not a new abstraction.

## Required tasklist shape

Create the smallest set of Normal/Luna tasks (normally four seams: ledger
CAS/context/schema/producers; keyed replay; confirmation/CLI; evidence and
alias closure). For each task state: ID, severity, Normal classification and
why it is not `[XHARD]`, executor, dependencies, exact production/test/evidence
files and symbols, preserved prior-MET behavior, prohibited files/behaviors,
acceptance criteria, and exact commands. Include the frozen focused pytest
command covering the nine NBF modules; legacy regression; OS subprocess
contention; replay/torn/crash; CLI 0/2/3/4/5; `python -m py_compile`; and
`git diff --check`. Tests must be behavioral and deterministic, not count
inflation.

Preserve ownership: NBF-01 primitives only. No admission callers, scheduler,
T7/T8 thresholds or policy, physical doors, launch adapters, signal-site
wiring, fallback policy, second journal/store/projection, rotator, family
lease, or main merge. Keep prior source/test changes and custody correction.

End the tasklist with a gate requiring one fresh Luna execution receipt/finding,
complete immutable candidate-bound evidence, then one separate Grok Oracle
decision. Explicitly prohibit implementation by this Oracle, frozen-tasklist or
plan mutation, commit/push/merge, and Batch 2 dispatch. The receipt must map all
seven findings to task IDs, state `[XHARD]` none, preserve the custody and
historical-evidence decisions, and say no implementation was performed.

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
