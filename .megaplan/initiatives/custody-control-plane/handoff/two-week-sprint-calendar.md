---
type: handoff
date: 2026-07-14
status: planning-only
---

# Two-week sprint calendar for the unified prevention epic

## Assessment and packaging decision

Keep M5, M6, M7, M8, M8A, M9, M10, and M11 and insert M6A for the independently
necessary WBC transactional substrate, yielding nine primary sprints of roughly
two weeks each.
The briefs already bound every milestone to one sprint, give each one a distinct
outcome and anti-scope, and require a content-addressed handoff before the next
acceptance boundary. No inspected evidence supports merging milestones,
dropping controls, or inventing another milestone now.

The boundaries are substantive rather than ceremonial:

- M5 repairs prerequisite Run Authority evidence; M6 freezes contracts and the
  generated zero-exemption inventory without implementing controls.
- M6A turns the WBC candidate's schema-only ledger into a transactional store/
  API with payload policy and migrations; M7 then establishes Custody writers.
- M8 adopts WBC at every producer and those composed contracts across runtimes
  and boundaries.
- M8A remains separate because DAG feasibility, task sizing, deterministic
  validation, launcher bounds, repair adoption, and executor circuits are
  Megaplan-domain policy rather than authority-kernel or recovery policy.
- M9 cuts readers and projections over to one reducer and joins cost/latency
  evidence; M10 can then prove effect-safe retry and event-driven recovery
  against coherent views.
- M11 is the integrated proof, rollout, genuine-block acceptance, rollback, and
  evidence-gated retirement boundary. Folding it into M10 would mix control
  construction with the independent evidence that authorizes rollout/removal.

The chain remains serial at **acceptance and promotion boundaries**. That does
not require serial team execution inside a sprint. After entry evidence is
validated, independent workstreams should run concurrently and converge on one
milestone handoff. Read-only fixture preparation, reviewer scheduling, and
operational-window preparation for a later sprint may start early, but they are
provisional: they cannot implement against an unaccepted contract, promote a
control, satisfy a downstream exit criterion, or bypass the manual merge gate.

## Sprint calendar

### Sprint 1 (weeks 1–2) — M5: trustworthy prerequisite evidence

**Objective:** turn the landed Run Authority implementation from a nominally
complete but rejected evidence set into three accepted receipts, zero canonical
verification divergences, and attested metadata-only retirement.

**Dependencies:** landed three-milestone Run Authority history, readable
canonical plans/chain state, and the constrained duplicate-session retirement
record. Accepted receipts are deliberately the result, not an entry condition.

**Parallel tracks and owners:**

- Run Authority evidence owners reconcile M1, M2, and M3 committed ranges and
  receipts in parallel.
- Suite/evidence owners resolve structural collection/import failures and bind
  the exact M3 reducer run to its source/runtime identity.
- Retirement-custody owners resolve the canonical tombstone and draft the
  attestation, but do not write the canonical `.retired` marker before proof.
- The independent reviewer builds the admission index and verifies lifecycle
  generation rather than accepting copied JSON or status prose.

**Acceptance evidence:** three fresh `accepted: true` receipts; clean pinned
`chain verify` with `verified_count: 3` and `divergence_count: 0`; lifecycle-
generated proof map/manifest; canonical `.retired` marker written only after
those gates; content-addressed retirement attestation; empty unresolved list.

**Exit:** manual review/merge accepts the complete M5 handoff. Any stale hash,
missing output, structural failure, rejected receipt, or divergence keeps M6
closed.

### Sprint 2 (weeks 3–4) — M6: exact contract, corpus, and zero-exemption map

**Objective:** validate M5 and current WBC evidence, freeze exact ownership and
version identities, and make every residual writer, reader, recovery, effect,
projection, compatibility path, finding, baseline, and rollout owner explicit.

**Dependencies:** accepted M5 handoff, current content-addressed WBC completion
and support evidence, and the top-level North Star.

**Parallel tracks and owners:**

- Contract/evidence owners validate both prerequisite manifests and version
  vectors.
- Surface owners inventory Python, resident, cloud, wrapper, provider, native,
  and compatibility writers/readers in parallel against one schema.
- Replay owners capture immutable Transaction Spine and Strategy Roadmap
  fixtures and map F01–F17 to controls and proof.
- Telemetry/rollout owners freeze work classes, unknown baselines, cohorts,
  kill switches, rollback owners, deletion authority, and the approval record.

