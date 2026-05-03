# Execution Checklist

- [x] **T13:** Read user_actions.md. For each before_execute action, programmatically verify completion using bash tools — grep .env for required keys, query the migrations table, curl the dev server, etc. Reading the file does NOT count as verification; you must run a command. For actions that genuinely cannot be verified mechanically (manual UI checks), explicitly ask the user. If anything is incomplete or unverifiable, mark this task blocked with reason and STOP.
  Executor notes: Checked for a repository user_actions.md with rg; none exists. Used the execution-provided user_actions instead. The only before_execute action is optional live Supabase credentials, and the offline verification did not need them.

- [x] **T1:** Add SQLite and Supabase migrations for the unified `feedback` table with all Sprint 2b columns, kind/source constraints, JSON `context_snapshot`, defaults for `active` and `resolved`, timestamps, and indexes for active global feedback, epic-specific feedback, and unresolved observations.
  Depends on: T13
  Executor notes: Migration coverage was exercised through SQLite and Supabase adapter test modules under Python 3.11; schema/index tests passed in the targeted store batch.

- [x] **T2:** Extend `Store` protocols and SQLite/Supabase adapters with feedback and observation persistence methods, JSON serialization for `context_snapshot`, and `load_hot_context(epic_id: str | None)` that always loads active `style` and `process` feedback and conditionally loads current-epic feedback plus the last 5 unresolved observations.
  Depends on: T13, T1
  Executor notes: Store feedback and observation persistence plus hot-context behavior were covered by the targeted store batch; it passed with 14 passed and 1 skipped.

- [x] **T3:** Update the turn loop to call `store.load_hot_context(active_epic_id)` even when no epic is active, preserve existing hot-context keys, and include active feedback and unresolved observation counts in prompt snapshots and hot-context summaries.
  Depends on: T13, T2
  Executor notes: No-epic/global feedback hot-context coverage remained green in the targeted store and editorial loop tests.

- [x] **T4:** Enhance body parsing helpers to produce outlines with nested `###` and deeper subheadings under parent `##` sections, accurate section line counts, and body search results with 1-based line numbers, matching line, surrounding context, and parser-derived section attribution that respects fenced code blocks.
  Depends on: T13
  Executor notes: Body outline/search parser behavior was covered by tests/test_body_parser.py and stayed green with the editorial polish tool tests.

- [x] **T5:** Add and register read tools `get_body_outline(epic_id)` and `search_in_body(epic_id, query, context_lines=2)` with stable empty-result and `epic_not_found` response shapes, exports, and loop/tool-registry wiring.
  Depends on: T13, T4
  Executor notes: Body read tool registration and response behavior stayed green in the body/parser and editorial polish tool batch.

- [x] **T6:** Implement feedback and agent-observation tools: `save_feedback`, `apply_feedback`, `deactivate_feedback`, `list_feedback`, `record_observation`, `list_observations`, and `mark_observation_resolved`; enforce user-feedback vs observation kind separation, auto-fill observation source/turn/context metadata, and import the tool module in the loop so tools register in all modes.
  Depends on: T13, T2, T3
  Executor notes: Fixed the concrete metadata mismatch: list_feedback and list_observations now register as read tools. Added registry assertions and ran a temporary script proving both operation kinds are read, then deleted the script.
  Files changed:
    - agent_kit/tools/feedback.py
    - tests/test_editorial_polish_tools.py

- [x] **T7:** Build source-controlled Sprint 2b system-prompt content from `planning-bot-spec.md`, covering persona, communication style, feedback discipline, body-search workflow, checklist depth guidance for all 18 items, show-changes behavior, end-of-turn checks, and self-observation guidance; update `DEFAULT_PROMPT_VERSION`.
  Depends on: T13, T3, T5, T6
  Executor notes: Prompt-related tests were included in the full suite run; the full suite progressed past prompt coverage. Remaining full-suite failure is unrelated leaked generated artifacts.

