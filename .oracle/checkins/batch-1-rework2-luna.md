# Luna independent review — NBF-01 / Batch 1 rework 2

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: 922241d0bdb3e993c3b554cc69f19948adef7bc3
- Merge-base: 798c50619204010ed3f4297fbb57988fe9381924
- Tasklist SHA-256: 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
- Plan v8 SHA-256: 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
- North Star SHA-256: d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
- Rework tasklist SHA-256: 6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721
- Attempt-1 rework tasklist SHA-256: 5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c
- Executor receipt: `.oracle/receipts/execution-nbf01-rework2-luna.md`
- Executor receipt SHA-256: d03d259725484d4eac22cae1e2582288a85a2d2dbfbbba7a2b0878b9b02e51
- Executor finding: `.oracle/findings/execution-nbf01-rework2-luna.md`
- Executor finding SHA-256: 896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb
- Custody receipt SHA-256: 48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9
- Current custody SHA-256: 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0
- Owned production diff SHA-256: 16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d
- Focused pytest: exit 0, 101 passed in 14.11s; stdout SHA-256 `1996f644e0e8cea7e6cc65ae3b0b8215b9a139b9996049bcb91160cc25f85292`; stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Legacy pytest: exit 0, 78 passed in 1.52s; stdout SHA-256 `a96ce9348b20653cb0c42b3ca9a255dd7cad88327a9c7506d2017b889095c310`; stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Test collection: 59 tests from the eight new modules and 42 tests from unchanged `test_incident_ledger.py`; total focused collection 101. The count is an observation, not a target.
- CLI statuses: independent subprocess transcripts under `/tmp/oracle-nbf01-rework2-luna/`; status 0/2/3/4/5 all reached with complete argv, cwd, exit, stdout, stderr, and byte hashes.
- py_compile: exit 0, empty stdout/stderr; both SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- git diff --check: exit 0, empty stdout/stderr; both SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Scope and diff

Identity capture from the reviewed worktree:

```text
HEAD       922241d0bdb3e993c3b554cc69f19948adef7bc3
origin/main 798c50619204010ed3f4297fbb57988fe9381924
merge-base 798c50619204010ed3f4297fbb57988fe9381924
branch     megado-nbf-guard-0826
```

`git diff --name-status origin/main -- arnold_pipelines tests` contains exactly the five permitted modified production files:

```text
M arnold_pipelines/megaplan/incident/__init__.py
M arnold_pipelines/megaplan/incident/ledger.py
M arnold_pipelines/megaplan/incident/schema.py
M arnold_pipelines/megaplan/orchestration/phase_result.py
M arnold_pipelines/megaplan/orchestration/phase_result_classify.py
```

The permitted owned untracked files are `incident/disposition.py` and the eight named new test modules. Independent `git hash-object` / raw SHA-256 pairs are:

```text
arnold_pipelines/megaplan/incident/disposition.py
  5fb675a96d0ce096af881a3feadcdc8b31c8cc65
  8212c519d1afcaba5f4fa9aa3be7a23d753ec2ad5ed9662572c79b457af0b38a

tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
  b6cedc6cb4f7d806e95c41339930a4a9f6803363
  79d59501de3d3f11924b86764f757629de312064d3e06f2f84477a5e19dca547

tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
  d45fb936d69f90954f09e267662e50503e6b62f0
  522903756431534096d2d0d1205834b878b0cbfa33a166229ff4fcd0ac65f5a4

tests/arnold_pipelines/megaplan/test_provider_route_projection.py
  e3fe6f278345eadae1a2335d912ee97ac78d790b
  c644f550273afde279d5adff4527c5821a8850c24a3b46019832ec956b39fa0c

tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
  be6bee9ff18e6ae9343e843095ddd7f67429af72
  a013b4d2de9e43857cc5cdc12bd9a304177bee0f536d1d3eac6817f0047a48eb

tests/arnold_pipelines/megaplan/test_scheduling_conditions.py
  fc54999a025f23d89860facda94b260d1d7e5bb3
  2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb

tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
  1bf257c63450a6fe7214625dffbbeff44b6ee46b
  7b2e40eafde4e3fca4cbf6831337455d7e138bf8cf4155c5544c0d0ff0978759

tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
  0fd46e4d02c1aa89be265291e256d6fca705472a
  7fd0fedcb70251c62a04abdc2456365172c8fc3a72b3af909973ba19d0cb8497

tests/arnold_pipelines/megaplan/test_worker_disposition.py
  ed2f3281e72c624fed7ea1eaf0cb4fc317119b4f
  a75ec92d7426b794c24567ce00cbb09040edc2cbc289e77a3ff528ec81b38991
```

`test_incident_ledger.py` is unchanged versus `origin/main` (`git diff --quiet` exit 0). The `.oracle` modifications and protected planning artifacts are dirty non-owned noise; I do not claim a clean tree by ignoring them. No later-batch production path is in the owned source diff.

The five frozen artifact hashes match the required identities. The executor receipt and finding hashes match the required identities. The executor receipt does not record an explicit candidate HEAD, and its per-command table records stdout hashes but not stderr hashes; the companion finding does not provide a complete per-command immutable evidence record in the receipt itself. My independent transcripts do.

