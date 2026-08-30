# Supplemental rework tasklist — NBF-01 / Batch 1, attempt 4

**Status:** supplemental rework only. NBF-01 remains **unaccepted**. Batch 2
is **prohibited** until a later Grok 4.6 Oracle gate returns `PASS_BATCH_1`.

This file does not mutate the frozen NBF tasklist, settled plan v8, North Star,
source base, custody, status, agent goal, or any prior brief, check-in,
finding, receipt, or rework packet. It is the smallest follow-on tasklist
after attempt 3 received `ACCEPTED_ISSUES`. Build on the existing dirty
candidate. Preserve every prior-MET primitive, every attempt-3 closure, and
the already-corrected custody document.

**Authority:** Grok 4.6 Oracle triage of the six accepted issues in
`.oracle/checkins/batch-1-rework3-grok.md`, grounded in Luna review
`.oracle/checkins/batch-1-rework3-luna.md` and independent re-read of the
current candidate symbols and tests. This turn is triage only. It does not
dispatch implementation or review.

**Identities (verified 2026-08-30):**

| Artifact | Identity |
| --- | --- |
| Repository | `/Users/peteromalley/Documents/Arnold-oracle-nbf` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Immutable source base / merge-base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Frozen tasklist SHA-256 | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Settled plan v8 SHA-256 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| North Star SHA-256 | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Custody SHA-256 | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Agent goal SHA-256 | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Tasklist-freeze receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |
| Attempt-1 rework tasklist | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-1 triage receipt | `7565016b618293fa666f61710f0f95bb8847d6d2336568ff064d8843699efa1e` |
| Attempt-2 rework tasklist | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-2 triage receipt | `3f1c460d06966d5eef2999e5e4b99e5324b2aa920609d10ffe2d54af81a41703` |
| Attempt-3 rework tasklist | `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779` |
| Attempt-3 triage receipt | `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b` |
| Attempt-3 executor finding | `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f` |
| Attempt-3 executor receipt | `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f` |
| Attempt-3 Luna review | `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd` |
| Attempt-3 Luna review receipt | `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425` |
| Attempt-3 Grok check-in | `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02` |
| Attempt-3 Grok Oracle receipt | `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30` |
| Attempt-3 owned tracked-production diff | `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8` |
| Unchanged `test_incident_ledger.py` | SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`; blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |
| Oracle verdict on attempt 3 | `ACCEPTED_ISSUES` |

The attempt-3 tracked-production diff digest is the **reviewed attempt-3
identity**, not a future target. Attempt-4 execution must measure and bind
its own post-fix tree. Do not rewrite attempt-3 artifacts when that digest
changes.

Focused `112 passed` and legacy `78 passed` are observations, never
acceptance targets. Preserve historical evidence as historical: start-gate
52→61, unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
attempt-2 `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
and attempt-3 `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`.

**Classification:** `[XHARD]: none`.

Every item is ordinary deterministic schema, journal, reducer, behavioral-test,
or receipt work already specified by settled-plan §§4.4–4.13, §4.16,
§§4.19–4.21 and frozen NBF-01. Breadth is not an exceptional threshold.
Plan §7 and the frozen tasklist already classified NBF-01 as Normal /
GPT-5.6 Luna. Attempts 1–3 did not reopen that call and this attempt
does not either.

**Executor model for RW4-01..RW4-06:** GPT-5.6 Luna (`codex:gpt-5.6-luna`).
Exploration, implementation, validation, and the later independent review
are Luna. Grok 4.6 is Oracle and the RW4-GATE decision only. This packet
does not dispatch either model.

**Not authorized by this tasklist:** commit, push, merge, rebase, reset,
clean, staging, plan mutation, frozen-tasklist mutation, Batch 2 dispatch,
main merge, box mutation, a second journal/projection/scheduler/policy
owner, another custody edit, rewriting historical receipts, implementation
by this Oracle, or any Batch 1 pass decision before RW4-GATE.

Build on the existing dirty candidate tree. Do not stash or overwrite
orchestrator-owned `.oracle` artifacts except the attempt-4 evidence files
this tasklist explicitly owns.

---

## Scope reminder (frozen NBF-01 ownership)

Own only the NBF-01 primitives already on this candidate: schemas,
`DispatchOutcome.kind=worker_disposition`, disposition-to-terminal mapping,
one existing-journal CAS, terminal writer, changed-precondition producers,
keyed provider-failure-key replay mechanics, probe leases, one composite
`provider_route_child_reserved`, post-commit receipt derivation,
reconciliation, two-scan confirmation, and the disposition helper/CLI.

**Prohibited files and behaviors (every task):**

- Do not edit admission callers, `dispatch_with_admission`, scheduler loops,
  T7 cooldown policy, T8 thresholds/degradation/hold/probe-policy/fallback
  selection/return-to-primary, physical doors, launch adapters, WBC
  construction, Python or shell signal-site wiring, `fallback_chains.py`
  policy, `workers/_impl.py`, `workers/omp.py`,
  `cloud/babysitter/launch.py`, `handlers/shared.py`, `auto.py`,
  `recovery_policy.py`, or any later-task file.
- Do not add a second journal, store, prepare/commit protocol, rotator,
  family lease, second projection authority, signature service, or
  speculative plugin/producer registry.
- Do not implement T8 policy from the §4.16 transition table's
  "Route-policy effect" column. Replay the streak/key mechanics only.
- Do not edit `.oracle/tasklist.md`, `.oracle/plan.md`,
  `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`,
  `.oracle/status.md`, or any historical Batch 1 / attempt-1 / attempt-2 /
  attempt-3 receipt, finding, check-in, brief, or rework packet.
- Do not rewrite history to make the mutated 52-vs-61 count, unreproducible
  `4aee815d...`, failed-handoff `50c86490...`, attempt-1 `e060f650...`,
  attempt-2 `16f6f854...`, or attempt-3 `8fe64464...` look consistent.
  Current 112/78 are observations, not waivers or targets.
- Do not request or perform another custody edit. `f8725af...` is already
  labeled historical; `798c506...` is current. RW-CUSTODY is MET.
- Do not signal from the CLI. One JSON acknowledgement on stdout;
  diagnostics on stderr only.
- Do not invent a generic unit-of-work / two-phase framework. Reuse the
  existing `_IncidentEventJournal` sequence-sidecar `fcntl.flock`,
  `_locked`, `_append_nbf_locked`, and `_emit_locked` pattern.
- Do not reopen C36, C37, or C38 reconciliation semantics.
- Do not reopen C01 via overweight `PhaseResult.from_dict` round-trip
  expansion.
- Do not expand C40 cache-mismatch or a broad cache/projection-version
  matrix.
