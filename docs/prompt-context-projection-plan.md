# Prompt Context Projection Plan

Ticket: `01KT4XBW2TBWWEKNZTX5DP35B6`

## Root Cause

Execute prompts can grow without a meaningful bound because durable JSON ledgers are passed directly into prompt templates. The observed failure was a huge `finalize.json` rendered through raw JSON dumps into execute prompts. The actual root is broader: persistent artifacts and prompt context are different products, but the current code often treats the artifact itself as the prompt payload.

Durable artifacts need full fidelity for resume, reporting, receipts, merge, review, and debugging. Prompt context needs to be purpose-specific, compact, task-scoped, worker-readable, and budgeted.

The fix is not to truncate `finalize.json` or move everything behind a path. The fix is to project artifacts into the communication shape each worker needs, include references to full provenance, and enforce prompt budgets at dispatch.

## Core Principle

Full artifacts stay on disk. Prompts receive:

- the current decision surface inline
- nearby history summarized inline
- full provenance as readable file references
- a final prompt-size guard before the model call

Path-only prompts are not acceptable for execute or review. If essential inline context alone exceeds budget, fail clearly instead of silently making the worker blind.

## Scope

Apply this to the surfaces that raw-dump execution/review ledgers today:

- `megaplan/prompts/execute.py`
- `megaplan/pipelines/doc/prompts/execute_doc.py`
- `megaplan/pipelines/creative/prompts/execute_creative.py`
- creative variants inheriting those partials, including joke
- `megaplan/prompts/review.py`
- `megaplan/prompts/review_doc.py`
- `megaplan/prompts/review_joke.py`
- rework execute helpers that currently depend on full `review.json`
- worker dispatch paths in Codex, Hermes, Shannon, and `prompt_override`

Planning, critique, gate, and tiebreaker prompts may have similar future pressure, but this ticket should not sprawl into every prompt that happens to use JSON.

## Artifact Roles

`finalize.json` remains the authoritative execution ledger. It should stay complete and durable. Execute projections extract active tasks, compact completed-task carry-forward, user actions, sense checks, baseline failures, watch items, `meta_commentary`, file hints, and references.

`execution_batch_*.json` remains the recovery checkpoint. Execute prompts should inline the active batch and checkpoint path, then reference the full checkpoint file.

`execution.json` remains the aggregate execution result. Review projections extract `task_updates[]` fields such as `task_id`, `status`, `executor_notes`, `files_changed`, and `commands_run`, plus top-level deviations and changed-file summaries.

`execution_audit.json` remains the audit record. Review projections inline blocking findings fully enough to act on them, summarize non-blocking findings, and reference the full file.

`review.json` remains the verdict and rework ledger. Rework execute prompts should not dump it wholesale. They should inline verdict summary, criteria/task verdict summaries, actionable rework items, affected files, and acceptance criteria.

`gate.json`, `gate_carry.json`, and `plan_v*.meta.json` remain provenance. Prompt projections inline only active constraints, gate verdict, settled decisions, success criteria, and material warnings.

## Projection Shape

Add a small shared module such as `megaplan/prompts/projections.py`, but keep it pragmatic. Shared helpers should handle repeated mechanics; prompt-specific extraction should stay near the prompt when it is unique.

Useful shared pieces:

- `compact_text(value, limit, source_path, field_path)`: prose-only truncation with omitted count and source location.
- `compact_list(items, max_items, item_projector, source_path, field_path)`: list projection with omitted count and source location.
- `artifact_reference_block(refs)`: renders labeled absolute paths with roles, and optionally a hash or key path.
- task projection helpers for common fields: ID, status, kind, description, dependencies, file hints, acceptance notes.

Projection outputs should be structured dictionaries or dataclasses first, then rendered into prompt blocks. This keeps tests field-based and lets rendering adapt to worker capability.

Do not build a large abstract projection framework upfront. Start with execute and review projections, then extract only the utilities that repeat across core/doc/creative variants.

## Worker Capability And Path Contract

Artifact references only work when the selected worker can read them. Prompt construction needs an explicit capability input, even if it starts simple:

- `has_file_tools`
- `can_read_plan_dir`
- `can_read_project_dir`
- `can_write_checkpoint`
- final prompt guard location

References should be absolute, resolved paths. If a projection references a file that the selected worker cannot read, either inline the required context or fail before dispatch with a clear configuration error.

For tool-enabled workers, references are authoritative provenance. For tool-less workers, references are not a substitute for required inline context.

### Capability Resolution

Capability must be computed by the dispatch layer, not guessed inside prompt templates. The resolver should consider:

- worker kind and model
- profile/toolset configuration
- sandbox mode
- local vs. remote/cloud execution
- whether the worker can actually read `plan_dir`
- whether the worker can actually read `project_dir`
- whether the worker can write the checkpoint path

