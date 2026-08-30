# Supplemental rework tasklist — NBF-01 / Batch 1, attempt 2

**Status:** supplemental rework only. NBF-01 remains **unaccepted**. Batch 2
is **prohibited** until this rework passes a fresh Grok 4.6 Oracle gate.

This file does not mutate the frozen NBF tasklist, settled plan v8, North Star,
source base, or attempt-1 rework artifacts. It is the smallest follow-on
tasklist after attempt-1 received `ACCEPTED_ISSUES`. Build on the existing
dirty candidate; preserve every prior-MET primitive and the custody correction.

**Authority:** Grok 4.6 Oracle triage of the seven still-accepted findings in
`.oracle/checkins/batch-1-rework1-grok.md`, grounded in Luna review
`.oracle/checkins/batch-1-rework1-luna.md`, helper
`.oracle/findings/nbf01-rework-helper.md`, and independent re-read of the
current candidate symbols.

**Identities (verified 2026-08-30):**

| Artifact | Identity |
| --- | --- |
| North Star SHA-256 | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Settled plan v8 SHA-256 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen tasklist SHA-256 | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base with `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` |
| Attempt-1 rework tasklist SHA-256 | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-1 executor receipt SHA-256 | `1acba71b835c7bb2d854773d200c988f1fd344fa4ecdfab8eb64306ba7c69143` |
| Attempt-1 executor finding SHA-256 | `e7607cf15818e2c05b1fc997d92a06f133fe98e12d543e6d8555ddea96192f91` |
| Custody receipt SHA-256 | `48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9` |
| Current `.oracle/custody.md` SHA-256 | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Attempt-1 Luna review SHA-256 | `cdc6cd9b0ecfc3097c0c2940bb9ce85b810a84ab81ceb777ead97dfdc86ec89b` |
| Attempt-1 Grok check-in SHA-256 | `2d82e2d09e1ff7e49ac895878a5cbabc19e19dda4d109bd528da54c83e6b79a8` |
| Current owned production diff SHA-256 | `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801` (observation, not a target) |
| Oracle verdict on attempt 1 | `ACCEPTED_ISSUES` |

**Classification:** `[XHARD]` items in this rework: **none**.

Every item is ordinary deterministic contract, codec, lock/compare/append,
replay, CLI, alias-deletion, or test/evidence work already specified by
settled-plan §§4.4–4.13, §4.16, §§4.19–4.21 and frozen NBF-01. Breadth is not
an exceptional threshold. Plan §7 and the frozen tasklist already classified
NBF-01 as Normal / GPT-5.6 Luna; attempt 1 did not reopen that call and this
attempt does not either.

**Executor model for RW2-01..RW2-04:** GPT-5.6 Luna (`codex:gpt-5.6-luna`).
Exploration, implementation, critique, and independent review are Luna.
Grok 4.6 is Oracle and the RW2-GATE decision only.

**Not authorized by this tasklist:** commit, push, merge, rebase, reset, clean,
staging, plan mutation, frozen-tasklist mutation, Batch 2 dispatch, main merge,
box mutation, a second journal/projection/scheduler/policy owner, another
custody edit, rewriting historical receipts, or implementation by this Oracle.

Build on the existing dirty candidate tree. Do not stash or overwrite
orchestrator-owned `.oracle` artifacts except the evidence files this tasklist
explicitly owns.

---

## Scope reminder (frozen NBF-01 ownership)

Own only the NBF-01 primitives: schemas, `DispatchOutcome.kind=worker_disposition`,
disposition-to-terminal mapping, one existing-journal CAS, terminal writer,
changed-precondition producers, keyed provider-failure-key replay mechanics,
probe leases, one composite `provider_route_child_reserved`, post-commit receipt
derivation, reconciliation, two-scan confirmation, and the disposition helper/CLI.

**Prohibited files and behaviors (every task):**

- Do not edit admission callers, `dispatch_with_admission`, scheduler loops,
  T7 cooldown policy, T8 thresholds/degradation/hold/probe-policy/fallback
  selection/return-to-primary, physical doors, launch adapters, WBC construction,
  Python or shell signal-site wiring, `fallback_chains.py` policy,
  `workers/_impl.py`, `workers/omp.py`, `cloud/babysitter/launch.py`,
  `handlers/shared.py`, `auto.py`, `recovery_policy.py`, or any later-task file.
- Do not add a second journal, store, prepare/commit protocol, rotator, family
  lease, or second projection authority.
- Do not implement T8 policy from the §4.16 transition table's "Route-policy
  effect" column. Replay the streak/key mechanics only.
- Do not edit `.oracle/tasklist.md`, `.oracle/plan.md`, `.oracle/northstar.md`,
  `.oracle/agent_goal.md`, `.oracle/custody.md`, or historical Batch 1 /
  attempt-1 receipts, findings, or check-ins.
- Do not rewrite history to make the mutated 52-vs-61 count or the
  unreproducible `4aee815d...` digest look consistent. Current 78/78 and
  `e060f650...` are observations, not waivers or targets.
- Do not request or perform another custody edit. `f8725af...` is already
  labeled historical; `798c506...` is current.
- Do not signal from the CLI. One JSON acknowledgement on stdout; diagnostics
  on stderr only.
- Do not invent a generic unit-of-work / two-phase framework. Reuse the
  existing `_IncidentEventJournal` sequence-sidecar `fcntl.flock`, `_locked`,
  and `_append_nbf_locked` pattern. Do not wrap a new transaction API around
  the door that already exists.

