# Independent review receipt — NBF-01 / Batch 1 rework 6

## Review identity and authority

- Reviewer/model: GPT-5.6 Luna, `codex:gpt-5.6-luna`, high reasoning.
- Role: exactly one independent Batch-1 rework-6 reviewer; not executor or Oracle.
- Repository/cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
- Review evidence root: `/tmp/oracle-nbf01-rework6-luna-review/`.
- No launcher or nested harness was used; this is the current review session.
- Review UTC window: `2026-08-30T05:59:35.511489+00:00` through
  `2026-08-30T06:12:13.432495+00:00` for recorded repository/probe commands.
- Empty stream SHA-256:
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Recommendation token emitted by this reviewer:
  `RECOMMEND_PASS_BATCH_1`. No Oracle token was issued.

## Candidate and frozen artifact identities

| Artifact | Recomputed SHA-256 | Result |
|---|---|---|
| Candidate HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` | MATCH |
| `origin/main` / merge-base | `798c50619204010ed3f4297fbb57988fe9381924` | MATCH |
| Branch | `megado-nbf-guard-0826` | MATCH |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` | MATCH |
| `.oracle/plan.md` settled v8 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | MATCH |
| `.oracle/tasklist.md` frozen | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` | MATCH |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | MATCH |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | MATCH |
| model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` | MATCH |
| tasklist-freeze receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` | MATCH |
| attempt-6 packet | `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83` | MATCH |
| attempt-6 triage receipt | `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8` | MATCH |
| attempt-6 execution brief | `c193077b92f94b55e3dc8f4bf3353ec5318e7e745d0e6aff950c373472e96fb6` | MATCH |
| attempt-6 executor finding | `a28a0ff726cccbc00806a44c7f8c7d305019491cf37656b6ad91769250806c44` | MATCH |
| attempt-6 executor receipt | `48d3988675ad1002000f193b915470391c83632bfc815fff2c35d8bd50a937e6` | MATCH |
| attempt-6 six-file production diff | `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e` | MATCH |
| attempt-6 completion manifest (historical executor artifact) | `c602969e318ca705f240cd1fcd90c2017f791110d92c7f163378852d0648b2ef` | MATCH |
| attempt-5 production baseline (historical) | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` | MATCH as supplied historical identity |

The worktree was intentionally dirty with pre-existing `.oracle` custody,
planning, history, check-in, finding, receipt, and rework artifacts. It was not
claimed clean.

## Owned-file identity inventory

