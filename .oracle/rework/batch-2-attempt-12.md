# Batch 2 attempt 12 — physical-door reconciliation

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-11 brief and the
three independent Luna REWORK verdicts (native/handler, OMP, and managed),
including the parallel writer results; no additional Sol oracle was
commissioned.

- Reconcile the disjoint native/handler, OMP, and managed physical-door
  implementations and tests without discarding valid work or adding a second
  WBC authority.
- Require direct calls to `_production_worker_dispatch`,
  `_run_omp_with_admission`/production `run_omp_step`, and
  `_admit_managed_launch`; only backend/system/final execution seams may be
  faked.
- Preserve typed terminal/unresolved transport, provider/route context,
  exactly-once behavior, legacy return forms, and handler PhaseResult
  scheduling evidence.
- Run collectable focused suites and record the `omp_rpc` environment blocker.

No frozen/status/execution-log/index changes, commit, push, merge, deploy, or
scope expansion.