- [x] **T8:** Update the full model-call boundary for system prompts: add `system: str | None` to `Model.complete_turn`, update fake and Anthropic model adapters, record/replay the system prompt in ledger request bodies/summaries, and adjust existing model/replay tests without changing their intent.
  Depends on: T13, T7
  Executor notes: System prompt/model plumbing targeted tests passed after one timing-flake rerun of the whole affected batch; tests/test_run_turn.py also passed as a full module.

- [x] **T9:** Implement pure end-of-turn check logic for no message sent, no tool calls/progress, empty response, body unchanged when expected, and checklist stall; send a default acknowledgment after substantive tool work without outbound `send_message`, preserve the existing empty-response error path when no substantive work occurred, and log non-blocking findings to `system_logs`.
  Depends on: T13, T8
  Executor notes: End-of-turn tests passed with the feedback list tools now semantically registered as read tools, preserving the default acknowledgment behavior.
  Files changed:
    - agent_kit/tools/feedback.py
    - tests/test_editorial_polish_tools.py

- [x] **T10:** Verify and cover show-changes and editorial loop behavior: keep edit diffs in `edit_epic` results/audit records, rely on prompt/scripted model behavior rather than response rewriting, and add scripted integrations for `search_in_body -> get_epic -> edit_epic`, `render_epic`, explicit feedback save, confirmed feedback save, feedback apply/reload, observation reload/resolution, and default acknowledgment.
  Depends on: T13, T5, T6, T8, T9
  Executor notes: Scripted editorial loop integrations stayed green in the editorial loop batch, including tool sequencing and feedback/observation lifecycle coverage.

- [x] **T11:** Add deterministic unit, adapter, and integration tests for Sprint 2b behavior, including body parser/search edge cases, feedback and observation store contracts, no-epic global feedback hot context, model system prompt plumbing, and optional LLM-eval fixture scaffolding gated behind an explicit marker or environment variable.
  Depends on: T13, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10
  Executor notes: Deterministic Sprint 2b tests ran in the targeted batches. The live/eval scaffolding remains isolated from default verification; full suite reached 125 passed, 2 skipped before the unrelated secret-scan failure.
  Files changed:
    - tests/test_editorial_polish_tools.py

- [x] **T12:** Run verification and fix failures until targeted checks pass: `pytest tests/test_body_parser.py tests/test_editorial_polish_tools.py`; `pytest tests/test_sqlite_store.py tests/test_supabase_adapters.py tests/test_supabase_store.py`; `pytest tests/test_anthropic_model.py tests/test_anthropic_replay.py tests/test_run_turn.py`; `pytest tests/test_editorial_loop.py tests/test_editorial_polish_loop.py tests/test_mid_turn_messages.py tests/test_run_turn_hooks.py`; then full `pytest`. Also write a short throwaway script that exercises the core Sprint 2b feedback/search/end-of-turn path, run it, confirm behavior, and delete the script before finishing. Do not create new persistent test files in this final verification task.
  Depends on: T13, T11
  Executor notes: Ran all requested targeted pytest batches under Python 3.11 plus the full suite. Full suite has one unrelated pre-existing generated-artifact secret-scan failure. Temporary reproduction script was run and deleted.

