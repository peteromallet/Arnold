# Supplemental rework tasklist — NBF-01 / Batch 1, attempt 3

**Status:** supplemental rework only. NBF-01 remains **unaccepted**. Batch 2
is **prohibited** until this rework passes a fresh Grok 4.6 Oracle gate
returning `PASS_BATCH_1`.

This file does not mutate the frozen NBF tasklist, settled plan v8, North Star,
source base, custody, status, agent goal, or any prior brief, check-in,
finding, receipt, or rework packet. It is the smallest follow-on tasklist
after attempt 2 received `ACCEPTED_ISSUES`. Build on the existing dirty
candidate. Preserve every prior-MET primitive and the already-corrected
custody document.

**Authority:** Grok 4.6 Oracle triage of the nine confirmed issues in
`.oracle/checkins/batch-1-rework2-grok.md`, grounded in Luna review
`.oracle/checkins/batch-1-rework2-luna.md` and independent re-read of the
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
| Attempt-2 owned tracked-production diff SHA-256 | `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d` |
| Attempt-2 supplemental tasklist SHA-256 | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-2 triage receipt SHA-256 | `3f1c460d06966d5eef2999e5e4b99e5324b2aa920609d10ffe2d54af81a41703` |
| Attempt-2 executor finding | `896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb` |
| Attempt-2 executor receipt | `d03d259725484d4eac22cae1e2582288a85a2d2dbfbbfbba7a2b0878b9b02e51` |
| Attempt-2 Luna review brief | `b4647bc377366ef4e2f6eeeb8bfc24f480bc0dbe2de21858873bcad372cde456` |
| Attempt-2 Luna review | `bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a` |
| Attempt-2 Luna review receipt | `53a69d3e8a4a232c63e7f25fcda279b0059162087a7d45244ba0bf8d271f6f2e` |
| Attempt-2 Grok check-in | `5ceb712841cb02a0abeb5142864b08107f86695020c872861dc1d1b8bc940455` |
| Attempt-2 Grok Oracle receipt | `622126f1a8ba909a6439a8f012c3e688c7c7bd4afe89ed1580bec1d06bb32e67` |
| Current `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Oracle verdict on attempt 2 | `ACCEPTED_ISSUES` |

The attempt-2 tracked-production diff digest is the **reviewed attempt-2
identity**, not a future target. Attempt-3 execution must measure and bind
its own post-fix tree. Do not rewrite attempt-2 artifacts when that digest
changes.

Focused `101 passed` and legacy `78 passed` are observations, never
acceptance targets. Preserve historical evidence as historical: start-gate
52→61, unreproducible `4aee815d…`, failed-handoff `50c86490…`, attempt-1
78/78 and `e060f650…`.

**Classification:** `[XHARD]: none`.

Every item is ordinary deterministic schema, ledger, reducer, CLI, test, or
evidence work already specified by settled-plan §§4.4–4.13, §4.16,
§§4.19–4.21 and frozen NBF-01. Breadth is not an exceptional threshold.
Plan §7 and the frozen tasklist already classified NBF-01 as Normal /
GPT-5.6 Luna. Attempts 1 and 2 did not reopen that call and this attempt
does not either.

**Executor model for RW3-01..RW3-06:** GPT-5.6 Luna (`codex:gpt-5.6-luna`).
Exploration, implementation, validation, and the later independent review
are Luna. Grok 4.6 is Oracle and the RW3-GATE decision only. This packet
does not dispatch either model.

**Not authorized by this tasklist:** commit, push, merge, rebase, reset,
clean, staging, plan mutation, frozen-tasklist mutation, Batch 2 dispatch,
main merge, box mutation, a second journal/projection/scheduler/policy
owner, another custody edit, rewriting historical receipts, implementation
by this Oracle, or any Batch 1 pass decision before RW3-GATE.

Build on the existing dirty candidate tree. Do not stash or overwrite
orchestrator-owned `.oracle` artifacts except the attempt-3 evidence files
this tasklist explicitly owns.

---

## Scope reminder (frozen NBF-01 ownership)

Own only the NBF-01 primitives: schemas, `DispatchOutcome.kind=worker_disposition`,
disposition-to-terminal mapping, one existing-journal CAS, terminal writer,
changed-precondition producers, keyed provider-failure-key replay mechanics,
probe leases, one composite `provider_route_child_reserved`, post-commit
receipt derivation, reconciliation, two-scan confirmation, and the
disposition helper/CLI.

**Prohibited files and behaviors (every task):**

- Do not edit admission callers, `dispatch_with_admission`, scheduler loops,
  T7 cooldown policy, T8 thresholds/degradation/hold/probe-policy/fallback
  selection/return-to-primary, physical doors, launch adapters, WBC
  construction, Python or shell signal-site wiring, `fallback_chains.py`
  policy, `workers/_impl.py`, `workers/omp.py`,
  `cloud/babysitter/launch.py`, `handlers/shared.py`, `auto.py`,
  `recovery_policy.py`, or any later-task file.
- Do not add a second journal, store, prepare/commit protocol, rotator,
  family lease, or second projection authority.
- Do not implement T8 policy from the §4.16 transition table's
  "Route-policy effect" column. Replay the streak/key mechanics only.
- Do not edit `.oracle/tasklist.md`, `.oracle/plan.md`,
  `.oracle/northstar.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`,
  `.oracle/status.md`, or any historical Batch 1 / attempt-1 / attempt-2
  receipt, finding, check-in, brief, or rework packet.
- Do not rewrite history to make the mutated 52-vs-61 count, unreproducible
  `4aee815d...`, failed-handoff `50c86490...`, or attempt-1 `e060f650...`
  look consistent. Current 101/78 are observations, not waivers or targets.
- Do not request or perform another custody edit. `f8725af...` is already
  labeled historical; `798c506...` is current.
- Do not signal from the CLI. One JSON acknowledgement on stdout;
  diagnostics on stderr only.
- Do not invent a generic unit-of-work / two-phase framework. Reuse the
  existing `_IncidentEventJournal` sequence-sidecar `fcntl.flock`,
  `_locked`, `_append_nbf_locked`, and `_emit_locked` pattern.
- Do not reopen C36–C38 reconciliation provenance, C01-as-`PhaseResult.from_dict`
  overweight, C40 cache-mismatch expansion, T8 policy, or any issue outside
  A3-01..A3-09. Close all and only those nine confirmed issues.

Owned source scope remains: five modified production files, new
`incident/disposition.py`, eight named new test modules.
`test_incident_ledger.py` remains unchanged versus `origin/main`.

---

## Prior-MET behavior that must be preserved

Attempt 2 landed real progress. Do not regress it while closing the
remaining holes:

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
- CP04 / CP10: no second journal, store, prepare/commit, scheduler,
  rotator, or family lease.
- CP05: only accepted `provider_exhausted` terminals increment observations.
- RW-CUSTODY: already MET. Do not edit `.oracle/custody.md`.
- Real two-process reservation contention remains a real `fcntl.flock` race.
- Historical evidence stays historical.

Keep those named tests and behaviors. Strengthen thin same-name tests in
place; do not delete them to invent a new count. Test-count growth is not
proof. New or strengthened tests must be behavioral, deterministic, and
must fail on the unmodified attempt-2 candidate for the hole they close.

---

## Independent confirmation of the nine issues

Oracle re-read the cited symbols on the current dirty tree. They still
behave as the attempt-2 verdict described.

1. **A3-01 / C10.** `append_terminal_outcome` (`ledger.py:651-718`) binds
   reservation fields under `_locked` and treats nonempty
   `worker_identity` / `started_at` / `finished_at` as "accepted-launch
   context" (`:677-678`). It never requires a persisted
   `controlled_adapter_state` with `launch_state_identity=accepted`.
   `_project_records` sets `accepted_launch=True` from the terminal itself
   (`:573-575`).
   `test_terminal_requires_persisted_accepted_launch_context` only rejects a
   missing worker/timing shape; it does not persist a marker and then prove
   a fully populated terminal without one. Luna probe
   `terminal_without_persisted_accepted_marker.accepted=true` stands.
2. **A3-02 / C02, C13, C14.** `DispatchOutcome.__post_init__`
   (`phase_result.py:169-173`) rejects `provider_evidence` and
   `terminal_failure` on `worker_disposition` and still accepts
   `success_payload`. `validate_nbf_event` (`schema.py:868-869`) likewise
   omits `success_payload`. `test_dispatch_outcome_incompatible_payload_matrix`
   is a selected constructor-only list and does not include
   worker-disposition+`success_payload`. Worker fingerprint is a required
   string, not a canonical 64-hex identity; `worker_identity` is any
   nonempty `str` or `dict` (`schema.py:316-321`).
   `NonWorkerSignalDisposition` accepts every `CauseKind`
   (`schema.py:415-416`). OOM constructor/append covers false/zero/negative
   cgroup evidence for worker disposition; unknown-death append covers
   fabricated killer only (`test_unknown_death_rejects_fabricated_killer_and_signal`).
   Legal positive OOM and legal unknown-death-remaining-unknown are not
   proven at the append boundary.
3. **A3-03 / C19–C21.** `ChangedPrecondition.produce` (`schema.py:516-539`)
   hashes caller `before` / `after` / `evidence`. The seven
   `produce_*` wrappers and `_produce_reason_specific` forward those
   snapshots. `append_changed_precondition` (`ledger.py:730-744`) checks
   snapshot equality against a persisted event, not authoritative source
   derivation. `test_forged_valid_hex_content_ids_reject` mutates
   `after_content_id` to `"a"*64` without recomputing `event_id`.
   `test_key_changing_precondition_rekeys_key_unchanged_does_not` forges
   keys via `from_dict`. Luna probe `forged_provider_transition=accepted`.
4. **A3-04 / C11, C32, C33.** Success / ordinary failure / worker
   disposition without a provider key select `latest_stream_key` when
   `active_base` matches (`ledger.py:557-569`).
   `test_success_resets_only_applicable_key` appends A, A, B, then success
   for B — the latest stream — so it cannot expose Luna's probe (success
   for A after B was latest left A at 2 and reset B to 0).
5. **A3-05 / C23, C34.** `reserve_provider_route_child` (`ledger.py:746-775`)
   rejects a repeated authorizer and does not require a persisted passed
   canonical probe bound to parent/phase/route/provider plus a
   producer-derived `provider_recovery_verified`. `append_probe_result`
   (`:930-932`) is an unconstrained probe write.
   `test_recovery_authorization_single_use_across_different_children`
   uses caller-supplied keys and an arbitrary lease.
6. **A3-06 / C27, C28, C09.** `test_fresh_replay_receipt_is_byte_identical`
   is an ordinary reservation (`test_provider_route_projection.py:44-49`).
   Composite replay lives under a different name.
   `test_torn_composite_write_exposes_neither_transition_nor_receipt`
   writes a truncated JSON prefix (`test_incident_ledger_transactions.py:36-42`)
   and never calls `reserve_provider_route_child` or `_emit_locked`.
   `test_two_process_terminal_linkage_is_atomic` races the same outcome/ID
   (`:81-102`); event-ID idempotency makes both `ok`.
7. **A3-07 / C39, C41.**
   `test_confirmation_compares_pid_start_progress_incarnation_cause`
   mutates only `victim_process_start_identity`.
   `expire_confirmation` (`ledger.py:918-925`) has no consumed guard.
   Projection of `supervision_confirmation_expired` overwrites
   `consumed=True` with `False` (`:601-604`). Named CLI status 5 covers
   missing and a differently-bound consumed confirmation; it omits expired
   and a distinct already-consumed matching replay.
8. **A3-08 / RW2-04.** Attempt-2 executor receipt omits explicit HEAD,
   truncates empty-output digests (`e3b0c44298fc1c1499b934ca495991b7852b855`),
   omits per-command stderr hashes, and cites CLI statuses as pytest names.
   Independent Luna `/tmp/oracle-nbf01-rework2-luna/` transcripts do not
   retroactively repair that artifact.
9. **A3-09.** `IncidentLedger.reserve_provider_route_child_with_receipt`
   (`ledger.py:781-783`) forwards generic `**kwargs`. Repo-wide search finds
   no production, test, frozen-tasklist, or settled-plan caller. Delete it.

---

## Nine-issue to task mapping

| Issue | Severity | Task | Merge rationale |
| --- | --- | --- | --- |
| A3-01 terminal accepted-launch is self-authorized (C10) | blocker | **RW3-01** | Same locked terminal/schema door as the payload matrix and producer bind. |
| A3-02 payload and typed identity matrix holes (C02/C13/C14) | blocker | **RW3-01** | Decode/append matrix is the validation half of that door. |
| A3-03 changed-precondition authority remains forgeable (C19–C21) | blocker | **RW3-01** | Producer derivation is schema-side; append/consume is the same lock. |
| A3-04 applicable provider stream is not selected (C11/C32/C33) | major | **RW3-02** | Reducer seam inside `_project_records`; coordinated with recovery. |
| A3-05 recovery/child authorization is not evidence-bound (C23/C34) | major | **RW3-02** | Child consume must target the same keyed stream RW3-02 selects. |
| A3-06 composite replay/crash and terminal-race evidence (C27/C28/C09) | major | **RW3-03** | Validates completed A3-01/A3-05 transaction behavior; tests plus `_emit_locked` injection only. |
| A3-07 confirmation and CLI evidence remains thin (C39/C41) | major | **RW3-04** | Contract G. Serial on `ledger.py` after RW3-03. |
| A3-09 unofficial convenience surface remains | minor | **RW3-05** | Seam-local deletion of one unofficial method. Not a new abstraction. Not folded into evidence. |
| A3-08 immutable executor evidence protocol incomplete (RW2-04) | major | **RW3-06** | Last. New attempt-3 executor finding/receipt only. |
| Fresh execution + independent Luna review + Grok Oracle | gate | **RW3-GATE** | Not implementation. |

Do not silently merge or omit A3-01..A3-09. Do not give two tasks concurrent
ownership of the same file. `ledger.py` has one writer at a time, in the
order below.

**Luna serial order:** RW3-01 → RW3-02 → RW3-05 → RW3-03 → RW3-04 → RW3-06.
RW3-GATE is last and is not implementation.

Rationale for the order:

- A3-01–A3-03 (RW3-01) are the authoritative schema/context foundations.
- A3-04 precedes and is packed atomically with A3-05 (RW3-02).
- A3-09 (RW3-05) is the same `reserve_provider_route_child*` method area;
  delete the unofficial wrapper after the real method is closed.
- A3-06 (RW3-03) validates the completed A3-01/A3-05 transaction behavior.
- A3-07 (RW3-04) would be independent except that it edits `ledger.py`;
  it therefore follows the other ledger writers.
- A3-08 (RW3-06) runs last against the stable post-fix candidate.

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

---

## RW3-01 — Foundations: accepted-launch marker, payload/identity matrix, authoritative producers

- **ID:** RW3-01
- **Issues closed:** A3-01, A3-02, A3-03
- **Severity:** blocker
- **Classification:** Normal / Luna (not `[XHARD]`)
- **Routing rationale:** Deterministic constructor/decode/validate/append
  contracts and reason-specific producers already specified by Contracts A,
  D, E and settled-plan §§4.4–4.7. Completing compare/bind inside the
  existing lock is not a new concurrency protocol or schema language.
- **Executor:** GPT-5.6 Luna
- **Depends on:** none
- **Overlapping-file lock:** sole writer of `phase_result.py`, `schema.py`,
  and `ledger.py` until this task finishes.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`append_terminal_outcome`, `_project_records` accepted-launch and
    changed-precondition validation only — not keyed-streak selection,
    `append_changed_precondition`, `consume_changed_precondition`,
    `_append_nbf_locked`, `_locked`; a smallest typed locked recorder for
    `controlled_adapter_state` if no public door exists).
  - `arnold_pipelines/megaplan/orchestration/phase_result.py`
    (`DispatchOutcome.__post_init__`, `from_dict`).
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`WorkerDisposition`, `ObservedProcessDeath`,
    `NonWorkerSignalDisposition`, `_positive_cgroup_delta`,
    `ChangedPrecondition.produce`, `__post_init__`,
    `produce_changed_precondition`, `_produce_reason_specific`, the seven
    `produce_*` reason-specific producers, `validate_nbf_event`).
  - `phase_result_classify.py` only if a mapping hole is opened by the
    matrix; do not expand classification policy.
- Tests:
  - `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
  - `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
    (accepted-launch / context-mismatch / matrix-at-append cases only;
    leave torn-composite and distinct-ID terminal race names for RW3-03,
    but existing terminal tests that currently succeed without a marker
    must persist the required accepted marker so they keep proving
    linkage rather than going red for the wrong reason)
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
    (matrix, identity, OOM, unknown-death; do not rewrite CLI tests)
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
  - `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`

### Prohibited

- Do not change keyed-streak reducer selection (RW3-02). You may reject
  invalid records fail-closed; do not implement applicable-key
  reset/rekey/break here beyond stopping invalid records from projecting.
- Do not implement confirmation identity/CLI (RW3-04) or delete
  `reserve_provider_route_child_with_receipt` (RW3-05).
- Do not add prepare/commit records, a second metadata file, or a
  UnitOfWork.
- Do not wire physical launch adapters or signal sites. The accepted
  marker is a ledger `controlled_adapter_state` event, not a babysitter
  or WBC change.
- Do not reopen C36–C38 marker provenance for `released_no_launch`.
- Do not accept truthy-but-negative OOM objects.
- Do not treat `PhaseResult.from_dict` unknown-field handling as a
  substitute for the DispatchOutcome matrix.

### Work

**A. A3-01 — persisted accepted-launch marker (C10)**

Keep `_locked` / `_append_nbf_locked`. Under that lock,
`append_terminal_outcome` must require **exactly one** persisted,
receipt-bound accepted `controlled_adapter_state` matching:

```text
reservation_event_id
admission_receipt_id
phase
selected_spec / primary_spec
logical_dispatch_id
worker identity
start context
physical_door_id
launch_state_identity = accepted
```

before appending any worker terminal. A fully populated terminal with no
marker must fail closed. Every single-field mismatch against that marker
must fail closed.

`_project_records` must **not** set `accepted_launch=True` from the
terminal being appended. Replay `controlled_adapter_state` into the
reservation. Terminal projection still precedes reservation `closed=True`
(preserve C29 order). Preserve atomic, idempotent one-terminal linkage
and no-launch separation (C12). `no_launch` / `unresolved_launch` still
have no worker terminal.

If tests currently append terminals with no marker, update them to persist
one matching accepted marker through the locked public NBF door. Do not
leave `_append_nbf` as the only way to mint the required proof.

**B. A3-02 — complete six-kind incompatibility and typed identity matrix
(C02/C13/C14)**

Enforce at direct construction, `from_dict`, `validate_nbf_event`, **and**
ledger append:

Legal kind/state map:

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

Specifically: `worker_disposition` must reject `success_payload` at
`DispatchOutcome.__post_init__`, `from_dict`, `validate_nbf_event`, and
`append_terminal_outcome` / `append_disposition`. Preserve C05: still
reject provider-exhaustion and no-launch state on worker disposition.

Typed identity:

- Worker semantic fingerprint is a canonical 64-hex SHA-256, not merely
  nonempty.
- Worker identity is a typed required structure, not any nonempty dict
  or bare truthy string used as a bypass.
- Observed-death subject/cause remain `worker|external_process` with
  `observed_dead_unknown` or `cgroup_oom` only.
- Non-worker subject is `non_worker_lifecycle`; worker-specific causes
  (`wedge`, `timeout`, `cgroup_oom`, `observed_dead_unknown`, …) reject.
- Required/missing/fabricated identity fields reject at decode and append.

OOM / unknown death, constructor **and** append/`validate_nbf_event`:

- Reject false (`positive is not True`), zero, and negative cgroup
  evidence.
- Accept legal positive OOM: `positive is True` and finite `delta > 0`.
- Reject unknown death with fabricated killer and with fabricated signal,
  each as its own append-path case.
- Accept legal unknown death (`killer_kind=external_unknown`,
  `signal is None`, `cause_kind=observed_dead_unknown`) and prove it
  remains unknown after append/replay.

**C. A3-03 — authoritative producers (C19–C21)**

Replace or seal the generic caller-snapshot path
(`ChangedPrecondition.produce` hashing caller `before`/`after`/`evidence`;
`produce_changed_precondition` / `_produce_reason_specific` forwarding
those snapshots). Public minting is only the seven allowlisted
reason-specific producers from settled-plan §4.6:

```text
source_revision_changed          -> reads authoritative repository/source receipt
runtime_generation_changed       -> reads authoritative runtime registry/manifest
seed_or_interpreter_binding_changed -> reads seed and interpreter attestations
timeout_policy_changed           -> reads canonical timeout-policy configuration
authorized_route_changed         -> binds jointly admitted composite route event
provider_recovery_verified       -> binds a successful canonical bounded probe result
verified_repair_committed        -> binds repository commit identity and verified digest
```

Each producer has a fixed `producer_kind` and `producer_version`. It
reads authoritative before, after, and cited evidence from typed source
objects. It derives `before_content_id` / `after_content_id` from
normalized authoritative content (they must differ) and `evidence_digest`
from the cited evidence event. Provider-failure-key before/after come
from authoritative keys, not caller strings.
`provider_recovery_verified` keeps before == after.

Callers must not supply `producer_kind`, `producer_version`, subject,
evidence digest, before/after content IDs, or provider-failure-key
transitions as trusted inputs. Fixture objects may be passed **as the
source to read**, not as pre-digested IDs.

`append_changed_precondition` and `consume_changed_precondition` must
recompute/verify producer, subject, version, cited evidence digest,
authoritative before/after content, and provider-failure-key transition.
A coherent forged event that recomputes every content hash and `event_id`
must still reject. Valid producer output is single-use under the journal
lock (preserve C22).

Keep KISS: extend compare inside `_append_nbf_locked`; do not wrap the
ledger in a new transaction API.

### Acceptance criteria

- Fully populated terminal with no persisted accepted marker rejects.
- Every single-field mismatch against the accepted marker rejects.
- Matching marker + matching reservation context appends exactly one
  terminal; identical replay is idempotent; conflicting kind/linkage
  rejects.
- `no_launch` still creates no worker terminal/fingerprint/provider/streak.
- Replay does not self-authorize `accepted_launch` from the terminal.
- Six-kind incompatibility matrix rejects every illegal payload family at
  constructor, decode, validation, and append, including
  `worker_disposition` + `success_payload`.
- Required/missing/fabricated identity fields reject at decode and append.
- False, zero, and negative OOM reject at constructor and append; legal
  positive OOM appends.
- Unknown death with fabricated killer rejects; unknown death with
  fabricated signal rejects; legal unknown death appends and remains
  unknown.
- Only allowlisted reason-specific producers can mint changes.
- Coherent forged provider-key / content-ID event with recomputed hashes
  rejects at `from_dict`, append, and consume.
- Valid producer output cannot authorize a second reservation.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
```

