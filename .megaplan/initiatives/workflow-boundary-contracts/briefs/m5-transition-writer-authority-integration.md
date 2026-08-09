# M5: TransitionWriter Authority Integration

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

Authority-increasing state and routing changes are represented as boundary
transitions and verified through `TransitionWriter` / `TransitionPolicy`.

Semantic health can detect state advances without the required decision, stale
decisions, denied decisions followed by state advance, and missing pinned
evidence.

## Scope

IN:

- Align `TransitionDecision` with `BoundaryContract` transition fields.
- Align `TransitionDecision` with `AuthorityRecord` so approvals, denials,
  delegated approvals, waivers, overrides, and revocations have actor, role,
  scope, conditions, expiry, checked evidence refs, and stale-input rejection.
- Extend transition coverage for:
  - review -> execute/done;
  - recovery routes that promote blocked or partial execution;
  - reset/reconcile routes;
  - config reroutes;
  - force-proceed/override waivers.
- Add explicit handling for partial, degraded-continue, rollback, and
  irreversible transition outcomes where the boundary type allows them.
- Ensure transition denials are structured and visible.
- Preserve SHA-pinned evidence for chain/worktree/CI where relevant.
- Add compare-and-swap / stale decision rejection where transitions depend on
  checked inputs.

OUT:

- Making BoundaryTurn the route engine.
- Removing legacy shortcuts before coverage exists.
- Solving all chain/PR/cloud transitions; those continue in M9.

## Locked Decisions

- Authority writes go through a transition writer or are explicitly deferred.
- Overrides are scoped waivers, not bypasses.
- Approval/waiver state is not boolean; it carries authority, scope, expiry,
  revocation, and checked evidence.
- Transition decisions are valid only for their checked inputs.
- Semantic health reports transition-contract failures separately from
  phase-writer failures.

## Done Criteria

1. Transition decisions reference boundary ids and checked evidence refs.
2. State advance without required transition decision produces a semantic
   finding.
3. Denied/stale transition followed by state advance produces a semantic
   finding.
4. Transition denials are operator-visible and auditor-visible.
5. Waived/partial/degraded transitions remain visible as non-green outcomes,
   with expiry or revalidation where required by the contract.
6. Existing transition policy tests pass.

## Touchpoints

- `arnold_pipelines/megaplan/orchestration/transition_policy.py`
- `arnold_pipelines/megaplan/orchestration/evidence_contract.py`
- `arnold_pipelines/megaplan/auto.py`
- review/execute/override handlers
- state locks / lease helpers