- Do not restore the two broad-suite missing modules or otherwise repair
  the pre-existing environment blocker.
- Do not add a seventh implementation issue, cleanup program, speculative
  abstraction, or broader criterion expansion.

Owned source scope remains: five modified production files, new
`incident/disposition.py`, eight named new test modules.
`test_incident_ledger.py` remains unchanged versus `origin/main`.

---

## Explicit exclusions — no task, no silent widening

This packet contains **no task** for:

- C36, C37, or C38 reconciliation semantics (Grok marked them MET).
- C01 via overweight `PhaseResult.from_dict` round-trip expansion.
- C40 cache-mismatch or broad cache/projection-version matrix expansion.
- T8 thresholds, degradation policy, retry scheduling, or escalation policy.
- Restoring `arnold.agent.costing.model_resource_capabilities` /
  `tools.environments.singularity` or any other environment repair.
- Custody edits or re-adjudication.
- Historical receipt/check-in rewrite or evidence normalization.
- Admission callers, scheduler, physical doors, launch adapters,
  signal-site wiring, fallback policy, family leases, rotators, second
  journal/store, prepare/commit, main merge, or Batch 2.

Attempt-3 Grok classified the broad-suite missing modules as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`: context, not an NBF regression and
not a waiver. Attempt 4 must record the full sweep evidence in RW4-06 but
must not turn that environment issue into an implementation task. C01/C40
remain unevidenced context; this packet does not expand them.

Triage found **no concrete contradiction** between these exclusions and
Issues 1–6. If execution discovers one, stop and return to Oracle; do not
silently widen scope.

---

## Prior-MET behavior that must be preserved

Attempt 3 landed real progress. Do not regress it while closing the
remaining holes.

Preserve from earlier attempts, still MET:

- One `_IncidentEventJournal` + sequence-sidecar flock. NBF writes enter
  `_locked` / `_append_nbf_locked`.
- C03 `no_launch` cannot serialize with `launch_state=accepted`.
- C04 worker-disposition required accepted launch, disposition_id, receipt,
  fingerprint, phase/spec, logical/worker identity, start/finish.
- C05 worker disposition cannot carry provider-exhaustion or no-launch
  state. Carrying an applicable `provider_failure_key` identity on a
  terminal payload for keyed-stream targeting is not provider-exhaustion
  evidence and must not reintroduce `provider_evidence` on
  `worker_disposition`.
- C06 lossless map to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- C08 never coerced into ordinary failure.
- C12 `no_launch` produces no worker terminal/fingerprint/provider/streak.
- C15 TERM vs KILL ladder IDs remain distinct.
- C16 semantic fingerprint excludes volatile liveness and logical/family IDs.
- C17 route-liveness digest absent from fingerprint and provider-failure key.
- C18 / C25 two-OS-process same-fingerprint reservation contention yields
  one winner (`test_two_process_reservation_contention_one_winner`).
- C22 valid changed-precondition consumed at most once.
- C26 composite child is one record and contains no child receipt-ID input.
- C29 reducer order: provider/fingerprint reduction still runs before
  reservation `closed=True`.
- C30 / C31 for matching streams: matching accepted exhaustion increments
  that key; a first observation of a different key starts that stream at 1.
- C35 scheduling / no-launch / unresolved / time / liveness refresh do not
  mutate provider streak.
- C36–C38 reconciliation: only positive `released_no_launch`, recovered
  terminal, or durable ambiguous hold; recovered disposition links one
  existing record; blind/conflicting/accepted-launch-as-no-launch reject.
- CP04 / CP10: no second journal, store, prepare/commit, scheduler,
  rotator, or family lease.
- CP05: only accepted `provider_exhausted` terminals increment observations.
- CP09 type/state distinction among no-launch, unresolved, ordinary
  failure, provider exhaustion, and worker disposition.
- RW-CUSTODY: already MET. Do not edit `.oracle/custody.md`.
- Real two-process reservation contention remains a real `fcntl.flock` race.
- Historical evidence stays historical.

Preserve attempt-3 closures, still MET:

- Persisted accepted-launch markers: `append_terminal_outcome` requires one
  receipt-bound accepted `controlled_adapter_state`; replay does not set
  `accepted_launch=True` from the terminal (C10, A3-01).
- Positive OOM and legal unknown-death append paths (C14).
- Worker-disposition + `success_payload` source rejection at
  `DispatchOutcome.__post_init__` and `validate_nbf_event` (keep and
  promote into the named four-door matrix; do not delete the source door).
- Keyed reducer without `latest_stream_key` mutation fallback
  (`ledger.py` `_project_records`: missing key mutates no stream).
- Real composite fresh replay under
  `test_fresh_replay_receipt_is_byte_identical` (C27).
- Real `_emit_locked` composite failure injection under
  `test_torn_composite_write_exposes_neither_transition_nor_receipt`.
- Complete CLI 0/2/3/4/5 including expired and already-consumed matching
  replay (C41). Rerun for regression; do not redesign.
- Expiry-after-consume rejection (`test_expire_confirmation_after_consume_rejects`).
- Route-child wrapper deletion: `hasattr(IncidentLedger,
  "reserve_provider_route_child_with_receipt")` is false (RW3-05, A3-09).
- One journal, one lock door.

Keep those named tests and behaviors. Strengthen thin same-name tests in
place; do not delete them to invent a new count. Test-count growth is not
proof. New or strengthened tests must be behavioral, deterministic, and
must fail on the unmodified attempt-3 candidate for the hole they close.

---

## Independent confirmation of the six accepted issues

Oracle re-read the cited symbols on the current dirty tree. They still
behave as the attempt-3 verdict described. No seventh issue is authorized.

1. **Issue 1 / C19–C21, RW3-01, A3-03 — blocker.**
   `_authoritative_source` (`schema.py:562-576`) copies a caller dict after
   checking `authority_kind`, `subject`, and `content`. The seven
   `produce_*` wrappers (`schema.py:771-797`) still accept those dicts via
   `_produce_reason_specific` / `_produce_authoritative`.
   `ChangedPrecondition.__post_init__` (`:489-535`) and `from_dict`
   (`:541-544`) treat snapshot self-hash as authority.
   `append_changed_precondition` (`ledger.py:774-794`) requires a persisted
   cited event whose digest matches the snapshot; it does not re-derive
   from a typed source handle.
   `consume_changed_precondition` (`:1011-1021`) accepts any object that
   equals the persisted dict.
   Required `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`
   (`test_changed_precondition_producers.py:38-48`) mutates
   `provider_failure_key_after` without rebuilding `after_snapshot`, so it
   rejects for snapshot/key mismatch. Attempt-3 Oracle independently rebuilt
   snapshots, content IDs, evidence digest, and `event_id`: `from_dict`,
   append, and consume all accepted
   (`/tmp/oracle-nbf01-rework3-grok/independent_probes.json`, stdout
   SHA-256 `0979b341b6f9e933210bed6e992f7dc946a3a09541951388a5f20c4bc343be83`).
2. **Issue 2 / C02, C13, RW3-01, A3-02 — blocker.**
   `DispatchOutcome.__post_init__` (`phase_result.py:187-193`) now rejects
   `worker_disposition` + `success_payload`. `validate_nbf_event`
   (`schema.py:953-954`) also rejects that pairing on
   `worker_terminal_outcome`. Required
   `test_dispatch_outcome_incompatible_payload_matrix`
   (`test_worker_disposition.py:39-52`) is still constructor-only and omits
   that pairing. `test_worker_disposition_rejects_success_payload_at_append`
   hits `_append_nbf` only. `validate_nbf_event` still first-accepts
   `worker_identity` as `(str, dict)` (`schema.py:945-946`). Named identity
   test (`test_observed_and_non_worker_reject_missing_schema_version_and_identity`)
   is selected omissions/version cases, not the complete four-door matrix.
   Legal positives exist for OOM and unknown death; they must remain.
3. **Issue 3 / C11, C32, C33, C34, CP06, CP07, RW3-02, A3-04, A3-05 — major.**
   `_project_records` (`ledger.py:547-567`) mutates only a supplied
   `provider_failure_key` and no longer falls back to `latest_stream_key`.
   Required `test_success_resets_only_applicable_key` (`:93-106`) still
   does A, A, B then success for latest B.
   `test_disposition_breaks_consecutiveness_without_degradation` (`:163-174`)
   still targets one stream. Required names
   `test_success_for_non_latest_key_does_not_reset_latest`,
   `test_ordinary_failure_breaks_only_applicable_stream`,
   `test_applicable_key_survives_restart_and_replay`,
   `test_cross_key_isolation_after_success_and_disposition`,
   `test_recovery_requires_passed_canonical_probe`, and
   `test_failed_absent_mismatched_replayed_consumed_recovery_rejects`
   are absent. `append_probe_result` (`ledger.py:1004-1010`) still writes a
   caller-shaped lease/key/evidence tuple without requiring an existing
   unexpired matching `provider_probe_started` lease.
4. **Issue 4 / C09, C28, CP08, CP11, RW3-03, A3-06 — major.**
   Required `test_two_process_terminal_linkage_is_atomic`
   (`test_incident_ledger_transactions.py:100-121`) still races the same
   outcome/ID; both children return `ok`. Distinct-ID conflicting-kind
   coverage lives only under
   `test_distinct_terminal_ids_conflicting_kinds_have_one_winner` (`:132-149`).
   `test_torn_composite_write_exposes_neither_transition_nor_receipt`
   (`:38-60`) injects `_emit_locked` and proves pre-append failure. There
   is no distinct injected failure after durable `_emit_locked` fsync
   (`ledger.py:267-271`) but before receipt return/`derive_receipt`.
   Composite fresh replay (`test_fresh_replay_receipt_is_byte_identical`)
   is already real and must be retained.
5. **Issue 5 / C39, RW3-04, A3-07 — major.**
   Frozen confirmation schema (`schema.py:800-819`) requires PID,
   process-start identity, progress sequence, incarnation, cause,
   `scan_interval_s`, `expires_at`, `evidence_digest`, and
   `confirmation_policy_identity`. `consume_confirmation`
   (`ledger.py:963-987`) compares the five identity fields plus evidence
   digest and persisted scan/expiry. Required
   `test_confirmation_compares_pid_start_progress_incarnation_cause`
   (`test_supervision_confirmation.py:31-42`) mutates and omits only those
   five identity fields. It does not cover evidence-digest, TTL/`expires_at`,
   `scan_interval_s`, or policy/version identity mismatch or omission.
   Restart, replacement, expiration, reopen, expiry-after-consume, and
   locked one-consumer race tests exist and must stay. C41 CLI 0/2/3/4/5
   is independently complete; rerun, do not redesign.
6. **Issue 6 / RW3-06, A3-08 — major.**
   Attempt-3 executor finding/receipt bind HEAD, source, and the production
   diff, but omit the required `git hash-object` / SHA-256 inventory for
   `incident/disposition.py` plus all eight new NBF test modules, and they
   abbreviate the broad sweep. Independent review transcripts cannot repair
   those immutable artifacts. Attempt 4 must write **new** paths, never
   edit attempt-3 evidence.

---

## Six-issue to task mapping

| Issue | Severity | Criteria | Task | Merge rationale |
| --- | --- | --- | --- | --- |
| 1 changed-precondition authority remains forgeable | blocker | C19–C21, C22 preserve, RW3-01, A3-03 | **RW4-01** | First serial task. Producer derivation is schema-side; append/consume is the same lock. No split: one writer until coherent forgery is closed. |
| 2 strict payload and typed-identity proof incomplete | blocker | C02, C13, RW3-01, A3-02 | **RW4-02** | Named four-door matrix on the already-closed source doors. Waits so Issue 1 owns `schema.py`/`ledger.py` first. |
| 3 applicable-key and recovery named proof missing | major | C11, C32, C33, C34, CP06, CP07, RW3-02, A3-04, A3-05 | **RW4-03** | Keyed reducer plus probe-lease binding. Uses Issue-1 authoritative recovery events. |
| 4 composite and terminal-race evidence incomplete | major | C09, C28, CP08, CP11, RW3-03, A3-06 | **RW4-04** | Validates completed composite/terminal doors. Tests plus smallest post-append injection only. |
| 5 durable confirmation equality matrix incomplete | major | C39, C41 regression, RW3-04, A3-07 | **RW4-05** | Contract G identity matrix. Serial on `ledger.py` after RW4-04. CLI already complete. |
| 6 immutable executor evidence protocol incomplete | major | RW3-06, A3-08 | **RW4-06** | Last. New attempt-4 executor finding/receipt only. |
| Fresh execution + independent Luna review + Grok Oracle | gate | Batch 1 gate | **RW4-GATE** | Not implementation. |

Do not silently merge or omit Issues 1–6. Do not give two tasks concurrent
ownership of the same file. `ledger.py` has one writer at a time, in the
order below. Issue 1 is not reordered behind evidence-only work.

**Luna serial order:** RW4-01 → RW4-02 → RW4-03 → RW4-04 → RW4-05 → RW4-06.
RW4-GATE is last and is not implementation.

Adjacent tasks are not combined: combining would obscure the Issue 1–6
mapping. File-ownership inspection does not require splitting RW4-01.

---

## Shared validation commands

Exact frozen focused command (settled plan §6 / NBF-01 / frozen tasklist):

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

Legacy regressions (do not treat as NBF-01 acceptance by themselves):

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

Compile and whitespace:

```bash
python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

