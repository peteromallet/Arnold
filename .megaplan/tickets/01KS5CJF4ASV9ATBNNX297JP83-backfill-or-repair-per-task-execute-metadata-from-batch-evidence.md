---
id: 01KS5CJF4ASV9ATBNNX297JP83
title: Backfill or repair per-task execute metadata from batch evidence
status: open
source: human
tags:
- bug
- execute
- quality-gate
- observability
codebase_id: null
created_at: '2026-05-21T13:46:02.762926+00:00'
last_edited_at: '2026-05-21T20:31:00+00:00'
resolution_note: 'Reopened 2026-05-21: the previous fix only covered current-batch
  payload attribution. Astrid M8 showed stale hollow task evidence already persisted
  in finalize.json can continue to block recovery after later retry batches and quality
  resolutions.'
epics: []
---

During the Sisypy `sisypy-undetermined-recurring-run-semantics` run on 2026-05-21, execute completed real implementation work but blocked because completed task updates were missing per-task `files_changed` and `commands_run`.

Observed sequence:

- Initial execute produced working code changes and batch-level `files_changed` / `commands_run`.
- The quality gate blocked because some `task_updates[]` entries did not repeat that metadata.
- An operator note told the worker to populate per-task metadata for future/retried tasks.
- Later, after review requested a real T1 rework, the rework fix landed, but execute blocked again because stale completed task T2 still lacked both metadata fields.
- A second execute pass was metadata-repair only and reported no new code changes.

Why this is a tooling problem:

The implementation was not blocked; only bookkeeping was. The harness had enough context to make the operator path less manual: batch-level evidence, task IDs, changed files, and commands were already present in artifacts or could be targeted for repair.

Desired behavior:

1. If batch-level metadata can be attributed to exactly one task, backfill `task_updates[].files_changed` and `task_updates[].commands_run` automatically.
2. If attribution is ambiguous, report a concise metadata-repair request that names the exact task IDs and candidate files/commands.
3. Preserve the implementation/review distinction in status: e.g. `blocked_metadata` or equivalent, not a generic execute block.
4. Rework execute passes should not be forced to redo unrelated implementation just to repair stale metadata from earlier completed tasks.
5. Add a regression fixture with a done task missing per-task metadata but containing equivalent batch-level metadata.

Concrete evidence from this run:

- Plan: `sisypy-undetermined-recurring-run-semantics`
- First metadata block: missing per-task fields despite top-level batch fields.
- Rework metadata block: `Done tasks missing both files_changed and commands_run: T2`.
- Final repair pass summary: `T2 metadata repaired: files_changed=['sisypy/universal_checks.py'], commands_run populated` and `54 passed`.

Additional evidence from Astrid timeline-event-sourcing M8 on 2026-05-21:

- Plan: `milestone-8-migration-20260521-1713`.
- PR: Astrid #20, branch `epic/timeline/m8-migration-tests`.
- Execute had already completed `15/15` tasks and `7/7` batches.
- `execution_batch_3.json` and `execution_checkpoint.json` were repaired for T9, but `finalize.json` still had T9 marked `done` with `files_changed: []` and `commands_run: []`.
- `override recover-blocked` continued to fail because blocker construction and `validate_execution_evidence(finalize_data, ...)` read the stale hollow task from final evidence, not the repaired historical batch/checkpoint metadata.
- Re-running `execute --retry-blocked-tasks` did not repair T9 because retry execution was scoped to later/current work; T9 was an earlier completed batch task.
- The practical operator fix was to backfill T9 directly in `finalize.json` with `tests/timeline/test_backend_contract.py`, `tests/timeline/conftest.py`, and the passing pytest commands.

Root tooling gap:

- Evidence repair must reconcile stale hollow task records in `finalize.json`, not only the latest/current execution batch payload.
- Recovery should distinguish implementation blockers from metadata-only blockers and provide a first-class repair path that updates the canonical final evidence artifact.
- Quality blocker IDs can be regenerated for the same stale review claim after retries; recovery should dedupe semantically equivalent resolved quality blockers or verify stale claims against current file content before creating a new hard blocker.
