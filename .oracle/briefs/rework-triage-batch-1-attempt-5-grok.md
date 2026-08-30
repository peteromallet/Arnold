# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework attempt 5 triage

## Mission and exact output boundary

You are Grok 4.6, the Oracle and manager/validator for NBF-01 Batch 1 rework
attempt 5. Attempt 4 ended in `ACCEPTED_ISSUES`. Read the final attempt-4 Luna
and Grok check-ins and receipts, independently inspect the current source and
tests, sense-check every finding, and author the smallest serial supplemental
packet for only the three accepted issues below. Start with the coherent
changed-precondition forgery blocker. Reject duplicates, nonissues, and scope
expansion. This is triage only, not implementation or a review commission.

Write exactly these two new immutable prose artifacts:

1. `.oracle/rework/batch-1-attempt-5.md`
2. `.oracle/receipts/rework-triage-batch-1-attempt-5-grok.md`

Do not edit production or test code. Do not dispatch Luna or any reviewer in
this triage turn; later execution/review is outside this brief. Do not stage,
commit, push, merge, rebase, reset, clean, mutate the frozen tasklist or
settled plan, rewrite history or any prior receipt/check-in, edit custody,
North Star, status, or agent goal, issue a Batch 1 pass decision, or start
Batch 2.

## Candidate and immutable identities

Bind the triage to candidate repository
`/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch
`megado-nbf-guard-0826`, observed candidate HEAD
`922241d0bdb3e993c3b554cc69f19948adef7bc3`, and source/merge-base
`origin/main@798c50619204010ed3f4297fbb57988fe9381924`. Re-check and report
the actual HEAD before writing the packet.

- frozen tasklist `.oracle/tasklist.md`, SHA-256
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star `.oracle/northstar.md`, SHA-256
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- production diff SHA-256
  `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

Final attempt-4 evidence to read, hash, and bind:

- Luna check-in `.oracle/checkins/batch-1-rework4-luna.md`, SHA-256
  `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`
- Luna receipt `.oracle/receipts/oracle-nbf01-rework4-luna.md`, SHA-256
  `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee`
- Grok check-in `.oracle/checkins/batch-1-rework4-grok.md`, SHA-256
  `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf`
- Grok receipt `.oracle/receipts/oracle-nbf01-rework4-grok.md`, SHA-256
  `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607`

Supporting attempt-4 provenance:

- packet `.oracle/rework/batch-1-attempt-4.md`, SHA-256
  `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- triage brief `.oracle/briefs/oracle-nbf01-rework4-triage-grok.md`, SHA-256
  `d6c559d694c006d4fd310ae706779604ebe228f713a27a40669d6c5c1c040c0f`
- triage receipt `.oracle/receipts/rework-triage-batch-1-attempt-4-grok.md`,
  SHA-256 `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- executor finding `.oracle/findings/execution-nbf01-rework4-luna.md`,
  SHA-256 `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- executor receipt `.oracle/receipts/execution-nbf01-rework4-luna.md`,
  SHA-256 `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`
- execution brief `.oracle/briefs/execution-nbf01-rework4-luna.md`, SHA-256
  `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d`

Keep prior attempt-1/2/3 artifacts and all historical digests immutable. In
particular, preserve the historical attempt-3 production digest
`8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`, attempt-2
digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
the start-gate 52→61 observation, unreproducible digest
`4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`, and
failed-handoff digest
`50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`.

## Required reading and independent sense-check

Read in full before authoring either output:

- `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`;
- frozen `.oracle/tasklist.md`, settled `.oracle/plan.md`, and the freeze
  receipt;
- all supplemental packets and triage receipts through attempt 4;
- attempt-4 Luna executor finding/receipt and final Luna/Grok check-in/receipt;
- the current production diff and the relevant source/test files.

Independently verify every attempt-4 claim that becomes a task. Reproduce the
coherent changed-precondition path, including the exact recomputation of every
serializable snapshot/content/event/provider-key field, and determine whether
`validate_nbf_event`, the canonical/private append door, projection, and
`reserve()` still accept it. Distinguish a genuine authorization defect from
test ceremony. Verify that C41 CLI 0/2/3/4/5, keyed provider/recovery behavior,
terminal race/crash behavior, and executor evidence completeness remain
preserved rather than reopening them.

Record complete path/hash checks, candidate HEAD/base, commands, models,
timestamps, exit statuses, and full stdout/stderr or immutable transcript
digests in the receipt. The packet and receipt must state that any broad-suite
missing-module collection failures remain
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`, not an implementation task.