| Path | SHA-256 | git blob |
|---|---|---|
| `arnold_pipelines/megaplan/incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `arnold_pipelines/megaplan/incident/ledger.py` | `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9` | `192f68694ad7cd29c1d28f74539fc7b9f2a82734` |
| `arnold_pipelines/megaplan/incident/schema.py` | `8acb8563adac794d3dc66e39d8db1d12d499207cb5e1b297a395c0a14f640a9d` | `032162bf0efc7b8e14414cd7d6b0738bdf83a613` |
| `arnold_pipelines/megaplan/incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `arnold_pipelines/megaplan/orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `tests/.../test_changed_precondition_producers.py` | `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215` | `0773a0f629712065d4f410502b316155f4b8cf89` |
| `tests/.../test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `tests/.../test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `tests/.../test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `tests/.../test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `tests/.../test_supervision_confirmation.py` | `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c` | `2a5a3a88cbae92d69260c93525246846adeb3547` |
| `tests/.../test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `tests/.../test_worker_disposition.py` | `20f60bc664bebe59d9c50a19b6a4fb389cfa4ea54c101bfef6d138f05750aa41` | `59d6ae5a39659fd5858ba10991b702f0396a8cb0` |
| `tests/.../test_incident_ledger.py` | `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` | `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |

The `...` prefixes in test rows are display abbreviations only; the exact paths
are the eight named paths in the packet plus the unchanged legacy test listed
in the check-in.

## Scope and production-delta proof

`scope-final-00.stdout` records both required production-diff commands, each
returning:

`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`

The tracked diff names are exactly:

- `incident/__init__.py`
- `incident/ledger.py`
- `incident/schema.py`
- `orchestration/phase_result.py`
- `orchestration/phase_result_classify.py`

The only owned untracked source/test paths are `incident/disposition.py` and the
eight named test modules. No later-batch source/test path entered.

The rework source correction was independently compared against a reconstructed
attempt-5 schema. `schema-correction-00.stdout` (exit 1, expected `diff -u`
difference; stdout SHA-256 `39a5e076c02d2703fcb65ceb03e89c4cc6fd52190ae3a43c6828f20bf63858f0`,
structured transcript SHA-256 `a4eaf97ecdefe82dffec0157723b6c593fda075008aa3668c94be1e17107ee6f`)
shows only:

```diff
+        if not isinstance(self.victim_identity_evidence, dict):
+            raise ValueError("victim identity evidence must be a typed object")
```

The reconstructed old schema hashes exactly to the supplied attempt-5 schema
SHA-256 `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1`.

The supplied attempt-5 test blob `45b23313a67229de5d3bbb1c896ab7729b4d09da`
was not present in this checkout's Git object database or retained temporary
roots, so an exact byte-copy of that historical untracked test file could not
be materialized. This is recorded rather than silently claimed. The packet's
old partial-dictionary matrix was independently reconstructed: all six cases
failed with `missing DispatchOutcome fields` before payload-family checks
(`attempt5-gap-fixed-00.stdout`, SHA-256
`a7a2b2da710d28170bbc7b17d7e5f1f9639ef5d2225b6d36f6f5f072503edf63`,
structured transcript SHA-256
`4cca1ba87f9a567d31ab10a2e884229c798910f4b7aa87922f05aed72bd4b409`). The
same isolated old schema accepted a fabricated non-empty victim string. The
current named tests and current independent matrix pass with the typed guard.

## Exact independent command records

Every row below has a JSON structured transcript in the evidence root. That
JSON records literal argv, cwd, UTC start/end, exit status, byte lengths, stream
paths, and stream SHA-256. The listed transcript SHA-256 is the SHA-256 of that
JSON file. The complete stream files are retained at the stated paths.

| Record | Exact argv / result | UTC start → end | stdout SHA-256 | stderr SHA-256 | transcript SHA-256 |
|---|---|---|---|---|---|
| `candidate-identity-00` | `sh -c 'git rev-parse HEAD && git rev-parse origin/main && git merge-base HEAD origin/main && git rev-parse --abbrev-ref HEAD && git status --short --branch && git ls-files --others --exclude-standard -- arnold_pipelines tests'`; 0 | 05:59:35.511489 → 05:59:35.735988 | `35859ccb3a6da3afce284be72c8e0cb9a8f0e93de51d9b29ccd52923092326f5` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `f5c523448006ecfa38a11594a8d398d38560eb88fa14dd6b7c838c3d53bba233` |
| `identity-hashes-00` | file SHA-256 plus `git hash-object` for all frozen/owned artifacts; 0 | 05:59:48.913935 → 05:59:50.491861 | `4143a502ea3e2aa660bf114103e07360ed533b68984dc6e1efd30044c56d6aab` | empty | `7a8db7c4e3975e8ea720e3cee057aeaf9dfc415f5939431be02c917ce84a28e8` |
| `scope-final-00` | exact six-file and five-file `git diff origin/main -- ... | shasum -a 256`, diff names, untracked list; 0 | 06:12:13.256806 → 06:12:13.432495 | `904fa8e8323dba3e89a009bf47e9af2cc17ac5092c2da55cde3bf153c91b9927` | empty | `0bbb5a0479934ffce8326ccfb8441bfa4c37a3ce9907e597df07c95346bd508a` |
| `named-three-00` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`; 0, 28 passed | 06:01:58.436570 → 06:02:17.445550 | `599aa505b5cc432511de408276d519b39b865b76810a79e6cffaa32747c3bd4b` | empty | `fdd881e01214010584ed145abf4ed881a0cae4e71b83e396f64fc65c4822b7de` |
| `worker-filter-00` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k 'incompatible_matrix or observed_and_non_worker'`; 0, 2 passed / 22 deselected | 06:02:20.739616 → 06:02:24.405481 | `80a4f8ddde5edde2de99f548cf0f9a0b75b3b59c7e57a3f8edc06b62bb24ed8f` | empty | `211ac377373b80026fb11b58633a0edf10ec0198af8af27ebd5db34715a30560` |
| `terminal-filter-00` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k 'append or disposition or worker'`; 0, 1 passed / 1 deselected | 06:02:28.882440 → 06:02:31.570063 | `58b2f1f37ac1beffe8942d51e0b992e877f822f2b8b3e654cf7074e759825579` | empty | `69c5f4d32d55375dd14a04bc66b08e24b465bd09f98c83e16552d5e87a3bbeae` |
| `focused-nine-00` | exact nine-module frozen suite; 0, 124 passed | 06:02:37.402642 → 06:02:55.045726 | `d02f8db1b55d2d556c5266f5a93039079ab7f2a35b8b929f314760b46ee8c2ea` | empty | `dc5f79189925ce8ce9a151529ef63060b29445d250c60cde881d8b4de3906552` |
| `legacy-ledger-00` | `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py`; 0, 42 passed | 06:02:58.612224 → 06:03:02.399109 | `2b1a6623a67040235222dfcd8ee8e12cd344e755861b83efb078963470fcff00` | empty | `5b2854df9091fb1694b52eb36fd9b64c216b4a196dd74e55d391c18cdca77480` |
| `legacy-modules-00` | exact four-module legacy suite; 0, 78 passed | 06:03:06.341206 → 06:03:10.824821 | `dbeeed5fc6eb2b714e0ecbae6f425a7cdf740c3205c49a08775adfdf7bbc3975` | empty | `e0047eff02ffb319bf3ab8b06b1d5db675a1df3616bb0439005afe3e57ac6b24` |
| `py-compile-00` | exact six-file `python -m py_compile`; 0 | 06:03:15.608335 → 06:03:15.736844 | empty | empty | `f2437984848b3cd4b072539188c0f9159937e8b453e67f4666a6665304b789b0` |
| `diff-check-00` | `git diff --check`; 0 | 06:03:20.154010 → 06:03:20.201692 | empty | empty | `07858aa09c2177bf4188e3456ff34d2a4d89b6866e3640462fffa3cb0f8049a4` |
| `payload-matrix-00` | isolated complete payload/identity probe; 0, six payload cases / seven worker-identity cases | 06:06:45.381632 → 06:06:46.638051 | `03eb77863ca365119b2e3cf9cbcfc21ae637de279f5b7c668f74bc7bb8dcf9c6` | empty | `95097d508be10c551faed1e95dbbde7af9e1a7acf00bc34701e61d60554b8f0e` |
| `changed-precondition-00` | isolated coherent-forgery and valid reader/consume probe; 0 | 06:07:57.776061 → 06:07:59.136582 | `8fb4acee6fca22a6419bab2b67df8c70afe4bb008311f297a01bff06bb233ab5` | empty | `02018263a8fe89a77e251d44c0af80b717d23581f2177e1a3feee89c6194f344` |
| `confirmation-00` | isolated wrong/omitted digest, consume-once, reopen probe; 0 | 06:08:22.125179 → 06:08:23.363982 | `90f91376606bfa1be4336f360fc16b768be5c40007a46b2cb1cd411208e7e76a` | empty | `3e1ede8e65afc5f6631bcd8d07a70b927e99aeb226127690417f94ad4019a788` |
| `cli-matrix-corrected-00` | isolated real subprocess CLI matrix; 0, child statuses 0/2/2/3/4/5/5/5 | 06:05:44.905529 → 06:05:56.190786 | `b2d687aa21c9f18f0d9d497cbdcdd6dc93469ad25c11cdf97ecbd03af9b3ac14` | empty | `0511a594bd4aeb3e67779645bb57dc28aa3d78b0c00c83eea0537515194a9bce` |
| `attempt5-gap-fixed-00` | isolated reconstructed old schema/partial matrix; 0 | 06:09:57.045129 → 06:09:58.443100 | `a7a2b2da710d28170bbc7b17d7e5f1f9639ef5d2225b6d36f6f5f072503edf63` | empty | `4cca1ba87f9a567d31ab10a2e884229c798910f4b7aa87922f05aed72bd4b409` |
| `attempt5-current-tests-00` | current repaired test file against old schema copy; 1, expected typed-victim assertion failure | 06:11:18.654049 → 06:11:24.432425 | `9863df768bc40a937f0a37fd54915b2f05a7e23364482376c40ae55b556b4cec` | empty | `f52b5c88af55d69efde31ed404f7c230313d74c3b6e547446980ea1de45113b3` |
| `final-integrity-00` | final HEAD/base/branch/status/scope inventory; 0 | 06:09:10.463128 → 06:09:10.763256 | `6c8402c402adfeecca31acb21bafa0941f7981f558b5dc1d658f1b3077165bf0` | empty | `7c58ea2a634bfaf569a68f33df8172f966f46d79013559f580c9686b27509c9d` |
| `final-owned-hashes-00` | final owned SHA-256/blob inventory; 0 | 06:11:57.724206 → 06:11:58.518891 | `463dea320b1e6bef1afa8a1a3516b2e0b39d0da4d2834d3ec8a80f7010feba39` | empty | `25dbdc76c1ea2599f4f45e4a946ec061a3c2ec9cf87a88ba785b11d9ffc0b69e` |

