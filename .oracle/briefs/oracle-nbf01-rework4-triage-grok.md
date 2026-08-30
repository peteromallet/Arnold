# Grok 4.6 Oracle brief — NBF-01 Batch 1 rework attempt 4 triage

## Mission and exact output boundary

You are Grok 4.6, the Oracle and manager/validator for NBF-01 Batch 1 rework
attempt 4. Attempt 3 ended in `ACCEPTED_ISSUES`. Inspect the current source and
tests plus the complete attempt-3 Luna/Grok evidence, then author the smallest
serial supplemental packet that covers **only** accepted issues 1–6 below.
Start with the C19–C21 coherent-forgery blocker. Preserve all attempt-3 progress
and every earlier-MET behavior. This is triage only, not implementation or gate
review.

Write exactly these two new immutable prose artifacts:

1. `.oracle/rework/batch-1-attempt-4.md`
2. `.oracle/receipts/rework-triage-batch-1-attempt-4-grok.md`

Do not edit production or test code. Do not stage, commit, push, merge, rebase,
reset, clean, mutate the frozen tasklist or settled plan, rewrite history or any
prior receipt, edit custody/North Star/status/agent goal, dispatch execution or
review, issue a Batch 1 pass decision, or start Batch 2.

## Immutable identities

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Candidate branch: `megado-nbf-guard-0826`
- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source and merge-base:
  `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist: `.oracle/tasklist.md`
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star: `.oracle/northstar.md`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-3 tracked-production diff SHA-256:
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- Attempt-3 Luna review check-in
  `.oracle/checkins/batch-1-rework3-luna.md` SHA-256:
  `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd`
- Attempt-3 Luna review receipt
  `.oracle/receipts/oracle-nbf01-rework3-luna.md` SHA-256:
  `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425`
- Attempt-3 Grok verdict check-in
  `.oracle/checkins/batch-1-rework3-grok.md` SHA-256:
  `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02`
- Attempt-3 Grok verdict receipt
  `.oracle/receipts/oracle-nbf01-rework3-grok.md` SHA-256:
  `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30`

The production digest is the reviewed attempt-3 identity, not an attempt-4
target. Attempt-4 execution must produce a new exact stable-tree digest and new
immutable evidence; no attempt-3 artifact may be edited to reflect later work.

## Required reading and inspection

Read in full before writing either output:

- `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`;
- frozen `.oracle/tasklist.md`, settled `.oracle/plan.md`, and tasklist-freeze
  receipt;
- all supplemental packets and triage receipts through attempt 3;
- attempt-3 executor finding/receipt;
- `.oracle/briefs/oracle-nbf01-rework3-grok.md`;
- the bound attempt-3 Luna review check-in/receipt;
- the bound attempt-3 Grok verdict check-in/receipt;
- prior Batch 1 review/check-in history needed to identify preserved MET work.

Inspect the current code and behavioral tests directly rather than copying the
review narrative. In particular inspect:

- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/incident/disposition.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- the eight new NBF test modules and unchanged legacy
  `tests/arnold_pipelines/megaplan/test_incident_ledger.py`.

Treat test counts as observations, not targets. Preserve historical 52→61,
unreproducible `4aee815d…`, failed handoff `50c86490…`, attempt-1 78/78 and
`e060f650…`, attempt-2 `16f6f854…`, and attempt-3 `8fe64464…` as immutable
historical evidence. RW-CUSTODY is already MET and must not be reopened.

## Model routing

Every implementation, validation, and evidence task in the attempt-4 packet is
**Normal / GPT-5.6 Luna**. These are deterministic schema, journal, reducer,
behavioral-test, and receipt corrections. **`[XHARD]: none`.** Grok 4.6 remains
Oracle only. Record that classification and a brief rationale on every task.
This triage turn must not dispatch either model.

## Only accepted attempt-4 issues

The packet must explicitly map Issue 1 through Issue 6 to task IDs. No seventh
implementation issue, cleanup program, speculative abstraction, or broader
criterion expansion is authorized.

### Issue 1 — blocker: changed-precondition authority remains forgeable (C19–C21, RW3-01, A3-03)

Exact seams:

- `ChangedPrecondition`, `_authoritative_source`, `_produce_authoritative`, and
  the seven allowlisted reason-specific producers in
  `arnold_pipelines/megaplan/incident/schema.py`;
- `IncidentLedger.append_changed_precondition` and
  `consume_changed_precondition` in
  `arnold_pipelines/megaplan/incident/ledger.py`;
- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`.

Current failure: `_authoritative_source` accepts caller dictionaries containing
`authority_kind`, `subject`, and `content`. A coherent forged transition with
recomputed snapshots, content IDs, evidence digest, provider keys, and event ID
passes `from_dict`, append, and consume. The required named test only changes a
provider key without coherently rebuilding the rest.

Required acceptance:

- Use the smallest typed authoritative source handle/reader per allowlisted
  reason; a caller-shaped snapshot is not an authority.
- Bind producer identity, reason, subject, source version, persisted cited
  evidence, evidence digest, canonical before/after content, and provider-key
  before/after derivation.
