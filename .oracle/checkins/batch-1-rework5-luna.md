# Independent Luna review — NBF-01 / Batch 1 rework 5

- Model: GPT-5.6 Luna (`openai-codex/gpt-5.6-luna`)
- Reasoning: high
- Review date: 2026-08-30 UTC
- Review completed: 2026-08-30T04:52:17Z
- Role: exactly one independent Batch-1 rework-5 reviewer; not executor or Oracle
- Launcher: current review session; no separate launcher command
- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source and merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Isolated transcript/probe root: `/tmp/oracle-nbf01-rework5-luna-review/`
- Attempt-5 packet: `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7`
- Attempt-5 triage receipt: `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a`
- Attempt-5 executor finding: `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197`
- Attempt-5 executor receipt: `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Agent goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Model-policy receipt SHA-256: `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064`
- Tasklist-freeze receipt SHA-256: `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24`

## Independence and candidate identity

All supplied frozen identities were independently rehashed and matched. The
owned-file hashes and blobs also match the Oracle-bound inventory. The exact
six-path production diff and the historical five-tracked-file production diff
both produce:

`7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`

The candidate is not clean. `git status --porcelain=v1` contains the expected
owned source/test changes plus unrelated dirty/untracked `.oracle` planning,
brief, finding, receipt, and historical artifacts. This review does not claim
cleanliness and does not treat that noise as Batch-1 acceptance evidence.
`git diff --name-status origin/main -- arnold_pipelines tests` contains exactly
these five tracked production paths; the untracked owned set contains exactly
`incident/disposition.py` and the eight named new test modules. No later-batch
production/test path entered the candidate scope.

Independent identity/scope transcript files and stream digests:

- `head.stdout` — `2f648953acab8d1a26001287c1f16a56fb991dc24ff9acc696f41064b3e1b76c`
- `status.stdout` — `44e9f2f663afa55a2775be9d477b16da639638f544c363a1cabc0117742388b8`
- `scope.stdout` — `6e1a3176e4aa7dc863b1fb079d7cac5981a4d38e1623ede05ad9dc5bbc515988`
- `untracked-owned.stdout` — `5608b8cca87a5da5f8ce72a330b4822853bf18d5eac740c83002d899eb5f85d0`

## Owned-file SHA-256 and git-blob inventory

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

The last file remains unchanged versus `origin/main`.

## Independent command transcripts

Every command below ran with cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. Complete stdout/stderr are
in the named files under the isolated root. The manifest
`command-manifest.json` contains exact argv, UTC start/end timestamps, exit
status, byte lengths, and separate stdout/stderr SHA-256 values.

| Label | Exit | Complete stdout path / SHA-256 | Complete stderr path / SHA-256 |
|---|---:|---|---|
| focused frozen nine-module pytest | 0; `123 passed in 52.35s` | `focused.stdout` / `e47d84bb8367f5a4c5b1c2abc109385c159c72563398ce3c661ef4ebdb08dba7` | `focused.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| legacy four-module pytest | 0; `78 passed in 4.67s` | `legacy.stdout` / `2ec1056eb93e9ec3ef87de80f5228ddbdaad56d5c652c84f93c05025fbf6b94b` | `legacy.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-01 producer module | 0; `8 passed` | `rw5-01-module.stdout` / `faad2a048f066402d263a731e67182173f50486382c58da46a5fbfff30212c04` | `rw5-01-module.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-01 producer filter | 0; `8 passed` | `rw5-01-filter.stdout` / `b55ef8f059b7c060044332115813ffd363da13410f7511facf5ca7897edd0618` | `rw5-01-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-02 three modules | 0; `27 passed` | `rw5-02-modules.stdout` / `b0efa8060be35c1197d478c38c498252a6e9b89253d83895692e082010a1347d` | `rw5-02-modules.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-02 required filter | 0; `5 passed, 18 deselected` | `rw5-02-filter.stdout` / `6ff623fe9a7b793fe215f8763c6fd2c012bfd8df3a83f6e8c46929bd8af198b0` | `rw5-02-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-03 confirmation module | 0; `7 passed` | `rw5-03-module.stdout` / `40b951cae52565860314b0637b01b87ec8f152cb33777b78996e501a0f6a1bcc` | `rw5-03-module.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-03 named confirmation | 0; `1 passed` | `rw5-03-node.stdout` / `0c33791aa03cbc8826ba04efd1b062adb3baa875c47625e4de7090bd753d7635` | `rw5-03-node.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW5-03 CLI/confirmation filter | 0; `14 passed, 16 deselected` | `rw5-03-filter.stdout` / `7797c2071bb4aa8f1e4609a4db27814c1d79abdb20febe487fcf714972919f58` | `rw5-03-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| transaction crash/contention filter | 0; `7 passed` | `crash-filter.stdout` / `5eff248970364c749b4415909c96e713367bcb59407d2f8096afc9411a559650` | `crash-filter.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| provider route projection | 0; `18 passed` | `provider-module.stdout` / `9a94cd775b4eaa3c9e9f779baee5725e48a64315187f192ce45350a08c700cc7` | `provider-module.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| compile required modules | 0 | `compile.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `compile.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git diff --check` | 0 | `diff-check.stdout` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `diff-check.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| required broad sweep | 2; collection interrupted | `broad.stdout` / `d7a182fedf68bad45198222f2141b63a0d957b31dac30479c089a08db81f2cb6` | `broad.stderr` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The focused and legacy full streams are retained verbatim, not represented by
counts alone. The manifest has the exact argv and UTC timestamps for every row.
The packet-required commands were run as literal argv; `compile` includes the
package export, ledger, schema, disposition, phase-result, and classifier
files. The two exact production-diff commands were separately captured and
both returned the expected digest above.

