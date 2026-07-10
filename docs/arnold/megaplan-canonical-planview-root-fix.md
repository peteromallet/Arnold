# Arnold RunAuthorityView Substrate + Megaplan PlanView Root Fix

Date: 2026-07-10

Domain exploration backing this plan:

- `docs/arnold/runauthority-domain-exploration-synthesis.md`

## Problem

Megaplan currently has split authority. A single run can be interpreted from:

- `finalize.json`
- `state.json`
- `execution_batch_*.json`
- chain state
- active-step metadata
- watchdog and repair sidecars
- branch and PR state
- tmux/process liveness
- git dirty/head evidence

Those surfaces can disagree. Different code paths then choose different truths. In the VibeComfy trust/correctness run, that produced several related failures:

- a resumed execute frontier widened back to stale task scope;
- an execute batch accepted an off-batch task update and corrupted downstream status;
- `finalize.json` showed `T1` blocked while downstream tasks were done;
- persisted status described stale active work after the runner had died;
- branch/PR lifecycle failed independently from plan state, but status did not clearly separate that failure.

The local fixes already pushed close two concrete holes:

- execute resume scope is limited to the current runnable frontier;
- code-mode execute merge rejects off-batch task updates.

Those are necessary guards, not the full root fix.

## Root Cause

Megaplan lacks one canonical, revisioned state reducer. Raw artifacts are both evidence and authority. Task status is overloaded as:

- executor claim;
- scheduler input;
- completion authority;
- recovery control signal;
- status/reporting truth.

That makes recovery non-idempotent. Once artifacts are poisoned, retries can preserve or re-derive bad state instead of quarantining it.

## Target Architecture

Introduce a generic Arnold `RunAuthorityView` substrate, then implement Megaplan's `PlanView` as a specialization of that substrate.

The reusable problem is not "plan state." It is reconciling mutable claims, durable evidence, attempts, leases, liveness, human authority, and external effects into one revisioned projection. Plans, chains, epics, pipelines, and agent runs all have that problem.

The Megaplan-specific problem is task DAG execution: tasks, sense checks, batches, dependency closure, plan revisions, chain milestones, watchdog/repair policy, and PR publication.

The relationship should be:

```text
RunAuthorityView
└── MegaplanPlanView
```

`RunAuthorityView` should be generic and domain-neutral. It should contain:

- run identity, manifest/revision, projection cursor, and projection digest;
- attempts, leases, fencing tokens, and provenance;
- neutral lifecycle/outcome state;
- verified claims and rejected/quarantined claims;
- runner observations correlated to the exact run and attempt;
- suspensions and typed human-authority records;
- typed diagnostics with severity;
- child-run references for chains, epics, and nested pipelines.

`MegaplanPlanView` should derive Megaplan-specific state from immutable inputs and verified evidence:

- plan definition and task DAG;
- plan revision;
- dispatch attempts;
- worker result envelopes;
- evidence validation decisions;
- git/branch/PR observations;
- process liveness observations;
- human verification events;
- branch/PR publication observations.

All orchestration consumers should read the relevant view, not independently interpret raw artifacts.

The view is not authority in storage. It is a deterministic, cacheable projection of authority-bearing evidence at `(run_revision, journal_cursor, observation_set_digest)`. Authority should live in append-only decision events plus immutable content-addressed evidence.

## Boundary And Non-Goals

The generic `RunAuthorityView` core must not know about:

- `.megaplan`;
- `finalize.json`;
- `execution_batch_*.json`;
- tasks or sense checks;
- GitHub pull requests;
- tmux command shapes;
- chain milestone policy;
- watchdog/repair escalation policy.

Those are adapter or Megaplan binding concerns.

Megaplan-specific concerns that remain in `MegaplanPlanView`:

- task DAGs and dependency closure;
- `next_ready_wave`;
- plan revision and prerequisite digest semantics;
- task/sense-check lease contents;
- code vs creative/doc cross-task policy;
- evidence satisfaction and explained skip/no-op rules;
- chain milestone and epic aggregation;
- watchdog/repair policy;
- Git/PR/no-push publication semantics.