---

## Prior-MET behavior that must be preserved

Attempt 1 landed real progress. Do not regress it while closing the remaining
holes:

- One `_IncidentEventJournal` + sequence-sidecar flock. NBF writes enter
  `_locked` / `_append_nbf_locked` (`ledger.py:405-465,536-759`).
- C03 `no_launch` cannot serialize with `launch_state=accepted`.
- C04 worker-disposition required accepted launch, disposition_id, receipt,
  fingerprint, phase/spec, logical/worker identity, start/finish.
- C05 worker disposition cannot carry provider-exhaustion or no-launch state.
- C06 lossless map to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- C08 never coerced into ordinary failure.
- C12 `no_launch` produces no worker terminal/fingerprint/provider/streak.
- C15 TERM vs KILL ladder IDs remain distinct.
- C16 semantic fingerprint excludes volatile liveness and logical/family IDs.
- C17 route-liveness digest absent from fingerprint and provider-failure key.
- C18 / C25 two-OS-process same-fingerprint reservation contention yields one
  winner (`test_two_process_reservation_contention_one_winner`).
- C26 composite child is one record and contains no child receipt-ID input.
- C35 scheduling / no-launch / unresolved / time / liveness refresh do not
  mutate provider streak.
- CP04 / CP10: no second journal, store, prepare/commit, scheduler, rotator,
  or family lease.
- CP05: only accepted `provider_exhausted` terminals increment observations.
- RW-CUSTODY: already MET. Do not edit `.oracle/custody.md`.
- Owned source scope: five modified production files, new
  `incident/disposition.py`, eight named new test modules.
  `test_incident_ledger.py` remains unchanged versus `origin/main`.
- Historical evidence stays historical: start-gate 52→61, unreproducible
  `4aee815d...`, failed-handoff digest `50c86490...`.

Keep those named tests and behaviors. Strengthen thin same-name tests in
place; do not delete them to invent a new count.

---

## Seven-to-task mapping

| Still-accepted finding | Severity | Task | Merge rationale |
| --- | --- | --- | --- |
| 1 One-door CAS and reservation-bound context | blocker | **RW2-01** | Same `IncidentLedger` lock/read/compare/append/replay door, including schema validators used on that door. |
| 2 Incomplete strict schema matrix | blocker | **RW2-01** | Decode/append matrix is the validation half of the same append authority. |
| 3 Caller-controlled changed-precondition authority | blocker | **RW2-01** | Producer derivation is schema-side; consume/reserve binding is the same locked door. |
| 4 Keyed provider replay | major | **RW2-02** | Distinct reducer seam inside `_project_records`; must not reopen unlocked compares or add T8 policy. |
| 5 Durable two-scan confirmation and CLI | major | **RW2-03** | Contract G is one helper/CLI contract; status 5 requires consumed confirmation. |
| 6 Thin acceptance evidence | major | **RW2-04** | Cross-cutting named behavioral gaps plus candidate-bound transcripts. |
| 7 Generic aliases/constructors | minor | **RW2-04** | Same seam as evidence closure: delete unofficial surfaces on existing types. Not a new abstraction. |

Do not split these further into ceremonial microtasks. Do not give two tasks
ownership of the same compare/append critical section. Do not reopen RW-CUSTODY.

**Suggested Luna order:** RW2-01 → RW2-02 → RW2-03 → RW2-04.
RW2-02 and RW2-03 may proceed in parallel after RW2-01. RW2-GATE is last and
is not implementation.

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

CLI (Contract G / settled-plan §4.21):

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Exact statuses: `0` append succeeded; `2` malformed JSON or schema violation;
`3` ledger append/locking failure; `4` invalid or unavailable ledger/context
location; `5` missing, expired, mismatched, or already-consumed confirmation.

Subprocess contention, replay, and crash commands are named per task. Prefer
`multiprocessing`/`subprocess` against one on-disk ledger (real `fcntl.flock`)
over in-process threading. Use injectable clocks for TTL/separation. Do not
inflate test count with duplicate happy-path stubs; add or strengthen one
behavioral test per named frozen hole.

Do not modify existing `tests/arnold_pipelines/megaplan/test_incident_ledger.py`
unless a frozen must-criterion cannot live in the eight new modules. Prefer the
eight named new modules.

---

## RW2-01 — Ledger door: CAS, reservation-bound context, schema matrix, producers

- **ID:** RW2-01
- **Severity:** blocker
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Frozen §§4.4–4.7 / Contracts A/B/D/E
  already specify the existing journal lock, compare steps, codecs, and
  reason-specific producers. This completes those contracts on the door that
  already exists. It is not a new concurrency protocol or schema language.
- **Executor:** GPT-5.6 Luna
- **Depends on:** none
- **Accepted findings folded:** 1, 2, 3
- **Criteria closed:** C01 (DispatchOutcome/SchedulingCondition matrix; do
  **not** overweight `PhaseResult.from_dict`), C02, C07, C09, C10, C13, C14,
  C18-as-CAS (already MET; do not regress), C19–C22, C25 (already MET; do not
  regress), C26 authorization identity used by RW2-02, C29, C36–C38, C40;
  Batch 1 CP03/CP04/CP09 remainder, CP11 race/reconciliation/fail-closed
  portions

### Owned files