## Independent CLI matrix

The independent subprocess transcript is
`cli-final-cases.json` (SHA-256
`521ba29ae46202155100515dfc86bdd7d11bba1fc78b841ae2aa6f62ac9bfad3`), with
runner stdout `cli-final.stdout` SHA-256
`b77d116724244a81e26fa926495f719959f332e09fcc9d08bdc257d797704cbb` and empty
runner stderr SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Each
case records exact stdin bytes, ledger root, argv, cwd, UTC start/end, complete
stdout/stderr, exit status, and both stream digests.

| Case | Ledger root | Exact stdin | Exit | stdout SHA-256 | stderr SHA-256 |
|---|---|---|---:|---|---|
| status 0 valid | `cli-final-ledgers/valid` | canonical `WorkerDisposition` JSON, confirmation id consumed for `cli-disp` | 0 | `409aac1d8187829a23849c4a8d1c9b665ea319601d2859e4e10e452d152c46ea` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| status 2 malformed | `cli-final-ledgers/malformed` | `{` | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` |
| status 2 schema | `cli-final-ledgers/schema` | `{"event_type":"worker_disposition"}` | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` |
| status 3 append failure | `cli-final-ledgers/append-failure` | canonical non-worker lifecycle JSON; `events.jsonl` is a directory | 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `238845a1f500ba8d33392dff92166e0bf9b86050a9b76873adc00a168508a5e2` |
| status 4 invalid location | `cli-final-ledgers/not-dir` | canonical worker JSON; ledger root is a file | 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` |
| status 5 missing confirmation | `cli-final-ledgers/missing` | canonical worker JSON with no confirmation id | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` |
| status 5 expired confirmation | `cli-final-ledgers/expired` | canonical worker JSON referencing expired confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` |
| status 5 consumed replay | `cli-final-ledgers/valid` | canonical worker JSON with `other` disposition id, same consumed confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655` |

The exact invocation for every row is:
`python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <root> --json-stdin`.
Status 0 emitted one JSON acknowledgement on stdout, no signal, and no stderr.

