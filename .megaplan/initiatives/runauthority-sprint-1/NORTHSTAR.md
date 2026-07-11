---
type: anchor
anchor_type: north_star
slug: runauthority-sprint-1
title: 'North Star: RunAuthority Sprint 1'
created_at: '2026-07-10T00:30:36.577953+00:00'
---

# North Star: RunAuthority Sprint 1

## End State

Arnold has the first concrete foundation for a narrow generic `RunAuthorityKernel`: claim authority is separated from mutable artifacts, known Megaplan replay/reconcile scope bugs are frozen by tests, and existing run inputs can be inventoried and projected into read-only shadow views.

The durable direction is:

```text
Evidence / Observation Layer
  -> RunAuthorityKernel
    -> RunAuthorityView
      -> MegaplanAuthorityBinding
        -> PlanExecutionView
      -> RunnerView
      -> PublicationView
      -> HumanGateView
      -> MegaplanRecoveryView
        -> MegaplanPlanView facade
```

The generic kernel owns authority mechanics only: run identity, revisions, coordinator fences, bounded capability grants, subject attempts, claims, evidence refs, validation decisions, quarantine, idempotency, CAS, projection metadata, and diagnostics envelopes. Megaplan owns task DAGs, sense checks, ready waves, batch scope, skip/no-op semantics, milestone policy, and Megaplan recovery policy.

## Non-Negotiables

- Do not build a generic god-view.
- Do not put task DAGs, PR lifecycle, tmux semantics, watchdog taxonomy, prompt contracts, or model routing policy into the generic kernel.
- Do not treat `finalize.json`, `state.json`, `execution_batch_*.json`, chain state, cloud markers, or repair sidecars as authority.
- Imported legacy artifacts are observations, claims, decisions, or projections; they are not silently promoted into authority.
- Every accepted task update must trace to explicit scope and evidence.
- `no_pending_execution`, failure-boundary reconcile, and creative/doc merge paths must not widen scope.
- Execution, runner, publication, human-gate, and recovery states must remain separable.
- Reducers must be pure: no direct filesystem, Git, process, API, or wall-clock reads.

## Explicit Non-Goals

- Do not fully rewire scheduler, chain, watchdog, repair, and publication into enforce mode in this sprint.
- Do not delete legacy artifact readers yet.
- Do not require signed warrants in Sprint 1; content hashes, identity, and evidence refs are enough for this slice.
- Do not solve every native-pipeline or generic agent-run edge before proving the Megaplan slice.
- Do not invent a universal lifecycle enum.
- Do not launch or modify unrelated VibeComfy application code.

## Allowed Temporary Bridges

- Legacy artifacts may remain written for compatibility as projections.
- Read-only shadow views may be generated from legacy files through adapters.
- Existing `ExecutionLease` may remain as coordinator exclusion while the new `CapabilityGrant` / `DispatchGrant` contract is defined.
- Existing `run_state`, store, compat, WAL, and status readers may be composed as adapters during inventory.
- Shadow/warn diagnostics may coexist with legacy status until enforcement is ready.

## Drift Signals

- The plan starts implementing a broad generic status model before freezing the Megaplan incident regressions.
- The generic kernel starts naming Megaplan tasks, PRs, tmux sessions, prompts, or repair taxonomies directly.
- Scope validation still depends on caller-supplied task lists instead of immutable grant identity.
- Legacy artifacts can still be re-merged into current authority without revision, attempt, grant, fence, and evidence identity.
- Publication or liveness failure is allowed to imply execution failure.
- The sprint produces only prose but no tests, inventory command, contracts, or shadow view code.