CLI (Contract G / settled-plan §4.21), invoked as a real subprocess, never
as a pytest name standing in for the transcript:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Exact statuses: `0` append succeeded; `2` malformed JSON or schema
violation; `3` ledger append/locking failure; `4` invalid or unavailable
ledger/context location; `5` missing, expired, mismatched, or
already-consumed confirmation.

Prefer `multiprocessing`/`subprocess` against one on-disk ledger (real
`fcntl.flock`) over in-process threading. Use injectable clocks for
TTL/separation. Do not inflate test count with duplicate happy-path stubs.
Do not modify `tests/arnold_pipelines/megaplan/test_incident_ledger.py`
unless a frozen must-criterion cannot live in the eight new modules.

Empty stdout/stderr SHA-256, when truly empty, is the full 64-hex
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Never truncate it.

Tests must be behavioral and deterministic, not pass-count inflation.

---

## RW4-01 — Authoritative producer / coherent-forgery closure

- **ID:** RW4-01
- **Issue closed:** Issue 1
- **Criteria:** C19, C20, C21; preserve C22
- **Prior IDs:** RW3-01 (producer half), A3-03
- **Severity:** blocker
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Deterministic schema/journal compare already specified
  by settled-plan §4.6 and frozen C19–C21. Typed source handles and
  lock-door re-derivation are not a new concurrency protocol, signature
  service, or schema language.