## Independent probe results

### RW5-01 / C19–C21 / authority closure

`independent-probes.stdout` SHA-256 is
`38128031bd5e100c5422074752d0533d8f3a49f2a7f6101c85f5db962e7aa908`; stderr
is empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The
complete JSON output records a valid reader append, projection, fresh replay,
all forged-door results, and valid one-use consumption.

- Valid reason-specific reader event appended, projected, replayed, and then
  consumed exactly once; the second consume rejected.
- A coherent forged event mutated before/after content, both provider keys,
  evidence, and recomputed content IDs, evidence digest, and event ID.
- `ChangedPrecondition.from_dict`, `validate_nbf_event`, `_append_nbf`,
  `_append_nbf_locked`, public append, forged-object consume, and reservation
  authorization all rejected it.
- The forged event never appeared in projection; no reservation was authorized.
- The source reader remains the only valid minting path in this probe.

### RW5-02 / C02/C13 / payload and identity matrix

`public-matrix.stdout` SHA-256 is
`2931e69c8a4a672e3fa7c1d3d6225e3526e766405e05320f27a40c7499c76692`; stderr is
empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. This
probe uses correctly shaped `DispatchOutcome.to_dict()` payloads, mutates one
incompatible field per kind, and records results at `from_dict`,
`validate_nbf_event`, public `append_terminal_outcome`, and public
`append_disposition`. All six cases reject at all four doors:

- `no_launch + success_payload`
- `unresolved_launch + provider_evidence`
- `success + terminal_failure`
- `ordinary_terminal_failure + success_payload`
- `provider_exhausted + disposition_id`
- `worker_disposition + success_payload`

The probe also rejects missing, bare-string, and incomplete worker identities at
decode, validation, and public append. Legal positive OOM, unknown-death, and
non-worker records construct, decode, validate, and append. The source behavior
is correct, but the frozen *named-test proof* is not complete: the current
`test_dispatch_outcome_incompatible_payload_matrix` sends only the
worker-disposition/success pairing through `from_dict`/validation, and its
separate public-terminal loop passes terminal-event-shaped dictionaries with
`kind` rather than `outcome_kind`. Those calls reject on unknown fields before
exercising each intended `DispatchOutcome` public terminal door. The identity
matrix likewise has no direct invalid construction and no public terminal
append, and the observed/non-worker named test remains selected rather than a
complete all-door matrix. This is RW5-02's unresolved evidence defect, not a
new implementation issue.

### RW5-03 / C39 confirmation equality

`independent-probes.stdout` also records wrong second evidence and omitted
helper/ledger evidence. Wrong evidence rejected with `confirmation evidence
identity mismatch`; omitted helper evidence raised `TypeError`; omitted ledger
digest rejected; matching evidence consumed once; replay rejected. Durable
replacement, expiry, expiry-after-consume rejection, reopen-preserved expiry,
and a corrected two-process race are recorded. The corrected race transcript is
`race-fixed.stdout` SHA-256
`fad16a65026eeaef38976f07279d9b6c4a781e0a16d16136fa933f39c327a9a4`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; its
result is exactly one consumed and one `ValueError`, with one committed consume
event. RW5-03 behavior and evidence are MET.

The first combined probe attempt used a wrong hard-coded race identity and
failed; it is preserved as a temporary probe diagnostic and is not acceptance
evidence. The corrected isolated race is the evidence cited above.

## C01–C41 criterion classification

