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
  conformance. Candidate `cbe69337d6f469fd7ae12f1fd0a51007d93b5d70`
  landed through audited no-ff merge
  `24afce006b9ad20391ac7af10ef67ea0b1774f9f`; that consolidation evidence is a
  launch prerequisite. The old cloud session's four-milestone terminal label is
  not completion proof for the current six-milestone corrective chain.
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
2. M6 validates the exact audited WBC merge against landed ancestry and current
   support/runtime proof, pins the reconciled Run Authority/WBC
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
The delivery-level mapping from every missed behavior through call sites,
milestones, tests, gates, and actual final verification is
`research/end-state-coverage-matrix-20260714.md`.

## Implemented adjacent M8A slice: critique custody

Resident run `subagent-20260715-122715-f5ca5724` implements a fail-closed
Megaplan-local critique custody contract on the reconciled runtime target. Raw
and normalized critique evidence now receives stable finding identity and an
immutable production receipt; gate validates the receipt-to-registry join;
finalize requires plan-mutation clearance plus an exact typed
finding-to-final-task map, revalidates the final DAG after all mutations, and
binds clearance to the exact task graph; execute rejects missing or stale
custody/feasibility evidence. The captured 35-task linear-plan shape is an
adversarial rejection fixture.

This is partial M8A delivery, not milestone completion or runtime activation.
M8A already owned graph feasibility and post-finalize validation but did not
spell out the finding production/normalization/resolution join. M8 and M11 must
still register/prove cross-runtime boundary adoption and bypass retirement;
M6A/M7 provide WBC storage and action custody but do not decide semantic
critique resolution. The root cause, invariants, adjacent loss paths, exact run
provenance, and milestone gap assessment are curated in
`research/critique-custody-contract-20260715.md`.

## Launch posture

The chain is deliberately unlaunched and fail-closed until its revision pin is
landed. Generic chain control now binds the chain bytes, ordered milestone
sequence, briefs, North Star, intended initiative revision, and resolved
source/editable runtime into immutable chain-state metadata before the first
milestone. Load/resume and reconciliation stop before normalization on drift,
and status exposes expected versus active identities. The audited WBC merge
evidence—not the invalid old four-milestone terminal label—is the WBC launch
input. M5 does not require already-accepted Run
Authority receipts or the later migration approval: producing genuine Run
Authority completion/retirement evidence is its purpose. The Run Authority
entry checks preserve source lineage and a manifest claim as inputs to
reconcile; they do not assert acceptance. The
serial chain and manual milestone merge gate block M6 until M5 has
three accepted receipts, zero canonical verification divergences, a regenerated
manifest, the canonical `runauthority-epic/.retired` marker, and its
content-addressed retirement attestation. M6 must then prove the audited WBC
merge is contained by the exact landed/runtime vector and reconcile its
support/runtime evidence honestly. M6A and every later implementation milestone remain blocked until
M6's ownership handoff and the approval record are accepted. Planning completion grants no authority to start,
resume, execute, merge, deploy, restart, or delete anything.

Every milestone handoff additionally requires a cumulative North Star receipt
proving the immutable launch bundle still matches, predecessor obligations still
hold, matrix rows moved only on machine-derived evidence, and blocking suites
ran in enforce mode. The immutable selector guard exists before M5; later
milestones add plan/review and runtime-trace proof without circularly protecting
the chain that selected them. The
blocking rationale is in
`handoff/wbc-adoption-adversarial-review-20260714.md`.
