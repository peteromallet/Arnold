# Batch-2 rework iteration 5 evidence

Candidate source/tests were committed before this evidence artifact.

- worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- branch: `rework/batch2-iteration5`
- source commit: `a155027450546e9476d6e33cc3a896b71449d261`
- source file-list SHA-256 (sorted `git diff-tree --name-only` stream): `741c3c1c5a859768ce961df8b617369c6191f9d0122013917e6279ae01646e0b`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`
- Python: `Python 3.11.11`
- pytest: `/opt/homebrew/bin/pytest`
- PATH: `/Users/peteromalley/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/sbin:/usr/bin:/bin`
- stderr: empty for all commands below

## Frozen NBF-02

Command: `python -m pytest -q tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py`

Raw stdout tail:

```text
........................................................ [ 28%]
........................................................................ [ 85%]
.....                                      [100%]
252 passed in 121.48s (0:02:01)
```

## Frozen NBF-03

Command: `python -m pytest -q tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py`

Raw stdout tail:

```text
........................                   [100%]
54 passed in 62.68s (0:01:02)
```

## Auto/checker/compile gates

Command: `python -m pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`

```text
............                                            [100%]
29 passed in 5.97s
```

Command: `python scripts/check_worker_admission_authority.py --check`

```json
{"diagnostics": [], "doors": ["arnold_pipelines/megaplan/workers/_impl.py", "arnold_pipelines/megaplan/workers/omp.py", "arnold_pipelines/megaplan/cloud/babysitter/launch.py"], "ok": true}
```

The duplicate legacy preflight scan returned no matches; `git diff --check` and `python -m py_compile` over all changed source/tests returned exit status 0.

## Coverage added in this iteration

- receipt-bound managed-child manifest acceptance and forged digest rejection;
- strict nullable `DispatchOutcome` normalization and wrapped primitive rejection;
- canonical controlled-adapter door and legal `not_started -> entered -> accepted` transitions;
- canonical authorization-grant event identity and a production linked-child positive path;
- aliased, dynamic, nested, and canonical-door raw launch checker negatives;
- trusted OMP executable/runtime/PATH binding and machine-owned membership;
- no-launch reconciliation and completed/dead child identity handling.
