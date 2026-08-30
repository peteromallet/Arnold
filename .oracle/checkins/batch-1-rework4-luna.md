# Luna independent review — NBF-01 / Batch 1 rework 4

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: 922241d0bdb3e993c3b554cc69f19948adef7bc3
- Tasklist SHA-256: 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
- Plan v8 SHA-256: 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
- North Star SHA-256: d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
- Attempt-4 packet SHA-256: 4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534
- Executor finding: `.oracle/findings/execution-nbf01-rework4-luna.md`
- Executor finding SHA-256: b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1
- Executor receipt: `.oracle/receipts/execution-nbf01-rework4-luna.md`
- Executor receipt SHA-256: 8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f
- Owned production diff SHA-256: aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41
- Isolated transcript root: `/tmp/oracle-nbf01-rework4-luna-review/`

## Scope and diff

Identity capture reproduced the Oracle-bound candidate exactly:

- `HEAD`: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- `origin/main`: `798c50619204010ed3f4297fbb57988fe9381924`
- merge-base: `798c50619204010ed3f4297fbb57988fe9381924`

The exact production-diff command reproduced digest
`aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`.
Every owned production/test SHA-256 and the listed git blob identity in the
attempt-4 executor evidence was independently reproduced; the unchanged
`test_incident_ledger.py` remains SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` and blob
`44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`.

Changed production scope is exactly the five tracked NBF files plus
`incident/disposition.py`. Changed test scope is exactly the eight named new
modules. The worktree contains unrelated dirty/untracked `.oracle` planning
and historical evidence artifacts; this review does **not** claim a clean
candidate. No later-batch production path is in the owned diff.

Owned-file SHA-256 inventory (the corresponding `hashes.json` also records
the five tracked git blob identities):

| File | SHA-256 |
|---|---|
| `arnold_pipelines/megaplan/incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` |
| `arnold_pipelines/megaplan/incident/ledger.py` | `da256e9d10763d1f5e76a13cacb95ae6d61a3ca6e95c42ae4d4f702e3c3061fe` |
| `arnold_pipelines/megaplan/incident/schema.py` | `e32c111c077cced274162e51df1d3b0623b99a2933b390928f1356fe34402004` |
| `arnold_pipelines/megaplan/incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` |
| `arnold_pipelines/megaplan/orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` |
| `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py` | `ed21611737f05d74aecaa1f41b4a8af37baf59d488c467b232d77acf992b3cea` |
| `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` |
| `tests/arnold_pipelines/megaplan/test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` |
| `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` |
| `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` |
| `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` | `73be8fb3f19e903f5b48680d200674e547aa4c4b111495e92b19ab7d1fe7a9d7` |
| `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` |
| `tests/arnold_pipelines/megaplan/test_worker_disposition.py` | `0f9c412cd85b217a132b0e84b4e2f944bf4ba4b947f1dbbbc785116e0a876d06` |

No later-batch production path is in the owned diff.

## Validation evidence

All commands below were executed independently from the repository root. Each
transcript has exact argv, cwd, exit status, complete stdout/stderr files, and
full stream digests under the isolated transcript root.

| Transcript | Exit/result | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|
| `focused.json` | 0; 121 passed in 17.43s | `eb007f81b56a64eda7073a78949932b1f77653d9df6ca93922045251646eba3b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `legacy.json` | 0; 78 passed in 1.43s | `211dfb1591ec7c1c795a37c2c284e61936f83ace4f8e319ad3fbeaf9975392a8` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `changed_subset.json` | 0; 3 passed, 5 deselected | `7cb45892af5510dfff0577f6d1cdf92492b282c211bb3578d90422bc122eaeb8` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `worker_terminal_sched.json` | 0; 25 passed | `1951731dcea742817c5409fee5e5fee678088ddaf9ef8b40074a7a7f0f2d9931` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider.json` | 0; 18 passed | `d015b2f31ef3fe7900d05082b66c5ec8069a2ebe988abc3a1192c3455c86b15d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `cross_tx.json` | 0; 5 passed, 12 deselected | `3f6c93b5bf0db5bcad8649961358aedefab718ecb84d0860a8791fb73a22884c` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `cross_tx_full.json` | 0; 6 passed, 11 deselected | `ab020e2215f61d573510338e4c5638861de5a1b8f4e17fed39cde704317f171d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider_replay.json` | 0; 6 passed, 12 deselected | `bcaf041802b7e74be4107ad7ac76c1f1125595572458fc65d8e3a14d9c38cafb` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `confirmation.json` | 0; 7 passed | `42317fada6dcccf66125f116d742efc2b7f7fa15372a60582b23352bdc60c64e` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `py_compile.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `diff_check.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `broad.json` | 2; collection interrupted by two missing modules | `fe5ee29bc0a5dc6c64b50b148a20f01128422c47042d84b06570ce0f2fee817e` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `broad_relevance.json` | 0; both modules absent on candidate/base, no owned import reach | `cd8db8718ff84e2a9432e2a859e33f5501d33df7f614cbfff1174f85ac84a901` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The focused and legacy stdout are complete in the transcript files, not
summaries. The exact focused command exercised all nine frozen modules,
including the unchanged legacy ledger test. The independently rerun packet
subsets cover changed-precondition readers, disposition/terminal/scheduling,
provider projection, transaction races/crashes, provider replay/receipt, and
confirmation.

