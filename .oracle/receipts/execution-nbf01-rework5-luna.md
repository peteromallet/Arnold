# Executor receipt — NBF-01 Batch 1 rework 5

## Invocation

- Model: `codex:gpt-5.6-luna`
- Reasoning: high
- Role: leaf executor inside the frozen attempt-5 pipeline
- Serial tasks: `RW5-01 → RW5-02 → RW5-03`
- Repository/cwd for repository commands: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Evidence/transcript directory: `/tmp/oracle-nbf01-rework5-luna/`
- No nested orchestrator, reviewer, Oracle verdict, commit, stage, push, merge, rebase, reset, or Batch 2 action.
- Existing dirty worktree and orchestrator-owned artifacts were preserved.

## Candidate and input identities

- HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Branch: `megado-nbf-guard-0826`
- Source/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Attempt-5 packet: `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7`
- Attempt-5 triage receipt: `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a`
- Attempt-5 execution brief: `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a`
- Frozen tasklist: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 `.oracle/plan.md`: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Agent goal: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Custody: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Attempt-4 Luna check-in: `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`
- Attempt-4 Luna receipt: `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee`
- Attempt-4 Grok check-in: `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf`
- Attempt-4 Grok receipt: `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607`
- Attempt-4 packet: `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- Attempt-4 triage receipt: `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- Attempt-4 executor finding: `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- Attempt-4 executor receipt: `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`
- Attempt-4 reviewed production diff baseline: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

## Exact command transcript manifest

Every listed command was run with cwd `/Users/peteromalley/Documents/Arnold-oracle-nbf`. Complete stdout/stderr are stored at the paths below. `command-manifest.json` is the structured manifest with exact argv, start/end UTC timestamps, exit codes, paths, and stream SHA-256s. Empty streams use their full SHA-256, not a pass-count substitute.

| Label | Exact argv | Exit | Start UTC → end UTC | stdout path / SHA-256 | stderr path / SHA-256 |
|---|---|---:|---|---|---|
| `rw5-01-targeted` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py` | 0 | `2026-08-30T04:07:02.019179+00:00` → `2026-08-30T04:07:06.775721+00:00` | `/tmp/oracle-nbf01-rework5-luna/rw5-01-targeted.stdout` / `2892f3c51b7158205f3080cea4d2ff8f225fd63aee99fd3b57f2d764b379e5bd` | `/tmp/oracle-nbf01-rework5-luna/rw5-01-targeted.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `rw5-02-named-matrix` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | 0 | `2026-08-30T04:07:06.776603+00:00` → `2026-08-30T04:07:39.961207+00:00` | `/tmp/oracle-nbf01-rework5-luna/rw5-02-named-matrix.stdout` / `951c4fd49bef94f93b2505bffb3f60bc779e1fbca89f333419ac49f33dd6e1ad` | `/tmp/oracle-nbf01-rework5-luna/rw5-02-named-matrix.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `rw5-03-confirmation` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` | 0 | `2026-08-30T04:07:39.962141+00:00` → `2026-08-30T04:07:44.935089+00:00` | `/tmp/oracle-nbf01-rework5-luna/rw5-03-confirmation.stdout` / `c0bb7edc122a2f852497ff28990e7e83659dd02337712c5e74fd90608cb7ad4a` | `/tmp/oracle-nbf01-rework5-luna/rw5-03-confirmation.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `focused-suite` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py` | 0 | `2026-08-30T04:07:44.935745+00:00` → `2026-08-30T04:08:13.744956+00:00` | `/tmp/oracle-nbf01-rework5-luna/focused-suite.stdout` / `d750360f18ed14e2e55fd423583e52d47f72eb8311d6ac45246f678856e0a057` | `/tmp/oracle-nbf01-rework5-luna/focused-suite.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `legacy-suite` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py` | 0 | `2026-08-30T04:08:13.745663+00:00` → `2026-08-30T04:08:21.432281+00:00` | `/tmp/oracle-nbf01-rework5-luna/legacy-suite.stdout` / `73e705395e04542e2550e9e1ff5a548e4d80f9a8c60ee1065187d060d7af2fdd` | `/tmp/oracle-nbf01-rework5-luna/legacy-suite.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `cli-subprocess-matrix` initial probe | `python /tmp/oracle-nbf01-rework5-luna/cli_matrix.py` | 1 | `2026-08-30T04:08:21.449037+00:00` → `2026-08-30T04:08:24.313725+00:00` | `/tmp/oracle-nbf01-rework5-luna/cli-subprocess-matrix.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `/tmp/oracle-nbf01-rework5-luna/cli-subprocess-matrix.stderr` / `65b31a0482df05b6c5d7de791d49c3857dd67036b90265065b5ec871244c8aa8` |
| `compile-check` | `python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | 0 | `2026-08-30T04:08:24.314454+00:00` → `2026-08-30T04:08:24.495487+00:00` | `/tmp/oracle-nbf01-rework5-luna/compile-check.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `/tmp/oracle-nbf01-rework5-luna/compile-check.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `diff-check` | `git diff --check` | 0 | `2026-08-30T04:08:24.496368+00:00` → `2026-08-30T04:08:24.559186+00:00` | `/tmp/oracle-nbf01-rework5-luna/diff-check.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `/tmp/oracle-nbf01-rework5-luna/diff-check.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `broad-sweep` | `python -m pytest -q tests/arnold_pipelines/megaplan` | 2 | `2026-08-30T04:08:24.559741+00:00` → `2026-08-30T04:08:46.802212+00:00` | `/tmp/oracle-nbf01-rework5-luna/broad-sweep.stdout` / `5a967bd2465a63ea0e7dcd6498840ae24cbcb8a2e524e64c7d4426111e1f09bc` | `/tmp/oracle-nbf01-rework5-luna/broad-sweep.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `final-production-diff` | `git diff -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py \| shasum -a 256` | 0 | `2026-08-30T04:08:46.803082+00:00` → `2026-08-30T04:08:46.948582+00:00` | `/tmp/oracle-nbf01-rework5-luna/final-production-diff.stdout` / `eb25e277adf5c097d6069bc25ca461589c8f471ce2b1696a0b15fa4a17ee9660` | `/tmp/oracle-nbf01-rework5-luna/final-production-diff.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The initial CLI probe failed before exercising the matrix because invoking a `/tmp` script omitted the repository from `sys.path`; its complete traceback is preserved. The corrected exact command `python /tmp/oracle-nbf01-rework5-luna/cli_matrix.py`, run from the repository root, exited `0`. Corrected streams: stdout `/tmp/oracle-nbf01-rework5-luna/cli-rerun.stdout`, SHA-256 `e646d70f5f9a21d4c5d69293538a3920cbc9a4dd77c93b589dd1a2b93e5cfd6e`; stderr `/tmp/oracle-nbf01-rework5-luna/cli-rerun.stderr`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; structured transcript `/tmp/oracle-nbf01-rework5-luna/cli-cases.json`, SHA-256 `94930a13670a6390f63a753395bb54f9a4fd48e8f697d4c086e2d570804e09b7`. Each CLI case records exact payload, ledger root, argv, UTC timestamps, status, complete stdout/stderr, and stream digests. Cases measured statuses 0, 2, 3, 4, 5, expired 5, successful seed 0, and already-consumed replay 5.

