# Custody / Cluster Control Plane — Run Authority and WBC Reconciliation

This is the canonical durable epic for completing pipeline-wide adoption of the
Run Authority, WBC, and cross-host custody contracts. It reuses the existing
Custody Control Plane
initiative because that initiative already owns the authority-lineage audit,
migration matrix, canonical run-state/custody foundation, and the original
residual migration design.

## What already exists

- Custody M1-M4 delivered the canonical run-state resolver, coherent evidence
  model, custody integrations, repair verification, and auditor coverage. Their
  briefs remain historical lineage and are not pending chain milestones.
- `runauthority-epic` landed grants, accepted attempts/decisions, fences,
  quarantine, and operational views. Its three current milestone completion
  receipts are nevertheless rejected, and canonical verification reports three
  divergences. Nominal `done`, merged PRs, and manifest presence are not enough.
- Workflow Boundary Contracts (WBC) owns versioned boundary declarations, the
  durable execution-attempt/external-effect evidence ledger, provenance,
  payload/reference policy, semantic findings, and WBC supported-runtime
  conformance. Its merge is in progress outside this task. This initiative does
  not guess or claim the final merge commit; M6 binds the exact operator-supplied
  merge result to its generated proof/support manifests before implementation.
  Read-only audit of the completed candidate found that its attempt ledger is
  schema-only and its producer matrix is only partially implemented, so M6A-M11
  make operational storage and universal adoption separately provable.
- Existing repair custody has blocker-scoped atomic claims and managed-run
  binding, but the residual cluster gap is an exact action-target/repair-
  occurrence identity plus a durable renewable cross-host lease,
  monotonic custody epoch, transfer/reclaim/reconciliation contract, and
  enforcement at every authoritative effect boundary.

## Settled ownership

| Contract | Owns | Does not own |
| --- | --- | --- |
| Run Authority | Capability grants, subject attempts, accepted claims/decisions, coordinator fences, CAS/idempotency, quarantine. | Renewable custody leases, WBC evidence history, repair scheduling, status/liveness. |
| WBC | Versioned boundary declarations, execution-attempt/effect evidence, provenance, receipts, findings, payload/reference policy, WBC conformance. | Dispatch or mutation grants, lease ownership, lifecycle mutation, repair. |
| Custody | Exact action-target and repair-occurrence identity, renewable exclusive lease and custody epoch, transfer/reclaim/release/expiry, recovery and reconciliation. | Run Authority decisions, duplicate attempt/effect ledger, boundary schemas. |
| Projections/observers | Rebuildable operator/status/liveness/custody views and diagnostics. | Positive authorization of dispatch, repair, completion, cancellation, publication, or delivery. |

Every authoritative action validates both the current Run Authority grant/fence
and current Custody lease/epoch. Required WBC evidence is additionally checked
at the declared boundary, but WBC evidence alone never authorizes action. The
full terminology, schema/event disposition, invariants, and code seams are in
`decisions/single-authoritative-runtime-history.md`.

## Unified residual prevention epic

The executable chain now contains nine ordered milestones:

1. M5 reconciles all three Run Authority receipts, proves zero divergence, then
   writes and attests the metadata-only retirement marker for the exact
   `.megaplan/initiatives/runauthority-epic/` initiative.
2. M6 accepts the exact WBC merge commit from the operator, verifies it against
   current completion/support proof, pins the reconciled Run Authority/WBC
   contract set, and generates the maintained zero-exemption boundary matrix.
3. M6A implements the WBC-owned transactional attempt/effect store and API,
   start-before-dispatch and terminal-outcome invariants, indeterminate/
   reconciliation semantics, payload policy enforcement, and durable migrations.
4. M7 defines the custody-owned occurrence/lease/epoch/transfer contract and
   consolidates remaining authoritative writers behind the dual Run Authority
   plus Custody gate and WBC evidence boundary.
5. M8 migrates every WBC producer plus runtime, chain, resident, cloud, repair,
   finalize/publication, cancellation/resume, and compatibility adopter.
6. M8A adds Megaplan-owned DAG feasibility, complexity, deterministic
   validation, launcher bounds, repair-adoption, and executor circuit controls
   without moving those policies into Run Authority.
7. M9 makes status, liveness, repair/auditor, chain/publication, retention/
   migration, and operator surfaces canonical consumers and rebuildable projections of
   the coherent owner-specific source cursor vector and joins productive-versus-
   replayed latency/cost evidence.
8. M10 makes retry, event-driven recovery, replay, migration, and external effects safe,
   exact-signature-bound, and independently verifiable with p95 unblock under
   five minutes plus the six-hour reconciliation backstop.
9. M11 delivers the comprehensive cross-contract acceptance/conformance suite,
   then proves captured replay, stale-fence/epoch and cross-host handoff safety,
   restart/reconciliation, idle and worker/repair canaries, controlled
   installed-runtime deployment, a genuine blocked-run recovery, and
   generated static/runtime boundary coverage plus evidence-gated bypass retirement.

`briefs/m5-post-wbc-custody-convergence.md` is retained as an earlier bounded
follow-up proposal. The nine-milestone chain supersedes it as executable scope;
its useful cloud-custody constraints are absorbed into M6A and M8-M11/M8A.

The authoritative relationship, ownership matrix, F01-F17 prevention mapping,
rollout gates, unknowns, and completion contract are in
`research/unified-authority-efficiency-prevention-20260714.md`.
The WBC revision/call-site/consumer evidence and maintained row-level proof
contract are in `research/wbc-adoption-audit-20260714.md` and
`research/wbc-boundary-adoption-matrix.md`.

## Launch posture

The chain is deliberately unlaunched and fail-closed. Chain entry requires a
generic immutable execution-binding guard and its content-addressed prelaunch
receipt, plus a current content-addressed WBC completion manifest. The guard
must bind local/normalized-remote chain bytes, ordered briefs and anchors,
source/tree and installed/editable/runtime provenance; launch, handoff, resume,
restart and reconciliation stop on drift. The planning assets do not name a
guessed WBC merge revision. M5 does not require already-accepted Run
Authority receipts or the later migration approval: producing genuine Run
Authority completion/retirement evidence is its purpose. The Run Authority
entry checks preserve source lineage and a manifest claim as inputs to
reconcile; they do not assert acceptance. The
serial chain and manual milestone merge gate block M6 until M5 has
three accepted receipts, zero canonical verification divergences, a regenerated
manifest, the canonical `runauthority-epic/.retired` marker, and its
content-addressed retirement attestation. M6 must then obtain the exact merged
WBC commit from the operator and prove the manifest/support/runtime identity
matches it. M6A and every later implementation milestone remain blocked until
M6's ownership handoff and the approval record are accepted. Planning completion grants no authority to start,
resume, execute, merge, deploy, restart, or delete anything.

Every milestone handoff additionally requires a cumulative North Star receipt
proving the immutable launch bundle still matches, predecessor obligations still
hold, matrix rows moved only on machine-derived evidence, and blocking suites
ran in enforce mode. This external chain-control guard must exist before M5; a
later milestone cannot circularly protect the chain that selects it. The
blocking rationale is in
`handoff/wbc-adoption-adversarial-review-20260714.md`.
