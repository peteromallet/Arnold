# Native S4 — Tiebreaker, finalize, and durable human reentry

## Outcome

Cut tiebreaker/finalize/human waits into named workflows and durable reentry semantics.

## Scope

Split tiebreaker researcher/challenger/synthesis/decision; expose finalize fallback and test-selection outcomes; make every human wait a durable suspension/reentry point; transition producer and fence atomically.

## Locked decisions

- The controlling milestone definition is `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §5, **Native S4 — Tiebreaker, finalize, and durable human reentry**, as qualified by its `Revision 2026-08-24 (post-reconciliation)`.
- Native representation obligations remain the row-level contract in `docs/arnold/megaplan-native-representation-alignment-plan.md` §Traceability Matrix. This milestone owns or affects: **Tiebreaker path; human suspension; finalize fallback; path checkpoints; model routing; D5–D6, D11**. An `enabled` row is substrate, never implemented conformance.
- `docs/arnold/megaplan-native-representation-report.md` remains architecture authority; this brief and the active chain are executable authority for this milestone.
- Native Parity precedes Platformization. M11 authority cannot be emulated locally. `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates.

## Open questions

- Who arbitrates duplicate human responses and which accepted receipt wins?
- Any answer that changes authority, milestone order, or a must-level done criterion requires an additive decision record; the executor may not decide it implicitly.

## Constraints

- Each durable child is its own .pype with stable call-site identity; launcher provenance is evidence only; waits survive process death.
- Preserve the exact predecessor artifact hashes and chain dependency. Missing or stale evidence fails closed.
- MRC mechanics may be reused only as patterns; maintenance receipts, capabilities, route tables, and canary results do not satisfy M11 or Native proof.

## Done criteria

- The proof pack follows `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §6: immutable source/predecessor/brief/North-Star digests; selected-surface inventory; invocation provenance; focused elapsed-budget test receipts; source/carrier scans and expected-red mutations; raw runtime traces; installed runtime/decoder/lowerer identities; applicable readiness/transition/post-transition receipts; applicable canary census and rollback; typed allowance/exception registry; independent review and supersession lineage; and validator output with stable issue codes and zero dangling references.
- Evidence is proportional to the milestone's claims, but authority, effect, and publication cuts may not omit readiness, typed transition, independent post-verification, or rollback evidence.
- The milestone-specific outputs below are content-addressed, named in the proof map, validator-green at merge HEAD, and consumed by the next milestone.
- D5/D6/D11 traces, all tiebreaker/finalize outcomes, duplicate-human arbitration, death/resume, post-transition receipt, and old-seam inertness.

## Touchpoints

- arnold_pipelines/megaplan/handlers/tiebreaker.py; arnold_pipelines/megaplan/handlers/finalize.py; control and resume surfaces
- `docs/arnold/native-plan-reconciliation-2026-08-24.md`
- `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`
- `docs/arnold/megaplan-native-representation-alignment-plan.md`

## Anti-scope

- No component-constant child workflow, shared mini-orchestrator handler, ephemeral human marker, or launcher table as semantic policy.
- Do not rewrite historical manifests or evidence, launch later milestones early, add compatibility aliases, or turn projections/status into authority.