## Independent validation evidence

The exact frozen focused command exited 0 with the complete stdout:

```text
........................................................................ [ 71%]
.............................                                            [100%]
101 passed in 14.11s
```

The exact frozen legacy command exited 0 with:

```text
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 1.52s
```

Adversarial subsets also exited 0:

- transactions `-k "two_process or torn or crash or contention"`: `5 passed, 8 deselected in 1.77s`, stdout SHA `ac1b5f4cee6d37390bb37b3914c5289695e19fbebfbc62d1660d7d64140b7d66`;
- provider `-k "replay or receipt or keyed"`: `4 passed, 6 deselected in 0.25s`, stdout SHA `79993755e5d9f5e2813be8e4549013ef9294fb0405ef72f4101c82496b487e30`;
- confirmation `-k "cli or confirmation or incarnation or reopen"`: `6 passed in 0.29s`, stdout SHA `fd14cdc4324f99c94e1c223a45b4157339986c37c6aa682625e9d58908d92420`.

Independent CLI transcripts:

| Status | Transcript | Result | stdout SHA-256 | stderr SHA-256 |
|---:|---|---|---|---|
| 0 | `cli_status_0b.json` | one JSON acknowledgement; consumed identity-matching worker confirmation; no signal | `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 2 | `cli_status_2b_malformed.json` and `cli_status_2b_schema.json` | malformed JSON and schema-invalid payload both return 2 before confirmation shortcuts | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` / same | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` / `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` |
| 3 | `cli_status_3b.json` | valid ledger root whose `events.jsonl` is a directory returns append failure 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `06678ba61b7788bb53c26e0abad3c8b4898a7ef458305ee30e40e604356af7dd` |
| 4 | `cli_status_4b.json` | file supplied as ledger root returns invalid-location 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` |
| 5 | `cli_status_5b_missing.json` and `cli_status_5c_consumed_mismatch.json` | missing and differently-consumed confirmation return 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` / same | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` / `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655` |

The CLI status-0 implementation is non-signalling, and the direct subprocess uses `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python` with `VIRTUAL_ENV` removed because that is the working Python 3.11.11 installation. All transcript files contain full argv, cwd, exit status, verbatim stdout/stderr, and hashes.

## Criterion dispositions (C01–C41, CP01–CP11)

Statuses are `MET`, `NOT_MET`, or `UNEVIDENCED`. A green suite is never used as sole proof where the frozen contract requires a behavioral hole test.

### NBF-01 criteria

