# Native S2R — Durable primitives, Custody binding, and GO-0

## Outcome

Enable the sole completion kernel and durable control primitives under the complete accepted M11 action envelope.

## Scope

Reconsume GO-FORMAT/C1/C2; implement typed decisions/outcomes, named exits, bounded loops, keyed reducers, frozen fanout, retry/fallback, suspension/reentry, checkpoints, call-site policy, typed errors, and agentic boundaries; run GO-0.

## Durable recovery slice

After C2's Bucket A launch admission, this milestone owns the Bucket B recovery
and replay hardening in the [launch/durability root map](../handoff/launch-and-durability-root-map-20260903.md): operation-owned journal deltas (R14),
held-operation/receipt-effect reconciliation (R15), reviewed-source object
provenance (R16), one allocator and exact N/N+1 migration (R18), and explicit
A/B/C recovery topology (R19). Keep these as one durable-primitives slice;
do not add micro-milestones or a second cleanup ledger.

## Locked decisions

- The controlling milestone definition is `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §5, **Native S2R — Durable primitives, Custody binding, and GO-0**, as qualified by its `Revision 2026-08-24 (post-reconciliation)`.
- Native representation obligations remain the row-level contract in `docs/arnold/megaplan-native-representation-alignment-plan.md` §Traceability Matrix. This milestone owns or affects: **Bounded loop; runtime iteration/map; typed loop outcomes; path checkpoints; timeout/model policy; H7, H9; D12–D14**. An `enabled` row is substrate, never implemented conformance.
- `docs/arnold/megaplan-native-representation-report.md` remains architecture authority; this brief and the active chain are executable authority for this milestone.
- Native Parity precedes Platformization. M11 authority cannot be emulated locally. `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates.

## Open questions

- Are any required durable primitives still missing accepted M11 action/effect semantics?
- Any answer that changes authority, milestone order, or a must-level done criterion requires an additive decision record; the executor may not decide it implicitly.

## Constraints

- One CAS/transition seam; mint-only narrow capabilities; elapsed budgets; append-only events; read-only projections; exactly one enabled completion kernel.
- Preserve the exact predecessor artifact hashes and chain dependency. Missing or stale evidence fails closed.
- MRC mechanics may be reused only as patterns; maintenance receipts, capabilities, route tables, and canary results do not satisfy M11 or Native proof.

## Done criteria

- The proof pack follows `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §6: immutable source/predecessor/brief/North-Star digests; selected-surface inventory; invocation provenance; focused elapsed-budget test receipts; source/carrier scans and expected-red mutations; raw runtime traces; installed runtime/decoder/lowerer identities; applicable readiness/transition/post-transition receipts; applicable canary census and rollback; typed allowance/exception registry; independent review and supersession lineage; and validator output with stable issue codes and zero dangling references.
- Evidence is proportional to the milestone's claims, but authority, effect, and publication cuts may not omit readiness, typed transition, independent post-verification, or rollback evidence.
- The milestone-specific outputs below are content-addressed, named in the proof map, validator-green at merge HEAD, and consumed by the next milestone.
- Generic primitive corpus, reducer/identity proofs, stale fence/epoch negatives, checkpoint restore, GO-0 transition/post-verification receipts, and exactly-one-kernel proof.
- Crash/replay/hold/migration fixtures prove idempotence, exact owned deltas,
  unchanged loser hashes, and no manual state surgery dependency. These proofs
  are required before durable-running promotion even if first dispatch succeeds.

## Touchpoints

- arnold/pipeline/native/; arnold/workflow/completion/; accepted M11 APIs; .megaplan/initiatives/megaplan-native-parity-corrective/
- `docs/arnold/native-plan-reconciliation-2026-08-24.md`
- `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`
- `docs/arnold/megaplan-native-representation-alignment-plan.md`

## Anti-scope

- No generic product routing, ambient mutation permission, duplicate kernel, open-stream expansion, or projection authority.
- Do not rewrite historical manifests or evidence, launch later milestones early, add compatibility aliases, or turn projections/status into authority.
