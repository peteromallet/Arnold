# Supplemental rework tasklist — NBF-01 / Batch 1, attempt 1

**Status:** supplemental rework only. NBF-01 remains **unaccepted**. Batch 2
is **prohibited** until this rework passes a fresh Grok 4.6 Oracle gate.

This file replaces foreign onboarding residue previously stored at this path
(`detect.py` / `catalog.py`). It does not mutate the frozen NBF tasklist,
settled plan v8, North Star, candidate production code, or source base.

**Authority:** Grok 4.6 Oracle triage of the eight `ACCEPTED_ISSUES` in
`.oracle/checkins/batch-1-grok.md`, grounded in Luna review
`.oracle/checkins/batch-1-luna.md` and independently re-read frozen contracts.

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
| Oracle verdict | `ACCEPTED_ISSUES` (`.oracle/checkins/batch-1-grok.md`) |

**Classification:** `[XHARD]` items in this rework: **none**.

Every item is ordinary deterministic contract, codec, lock/compare/append, replay,
CLI, or test work already specified by settled-plan §§4.4–4.13, §4.16, §§4.19–4.21
and frozen NBF-01. Breadth is not an exceptional threshold. Plan §7 and the frozen
tasklist already classified NBF-01 as Normal / GPT-5.6 Luna; this rework does not
reopen that call.

**Executor model for RW-01..RW-06 and RW-CUSTODY:** GPT-5.6 Luna
(`codex:gpt-5.6-luna`). Exploration, implementation, critique, and independent
review are Luna. Grok 4.6 is Oracle and the RW-GATE decision only.

**Not authorized by this tasklist:** commit, push, merge, rebase, reset, clean,
staging, plan mutation, frozen-tasklist mutation, Batch 2 dispatch, main merge,
box mutation, or a second journal/projection/scheduler/policy owner.

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
  `.oracle/agent_goal.md`, or historical Batch 1 receipts/findings/check-ins.
- Do not rewrite history to make the mutated 52-vs-61 count or the
  unreproducible `4aee815d...` digest look consistent.
- Do not signal from the CLI. One JSON acknowledgement on stdout; diagnostics
  on stderr only.
- Do not invent a generic unit-of-work / two-phase framework. Reuse the existing
  `_IncidentEventJournal` sequence-sidecar `fcntl.flock` + `_emit_locked`
  pattern. Delete aliases that do not enforce a contract
  (`append_worker_disposition`, `write_terminal_outcome`, `reserve_admission`,
  `reconcile`, `replay_projection`, generic `**kwargs` producer) unless a frozen
  symbol requires them.

---

## Eight-to-task mapping

| Accepted issue | Severity | Task | Merge rationale |
| --- | --- | --- | --- |
| 1 Atomic CAS / one ledger door | blocker | **RW-01** | Same `IncidentLedger` lock/read/compare/append seam. |
| 4 Forgeable terminal/reconciliation context | blocker | **RW-01** | Binding *is* the compare step of the same methods. |
| 2 Strict schema and illegal-state matrix | blocker | **RW-02** | Decode/matrix authority in `phase_result.py` + record codecs. |
| 3 Evidence-bound changed-precondition producers | blocker | **RW-03** | Producer identity derivation is schema-side; consume-under-lock is supplied by RW-01. |
| 5 Global/incomplete keyed provider replay | major | **RW-04** | Distinct reducer seam inside `projection()`; must not reopen unlocked compares. |
| 6 Timestamp-only two-scan confirmation | major | **RW-05** | Contract G is one helper/CLI contract. |
| 7 Incomplete disposition CLI contract | major | **RW-05** | Status 5 requires consumed confirmation; status 4 requires ledger-location validation. |
| 8 Thin/mutated acceptance evidence | major | **RW-06** | Cross-cutting behavioral gaps plus evidence-integrity protocol. |
| Custody `f8725af...` vs `798c506...` | evidence | **RW-CUSTODY** | Evidence-only document correction; not an NBF primitive. |

Do not split these further into ceremonial microtasks. Do not give two tasks
ownership of the same compare/append critical section.

