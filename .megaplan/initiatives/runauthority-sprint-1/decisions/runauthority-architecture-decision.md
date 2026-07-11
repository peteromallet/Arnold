# RunAuthority Architecture Decision

Date: 2026-07-10

Main plan:

- `docs/arnold/runauthority-main-plan.md`

This document records the judgment call behind the main plan. The main plan captures the controlling implementation direction.

This is the judgment call after the initial PlanView plan, the 28-domain DeepSeek exploration, and the Sol synthesis pass.

Related docs:

- `docs/arnold/megaplan-canonical-planview-root-fix.md`
- `docs/arnold/runauthority-domain-exploration-synthesis.md`

## Decision

Build a generic Arnold `RunAuthorityKernel`, not a generic god-view.

The kernel answers one question:

> Which claims are authoritative for this run, under which revision, attempt, capability, evidence, and fencing epoch?

It should not answer domain questions like:

- which Megaplan task is ready;
- whether a branch can be pushed;
- whether a PR needs merging;
- whether a tmux process is the right runner;
- whether a watchdog should repair or escalate;
- whether a chain milestone is complete.

Those are composed domain views and services.

The shape is:

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

`MegaplanPlanView` can exist as an operator and orchestration facade, but internally it should be composed from smaller views. There should be one canonical authority model, not one reducer that knows every Arnold domain.

## Why

The VibeComfy/Megaplan incident was caused by split authority:

- `finalize.json`;
- `state.json`;
- `execution_batch_*.json`;
- chain state;
- active-step metadata;
- watchdog and repair sidecars;
- Git/PR state;
- process/tmux liveness;
- model routing records.

Different code paths trusted different surfaces. That let stale or off-scope artifacts mutate apparent completion, recovery, and status.

The reusable root problem is not tasks. It is claim authority:

- who made a claim;
- what scope they were authorized to affect;
- under which run revision and coordinator fence;
- what evidence backs the claim;
- whether the claim was accepted, rejected, quarantined, or superseded.

That is generic. Task DAGs, PR state, liveness policy, repair policy, and milestone advancement are not.

## Generic Kernel

The generic `RunAuthorityKernel` owns:

- run identity;
- opaque run revision;
- coordinator attempts;
- coordinator leases and fencing tokens;
- bounded capability grants;
- subject attempts;
- claim envelopes;
- immutable evidence references;
- validation decisions;
- acceptance/rejection/quarantine/supersession;
- idempotency keys;
- compare-and-swap commit semantics;
- parent/child run references;
- typed human-decision records;
- projection cursor, schema version, and view hash;
- diagnostics envelopes with evidence refs.

Use generic names in the kernel:

- `CapabilityGrant`, not `DispatchGrant`;
- `SubjectAttempt`, not `TaskAttempt`;
- `Claim`, not `task_update`;
- `Decision`, not `task_status`.

Megaplan can wrap these with domain names:

- `DispatchGrant`;
- `TaskAttempt`;
- `SenseCheckAttempt`;
- `TaskClaim`;
- `TaskValidationDecision`.

## Evidence And Observations

Collectors can read files, Git, GitHub, tmux, processes, APIs, clocks, and old artifacts.

Collectors do not make authority decisions. They emit immutable observation envelopes or evidence refs.

High-volume telemetry, especially heartbeats, should not all become authority events. Store observations separately and let authority decisions reference an observation set digest.

Authority lives in:

- append-only decision journal;
- immutable evidence;
- deterministic projection.

Compatibility artifacts are projections or imported observations. They are not authority.

## Domain Bindings

A domain binding defines:

- what a capability scope means;
- what claim types exist;
- which evidence can satisfy each claim type;
- dependency and supersession rules;
- domain diagnostics;
- what derived views should expose.

Megaplan supplies `MegaplanAuthorityBinding`.

Megaplan owns:

- plan revisions and task DAGs;
- sense checks;
- task attempts;
- prerequisite digests;
- dependency closure;
- `next_ready_wave`;
- batch and creative/doc cross-task policy;
- evidence satisfaction, waiver, skip, and no-op semantics;
- milestone and chain advancement;
- model routing when it affects execution;
- Megaplan repair/custody policy.

## Sibling Views

These should not be fields in the generic kernel, though they can share observation envelopes and authority decisions.

### PlanExecutionView

Megaplan-specific:

- tasks;
- task attempts;
- sense checks;
- accepted task authority;
- dependency closure;
- ready frontier;
- blocked/waived/not-applicable semantics.

### RunnerView

Composed view over process/session/heartbeat observations.

Generic observation envelopes are useful, but liveness policy should not be promoted into the kernel yet. Different Arnold run types may have different runner semantics.

### PublicationView

Separate view for branch, push, PR, merge, auth, dirty workspace, and no-push state.

Publication must be a sibling because execution can be done while publication is blocked. Branch ancestry failure must not make execution look failed.

### HumanGateView

Human decisions are generic records in the kernel. Gate policy and allowed answers are domain-specific.

