# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework attempt 3 triage

## Mission

You are Grok 4.6, the Oracle and manager/validator for NBF-01 Batch 1 rework
attempt 3. Attempt 2 ended in `ACCEPTED_ISSUES`. Inspect the actual current
candidate code and tests plus every bound attempt-2 artifact below, then produce
the smallest explicit supplemental rework packet that closes all and only the
nine confirmed issues in the attempt-2 Grok verdict. Preserve every prior-MET
behavior and the frozen ownership boundary. This is triage, not implementation.

Write exactly these two new immutable prose artifacts:

1. `.oracle/rework/batch-1-attempt-3.md`
2. `.oracle/receipts/rework-triage-batch-1-attempt-3-grok.md`

Do not edit production code, test code, the frozen tasklist, the settled plan,
the North Star, custody, status, agent goal, historical evidence, or any prior
brief/check-in/finding/receipt. Do not stage, commit, push, merge, rebase, reset,
clean, launch execution, commission a review, or start Batch 2. No Batch 1 pass
decision is authorized in this triage turn.

## Frozen identities and candidate binding

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Candidate branch: `megado-nbf-guard-0826`
- Planning HEAD (the production candidate is still uncommitted on top):
  `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base and merge-base:
  `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist: `.oracle/tasklist.md`
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star: `.oracle/northstar.md`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-2 owned tracked-production diff SHA-256:
  `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`
- Attempt-2 supplemental tasklist SHA-256:
  `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721`
- Attempt-2 triage receipt SHA-256:
  `3f1c460d06966d5eef2999e5e4b99e5324b2aa920609d10ffe2d54af81a41703`

The tracked-production diff digest is the reviewed attempt-2 identity, not a
future target: attempt-3 execution must measure and bind its own post-fix tree.
Do not rewrite attempt-2 artifacts when that digest changes.

## Required attempt-2 evidence — read completely

Read all of the following before writing either output, and independently
inspect every cited source/test symbol rather than accepting narrative claims:

| Artifact | SHA-256 |
| --- | --- |
| `.oracle/findings/execution-nbf01-rework2-luna.md` | `896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb` |
| `.oracle/receipts/execution-nbf01-rework2-luna.md` | `d03d259725484d4eac22cae1e2582288a85a2d2dbfbbfbba7a2b0878b9b02e51` |
| `.oracle/briefs/oracle-nbf01-rework2-luna-review.md` | `b4647bc377366ef4e2f6eeeb8bfc24f480bc0dbe2de21858873bcad372cde456` |
| `.oracle/checkins/batch-1-rework2-luna.md` | `bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a` |
| `.oracle/receipts/oracle-nbf01-rework2-luna.md` | `53a69d3e8a4a232c63e7f25fcda279b0059162087a7d45244ba0bf8d271f6f2e` |
| `.oracle/checkins/batch-1-rework2-grok.md` | `5ceb712841cb02a0abeb5142864b08107f86695020c872861dc1d1b8bc940455` |
| `.oracle/receipts/oracle-nbf01-rework2-grok.md` | `622126f1a8ba909a6439a8f012c3e688c7c7bd4afe89ed1580bec1d06bb32e67` |

Also read in full `.oracle/agent_goal.md`, `.oracle/tasklist.md`,
`.oracle/rework/batch-1-attempt-1.md`, `.oracle/rework/batch-1-attempt-2.md`,
the original and attempt-1 Batch 1 Luna/Grok check-ins, both prior triage
receipts, `.oracle/custody.md`, and `.oracle/receipts/model-policy-grok-switch.md`.
Inspect the current owned source and tests, especially:

- `arnold_pipelines/megaplan/incident/{__init__,schema,ledger,disposition}.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- the eight new `tests/arnold_pipelines/megaplan/test_{worker_disposition,scheduling_conditions,provider_route_projection,incident_ledger_transactions,reservation_reconciliation,terminal_outcomes,changed_precondition_producers,supervision_confirmation}.py` modules
- unchanged legacy `tests/arnold_pipelines/megaplan/test_incident_ledger.py`

Treat focused `101 passed` and legacy `78 passed` as observations, never as
acceptance targets. Preserve historical evidence as historical: the 52→61
mutation, unreproducible `4aee815d…`, failed-handoff `50c86490…`, attempt-1
78/78 and `e060f650…`. Custody is already corrected and must not be edited.

## Model and delegation policy

Grok 4.6 owns Oracle judgment and any genuinely justified `[XHARD]` item.
GPT-5.6 Luna owns all Normal exploration, implementation, validation, and the
later independent review. For every attempt-3 task, record `Normal/Luna` or
`[XHARD]/Grok 4.6` and give a concrete routing rationale. Deterministic schema,
ledger, reducer, CLI, test, and evidence work is presumptively Normal/Luna; do
not inflate difficulty to `[XHARD]`. If no issue is truly `[XHARD]`, state
`[XHARD]: none`. This turn only authors the triage packet and receipt; it does
not dispatch either model.

## Nine confirmed issues — complete required coverage

The attempt-3 packet must map every issue below to one or more task IDs, with no
silent merging or omission. For each task give severity, model/routing class,
executor, exact dependencies, exact production/test/evidence files and symbols,
preserved prior-MET behavior, prohibited scope, behavioral acceptance tests,
exact validation commands, and evidence/receipt requirements.

### A3-01 — blocker: terminal accepted-launch is self-authorized (C10)

Seams: `IncidentLedger.append_terminal_outcome` and `_project_records` in
`incident/ledger.py` (attempt-2 review cited approximately lines 659–718 and
544–575), plus terminal/transaction/reconciliation tests. Replay currently
derives `accepted_launch` from the terminal being appended; Luna's source probe
accepted a fully populated terminal without a previously persisted accepted
launch marker.

Acceptance must require exactly one persisted, receipt-bound accepted
`controlled_adapter_state` matching the reservation/phase/spec/logical worker/
worker/start context before a terminal append. A fully populated terminal with
no marker and every single-field mismatch must fail closed. Preserve atomic,
idempotent one-terminal linkage and no-launch separation.

### A3-02 — blocker: payload and typed identity matrix holes (C02/C13/C14)

Seams: `DispatchOutcome.__post_init__` / `from_dict` in
`orchestration/phase_result.py`, disposition/death constructors and
`validate_nbf_event` in `incident/schema.py`, the ledger append door, and
worker-disposition/scheduling/terminal tests. `worker_disposition` still accepts
`success_payload`; worker fingerprint/identity typing and subject/cause rules
are incomplete; append-path OOM and unknown-death coverage is selected rather
than exhaustive.

Acceptance must enforce the complete six-kind incompatibility matrix at direct
construction, decode, validation, and append. Exercise every incompatible
payload family; required/missing/fabricated identity fields; false, zero, and
negative OOM evidence; unknown death with fabricated killer and signal; legal
positive OOM; and legal unknown death that remains unknown. Tests must reach
the actual append boundary, not only constructors.

### A3-03 — blocker: changed-precondition authority remains forgeable (C19–C21)

Seams: `ChangedPrecondition.produce`, `produce_changed_precondition`,
`_produce_reason_specific`, reason-specific producers in `incident/schema.py`,
and `IncidentLedger.append_changed_precondition` / consumption in
`incident/ledger.py`, with producer tests. Current IDs hash caller-supplied
before/after/evidence snapshots, and a coherent forged provider-key transition
with recomputed IDs can append.

Acceptance must replace or seal the generic caller-snapshot path with an
allowlisted reason-specific authoritative reader per reason. Append and consume
must recompute/verify producer, subject, version, cited evidence digest,
authoritative before/after content, and provider-failure-key transition. Add a
coherent forgery test that recomputes every content/event hash and still rejects;
prove valid producer output is single-use under the journal lock.

### A3-04 — major: applicable provider stream is not selected (C11/C32/C33)

Seam: `IncidentLedger._project_records` in `incident/ledger.py` plus provider
projection and terminal tests. Success, ordinary failure, and worker disposition
without a provider key currently mutate `latest_stream_key`; Luna proved a
success for A after B was most recent left A at streak 2 and reset B to 0.

Acceptance must carry/derive the applicable provider-failure-key identity for
success, ordinary failure, and worker disposition, mutate only that keyed
stream, reset the correct success stream, and break consecutiveness on the
correct ordinary/disposition stream without creating degradation. Add
non-latest-target, restart/replay, and cross-key isolation tests. Do not add T8
thresholds or policy.

### A3-05 — major: recovery/child authorization is not evidence-bound (C23/C34)

Seams: `IncidentLedger.reserve_provider_route_child`, probe-result persistence,
reason-specific `provider_recovery_verified` production/consumption, composite
append, and provider tests. A repeated authorizer rejects, but the candidate
does not require a persisted passed canonical probe tied to parent/phase/route/
provider plus a producer-derived recovery change.

Acceptance must require the matching successful canonical probe and fixed
authoritative `provider_recovery_verified`, consume the authorization exactly
once inside the one composite append, create exactly one linked same-route
child reservation, and preserve the matching keyed streak. Prove mismatched,
failed, absent, replayed, and already-consumed probe/recovery evidence rejects.

### A3-06 — major: composite replay/crash and terminal-race evidence is ceremonial (C27/C28/C09)

Seams: `_emit_locked`, composite route-child append/receipt derivation, terminal
linkage, `test_incident_ledger_transactions.py`, and
`test_provider_route_projection.py`. The required replay test currently covers
an ordinary reservation; torn-composite writes a malformed prefix instead of
injecting a real composite failure; terminal contention races the same ID.

Acceptance must put a real composite transaction beneath the exact required
fresh-replay test name and prove its post-append receipt is byte-identical after
a new ledger instance. Inject failure at the real composite `_emit_locked` /
post-append receipt boundary and prove both-or-neither projection/receipt after
restart. Race two OS processes using distinct terminal IDs and conflicting
kinds against one reservation; exactly one linkage may win and replay must stay
valid. Avoid a second journal or prepare/commit protocol.

### A3-07 — major: confirmation and CLI evidence remains thin (C39/C41)

Seams: confirmation event schemas, `observe_confirmation`,
`consume_confirmation`, `expire_confirmation`, replay, and `_record_cli` in
`incident/ledger.py` / `incident/disposition.py`, plus supervision-confirmation
tests. Identity coverage mutates only process start; expiry can overwrite a
consumed state; status 5 lacks expired and distinct already-consumed subprocess
cases.

Acceptance must cover exact equality and every single-field mismatch/omission
for PID, process start, progress sequence, incarnation, cause, evidence, TTL,
and scan separation; durable restart, replacement, expiration, single
consumption, and reopen behavior; and rejection of expiry after consumption.
Run real non-signalling CLI subprocesses for 0/2/3/4/5, including malformed and
schema-invalid 2, append/lock 3, invalid ledger 4, and missing, expired, and a
distinct already-consumed replay for 5. Status 0 must emit one JSON ack only
after a matching consumed confirmation.

### A3-08 — major: immutable executor evidence protocol is incomplete (RW2-04)

The attempt-2 executor receipt omitted explicit HEAD, used truncated empty-output
digests, omitted per-command stderr hashes, and cited CLI pytest names instead
of independently bound subprocess transcripts. Independent review evidence
does not retroactively repair that executor artifact.

Acceptance for the later attempt-3 execution must require a new immutable
executor finding and receipt at new attempt-3 paths, bound to the exact post-fix
HEAD and tree. They must include a complete tracked/untracked changed-file
inventory; production diff digest; full argv and cwd for every command; exit
status; verbatim stdout/stderr or immutable transcript path; and full 64-hex
SHA-256 for stdout and stderr. Independently invoke and bind CLI 0/2/3/4/5.
Never rewrite attempt-2 evidence.

### A3-09 — minor: unofficial convenience surface remains

Seam: `IncidentLedger.reserve_provider_route_child_with_receipt` in
`incident/ledger.py` (attempt-2 review cited approximately lines 781–783). It is
not a frozen required symbol and forwards generic `**kwargs`.

Acceptance must delete it unless the triage inspection identifies and documents
a frozen downstream caller that requires it; if required, constrain it to an
explicit typed signature rather than generic forwarding. Add only the smallest
necessary API-surface assertion.

## Dependency and packaging constraints

Use the fewest coherent implementation tasks. The packet may combine adjacent
seams, but its issue-to-task matrix must retain A3-01 through A3-09 explicitly.
At minimum reflect these dependencies:

- authoritative schema/context foundations A3-01–A3-03 precede dependent
  reducer/recovery work;
- A3-04 precedes or is coordinated atomically with A3-05;
- A3-06 validates the completed A3-01/A3-05 transaction behavior;
- A3-07 may execute independently where file ownership does not overlap;
- A3-08 runs last against the stable post-fix candidate;
- A3-09 is a small seam-local cleanup and must not create a new abstraction.

Require one writer per overlapping file or an explicit serial order. Preserve
all prior MET results named by the attempt-2 Grok verdict, especially the single
`_IncidentEventJournal` and sequence-sidecar flock, one `_locked` NBF mutation
door, C03–C06, C08, C12, C15–C18, C22, C25, C26 shape, C29 order, C30/C31 for
matching streams, C35, real two-process reservation contention, no second
journal/store, and RW-CUSTODY.

Prohibit admission callers, scheduler work, T7/T8 policy, physical doors,
launch-adapter or signal-site wiring, fallback policy, a second journal/store/
projection, prepare/commit, family lease, rotator, main merge, and Batch 2.

## Required behavioral validation contract

The packet must name exact commands, not only desired counts. Include:

1. focused pytest over the eight new NBF modules plus unchanged
   `test_incident_ledger.py`;
2. required legacy incident projection/summary/bridge and phase-result-classify
   regressions;
3. direct OS-process reservation contention and distinct-ID terminal races;
4. actual composite replay and injected crash/torn-write recovery;
5. coherent changed-precondition forgery with recomputed IDs;
6. terminal-without-accepted-marker and every context mismatch;
7. non-latest applicable-provider-key reset/break/replay;
8. successful/failed/missing/mismatched/consumed recovery probe authorization;
9. complete confirmation identity, TTL, replacement, restart, and one-consumer
   races;
10. independent CLI subprocesses for statuses 0, 2, 3, 4, and 5;
11. `python -m py_compile` for every owned production module; and
12. `git diff --check`.

Tests must be behavioral, deterministic, and fail on the attempt-2 candidate;
test-count growth is not proof. Require attempt-3 executor evidence to record
full stdout/stderr hashes for each command and bind the exact stable candidate.

## Output requirements

`.oracle/rework/batch-1-attempt-3.md` must contain:

- the frozen identities above and all nine issue IDs;
- the smallest task set, with severity, model/routing classification and
  rationale, executor, dependencies, exact file/symbol ownership, preserved
  behavior, prohibited scope, behavioral acceptance criteria, and exact tests;
- an explicit issue-to-task and dependency matrix;
- a final execution-evidence gate requiring one fresh immutable attempt-3 Luna
  executor finding/receipt, followed later by exactly one fresh independent
  Luna full review and a separate Grok 4.6 Oracle gate;
- an explicit ban on commit/push/merge/Batch 2 before `PASS_BATCH_1`.

`.oracle/receipts/rework-triage-batch-1-attempt-3-grok.md` must record:

- Grok 4.6 Oracle role and no implementation/review dispatch;
- source, frozen tasklist, North Star, attempt-2 production diff, and every
  fresh Luna/Grok attempt-2 evidence digest in this brief;
- the exact attempt-3 packet SHA-256;
- the nine-issue-to-task mapping, dependency order, and model routing decisions;
- preservation of custody, historical evidence, frozen tasklist, and prior-MET
  behavior;
- confirmation that no production/test edit, stage, commit, push, merge, or
  Batch 2 work occurred.

End the receipt with the next authorized action only: dispatch the Normal/Luna
attempt-3 executor against the supplemental packet. Do not issue
`PASS_BATCH_1` or edit any artifact other than the two required outputs.

## Complete immutable North Star (verbatim)

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
