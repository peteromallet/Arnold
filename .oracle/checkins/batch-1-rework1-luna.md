# Luna independent review — NBF-01 / Batch 1 rework 1

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: 922241d0bdb3e993c3b554cc69f19948adef7bc3
- Tasklist SHA-256: 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
- Plan v8 SHA-256: 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
- North Star SHA-256: d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
- Rework tasklist SHA-256: 5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c
- Executor receipt: `.oracle/receipts/execution-nbf01-rework1-luna.md`
- Executor receipt SHA-256: 1acba71b835c7bb2d854773d200c988f1fd344fa4ecdfab8eb64306ba7c69143
- Custody receipt SHA-256: 48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9
- Owned production diff SHA-256: e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801
- Focused pytest: exit 0, 78 passed (`78 passed in 1.53s`; stdout SHA-256 `9cf73370d5321101a5f60d46e4572164f52630f3338b5d41a1f8cda4fcd4a006`)
- Legacy pytest: exit 0, 78 passed (`78 passed in 2.06s`; stdout SHA-256 `84f2299be394af8fc77dcda51eaca94e685326f456ebae809e5bbfd92fc18514`)
- CLI statuses: 0/2/3/4/5 reproduced; stdout SHA-256 values and verbatim output are in `/tmp/oracle-nbf01-rework1-luna/cli_status_*.txt`. Status 0 emitted one JSON acknowledgement; the CLI has no signal primitive.
- py_compile / git diff --check: both exit 0; stdout SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` for each.

## Scope and diff

Independent identity capture:

```text
HEAD       922241d0bdb3e993c3b554cc69f19948adef7bc3
origin/main 798c50619204010ed3f4297fbb57988fe9381924
merge-base 798c50619204010ed3f4297fbb57988fe9381924
branch     megado-nbf-guard-0826
```

The owned production diff command was rerun exactly and reproduced
`e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`.
Tracked production changes are exactly:

```text
M arnold_pipelines/megaplan/incident/__init__.py
M arnold_pipelines/megaplan/incident/ledger.py
M arnold_pipelines/megaplan/incident/schema.py
M arnold_pipelines/megaplan/orchestration/phase_result.py
M arnold_pipelines/megaplan/orchestration/phase_result_classify.py
```

Owned untracked file identities, independently recomputed as `git hash-object`
and raw-file SHA-256:

```text
arnold_pipelines/megaplan/incident/disposition.py
  git ea1d175d554e2364ca97ae84ff32ee3663b3818e
  sha256 04bf85191483258aa8c746fa12c9f5f746becfe288e4eaa0ac69fa2e5491374d
tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
  git b6cedc6cb4f7d806e95c41339930a4a9f6803363
  sha256 79d59501de3d3f11924b86764f757629de312064d3e06f2f84477a5e19dca547
tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
  git 1fb063bd24496d14e639bb360e1cea4a1d796e4e
  sha256 778fa119d6c7b46a9bd70e34d1df30fbb9b1102092383eeb34a304f0abaf3954
tests/arnold_pipelines/megaplan/test_provider_route_projection.py
  git d39b9b4b1ccb35b6bae567c20c64a2f559d38e8e
  sha256 034a83fd510cbb198b807fac6892f23e0ff19cdd029816d8a45fd4747368e63a
tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
  git 86d04ecfcefffa77c94261cb10529592725e677c
  sha256 eeee8b8970c2e3fcb742015b71085ac1dd6ddbbe246e792e9630b6467d9a18c
tests/arnold_pipelines/megaplan/test_scheduling_conditions.py
  git fc54999a025f23d89860facda94b260d1d7e5bb3
  sha256 2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb
tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
  git c002cd92c9ebf0da853f0cdc2e20c7839b642b79
  sha256 91328027e373347b71f07c71fd10305199cb18d0397dead8d4f5674d883f4eb0
tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
  git 4905610fc8e4860a28bc18a24ccbc89b635605b2
  sha256 695bc33ad89622ce9fa9227f0a7673cd17f17e7f1f583263e2757be12247195d
tests/arnold_pipelines/megaplan/test_worker_disposition.py
  git 20699ed29f05e53c3ea034d88d8338b7800029e3
  sha256 8484d6d4a85276534743299a72120c6d8dfd0c3cb96a19cea5faececcebaffac