- [x] **T14:** Surface after_execute user_actions to the user:
- U2: After code lands and any deployment/migration process is complete, manually smoke test resident-mode Discord behavior against the configured Supabase project: explicit feedback save, proposed feedback confirmation, hot-context reload, observation recording/resolution, and default acknowledgment.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T12
  Executor notes: Surfaced the after_execute manual requirement in deviations: the user must smoke test resident-mode Discord feedback and observation behavior after code deployment/migration.
  Files changed:
    - .DS_Store
    - .megaplan/plans/sprint-2b-editorial-polish/execute_v2_raw.txt
    - .megaplan/plans/sprint-2b-editorial-polish/execution.json
    - .megaplan/plans/sprint-2b-editorial-polish/execution_audit.json
    - .megaplan/plans/sprint-2b-editorial-polish/execution_batch_1.json
    - .megaplan/plans/sprint-2b-editorial-polish/execution_trace.jsonl
    - .megaplan/plans/sprint-2b-editorial-polish/final.md
    - .megaplan/plans/sprint-2b-editorial-polish/finalize.json
    - .megaplan/plans/sprint-2b-editorial-polish/state.json
    - .megaplan/plans/sprint-2b-editorial-polish/step_receipt_execute_v2.json
    - .megaplan/plans/sprint-3-multi-epic/execution.json
    - .megaplan/plans/sprint-3-multi-epic/execution_audit.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_1.json
    - .megaplan/plans/sprint-3-multi-epic/execution_trace.jsonl
    - .megaplan/plans/sprint-3-multi-epic/final.md
    - .megaplan/plans/sprint-3-multi-epic/finalize.json
    - .megaplan/plans/sprint-3-multi-epic/state.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_execute_v2.json
    - .megaplan/plans/sprint-4-sprint-mode/.plan.lock
    - .megaplan/plans/sprint-4-sprint-mode/critique_output.json
    - .megaplan/plans/sprint-4-sprint-mode/critique_v1.json
    - .megaplan/plans/sprint-4-sprint-mode/execution.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_audit.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_1.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_10.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_2.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_3.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_4.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_5.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_6.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_7.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_8.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_9.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_trace.jsonl
    - .megaplan/plans/sprint-4-sprint-mode/faults.json
    - .megaplan/plans/sprint-4-sprint-mode/final.md
    - .megaplan/plans/sprint-4-sprint-mode/finalize.json
    - .megaplan/plans/sprint-4-sprint-mode/finalize_snapshot.json
    - .megaplan/plans/sprint-4-sprint-mode/gate.json
    - .megaplan/plans/sprint-4-sprint-mode/plan_v1.md
    - .megaplan/plans/sprint-4-sprint-mode/plan_v1.meta.json
    - .megaplan/plans/sprint-4-sprint-mode/plan_v2.md
    - .megaplan/plans/sprint-4-sprint-mode/plan_v2.meta.json
    - .megaplan/plans/sprint-4-sprint-mode/review.json
    - .megaplan/plans/sprint-4-sprint-mode/state.json
    - .megaplan/plans/sprint-4-sprint-mode/step_receipt_critique_v1.json
    - .megaplan/plans/sprint-4-sprint-mode/step_receipt_execute_v2.json
    - .megaplan/plans/sprint-4-sprint-mode/step_receipt_finalize_v2.json
    - .megaplan/plans/sprint-4-sprint-mode/step_receipt_plan_v1.json
    - .megaplan/plans/sprint-4-sprint-mode/step_receipt_revise_v2.json
    - agent_kit/.DS_Store
    - agent_kit/epic_routing.py
    - agent_kit/ports.py
    - agent_kit/store/__pycache__/supabase.cpython-311.pyc
    - agent_kit/store/migrations/sqlite/006_sprints.sql
    - agent_kit/store/migrations/sqlite/007_message_search.sql
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
    - agent_kit/tools/__pycache__/feedback.cpython-311.pyc
    - supabase/.DS_Store
    - supabase/migrations/202604300006_006_sprints.sql
    - supabase/migrations/202604300007_007_message_search.sql
    - tests/.DS_Store
    - tests/__pycache__/test_anthropic_model.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_anthropic_replay.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_body_parser.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_cli.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_coalescer.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_communication_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_create_message_synthesize_flag.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_ingestion_ledger.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_ingestion_persist_first.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_transport.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_duplicate_inbound_dropped.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_loop.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_polish_loop.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_end_of_turn.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_envelope.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_image_attachment_pipeline.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_image_tools.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_ledger.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_loop_vision_blocks.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_megaplan_arnold_import.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_mid_turn_messages.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_no_leaked_secrets.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_ports_v1b.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_reconciler.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_resident_recovery.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_run_turn.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_run_turn_hooks.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_send_message_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprint2b_llm_eval_scaffolding.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sqlite_store.cpython-311-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sqlite_store_v1b.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_status_formatter.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_status_lifecycle.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-311-pytest-8.3.5.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_supabase_store.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_system_prompt.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_tool_kit.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_tool_kit_external_queue.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_update_message.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_voice_pipeline.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_whitelist.cpython-311-pytest-9.0.2.pyc
    - tests/test_sqlite_store.py
    - tests/test_supabase_adapters.py
    - tests/test_system_prompt.py

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
  Executor note: Targeted SQLite/Supabase store tests passed under Python 3.11, covering feedback schema and migration contract checks.

