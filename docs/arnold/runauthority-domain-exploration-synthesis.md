# RunAuthorityView Domain Exploration Synthesis

Date: 2026-07-10

This document consolidates the 28 DeepSeek Pro domain explorations launched for the Arnold `RunAuthorityView` / Megaplan `PlanView` root-fix plan.

Raw agent reports were produced under:

- `/tmp/runauthority-domain-briefs`
- `/tmp/runauthority-domain-results`

The fan completed successfully:

- model: `deepseek:deepseek-v4-pro`
- domains: 28
- succeeded: 28
- failed: 0
- summed agent time: 4645.1 seconds
- wall time: 728.1 seconds

The companion architecture plan is:

- `docs/arnold/megaplan-canonical-planview-root-fix.md`

## Scope Covered

The swarm was intentionally split by authority boundary, not by directory. The explored domains were:

1. plan state artifacts
2. execute batch dispatch
3. execute merge and reconcile
4. authority and evidence readers
5. DAG frontier scheduler
6. chain, milestone, and epic state
7. publication, Git, and PR state
8. cloud launch, env, and runtime
9. status, liveness, and observability
10. watchdog, repair, and superfixer
11. overrides and human gates
12. store, repository, and compatibility
13. events, journals, and WAL
14. runtime durable operations
15. native pipeline agent runs
16. workflow boundary authority
17. provenance, warrants, and security
18. concurrency, locks, and idempotency
19. model routing and profiles
20. worker result envelopes
21. prompts and output contracts
22. current test coverage
23. migration, rollout, and feature flags
24. operator diagnostics and UX
25. artifact quarantine and recovery
26. parent and child runs
27. VibeComfy incident trace
28. deletion and retirement map

This covers all major surfaces currently known to participate in run authority, recovery, execution, publication, and diagnostics. It is not a proof that every file in Arnold was inspected line-by-line. It is a coverage map of every authority-bearing stage the agents could identify.

## Core Finding

The root problem is broader than a Megaplan execute bug.

Arnold has multiple competing authority systems:

- mutable plan artifacts: `state.json`, `finalize.json`, `execution_batch_*.json`;
- event/journal machinery;
- run-state resolver and classifiers;
- store repository and compatibility wrappers;
- chain state and milestone state;
- cloud markers and watchdog snapshots;
- repair-loop sidecars;
- Git/PR observations;
- active-step and process liveness probes;
- worker result envelopes;
- profile/routing records;
- human override records.

These surfaces are individually reasonable in places, but they are not composed through one deterministic reducer. The recurring smell is the same across domains: a raw observation or worker claim is used as a decision source before it has been scoped, validated, fenced, and projected.

The fix should therefore be a generic Arnold `RunAuthorityView` substrate with a Megaplan `PlanView` binding, not another local patch in `execute`.

## Domain Verdicts

