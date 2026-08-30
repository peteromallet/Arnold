# Batch-2 rework iteration 7 evidence

schema: `arnold.batch2.rework.execution_receipt.v7`

- worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- branch: `rework/batch2-iteration5`
- prior candidate: `ce541b8866345e201db842242d0a03c5806f4c59` / `d162aa12be05e4bd51075d987f8f2b7ae2d556a9`
- candidate source/tests commit: `882857c2935c02e19fc22ad422e69ea751f019fb`
- candidate tree: `566f01b96cfce4446f2b38148fcec419817cc227`
- source file-list SHA-256 (sorted `git diff-tree --name-only` stream): `e48bdd6e61776f3fe7c24798a96a00b0c647b12758d491b270bd4b97417b3aeb`
- interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`
- Python: `3.11.11`
- no merge, push, or Batch 3 action was performed.

## Exact frozen gates

```text
NBF-02: python -m pytest -q tests/cloud/test_runtime_attestation.py tests/cloud/test_worker_dispatch_admission.py tests/cloud/test_dispatch_with_admission.py tests/cloud/test_chain_admission.py tests/cloud/test_worker_dispatch_context.py tests/cloud/test_dispatch_reconciliation.py tests/cloud/test_controlled_final_launch.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_memory_headroom.py tests/arnold_pipelines/megaplan/test_worker_memory_gate.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py tests/arnold_pipelines/megaplan/test_plan_circuit.py tests/workers/test_omp_adapter.py
255 passed in 111.85s (0:01:51)

NBF-03: python -m pytest -q tests/cloud/test_worker_dispatch_spy.py tests/cloud/test_worker_admission_authority.py tests/cloud/test_chain_admission.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
59 passed in 83.14s (0:01:23)

auto: python -m pytest -q tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py
29 passed in 6.55s

authority: python scripts/check_worker_admission_authority.py --check
{"diagnostics": [], "doors": ["arnold_pipelines/megaplan/workers/_impl.py", "arnold_pipelines/megaplan/workers/omp.py", "arnold_pipelines/megaplan/cloud/babysitter/launch.py"], "ok": true}

compile: python -m py_compile <all changed source and test files>; exit 0
diff: git diff --check HEAD^ HEAD; exit 0
```

| gate | raw stdout | SHA-256 | raw stderr | SHA-256 |
|---|---|---|---|---|
| NBF-02 | `.oracle/evidence/iteration7-nbf02.stdout` | `93d8151e998c4865cf15d9c3b5ff3ae3c86f4d7e1ac69fc7ccab4443ce2e6781` | `.oracle/evidence/iteration7-nbf02.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| NBF-03 | `.oracle/evidence/iteration7-nbf03.stdout` | `b2d45ad57fda9464bf97f0d15f192ac7c5004a82ecfabc464f35b828ecc2017d` | `.oracle/evidence/iteration7-nbf03.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| auto | `.oracle/evidence/iteration7-auto.stdout` | `d6d96675d9521e95d9484c991df6c1a8ab378a8bca4a805a6a84eeb27ea982e4` | `.oracle/evidence/iteration7-auto.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| authority | `.oracle/evidence/iteration7-authority.stdout` | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | `.oracle/evidence/iteration7-authority.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Runtime binding

The raw runtime probe is `.oracle/evidence/iteration7-runtime-binding.stdout`
(SHA-256 `504f0818a0951680c94936f47f0f15bfd4867d76bc13bb5d2ae4e875792ea73a`).
It records candidate SHA `882857c2935c02e19fc22ad422e69ea751f019fb`, the pinned
interpreter, one machine-owned OMP executable and its digest, the `omp_rpc`
import and digest, and the same PATH SHA (`d73e27b26c01420092714e5ea5dbbe2b5e1ff90e40f4f7a4b4f5f231e8b7490f`) in both probe and nested binding.

Iteration 7 now derives process executable/argv/command digest from OS
observation rather than caller argv, carries an opaque in-process observation
attestation through terminal normalization, rejects copied/edited/dead/other
PID snapshots, propagates identity on native free-text WorkerResult returns,
and roots OMP trust in the real uid-owned home rather than `HOME`.