- **Executor:** GPT-5.6 Luna
- **Depends on:** none
- **Overlapping-file lock:** sole writer of `schema.py` producer/handle
  symbols and of `ledger.py` `append_changed_precondition` /
  `consume_changed_precondition` until this task finishes. No later task
  may proceed until the coherent forgery is behaviorally closed.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`ChangedPrecondition`, `_authoritative_source`, `_produce_authoritative`,
    `_produce_reason_specific`, `produce_changed_precondition`, the seven
    allowlisted `produce_*` reason-specific producers, `from_dict` /
    `__post_init__`, `validate_nbf_event` changed-precondition branch).
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`IncidentLedger.append_changed_precondition`,
    `consume_changed_precondition`; existing `_locked` /
    `_append_nbf_locked` only).
- Tests:
  - `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
  - Smallest consume/one-use cases already living in
    `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
    (`test_consumed_change_cannot_authorize_second_reservation`) may be
    strengthened in place. Do not retarget torn-composite or terminal-race
    names.

### Prohibited

- Do not add a second authority store, generic producer escape hatch,
  signature service, or speculative plugin/registry system.
- Do not restore `ChangedPrecondition.produce` or
  `produce_changed_precondition` as minting paths; they already raise and
  must keep raising.
- Do not treat a dataclass whose only fields are `authority_kind`,
  `subject`, and `content` as a typed handle. That is still a
  caller-shaped snapshot.
- Do not rely only on content-address equality an attacker can recompute
  from snapshots they also supply.
- Do not change keyed-streak reducer selection (RW4-03), payload matrix
  (RW4-02), composite crash (RW4-04), or confirmation (RW4-05).
- Do not add prepare/commit records or a UnitOfWork.
- Do not reopen C36–C38.

### Work

Replace `_authoritative_source` (`schema.py:562-576`) and the caller-dict
adapter behind `_produce_authoritative`. Public minting is only the seven
allowlisted reason-specific producers from settled-plan §4.6:

```text
source_revision_changed          -> reads authoritative repository/source receipt
runtime_generation_changed       -> reads authoritative runtime registry/manifest
seed_or_interpreter_binding_changed -> reads seed and interpreter attestations
timeout_policy_changed           -> reads canonical timeout-policy configuration
authorized_route_changed         -> binds jointly admitted composite route event
provider_recovery_verified       -> binds a successful canonical bounded probe result
verified_repair_committed        -> binds repository commit identity and verified digest
```

Each producer has a fixed `producer_kind` and `producer_version`. Each
reason has the smallest typed authoritative source handle **and** a closed
reader for that reason. The handle carries the reason-specific source
identity the reader actually reads (revision, runtime generation,
seed/interpreter binding, timeout-policy identity, jointly admitted route
event, passed probe-result identity, verified repair commit), plus
`source_version` and subject. Fixture objects may be passed **as the
source to read**, not as pre-digested IDs or `{authority_kind, subject,
content}` blobs.

The reader, not the caller, binds:

```text
producer identity (kind + version, fixed by reason)
reason
authoritative subject
source version
persisted cited evidence event
evidence digest
canonical before/after content
before_content_id / after_content_id (must differ)
provider-failure-key before/after derivation
```

`provider_recovery_verified` keeps before-key == after-key. Callers must
not supply `producer_kind`, `producer_version`, subject, evidence digest,
before/after content IDs, or provider-failure-key transitions as trusted
inputs.

Validate at **three doors**, not snapshot self-hash alone:

1. `ChangedPrecondition.from_dict` / decode. Reconstruct the typed handle
   and re-run the reason-specific reader. Caller-shaped
   `{authority_kind, subject, content}` snapshots reject. A dict that
   mutates a valid event and recomputes every serializable hash/ID
   (`after_snapshot`, `after_content_id`, `evidence_digest`,
   `provider_failure_key_after`, `event_id`, and any other content-addressed
   field) still rejects.
2. `append_changed_precondition` under `_locked`. Require the cited
   evidence event to be persisted. Re-derive producer/reason/subject/
   source-version/content IDs/provider keys/evidence digest from that
   persisted evidence plus the typed handle. Do not accept a well-formed
   caller snapshot whose hashes merely agree with themselves.
3. `consume_changed_precondition` under the same lock. Re-validate the
   same bindings. Unpersisted or non-authoritative objects reject. A valid
   persisted producer event consumes exactly once (preserve C22).

Keep KISS: extend compare inside `_append_nbf_locked`; do not wrap the
ledger in a new transaction API.

### Acceptance criteria

- Only the matching reason-specific source reader can mint a valid event.
- Generic `ChangedPrecondition.produce` and `produce_changed_precondition`
  still raise.
- Caller-shaped snapshots, independently supplied producer identity,
  independently supplied content IDs, and independently supplied
  provider-key transitions reject.
- A coherent forged transition that recomputes every serializable hash/ID
  rejects at `from_dict`, `append_changed_precondition`, **and**
  `consume_changed_precondition`.
- A valid event minted through the matching reader appends and is consumed
  exactly once under the existing journal lock; a second consume rejects.
- C22 remains: `test_consumed_change_cannot_authorize_second_reservation`
  still holds.
