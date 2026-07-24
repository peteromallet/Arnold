# M1: Alive-But-Failed Recovery Hardening

## Outcome

Make the alive-but-failed repair-custody correction durable, deployed, and
proven against the original `megaplan-native-parity-corrective` cloud failure.

This sprint should finish the local repair-loop/status contract work, close only
the minimum `FailureReceipt`/status/auditor gather gap needed for visible
custody, deploy corrected source and wrappers to the cloud runtime, re-check the
original session, and write a handoff for `workflow-boundary-contracts`.

## Source Inputs

Treat these as the detailed source material:

- `.megaplan/initiatives/superfixer-repair-custody/briefs/alive-but-failed-recovery-hardening.md`
- `.megaplan/initiatives/superfixer-repair-custody/prep-alive-but-failed-recovery-hardening.md`
- `.megaplan/initiatives/superfixer-repair-custody/NORTHSTAR.md`
- `.megaplan/initiatives/workflow-boundary-contracts/notes/alive-but-failed-operational-precedent.md`

The repo may already contain a local patch for this behavior. Audit the current
checkout first. Preserve correct existing work rather than reimplementing it.

## Scope

IN:

- Verify and finish the repair outcome lattice:
  `complete`, `progressed`, and true human blocker are success; liveness-only
  outcomes are not.
- Ensure legacy `live_with_fresh_activity` loads as non-success partial
  liveness.
- Ensure new producers write `partial_liveness` for fresh activity/liveness
  without original failure clearance.
- Ensure `partial_liveness` does not clear repair markers, write
  `last_success_*`, or satisfy watchdog recovery.
- Ensure live process plus unchanged repairable `phase_failed`/failure receipt
  surfaces as `alive_but_failed` or equivalent attention-needed custody, not
  plain `running`.
- Add the smallest missing operational `FailureReceipt`/status/auditor gather
  projection needed to prove custody for this failure.
- Run focused tests and wrapper syntax checks.
- Deploy source and installed wrappers to the Hetzner/cloud runtime used by the
  original `megaplan-native-parity-corrective` session.
- Re-check the original session after deployment and trigger the minimum safe
  retry/relaunch/repair path needed to prove the false-success loop is gone.
- Write a handoff note or run summary for `workflow-boundary-contracts` covering
  `partial_liveness`, `alive_but_failed`, failure-receipt clearance, source
  checkout identity, runtime identity, installed wrapper identity, and residual
  product failures if any.

OUT:

- Completing native parity product work.
- Building the full `BoundaryContract` system.
- Replacing watchdog shell architecture wholesale.
- Implementing the full incident control plane.
- Renaming `partial_liveness` or `alive_but_failed` without migration.
- Treating status/repair/auditor findings as product route authority.

## Locked Decisions

- Process liveness is not repair success.
- Fresh activity while the original repairable failure receipt remains current
  is partial liveness.
- Repair completion is trusted only when the original finding/failure receipt
  clears, or when a structured true-human/no-fix verdict is recorded.
- `FailureReceipt` is operational here and later generalized by
  `workflow-boundary-contracts`; this sprint must not invent a competing
  boundary schema.
- Deployment proof matters as much as local tests: source checkout, runtime
  identity, installed wrapper identity, repair-data outcome, and post-relaunch
  receipt must be recorded.

## Open Questions

- Does the original session still have a separate native-parity product/import
  bug after repair custody is fixed?
- Is the current local `FailureReceipt`/incident bridge projection sufficient,
  or is one more projection needed before cloud verification?
- Which remote checkout and installed wrapper paths are authoritative at launch
  time?

## Done Criteria

1. Focused repair/status/meta/incident/wrapper tests pass.
2. Touched wrappers pass `bash -n`.
3. Search evidence shows no current producer treats `live_with_fresh_activity`
   as success.
4. A live process plus unresolved repairable failure fixture/status reports
   `alive_but_failed` / attention-needed custody.
5. `partial_liveness` cannot clear markers or update `last_success_*`.
6. Cloud source/runtime/wrapper identities are recorded after deployment.
7. The original `megaplan-native-parity-corrective` session is rechecked after
   deployment.
8. The original session either genuinely progresses/recovers, or remains
   accurately failed with visible repair custody rather than being masked by
   liveness.
9. Any remaining native-parity product failure is documented separately.
10. A handoff summary is written for `workflow-boundary-contracts`.