- Production:
  - `arnold_pipelines/megaplan/incident/ledger.py`
    (`reserve`, `append_terminal_outcome`, `reserve_provider_route_child`,
    `consume_changed_precondition`, `create_probe_lease`,
    `reconcile_reservation`, `_append_nbf`, `_append_nbf_locked`, `_locked`,
    `_project_records` replay-validation only — not keyed-streak semantics,
    `read_nbf_events`).
  - `arnold_pipelines/megaplan/orchestration/phase_result.py`
    (`DispatchOutcome.__post_init__` / `from_dict`, `SchedulingCondition`).
  - `arnold_pipelines/megaplan/incident/schema.py`
    (`WorkerDisposition`, `ObservedProcessDeath`,
    `NonWorkerSignalDisposition`, `ChangedPrecondition.produce`,
    `__post_init__`, `_producer` / reason-specific producers,
    `produce_changed_precondition`, `ReservationReconciled`,
    `validate_nbf_event`).
  - `phase_result_classify.py` only if a mapping hole remains; do not expand
    classification policy.
- Tests:
  - `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
  - `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
  - `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
  - `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`

### Prohibited

- Do not change keyed-streak reducer semantics (RW2-02). You may reject
  invalid replay records fail-closed; do not implement applicable-key reset/
  rekey/break here beyond what is required to stop invalid records from
  projecting.
- Do not implement confirmation identity equality or CLI statuses (RW2-03),
  except that any change/probe consume used by these methods must occur under
  the same lock.
- Do not delete aliases here (RW2-04) except generic producer `**kwargs`
  surfaces that are the finding-3 door.
- Do not treat `PhaseResult.from_dict` unknown-field handling as a substitute
  for the DispatchOutcome matrix (Oracle already rejected that overweight).
- Do not add prepare/commit records, a second metadata file, or a UnitOfWork.
- Do not accept truthy-but-negative OOM objects.

### Work

The lock is already around the named methods. The remaining defect is
**incomplete compare/bind/validate inside that lock**, plus constructor and
append-path holes that let incompatible payloads and caller-forged identities
through.

**A. Reservation-bound CAS (finding 1)**

Keep `_locked` / `_append_nbf_locked`. Under that lock, in order:

1. Re-read records and projection. Compare expected projection version; fail
   closed on mismatch, schema failure, lock failure, append/fsync failure, or
   cache mismatch. Cache loss repairs from replay only. Invalid stored NBF
   payloads must fail closed and **never project** (`_valid_nbf` currently
   filters them at `ledger.py:32-36,470`).
2. `reserve`: reject unchanged terminal fingerprint without one eligible unused
   change; reject an active duplicate even across logical IDs; validate the
   persisted change (plan/phase/subject/provider-key binding) and consume it
   in the same locked append (`changed_precondition_consumed` or equivalent
   single-use marker already in this journal — do not add a second store);
   drop unconstrained `**extra`; append exactly one `admission_reserved`;
   derive and return the receipt only after durable commit. Preserve the
   existing two-process reservation winner.
3. `append_terminal_outcome`: bind plan, phase, projection key, fingerprint,
   receipt, logical identity, physical door, accepted-launch marker, worker/
   process identity, timing, and execution context to the **persisted**
   reservation. Derive expected admission receipt from the committed
   reservation event; do not treat a missing `admission_receipt_id` on the
   reservation as unconstrained (`ledger.py:580-584` is vacuous today). Do
   **not** skip `logical_dispatch_id` for provider exhaustion
   (`ledger.py:574-575`). Do **not** treat empty reservation fields as "no
   constraint" (`ledger.py:576-579`). Require exactly one already-committed
   matching disposition for `worker_disposition` and never re-append it;
   project terminal fingerprint **before** reservation closure from this one
   append (`ledger.py:495-500` currently closes first). Duplicate matching
   linkage is idempotent; conflicting terminal kind/linkage rejects; reject
   `no_launch` / `unresolved_launch`.
4. `reconcile_reservation`: permit only `released_no_launch`,
   `terminal_outcome_recovered`, and `permanent_hold_ambiguous`. Prove each
   from **persisted** authoritative evidence (controlled-adapter `not_started`
   marker bound to this receipt/reservation, or recovered accepted terminal /
   existing canonical disposition). Reject arbitrary nonempty
   `("marker",)` IDs (`ledger.py:678-680` and
   `test_positive_no_launch_reconciliation_only`). Reject blind release,
   closed-reservation release, accepted-launch release as no-launch,
   missing-PID/cache/timestamp "proof", and conflicting reconciliation.
   Identical replay is idempotent. Recovered worker disposition links one
   existing disposition and never duplicates disposition or signal evidence.
   Absence is not proof.
5. `reserve_provider_route_child`: one composite record, no child receipt-ID
   input; bind parent plan/phase/projection/logical identity; consume the
   authorizing recovery event in the same locked append so distinct child IDs
   cannot reuse one authorizer; unresolved or no-launch parents cannot create
   a child. Streak-preserve semantics of that consumption belong to RW2-02;
   single-use consumption belongs here.
6. `create_probe_lease`: one winner under the lock.
7. `consume_changed_precondition`: require the referenced event to be
   persisted; compare the supplied object with the persisted payload; do not
   re-read via `self.read_nbf_events()` identity tricks (`ledger.py:745`);
   single consumption under the lock (one winner across processes).
8. Torn/crash: a crash after read/before append, and a torn composite NDJSON
   write, expose neither partial transition nor derived receipt. `_emit_locked`
   still writes NDJSON directly (`ledger.py:261-271`); inject failure at that
   boundary rather than renaming a torn-line skip as a crash test.

**B. Strict schema matrix (finding 2)**

Close the complete Contract A kind/state/payload matrix at every decode and
append validation path (`DispatchOutcome.__post_init__` / `from_dict` and
`validate_nbf_event`). Remaining holes independently confirmed:

- `ordinary_terminal_failure` still accepts `success_payload`
  (`phase_result.py:170-175`; `schema.py:669-670`).
- `provider_exhausted` still accepts `terminal_failure`
  (`phase_result.py:176-183`; `schema.py:661-670` has no such reject).
- Named matrix test is not a full six-kind matrix
  (`test_dispatch_outcome_incompatible_payload_matrix`).
- Unresolved now shares the no-launch payload reject at
  `phase_result.py:159-161`; do not "fix" that already-closed case as if it
  were still open. Cover the remaining incompatible families, including
  provider/failure/disposition payloads on unresolved if any path still
  accepts them, and append-path variants.
- Worker / observed-death / non-worker identity, version, enum, finite
  non-negative `elapsed_s`, and typed PID/fingerprint rules remain incomplete
  at append (`validate_nbf_event` constructor-only for those types).
- OOM requires typed positive cgroup delta (`positive is True` and finite
  `delta>0`). Constructor tests exist; append-path / `validate_nbf_event`
  variants do not.
- Unknown death must use `killer_kind=external_unknown`,
  `cause_kind=observed_dead_unknown`, and `signal is None` at decode **and**
  append.
- `ChangedPrecondition.__post_init__` must not provide a constructor bypass
  of the reason→producer-kind/version mapping once producers are closed.
- `ReservationReconciled` schema membership is not proof; this task proves
  the three resolutions against the ledger.

Legal kind/state map:

```text
no_launch                 -> not_started
success                   -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted        -> accepted
worker_disposition        -> accepted
unresolved_launch         -> ambiguous
```

**C. Evidence-bound producers (finding 3)**

Replace generic caller-controlled producer surfaces
(`ChangedPrecondition.produce` hashing caller `before`/`after`/`evidence` at
`schema.py:452-475`; `produce_changed_precondition` / `_producer(..., **kwargs)`
at `schema.py:547-565`) with the seven frozen reason-specific producers:

```text
source_revision_changed
runtime_generation_changed
seed_or_interpreter_binding_changed
timeout_policy_changed
authorized_route_changed
provider_recovery_verified
verified_repair_committed
```

Each producer has a fixed `producer_kind` and `producer_version`; reads
authoritative before state, after state, and cited evidence; derives
`before_content_id` / `after_content_id` from normalized authoritative content
(they must differ); derives `evidence_digest` from the cited evidence event;
binds `provider_failure_key_before` / `after` from authoritative keys, not
caller strings.

Callers must not supply `producer_kind`, `producer_version`, subject, evidence
digest, before/after content IDs, or provider-failure-key transitions as
trusted inputs. Fixture objects may be passed **as the source to read**, not
as pre-digested IDs.

Ledger append/consume/reserve validate reason, producer kind/version, evidence
type/digest, subject, before/after derivation, and provider-key binding.
Reject: free-form reasons; forged but well-formed 64-hex IDs that do not match
authoritative content **with a recomputed coherent `event_id`**;
caller-supplied key transitions; mismatched subject/evidence/version;
`provider_recovery_verified` with unequal keys. Today's
`test_forged_valid_hex_content_ids_reject` mutates `after_content_id` to
`"a"*64` without recomputing `event_id` — that is inconsistent-identity
coverage only. Strengthen it in place.

Keep KISS: extend `_append_nbf_locked` so compare happens after lock and
before emit; do not wrap the ledger in a new transaction API.

### Acceptance criteria

- Two OS processes racing `reserve` on the same projection key + fingerprint
  still yield exactly one `admission_reserved` winner.
- Two OS processes racing terminal linkage for one reservation yield one
  terminal; the other is idempotent or a conflict reject, never two kinds.
- Two OS processes cannot both consume the same changed-precondition or probe
  lease.
- Terminal append with mismatched plan/phase/projection/fingerprint/receipt/
  logical identity against the reservation rejects, including provider
  exhaustion.
- Empty reservation fields cannot authorize a caller-supplied identity.
- `released_no_launch` with arbitrary nonempty evidence IDs rejects; only
  positive persisted controlled-adapter `not_started` evidence bound to the
  reservation releases, and it creates no terminal/fingerprint/provider/streak.
- Release after accepted launch or after closure rejects.
- Recovered disposition requires matching persisted disposition; no second
  disposition/signal append.
- Conflicting reconciliation rejects; identical reconciliation replays as a
  no-op.
- Invalid replay records fail closed and never project.
- Lock, schema, projection-version, append, fsync, and cache mismatch fail
  closed.
- Receipt still derives after append.
- Round-trip of the six outcome kinds plus scheduling conditions rejects
  unknown/missing fields and the full incompatible-payload matrix, including
  ordinary-failure+`success_payload` and provider-exhausted+`terminal_failure`.
- False OOM evidence and fabricated unknown-death killer/signal reject at
  decode **and** append.
- Incomplete worker/observed/non-worker identities reject at decode and append.
- TERM vs KILL ladder IDs remain distinct.
- Only allowlisted reason-specific producers can mint events.
- Forged valid 64-hex content IDs that do not match producer-derived digests
  reject at `from_dict`/append/consume even when `event_id` is recomputed.
- Provider-failure-key before/after cannot be caller-set independently of
  authoritative evidence.
- A valid event is consumed at most once and cannot authorize a second
  reservation.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
```