### Independent CLI subprocess matrix

These are separate subprocess invocations of
`python -m arnold_pipelines.megaplan.incident.disposition record`, with exact
stdin payloads, ledger roots, argv, cwd, status, and stream digests in the JSON
transcripts. The valid status-0 process emitted one JSON acknowledgement and
no signal; the CLI module contains no signal primitive.

| Case | Exit | stdout SHA-256 | stderr SHA-256 | Transcript SHA-256 |
|---|---:|---|---|---|
| status 0 valid acknowledgement | 0 | `de85b9592423e61ef59c4a860ba75e55ed618dd8934da164df3f802f16b71e85` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ff4d24a2c5962c6f072dba39ab1919809d00e185440880dbc579eebfa141ff1a` |
| status 2 malformed JSON | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` | `fa9156725d63e8d43af249acbd26ae0b0c3a9b115371b8997456546b19662151` |
| status 2 schema-invalid | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb4199a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` | `b72d9557936490688d8cd706463ed69858d050aacc4c81c4cda5420cc8b205d9` |
| status 3 valid-location append/lock failure | 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `b5f11611441f45b0b3e377f413816e00edba8f940215647376e50b72bdb6dfb7` | `02159a8fe21e9c5c38889075ec328170c23e5da3d72b44c44253d159cce0202f` |
| status 4 invalid ledger location | 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` | `28adf7ea6de7003922f4af7e4341e3564a21a5ec91f2b1a76f1f7fac6e423082` |
| status 5 missing confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` | `664e9cd8bd5ba1d782a5f4d7cb4b0b2d190be7ca0b121a4ec8c9e2f788d8ce7a` |
| status 5 expired confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` | `3230f4b0db51a9fa9659fe4a7639a4492c9b5abc4c228cc1c8f2c2f24ce2062c` |
| status 5 same confirmation/disposition replay | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `7fe9e01d6cba7af6c48aff7b6a459cfc1116a9bfbc742574a8da501cc954e208` | `180076526816411f7c4d0b16b6cb01a0487496f756c7dc3036bb2884e46bf596` |

The first `provider.json` stderr digest above is intentionally the exact
empty-stream digest; the complete value is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Likewise, all shortened-looking values in this prose are expanded in the
receipt and files; no stream was truncated.

## Criterion dispositions (C01–C41, CP01–CP11)

Evidence status is based on source inspection, the independent transcripts,
and the frozen acceptance wording. A green count does not repair an omitted
behavioral door.

