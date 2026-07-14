---
type: decision
slug: single-authoritative-runtime-history
status: proposed-human-gate
approval_record: pending
wbc_merge_commit: 24afce006b9ad20391ac7af10ef67ea0b1774f9f
wbc_completion_manifest_digest: not-claimed-old-s1-s4-is-not-current-c1-c6
wbc_substrate_revision: pending-m6a-owner-handoff
chain_execution_binding_receipt: required-in-chain-state-at-launch
date: 2026-07-13
---

# Composed Run Authority, WBC, and Custody contracts

## Decision

Complete pipeline-wide adoption of three composed contracts with no overlapping
positive authority. Run Authority owns grants, subject attempts, accepted claims
and decisions, coordinator fences, CAS/idempotency rules, and quarantine. WBC
owns exact-version boundary declarations, the durable transactional execution-
attempt and external-effect evidence ledger/API, payload/reference policy, semantic findings,
and WBC supported-runtime conformance. Custody owns exact action-target and
repair-occurrence identity, renewable exclusive leases, custody epochs,
ownership transfer, release/expiry, recovery scheduling, and reconciliation.

These contracts are joined by exact identity and causal lineage. They are not a
license to create a new all-purpose ledger, route engine, status authority,
transition writer, repair queue, or lifecycle.

An authoritative action is valid only when the action boundary validates both
the current Run Authority grant plus coordinator fence and the current Custody
lease plus custody epoch. WBC evidence is required where the boundary contract
declares it, but WBC evidence never supplies either authorization. A reducer or
projection may deny, quarantine, or explain; a projection alone never acts as a
bearer grant or lease.

## Evidence basis

- The inspected project/runtime revision is
  `612b139971e1a65d2a40f9e387a5e8ff3e2ab960`; the working tree is concurrently
  dirty, so this decision relies on named clean source paths and read-only refs,
  not a claim that the whole checkout is a deployable revision.
- `arnold_pipelines/run_authority/contracts.py` implements
  `CoordinatorFence`, `CapabilityGrant`, `SubjectAttempt`, `Claim`, `Decision`,
  `QuarantineRecord`, idempotency, and CAS contracts. It implements no renewable
  wall-clock custody lease.
- `arnold_pipelines/run_authority/reducer.py` is a pure deterministic reducer.
  Its `RunAuthorityView` carries a journal cursor, evidence-set digest, and view
  hash; those fields prove projection identity, not current custody.
- `.megaplan/initiatives/runauthority-epic/decisions/runauthority-architecture-decision.md`
  keeps repair/custody policy in the Megaplan domain. Its older phrase
  "coordinator leases and fencing tokens" is resolved here: Run Authority keeps
  the monotonic coordinator fence; renewable exclusive ownership belongs to
  Custody because the implementation has only the fence and the verified split
  assigns leases/transfer/recovery to Custody.
- The WBC North Star and
  `decisions/2026-07-11-kernel-execution-attempt-ledger.md` define
  `BoundaryContract`, `BoundaryReceipt`/`BoundaryEvidence`, `SemanticFinding`,
  and `ExecutionAttemptLedger`. The audited integration line adds
  `arnold/workflow/execution_attempt_ledger.py` with `GrantRef` references and
  external-effect intent/outcome events. Read-only remote-tracking evidence at
  `0211937ea0`, `599cd2faf9`, and `cbe69337d6` shows foundation, Megaplan/cloud
  consumption, and conformance integration seams; those refs are pre-merge
  observations, not the launch version. Audit of the completed candidate at
  `cbe69337d6f469fd7ae12f1fd0a51007d93b5d70` found
  `ExecutionAttemptLedger` explicitly schema-only and no production store/API;
  its 35-contract matrix has 5 auto-matched, 8 manual-emission, 13 declared-
  only, and 9 unknown rows despite a broader support manifest. Audited no-ff
  consolidation merge `24afce006b9ad20391ac7af10ef67ea0b1774f9f` landed the
  candidate on canonical main. These observations require M6 inventory, M6A
  substrate, and M8-M11 adoption proof; they do not change WBC ownership. The
  exact landed/runtime vector is verified separately from the WBC merge commit.
