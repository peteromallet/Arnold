# Immutable receipt — GPT-5.6 Luna independent NBF-01 rework-5 review

## Review identity

- Model: `openai-codex/gpt-5.6-luna`
- Reasoning level: high
- Role: exactly one independent Batch-1 rework-5 reviewer
- Review date: 2026-08-30 UTC
- Review completion timestamp: `2026-08-30T04:52:17Z`
- Launcher: current review session; no separate launcher command
- Repository/cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source ref and merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- External transcript/probe root: `/tmp/oracle-nbf01-rework5-luna-review/`
- No production/test/plan/custody/history edit, commit, stage, push, merge,
  rebase, reset, clean, Batch-2 start, or second review was performed.

## Bound artifact identities

| Artifact | SHA-256 |
|---|---|
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| `.oracle/plan.md` settled v8 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` frozen | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/receipts/tasklist-freeze-v8.md` | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |
| `.oracle/rework/batch-1-attempt-5.md` | `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7` |
| `.oracle/receipts/rework-triage-batch-1-attempt-5-grok.md` | `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a` |
| attempt-5 executor finding | `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197` |
| attempt-5 executor receipt | `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160` |
| historical attempt-4 Luna check-in | `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c` |
| historical attempt-4 Luna receipt | `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee` |
| historical attempt-4 Grok check-in | `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf` |
| historical attempt-4 Grok receipt | `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607` |
| historical attempt-4 packet | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` |

Candidate identity commands independently returned HEAD, origin/main, and
merge-base exactly as above. Worktree status is dirty with owned candidate
changes and unrelated `.oracle` noise; no clean-tree claim is made.

## Complete owned path/hash inventory

| Path | SHA-256 | git blob |
|---|---|---|
| `arnold_pipelines/megaplan/incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `arnold_pipelines/megaplan/incident/ledger.py` | `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9` | `192f68694ad7cd29c1d28f74539fc7b9f2a82734` |
| `arnold_pipelines/megaplan/incident/schema.py` | `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1` | `eedfad759321236ed217cc71943227a7cd122bca` |
| `arnold_pipelines/megaplan/incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `arnold_pipelines/megaplan/orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py` | `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215` | `0773a0f629712065d4f410502b316155f4b8cf89` |
| `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `tests/arnold_pipelines/megaplan/test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` | `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c` | `2a5a3a88cbae92d69260c93525246846adeb3547` |
| `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `tests/arnold_pipelines/megaplan/test_worker_disposition.py` | `61d85e93036f00426a857136dc3ca10a01b233128b8984b0cc02b75dfaa28a84` | `45b23313a67229de5d3bbb1c896ab7729b4d09da` |
| `tests/arnold_pipelines/megaplan/test_incident_ledger.py` | `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` | `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |

`test_incident_ledger.py` matches `origin/main` and remains unchanged.

## Production diff identity and scope

Exact commands:

```text
git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256
git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256
```