The strengthened RW5-01 test was run against a temporary unmodified attempt-4 source state and failed exactly at the open `validate_nbf_event` assertion: `1 failed, 7 passed`, pytest exit `1`. Transcript: `/tmp/oracle-nbf01-rework5-luna/pre-fix.stdout`, SHA-256 `58bd170a5b0333811b00cf308822b5d28a3ded858756bc1f097b942d13354295`; stderr was empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. After restoring the fix and the complete forged-key mutation, the final exact RW5-01 command exited `0` with `8 passed`: stdout `/tmp/oracle-nbf01-rework5-luna/final-rw5-01.stdout`, SHA-256 `f4cda9e14392d1b54ff71b5db7c69b85265cff308f9065e46be91a6e96c168dc`; stderr was empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The final exact frozen focused suite also exited `0` with `123 passed`: stdout `/tmp/oracle-nbf01-rework5-luna/final-focused.stdout`, SHA-256 `aa434b7d32d02881839177b184fc404ae9d609000078a8683503e9955b84e21c`; stderr was empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Timestamped exact argv/start/end/stream metadata for both final reruns is `/tmp/oracle-nbf01-rework5-luna/final-command-manifest.json`, SHA-256 `6bd28bb5fc321cb82d706b7c396d5db4aabb7976cddb17b5fce448500de22a14`.

## Evidence-integrity supplemental command matrix