| Criterion | Status | Source and behavioral evidence |
|---|---|---|
| C01 | UNEVIDENCED | `PhaseResult.from_dict` and `DispatchOutcome` exist; packet explicitly forbids overweight C01 expansion and no complete six-kind PhaseResult proof was run. |
| C02 | NOT_MET | Source rejects all six incompatible families, and `public-matrix.stdout` proves behavior, but the required named matrix does not actually exercise every intended `from_dict`/`validate_nbf_event`/public terminal door with correctly shaped records. |
| C03 | MET | `DispatchOutcome.__post_init__`; no-launch requires `not_started`; focused suite. |
| C04 | MET | Accepted outcomes require receipt, fingerprint, phase/spec, logical/worker identity, and timing; focused suite. |
| C05 | MET | Worker disposition rejects provider/no-launch/ordinary-failure payloads; focused suite and probe. |
| C06 | MET | `terminal_outcome_kind` and ledger mapping preserve `worker_disposition`; no coercion. |
| C07 | MET | `append_terminal_outcome` requires one pre-existing matching disposition and idempotently returns matching linkage. |
| C08 | MET | Classifier and constructor reject disposition-to-ordinary-failure coercion. |
| C09 | MET | Distinct terminal IDs race under the ledger lock; transaction filter and focused suite pass. |
| C10 | MET | Terminal writer requires exactly one persisted accepted adapter marker matching context. |
| C11 | MET | Keyed reducer tests preserve disposition break without provider degradation. |
| C12 | MET | No-launch/unresolved are rejected by terminal writer and have no terminal projection branch. |
| C13 | NOT_MET | Source rejects typed identity defects, and independent probe confirms it, but named identity evidence lacks direct invalid construction/public terminal coverage and is not complete for observed/non-worker records. |
| C14 | MET | Positive cgroup OOM and legal unknown-death paths construct/append; focused suite and probe. |
| C15 | MET | Deterministic IDs differ for SIGTERM and SIGKILL. |
| C16 | MET | Fingerprint derivation excludes logical/family IDs and volatile liveness. |
| C17 | MET | Route-liveness digest is excluded from semantic/provider keys. |
| C18 | MET | Same projection/fingerprint key is independent of logical ID; contention test. |
| C19 | MET | Forged coherent wire event rejected at decode, validation, both private append doors, public append, projection, and reservation authorization. |
| C20 | MET | Fixed producer identity, evidence, source handles, snapshots, provider keys, and source binding validated before append/consume. |
| C21 | MET | Recomputed all-identity forgery rejected and cannot persist or authorize. |
| C22 | MET | Valid change consumes once; replayed consume rejects. |
| C23 | MET | Passed probe requires persisted lease; provider tests. |
| C24 | MET | Key-changing canonical producer rekeys; key-preserving change does not. |
| C25 | MET | Two OS processes contend under `fcntl.flock`; one reservation winner. |
| C26 | MET | Composite route-child event has one record and no child receipt input. |
| C27 | MET | Fresh replay derives byte-identical composite receipt. |
| C28 | MET | Torn and pre/post-append crash boundaries leave neither or replay one complete composite. |
| C29 | MET | Terminal reducer applies provider/fingerprint state before closure. |
| C30 | MET | Matching accepted exhaustion increments keyed stream. |
| C31 | MET | Different key rekeys/starts at one. |
| C32 | MET | Non-latest success resets only its applicable stream. |
| C33 | MET | Non-latest ordinary failure/disposition breaks only applicable stream. |
| C34 | MET | Lease-bound probe/recovery and single-use authorization preserve keyed streak. |
| C35 | MET | Scheduling/no-launch/unresolved/time/liveness paths do not mutate provider streak. |
| C36 | MET | Positive no-launch, recovered-terminal, and ambiguous reconciliation behavior retained; packet forbids reopening it. |
| C37 | MET | Existing recovered terminal/disposition linkage and idempotency pass. |
| C38 | MET | Blind, conflicting, and accepted-launch no-launch releases reject. |
| C39 | MET | Named confirmation test now covers wrong/omitted second evidence plus identity, timing, TTL, policy, expiry, restart, replacement, and one-consumer behavior; independent probe confirms equality. |
| C40 | UNEVIDENCED | Packet explicitly excludes broad cache/projection-version expansion; no complete cache-failure matrix. |
| C41 | MET | Independent CLI subprocesses cover 0, 2, 3, 4, 5, expired 5, and consumed replay 5. |

