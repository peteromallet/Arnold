# Batch 2 attempt 8 — converged Luna rework

Verdict: **REWORK REQUIRED**. Bound to attempt-7 brief SHA
`7497ba76a6cd1463edf84c3e51c7507dfd0151c9788371c275001d98cf6a9b19` and the
three Luna REWORK verdicts; no additional Sol oracle was commissioned.

- **A8-AUTH** — production doors use only backend/system-owned route,
  memory, and cooldown observations; dependency injection remains confined to
  non-production/test paths.
- **A8-CONTEXT** — provider and route-liveness identity/context survive typed
  outcome, terminal ledger, replay, auth metadata, and PhaseResult transport.
- **A8-UNRESOLVED** — append/link uncertainty remains lossless through native,
  OMP, managed, and handler boundaries without tuple-unpacking typed outcomes;
  legacy tuple/int success APIs remain intact.
- **A8-REALDOOR/A8-FIXTURES** — actual-door and downstream coverage is repaired
  where available, and remaining accepted-first fixtures use the canonical
  lifecycle prefix.

No second WBC authority, frozen/status/execution-log/index changes, commit,
push, merge, deploy, or Batch-3 redesign.
