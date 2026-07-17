# Custody / Cluster Control Plane — Run Authority and WBC Reconciliation

This is the canonical durable epic for completing pipeline-wide adoption of the
Run Authority, WBC, and cross-host custody contracts. It reuses the existing
Custody Control Plane
initiative because that initiative already owns the authority-lineage audit,
migration matrix, canonical run-state/custody foundation, and the original
residual migration design.

## Current audited status

At the authoritative live-state reread at `2026-07-17T14:08:58Z`, the Custody
chain was launched but not complete.
Its raw chain cursor is at milestone index 2 after two completed entries out of
ten, with current plan `m6-exact-contract-and-20260716-1303`. That plan is
`blocked` at iteration 5 and points next to `finalize`; its latest history entry
at `2026-07-17T14:03:57Z` records another rejected finalize request caused by an
invalid JSON schema, while the chain also records `last_state: blocked`. Earlier drift
evidence records canonical repair state `UNKNOWN` and intent
`broken_superfixer` versus legacy/actual `queue_only`/`no_action`. These are
distinct evidence dimensions, not proof that M6 executed, that later code is
wired into the current runtime, or that the chain is complete.

The full current-epoch implementation/adoption audit, including every F01–F17
row, the preceding 15-item crosswalk, checkout/runtime divergence, existing
solutions to reuse, telemetry unknowns, and the three ranked priorities, is in
`research/f01-f17-current-epoch-adoption-audit-20260717.md`.
The durable answer for whether and how each F01-F17 item and ranked priority can
enter this exact ten-milestone run, including prerequisites, first safe action,
acceptance evidence and custody/replay/revision risks, is the **Current-run
implementation crosswalk** in
`research/unified-authority-efficiency-prevention-20260714.md`.

Those raw reports entered repository history at
`44441636f125ad490dd12adba8254462c15ea48f` and
`b363d7d8ad9c02a04f369dd62074206fa1d6cf4d`. Their execution-ready planning
amendment is indexed by
`decisions/f01-f17-upcoming-milestone-amendment-20260717.md`. That decision is
the unique F01–F17/R1–R3 allocation table; the M6A–M11 briefs own execution and
acceptance details. It explicitly distinguishes component presence from runtime
wiring and prevents one recommendation from being lost or implemented twice.

## Protected boundary and amendment status

M5 and M5A are complete, and M6 is current. Their milestone labels, branches,
configuration, dependencies, prep direction, notes, and brief bytes are
immutable. The canonical chain imports those live definitions unchanged; the
M5, M5A, and M6 brief SHA-256 values are respectively `2e8f3f96…`,
`9a337ca4…`, and `3fea24d7…`. The finalized M6 plan artifacts remain solely in
live run state and are not modified here.

Only M6A, M7, M8, M8A, M9, M10, and M11 are amended. Stable labels and serial
ordering remain unchanged. Each pending brief now names its recommendation
ownership, predecessor evidence, first safe action, output bundle, runtime
acceptance, and version/custody/replay stop conditions. The amendment does not
rebind, resume, restart, finalize, deploy, promote, delete, or otherwise mutate
the live chain; any future adoption by that run must occur through its supported
between-milestone binding workflow after M6 becomes accepted.

## What already exists

- Custody M1-M4 delivered the canonical run-state resolver, coherent evidence
  model, custody integrations, repair verification, and auditor coverage. Their
  briefs remain historical lineage and are not pending chain milestones.
- `runauthority-epic` landed grants, accepted attempts/decisions, fences,
  quarantine, and operational views. Its original milestone completion receipts
  were rejected with three canonical divergences; Custody M5 subsequently
  reconciled and accepted them. That M5 acceptance does not prove later Custody
  milestones or universal runtime adoption. Nominal `done`, merged PRs, and
  manifest presence are not enough.
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

The canonical chain contains ten stable milestone identities. The residual
design below groups nine post-foundation outcomes because M5A atomic fail-closed
completion was inserted between M5 and M6. The current chain artifact records
M5 and M5A as its two-entry completed prefix, with M5A publication evidence
`local_no_push_reconciliation`; that cursor does not prove M6 or universal
runtime adoption, so neither numbering scheme is completion evidence.

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

## Launch and recovery posture

The earlier unlaunched posture has been superseded by the launched session
described above. The chain is positioned at M6, whose plan is gated but inactive;
chain status and the later repair-drift event remain fail-closed evidence rather
than authority to proceed. This status note does not authorize finalize, relaunch,
resume, replan, merge, deployment, restart, or successor execution. Generic
chain control binds the chain bytes, ordered milestone
sequence, briefs, North Star, intended initiative revision, and resolved
source/editable runtime into immutable chain-state metadata before the first
milestone. Load/resume and reconciliation stop before normalization on drift,
and status exposes expected versus active identities. The audited WBC merge
evidence—not the invalid old four-milestone terminal label—is the WBC launch
input. M5 does not require already-accepted Run
Authority receipts or the later migration approval: producing genuine Run
Authority completion/retirement evidence is its purpose. The Run Authority
entry checks preserve source lineage and a manifest claim as inputs to
reconcile; they do not assert acceptance. The serial predecessor and acceptance
gates required M5 to produce three accepted receipts, zero canonical verification
divergences, a regenerated manifest, the canonical
`runauthority-epic/.retired` marker, and its content-addressed retirement
attestation before the cursor could reach M6. M6 must now prove the audited WBC
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
