# M2: Authority Reader Migration

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Migrate every authority-increasing reader to consult the corroborated-done predicate before treating work as done: task selection, dependency scheduling, resume, and chain advancement all resolve divergence DOWN to unknown/unsatisfied before they increase authority.

This carries forward the load-bearing invariant from old M7 without carrying forward its projection-store architecture. It closes the phantom-dependency class early, before enforcement, by ensuring a ledger-done claim with missing output or stale evidence cannot unlock dependent work.

## Scope

IN:

- Identify every authority-increasing reader that consumes task/milestone done state:
  - task selection
  - dependency scheduling
  - resume/re-drive
  - chain milestone advancement
  - plan selection/current-plan pointer reads used to advance state
- Replace asserted-done trust with calls to `is_task_satisfied(task, evidence_nucleus, current_head/code_hash)`.
- Resolve divergence DOWN: missing outputs, stale evidence, code/head mismatch, or contradictory store claims become unknown/unsatisfied, never success.
- Emit structured divergence diagnostics that name the reader, task/milestone, evidence refs, current head/code hash, and next action.
- Preserve compatibility for legacy plans by treating uncorroborated completion as unknown/legacy under the current rollout mode.
- Add the phantom-dependency regression: a dependency listed done but missing its output does not unblock dependent task execution.

OUT:

- No projection store.
- No new evidence collection.
- No reset/reconcile operation; recovery operations are handled later by M9.
- No global enforcement flip; readers change their authority semantics, not rollout defaults.

## Locked Decisions

- Authority-increasing readers must use the corroborated-done predicate.
- Divergence resolves DOWN to unknown/unsatisfied, never up to success.
- The task ledger and per-batch done claims are inputs, not standalone authority.
- This milestone keeps the invariant and drops the all-readers projection architecture.

## Open Questions

- Exact complete route list for authority-increasing readers.
- How much divergence detail appears in normal status versus debug artifacts.
- Whether legacy unknown should pause, warn, or continue for each reader before M10 rollout enforcement.

## Constraints

- Reuse M1 `is_task_satisfied(...)`; do not build a second verifier.
- Preserve resumability without infinite re-execute/re-init loops.
- Keep status reads that do not increase authority eventually consistent where safe.
- Tests must distinguish informational reads from authority-increasing reads.

## Done Criteria

1. The authority-increasing reader list is documented and covered by tests or explicitly deferred.
2. Task selection consults `is_task_satisfied(...)` before skipping completed work.
3. Dependency scheduling refuses to treat an uncorroborated dependency as done.
4. Resume/re-drive resolves stale or divergent done claims down before advancing.
5. Chain milestone advancement consults corroborated milestone/task satisfaction before advancing.
6. Divergence diagnostics are structured and operator-visible.
7. Tests cover corroborated done, phantom dependency, stale evidence, missing output, legacy unknown, resume divergence, and chain advance divergence.

## Touchpoints

- task selection / dependency scheduling modules
- `megaplan/_core/state.py`
- `megaplan/_core/workflow.py`
- `megaplan/chain/__init__.py`
- resume/re-drive paths
- execute artifacts / task ledger readers
- authority-reader and phantom-dependency regression tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the mandatory add-back that prevents silent authority increases from stale state. It is intentionally narrower than the old projection milestone, but it is still load-bearing across scheduling, resume, and chain advancement.