Required behavioral names. Add missing names; strengthen thin present names
in place (do not replace C18/C25):

Present — keep and strengthen:

- `test_two_process_reservation_contention_one_winner`
- `test_crash_after_read_before_append_exposes_no_partial_reservation`
  (must be a real crash-before-append / locked-compare abort, not a torn-line
  rename)
- `test_dispatch_outcome_incompatible_payload_matrix` (full six-kind matrix,
  including ordinary-failure+`success_payload` and
  provider-exhausted+`terminal_failure`)
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_oom_rejects_falsey_or_negative_cgroup_evidence` (constructor **and**
  append/`validate_nbf_event`)
- `test_unknown_death_rejects_fabricated_killer_and_signal` (constructor **and**
  append)
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
  (constructor **and** append)
- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject` (coherent forged event with
  recomputed `event_id`)
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`

Missing — add:

- `test_two_process_terminal_linkage_is_atomic`
- `test_terminal_rejects_reservation_context_mismatch`
- `test_terminal_requires_persisted_accepted_launch_context`
- `test_blind_release_and_accepted_launch_release_reject`
- `test_recovered_disposition_links_existing_record_without_duplicate`
- `test_conflicting_reconciliation_rejected_identical_replay_idempotent`
- `test_lock_schema_and_projection_version_mismatch_fail_closed`
- `test_consumed_change_cannot_authorize_second_reservation`
- `test_recovery_authorization_single_use_across_different_children`
- `test_invalid_replay_record_never_projects`

Use subprocesses and a real ledger directory for races. Sequential-only
contention is not acceptance.

---

## RW2-02 — Keyed provider replay mechanics (not T8 policy)

- **ID:** RW2-02
- **Severity:** major
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Contract F / §4.16 already lists the
  streak/key table. Policy column (degradation at 2, holds, fallback) is
  explicitly out of scope.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW2-01
- **Accepted findings folded:** 4
- **Criteria closed:** C11, C23 (streak preserve + single-use child auth),
  C24, C27 composite replay byte identity (with RW2-04 torn-composite),
  C30–C35 as **keyed** behavior, CP05–CP08

### Owned files

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  `_project_records` keyed reducer and any keyed lookup used under the RW2-01
  lock. `reserve_provider_route_child` consumption of one recovery authorizer
  was required in RW2-01; this task proves streak preserve + one child +
  keyed isolation. Do not reopen unlocked compare-then-append.
- Tests: `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`

### Prohibited

- No T8 thresholds, `provider_degraded` scheduling, scalar hold/probe policy,
  fallback selection, return-to-primary decisions, or edits to
  `fallback_chains.py`.
- Do not let probes, waits, recovery events, dispositions, or ordinary
  failures increment exhaustion streaks.
- Do not keep a single process-wide `provider_key` / `streak`, and do not
  treat `max(observation_streak)` or `latest_stream_key` as the active key
  (`ledger.py:497-531` currently reports the latest stream, while success/
  disposition broadcast-reset every same-base candidate).
- Do not implement CAS/schema/producers/CLI here.

### Work

Project by the frozen projection key:

```text
plan_id, primary_spec, configured_fallback_chain_identity, provider_failure_key
```

Today's stream identity uses `selected_spec` and omits `primary_spec`
(`ledger.py:498-500`). Terminal payloads must carry configured fallback-chain
identity. Provider-failure key remains
`digest(version, phase, normalized spec, typed failure class, provider epoch)`
and still excludes route-liveness, timestamps, probes, retry counts, and
membership digests.

Replay mechanics only:

- first accepted `provider_exhausted` for a key → streak 1;
- matching accepted exhaustion → increment that key;
- different-key accepted exhaustion → rekey **that** stream at 1; active
  state follows the canonical event/key stream, not the largest historical
  count;
- accepted success → reset the **applicable** key/streak only
  (`ledger.py:505-509` currently resets every same-base stream);
- accepted ordinary failure or `worker_disposition` → break consecutiveness
  of the **applicable** stream; never enter degradation and never coerce kind
  (`ledger.py:510-514` currently broadcast-resets);
- probe pass/fail and `provider_recovery_verified` create/consume → preserve
  matching streak;
- `provider_recovery_verified` authorizes **one** linked same-route child
  (consume via RW2-01) and does not reset/rekey;
- other allowlisted changes reset/rekey **only** when canonical
  `provider_failure_key_before != provider_failure_key_after`
  (`ledger.py:515-519` currently only stores changes);
- scheduling, no-launch, unresolved, time, liveness refresh → no streak
  mutation;
- duplicate event IDs idempotent; torn/invalid never project.

### Acceptance criteria

- Two phases/specs/keys no longer share one global streak; isolation is by
  values, not `len(provider_streaks)==2`.
- Recovery + probe around a live streak leave that streak unchanged and allow
  exactly one matching child.
- A second child attempt without a new unused recovery event rejects.
- Authoritative key-changing changed-precondition rekeys; key-unchanged
  change does not erase observations.
- Fresh reopen/replay reproduces keyed state and composite receipt bytes.
- Worker disposition breaks applicable consecutiveness without becoming
  degradation.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

Present — keep and strengthen:

- `test_provider_streak_is_keyed_not_global` (assert values and isolation,
  not dictionary length)
- `test_fresh_replay_receipt_is_byte_identical` (must cover a composite
  `provider_route_child_reserved` event, not only an ordinary reservation)

Missing — add:

- `test_nonmatching_key_rekeys_at_one`
- `test_success_resets_only_applicable_key`
- `test_probe_and_recovery_preserve_streak_and_authorize_one_child`
- `test_key_changing_precondition_rekeys_key_unchanged_does_not`
- `test_disposition_breaks_consecutiveness_without_degradation`

---

## RW2-03 — Durable two-scan confirmation and disposition CLI

- **ID:** RW2-03
- **Severity:** major
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** §4.20–4.21 already specify identity
  equality, replacement/expiry, restart replay, statuses 0/2/3/4/5, and
  non-signalling JSON CLI.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW2-01
- **Accepted findings folded:** 5
- **Criteria closed:** C39, C41

### Owned files

- Production: `arnold_pipelines/megaplan/incident/disposition.py`
  (`observe_confirmation`, `consume_confirmation`, `expire_confirmation` if
  present as helper, `_record_cli`); `arnold_pipelines/megaplan/incident/schema.py`
  confirmation event codecs (`SupervisionConfirmation`, confirmation branches
  of `validate_nbf_event`); `arnold_pipelines/megaplan/incident/ledger.py`
  confirmation observe/consume/replace/expire **under the existing lock**, and
  `IncidentLedger.__init__` ledger-location validation so CLI status 4 is a
  real branch (invalid/unavailable `--ledger-root` must fail before append).
- Tests: `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`,
  CLI branches in `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
  (or the confirmation module; do not add a ninth test module).

