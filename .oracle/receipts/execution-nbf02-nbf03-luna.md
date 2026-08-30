# NBF-02/NBF-03 execution receipt — Luna

## Result

Implementation was applied in dependency order (NBF-02 then NBF-03) without invoking an orchestrator or dispatching another agent. No commit command, stage, push, merge, rebase, reset, clean, protected live-box/chain mutation, or Batch 3 action was performed by this leaf. The repository tip advanced externally during execution; that commit is recorded below.

- Branch: `megado-nbf-guard-0826`
- Final HEAD: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Starting Batch-1 commit observed: `878a9b2980f0eab6642ed51c30e687903a7213b9`
- Evidence root: `/tmp/oracle-nbf02-nbf03-luna-final-0830/`
- Final command manifest: `/tmp/oracle-nbf02-nbf03-luna-final-0830/command-manifest.json`
- Final command manifest SHA-256: `af8cb511368db862d7c593be923a51baa4e351ca8e596b302d7d3c6fc20f7c05`
- Reachable command manifest: `/tmp/oracle-nbf02-nbf03-luna-final-0830/reachable/manifest.json`
- Reachable manifest SHA-256: `0192b03001f81d71bc8107f3b809c9c0605bdf1a8c63d48aa98a474c123af3b8`

## Delivered

- Canonical typed admission request/receipt/refusal and immutable execution context in `cloud/worker_dispatch.py`.
- Exact OMP `omp models --json` membership proof, static catalog validation, native positive backend proof, semantic fingerprint reservation, memory/cooldown admission, and no liveness-only bypass.
- Generic `dispatch_with_admission`, injectable clock/sleeper, controlled `not_started -> entered -> accepted -> closed` final-launch adapter, one terminal projection, truthful reconciliation helper, and authorized linked-child construction.
- Production native `_impl.py`, direct/nested OMP `run_omp_step`, and babysitter managed-launch bindings; raw runtime refresh/configured-runtime preflights removed from the three physical door files.
- Lossless scheduling/no-launch/worker-disposition transport through `PhaseResult`, handler accounting, `RecoveryPolicy`, and `auto.py`; scheduling/no-launch bypass normal failure/breaker accounting.
- AST authority checker at `scripts/check_worker_admission_authority.py`.

## Validation status

- Exact NBF-02 pytest command: exit `4`; missing `tests/cloud/test_worker_dispatch_admission.py` at collection. Full streams and literal command are in manifest record 1.
- Exact NBF-03 pytest command: exit `4`; missing `tests/cloud/test_worker_dispatch_spy.py` at collection. Full streams and literal command are in manifest record 2.
- Authority checker: exit `0` (manifest record 3).
- Canonical admission/terminal smoke: exit `0`; one success terminal and controlled state sequence proven (manifest record 4).
- Full source compile: exit `0` (manifest record 5).
- Secondary raw-symbol scan: exit `0` (manifest record 6).
- Reachable focused suite: exit `0`; runtime attestation, phase result, scheduling, memory, plan circuit, and OMP adapter tests all passed (reachable manifest record 1).
- Existing common WBC suite: exit `0`; 34 passed (reachable manifest record 2).
- Existing babysitter routing/goal suite: exit `1`; 35 passed and four baseline failures assert the old legacy DeepSeek/Hermes renderer contract, conflicting with the current single-Codex/OMP implementation (reachable manifest record 3). This is not reported as a new success or silently suppressed.
- Final `git diff --check && python scripts/check_worker_admission_authority.py --check`: exit `0` (reachable manifest record 4).

Every recorded command includes literal argv, cwd, UTC start/end, exit code, complete stdout/stderr paths, and stream SHA-256 digests. See the companion findings artifact for the complete owned-path inventory and detailed acceptance mapping.