- **C01 — NOT_MET.** Exact symbols: `DispatchOutcome.from_dict` / `SchedulingCondition.from_dict` in `orchestration/phase_result.py:141-208` and `validate_nbf_event` in `incident/schema.py:700+`. Evidence: top-level strict fields exist and the focused collection contains six outcome-kind cases, but no valid six-kind round-trip matrix exists; `test_dispatch_outcome_incompatible_payload_matrix` is rejection-only. Smallest correction: add valid round-trips plus missing/unknown-field and append-path coverage for every six kind and scheduling condition.
- **C02 — NOT_MET.** Exact symbols: `DispatchOutcome.__post_init__` `phase_result.py:159-198`. Evidence: ordinary failure plus `success_payload` and provider exhaustion plus `terminal_failure` are rejected and tested, but `worker_disposition` still accepts `success_payload` at lines 169-173; the named matrix does not exercise all incompatible families. Smallest correction: reject every incompatible payload, including worker-disposition success payload, and make the named test a complete matrix at constructor, decode, and append boundaries.
- **C03 — MET.** Exact symbol: `DispatchOutcome.__post_init__` `phase_result.py:151-155`. Evidence: `test_no_launch_rejects_accepted_launch_state` raises `ValueError`; direct state map also rejects it.
- **C04 — MET.** Exact symbols: `DispatchOutcome.__post_init__` `phase_result.py:156-171` and `WorkerDisposition.__post_init__` `schema.py:311-329`. Evidence: `test_worker_disposition_round_trip_and_distinct_outcome` constructs the required accepted receipt/fingerprint/phase/spec/logical/worker/timing shape; constructors require disposition and worker context.
- **C05 — MET.** Exact symbols: `DispatchOutcome.__post_init__` `phase_result.py:159-173,188-191`. Evidence: no-launch/unresolved reject worker/provider/disposition payloads and worker disposition rejects provider and ordinary-failure payloads; the named matrix exercises these families. The C02 success-payload gap is separate.
- **C06 — MET.** Exact symbol: `terminal_outcome_kind` in `phase_result_classify.py:204-218` plus `IncidentLedger.append_terminal_outcome` `ledger.py:651-718`. Evidence: `worker_disposition` is returned unchanged and terminal payload uses `outcome.kind`; no ordinary-failure coercion branch exists.
- **C07 — MET.** Exact symbol: `IncidentLedger.append_terminal_outcome` `ledger.py:688-694`. Evidence: a previously committed disposition is required and receipt/fingerprint/phase/spec/logical/worker fields are compared; `test_recovered_disposition_links_existing_record_without_duplicate` and `test_disposition_terminal_links_existing_record_once` prove one existing disposition and no second terminal append. Concurrent terminal evidence is deficient under C09, and accepted-launch proof is deficient under C10.
- **C08 — MET.** Exact symbols: `DispatchOutcome.__post_init__` `phase_result.py:174-181` and `terminal_outcome_kind`. Evidence: `test_outcome_never_coerces_disposition_to_failure` rejects a disposition ID on ordinary failure; classifier preserves the typed kind.
- **C09 — NOT_MET.** Exact symbol: `IncidentLedger.append_terminal_outcome` `ledger.py:695-713`; test `test_two_process_terminal_linkage_is_atomic` in `test_incident_ledger_transactions.py:81-103`. The test uses two OS processes, but both pass the same outcome and therefore the same deterministic terminal ID; event-ID idempotency alone makes it pass and it never races distinct terminal IDs/kinds. Smallest correction: use a synchronization barrier and distinct terminal IDs/kinds against one reservation, then assert one committed terminal and a conflict/idempotent loser.
- **C10 — NOT_MET.** Exact symbols: `IncidentLedger.append_terminal_outcome` `ledger.py:659-718` and `_project_records` `ledger.py:544-575`. Evidence: context fields are compared under `_locked`, but no persisted `controlled_adapter_state` with `launch_state=accepted` is required; `accepted_launch` is set only while replaying the terminal itself. Independent source probe `/tmp/oracle-nbf01-rework2-luna/manual_source_probes.json` returned `"terminal_without_persisted_accepted_marker":{"accepted":true,...}`. Smallest correction: require one persisted, receipt-bound accepted launch marker before terminal append and test all reservation-field mismatches.
- **C11 — NOT_MET.** Exact symbol: `_project_records` `ledger.py:494-569`. Evidence: streams are keyed by a provider key, but success and ordinary/disposition outcomes select `latest_stream_key` using only `active_base`, not the outcome's applicable provider/projection key. The independent provider probe created two exhaustion observations for key A, one for key B, then recorded success for A; output left A at streak 2 and reset B to 0. Smallest correction: persist and resolve the applicable projection/provider-failure key for every terminal, then mutate only that stream; add value/isolation tests that target the non-latest stream.
- **C12 — MET.** Exact symbols: `DispatchOutcome` kind/state map and `IncidentLedger.append_terminal_outcome` `ledger.py:657-658`. Evidence: no-launch and unresolved outcomes are rejected by the worker-terminal writer; `_project_records` has no provider-terminal branch for them. Scheduler/breaker transport is later-batch scope.
- **C13 — NOT_MET.** Exact symbols: `WorkerDisposition.__post_init__`, `ObservedProcessDeath.__post_init__`, `NonWorkerSignalDisposition.__post_init__`, and `validate_nbf_event` in `schema.py:281-427,700+`. Evidence: version and enum checks exist, but worker fingerprint is only a non-empty string, worker identity accepts any non-empty dict, observed context has no typed identity schema, and non-worker cause accepts every `CauseKind` including worker-specific causes. The named test checks selected constructor and append failures only, not complete append identity coverage. Smallest correction: enforce canonical fingerprint/PID/process identity and subject-specific enum/identity constraints at decode and append, with exhaustive append tests.
- **C14 — NOT_MET.** Exact symbols: `_positive_cgroup_delta` and observed-death constructor `schema.py:127-132,368-384`. Evidence: positive cgroup evidence now requires `positive is True` and finite `delta > 0`; unknown death requires `external_unknown` and `signal is None`. However `test_unknown_death_rejects_fabricated_killer_and_signal` appends only the fabricated killer variant, not fabricated signal, and no append/`validate_nbf_event` matrix covers every falsey/negative/fabricated case. Smallest correction: add append-path tests for false/zero/negative OOM and both unknown killer and signal, and retain the strict constructor rules.
- **C15 — MET.** Exact symbol: `WorkerDisposition.deterministic_id` `schema.py:339-341`. Evidence: `test_term_and_kill_ladder_ids_are_distinct` passes and signal plus ladder step are in the digest.
- **C16 — MET.** Exact symbols: `SemanticDispatchFingerprint.VOLATILE` and `derive` `schema.py:205-237`. Evidence: `test_provider_key_and_fingerprint_exclude_volatile_identity` proves logical-ID and route-liveness changes do not change the fingerprint.
- **C17 — MET.** Exact symbols: `ProviderFailureKey.derive` `schema.py:259-277` and fingerprint volatile set. Evidence: provider key components are phase/spec/failure class/epoch; route-liveness digest is excluded; named provider/fingerprint test passes.
- **C18 — MET.** Exact symbols: `reservation_key` `ledger.py:29-36` and locked `reserve` `ledger.py:611-649`. Evidence: `test_two_process_reservation_contention_one_winner` uses `multiprocessing` with one on-disk ledger and observes one winner; logical ID is not in the reservation key.
- **C19 — NOT_MET.** Exact symbols: `ChangedPrecondition.produce` `schema.py:515-539`, `produce_changed_precondition`, and `_produce_reason_specific`. Evidence: reason-specific wrappers still route through one caller-controlled generic producer; callers may supply `before`, `after`, evidence, subject, and optional producer identity. Only mismatched producer identity is rejected. Smallest correction: expose only fixed reason-specific producers and remove the generic producer authority surface.
- **C20 — NOT_MET.** Exact symbols: `ChangedPrecondition.produce` `schema.py:538-539` and `IncidentLedger.append_changed_precondition` `ledger.py:730-744`. Evidence: content IDs are hashes of caller-provided snapshots; append verifies only that `evidence_snapshot` equals a persisted event and its digest, not the reason-specific authoritative source/evidence type/provider binding. Smallest correction: producers must read the authoritative source and cited event and the ledger must validate the fixed reason/evidence/subject/provider-key contract.
- **C21 — NOT_MET.** Exact symbols: `ChangedPrecondition.__post_init__` `schema.py:465-504` and append path `ledger.py:730-744`. Evidence: the required test mutates `after_content_id` to `"a"*64` without recomputing `event_id`, so it is inconsistent-identity coverage only. Independent source probe accepted a forged valid provider-key transition constructed by `from_dict` with recomputed-valid component hashes, returning `"forged_provider_transition":"accepted"`. Smallest correction: reject coherent forged content/key identities by deriving them from authoritative sources in append/consume.
- **C22 — MET.** Exact symbol: `consume_changed_precondition` `ledger.py:934-944` and reservation consumption in `reserve` `ledger.py:622-631`. Evidence: both operate under `_locked`; `test_consumed_change_cannot_authorize_second_reservation` consumes one valid change in a first reservation and proves a second authorization raises. The producer authority defects remain C19-C21.
- **C23 — NOT_MET.** Exact symbol: `reserve_provider_route_child` `ledger.py:746-775`. Evidence: the method checks a persisted changed-precondition and rejects a repeated authorizer, but it does not verify a successful canonical probe result, authorizer plan/phase/provider binding, or a distinct authoritative consumption event. `test_recovery_authorization_single_use_across_different_children` uses `append_probe_result` with an arbitrary lease and caller-supplied keys, then checks only one child. Smallest correction: require a passed, persisted, evidence-bound recovery event matching the parent and consume it atomically in the composite append.
- **C24 — NOT_MET.** Exact symbol: `_project_records` changed-precondition branch `ledger.py:576-585`. Evidence: it rekeys every matching stream from caller-carried before/after keys; there is no authoritative provider-key binding and no targeted test proving key-changing versus key-preserving behavior. The named test itself mutates provider-key fields with `from_dict` and appends them. Smallest correction: validate authoritative before/after keys and mutate only the applicable stream when they differ; preserve the stream when equal.
- **C25 — MET.** Exact symbol: locked `reserve` `ledger.py:613-649` and two-process test `test_two_process_reservation_contention_one_winner`. The adversarial subset passes `5 passed, 8 deselected`; the reservation test uses two OS processes and one real ledger directory.
- **C26 — MET for event shape.** Exact symbol: `reserve_provider_route_child` `ledger.py:746-775` and `validate_nbf_event` composite branch. Evidence: the composite event has one append, no child receipt-ID parameter, and `test_fresh_replay_composite_receipt_is_byte_identical` reopens and derives the same receipt. Authorization defects are C23, not the record-shape claim.
- **C27 — NOT_MET.** Exact symbols: `derive_receipt` `ledger.py:777-779` and provider-route tests. `test_fresh_replay_receipt_is_byte_identical` is still an ordinary reservation test, while the composite test has a different name; the required same-name behavioral contract explicitly requires the composite case. No interruption between composite append and receipt derivation is tested. Smallest correction: make `test_fresh_replay_receipt_is_byte_identical` exercise a composite event and add post-append/pre-derivation replay interruption coverage.
- **C28 — NOT_MET.** Exact symbols: `_IncidentEventJournal._emit_locked` `ledger.py:213-271` and `_read_records`. `test_torn_composite_write_exposes_neither_transition_nor_receipt` merely writes an incomplete generic JSON prefix and reopens it; it never creates a parent/authorizer/composite event or injects failure during `_emit_locked`. Smallest correction: inject a partial composite write and append/fsync/crash boundary, then assert neither route transition, child reservation, projection, nor receipt appears.
- **C29 — MET for projection ordering.** Exact symbol: `_project_records` terminal branch `ledger.py:544-575`. Evidence: provider/fingerprint reduction runs before `reservations[key]["closed"] = True`; terminal append is one committed event. The lack of persisted accepted-launch proof is separately C10.
- **C30 — MET for matching stream mechanics.** Exact symbol: `_project_records` `ledger.py:552-562`. Evidence: `test_keyed_streak_replay_matching_different_and_success` appends two accepted exhausted outcomes with the same canonical provider key and observes streak 2 after reopen; independent streams are also asserted at value 1 in `test_provider_streak_is_keyed_not_global`. Full isolation failures are C11/C32/C33.
- **C31 — MET for first observation of a nonmatching key.** Exact symbol: `_project_records` `ledger.py:552-562`. Evidence: `test_nonmatching_key_rekeys_at_one` asserts both old and new provider-key stream values are 1. It does not cure incomplete applicable-key selection.
- **C32 — NOT_MET.** Exact symbol: `_project_records` `ledger.py:563-566`. Evidence: success with no provider key selects the latest stream for the active base, not the applicable stream. The independent provider probe recorded success for A after B was latest and left A at 2 while B became 0. Smallest correction: carry applicable provider-failure-key identity into success terminal context and reset only that stream.
- **C33 — NOT_MET.** Exact symbol: `_project_records` `ledger.py:567-569`. Evidence: ordinary/disposition outcomes use the same latest-stream fallback, so an intervening disposition can break the wrong stream. The named disposition test covers only one stream and cannot expose this. Smallest correction: target the applicable keyed stream and add two-stream ordinary/disposition isolation with explicit no-degradation assertions.
- **C34 — NOT_MET.** Exact symbols: provider event branches in `_project_records` `ledger.py:576-588` and route-child `ledger.py:758-772`. Evidence: probes have no streak reducer branch, but recovery creation/consumption is not authoritative or fully bound; `test_recovery_authorization_single_use_across_different_children` does not begin with a live keyed streak plus a canonical passed probe. Smallest correction: add evidence-bound passed-probe/recovery projection and one-child tests that preserve the live key/value.
- **C35 — MET as the NBF-01 primitive.** Exact symbol: `_project_records` terminal branch `ledger.py:544-569`. Evidence: scheduling/no-launch/unresolved records have no provider-observation reducer branch; `test_scheduling_condition_is_lossless_through_phase_result` and focused suite pass. Scheduler and breaker behavior are later-batch scope.
- **C36 — NOT_MET.** Exact symbols: `ReservationReconciled.__post_init__` `schema.py:570-590` and `reconcile_reservation` `ledger.py:785-832`. Evidence: ledger binding and missing arbitrary evidence rejection are improved, but a generic `controlled_adapter_state` appended through private `_append_nbf` is accepted as positive proof; no persisted sequencing provenance proves it was written before launch capability. `test_conflicting_reconciliation_rejected_identical_replay_idempotent` constructs its marker directly. Smallest correction: require a persisted authoritative controlled-adapter transition bound to the reservation and legal sequence, and prove recovered terminal/disposition evidence.
- **C37 — NOT_MET.** Exact symbol: `reconcile_reservation` `ledger.py:819-826`. Evidence: recovered-disposition test appends the terminal first and then reconciles it; the method checks disposition presence but does not itself establish or fully match the recovered disposition context, and no recovery-after-disposition-only path exists. Smallest correction: require one matching persisted disposition plus accepted terminal context and make recovery idempotent without writing a second disposition or signal.
- **C38 — NOT_MET.** Exact symbols: `reconcile_reservation` `ledger.py:792-832`. Evidence: conflict/idempotent replay is tested, and blind missing evidence is rejected, but accepted/closed/no-launch contradiction and authoritative marker provenance are not fully covered. Smallest correction: reject every release after accepted/closed state and require positive bound sequencing evidence, with distinct accepted-launch and closed-reservation tests.
- **C39 — NOT_MET.** Exact symbols: `consume_confirmation` `disposition.py:54-88`, `IncidentLedger.consume_confirmation` `ledger.py:891-916`, and confirmation projection `ledger.py:594-604`. Evidence: source compares all five identity fields under the lock and rejects omitted helper arguments, and replacement/expiry/reopen/single-consumer names exist. The required same-name test only supplies a process-start mismatch; it does not independently mutate PID, progress, supervisor/container incarnation, cause, or omit each identity. CLI expiry is not named. Also `expire_confirmation` has no consumed-state guard and its projection can overwrite `consumed=True` with `False`. Smallest correction: strengthen the named matrix for each identity and omitted argument, reject expiry of consumed confirmations, and test CLI expired/already-consumed behavior.
- **C40 — NOT_MET.** Exact symbols: `_locked`, `_append_nbf_locked`, `_project_records`, and `read_nbf_events` `ledger.py:371-480`. Evidence: operations now compare after the sequence-sidecar flock and invalid NBF payloads raise from replay (`test_invalid_replay_record_never_projects`), but there is no cache-mismatch authority or complete projection-version CAS for every transition; the named fail-closed test checks only reservation version mismatch. Smallest correction: validate the authoritative projection/cache/version for every transition inside the existing lock and add append/fsync/cache fault cases.
- **C41 — NOT_MET.** Exact symbol: `_record_cli` `disposition.py:92-167` plus `append_disposition` `ledger.py:720-728`. Evidence: independent subprocesses reached 0/2/3/4/5 and status 0 used a consumed matching worker confirmation. The named test covers status 2, 3, 4, missing and differently-consumed 5, but not expired CLI 5 or a fully distinct already-consumed replay; CLI confirmation checks also begin from a read-only projection before the append recheck. Smallest correction: complete the named status-5 matrix, including expired and already-consumed cases, and keep schema-before-confirmation plus locked identity validation.