Required behavioral names. Strengthen thin present names in place:

Present — keep and strengthen:

- `test_terminal_requires_persisted_accepted_launch_context`
  (fully populated outcome, no marker, and every single-field mismatch)
- `test_terminal_rejects_reservation_context_mismatch`
- `test_dispatch_outcome_incompatible_payload_matrix`
  (full six-kind matrix at constructor, `from_dict`, `validate_nbf_event`,
  and append, including worker-disposition+`success_payload`)
- `test_oom_rejects_falsey_or_negative_cgroup_evidence`
- `test_unknown_death_rejects_fabricated_killer_and_signal`
  (append both fabricated killer and fabricated signal)
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject`
  (coherent forged event; recompute every content hash and `event_id`)
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
- `test_consumed_change_cannot_authorize_second_reservation`

Missing — add:

- `test_terminal_without_accepted_marker_rejects_fully_populated_outcome`
- `test_accepted_marker_single_field_mismatch_rejects`
- `test_legal_positive_oom_appends`
- `test_legal_unknown_death_remains_unknown_after_append`
- `test_worker_disposition_rejects_success_payload_at_append`
- `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`

These names must fail on the unmodified attempt-2 candidate.

---

## RW3-02 — Applicable keyed stream and evidence-bound recovery/child

- **ID:** RW3-02
- **Issues closed:** A3-04, A3-05
- **Severity:** major
- **Classification:** Normal / Luna (not `[XHARD]`)
- **Routing rationale:** Contract F / §4.16 already lists keyed
  reset/break/preserve mechanics and single-use recovery authorization.
  Policy column (degradation at 2, holds, fallback) is out of scope.
  Pairing A3-04 with A3-05 is required so child consume mutates the
  stream the reducer actually selects.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW3-01
- **Overlapping-file lock:** sole writer of `ledger.py` after RW3-01.

### Owned files and symbols

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  (`_project_records` keyed reducer, `append_terminal_outcome` applicable
  key persistence, `reserve_provider_route_child`, `append_probe_result`
  / probe persistence, consumption of `provider_recovery_verified` inside
  the one composite append). Schema producer for
  `produce_provider_recovery_verified` was closed in RW3-01; this task
  consumes that authoritative event.
- Tests: `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
  (except the required same-name composite fresh-replay body, which RW3-03
  owns after this task lands the real composite).

