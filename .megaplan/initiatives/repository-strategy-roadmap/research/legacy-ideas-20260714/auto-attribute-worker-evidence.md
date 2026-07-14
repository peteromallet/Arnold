# Auto-attribute git-diff changes to done tasks with empty `files_changed`

## Problem

When an executor reports task status `done` but emits empty `files_changed: []` (and no `commands_run`), `_check_done_task_evidence` in `megaplan/execute/quality.py` flags those tasks as `missing_task_evidence`. `build_blocking_reasons` adds a blocking reason. `state["current_state"]` stays at `finalized` instead of advancing to `executed`. The auto-driver retries forever (caught now by the new `worker_blocked` guard, but the actual run still fails).

We observed this in the reliability-20260424-235843 bake-off: both hermes-based profiles (`all-open` with kimi+glm, `all-kimi`) produced 500+ lines of real code on disk but emitted empty `files_changed` arrays for every done task. The work was correct; only the reporting was broken. claude/codex (`standard` profile) reported correctly and shipped.

The *driver-side* fix (commit `dc89aace`) is a guard rail that fails fast instead of looping. The *executor-side* fix is to recover: when the worker leaves `files_changed` empty but the worktree has unclaimed git changes, auto-attribute those changes to the done tasks so the run can proceed.

## Goal

Add an executor-side fallback that promotes uncommitted git-tracked changes to `files_changed` on done tasks whose `files_changed` is empty, when there is no other plausible owner. Mark these auto-attributed entries with metadata so audit trails distinguish "model claimed" from "system inferred".

## Requirements

### Where the change lives

In `megaplan/execute/core.py` (around the `_merge_batch_results` call site, before `_check_done_task_evidence`), or as a new helper invoked between them. Keep `_check_done_task_evidence` unchanged — its semantics are correct; we're feeding it richer task data.

### Inference rules

After `_merge_batch_results` and before `_check_done_task_evidence`:

1. Compute `unclaimed_paths`: the set of files in the worktree's `git status --porcelain` (relative to `project_dir`) that are NOT already in any task's `files_changed`.
2. Identify `unattributed_done_tasks`: tasks in this batch with `status == "done"` AND empty `files_changed` AND empty `commands_run` AND `mode == "code"`.
3. If `unclaimed_paths` is non-empty AND `unattributed_done_tasks` is non-empty:
   - **Single done task with empty evidence**: attribute every unclaimed path to that task. Set `files_changed = list(unclaimed_paths)` and add a top-level field `auto_attributed_files: true` on that task.
   - **Multiple done tasks with empty evidence**: this is genuinely ambiguous. Attribute every unclaimed path to *every* such task (permissive — the audit data is now lossy but not blocking). Set `auto_attributed_files: true` on each. Also append a `deviations` entry: `"Auto-attribution ambiguous: <N> done tasks shared <K> unclaimed files"`.
   - **No unclaimed paths** (worktree clean of unattributed changes): no change. The task remains evidence-less and `_check_done_task_evidence` will block it (correct — model said done but nothing changed).

### Out of scope

- Sense-check acknowledgment fallback (separate evidence pathway).
- Doc/joke modes (different evidence: `sections_written`).
- Honoring `commands_run` as evidence — keep current advisory behavior.
- Backporting attribution to historical batches (only run on the current batch).

### Tests

In `tests/test_execute_*.py` (or a new `tests/test_auto_attribute_evidence.py`):

1. **Single done task with empty `files_changed` + unclaimed git changes** → after attribution, `_check_done_task_evidence` returns no missing entries; `auto_attributed_files: true` set on the task.
2. **Multiple done tasks with empty evidence sharing unclaimed paths** → all tasks get the full unclaimed set, ambiguity deviation logged.
3. **Done task with empty `files_changed` + clean worktree** → still flagged as missing (correct: no work happened).
4. **Done task with already-populated `files_changed`** → untouched (no over-attribution).
5. **Skipped tasks ignored** — only `status == "done"` tasks attract attribution.
6. **Files already claimed by other tasks are excluded from `unclaimed_paths`** — prevents double-attribution.

### Logging

When auto-attribution fires, append a single deviation per affected task:
```
Auto-attributed N unclaimed file(s) to task <id> (worker reported empty files_changed): <comma-separated list, truncated>
```

This appears in `execution_audit.json` and the deviations summary so users can see attribution happened without surprise.

## Success criteria

1. A unit test simulates a hermes-style payload (done tasks with empty `files_changed`) plus a fake worktree with unclaimed changes; after attribution, the batch is no longer blocked.
2. Existing executor tests pass unchanged (additive feature).
3. `auto_attributed_files: true` is visible in the resulting `execution_batch_<n>.json` so audits can distinguish model-reported from inferred.
4. The ambiguity deviation appears when multiple done tasks claim the unclaimed pool.
5. Clean worktree → no spurious attribution; missing-evidence still blocks.

## Why "light" robustness for this bake-off

Light reduces the critique fan-out and shortens the loop, so a 2-profile run finishes faster and cheaper than the standard-robustness 4-profile bake-off we did earlier tonight. The fix surface is small and concrete; we don't need 5 parallel critique checks to catch design issues.