**Acceptance evidence:** exact contract/version bundle and proof index; every
matrix row uniquely owned and classified; zero unexplained inventory buckets;
stable captured-corpus hashes; controlled-writer/reader registries; honest
unknowns for projection I/O, compaction, and productive-versus-replayed work;
accepted approval record; empty blocker list.

**Exit:** the manually reviewed M6 handoff is immutable and complete. Missing
ownership, stale prerequisite proof, mutating inspection, or non-replayable
input blocks all implementation.

### Sprint 3 (weeks 5–6) — M6A: WBC transactional ledger foundation

**Objective:** implement the WBC-owned durable store/query API, transactional or
outbox semantics, start-before-dispatch and exactly-one-terminal invariants,
explicit indeterminate/reconciliation behavior, enforced privacy/retention/
encryption, and deterministic crash-resumable migrations.

**Dependencies:** accepted M6 exact landed WBC/runtime vector, generated
boundary inventory, unchanged ownership decision, and accepted approval record.

**Parallel tracks and owners:** WBC storage/API owners implement ordering and
queries; lifecycle/outbox owners prove atomic/reconciled joins; data-policy
owners implement storage-level privacy/retention/encryption; migration owners
build mixed-version backfill/resume; test owners inject persistence faults and
capture runtime traces.

**Acceptance evidence:** process-safe store/API; durable start and terminal
queries; transaction/outbox reconciliation; stored-byte policy proof; migration
checksums and crash-resume; failure/replay traces; zero swallowed required
writes; no second ledger owner.

**Exit:** M6A publishes its versioned API/migrations and substrate proof. Any
silent append loss, optimistic query, fabricated backfill, data-policy failure,
or unresolved final-revision/runtime mismatch keeps M7 closed.

### Sprint 4 (weeks 7–8) — M7: controlled writers and immutable evidence

**Objective:** put every residual authority-increasing write behind the landed
Run Authority/WBC identities, make attempts and repair receipts immutable and
adoptable, and establish append-safe/atomic-rebuild projection writing.

**Dependencies:** accepted M6 proof/ownership bundle, M6A substrate, and approval record.

**Parallel tracks and owners:**

- TransitionWriter/custody owners implement fenced CAS/outbox,
  idempotency, terminal joins, dead-lettering, and reconciliation.
- WBC/Run Authority adapter owners bind immutable attempts, decisions, effects,
  exact repair signatures, and quarantine without creating another ledger.
- Projection owners implement cursor-checked append and atomic rebuild while
  preserving the previous complete view.
- Conformance owners run duplicate, stale-fence, partial-persistence, old-reader
  compatibility, and 10,000-heartbeat fault/stress fixtures.

**Acceptance evidence:** zero unregistered authority-increasing writers; exactly
one accepted actor/effect under concurrency; byte-stable prior attempts; T7
cannot bind to T12; every custody path is joinable and terminal; deterministic
rebuild; monotonic stress and idle pinned-runtime canary proof; compatibility
expiry map and rollback evidence that never restores raw write authority.

**Exit:** M7 publishes the controlled-writer/adaptor registry, immutable receipt
contract, projection boundary, reconciliation runbook, and no-new-owner proof.

### Sprint 5 (weeks 9–10) — M8: universal WBC producer and runtime adoption

**Objective:** move every production WBC producer and every supported phase,
chain, resident, cloud, repair/auditor, finalize/publication, cancellation/
resume, child-lineage, provider, and compatibility adopter onto M6A/M7. WBC
retains ownership; manifest-proven or fixture-only producers are not exempt.

**Dependencies:** accepted M6 boundary inventory, M6A store/API, M7 handoff,
and exact WBC revision/support manifest.

**Parallel tracks and owners:**

- Workflow/chain owners migrate admission/common dispatch, all phase, execute,
  tiebreaker, review/reducer, fallback, finalize, resume/cancel/override,
  publication, and delivery seams.
- Resident/cloud/AgentBox owners migrate managed-child, parent aggregation,
  provider, wrapper, and runtime-package seams.
- Custody owners prove mutual exclusion between current worker and repair and
  enforce parent/root delivery authority.
- Compatibility/conformance owners prove durable start before dispatch,
  exactly-one terminal/indeterminate, exact-version lookup, post-write reread,
  read-only history, generated call-site/runtime-trace equality, and zero bypass.