### Prohibited

- No wrapper-local confirmation files or second store.
- No signalling from the CLI.
- No free-form caller TTL; use
  `confirmation_ttl_s = min(max(2 * scan_interval_s, 30.0), 300.0)`.
- Do not skip consumed-confirmation checks for sustained-proof dispositions.
  Immediate timeout/owner-terminate may omit two-scan per §4.19, but the CLI
  must still return 5 when a required confirmation is missing/expired/
  mismatched/already-consumed.
- Do not keep helper-side unlocked `ledger.projection()` as the consume
  authority (`disposition.py:70-93`).
- Do not implement keyed replay or producers here.

### Work

Confirmation identity:

```text
digest(schema_version, site_id, subject_class, victim_pid,
       process_start, progress, supervisor_incarnation, cause_kind)
```

`SupervisionConfirmation` / `validate_nbf_event` must recompute
`confirmation_id`; `observe_confirmation` must not accept a forged ID.
Direct `ledger.observe_confirmation` is not an unofficial door.

Under the ledger lock:

1. First qualifying observation appends `supervision_confirmation_observed`
   only. Repeated same-identity observations must not silently overwrite the
   original first scan or expiry.
2. Second matching observation, ≥ one `scan_interval_s` later and ≤ expiry,
   equal on PID/process-start/progress/incarnation/cause/evidence identity,
   appends `supervision_confirmation_consumed` once. Identity arguments are
   **mandatory**; omitted fields are not timestamp-only success
   (`disposition.py:88-90`).
