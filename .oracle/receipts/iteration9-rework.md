# Batch-2 rework iteration 9 evidence

schema: `arnold.batch2.rework.execution_receipt.v9`

- worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- branch: `rework/batch2-iteration5`
- parent candidate source/evidence: `5c6a770805afd08fad49de042ee8144ab9276663`
- candidate source/tests commit: `dd37c5bf8a9c5c209eacaabcf5b245fa3525e42f`
- source file-list SHA-256 (sorted `git diff-tree --name-only` stream): `820ccd713b4d4bd0474aae17352e25abc70a3eb29a9b8ab3922ceaa5ee5f5251`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python` (Python 3.11.11)
- no merge, push, or original OMP-branch action was performed.

## Gates

```text
NBF-02: python -m pytest -q tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py
257 passed in 139.05s (0:02:19)

NBF-03: python -m pytest -q tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
59 passed in 76.75s (0:01:16)

auto: python -m pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py
29 passed in 5.13s

authority/AST: python scripts/check_worker_admission_authority.py --check
{"diagnostics": [], "doors": ["arnold_pipelines/megaplan/workers/_impl.py", "arnold_pipelines/megaplan/workers/omp.py", "arnold_pipelines/megaplan/cloud/babysitter/launch.py"], "ok": true}

compile: python -m py_compile arnold_pipelines/megaplan/cloud/worker_dispatch.py tests/cloud/test_dispatch_with_admission.py; exit 0
diff: git diff --check HEAD^ HEAD; exit 0
```

Summary stdout evidence hashes:

| gate | evidence | SHA-256 |
|---|---|---|
| NBF-02 | `.oracle/evidence/iteration9-nbf02.stdout` | `fa7eff0471c2ad1c3c6b053211321a6f855c60b527df87d30c76d50a88ad2135` |
| NBF-03 | `.oracle/evidence/iteration9-nbf03.stdout` | `0a8420c9a1f52267a72610f07a951935ce159d02b6b4cbd0bfe0af0f3b1fe302` |
| auto | `.oracle/evidence/iteration9-auto.stdout` | `ac5368fa7c0f654790531dfa5fb27c4be1d6d7a24e45b17a32890d545c1b5a74` |
| authority/AST | `.oracle/evidence/iteration9-authority.stdout` | `181d255a5958ecae2fbb4d3cb1ab2d8828b09945fe5bf25b75386483c9aaf0e8` |
| compile | `.oracle/evidence/iteration9-compile.stdout` | `1ed840ee2e93500e391fe573c5b21d026364ad4b0800f0c18873e3984850451b` |
| diff | `.oracle/evidence/iteration9-diff.stdout` | `c2738328a9f1c88211c2de39572cadaba7a83b8a3adf88345a2f91c2b1b08b70` |

## Correction

`ControlledFinalLaunch.run` remains the sole process-attestation consumer. It
passes its accepted identity into `_normalize_outcome`, which projects that
identity and compares repeated result metadata without consuming the token a
second time. Direct normalization callers retain the original validation path.
The production-intent regression launches a real child, captures the machine
snapshot, completes `dispatch_with_admission`, and then verifies a second
validation rejects the consumed token.