- `arnold_pipelines/megaplan/cloud/repair_requests.py` currently provides
  blocker-scoped atomic claims and managed-run binding, while
  `cloud/repair_contract.py` builds custody/dispatch projections. The residual
  gap is a durable cross-host renewable lease/epoch/transfer contract and its
  enforcement at every authoritative effect boundary.

## Settled terminology

| Term | Exact meaning | Never means |
| --- | --- | --- |
| Run Authority subject attempt | The identity authorized by a capability grant to make a claim under one coordinator fence. | A WBC event stream or a repair process lease. |
| WBC execution attempt | The ordered durable event/effect history for work actually attempted by a supported runtime, joined to Run Authority IDs. | Permission to start, retry, complete, cancel, repair, publish, or deliver. |
| Custody target | The exact run/revision, subject attempt, operation class, and environment scope over which one actor may perform authoritative actions. | A status row, queue item, broad session name, or capability grant. |
| Repair occurrence | The exact failure/recovery subject identified by environment, session, chain, plan revision, phase/task, subject attempt, normalized failure kind, blocker/phase-result digest, and current Run Authority fence. | A basename, mutable latest pointer, generic problem label, or status row. |
| Custody lease | Renewable exclusive ownership of one custody target (and exact repair occurrence for recovery) by one actor/host/process-birth identity, with a monotonic custody epoch and expiry. | A Run Authority grant, a PID/tmux observation, a queue claim, or a projection. |
| Coordinator fence | Run Authority's monotonic fence for the coordinating attempt/revision. | A renewable lease or proof that an owner is alive. |
| Custody epoch | Custody's monotonic fencing token for lease acquisition/transfer/reclaim. | A replacement for the Run Authority coordinator fence. |
| Receipt/evidence/finding | WBC-owned fact or mismatch record tied to exact contract and attempt identity. | An authorization decision or lifecycle mutation. |
| Projection/view | Rebuildable derived state at a declared source cursor/hash. | Positive dispatch, repair, completion, cancellation, publication, or delivery authority. |

## Capability, event, and schema ownership matrix

| Capability / schema / event | Decision | Owner and consumer rule |
| --- | --- | --- |
| `CoordinatorFence`, `CapabilityGrant`, `SubjectAttempt`, `Claim`, accepted/rejected/quarantined/superseded `Decision`, CAS/idempotency | Consume Run Authority | Custody and all action writers validate the exact current records; no duplicate custody schema is created. |
| `BoundaryContract`, template/profile/version, `BoundaryReceipt`, `BoundaryEvidence`, `SemanticFinding`, durable payload/reference and retention/redaction policy | Consume WBC | Custody consumes exact-version evidence and findings. Receipts and findings can block or trigger evaluation, never authorize action. |
| `ExecutionAttemptLedger`, transactional store/API, start/complete/fail/retry/suspend/resume/cancel, external-effect intent/outcome, persistence-failed/reconciliation evidence | Consume and operationalize WBC in M6A/M8 | WBC remains owner. Custody and Run Authority adapters reference the exact stream; Custody must not create a second attempt/effect ledger. Schema/support declarations without production writes and reads are incomplete. |
| `CustodyTargetKey` and repair-specialized `RepairOccurrenceKey` | Own custody-specific contract | One canonical digest over exact action scope; repair adds the exact failure tuple above. Immutable across retries and never rebound to another attempt. |
| `CustodyLease` and `CustodyLeaseEvent` (`acquired`, `renewed`, `transferred`, `released`, `expired`, `fenced`, `conflict_detected`, `reconciled`) | Own custody-specific contract | Stored durably with lease ID, target/occurrence key, owner/host/process-birth identity, Run Authority grant/fence refs, monotonic custody epoch, expiry, causal predecessor, and idempotency key. |
| Repair request/claim/managed-run link | Merge into custody occurrence/lease lifecycle | Existing queue claims remain admission mechanics. They must bind one occurrence and culminate in a lease or a typed non-owner result; they are not separate authority. |
| `TransitionWriter` lifecycle CAS/outbox | Consume existing mutation seam | It applies already-authorized state changes transactionally. It does not decide grants, mint leases, or infer completion. |
| Recovery trigger, lease acquisition/transfer/reclaim, retry/reconcile, independent-verifier scheduling | Own custody-specific behavior | Triggered by durable WBC/Run Authority facts, deduplicated by occurrence, and fail-closed on stale grant/fence/epoch. |
| Run-state, status, chain, cloud, watchdog, repair, resident, delivery and auditor views | Remove/merge duplicate authority; keep projections | Rebuild from source records at a coherent cursor. They may block and diagnose; every positive action rereads source authority and custody. |
| PID/tmux/heartbeat, mutable JSON, marker, log, provider status, receipt-only completion | Remove as action authority | Preserve only as observations/evidence inputs. Missing or contradictory inputs yield unknown/incoherent and no action. |
| Domain scheduling, DAG readiness, model routing, task sizing and budgets | Keep domain-owned | Megaplan planner/executor policy; neither Run Authority, WBC, nor Custody absorbs it. |