Both returned exit 0 and digest
`7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.
Transcripts: `production-diff.patch` and `production-diff-five.patch`.

Changed scope is exactly `schema.py` and `ledger.py` among the six production
paths; three named test modules changed. The remaining named production files
and five named test modules are candidate-owned but unchanged by attempt 5.
No admission, scheduler, T7/T8 policy, physical-door, launch, signal-site,
fallback, rotator, second-journal, or later-batch path is in scope.

## Command transcripts

`command-manifest.json` is the complete manifest. Every row records exact argv,
cwd, UTC start/end, elapsed time, exit status, byte lengths, complete stdout
path/digest, and complete stderr path/digest. All commands ran in the stated
repository cwd.

| Label | Exit/result | stdout path / SHA-256 | stderr path / SHA-256 |
|---|---|---|---|
| focused frozen nine-module pytest | 0; `123 passed in 52.35s` | `focused.stdout` / `e47d84bb8367f5a4c5b1c2abc109385c159c72563398ce3c661ef4ebdb08dba7` | `focused.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| legacy four-module pytest | 0; `78 passed in 4.67s` | `legacy.stdout` / `2ec1056eb93e9ec3ef87de80f5228ddbdaad56d5c652c84f93c05025fbf6b94b` | `legacy.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| changed-precondition module | 0; `8 passed` | `rw5-01-module.stdout` / `faad2a048f066402d263a731e67182173f50486382c58da46a5fbfff30212c04` | `rw5-01-module.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| changed-precondition filter | 0; `8 passed` | `rw5-01-filter.stdout` / `b55ef8f059b7c060044332115813ffd363da13410f7511facf5ca7897edd0618` | `rw5-01-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| payload three-module command | 0; `27 passed` | `rw5-02-modules.stdout` / `b0efa8060be35c1197d478c38c498252a6e9b89253d83895692e082010a1347d` | `rw5-02-modules.stderr` / `e3b0c44298fc1c149afbf4c8996fb934ca495991b7852b855` |
| payload required filter | 0; `5 passed, 18 deselected` | `rw5-02-filter.stdout` / `6ff623fe9a7b793fe215f8763c6fd2c012bfd8df3a83f6e8c46929bd8af198b0` | `rw5-02-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| confirmation module | 0; `7 passed` | `rw5-03-module.stdout` / `40b951cae52565860314b0637b01b87ec8f152cb33777b78996e501a0f6a1bcc` | `rw5-03-module.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| named confirmation | 0; `1 passed` | `rw5-03-node.stdout` / `0c33791aa03cbc8826ba04efd1b062adb3baa875c47625e4de7090bd753d7635` | `rw5-03-node.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| CLI/confirmation filter | 0; `14 passed, 16 deselected` | `rw5-03-filter.stdout` / `7797c2071bb4aa8f1e4609a4db27814c1d79abdb20febe487fcf714972919f58` | `rw5-03-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| transaction crash/contention filter | 0; `7 passed` | `crash-filter.stdout` / `5eff248970364c749b4415909c96e713367bcb59407d2f8096afc9411a559650` | `crash-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| provider route projection | 0; `18 passed` | `provider-module.stdout` / `9a94cd775b4eaa3c9e9f779baee5725e48a64315187f192ce45350a08c700cc7` | `provider-module.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| required py_compile | 0 | `compile.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `compile.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git diff --check` | 0 | `diff-check.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `diff-check.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| required broad sweep | 2; two collection errors | `broad.stdout` / `d7a182fedf68bad45198222f2141b63a0d957b31dac30479c089a08db81f2cb6` | `broad.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The manifest is the authoritative exact-argv/timestamp record; the listed
stream files are complete and untruncated.

## Independent CLI subprocess matrix

Complete per-case transcript: `cli-final-cases.json`, SHA-256
`521ba29ae46202155100515dfc86bdd7d11bba1fc78b841ae2aa6f62ac9bfad3`.
Runner stdout: `cli-final.stdout`, SHA-256
`b77d116724244a81e26fa926495f719959f332e09fcc9d08bdc257d797704cbb`.
Runner stderr is empty, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Each JSON row contains exact argv, cwd, root, UTF-8 stdin, UTC times, complete
streams, exit status, and separate stream digests.

| Case | Root | Payload | Exit | stdout SHA-256 | stderr SHA-256 |
|---|---|---|---:|---|---|
| status 0 | `cli-final-ledgers/valid` | valid typed worker disposition with consumed confirmation `cli-disp` | 0 | `409aac1d8187829a23849c4a8d1c9b665ea319601d2859e4e10e452d152c46ea` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| status 2 malformed | `cli-final-ledgers/malformed` | `{` | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` |
| status 2 schema | `cli-final-ledgers/schema` | `{"event_type":"worker_disposition"}` | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` |
| status 3 append/lock | `cli-final-ledgers/append-failure` | valid non-worker lifecycle record; `events.jsonl` directory | 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `238845a1f500ba8d33392dff92166e0bf9b86050a9b76873adc00a168508a5e2` |
| status 4 location | `cli-final-ledgers/not-dir` | valid worker record; root is a file | 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` |
| status 5 missing | `cli-final-ledgers/missing` | valid worker record without confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` |
| status 5 expired | `cli-final-ledgers/expired` | valid worker record referencing expired confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` |
| status 5 consumed replay | `cli-final-ledgers/valid` | valid worker record with `other` disposition on consumed confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655` |

The exact argv for every row is
`python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <root> --json-stdin`.
Status 0 emitted exactly one JSON acknowledgement on stdout, no stderr, and no
signal.

## Independent probes

### RW5-01 authority closure

`independent-probes.stdout` SHA-256:
`38128031bd5e100c5422074752d0533d8f3a49f2a7f6101c85f5db962e7aa908`.
Stderr is empty, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The JSON records a valid reason-specific reader event append, projection,
fresh replay, one-use consume, and coherent forgery checks. Forgery mutated
before/after snapshots, both provider keys, evidence, all relevant content
IDs/digests, and event ID. It was rejected by `ChangedPrecondition.from_dict`,
`validate_nbf_event`, `_append_nbf`, `_append_nbf_locked`, public append,
forged-object consume, and `reserve()`. It did not project or authorize.

### RW5-02 four-door behavior and remaining named-proof defect

`public-matrix.stdout` SHA-256:
`2931e69c8a4a672e3fa7c1d3d6225e3526e766405e05320f27a40c7499c76692`.
Stderr is empty, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The correctly shaped independent probe rejects all six incompatible cases at
construction, `from_dict`, `validate_nbf_event`, public
`append_terminal_outcome`, and public `append_disposition`; it also rejects
missing, bare, and incomplete worker identities and accepts legal OOM,
unknown-death, and non-worker records. `public-matrix.stdout` is complete.

The required *named* matrix is nevertheless incomplete. Its public-terminal
loop passes terminal-event-shaped dictionaries with `outcome_kind` rather than
the `DispatchOutcome.from_dict` discriminator `kind`; those cases fail on
unknown fields before exercising each intended semantic public-terminal door.
The named matrix's decode/validation path explicitly exercises only the repaired
worker-disposition plus success-payload pairing. Its worker-identity matrix
omits direct invalid construction and public terminal append, while the named
observed/non-worker test is not a complete all-door missing/fabricated identity
matrix. This is a rework evidence defect under RW5-02, not a fourth issue and
not evidence of a production acceptance bypass.

### RW5-03 confirmation evidence equality

`independent-probes.stdout` records wrong second evidence rejection, omitted
helper evidence rejection, omitted ledger digest rejection, matching consume,
replay rejection, durable replacement, expiry, expiry-after-consume rejection,
and reopen-preserved expiry. Corrected locked race transcript:
`race-fixed.stdout`, SHA-256
`fad16a65026eeaef38976f07279d9b6c4a781e0a16d16136fa933f39c327a9a4`, empty
stderr SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
It yielded exactly one consumed result, one `ValueError`, and one committed
consume event. The first combined probe attempt used intentionally wrong
hard-coded race identities and failed; it is not acceptance evidence.

## Broad-suite blocker

The broad command ran exactly once and exited 2 during collection. Complete
stdout is `broad.stdout` with SHA-256
`d7a182fedf68bad45198222f2141b63a0d957b31dac30479c089a08db81f2cb6`; stderr is
empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The only collection failures are absent `arnold.agent.costing.model_resource_capabilities`
and absent `tools.environments.singularity`. Candidate filesystem checks found
both absent; `git ls-tree -r origin/main` found neither at source. Classification:
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`. No repair or rerun was performed.

## Final evidence classification

- C01 and C40: `UNEVIDENCED`, as required by the packet exclusions.
- C02 and C13: `NOT_MET` because the named RW5-02 matrix does not exercise all
  required doors with correctly shaped payloads and typed identities, despite
  the independent production-behavior probe rejecting them.
- C19–C21: `MET`; coherent recomputation no longer produces persisted or
  reservation-authorizing authority.
- C39: `MET`; wrong and omitted second evidence now reject and prior lifecycle
  behavior remains intact.
- CP02 and CP11: `NOT_MET` through the unresolved C02/C13 named-proof gap.
- All other C03–C12, C14–C18, C22–C38, C41 and CP01, CP03–CP10: `MET` on the
  cited source, focused/legacy/packet transcripts, and probes.
- RW5-01: `MET`; RW5-02: `NOT_MET`; RW5-03: `MET`.
- Historical RW4-01: now closed by RW5-01; RW4-02 remains not met; RW4-03,
  RW4-04, RW4-06 remain met; RW4-05 is closed by RW5-03.
- A3-01, A3-03 through A3-09: `MET`; A3-02 remains `NOT_MET` with RW5-02.
- RW-CUSTODY: `MET`; custody SHA is unchanged.

The full criterion tables and North Star/KISS analysis are in
`.oracle/checkins/batch-1-rework5-luna.md`.

## Recommendation

`RECOMMEND_ACCEPTED_ISSUES`
