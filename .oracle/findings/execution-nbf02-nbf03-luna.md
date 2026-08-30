# NBF-02/NBF-03 executor findings — Luna

## Scope and identity

Executed directly on the assigned branch/worktree. No Megaplan/Megado/orchestrator, subagent, commit command, stage, push, merge, rebase, reset, clean, protected-box/chain mutation, or Batch 3 action was performed by this leaf. The repository tip advanced externally during execution from the starting observation to the final observed commit; this leaf did not create that commit.

- Frozen starting commit observed: `878a9b2980f0eab6642ed51c30e687903a7213b9`
- Final HEAD observed: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Branch: `megado-nbf-guard-0826`
- Validation evidence root: `/tmp/oracle-nbf02-nbf03-luna-final-0830/`
- Final command-manifest SHA-256: `af8cb511368db862d7c593be923a51baa4e351ca8e596b302d7d3c6fc20f7c05` (the manifest file itself is the complete literal-command record; stream files are complete)
- Reachable validation manifest SHA-256: `0192b03001f81d71bc8107f3b809c9c0605bdf1a8c63d48aa98a474c123af3b8`

## Implementation

### NBF-02

- Added `cloud/worker_dispatch.py` with typed `WorkerAdmissionRequest`, `WorkerAdmissionReceipt`, `AdmissionRefusal`, `WorkerExecutionContextRef`, `SchedulingCondition` handling, route-applicable admission, semantic fingerprinting, ledger reservation, cooldown retry loop, terminal writer integration, truthful reconciliation helper, and authorized linked-child request construction.
- Extended the public `runtime_attestation.require_production_worker_dispatch_runtime` authority with the typed request path while preserving the Batch-1 seed-only compatibility call.
- Added `cloud/controlled_final_launch.py`, persisting `not_started -> entered -> accepted -> closed` through the existing incident ledger and enforcing one closure call.
- OMP admission uses static catalog validation plus exact `omp models --json` membership; native routes use a positive backend executable proof and do not enter the OMP catalog.
- Production native dispatch in `workers/_impl.py` enters the canonical seam; production direct/nested OMP dispatch is owned by `workers/omp.py`; handler-side memory refusal/WBC construction is skipped in production so the canonical gate precedes final launch/WBC construction.
- Scheduling conditions are transported through `PhaseResult`; `phase_result_guard`, `RecoveryPolicy`, handler accounting, and `auto.py` recognize scheduling/no-launch without normal failure/breaker accounting.
- Existing handler-side memory selection remains for non-production development compatibility; production memory/cooldown admission is canonical.
- `worker_disposition` remains lossless and is passed to the existing canonical terminal writer without appending a second disposition.

### NBF-03

- Added OMP physical-door guard with nested delegation suppression so `_impl.py` does not add an outer OMP admission hit.
- Added babysitter managed-launch admission wrapper before `run_managed_command`.
- Added `scripts/check_worker_admission_authority.py --check` using AST inspection, import-alias resolution, forbidden raw preflight detection, door-presence checks, and chain direct-launch checks.
- Removed raw runtime seed/source preflight calls from the three door files. The secondary raw-symbol scan is clean.
- Added support for persisted `closed` controlled-adapter state in the existing NBF event validator.

## Focused validation

All commands ran with cwd `/Users/peteromalley/Documents/Arnold-oracle-nbf`. Every command has complete stdout/stderr files and SHA-256 digests in `/tmp/oracle-nbf02-nbf03-luna-final-0830/command-manifest.json` unless noted.

