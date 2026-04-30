# Execution Checklist

- [ ] **T13:** Read user_actions.md. For each before_execute action, programmatically verify completion using bash tools — grep .env for required keys, query the migrations table, curl the dev server, etc. Reading the file does NOT count as verification; you must run a command. For actions that genuinely cannot be verified mechanically (manual UI checks), explicitly ask the user. If anything is incomplete or unverifiable, mark this task blocked with reason and STOP. (skipped)
  Executor notes: Skipped rework because this prerequisite was previously completed and no reviewer issue details could be read to justify changes.

- [ ] **T1:** Add SQLite and Supabase migrations for the unified `feedback` table with all Sprint 2b columns, kind/source constraints, JSON `context_snapshot`, defaults for `active` and `resolved`, timestamps, and indexes for active global feedback, epic-specific feedback, and unresolved observations. (skipped)
  Depends on: T13
  Executor notes: Skipped rework because reviewer details could not be read and the read-only environment prevents file edits. Prior evidence indicates migrations were added and covered.

- [ ] **T2:** Extend `Store` protocols and SQLite/Supabase adapters with feedback and observation persistence methods, JSON serialization for `context_snapshot`, and `load_hot_context(epic_id: str | None)` that always loads active `style` and `process` feedback and conditionally loads current-epic feedback plus the last 5 unresolved observations. (skipped)
  Depends on: T13, T1
  Executor notes: Skipped rework because reviewer details could not be read and the environment prevents verification or edits. Prior evidence indicates adapter and hot-context behavior was implemented and tested.

- [ ] **T3:** Update the turn loop to call `store.load_hot_context(active_epic_id)` even when no epic is active, preserve existing hot-context keys, and include active feedback and unresolved observation counts in prompt snapshots and hot-context summaries. (skipped)
  Depends on: T13, T2
  Executor notes: Skipped rework because shell commands and writes are unavailable. Prior evidence indicates no-epic hot context was wired through the loop.

- [ ] **T4:** Enhance body parsing helpers to produce outlines with nested `###` and deeper subheadings under parent `##` sections, accurate section line counts, and body search results with 1-based line numbers, matching line, surrounding context, and parser-derived section attribution that respects fenced code blocks. (skipped)
  Depends on: T13
  Executor notes: Skipped rework because the environment prevented reading reviewer details, editing parser code, or rerunning parser tests.

- [ ] **T5:** Add and register read tools `get_body_outline(epic_id)` and `search_in_body(epic_id, query, context_lines=2)` with stable empty-result and `epic_not_found` response shapes, exports, and loop/tool-registry wiring. (skipped)
  Depends on: T13, T4
  Executor notes: Skipped rework because the environment prevented inspection and edits. Prior evidence indicates body read tools were registered and tested.

- [ ] **T6:** Implement feedback and agent-observation tools: `save_feedback`, `apply_feedback`, `deactivate_feedback`, `list_feedback`, `record_observation`, `list_observations`, and `mark_observation_resolved`; enforce user-feedback vs observation kind separation, auto-fill observation source/turn/context metadata, and import the tool module in the loop so tools register in all modes. (skipped)
  Depends on: T13, T2, T3
  Executor notes: Skipped rework because no files can be modified and tests cannot be run. Prior evidence indicates feedback and observation tool contracts were covered.

- [ ] **T7:** Build source-controlled Sprint 2b system-prompt content from `planning-bot-spec.md`, covering persona, communication style, feedback discipline, body-search workflow, checklist depth guidance for all 18 items, show-changes behavior, end-of-turn checks, and self-observation guidance; update `DEFAULT_PROMPT_VERSION`. (skipped)
  Depends on: T13, T3, T5, T6
  Executor notes: Skipped rework because prompt files cannot be edited or verified in the current sandbox. Prior evidence indicates prompt coverage existed.

- [ ] **T8:** Update the full model-call boundary for system prompts: add `system: str | None` to `Model.complete_turn`, update fake and Anthropic model adapters, record/replay the system prompt in ledger request bodies/summaries, and adjust existing model/replay tests without changing their intent. (skipped)
  Depends on: T13, T7
  Executor notes: Skipped rework because model plumbing files cannot be edited or tested. Prior evidence indicates system prompt propagation was covered.

