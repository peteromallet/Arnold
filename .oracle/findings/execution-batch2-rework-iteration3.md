# Batch 2 rework iteration 3 — commit-bound verification

candidate_commit: `5bba3353c4687d32db719dd0c500a1bf21dc0be2`
parent_commit: `74189170daad756a9d4a7c568e3843e135417718`
source_diff_sha256: `f484b3d405c250ae7baea99749c5f4a07375c5468b9da4a45baeb26c2933bf4d`

## Exact post-commit results

- Frozen NBF-02 command (including `tests/workers/test_omp_adapter.py`): `246 passed in 89.03s`.
- Frozen NBF-03 command: `47 passed in 16.50s`.
- Auto owning suite (`tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`): `29 passed in 5.04s`.
- `python scripts/check_worker_admission_authority.py --check`: `ok: true`, empty diagnostics.
- Forbidden raw preflight scan: no matches.
- Changed-file `py_compile`: passed.
- `git diff --check`: passed.
- Negative probes: nonexistent native model rejected; forged production runtime claims rejected; wrapped integer rejected; production linked child without authoritative ledger rejected; synthetic `subprocess.Popen` door rejected.

## Environment binding

- Python: `3.11.11 (main, Jan 28 2025, 20:35:47) [Clang 15.0.0 (clang-1500.1.0.2.5)]`
- Interpreter: `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`
- Arnold import: `/Users/peteromalley/Documents/Arnold-batch2-rework/arnold/__init__.py`
- Arnold pipelines import: `/Users/peteromalley/Documents/Arnold-batch2-rework/arnold_pipelines/__init__.py`
- OMP RPC source binding: `/Users/peteromalley/Documents/oh-my-pi/python/omp-rpc/src`

The test outputs were captured immediately after checking out the candidate commit; no source or history changes occurred during verification.