## Only accepted attempt-5 issues

The supplemental packet must contain exactly Issues 1–3 below, mapped to task
IDs RW5-01, RW5-02, and RW5-03. Do not create a fourth issue or a cleanup,
environment-repair, policy, custody, or evidence-normalization program.

### Issue 1 — blocker: coherent changed-precondition authority remains forgeable

Criteria: C19–C21, RW4-01, A3-03. Affected seams are
`ChangedPrecondition`, `_authoritative_source`, `_produce_authoritative`, the
allowlisted reason-specific producers and `_validate_changed_precondition_wire`
in `arnold_pipelines/megaplan/incident/schema.py`, plus
`IncidentLedger.append_changed_precondition`, `_append_nbf`, projection,
`reserve`, and `consume_changed_precondition` in `incident/ledger.py`, with
the existing coherent-forgery tests.

Independent attempt-4 evidence says typed handles guard the public producer,
but a caller-shaped, internally self-consistent wire snapshot still passes
`validate_nbf_event`, `_append_nbf`, projection, and fresh `reserve()`
authorization. Treat this as the blocker unless fresh source/probe evidence
falsifies it. The required narrowly bounded outcome is one authoritative
producer/reader contract at every changed-precondition authorization door.

Acceptance must require all of the following:

- A smallest typed authoritative source handle/reader per allowlisted reason;
  a caller-shaped snapshot is never authority.
- Producer identity, reason, subject, source version, persisted cited evidence,
  evidence digest, canonical before/after content, and provider-key derivation
  are bound and validated at decode, canonical/private append, and locked
  consume.
- The adversarial test recomputes every serializable hash/ID and proves
  rejection at each relevant door, including no projection and no `reserve()`
  authorization; a valid reason-specific reader event still appends and is
  consumed once under the existing journal lock.
- No second authority store, generic producer escape hatch, signature service,
  speculative plugin system, second journal, or new policy owner is introduced.

Goal/North Star binding: this directly gates C19–C21 and CP02/CP04/CP11, and
the North Star principle “One door per invariant”; it also prevents the
“Redispatch of an identical failure fingerprint without a changed precondition”
anti-pattern.

Dependencies/order: RW5-01 is first and blocks RW5-02 and RW5-03. Sole writer
is the selected Normal/GPT-5.6 Luna executor for the owned schema/ledger seams
and existing changed-precondition test module. Grok must state why no file
ownership split is needed; any proposed split must preserve serial one-writer
ordering.

Exact validation commands to require from execution include the targeted
changed-precondition module, the named adversarial wire/private-append/
`reserve()` regression, the full frozen focused suite, legacy ledger suite,
`python -m py_compile` for owned production modules, and `git diff --check`.
Record exact argv/cwd/exit/stdout/stderr digests for each.

### Issue 2 — major: strict payload and typed-identity proof is incomplete

Criteria: C02/C13, RW4-02, A3-02. Affected seams are
`DispatchOutcome.__post_init__`, `DispatchOutcome.from_dict`, six-kind decode
paths in `orchestration/phase_result.py`, worker/observed-death/non-worker
schemas and `validate_nbf_event`, the real locked ledger append door, and the
existing named tests in `test_scheduling_conditions.py`,
`test_worker_disposition.py`, and `test_terminal_outcomes.py`.

Attempt-4's named matrix is constructor-oriented except for one
worker-disposition + success-payload pairing; typed identity omissions and
fabrications are not proved across every required door. The narrowly bounded
outcome is evidence, and only minimal behavior if necessary, for the complete
incompatible-payload and identity matrix at direct construction, `from_dict`,
`validate_nbf_event`, and real public locked append. Include all six kinds,
missing/fabricated worker, observed-death, and non-worker identities, and legal
positive OOM/unknown/non-worker cases. Do not expand `PhaseResult.from_dict`
or reopen C01.

Goal/North Star binding: C02/C13 and CP02/CP09, with “Deaths speak” and typed
records that cannot be silently coerced. Dependencies: RW5-02 follows the
RW5-01 authority closure and must not weaken its rejection boundary. Sole writer
is Normal/GPT-5.6 Luna over the existing schema/phase/test seams.

Exact validation commands must include the three named test modules and their
full incompatible-payload/typed-identity matrix, then the frozen focused and
legacy suites, `python -m py_compile` for owned modules, and `git diff --check`.
Capture complete streams and digests, not just pass counts.

