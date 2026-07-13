# RunAuthority Main Plan

Date: 2026-07-10

Status: controlling direction for the RunAuthority / Megaplan PlanView work.

Supporting docs:

- `docs/arnold/megaplan-canonical-planview-root-fix.md`
- `docs/arnold/runauthority-domain-exploration-synthesis.md`
- `docs/arnold/runauthority-architecture-decision.md`

This document captures the core direction in one place. If the supporting docs contain broader or contradictory language, this document wins.

## Executive Decision

Build a narrow generic Arnold `RunAuthorityKernel`, not a generic god-view.

The kernel answers:

> Which claims are authoritative for this run, under which revision, attempt, capability, evidence, and fencing epoch?

It does not answer:

- which Megaplan task is ready;
- whether a PR needs merging;
- whether a tmux process is the right runner;
- whether a watchdog should repair or escalate;
- whether a chain milestone is complete;
- whether a domain-specific skip/no-op is acceptable.

Those are domain bindings, sibling views, or services.

The architecture is:

```text
Evidence / Observation Layer
  -> RunAuthorityKernel
    -> RunAuthorityView
      -> Domain Bindings
        -> MegaplanAuthorityBinding
          -> PlanExecutionView
        -> RunnerView
        -> PublicationView
        -> HumanGateView
        -> MegaplanRecoveryView
          -> MegaplanPlanView facade
```

There is one canonical authority model, not one canonical reducer that knows every domain.

## Why This Exists

The VibeComfy/Megaplan incident exposed a split-authority failure. The same run could be interpreted from:

- `finalize.json`;
- `state.json`;
- `execution_batch_*.json`;
- chain state;
- active-step metadata;
- watchdog and repair sidecars;
- Git/PR state;
- tmux/process liveness;
- git dirty/head evidence;
- model routing records.

Those surfaces disagreed. Different code paths then picked different truths. That caused stale/off-scope artifacts to affect task completion, frontier calculation, recovery, status, and publication.

The immediate fixes already pushed are necessary but not sufficient:

- execute resume scope is limited to the current runnable frontier;
- code-mode execute merge rejects off-batch task updates.

The root fix is to stop treating mutable artifacts as authority.

## Core Principle

Raw artifacts are evidence, claims, observations, or projections. They are not authority.

Authority comes from:

- immutable evidence;
- scoped capability grants;
- coordinator fencing;
- validation decisions;
- append-only decision journal;
- deterministic projection.

Compatibility artifacts may be regenerated from authority. Authority must not be silently regenerated from compatibility artifacts.

## Layers

### 1. Evidence And Observation Layer

Collectors may read:

- files;
- Git;
- GitHub;
- tmux;
- processes;
- APIs;
- clocks;
- legacy artifacts.

Collectors emit immutable observation envelopes or evidence refs. They do not make authority decisions.

High-volume telemetry, especially heartbeats, should not all become authority events. Store observations separately and let authority decisions reference the observation set digest used.

### 2. RunAuthorityKernel

Generic Arnold substrate for authority mechanics.

The kernel owns:

- run identity;
- opaque run revision;
- coordinator attempts;
- coordinator leases;
- fencing tokens;
- bounded capability grants;
- subject attempts;
- claim envelopes;
- immutable evidence references;
- validation decisions;
- acceptance, rejection, quarantine, and supersession;
- idempotency keys;
- compare-and-swap commit rules;
- parent/child run references;
- typed human-decision records;
- projection cursor;
- schema version;
- view hash;
- diagnostic envelopes with evidence refs.

Use generic names in the kernel:

- `CapabilityGrant`, not `DispatchGrant`;
- `SubjectAttempt`, not `TaskAttempt`;
- `Claim`, not `task_update`;
- `Decision`, not `task_status`.

### 3. Domain Bindings

A domain binding defines:

- what capability scope means;
- what claim types exist;
- what evidence can satisfy those claims;
- which claims can advance domain state;
- dependency and supersession rules;
- domain diagnostics;
- derived domain views.

Megaplan supplies `MegaplanAuthorityBinding`.

### 4. MegaplanAuthorityBinding And PlanExecutionView

Megaplan owns:

- plan revisions;
- task DAGs;
- sense checks;
- task attempts;
- prerequisite digests;
- dependency closure;
- `next_ready_wave`;
- batch scope;
- creative/doc cross-task policy;
- evidence satisfaction;
- waiver, skip, and no-op semantics;
- milestone and chain advancement;
- model routing when it affects execution;
- Megaplan-specific recovery/custody policy.

`PlanExecutionView` exposes accepted task authority, dependency closure, ready frontier, blocked state, and task/sense-check results.

### 5. Sibling Views

Sibling views are not generic-kernel fields. They share observation envelopes and authority decisions but keep their policies separate.

`RunnerView`:

- process/session/heartbeat state;
- runner identity correlation;
- stale active-step detection;
- orphan process detection.

`PublicationView`:

- branch ancestry;
- dirty workspace;
- pushed SHA;
- PR number/head;
- auth state;
- no-push mode;
- merge state.

`HumanGateView`:

- open gates;
- allowed decisions;
- human responses;
- view-hash binding;
- supersession and expiry.

`MegaplanRecoveryView`:

- quarantined artifacts;
- invalid lease/revision/prerequisite cases;
- stale runner state;
- invalid branch ancestry;
- dirty workspace;
- repair custody and permitted next actions.

`MegaplanPlanView` is a facade that can render or package these views together for operators and orchestrators. Internally, consumers should use the smallest relevant view.

## Deliberately Not Generalized

Do not put these in the generic kernel:

- task DAGs;
- ready waves;
- sense checks;
- milestone policy;
- Git branches and PR lifecycle;
- no-push semantics;
- tmux command shapes;
- watchdog/superfixer taxonomy;
- prompt contracts;
- model routing policy;
- universal execution-complete enum;
- parent completion aggregation;
- a single lifecycle enum that merges execution, runner, publication, gates, and recovery.

Promote semantics into the generic kernel only after a second non-Megaplan consumer proves they are truly shared.

## Required Invariants

1. Raw status is a claim, never completion authority.
2. Every authoritative transition identifies run revision, subject attempt, capability grant, coordinator fence, and evidence.
3. A capability can affect only its explicit scope.
4. Wrong-revision, stale-fence, off-scope, late, or superseded results are rejected or quarantined.
5. Downstream authority requires authoritative dependency closure.
6. Recovery cannot silently reinterpret or reapply legacy artifacts.
7. Reducers do no I/O and consult no wall clock.
8. File, Git, process, API, and clock reads become observations before they affect authority.
9. Execution, runner, publication, human-gate, and recovery states do not imply one another.
10. Consumers see an atomically versioned view with journal cursor and evidence set digest.
11. Duplicate idempotency key with a different payload hash is a hard conflict.
12. Compatibility projections can be regenerated from authority; authority cannot be regenerated unquestioningly from compatibility projections.

## Incident-Specific Failure Classes To Close

### Scope Widening

Known risky paths:

- `no_pending_execution` replay;
- `reconcile_latest_execution_batch`;
- creative/doc mode all-task merge behavior;
- legacy batches with no lease identity.

Rule: merge must validate immutable capability scope, not trust caller-supplied task ids.

### Raw Status As Authority

Known symptom:

- `finalize.json` status and `execution_batch_*.json` task updates can be interpreted as completion.

Rule: task status is a claim. Completion lives on accepted task attempts with verified evidence.

### Recovery Over Poisoned Artifacts

Known risky inputs:

- stale execution batches;
- stale `finalize.json`;
- stale active-step metadata;
- repair sidecars;
- chain state from older coordinator attempts.

Rule: poisoned inputs become quarantined claims with custody records, not silently re-applied state.

### Liveness Without Identity Binding

Known risky inputs:

- tmux session exists;
- process exists;
- active-step timestamp exists;
- watchdog marker exists.

Rule: `running` requires correlated run identity, coordinator attempt, session/process observation, and fresh heartbeat/active-step evidence. Mismatches become `stale`, `suspect`, or `orphan`.

### Publication Conflated With Execution

Known failure:

- branch ancestry and PR lifecycle failures can look like execution failures.

Rule: publication is a sibling state. Execution can be complete while publication is `invalid_branch_ancestry`, `auth_blocked`, `dirty_workspace`, `push_failed`, `pr_open`, or `awaiting_merge`.

## Phased Implementation

### Phase 0: Freeze Known Regressions

Close the current exploit paths before broader migration.

Tasks:

- test that `no_pending_execution` replay preserves original dispatch scope;
- test that `reconcile_latest_execution_batch` preserves original dispatch scope;
- decide and enforce creative/doc cross-task policy;
- add a VibeComfy incident fixture;
- keep existing off-batch merge and resume-frontier fixes.

Exit:

- the known incident cannot corrupt authority through replay, reconcile, or creative/doc merge paths.

### Phase 1: Authority Input Inventory

Build a command/module that lists all authority-relevant inputs for a run and classifies each as:

- observation;
- claim;
- decision;
- projection.

Include:

- `state.json`;
- `finalize.json`;
- execution batches;
- chain state;
- cloud markers;
- watchdog report;
- repair sidecars;
- Git/PR observations;
- process/session observations;
- `run_state` readers;
- store/repository/compat readers;
- WAL/event readers.

Exit:

- one command can explain what sources exist, what role each plays, and where contradictions are.

### Phase 2: Kernel Contracts

Define:

- event envelope;
- observation envelope;
- evidence envelope;
- capability grant;
- subject attempt;
- coordinator fence;
- decision record;
- quarantine record;
- projection metadata;
- idempotency and CAS rules.

Exit:

- reducers can fold authority decisions deterministically without I/O.

### Phase 3: Legacy Adapters And Shadow Views

Build read-only adapters over current artifacts.

