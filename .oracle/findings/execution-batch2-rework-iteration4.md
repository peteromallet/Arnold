# Batch 2 rework iteration 4 execution finding

candidate_code_commit: 5c74f0c6155deedf22b911bc588d5c8a79e12390
parent_checkpoint: 5da26ec5be4d13559948fe4256a114ad7626482b
scope: production identity, OMP machine registry admission, runtime binding, canonical linked-child boundary, authority checker, typed no-launch/ambiguous reconciliation

## Exact committed gates

The following were run from `/Users/peteromalley/Documents/Arnold-batch2-rework` with:

```text
PATH=/Users/peteromalley/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/sbin:/usr/local/bin:/usr/bin:/bin
PYTHONPATH=/Users/peteromalley/Documents/oh-my-pi/python/omp-rpc/src:/Users/peteromalley/Documents/Arnold-batch2-rework
PYTHONDONTWRITEBYTECODE=1
TMPDIR=/private/tmp
interpreter=/Users/peteromalley/.pyenv/versions/3.11.11/bin/python
```

NBF-02 exact focused command: `246 passed in 107.29s (0:01:47)`.
Raw streams: `iteration4-nbf02.stdout`, `iteration4-nbf02.stderr`.

NBF-03 exact focused command: `52 passed in 24.18s`.
Raw streams: `iteration4-nbf03.stdout`, `iteration4-nbf03.stderr`.

Automatic owning suite `tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`: `29 passed in 4.62s`.
Raw streams: `iteration4-auto.stdout`, `iteration4-auto.stderr`.

Static checker: `python scripts/check_worker_admission_authority.py --check` returned JSON `{"diagnostics": [], "ok": true}`.
`git diff --check` and changed-file `py_compile` both passed.

## Adversarial machine probes

The kernel-owned boot identity and process-start observation accepted the current process only. Forged process-start, forged boot, and nonexistent PID each rejected with `ValueError` (`production worker process start identity mismatch`, `production worker boot identity cannot be machine-verified`, `production worker PID is not live`).

Checker regressions cover `subprocess as alias`, `from subprocess import Popen`, assignment aliases, dynamic `getattr(..., 'Popen')`, and aliased admission lacking the typed worker return.

## Binding

The OMP route proof uses the machine-owned `omp models --json` catalog in production; caller-positive resolvers are ignored for production doors. Runtime provenance now includes and production compares import root, imports, interpreter, sys.path, source revision, manifest, and launch seed. Production intent is forced by canonical `workers.*` and `cloud.babysitter.*` doors. Post-entry uncertainty is durably reconciled as `permanent_hold_ambiguous`; pre-entry no-launch is a typed `PreLaunchNoLaunch` result.