- Validate at decode/`from_dict`, append, and locked consume; do not rely only on
  content-address equality that an attacker can recompute.
- Retarget the existing coherent-forgery test so it recomputes every serializable
  hash/ID and proves rejection at each door.
- Prove a valid event can be minted only through the matching reason-specific
  source reader and consumed exactly once under the existing journal lock.
- Preserve C22 and do not add a second authority store, generic producer escape
  hatch, signature service, or speculative plugin system.

This is the first serial task, conventionally `RW4-01`. Grok may split only if
the source inspection proves a necessary file-ownership boundary, but no later
task may proceed until the coherent forgery is behaviorally closed.

### Issue 2 — blocker: strict payload and typed-identity proof is incomplete (C02/C13, RW3-01, A3-02)

Exact seams:

- `DispatchOutcome.__post_init__`, `DispatchOutcome.from_dict`, and associated
  six-kind decode paths in `orchestration/phase_result.py`;
- worker/observed-death/non-worker disposition schemas and
  `validate_nbf_event` in `incident/schema.py`;
- the actual locked ledger append validation door;
- existing named tests in `test_scheduling_conditions.py`,
  `test_worker_disposition.py`, and `test_terminal_outcomes.py`.

Required acceptance: strengthen existing named tests in place across direct
construction, `from_dict`, `validate_nbf_event`, and real append for the complete
incompatible-payload family and required typed identity fields. Include the
repaired `worker_disposition` + `success_payload` rejection in the named matrix,
missing/fabricated worker, observed-death, and non-worker identities, and legal
positive cases. Do not reopen C01 by forcing overweight records through
`PhaseResult.from_dict`; this task is C02/C13 proof at their owned doors.

### Issue 3 — major: applicable-key and recovery named proof is missing (C11/C32/C33/C34, CP06/CP07, RW3-02, A3-04/A3-05)

Exact seams:

- keyed provider replay in `IncidentLedger._project_records`;
- probe lease/result, `provider_recovery_verified`, and
  `reserve_provider_route_child` validation in `incident/ledger.py` and the
  relevant typed schema;
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`.

Required acceptance:

- Existing required names must target a **non-latest** stream, not the latest
  stream by construction, and assert numeric streaks for every affected and
  unaffected key.
- Prove success resets only its applicable non-latest key; ordinary failure and
  worker disposition break only their applicable non-latest key without
  degradation; restart/replay preserves the same selection and cross-key
  isolation.
- Bind any accepted canonical probe result to an existing unexpired matching
  probe lease. Prove passed, failed, absent, expired, mismatched, replayed, and
  already-consumed probe/recovery paths.
- Prove valid recovery consumes once in the one composite child append and
  preserves the applicable keyed streak.
- Do not add T8 thresholds/policy or fall back to `latest_stream_key`.

### Issue 4 — major: composite and terminal-race evidence is incomplete (C09/C28, CP08/CP11, RW3-03, A3-06)

Exact seams:

- `IncidentLedger._emit_locked`, composite child append and post-append receipt
  derivation, and terminal linkage in `incident/ledger.py`;
- `test_two_process_terminal_linkage_is_atomic` and composite crash tests in
  `test_incident_ledger_transactions.py`;
- composite replay test in `test_provider_route_projection.py`.

Required acceptance:

- Put the distinct-terminal-ID, conflicting-kind race from two real OS processes
  under the exact frozen required test name; exactly one linkage wins and fresh
  replay remains valid.
- Retain the real `_emit_locked` composite failure test and add a distinct
  injected failure after durable append but before receipt return/derivation.
- Reopen with a fresh ledger and prove the committed composite projects exactly
  once with a byte-identical deterministic receipt, while a pre-append failure
  exposes neither transition nor receipt.
- Do not add prepare/commit, a second journal, or a second receipt store.

### Issue 5 — major: durable confirmation equality matrix is incomplete (C39, RW3-04, A3-07)

Exact seams:

- confirmation schema and `observe_confirmation`, `consume_confirmation`,
  `expire_confirmation`, replacement/replay in `incident/ledger.py` and
  `incident/schema.py`;
- existing named confirmation tests in
  `test_supervision_confirmation.py`.

Required acceptance: require, persist, and compare every frozen identity,
timing, and evidence field, including PID, process-start identity, progress
sequence, incarnation, cause, evidence digest, TTL, expiry, scan interval/
separation, and policy/version identity where the frozen schema requires it.
Strengthen the existing named equality test with each single-field mismatch and
omission. Preserve restart, replacement, expiration, reopen, expiry-after-
consume rejection, and locked one-consumer race behavior. C41 CLI 0/2/3/4/5 is
already independently complete; rerun it for regression but do not redesign it.

### Issue 6 — major: immutable executor evidence protocol is incomplete (RW3-06, A3-08)

This is last and depends on the stable post-fix tree. Require new attempt-4
executor artifacts, never edits to attempt-3 evidence:

- `.oracle/findings/execution-nbf01-rework4-luna.md`
- `.oracle/receipts/execution-nbf01-rework4-luna.md`

Required acceptance:

- Bind exact HEAD, branch, source/merge-base, frozen tasklist/North Star,
  attempt-4 packet/triage receipt, and final production diff.
- Inventory every modified tracked file and every untracked owned production/
  test file with both `git hash-object` and full SHA-256. Explicitly include
  `incident/disposition.py` and all eight new NBF test modules.
- For every validation command record exact argv, cwd, exit, verbatim complete
  stdout/stderr or immutable isolated transcript, and full stdout/stderr SHA-256.
- Record the full megaplan-directory sweep output verbatim, including any
  pre-existing missing-module collection blocker; do not summarize it and do
  not repair those modules under this packet.
- Preserve all historical executor/reviewer artifacts without rewriting them.

## Explicit exclusions — reject scope reopening

The attempt-4 packet must explicitly reject and contain no task for:

- C36, C37, or C38 reconciliation semantics; Grok marked them MET;
- C01 via overweight `PhaseResult.from_dict` round-trip expansion;
- C40 cache-mismatch or broad cache/projection-version matrix expansion;
- T8 thresholds, degradation policy, retry scheduling, or escalation policy;
- restoring the two broad-suite missing modules or other environment repair;
- custody edits or re-adjudication;
- historical receipt/check-in rewrite or evidence normalization;
- admission callers, scheduler, physical doors, launch adapters, signal-site
  wiring, fallback policy, family leases, rotators, second journal/store,
  prepare/commit, main merge, or Batch 2.

Attempt-3 Grok classified the broad-suite missing modules as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`: context, not an NBF regression and not a
waiver. Attempt 4 must record the full sweep evidence but must not turn that
environment issue into an implementation task. C01/C40 remain unevidenced
context; this packet must not expand them. If the triage discovers a concrete
contradiction between an exclusion and one of Issues 1–6, document the conflict
in the receipt and stop rather than silently widening scope.