The `attempt5-gap-00` first import attempt exited 1 with a temporary probe
loader error and is retained as diagnostic only. The first CLI matrix run also
contained intentionally uncreated roots and is diagnostic only; the corrected
matrix above is the acceptance evidence. The schema `diff -u` exit 1 is the
expected difference result, not a test failure.

## Independent probe conclusions

### RW6-01 / C02 / C13

All six incompatible payload combinations rejected at every applicable door.
Direct construction and complete `from_dict` used complete `DispatchOutcome`
records with one mutated incompatible field. Complete terminal records reached
`validate_nbf_event`; public terminal append reached `DispatchOutcome.from_dict`
first; public disposition append reached terminal validation. Errors were the
intended payload-family or scheduling-terminal errors, not missing-field or
unknown-field accidents. Worker identities rejected missing, fabricated,
bare-string, wrong-type, incomplete, non-positive PID, malformed host, and
malformed boot identity at direct/decode/validation/public terminal/public
disposition doors. Observed and non-worker matrices reached all applicable doors
for missing/fabricated/wrong-version/subject/cause/killer/victim/lifecycle
identity cases. Legal OOM, unknown death, non-worker lifecycle, worker
 disposition, no-launch, unresolved, success, ordinary, and provider-positive
records remained legal where applicable.

