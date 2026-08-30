# Batch-2 rework iteration 8 evidence

schema: `arnold.batch2.rework.execution_receipt.v8`

- worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- branch: `rework/batch2-iteration5`
- prior candidate: `882857c2935c02e19fc22ad422e69ea751f019fb` / `2020564dd34af3e36b2540799de4ebb876a1db16`
- candidate source/tests commit: `5af7fd74e34e8928b84d51708edcc7abcb8a76ca`
- candidate tree: `83d4e13b8bd5da80dc3a8795433d89575a505967`
- source file-list SHA-256: `820ccd713b4d4bd0474aae17352e25abc70a3eb29a9b8ab3922ceaa5ee5f5251`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`
- Python: `3.11.11`
- no merge, push, or Batch 3 action was performed.

## Exact gates

```text
NBF-02: python -m pytest -q tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py
256 passed in 127.02s (0:02:07)

NBF-03: python -m pytest -q tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
59 passed in 96.31s (0:01:36)

auto: python -m pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py
29 passed in 6.47s

authority: python scripts/check_worker_admission_authority.py --check
{"diagnostics": [], "doors": ["arnold_pipelines/megaplan/workers/_impl.py", "arnold_pipelines/megaplan/workers/omp.py", "arnold_pipelines/megaplan/cloud/babysitter/launch.py"], "ok": true}

compile: python -m py_compile <all changed source and test files>; exit 0
diff: git diff --check HEAD^ HEAD; exit 0
```

| gate | stdout | SHA-256 | stderr | SHA-256 |
|---|---|---|---|---|
| NBF-02 | `.oracle/evidence/iteration8-nbf02.stdout` | `1f035cac6c6d7799a74dcc940b33805010d6062f364f3dd2e87e45c9db0499b6` | `.oracle/evidence/iteration8-nbf02.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| NBF-03 | `.oracle/evidence/iteration8-nbf03.stdout` | `4abaceb29562b46159d9213879a9ce5875cfd46138c30d86e8cc8a8fd319cc9c` | `.oracle/evidence/iteration8-nbf03.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| auto | `.oracle/evidence/iteration8-auto.stdout` | `b15bcb6233d42dba823148454ebe3acae094ccd4effa00a91f96271132ee9fda` | `.oracle/evidence/iteration8-auto.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| authority | `.oracle/evidence/iteration8-authority.stdout` | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | `.oracle/evidence/iteration8-authority.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Trusted OMP process binding

`.oracle/evidence/iteration8-runtime-binding.stdout` is the raw runtime probe
(SHA-256 `24b07a2c102d7067c247d4881d788c2529f79831718fb074a4f3e2d415ceb438`).
It is bound to candidate `5af7fd74e34e8928b84d51708edcc7abcb8a76ca` and records:

- trusted CLI script: `/Users/peteromalley/.bun/install/global/node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js`, SHA-256 `1e023799891c51f6efea97b78aaf97dc6623b48b559dfd873caf8364a032f49c`
- observed Bun launcher: `/Users/peteromalley/.bun/bin/bun`, SHA-256 `e0c90ec15d33363e6b70713d56bc3b2c7585c17f40a0fe0f8fd9305901d4e233`
- `omp_rpc` import SHA-256 `9a9d69fca3956cbe8004309670f7ff430a677de34999976df7cd242913cf2f69`
- identical PATH SHA in probe and nested runtime binding: `d73e27b26c01420092714e5ea5dbbe2b5e1ff90e40f4f7a4b4f5f231e8b7490f`

Iteration 8 binds the observed process to Bun plus the exact trusted script
and observed argv, while process attestations are single-use and scoped to one
receipt/logical dispatch/fingerprint, rejecting cross-receipt replay.