**Suggested Luna order:** RW-02 → RW-01 → RW-03 → RW-04 → RW-05 → RW-06.
RW-CUSTODY may run in parallel. RW-GATE is last and is not implementation.

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
inflate test count with duplicate happy-path stubs; add one behavioral test per
named frozen hole.

Do not modify existing `tests/arnold_pipelines/megaplan/test_incident_ledger.py`
unless a frozen must-criterion cannot live in the eight new modules. Prefer the
eight named new modules.

---

## RW-01 — One journal door: lock/read/compare/append plus reservation-bound terminal/recon

- **ID:** RW-01
- **Severity:** blocker
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Frozen §4.7 already specifies the existing
  journal lock, the compare steps, and fail-closed behavior. This is completing
  the specified CAS, not designing a new concurrency protocol.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW-02 should land first so append/decode validators exist;
  RW-01 must not ship unlocked compares while waiting. If sequenced in one Luna
  pass, implement RW-02 codecs before closing this door.
- **Accepted issues folded:** 1, 4
- **Criteria closed:** C07, C09, C10, C18-as-CAS, C22-as-CAS, C25, C29, C36,
  C37, C38, C40; Batch 1 CP03/CP04/CP11 race and reconciliation portions

### Owned files

- Production: `arnold_pipelines/megaplan/incident/ledger.py`
  (`reserve`, `append_terminal_outcome`, `reserve_provider_route_child`,
  `consume_changed_precondition`, `create_probe_lease`, `reconcile_reservation`,
  `_append_nbf` / the existing `_emit_locked` door). May add a private helper
  that performs lock → re-read projection → compare → single append → durable
  return. Must reuse `_IncidentEventJournal`; no new journal class.
- Tests: `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`,
  `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`,
  `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`

### Prohibited

- Do not change keyed-streak reducer semantics (RW-04).
- Do not implement producer identity derivation (RW-03); do make consumption
  and conflict decisions atomic even for currently stored events.
- Do not implement confirmation identity equality or CLI statuses (RW-05),
  except that any confirmation/change/probe consume used by these methods must
  occur under the same lock.
- Do not edit `IncidentLedger.__init__` location policy except if strictly
  required to fail-closed on lock/path errors during append (RW-05 owns the
  CLI status-4 constructor contract).
- Do not add prepare/commit records or a second metadata file.

### Work

Move every named method's read/compare/consume/conflict/append into **one**
critical section on the existing sequence-sidecar lock. Today's defect is
`projection()` / record scans **before** `_append_nbf` acquires `fcntl.flock`,
while `_append_nbf` idempotency is only by `event_id`. `reserve` includes
`logical_dispatch_id` in the event id, so two processes with the same
fingerprint can both append.

Under that lock, in order:

1. Re-read records and projection. Compare expected projection version; fail
   closed on mismatch, schema failure, lock failure, append/fsync failure, or
   cache mismatch. Cache loss repairs from replay only.
2. `reserve`: reject unchanged terminal fingerprint without one eligible unused
   change; reject an active duplicate even across logical IDs; validate and
   consume any required change; append exactly one `admission_reserved`; derive
   and return the receipt only after durable commit.
3. `append_terminal_outcome`: bind plan, phase, projection key, fingerprint,
   receipt, logical identity, and reservation event to the named reservation;
   require exactly one already-committed matching disposition for
   `worker_disposition` and never re-append it; project terminal fingerprint
   **before** reservation closure from this one append; duplicate matching
   linkage is idempotent; conflicting terminal kind/linkage rejects; reject
   `no_launch` / `unresolved_launch`.
4. `reconcile_reservation`: permit only `released_no_launch`,
   `terminal_outcome_recovered`, and `permanent_hold_ambiguous`. Prove each
   from **persisted** authoritative evidence (controlled-adapter `not_started`
   marker bound to this receipt/reservation, or recovered accepted terminal /
   existing canonical disposition). Reject blind release, closed-reservation
   release, accepted-launch release as no-launch, missing-PID/cache/timestamp
   "proof", and conflicting reconciliation. Identical replay is idempotent.
   Recovered worker disposition links one existing disposition and never
   duplicates disposition or signal evidence. Absence is not proof.
