# Native Build Forward

**Status: canonical source authored; not launched.** The supported resident
continuation has a six-milestone completed prefix and is paused at C2; this
source update does not copy or reset that state.

This initiative is the single cloud-epic source for the operator-accepted hybrid build-forward sequence. It starts with read-only MRC intake, resolves Custody M11 admission as a six-result gate, certifies the milestone-gate bootstrap, executes all twelve Native Parity milestones, and only then executes all seven Platformization milestones.

## Authority

- Architecture: `docs/arnold/megaplan-native-representation-report.md`.
- Adjudication: `docs/arnold/native-plan-reconciliation-2026-08-24.md`.
- Implementation guide: `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`, post-reconciliation revision.
- Executable source: this `chain.yaml`, `NORTHSTAR.md`, and `briefs/*.md`; milestone execution must also consume the active validators, transition handlers, proof maps, and accepted receipts.

The deprecated `docs/arnold/DEPRECATED-completion-spec-sequencing-and-ownership.md` remains architecture, ownership, completion-contract, oracle, and enforcement-matrix reference only. It is not an execution entry point. Historical completed initiatives are substrate and evidence, not corrective conformance.

## Files

- `NORTHSTAR.md` — durable Native-Parity-then-Platformization destination and authority boundaries.
- `chain.yaml` — the 22-position controlling sequence with explicit linear dependencies, `partnered-5`, and unattended auto-merge policy.
- `briefs/*.md` — one full brief per prerequisite, Native, and Platform milestone.
- `cloud.yaml` — canonical SSH cloud-chain target and isolated workspace/session.
- `handoff/launch-and-durability-root-map-20260903.md` — the single compact
  mapping of all 23 accepted forensic roots to launch or durability ownership.

## Admission behavior

P0 may run read-only. P1 validates reconciliation §7 gates 1–5 and emits a conditional admission result that keeps gate 6—the P2 bootstrap manifest and three readiness artifacts—explicitly unsatisfied. P2 closes that row. Native S1 may start only after all six are content-addressed and validator-green; historical completion claims, local facades, MRC receipts, projections, and inferred acceptance never qualify.

No command has been run to initialize, launch, deploy, or push this initiative.

## Continuation and review policy

The existing six-milestone prefix remains exactly
`P0 → P1 → P2 → Native S1 → S2F → C1`; C2 is the next position. Resume must
use the typed current-attempt restart/recovery transaction, preserving that
six-milestone prefix under CAS and creating the continuation identity. Ordinary
reconcile and `target-rebind` are not adoption for progressed C2;
`target-rebind` is pre-execute-only and C2 has no `milestone.branch`. Any
ordinary source/runtime transfer remains quarantine-only until the typed
adoption is separately authorized. It must not be driven from a local
zero-state, a copied cursor, or a parallel bureaucracy chain.

The launch-critical Bucket A work is folded into C2 and its existing suffix;
durable autonomy and operator simplification are folded into Native S6 and
Platform S2A-or-later. Each milestone uses its configured Megaplan robustness.
There are no mandatory Megado per-batch Luna reviews or duplicate progress
ledgers. The initiative's bounded artifacts are this North Star, the chain
spec, one brief per milestone, and generated execution/review evidence.