| Criterion | Status | Exact source/evidence |
|---|---|---|
| C01 | UNEVIDENCED | `phase_result.py`: `SchedulingCondition`, `DispatchOutcome`; `PhaseResult.from_dict` exists, but no complete six-kind round-trip/unknown-field behavioral proof. |
| C02 | NOT_MET | `test_worker_disposition.py::test_dispatch_outcome_incompatible_payload_matrix` constructs the six cases, then exercises decode/validation/raw `_append_nbf` only for the repaired worker+success pairing; it does not exercise the required complete matrix through public `append_terminal_outcome`/`append_disposition`. |
| C03 | MET | `DispatchOutcome.__post_init__`; no-launch requires `not_started`; focused transcript `focused.json`. |
| C04 | MET | `DispatchOutcome` and `WorkerDisposition` required receipt/fingerprint/phase/spec/logical-worker/timing fields; focused transcript. |
| C05 | MET | Worker-disposition constructor and terminal validator reject provider/no-launch/ordinary-failure payloads; focused and worker-terminal transcripts. |
| C06 | MET | `phase_result_classify.py::terminal_outcome_kind` preserves `worker_disposition`; terminal writer uses the same outcome kind. |
| C07 | MET | `IncidentLedger.append_terminal_outcome` checks one committed disposition and idempotent matching linkage; `test_disposition_terminal_links_existing_record_once`. |
| C08 | MET | `classify_dispatch_outcome` is lossless; `test_outcome_never_coerces_disposition_to_failure`. |
| C09 | MET | `test_two_process_terminal_linkage_is_atomic` uses distinct terminal IDs, conflicting kinds, two forked OS processes, and fresh winner replay; `cross_tx_full.json`. |
| C10 | MET | `append_controlled_adapter_state` is required and marker context is matched before terminal append; transaction tests. |
| C11 | MET | Keyed reducer and named non-latest stream tests in `test_provider_route_projection.py`; `provider.json`. |
| C12 | MET | No-launch/unresolved have no terminal branch; reconciliation and focused tests. |
| C13 | NOT_MET | `_typed_worker_identity` is strong in source, but the named matrix does not cover missing/fabricated typed identity at every decode and append door; current test only has selected bare-string/version omissions. |
| C14 | MET | Positive OOM and legal unknown death append paths plus rejection paths; worker-disposition tests. |
| C15 | MET | `WorkerDisposition.deterministic_id` distinguishes SIGTERM/SIGKILL; focused transcript. |
| C16 | MET | `SemanticDispatchFingerprint.VOLATILE` excludes logical/family/liveness identities; provider test. |
| C17 | MET | Route-liveness digest/generation are excluded from semantic/provider keys; provider test. |
| C18 | MET | Reservation key is projection key plus semantic fingerprint; same-fingerprint/different-logical-ID test. |
| C19 | NOT_MET | `schema.py::_validate_changed_precondition_wire` validates self-consistent snapshots, while `ledger.py::_append_nbf` accepts them without typed source handles; independent wire probe accepted a coherently recomputed forged event. |
| C20 | NOT_MET | `append_changed_precondition` is guarded, but the canonical wire append door is not; producer provenance is therefore not enforced at every authorization boundary. |
| C21 | NOT_MET | `wire_forgery_probe.json` shows `validate_nbf_event` and raw `_append_nbf` both accepted recomputed forged snapshots/IDs and the forged event projected. |
| C22 | MET | Valid producer consumption is single-use under `_locked`; changed-producer subset and focused suite. |
| C23 | MET | `append_probe_result` requires an existing unexpired matching lease; provider suite. |
| C24 | MET | Changed-key replay rekeys and key-preserving change keeps one old stream; provider suite. |
| C25 | MET | Real `fcntl.flock` two-process reservation contention yields one winner; `cross_tx.json`. |
| C26 | MET | Composite payload has no child receipt input; schema and provider replay tests. |
| C27 | MET | `test_fresh_replay_composite_receipt_is_byte_identical` reopens a real composite ledger and derives the same receipt. |
| C28 | MET | Pre-append `_emit_locked` failure and post-append pre-return failure both reopen correctly; `cross_tx_full.json`. |
| C29 | MET | `_project_records` applies terminal provider/fingerprint effects before closure; terminal tests. |
| C30 | MET | Matching accepted provider exhaustion increments its keyed stream. |
| C31 | MET | Nonmatching key starts/rekeys at one. |
| C32 | MET | Non-latest success resets only its applicable key; provider suite. |
| C33 | MET | Non-latest ordinary failure/disposition breaks only applicable stream without degradation. |
| C34 | MET | Canonical passed probe, lease, recovery producer, one-use authorization, and negative matrix are exercised. |
| C35 | MET | Scheduling/no-launch/unresolved branches do not mutate provider streams; focused/provider suites. |
| C36 | MET | Positive no-launch and ambiguous reconciliation paths remain intact; not reopened. |
| C37 | MET | Recovered terminal/disposition linkage and idempotent replay remain intact; not reopened. |
| C38 | MET | Blind/accepted-launch no-launch releases reject; not reopened. |
| C39 | NOT_MET | `ledger.py::consume_confirmation` compares the fields, but `test_confirmation_compares_pid_start_progress_incarnation_cause` omits evidence-digest mismatch/omission from the required full matrix. The seven-test suite is green but does not prove every frozen equality case. |
| C40 | UNEVIDENCED | The packet explicitly excludes broad cache-mismatch expansion; no complete cache-failure matrix is evidenced. |
| C41 | MET | Independent subprocesses prove statuses 0, 2, 3, 4, and 5, including expired and same consumed replay; CLI table above. |

