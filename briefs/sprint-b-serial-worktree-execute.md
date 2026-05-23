# Sprint B — Serial Worktree Execute And Crash-Safe Integration

## Outcome

Replace new execute runs with serial per-task worktree execution using the
substrate from Sprint A. The first implementation must prove one task can run in
one disposable worktree, produce a validated patch bundle, integrate as an
`mp-task:<id>` commit on the milestone checkout, and recover safely across the
critical crash boundaries.

This sprint is the core migration from batch execute to worktree-native execute.

## Locked Direction

Use the settled direction from ticket
`.megaplan/tickets/01KS3DCH9Y1NTMTWH18S98RZT4-per-task-worktree-execute-model-replace-batches-with-isolated-per-task-scratch-w.md`
and the substrate delivered by Sprint A.

Do not re-litigate:

- execute is worktree-native;
- concurrency starts at `1`;
- workers get explicit task worktree paths;
- workers do not commit;
- coordinator captures patches and integrates them;
- successful task worktrees are pruned after integration and evidence capture;
- failed/conflicted worktrees are preserved;
- Hermes remains serialized;
- conflict resolution can block in this sprint as long as evidence is preserved.

## Scope In

1. Add a task-native execute path, e.g. `handle_execute_one_task`, that replaces
   new batch execution.
2. Create one detached or task-owned worktree per task under the managed root
   using stable run/task IDs.
3. Copy required plan artifacts into the task worktree. Do not give workers
   shared writable access to `.megaplan/plans/...`.
4. Pass explicit `worktree_path` / work dir through worker dispatch. Do not rely
   on process-global work-dir override for task execution.
5. Run tasks serially with effective concurrency `1`.
6. Capture, validate, apply, commit, record, push/sync-disabled as appropriate,
   then prune successful task worktrees.
7. Preserve failed/conflicted task worktrees and patch bundles.
8. Replace resume cursor semantics from `batch_index` to task ID for new
   worktree-native plans.
9. Retire or hard-block new batch execute path after migration. Old plans must
   route through Sprint A migration behavior.
10. Implement the restartable integration state machine:

    ```text
    patch_captured
    apply_checked
    applied_to_index
    committed
    registry_recorded
    pushed
    pr_synced
    worktree_pruned
    ```

11. Add crash-injection tests for:
    - after `git apply --3way` succeeds but before `git commit`;
    - after `git commit` but before registry update;
    - mid-apply leaving conflict markers or `.git/index.lock`.

## Scope Out

- Do not add parallel execution.
- Do not implement milestone PR lifecycle beyond preserving current chain
  behavior and avoiding new sweeping commits.
- Do not implement agent conflict-resolution commands yet; blocking with
  preserved evidence is acceptable.
- Do not support concurrent Hermes execution.
- Do not implement cross-repo task routing.
- Do not support recursive submodule edits.
- Do not build rich PR body task tables yet.

## Done Criteria

1. A real-Git test runs a plan with at least three serial tasks and produces
   linear `mp-task:<id>` commits.
2. The milestone checkout is clean before and after each task integration.
3. No task patch can be applied twice across restart.
4. A crash after commit but before registry update resumes by recognizing the
   existing `mp-task:<id>` commit and marking the task integrated.
5. A crash after apply but before commit resumes by either finishing the commit
   from a known patch fingerprint or blocking with a custody report; it never
   re-runs into a dirty checkout.
6. Failed/conflicted worktrees are preserved and visible in status/custody
   output.
7. Old `execution_batch_*.json` plans do not silently execute in the new path.
8. Existing worker tests and execute tests are updated for task-native artifacts.

## Touchpoints

- `megaplan/execute/core.py`
- `megaplan/execute/timeout.py`
- `megaplan/execute/quality.py`
- `megaplan/handlers/execute.py`
- `megaplan/workers/_impl.py`
- `megaplan/workers/hermes.py`
- `megaplan/_core/workflow.py`
- `megaplan/_core/io.py`
- `megaplan/store/plan_repository.py`
- `megaplan/cli.py`
- tests under `tests/test_execute.py`, `tests/test_workers.py`, and new
  real-Git integration tests

## Anti-Scope

Do not optimize for speed before recovery correctness.
Do not push task branches.
Do not delete failed/conflicted worktrees automatically.
Do not let worker output claim integration or cleanup status.
Do not make branch/PR lifecycle part of the first working execute rewrite.