1. Exact NBF-02 tasklist command: exit `4` at collection because `tests/cloud/test_worker_dispatch_admission.py` is absent. Stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/stdout/01.log`, SHA-256 `24f0b6026255df17440df650134db1c767346a9d49b0d687d39847d5911a9e9a`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/stderr/01.log`, SHA-256 `ccc4ea0ae198254662a6ec407b4f14822e6be9cb8d99719736ad1850178803640ed`. Started `2026-08-30T06:54:27.956580+00:00`; ended `2026-08-30T06:54:30.509184+00:00`.
2. Exact NBF-03 tasklist pytest command: exit `4` at collection because `tests/cloud/test_worker_dispatch_spy.py` is absent. Stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/stdout/02.log`, SHA-256 `24f0b6026255df17440df650134db1c767346a9d49b0d687d39847d5911a9e9a`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/stderr/02.log`, SHA-256 `ede0e101777197711d5148a37a4caee53d5b78c91e98b1b5082cf26996c5276b`. Started `2026-08-30T06:54:30.511558+00:00`; ended `2026-08-30T06:54:32.771304+00:00`.
3. `python scripts/check_worker_admission_authority.py --check`: exit `0`; stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/stdout/03.log`, SHA-256 `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/stderr/03.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:54:32.772168+00:00`; ended `2026-08-30T06:54:34.326574+00:00`.
4. Canonical admission/controlled-terminal smoke: exit `0`; stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/stdout/04.log`, SHA-256 `9bab2afe8aa00a9a43be7f5c2b1a56b1771794964a06052ab27c4e89840791be`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/stderr/04.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:54:34.327317+00:00`; ended `2026-08-30T06:54:35.774274+00:00`. Proved one admitted success, `not_started/entered/accepted/closed` sequencing, and one terminal projection.
5. Full focused source compile command: exit `0`; stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/stdout/05.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; stderr same path family `/tmp/oracle-nbf02-nbf03-luna-final-0830/stderr/05.log`, same empty-stream SHA-256. Started `2026-08-30T06:54:35.775090+00:00`; ended `2026-08-30T06:54:36.032111+00:00`.
6. Exact secondary raw-symbol scan: exit `0`; stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/stdout/06.log`, SHA-256 `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/stderr/06.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:54:36.032752+00:00`; ended `2026-08-30T06:54:36.100202+00:00`.
7. Reachable regression suite (`test_runtime_attestation.py`, phase-result/scheduling, memory, plan circuit, OMP adapter): exit `0`, **all tests passed**. Stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stdout/01.log`, SHA-256 `09033a14e7f25d3e1997ae90583f8da00e893391ea71dad5675720a7c4ca2b2e`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stderr/01.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:55:05.865144+00:00`; ended `2026-08-30T06:56:16.689892+00:00`.
8. `pytest -q tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py`: exit `0`, **34 passed**. Stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stdout/02.log`, SHA-256 `c5ef3d8f324a8c439b2fb24f486ff0a4fb85a437ba78f643d446bfc77a899501`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stderr/02.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:56:16.692614+00:00`; ended `2026-08-30T06:56:23.685553+00:00`.
9. Existing babysitter routing/goal tests: exit `1`, **35 passed, 4 pre-existing contract failures** unrelated to this change (expected legacy DeepSeek/Hermes renderer assertions conflict with current single-Codex/OMP implementation). Stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stdout/03.log`, SHA-256 `552afd1fbff6ded7b73fb00d73dc94123deae93a90e5e0f4c519d94a67dccc99`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stderr/03.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:56:23.686604+00:00`; ended `2026-08-30T06:56:45.949776+00:00`.
10. Final `git diff --check && python scripts/check_worker_admission_authority.py --check`: exit `0`; stdout `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stdout/04.log`, SHA-256 `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2`; stderr `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/stderr/04.log`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Started `2026-08-30T06:57:08.406656+00:00`; ended `2026-08-30T06:57:09.843972+00:00`.

## Owned-path inventory

Tracked modified paths:

- `arnold_pipelines/megaplan/auto.py`
- `arnold_pipelines/megaplan/cloud/babysitter/launch.py`
- `arnold_pipelines/megaplan/cloud/runtime_attestation.py`
- `arnold_pipelines/megaplan/cloud/controlled_final_launch.py`
- `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
- `arnold_pipelines/megaplan/handlers/shared.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/recovery_policy.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/omp.py`
- `scripts/check_worker_admission_authority.py`

The pre-existing protected untracked `.oracle/briefs/execution-nbf02-nbf03-luna.md` was not edited. Fresh executor evidence is written only to the requested findings and receipts paths.

## Limits and honest status

The exact frozen NBF-02/NBF-03 new pytest modules are absent in this checkout, so their exact commands stop at collection and no green result is claimed. The implementation is compile-clean, the authority checker/raw scan pass, canonical admission and terminal smoke passes, existing runtime/transport/memory/WBC suites pass, and the existing babysitter suite retains four unrelated baseline contract failures. No T8 provider policy, signal-site wiring, or Batch 3 work was added.
