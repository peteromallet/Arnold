# Receipt — NBF-01 Batch 1 rework 6 executor

## Invocation

- Model: `codex:gpt-5.6-luna`.
- Reasoning: high.
- Role: sole Normal leaf executor and one writer.
- Authorized task: `RW6-01 — C02/C13 complete six-kind/four-door payload and typed-identity matrix`.
- Invocation metadata: sealed attempt-6 leaf execution; no delegated worker,
  nested harness, reviewer, or orchestrator.
- Repository cwd for every recorded command:
  `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
- Fresh evidence root:
  `/tmp/oracle-nbf01-rework6-luna-final-0830/`.
- Recorded evidence window:
  `2026-08-30T06:09:17.202777Z` through `2026-08-30T06:10:59.936434Z`.
- Candidate HEAD before and after:
  `922241d0bdb3e993c3b554cc69f19948adef7bc3`.
- Branch: `megado-nbf-guard-0826`.
- Merge-base: `798c50619204010ed3f4297fbb57988fe9381924`.

## Sealed inputs

| Artifact | SHA-256 |
|---|---|
| `.oracle/rework/batch-1-attempt-6.md` | `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83` |
| `.oracle/receipts/rework-triage-batch-1-attempt-6-grok.md` | `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/plan.md` (settled plan v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |

Attempt-5 reviewed production baseline: `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.
The pre-edit six-path production diff was already
`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`, so it
did not match the supplied attempt-5 baseline. This dirty candidate already
contained the RW6-01 source correction. It was preserved; this leaf made no
source or test edits.

## Candidate change observed

The existing test repair is in
`tests/arnold_pipelines/megaplan/test_worker_disposition.py`:

- `test_dispatch_outcome_incompatible_payload_matrix` uses complete legal
  records, mutates one exclusive payload, and reaches all four applicable
  doors with intended payload-family messages;
- `test_incompatible_matrix_rejects_at_public_terminal_append` drives the real
  public terminal append door with complete records;
- `test_typed_identity_matrix_rejects_missing_and_fabricated_worker_at_all_doors`
  covers missing, fabricated, bare, incomplete, wrong-version, and malformed
  host/pid/boot identities;
- `test_worker_disposition_rejects_success_payload_at_append` covers the
  public disposition append door;
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
  covers observed-death and non-worker identity, cause, subject, and version
  boundaries at their applicable doors.

The existing minimal production correction is
`arnold_pipelines/megaplan/incident/schema.py`,
`ObservedProcessDeath.__post_init__`: `victim_identity_evidence` must be a
mapping and non-empty. No `phase_result.py`, `ledger.py`, `incident/__init__.py`,
`incident/disposition.py`, or `phase_result_classify.py` edit was made in this
leaf. No speculative validator change was made.

## Command evidence

The preflight manifest is
`/tmp/oracle-nbf01-rework6-luna-final-0830/preflight/command-manifest.ndjson`,
SHA-256 `a768f5f8eecf9b25747da59deccc9ca0ecdd3dd825d42476272faaad3e5c8993`.
It records these exact commands, all exit 0, with complete stdout/stderr and
structured transcript paths and digests:

- `git rev-parse HEAD` — stdout digest
  `6eefd4262d52ff083bbc92dc11f69973634a793c3576de7911331cc6911f4542`;
- `git rev-parse --abbrev-ref HEAD` — stdout digest
  `d16a4b7e75934804a550403f7aeaede152310ae73b9091d09b5a60599bed7333`;
- `git merge-base HEAD origin/main` — stdout digest
  `9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430`;
- `git status --short` — stdout digest
  `9fc276e9779ac28f9c5350639579875ab2a8d848f478718f39e27eb4d00d4861`;
- the sealed-input `sha256sum` command — stdout digest
  `36f34c2e8051037c7878d203eb4da00eeb005d663c53cdf73eeae3396d69bfec`;
- the exact six-path `git diff origin/main -- ...` command — stdout digest
  `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`;
- legacy test `sha256sum` — stdout digest
  `94126566fd58e63ac328129cf67950eae38bf1af696197b9981a746a5c059bf5`;
- legacy test `git hash-object` — stdout digest
  `70122f810f17b4580bc2104b29d808f0acbad0c639bfe14c0b1e234929d2926c`.