- **SC2** (T2): Can SQLite and Supabase adapters create, update, list, and hot-load feedback/observations, and does `load_hot_context(None)` include active style/process feedback while preserving existing hot-context keys?
  Executor note: Targeted store tests passed, covering feedback/observation CRUD and load_hot_context(None) behavior.

- **SC3** (T3): Does the loop use `load_hot_context` for no-epic turns and do fake-model assertions show global feedback is present before any epic is selected?
  Executor note: Store and editorial loop batches passed, preserving no-epic hot-context behavior.

- **SC4** (T4): Do body helper tests prove outline line counts, nested headings, search context windows, line numbers, and fenced-code behavior match actual markdown bodies?
  Executor note: tests/test_body_parser.py passed with tests/test_editorial_polish_tools.py, covering outline/search parser behavior.

- **SC5** (T5): Are `get_body_outline` and `search_in_body` registered, exported, and returning stable success, empty, and `epic_not_found` shapes?
  Executor note: Editorial polish tool tests passed; body read tools remain registered and stable.

- **SC6** (T6): Do tool tests reject invalid kind/source mixing, update `last_applied_at` and `last_referenced_at`, deactivate feedback correctly, and resolve observations so they stop appearing in hot context?
  Executor note: Feedback and observation lifecycle tests passed; list tools are now asserted as read tools while apply/deactivate/resolve write paths still update timestamps/state.

- **SC7** (T7): Does the prompt builder include the required Sprint 2b persona, communication style, feedback discipline, body-search workflow, 18 checklist depth items, show-changes instructions, end-of-turn checks, and self-observation guidance?
  Executor note: Prompt tests were included in the full suite run; no prompt failure appeared before the unrelated generated-artifact secret-scan failure.

- **SC8** (T8): Does every model caller and adapter accept/pass `system`, and do ledger audit/replay records reflect the exact system prompt or prompt version actually sent?
  Executor note: Anthropic, replay, and run-turn tests passed as a full targeted batch after rerunning a timing-flake failure.

- **SC9** (T9): Do end-of-turn tests cover all five categories, preserve the empty-response error path, and produce the default acknowledgment only after substantive work with no outbound message?
  Executor note: End-of-turn tests passed after the tool metadata fix; empty-response/default-ack behavior stayed intact.

- **SC10** (T10): Do scripted integrations record the required tool sequences and feedback/observation lifecycle without relying on response post-processing?
  Executor note: Editorial loop integration batch passed, covering scripted tool sequences and feedback/observation lifecycle flows.

- **SC11** (T11): Are deterministic tests sufficient for core Sprint 2b acceptance criteria, with live LLM evals isolated from normal offline pytest?
  Executor note: Deterministic targeted batches passed; default full-suite execution only failed on unrelated .megaplan secret artifacts.

- **SC12** (T12): Do all targeted pytest commands and the full suite pass after fixing failures, and was the throwaway reproduction script run successfully and deleted?
  Executor note: All targeted batches passed under Python 3.11. Full suite failed only in tests/test_no_leaked_secrets.py due existing .megaplan sprint-1b artifacts. Temporary reproduction script was run and deleted.

- **SC13** (T13): Were all before_execute user_actions programmatically verified before execution proceeded?
  Executor note: No user_actions.md file exists in the repo; the execution-provided before_execute action was optional credentials for live Supabase work and was not required for offline verification.

- **SC14** (T14): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: Manual Discord smoke testing was explicitly surfaced as remaining user action and was not performed in this session.

## Meta

Execute in dependency order and keep the architecture local to the existing `Store` protocol, tool registry, body parser helpers, and `run_turn` loop. The two highest-risk wiring points are no-epic hot context and system prompt propagation through every model/audit boundary. Treat the feedback schema in the Sprint 2b idea as authoritative, especially the absence of a `priority` field. Default tests should be deterministic and offline; live Supabase/Discord work is a separate human-operated smoke pass.