### Batch 1 checkpoint bullets

- **CP01 — MET.** Exact focused command exited 0 with 101 passed. This is the necessary gate only, not sufficient proof.
- **CP02 — NOT_MET.** C01/C02/C13/C14 and C36-C41 remain incomplete.
- **CP03 — NOT_MET.** Typed worker-disposition mapping is lossless and does not reappend the disposition on the direct path, but terminal accepted-launch context and distinct concurrent linkage are not proven (C09/C10).
- **CP04 — MET for the single ledger authority.** All NBF methods use `IncidentLedger`, `_IncidentEventJournal`, and the sequence-sidecar flock; no second NBF journal/store or transaction framework exists. Incomplete field bindings are separate criterion failures.
- **CP05 — MET.** Only accepted `worker_terminal_outcome` with `outcome_kind=provider_exhausted` enters the provider reducer. Scheduling, no-launch, unresolved, probes, recovery records, ordinary failure, and disposition do not increment it.
- **CP06 — NOT_MET.** Recovery authorization is not fully evidence-bound and single-use in the required canonical child contract.
- **CP07 — NOT_MET.** Matching/rekey mechanics exist, but success/disposition targeting and authoritative key-change behavior fail C11/C24/C32/C33.
- **CP08 — NOT_MET.** Composite shape and a differently named replay test exist; required same-name composite replay, crash/torn-write, and authorization proof are incomplete.
- **CP09 — MET for mechanical type/state distinction.** `no_launch` and `unresolved_launch` are separate from accepted terminal kinds and the terminal writer rejects them; full payload strictness is C02.
- **CP10 — MET.** No second journal, store, prepare/commit protocol, scheduler, rotator, family lease, or T8 policy owner appears in the owned diff.
- **CP11 — NOT_MET.** The full crash, terminal-race, coherent-forgery, keyed isolation, confirmation, CLI, and append-path matrix is not proven.