```

`test_incident_ledger.py` is unchanged versus `origin/main` (`git diff --quiet`
exit 0). The focused collection is 78 tests: 36 from the eight new modules and
42 from unchanged `test_incident_ledger.py`. The current count is an observation,
not a target. Dirty `.oracle` planning/evidence artifacts are protected,
unrelated noise; they are not claimed clean and are not candidate source scope.

The eight new modules are not complete behavioral coverage. Missing required
names are: RW-01 `test_two_process_terminal_linkage_is_atomic`,
`test_terminal_rejects_reservation_context_mismatch`,
`test_blind_release_and_accepted_launch_release_reject`,
`test_recovered_disposition_links_existing_record_without_duplicate`,
`test_conflicting_reconciliation_rejected_identical_replay_idempotent`, and
`test_lock_schema_and_projection_version_mismatch_fail_closed`; RW-03
`test_consumed_change_cannot_authorize_second_reservation`; RW-04
`test_nonmatching_key_rekeys_at_one`, `test_success_resets_only_applicable_key`,
`test_probe_and_recovery_preserve_streak_and_authorize_one_child`,
`test_key_changing_precondition_rekeys_key_unchanged_does_not`, and
`test_disposition_breaks_consecutiveness_without_degradation`; RW-05
`test_confirmation_survives_ledger_reopen_with_original_expiry`,
`test_two_process_confirmation_single_consumer`,
`test_cli_status_0_one_json_ack_no_signal`, `test_cli_status_2_malformed_or_schema`,
`test_cli_status_4_invalid_ledger_location`, and
`test_cli_status_5_missing_and_already_consumed_confirmation`; and RW-06
`test_torn_composite_write_exposes_neither_transition_nor_receipt`.
Existing same-name tests are also thin where noted below: the RW-02 unresolved
case checks only `success_payload`; the RW-03 forged-ID case changes the ID to
`"a" * 64` without recomputing the event identity; the RW-04 keyed case only
asserts that two dictionary entries exist; and RW-05 confirmation coverage only
passes a process-start mismatch to an optional argument and checks one replacement
record.

## Independent command evidence

Full transcript files under `/tmp/oracle-nbf01-rework1-luna/` record each exact
argv, working directory, exit status, verbatim stdout/stderr, and stdout SHA-256:

| Command | Exit | Verbatim final summary / stdout SHA-256 |
|---|---:|---|
| Frozen focused pytest | 0 | `78 passed in 1.53s`; `9cf73370d5321101a5f60d46e4572164f52630f3338b5d41a1f8cda4fcd4a006` |
| Frozen legacy pytest | 0 | `78 passed in 2.06s`; `84f2299be394af8fc77dcda51eaca94e685326f456ebae809e5bbfd92fc18514` |
| Transactions subset | 0 | `3 passed, 2 deselected in 0.74s`; `47b54326e7889272182efd474399939e2da63379311228c229ca5ea2059fd304` |
| Provider subset | 0 | `3 passed, 1 deselected in 0.54s`; `fe81748103ec979aabecb726165d9a063f7b86f6cf9529798de207fa16eac8b1` |
| Confirmation subset | 0 | `4 passed in 0.49s`; `d659bd6603166793c084fa55538154b1e66dc1fb0a6b6de0f8bdd839943321ed` |
| py_compile | 0 | empty stdout; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| git diff --check | 0 | empty stdout; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

CLI subprocess evidence, using `PYENV_VERSION=3.11.11` Python, was independently
run via the requested module:

| Status | Evidence |
|---:|---|
| 0 | One stdout JSON object `{"disposition_id":"cli-d","ledger_event_id":"cli-d","record_id":"cli-d"}`, stderr empty, stdout SHA `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` |
| 2 | Malformed JSON; stdout empty, stderr `disposition schema error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`, SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 3 | Valid ledger root with an `events.jsonl` append fault; stdout empty, stderr `ledger append failure: [Errno 21] Is a directory: .../events.jsonl`, SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 4 | Existing file supplied as ledger root; stdout empty, stderr `invalid ledger location: ledger root must be a directory`, SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 5 | Worker disposition without confirmation; stdout empty, stderr `required confirmation missing`, SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Status 0 is non-worker and therefore does not exercise a consumed worker
confirmation. The required status-5 missing/already-consumed behavioral test is
absent. CLI source `arnold_pipelines/megaplan/incident/disposition.py:96-141` has
branches, but source plus a happy subprocess is not the required named regression
evidence.

## Criterion dispositions (C01–C41, CP01–CP11)

Statuses are `MET`, `NOT_MET`, or `UNEVIDENCED`. A source claim does not replace
a required behavioral test. Line references below are candidate source locations.

### NBF-01 criteria

- **C01 — NOT_MET.** `SchedulingCondition.from_dict` and `DispatchOutcome.from_dict` in `orchestration/phase_result.py:91-99,195-203` are closed at their own top level, but `PhaseResult.from_dict` at `:607-640` directly pulls fields/defaults and does not reject unknown/current-schema errors before construction. The focused tests only round-trip one scheduling record. Correction: use strict current nested decoding at every read/write/append boundary and add missing/unknown-field coverage.
- **C02 — NOT_MET.** `DispatchOutcome.__post_init__` at `phase_result.py:159-183` closes some cases, but unresolved outcomes still accept provider/failure/disposition payloads, ordinary failure accepts `success_payload`, and provider exhaustion accepts `terminal_failure`. `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads` only supplies `success_payload`. Correction: implement the full six-kind payload matrix and test every incompatible payload family.
- **C03 — MET.** `DispatchOutcome.__post_init__` rejects `no_launch` with accepted state at `phase_result.py:151-155`; `test_no_launch_rejects_accepted_launch_state` is a real direct regression.
- **C04 — MET.** Accepted outcomes require receipt/fingerprint and common phase/spec/logical identity at `phase_result.py:156-164`; worker disposition additionally requires disposition, worker, and start/finish at `:165-167`. `test_worker_disposition_round_trip_and_distinct_outcome` exercises the valid shape. Reservation linkage is separately deficient under C07/C10.
- **C05 — MET.** `phase_result.py:168-183` rejects worker disposition provider/failure payloads, rejects success/provider/disposition combinations as applicable, and no-launch rejects worker/provider/disposition evidence. The source and disposition matrix test cover the core prohibition.
- **C06 — MET.** `terminal_outcome_kind` in `phase_result_classify.py:212-217` returns `worker_disposition` without coercion, and `ledger.py:602-604` writes the same kind. No ordinary-failure remapping exists.
- **C07 — NOT_MET.** `append_terminal_outcome` now uses `_locked`, validates a previously committed disposition at `ledger.py:587-593`, and never appends a disposition while writing the terminal. However the required recovered-disposition behavioral name is missing, matching context is incomplete, and no two-process terminal linkage test exists. Correction: add a real concurrent linkage test and require exactly one fully matching committed disposition.
- **C08 — MET.** `DispatchOutcome` rejects ordinary failure carrying `disposition_id` at `phase_result.py:170-171`; `test_outcome_never_coerces_disposition_to_failure` is a real coercion regression.
- **C09 — NOT_MET.** The locked terminal loop at `ledger.py:594-601` handles a matching existing kind idempotently and conflicts on another kind, but required `test_two_process_terminal_linkage_is_atomic` is absent. Two independently supplied terminal IDs are not behaviorally tested. Correction: add the required OS-process race and assert one terminal kind/event only.
- **C10 — NOT_MET.** Terminal context comparison exists at `ledger.py:570-586`, but it skips `logical_dispatch_id` for provider exhaustion and treats empty reservation fields as no constraint. Projection marks `closed` before provider-state projection at `:495-500`, contrary to the required projection-before-closure ordering. Required context-mismatch test is absent. Correction: bind all reservation fields, remove compatibility bypasses, project terminal fingerprint before closure, and test each mismatch.
- **C11 — NOT_MET.** `_project_records` creates `provider_streams` at `ledger.py:476-531`, but the stream key omits the frozen projection key and ordinary/disposition intervention resets every candidate with the same base (`:510-514`), not only the applicable stream. The named test only asserts `len(provider_streaks) == 2`; it does not assert values or isolation. Correction: key by the complete frozen projection key/failure key and reduce only the applicable stream.
- **C12 — MET.** `append_terminal_outcome` rejects `no_launch` and `unresolved_launch` at `ledger.py:561-562`; no terminal/provider branch is created for those outcomes in the NBF projection. Scheduler/breaker ownership is correctly later-batch scope.
- **C13 — NOT_MET.** Worker/observed/non-worker records have strict field sets and basic enums in `schema.py:272-380`, but identity typing is incomplete (for example worker disposition PID/fingerprint fields are not validated as typed identities), and no append-path behavioral variants exist. `test_observed_and_non_worker_reject_missing_schema_version_and_identity` checks only selected constructor cases. Correction: close all identity/version/subject/mode invariants and exercise `append_disposition` plus `validate_nbf_event`.
- **C14 — UNEVIDENCED.** `_positive_cgroup_delta` correctly requires a dict with `positive is True` and finite positive delta (`schema.py:127-132`), and unknown observed death forces `external_unknown` plus `signal is None` (`:333-338`). The named constructor test exercises false/zero/negative and fabricated killer/signal, but no append-path variant exists as required. Correction: add append and `validate_nbf_event` cases for each falsey/negative/fabricated value.
- **C15 — MET.** `WorkerDisposition.deterministic_id` includes signal and ladder step at `schema.py:296-298`; `test_term_and_kill_ladder_ids_are_distinct` passes.
- **C16 — MET.** `SemanticDispatchFingerprint.derive` filters `VOLATILE` fields at `schema.py:180-186`; `test_provider_key_and_fingerprint_exclude_volatile_identity` verifies logical ID and liveness digest invariance.
- **C17 — MET.** Provider failure key derivation uses phase/spec/class/epoch at `schema.py:220-239`, while route-liveness digest is volatile in the fingerprint. The provider/fingerprint test covers the narrow exclusion.
- **C18 — MET.** `reservation_key` excludes logical ID at `ledger.py:40-43`, and `reserve` compares the active key under `_locked` at `:536-553`. The real `multiprocessing` test `test_two_process_reservation_contention_one_winner` starts two OS processes and observes one winner.
- **C19 — NOT_MET.** Fixed reason checks exist in `ChangedPrecondition.__post_init__` (`schema.py:412-440`), but public `ChangedPrecondition.produce`, `produce_changed_precondition`, and `_producer` retain caller-controlled generic surfaces, including `**kwargs`, at `:452-475,547-565`. This violates the explicit alias/generic-producer prohibition. Correction: expose only fixed reason-specific producer contracts that do not accept producer identity as input.
- **C20 — NOT_MET.** `ChangedPrecondition.produce` hashes caller-provided `before`, `after`, and `evidence` at `schema.py:474-475`; it does not read authoritative source/registry/probe/repair state. `append_changed_precondition` only verifies that a cited event and digest exist (`ledger.py:616-628`). Correction: derive all identities from reason-specific authoritative sources and validate evidence type, subject, version, and binding under the ledger door.
- **C21 — NOT_MET.** `ChangedPrecondition.from_dict` validates shape and 64-hex format but not authoritative content (`schema.py:445-449`). `test_forged_valid_hex_content_ids_reject` changes only `after_content_id` without recomputing `event_id`, so it is malformed/inconsistent identity coverage, not a coherent valid forged event. Correction: add a forged-but-well-formed event with recomputed event identity and reject it by authoritative derivation; reject caller key transitions.
- **C22 — NOT_MET.** `consume_changed_precondition` compares and appends under `_locked` (`ledger.py:741-751`), and `reserve` sees consumed changes through replay (`:547-550`), but there is no required `test_consumed_change_cannot_authorize_second_reservation`, and producer authority remains forgeable. Correction: add the named second-reservation test and consume only a producer/evidence-bound event atomically with reservation.
- **C23 — NOT_MET.** `reserve_provider_route_child` checks a persisted provider authorizer and rejects reuse by authorizer ID (`ledger.py:630-654`), but it does not append a distinct consumption event or validate a canonical evidence-bound probe/recovery event, and the required recovery/child test is absent. Correction: require and consume one valid recovery authorization in the composite append and prove preserved streak plus one child.
- **C24 — NOT_MET.** `_project_records` has no changed-precondition provider-key before/after reduction; it only stores changes (`ledger.py:515-519`). Required key-changing/key-unchanged test is absent. Correction: apply selective reset/rekey only from an authoritative before/after provider-key transition.
- **C25 — MET.** `test_two_process_reservation_contention_one_winner` is an actual two-OS-process race over one on-disk ledger, and `reserve` now reads/compares/appends while holding the sequence-sidecar flock (`ledger.py:538-553`). It observed one winner and one reservation.
- **C26 — MET for record shape.** `reserve_provider_route_child` has no child receipt-ID argument and assembles one `provider_route_child_reserved` payload at `ledger.py:652-654`; validation rejects `child_admission_receipt_id` at `schema.py:677-678`. Authorization behavior remains deficient under C23.
- **C27 — UNEVIDENCED.** `derive_receipt` derives from the committed event at `ledger.py:656-658`, and `test_fresh_replay_receipt_is_byte_identical` reopens a ledger and reproduces an ordinary reservation receipt. It does not exercise a composite route-child event, and the required RW-06 crash boundary is absent. Correction: fresh-replay a composite event after append/receipt-derivation interruption.
- **C28 — UNEVIDENCED.** `test_torn_line_is_not_projected` covers one malformed JSON tail, but the required `test_torn_composite_write_exposes_neither_transition_nor_receipt` is absent and no failed append/fsync or composite crash injection exists. `_IncidentEventJournal._emit_locked` writes directly to the NDJSON path (`ledger.py:261-271`). Correction: inject torn/failed composite writes and assert neither route transition, reservation, projection, nor receipt is exposed.
- **C29 — NOT_MET.** In `_project_records`, terminal processing sets `reservations[key]["closed"] = True` before provider terminal projection (`ledger.py:492-500`). This contradicts the required terminal projection-before-closure invariant. Correction: make one terminal reducer transition project fingerprint/provider state first and close the bound reservation as part of the same authoritative transition.
- **C30 — NOT_MET.** Matching exhaustion increments a stream at `ledger.py:502-504`, but the stream is not keyed by the complete frozen projection key and no required matching keyed behavioral name exists. The existing test proves only one global-style stream reaches 2. Correction: add keyed matching observations across independent keys and assert only the applicable key increments.
- **C31 — NOT_MET.** A different provider-failure key gets a new dictionary stream and a default first observation at `ledger.py:498-504`, but there is no required nonmatching-key test and no complete projection-key binding. Correction: test explicit rekey-at-one and preserve independent streams.
- **C32 — NOT_MET.** Success resets all streams sharing the same base at `ledger.py:505-509`, not only the applicable key. The required success-isolation test is absent. Correction: reset exactly the applicable keyed stream and active key.
- **C33 — NOT_MET.** Ordinary failure/worker disposition sets `observation_streak=0` and `broken=True` for every same-base candidate at `ledger.py:510-514`; no required disposition behavioral test exists. Correction: break only the applicable stream, preserve typed disposition, and prove no degradation transition.
- **C34 — NOT_MET.** Probe/recovery events have no streak reducer branch, but route-child authorization is not evidence-bound/consumed as required and no recovery-preservation/one-child test exists. Correction: add the required probe/recovery test and locked single-use authorization.
- **C35 — MET as the NBF primitive.** `_project_records` mutates provider streams only for terminal outcomes; scheduling/no-launch/unresolved/time/liveness records have no reducer branch. End-to-end scheduler behavior is explicitly later-batch scope and was not changed.
- **C36 — NOT_MET.** `ReservationReconciled` only validates resolution membership and nonempty IDs (`schema.py:505-517`). `reconcile_reservation` checks `not_started` plus `controlled_adapter` (`ledger.py:664-681`) but accepts arbitrary marker IDs and has no positive persisted adapter binding, terminal recovery proof, or ambiguous-state proof. Correction: bind all reconciliation fields to the reservation and prove each legal resolution from authoritative ledger evidence.
- **C37 — NOT_MET.** No recovered-disposition path validates accepted terminal/disposition context or links one existing signal record; `reconcile_reservation` just appends the supplied reconciliation (`ledger.py:664-681`). Required recovery test is absent. Correction: require one matching committed disposition and create/link exactly one terminal outcome without another disposition/signal.
- **C38 — NOT_MET.** Identical/conflicting reconciliation handling is present under the lock (`ledger.py:671-675`), but blind release remains forgeable, and accepted/closed contradictory release is not fully rejected. Required conflict/replay and accepted-release test names are absent. Correction: reject non-authoritative evidence, accepted/closed release, and test atomic identical/conflicting replay.
- **C39 — NOT_MET.** Confirmation IDs bind identity fields (`disposition.py:32-33`), but `consume_confirmation` compares only optional caller values and prior evidence digest (`disposition.py:70-93`); omitted second-scan identity values are accepted. Replacement searches only same PID (`ledger.py:691-701`), expiry projection does not invalidate the active confirmation (`:525-529`), and no reopen/concurrent-consumer tests exist. Correction: ledger-owned equality, replacement, expiry, restart, and one-consumer CAS with required names.
- **C40 — NOT_MET.** NBF operations now generally use `_locked` and `_append_nbf_locked` (`ledger.py:405-465`), but there is no cache-mismatch authority, only partial projection-version checking, invalid records are filtered from projection, and the required fail-closed test is absent. Correction: validate schema/projection/cache state inside the existing lock for every transition and add fault tests.
- **C41 — NOT_MET.** Independent CLI subprocesses produced statuses 0/2/3/4/5, but no required CLI behavioral test exists; status 0 tested a non-worker record, and status 5 was only the missing-confirmation shortcut, not missing plus already-consumed confirmation. The status branches are in `disposition.py:96-141`. Correction: add the required subprocess tests, including consumed-confirmation rejection, and bind valid worker status 0 to a consumed confirmation.

### Batch 1 checkpoint bullets

- **CP01 — MET.** Exact focused command exited 0 with `78 passed in 1.53s`.
- **CP02 — NOT_MET.** Strict fields/legal transitions remain incomplete under C01, C02, C13, C14 evidence, and C36–C41.
- **CP03 — NOT_MET.** Kind mapping is lossless in the direct classifier, but exactly-once terminal/disposition linkage, full context binding, and concurrent proof are incomplete (C07, C09, C10).
- **CP04 — MET.** All owned primitives are methods on `IncidentLedger`; NBF writes use the existing `_IncidentEventJournal` sequence-sidecar flock and `_emit_locked`, with no second journal or store. Public aliases add forbidden surface but not a second durable authority.
- **CP05 — MET.** Only `worker_terminal_outcome` with `outcome_kind=provider_exhausted` enters the provider reducer (`ledger.py:492-504`); probes, waits, recovery records, ordinary failures, and dispositions do not increment it.
- **CP06 — NOT_MET.** Recovery authorization is not canonical evidence-bound locked consumption and has no required one-child/preserved-streak test.
- **CP07 — NOT_MET.** The current reducer is incomplete/global for applicable-key reset/rekey/intervention semantics.
- **CP08 — NOT_MET.** Composite shape and post-append derivation exist, but no composite fresh-replay/crash proof and no complete authorization proof exists.
- **CP09 — NOT_MET.** Kind/state distinctions exist, but illegal payload combinations remain accepted by `DispatchOutcome` and append validation.
- **CP10 — MET.** No second journal, store, prepare/commit protocol, scheduler, rotator, policy owner, or family-wide lease appears. The candidate reuses `_IncidentEventJournal`.
- **CP11 — NOT_MET.** Required crash, terminal race, confirmation race/reopen, keyed transition, producer-consumption, and CLI behavioral matrix is absent or incomplete.

## Rework task dispositions (RW-01…RW-06, RW-CUSTODY)

- **RW-01 — NOT_MET.** `IncidentLedger.reserve`, terminal, route-child, reconciliation, change-consumption, and probe paths use `_locked` and therefore improve the original unlocked compare defect (`ledger.py:536-681,741-759`). However six required RW-01 names are missing; terminal provider context intentionally skips logical ID (`:574-575`), empty reservation fields bypass binding (`:576-586`), reconciliation accepts arbitrary marker IDs (`:678-680`), and no recovered-disposition or two-process terminal proof exists. Smallest correction: remove compatibility/bypass checks, bind authoritative reservation evidence, and add the six missing behavior tests.
- **RW-02 — NOT_MET.** The basic kind/state, OOM, and unknown-death checks are implemented, and all seven RW-02 names exist. The incompatible-payload test is not a full matrix, unresolved/provider/failure cases remain open, `PhaseResult.from_dict` is permissive, and required append-path variants are absent. Smallest correction: close every payload combination at decode and `validate_nbf_event`/append, with matrix tests.
- **RW-03 — NOT_MET.** Fixed reason checks reject an explicitly forged producer kind and caller key transition, but generic `**kwargs` producers remain; authoritative IDs are hashes of caller values; forged valid IDs can be made self-consistent; and the consumed-change test is missing. Smallest correction: replace generic producers with source-reading reason-specific APIs, validate evidence/source bindings, and add atomic second-consumption coverage.
- **RW-04 — NOT_MET.** A partial `provider_streams` reducer exists, but it omits the complete projection-key contract, resets same-base streams broadly, ignores authoritative changed-precondition key transitions, and does not prove recovery authorization. Five required names are missing and the existing keyed test is only a dictionary-length assertion. Smallest correction: implement the complete keyed reducer and required behavioral cases without adding T8 policy.
- **RW-05 — NOT_MET.** Ledger locking and some identity/evidence checks exist, plus independent CLI statuses 0/2/3/4/5. Confirmation remains timestamp/evidence based when optional identity arguments are omitted; PID-change replacement and durable expiry/reopen behavior are incomplete; six required names are missing; status 0 is not a consumed worker disposition and status 5 already-consumed is untested. Smallest correction: make second-scan equality mandatory and durable under the ledger lock, then add the exact CLI/concurrency/reopen tests.
- **RW-06 — NOT_MET.** Focused/legacy/subset/compile/diff checks were rerun and the production digest reproduces, but the required torn-composite test is missing, the fresh receipt test is ordinary-reservation-only, and the executor finding is not a complete immutable transcript: it abbreviates argv and records no stdout SHA-256 per command. Smallest correction: add the missing behavioral regressions and publish complete command transcripts whose digests bind this exact candidate.
- **RW-CUSTODY — MET.** `.oracle/custody.md` SHA-256 is `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`; it labels `f8725af516da8d4249eb0d63563c37776d80daf8` historical and retains `798c50619204010ed3f4297fbb57988fe9381924` as current. The custody receipt SHA-256 is the expected `48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9`. No source/tasklist/plan change is part of this correction.

## North Star

### Four enduring principles

1. **One door per invariant — NOT_MET for the complete NBF contract; MET only for the narrow journal mechanism.** Candidate NBF methods reuse one `_IncidentEventJournal` and one sequence-sidecar flock (`ledger.py:405-465`), and no second durable store exists. But reservation/terminal/reconciliation/producer/confirmation semantics still contain bypasses and incomplete compare bindings. Physical admission/dispatch/death doors are correctly deferred, not satisfied by this batch.
2. **Deaths speak — NOT_MET as an end-state claim; partial foundation only.** Typed worker, observed-death, and non-worker records exist (`schema.py:242-380`), with positive OOM and explicit unknown-death constraints. NBF-01 correctly does not wire real signal sites, but the required repository-wide death behavior is therefore not evidenced here and append-path/identity coverage is incomplete.
3. **Models are admitted, not assumed — NOT_MET / deferred by scope.** No admission gate, catalog/family/live-provider caller was changed. That is correct NBF-01 scope discipline, not evidence that the North Star end state holds.
4. **Fixes ship on main through the fixer contract — NOT_MET / not yet evidenced.** HEAD is an uncommitted working-tree candidate; no commit, push, or main delivery exists. Later delivery owns that proof, and this review cannot authorize it.

### Anti-patterns

- **Single-scan truth — NOT_MET.** `consume_confirmation` at `disposition.py:70-93` accepts omitted identity fields and compares timestamps/evidence rather than requiring all second-scan PID, process-start, progress, supervisor/container incarnation, and cause values. Replacement/expiry are not fully durable.
- **Anonymous exits — NOT_MET as repository end state; partial typed primitive.** Typed disposition records and explicit `DispatchOutcome.kind=worker_disposition` exist, but real signal-site wiring is intentionally later and unknown-death/CLI coverage is incomplete. No NBF-01 scope exception turns this into a complete North Star pass.
- **Judgment-based healthy claims — NOT_MET.** Reconciliation accepts caller-shaped marker IDs (`ledger.py:678-680`), and confirmation can omit identity values on consumption. A schema-shaped confirmation is not positive sustained proof.
- **Identical-fingerprint redispatch — NOT_MET.** Same-key two-process reservation now contends, but changed-precondition identities derive from caller inputs (`schema.py:452-475`), producer APIs remain generic, and reconciliation/terminal binding holes prevent trusting the complete durable block.

## KISS / YAGNI / scope

- **Speculative abstractions — NOT_MET.** `schema.py:452-475,547-565` retains a generic producer plus `**kwargs`; `disposition.py:36-46` exposes generic constructor surfaces. These surfaces make the contract harder to audit without providing authoritative source binding.
- **Duplicate doors — PARTIAL / NOT_MET for transaction ownership.** There is one journal class and one physical NBF append mechanism (`ledger.py:201-271,405-465`), which is good. The public `append_event` legacy path is a separate legacy event API, not a second NBF authority; however pre-compare wrappers and aliases obscure the single contract, and some semantic checks still occur outside the locked helper (`disposition.py:70-90`).
- **Ceremonial validation — NOT_MET.** 36 new collected tests plus 42 unchanged tests produce green 78, but required races, composite crash, forged coherent hashes, keyed isolation, confirmation restart/consumer, and CLI named tests are absent. The focused count is not acceptance evidence by itself.
- **Generic frameworks — MET.** No UnitOfWork, two-phase protocol, second journal/store, scheduler, rotator, or family lease was added. The implementation reuses `_IncidentEventJournal` and `_emit_locked`.
- **Later-batch behavior — MET.** No admission callers, dispatch loops, T7/T8 policy, physical doors, launch adapters, signal-site wiring, provider fallback decisions, or later-batch production paths appear in the owned diff.
- **Scope — MET.** Candidate source/test paths are exactly the five modified production files, `incident/disposition.py`, and eight new test modules. `.oracle` changes are protected noise, not silently ignored clean-tree claims.

## Evidence integrity

Frozen identities independently match the requested values for North Star, plan v8,
frozen tasklist, rework tasklist, source base, branch, and planning HEAD. The
current custody digest and custody receipt digest match the requested values.
The candidate production diff digest independently reproduces the executor's
post-rework claim. All nine owned untracked files have independently recorded
git-object and raw SHA-256 identities above. The unchanged legacy test was
verified against `origin/main`.

The historical integrity problems remain historical and were not rewritten:

- The original start-gate receipt claimed focused **52**, and the same historical
  path later mutated to **61**. Independent current reproduction is **78 focused**
  and **78 legacy** after rework; the count is an observation, not a target.
- The prior owned-source digest `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
  remains unreproducible and is not substituted with the current digest.
