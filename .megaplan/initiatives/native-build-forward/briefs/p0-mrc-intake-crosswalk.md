# P0 — MRC closeout intake and authority crosswalk

## Outcome

Produce a read-only, content-addressed MRC→M11→Native capability and evidence crosswalk without changing any runtime authority.

## Scope

Freeze the exact MRC candidate and evidence manifest; inventory relevant APIs, capabilities, receipts, canary claims, and owners; classify each row as accepted M11 API, M11-owned adapter, MRC-only pattern, or missing M11 proof.

## Locked decisions

- The controlling milestone definition is `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §5, **P0 — MRC closeout intake and authority crosswalk**, as qualified by its `Revision 2026-08-24 (post-reconciliation)`.
- Native representation obligations remain the row-level contract in `docs/arnold/megaplan-native-representation-alignment-plan.md` §Traceability Matrix. This milestone owns or affects: **H0, H2, H4, H8; D12–D13**. An `enabled` row is substrate, never implemented conformance.
- `docs/arnold/megaplan-native-representation-report.md` remains architecture authority; this brief and the active chain are executable authority for this milestone.
- Native Parity precedes Platformization. M11 authority cannot be emulated locally. `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates.

## Open questions

- Which canonical Custody checkout and Run Authority records are authoritative for each crosswalk row?
- Any answer that changes authority, milestone order, or a must-level done criterion requires an additive decision record; the executor may not decide it implicitly.

## Constraints

- Read-only only. No grant, lease, transition, effect, promotion, manifest import, or Native runtime selection may change. An MRC receipt must fail any M11 admission check.
- Preserve the exact predecessor artifact hashes and chain dependency. Missing or stale evidence fails closed.
- MRC mechanics may be reused only as patterns; maintenance receipts, capabilities, route tables, and canary results do not satisfy M11 or Native proof.

## Done criteria

- The proof pack follows `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §6: immutable source/predecessor/brief/North-Star digests; selected-surface inventory; invocation provenance; focused elapsed-budget test receipts; source/carrier scans and expected-red mutations; raw runtime traces; installed runtime/decoder/lowerer identities; applicable readiness/transition/post-transition receipts; applicable canary census and rollback; typed allowance/exception registry; independent review and supersession lineage; and validator output with stable issue codes and zero dangling references.
- Evidence is proportional to the milestone's claims, but authority, effect, and publication cuts may not omit readiness, typed transition, independent post-verification, or rollback evidence.
- The milestone-specific outputs below are content-addressed, named in the proof map, validator-green at merge HEAD, and consumed by the next milestone.
- Validated MRC intake manifest, source SHA/digests, API inventory, ownership/disposition table, and a negative proof that MRC evidence cannot satisfy Custody admission.

## Touchpoints

- docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md; docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json; .megaplan/initiatives/custody-control-plane/
- `docs/arnold/native-plan-reconciliation-2026-08-24.md`
- `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`
- `docs/arnold/megaplan-native-representation-alignment-plan.md`

## Anti-scope

- No Custody repair, no Native implementation, no relabeling maintenance semantics as workflow semantics.
- Do not rewrite historical manifests or evidence, launch later milestones early, add compatibility aliases, or turn projections/status into authority.