The evidence-sealing pass reproduced every existing manifest/stream hash and found that the executor manifests omitted distinct packet-specific focused invocations. Only those missing focused commands were run; the broad sweep was not rerun. The sealing runner captured streams in memory so that the instruction limiting writes to this finding and receipt remained satisfied. Complete stdout is represented below as a JSON string, preserving every byte including spaces and terminal newline; every stderr stream was the empty string `""` with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### `packet-rw5-01-filter`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py","-k","coherent_forged or valid_reason_specific_source_reader or forged or producer or authoritative"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:25:10.122904+00:00` → `2026-08-30T04:25:14.494849+00:00`
- Exit: `0`
- Complete stdout: `"........                                                                 [100%]\n8 passed in 0.33s\n"`
- Stdout SHA-256: `549ca11e4fe3df25ea1c34a3bac944e6e63975250497b6adc3e172fa62165968`

### `packet-rw5-01-transaction-filter`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py","tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py","-k","precondition or consumed_change or forged or producer or authoritative"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:25:14.494985+00:00` → `2026-08-30T04:25:17.860362+00:00`
- Exit: `0`
- Complete stdout: `".........                                                                [100%]\n9 passed, 16 deselected in 0.30s\n"`
- Stdout SHA-256: `077fdcc1f0e1a636fffd4911c7cde39d6bb0838f566fac884a22e51a4a254a0c`

### `packet-focused-order`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_worker_disposition.py","tests/arnold_pipelines/megaplan/test_scheduling_conditions.py","tests/arnold_pipelines/megaplan/test_provider_route_projection.py","tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py","tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py","tests/arnold_pipelines/megaplan/test_terminal_outcomes.py","tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py","tests/arnold_pipelines/megaplan/test_supervision_confirmation.py","tests/arnold_pipelines/megaplan/test_incident_ledger.py"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:25:17.860431+00:00` → `2026-08-30T04:25:52.509492+00:00`
- Exit: `0`
- Complete stdout: `"........................................................................ [ 58%]\n...................................................                      [100%]\n123 passed in 31.40s\n"`
- Stdout SHA-256: `94c6773260697bcf7dd9668753cf8b7f22be4cbe51c83e008892d20d2f0ec949`

### `packet-rw5-02-filter`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_worker_disposition.py","-k","incompatible_payload or observed_and_non_worker or legal_positive_oom or legal_unknown_death or worker_disposition_rejects_success"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:25:52.509556+00:00` → `2026-08-30T04:25:57.108307+00:00`
- Exit: `0`
- Complete stdout: `".....                                                                    [100%]\n5 passed, 18 deselected in 0.33s\n"`
- Stdout SHA-256: `a54c4b1cbd3988e11b462a309eb96926b0c3a0cbb26129ecfea0e4f0b947355b`

### `packet-rw5-03-node`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_supervision_confirmation.py::test_confirmation_compares_pid_start_progress_incarnation_cause"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:25:57.108386+00:00` → `2026-08-30T04:26:03.955258+00:00`
- Exit: `0`
- Complete stdout: `".                                                                        [100%]\n1 passed in 0.63s\n"`
- Stdout SHA-256: `1ab9905d8b0f34f6d791ff7da4efa2de0f7f3e282a078758cc0496cc0230c0f0`

### `packet-rw5-03-filter`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_supervision_confirmation.py","tests/arnold_pipelines/megaplan/test_worker_disposition.py","-k","cli_status or confirmation"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:26:03.955396+00:00` → `2026-08-30T04:26:42.741488+00:00`
- Exit: `0`
- Complete stdout: `"..............                                                           [100%]\n14 passed, 16 deselected in 32.81s\n"`
- Stdout SHA-256: `ff43897fc09696941b9bff4512f813c1f5c75ba6423ebaaf338d4f7e8b5ba524`

### `packet-compile-order`

- Exact argv: `["python","-m","py_compile","arnold_pipelines/megaplan/orchestration/phase_result.py","arnold_pipelines/megaplan/orchestration/phase_result_classify.py","arnold_pipelines/megaplan/incident/schema.py","arnold_pipelines/megaplan/incident/ledger.py","arnold_pipelines/megaplan/incident/disposition.py"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:26:42.741686+00:00` → `2026-08-30T04:26:43.301000+00:00`
- Exit: `0`
- Complete stdout: `""`; stdout SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### `packet-rw5-01-module`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:29:20.827641+00:00` → `2026-08-30T04:29:25.412592+00:00`
- Exit: `0`
- Complete stdout: `"........                                                                 [100%]\n8 passed in 0.36s\n"`
- Stdout SHA-256: `28dc6d5399d1981687db3d419b9bcba5286cae926208993213af8e03278ceb43`

