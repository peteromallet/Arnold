# Native C2 — Completion binding and evaluation shadow

## Outcome

Prove immutable completion binding/evaluation and persisted-wire behavior in shadow before S2R enables it.

## Scope

Implement binding/evaluation schemas, proof modes, aggregation signatures, decoder matrix, restore/projection invariance, and atomic shadow acceptance.

## Launch-critical continuation intake

Before any real owner/provider/fixer dispatch, this milestone consumes Bucket A
of [`handoff/launch-and-durability-root-map-20260903.md`](../handoff/launch-and-durability-root-map-20260903.md): the supported current-attempt continuation (R01, with R02 conditional), semantic identity/CAS (R03A/R03B), complete immutable custody (R04), scoped route and provider boundaries (R05–R07), source-bound bootstrap and structured probe (R08, R12), broker capability and pointer/origin admission (R09/R10), zero-write/precondition ordering (R11/R13), and resident toolchain closure (R20). These are one C2 admission surface, not new milestones.

C2 also records conditional closure or not-applicable receipts for R14–R19
against the exact preserved remote chain state: chain-state, marker/manifest,
journal/hold/sequence, source, runtime identity, and a fresh read timestamp.
An applicable condition is closed only through its supported operation; a
not-applicable result names the exact state that makes it so. R17 is mandatory
Bucket A work, not conditional: reread lease/fence/tmux/PID/provider/fixer and
`should_run` authority at the final admission lock. This is required because
the supported fresh/on-box launch previously treated a historical marker as
live authority (C-OCC-030). R14–R19's generic crash/replay/migration/topology
hardening remains in S2R/S6 and is not claimed complete by these receipts.

The remote continuation's exact completed prefix is P0, P1, P2, Native S1,
Native S2F, and Native C1; C2 is next. Preserve those six artifacts and their
hashes. Adoption is the typed current-attempt restart/recovery transaction:
preserve the six-prefix under CAS, retire the progressed attempt once, and
create the continuation identity. Ordinary reconcile and `target-rebind` are
not adoption for progressed C2; `target-rebind` is pre-execute-only and C2 has
no `milestone.branch`. Any ordinary source/runtime transfer remains
quarantine-only until separately authorized. A source commit or local green
test is not publication, deployment, or live proof.

## Locked decisions

- The controlling milestone definition is `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §5, **Native C2 — Completion binding and evaluation shadow**, as qualified by its `Revision 2026-08-24 (post-reconciliation)`.
- Native representation obligations remain the row-level contract in `docs/arnold/megaplan-native-representation-alignment-plan.md` §Traceability Matrix. This milestone owns or affects: **Path checkpoints; golden regeneration guard; behavior parity; D10, D12–D14**. An `enabled` row is substrate, never implemented conformance.
- `docs/arnold/megaplan-native-representation-report.md` remains architecture authority; this brief and the active chain are executable authority for this milestone.
- Native Parity precedes Platformization. M11 authority cannot be emulated locally. `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates.

## Open questions

- Which decoder promises begin at S2R and which remain experimental until Platform S6?
- Any answer that changes authority, milestone order, or a must-level done criterion requires an additive decision record; the executor may not decide it implicitly.

## Constraints

- Python type compatibility is not wire compatibility. Projections are rebuildable and cannot authorize acceptance. No authoritative writer exists.
- Preserve the exact predecessor artifact hashes and chain dependency. Missing or stale evidence fails closed.
- MRC mechanics may be reused only as patterns; maintenance receipts, capabilities, route tables, and canary results do not satisfy M11 or Native proof.

## Done criteria

- The proof pack follows `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` §6: immutable source/predecessor/brief/North-Star digests; selected-surface inventory; invocation provenance; focused elapsed-budget test receipts; source/carrier scans and expected-red mutations; raw runtime traces; installed runtime/decoder/lowerer identities; applicable readiness/transition/post-transition receipts; applicable canary census and rollback; typed allowance/exception registry; independent review and supersession lineage; and validator output with stable issue codes and zero dangling references.
- Evidence is proportional to the milestone's claims, but authority, effect, and publication cuts may not omit readiness, typed transition, independent post-verification, or rollback evidence.
- The milestone-specific outputs below are content-addressed, named in the proof map, validator-green at merge HEAD, and consumed by the next milestone.
- C2 proof pack and manifest, cross-version decoder positives/negatives, projection delete/rebuild/forgery fixtures, aggregation proofs, and zero-writer evidence.
- Bucket A launch admission has exact custody/runtime/profile/provider receipts,
  zero-write evidence, preserved-state R14–R19 closure/not-applicable receipts,
  mandatory fresh R17 liveness evidence, and a real dispatch handoff; no
  provider/fixer claim is inferred from partial runtime or marker artifacts.

## Touchpoints

- arnold/workflow/completion/; .megaplan/initiatives/standardized-completion-specifications/; .megaplan/initiatives/megaplan-native-parity-corrective/
- `docs/arnold/native-plan-reconciliation-2026-08-24.md`
- `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md`
- `docs/arnold/megaplan-native-representation-alignment-plan.md`

## Anti-scope

- No projection-as-proof, implicit migration, mixed-version reinterpretation, or live completion enablement.
- Do not rewrite historical manifests or evidence, launch later milestones early, add compatibility aliases, or turn projections/status into authority.
- Do not create a parallel bureaucracy/cleanup chain, duplicate root ledger, or
  per-batch Luna review gate; later durability work remains in the existing
  S2R/S6/Platform suffix.
