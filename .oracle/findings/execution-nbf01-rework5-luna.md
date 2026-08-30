# Executor finding — NBF-01 Batch 1 rework 5

This is executor evidence for the sealed serial packet `RW5-01 → RW5-02 → RW5-03`, not an Oracle review or batch decision.

## Candidate and sealed inputs

- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Branch: `megado-nbf-guard-0826`
- Source/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Worktree was already dirty; existing orchestrator-owned `.oracle` changes and attempt-4 production work were preserved. No commit, stage, reset, rebase, push, merge, or Batch 2 action was performed.
- Attempt-5 packet SHA-256: `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7`
- Attempt-5 triage receipt SHA-256: `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a`
- Attempt-5 execution brief SHA-256: `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 (`.oracle/plan.md`) SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Agent goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Attempt-4 reviewed production-diff baseline: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

## Serial outcomes

### RW5-01 — changed-precondition authority

Closed the remaining wire/private-append authorization hole in `schema.py` and `ledger.py`. Public NBF validation now rejects an unbound changed-precondition wire record; canonical/private append validation accepts only the matching producer-created typed event and rechecks its producer binding. Ledger replay uses the existing persisted-record validation path, while `append_changed_precondition` passes the producer-bound event through the existing `_locked` / `_append_nbf_locked` door. The strengthened coherent-forgery test mutates before/after source content, both provider keys, evidence, and all serializable IDs/digests, then proves rejection at decode, `validate_nbf_event`, `_append_nbf`, `_append_nbf_locked`, public append, projection/authorization, and consume. The legitimate reason-specific reader path still appends and consumes once; replayed consume is rejected.

Targeted result: `8 passed`.

The strengthened coherent-forgery test was run against a temporary
unmodified attempt-4 source state and failed exactly at the open
`validate_nbf_event` authorization assertion (`1 failed, 7 passed`, pytest
exit `1`). After restoring the fix, the final-tree rerun passed `8 passed`.
The pre-fix stdout transcript is `/tmp/oracle-nbf01-rework5-luna/pre-fix.stdout`
(SHA-256 `58bd170a5b0333811b00cf308822b5d28a3ded858756bc1f097b942d13354295`);
the final-tree stdout transcript is
`/tmp/oracle-nbf01-rework5-luna/final-rw5-01.stdout` (SHA-256
`f4cda9e14392d1b54ff71b5db7c69b85265cff308f9065e46be91a6e96c168dc`).

### RW5-02 — payload and typed-identity matrix

Strengthened `test_dispatch_outcome_incompatible_payload_matrix` and added public terminal/disposition append coverage for all six dispatch kinds and incompatible payload families. Added all-door missing/bare/incomplete worker identity cases and retained positive OOM and unknown-death paths. `PhaseResult` lossless scheduling behavior and existing worker disposition semantics remain unchanged; no C01 round-trip expansion was added.

Named result: `27 passed`.

### RW5-03 — confirmation evidence equality

Extended `test_confirmation_compares_pid_start_progress_incarnation_cause` with wrong second evidence, omitted helper evidence, and omitted ledger evidence-digest cases. Matching evidence and existing TTL, expiry, replacement, reopen, replay, and one-consumer behavior remain covered.

Named result: `7 passed`.

## Exact changed paths

Production changes:

- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`

The other owned production files were measured and remained in the candidate scope but were not changed by this rework:

- `arnold_pipelines/megaplan/incident/__init__.py`
- `arnold_pipelines/megaplan/incident/disposition.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`

Test changes:

- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`

The remaining named test modules were preserved and included in focused validation. `test_incident_ledger.py` remains unchanged relative to source: SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`; git blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`.

The final tracked production diff identity over the six owned production paths is SHA-256 `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`. This is measured independently from the attempt-4 baseline.

The recorded tracked diff-name output contains only pre-existing `.oracle` artifacts and the five pre-existing modified production files; no later-batch production/test path entered the diff. Full identity and owned-file inventory are in `artifact://`-style local evidence paths listed in the receipt.

## Preserved prior-MET behavior

The validation retained one `_IncidentEventJournal`, sequence-sidecar `fcntl.flock`, one `_locked` NBF mutation door, typed dispositions, keyed non-latest provider/recovery behavior, canonical probe lease binding, composite replay/crash behavior, terminal race behavior, CLI statuses 0/2/3/4/5, and valid changed-precondition consume-once/replay rejection. Existing focused coverage retained the prior scheduling/no-launch/unresolved distinctions, positive OOM and unknown-death handling, lossless worker disposition, route-child receipt derivation, reconciliation, and legacy ledger behavior.

## Validation evidence

Initial execution command streams and SHA-256s are recorded under `/tmp/oracle-nbf01-rework5-luna/`; `/tmp/oracle-nbf01-rework5-luna/command-manifest.json` is the initial manifest, and `/tmp/oracle-nbf01-rework5-luna/final-command-manifest.json` records the final-tree reruns. The evidence-integrity seal below embeds the complete streams and identities for packet-specific focused commands that were missing from those manifests.

