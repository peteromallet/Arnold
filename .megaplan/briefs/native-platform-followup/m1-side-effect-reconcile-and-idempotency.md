# M1 - Side Effect Reconcile And Idempotency

## Objective

Make native compositional resume safe around real-world side effects. A path
resume that restores Python state but ignores the worktree can resume into
corruption. This milestone wires side-effect idempotency and worktree
reconcile-on-resume into the native execution path.

## Prerequisite

Do not start until the native composition follow-up has completed through path
resume and per-attempt audit skeletons.

## Files To Change And Instructions

- `arnold/pipeline/native/runtime.py`
  Invoke reconcile checks before executing a resumed side-effecting step and
  before entering a child workflow that may own side effects.
- `arnold/pipeline/native/checkpoint.py`
  Persist enough side-effect metadata to reconcile by path and attempt.
- `arnold/pipeline/native/audit.py`
  Attach idempotency keys and side-effect class metadata to per-attempt records.
- `agentbox/reconcile.py` or a new `arnold/pipeline/native/reconcile.py`
  Move from report-only reconciliation to a safe reconcile-and-continue
  contract for known git/file operations. Include a reconcile-action table for
  each supported state: clean, dirty-with-owned-changes, dirty-with-unknown
  changes, in-progress merge/rebase/cherry-pick, branch already exists, commit
  already exists, and expected file write already applied.
- `agentbox/git_worktree.py`
  Ensure worktree state checks can distinguish clean, dirty, in-progress
  merge/rebase/cherry-pick, already-created branch, and already-created commit.
- `arnold/pipeline/effect_ledger.py` or the existing effect ledger home
  Connect idempotency-key deduplication to native step execution.
- `tests/arnold/pipeline/native/`
  Add fixtures that kill/resume around file writes and git operations.
- `tests/agentbox/` or equivalent
  Add reconciliation tests for branch creation, commit already exists,
  dirty-worktree abort, and in-progress git operation cleanup.

## Verifiable Completion Criterion

- Side-effecting steps declare or derive idempotency keys from
  `(step_path, operation, target)`.
- Resume after a completed side effect does not duplicate the external action.
- Resume after an interrupted git/file operation reconciles to a known-good
  state or fails closed with a diagnostic.
- The reconcile-action table defines the exact allowed action for each known
  state and the metadata required to choose it; unknown states fail closed
  rather than guessing.
- Composite resume invokes reconciliation for nested child workflow paths.
- Tests include at least one interrupted git operation and one interrupted file
  write.

## Risks And Blockers

- Reconcile logic must fail closed. Guessing can corrupt user work.
- A destructive operation such as reset, clean, or abort must be justified by
  owned-operation metadata from the checkpoint/effect ledger; user-authored
  untracked or dirty changes must not be silently removed.
- Worktree ownership belongs to the same project/run lease used by the worker
  fleet in M5; this milestone should preserve the hook points even before the
  fleet exists.

## Dependencies

- First milestone of this platform follow-up epic.