5. `reserve_provider_route_child`: one composite record, no child receipt-ID
   input; authorizing event consumed in the same locked append; unresolved or
   no-launch parents cannot create a child.
6. `create_probe_lease`: one winner under the lock.
7. `consume_changed_precondition`: single consumption under the lock (one
   winner across processes).

Keep KISS: extend `_append_nbf` so compare happens after lock and before emit;
do not wrap the ledger in a new transaction API.

### Acceptance criteria

- Two OS processes racing `reserve` on the same projection key + fingerprint
  yield exactly one `admission_reserved` winner; the loser fails closed.
- Two OS processes racing terminal linkage for one reservation yield one
  terminal; the other is idempotent or a conflict reject, never two kinds.
- Two OS processes cannot both consume the same changed-precondition or probe
  lease.
- Terminal append with mismatched plan/phase/projection/fingerprint/receipt/
  logical identity against the reservation rejects.
- `released_no_launch` with arbitrary nonempty evidence IDs rejects; only
  positive persisted controlled-adapter `not_started` evidence bound to the
  reservation releases, and it creates no terminal/fingerprint/provider/streak.
- Release after accepted launch or after closure rejects.
- Recovered disposition requires matching persisted disposition; no second
  disposition/signal append.
- Conflicting reconciliation rejects; identical reconciliation replays as a
  no-op.
- Lock, schema, projection-version, append, fsync, and cache mismatch fail
  closed.
