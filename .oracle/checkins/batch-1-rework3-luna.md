# Luna independent review — NBF-01 / Batch 1 rework 3

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: 922241d0bdb3e993c3b554cc69f19948adef7bc3
- Tasklist SHA-256: 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
- Plan v8 SHA-256: 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
- North Star SHA-256: d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
- Attempt-3 rework tasklist SHA-256: c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779
- Executor finding: `.oracle/findings/execution-nbf01-rework3-luna.md`
- Executor finding SHA-256: 4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f
- Executor receipt: `.oracle/receipts/execution-nbf01-rework3-luna.md`
- Executor receipt SHA-256: e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f
- Owned production diff SHA-256: 8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8
- Isolated transcript root: `/tmp/oracle-nbf01-rework3-luna/`

## Scope and diff

Identity capture matched the Oracle-bound candidate: `HEAD`, `origin/main`, and merge-base are respectively `922241d0bdb3e993c3b554cc69f19948adef7bc3`, `798c50619204010ed3f4297fbb57988fe9381924`, and `798c50619204010ed3f4297fbb57988fe9381924`. The owned production files match the supplied SHA-256 and blob identities, including `disposition.py` (`2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a`, blob `291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1`). All eight new test-file hashes match the supplied identities. The unchanged `test_incident_ledger.py` matches origin/main (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`).

Changed production scope is exactly the five tracked NBF files plus new `incident/disposition.py`; changed test scope is exactly the eight named new modules. No admission caller, scheduler, T7/T8 policy, physical door, launch adapter, signal site, fallback policy, second journal/store/projection, family lease, rotator, or main-merge work entered the candidate. The worktree is not clean because pre-existing `.oracle` planning/evidence artifacts are dirty; that is preserved non-owned noise, not a clean-tree claim.

The single ledger authority is `_IncidentEventJournal` plus `IncidentLedger` in `incident/ledger.py`. NBF compare/read paths use `_locked` and `_append_nbf_locked`, with the existing sequence-sidecar `fcntl.flock` and `_emit_locked`. There is one `events.jsonl` journal and no UnitOfWork, prepare/commit protocol, second store, scheduler, or projection owner.

## Validation evidence

The exact commands were rerun independently. Full JSON transcript records contain argv, cwd, exit status, verbatim streams, and both stream hashes.

| Command transcript | Exit | Result | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|---|
| `focused.json` | 0 | `112 passed in 15.31s` | `b295944369c7307eae526dbb7f26489f657782bc8f7f7f104a1a5613ebfaaac3` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `legacy.json` | 0 | `78 passed in 1.47s` | `6bf9fdef28e576401171fa27f28aed01180b01cf2c0864567bc6bc54d21d4f7b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tx_subset.json` | 0 | `5 passed, 11 deselected` | `a64d95de6a86d87df3375b0a5fdac47745385bc5dd0622308e19fcdee85dba09` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider_subset.json` | 0 | `5 passed, 6 deselected` | `808c3d14219287627b518671c7308d76b836ed617dc7d6e8e463ef82c4169e47` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `confirmation_subset.json` | 0 | `7 passed` | `35c11cc3672b8bda3b90af5b09f81b95192b96e163255ff89c7c355117ee769d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `compile.json` | 0 | `py_compile` completed | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `diff_check.json` | 0 | `git diff --check` completed | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `broad.json` | 2 | collection stopped at two missing modules | `602e26d1aaada829260638a8e5c880caa4b0efa7366c8968a7c7df1e489fa096` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `collect_new.json` | 0 | `70 tests collected` | `97d1c095a2cdb9587407637a79e5d35baf21a9dc0d1cffd3c742a5016b655c9d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `collect_unchanged.json` | 0 | `42 tests collected` | `208afccf84501ad8455173d54844085406ca307fdd52686e935328bd860c9b3` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Focused pytest therefore collected 70 tests from the eight new modules and 42 unchanged tests from `test_incident_ledger.py`, for 112 total. Green focused and legacy suites are necessary, not sufficient.

## Criterion dispositions (C01–C41)

Evidence labels: focused=`b2959443…`; legacy=`6bf9fdef…`; transaction subset=`a64d95de…`; provider subset=`808c3d14…`; confirmation subset=`35c11cc3…`; independent probes=`62fa6b24…`; recovery probes=`89baff32…`; CLI transcript hashes are listed below.

| Criterion | Status | Exact file/symbol; evidence | Smallest correction if not MET |
|---|---|---|---|
| C01 | UNEVIDENCED | `phase_result.py`: `SchedulingCondition`, `DispatchOutcome`; `phase_result_classify.py`: `classify_dispatch_outcome`. Scheduling lossless test and worker round-trip exist, but no behavioral six-kind round-trip test; the matrix test is rejection-only. | Add one real round-trip/unknown/missing-field test for all six outcome kinds through `from_dict`/serialization and phase transport. |
| C02 | NOT_MET | `DispatchOutcome.__post_init__` and `schema.validate_nbf_event` reject several combinations; independent probe `independent_probes.json` (`62fa6b24…`) confirms worker-disposition + success-payload rejects at four exercised doors. The required matrix test at `test_worker_disposition.py:34` is constructor-only, omits the complete six-kind matrix, and does not exercise decode/validation/append. | Make the named test cover every illegal family for every kind at constructor, decode, validation, and append. |
| C03 | MET | `DispatchOutcome.__post_init__`; `test_no_launch_rejects_accepted_launch_state`; focused transcript `b2959443…`. | — |
| C04 | MET | `DispatchOutcome.__post_init__`, `WorkerDisposition.__post_init__`, `append_terminal_outcome`; named context tests; focused transcript. | — |
| C05 | MET | `DispatchOutcome.__post_init__`, terminal schema validation, and provider/disposition payload checks; named matrix and append tests; independent probe `62fa6b24…`. | — |
| C06 | MET | `terminal_outcome_kind` and `append_terminal_outcome`; `test_disposition_terminal_links_existing_record_once`; focused transcript. | — |
| C07 | MET | `append_terminal_outcome` validates committed disposition context and returns the existing terminal on identical replay; terminal-outcome test; focused transcript. | — |
| C08 | MET | `classify_dispatch_outcome` is lossless and does not coerce worker disposition; `test_outcome_never_coerces_disposition_to_failure`; focused transcript. | — |
| C09 | NOT_MET | `append_terminal_outcome` has locked conflict handling. However required `test_two_process_terminal_linkage_is_atomic` at `test_incident_ledger_transactions.py:100` races the same terminal ID and both children return `ok`; the distinct-ID/conflicting-kind scenario is only under a different name at line 132. The frozen contract makes the named proof mandatory. | Move the distinct-ID, conflicting-kind, two-OS-process race into the required test name and retain same-ID idempotency separately. |
| C10 | MET | `append_controlled_adapter_state` and `append_terminal_outcome` require one receipt-bound accepted marker under `_locked`; replay does not infer acceptance from a terminal. `test_terminal_without_accepted_marker_rejects_fully_populated_outcome`, `test_accepted_marker_single_field_mismatch_rejects`, and independent `terminal_without_marker` probe (`62fa6b24…`) pass. | — |
| C11 | NOT_MET | `_project_records` is keyed, but required non-latest disposition coverage is absent. `test_disposition_breaks_consecutiveness_without_degradation` targets only one stream; no exact non-latest ordinary/disposition test exists. | Add non-latest keyed disposition and ordinary-failure tests asserting only the applicable stream changes and no degradation. |
| C12 | MET | No terminal branch exists for `no_launch`/`unresolved_launch`; `test_no_launch...`, reconciliation tests, focused transcript. | — |
| C13 | UNEVIDENCED | `_typed_worker_identity` and canonical fingerprint checks exist. The named identity test only checks selected omissions/version cases; terminal schema still has an initial `(str, dict)` truthy check before the typed check. Complete missing/fabricated identity coverage is not present. | Add decode and append cases for every required worker/observed/non-worker identity field and assert canonical 64-hex fingerprint behavior. |
| C14 | MET | `_positive_cgroup_delta`, `ObservedProcessDeath.__post_init__`, and unknown-death branch enforce positive OOM and `external_unknown`/no signal. Independent probe `62fa6b24…` shows false/zero/negative rejection, legal positive OOM append, legal unknown append, and both fabricated killer/signal rejection. | — |
| C15 | MET | `WorkerDisposition.deterministic_id`; `test_term_and_kill_ladder_ids_are_distinct`; focused transcript. | — |
| C16 | MET | `SemanticDispatchFingerprint.VOLATILE` excludes logical/family/liveness identities; `test_provider_key_and_fingerprint_exclude_volatile_identity`; focused transcript. | — |
| C17 | MET | `SemanticDispatchFingerprint` and `ProviderFailureKey` derivation exclude route-liveness digest/generation; provider test; focused transcript. | — |
| C18 | MET | Reservation key is projection-key plus semantic fingerprint, independent of logical ID; `test_two_process_reservation_contention_one_winner` uses `multiprocessing`/`fork`; transaction subset `a64d95de…`. | — |
| C19 | NOT_MET | `ChangedPrecondition` producers in `schema.py` accept caller-provided typed `before`, `after`, `evidence`, subject, and optional provider-key values; `produce_*` wrappers forward them. Independent coherent forged event was accepted by both `ChangedPrecondition.from_dict` and `IncidentLedger.append_changed_precondition` (`independent_probes.json`, stdout hash `62fa6b24…`). | Replace caller-selected snapshots/IDs with authoritative source readers or typed authoritative handles; validate producer/evidence/subject/key binding under the existing lock. |
| C20 | NOT_MET | `_authoritative_source` only checks a caller dict's `authority_kind`, subject, and content; `append_changed_precondition` checks that the cited event exists and hashes match, not that the source is authoritative. The coherent forgery probe accepted. | Bind each of the seven producers to its authoritative source and cited evidence type, then validate all bindings at append/consume. |
| C21 | NOT_MET | Coherently recomputed forged content and event IDs were accepted at `from_dict` and append in `independent_probes.json` (`62fa6b24…`). No consume rejection is demonstrated because append already accepted the forgery. | Reject the same forged event at decode, append, and consume after recomputation; add that complete named test. |
| C22 | MET | `consume_changed_precondition` checks persisted identity and consumed state under `_locked`; `test_consumed_change_cannot_authorize_second_reservation`; focused transcript. | — |
| C23 | NOT_MET | `reserve_provider_route_child` checks a passed probe, matching lease, parent, route, and one authorizer; recovery probe transcript `89baff32…` shows missing, failed, and second-use rejection plus one valid child. But `append_probe_result` accepts caller-supplied lease/key/evidence and the required exact preservation test is absent. | Bind probe result to an existing unexpired lease and canonical parent/phase/route/provider, and add the full negative matrix. |
| C24 | NOT_MET | `_project_records` rekeys on provider-key change, but producer authority is forgeable and `test_key_changing_precondition_rekeys_key_unchanged_does_not` does not assert the unchanged streak value. | Use authoritative before/after keys and assert changed-key reset/rekey versus unchanged-key preservation numerically. |
| C25 | MET | Real two-process same-key reservation race `test_two_process_reservation_contention_one_winner`; transaction subset `a64d95de…`. | — |
| C26 | MET | `reserve_provider_route_child` payload has no child receipt-ID input; `validate_nbf_event` rejects it; composite tests and provider subset `808c3d14…`. | — |
| C27 | MET | Required `test_fresh_replay_receipt_is_byte_identical` is now a real composite and reopens the ledger before deriving the same receipt; provider subset `808c3d14…`. | — |
| C28 | NOT_MET | `test_torn_composite_write_exposes_neither_transition_nor_receipt` calls real `reserve_provider_route_child` and injects `_emit_locked`, proving neither transition nor child. It does not inject the post-append/receipt-derivation boundary required by RW3-03. | Add the post-append receipt-boundary failure and prove restart both-or-neither. |
| C29 | MET | `_project_records` applies provider/fingerprint terminal effects before `reservations[key]["closed"] = True`; terminal tests and focused transcript. | — |
| C30 | MET | Accepted `provider_exhausted` terminal branch increments keyed stream; keyed replay test passes. | — |
| C31 | MET | Different provider key starts its stream at one; `test_nonmatching_key_rekeys_at_one`; provider subset. | — |
| C32 | NOT_MET | Source reducer selects by supplied terminal `provider_failure_key`, and independent probe proves A success after B leaves A=2/B=1 (`62fa6b24…`). But required `test_success_for_non_latest_key_does_not_reset_latest` is absent; `test_success_resets_only_applicable_key` is the latest-stream case A,A,B then success B (`test_provider_route_projection.py:93`). | Add the exact non-latest named test with value assertions and no `latest_stream_key` fallback. |
| C33 | NOT_MET | Reducer has keyed ordinary/disposition break code, but required `test_ordinary_failure_breaks_only_applicable_stream` is absent and existing disposition test targets the latest/single stream. | Add non-latest ordinary and disposition interleavings with explicit no-degradation assertions. |
| C34 | NOT_MET | Valid recovery child preserves streak in `test_recovery_authorization_single_use_across_different_children` and `recovery_probes.json` (`89baff32…`), but required `test_probe_and_recovery_preserve_streak_and_authorize_one_child` and the full failed/absent/mismatched/replayed/consumed matrix are absent. | Add the required named test and all rejection states against a canonical passed probe/recovery event. |
| C35 | MET | `_project_records` has no scheduling/no-launch/unresolved/time/liveness provider-observation branch; scheduling/no-launch tests pass and focused transcript is green. | — |
| C36 | MET | `ReservationReconciled` has only the three frozen resolutions; positive controlled-adapter no-launch and ambiguous hold tests pass. | — |
| C37 | MET | `reconcile_reservation` requires an existing terminal/disposition and identical replay is idempotent; `test_recovered_disposition_links_existing_record_without_duplicate`; focused transcript. | — |
| C38 | MET | `reconcile_reservation` rejects missing positive evidence and accepted-launch release; `test_blind_release_and_accepted_launch_release_reject`; focused transcript. | — |
| C39 | NOT_MET | `consume_confirmation` compares five identity fields, evidence digest, separation, and expiry. It does not accept/compare caller TTL, `expires_at`, `scan_interval_s`, policy identity, or the first evidence identity as a complete second-scan record. The named test omits only the five identity fields; it does not cover TTL/expiry/scan interval/evidence omissions. | Require and compare every frozen confirmation identity/TTL/separation field, preserve consumed state during expiry projection, and add the complete omission/mismatch matrix. |
| C40 | UNEVIDENCED | `_locked`, `_append_nbf_locked`, strict replay validation, and version checks fail closed; one journal is proven. No cache-mismatch authority/test exists in the current primitive and no complete lock/append/cache failure matrix was captured. | Add only the smallest existing-cache mismatch/failure proof, without adding a second cache/store. |
| C41 | MET | Independent CLI subprocesses in `cli2_*.json` exercise status 0, malformed/schema 2, append failure 3, invalid location 4, missing/expired/distinct/same-identity replay 5. Status 0 emitted one JSON acknowledgement after a consumed matching confirmation and no signal. Hashes are listed below. | — |

## Batch 1 checkpoint dispositions (CP01–CP11)

| Checkpoint | Status | Evidence and smallest correction |
|---|---|---|
| CP01 | MET | Focused suite: exit 0, 112 passed, stdout `b295944369c7307eae526dbb7f26489f657782bc8f7f7f104a1a5613ebfaaac3`; unchanged ledger count is 42. |
| CP02 | NOT_MET | C02/C13/C19–C21 and C39 remain incomplete or false in source/tests. Complete the strict matrix, authoritative producers, and confirmation identity contract. |
| CP03 | MET | Explicit worker-disposition kind, mapping, committed disposition linkage, and idempotent terminal test pass. |
| CP04 | MET | One `_IncidentEventJournal`, one `events.jsonl`, sequence-sidecar flock, and all NBF writes through `_locked`/`_append_nbf_locked`; source inspection and `independent_probes` event-files output. |
| CP05 | MET | Only `worker_terminal_outcome` with `outcome_kind == provider_exhausted` enters the observation increment branch; probe results have no reducer increment branch. |
| CP06 | NOT_MET | Recovery source path has a valid child and single-use check, but required preservation/negative evidence matrix is absent and probe inputs remain caller-shaped. |
| CP07 | NOT_MET | Keyed source logic exists, but required non-latest behavior names are missing and producer key authority is forgeable. |
| CP08 | NOT_MET | Composite replay is real, but post-append receipt-boundary crash evidence is missing. |
| CP09 | MET | Distinct typed paths exist for no-launch, unresolved, ordinary, provider exhaustion, and worker disposition; focused suite and source inspection. |
| CP10 | MET | No later-batch files or second authority are in the changed scope; single ledger door confirmed. |
| CP11 | NOT_MET | Focused suite is green, but distinct-ID named race, post-append composite crash, complete confirmation matrix, and coherent producer forgery remain unproved/false. |

## Rework task dispositions

| Work item | Status | Evidence |
|---|---|---|
| RW3-01 | NOT_MET | Marker and payload improvements are present (`C10`, independent marker/matrix probe `62fa6b24…`), but the complete matrix is not in the required test and coherent changed-precondition forgery remains accepted (`62fa6b24…`). |
| RW3-02 | NOT_MET | Reducer now uses keyed terminal fields and valid recovery child checks exist (`89baff32…`), but all six required provider/recovery names are missing; existing success/disposition tests are latest-stream cases. |
| RW3-03 | NOT_MET | Required fresh-replay name is a real composite and `_emit_locked` failure is exercised. Required terminal-linkage name still races identical IDs, and post-append receipt failure is absent. |
| RW3-04 | NOT_MET | CLI matrix is complete independently, but confirmation mismatch/omission coverage excludes TTL, expiry, scan interval, policy, and evidence identity; the criterion therefore remains incomplete. |
| RW3-05 | MET | `hasattr(IncidentLedger, "reserve_provider_route_child_with_receipt")` is false; `reserve_provider_route_child` and `derive_receipt` remain. Required API test passes. |
| RW3-06 | NOT_MET | New attempt-3 paths, explicit HEAD, candidate diff, and historical labels exist. However neither executor artifact records the required per-file `git hash-object` and SHA-256 inventory for `disposition.py` plus all eight new test modules. The receipt also abbreviates the broad-suite output rather than recording its verbatim streams. Independent review transcripts cannot repair an incomplete immutable executor artifact. |
| RW3-GATE | UNEVIDENCED | No Grok Oracle gate was issued in this review, by instruction. This reviewer does not issue the Batch 1 verdict. |

## A3 dispositions

| A3 item | Status | Current symbols/evidence; hole closed? |
|---|---|---|
| A3-01 | MET | `append_controlled_adapter_state`, `append_terminal_outcome`, `_project_records`; fully populated terminal without marker and every marker-context mismatch reject. Hole closed behaviorally. |
| A3-02 | NOT_MET | `DispatchOutcome.__post_init__`, `from_dict`, `validate_nbf_event`: worker+success is fixed, but full six-kind matrix and typed identity completeness are not proven by the required named test. Hole not fully closed. |
| A3-03 | NOT_MET | `ChangedPrecondition` and `_authoritative_source`; coherent recomputed forge accepted at decode and append in `62fa6b24…`. Hole remains. |
| A3-04 | NOT_MET | `_project_records` is keyed and independent A-success probe works, but required non-latest success/ordinary/disposition tests are missing. Hole not accepted under frozen evidence contract. |
| A3-05 | NOT_MET | `reserve_provider_route_child`, `append_probe_result`; valid child and failed/missing/second-use checks exist, but canonical probe binding and required complete matrix are insufficient. Hole not fully closed. |
| A3-06 | NOT_MET | `test_fresh_replay_receipt_is_byte_identical` is real, but required terminal race name is same-ID idempotency and no post-append failure injection exists. Hole remains in evidence. |
| A3-07 | NOT_MET | `consume_confirmation`, `expire_confirmation`, `_record_cli`; CLI is complete, but confirmation TTL/separation/evidence/policy omission matrix is thin. Hole not fully closed. |
| A3-08 | NOT_MET | Executor HEAD/diff and most command records exist, but required per-file hashes and complete immutable command evidence are absent. |
| A3-09 | MET | Unofficial `reserve_provider_route_child_with_receipt` is absent and the two supported methods remain. |

## Independent probes of attempt-2 holes

The independent behavioral probe transcript is `independent_probes.json`, stdout SHA-256 `62fa6b24fdf1db5c4e2e098b757c227384d137d0a3384528c0769835f4e115c1`, stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, exit 0. It independently exercised: fully populated terminal without accepted marker; worker-disposition + success payload at constructor/decode/validation/append; typed worker identity; false/zero/negative OOM; legal positive OOM append; legal unknown death and fabricated killer/signal append rejection; coherent recomputed changed-precondition forgery; non-latest A success after B (result `A=2, B=1`); missing applicable key (no stream change); confirmation omission, evidence mismatch, expiry-after-consume; alias absence; and one journal/events file.

The recovery probe transcript is `recovery_probes.json`, stdout SHA-256 `89baff32ef176c411763c002b13d1740906510040c68f78013218c1cc9ec43b2`, stderr empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, exit 0. It independently exercised missing authorizer, failed probe, mismatched recovery key, one valid child preserving streak 1, and second child rejection after authorization consumption.

The real transaction suite also independently exercised OS-process reservation contention and composite `_emit_locked` injection: transaction subset stdout SHA-256 `a64d95de6a86d87df3375b0a5fdac47745385bc5dd0622308e19fcdee85dba09`; provider subset stdout SHA-256 `808c3d14219287627b518671c7308d76b836ed617dc7d6e8e463ef82c4169e47`. The named terminal-linkage test's two processes use the same ID, so it proves idempotency rather than the required conflicting race.

### Independent CLI subprocess evidence

All CLI records are under `/tmp/oracle-nbf01-rework3-luna/cli2_*.json`; each records the full argv, cwd, exit, verbatim streams, and both hashes. The argv for every row is `python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <case-root> --json-stdin`.

| Case | Exit | stdout SHA-256 | stderr SHA-256 | Result |
|---|---:|---|---|---|
| status 0 consumed matching confirmation | 0 | `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | one JSON ack: `{"disposition_id":"cli-d","ledger_event_id":"cli-d","record_id":"cli-d"}` |
| status 5 same disposition replay | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `7fe9e01d6cba7af6c48aff7b6a459cfc1116a9bfbc742574a8da501cc954e208` | already consumed |
| status 2 malformed | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` | malformed JSON |
| status 2 schema-invalid | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` | schema violation at an existing location |
| status 3 append failure | 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `6429e423ada8619a78f87e9f17b5fb6960164ca1c9d1f527a426a579909dc2ec` | valid location with `events.jsonl` directory |
| status 4 invalid location | 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` | ledger-root is a file |
| status 5 missing confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` | existing ledger, no confirmation |
| status 5 expired confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` | durable expired confirmation |
| status 5 differently-bound consumed replay | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655` | consumed confirmation bound to different disposition |

CLI status 0 has no signalling path in `disposition.py`; the module only appends and acknowledges. The command evidence is independent of pytest names.

## Broad-suite relevance classification

Fresh `pytest -q tests/arnold_pipelines/megaplan` stopped at collection (exit 2; stdout SHA-256 `602e26d1aaada829260638a8e5c880caa4b0efa7366c8968a7c7df1e489fa096`). The two import chains are:

1. `test_cli_check_validator.py` → `arnold.workflow.validator` → `arnold.agent.costing.model_resource_capabilities`.
2. `test_key_pool_codex.py` → `arnold.agent.run_agent` → `arnold.agent.tools.terminal_tool` → `arnold_pipelines/megaplan/agent/tools/terminal_tool.py` → `tools.environments.singularity`.

Both module paths are absent on the candidate and absent at `origin/main` (`git cat-file -e` checks). No owned attempt-3 source/test file changes either import chain; changed-file inventory is limited to the NBF files listed above. Classification for both is exactly **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**. This reduces broad-suite coverage but does not waive any NBF criterion.

## Preserved prior-MET result

The following remain MET: one journal/sequence-sidecar lock; C03–C08; C12; C15–C18; C22; C25–C26; C29–C31; C35; C36–C38; CP04/CP05/CP09/CP10; real two-process reservation contention; unchanged legacy ledger test; and absence of later-batch wiring. The focused suite is 112 passed and the legacy regression suite is 78 passed. `py_compile` and `git diff --check` both exit 0.

Prior named behavior remains mechanical rather than narrative: `test_two_process_reservation_contention_one_winner` uses two forked OS processes and one on-disk ledger; terminal projection precedes closure in `_project_records`; no-launch has no terminal branch; and provider observations enter only from accepted exhausted terminal outcomes. The preserved behavior does not cure the new gaps listed above.

## North Star

- **One door per invariant:** MET for this primitive slice. All NBF writes use the existing ledger `_locked`/`_append_nbf_locked` door and one `events.jsonl`; no duplicate ledger/store/scheduler authority entered. The broader admission and death doors remain later-batch scope, not falsely claimed as implemented here.
- **Deaths speak:** Partially MET for the owned schema/CLI primitives: typed worker/observed/non-worker records, killer/signal/cause, OOM proof, and non-signalling CLI exist. Full repository signal-site wiring is later-batch scope and absent as required.
- **Models admitted, not assumed:** UNEVIDENCED for this NBF-01 slice. No admission caller or model catalog/live-membership implementation was changed, so this review cannot claim dispatch-time model admission. That is correctly later-batch scope, not a Batch 1 defect.
- **Fixes ship on main through fixer contract:** NOT MET as a delivery state. The candidate is uncommitted and unpushed by contract; no deploy-only hotfix was observed, but this review cannot claim the enduring delivery principle until the later fixer/merge gates. It is not an NBF-01 implementation failure.

Anti-patterns:

- **Single-scan truth:** partially addressed by durable confirmation and two-process consumer tests, but C39's complete identity/TTL matrix is not proven.
- **Anonymous integer exits:** addressed in the owned primitive; typed killer/cause/signal records and CLI status separation exist. The CLI does not signal.
- **Judgment-based healthy claims:** not owned by this batch; no admission/liveness verdict was introduced. The ledger confirmation requires durable identity/evidence, but incomplete fields remain an issue.
- **Identical-fingerprint redispatch:** partially addressed: locked reservation uniqueness, marker-bound terminals, and changed-precondition consumption exist, but C19–C21 show a coherent forged change can authorize the path.

## KISS / YAGNI / scope

No material later-batch behavior or duplicate authority was introduced. The design stays on the existing journal and lock, and the unofficial route-child wrapper was deleted. The main YAGNI/correctness concern is the snapshot-shaped producer API (`_authoritative_source`, `produce_*` forwarding caller objects) and optional/generic probe inputs: they look typed but leave the trust boundary caller-controlled. That is both unnecessary surface and the source of the forgery defect. Confirmation and terminal records also carry broad optional payload fields while the required equality matrix is incomplete: ceremonial shape without complete enforcement. Smallest design is authoritative producer adapters plus strict closed records, not a new framework.

## Evidence integrity

Current hashes and identities bind this review to the exact candidate. The executor diff digest reproduces. The executor finding and receipt correctly label HEAD/source/candidate and preserve historical evidence, but RW3-06 is not complete: the required per-file `git hash-object` and raw SHA-256 inventory is absent, and the executor receipt abbreviates broad-suite output rather than retaining verbatim streams. The independent transcripts in `/tmp/oracle-nbf01-rework3-luna/` are complete for every command run here and are bound below in the receipt.

The following remain historical and were not rewritten: start-gate focused **52→61** mutation; unreproducible owned-source digest `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`; prior independent Luna failed-handoff digest `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`; attempt-1 focused/legacy 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`; and attempt-2 reviewed production digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`. The current candidate digest is `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`, not an attempt-2 target.

## Issues

1. **blocker — changed-precondition authority remains forgeable (C19–C21, RW3-01, A3-03).** `schema.py:_authoritative_source` trusts caller dictionaries; `append_changed_precondition` verifies only persisted cited-event equality. A coherent forged event with recomputed snapshots, content IDs, evidence digest, and event ID was accepted by both decode and append in independent probe transcript `62fa6b24…`. Smallest correction: authoritative reason-specific source readers/handles and locked producer/evidence/key validation, with append and consume rejection tests.
2. **blocker — required strict matrix evidence is incomplete (C02/C13, RW3-01, A3-02).** The named matrix is constructor-only; typed identity coverage is partial. Independent probe confirms one repaired pairing, not the complete six-kind decode/validation/append matrix. Smallest correction: strengthen the existing named tests in place across all four doors.
3. **major — applicable-key behavioral proof is missing (C11/C32/C33/C34, CP06/CP07, RW3-02, A3-04/A3-05).** The reducer is keyed in source and an independent A-after-B success probe works, but required non-latest success/ordinary/disposition/cross-restart/recovery names are absent. The existing success test targets B as latest; the existing disposition test is not non-latest. Smallest correction: add the required named non-latest and canonical-probe matrix tests with numeric stream assertions.
4. **major — composite and terminal race evidence is incomplete (C09/C28, CP08/CP11, RW3-03, A3-06).** Required terminal-linkage name races the same ID and proves idempotency; distinct-ID race is under another name. Composite failure injection stops at `_emit_locked`; no post-append receipt-boundary injection exists. Smallest correction: move the distinct-ID OS-process race under the required name and add post-append crash/reopen both-or-neither coverage.
5. **major — durable confirmation equality matrix is incomplete (C39, RW3-04, A3-07).** `consume_confirmation` does not compare every frozen TTL/expiry/scan/policy/evidence identity field, and the required test only covers five identity fields and omissions. Smallest correction: require every field and add each mismatch/omission plus restart/replacement/expiry/concurrent-consumer assertions.
6. **major — immutable executor evidence protocol is incomplete (RW3-06, A3-08).** Attempt-3 finding/receipt omit the required `git hash-object` and SHA-256 for `disposition.py` and all eight new test modules; receipt's broad sweep is a summary rather than verbatim output. Smallest correction: publish a new immutable executor finding/receipt for this exact tree with the missing inventory and complete stream records; do not edit historical artifacts.
7. **major — broad-suite coverage is reduced (CP01 context).** Both collection failures are pre-existing/out-of-scope, not NBF regressions, but the full directory sweep remains incomplete. Smallest correction: restore the two missing modules in the source-base environment or run a source-base-equivalent environment; do not waive in-scope criteria.
8. **minor — C01/C40 are not fully evidenced.** Six-kind round-trip and cache-mismatch/complete fail-closed matrices are not behaviorally demonstrated. Smallest correction: add narrowly targeted tests without new authority surfaces.

## Recommendation

RECOMMEND_ACCEPTED_ISSUES