## Serial task and dependency contract

Use the fewest coherent tasks, but serialize all repository writers because the
remaining seams overlap. The default minimal sequence is:

```text
RW4-01 C19–C21 authoritative producer/forgery closure
  → RW4-02 C02/C13 named four-door matrix
  → RW4-03 keyed/recovery named proof and probe-lease binding
  → RW4-04 terminal race and post-append composite crash/reopen proof
  → RW4-05 confirmation equality matrix
  → RW4-06 stable-tree immutable executor evidence
  → RW4-GATE later fresh Luna review and separate Grok decision
```

Grok may combine adjacent tasks only when it reduces ownership/coordination
without obscuring Issue 1–6 mapping or acceptance. It may not reorder Issue 1
behind evidence-only work. For each task include: ID, issue IDs and criteria,
severity, `Normal / GPT-5.6 Luna`, why not `[XHARD]`, exact dependencies, sole
writer/owned files and symbols, preserved prior-MET behavior, prohibited scope,
step-by-step behavioral acceptance, exact test commands, and immutable evidence
requirements.

Preserve attempt-3 progress: persisted accepted-launch markers, positive OOM and
legal unknown-death append paths, worker+success rejection, keyed reducer without
latest-stream mutation fallback, real composite fresh replay, `_emit_locked`
failure injection, complete CLI 0/2/3/4/5 including expired/already-consumed,
expiry-after-consume rejection, route-child wrapper deletion, one journal, one
lock door, and all prior-MET C/CP results named by the attempt-3 Grok verdict.

## Required validation and final gate in the packet

Require exact commands for:

1. the frozen focused suite: eight new NBF modules plus unchanged
   `test_incident_ledger.py`;
2. the frozen legacy incident projection/summary/bridge and phase-result
   classification suite;
3. coherent changed-precondition forgery and valid source-reader/one-consume
   tests;
4. four-door payload/identity matrix tests;
5. non-latest keyed provider and canonical probe/recovery matrix;
6. real two-process distinct-terminal race and pre/post-append composite crash/
   reopen/receipt tests;
7. full confirmation equality, restart, TTL, replacement, expiry, and consumer
   contention tests;
8. direct CLI 0/2/3/4/5 regression subprocesses;
9. full `pytest -q tests/arnold_pipelines/megaplan` with complete output recorded
   even when the known pre-existing environment blocker recurs;
10. `python -m py_compile` over owned production modules; and
11. `git diff --check`.

Tests must be behavioral and deterministic, not pass-count inflation. End the
packet with `RW4-GATE`: after one fresh immutable Luna execution finding/receipt
for the exact stable candidate, require exactly one fresh independent Luna full
review and a separate Grok 4.6 Oracle synthesis. Commit/push/merge and Batch 2
remain forbidden until a later `PASS_BATCH_1`.

## Receipt requirements

`.oracle/receipts/rework-triage-batch-1-attempt-4-grok.md` must bind every
identity above plus the new attempt-4 packet SHA-256, map Issue 1–6 to task IDs
and dependencies, state every task is Normal/Luna and `[XHARD]: none`, enumerate
the explicit exclusions, preserve custody/history/prior-MET decisions, and
confirm this turn wrote only the packet and receipt—no implementation, test
edit, dispatch, stage, commit, push, merge, frozen-tasklist mutation, or Batch 2.
Its next authorized action is only dispatch of the Normal/Luna attempt-4
executor against the new packet.

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