## Required action envelope and invariant

Every dispatch, repair mutation, terminal completion, cancellation, publication,
or delivery effect carries and validates this join immediately before the effect:

```text
run_id + run_revision + subject_id + subject_attempt_id
Run Authority grant_id + coordinator_attempt_id + coordinator_fence
custody_target_id + optional repair_occurrence_id + custody_lease_id + custody_epoch
WBC contract/profile/version + ledger attempt/event refs (when declared)
idempotency_key + causal predecessors + expected source cursor/CAS
```

Validation is conjunctive. Missing/stale/mismatched Run Authority records reject
the action. Missing/stale/mismatched custody records reject the action. Missing
required WBC evidence makes the boundary incomplete or indeterminate but cannot
be converted into a grant. A cached projection never fills a missing field.

## Ownership split for the prevention extension

- Run Authority owns grants, coordinator/subject attempts, acceptance,
  rejection/quarantine/supersession, fences, dependency acceptance, and the
  pure reducer. The reducer is authoritative interpretation of its source
  records, but its serialized projection is not a bearer authorization.
- TransitionWriter applies lifecycle CAS/outbox updates. Repair custody owns
  occurrence-bound request/claim/lease/dispatch/terminalization/reopen,
  ownership transfer/reclaim, reconciliation, and independent verification
  scheduling. Neither can accept task claims or self-verify.
- WBC owns exact-version boundary declarations and immutable execution-attempt/
  effect evidence, receipts, payload/reference policy, findings, and supported-
  runtime conformance. It grants no authority and mutates no lifecycle.
- Maintenance owns coherent observation, the six-hour reconciliation backstop,
  daily read-only efficiency analysis, and deterministic finding/ticket-proposal
  policy. It is not a repair actor or active-plan optimizer.
- Megaplan planner/compiler owns dependency semantics, routing groups, critical-
  path/parallelism/turn feasibility, task complexity/splitting, and compiling
  deterministic validation jobs.
- The executor/launcher owns source/runtime preflight, model/import isolation,
  verify-only repair adoption, and bounded timeout/failover/compaction/rework/
  retry circuits.
- Observability owns append-efficient rebuildable projections, the joined work/
  latency ledger, pure operator views, and exact-evidence auditor reasons. It
  cannot refresh liveness, resolve authority independently, or positively
  authorize an action.

M8A implements the adjacent planner/compiler/executor policy because putting it
in Run Authority would violate the narrow-kernel decision and putting it into
M8 or M10 would make those custody milestones oversized.