- Receipt still derives after append.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
```

Required new behavioral names (add, do not replace sequential coverage):

- `test_two_process_reservation_contention_one_winner`
- `test_two_process_terminal_linkage_is_atomic`
- `test_terminal_rejects_reservation_context_mismatch`
- `test_blind_release_and_accepted_launch_release_reject`
- `test_recovered_disposition_links_existing_record_without_duplicate`
- `test_conflicting_reconciliation_rejected_identical_replay_idempotent`
- `test_crash_after_read_before_append_exposes_no_partial_reservation`
- `test_lock_schema_and_projection_version_mismatch_fail_closed`

Use subprocesses and a real ledger directory. Sequential-only contention is
not acceptance.

---

## RW-02 — Strict schema and illegal-state matrix

- **ID:** RW-02
- **Severity:** blocker
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Closed enums, field sets, and payload
  matrices are deterministic codecs already written in Contracts A/D/E/G.
- **Executor:** GPT-5.6 Luna
- **Depends on:** none
- **Accepted issues folded:** 2
- **Criteria closed:** C01 (DispatchOutcome/SchedulingCondition matrix; do not
  over-weight `PhaseResult.from_dict` as the door), C02, C13, C14, plus
  ReservationReconciled schema membership used by RW-01

### Owned files

- Production: `arnold_pipelines/megaplan/orchestration/phase_result.py`
  (`DispatchOutcome.__post_init__` / `from_dict`, `SchedulingCondition`);
  `arnold_pipelines/megaplan/incident/schema.py`
  (`WorkerDisposition`, `ObservedProcessDeath`, `NonWorkerSignalDisposition`,
  `ReservationReconciled`, `validate_nbf_event` decode paths).
- `phase_result_classify.py` only if a mapping hole remains; do not expand
  classification policy.
- Tests: `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`,
  `tests/arnold_pipelines/megaplan/test_worker_disposition.py`

### Prohibited

- Do not implement CAS, producers, keyed T8 policy, CLI, or confirmation
  projection here.
- Do not treat `PhaseResult.from_dict` unknown-field handling as a substitute
  for the DispatchOutcome matrix (Oracle already rejected that overweight).
- Do not accept truthy-but-negative OOM objects.

### Work

Close the complete Contract A kind/state/payload matrix at every decode and
append validation path:

```text
no_launch                 -> not_started
success                   -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted        -> accepted
worker_disposition        -> accepted
unresolved_launch         -> ambiguous
```

Reject every incompatible combination, including the current holes:

- `unresolved_launch` must not accept success, provider, ordinary-failure, or
  disposition payloads, nor `launch_state=accepted`.
- `success` must not accept provider or disposition evidence.
- `no_launch` cannot carry worker/provider/disposition/terminal/success
  payloads or `launch_state=accepted`.
- `worker_disposition` requires accepted launch, `disposition_id`, receipt,
  fingerprint, phase/spec, logical/worker identity, start/finish; cannot carry
  provider-exhaustion or ordinary-failure payloads.
- `provider_exhausted` requires the structured evidence fields in Contract A;
  it is not also ordinary failure.
- `ordinary_terminal_failure` cannot carry `disposition_id`.

Close version/enum/identity invariants:

- `WorkerDisposition`: schema_version, event_type, enums
  (mode/subject/signal/killer/cause), required identities, finite
  non-negative `elapsed_s`.
- `ObservedProcessDeath`: schema_version, event_type, subject
  worker|external_process, cause `cgroup_oom`|`observed_dead_unknown`.
  Unknown death **must** use `killer_kind=external_unknown`,
  `cause_kind=observed_dead_unknown`, and `signal is None`. It must not
  accept watchdog/SIGKILL or invented fingerprint/worker identity.
- OOM (`kernel_cgroup_oom` / `cgroup_oom`) requires **typed positive cgroup
  delta**, not Python truthiness. `{"positive": false}`, `0`, `""`, and empty
  containers reject.
- `NonWorkerSignalDisposition`: schema_version, event_type,
  `subject=non_worker_lifecycle`, cause/signal/killer enums; cannot impersonate
  a worker fingerprint.
- `ReservationReconciled`: schema_version, the three resolutions only, and
  typed evidence-kind/identity fields. Schema membership is not proof; RW-01
  proves the three resolutions against the ledger.

Enforce the same validators on `from_dict` and on ledger append
(`validate_nbf_event`).

### Acceptance criteria

- Round-trip of the six outcome kinds plus scheduling conditions rejects
  unknown/missing fields and the full incompatible-payload matrix.
- False OOM evidence rejects at decode and append.
- Fabricated unknown-death killer/signal values reject at decode and append.
- Incomplete worker/observed/non-worker identities reject.
- TERM vs KILL ladder IDs remain distinct (already MET; do not regress).

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

Required new behavioral names:

- `test_dispatch_outcome_incompatible_payload_matrix`
- `test_no_launch_rejects_accepted_launch_state` (named C03 regression)
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_oom_rejects_falsey_or_negative_cgroup_evidence`
- `test_unknown_death_rejects_fabricated_killer_and_signal`
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`

Also append-path variants through `IncidentLedger.append_disposition` /
`validate_nbf_event` so decode-only tests cannot hide writer holes.

---

## RW-03 — Evidence-bound changed-precondition producers

- **ID:** RW-03
- **Severity:** blocker
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Seven allowlisted reason-specific
  producers and derivation rules are already written in §4.6 / Contract B.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW-01, RW-02
- **Accepted issues folded:** 3
- **Criteria closed:** C19, C20, C21, C22 (evidence binding; atomicity owned
  by RW-01), C23 authorization identity (consumption/child remains RW-01/RW-04)

### Owned files

- Production: `arnold_pipelines/megaplan/incident/schema.py`
  (`ChangedPrecondition.produce`, `_producer` / reason-specific producers);
  `arnold_pipelines/megaplan/incident/ledger.py` only for
  `append_changed_precondition` and the **validation predicates** inside the
  already-locked consume/reserve path. Do not move those compares outside the
  lock RW-01 installed.
- Tests: `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`

### Prohibited

- Callers must not supply `producer_kind`, `producer_version`, subject,
  evidence digest, before/after content IDs, or provider-failure-key
  transitions as trusted inputs.
- Do not keep generic `produce(..., producer_kind=..., **kwargs)`.
- Do not implement T8 fallback/probe policy. `provider_recovery_verified`
  binds a successful canonical probe-result event already on the ledger.
- Do not reset/rekey streaks here (RW-04).

### Work

Replace the generic caller-controlled producer with the seven frozen
reason-specific producers:

```text
source_revision_changed
runtime_generation_changed
seed_or_interpreter_binding_changed
timeout_policy_changed
authorized_route_changed
provider_recovery_verified
verified_repair_committed
```

Each producer:

- has a fixed `producer_kind` and `producer_version`;
- reads authoritative before state, after state, and cited evidence;
- derives `before_content_id` / `after_content_id` from normalized
  authoritative content; they must differ;
- derives `evidence_digest` from the cited evidence event;
- binds `provider_failure_key_before` / `after` from authoritative keys, not
  caller strings.

Ledger append/consume/reserve validate reason, producer kind/version, evidence
type/digest, subject, before/after derivation, and provider-key binding.
Reject: free-form reasons; forged but well-formed 64-hex IDs that do not match
authoritative content; caller-supplied key transitions; mismatched
subject/evidence/version; `provider_recovery_verified` with unequal keys.

For tests, authoritative sources may be fixture objects passed into the
producer **as the source to read**, not as pre-digested IDs. A test that
mutates an ID to `"x"` is malformed-length coverage only and is not enough.

### Acceptance criteria

- Only allowlisted reason-specific producers can mint events.
- Forged valid 64-hex `before_content_id` / `after_content_id` that do not
  match producer-derived digests reject at `from_dict`/append/consume.
- Provider-failure-key before/after cannot be caller-set independently of
  authoritative evidence.
- A valid event is consumed at most once (rely on RW-01's locked consume;
  add a producer-level test that a second reserve cannot reuse it).
- `provider_recovery_verified` keys stay equal; other reasons may differ only
  when authoritative keys differ.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
```