## Rework task dispositions (RW2-01…RW2-04, RW-CUSTODY)

- **RW2-01 ledger door — NOT_MET.** The existing lock/read/compare/append seam is real and reservation contention passes with two OS processes. The terminal writer accepts an outcome without a persisted accepted-launch marker; changed-precondition key fields remain caller-forgeable; and the full strict append matrix is incomplete. Required tests are present but several are weak or do not exercise the frozen hole.
- **RW2-02 keyed provider replay mechanics — NOT_MET.** Provider streams exist and matching/nonmatching basic values pass, but success and disposition mutate the latest stream rather than the applicable stream. Recovery/probe preservation is not evidence-bound. The required same-name `test_fresh_replay_receipt_is_byte_identical` still covers an ordinary reservation, while the composite case has another name.
- **RW2-03 durable confirmation and CLI — NOT_MET.** The core ledger lock and identity comparisons are materially improved, and independent CLI 0/2/3/4/5 subprocesses pass. The required named identity matrix is thin, expiry can overwrite consumed state, and CLI status-5 coverage lacks expired and distinct already-consumed replay cases.
- **RW2-04 behavioral regressions, aliases, evidence — NOT_MET.** The torn-composite test is only a malformed-line test; same-name receipt replay is ordinary-only; the executor receipt omits explicit candidate HEAD and per-command stderr hashes; and no complete changed-file inventory is bound in the receipt. Listed legacy aliases/constructors are gone, but the generic `ChangedPrecondition.produce` authority surface remains.
- **RW-CUSTODY — MET.** `.oracle/custody.md` is the expected `94df44...` and explicitly labels `f8725af516da8d4249eb0d63563c37776d80daf8` historical while retaining `798c50619204010ed3f4297fbb57988fe9381924` as current. The custody receipt is the expected `48f540...`. I did not edit custody.

