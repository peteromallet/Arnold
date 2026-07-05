# S7 - Final Conformance Rollout

## Objective

Generate final semantic conformance evidence from checked source, behavior
scenarios, installed-package execution, and quarantined compatibility paths.
Close the epic only if the North Star is genuinely reached or any deliberate
narrowing is proved by checker rule plus behavior scenario.

## Legacy 10-Sprint Source Mapping

- Absorbs `m10-final-conformance-rollout.md`.
- Re-validates every old M1-M10 acceptance criterion against the compressed
  seven-sprint implementation.

## Work Required

- Make final ledger/report generation consume checker evidence. Reject stale,
  hand-authored, path-only, or report-only implemented rows.
- Re-prove every traceability row. No old `enabled` or `implemented` status is
  inherited.
- Run the full deterministic split-outcome scenario suite, including:
  - prep clarify suspend/resume;
  - gate reprompt/downgrade;
  - critical vs cosmetic cap exhaustion;
  - tiebreaker replan/rejoin;
  - execute blocked batch recover/resume;
  - destructive approval gate;
  - review rework cycle;
  - blocking vs advisory review cap;
  - no-review terminal path;
  - override force-proceed and abort.
- Run installed-package source check, topology regeneration, handler-purity
  scan, compatibility quarantine checks, and dead-delete mutation checks.
- Validate resume identity and serialized-state consumer compatibility for
  human gates, tiebreaker pending, execute approvals, and blocked recovery.
- Pin or hash deterministic prompt/model fixtures used in behavior scenarios,
  or document refresh rules that prevent stale-fixture false confidence.
- Update end-state/current-state/corrective docs where implementation made
  deliberate narrowing decisions.
- Keep prior conformance reports only as historical baseline/failure evidence.

## Verifiable Completion Criterion

- Generated conformance report cannot mark a row implemented without checker
  evidence.
- Installed package uses the same canonical `.pypeline` source and semantics.
- All split-outcome behavior scenarios pass.
- Compatibility paths are either deleted, data-only adapters, or fenced legacy
  paths that cannot satisfy row evidence.
- Final state satisfies the North Star and
  `docs/arnold/megaplan-native-representation-report.md`, or records deliberate
  narrowing with checker and behavior proof.

## Do Not Close If

- Any report-owned route is still owned by components, handlers, manifest edge
  maps, auto next-step derivation, CLI dispatch, or projected-native
  compatibility.
- The final report is hand-maintained next to conflicting prose documents.