- [ ] **T9:** Implement pure end-of-turn check logic for no message sent, no tool calls/progress, empty response, body unchanged when expected, and checklist stall; send a default acknowledgment after substantive tool work without outbound `send_message`, preserve the existing empty-response error path when no substantive work occurred, and log non-blocking findings to `system_logs`. (skipped)
  Depends on: T13, T8
  Executor notes: Skipped rework because end-of-turn code cannot be inspected or modified and tests cannot run.

- [ ] **T10:** Verify and cover show-changes and editorial loop behavior: keep edit diffs in `edit_epic` results/audit records, rely on prompt/scripted model behavior rather than response rewriting, and add scripted integrations for `search_in_body -> get_epic -> edit_epic`, `render_epic`, explicit feedback save, confirmed feedback save, feedback apply/reload, observation reload/resolution, and default acknowledgment. (skipped)
  Depends on: T13, T5, T6, T8, T9
  Executor notes: Skipped rework because scripted integration tests cannot be inspected, edited, or rerun. Prior evidence indicates tool sequences and lifecycle flows were covered.

- [ ] **T11:** Add deterministic unit, adapter, and integration tests for Sprint 2b behavior, including body parser/search edge cases, feedback and observation store contracts, no-epic global feedback hot context, model system prompt plumbing, and optional LLM-eval fixture scaffolding gated behind an explicit marker or environment variable. (skipped)
  Depends on: T13, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10
  Executor notes: Skipped rework because deterministic test files and LLM-eval scaffolding cannot be inspected or modified in this sandbox.

- [ ] **T12:** Run verification and fix failures until targeted checks pass: `pytest tests/test_body_parser.py tests/test_editorial_polish_tools.py`; `pytest tests/test_sqlite_store.py tests/test_supabase_adapters.py tests/test_supabase_store.py`; `pytest tests/test_anthropic_model.py tests/test_anthropic_replay.py tests/test_run_turn.py`; `pytest tests/test_editorial_loop.py tests/test_editorial_polish_loop.py tests/test_mid_turn_messages.py tests/test_run_turn_hooks.py`; then full `pytest`. Also write a short throwaway script that exercises the core Sprint 2b feedback/search/end-of-turn path, run it, confirm behavior, and delete the script before finishing. Do not create new persistent test files in this final verification task. (skipped)
  Depends on: T13, T11
  Executor notes: Skipped because the required verification commands and throwaway reproduction script cannot be executed or written in the current read-only, command-rejected environment.

- [ ] **T14:** Surface after_execute user_actions to the user:
- U2: After code lands and any deployment/migration process is complete, manually smoke test resident-mode Discord behavior against the configured Supabase project: explicit feedback save, proposed feedback confirmation, hot-context reload, observation recording/resolution, and default acknowledgment.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated. (skipped)
  Depends on: T12
  Executor notes: Skipped rework because after-execute user action U2 was already surfaced and no further repo edits are possible in this environment.

## Watch Items

- Do not invoke the `megaplan` CLI, activate the `megaplan` skill, or start nested plans; mentions of megaplan are repository context only.
- Global `style` and `process` feedback must load every turn, including no-active-epic and new-epic turns; this was FLAG-001.
- System prompt plumbing must update the model protocol, fake model, Anthropic adapter, ledger request body, and replay path together; this was FLAG-002.
- The Sprint 2b table schema has no `priority` column, so omit priority filtering unless the user clarifies otherwise.
- Keep `source_message_id` nullable unless existing code proves Discord-sourced feedback requires it.
- Agent observations are agent-only: no user confirmation, `source='agent_observation'`, current `turn_id`, and context snapshot should be auto-filled.
- User feedback flows differ: explicit save writes immediately; agent-proposed style/process feedback should wait for user confirmation.
- End-of-turn checks should add safety acknowledgments without rewriting normal model prose or masking empty-model-response errors.
- Prompt-driven show-changes behavior should be tested with scripted model flows, not post-processing that edits model responses.
- Preserve existing `epic`, `recent_messages`, and `recent_tool_calls` hot-context keys to avoid regressions.
- Keep deterministic tests in default CI; any live LLM evals must be behind an explicit marker or environment flag.
- Do not require the redacted Supabase service key for local unit tests or committed artifacts.
- Debt watch: avoid expanding unrelated attachment/storage reconciliation promises from earlier sprints; Sprint 2b should stay focused on editorial polish.