Do not build a universal God-view enum that mixes task, PR, process, human-gate, and repair semantics. A field moves into the generic substrate only after at least two independent consumers need the same semantics.

## Core Invariants

1. Raw task status is a claim, not authority.
2. A task is complete only when its latest valid attempt has verified evidence.
3. A dispatch can mutate only tasks leased to that dispatch.
4. Results carry `plan_revision`, `attempt_id`, `dispatch_id`, and prerequisite digest.
5. Off-lease updates are rejected or quarantined, never merged into task authority.
6. Downstream tasks cannot be authoritative if dependency closure is not authoritative.
7. The next runnable frontier is computed from `PlanView`, not from stale raw statuses.
8. "Running" requires live process evidence matching active-step metadata.
9. Recovery scopes stale repair/watchdog markers to `(plan_revision, attempt_id)`.
10. Branch/PR validity is a separate typed state, not implied by plan success.
11. `PlanView` and `RunAuthorityView` are projections, not mutable authority files.
12. Reducers are pure and deterministic; they never read files, Git, processes, or wall-clock time directly.
13. Claims and authority decisions are separate event classes.
14. Named artifacts are projections or pointers; authoritative payloads are immutable and content-addressed.

## Data Model

Use these entities for the Megaplan specialization:

- `Plan`: stable identity.
- `PlanRevision`: immutable DAG and policy snapshot, identified by canonical content hash.
- `Run`: one orchestration lifecycle for a `PlanRevision`.
- `CoordinatorAttempt`: one runner/recovery ownership epoch for a run.
- `TaskAttempt`: `(run_id, task_id, attempt_no)`. Completion belongs here, not on task definition.
- `DispatchGrant`: immutable capability granting a worker authority over explicit task and sense-check ids.
- `ResultEnvelope`: immutable worker claim associated with exactly one `DispatchGrant`.
- `EvidenceObject`: content-addressed artifact, command result, git observation, test result, or human assertion.
- `ValidationDecision`: policy-versioned decision accepting, rejecting, or quarantining claims/evidence.
- `RunnerSession`, `PublicationTarget`, `HumanGate`, `RecoveryAction`, and typed `Diagnostic`.

Relationship:

```text
PlanRevision
  -> Run
    -> CoordinatorAttempt
      -> DispatchGrant
        -> TaskAttempt
          -> ResultEnvelope
            -> EvidenceObject
              -> ValidationDecision
```

`MegaplanPlanView` projects these into task state, ready frontier, runner state, publication state, human gates, recovery state, and diagnostics. It carries `source_seq`, `view_schema_version`, `plan_revision_hash`, and `view_hash`.

## Event And Reducer Model

Use a typed control-plane event stream distinct from telemetry. Core events:

- `plan_revision_activated`
- `coordinator_lease_acquired`
- `coordinator_lease_lost`
- `dispatch_granted`
- `dispatch_revoked`
- `dispatch_expired`
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
- `human_gate_superseded`
- `publication_observed`
- `publication_failed`
- `recovery_decided`
- `recovery_completed`

Every event envelope needs:

- `event_id`;
- run ids and plan revision hash;
- stream sequence;
- schema version;
- idempotency key;
- correlation and causation ids;
- actor identity;
- timestamps.

Reducers fold events only. File reads, Git observations, process observations, and clock decisions must become events before they affect authority. Lease expiry is therefore an explicit `dispatch_expired` event, not a `now() > expires_at` check inside replay.

Facts and claims:

- result submitted;
- process observed;
- branch observed;
- artifact found.

Authority decisions:

- evidence accepted;
- task attempt accepted;
- recovery action adopted;
- branch state classified.

Only authority decision events advance execution authority.

The existing `events.ndjson` fold is not enough as-is because it is last-full-snapshot-wins and mixes operational events with shadow state snapshots. Reuse the store/event infrastructure, but introduce a typed control stream rather than extending snapshot replay indefinitely.

## Lease Model

Split lease semantics in two:

1. `CoordinatorLease`: exclusive authority to schedule and commit reducer decisions for a run. It carries a monotonically increasing fencing token.
2. `DispatchGrant`: bounded worker capability over explicit task/sense-check ids.

`DispatchGrant` fields:

- `dispatch_id`;
- `run_id`;
- `coordinator_fence`;
- `plan_revision_hash`;
- `task_attempt_ids`;
- `sense_check_ids`;
- `prerequisite_digest`;
- `worker_identity`;
- `issued_at`;
- `expires_at`;
- `lease_hash`.

Dispatch lifecycle:

```text
granted -> claimed/running -> result_submitted -> validating -> accepted|rejected|quarantined
        -> expired|revoked|superseded
```

Late results are allowed to arrive. They may be accepted only if no later task attempt or coordinator fence supersedes them and a compare-and-swap commit succeeds. Otherwise they are quarantined.

The current `ExecutionLease` should be treated as a temporary coordinator-exclusion mechanism, not as dispatch authority. It lacks task scope, attempt identity, revision binding, and fencing.

## Evidence And Provenance

Authoritative completion must trace:

```text
TaskAttempt
  <- accepted ResultEnvelope
  <- accepted ValidationDecision
  <- EvidenceObjects
```

Evidence objects include:

- SHA-256 digest;
- size;
- media/schema type;
- producer worker and dispatch;
- task attempt;
- repository/workspace identity;
- base/head SHA and execution window;
- command, exit code, test selection, and timestamps where relevant;
- parent evidence hashes for derived evidence.

`executor_notes`, plausible skip explanations, and raw `status` are annotations only. They cannot satisfy completion or dependency closure alone.

Signatures can follow after the first migration slices. The minimum first boundary is content hashes, worker identity, dispatch capability hash, and immutable validation records.

## State Facets

Do not collapse these into one run enum.

- `execution_state`: per `TaskAttempt`: `pending`, `ready`, `leased`, `running`, `submitted`, `verifying`, `satisfied`, `failed`, `blocked`, `waived`, `not_applicable`, `superseded`. `ready` is derived.
- `runner_state`: `absent`, `starting`, `live`, `suspect`, `stale`, `orphan`, `exited`. `live` requires matching run, coordinator attempt, dispatch, fresh heartbeat, and process/session observation. Heartbeat-only is `suspect`, not `live`.
- `publication_state`: `disabled_no_push`, `unprepared`, `branch_valid`, `invalid_ancestry`, `local_ahead`, `pushed`, `pr_open`, `merged`, `failed`, `auth_blocked`. Publication never changes execution completion.
- `human_gate_state`: `open`, `answered`, `accepted`, `rejected`, `superseded`, `expired`. Each gate binds to gate id, plan revision, view hash, scope, allowed decisions, and evidence requirements.
- `recovery_state`: actions such as `quarantine_artifact`, `supersede_attempt`, `repair_branch`, `replan`, and `adopt_evidence`, each with precondition view hash and actor.

## Idempotency And Storage Contract

- Event append uniqueness: `(stream_id, idempotency_key)`.
- Same idempotency key plus different payload hash is a hard conflict.
- Authority mutation uses compare-and-swap on `expected_source_seq` plus coordinator fencing token.
- Result identity is unique by `(dispatch_id, task_attempt_id, result_kind)`.
- Validation identity is deterministic from policy version and ordered evidence hashes.
- Journal append and outbox/artifact-reference registration must be one transaction.
- File mode needs one locked append/CAS boundary.
- DB mode needs row/version checks.
- Reprocessing the same event is a no-op.
- Ordering is stream sequence, never filename or timestamp.
- `prerequisite_digest` is a canonical hash of plan revision plus each prerequisite's accepted attempt id and validation/evidence hashes.

## Incremental Plan

### Phase 1: Read-Only Canonical View

- Add `derive_plan_view(plan_dir, workspace)` that reads current artifacts and emits a typed view.
- Add `validate_plan_view(view)` that reports contradictions without mutating files.
- Add CLI/status output showing canonical state beside legacy state.
- Add diagnostics for stale active-step records, impossible dependency closure, off-lease batch artifacts, and invalid branch ancestry.

### Phase 2: Scheduler Binding

- Make execute compute `next_ready_wave(view)`.
- Dispatch only the canonical runnable frontier.
- Include `plan_revision`, `dispatch_id`, attempt id, leased task ids, and dependency digest in every batch artifact.
- Reject dispatch if legacy artifacts and canonical view disagree on runnable frontier.

