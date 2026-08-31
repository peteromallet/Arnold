# Batch 2 attempt 14 — OMP coercion regression

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-13 brief and its
reviews (native REWORK, OMP-managed PASS, regression PASS). This pass addresses
only the reported `_impl` OMP typed-result coercion/handler boundary and the
associated flag-off/flag-on regression probes; no additional Sol oracle was
commissioned.

- Preserve the OMP door's typed terminal envelope while projecting accepted
  results to the historical `WorkerResult` carrier where the worker loop needs
  it.
- Keep unresolved launches typed as `scheduling_condition` with the complete
  `dispatch_outcome`, without failure accounting or relaunch.
- Exercise both `MEGAPLAN_USE_AGENT_DISPATCHER=0` and `=1`, plus the three
  physical doors and higher-level handler/phase-result consumers.

No frozen/index/status/execution-log changes, commit, push, merge, deploy, or
scope expansion.