The validation manifest is
`/tmp/oracle-nbf01-rework6-luna-final-0830/validation/command-manifest.ndjson`,
SHA-256 `ca18c4ee9eb4b7c48ddb8a6f75e073ccad1518577667bd84b4b52738e58658eb`.
Every row below has its complete streams at the listed immutable paths and a
complete structured transcript at the listed JSON path. Empty streams use
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| # | Exact argv | Exit/result | stdout SHA-256 | stderr SHA-256 | Transcript path | Transcript SHA-256 |
|---:|---|---:|---|---|---|---|
| 1 | `python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | 0; 28 passed | `e1b901de52356d4a4f7fbe2acc082fdd083f764e68d041aa8d5094691793299e` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-001.json` | `24d00e0353fc84f7680fbd559965511f0ec1c0fe3c206c141ae64111bd82e643` |
| 2 | `python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"` | 0; 2 passed, 22 deselected | `c15e3b3f685b855afc4ed4a33d067ada47b85290c28b88cf9c3a680f06c7e5c0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-002.json` | `1107909cc9db6c5f907fcaf0f27fb4782f47aea6d0d68e76dbcb2c8412e60992` |
| 3 | `python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"` | 0; 1 passed, 1 deselected | `cbef2dd0385da86eece360e3d0ee595e1117d4e9248047b20d4985e9a3ecff97` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-003.json` | `39bd8dd84b0e2504937f267887e9523e53a0d86ab10b161944b7e4caca9606e1` |
| 4 | `python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py` | 0; 124 passed | `d9bfdba7a5c53164e2664c7c5b12d3d99f2d1464382416d3b56ae1ae81b7c6a7` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-004.json` | `41fd543d0971c1e1e8d79a66b0bd305e64db1ab8a161ce933c0033a6d0bab40f` |
| 5 | `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py` | 0; 42 passed | `745040281d8d7f49095b94c095703a369a4b2acc63334f4f4cca7588618c5991` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-005.json` | `176a2ab4063933d9bcf564662687943de2bd6e9baec9a43e140cecd8abee421c` |
| 6 | `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py` | 0; 78 passed | `1beeac65683fcf647b3d859c3bc90c1fd986b6ed82e0a661b92ee6d13cce93af` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-006.json` | `a02134f5cb8d7a1343644f98d518c44c004229a9899b12da4b57ed44bc1d57e2` |
| 7 | `python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-007.json` | `0faa6fb0774c58dce1d8de83941c9bb9a3f3ac12e7c7673ed7601b870c49eb41` |
| 8 | `git diff --check` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `validation/record-008.json` | `d58abd51da854280e14b8d2ba86c422a79a6e319288069471788c10e03117be0` |

Final identity/diff commands are in
`/tmp/oracle-nbf01-rework6-luna-final-0830/final/command-manifest.ndjson`,
SHA-256 `86eba8e5386bb7599ab55246b52d82eb5ef5555db307e6efba01b20383cdd187`.
They recorded literal `git rev-parse HEAD`, branch, merge-base, the exact
six-path production diff, and `git diff --name-only origin/main`, all exit 0.
Their stdout digests are respectively
`6eefd4262d52ff083bbc92dc11f69973634a793c3576de7911331cc6911f4542`,
`d16a4b7e75934804a550403f7aeaede152310ae73b9091d09b5a60599bed7333`,
`9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430`,
`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`, and
`9697c8b37103d4a2474f4c477ad2046dbab002222f5790ce91c0b760e3c45972`.
All stderr digests are the empty-stream digest above. The final production
diff digest is therefore
`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`.

## File/object inventory

Inventory commands and complete transcripts are in
`/tmp/oracle-nbf01-rework6-luna-final-0830/inventory/command-manifest.ndjson`,
SHA-256 `c10e450501f3cd9a5a30cd6749c28bfa1f339aba815f5eb4e4efa10ffa050362`.
The inventory captured `git ls-files -m`, SHA-256, git object IDs, an
unchanged-legacy `git diff --exit-code`, and the legacy blob. Every modified
tracked file and owned untracked production/test file follows:

| Path | SHA-256 | git object |
|---|---|---|
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | `e1d22bebc5ebe1930e45edb99ed9a2fcce985987` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | `a0372be1ce00f8e9823a07ee82bb6208c6442cd9` |
| `.oracle/findings/plan-settled-W1-synthesis.md` | `12d730fe1625de0d561ecd87647c2f0b5ec575d5b066986cd5b5acce6d70518c` | `9f159c11cdeece386f89db2e11c0ce3cc5b2fd49` |
| `.oracle/rework/batch-1-attempt-1.md` | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` | `facbbc0868d543423cfcf5ae9667b3dd2d4b3ab2` |
| `.oracle/status.md` | `bbcf8bc7f5a0688e136f16f6e63dc80240eb85856be7dc4d1d829b860f585dfc` | `b6d5659fe130921a8d2dc6c7ab28b3fa8595ffdf` |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` | `bda2d0f87d8759c27d708ed886d6edf2cfc76cd7` |
| `arnold_pipelines/megaplan/incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `arnold_pipelines/megaplan/incident/ledger.py` | `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9` | `192f68694ad7cd29c1d28f74539fc7b9f2a82734` |
| `arnold_pipelines/megaplan/incident/schema.py` | `8acb8563adac794d3dc66e39d8db1d12d499207cb5e1b297a395c0a14f640a9d` | `032162bf0efc7b8e14414cd7d6b0738bdf83a613` |
| `arnold_pipelines/megaplan/orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `arnold_pipelines/megaplan/incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py` | `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215` | `0773a0f629712065d4f410502b316155f4b8cf89` |
| `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `tests/arnold_pipelines/megaplan/test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` | `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c` | `2a5a3a88cbae92d69260c93525246846adeb3547` |
| `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `tests/arnold_pipelines/megaplan/test_worker_disposition.py` | `20f60bc664bebe59d9c50a19b6a4fb389cfa4ea54c101bfef6d138f05750aa41` | `59d6ae5a39659fd5858ba10991b702f0396a8cb0` |

Legacy proof: `tests/arnold_pipelines/megaplan/test_incident_ledger.py` remains
unchanged versus `origin/main`; SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`, git blob
`44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`. Its exact `git diff --exit-code`
record exited 0. The tracked diff-name transcript is
`final/record-005.stdout`; it contains only existing Oracle files, existing NBF
production files, and `docs/nbf-grok-verdicts.md`; no later-batch source/test
file entered the diff. The owned untracked source/test inventory is limited to
the existing NBF set shown above.

## Explicit non-actions

No self-review, independent reviewer, commit, stage, push, merge, rebase,
reset, clean, nested harness, broad-suite rerun, Batch 2 action, C41 rerun, or
frozen/history/status/goal/custody/tasklist/plan/North Star mutation occurred.
This receipt contains no Oracle verdict.