### Phase 3: Merge Binding

- Merge worker results only through the canonical reducer.
- Enforce lease scope for tasks and sense checks.
- Treat worker output as claims until evidence validation passes.
- Quarantine off-lease, wrong-revision, wrong-digest, or unsupported updates.

### Phase 4: Status And Liveness Binding

- Make `cloud status`, `chain status`, watchdog, and repair loops consume `PlanView`.
- Report `stale_active_step` when active-step metadata lacks matching process/tmux evidence.
- Report `branch_invalid` separately from `plan_blocked`.
- Prevent `effective_status: running` when runner evidence is dead.

### Phase 5: Recovery Binding

- Replace ad hoc recovery decisions with reducer-driven transitions:
  - `recoverable`
  - `needs_replan`
  - `needs_branch_repair`
  - `needs_human_verification`
  - `poisoned_artifacts_quarantined`
- Before resume, reconcile or quarantine contradictions.
- Never resume from an inconsistent view unless the recovery command records the chosen repair.

### Phase 6: Branch/PR Lifecycle Binding

- Model branch ancestry, PR existence, push state, and no-push mode as explicit state.
- If branch has no common ancestry with base, require branch repair or fresh milestone branch.
- Do not conflate GitHub auth, PR creation, branch ancestry, and plan execution.

## Tests Required

- Generic core contains no task, phase, GitHub, tmux, or Megaplan artifact vocabulary.
- Cached views are invalidated when journal cursor or observation-set digest changes.
- Deterministic replay produces the same view hash from the same event stream.
- Snapshot/journal equivalence holds across compaction.
- Duplicate idempotency key with different payload hash is a hard conflict.
- Coordinator fencing-token takeover prevents stale coordinator commits.
- Delayed old result after a newer task attempt is quarantined.
- Stale human answer cannot resolve a superseding gate.
- Sequential DAG where `T1` is incomplete and downstream raw statuses are done: canonical frontier is `T1`, downstream is non-authoritative.
- Batch result for `T2` includes `T7`: `T7` is not mutated; artifact is quarantined or rejected.
- Stale active-step metadata but dead tmux/process: canonical status is not running.
- Heartbeat-only runner evidence is `suspect`, not `live`.
- Live process but stale persisted state: status distinguishes running process from unchanged plan phase.
- Branch has no common history with base: branch state is invalid, plan state remains separate.
- Resume after completed tasks: single-batch fast path cannot widen to all task ids.
- Wrong `plan_revision` or prerequisite digest: result cannot mutate current view.
- Watchdog/repair marker from old attempt: ignored for current attempt unless explicitly adopted.
- No-push and PR mode produce equivalent plan execution state, differing only in publication state.
- Random DAG property test: dispatch is always a subset of ready frontier; authoritative completion implies authoritative dependency closure.
- `no_pending_execution` replay cannot merge historical off-lease updates.
- `reconcile_latest_execution_batch` cannot merge updates outside the artifact's recorded `batch_task_ids`.
- Creative/doc mode either rejects off-batch updates or requires an explicit cross-task lease.
- Legacy artifact with no revision/dispatch id is read-only evidence, not merge authority.
- Branch with no common history reports `publication_state: invalid_branch_ancestry` while preserving execution state.
- Status surfaces quarantined updates and stale active-step diagnostics to operators.
- Explained skips/no-ops cannot satisfy dependency closure based only on non-empty notes.
- Concurrent chain/recover/status operations cannot observe a partially-written `PlanView`.
- Wrong worker identity or missing evidence hash prevents authoritative completion.

## Open Design Questions

- Whether `PlanView` should be event-sourced from an append-only journal immediately, or first derived from existing artifacts as a compatibility layer.
- Whether quarantine writes should be sidecar artifacts or a first-class event stream.
- How strict to make sense-check lease scope for creative/doc modes that may intentionally over-produce.
- Whether branch/PR lifecycle should live inside `PlanView` or as a sibling `PublicationView`.
- Whether `PlanView` should extend the existing `run_state` resolver, `store/plan_repository.py`, `store/compat.py`, and R1 authority WAL paths, rather than introducing a parallel store.
- Whether provenance checks require signed worker result envelopes immediately, or can start with content hashes and dispatch-lease hashes before adding signing/key rotation.