## Preserved prior-MET result

Preserved and independently confirmed:

- one `_IncidentEventJournal` with the sequence-sidecar `fcntl.flock`; NBF writes enter `_locked` / `_append_nbf_locked`;
- C03, C04, C05, C06, C08, and C12 typed distinctions;
- C15 TERM/KILL deterministic IDs;
- C16 semantic fingerprint volatile exclusions and C17 route-liveness exclusion;
- C18/C25 real two-process reservation contention, now using a locked compare/append;
- C26 composite record shape with no child receipt-ID input;
- C35 absence of provider-streak mutation for scheduling/no-launch/unresolved primitive records;
- CP04's one-journal/no-second-store shape, CP05's accepted-provider-exhaustion-only reducer entry, and CP10's no-second scheduler/rotator/family lease;
- the unchanged legacy ledger test module: 42 collected tests and no diff versus `origin/main`;
- RW-CUSTODY as already MET.

Preservation is not acceptance of the remaining weaker semantics above.

## North Star

### Four enduring principles

1. **One door per invariant — NOT_MET for the complete NBF candidate.** The single incident journal and sequence-sidecar lock are correctly reused, and all current NBF methods are on `IncidentLedger`. This is real progress. It is not a complete one-door invariant because terminal accepted-launch proof is self-derived from the terminal, reconciliation accepts synthetic adapter markers, provider-key changes are caller-controlled, and applicable provider stream selection is not authoritative. Physical admission/dispatch/death doors are intentionally later-batch scope and are not claimed here.
2. **Deaths speak — NOT_MET as the North Star end state; partial primitive progress.** Typed worker, observed-death, and non-worker records carry killer/signal/cause/elapsed fields, unknown death is constrained, and the CLI is non-signalling. No real signal-site wiring belongs to NBF-01, but the append-path matrix and durable confirmation evidence remain incomplete, so this candidate cannot claim that every termination speaks.
3. **Models are admitted, not assumed — NOT_MET / deferred by scope.** No admission gate, catalog/family classifier, or live provider membership caller is owned by NBF-01. That is correct scope discipline, but it is not evidence that the North Star end state holds. Batch 2 owns this principle.
4. **Fixes ship on main through the fixer contract — NOT_MET / not yet evidenced.** This candidate is an uncommitted dirty worktree. No commit, push, or main delivery exists, and this review cannot authorize either. Later delivery owns that proof.

