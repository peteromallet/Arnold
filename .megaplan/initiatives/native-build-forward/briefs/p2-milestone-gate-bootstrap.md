# P2 — Milestone-gate bootstrap and readiness

## Outcome

Certify the generic milestone-gate bootstrap and produce the three exact readiness artifacts required by Native.

## Scope

Implement or validate non-self-hosted pre-merge conformance, merge-HEAD revalidation, exact predecessor assertions, typed receipt-consuming transitions, and independent post-transition verification.

## Locked decisions

- The controlling milestone definition is `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §5, **P2 — Milestone-gate bootstrap and readiness**, as qualified by its `Revision 2026-08-24 (post-reconciliation)`.
- Native representation obligations remain the row-level contract in `docs/arnold/megaplan-native-representation-alignment-plan.md` §Traceability Matrix. This milestone owns or affects: **H0, H2, H5; all D waves indirectly**. An `enabled` row is substrate, never implemented conformance.
- `docs/arnold/megaplan-native-representation-report.md` remains architecture authority; this brief and the active chain are executable authority for this milestone.
- Native Parity precedes Platformization. M11 authority cannot be emulated locally. `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates.

## Open questions

- Which trusted independent verifier and merge-readiness principal certify the bootstrap without self-certification?
- Any answer that changes authority, milestone order, or a must-level done criterion requires an additive decision record; the executor may not decide it implicitly.

## Constraints

- Bootstrap may not authorize itself. Evidence must bind merge HEAD and the exact downstream specs. Emit downstream-spec-readiness.json, completion-crosswalk-readiness.json, and editable-runtime-readiness.json.
- Preserve the exact predecessor artifact hashes and chain dependency. Missing or stale evidence fails closed.
- MRC mechanics may be reused only as patterns; maintenance receipts, capabilities, route tables, and canary results do not satisfy M11 or Native proof.

## Done criteria

- The proof pack follows `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §6: immutable source/predecessor/brief/North-Star digests; selected-surface inventory; invocation provenance; focused elapsed-budget test receipts; source/carrier scans and expected-red mutations; raw runtime traces; installed runtime/decoder/lowerer identities; applicable readiness/transition/post-transition receipts; applicable canary census and rollback; typed allowance/exception registry; independent review and supersession lineage; and validator output with stable issue codes and zero dangling references.
- Evidence is proportional to the milestone's claims, but authority, effect, and publication cuts may not omit readiness, typed transition, independent post-verification, or rollback evidence.
- The milestone-specific outputs below are content-addressed, named in the proof map, validator-green at merge HEAD, and consumed by the next milestone.
- Accepted bootstrap completion manifest plus all three readiness artifacts, independent verification, mutation failures for stale/wrong-tree/partial receipts, and downstream spec hash binding.

## Touchpoints

- .megaplan/initiatives/megaplan-chain-milestone-gates/; .megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml
- `docs/arnold/native-plan-reconciliation-2026-08-24.md`
- `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`
- `docs/arnold/megaplan-native-representation-alignment-plan.md`

## Anti-scope

- No Native semantic work, no stale pre-merge proof, no prose-only gate, no human-gated cloud policy.
- Do not rewrite historical manifests or evidence, launch later milestones early, add compatibility aliases, or turn projections/status into authority.