## Swarm Review Synthesis

Twenty focused DeepSeek reviewers audited this plan across execute, merge, DAG scheduling, liveness, cloud launch, git/PR publication, watchdog/repair, override transitions, chain milestones, artifact revisioning, concurrency, model routing, worker active steps, human gates, push/no-push parity, test strategy, migration/backcompat, observability, and provenance.

The original plan is directionally right, but the swarm found edge paths that would preserve the same failure family if left out.

### Critical Additions

1. `no_pending_execution` replay must be scope-safe.

   Resume/no-pending paths can replay historical `execution_batch_*.json` artifacts with broad task scope. This is a second widening path distinct from the single-batch fast-path bug already fixed. Every replay/reconciliation merge must use the original dispatch lease recorded on the artifact. If no lease is present, the artifact is legacy/untrusted and may only be read as evidence, not merged as authority.

2. `reconcile_latest_execution_batch` must not use all tasks as scope.

   Failure-boundary reconciliation can currently treat the latest batch as if it can update the whole plan. Reconciliation must only merge entries matching the artifact's recorded `batch_task_ids`, `dispatch_id`, `plan_revision`, and prerequisite digest.

3. Creative/doc mode cannot be an unscoped exception by default.

   The code-mode off-batch fix restricts merge targets to `batch_task_ids`, but creative/doc paths still have an explicit all-task merge exception. Either enforce leases for every mode or model creative cross-task overproduction as a separate lease type with bounded target ids.

4. Existing compatibility surfaces must be reused.

   The codebase already has partial canonical-state machinery:

   - `run_state/resolver.py`
   - `run_state/classifiers.py`
   - `store/plan_repository.py`
   - `store/compat.py`
   - R1 authority WAL paths in `_core/io.py`
   - observability event projection modules

   Phase 1 must define whether `PlanView` composes these components or supersedes them. Do not build a second truth layer beside them without an explicit migration bridge.

5. Publication state needs its own model.

   The VibeComfy relaunch showed GitHub auth was not the real publication blocker once `/workspace/.cloud-hot-env` was sourced. The PR blocker was branch ancestry: the milestone branch had no common history with `main`.

   Split state into:

   - `execution_state`
   - `publication_state`
   - `runner_state`
   - `human_gate_state`

   A branch with invalid ancestry should produce `publication_state: invalid_branch_ancestry`, not make the plan look execution-blocked.

6. Liveness must combine active-step metadata with process evidence.

   Active-step staleness is timestamp-based in some paths and process/tmux-based in others. `running` requires a matching live process/session plus a current active-step record for the same run id. Mismatch states are `stale_active_step` or `orphan_runner`, never healthy running.

7. Diagnostics need severity and operator visibility.

   Current merge issues can stay in local `issues` lists and never reach operator status. PlanView must surface contradictions as typed diagnostics.

   Suggested severities:

   - `advisory`: harmless divergence or ignored legacy artifact.
   - `quarantine`: bad artifact ignored, execution can continue.
   - `blocked`: recovery decision required before dispatch.
   - `fatal`: canonical state cannot be derived safely.

8. Provenance must be part of authority.

   A canonical view derived from untrusted mutable files is still vulnerable. PlanView should at least bind authority to content hashes and dispatch ids, then later support signed worker result envelopes with worker identity and key id.

   Authoritative completion must trace to a valid `(plan_revision, dispatch_id, task_id, evidence_hash)` tuple. Raw `executor_notes` alone cannot satisfy this.

## Revised Implementation Path

### Phase 0: Compatibility Inventory

- Map every current authority reader and reducer:
  - `effective_execute_completed_task_ids`
  - `corroborated_completed_task_ids`
  - `run_state` classifiers
  - `PlanRepository`
  - R1 WAL authority reads
  - status snapshot builders
  - repair/watchdog sidecars
- Decide whether `PlanView` composes these components or replaces them.
- Reconcile Arnold's existing journal-like surfaces:
  - `arnold/kernel/journal.py`
  - `arnold/runtime/event_journal.py`
  - Megaplan `events.ndjson` / R1 authority WAL
  - store event appenders and observability projections
