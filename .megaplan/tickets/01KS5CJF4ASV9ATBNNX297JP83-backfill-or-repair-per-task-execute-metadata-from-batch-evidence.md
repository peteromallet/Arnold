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
last_edited_at: '2026-05-21T13:46:02.762926+00:00'
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