### MegaplanRecoveryView

Megaplan-specific custody and repair actions over bad artifacts, stale runner state, invalid leases, invalid branch ancestry, dirty workspaces, or dependency contradictions.

Recovery policy should consume views and emit decisions. It should not mutate legacy artifacts directly.

## Deliberately Not Generalized

Do not put these in the generic substrate:

- task DAGs;
- ready waves;
- sense checks;
- chain milestone policy;
- Git branches and PR lifecycle;
- no-push semantics;
- tmux command shape;
- watchdog/superfixer taxonomy;
- prompt contracts;
- model routing policy;
- universal execution-complete enum;
- parent completion aggregation;
- a single run lifecycle enum that merges execution, runner, publication, gates, and recovery.

Promote something into the generic kernel only after two consumers prove they need the same semantics, not merely the same vocabulary.

## Core Invariants

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

## Implementation Sequence

### 0. Freeze The Known Incident

Before architecture work, close the current exploit paths:

- `no_pending_execution` replay must preserve original dispatch scope;
- `reconcile_latest_execution_batch` must preserve original dispatch scope;
- creative/doc mode must have explicit bounded scope or be quarantined;
- add a VibeComfy incident fixture.

### 1. Inventory Authority Readers

Add a command or module that inventories every source for a run and marks each as:

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
- watchdog reports;
- repair sidecars;
- Git/PR observations;
- process/session observations;
- current `run_state`, repository, compatibility, and WAL readers.

### 2. Define Kernel Contracts

Define:

- event envelope;
- evidence envelope;
- observation envelope;
- capability grant;
- subject attempt;
- coordinator fence;
- decision record;
- quarantine record;
- projection metadata;
- idempotency and CAS rules.

Do this before implementing Megaplan scheduler changes.

### 3. Build Legacy Adapters And Shadow Views

Build read-only adapters over current artifacts. Imported legacy state is never authoritative unless it carries valid revision, attempt, grant, fence, and evidence identity.

Produce:

- `RunAuthorityView`;
- `PlanExecutionView`;
- `RunnerView`;
- `PublicationView`;
- `HumanGateView`;
- `MegaplanRecoveryView`;
- composed `MegaplanPlanView` facade.

Start in shadow mode and report drift.

### 4. Add Megaplan Capability Grants

Introduce Megaplan `DispatchGrant` as a domain wrapper over generic `CapabilityGrant`.

Every worker result must echo:

- dispatch id;
- plan revision;
- coordinator fence;
- task/sense-check scope;
- prerequisite digest;
- worker identity.

### 5. Route Merge/Reconcile Through One Validator

Normal merge, failure-boundary reconcile, no-pending replay, review rework, and creative/doc merge all go through the same grant and evidence validator.

Reject or quarantine:

- off-scope updates;
- wrong revision;
- wrong dispatch id;
- stale prerequisite digest;
- unsupported creative cross-task updates;
- insufficient evidence.

### 6. Switch Frontier And Dependency Authority

Implement `PlanExecutionView.next_ready_wave` from accepted task attempts and dependency closure.

Stop computing scheduler frontier from raw `finalize.json` status.

### 7. Add Sibling Views

Add `RunnerView`, `PublicationView`, `HumanGateView`, and `MegaplanRecoveryView` as separate modules.

Status can render them together, but services consume the smallest relevant view.

### 8. Rewire Consumers

Move these through shadow, warn, enforce:

- execute scheduler;
- merge/reconcile;
- chain advancement;
- cloud status;
- watchdog;
- repair loop;
- PR/publication wait handling;
- human override handling.

### 9. Second Consumer Proof

Before broadening the generic substrate, apply the kernel to one non-Megaplan consumer:

- native pipeline run;
- durable operation supervisor;
- generic agent run.

Promote semantics only when that second consumer proves they are shared.

### 10. Delete Compatibility Paths

Delete duplicate classifiers and direct artifact readers only after enforce-mode equivalence tests pass.

Targets:

- raw `finalize.json` completion readers;
- raw `execution_batch_*.json` authority readers;
- replay paths that merge old artifacts into authority;
- duplicate cloud status classifiers;
- duplicate run-state classifiers not backed by composed views;
- repair mutations that bypass authority decisions.

## Changes To Existing Plan

The earlier docs were directionally right but too broad in places.

Corrections:

- Replace "one canonical reducer" with "one authority kernel plus domain reducers/views."
- Keep publication as a sibling view, not part of generic `RunAuthorityView`.
- Keep liveness policy in `RunnerView` until a second consumer proves shared semantics.
- Treat human decisions as generic records, but gate policy as domain-specific.
- Treat parent/child refs as generic identity, but aggregation as domain-specific.
- Keep `derive_plan_view(plan_dir, workspace, process_probe, git_probe)` as a compatibility facade, not the canonical reducer API.
- Do not put every heartbeat into the control stream; authority decisions reference observation digests.
- Consumers should use the smallest relevant view, not always the whole `MegaplanPlanView`.

This is the structure to implement against.