3. PID reuse, process-start change, progress advance, cause change, or
   supervisor/container incarnation change appends
   `supervision_confirmation_replaced` and starts a new first scan.
   Replacement must not be PID-limited (`ledger.py:691-701`).
4. Expiry appends `supervision_confirmation_expired`; next observation is a
   new first scan. Projection of expiry must invalidate the active
   confirmation (`ledger.py:527-529` currently sets `consumed` only when the
   type ends with `"consumed"`, so expired records remain live).
5. Restart/reopen replays original `expires_at`.
6. Concurrent second scans: one consumer.
7. Missing/torn/mismatched/already-consumed confirmation authorizes no
   disposition/signal.

CLI exact routing. Validate schema **before** confirmation-status shortcuts
so malformed worker payloads return 2, not 5 (`disposition.py:117-129`
currently checks confirmation first). Status 0 for a worker disposition must
prove a consumed confirmation whose receipt/PID/start/progress/incarnation/
cause matches the submitted disposition — not a non-worker record.

- `0` — schema-valid disposition, valid ledger location, required
  confirmation consumed, append succeeded; one JSON ack with
  disposition/ledger IDs; no signal.
- `2` — malformed JSON or schema violation.
- `3` — ledger append/locking failure (valid location, append fails).
- `4` — invalid or unavailable ledger/context location (constructor or
  path resolution fails closed; must not collapse into 3).
- `5` — missing, expired, mismatched, or already-consumed confirmation.

Independent subprocess transcripts under `/tmp/oracle-nbf01-rework1-luna/`
already prove statuses 0/2/3/4/5 are reachable. That is **not** the required
named pytest evidence. Status 0 used a non-worker record. Status 5 covered
missing confirmation only.

### Acceptance criteria

- Timestamp-only second scans with different PID/progress/incarnation/cause
  do not consume, including when identity kwargs are omitted.
- Replacement and expiry are durable events; restart preserves original expiry.
- Two processes racing consume yield one consumer.
- CLI 0 emits one JSON object, does not signal, and for worker dispositions
  requires a consumed matching confirmation.
- CLI 2 is reachable with malformed JSON and with schema-invalid payloads
  even when confirmation is missing.
- CLI 3 is reachable with a lock/append fault fixture at a valid location.
- CLI 4 is reachable with a non-ledger path and does not collapse into 3.
- CLI 5 is reachable with missing, expired, mismatched, and already-consumed
  confirmation.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

Present — keep and strengthen:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
  (mandatory equality; omitted kwargs must not consume)