## Sense Checks

- **SC1** (T1): Do both migrations create exactly the unified `feedback` schema with valid constraints, defaults, JSON-compatible context storage, and indexes for global feedback, epic feedback, and unresolved observations?
  Executor note: Could not re-verify in this pass because commands are rejected; prior evidence says both migrations matched the feedback schema.

- **SC2** (T2): Can SQLite and Supabase adapters create, update, list, and hot-load feedback/observations, and does `load_hot_context(None)` include active style/process feedback while preserving existing hot-context keys?
  Executor note: Could not re-verify in this pass because commands are rejected; prior evidence says SQLite and Supabase adapter contracts were covered.

- **SC3** (T3): Does the loop use `load_hot_context` for no-epic turns and do fake-model assertions show global feedback is present before any epic is selected?
  Executor note: Could not re-verify in this pass because commands are rejected; prior evidence says no-epic hot context was wired and tested.

- **SC4** (T4): Do body helper tests prove outline line counts, nested headings, search context windows, line numbers, and fenced-code behavior match actual markdown bodies?
  Executor note: Could not re-run body helper tests in this environment.

- **SC5** (T5): Are `get_body_outline` and `search_in_body` registered, exported, and returning stable success, empty, and `epic_not_found` shapes?
  Executor note: Could not re-verify tool registration in this environment.

- **SC6** (T6): Do tool tests reject invalid kind/source mixing, update `last_applied_at` and `last_referenced_at`, deactivate feedback correctly, and resolve observations so they stop appearing in hot context?
  Executor note: Could not re-run feedback tool tests in this environment.

- **SC7** (T7): Does the prompt builder include the required Sprint 2b persona, communication style, feedback discipline, body-search workflow, 18 checklist depth items, show-changes instructions, end-of-turn checks, and self-observation guidance?
  Executor note: Could not re-inspect prompt content or rerun prompt tests in this environment.

- **SC8** (T8): Does every model caller and adapter accept/pass `system`, and do ledger audit/replay records reflect the exact system prompt or prompt version actually sent?
  Executor note: Could not re-verify model system prompt plumbing in this environment.

- **SC9** (T9): Do end-of-turn tests cover all five categories, preserve the empty-response error path, and produce the default acknowledgment only after substantive work with no outbound message?
  Executor note: Could not re-run end-of-turn tests in this environment.

- **SC10** (T10): Do scripted integrations record the required tool sequences and feedback/observation lifecycle without relying on response post-processing?
  Executor note: Could not re-run scripted integration tests in this environment.

- **SC11** (T11): Are deterministic tests sufficient for core Sprint 2b acceptance criteria, with live LLM evals isolated from normal offline pytest?
  Executor note: Could not re-verify deterministic and gated LLM-eval test coverage in this environment.

- **SC12** (T12): Do all targeted pytest commands and the full suite pass after fixing failures, and was the throwaway reproduction script run successfully and deleted?
  Executor note: No. Targeted pytest commands, full suite, and throwaway reproduction script could not be run because shell commands and writes are unavailable.

- **SC13** (T13): Were all before_execute user_actions programmatically verified before execution proceeded?
  Executor note: Could not re-run prerequisite verification in this environment; prior evidence says before_execute actions were programmatically checked.

- **SC14** (T14): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: Prior evidence says after_execute U2 was surfaced; no additional executor action was possible in this environment.

## Meta

Execute in dependency order and keep the architecture local to the existing `Store` protocol, tool registry, body parser helpers, and `run_turn` loop. The two highest-risk wiring points are no-epic hot context and system prompt propagation through every model/audit boundary. Treat the feedback schema in the Sprint 2b idea as authoritative, especially the absence of a `priority` field. Default tests should be deterministic and offline; live Supabase/Discord work is a separate human-operated smoke pass.