| Domain | Verdict | Main planning consequence |
| --- | --- | --- |
| plan state artifacts | High risk | `state.json`, `finalize.json`, and batches must become projections/evidence, not independent truth. |
| execute batch dispatch | High risk | Dispatch must issue scoped `DispatchGrant`s with revision and prerequisite digest. |
| execute merge and reconcile | Mostly complete, one high-risk edge | Merge guard exists for code mode, but replay/reconcile/creative scopes still need lease enforcement. |
| authority/evidence readers | Strong but composition-risky | Existing evidence readers should feed PlanView; they should not remain parallel authority. |
| DAG frontier scheduler | High risk | Frontier must be computed from PlanView, not raw task statuses. |
| chain/milestone/epic | High risk | Chain advancement needs child-run and publication facets, not ad hoc plan-state reads. |
| publication/Git/PR | High risk | Branch/PR state must be separate from execution state. |
| cloud launch/runtime | Good with high-risk edges | Cloud markers are claims; status snapshot can become an observation source, not authority. |
| status/liveness/observability | Good but high-risk | Status has useful classifiers but does not surface canonical source/evidence consistently. |
| watchdog/repair/superfixer | High risk | Repair must consume PlanView and write typed recovery decisions, not mutate stale artifacts directly. |
| overrides/human gates | High risk | Human authority must be typed, scoped, revision-bound, and visible in the view. |
| store/repository/compat | High risk | Store should expose immutable evidence plus typed events; compat paths need retirement criteria. |
| events/journals/WAL | High risk | Current event streams are not yet an authority-grade control stream. |
| runtime durable ops | Good integration surface | Reuse durable-op semantics for idempotent authority transitions. |
| native pipeline agent runs | Good | Confirms `RunAuthorityView` should be generic, not Megaplan-only. |
| workflow boundary authority | Infra exists, operating gaps remain | Boundary/warrant concepts should bind into authority events. |
| provenance/warrants/security | Good scaffolding | Need to make warrants consumed, not decorative. |
| concurrency/locks/idempotency | High risk | Need coordinator fencing plus dispatch leases; current locks are insufficient. |
| model routing/profiles | High risk | Routing decisions must be revisioned and observable as claims/decisions. |
| worker result envelopes | Strong | Reuse as claim envelope input to validation. |
| prompts/output contracts | High risk | Prompts and schemas must carry/echo lease identity. |
| tests | High risk | Current tests mostly cover isolated readers, not read-decide-mutate cycles. |
| migration/flags | High risk | Roll out in shadow/warn/enforce phases with drift diagnostics. |
| diagnostics UX | Incomplete | Operator views need PlanView facets and source-of-truth explanations. |
| quarantine/recovery | High risk | Poisoned artifacts need quarantine records and repair custody. |
| parent/child runs | Medium risk | Need generic child-run refs and lineage before epic/chain authority is robust. |
| VibeComfy incident trace | Complete trace, scattered surfaces | Incident reproduces all major failure classes. |
| deletion/retirement | High risk | Several duplicate classifiers/readers can retire only after PlanView migration. |

## Failure Classes To Plan Around

### 1. Scope Widening

The same task update can be scoped differently depending on the path:

- regular code-mode merge now limits updates to `batch_task_ids`;
- `no_pending_execution` replay can re-merge historical batches with all task ids;
- `reconcile_latest_execution_batch` can use all finalize tasks as scope;
- creative/doc mode still has all-task merge behavior.

Plan implication: merge must validate a `DispatchGrant`, not a caller-supplied list. Scope must come from immutable dispatch authority.

### 2. Raw Status As Authority

Task status still plays too many roles:

- executor claim;
- scheduler input;
- completion state;
- recovery signal;
- chain milestone input;
- status UI truth.

Plan implication: task records can preserve claims, but completion authority must live on accepted task attempts derived from validated evidence.

### 3. Recovery Over Poisoned Artifacts

Retries can preserve or re-read stale artifacts:

- old execution batches;
- stale `finalize.json`;
- stale active-step metadata;
- repair sidecars;
- chain state from a previous coordinator attempt.

Plan implication: recovery should be a reducer decision over `(plan_revision, attempt_id, coordinator_fence, observation_digest)`. Poisoned inputs should become quarantined claims, not silently re-applied.

### 4. Liveness Without Identity Binding

Several surfaces know something is "running", but not always which run, revision, attempt, or dispatch:

- tmux sessions;
- process probes;
- active-step heartbeats;
- cloud session markers;
- watchdog reports.

Plan implication: runner observations need run identity, coordinator attempt, command/session identity, and heartbeat freshness. `active_step` alone is not enough.

### 5. Publication Conflated With Execution

Branch ancestry, push, PR creation, PR merge, and dirty workspace failures can currently bubble up like plan execution failures.

Plan implication: publication gets its own facet: `publication_state`. Execution can be complete while publication is `invalid_branch_ancestry`, `auth_blocked`, `dirty_workspace`, `push_failed`, or `awaiting_merge`.

### 6. Human And Override Authority Is Underspecified

Overrides exist but do not consistently bind to:

- plan revision;
- decision target;
- source view hash;
- actor;
- expiration or supersession semantics.

Plan implication: human authority should be evented through `human_gate_*` and `override_applied` records with view hash binding.

### 7. Duplicate Classifiers

The swarm found overlapping status/recovery logic in:

- `run_state/classifiers.py`;
- `cloud/cli.py` status classification;
- `execute/_binding/reducer.py`;
- chain status;
- watchdog/repair classifiers;
- semantic health and custody projections.

Plan implication: these should converge on PlanView facets, then be retired or downgraded to adapters.

## Required Architecture

### Generic `RunAuthorityView`

Generic substrate fields:

- `run_id`
- `run_revision`
- `view_schema_version`
- `projection_cursor`
- `view_hash`
- `attempts`
- `coordinator_lease`
- `runner_state`
- `claims`
- `validation_decisions`
- `quarantine_records`
- `human_gates`
- `child_runs`
- `diagnostics`

Generic substrate responsibilities:

- fold typed control-plane events deterministically;
- apply idempotency keys;
- enforce coordinator fencing;
- expose runner/liveness state;
- expose rejected/quarantined claims;
- expose child-run lineage;
- carry diagnostics with evidence refs.

Generic substrate non-responsibilities:

- task DAG semantics;
- Megaplan batch formats;
- GitHub PR policy;
- Comfy/VibeComfy specifics;
- watchdog escalation policy;
- model routing policy.

### Megaplan `PlanView`

Megaplan-specific facets:

- `plan_revision_hash`
- `task_attempts`
- `task_authority`
- `sense_check_authority`
- `dispatch_grants`
- `next_ready_wave`
- `dependency_closure`
- `execution_state`
- `milestone_state`
- `publication_state`
- `recovery_state`
- `routing_state`
- `operator_next_action`

The view should be derived from:

- plan definition/DAG;
- typed control events;
- immutable worker result envelopes;
- evidence readers;
- store/repository observations;
- Git/PR observations;
- process/liveness observations;
- human override events.

## Event Stream Requirements

The plan should introduce a typed control stream distinct from telemetry. Minimum event set:

- `plan_revision_activated`
- `coordinator_lease_acquired`
- `coordinator_lease_lost`
- `dispatch_granted`
- `dispatch_expired`
- `dispatch_revoked`
- `worker_started`
- `heartbeat_observed`
- `worker_exited`
- `result_submitted`
- `evidence_registered`
- `claim_validated`
- `claim_rejected`
- `claim_quarantined`
- `task_attempt_accepted`
- `task_attempt_failed`
- `task_attempt_superseded`
- `human_gate_opened`
- `human_gate_answered`
- `human_gate_resolved`
- `publication_observed`
- `publication_failed`
- `recovery_decided`
- `recovery_completed`

Each event envelope needs:

- event id;
- run id;
- plan revision hash where applicable;
- stream sequence;
- schema version;
- idempotency key;
- actor identity;
- correlation id;
- causation id;
- evidence refs;
- canonical payload hash.

Reducers must fold events only. File reads, Git calls, tmux probes, and wall-clock checks become observation events first.

## Implementation Plan

### Phase 0: Freeze Current Incident Regressions

Goal: prevent recurrence while the broader migration happens.

Tasks:

- Add tests for `no_pending_execution` replay not widening historical batch scope.
- Add tests for `reconcile_latest_execution_batch` using artifact dispatch scope, not all tasks.
- Decide and test creative/doc mode cross-task policy explicitly.
- Add a VibeComfy incident replay fixture that captures the stalled/corrupted state pattern.
- Keep the already-pushed off-batch merge guard and resume frontier guard.

Exit criteria:

- The known incident cannot corrupt task authority through replay, reconcile, or creative/doc merge paths.

### Phase 1: Inventory And Adapters

Goal: make authority readers explicit before replacing them.

Tasks:

- Add a `RunAuthorityInputs` inventory object listing every raw source consumed for one run.
- Add adapter wrappers for `state.json`, `finalize.json`, execution batches, chain state, cloud markers, watchdog report, Git observations, and process observations.
- Mark each adapter output as `claim`, `observation`, `decision`, or `projection`.
- Add diagnostics when two adapters claim contradictory authority.

Exit criteria:

- One command can print all authority inputs for a run with source paths and roles.

### Phase 2: Typed Control Stream

Goal: introduce authority-grade events without changing behavior yet.

Tasks:

- Define event envelope schema and canonical hashing.
- Reuse store/event infrastructure where possible, but keep authority events distinct from telemetry snapshots.
- Emit shadow events from execute dispatch, merge, evidence validation, runner/liveness observation, publication observation, recovery decisions, and human overrides.
- Add replay tests proving deterministic fold and idempotent duplicate handling.

Exit criteria:

- Shadow `RunAuthorityView` can be derived and compared against legacy status for a live run.

### Phase 3: Coordinator Lease And Dispatch Grants

Goal: stop stale coordinators and off-scope workers from mutating authority.

Tasks:

- Add `CoordinatorLease` with fencing token.
- Add `DispatchGrant` with `dispatch_id`, `plan_revision_hash`, `task_attempt_ids`, `sense_check_ids`, `prerequisite_digest`, `worker_identity`, expiry, and `lease_hash`.
- Stamp dispatch identity into prompt context and output schemas.
- Require result envelopes to echo lease identity.
- Quarantine late, off-lease, wrong-revision, or wrong-prerequisite results.

Exit criteria:

- Merge no longer trusts caller-provided scope; it validates immutable dispatch authority.

### Phase 4: PlanView Reducer

Goal: compute task authority and frontier from accepted events.

Tasks:

- Implement `derive_run_authority_view(events, observations)`.
- Implement `derive_megaplan_plan_view(run_view, plan_revision)`.
- Project `task_authority`, `next_ready_wave`, `runner_state`, `publication_state`, `human_gates`, `recovery_state`, and `diagnostics`.
- Make reducers pure: no filesystem, Git, process, or clock reads during fold.
- Add view hashing and schema versioning.

Exit criteria:

- PlanView can reproduce the scheduler frontier and expose disagreements with legacy artifacts.

### Phase 5: Shadow, Warn, Enforce Migration

Goal: move consumers gradually without breaking live work.

Tasks:

- Add feature modes: `off`, `shadow`, `warn`, `enforce`.
- In shadow mode, compute PlanView and log drift only.
- In warn mode, surface drift in CLI/cloud status/operator diagnostics.
- In enforce mode, execute scheduler, merge, chain status, and repair consume PlanView.
- Preserve legacy artifact writes as projections during the transition.

Exit criteria:

- Drift is visible and classified before enforcement can block or mutate behavior.

### Phase 6: Rewire Consumers

Goal: stop independent interpretation of raw artifacts.

Priority consumers:

- execute frontier computation;
- merge/reconcile;
- chain milestone advancement;
- watchdog and repair;
- cloud status snapshot;
- operator diagnostics;
- publication/PR wait handling;
- human gate and override handling.

Exit criteria:

- These consumers read PlanView facets or typed adapters, not raw status/batch artifacts directly.

### Phase 7: Quarantine And Recovery Custody

Goal: make bad inputs visible and recoverable.

Tasks:

- Add `claim_quarantined` records with source path, reason, scope, and remediation recommendation.
- Add custody buckets for stale derived state, invalid lease, invalid revision, invalid branch ancestry, no evidence, stale runner, and dirty workspace.
- Surface quarantine in CLI/cloud status.
- Add repair actions that operate on typed custody records, not direct raw-artifact mutation.

Exit criteria:

- A poisoned batch or stale state file is quarantined with an operator-visible reason and cannot be silently re-applied.

### Phase 8: Publication Facet

Goal: separate execution completion from Git/PR lifecycle.

Tasks:

- Add publication observations for branch ancestry, base ref, pushed SHA, PR number, PR head, merge status, auth status, dirty workspace, and no-push mode.
- Classify publication independently: `not_started`, `disabled`, `dirty_workspace`, `invalid_branch_ancestry`, `auth_blocked`, `push_failed`, `pr_open`, `awaiting_merge`, `merged`.
- Update chain status and operator diagnostics to show execution state and publication state separately.

Exit criteria:

- A branch ancestry failure can no longer masquerade as execute failure or plan incompletion.

### Phase 9: Parent/Child Run Lineage

Goal: make chains, epics, subpipelines, and agent runs first-class.

Tasks:

- Define child-run refs with `run_id`, `parent_run_id`, role, revision, status, and evidence refs.
- Make chain milestone aggregation consume child PlanViews.
- Add fencing so stale parent coordinators cannot overwrite child state.
- Add tests for child crash, stale parent, and publication failure isolation.

Exit criteria:

- Parent completion is derived from child authority views, not ad hoc status files.

### Phase 10: Deletion And Retirement

Goal: reduce structural drift once PlanView is enforced.

Retire or downgrade:

- direct raw `finalize.json` completion readers;
- direct `execution_batch_*.json` status readers;
- replay paths that merge old artifacts into current authority;
- duplicate cloud status classifiers;
- duplicate run-state classifiers not backed by PlanView;
- compatibility quarantine constants after migration;
- direct repair mutations that bypass reducer events.

Exit criteria:

- Deleted paths have migration tests proving their replacement behavior.

## Test Plan

Create focused tests for:

- off-lease task update rejection;
- off-lease update quarantine metadata;
- `no_pending_execution` replay preserving original dispatch scope;
- `reconcile_latest_execution_batch` preserving original dispatch scope;
- creative/doc mode cross-task policy;
- stale coordinator fencing;
- duplicate result idempotency;
- late result supersession;
- dependency closure blocking downstream authority;
- frontier computed from accepted task attempts;
- runner state requiring matching process and heartbeat evidence;
- active-step stale but process alive;
- tmux alive but wrong run identity;
- branch ancestry failure classification;
- GitHub auth failure classification;
- dirty workspace publication blocking;
- human override bound to view hash and plan revision;
- stale human override supersession;
- poisoned artifact quarantine;
- repair custody routing;
- chain milestone child-run aggregation;
- parent coordinator stale write rejection;
- PlanView shadow drift diagnostics;
- view hash determinism;
- event replay determinism;
- event duplicate idempotency;
- store crash/restart replay.

Current tests mostly exercise isolated read paths. The new tests must cover complete read-decide-mutate or observe-decide-project cycles.

## Rollout Gates

Do not enforce PlanView until:

- shadow view can be generated for existing runs;
- drift diagnostics identify exact source paths and event ids;
- replay/reconcile/creative scope gaps are covered;
- operator status shows PlanView source-of-truth and stale sources;
- repair loop consumes typed custody records;
- publication failures are separated from execution failures;
- rollback is possible by returning to legacy reads while preserving emitted events.

## Open Decisions

1. Whether to reuse existing `events.ndjson` storage for authority events or create a separate control stream.
2. Whether creative/doc mode should permit cross-task updates at all, and if so under what explicit lease.
3. Whether current `ExecutionLease` is retired or wrapped as `CoordinatorLease`.
4. Which existing feature flag owns the rollout, or whether PlanView needs its own `PLANVIEW_AUTHORITY_MODE`.
5. Whether `run_state/` becomes the generic `RunAuthorityView` implementation or remains a compatibility adapter during migration.
6. How long to keep legacy artifacts as projections after enforce mode.
7. How strict evidence validation should be for explained no-op and explained skip statuses.

## Coverage Confidence

High confidence:

- execute dispatch/merge/reconcile;
- scheduler/frontier;
- state/finalize/batch artifacts;
- chain/milestone state;
- cloud/status/watchdog/repair;
- publication/Git/PR;
- store/compat/events;
- model routing and worker envelopes;
- prompt/schema contracts;
- diagnostics and tests.

Medium confidence:

- every native pipeline edge outside Megaplan;
- all child-run/subpipeline consumers;
- every historical compatibility path;
- every operator UX surface.

Low confidence:

- code hidden outside Arnold that reads these artifacts directly;
- long-lived cloud state not present in the local checkout;
- user-created scripts that bypass Arnold APIs.

## Recommended Next Step

Do Phase 0 and Phase 1 as one hardening sprint before building the full reducer. The immediate concrete risk is still unscoped replay/reconcile/creative merge, and the highest-leverage planning move is a source inventory command that shows every authority input and its role for a run.

After that, implement typed shadow events and PlanView derivation behind `shadow` mode. Do not switch scheduler, chain, or repair to PlanView until shadow drift reports are actionable and visible in operator status.