## CP01–CP11 checkpoint classification

| Checkpoint | Status | Evidence |
|---|---|---|
| CP01 | MET | Focused frozen command exits 0 with 123 passed. |
| CP02 | NOT_MET | C02/C13 named four-door and typed-identity proof is incomplete. |
| CP03 | MET | Lossless worker-disposition kind, one-way terminal mapping, and linkage behavior pass. |
| CP04 | MET | One `_IncidentEventJournal`, one sequence-sidecar flock, one NBF lock/append authority. |
| CP05 | MET | Only accepted provider-exhausted terminal outcomes enter the keyed observation reducer. |
| CP06 | MET | Probe lease and recovery authorization are canonical, single-use, and streak-preserving. |
| CP07 | MET | Success, different-key, ordinary-failure, and disposition stream interleavings pass. |
| CP08 | MET | Composite route-child crash/replay and post-commit receipt derivation pass. |
| CP09 | MET | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition remain typedly distinct. |
| CP10 | MET | No second journal/store/prepare-commit/scheduler/rotator/family lease found. |
| CP11 | NOT_MET | C02/C13 evidence gap remains; other crash/race/replay/TTL rows pass. |

## Rework and prior-task classification

| Item | Historical attempt-4 status | Current post-attempt-5 status | Evidence |
|---|---|---|---|
| RW5-01 | — | MET | Coherent forged event rejected at every required wire/private append/projection/reserve door; valid reader path appends and consumes once. |
| RW5-02 | — | NOT_MET | Behavior rejects correctly, but named full matrix and typed-identity all-door proof is incomplete as described above. |
| RW5-03 | — | MET | Wrong/omitted second evidence rejects; matching evidence and lifecycle/race behavior remain correct. |
| RW4-01 (historical) | NOT_MET | MET after RW5-01 | Attempt-4 wire forgery is historical; current coherent forgery is rejected. |
| RW4-02 (historical) | NOT_MET | NOT_MET | Attempt-5 named payload/identity matrix still has public-terminal and identity-door proof gaps. |
| RW4-03 (historical) | MET | MET | Keyed non-latest/recovery/lease behavior preserved. |
| RW4-04 (historical) | MET | MET | Distinct terminal race and composite crash/reopen behavior preserved. |
| RW4-05 (historical) | NOT_MET | MET after RW5-03 | Evidence mismatch/omission now explicitly rejected and lifecycle tests remain green. |
| RW4-06 (historical) | MET | MET | Executor evidence protocol and independent current transcripts are complete. |
| A3-01 | MET | MET | Accepted marker required before terminal closure. |
| A3-02 | NOT_MET | NOT_MET | Same RW5-02 named four-door/typed-identity evidence gap. |
| A3-03 | NOT_MET | MET | Same coherent wire forgery now rejected before persistence/authorization. |
| A3-04 | MET | MET | Keyed stream behavior preserved. |
| A3-05 | MET | MET | Passed canonical probe and lease remain required. |
| A3-06 | MET | MET | Terminal race and composite crash behavior preserved. |
| A3-07 | NOT_MET | MET | Confirmation evidence equality is now named and independently probed. |
| A3-08 | MET | MET | Exact executor evidence and current independent review evidence present. |
| A3-09 | MET | MET | `reserve_provider_route_child_with_receipt` remains absent. |
| RW-CUSTODY | MET | MET | Custody file SHA matches; no custody edit performed. |

## Broad-suite classification

The required `pytest -q tests/arnold_pipelines/megaplan` ran exactly once,
exit 2, with complete stdout in `broad.stdout` and the digest recorded above.
Collection stopped only at these missing modules:

- `arnold.agent.costing.model_resource_capabilities`
- `tools.environments.singularity`

