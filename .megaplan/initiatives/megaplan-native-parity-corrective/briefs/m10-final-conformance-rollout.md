# M10 - Final Conformance Rollout

## Objective

Generate final semantic conformance evidence from checked source, behavior
scenarios, installed-package execution, and quarantined compatibility paths.

## Files To Change And Instructions

- Semantic checker and conformance validator
  Make final ledger/report generation consume checker evidence. Reject stale,
  hand-authored, path-only, or report-only implemented rows.
- Traceability artifacts
  Re-prove every row. No old `enabled` or `implemented` status is inherited.
- Docs
  Update end-state/current-state/corrective docs where implementation made
  deliberate narrowing decisions. Any narrowing requires a checker rule and
  behavior scenario.
- Tests
  Run full deterministic scenario suite, installed-package source check,
  topology regeneration, handler-purity scan, compatibility quarantine checks,
  and dead-delete mutation checks.

## Verifiable Completion Criterion

- Generated conformance report cannot mark a row implemented without checker
  evidence.
- Installed package uses the same canonical `.pypeline` source and semantics.
- All split-outcome behavior scenarios pass.
- Prior conformance reports are preserved only as historical baseline/failure
  evidence.
- The final state satisfies the North Star and
  `docs/arnold/megaplan-native-representation-report.md` or records deliberate
  narrowing with checker and behavior proof.