Required new behavioral names:

- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject`
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
- `test_consumed_change_cannot_authorize_second_reservation`

---

## RW-04 — Keyed provider replay mechanics (not T8 policy)

- **ID:** RW-04
- **Severity:** major
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Contract F / §4.16 already lists the
  streak/key table. Policy column (degradation at 2, holds, fallback) is
  explicitly out of scope.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW-01, RW-03
- **Accepted issues folded:** 5
- **Criteria closed:** C11, C23 (streak preserve + single-use child auth),
  C24, C30–C35 as **keyed** behavior, CP05–CP07

### Owned files

- Production: `arnold_pipelines/megaplan/incident/ledger.py` `projection()`
  reducer and any keyed lookup used under the RW-01 lock. Do not reopen
  unlocked compare-then-append.
- Tests: `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`

### Prohibited

- No T8 thresholds, `provider_degraded` scheduling, scalar hold/probe policy,
  fallback selection, return-to-primary decisions, or edits to
  `fallback_chains.py`.
- Do not let probes, waits, recovery events, dispositions, or ordinary
  failures increment exhaustion streaks.
- Do not keep a single process-wide `provider_key` / `streak`.

### Work

Project by the frozen projection key:

```text
plan_id, primary_spec, configured_fallback_chain_identity, provider_failure_key
```

Provider-failure key remains
`digest(version, phase, normalized spec, typed failure class, provider epoch)`
and still excludes route-liveness, timestamps, probes, retry counts, and
membership digests.

Replay mechanics only:

- first accepted `provider_exhausted` for a key → streak 1;
- matching accepted exhaustion → increment that key;
- different-key accepted exhaustion → rekey that stream at 1;
- accepted success → reset the **applicable** key/streak;
- accepted ordinary failure or `worker_disposition` → break consecutiveness
  of the applicable stream; never enter degradation and never coerce kind;
- probe pass/fail and `provider_recovery_verified` create/consume → preserve
  matching streak;
- `provider_recovery_verified` authorizes **one** linked same-route child
  (consume via RW-01) and does not reset/rekey;
- other allowlisted changes reset/rekey **only** when canonical
  `provider_failure_key_before != provider_failure_key_after`;
- scheduling, no-launch, unresolved, time, liveness refresh → no streak
  mutation;
- duplicate event IDs idempotent; torn/invalid never project.

### Acceptance criteria

- Two phases/specs/keys no longer share one global streak.
- Recovery + probe around a live streak leave that streak unchanged and allow
  exactly one matching child.
- A second child attempt without a new unused recovery event rejects.
- Authoritative key-changing changed-precondition rekeys; key-unchanged
  change does not erase observations.
- Fresh reopen/replay reproduces keyed state.

### Exact tests

```bash
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

