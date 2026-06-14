---
id: 01KTPVSH8X04XE0D122M0V0712
title: Neutral pipeline executor fails SILENTLY on an unresolvable next-label (routing
  typo halts mid-run)
status: open
source: human
tags:
- arnold
- pipeline
- executor
- correctness
- high-severity
codebase_id: null
created_at: '2026-06-09T18:54:50.141269+00:00'
last_edited_at: '2026-06-09T18:56:37.998306+00:00'
epics:
- epic_id: aggressive-generalized-pipeline-migration
  resolves_on_complete: false
  linked_at: '2026-06-09T18:56:37.998300+00:00'
---

SEVERITY: HIGH — standalone correctness hazard, independent of the epic-2 migration completing.

FINDING (independent architecture review, 2026-06-09): when a Step returns a StepResult whose `next` label matches no outgoing Edge on a stage that declares no decision_vocabulary, the neutral executor SILENTLY halts the walk-loop instead of failing loud.

EVIDENCE (arnold/pipeline, /private/tmp/arnold-target):
- routing.py:139 — resolve_edge raises RoutingError when `next` matches no edge.
- executor.py:222-224 — the executor SWALLOWS that error and `break`s the walk-loop for simple (no-vocabulary) stages.
- tests/arnold/pipeline/test_executor.py:457-475 (test_loop_prevention_missing_edge_terminates) — a `"gone"` typo for `"go"` is asserted to terminate with step_b NEVER running. The silent-halt is currently tested as INTENDED behavior.

WHY IT MATTERS: the build-time validator catches structural unreachability, but it CANNOT catch a step emitting a label that mismatches its own stage's edges (that's a runtime value). So a one-character typo in a `next` label silently truncates a pipeline mid-run with no error, no log, no failed status. Classic string-typed-routing failure mode; will cost someone a baffling debugging afternoon.

PROPOSED FIX (small, well-scoped, in the neutral executor):
- Distinguish a legitimate terminal exit (`next == "halt"`, or a stage with no outgoing edges) from an UNRESOLVABLE label on a stage that HAS edges. Fail LOUD (raise / record a failed terminal status with a clear diagnostic naming the bad label + the stage's available labels) for the latter; keep loop-prevention only for genuine terminal stages.
- Flip test_loop_prevention_missing_edge_terminates to assert fail-loud (it currently encodes the bug as intended).
- Add a regression test: step emits a label not in its edge set on an edged stage -> explicit error, not silent halt.

CROSS-REF: surfaced alongside the --no-push local-commit fix work; same review flagged tickets for the typed-seam-not-wired and suspend-not-primitive gaps. This one is NOT migration-dependent — worth fixing now.