- `test_confirmation_replacement_and_expiry_are_durable`
  (PID, process-start, progress, incarnation, and cause changes; expiry
  invalidates replay)

Missing — add:

- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_3_append_or_lock_failure`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`
  (also expired and mismatched)

Drive CLI via `python -m arnold_pipelines.megaplan.incident.disposition record`
(subprocess) for statuses 0/2/3/4/5. Do not skip 3/4/5.

---

## RW2-04 — Behavioral regressions, alias closure, immutable evidence protocol

- **ID:** RW2-04
- **Severity:** major (aliases are minor work inside this seam, not a new
  abstraction)
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Filling frozen must-criterion holes,
  deleting unofficial aliases, and recording reproducible command transcripts
  is ordinary validation/evidence work.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW2-01, RW2-02, RW2-03
- **Accepted findings folded:** 6, 7
- **Criteria closed:** C27 replay byte identity remainder, C28 torn/failed
  composite, CP01 as a real gate, CP11 remainder; evidence-integrity
  protocol; unofficial-surface closure

### Owned files

- Production alias deletion only (no new abstraction):
  - `arnold_pipelines/megaplan/incident/ledger.py` unofficial aliases
    `append_worker_disposition`, `write_terminal_outcome`,
    `reserve_admission`, `reconcile`, `replay_projection`
    (`ledger.py:768-772`) and the same-class unofficial aliases
    `append_provider_probe_result`, `acquire_probe_lease`,
    `append_confirmation`, `append_changed_precondition_event`
    (`ledger.py:761-764`) unless a frozen downstream symbol truly requires
    one (none do: frozen tasklist/plan do not name them; NBF tests do not
    call them; `replay_projections` in `arnold/critique_ledger` and
    `custody/projections.py` are different modules).
  - `arnold_pipelines/megaplan/incident/disposition.py` generic
    `make_worker_disposition`, `make_observed_process_death`,
    `make_non_worker_disposition` (`disposition.py:36-46`). Use explicit
    typed constructors (`WorkerDisposition`, `ObservedProcessDeath`,
    `NonWorkerSignalDisposition`).
  - `arnold_pipelines/megaplan/incident/schema.py` unofficial aliases
    `WorkerDeathDisposition`, `ReservationReconciliation`
    (`schema.py:687-688`) unless a frozen symbol requires them (none do).
- Tests (additive only, in the eight named new modules): especially
  `test_incident_ledger_transactions.py` (torn composite / crash boundaries),
  `test_provider_route_projection.py` (fresh-replay composite receipt byte
  identity), plus any must-criterion still absent after RW2-01..RW2-03.
- Evidence (new files only):
  - `.oracle/findings/execution-nbf01-rework2-luna.md`
  - `.oracle/receipts/execution-nbf01-rework2-luna.md`
- Do **not** rewrite `.oracle/receipts/execution-nbf01-luna.md`,
  `.oracle/findings/execution-nbf01-luna.md`,
  `.oracle/receipts/execution-nbf01-rework1-luna.md`,
  `.oracle/findings/execution-nbf01-rework1-luna.md`,
  `.oracle/custody.md`, or the Batch 1 / rework1 check-ins.

### Prohibited

- Do not fabricate a 52-test past or force the suite to any target count.
  Current 78/78 is an observation, not a target.
- Do not "fix" the historical `4aee815d...` digest by editing old receipts.
- Do not add tests that only increase collection count without exercising a
  frozen must-criterion hole named by Luna/Grok.
- Do not modify `test_incident_ledger.py` just to change 42+N arithmetic.
- Do not introduce a new facade, UnitOfWork, or "canonical alias module"
  in place of deletion.
- Do not edit historical attempt-1 evidence.

### Work

1. Audit RW2-01..RW2-03 tests against every frozen NBF-01 must criterion that
   Grok marked `NOT_MET` or `UNEVIDENCED` on attempt 1. Add only the missing
   behavioral cases, including:
   - torn/failed composite write: partial NDJSON line and crash between
     composite append and receipt derivation expose neither partial
     transition nor derived receipt;
   - fresh-replay receipt byte identity after reopen for the composite event;
   - any remaining forged-hash, context-mismatch, positive-OOM, unknown-death,
     replacement/incarnation/restart, CLI 0/2/3/4/5, or two-process race still
     unnamed after earlier tasks;
   - keyed replay byte identity of isolated streams after reopen.
2. Remove or constrain the unofficial aliases/constructors listed above.
   Retarget any incidental caller in the eight NBF modules to the explicit
   typed method. Do not touch critique-ledger / custody `replay_projections`.