- One journal, one lock door, no second authority store.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "precondition or consumed_change or forged or producer or authoritative"
```

Present — keep and retarget:

- `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`
  (rebuild **every** serializable hash/ID, including `after_snapshot`,
  content IDs, evidence digest, provider keys, and `event_id`; prove
  rejection at `from_dict`, append, and consume)
- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject`
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
  (digests match the **reader** output from typed source objects, not a
  caller content blob)
- `test_producer_derives_unequal_ids_and_recovery_preserves_key`
- `test_free_form_reason_and_reuse_are_rejected`
- `test_consumed_change_cannot_authorize_second_reservation`

Missing — add if the retargeted coherent-forgery name cannot also prove
the valid path without becoming two unrelated assertions:

- `test_valid_reason_specific_source_reader_mints_and_consumes_once`

These names must fail on the unmodified attempt-3 candidate for the
coherent-forgery hole.

---

## RW4-02 — C02/C13 named four-door matrix

- **ID:** RW4-02
- **Issue closed:** Issue 2
- **Criteria:** C02, C13
- **Prior IDs:** RW3-01 (matrix half), A3-02
- **Severity:** blocker
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Completing an already-specified constructor / decode /
  `validate_nbf_event` / append rejection matrix is ordinary schema proof.
  Not a new type system and not C01 transport expansion.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW4-01
- **Overlapping-file lock:** sole writer of `phase_result.py`
  `DispatchOutcome` doors, `schema.py` worker/observed-death/non-worker
  / `validate_nbf_event` payload-identity branches, and the locked append
  validation used by those records, after RW4-01.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/orchestration/phase_result.py`
    (`DispatchOutcome.__post_init__`, `DispatchOutcome.from_dict`, the
    six-kind decode path).
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`WorkerDisposition`, `ObservedProcessDeath`,
    `NonWorkerSignalDisposition`, `_typed_worker_identity`,
    `validate_nbf_event` including the `worker_terminal_outcome` branch).
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`append_disposition`, `append_terminal_outcome`, `_append_nbf_locked`
    validation door only).
- Tests:
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
    (matrix, identity, legal positives; do not rewrite CLI tests)
  - `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`

### Prohibited

- Do not reopen C01 by forcing overweight records through
  `PhaseResult.from_dict`. Keep
  `test_scheduling_condition_is_lossless_through_phase_result` as the
  existing scheduling proof; do not expand it into a six-kind PhaseResult
  transport program.
- Do not reopen C14 OOM/unknown-death source doors; they are MET. Keep
  legal positive OOM and legal unknown-death append paths.
- Do not reopen C19–C21 producers (RW4-01).
- Do not add a ninth test module.
- Do not treat `_append_nbf` of a hand-built dict as a substitute for
  public `append_terminal_outcome` / `append_disposition` coverage in the
  named matrix.

### Work

Strengthen existing named tests in place across **four doors**:

```text
direct construction
from_dict
validate_nbf_event
real locked append (append_terminal_outcome / append_disposition / _append_nbf_locked)
```

Legal kind/state map (unchanged):

```text
no_launch                 -> not_started
success                   -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted        -> accepted
worker_disposition        -> accepted
unresolved_launch         -> ambiguous
```

Incompatible payload families to reject for every illegal pairing:

```text
success_payload
terminal_failure
provider_evidence
disposition_id
worker/timing/receipt/fingerprint context on no_launch and unresolved_launch
```

Specifically include the repaired `worker_disposition` + `success_payload`
rejection in the named matrix at all four doors. Preserve C05: still
reject provider-exhaustion and no-launch state on worker disposition.
Preserve the existing source constructor door; add decode, validation,
and public append.

Typed identity at those same doors:

- Worker semantic fingerprint is a canonical 64-hex SHA-256.
- Worker identity is the typed `host` / `pid` / `boot_id` structure.
  Close the `validate_nbf_event` `worker_terminal_outcome` `(str, dict)`
  first-accept (`schema.py:945-946`). A bare string or arbitrary mapping
  is not a worker identity.
- Observed-death subject/cause remain `worker|external_process` with
  `observed_dead_unknown` or `cgroup_oom` only. Missing or fabricated
  subject, cause, killer, or victim identity reject.
- Non-worker subject is `non_worker_lifecycle`; worker-specific causes
  reject. Missing/fabricated lifecycle identity reject.
- Required/missing/fabricated identity fields reject at decode and append.
- Legal positive cases remain: legal `worker_disposition`, legal
  observed-death unknown, legal non-worker lifecycle shutdown, legal
  success/ordinary/provider terminals with matching payloads.

### Acceptance criteria

- Named six-kind incompatibility matrix rejects every illegal payload
  family at constructor, `from_dict`, `validate_nbf_event`, and real
  append, including `worker_disposition` + `success_payload`.
- Missing and fabricated worker, observed-death, and non-worker identity
  fields reject at those doors.
- Legal positive cases still append.
- C08 coercion rejection still holds with typed worker identity.
- `PhaseResult.from_dict` is not used as a C01 expansion vehicle.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
```

Present — keep and strengthen:

- `test_dispatch_outcome_incompatible_payload_matrix`
  (full six-kind matrix at all four doors, including
  worker-disposition + `success_payload`)
- `test_worker_disposition_rejects_success_payload_at_append`
  (keep; not a substitute for putting that pairing in the named matrix)
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
  (complete missing/fabricated identity at decode and append, not only
  schema_version / empty lifecycle)
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_outcome_never_coerces_disposition_to_failure`
- `test_worker_disposition_round_trip_and_distinct_outcome`
- `test_legal_positive_oom_appends`
- `test_legal_unknown_death_remains_unknown_after_append`
- `test_scheduling_condition_is_lossless_through_phase_result`

The named matrix must fail on the unmodified attempt-3 candidate for the
constructor-only / omitted-pairing hole.

---

## RW4-03 — Keyed/recovery named proof and probe-lease binding

- **ID:** RW4-03
- **Issue closed:** Issue 3
- **Criteria:** C11, C32, C33, C34, CP06, CP07
- **Prior IDs:** RW3-02, A3-04, A3-05
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Named numeric streak assertions and binding
  `append_probe_result` to an existing unexpired lease are ordinary
  reducer/journal checks already specified by Contract F / §4.16.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW4-01, RW4-02
- **Overlapping-file lock:** sole writer of `ledger.py` keyed reducer,
  probe lease/result, `provider_recovery_verified` consume, and
  `reserve_provider_route_child` after RW4-02.

### Owned files and symbols

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  (`IncidentLedger._project_records` keyed replay, `append_probe_result`,
  `create_probe_lease`, `reserve_provider_route_child`, consumption of
  producer-derived `provider_recovery_verified` inside the one composite
  append). Schema producer for `produce_provider_recovery_verified` was
  closed in RW4-01; this task consumes that authoritative event.
- Tests: `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
  (except post-append crash injection, which RW4-04 owns). Leave
  `test_fresh_replay_receipt_is_byte_identical` as the real composite
  replay already landed.