### RW5-01 / C19–C21

The independent forged event changed before/after snapshots, content IDs,
evidence snapshot/digest, both provider-failure keys, and event ID. Every
required decode, validation, private/canonical append, public append, projection,
reservation-authorization, and consume door rejected. The forged event was not
projected. A legitimate reason-specific reader appended and consumed exactly
once; a second consume rejected.

### RW5-03 / C39

Wrong second evidence returned `confirmation evidence identity mismatch`;
omitted helper evidence raised `TypeError`; omitted ledger evidence digest
rejected; matching evidence consumed once; replay rejected. Reopened projection
retained the original identity/expiry and consumed state.

### C41

Real child subprocesses returned status 0 for a valid acknowledged disposition,
2 for malformed JSON and schema violation, 3 for append failure, 4 for invalid
location, and 5 for missing, expired, and already-consumed confirmation. The
valid case emitted one JSON acknowledgement and no stderr; no CLI case signaled.

## Criterion dispositions

Statuses are exactly `MET`, `NOT_MET`, or `UNEVIDENCED`.

| Criterion | Disposition | Evidence |
|---|---|---|
| C01 | UNEVIDENCED | Explicit packet exclusion of overweight `PhaseResult.from_dict` expansion; not reopened. |
| C02 | MET | Final named and independent complete six-kind/four-door payload matrix. |
| C03 | MET | Strict kind/state construction/decode and focused tests. |
| C04 | MET | Accepted worker-disposition context requirements and focused tests. |
| C05 | MET | Worker-disposition payload-family exclusions. |
| C06 | MET | Lossless terminal-kind mapping. |
| C07 | MET | Existing canonical disposition and matching linkage required. |
| C08 | MET | Ordinary-failure coercion rejected. |
| C09 | MET | Distinct terminal IDs, idempotency, and contention tests. |
| C10 | MET | Persisted accepted launch marker required. |
| C11 | MET | Disposition breaks streak without provider degradation. |
| C12 | MET | No-launch/unresolved terminal exclusion and projection behavior. |
| C13 | MET | Complete typed worker/observed-death/non-worker identity matrix. |
| C14 | MET | Positive OOM and explicit unknown-death legal append probes. |
| C15 | MET | Distinct TERM/KILL deterministic IDs. |
| C16 | MET | Volatile/liveness/logical identity excluded from fingerprint. |
| C17 | MET | Route-liveness digest excluded from fingerprint/provider key. |
| C18 | MET | Same reservation key across logical IDs contends. |
| C19 | MET | Independent coherent forgery rejection at all required doors. |
| C20 | MET | Producer/evidence/subject/version/snapshot binding. |
| C21 | MET | Recomputed forgery cannot persist, project, or authorize. |
| C22 | MET | Valid change consumed at most once. |
| C23 | MET | Lease-bound recovery authorization primitive. |
| C24 | MET | Canonical key-changing versus key-preserving producer behavior. |
| C25 | MET | Two-process reservation race has one winner. |
| C26 | MET | One composite route-child record, no child receipt input. |
| C27 | MET | Replay-stable post-commit receipt derivation. |
| C28 | MET | Torn/pre/post-append crash behavior. |
| C29 | MET | Terminal projection before reservation closure. |
| C30 | MET | Matching provider exhaustion increments keyed streak. |
| C31 | MET | Different provider key rekeys at one. |
| C32 | MET | Applicable success resets its keyed streak. |
| C33 | MET | Ordinary failure/disposition breaks consecutiveness. |
| C34 | MET | Probe/recovery preserves keyed streak and lease isolation. |
| C35 | MET | Scheduling/no-launch/unresolved/time/liveness do not mutate streak. |
| C36 | MET | Three legal reconciliation resolutions retained. |
| C37 | MET | Recovered disposition links existing record exactly once. |
| C38 | MET | Blind/conflicting/accepted-launch no-launch releases reject. |
| C39 | MET | Evidence equality, restart, expiry, replacement, and consume-once. |
| C40 | UNEVIDENCED | Explicit exclusion of broad cache/projection-version expansion; not reopened. |
| C41 | MET | Independent real CLI status 0/2/3/4/5 matrix. |