Imported legacy state without revision, attempt, grant, fence, and evidence identity is observation only.

Produce shadow:

- `RunAuthorityView`;
- `PlanExecutionView`;
- `RunnerView`;
- `PublicationView`;
- `HumanGateView`;
- `MegaplanRecoveryView`;
- `MegaplanPlanView` facade.

Exit:

- shadow views can be generated for existing runs and compared with legacy status.

### Phase 4: Megaplan Dispatch Grants

Introduce Megaplan `DispatchGrant` as a wrapper over `CapabilityGrant`.

Every worker result must echo:

- dispatch id;
- plan revision;
- coordinator fence;
- task/sense-check scope;
- prerequisite digest;
- worker identity.

Exit:

- merge no longer trusts caller-provided scope.

### Phase 5: Unified Merge/Reconcile Validator

Route every merge-like path through one validator:

- normal merge;
- failure-boundary reconcile;
- no-pending replay;
- review rework;
- creative/doc merge.

Reject or quarantine:

- off-scope updates;
- wrong revision;
- wrong dispatch id;
- stale prerequisite digest;
- unsupported creative cross-task updates;
- insufficient evidence.

Exit:

- every accepted task update traces to a valid grant and evidence decision.

### Phase 6: Frontier And Dependency Authority

Implement `PlanExecutionView.next_ready_wave` from accepted task attempts and dependency closure.

Stop using raw `finalize.json` status for scheduler authority.

Exit:

- scheduler, dependency checks, and downstream completion agree on accepted task authority.

### Phase 7: Sibling Operational Views

Implement:

- `RunnerView`;
- `PublicationView`;
- `HumanGateView`;
- `MegaplanRecoveryView`.

Exit:

- execution status, runner liveness, publication state, human gates, and recovery custody are visible separately.

### Phase 8: Rewire Consumers

Move consumers through `shadow -> warn -> enforce`:

- execute scheduler;
- merge/reconcile;
- chain advancement;
- cloud status;
- watchdog;
- repair loop;
- PR/publication wait handling;
- human override handling.

Exit:

- no major consumer independently interprets raw artifacts for authority.

### Phase 9: Second Consumer Proof

Apply the generic kernel to one non-Megaplan consumer before promoting more semantics.

Candidates:

- native pipeline run;
- durable operation supervisor;
- generic agent run.

Exit:

- shared semantics are proven by implementation, not assumed.

### Phase 10: Delete Compatibility Paths

Retire duplicate/legacy paths after enforce-mode equivalence tests pass.

Targets:

- raw `finalize.json` completion readers;
- raw `execution_batch_*.json` authority readers;
- replay paths that merge old artifacts into authority;
- duplicate cloud status classifiers;
- duplicate run-state classifiers not backed by composed views;
- repair mutations that bypass authority decisions.

Exit:

- compatibility projections are only projections; duplicate authority readers are gone.

## Testing Strategy

Must cover complete read-decide-mutate or observe-decide-project cycles, not just isolated readers.

Required tests:

- off-scope task update rejection;
- off-scope quarantine metadata;
- replay preserving original dispatch scope;
- reconcile preserving original dispatch scope;
- creative/doc cross-task policy;
- stale coordinator fencing;
- duplicate result idempotency;
- late result supersession;
- dependency closure blocking downstream authority;
- frontier from accepted task attempts;
- runner identity mismatch;
- stale active-step with no runner;
- orphan runner with stale active-step;
- branch ancestry classification;
- GitHub auth classification;
- dirty workspace publication blocking;
- human decision bound to view hash and revision;
- stale human override supersession;
- poisoned artifact quarantine;
- repair custody routing;
- chain child-run aggregation;
- parent coordinator stale write rejection;
- shadow drift diagnostics;
- view hash determinism;
- event replay determinism;
- event duplicate idempotency;
- store crash/restart replay.

## Rollout Gates

Do not enforce until:

- shadow view works on existing runs;
- drift diagnostics identify exact source paths and reasons;
- replay/reconcile/creative scope gaps are covered;
- status shows separate execution, runner, publication, gate, and recovery state;
- repair consumes custody records;
- publication failures are separated from execution failures;
- rollback is possible by returning to legacy reads while preserving emitted events.

## Open Decisions

1. Whether to reuse existing event storage or create a distinct authority decision stream.
2. The exact creative/doc cross-task lease policy.
3. Whether current `ExecutionLease` is wrapped into `CoordinatorLease` or retired.
4. The feature flag name and rollout mode values.
5. Whether `run_state/` becomes part of the kernel implementation or remains a compatibility adapter.
6. How long to keep legacy artifacts as projections after enforce mode.
7. How strict evidence validation should be for skip/no-op claims.

## Immediate Next Work

Start with Phase 0 and Phase 1.

The system is not ready for the full reducer until the current incident class is frozen and the authority input inventory exists. The inventory is the first real implementation boundary: it will show what must become an observation, what is already a decision, what is only projection, and where split authority remains.
