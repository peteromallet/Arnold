# Batch-2 rework iteration 10 evidence

schema: `arnold.batch2.rework.execution_receipt.v10`

- worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- branch: `rework/batch2-iteration5`
- parent candidate source/evidence: `4c08d63d83`
- candidate source/tests commit: `dbc7d012963afccb6e74218f1ea43c5a13a9c898`
- source file-list SHA-256 (sorted `git diff-tree --name-only` stream): `820ccd713b4d4bd0474aae17352e25abc70a3eb29a9b8ab3922ceaa5ee5f5251`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python` (Python 3.11.11)
- no merge, push, or original OMP-branch action was performed.

## Correction

`_normalize_outcome` has one local `worker_identity(candidate)` projector. The
generic production-shaped `LaunchResult(value=WorkerResult(...),
worker_identity=...)` branch now invokes that projector with its candidate
identity only; it no longer passes the receipt as a stale second positional
argument. This preserves the sole-consumer attestation design: direct callers
still validate and consume once, while `ControlledFinalLaunch` callers project
the already accepted identity and compare repeated metadata without consuming
the token again. Native and OMP process-bound identities are covered with real
machine-observed child snapshots and OMP runtime binding.

## Gates

```text
focused: python -m pytest -q tests/cloud/test_dispatch_with_admission.py::test_production_shaped_native_worker_result_normalizes tests/cloud/test_dispatch_with_admission.py::test_production_omp_wrapper_worker_result_normalizes tests/cloud/test_dispatch_with_admission.py::test_production_dispatch_projects_consumed_attestation_once_and_rejects_replay tests/cloud/test_dispatch_with_admission.py::test_real_omp_process_identity_uses_bun_launcher_and_trusted_script
4 passed in 2.01s

NBF-02: python -m pytest -q tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py
259 passed in 112.07s (0:01:52)

NBF-03: python -m pytest -q tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
59 passed in 66.17s (0:01:06)

auto: python -m pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py
29 passed in 5.36s

authority/AST: python scripts/check_worker_admission_authority.py --check
{"diagnostics": [], "doors": ["arnold_pipelines/megaplan/workers/_impl.py", "arnold_pipelines/megaplan/workers/omp.py", "arnold_pipelines/megaplan/cloud/babysitter/launch.py"], "ok": true}

compile: python -m py_compile arnold_pipelines/megaplan/cloud/worker_dispatch.py tests/cloud/test_dispatch_with_admission.py; exit 0
diff: git diff --check; exit 0
```

## Evidence hashes

| gate | evidence | SHA-256 |
|---|---|---|
| focused | `.oracle/evidence/iteration10-focused.stdout` | `c8842096747d50c47c261987b0a490fcb1f3005509243fe3c3aac6d16c95bf23` |
| NBF-02 | `.oracle/evidence/iteration10-nbf02.stdout` | `badedfc47b176804bbdefad06411e4c16fadeb7323775d4665f356bf2a2add38` |
| NBF-03 | `.oracle/evidence/iteration10-nbf03.stdout` | `76aafbd0214925470f51840ba9d760ba0a450ed71b29c2aaa67e95f85f6666fc` |
| auto | `.oracle/evidence/iteration10-auto.stdout` | `b5947209654e41ea4bda567bf91e2be1b450fa9de052bb8264d4929f45672847` |
| authority/AST | `.oracle/evidence/iteration10-authority.stdout` | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` |
| compile | `.oracle/evidence/iteration10-compile.stdout` | `1ed840ee2e93500e391fe573c5b21d026364ad4b0800f0c18873e3984850451b` |
| diff | `.oracle/evidence/iteration10-diff.stdout` | `d01365ca96778761ef88ce996c1625320c928aeba2873d2f9f35759bb0532a77` |