## Immutable chain execution binding

Generic chain control now writes an immutable
`arnold.megaplan.chain_execution_binding.v1` identity into chain state before
the first milestone. It binds chain bytes, ordered milestone labels/indices and
brief hashes, North Star hash, intended initiative revision, and resolved
source/editable runtime identity. The remote launch must execute this same guard
after upload; a path or marker alone is not authority.

Launch-bound fields are immutable. Later observations are recorded separately.
Load/resume and reconciliation recompute observed identity before compatibility
normalization and fail with typed `chain_execution_binding_drift` on mismatch;
status exposes expected and active bundles. Rebinding requires an explicit
operator-approved, content-addressed migration event.

Before milestone N closes or N+1 initializes, the guard also requires a
cumulative North Star receipt proving the expected brief/anchor drove the plan
and review, predecessor obligations remain satisfied, matrix rows advanced only
on machine-derived evidence, prior conformance did not regress, and blocking
suites ran in enforce mode. The prelaunch selector binding exists outside the
milestone sequence because M5 cannot protect the chain selector that decides
whether M6A-M11 run.

## Locked invariants

- Persist a WBC attempt reservation/start before every dispatch and exactly one
  durable completed/failed/cancelled/indeterminate outcome before terminal
  success or advancement, through the WBC-owned transactional API.
- Bind every decision/effect to exact workflow/contract/code/config version,
  run/attempt, actor, capability grant, coordinator fence, idempotency key, and
  causal parents; never reinterpret an old record through an implicit latest.
- Only registered controlled writers may increase authority. Projection and
  compatibility writers remain downstream and cannot grant authority.
- Every authoritative action requires both a current Run Authority grant/fence
  and a current Custody lease/epoch. WBC evidence, receipts, findings, process
  observations, and projections are never substitutes for either half.
- Lease transfer/reclaim is append-only and increments the custody epoch.
  Cross-host handoff never overlaps accepted epochs; the old host is fenced
  before the new owner can act.
- Coherent evidence is versioned before and after collection. Tearing,
  staleness, missing ownership, or version mismatch returns `UNKNOWN` or
  `INCOHERENT`, emits drift, and performs no action.
- Callers reread authoritative state after transition or effect before
  advancing. Post-mutation retries require current authority and reconciliation.
- A repair actor cannot verify itself. Closure requires an independent negative
  control plus resumed authoritative progress.
- Projections are disposable and reproducible. Rollback never restores a legacy
  writer, erases causal evidence, or converts a projection into authority.
- Legacy bypasses are shadowed, fail closed, then removed only after parity,
  cross-version/replay, zero-reader/writer, and rollback evidence.
- Eligible blocked occurrences reach accepted repair or typed escalation with
  measured p95 under five minutes; the scan and six-hour auditor reconcile
  missed events and never become primary dispatch authority.
- Completion additionally requires captured-incident replay, idle projection
  and planner/executor and repair/worker canaries, installed-runtime provenance,
  one genuine blocked-run recovery, joined productive/replayed evidence, and
  deletion/retirement receipts, generated call-site set equality, and captured
  runtime traces for every WBC boundary row. Local green tests, schema-only
  suites, nominal support manifests, fixture-only emitters, or manual assertions
  do not satisfy this decision.

## Concrete implementation seams

- Extend the generic custody contract at the existing repair-request/managed-run
  boundary in `arnold_pipelines/megaplan/cloud/repair_requests.py`; do not add it
  to `arnold_pipelines/run_authority/contracts.py` or WBC schemas.
- Make `arnold_pipelines/megaplan/cloud/repair_contract.py` consume the lease
  journal and expose a projection; remove any path where its projection itself
  authorizes dispatch.
- Gate action writers in execute/chain/cloud/resident publication and delivery
  adapters through a shared validator that rereads Run Authority and Custody
  source records and then checks required WBC boundary evidence.