**Acceptance evidence:** combined support manifest and independent generated
inventory with no unexplained producer/adopter;
fail-closed missing/stale identity tests before user code/effects; joined causal
start/terminal/retry/suspend/effect traces; parent-owned delivery crash/replay
proof; static/runtime zero-bypass inventory; compatibility expiry map.

**Exit:** exact-version producer/adopter manifest, decision joins, child/root
evidence, runtime trace digests and reader registry are accepted. No schema-
only, declared-only, unknown, fixture/manual-only, warn-only, best-effort, or
implicit-latest path proceeds to M8A.

### Sprint 6 (weeks 11–12) — M8A: feasible plans and bounded execution

**Objective:** prevent avoidable orchestration work without changing authority
semantics: enforce explainable feasible DAGs/tasks, deterministic non-model
validation, bounded startup/provider/compaction/rework, verified repair
adoption, and exact-identity executor circuits/telemetry.

**Dependencies:** accepted M8 exact-version adopter handoff, M7 immutable
receipt contract, and M6 captured corpus.

**Parallel tracks and owners:**

- Planner/compiler owners implement dependency reasons, routing groups,
  critical-path/parallelism/turn feasibility, complexity splitting, and rework
  wave compilation.
- Validation owners compile deterministic checks into content-addressed harness
  jobs that make zero model calls.
- Launcher/executor owners bound refs, source/runtime provenance, model/import
  resolution, timeouts/failover, compaction, rework, and normalized circuits.
- Repair-adoption/telemetry owners implement verify-only receipt adoption and
  emit fully identified productive, proof, queue, retry, compaction, repair,
  validation, and replay events.

**Acceptance evidence:** content-hash-stable replay of both captured plans;
safe waves without semantic widening; complexity-7/8/9 admission outcomes;
zero-model deterministic validation; bounded invalid-ref/provider/import/
compaction/rework fixtures; circuit before a third equivalent blind retry;
valid receipt adoption and mismatch quarantine; totals reconciled to work class
or explicit unavailable reason.

**Exit:** report-only replay is reviewed, new-plan and executor canaries pass,
and all decisions/counters carry exact attempt identity. Existing plans remain
unchanged.

### Sprint 7 (weeks 13–14) — M9: one reducer, rebuildable views, honest telemetry

**Objective:** cut every control-relevant reader to the exact reducer cursor/hash,
prove projections disposable and observers pure, and expose joined productive-
versus-replayed cost/latency plus deterministic auditor reasons.

**Dependencies:** accepted M8A evidence plus M8 adopter/reader registry and
exact-version traces.

**Parallel tracks and owners:**

- Reducer/projection owners build deterministic plan, chain, repair, resident,
  cloud, liveness, and operator views.
- Reader owners migrate CLI/status/watchdog/auditor/resident/cloud consumers and
  keep historical adapters visibly non-authoritative.
- Telemetry owners join task/batch/attempt/repair time, tokens, cost, outcomes,
  and unknown denominators without calling legitimate implementation waste.
- Auditor/canary owners implement exact-evidence reasons, observer-purity and
  drift fixtures, and the idle projection canary.

**Acceptance evidence:** delete/rebuild digest parity; 100% cursor/hash
agreement; explicit unknown/stale dimensions with zero authority action;
observer-purity proof; captured review/rework consistency; no cross-session
join; reconciled work ledger; each reason fires exactly once with exact IDs;
idle canary with zero false stalls.

**Exit:** accepted projection schemas/digests, reader registry, ledger,
deterministic reasons, compatibility expiry, and shadow/canary comparison.

### Sprint 8 (weeks 15–16) — M10: effect-safe retry and event-driven recovery

**Objective:** make retries, repair, replay, publication, delivery, provider
effects, and recovery safe under crashes and ambiguity, with exact-signature
event-driven recovery and independent closure.

**Dependencies:** accepted M9 views, pure-observer proof, and joined evidence.

**Parallel tracks and owners:**

- Recovery-custody owners implement deduplicated block/exit triggers, exact live
  signature/fence validation, leases, terminalization, and recurrence lineage.
- Effect owners implement intent-before-effect, provider/target reconciliation,
  authoritative reread, and bounded retry/fallback.
- Delivery/publication owners prove parent-owned at-most-once effects and retain
  visible unknown outcomes.
- Independent verification/canary owners run crash matrices, repair/worker
  canaries, p95 measurement, missed-event backstop, kill-switch/rollback proof,
  and prepare the genuine blocked-run candidate.