### `packet-rw5-02-modules`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_scheduling_conditions.py","tests/arnold_pipelines/megaplan/test_worker_disposition.py","tests/arnold_pipelines/megaplan/test_terminal_outcomes.py"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:29:25.412700+00:00` → `2026-08-30T04:30:02.565317+00:00`
- Exit: `0`
- Complete stdout: `"...........................                                              [100%]\n27 passed in 31.00s\n"`
- Stdout SHA-256: `e86ae1ecdfb9dffc77d7391531645e560a463cda596d5f2578808c09582a0acc`

### `packet-rw5-03-module`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_supervision_confirmation.py"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:30:02.565412+00:00` → `2026-08-30T04:30:09.884380+00:00`
- Exit: `0`
- Complete stdout: `".......                                                                  [100%]\n7 passed in 0.65s\n"`
- Stdout SHA-256: `278a41d40d756996f4a45abed8fa499e149c479579ca17bede72ae52a86954f3`

### `packet-legacy-order`

- Exact argv: `["pytest","-q","tests/arnold_pipelines/megaplan/test_incident_projection.py","tests/arnold_pipelines/megaplan/test_incident_summaries.py","tests/arnold_pipelines/megaplan/test_incident_bridge.py","tests/arnold_pipelines/megaplan/test_phase_result_classify.py"]`
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- UTC: `2026-08-30T04:30:09.884457+00:00` → `2026-08-30T04:30:21.238327+00:00`
- Exit: `0`
- Complete stdout: `"........................................................................ [ 92%]\n......                                                                   [100%]\n78 passed in 2.86s\n"`
- Stdout SHA-256: `9ef283caa33d9a432c1a297931086fa3818d305a60127da675b851150e5d172e`

The packet's repeated focused/legacy/compile/diff commands collapse to the distinct invocations above plus the already-verified `git diff --check` entry. The required broad sweep remains exactly the one captured invocation at `2026-08-30T04:08:24.559741+00:00` → `2026-08-30T04:08:46.802212+00:00`, exit `2`, classified `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`; no sealing command invoked the broad suite.

## Final identity and file inventory

Final identity recorder manifest: `/tmp/oracle-nbf01-rework5-luna/identity-results.json`, SHA-256 `bf68ef60ba5d61bd8a0026e1e5fcb28be39b4a469cd4613dfb5a1a45031fbb16`; its stdout transcript SHA-256 `5ae7ca518a37a02d7351cd1049b989c74a9b3db1ee74052f5914b8feaf893924`; stderr is empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The final owned production diff digest is `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.

Each inventory line gives `path — git hash-object; full SHA-256`:

- `arnold_pipelines/megaplan/incident/__init__.py` — `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b`; `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923`
- `arnold_pipelines/megaplan/incident/ledger.py` — `192f68694ad7cd29c1d28f74539fc7b9f2a82734`; `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9`
- `arnold_pipelines/megaplan/incident/schema.py` — `eedfad759321236ed217cc71943227a7cd122bca`; `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1`
- `arnold_pipelines/megaplan/incident/disposition.py` — `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3`; `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5`
- `arnold_pipelines/megaplan/orchestration/phase_result.py` — `eb60256d6d4501dc97a37b90fe92191a611878ae`; `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` — `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5`; `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641`
- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py` — `0773a0f629712065d4f410502b316155f4b8cf89`; `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215`
- `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py` — `c91963087ae35fce9f50ae322663825e4642bb59`; `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8`
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py` — `6de73b1e16d59ade8c22c5428dfdad5b660b072c`; `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949`
- `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py` — `2d2ec909688040de467fb82f16e0676c1e69e8cd`; `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e`
- `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py` — `fc54999a025f23d89860facda94b260d1d7e5bb3`; `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb`
- `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` — `2a5a3a88cbae92d69260c93525246846adeb3547`; `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` — `1dcb901b9623e320642f4b96dae499e0c8e336a2`; `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915`
- `tests/arnold_pipelines/megaplan/test_worker_disposition.py` — `45b23313a67229de5d3bbb1c896ab7729b4d09da`; `61d85e93036f00426a857136dc3ca10a01b233128b8984b0cc02b75dfaa28a84`
- `tests/arnold_pipelines/megaplan/test_incident_ledger.py` — `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`; `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` (unchanged legacy coverage)

Tracked `git diff --name-only` output and its SHA-256 are in `identity-results.json`; it contains no later-batch source/test path. No historical or custody artifact was edited by this execution. The only executor-owned `.oracle` writes are this receipt and the matching finding; source/test writes are the exact owned paths inventoried above.

Executor finding artifact SHA-256 after evidence sealing: `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197`.

No Oracle token, acceptance claim, or batch decision is present in this receipt.