## Checkpoint dispositions

| Checkpoint | Disposition | Evidence |
|---|---|---|
| CP01 | MET | Frozen nine-module suite exited 0 with 124 passed. |
| CP02 | MET | Complete C02/C13 matrices plus strict owned schemas. |
| CP03 | MET | Explicit `worker_disposition` mapping/linkage and no duplication. |
| CP04 | MET | One `_IncidentEventJournal`, sequence-sidecar flock, and NBF authority. |
| CP05 | MET | Only accepted provider-exhausted worker terminals increment observations. |
| CP06 | MET | Single-use lease/recovery authorization preserves streak. |
| CP07 | MET | Success reset, key rekey, ordinary/disposition break interleavings. |
| CP08 | MET | Composite atomicity and replay-stable receipt. |
| CP09 | MET | No-launch/unresolved/ordinary/provider/worker distinctions. |
| CP10 | MET | No second journal/store/prepare-commit/scheduler/rotator/family lease. |
| CP11 | MET | Crash, race, replay, torn-write, linkage, keyed streak, TTL, incarnation, and one-consumer tests. |

## North Star, KISS/YAGNI, and preservation

- **One door per invariant:** MET for Batch-1 primitive scope. One existing
  journal, one flock, one canonical NBF append authority, one terminal writer,
  one disposition helper, and one reason-specific producer boundary remain.
  Admission, dispatch, physical launch, and real signal-site doors are
  correctly deferred rather than duplicated.