- Define `RunAuthorityView` and `MegaplanPlanViewBinding`.
- Define observation envelopes and projection coordinates.
- Add a feature flag for read-only PlanView derivation.

### Phase 1: Read-Only PlanView And Diagnostics

- Implement generic `derive_run_authority_view(definition, observations, authority_policy)`.
- Implement Megaplan `derive_plan_view(plan_dir, workspace=None, process_probe=None, git_probe=None)` as an adapter that imports legacy artifacts as synthetic untrusted observations.
- Emit typed subviews:
  - `execution`
  - `dispatches`
  - `publication`
  - `runner`
  - `human_gates`
  - `diagnostics`
- Add `validate_plan_view(view)` returning typed diagnostics with severity.
- Make CLI/status print canonical view beside legacy state.
- Compare shadow `PlanView` with legacy status plus existing `CanonicalRunState`.

### Phase 2: Dispatch Lease Model

- Add lease fields to new batch artifacts:
  - `plan_revision`
  - `attempt_id`
  - `dispatch_id`
  - `batch_task_ids`
  - `batch_sense_check_ids`
  - `prerequisite_digest`
  - `worker_identity`
  - `created_head_sha`
- Preserve legacy artifacts as read-only evidence unless they can be safely scoped.
- Make dispatch calculation consume `PlanView.next_ready_wave`.
- Keep existing `ExecutionLease` only as coordinator exclusion until `CoordinatorLease` fencing replaces it.

### Phase 3: Merge And Reconciliation Binding

- Route normal merge, failure-boundary reconciliation, no-pending replay, review rework, and creative/doc merge through the same lease validator.
- Reject or quarantine:
  - off-lease task updates;
  - wrong revision;
  - wrong dispatch id;
  - stale prerequisite digest;
  - unsupported creative cross-task update;
  - result without sufficient evidence.
- Store quarantine records in a durable artifact or event stream surfaced by status.
- Emit new merge/reconciliation authority decisions through the typed control stream; keep legacy JSON artifacts as compatibility projections.

### Phase 4: Dependency And Evidence Authority

- Replace dependency checks that read raw `status` with checks against authoritative completion.
- Require dependency closure for authoritative downstream completion.
- Revisit explained skip/no-op paths: they should not satisfy dependencies based only on plausible notes.

### Phase 5: Status, Liveness, And Publication

- Make `cloud status`, `chain status`, watchdog, and repair use PlanView.
- Add explicit status fields:
  - `execution_state`
  - `runner_state`
  - `publication_state`
  - `recovery_state`
- Treat no-push mode as a publication mode, not a different execution mode.
- Detect branch ancestry failure independently from plan execution.

### Phase 6: Recovery And Repair

- Recovery commands must first derive and validate PlanView.
- If view is inconsistent:
  - quarantine bad artifacts;
  - record the recovery decision;
  - compute the next runnable frontier from canonical evidence;
  - refuse resume if the contradiction is fatal.
- Scope watchdog/repair markers to `(plan_revision, attempt_id, run_id)`.

### Phase 7: Provenance Hardening

- Bind every authoritative result to content hashes and dispatch lease ids.
- Add worker identity to result envelopes.
- Add key id and signature verification where warrant infrastructure already exists.
- Bind override freshness tokens to PlanView revision hash instead of wall-clock timestamp alone.

### Phase 8: Second Consumer Proof

- Prove `RunAuthorityView` against one non-Megaplan consumer before promoting more fields into the generic substrate.
- Candidate consumers:
  - native pipeline run;
  - agent run;
  - durable operation supervisor.
- Keep Megaplan-only fields in `MegaplanPlanViewBinding` until this second consumer proves the semantics are shared.

## Success Criteria

- No code path treats raw `status: done` as completion without evidence.
- No status command reports a run as healthy/running when process evidence is absent.
- Execute, status, watchdog, repair, and chain all agree on the same current state.
- Recovery from poisoned artifacts is deterministic and explainable.
- Existing runs can be diagnosed through the compatibility-derived view before full migration.