Fail closed. If reachability is unknown, treat the file as unreadable and either inline the required context or fail before dispatch. Absolute paths are necessary for local readability, but they are not enough for sandboxed or remote workers.

## Execute Layer

The projected task roster becomes the execution boundary. `finalize.json` is provenance and recovery state, not the inline authority.

Always inline for active execute work:

- intent brief and notes block
- approval note and robustness level
- task IDs and exact batch framing
- ``Only produce `task_updates` for these tasks: [...]``
- ``Only produce `sense_check_acknowledgments` for these sense checks: [...]``
- task kind/status, full active task description, dependencies, file hints, and acceptance criteria
- active user-action prerequisites
- active sense-check IDs, questions, and task IDs
- settled decisions, execution-order summary, and capped `meta_commentary`
- baseline failure summary from `baseline_test_failures` and `baseline_test_command`
- relevant watch/debt items
- prior batch deviations, capped but preserving downstream task IDs and file paths
- checkpoint path and checkpoint instructions
- output JSON shape and `task_updates[].status` contract
- harness guard

Inline for completed tasks:

- task ID, status, touched files, commands run, and short result summary
- dependency-relevant executor notes, preserving file paths and downstream task IDs
- count of omitted completed tasks

Reference:

- full `finalize.json`
- full completed task ledger/checkpoint files
- full prior command logs
- unrelated sense-check history
- full gate/review/meta files

The current batch doc and creative prompts already include active batch context and then also raw-dump full `finalize.json`; remove the redundant full dump and replace it with artifact references. Core batch execute has a different leak: it dumps `completed_tasks` wholesale. That should become capped completed-task carry-forward rather than raw task dictionaries. The non-batch execute path needs a `mode="full"` projection that projects all active tasks under global caps.

Projection bounds redundant and historical context. It does not make arbitrarily large active work fit. If the active task descriptions, acceptance criteria, and sense checks alone exceed budget, the remedy is smaller batches or smaller milestones, with the guard failing clearly as the backstop.

## Doc Pipeline

Doc execution follows the execute rule, with document continuity added inline.

Keep inline:

- current section/task brief
- output path and current document artifact path
- completed section titles/task IDs
- compact continuity notes from previous sections
- active doc-specific acceptance criteria

Reference full drafts only when the worker has file tools and the draft is too large. For review of generated documents, the output document itself is primary evidence; it must stay inline for tool-less reviewers.

## Creative Pipeline

Creative execution needs taste and constraint continuity, but not full ledgers.

Keep inline:

- active creative brief
- active constraints, stance, stop conditions, and schema
- compact prior gate/review carry
- latest relevant critique summary
- output format

Reference full gate, review, meta, finalize, and long creative histories. Standardize creative execute on the same gate summary path before applying projections; do not keep a direct full `gate.json` dump in creative when core execute uses a summary.

## Review Layer

Review needs more evidence than execute. It should be compact, not blind.

Always inline:

- task roster with statuses and acceptance criteria
- success criteria extracted from plan artifacts
- executor claims, touched files, and commands run
- active executor notes with enough room for rationale
- sense-check questions and executor acknowledgments
- blocking audit findings with actionable detail
- review rubric and output schema
- artifact reference block

Inline or reference based on capability:

- code diff: inline under the existing small-diff threshold; otherwise require tool access or fail
- doc/creative output files: inline for tool-less reviewers; reference only for tool-enabled reviewers when over a high cap
- non-blocking audit findings: summarize with count and examples, reference full file
- full `execution.json`, `execution_audit.json`, and `finalize.json`: reference for tool-enabled reviewers

Rework execute prompts should replace the full `review.json` dump with verdict summary, criteria pass/fail counts, task-level reviewer verdicts, actionable rework items, affected files, and a reference to full `review.json`.

## Finalize Layer

Finalize is different. When the finalize worker lacks file tools, the full approved plan text and required output contract must remain inline. The plan text is the primary input, not optional provenance.

Rule:

- Tool-less finalize: keep full plan text, schema, task field guidance, gate essentials, and required context inline.
- Tool-enabled finalize: references may be used for secondary provenance, but the task-decomposition input still needs enough inline specificity.
- If required finalize context exceeds budget, fail with a clear error recommending a smaller milestone or a tool-enabled finalize worker. Do not silently summarize the approved plan into something weaker.

## Dispatch Guard

Projections are the structural fix. Dispatch guards are the systemic backstop.

Primary guards must run on the final prompt string immediately before the model call:

- Codex: after final `prompt` construction in `megaplan/workers/_impl.py` and before `run_command`.
- Hermes: after worker-side appends such as web-search, output-file, and schema guidance in `megaplan/workers/hermes.py`, before `run_conversation`.
- Shannon: after `_append_json_output_contract` in `megaplan/workers/shannon.py`, before writing/sending the prompt.

Secondary guard:

- `run_step_with_worker` in `megaplan/workers/_impl.py` should guard supplied `prompt_override` values. This is a backstop for arbitrary prompt producers such as tiebreakers, reprompts, or fanout paths, not the primary enforcement point for worker-built prompts.

The guard should report prompt characters, conservative approximate tokens, thresholds, worker kind/model/profile, phase, and task context when available. It should warn below the hard limit and raise `LLM_CALL_ERROR` before dispatch above the hard limit. The error should point at prompt projection fixes, not model failure.

Thresholds should be configurable. Defaults should be conservative and model-aware where possible; if only character counts are available, estimate tokens conservatively at 3 chars/token and leave room for worker-side suffixes.

Initial defaults:

- hard limit: 300,000 characters for execute/review worker prompts
- warn limit: 240,000 characters
- reserved suffix margin: 20,000 characters
- finalize hard limit: model-specific; tool-less finalize may legitimately be larger because full approved plan text is primary input

These numbers are guardrails, not model truth. If model-specific context windows are available, the guard should derive limits from the model context budget minus reserved output and suffix margins.

Guard errors must be phase-aware. For execute/review oversize prompts, point at projections and batch sizing. For tool-less finalize oversize prompts, point at smaller milestones or a tool-enabled finalize worker, not at summarizing away the approved plan.

This guard bounds one prompt dispatch. It does not bound cumulative session context across multi-turn Codex/Shannon sessions. Session-context bloat is a separate problem and not solved by this ticket.

## Implementation Plan

1. Replace brittle prompt snapshots with behavioral assertions where they would block projection work.
2. Add projection utilities and capability-aware rendering support.
3. Replace raw execute-context dumps in core execute prompts, feeding existing partials such as prerequisite/review/execution-context blocks instead of creating parallel carry-forward paths.
4. Replace raw execute-context dumps in doc and creative execute prompts.
5. Replace raw review/rework-context dumps in review, review-doc, review-joke, and rework execute prompts.
6. Add primary final-prompt guards to every path into Codex `run_command`, Hermes `run_conversation`, and Shannon prompt dispatch, including repair/retry prompts.
7. Add the secondary `prompt_override` guard.
8. Add large synthetic artifact regression tests.
9. Run targeted tests for execute, doc execute, creative execute, review, finalize, and worker dispatch.

## Test Plan

Regression coverage should prove:

- large `finalize.json` is not rendered wholesale into execute prompts
- active task descriptions, dependencies, acceptance criteria, and sense checks remain inline
- completed-task summaries are capped but preserve dependency-relevant file paths and task IDs
- ``Only produce `task_updates` for these tasks: [...]`` remains character-compatible with `_mock_payloads.py:_task_ids_from_prompt_override`, or that parser is updated in lockstep
- ``Only produce `sense_check_acknowledgments` for these sense checks: [...]`` remains present
- artifact reference blocks include readable absolute paths
- doc and creative batch prompts do not raw-dump `finalize.json`
- review prompts retain enough inline evidence to judge work
- review-doc and review-joke keep output content inline when the reviewer lacks tools
- finalize prompts remain self-contained for tool-less workers
- final prompt guards catch oversize prompts after worker-side suffixes are appended
- arbitrary `prompt_override` calls are budget-guarded
- full persisted artifacts are unchanged by projection

Known test work:

- Replace exact-string snapshot tests that duplicate prompt templates with behavioral assertions on required/forbidden content.
- Add synthetic large-artifact fixtures instead of checking in a huge real fixture.
- Add direct tests for doc batch, creative batch, finalize prompt construction, and review criteria prompt variants.

## Acceptance Criteria

- No normal execute path raw-dumps full `finalize.json`, `review.json`, `gate.json`, or completed-task ledgers.
- Review paths use compact evidence projections rather than raw execution ledgers.
- Rework execute paths communicate verdict/rework essentials without dumping full `review.json`.
- Workers receive readable artifact references when they have file tools.
- Tool-less workers keep required primary evidence inline or fail clearly before dispatch.
- A large synthetic execution plan stays below the configured prompt budget.
- Final prompt guards prevent oversized prompts from reaching model APIs.
- Full JSON artifacts remain complete on disk.

## Judgement Call

The elegant version is not "make `finalize.json` smaller" and not "just mention the JSON file in the prompt." It is a communication contract:

- ledgers preserve everything
- prompts communicate what this worker needs now
- references preserve provenance
- guards make prompt size enforceable

That solves the root without sacrificing the context that makes the workers useful.