### Prohibited

- No T8 thresholds, `provider_degraded` scheduling, scalar hold/probe
  policy, fallback selection, return-to-primary, or
  `fallback_chains.py` edits.
- Do not let probes, waits, recovery events, dispositions, or ordinary
  failures increment exhaustion streaks.
- Do not keep `latest_stream_key` as a mutation fallback for
  success/ordinary/disposition.
- Do not implement CAS/schema/producers/CLI here.
- Do not add a second child-receipt argument or a second journal.

### Work

**A. A3-04 — select the applicable stream (C11/C32/C33)**

Carry or derive the applicable provider-failure-key identity on success,
ordinary failure, and worker disposition terminals. Persist it on the
existing terminal `provider_failure_key` field. Do not smuggle it through
`provider_evidence` on those kinds (preserve C05).

`_project_records` mutates **only** that keyed stream:

- accepted success resets the matching stream's streak and clears its
  broken flag;
- accepted ordinary failure or `worker_disposition` breaks
  consecutiveness of the matching stream (`broken=True`, streak 0) and
  never enters degradation;
- missing applicable key must **not** fall back to `latest_stream_key`.
  It mutates no stream.

Preserve C30/C31 matching-stream increment and first observation of a
new key at 1. Preserve C35: scheduling/no-launch/unresolved/time/liveness
still have no provider-terminal reducer branch.