### Issue 3 — major: confirmation evidence-digest equality is incomplete

Criteria: C39, RW4-05, A3-07. Affected seams are the confirmation schema,
`observe_confirmation`, `consume_confirmation`, expiration/replacement/replay
in `incident/ledger.py` and `incident/schema.py`, and the existing named test
`test_confirmation_compares_pid_start_progress_incarnation_cause` in
`test_supervision_confirmation.py`.

Attempt-4 source compares `second_evidence_digest`, but the required named test
does not mutate or omit that field. The narrowly bounded outcome is explicit
wrong and missing second-evidence cases in the existing equality matrix,
retaining all already-MET restart, replacement, expiration, reopen,
expiry-after-consume, and locked one-consumer behavior. C41 CLI 0/2/3/4/5 is
already complete and is a regression rerun only; do not redesign the CLI.

Goal/North Star binding: C39/CP11, the anti-pattern against treating a single
scan as sustained truth, and durable typed evidence for confirmation. RW5-03
follows RW5-02 and is last among behavioral fixes; sole writer is
Normal/GPT-5.6 Luna over the existing confirmation schema/ledger/test seam.

Exact validation commands must include the named confirmation test with wrong
and omitted evidence, the CLI status 0/2/3/4/5 regression subprocess matrix,
the frozen focused and legacy suites, `python -m py_compile` for owned modules,
and `git diff --check`, with full command metadata and stream digests.

## Model classification and exceptional threshold

Every implementation, test, validation, and evidence task in this packet is
**Normal / GPT-5.6 Luna**. `[XHARD]: none.` The work is deterministic schema,
ledger, behavioral-test, and receipt correction work that is decomposable into
three serial tasks. Do not classify it as XHARD because it is important, spans
files, takes time, or had a prior incomplete attempt. Any proposed `[XHARD]`
classification must include concrete evidence that decomposition is
insufficient and that the Normal pool cannot reliably execute the specific
irreducible judgment kernel; absent that full threshold evidence, reject it and
keep the task Normal/Luna. Grok 4.6 is Oracle only and must not implement.

For each task in the packet include: task ID; issue/criterion IDs and severity;
Normal/GPT-5.6 Luna classification and why not XHARD; exact dependency and
serial order; sole writer and owned files/symbols; preserved prior-MET
behavior; prohibited scope; narrowly bounded outcome; step-by-step behavioral
acceptance; exact validation commands; and immutable evidence requirements.

## Serial task contract

Use one repository writer at a time and the fewest coherent tasks:

```text
RW5-01 C19–C21 wire/private-append/reserve authorization closure
  → RW5-02 C02/C13 complete six-kind/four-door payload and identity matrix
  → RW5-03 C39 confirmation evidence-digest mismatch/omission matrix
  → later fresh Normal execution evidence, exactly one independent Luna review,
    and a separate Grok Oracle gate
```

Do not dispatch any of those later phases from this triage turn. Preserve all
attempt-4 MET behavior: keyed non-latest provider/recovery proof, canonical
probe lease binding, terminal race and composite crash/reopen proof, CLI
0/2/3/4/5, one journal/lock, typed dispositions, and immutable executor
evidence. Do not reopen C36–C38, C01 overweight round-trip, C40 cache mismatch,
T8 policy, broad missing modules, custody, historical receipts, admission,
scheduler, physical doors, launch/signal/fallback policy, family leases,
rotators, second stores, prepare/commit, merge, or Batch 2.

## Required packet/receipt contents

The supplemental packet must map exactly Issues 1–3 to RW5-01…RW5-03 and state
the above serial dependencies, exclusions, model classifications, acceptance
criteria, and exact validation commands. The receipt must record:

- actual candidate HEAD, branch, source/merge-base, tasklist and North Star
  identities, and all four final attempt-4 artifact matches;
- every command used by Grok for inspection, with exact argv, cwd, timestamp,
  exit status, complete stdout/stderr or immutable transcript paths, and full
  stream SHA-256 digests;
- fresh independent probe results for the coherent forgery, including whether
  projection and `reserve()` authorization remain possible;
- accepted/rejected/duplicate/nonissue reasoning for each attempt-4 finding;
- the full path and SHA-256 of both new outputs after writing;
- explicit confirmation that no source/test/frozen/history/status/goal/custody
  file, commit, Batch 2, or reviewer dispatch was performed.

Do not issue `PASS_BATCH_1` or `ACCEPTED_ISSUES` from this triage brief; the
output is a supplemental task packet for a later execution gate.

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