- Prior independent Luna's failed-handoff digest
  `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf` remains a
  historical snapshot, not the post-rework digest.

The new executor receipt is internally consistent about the post-rework count
and production digest, but its companion finding abbreviates command argv and
does not bind stdout hashes. The independent transcript files listed above bind
the commands reviewed here to the candidate. No production/test/plan/frozen
artifact/custody/history file was mutated by this review before these digests;
only the two explicitly authorized output files are written.

## Issues

1. **blocker — incomplete one-door CAS and reservation-bound terminal/reconciliation contract.** Exact symbols: `IncidentLedger.append_terminal_outcome`, `reconcile_reservation`, `reserve_provider_route_child`, and the required missing RW-01 tests. Evidence: provider exhaustion skips logical identity (`ledger.py:574-575`), empty reservation fields bypass comparison (`:576-586`), release accepts arbitrary controlled-adapter IDs (`:678-680`), and no concurrent terminal linkage test exists. Smallest correction: bind every field to persisted reservation state, prove authoritative reconciliation evidence, and add the missing OS-process/race/idempotency regressions.
2. **blocker — strict schema and payload matrix remains incomplete.** Exact symbols: `DispatchOutcome.__post_init__`, `PhaseResult.from_dict`, `validate_nbf_event`, and disposition append paths. Evidence: incompatible payloads remain accepted at `phase_result.py:159-183`; `PhaseResult.from_dict` defaults/ignores fields at `:607-640`; append-path variants and the full matrix are absent. Smallest correction: enforce the complete matrix and typed/versioned identity rules at every decode/append door, with the exact RW-02 tests.
3. **blocker — changed-precondition producers remain caller-forgeable.** Exact symbols: `ChangedPrecondition.produce`, `produce_changed_precondition`, `_producer`, `append_changed_precondition`. Evidence: caller `before`/`after` are hashed directly (`schema.py:452-475`), generic `**kwargs` remains (`:547-565`), and the valid-hex forge test is not coherent. Smallest correction: fixed reason-specific authoritative producers plus evidence/source/provider-key binding and atomic single consumption.
4. **major — keyed provider replay and recovery mechanics are incomplete.** Exact symbol: `IncidentLedger._project_records` (`ledger.py:476-531`) and route-child reservation (`:630-654`). Evidence: complete projection key is absent, intervention resets broad same-base streams, changed-precondition transitions are ignored, and required RW-04 behavior names are missing. Smallest correction: implement complete keyed reduction and one evidence-bound recovery child without T8 policy.
5. **major — durable two-scan confirmation and CLI acceptance evidence are incomplete.** Exact symbols: `consume_confirmation`, `IncidentLedger.observe_confirmation`, `expire_confirmation`, `_record_cli`. Evidence: optional identity fields permit timestamp-only consumption (`disposition.py:70-93`), replacement is PID-limited (`ledger.py:691-701`), expired projections remain live (`:525-529`), and required reopen/concurrency/CLI names are absent. Smallest correction: require all equality fields, durable replacement/expiry/replay and one-consumer CAS, then add exact status 0/2/4/5 and already-consumed tests.
6. **major — crash/replay and immutable evidence protocol is incomplete.** Exact criterion: C27/C28, RW-06. Evidence: only a malformed-line test exists; required torn-composite test is absent; fresh replay is ordinary-reservation-only; executor finding has abbreviated commands/no stdout hashes. Smallest correction: inject composite write/receipt crash boundaries and publish complete per-command digests.
7. **minor — prohibited aliases and generic constructor surfaces remain.** Exact symbols: `IncidentLedger.append_worker_disposition`, `write_terminal_outcome`, `reserve_admission`, `reconcile`, `replay_projection` (`ledger.py:768-772`) and generic disposition constructors (`disposition.py:36-46`). Evidence: supplemental tasklist explicitly requires deletion of aliases that do not enforce a frozen symbol contract. Smallest correction: remove aliases unless a frozen downstream symbol requires one; use explicit typed constructors.

## Recommendation

The candidate passes the focused and legacy commands, has the requested source
scope, and materially improves locking and basic schema checks. It does not pass
the frozen Batch 1 gate: required behavioral names are missing, multiple named
cases are ceremonial or malformed-only, terminal/reconciliation binding is still
forgeable, producer authority is caller-controlled, provider replay is not fully
keyed, confirmation is not a complete two-scan proof, and composite crash
coverage is absent. Do not commit, advance Batch 2, or treat the green count as a
waiver.

RECOMMEND_ACCEPTED_ISSUES