Required new behavioral names:

- `test_provider_streak_is_keyed_not_global`
- `test_nonmatching_key_rekeys_at_one`
- `test_success_resets_only_applicable_key`
- `test_probe_and_recovery_preserve_streak_and_authorize_one_child`
- `test_key_changing_precondition_rekeys_key_unchanged_does_not`
- `test_disposition_breaks_consecutiveness_without_degradation`

---

## RW-05 — Durable two-scan confirmation and disposition CLI

- **ID:** RW-05
- **Severity:** major
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** §4.20–4.21 already specify identity
  equality, replacement/expiry, restart replay, statuses 0/2/3/4/5, and
  non-signalling JSON CLI.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW-01, RW-02
- **Accepted issues folded:** 6, 7
- **Criteria closed:** C39, C41

### Owned files

- Production: `arnold_pipelines/megaplan/incident/disposition.py`
  (`observe_confirmation`, `consume_confirmation`, `_record_cli`, helper
  constructors); `arnold_pipelines/megaplan/incident/schema.py` confirmation
  event codecs if still incomplete; `arnold_pipelines/megaplan/incident/ledger.py`
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

### Work

Confirmation identity:

```text
digest(schema_version, site_id, subject_class, victim_pid,
       process_start, progress, supervisor_incarnation, cause_kind)
```

Under the ledger lock:

1. First qualifying observation appends `supervision_confirmation_observed`
   only.
2. Second matching observation, ≥ one `scan_interval_s` later and ≤ expiry,
   equal on PID/process-start/progress/incarnation/cause/evidence identity,
   appends `supervision_confirmation_consumed` once.
3. PID reuse, process-start change, progress advance, cause change, or
   supervisor/container incarnation change appends
   `supervision_confirmation_replaced` and starts a new first scan.
4. Expiry appends `supervision_confirmation_expired`; next observation is a
   new first scan.
5. Restart/reopen replays original `expires_at`.
6. Concurrent second scans: one consumer.
7. Missing/torn/mismatched/already-consumed confirmation authorizes no
   disposition/signal.

CLI exact routing:

- `0` — schema-valid disposition, valid ledger location, required
  confirmation consumed, append succeeded; one JSON ack with
  disposition/ledger IDs; no signal.
- `2` — malformed JSON or schema violation.
- `3` — ledger append/locking failure (valid location, append fails).
- `4` — invalid or unavailable ledger/context location (constructor or
  path resolution fails closed; must not collapse into 3).
- `5` — missing, expired, mismatched, or already-consumed confirmation.

### Acceptance criteria

- Timestamp-only second scans with different PID/progress/incarnation/cause
  do not consume.
- Replacement and expiry are durable events; restart preserves expiry.
- Two processes racing consume yield one consumer.
- CLI 4 is reachable with a non-ledger path; CLI 5 is reachable with missing
  and already-consumed confirmation; CLI 0 still emits one JSON object and
  does not signal.

### Exact tests

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py
```

Required new behavioral names:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`

Drive CLI via `python -m arnold_pipelines.megaplan.incident.disposition record`
(subprocess) for statuses 0/2/4/5. Status 3 may use a lock/append fault
fixture; do not skip 4/5.

---

## RW-06 — Behavioral regressions and immutable evidence protocol

- **ID:** RW-06
- **Severity:** major
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** Filling frozen must-criterion holes and
  recording reproducible command transcripts is ordinary validation/evidence
  work. Do not classify it `[XHARD]` because the first handoff mutated counts.
- **Executor:** GPT-5.6 Luna
- **Depends on:** RW-01 through RW-05
- **Accepted issues folded:** 8
- **Criteria closed:** C27 replay byte identity, C28 torn/failed composite,
  CP01 as a real gate, CP11 remainder; evidence-integrity correction

### Owned files

- Tests (additive only, in the eight named new modules): especially
  `test_incident_ledger_transactions.py` (torn composite / crash boundaries),
  `test_provider_route_projection.py` (fresh-replay receipt byte identity),
  plus any must-criterion still absent after RW-01..RW-05.