**B. A3-05 — evidence-bound recovery/child (C23/C34)**

`reserve_provider_route_child` must require:

1. a persisted **passed** canonical `provider_probe_result` bound to the
   parent reservation/phase/route/provider;
2. a producer-derived `provider_recovery_verified` whose authoritative
   before/after keys match that provider and remain equal;
3. consumption of that authorization **exactly once** inside the one
   composite append;
4. creation of exactly one linked same-route child reservation;
5. preservation of the matching keyed streak.

Reject mismatched, failed, absent, replayed, and already-consumed
probe/recovery evidence. Repeated authorizer reject stays. Composite
shape stays one record with no child receipt-ID input (C26).

### Acceptance criteria

- Success for key A after B is most recent resets A and leaves B
  unchanged.
- Ordinary failure / disposition for a non-latest key breaks only that
  stream and does not create degradation.
- Cross-key isolation holds after restart/replay.
- Matching recovery + passed probe around a live streak leave that streak
  unchanged and allow exactly one matching child.
- Failed, missing, mismatched, replayed, and already-consumed
  probe/recovery evidence reject.
- A second child without a new unused recovery event rejects.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

Present — keep and retarget:

- `test_success_resets_only_applicable_key`
  (must target the **non-latest** stream; the current A,A,B-then-success-B
  body is latest-stream coverage and does not close A3-04)
