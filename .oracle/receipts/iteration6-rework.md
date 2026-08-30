# Batch-2 rework iteration 6 evidence

schema: `arnold.batch2.rework.execution_receipt.v6`

- worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- branch: `rework/batch2-iteration5`
- parent source/evidence: `a155027450546e9476d6e33cc3a896b71449d261` / `41d8201d45`
- candidate source/tests commit: `ce541b8866`
- source file-list SHA-256 (sorted `git diff-tree --name-only` stream): `de3e2768e73a9da74f18308a0dd3f871c262b2d30483e36cd2f4af6f9fd9e45b`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`
- Python: `3.11.11`
- no merge, push, or Batch 3 action was performed.

## Frozen gates

The exact frozen commands were run against candidate source `ce541b8866`:

```text
python -m pytest -q tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py
254 passed in 105.01s (0:01:45)

python -m pytest -q tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
59 passed in 76.88s (0:01:16)

python -m pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py
29 passed in 5.56s

python scripts/check_worker_admission_authority.py --check
{"diagnostics": [], "doors": ["arnold_pipelines/megaplan/workers/_impl.py", "arnold_pipelines/megaplan/workers/omp.py", "arnold_pipelines/megaplan/cloud/babysitter/launch.py"], "ok": true}

python -m py_compile <all changed source and test files>
exit 0

git diff --check HEAD^ HEAD
exit 0
```

Raw captured streams are committed below. Empty stderr streams have the
standard SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| command | stdout | stdout SHA-256 | stderr | stderr SHA-256 |
|---|---|---|---|---|
| NBF-02 | `.oracle/evidence/iteration6-nbf02.stdout` | `6258638041b336c48ebef5ccf0de7157eeda24bc621849c8411bfaf38cee5aff` | `.oracle/evidence/iteration6-nbf02.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| NBF-03 | `.oracle/evidence/iteration6-nbf03.stdout` | `b093b90d8f874c709fb3c56178880cda68e6efc29dfdcf0484f1bb3d7b9ff4ea` | `.oracle/evidence/iteration6-nbf03.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| auto | `.oracle/evidence/iteration6-auto.stdout` | `9e7f9a2e4293b580f2670e145863d14805bfe110bdc3c4e204fe3f4878d8355c` | `.oracle/evidence/iteration6-auto.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| authority checker | `.oracle/evidence/iteration6-authority.stdout` | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | `.oracle/evidence/iteration6-authority.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Machine-owned OMP binding

The runtime probe resolved `omp` to the machine-owned executable, not a PATH
forgery:

- executable: `/Users/peteromalley/.bun/install/global/node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js`
- executable SHA-256: `1e023799891c51f6efea97b78aaf97dc6623b48b559dfd873caf8364a032f49c`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python3.11`
- `omp_rpc` import: `/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/omp_rpc/__init__.py`
- `omp_rpc` SHA-256: `9a9d69fca3956cbe8004309670f7ff430a677de34999976df7cd242913cf2f69`
- PATH SHA-256: `d73e27b26c01420092714e5ea5dbbe2b5e1ff90e40f4f7a4b4f5f231e8b7490f`
- full probe stream: `.oracle/evidence/iteration6-runtime-binding.stdout`
- full probe stdout SHA-256: `d994db7a3e4e984ce2ab2d9af5571105339c5a197cee0f4d61596e9734d9e759`

The implementation binds completed native/OMP outcomes to a machine-inspected
pre-exit child snapshot, executable digest, host, start identity, and (for OMP)
the complete runtime binding. The authority checker rejects aliased/dynamic
raw launch access and noncanonical `run_managed_command` callers. Linked-child
reservations with unchanged semantic fingerprints are rejected, while the
canonical changed-precondition path remains covered.