| Checkpoint | Status | Evidence |
|---|---|---|
| CP01 | MET | Frozen focused suite exits 0 with 121 passed; unchanged ledger test included. |
| CP02 | NOT_MET | C02/C13 and C19–C21 remain incomplete/false under the required doors. |
| CP03 | MET | Lossless worker-disposition kind, prior canonical disposition linkage, and one terminal record pass. |
| CP04 | MET | One `_IncidentEventJournal`, one sequence-sidecar flock, and one `events.jsonl`; source and focused/transaction behavior. |
| CP05 | MET | Only accepted `worker_terminal_outcome(outcome_kind=provider_exhausted)` enters the observation increment branch. |
| CP06 | MET | Lease-bound passed probe and producer-derived single-use recovery child preserve the existing keyed streak; provider suite. |
| CP07 | MET | Numeric non-latest keyed reset/break/replay tests pass. |
| CP08 | MET | Distinct terminal race and pre/post-append composite crash tests pass. |
| CP09 | MET | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are distinct types/states. |
| CP10 | MET | No second journal/store/scheduler/rotator/family lease entered scope. |
| CP11 | NOT_MET | C02/C13/C19–C21/C39 and the corresponding rework evidence requirements are not all met. |

## Rework task dispositions (RW4-01…RW4-06, RW4-GATE, A3-01…A3-09)

| Work item | Status | Evidence |
|---|---|---|
| RW4-01 | NOT_MET | Public `append_changed_precondition` rejects forged dicts, but `validate_nbf_event` and raw canonical `_append_nbf` accept a coherent recomputed forged event (`wire_forgery_probe.json`, stdout SHA-256 `4a292ceb0c1dff3ce9d26125ab82293e6bf5f2013cc8e77be48bec111aabd6aa`). |
| RW4-02 | NOT_MET | The implementation's strict validators are present, but the mandated named matrix is not a full four-door matrix; its only append proof uses private `_append_nbf`, not public terminal/disposition append. |
| RW4-03 | MET | Provider suite has all required non-latest numeric isolation, restart, lease, passed-probe, recovery, and negative replay cases. |
| RW4-04 | MET | Required distinct-ID two-process terminal race and distinct pre/post-append composite failure tests pass. |
| RW4-05 | NOT_MET | The required confirmation test covers identity/TTL/policy/version cases but not explicit evidence-digest mismatch and omission. |
| RW4-06 | MET | Attempt-4 finding/receipt include exact HEAD/base/packet identities, all owned full SHA-256 and git-blob inventory, complete command metadata/stream hashes, independent CLI records, and the verbatim broad-sweep path. |
| RW4-GATE | UNEVIDENCED | This independent reviewer cannot issue the separate Grok Oracle gate or `PASS_BATCH_1`. |
| A3-01 | MET | Persisted accepted marker is required; terminal cannot self-authorize acceptance. |
| A3-02 | NOT_MET | Full required six-kind/four-door payload and typed-identity matrix remains absent from the named test. |
| A3-03 | NOT_MET | Coherent wire forgery survives `validate_nbf_event` and `_append_nbf`. |
| A3-04 | MET | Applicable keyed stream behavior is numerically covered. |
| A3-05 | MET | Passed canonical probe and unexpired matching lease are required before child reservation. |
| A3-06 | MET | Distinct terminal race and composite crash/reopen behavior are covered. |
| A3-07 | NOT_MET | Full confirmation equality evidence matrix lacks explicit second-evidence mismatch/omission proof. |
| A3-08 | MET | Attempt-4 immutable executor evidence protocol is materially complete. |
| A3-09 | MET | `reserve_provider_route_child_with_receipt` is absent; supported route-child and receipt APIs remain. |

## Independent probes

### Authoritative producer and coherent-forgery probe

The independent `independent_probe.json` rebuilt source snapshots, content IDs,
evidence digest, and event ID. It recorded:

- valid typed source-reader event append: accepted;
- valid typed source-reader event consume: accepted;
- second valid consume: rejected;
- forged decode: rejected;
- forged public `append_changed_precondition`: rejected;
- forged public consume: rejected.

That proves the public reason-specific path is guarded. It does not erase the
separate wire-door result below.

### Wire authorization-boundary probe

`wire_forgery_probe.json` independently rebuilt a valid source-revision event's
after snapshot, after content ID, event ID, and all self-consistent wire data,
then called:

1. `validate_nbf_event(forged)` — **accepted**;
2. `IncidentLedger._append_nbf(forged)` — **accepted**;
3. fresh projection — forged changed-precondition event present.

This is the remaining blocker: the wire validator and the canonical private
append door treat self-consistency as authority. It contradicts RW4-01's
three-door provenance requirement and the North Star's one-door invariant.

## Broad-suite relevance classification

The full required sweep exited 2 during collection. Its complete stdout is
`/tmp/oracle-nbf01-rework4-luna-review/broad.stdout` (stdout SHA-256
`fe5ee29bc0a5dc6c64b50b148a20f01128422c47042d84b06570ce0f2fee817e`), with
empty stderr digest
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
It failed only while collecting:

- `test_cli_check_validator.py` importing absent
  `arnold.agent.costing.model_resource_capabilities`;
- `test_key_pool_codex.py` importing absent `tools.environments.singularity`.

Independent relevance proof recorded `owned_diff_reaches_blockers=no`; both
modules are absent on the candidate and at `origin/main`; no owned attempt-4
file introduced or newly reached either import. Classification:
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` for both. This reduces broad coverage but
does not waive any in-scope NBF criterion.

## Preserved prior-MET result

The focused 121-pass observation, legacy 78-pass observation, unchanged
legacy ledger hash, one-journal/sequence-sidecar lock, marker-bound terminal
projection, OOM/unknown-death positives, keyed streak mechanics, canonical
probe lease binding, composite replay/crash behavior, durable confirmation
restart/replacement/expiry/single-consumer behavior, CLI status matrix, and
absence of later-batch files are preserved. The current focused count is an
observation, not an acceptance target.

The following historical evidence remains untouched and labeled historical:
start-gate focused **52→61** mutation; unreproducible owned-source digest
`4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`; prior
failed-handoff digest `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`;
attempt-1 focused/legacy 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`;
attempt-2 production digest
`16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`; and
attempt-3 production digest
`8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`.

## North Star

- **One door per invariant:** MET for this NBF-01 ledger primitive only. The
  one `_IncidentEventJournal` and one lock door are preserved. RW4-01 is not
  fully met because the raw wire append door accepts self-consistent forged
  authority; this is the concrete one-door defect. Admission/death physical
  doors remain later scope and are not claimed here.
- **Deaths speak:** MET for the owned typed disposition/observed-death records
  and non-signalling CLI. Repository-wide signal-site wiring remains later
  scope; no later behavior is falsely claimed.
- **Models are admitted, not assumed:** UNEVIDENCED for this NBF-01 slice; no
  admission callers or live route membership are owned here.
- **Fixes ship on main:** UNEVIDENCED/NOT YET APPLICABLE to this uncommitted
  Batch-1 candidate. No deployed-only hotfix was observed; delivery remains a
  later guarded gate.

Anti-pattern review:

- Single-scan truth is reduced by durable confirmation, but C39's complete
  equality evidence is not met.
- Anonymous exits are not used by the owned disposition/CLI primitive.
- Judgment-only health is not introduced by this batch.
- Identical-fingerprint redispatch is blocked by the reservation CAS on the
  guarded public path, but the wire append bypass can mint a forged change
  authorization.

## KISS / YAGNI / scope

The candidate preserves one journal, one flock, one projection, and one
terminal writer; no second store, scheduler, rotator, family lease, or later
policy entered the diff. That is aligned with KISS. The remaining producer
implementation is not fully clean: `ChangedPrecondition.from_dict` includes
its process-local `_source_handles` in the dataclass-field check and then
unconditionally raises, while `_validate_changed_precondition_wire` accepts
self-consistent caller snapshots. This split both over-restricts legitimate
serialized replay and leaves the lower-level wire append permissive. The
smallest fix is not a new framework: make every changed-precondition append
use the existing reason-specific authoritative reader/handle contract, and
make the wire/private append reject or route changed-precondition payloads
without a producer-bound handle.