- Evidence (new files only):
  - `.oracle/findings/execution-nbf01-rework-attempt-1-luna.md`
  - `.oracle/receipts/execution-nbf01-rework-attempt-1-luna.md`
- Do **not** rewrite `.oracle/receipts/execution-nbf01-luna.md`,
  `.oracle/findings/execution-nbf01-luna.md`, or the Batch 1 check-ins.

### Prohibited

- Do not fabricate a 52-test past or force the suite to any target count.
- Do not "fix" the historical `4aee815d...` digest by editing old receipts.
- Do not add tests that only increase collection count without exercising a
  frozen must-criterion hole named by Luna/Grok.
- Do not modify `test_incident_ledger.py` just to change 42+19 arithmetic.

### Work

1. Audit RW-01..RW-05 tests against every frozen NBF-01 must criterion that
   Grok marked `NOT_MET` or `UNEVIDENCED`. Add only the missing behavioral
   cases, including:
   - torn/failed composite write: partial NDJSON line and crash between
     composite append and receipt derivation expose neither partial
     transition nor derived receipt;
   - fresh-replay receipt byte identity after reopen;
   - any remaining forged-hash, context-mismatch, positive-OOM, unknown-death,
     replacement/incarnation/restart, CLI 4/5, or two-process race still
     unnamed after earlier tasks.