### Prohibited

- No T8 thresholds, `provider_degraded` scheduling, scalar hold/probe
  policy, fallback selection, return-to-primary, or
  `fallback_chains.py` edits.
- Do not let probes, waits, recovery events, dispositions, or ordinary
  failures increment exhaustion streaks.
- Do not restore `latest_stream_key` as a mutation fallback.
- Do not add a second child-receipt argument or a second journal.
- Do not reopen C19–C21 handles. Recovery events used here must come from
  the RW4-01 reader.

### Work

**A. Applicable non-latest keyed streams (C11/C32/C33)**

Existing required names must target a **non-latest** stream, not the
latest stream by construction, and assert numeric streaks for every
affected **and** unaffected key.

- Accepted success resets only its applicable non-latest key and leaves
  later keys unchanged.
- Accepted ordinary failure or `worker_disposition` breaks only its
  applicable non-latest key (`broken=True`, streak 0) without
  degradation.
- Missing applicable key mutates no stream.
- Restart/replay preserves the same selection and cross-key isolation.

Preserve C30/C31 matching-stream increment and first observation of a
new key at 1. Preserve C35. Preserve C05: do not smuggle keys through
`provider_evidence` on success/ordinary/disposition.

**B. Canonical probe / recovery binding (C23/C34, CP06)**

Bind any accepted canonical probe result to an existing unexpired
matching probe lease (`provider_probe_started`) with the same provider
key and parent/phase/route context. `append_probe_result` must reject
absent, expired, mismatched, replayed, and already-consumed leases.

`reserve_provider_route_child` remains one composite child append.
Valid recovery consumes once in that append and preserves the applicable
keyed streak. Prove passed, failed, absent, expired, mismatched,
replayed, and already-consumed probe/recovery paths.

### Acceptance criteria

- Required names target a non-latest stream and assert numeric streaks
  for every affected and unaffected key.
- Success for non-latest A after B is latest resets A only; B unchanged.
- Ordinary failure / disposition for a non-latest key breaks only that
  stream and does not create degradation.
- Cross-key isolation holds after restart/replay.
- Accepted probe results require an existing unexpired matching lease.
- Matching recovery + passed probe around a live streak leave that streak
  unchanged and allow exactly one matching child.
- Failed, missing, expired, mismatched, replayed, and already-consumed
  probe/recovery evidence reject.
- A second child without a new unused recovery event rejects.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

Present — keep and retarget:

- `test_success_resets_only_applicable_key`
  (must target the **non-latest** stream; current A,A,B-then-success-B
  body is latest-stream coverage and does not close Issue 3)
- `test_disposition_breaks_consecutiveness_without_degradation`
  (non-latest target plus explicit no-degradation and unaffected-key
  numeric assertions)
- `test_provider_streak_is_keyed_not_global` (assert values, not dict length)
- `test_nonmatching_key_rekeys_at_one`
- `test_recovery_authorization_single_use_across_different_children`
  (start from a live keyed streak, a lease-bound passed canonical probe,
  and a producer-derived recovery)
- `test_key_changing_precondition_rekeys_key_unchanged_does_not`
  (numeric unchanged-streak assertion; keys from RW4-01 readers)

Missing — add:

- `test_success_for_non_latest_key_does_not_reset_latest`
- `test_ordinary_failure_breaks_only_applicable_stream`
- `test_applicable_key_survives_restart_and_replay`
- `test_cross_key_isolation_after_success_and_disposition`
- `test_recovery_requires_passed_canonical_probe`
- `test_failed_absent_mismatched_replayed_consumed_recovery_rejects`
- `test_probe_result_requires_unexpired_matching_lease`

Leave `test_fresh_replay_receipt_is_byte_identical` in place for RW4-04
to keep as composite replay proof.

---

## RW4-04 — Terminal race and post-append composite crash/reopen proof

- **ID:** RW4-04
- **Issue closed:** Issue 4
- **Criteria:** C09, C28, CP08, CP11
- **Prior IDs:** RW3-03, A3-06
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Named behavioral proof of the already-specified
  `_emit_locked` composite append and one-terminal linkage. No new
  transaction protocol.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW4-01, RW4-02, RW4-03
- **Overlapping-file lock:** sole writer of `ledger.py` `_emit_locked` /
  composite receipt-return boundary and of the required terminal-race /
  crash tests after RW4-03.

### Owned files and symbols

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  (`_emit_locked`, `reserve_provider_route_child` receipt derivation,
  `append_terminal_outcome` linkage, `_append_nbf_locked`). Add only the
  smallest test-visible injection seam on the existing `_emit_locked` /
  post-append receipt boundary if monkeypatching the method is
  insufficient. Do not add a second journal or prepare/commit protocol.
- Tests:
  - `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
    (`test_two_process_terminal_linkage_is_atomic`,
    `test_torn_composite_write_exposes_neither_transition_nor_receipt`,
    and the new post-append crash/reopen name)
  - `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
    (`test_fresh_replay_receipt_is_byte_identical` retained as real
    composite replay)

### Prohibited

- No second journal, store, or prepare/commit protocol.
- Do not treat same-ID idempotency under the required terminal-race name
  as C09.
- Do not remove the real `_emit_locked` pre-append composite failure test.
- Do not reopen producer or reducer work.

### Work

1. Put the distinct-terminal-ID, conflicting-kind race from two real OS
   processes under the exact frozen required name
   `test_two_process_terminal_linkage_is_atomic`. Exactly one linkage
   wins. Replay of the winner remains valid; the loser is a conflict
   reject, never a second kind. Fresh replay of the committed terminal
   remains valid. Preserve same-ID idempotency as a separate case (the
   current body may move under a non-required extra name); it is not
   this race.
2. Retain `test_torn_composite_write_exposes_neither_transition_nor_receipt`
   as the real `_emit_locked` composite failure (pre-append: neither
   transition nor receipt).
