# Batch-2 Sol accepted-issues rework — receipt

- Worktree: `/Users/peteromalley/Documents/Arnold-batch2-rework`
- Branch: `rework/batch2-sol-accepted`
- Base checkpoint: `5da26ec5be4d13559948fe4256a114ad7626482b5`
- Scope: six bounded Batch-2 blockers only; no merge, push, or Batch-3 start.
- Live worktree protected: `/Users/peteromalley/Documents/Arnold-oracle-nbf`

The implementation finding is `.oracle/rework/batch-2-sol-accepted-rework.md`.
The source changes are limited to the canonical dispatcher, controlled launch
context boundary, three production door call sites, auto scheduling transport,
and the authority checker.

Validation was run in the fresh worktree on 2026-08-30:

```text
pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py
29 passed

pytest -q tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_worker_dispatch_spy.py
13 passed

python scripts/check_worker_admission_authority.py --check
exit 0

NBF-02 owned frozen paths (without unavailable omp_rpc module)
194 passed

python -m py_compile <all changed Python files>
exit 0

git diff --check
exit 0
```

The exact frozen NBF-02 command collected with one pre-existing environment
error (`tests/workers/test_omp_adapter.py`: `ModuleNotFoundError: omp_rpc`).
The exact NBF-03 command reproduced the known four babysitter baseline
failures plus six fresh-worktree renderer import failures caused by invoking a
script subprocess without an installed package/PYTHONPATH. Neither class was
silently waived or changed.