- **Deaths speak:** MET for this foundation. Worker, observed-death, and
  non-worker records are typed; positive cgroup evidence is required for OOM;
  TERM/KILL identities differ; the CLI records and never signals. Repository-wide
  signal wiring remains later scope.
- **Models are admitted, not assumed:** UNEVIDENCED and correctly deferred;
  this batch owns no live admission/catalog/family boundary.
- **Fixes ship on main:** UNEVIDENCED for this uncommitted candidate; delivery is
  a later guarded checkpoint, not a claim here.
- **Anti-patterns:** durable equality/TTL/identity confirmation avoids single-scan
  truth; typed records replace anonymous exits; persisted accepted markers and
  canonical linkage provide positive evidence; identical-fingerprint redispatch
  requires a changed precondition.
- **KISS/YAGNI:** MET. No second authority store, signature framework, generic
  producer escape hatch, scheduler, rotator, family lease, admission machinery,
  later-batch caller, or speculative production surface was added. The sole
  rework production correction is the necessary mapping/type guard.
- Prior-MET C03–C18, C22–C38, C41 and CP04–CP10 behavior remained green; RW5-01
  and RW5-03 were independently rechecked. The legacy incident-ledger test was
  unchanged and passed.

## Explicit non-actions

No production, test, plan, frozen-tasklist, North Star, custody, status, goal,
historical receipt/finding/check-in, or rework-packet edit was performed other
than writing this receipt and the paired check-in. No commit, stage, push, merge,
rebase, reset, clean, Batch-2 start, nested harness, or second review was
performed. Temporary probes, ledgers, and transcripts exist only under
`/tmp/oracle-nbf01-rework6-luna-review/`.

## Literal command appendix

The required validation argv, recorded exactly in the JSON transcripts, were:

```text
python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py
python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
git diff --check
```

The exact independent probe argv were:

```text
env PYTHONPATH=/Users/peteromalley/Documents/Arnold-oracle-nbf python /tmp/oracle-nbf01-rework6-luna-review/payload_identity_probe.py
env PYTHONPATH=/Users/peteromalley/Documents/Arnold-oracle-nbf python /tmp/oracle-nbf01-rework6-luna-review/changed_precondition_probe.py
env PYTHONPATH=/Users/peteromalley/Documents/Arnold-oracle-nbf python /tmp/oracle-nbf01-rework6-luna-review/confirmation_probe.py
env PYTHONPATH=/Users/peteromalley/Documents/Arnold-oracle-nbf python /tmp/oracle-nbf01-rework6-luna-review/cli_matrix_probe.py
env PYTHONPATH=/Users/peteromalley/Documents/Arnold-oracle-nbf python /tmp/oracle-nbf01-rework6-luna-review/attempt5_gap_probe.py
```

The CLI probe's child argv for every status case was:

```text
/Users/peteromalley/.pyenv/versions/3.11.11/bin/python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <isolated-root> --json-stdin
```

The full per-child stdin, stdout, stderr, UTC timestamps, exit status, stream
digests, and child transcript digests are in
`/tmp/oracle-nbf01-rework6-luna-review/cli-matrix/*.json`; the corrected
aggregate manifest is
`/tmp/oracle-nbf01-rework6-luna-review/cli-matrix/manifest.json` with SHA-256
`9804b5a2f9fae2d3b872f6870cc1fda59af551833c1c299420f1776f6cdd50b0`.
