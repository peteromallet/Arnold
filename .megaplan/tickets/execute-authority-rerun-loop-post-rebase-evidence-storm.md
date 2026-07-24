# Execute authority rerun-loop after a base-refresh rebase (evidence-SHA storm)

Status: open engine bug — needs a dedicated megaplan (~1–2 days). Surfaced via
`superfixer-debug` on cloud session `progress-auditor-stage-metrics`
(2026-07-05). The chain was unblocked pragmatically (accept-and-advance + T10
doc commit); this brief captures the root cause for a proper fix.

## Problem

When a milestone branch is **rebased onto an advanced base branch** mid-run (the
superfixer's base-refresh), the execute-phase **authority-divergence check enters
a rerun loop it cannot escape**: execute re-runs its tasks, freshly-produced
evidence is flagged `stale_evidence:head_mismatch:task_files_changed` (and
compounding `missing_output:commands_run:<cmd>`), the plan blocks with
`retry_strategy:rerun_phase`, execute re-runs wholesale, diverges again — never
settling. Observed: **428 `authority_divergence` events** in one session, attempt
counter climbing, all while the work was genuinely complete and in the base.

## Evidence (this session)

- Plan `progress-auditor-stage-20260704-1400`, milestone m1. Base advanced
  (`editible-install` 3bf4c4e0 → a8fa9743) during execute; chain rebased the
  milestone branch onto the new base (`sync_state clean`).
- Execute + finalize both committed; tests pass 61/61; PR #140. Yet 428
  `authority_divergence` events, plan stuck at `current_state=blocked`.
- **Key asymmetry:** at a SETTLED head, `effective_execute_completed_task_ids`
  corroborates the done tasks cleanly (T1–T9 = 9/12). The divergence is
  TRANSIENT — it fires only DURING the rerun loop while the live HEAD is moving.
- After the run is stopped, the same check at the settled head passes for the
  substantively-done tasks.

## Root-cause mechanism (two coupled bugs)

### Bug A — execute rerun has no per-task resume; whole phase re-runs
`_block_for_execute_authority_divergence` (`auto.py:2517-2567`) writes
`resume_cursor={"phase":"execute","retry_strategy":"rerun_phase"}`. That cursor
is consumed **only as advisory prompt text** in `prompts/execute.py:~156-168`
("Focus on the remaining tasks… return task_updates for ALL tasks"). There is no
code path that hard-skips already-corroborated tasks — the worker is re-dispatched
wholesale each iteration, re-committing per-task artifacts, moving the live HEAD.

Callers of the divergence block: `auto.py:3645` (post-done), `auto.py:3779`
(orphaned-active_step clearance), `auto.py:4879` (post-execute success). The main
driver loop is `auto.py:~3407` (`while iteration < max_iterations`).

### Bug B — `current_head` resolves to the live moving tip during the rerun
`_resolve_execute_authority_current_head` (`authority_readers.py:427-443`) returns
`actual_head` (live git HEAD) when the recorded execution head is an ancestor of
live (lines 438-440). As the rerun commits task-by-task, live HEAD advances past
where earlier-task evidence was captured.

The freshness gate `_head_is_fresh_in_execution_window`
(`task_satisfaction.py:323-335`) checks `observed ancestor of current` AND
`base ancestor of observed`. For pure same-line ancestors this *should* pass — so
linear advancement alone is not the full explanation. The actual transient
failure is one of (NOT yet pinned — this is the investigation work):
- evidence captured at the **base head** (not the task's own commit), so
  `observed_head != current_head` still trips `task_satisfaction.py:306-313`;
- evidence refs orphaned by a mid-run rebase/force-push (failing the ancestor
  check);
- the compounding `missing_output` path (Bug C).

### Bug C — `commands_run` matching is exact-string AND head-gated
`_ref_matches_declared_output` (`task_satisfaction.py:387-396`) matches
`commands_run` by exact `command == value` (no normalization). Matching runs
against `effective_refs`, built at `task_satisfaction.py:~126-128` via
`_prefer_fresh_linked_refs(linked_refs, per_ref_stale)`, which **drops every ref
that failed the freshness window before matching**. So a command that genuinely
ran, captured at an older intermediate head, is excluded from `effective_refs`
and then reported as `missing_output:commands_run:<cmd>` — a head-dependent, not
head-independent, double-penalty compounding the storm.

## Sibling bug (fixer layer — hunt siblings per superfixer-debug)

### Bug D — dispatch gate has no pid-liveness probe (zombie `active_step`)
`_plan_has_live_active_step` (`chain/__init__.py:3318-3327`) checks only
*presence* of `phase`/`worker_pid`/`pid`/`session_id` — never whether the pid is
alive. A dead execute worker leaves a zombie `active_step` that:
- makes `_blocked_plan_replay_would_be_redundant` (`chain/__init__.py:3330`)
  return False → the chain falls through to resume, but the dispatcher sees an
  "in-flight" execute and never launches the designed `rerun_phase` recovery;
- the only clearer, `_clear_orphaned_active_step` (`auto.py:2659`), is gated on
  `recommended_action` set solely by `build_phase_obsensability`/`_pid_alive`
  (`_core/phase_runtime.py:~288`), which runs ONLY from the `status` CLI
  (`cli/status_view.py:~796,869`) — unreachable from `chain start`.

So a dead-PID `active_step` is structurally un-clearable by the watchdog's only
primitive (re-run `chain start`). This is the bug that turned Bug A/B/C from
"self-healing rerun" into "permanently stuck, needs-human."

## Proposed fix directions (in priority order; each needs validation)

1. **Per-task resume on authority divergence (fixes Bug A — the loop boundary).**
   Make `rerun_phase` actually skip corroborated tasks: have the execute dispatch
   honor the corroboration set and resume at the first uncorroborated task, not
   re-dispatch wholesale. Touch `auto.py:2545` (cursor) + the execute dispatch
   consumer in `prompts/execute.py` and the dispatch site. This is the correct
   structural fix; largest change.

2. **Pid-liveness probe in the dispatch gate (fixes Bug D — the zombie).**
   Add a real `kill(pid,0)`/`os.path.exists(/proc/<pid>)` check to
   `_plan_has_live_active_step` (`chain/__init__.py:3318`), and/or route
   chain-start reconciliation through the same orphan-clear + observability the
   `auto` driver uses. Stops the dead-PID-zombie class. Likely the cheapest
   high-value fix.

3. **Robustify `current_head` resolution + command matching (fixes Bug B/C —
   the transient storm).** Candidates (NOT confirmed — the exact mechanism must
   be pinned first by observing a live run, see Reproduce):
   - evaluate execute authority only at a SETTLED head (not mid-rerun);
   - pass full `linked_refs` (not just `effective_refs`) to
     `_missing_declared_outputs` for content-class fields so a head-stale but
     content-correct record isn't double-penalized (`task_satisfaction.py:~128`).
   - **Ruled out:** a `git merge-base` fallback for an orphaned
     `execution_baseline.head` (`execute_execution_window`,
     `authority_readers.py:283`). In this session the recorded base WAS a valid
     ancestor at the settled head, so that fallback wouldn't have fired — the
     storm is not an orphaned-base problem.

## Reproduce / validate

- repro plan: any multi-task execute whose milestone branch gets rebased onto an
  advanced base mid-run.
- in-memory harness (what was used to disprove the merge-base hypothesis):
  ```python
  from arnold_pipelines.megaplan.auto import _execute_completion_authority
  from arnold_pipelines.megaplan.orchestration.authority_readers import (
      effective_execute_completed_task_ids,
  )
  # load plan state + finalize tasks, call both at a SETTLED head vs a
  # mid-rerun head; corroborated set should match — divergences are the gap.
  ```
- success criterion: a plan that hits execute authority divergence after a
  base-refresh rebase converges within the normal iteration budget without
  human intervention, AND a dead execute worker's `active_step` is cleared and
  re-dispatched automatically.

## Related artifacts

- Needs-human + repair-data for this session (box):
  `/workspace/.megaplan/cloud-sessions/repair-data/progress-auditor-stage-metrics.*`
- Plan: `/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/plans/progress-auditor-stage-20260704-1400`
- PR #140 (merged): `megaplan/progress-auditor-stage-metrics/m1` → `editible-install`.