3. Record evidence **without rewriting history**:
   - Preserve that the original start-gate receipt claimed **52** focused
     passed, later mutated on the same path to **61**, and that Luna
     reproduced **61** focused / **78** legacy at the failed handoff.
   - Preserve that claimed owned production digest
     `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
     **does not reproduce**.
   - Preserve failed-handoff Luna digest
     `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`
     as a historical snapshot.
   - Preserve attempt-1 post-rework observation `e060f650...` and focused
     **78** as observations, not targets or waivers.
4. After this attempt, capture a **new** command transcript and digest bound
   to the actual candidate source. Exact digest command (run from repo root,
   record full argv, cwd, exit, stdout, stderr, and sha256 of stdout bytes):

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Also digest untracked owned files with a listed `git hash-object` /
`shasum -a 256` of each:

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

The attempt-1 executor finding abbreviated argv and omitted per-command
stdout SHA-256. This attempt must not. Bind each command to the candidate
actually executed. Do not claim binary-diff mode unless the transcript shows
the exact flags and the digest reproduces on a second run.

### Acceptance criteria

- Every previously `NOT_MET`/`UNEVIDENCED` must criterion has a named
  behavioral test that can fail if the hole reopens.
- Focused, legacy, `py_compile`, `git diff --check`, OS subprocess
  contention, replay/torn/crash, and CLI 0/2/3/4/5 commands are in the new
  transcript with full argv, cwd, exit, stdout, stderr, and stdout SHA-256.
- New receipt states the focused pass **count as observed**, not as a target.
- Historical 52-vs-61 mutation and unreproducible `4aee815d...` remain
  labeled as evidence-integrity failures of the original handoff.
- Attempt-1 78/78 and `e060f650...` remain observations.
- Owned diff is still only the five modified production files +
  `disposition.py` + the eight new test modules.
- Named unofficial aliases/constructors are gone, or a written exception
  cites the exact frozen downstream symbol that requires one.

### Exact tests / commands (full gate suite)

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

Plus explicit CLI subprocess cases for statuses 0, 2, 3, 4, and 5.

Required additional test name if still missing after RW2-01..RW2-03:

- `test_torn_composite_write_exposes_neither_transition_nor_receipt`

---

## RW2-GATE — Fresh Luna execution, complete evidence, separate Grok Oracle

- **ID:** RW2-GATE
- **Severity:** blocker for Batch 1 acceptance
- **Classification:** Oracle (Grok 4.6). Luna performs execution-result
  writeup and **one** independent review pass. Grok issues the binary
  decision. Not `[XHARD]` implementation.
- **Executor:** GPT-5.6 Luna for review artifacts; Grok 4.6 for the Oracle
  verdict
- **Depends on:** RW2-01..RW2-04
- **Accepted findings folded:** none (gate)

### Owned files

- New only:
  - `.oracle/findings/execution-nbf01-rework2-luna.md` (if not already
    written by RW2-04)
  - `.oracle/receipts/execution-nbf01-rework2-luna.md`
  - `.oracle/checkins/batch-1-rework2-luna.md`
  - `.oracle/receipts/oracle-nbf01-rework2-luna.md`
  - `.oracle/checkins/batch-1-rework2-grok.md`
  - `.oracle/receipts/oracle-nbf01-rework2-grok.md`

### Prohibited

- No implementation by Grok 4.6 / this Oracle.
- No mutation of `.oracle/tasklist.md`, `.oracle/plan.md`, North Star,
  custody, or historical receipts.
- No commit, push, merge, or Batch 2 dispatch.
- No second Luna review pass unless Grok documents the exact exception.
- Do not self-issue `PASS_BATCH_1` from Luna.
- Do not commission another reviewer from this triage.

### Work

1. Luna execution receipt must identify the rework-2 result, the exact
   focused command output, legacy output, compile, diff-check, OS subprocess
   contention, replay/torn/crash, CLI 0/2/3/4/5, and the reproducible
   owned-diff digest from RW2-04, each with full argv/cwd/exit/stdout/stderr
   and stdout SHA-256 bound to the candidate actually run.
2. One independent Luna review against frozen NBF-01 criteria and North Star,
   not against narrative.
3. Separate Grok 4.6 Oracle decision: exactly `PASS_BATCH_1` or
   `ACCEPTED_ISSUES`.
4. Only Oracle `PASS_BATCH_1` unblocks the **later** orchestrator commit of
   Batch 1. This gate does not perform that commit.

### Acceptance criteria

- Fresh Luna execution + review artifacts exist and hash-identify the
  candidate actually reviewed.
- Evidence receipt is internally consistent (one focused count stated as
  observed, one digest command that reproduces, per-command stdout hashes).
- Grok verdict is present. Until then NBF-01 is unaccepted and Batch 2
  remains prohibited.

### Exact tests

Re-run the RW2-04 full gate suite immediately before review. Do not reuse
the mutated historical receipt or the abbreviated attempt-1 finding as
current evidence.

---

## KISS / YAGNI notes for Luna critique

Critique this rework for elegance, not extra scope:

- One journal, one lock, one append. The helper already exists (`_locked` /
  `_append_nbf_locked`). Move remaining compares inside it; do not add a
  UnitOfWork, two-phase commit, or extra projection cache service.
- Do not implement T8 because keyed replay is in scope.
- Do not add test files beyond the eight named NBF-01 modules.
- Drop aliases and `**kwargs` producer surfaces that do not enforce frozen
  producer identity. Deletion is the fix; a new facade is not.
- Do not overweight `PhaseResult.from_dict` as the C01 door.
- A green focused count that grows without covering two-process terminal
  races, forged coherent hashes, CLI 0/2/3/4/5, keyed isolation by value,
  or incarnation equality is another thin handoff and must fail RW2-GATE.
- Preserve prior-MET tests. Strengthen thin same-name tests in place.

---

## Explicit prohibitions (this Oracle / this tasklist)

This triage authorizes **no** implementation by Grok 4.6. It authorizes
**no** mutation of the frozen tasklist or settled plan, **no** commit,
push, merge, rebase, reset, or clean, **no** custody rewrite, **no**
historical-receipt rewrite, and **no** Batch 2 dispatch. NBF-01 remains
unaccepted until a fresh Luna execution of this supplemental tasklist and a
**separate** Grok Oracle gate pass.
