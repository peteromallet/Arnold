# Batch 2 attempt 15 — OMP identity and dispatcher transport

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-14 brief and its
reviews (OMP-handler REWORK, doors REWORK structural, regression PASS). This
pass addresses only the converged OMP `WorkerResult` identity roundtrip and
live dispatcher-on physical-door coverage; no additional Sol oracle was
commissioned.

- Preserve worker identity and typed terminal context through
  `WorkerResult`/`AgentResult` projection and the legacy tuple carrier.
- Exercise dispatcher flag-off and flag-on through the real OMP production
  door; unresolved outcomes remain typed scheduling conditions without
  failure accounting or relaunch.
- Keep managed/native behavior, frozen files, and the existing checker and
  lifecycle contracts unchanged.

No index/status/execution-log changes, commit, push, merge, deploy, or scope
expansion.