The confirmation implementation does compare the omitted evidence field in
`consume_confirmation`; the issue is the mandated behavioral matrix and
receipt evidence, not a claim that this specific comparison is absent.

## Evidence integrity

All Oracle-bound identities for source, branch, base, North Star, plan v8,
frozen tasklist, custody, agent goal, model-policy receipt, attempt-4 packet,
executor finding, and executor receipt were independently hashed. The
production diff and every owned-file hash matched the supplied inventory.
The full broad output is retained verbatim at the isolated root. The
attempt-4 executor finding and receipt were read as evidence, not treated as
proof; their claims were checked against fresh commands and the candidate
source.

No historical attempt-1/2/3 artifact was rewritten. The only worktree writes
in this review are this check-in and the immutable review receipt. Temporary
scripts, probes, ledger roots, and all command transcripts are under the
isolated review root. No production/test/plan/frozen-tasklist/North-Star/custody
file was mutated. No commit, push, merge, rebase, reset, clean, Batch-2 start,
second review, or `PASS_BATCH_1` action occurred.

## Issues

1. **blocker — coherent changed-precondition forgery remains accepted at the
   wire append door (C19–C21, RW4-01, A3-03).**
   `arnold_pipelines/megaplan/incident/schema.py::_validate_changed_precondition_wire`
   derives and checks hashes from caller-provided snapshots, but does not
   require producer-bound source handles. `IncidentLedger._append_nbf` calls
   only that validator. The independent `wire_forgery_probe` rebuilt the
   after snapshot, content ID, event ID, and all self-consistent fields; both
   `validate_nbf_event` and `_append_nbf` accepted it and the forged event
   projected. Public `append_changed_precondition` is guarded, but the ledger's
   canonical NBF append door is not. Smallest correction: keep one journal and
   lock, but route changed-precondition payloads through the matching
   reason-specific producer/handle validation at every append path; reject
   caller-shaped wire snapshots at decode/private append rather than treating
   self-hash equality as provenance. Add the independent wire-door regression.

2. **major — required four-door payload/identity matrix is not actually
   present (C02/C13, RW4-02, A3-02).**
   `test_worker_disposition.py::test_dispatch_outcome_incompatible_payload_matrix`
   has constructor cases for the six kinds, but only the repaired
   worker-disposition+success-payload case is sent through `from_dict`,
   `validate_nbf_event`, and private `_append_nbf`. It does not drive the full
   illegal-payload matrix through public `append_terminal_outcome` and
   `append_disposition`, and the identity test covers selected omissions rather
   than every missing/fabricated worker/observed/non-worker identity at each
   door. Green `rw402`/focused counts do not satisfy the named acceptance.
   Smallest correction: strengthen the existing named tests in place with the
   complete six-kind payload matrix and typed-identity omission/fabrication
   cases at direct construction, decode, `validate_nbf_event`, and real public
   locked append doors; preserve the legal OOM/unknown/non-worker positives.

3. **major — confirmation evidence-digest equality is not fully evidenced
   (C39, RW4-05, A3-07).** `ledger.py::consume_confirmation` does compare
   `second_evidence_digest` to the persisted first digest, but
   `test_confirmation_compares_pid_start_progress_incarnation_cause` never
   mutates or omits the evidence input. The required full matrix therefore
   does not prove evidence mismatch/omission even though the seven-test suite
   passes. Smallest correction: add explicit wrong and missing second-evidence
   cases to that existing matrix, retaining restart, replacement, expiry,
   consumed-state, and OS-process race tests.

## Recommendation

The candidate has strong keyed replay, canonical probe leases, composite
atomicity, typed dispositions, and CLI regression behavior. It does not meet
the frozen rework packet because the coherent-forgery authorization boundary
remains bypassable and two required behavioral evidence matrices are still
incomplete. The smallest concrete attempt-5 triage action is to close the raw
changed-precondition wire/private-append door first, then strengthen the
existing RW4-02 four-door payload/identity test and RW4-05 evidence equality
case; rerun the frozen focused and required subset commands and capture fresh
executor evidence. Do not widen into admission, scheduling, signals, T8
policy, custody, or broad environment repair.

RECOMMEND_ACCEPTED_ISSUES
