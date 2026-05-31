# Sisypy Run Frictions - 2026-05-21

Context: while running the Sisypy `sisypy-undetermined-recurring-run-semantics` plan from a nested, untracked project directory, the product work completed, but several Megaplan operator frictions made the run need more babysitting than it should.

## Observed Frictions

- The project directory was not itself a git repository, so snapshot and audit checks repeatedly emitted `Project directory is not a git repository`. This was true but not actionable for the operator because the directory was intentionally nested/untracked inside a larger workspace.
- Execute batches completed real code work, but the execution quality gate blocked because some per-task `task_updates[]` entries lacked `files_changed` and `commands_run`, even when batch-level metadata had enough information.
- A review pass correctly found a real implementation miss: `load_evidence_pack()` was dropping `capture.notes` instead of loading it into `EvidencePack.capture_notes`.
- After the rework fix landed, execute blocked again on stale metadata for an earlier completed task. The second rework pass was metadata repair only.
- The final review summary reported `16/18` success criteria passed with no rework items. That is not wrong, but it leaves the operator without a crisp explanation of which two criteria were not counted and whether they were skipped, advisory, or irrelevant.

## Desired Product Shape

- Quality gates should distinguish implementation blockers from bookkeeping blockers in user-facing status and recommended actions.
- If per-task metadata is missing but batch-level metadata is present, Megaplan should either backfill it automatically or emit a targeted repair command/report.
- Non-git project directories should produce one clear capability warning, not repeated advisory noise across every observation/audit boundary.
- Review summaries should explain partial success counts when they still mark the plan done.

## Follow-up Tickets

This note is paired with local Megaplan tickets created on 2026-05-21 for the specific improvements above.
