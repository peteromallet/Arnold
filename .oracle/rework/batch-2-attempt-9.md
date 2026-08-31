# Batch 2 attempt 9 — converged Luna rework

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-8 brief SHA
`46df4b04ce71fc6ab7cbc23cd6945cd0486d3ab936f98255f7eaa568a06cd585` and the
three Luna REWORK verdicts; no additional Sol oracle was commissioned.

- **A9-CONSTRUCTOR-AUTH** — native construction proof is produced by an
  authenticated backend-owned constructor/capability preparation seam, not a
  caller-supplied WorkerAdmissionRequest hook; exact route/model/provider,
  freshness, catalog, and constructability are proven before side effects.
- **A9-REALDOORS** — actual native, OMP, and managed doors test valid,
  unknown, stale, mismatch, and missing proofs with zero pre-admission side
  effects, plus terminal and legacy compatibility coverage.
- **A9-HANDLER** — unresolved scheduling envelopes carry a valid
  SchedulingCondition and DispatchOutcome through handlers into PhaseResult,
  without failure/breaker accounting.
- **A9-MANAGED-OBS** — managed keeps its integer API while exposing the typed
  unresolved/terminal outcome through a canonical managed-door-owned result
  channel, without relaunch.

No second WBC authority, frozen/status/execution-log/index changes, commit,
push, merge, deploy, or Batch-3 redesign.