### Anti-patterns

- **Single-scan verdicts treated as sustained truth — NOT_MET.** The core helper now binds confirmation identity to PID, process start, progress, supervisor/container incarnation, and cause and performs locked equality. The required test is still only one mismatch, and expiry/replacement/replay coverage is incomplete; acceptance cannot rest on the source alone.
- **Anonymous integer exits — NOT_MET as repository end state; partial primitive.** Typed disposition and typed worker-disposition outcome are real. Signal sites are not wired in this batch, and evidence/CLI closure is incomplete, so repository-wide deaths are not yet guaranteed to speak.
- **Judgment-based healthy claims without positive proof — NOT_MET.** Reconciliation checks a persisted event-shaped marker but not authoritative controlled-adapter provenance/ordering; the independent source probe showed terminal acceptance without a persisted accepted-launch marker. Schema-shaped evidence is not positive proof.
- **Identical-fingerprint redispatch without changed precondition — NOT_MET.** Reservation CAS across two OS processes is now real, but generic caller-controlled producers and coherent forged provider-key transitions remain accepted. The durable block is therefore not trustworthy.

## KISS / YAGNI / scope

- **Scope discipline — MET.** The candidate changed only the five modified production files, `incident/disposition.py`, and the eight named new test modules. No admission caller, scheduling loop, T7/T8 policy, physical door, launch adapter, signal-site wiring, provider fallback policy, second journal, store, scheduler, rotator, or family lease was added.
- **One journal / one lock — MET in shape.** `_locked` and `_append_nbf_locked` are the boring existing mechanism; no UnitOfWork, prepare/commit pair, second journal, or extra projection service was introduced.
- **KISS quality — NOT_MET.** `ChangedPrecondition.produce` remains a broad generic producer with caller-supplied snapshots, identities, and evidence. `reserve_provider_route_child_with_receipt` is an additional generic convenience surface not named by the frozen contract. These add audit surface without enforcing the authoritative producer contract.
- **YAGNI — MET for batch boundary.** No T8 threshold/policy, later physical wiring, speculative network health check, or new framework was added. Exposed but weakly validated policy-shaped event inputs are a correctness problem, not justification for widening this batch.
- **Ceremonial validation — NOT_MET.** The focused suite is green at 101 observed tests, but the new named tests include a same-ID terminal race, a malformed-line substitute for torn composite write, an ordinary-reservation substitute for the required composite replay name, an incomplete identity matrix, and a forged-hash test that does not recompute event identity.
- **Duplicate doors — PARTIAL / NOT_MET for semantic authority.** There is one physical NBF journal door, but generic producer authority, synthetic adapter markers, and read-only confirmation checks leave semantic claims outside the intended authoritative source boundaries.
- **Later-batch behavior — MET.** No admission callers, scheduling loops, T7/T8 policy, physical doors, launch adapters, signal-site wiring, or provider fallback decisions appear in the candidate diff.

## Evidence integrity

Frozen identities independently match:

- North Star `d75f89...`;
- plan v8 `0ec216...`;
- frozen tasklist `9d206c...`;
- attempt-2 rework tasklist `6d625c...`;
- immutable source `origin/main@798c506...`;
- candidate HEAD `922241d...`, merge-base `798c506...`, and branch `megado-nbf-guard-0826`;
- executor receipt `d03d259...`, finding `896cc4...`, custody receipt `48f540...`, and current custody `94df44...`.

The exact owned production diff command reproduced `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`. All nine owned untracked files have independently reproduced Git object and raw-file identities above. The new executor finding's owned-production manifest and the independent hashes agree. `test_incident_ledger.py` remains unchanged.

The historical evidence remains historical and was not rewritten:

- the original start-gate receipt's focused **52** claim and later same-path mutation to **61** remain historical integrity failures;
- the unreproducible owned-source digest `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70` remains unreproducible;
- the prior independent failed-handoff digest `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf` remains historical;
- attempt-1 focused/legacy **78/78** and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801` remain observations, not targets or waivers.

The current independent focused count is **101** and current legacy count is **78**, both observations. The candidate/diff digest and all independent test/CLI transcript digests in `/tmp/oracle-nbf01-rework2-luna/` bind the reviewed source. The executor receipt is not internally complete for RW2-04 because it omits explicit candidate HEAD and per-command stderr hashes; my review does not treat it as proof.

## Issues

1. **blocker — C10 / terminal accepted-launch context is self-authorized.** Exact symbols: `IncidentLedger.append_terminal_outcome` and `_project_records` (`ledger.py:659-718,544-575`). Concrete evidence: a direct preferred-Python source probe recorded a success terminal with no persisted accepted controlled-adapter marker (`manual_source_probes.json`, stdout SHA `574ed0ec9494696307c4a8b22b95647e9e8b12bc6ffd68d73bd0e4824c8435ab`). The replay flag `accepted_launch` is set only after the terminal event is already present. Smallest correction: require one persisted receipt-bound `controlled_adapter_state` accepted marker before terminal append and add a negative test with a fully populated outcome.
2. **blocker — C02/C13/C14 strict schema matrix remains incomplete at append.** Exact symbols: `DispatchOutcome.__post_init__`, disposition constructors, and `validate_nbf_event`. Evidence: worker disposition accepts `success_payload`; worker fingerprint/identity typing and subject-specific cause restrictions are incomplete; the required append tests do not cover all false OOM/unknown-signal/identity cases. Smallest correction: close the full payload and typed identity matrix at constructors, `from_dict`, `validate_nbf_event`, and append, with each named test exercising every required family.
3. **blocker — C19-C21 changed-precondition producer authority remains caller-controlled.** Exact symbols: `ChangedPrecondition.produce`, `produce_changed_precondition`, `_produce_reason_specific`, and `append_changed_precondition` (`schema.py:515-539`; `ledger.py:730-744`). Concrete evidence: independent source probe accepted a forged valid provider-key transition (`manual_source_probes.json`, stdout SHA `574ed0ec9494696307c4a8b22b95647e9e8b12bc6ffd68d73bd0e4824c8435ab`); the named forged-ID test does not recompute `event_id`. Smallest correction: replace generic caller-snapshot producers with fixed reason-specific authoritative readers and validate provider-key/evidence bindings before append/consume.
4. **major — C11/C32/C33 applicable provider stream is not selected authoritatively.** Exact symbol: `_project_records` (`ledger.py:494-569`). Concrete evidence: independent provider probe recorded success for key A after key B was latest; resulting projection left A at 2 and reset B to 0 (transcript SHA `4fd3032dac94068518c07362b7f2500813aa46d4b25d6e9b3e8917da2b7e6b81`). Smallest correction: carry an applicable provider-failure-key identity for success/ordinary/disposition outcomes and mutate only that keyed stream; add non-latest-target tests.
5. **major — C23/C34 recovery authorization is not fully evidence-bound or probe-bound.** Exact symbol: `reserve_provider_route_child` (`ledger.py:746-775`). Concrete evidence: route-child test uses arbitrary lease/key inputs and only checks duplicate child rejection; source does not require a passed canonical probe result tied to parent/phase/provider. Smallest correction: require a persisted successful probe result and fixed producer-derived `provider_recovery_verified`, then consume it atomically in the one composite event while preserving the keyed streak.
6. **major — C27/C28 composite replay and crash evidence is not real.** Exact tests: `test_fresh_replay_receipt_is_byte_identical` is ordinary-only; `test_fresh_replay_composite_receipt_is_byte_identical` is a different name; `test_torn_composite_write_exposes_neither_transition_nor_receipt` writes a malformed prefix without a composite or injected append crash. Smallest correction: move the composite scenario under the required name and inject failure during composite `_emit_locked` / post-append receipt derivation, proving both-or-neither projection.
7. **major — C39/C41 confirmation and CLI evidence is still thin.** Exact symbols: `consume_confirmation`, `expire_confirmation`, `_record_cli`. Concrete evidence: the required confirmation test mutates only process-start; CLI named test omits expired status 5 and a distinct already-consumed replay; `expire_confirmation` has no consumed guard and replay can change consumed state to expired. Smallest correction: strengthen the exact named identity/omission/expiry matrix and reject expiry after consumption; add CLI expired and already-consumed subprocess cases.
8. **major — RW2-04 immutable evidence protocol is incomplete in the executor artifacts.** Exact artifact: `.oracle/receipts/execution-nbf01-rework2-luna.md` SHA `d03d259...`. Concrete evidence: no explicit candidate HEAD, no complete changed-file inventory in the receipt, and no per-command stderr SHA-256; it says all stderr is empty instead. Smallest correction: issue a new immutable executor receipt that names HEAD, tracked/untracked changed-file inventory, and stdout/stderr hashes for every required command. Independent transcripts here are complete but do not rewrite the executor artifact.
9. **minor — unofficial convenience surface remains.** Exact symbol: `IncidentLedger.reserve_provider_route_child_with_receipt` (`ledger.py:781-783`). It is not one of the frozen required symbols and adds a generic `**kwargs` forwarding surface. `ChangedPrecondition.produce` is a larger blocker above. Smallest correction: delete the convenience alias unless a frozen downstream symbol is documented to require it.

## Recommendation

The candidate has real progress: one locked journal door, a true two-process reservation race, strict OOM/unknown-death constructor rules, keyed provider stream scaffolding, durable confirmation identity comparisons, non-signalling CLI statuses, and no scope expansion. It still fails Batch 1. Full frozen acceptance requires fail-closed authoritative semantics and behavioral evidence, not green count growth: terminal acceptance is self-authorized, producer identities can be forged, provider success/disposition target the wrong stream, composite replay/crash tests are ceremonial, confirmation/CLI tests are incomplete, and the executor evidence is not complete under RW2-04.

RECOMMEND_ACCEPTED_ISSUES