- RW5-01 exact targeted command: exit `0`, `8 passed`; stdout SHA-256 `2892f3c51b7158205f3080cea4d2ff8f225fd63aee99fd3b57f2d764b379e5bd`; stderr empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- RW5-02 exact named command: exit `0`, `27 passed`; stdout SHA-256 `951c4fd49bef94f93b2505bffb3f60bc779e1fbca89f333419ac49f33dd6e1ad`; stderr empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- RW5-03 exact confirmation command: exit `0`, `7 passed`; stdout SHA-256 `c0bb7edc122a2f852497ff28990e7e83659dd02337712c5e74fd90608cb7ad4a`; stderr empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Frozen focused suite: exit `0`, `123 passed`; stdout SHA-256 `d750360f18ed14e2e55fd423583e52d47f72eb8311d6ac45246f678856e0a057`; stderr empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Required legacy suite: exit `0`, `78 passed`; stdout SHA-256 `73e705395e04542e2550e9e1ff5a548e4d80f9a8c60ee1065187d060d7af2fdd`; stderr empty SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Compile command: exit `0`, both streams empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `git diff --check`: exit `0`, both streams empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- CLI subprocess matrix: corrected rerun recorded in `cli-cases.json` with complete payloads, ledger roots, argv, timestamps, statuses, stdout/stderr, and per-stream hashes. It measured status 0 success, status 2 schema, status 3 append failure, status 4 invalid root, status 5 missing confirmation, status 5 expired confirmation, status 0 seed, and status 5 already-consumed replay. The corrected matrix stdout SHA-256 is `e646d70f5f9a21d4c5d69293538a3920cbc9a4dd77c93b589dd1a2b93e5cfd6e`; stderr is empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; structured case transcript SHA-256 is `94930a13670a6390f63a753395bb54f9a4fd48e8f697d4c086e2d570804e09b7`.

The required broad sweep was executed exactly once. It exited `2` during collection with two missing-module errors: `arnold.agent.costing.model_resource_capabilities` and `tools.environments.singularity`. The complete stream is `/tmp/oracle-nbf01-rework5-luna/broad-sweep.stdout`, SHA-256 `5a967bd2465a63ea0e7dcd6498840ae24cbcb8a2e524e64c7d4426111e1f09bc`; stderr was empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Independent source/candidate checks confirmed both module files absent at the candidate and `origin/main`; this is recorded as `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` and was not repaired or rerun.

After that pre-fix proof, the final tree was revalidated with the exact RW5-01 command (`8 passed`, stdout SHA-256 `f4cda9e14392d1b54ff71b5db7c69b85265cff308f9065e46be91a6e96c168dc`) and the exact frozen focused command (`123 passed`, stdout SHA-256 `aa434b7d32d02881839177b184fc404ae9d609000078a8683503e9955b84e21c`); both stderr streams were empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Timestamped exact argv/start/end/stream metadata is `/tmp/oracle-nbf01-rework5-luna/final-command-manifest.json`, SHA-256 `6bd28bb5fc321cb82d706b7c396d5db4aabb7976cddb17b5fce448500de22a14`.

## Evidence-integrity seal

A read-only audit reproduced every displayed sealed-input hash, every existing manifest stream hash, every CLI-case embedded stream hash, the complete owned-file blob/SHA inventory, and the final production diff. The initial command manifest SHA-256 is `d4ade54398606443671a10ed0fe70dd984722fe4d2437c07cce5fb84bd323fda`; the final command manifest, identity manifest, and corrected CLI case transcript retain the hashes shown above and in the receipt. The failed first CLI driver remains preserved at exit `1`; the corrected case matrix remains exit/status complete with `0/2/3/4/5`, expired `5`, seed `0`, and already-consumed `5`.

The packet-specific exact focused invocations missing from the executor manifests were run once during evidence sealing, without rerunning the broad suite:

- RW5-01 producer filter: exit `0`, `8 passed`; stdout SHA-256 `549ca11e4fe3df25ea1c34a3bac944e6e63975250497b6adc3e172fa62165968`.
- RW5-01 producer/transaction filter: exit `0`, `9 passed, 16 deselected`; stdout SHA-256 `077fdcc1f0e1a636fffd4911c7cde39d6bb0838f566fac884a22e51a4a254a0c`.
- Packet-order frozen focused suite: exit `0`, `123 passed`; stdout SHA-256 `94c6773260697bcf7dd9668753cf8b7f22be4cbe51c83e008892d20d2f0ec949`.
- RW5-02 payload/identity filter: exit `0`, `5 passed, 18 deselected`; stdout SHA-256 `a54c4b1cbd3988e11b462a309eb96926b0c3a0cbb26129ecfea0e4f0b947355b`.
- RW5-03 named confirmation node: exit `0`, `1 passed`; stdout SHA-256 `1ab9905d8b0f34f6d791ff7da4efa2de0f7f3e282a078758cc0496cc0230c0f0`.
- RW5-03 CLI/confirmation filter: exit `0`, `14 passed, 16 deselected`; stdout SHA-256 `ff43897fc09696941b9bff4512f813c1f5c75ba6423ebaaf338d4f7e8b5ba524`.
- Packet-order `py_compile`: exit `0`; both streams empty.
- Literal packet RW5-01 module command: exit `0`, `8 passed`; stdout SHA-256 `28dc6d5399d1981687db3d419b9bcba5286cae926208993213af8e03278ceb43`.
- Literal packet RW5-02 three-module command: exit `0`, `27 passed`; stdout SHA-256 `e86ae1ecdfb9dffc77d7391531645e560a463cda596d5f2578808c09582a0acc`.
- Literal packet RW5-03 module command: exit `0`, `7 passed`; stdout SHA-256 `278a41d40d756996f4a45abed8fa499e149c479579ca17bede72ae52a86954f3`.
- Literal packet legacy command: exit `0`, `78 passed`; stdout SHA-256 `9ef283caa33d9a432c1a297931086fa3818d305a60127da675b851150e5d172e`.

All supplemental stderr streams were empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Exact argv, UTC timestamps, complete streams, and hashes are embedded in the receipt. The production diff remained `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`; the frozen tasklist and North Star remained `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` and `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

No Oracle token or acceptance decision is present in this finding.
