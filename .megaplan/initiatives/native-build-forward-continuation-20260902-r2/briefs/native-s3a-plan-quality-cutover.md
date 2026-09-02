# Native S3A — Prep, plan, critique cutover and GO-1A

## Outcome

Move the front-half plan-quality topology and decisions into canonical .pype source and declared policy.

## Scope

Create workflow.pype and the plan-quality critique child; expose prep clarification, plan boundaries, robustness skip, evaluator retry, dynamic lens fanout/reducer, fallback, execution plane, and shared resume gate; transition once.

## Locked decisions

- The controlling milestone definition is `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §5, **Native S3A — Prep, plan, critique cutover and GO-1A**, as qualified by its `Revision 2026-08-24 (post-reconciliation)`.
- Native representation obligations remain the row-level contract in `docs/arnold/megaplan-native-representation-alignment-plan.md` §Traceability Matrix. This milestone owns or affects: **Prep clarification; plan artifacts; critique skip/retry/fanout; human suspension; model routing; handler purity; D1–D2, D11, D15**. An `enabled` row is substrate, never implemented conformance.
- `docs/arnold/megaplan-native-representation-report.md` remains architecture authority; this brief and the active chain are executable authority for this milestone.
- Native Parity precedes Platformization. M11 authority cannot be emulated locally. `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates.

## Open questions

- Which temporary legacy resume seam needs an expiry-bound allowance through S3B?
- Any answer that changes authority, milestone order, or a must-level done criterion requires an additive decision record; the executor may not decide it implicitly.

## Constraints

- All routes/retries/fanout are visible in source or declared policy; transport retry is not semantic retry; old front-half producer becomes inert after one transition.
- Preserve the exact predecessor artifact hashes and chain dependency. Missing or stale evidence fails closed.
- MRC mechanics may be reused only as patterns; maintenance receipts, capabilities, route tables, and canary results do not satisfy M11 or Native proof.

## Done criteria

- The proof pack follows `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §6: immutable source/predecessor/brief/North-Star digests; selected-surface inventory; invocation provenance; focused elapsed-budget test receipts; source/carrier scans and expected-red mutations; raw runtime traces; installed runtime/decoder/lowerer identities; applicable readiness/transition/post-transition receipts; applicable canary census and rollback; typed allowance/exception registry; independent review and supersession lineage; and validator output with stable issue codes and zero dangling references.
- Evidence is proportional to the milestone's claims, but authority, effect, and publication cuts may not omit readiness, typed transition, independent post-verification, or rollback evidence.
- The milestone-specific outputs below are content-addressed, named in the proof map, validator-green at merge HEAD, and consumed by the next milestone.
- D1/D2 goldens, malformed/evaluator retry fixtures, clarification death/resume, handler-purity mutations, old-producer inertness, and GO-1A receipt.

## Touchpoints

- arnold_pipelines/megaplan/workflows/; arnold_pipelines/megaplan/handlers/prep.py; arnold_pipelines/megaplan/handlers/critique.py
- `docs/arnold/native-plan-reconciliation-2026-08-24.md`
- `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`
- `docs/arnold/megaplan-native-representation-alignment-plan.md`

## Anti-scope

- No handler-wrapped parallel_map, hidden lens selection, dual front-half writer, or status-derived resume authority.
- Do not rewrite historical manifests or evidence, launch later milestones early, add compatibility aliases, or turn projections/status into authority.