2. Record evidence **without rewriting history**:
   - Preserve that the original start-gate receipt claimed **52** focused
     passed, later mutated on the same path to **61**, and that Luna
     reproduced **61** focused / **78** legacy.
   - Preserve that claimed owned production digest
     `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
     **does not reproduce**.
   - Luna independently computed
     `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`
     for `git diff origin/main --` over the five modified owned production
     files at the failed handoff. Treat that as a historical snapshot, not
     the post-rework digest.
3. After rework, capture a **new** command transcript and digest bound to
   the actual candidate source. Exact digest commands (run from repo root,
   record full argv, cwd, exit, and sha256 of stdout bytes):

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

Do not claim binary-diff mode unless the transcript shows the exact flags
and the digest reproduces on a second run.

### Acceptance criteria

- Every previously `NOT_MET`/`UNEVIDENCED` must criterion has a named
  behavioral test that can fail if the hole reopens.
- Focused, legacy, `py_compile`, `git diff --check`, subprocess contention,
  replay/torn/crash, and CLI 0/2/4/5 commands are in the new transcript with
  exit codes.
- New receipt states the focused pass **count as observed**, not as a target.
- Historical 52-vs-61 mutation and unreproducible `4aee815d...` remain
  labeled as evidence-integrity failures of the prior handoff.
- Owned diff is still only the five modified production files +
  `disposition.py` + the eight new test modules.

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

Plus explicit CLI subprocess cases for statuses 0, 2, 4, and 5.

Required additional test names if still missing after RW-01..RW-05:

- `test_torn_composite_write_exposes_neither_transition_nor_receipt`
- `test_fresh_replay_receipt_is_byte_identical`

---

## RW-CUSTODY — Label historical vs refreshed source SHA in custody.md

- **ID:** RW-CUSTODY
- **Severity:** evidence-only (not an NBF-01 production blocker by itself)
- **Classification:** normal (not `[XHARD]`)
- **Exceptional-threshold rationale:** One-paragraph labeling of an existing
  SHA. No design judgment.
- **Executor:** GPT-5.6 Luna
- **Depends on:** none (parallel)
- **Accepted issues folded:** Luna issue 9 / Grok custody contradiction

### Boundary (explicit)

This is a **separately authorized custody-document task**. It is **not** part
of the NBF-01 primitive door and must not be mixed into RW-01..RW-05 file
ownership.

The original Batch 1 Oracle brief forbade editing custody files. **This
supplemental rework tasklist is the authorization** to edit
`.oracle/custody.md` for a labeling correction only.

It does **not** belong only in receipts: leaving `.oracle/custody.md`
contradictory will keep poisoning start-gate identity checks. Receipts must
still treat `f8725af...` as historical and `798c506...` as current even if
this task has not yet landed.

### Owned files

- `.oracle/custody.md` only.

### Prohibited

- Do not change the frozen tasklist, plan, North Star, candidate code, git
  refs, or source base.
- Do not delete the old SHA.
- Do not rebase, fetch-reset, or rewrite branch history.
- Do not retitle the resume section as if the original baseline never existed.

### Work

In the top baseline block, explicitly label
`f8725af516da8d4249eb0d63563c37776d80daf8` as **historical** (origin/main at
the original 2026-08-27 custody capture).

Keep the resume section's refreshed source
`798c50619204010ed3f4297fbb57988fe9381924` as **current immutable source
base**. One or two sentences of contrast are enough.

### Acceptance criteria

- A reader of `.oracle/custody.md` cannot treat `f8725af...` as the live
  source base.
- Current source base remains `798c50619204010ed3f4297fbb57988fe9381924`.
- No other `.oracle` or production path changes in this task.

### Exact tests

None. Evidence: the edited paragraphs plus
`shasum -a 256 .oracle/custody.md` recorded in the RW-06/RW-GATE receipts.

---

## RW-GATE — Fresh Luna review, corrected evidence, separate Grok Oracle

- **ID:** RW-GATE
- **Severity:** blocker for Batch 1 acceptance
- **Classification:** Oracle (Grok 4.6). Luna performs execution-result
  writeup and **one** independent review pass. Grok issues the binary
  decision. Not `[XHARD]` implementation.
- **Executor:** GPT-5.6 Luna for review artifacts; Grok 4.6 for the Oracle
  verdict
- **Depends on:** RW-01..RW-06, and RW-CUSTODY if still open
- **Accepted issues folded:** none (gate)

### Owned files

- New only:
  - `.oracle/findings/execution-nbf01-rework-attempt-1-luna.md` (if not
    already written by RW-06)
  - `.oracle/receipts/execution-nbf01-rework-attempt-1-luna.md`
  - `.oracle/checkins/batch-1-rework-attempt-1-luna.md`
  - `.oracle/receipts/oracle-nbf01-rework-attempt-1-luna.md`
  - `.oracle/checkins/batch-1-rework-attempt-1-grok.md`
  - `.oracle/receipts/oracle-nbf01-rework-attempt-1-grok.md`

### Prohibited

- No commit, push, merge, plan mutation, frozen-tasklist mutation, or
  Batch 2 dispatch.
- No second Luna review pass unless Grok documents the exact exception.
- Do not self-issue `PASS_BATCH_1` from Luna.

### Work

1. Luna execution receipt must identify the rework result, the exact focused
   command output, legacy output, compile, diff-check, contention/replay/
   crash/CLI commands, and the reproducible owned-diff digest from RW-06.
2. One independent Luna review against frozen NBF-01 criteria and North Star,
   not against narrative.
3. Separate Grok 4.6 Oracle decision: exactly `PASS_BATCH_1` or
   `ACCEPTED_ISSUES`.
4. Only Oracle `PASS_BATCH_1` unblocks the **later** orchestrator commit of
   Batch 1. This gate does not perform that commit.

### Acceptance criteria

- Fresh Luna execution + review artifacts exist and hash-identify the
  candidate actually reviewed.
- Evidence receipt is internally consistent (one focused count, one digest
  command that reproduces).
- Grok verdict is present. Until then NBF-01 is unaccepted and Batch 2
  remains prohibited.

### Exact tests

Re-run the RW-06 full gate suite immediately before review. Do not reuse the
mutated historical receipt as current evidence.

---

## KISS / YAGNI notes for Luna critique

Critique this rework for elegance, not extra scope:

- One journal, one lock, one append. If a helper appears, it must be the
  existing flock/`_emit_locked` path with compare moved inside.
- Do not add a UnitOfWork, two-phase commit, or extra projection cache
  service to "make CAS real."
- Do not implement T8 because keyed replay is in scope.
- Do not add test files beyond the eight named NBF-01 modules.
- Drop aliases and `**kwargs` producer surfaces that do not enforce frozen
  producer identity.
- A green focused count that grows without covering two-process races,
  forged valid hashes, CLI 4/5, or incarnation equality is another thin
  handoff and must fail RW-GATE.