Independent candidate filesystem checks found both absent. `git ls-tree -r
origin/main` also found neither at source. Classification:
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`. No module was repaired and no broad sweep
was rerun. This limits broad coverage but waives no in-scope criterion.

## Preserved prior-MET result

The focused suite, provider route suite, transaction crash/contention tests,
terminal/reconciliation tests, confirmation lifecycle, and CLI matrix preserve:

- one incident journal and sequence-sidecar `fcntl.flock`;
- keyed provider streak/recovery/probe lease and non-latest isolation;
- terminal linkage race, composite pre/post-append crash recovery, torn-record
  rejection, deterministic replay, and post-commit receipt derivation;
- typed no-launch/unresolved/ordinary/provider/worker-disposition distinctions;
- positive OOM, explicit unknown death, non-worker lifecycle, and TERM/KILL IDs;
- canonical changed-precondition producer and one-use consume behavior;
- route-child wrapper deletion;
- durable confirmation restart, replacement, expiry, TTL, identity, and one
  consumer behavior;
- CLI statuses and non-signalling contract;
- unchanged `test_incident_ledger.py` and absence of later-batch production/test
  paths.

No prior-MET item was regressed. Counts remain observations, not acceptance
waivers.

## North Star alignment

- **One door per invariant:** MET for the NBF-01 primitive. One journal,
  sequence-sidecar lock, and NBF append authority remain. RW5-01 closes the
  former self-consistent wire snapshot bypass. Admission and real signal-site
  physical doors remain correctly deferred to later batches.
- **Deaths speak:** MET for this owned foundation. Worker, observed-death, and
  non-worker records are typed; OOM requires positive cgroup evidence; the CLI
  records only and never signals. Repository-wide signal wiring is correctly
  out of scope.
- **Models are admitted, not assumed:** UNEVIDENCED and correctly deferred;
  no admission/catalog/live-membership code is owned here.
- **Fixes ship on main:** UNEVIDENCED for this uncommitted dirty candidate;
  no deployment-only claim was made. Delivery is later scope.

Anti-patterns: durable confirmation and equality checks prevent one-scan
identity drift; anonymous integer exit codes are not used by the owned
primitive; persisted accepted markers avoid judgment-only terminal closure;
and coherent forged retry authorization is now blocked. The remaining concern
is evidence quality, not a detected runtime bypass.

## KISS / YAGNI / scope assessment

KISS is good at the architecture boundary: one journal, one flock, one
projection, one terminal writer, one disposition helper, and no second store,
scheduler, rotator, family lease, signature service, or generic producer
escape hatch. The process-local typed source-handle contract is a small,
appropriate provenance boundary. Its `ChangedPrecondition.from_dict` rejection
is intentionally fail-closed for untrusted wire input, although the missing
private-field error is less clear than the final typed-handle error; this is a
minor maintainability blemish, not an additional issue.

YAGNI and scope are MET: no admission, scheduler, T7/T8 policy, fallback
selection, physical door, launch, signal wiring, custody, environment repair,
second journal, or later-batch behavior entered the candidate. The residual
RW5-02 problem is not overengineering; it is a named behavioral-proof gap
caused by malformed public-terminal test inputs and incomplete identity-door
coverage. Fix only that existing matrix; do not widen the batch.

## Residual issue

**RW5-02 / C02/C13 / RW4-02 / A3-02 — named matrix remains incomplete.**
The production validators and independent correctly shaped probe reject the six
incompatible families. However, the named matrix's `from_dict` and public
terminal calls use terminal-event-shaped records with the wrong discriminator
(`kind` versus `outcome_kind`), so they fail before the intended `DispatchOutcome`
semantic door. The named identity matrix covers decode/validation/disposition
append for worker identities but omits direct invalid construction and public
terminal append, and observed/non-worker cases are not a complete all-door
matrix. This does not establish a fourth issue. Strengthen the existing RW5-02
named tests in place; preserve RW5-01 and RW5-03.

## Recommendation

`RECOMMEND_ACCEPTED_ISSUES`
