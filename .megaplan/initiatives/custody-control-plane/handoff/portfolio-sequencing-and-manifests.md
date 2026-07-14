---
type: handoff
date: 2026-07-13
---

# Portfolio sequencing and content-addressed handoffs

## Canonical sequence

1. Run M5 against the landed Run Authority chain. Reconcile all three rejected
   receipts, bind the passing M3 reducer result, eliminate structural evidence
   failures, reach zero canonical verification divergences, regenerate the
   content-addressed proof/manifest, and attest canonical retirement.
2. Admit M6 only after manual review/merge verifies M5's exact handoff. Let WBC
   finish independently. Do not change its C1-C6 identities, source,
   active state, process, branch, gates, or owned contracts from this epic.
3. Validate WBC's completion manifest through its own chain lifecycle and
   deliberate proof map. Its support/conformance manifest must enumerate the
   producer/consumer set it actually proved.
4. Record the initiative approval after M6 reconciles both manifests and its
   residual ownership map. Only then may M7-M11 and M8A begin implementation.
5. Each later milestone consumes the previous milestone's immutable handoff and
   updates residual matrix rows. M11 generates—not hand-authors—the final proof
   map and completion manifest after every retirement gate passes.

Megaplan Maintenance is adjacent: its repair/audit products consume the same
authority and custody contracts but are neither a WBC launch condition nor a
second authority owner. Native topology/parity work owns `.pypeline`, compiler,
manifest, and compatibility-topology decisions; those surfaces enter this epic
only as pinned evidence/adopters.

## Staged admission evidence

- M5 entry: the landed three-milestone Run Authority history, canonical plan and
  chain state, and constrained retirement record. Already-accepted receipts are
  deliberately not required.
- M6 entry: M5's three accepted current receipts, zero-divergence verification,
  regenerated proof map/manifest, canonical
  `.megaplan/initiatives/runauthority-epic/.retired` marker, and its retirement
  attestation. WBC's current manifest/support proof must pass before M6 can
  complete.
- M7 entry: M6's immutable ownership/residual handoff and the accepted decision
  record, including exact manifest digests, runtime revisions, policies,
  allowlists, canary/rollback owners, and deletion authority.

## Milestone handoffs

- M5 → M6: three accepted Run Authority receipts, zero-divergence canonical
  verification, regenerated proof/manifest bundle, canonical
  `runauthority-epic/.retired` marker and retirement attestation, and empty
  unresolved-evidence list.
- M6 → M7: exact contract/version bundle, prerequisite proof index, residual
  zero-exemption matrix, controlled-writer registry, compatibility inventory,
  and unresolved blocker list (which must be empty for enforcement).
- M7 → M8: writer/adaptor registry, fencing/idempotency/partial-persistence
  conformance, projection contract, dead-letter/reconciliation runbook, and
  evidence that no new ledger/lifecycle owner was introduced.
- M8 → M8A: adopter support manifest, boundary/attempt/decision join evidence,
  exact-version fixtures, child/root lineage proof, and residual reader map.
- M8A → M9: DAG feasibility reports, captured replay hashes, deterministic
  validation receipts, source/runtime preflight, bounded executor circuits,
  repair-adoption proof, and fully identified work/latency events.
- M9 → M10: one-reducer projection schemas/digests, reader registry, joined
  productive/replayed ledger, deterministic reason evidence, drift and false-
  liveness fixtures, idle projection canary, and pure-observer proof.
- M10 → M11: effect registry, crash/reconciliation matrix, replay receipts,
  exact-signature event-driven recovery SLO, independent recovery evidence,
  repair/worker canary/kill-switch/rollback proof, genuine-block candidate, and
  a list of legacy paths eligible (not yet authorized) for removal.
- M11 → downstream: generated completion manifest hashing the unchanged chain,
  North Star, M5-M11 briefs, chain state, merged publication evidence, WBC/Run
  Authority inputs, per-row proof, captured replay, installed-runtime provenance,
  canaries, genuine blocked-run recovery, per-row deletion/retirement proof,
  conformance, projection rebuild, rollback, and zero-bypass evidence.

Any change to a hashed prerequisite or handoff invalidates downstream admission
until the corresponding evidence is regenerated. Status prose, timestamps,
green subsets, or manually copied JSON are not completion proof.
