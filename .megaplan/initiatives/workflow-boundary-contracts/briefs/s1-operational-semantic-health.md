# S1: Operational Semantic Health

> Superseded as an executable milestone by C1-C6. Preserved as historical
> checklist material; see the 2026-07-10 corrective reshape decision.

## Outcome

Protect current cloud runs from semantic progress failures before the full
boundary-contract architecture exists. A prep artifact/state divergence should
be detected, written as durable structured evidence, queued into the watched
repair path, and caught immediately after producer completion where possible.

This sprint collapses the detailed briefs:

- `m1-prep-semantic-health-guard.md`
- `m2-semantic-finding-custody-and-repair-queue.md`
- `m6-producer-side-immediate-verification.md`

## Scope

IN:

- Add the narrow prep semantic-health evaluator for the observed
  artifact/state divergence class.
- Add watchdog observation/dispatch integration with false-positive controls for
  active work, abandoned plans, stale artifacts, and duplicate active repair.
- Define durable `SemanticFinding` records with stable identity, rich evidence,
  lifecycle state, repair domain, suppression/waiver semantics, and current
  durable reality refs.
- Ensure semantic findings can be enqueued into the watched repair queue and
  consumed by `arnold-repair-loop` even when there is no `latest_failure`.
- Add parent/controller-side post-boundary verification for just-finished
  producers, re-reading durable disk state and enqueueing structured findings
  without mutating lifecycle state.
- Preserve the detailed acceptance criteria from the three source briefs as the
  sprint checklist.

OUT:

- Broad phase coverage.
- The full reusable boundary contract model.
- Chain/PR/cloud custody contracts.
- Public workflow boundary conformance.

## Locked Decisions

- This sprint is a bridge toward `BoundaryContract`, not the final abstraction.
- Activity/liveness alone never marks a boundary healthy.
- Findings are cleared by evaluators proving the contract is satisfied, not by
  repair code declaring success.
- Producer-side verification is non-mutating except for evidence and repair
  request writes.
- Dispatch is separately gated from observe.

## Done Criteria

1. The prep artifact/state divergence shape produces a structured finding and
   can dispatch repair on the same watchdog scan when dispatch is enabled.
2. Healthy prep, fresh active prep, abandoned plans, and duplicate active repair
   do not produce unsafe dispatch.
3. `SemanticFinding` serializes/reloads losslessly, has stable identity, and
   preserves newer evidence for repeated signatures.
4. Findings land in the repair queue watched by `megaplan-repair-trigger.path`.
5. `arnold-repair-loop` context includes semantic findings without requiring
   `latest_failure`.
6. Producer-side verification catches the prep divergence immediately after
   boundary completion and enqueues nothing for still-consistent completions.
7. Tests cover false-positive controls, queue path correctness, dedupe,
   disabled dispatch, and eventual-consistency/read-stability behavior.

## Touchpoints

- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
- `arnold_pipelines/megaplan/cloud/repair_requests.py`
- `arnold_pipelines/megaplan/cloud/repair_contract.py`
- semantic-health module under `arnold_pipelines/megaplan/cloud/`
- `arnold_pipelines/megaplan/auto.py`
- `arnold_pipelines/megaplan/handlers/shared.py`
- `tests/cloud/`
