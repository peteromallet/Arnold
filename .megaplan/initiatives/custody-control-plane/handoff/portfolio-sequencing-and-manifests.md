---
type: handoff
date: 2026-07-13
---

# Portfolio sequencing and content-addressed handoffs

## Canonical sequence

1. Land and attest the generic immutable chain execution-binding guard outside
   this chain. It must reject launch/handoff/resume/reconcile drift and require
   cumulative North Star receipts; otherwise the chain cannot safely select the
   new milestone sequence.
2. Finish the WBC merge outside this epic and generate current WBC completion/
   support proof. The operator supplies the exact merge commit afterward; this
   initiative never guesses it from a topic branch, dirty tree, or latest ref.
3. Admit the chain only when the execution-binding receipt and WBC
   `chain_completed` preconditions validate.
   Run M5 against the landed Run Authority chain. Reconcile all three rejected
   receipts, bind the passing M3 reducer result, eliminate structural evidence
   failures, reach zero canonical verification divergences, regenerate the
   content-addressed proof/manifest, and attest canonical retirement.
4. Admit M6 only after manual review/merge verifies M5's exact handoff. Bind the
   audited WBC merge commit to its consolidation evidence, deliberate proof map,
   support/conformance manifest, landed ancestry, and installed/runtime revision. Do
   not change WBC's C1-C6 identities, source, active state, process, branch,
   gates, or owned contracts from this epic. Generate the exact WBC boundary
   inventory; do not accept the support manifest as runtime adoption proof.
5. Record the initiative approval after M6 reconciles both manifests and its
   residual ownership map. Only then may M6A implement the WBC-owned
   transactional ledger/API, payload-policy enforcement and migrations.
6. Admit M7 only after M6A's store/API and fault/migration proof are accepted;
   admit M8 universal producer adoption only after M7's Custody writer contract.
   M9-M11 and M8A consume the resulting exact-version evidence in serial order.
7. Each later milestone consumes the previous milestone's immutable handoff and
   updates residual matrix rows. M11 generates—not hand-authors—the final proof
   map and completion manifest after every retirement gate passes.

Megaplan Maintenance is adjacent: its repair/audit products consume the same
authority and custody contracts but are neither a WBC launch condition nor a
second authority owner. Native topology/parity work owns `.pypeline`, compiler,
manifest, and compatibility-topology decisions; those surfaces enter this epic
only as pinned evidence/adopters.

## Staged admission evidence

- Chain/M5 entry: a current immutable execution binding, audited WBC merge
  evidence plus the landed three-
  milestone Run Authority history, canonical plan/chain state, and constrained
  retirement record. Already-accepted Run Authority receipts are deliberately
  not required, and the WBC evidence grants no action authority. The old
  four-milestone cloud terminal state is explicitly not current C1-C6 completion.
- M6 entry: M5's three accepted current receipts, zero-divergence verification,
  regenerated proof map/manifest, canonical
  `.megaplan/initiatives/runauthority-epic/.retired` marker, and its retirement
  attestation. The exact audited WBC merge commit must match landed ancestry,
  current support proof and runtime before M6 can complete.
- M6A entry: M6's immutable ownership/residual handoff, exact final landed WBC
  and runtime vector, generated boundary inventory, and accepted decision record.
- M7 entry: M6A's transactional store/API, migrations and accepted fault/data-
  policy proof plus the unchanged M6 decision
  record, including exact manifest digests, runtime revisions, policies,
  allowlists, canary/rollback owners, and deletion authority.

Every entry and exit additionally consumes a cumulative North Star receipt from
the generic guard. It binds expected versus observed chain/brief/anchor/source/
runtime identity and proves predecessor obligations and prior conformance did
not regress in enforce mode.

## Milestone handoffs

- M5 → M6: three accepted Run Authority receipts, zero-divergence canonical
  verification, regenerated proof/manifest bundle, canonical
  `runauthority-epic/.retired` marker and retirement attestation, and empty
  unresolved-evidence list.
- M6 → M6A: exact contract/version bundle, prerequisite proof index, residual
  zero-exemption matrix, generated WBC boundary inventory, controlled-writer/
  consumer registry, compatibility inventory, accepted approval, and unresolved
  blocker list (which must be empty for implementation).
- M6A → M7: operational WBC store/query API, transaction/outbox and exactly-one-
  terminal semantics, payload privacy/retention/encryption enforcement,
  deterministic migrations, process-safe adapters, fault/replay traces, and an
  empty substrate-blocker list.
- M7 → M8: controlled writer/action-validator registry, custody-target and
  repair-occurrence schemas, renewable lease/custody-epoch/transfer contract,
  dual-fence/idempotency/partial-persistence conformance, projection contract,
  dead-letter/reconciliation runbook, and evidence that no new authority,
  WBC-ledger, or lifecycle owner was introduced.
- M8 → M8A: universal producer/adopter manifest, generated call-site plus
  runtime-trace equality, boundary/attempt/decision join evidence,
  exact-version fixtures, child/root lineage proof, and residual reader map.
- M8A → M9: DAG feasibility reports, captured replay hashes, deterministic
  validation receipts, source/runtime preflight, bounded executor circuits,
  repair-adoption proof, and fully identified work/latency events.
- M9 → M10: coherent source-cursor projection schemas/digests, reader registry, joined
  productive/replayed ledger, deterministic reason evidence, drift and false-
  liveness fixtures, idle projection canary, and pure-observer proof.
- M10 → M11: effect registry, crash/reconciliation and cross-host handoff matrix,
  replay receipts, exact-occurrence event-driven recovery SLO, independent recovery evidence,
  repair/worker canary/kill-switch/rollback proof, genuine-block candidate, and
  a list of legacy paths eligible (not yet authorized) for removal.
- M11 → downstream: comprehensive cross-contract acceptance/conformance results
  plus a generated completion manifest hashing the unchanged chain,
  North Star, M5-M11 and M6A briefs, chain state, merged publication evidence, WBC/Run
  Authority inputs, per-row proof, captured replay, installed-runtime provenance,
  canaries, genuine blocked-run recovery, per-row deletion/retirement proof,
  conformance, projection rebuild, rollback, and zero-bypass evidence.

Any change to a hashed prerequisite or handoff invalidates downstream admission
until the corresponding evidence is regenerated. Status prose, timestamps,
green subsets, or manually copied JSON are not completion proof.