**Acceptance evidence:** exhaustive fault matrix with no duplicate effect or
false closure; one current worker-or-repair grant; all custody records terminal
or visibly pending; no T7/T12 cross-bind; p95 eligible-event to accepted repair
or typed escalation under five minutes; deliberate missed event recovered by
the six-hour backstop; independent resumed-progress proof; authorized genuine-
block candidate.

**Exit:** accepted effect/reconciliation registry, SLO and backstop receipts,
terminal-custody and verifier evidence, canary/kill-switch/rollback package, and
evidence-backed retirement candidates. M10 authorizes no deletion itself.

### Sprint 9 (weeks 17–18) — M11: integrated proof, rollout, and retirement

**Objective:** prove the whole exact-version control plane in installed runtimes,
exercise mixed versions and rollback, run the staged canaries and one genuine
blocked-run recovery, retire only proven bypasses, and generate—not hand-author—
completion evidence.

**Dependencies:** accepted M10 bundle; unchanged chain, North Star, and briefs;
current Run Authority/WBC proof; clean pinned runtime identity; separately
approved promotion/deployment/deletion record.

**Parallel tracks and owners:**

- Conformance owners run captured/adversarial replay, projection rebuild,
  mixed-version, no-bypass, and forced-rollback suites.
- Runtime/rollout owners prove source/install/wrapper/config/contract/process
  provenance through idle, planner/executor, repair/worker, and controlled-
  deployment gates.
- Independent recovery owners execute and verify one genuine eligible blocked
  run with 5-minute, 1-hour, and 6-hour checkpoints.
- Retirement/evidence owners remove only approved zero-caller bypasses, preserve
  required read-only adapters, record deletion receipts, and generate the proof
  map/completion manifest through the chain lifecycle.

**Acceptance evidence:** every matrix row canonical or retired; full replay and
mixed-version parity; canary and rollback receipts; exact installed/runtime
provenance; genuine-block recovery with no duplicate/replayed effect and
independent verification; productive/replayed ledger coverage with explicit
unknowns; zero static/runtime legacy authority bypass; approved deletion and
compatibility-expiry receipts; valid chain-generated manifest.

**Exit:** manual final acceptance of the complete content-addressed evidence
set. Any provenance mismatch, live legacy caller, replay/canary divergence,
genuine-block failure, rollback dependency on a legacy writer, or missing hash
keeps the epic open.

## Range, capacity, and uncertainty

The nominal plan is **nine two-week sprints, or 18 staffed working weeks**.
For commitment and staffing, reserve **nine to eleven sprints (18–22 active
working weeks)** without reducing scope. A reasonable elapsed-calendar planning
range is **20–24 weeks**, because manual review/merge, prerequisite evidence,
operational approvals, canary windows, and a genuine eligible blocked-run may
not align exactly with sprint boundaries. External prerequisite or approval
delay can extend elapsed time beyond that range without adding engineering
scope.

The two reserve sprints are contingency capacity, not optional scope and not
new technical milestones. If a gate fails, the owning milestone continues into
the next two-week box; downstream acceptance does not borrow incomplete proof.
The main uncertainties are:

- M5 forensic receipt reconstruction and structural-suite repair;
- current WBC proof/version drift and inventory size discovered in M6;
- M6A transactional backend, data-policy, migration and crash-reconciliation
  behavior across supported runtimes;
- hidden writer/adopter/reader surfaces and adversarial fault findings in
  M7–M10;
- calibration of M8A feasibility/circuit rules without false semantic changes;
- as-yet unmeasured projection I/O, compaction, and productive-versus-replayed
  baselines;
- sufficient event samples for an honest recovery p95 and availability of the
  M11 controlled-deployment, rollback, and genuine-block windows;
- compatibility expiry and explicit deletion/promotion approvals.

Scope remains the full unified prevention epic: Run Authority correctness;
custody and repair identity; immutable evidence and reducer/projection work;
planner/DAG feasibility; executor retry, timeout, compaction, rework, and
circuit controls; efficiency/cost telemetry; event-driven recovery and the
six-hour backstop; content-addressed proof gates; staged rollout; genuine-block
acceptance; and evidence-gated legacy retirement.

This calendar is planning guidance only. It launches no chain, changes no
runtime, grants no deployment/deletion authority, and does not replace any
milestone's own acceptance contract.