- `test_disposition_breaks_consecutiveness_without_degradation`
  (non-latest target plus explicit no-degradation assertion)
- `test_provider_streak_is_keyed_not_global` (assert values, not dict length)
- `test_nonmatching_key_rekeys_at_one`
- `test_recovery_authorization_single_use_across_different_children`
  (start from a live keyed streak, a passed canonical probe, and a
  producer-derived recovery)

Missing — add:

- `test_success_for_non_latest_key_does_not_reset_latest`
- `test_ordinary_failure_breaks_only_applicable_stream`
- `test_applicable_key_survives_restart_and_replay`
- `test_cross_key_isolation_after_success_and_disposition`
- `test_recovery_requires_passed_canonical_probe`
- `test_failed_absent_mismatched_replayed_consumed_recovery_rejects`

Leave `test_fresh_replay_receipt_is_byte_identical` in place; RW3-03
replaces its body with a real composite after this task's child path is
closed.

---

## RW3-03 — Real composite replay/crash and distinct-ID terminal race

- **ID:** RW3-03
- **Issues closed:** A3-06
- **Severity:** major
- **Classification:** Normal / Luna (not `[XHARD]`)
- **Routing rationale:** Named behavioral proof of the already-specified
  `_emit_locked` composite append and one-terminal linkage. No new
  transaction protocol.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW3-01, RW3-02
