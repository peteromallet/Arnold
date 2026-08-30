# Batch-2 Sol accepted-issues rework — executor finding

This bounded rework is based on checkpoint `5da26ec5be4d13559948fe4256a114ad7626482b5`
in a fresh worktree (`rework/batch2-sol-accepted`). The live
`Arnold-oracle-nbf` worktree was not modified and no Batch-3 work was started.

## Implemented closures

1. `dispatch_with_admission` retains its historical keyword only for source
   compatibility; it always invokes the canonical admission authority and
   cannot accept a caller-supplied receipt-minting gate. Production doors no
   longer pass `gate=`.
2. `ControlledFinalLaunch` exports the exact immutable execution context to
   the inherited `ARNOLD_WORKER_EXECUTION_CONTEXT` boundary for the entire
   closure, restores the parent environment, and keeps persisted entered /
   accepted state authoritative.
3. Outcome normalization now strictly reconstructs typed outcomes after
   transport normalization, preserves native compatibility worker payloads,
   and rejects scheduling outcomes returned after launch entry instead of
   serializing accepted plus no-launch state.
4. No-launch reconciliation checks the complete reservation history for
   entered/accepted/ambiguous/closed evidence, requires unique bound
   `not_started` evidence, and rejects hidden contradictory launch history.
   Linked-child construction rejects unsupported parent kinds.
5. The legacy cooldown sleep branch was removed from `auto.py`. A structured
   pre-typed refusal is projected to `PhaseResult.scheduling_condition`; the
   one canonical scheduler owns sleeping/retry and breaker bypass.
6. The authority checker rejects `gate=` overrides and multiple admission
   calls in a physical door, in addition to its existing raw-preflight and
   direct-launch checks.

## Validation

- Compatibility auto-driver suite: **29 passed**.
- Rework focused tests: **13 passed**.
- NBF-02 owned frozen surface (all paths except the environment-only
  `tests/workers/test_omp_adapter.py` collection path): **194 passed**.
- Authority checker: **exit 0**.
- Context process-boundary probe: **PASS**; context was visible during the
  closure and absent after restoration.
- Changed-file py_compile and `git diff --check`: **PASS**.
- The literal NBF-02 command cannot collect `tests/workers/test_omp_adapter.py`
  in this checkout because `omp_rpc` is unavailable (`ModuleNotFoundError`);
  this is an environment blocker, not a source failure.
- Literal NBF-03 focused command: 37 passed and 8 failures. The four
  babysitter contract failures are the unchanged source-baseline failures
  already recorded by the authoritative Batch-2 evidence; six additional
  renderer subprocess cases fail in an uninstalled fresh worktree because
  the script cannot import `arnold_pipelines` without `PYTHONPATH`.

No frozen plan/tasklist/North Star/custody/status artifact was changed.
