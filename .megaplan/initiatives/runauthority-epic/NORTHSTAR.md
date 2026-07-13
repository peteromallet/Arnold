---
type: anchor
anchor_type: north_star
slug: runauthority-epic
title: 'North Star: RunAuthority Epic'
created_at: '2026-07-10T01:30:00+00:00'
---

# North Star: RunAuthority Epic

## End State

Arnold has a narrow generic `RunAuthorityKernel` and a Megaplan binding that make run authority explicit, scoped, replayable, and enforceable. Mutable artifacts such as `finalize.json`, `state.json`, execution batches, chain state, cloud markers, watchdog reports, repair sidecars, Git/PR state, and process liveness are treated as observations, claims, decisions, or compatibility projections, never as authority by themselves.

The epic should finish with:

- known split-authority regression paths frozen by tests;
- a command/module that inventories authority-relevant inputs for a run;
- initial generic kernel contracts and deterministic reducers;
- read-only shadow views for execution, runner, publication, human gates, and recovery;
- Megaplan dispatch grants and a unified merge/reconcile validator in enforceable form;
- scheduler/frontier decisions derived from accepted task attempts and dependency closure;
- consumers migrated through shadow/warn/enforce where practical;
- duplicate raw-artifact authority reads either removed or quarantined behind compatibility projections.

## Architecture

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

The generic kernel owns authority mechanics only: run identity, revisions, coordinator fences, bounded capability grants, subject attempts, claims, evidence refs, validation decisions, quarantine, idempotency, CAS, projection metadata, and diagnostics envelopes. Megaplan owns task DAGs, sense checks, ready waves, batch scope, skip/no-op semantics, milestone policy, model routing policy, and Megaplan recovery policy.

## Sprint Sequence

Sprint 1 builds the foundation: freeze known regressions, inventory authority inputs, define kernel contracts, and produce read-only shadow views.

Sprint 2 builds the enforcement spine: Megaplan dispatch grants, unified merge/reconcile validation, and frontier/dependency authority from accepted task attempts.

Sprint 3 migrates consumers and cleans up: sibling operational views, shadow/warn/enforce rewiring, second-consumer proof where feasible, and deletion/quarantine of duplicate raw authority readers.

## Non-Negotiables

- Do not build a generic god-view.
- Do not put task DAGs, PR lifecycle, tmux semantics, watchdog taxonomy, prompt contracts, or model routing policy into the generic kernel.
- Do not treat legacy artifacts as authority.
- Every accepted update must trace to run revision, subject attempt, capability grant, coordinator fence, and evidence.
- Recovery cannot silently reinterpret or reapply stale artifacts.
- Execution, runner, publication, human-gate, and recovery states must remain separable.
- Reducers must be pure: no filesystem, Git, process, API, or wall-clock reads.
- Compatibility projections may remain, but authority must not be reconstructed unquestioningly from them.

## Completion Signal

The epic is done only when Megaplan can explain and enforce task authority through grants, attempts, evidence-backed decisions, and deterministic views, while operator status/debug output separates execution authority from runner liveness, publication state, human gates, and recovery custody.