- **Overlapping-file lock:** sole writer of `ledger.py` after RW3-05;
  sole writer of the composite-replay and terminal-race tests.

### Owned files and symbols

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  (`_emit_locked`, `reserve_provider_route_child` receipt derivation,
  `append_terminal_outcome` linkage). Add only the smallest test-visible
  injection seam on the existing `_emit_locked` / post-append receipt
  boundary if monkeypatching the method is insufficient. Do not add a
  second journal or prepare/commit protocol.
- Tests:
  - `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
    (`test_fresh_replay_receipt_is_byte_identical`)
  - `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
    (`test_torn_composite_write_exposes_neither_transition_nor_receipt`,
    `test_two_process_terminal_linkage_is_atomic`)

### Prohibited

- No second journal, store, or prepare/commit protocol.
- Do not keep ordinary-reservation coverage under the required
  fresh-replay name as the acceptance proof.
- Do not treat a truncated JSON prefix as a composite crash.
- Do not race the same terminal ID and call that C09.
- Do not reopen producer or reducer work.

### Work

1. Put a **real** composite `provider_route_child_reserved` transaction
   under the exact required name
   `test_fresh_replay_receipt_is_byte_identical`. After append, a new
   `IncidentLedger` instance must derive a byte-identical receipt.
   A differently named composite test may remain as extra coverage; it is
   not a substitute for this name.
2. Inject failure at the real composite `_emit_locked` and at the
   post-append receipt-derivation boundary. After restart, prove
   both-or-neither: either the child reservation, projection, and receipt
   all exist, or none do. A torn/partial composite line must expose
   neither transition nor receipt.
3. Race two OS processes using **distinct** terminal IDs and conflicting
   kinds against one reservation. Exactly one linkage may win. Replay of
   the winner remains valid; the loser is a conflict reject, never a
   second kind. Preserve same-ID idempotency as a separate case if useful;
   it is not this race.

### Acceptance criteria

- Required fresh-replay name covers a real composite and is
  byte-identical after reopen.
- Injected composite `_emit_locked` / post-append failure yields
  both-or-neither after restart.
- Distinct-ID conflicting-kind two-process terminal race yields one
  committed terminal; replay stays valid.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention"

pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt or keyed"
```

Required names:

- `test_fresh_replay_receipt_is_byte_identical` (composite, not ordinary
  reservation)
- `test_torn_composite_write_exposes_neither_transition_nor_receipt`
  (real `reserve_provider_route_child` + `_emit_locked` injection)
- `test_two_process_terminal_linkage_is_atomic` (distinct IDs, conflicting
  kinds, two OS processes)

These three must fail on the unmodified attempt-2 candidate.

---

## RW3-04 — Confirmation identity matrix and CLI 0/2/3/4/5

- **ID:** RW3-04
- **Issues closed:** A3-07
- **Severity:** major
- **Classification:** Normal / Luna (not `[XHARD]`)
- **Routing rationale:** Settled-plan §§4.20–4.21 already specify identity
  equality, replacement/expiry, restart replay, statuses 0/2/3/4/5, and
  non-signalling JSON CLI. Remaining work is completing the named matrix
  and the consumed-expiry guard.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW3-01 (serial on `ledger.py` after RW3-03)
- **Overlapping-file lock:** sole writer of `disposition.py` and of
  confirmation methods in `ledger.py` after RW3-03.

### Owned files and symbols

- Production:
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`observe_confirmation`, `consume_confirmation`,
    `expire_confirmation`, confirmation replay in `_project_records`)
  - `arnold_pipelines/megaplan/incident/disposition.py`
    (`observe_confirmation`, `consume_confirmation`, `_record_cli`)
  - `arnold_pipelines/megaplan/incident/schema.py` confirmation codecs
    only if identity recompute still has a hole after RW3-01; do not
    reopen producers.
- Tests:
  - `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
  - CLI branches in
    `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
    (do not add a ninth test module)

### Prohibited

- No wrapper-local confirmation files or second store.
- No signalling from the CLI.
- No free-form caller TTL; keep
  `confirmation_ttl_s = min(max(2 * scan_interval_s, 30.0), 300.0)`.
- Do not implement keyed replay or producers here.

### Work

Strengthen identity comparison so exact equality is required and every
single-field mismatch **and** omission rejects for:

```text
victim_pid
victim_process_start_identity
relevant_progress_identity
supervisor_incarnation_identity
cause_kind
evidence digest
TTL / expires_at
scan_interval_s separation
```

Durable restart, replacement, expiration, single consumption, and reopen
behavior stay. `expire_confirmation` must reject after consumption.
Projection of expiry must not overwrite a consumed confirmation with
`consumed=False`.

CLI, via real non-signalling subprocesses of
`python -m arnold_pipelines.megaplan.incident.disposition record`:

- `0` — one JSON ack only after a matching consumed confirmation; no
  signal.
- `2` — malformed JSON, and separately schema-invalid payload.
- `3` — valid location, append/lock failure.
- `4` — invalid or unavailable ledger/context location; must not collapse
  into 3.
- `5` — missing, **expired**, and a **distinct already-consumed matching
  replay** (same confirmation, same disposition identity, second CLI
  invoke). Differently-bound consumed confirmation may remain as extra
  coverage; it is not a substitute for the matching replay.

### Acceptance criteria

- Each identity field mismatch and each omission rejects consume.
- Replacement and expiry are durable; restart preserves original expiry.
- Expiry after consumption rejects; consumed state survives replay.
- Two processes racing consume still yield one consumer.
- CLI 0/2/3/4/5 subprocesses exist as named tests, including expired 5
  and distinct already-consumed matching replay.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

Present — keep and strengthen:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
  (every field mismatch and every omission, not only process-start)
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_3_append_or_lock_failure`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`
  (add expired and distinct already-consumed matching replay)

Missing — add:

- `test_expire_confirmation_after_consume_rejects`
- `test_cli_status_5_expired_confirmation`
- `test_cli_status_5_distinct_already_consumed_replay`

Drive CLI via subprocess. Do not skip 3/4/5.

---

## RW3-05 — Delete unofficial convenience surface

- **ID:** RW3-05
- **Issues closed:** A3-09
- **Severity:** minor
- **Classification:** Normal / Luna (not `[XHARD]`)
- **Routing rationale:** Deleting one unofficial `**kwargs` forwarder is
  ordinary API-surface cleanup. Inspection found no frozen downstream
  caller in production, tests, `.oracle/tasklist.md`, or `.oracle/plan.md`.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW3-02
- **Overlapping-file lock:** sole writer of the unofficial method on
  `ledger.py` after RW3-02 and before RW3-03.

### Owned files and symbols

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  (`IncidentLedger.reserve_provider_route_child_with_receipt` at
  `:781-783`).
- Tests: smallest API-surface assertion in
  `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
  or `test_incident_ledger_transactions.py`. Do not create a new module.

### Prohibited

- Do not create a new abstraction, facade, or typed wrapper in place of
  deletion.
- Do not constrain-and-keep the method. Inspection documented no frozen
  caller; delete it.
- Do not touch critique-ledger / custody `replay_projections`.
- Do not mix this cleanup into RW3-06 evidence work.

### Work

Delete `reserve_provider_route_child_with_receipt`. Callers use
`reserve_provider_route_child` plus `derive_receipt` after durable
commit. Add only the smallest necessary API-surface assertion that the
unofficial name is absent.

### Acceptance criteria

- `hasattr(IncidentLedger, "reserve_provider_route_child_with_receipt")`
  is false.
- `reserve_provider_route_child` and `derive_receipt` remain.

### Exact tests

One assertion, for example
`test_unofficial_route_child_with_receipt_surface_absent`, in an
existing NBF module.

---

## RW3-06 — Fresh attempt-3 executor evidence protocol

- **ID:** RW3-06
- **Issues closed:** A3-08
- **Severity:** major
- **Classification:** Normal / Luna (not `[XHARD]`)
- **Routing rationale:** Recording reproducible command transcripts bound
  to the post-fix tree is ordinary validation/evidence work. Independent
  review evidence does not retroactively repair an executor artifact.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW3-01, RW3-02, RW3-03, RW3-04, RW3-05
- **Overlapping-file lock:** none on production. Writes only new
  attempt-3 evidence paths.

### Owned files

New only:

- `.oracle/findings/execution-nbf01-rework3-luna.md`
- `.oracle/receipts/execution-nbf01-rework3-luna.md`

Do **not** rewrite any attempt-1 or attempt-2 finding, receipt, check-in,
or brief.

### Prohibited

- Do not fabricate a 52-test past or force any target count. 101/78 are
  observations, not targets.
- Do not "fix" historical `4aee815d...`, `50c86490...`, or `e060f650...`
  by editing old receipts.
- Do not claim binary-diff mode unless the transcript shows the exact
  flags and the digest reproduces on a second run.
- Do not cite CLI pytest names as the independent CLI evidence.

### Work

After the candidate is stable, capture a **new** immutable executor
finding and receipt bound to the exact post-fix HEAD and tree. They must
include:

1. `git rev-parse HEAD`, branch, merge-base, `origin/main`.
2. Complete tracked and untracked changed-file inventory for owned NBF
   paths.
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

4. `git hash-object` and `shasum -a 256` for:

```text
arnold_pipelines/megaplan/incident/disposition.py
tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
tests/arnold_pipelines/megaplan/test_provider_route_projection.py
tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
tests/arnold_pipelines/megaplan/test_scheduling_conditions.py
tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

5. For **every** command: full argv, cwd, exit status, verbatim stdout
   and stderr or an immutable transcript path, and full 64-hex SHA-256
   for **both** stdout and stderr. Empty output uses the full empty
   digest above; never truncate.
6. Independently invoke and bind CLI subprocesses for statuses 0, 2
   (malformed and schema-invalid), 3, 4, and 5 (missing, expired, and
   distinct already-consumed matching replay).

Preserve in the new finding, as historical:

- start-gate 52→61 mutation;
- unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`;
- failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`;
- attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`;
- attempt-2 reviewed production digest
  `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`
  as the attempt-2 identity, not the attempt-3 target.