- Keep `arnold_pipelines/run_authority/reducer.py` pure. Keep WBC ledger and
  conformance producers in `arnold.workflow`/their Megaplan adapters. Connect
  them with exact IDs, not imports that collapse ownership.
- M6A implements the WBC-owned persistent store/query API, transaction/outbox,
  payload-policy enforcement and versioned migrations. M8 routes every
  discovered producer through it; M9 routes every consumer through exact-version
  queries. Neither milestone transfers WBC ownership to Custody.
- Convert status/watchdog/auditor/current-target readers to pure projections;
  they emit typed drift/unknown and never acquire, renew, transfer, or act.

## Final cross-contract acceptance suite

M11 owns one comprehensive acceptance/conformance suite, interpreted from the
user's phrase "port excipation suit." Repository search found established
"acceptance suite" and "conformance suite" terminology but no distinct
"excipation" or "port exception" contract. The suite must include:

1. Matrix tests showing a current Run Authority grant/fence plus current
   Custody lease/epoch is necessary and sufficient at the authorization layer;
   required WBC evidence is then checked as boundary completion evidence.
2. Negative tests proving WBC contracts, ledger events, receipts, findings, and
   every projection alone cannot dispatch, repair, complete, cancel, publish,
   or deliver.
3. Stale run revision, coordinator fence, custody epoch, expired lease, wrong
   occurrence, wrong host/process-birth, and torn/cross-cursor evidence tests.
4. Cross-host acquire/renew/transfer/reclaim races proving one accepted owner,
   no overlap, and stale-owner fencing before effects.
5. Duplicate, late, lost, and out-of-order trigger/retry tests proving exact
   idempotency and no duplicate action/effect.
6. T7/T12 and same-basename negative fixtures proving exact repair occurrence
   identity cannot cross-bind.
7. Persistence fault, process crash, restart, replay, projection deletion/
   rebuild, missed event, six-hour reconciliation, and independent-verification
   tests with no false success or orphan custody.
8. Installed-runtime and mixed-version tests against the audited landed WBC
   merge commit and generated support manifest, followed by static/runtime
   zero-bypass scans and rollback proof.
9. Generated semantic call-site set equality plus captured success/failure/
   cancel/retry runtime traces for every WBC boundary row; schema or support-
   manifest declarations alone fail.
10. Transactional store, payload privacy/retention/encryption, crash-resumable
    migration/backfill, failure injection, replay and cross-contract tests.

## Approval record required before M6A implementation

The frontmatter approval field remains pending until a human-approved immutable
record pins all of the following:

- M5's three accepted Run Authority receipts, zero-divergence canonical
  verification, regenerated completion-manifest digest, landed revisions,
  proof map, canonical `.megaplan/initiatives/runauthority-epic/.retired`
  marker, and content-addressed retirement attestation;
- validated WBC completion-manifest digest, chain hash, landed revision, and
  proof/support manifests;
- immutable chain execution-binding implementation/receipt and cumulative
  North Star handoff schema, with launch/resume/reconcile drift tests;
- M6's residual surface and controlled-writer inventories with zero unexplained
  or overlapping owner, including the generated WBC boundary inventory and its
  audited schema-only/declared-only/unknown gaps;
- storage, retention, redaction, access, identity/fence, mixed-version, and
  legacy-read policies inherited from prerequisite contracts;
- repair/effect allowlists, canary cohorts, kill switch, promotion/deletion
  authority, rollback owner, and independent verifier;
- confirmation that production enforcement, mutating repair, provider/Git
  effects, deployment, and destructive deletion begin disabled;
- any remaining PC/program-counter/parity-control-plane scope resolution.

M5 may start while this field is pending because it is evidence reconciliation,
not migration implementation. M6 may perform observe-only contract/ownership
inventory and must leave M6A blocked until this record is accepted. Absent that
record, M6A, M7-M11, and M8A fail closed. Planning validation, a green test, or a
milestone/chain status is not approval.