3. Add a **distinct** injected failure after durable append (`_emit_locked`
   has written and `fsync`'d the line) but before receipt
   return/`derive_receipt`. Reopen with a fresh `IncidentLedger` and prove
   the committed composite projects exactly once with a byte-identical
   deterministic receipt.
4. A pre-append failure still exposes neither transition nor receipt.

### Acceptance criteria

- Required terminal-race name uses two real OS processes, distinct
  terminal IDs, and conflicting kinds; exactly one linkage wins; winner
  replay remains valid.
- Pre-append `_emit_locked` failure exposes neither child transition nor
  receipt after reopen.
- Post-append pre-receipt failure leaves a committed composite that a
  fresh ledger projects exactly once with a byte-identical deterministic
  receipt.
- Required fresh-replay name remains a real composite and is
  byte-identical after reopen.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention"

pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt"
```

Required names:

- `test_two_process_terminal_linkage_is_atomic` (distinct IDs, conflicting
  kinds, two OS processes, exactly one winner, valid fresh replay)
- `test_torn_composite_write_exposes_neither_transition_nor_receipt`
  (retain real `reserve_provider_route_child` + `_emit_locked` injection)
- `test_post_append_receipt_boundary_failure_reopens_with_byte_identical_receipt`
  (new; distinct from the `_emit_locked` test)
- `test_fresh_replay_receipt_is_byte_identical` (composite, reopen,
  byte-identical; already MET, keep)

The retargeted terminal-race name and the new post-append name must fail
on the unmodified attempt-3 candidate.

---

## RW4-05 — Confirmation equality matrix

- **ID:** RW4-05
- **Issue closed:** Issue 5
- **Criteria:** C39; C41 regression only
- **Prior IDs:** RW3-04, A3-07
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Completing the frozen confirmation identity/TTL
  equality matrix is ordinary schema/ledger compare. CLI 0/2/3/4/5 is
  already independently complete.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW4-01 (serial on `ledger.py` after RW4-04)
- **Overlapping-file lock:** sole writer of confirmation methods in
  `ledger.py` / `schema.py` after RW4-04. Do not rewrite `disposition.py`
  CLI behavior.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`observe_confirmation`, `consume_confirmation`,
    `expire_confirmation`, replacement/replay in `_project_records`)
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`SupervisionConfirmation` codecs/compare only if a frozen field is
    not yet required at consume)
- Tests:
  - `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
  - CLI branches in
    `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
    are **regression only**. Do not redesign them. Do not add a ninth
    module.

### Prohibited

- No wrapper-local confirmation files or second store.
- No signalling from the CLI.
- No free-form caller TTL; keep
  `confirmation_ttl_s = min(max(2 * scan_interval_s, 30.0), 300.0)`.
- Do not implement keyed replay or producers here.
- Do not redesign C41. Rerun the existing named CLI subprocesses.

### Work

Require, persist, and compare every frozen identity, timing, and evidence
field, including:

```text
victim_pid
victim_process_start_identity
relevant_progress_identity
supervisor_incarnation_identity
cause_kind
evidence digest
TTL / expires_at
scan_interval_s / scan separation
confirmation_policy_identity / schema_version where the frozen schema requires it
```

Strengthen `test_confirmation_compares_pid_start_progress_incarnation_cause`
with each single-field mismatch **and** omission for that full set, not
only the five identity fields.

Preserve restart, replacement, expiration, reopen, expiry-after-consume
rejection, and locked one-consumer race behavior.

### Acceptance criteria

- Each frozen identity/timing/evidence field mismatch and each omission
  rejects consume.
- Replacement and expiry remain durable; restart preserves original expiry.
- Expiry after consumption rejects; consumed state survives replay.
- Two processes racing consume still yield one consumer.
- CLI 0/2/3/4/5 subprocesses still pass, including expired 5 and distinct
  already-consumed matching replay.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

Present — keep and strengthen:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
  (every frozen field mismatch and every omission, including evidence
  digest, TTL/`expires_at`, `scan_interval_s`, and policy/version
  identity)
- `test_confirmation_ttl_and_single_consumption`
- `test_second_scan_too_early_and_expired_rejected`
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_expire_confirmation_after_consume_rejects`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_3_append_or_lock_failure`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`
- `test_cli_status_5_expired_confirmation`
- `test_cli_status_5_distinct_already_consumed_replay`

Drive CLI via subprocess. Do not skip 3/4/5. Do not treat pytest names as
the independent CLI evidence in RW4-06.

---

## RW4-06 — Stable-tree immutable executor evidence

- **ID:** RW4-06
- **Issue closed:** Issue 6
- **Criteria:** RW3-06 / A3-08 protocol, applied to attempt 4
- **Severity:** major
- **Classification:** Normal / GPT-5.6 Luna
- **`[XHARD]`: none.** Recording reproducible command transcripts bound
  to the post-fix tree is ordinary validation/evidence work. Independent
  review evidence does not retroactively repair an executor artifact.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW4-01, RW4-02, RW4-03, RW4-04, RW4-05
- **Overlapping-file lock:** none on production. Writes only new
  attempt-4 evidence paths.

### Owned files

New only:

- `.oracle/findings/execution-nbf01-rework4-luna.md`
- `.oracle/receipts/execution-nbf01-rework4-luna.md`

Do **not** rewrite any attempt-1, attempt-2, or attempt-3 finding,
receipt, check-in, or brief.

### Prohibited

- Do not fabricate a 52-test past or force any target count. 112/78 are
  observations, not targets.
- Do not "fix" historical `4aee815d...`, `50c86490...`, `e060f650...`,
  `16f6f854...`, or `8fe64464...` by editing old receipts.
- Do not claim binary-diff mode unless the transcript shows the exact
  flags and the digest reproduces on a second run.
- Do not cite CLI pytest names as the independent CLI evidence.
- Do not restore the two missing broad-suite modules. Record the full
  sweep verbatim, including the pre-existing collection blocker.
- Do not summarize the megaplan-directory sweep.

### Work

After the candidate is stable, capture a **new** immutable executor
finding and receipt bound to the exact post-fix HEAD and tree. They must
include:

1. Bind exact HEAD, branch, source/merge-base, frozen tasklist SHA-256,
   North Star SHA-256, this attempt-4 packet SHA-256, this triage receipt
   SHA-256, and the final owned tracked-production diff.
2. Inventory **every** modified tracked file and **every** untracked owned
   production/test file with both `git hash-object` and full SHA-256.
   Explicitly include:

```text
arnold_pipelines/megaplan/incident/__init__.py
arnold_pipelines/megaplan/incident/ledger.py
arnold_pipelines/megaplan/incident/schema.py
arnold_pipelines/megaplan/incident/disposition.py
arnold_pipelines/megaplan/orchestration/phase_result.py
arnold_pipelines/megaplan/orchestration/phase_result_classify.py
tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
tests/arnold_pipelines/megaplan/test_provider_route_projection.py
tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
tests/arnold_pipelines/megaplan/test_scheduling_conditions.py
tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

3. Production diff digest from:

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

4. For **every** validation command: exact argv, cwd, exit status,
   verbatim complete stdout and stderr or an immutable isolated
   transcript path, and full 64-hex SHA-256 for **both** stdout and
   stderr. Empty output uses the full empty digest above; never truncate.
5. Record the full `pytest -q tests/arnold_pipelines/megaplan` sweep
   output **verbatim**, including any pre-existing missing-module
   collection blocker. Do not summarize it. Do not repair those modules
   under this packet.
6. Independently invoke and bind CLI subprocesses for statuses 0, 2
   (malformed and schema-invalid), 3, 4, and 5 (missing, expired, and
   distinct already-consumed matching replay).

Preserve in the new finding, as historical:

- start-gate 52→61 mutation;
- unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`;
- failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`;
- attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`;
- attempt-2 reviewed production digest
  `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`;
- attempt-3 reviewed production digest
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
  as the attempt-3 identity, not the attempt-4 target.

### Acceptance criteria

- New finding and receipt exist at the attempt-4 paths and are not edits
  of attempt-3 artifacts.
- HEAD, branch, source/merge-base, frozen tasklist, North Star, packet,
  triage receipt, and final production diff are explicit.
- Every owned production and test file above has both `git hash-object`
  and SHA-256, including `disposition.py` and all eight new NBF modules.
- Every required command has argv, cwd, exit, stdout, stderr, and full
  stdout/stderr SHA-256.
- Broad megaplan sweep is recorded verbatim.
- CLI 0/2/3/4/5 are independent subprocess transcripts.
- Historical evidence remains labeled historical.

### Exact commands (full gate suite)

Run and transcript all of:

1. Frozen focused suite (eight new NBF modules plus unchanged
   `test_incident_ledger.py`) — shared command above.
2. Frozen legacy incident projection/summary/bridge and phase-result
   classification suite — shared command above.
3. Coherent changed-precondition forgery and valid source-reader /
   one-consume tests:

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "precondition or consumed_change or forged or producer or authoritative"
```

4. Four-door payload/identity matrix tests:

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
```

5. Non-latest keyed provider and canonical probe/recovery matrix:

```bash
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

6. Real two-process distinct-terminal race and pre/post-append composite
   crash/reopen/receipt tests:

```bash
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention or post_append or receipt"

pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt"
```

7. Full confirmation equality, restart, TTL, replacement, expiry, and
   consumer contention tests:

```bash
pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
```

8. Direct CLI 0/2/3/4/5 regression subprocesses of
   `python -m arnold_pipelines.megaplan.incident.disposition record`.
9. Full `pytest -q tests/arnold_pipelines/megaplan` with complete output
   recorded even when the known pre-existing environment blocker recurs.
10. `python -m py_compile` over owned production modules — shared command
    above.
11. `git diff --check`.

---

## RW4-GATE — Fresh Luna execution, one independent Luna review, separate Grok Oracle

- **ID:** RW4-GATE
- **Severity:** blocker for Batch 1 acceptance
- **Classification:** Oracle (Grok 4.6). Luna performs the RW4-06
  execution-result writeup and **exactly one** later independent full
  review. Grok issues the binary decision. Not `[XHARD]` implementation.
- **Executor:** GPT-5.6 Luna for review artifacts; Grok 4.6 for the
  Oracle verdict
- **Depends on:** RW4-01..RW4-06
- **Issues folded:** none (gate)

### Owned files

- Already written by RW4-06:
  - `.oracle/findings/execution-nbf01-rework4-luna.md`
  - `.oracle/receipts/execution-nbf01-rework4-luna.md`
- Later, new only:
  - `.oracle/checkins/batch-1-rework4-luna.md`
  - `.oracle/receipts/oracle-nbf01-rework4-luna.md`
  - `.oracle/checkins/batch-1-rework4-grok.md`
  - `.oracle/receipts/oracle-nbf01-rework4-grok.md`

### Prohibited

- No implementation by Grok 4.6 / this Oracle.
- No second reviewer, fan-out, or self-review.
- No mutation of `.oracle/tasklist.md`, `.oracle/plan.md`, North Star,
  custody, status, agent goal, or historical receipts.
- No commit, push, merge, or Batch 2 before `PASS_BATCH_1`.
- No Batch 1 pass decision is authorized by this triage packet.

### Gate sequence

1. Luna executes RW4-01..RW4-06 against this packet and writes the
   attempt-4 executor finding/receipt for the exact stable candidate.
2. Exactly one fresh independent Luna full review at the attempt-4
   check-in/receipt paths.
3. Separate Grok 4.6 Oracle synthesis. Only that gate may issue
   `PASS_BATCH_1` or `ACCEPTED_ISSUES`.

Until that Oracle returns `PASS_BATCH_1`:

```text
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
NO_COMMIT_PUSH_MERGE
```

---

## Issue / dependency matrix

```text
Issue 1 ─ RW4-01 ─┐
                  ▼
Issue 2 ─ RW4-02 ─┤
                  ▼
Issue 3 ─ RW4-03 ─┤
                  ▼
Issue 4 ─ RW4-04 ─┤
                  ▼
Issue 5 ─ RW4-05 ─┤
                  ▼
Issue 6 ─ RW4-06 ─┴─► RW4-GATE
```

| Issue | Task | Depends on | Model | Executor | `[XHARD]` |
| --- | --- | --- | --- | --- | --- |
| 1 C19–C21 | RW4-01 | none | Normal / GPT-5.6 Luna | Luna | none |
| 2 C02/C13 | RW4-02 | RW4-01 | Normal / GPT-5.6 Luna | Luna | none |
| 3 keyed/recovery | RW4-03 | RW4-01, RW4-02 | Normal / GPT-5.6 Luna | Luna | none |
| 4 race/crash | RW4-04 | RW4-01, RW4-02, RW4-03 | Normal / GPT-5.6 Luna | Luna | none |
| 5 confirmation | RW4-05 | RW4-01, serial after RW4-04 | Normal / GPT-5.6 Luna | Luna | none |
| 6 executor evidence | RW4-06 | RW4-01..RW4-05 | Normal / GPT-5.6 Luna | Luna | none |
| gate | RW4-GATE | RW4-06 + independent Luna review | Oracle | Luna review, Grok verdict | none |

`[XHARD]: none`.

---

## Execution-evidence gate (final)

Attempt-4 execution is incomplete until **one** fresh immutable Luna
executor finding and receipt exist at:

- `.oracle/findings/execution-nbf01-rework4-luna.md`
- `.oracle/receipts/execution-nbf01-rework4-luna.md`

bound to the exact post-fix HEAD and tree, with the inventory and
per-command stdout/stderr SHA-256 required by RW4-06.

After that, commission **exactly one** fresh independent Luna full review
and a **separate** Grok 4.6 Oracle synthesis. Do not commit, push, merge,
or start Batch 2 before `PASS_BATCH_1`. This triage packet authorizes none
of those actions.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
NO_PASS_BATCH_1
```