### Acceptance criteria

- New finding and receipt exist at the attempt-3 paths and are not edits
  of attempt-2 artifacts.
- HEAD is explicit.
- Every required command has argv, cwd, exit, stdout, stderr, and full
  stdout/stderr SHA-256.
- CLI 0/2/3/4/5 are independent subprocess transcripts.
- Historical evidence remains labeled historical.

### Exact commands (full gate suite)

Run and transcript all of:

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

pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py

pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention"

pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt or keyed"

pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  -k "cli or confirmation or incarnation or reopen"

python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py

git diff --check
```

Plus explicit CLI subprocess cases for statuses 0, 2, 3, 4, and 5 as
specified above.

The behavioral contract this evidence must show, by command family:

1. focused pytest over the eight new NBF modules plus unchanged
   `test_incident_ledger.py`;
2. required legacy incident projection/summary/bridge and
   phase-result-classify regressions;
3. direct OS-process reservation contention and distinct-ID terminal
   races;
4. actual composite replay and injected crash/torn-write recovery;
5. coherent changed-precondition forgery with recomputed IDs;
6. terminal-without-accepted-marker and every context mismatch;
7. non-latest applicable-provider-key reset/break/replay;
8. successful/failed/missing/mismatched/consumed recovery probe
   authorization;
9. complete confirmation identity, TTL, replacement, restart, and
   one-consumer races;
10. independent CLI subprocesses for statuses 0, 2, 3, 4, and 5;
11. `python -m py_compile` for every owned production module;
12. `git diff --check`.

---

## RW3-GATE — Fresh Luna execution, one independent Luna review, separate Grok Oracle

- **ID:** RW3-GATE
- **Severity:** blocker for Batch 1 acceptance
- **Classification:** Oracle (Grok 4.6). Luna performs the RW3-06
  execution-result writeup and **exactly one** later independent full
  review. Grok issues the binary decision. Not `[XHARD]` implementation.
- **Executor:** GPT-5.6 Luna for review artifacts; Grok 4.6 for the
  Oracle verdict
- **Depends on:** RW3-01..RW3-06
- **Issues folded:** none (gate)

### Owned files

- Already written by RW3-06:
  - `.oracle/findings/execution-nbf01-rework3-luna.md`
  - `.oracle/receipts/execution-nbf01-rework3-luna.md`
- Later, new only:
  - `.oracle/checkins/batch-1-rework3-luna.md`
  - `.oracle/receipts/oracle-nbf01-rework3-luna.md`
  - `.oracle/checkins/batch-1-rework3-grok.md`
  - `.oracle/receipts/oracle-nbf01-rework3-grok.md`

### Prohibited

- No implementation by Grok 4.6 / this Oracle.
- No second reviewer, fan-out, or self-review.
- No mutation of `.oracle/tasklist.md`, `.oracle/plan.md`, North Star,
  custody, status, agent goal, or historical receipts.
- No commit, push, merge, or Batch 2 before `PASS_BATCH_1`.
- No Batch 1 pass decision is authorized by this triage packet.

### Gate sequence

1. Luna executes RW3-01..RW3-06 against this packet and writes the
   attempt-3 executor finding/receipt.
2. Exactly one fresh independent Luna full review at the attempt-3
   check-in/receipt paths.
3. Separate Grok 4.6 Oracle gate. Only that gate may issue
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
A3-01 ─┐
A3-02 ─┼─ RW3-01 ─┐
A3-03 ─┘          │
                  ▼
A3-04 ─┐          │
A3-05 ─┴─ RW3-02 ─┼─► RW3-05 (A3-09) ─► RW3-03 (A3-06) ─► RW3-04 (A3-07) ─► RW3-06 (A3-08) ─► RW3-GATE
```

| Issue | Task | Depends on | Model | Executor |
| --- | --- | --- | --- | --- |
| A3-01 | RW3-01 | none | Normal | Luna |
| A3-02 | RW3-01 | none | Normal | Luna |
| A3-03 | RW3-01 | none | Normal | Luna |
| A3-04 | RW3-02 | RW3-01 | Normal | Luna |
| A3-05 | RW3-02 | RW3-01 | Normal | Luna |
| A3-06 | RW3-03 | RW3-01, RW3-02, RW3-05 | Normal | Luna |
| A3-07 | RW3-04 | RW3-01, serial after RW3-03 | Normal | Luna |
| A3-09 | RW3-05 | RW3-02 | Normal | Luna |
| A3-08 | RW3-06 | RW3-01..RW3-05 | Normal | Luna |
| gate | RW3-GATE | RW3-06 + independent Luna review | Oracle | Luna review, Grok verdict |

`[XHARD]: none`.

---

## Execution-evidence gate (final)

Attempt-3 execution is incomplete until **one** fresh immutable Luna
executor finding and receipt exist at:

- `.oracle/findings/execution-nbf01-rework3-luna.md`
- `.oracle/receipts/execution-nbf01-rework3-luna.md`

bound to the exact post-fix HEAD and tree, with the inventory and
per-command stdout/stderr SHA-256 required by RW3-06.

After that, commission **exactly one** fresh independent Luna full review
and a **separate** Grok 4.6 Oracle gate. Do not commit, push, merge, or
start Batch 2 before `PASS_BATCH_1`. This triage packet authorizes none
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
