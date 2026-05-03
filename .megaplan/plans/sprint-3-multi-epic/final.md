# Execution Checklist

- [x] **T13:** Read user_actions.md. For each before_execute action, programmatically verify completion using bash tools — grep .env for required keys, query the migrations table, curl the dev server, etc. Reading the file does NOT count as verification; you must run a command. For actions that genuinely cannot be verified mechanically (manual UI checks), explicitly ask the user. If anything is incomplete or unverifiable, mark this task blocked with reason and STOP.
  Executor notes: No Supabase credentials were introduced, logged, or embedded. Rework verification stayed on local SQLite and adapter tests that do not require live Supabase credentials.
  Files changed:
    - .DS_Store
    - .megaplan/plans/sprint-1b-discord-resident/execution_trace.jsonl
    - .megaplan/plans/sprint-1b-discord-resident/final.md
    - .megaplan/plans/sprint-1b-discord-resident/finalize.json
    - .megaplan/plans/sprint-1b-discord-resident/review.json
    - .megaplan/plans/sprint-1b-discord-resident/review_v4_raw.txt
    - .megaplan/plans/sprint-1b-discord-resident/state.json
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
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_10.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_11.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_12.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_2.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_3.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_4.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_5.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_6.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_7.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_8.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_9.json
    - .megaplan/plans/sprint-3-multi-epic/execution_trace.jsonl
    - .megaplan/plans/sprint-3-multi-epic/final.md
    - .megaplan/plans/sprint-3-multi-epic/finalize.json
    - .megaplan/plans/sprint-3-multi-epic/review.json
    - .megaplan/plans/sprint-3-multi-epic/state.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_execute_v2.json
    - .megaplan/plans/sprint-4-sprint-mode/.plan.lock
    - .megaplan/plans/sprint-4-sprint-mode/critique_output.json
    - .megaplan/plans/sprint-4-sprint-mode/critique_v1.json
    - .megaplan/plans/sprint-4-sprint-mode/execution.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_audit.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_1.json
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
    - agent_kit/__pycache__/__init__.cpython-312.pyc
    - agent_kit/__pycache__/__init__.cpython-314.pyc
    - agent_kit/__pycache__/body.cpython-312.pyc
    - agent_kit/__pycache__/body.cpython-314.pyc
    - agent_kit/__pycache__/end_of_turn.cpython-312.pyc
    - agent_kit/__pycache__/end_of_turn.cpython-314.pyc
    - agent_kit/__pycache__/envelope.cpython-311.pyc
    - agent_kit/__pycache__/envelope.cpython-312.pyc
    - agent_kit/__pycache__/envelope.cpython-314.pyc
    - agent_kit/__pycache__/envelope.cpython-38.pyc
    - agent_kit/__pycache__/epic_routing.cpython-311.pyc
    - agent_kit/__pycache__/epic_routing.cpython-312.pyc
    - agent_kit/__pycache__/epic_routing.cpython-314.pyc
    - agent_kit/__pycache__/gating.cpython-311.pyc
    - agent_kit/__pycache__/gating.cpython-312.pyc
    - agent_kit/__pycache__/gating.cpython-314.pyc
    - agent_kit/__pycache__/gating.cpython-38.pyc
    - agent_kit/__pycache__/ledger.cpython-312.pyc
    - agent_kit/__pycache__/ledger.cpython-314.pyc
    - agent_kit/__pycache__/logging.cpython-312.pyc
    - agent_kit/__pycache__/logging.cpython-314.pyc
    - agent_kit/__pycache__/loop.cpython-311.pyc
    - agent_kit/__pycache__/loop.cpython-312.pyc
    - agent_kit/__pycache__/loop.cpython-314.pyc
    - agent_kit/__pycache__/loop.cpython-38.pyc
    - agent_kit/__pycache__/ports.cpython-311.pyc
    - agent_kit/__pycache__/ports.cpython-312.pyc
    - agent_kit/__pycache__/ports.cpython-314.pyc
    - agent_kit/__pycache__/ports.cpython-38.pyc
    - agent_kit/__pycache__/prompts.cpython-311.pyc
    - agent_kit/__pycache__/prompts.cpython-312.pyc
    - agent_kit/__pycache__/prompts.cpython-314.pyc
    - agent_kit/__pycache__/prompts.cpython-38.pyc
    - agent_kit/__pycache__/resident.cpython-311.pyc
    - agent_kit/__pycache__/resident.cpython-314.pyc
    - agent_kit/__pycache__/resident.cpython-38.pyc
    - agent_kit/__pycache__/sprints.cpython-311.pyc
    - agent_kit/__pycache__/sprints.cpython-312.pyc
    - agent_kit/__pycache__/sprints.cpython-314.pyc
    - agent_kit/__pycache__/sprints.cpython-38.pyc
    - agent_kit/__pycache__/templates.cpython-312.pyc
    - agent_kit/__pycache__/templates.cpython-314.pyc
    - agent_kit/__pycache__/tool_kit.cpython-312.pyc
    - agent_kit/__pycache__/tool_kit.cpython-314.pyc
    - agent_kit/blob/__pycache__/__init__.cpython-312.pyc
    - agent_kit/blob/__pycache__/__init__.cpython-314.pyc
    - agent_kit/blob/__pycache__/supabase_storage.cpython-312.pyc
    - agent_kit/blob/__pycache__/supabase_storage.cpython-314.pyc
    - agent_kit/envelope.py
    - agent_kit/epic_routing.py
    - agent_kit/gating.py
    - agent_kit/loop.py
    - agent_kit/model/__pycache__/__init__.cpython-312.pyc
    - agent_kit/model/__pycache__/__init__.cpython-314.pyc
    - agent_kit/model/__pycache__/anthropic.cpython-312.pyc
    - agent_kit/model/__pycache__/anthropic.cpython-314.pyc
    - agent_kit/model/__pycache__/fake.cpython-312.pyc
    - agent_kit/model/__pycache__/fake.cpython-314.pyc
    - agent_kit/ports.py
    - agent_kit/prompts.py
    - agent_kit/sprints.py
    - agent_kit/store/__pycache__/__init__.cpython-312.pyc
    - agent_kit/store/__pycache__/__init__.cpython-314.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-311.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-312.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-314.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-38.pyc
    - agent_kit/store/__pycache__/supabase.cpython-311.pyc
    - agent_kit/store/__pycache__/supabase.cpython-312.pyc
    - agent_kit/store/__pycache__/supabase.cpython-314.pyc
    - agent_kit/store/__pycache__/supabase.cpython-38.pyc
    - agent_kit/store/migrations/sqlite/006_sprints.sql
    - agent_kit/store/migrations/sqlite/007_message_search.sql
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
    - agent_kit/tools/__pycache__/__init__.cpython-312.pyc
    - agent_kit/tools/__pycache__/__init__.cpython-314.pyc
    - agent_kit/tools/__pycache__/communication.cpython-312.pyc
    - agent_kit/tools/__pycache__/communication.cpython-314.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-311.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-312.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-314.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-38.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-311.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-312.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-314.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-38.pyc
    - agent_kit/tools/__pycache__/feedback.cpython-311.pyc
    - agent_kit/tools/__pycache__/feedback.cpython-312.pyc
    - agent_kit/tools/__pycache__/feedback.cpython-314.pyc
    - agent_kit/tools/__pycache__/images.cpython-312.pyc
    - agent_kit/tools/__pycache__/images.cpython-314.pyc
    - agent_kit/tools/editorial.py
    - agent_kit/tools/editorial_reads.py
    - agent_kit/tools/feedback.py
    - agent_kit/transport/__pycache__/__init__.cpython-314.pyc
    - agent_kit/transport/__pycache__/discord.cpython-314.pyc
    - arnold/.DS_Store
    - arnold/__pycache__/__init__.cpython-312.pyc
    - arnold/__pycache__/__init__.cpython-314.pyc
    - arnold/__pycache__/__main__.cpython-314.pyc
    - arnold/__pycache__/cli.cpython-312.pyc
    - arnold/__pycache__/cli.cpython-314.pyc
    - arnold_v2.egg-info/PKG-INFO
    - arnold_v2.egg-info/SOURCES.txt
    - arnold_v2.egg-info/dependency_links.txt
    - arnold_v2.egg-info/entry_points.txt
    - arnold_v2.egg-info/requires.txt
    - arnold_v2.egg-info/top_level.txt
    - megaplan/.DS_Store
    - megaplan/__pycache__/__init__.cpython-314.pyc
    - megaplan/arnold/__pycache__/__init__.cpython-314.pyc
    - prompts/system.md
    - supabase/.DS_Store
    - supabase/migrations/202604300006_006_sprints.sql
    - supabase/migrations/202604300007_007_message_search.sql
    - tests/.DS_Store
    - tests/__pycache__/__init__.cpython-312.pyc
    - tests/__pycache__/__init__.cpython-314.pyc
    - tests/__pycache__/helpers.cpython-312.pyc
    - tests/__pycache__/helpers.cpython-314.pyc
    - tests/__pycache__/store_contract.cpython-312.pyc
    - tests/__pycache__/store_contract.cpython-314.pyc
    - tests/__pycache__/store_contract_v1b.cpython-312.pyc
    - tests/__pycache__/store_contract_v1b.cpython-314.pyc
    - tests/__pycache__/test_anthropic_model.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_anthropic_model.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_anthropic_replay.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_anthropic_replay.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_body_parser.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_body_parser.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_cli.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_cli.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_coalescer.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_coalescer.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_communication_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_communication_resident.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_create_message_synthesize_flag.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_create_message_synthesize_flag.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_discord_ingestion_ledger.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_ingestion_ledger.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_discord_ingestion_persist_first.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_ingestion_persist_first.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_discord_transport.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_transport.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_duplicate_inbound_dropped.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_duplicate_inbound_dropped.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_loop.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_loop.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_polish_loop.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_polish_loop.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_end_of_turn.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_end_of_turn.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_end_of_turn.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_envelope.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_envelope.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_envelope.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_image_attachment_pipeline.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_image_attachment_pipeline.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_image_tools.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_image_tools.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_ledger.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_ledger.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_loop_vision_blocks.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_loop_vision_blocks.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_megaplan_arnold_import.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_megaplan_arnold_import.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_mid_turn_messages.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_mid_turn_messages.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_no_leaked_secrets.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_no_leaked_secrets.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_ports_v1b.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_ports_v1b.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_reconciler.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_reconciler.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_resident.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_resident_recovery.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_resident_recovery.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_run_turn.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_run_turn.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_run_turn_hooks.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_run_turn_hooks.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_send_message_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_send_message_resident.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprint2b_llm_eval_scaffolding.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprint2b_llm_eval_scaffolding.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-311.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sprints.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprints.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprints.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprints.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store.cpython-311-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sqlite_store.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_sqlite_store.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sqlite_store.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store_v1b.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sqlite_store_v1b.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_status_formatter.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_status_formatter.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_status_lifecycle.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_status_lifecycle.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-311-pytest-8.3.5.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_supabase_store.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_supabase_store.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_system_prompt.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_system_prompt.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_system_prompt.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_system_prompt.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_tool_kit.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_tool_kit.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_tool_kit_external_queue.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_tool_kit_external_queue.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_update_message.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_update_message.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_voice_pipeline.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_voice_pipeline.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_whitelist.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_whitelist.cpython-314-pytest-9.0.3.pyc
    - tests/test_editorial_polish_tools.py
    - tests/test_sprints.py
    - tests/test_sqlite_store.py
    - tests/test_supabase_adapters.py
    - tests/test_system_prompt.py

- [x] **T1:** Audit `planning-bot-spec.md` and the current routing/store code to pin Sprint 3 contracts: epic selection rules, reference behavior, user modes, understanding summaries, switch announcements, gap acknowledgment threshold, Discord inbound persistence, resident coalescing, `run_turn` lock acquisition, `Store` conventions, schema fields, migration style, and whether persisted inbound messages need reassignment after routing.
  Depends on: T13
  Executor notes: Reconfirmed the relevant insertion point by editing `ResidentRunner.handle_transport_message`: epic routing now runs before coalescing and before any `run_turn` lock acquisition.
  Files changed:
    - agent_kit/resident.py

- [x] **T2:** Extend `agent_kit/ports.py` with Store protocol methods for `list_epics`, `search_epics`, and `search_messages`, using stable portable result shapes containing IDs, title/content snippets, status, timestamps, direction, rank where applicable, and disambiguation metadata. Add a minimal message epic reassignment method only if T1 confirms inbound rows are persisted before final selected-epic routing.
  Depends on: T13, T1
  Executor notes: Store protocol coverage remains intact; the added portability test invokes `search_messages` through the tool registry against a Store-shaped spy, proving the tool path depends on Store methods rather than adapter SQL.
  Files changed:
    - tests/test_sprint3_multi_epic.py

- [x] **T3:** Add full-text search migrations for both stores: SQLite migration under `agent_kit/store/migrations/sqlite/` using FTS5 or the repo's established SQLite FTS pattern for `messages.content`, and Supabase migration under `supabase/migrations/` using PostgreSQL full-text search with a GIN index or generated/search-vector column. Keep visibility/scoping aligned with existing message reads.
  Depends on: T13, T1, T2
  Executor notes: Existing SQLite and Supabase message-search migrations were left unchanged. Focused Sprint 3 and relevant adapter suites passed after the routing/tool portability rework.

- [x] **T4:** Implement the new Store methods in `agent_kit/store/sqlite.py` and `agent_kit/store/supabase.py`, including deterministic ranking/tie-breakers and compatible result shapes. Implement message epic reassignment in both adapters if T2 added it.
  Depends on: T13, T2, T3
  Executor notes: SQLite/Supabase list and search behavior stayed compatible under the relevant store and adapter suites; no adapter logic needed changes for this rework.

- [x] **T5:** Implement deterministic pre-turn epic routing before resident payload coalescing and before `run_turn` lock acquisition. Inputs must include message text, author/conversation identity, recent active epics, current/default context, and previous selected epic. Explicit epic names/correction phrases override recency; ambiguous messages select the single most recently edited active epic within 24 hours; unclear context must produce clarification behavior instead of mutating a guessed real epic.
  Depends on: T13, T1, T4
  Executor notes: Epic routing still selects the single recent active epic in the 30-scenario fixture, and the revised resident path now combines all queued inbound message text before making the pre-turn decision.
  Files changed:
    - agent_kit/resident.py
    - tests/test_sprint3_multi_epic.py

- [x] **T6:** Wire selected-epic lock safety and switch announcements through `agent_kit/resident.py` and `agent_kit/loop.py`: call `run_turn(epic_id=...)` with the selected real epic, update queued payloads and persisted inbound rows before execution when routing changes, ensure outbound rows attach to the selected epic, reject or safely defer late unsafe epic switches, and include the destination epic title in outbound messages only when an actual switch occurs.
  Depends on: T13, T5
  Executor notes: Fixed the lock-safety gap for bundled payloads: when routing changes epics, every queued inbound message row is reassigned before coalescing, and every queued ID is added under the selected epic. The new test asserts both rows and the coalescer burst use `epic_new` before dispatch.
  Files changed:
    - agent_kit/resident.py
    - tests/test_sprint3_multi_epic.py

- [x] **T7:** Register `list_epics`, `search_epics`, and `search_messages` read tools through the existing tool registry under `agent_kit/tools/` or the actual registry found during T1. Tool handlers must call only the Store protocol methods, return concise stable payloads for disambiguation/user summaries, and avoid direct adapter SQL or cross-user data exposure.
  Depends on: T13, T4
  Executor notes: Added a Store-portability regression test for `search_messages` through `registry.invoke` using a minimal Store spy. This would fail if the tool handler bypassed the Store protocol and reached for SQLite/Supabase-specific behavior.
  Files changed:
    - tests/test_sprint3_multi_epic.py

- [x] **T8:** Implement reference resolution against the most recent outbound bot message in the same conversation/selected-epic context. Resolve phrases such as `the second one`, `that point`, and `the last option` using structured outbound metadata when available, otherwise parse common raw-text structures including numbered lists, bullets, headings, and short option lists. Return resolved target plus ambiguity state so low-confidence cases ask for clarification.
  Depends on: T13, T6
  Executor notes: Reference resolution behavior was unchanged and remained covered by the focused Sprint 3 suite after the resident/tool rework.

- [x] **T9:** Implement user mode detection and conversation gap acknowledgment in the prompt/policy builder path found during T1. Detect Deep-thinking, Brainstorming, and Executing separately from epic routing, pass distinct response policy inputs for each mode, decide stickiness according to the spec or T1 finding, and add the specified gap acknowledgment only when the configured threshold is crossed.
  Depends on: T13, T1, T6
  Executor notes: Mode and gap prompt-policy behavior was unchanged and continued to pass in the focused Sprint 3 suite.

- [x] **T10:** Implement `show me what you know about X` understanding summaries. Resolve `X` through explicit epic matching, `search_epics`, and `search_messages`; ground output in stored epic/message data; and return every structured section required by `planning-bot-spec.md` without unsupported synthesis.
  Depends on: T13, T7, T9
  Executor notes: Understanding-summary behavior was unchanged and the required seven-section assertion continued to pass in the focused Sprint 3 suite.

- [x] **T11:** Add or extend focused project tests for the new behavior: Store contract/migration coverage for SQLite and Supabase adapters, seeded search corpus with 10 expected hit IDs, pre-turn routing and selected-epic lock safety, inbound/outbound row attachment, unsafe late-switch protection, epic selection fixtures with five active epics, reference resolver fixtures, mode detection fixtures, switch announcement assertions, multi-epic switching/search/summary integration, 30 canned epic-selection eval scenarios requiring at least 27 correct, and 10 ambiguity scenarios requiring clarification instead of guessing.
  Depends on: T13, T3, T4, T5, T6, T7, T8, T9, T10
  Executor notes: Extended Sprint 3 tests for the reviewer concerns: bundled inbound row reassignment/coalescing before dispatch, and Store-only `search_messages` tool invocation via a spy.
  Files changed:
    - tests/test_sprint3_multi_epic.py

- [x] **T12:** Run verification and fix until passing: run the most relevant existing Store contract tests first for SQLite, then Supabase adapter tests if credentials/config are available, then routing/lock-safety tests, unit tests for epic selection/reference resolution/mode detection, integration tests for switching/search tools/understanding summaries, LLM-graded evals for epic selection and ambiguity handling, and finally the repository's broader lint/test suite. Also write a short throwaway script that exercises the Sprint 3 routing/search/reference scenario end to end, run it, confirm behavior, and delete the script before finalizing.
  Depends on: T13, T11
  Executor notes: Verification passed for the focused Sprint 3 suite, relevant store/resident/run-turn/tool suites, and the broad suite with only the known deleted-artifact secret scan excluded. The temporary repro script exercised multi-message pre-turn reassignment/coalescing and Store-backed message search, passed, and was deleted.

- [x] **T14:** Surface after_execute user_actions to the user:
- U2: After code review/merge approval, apply the Supabase migration to the intended Supabase environment using the team's normal deployment process.
- U3: Manually review a short live or staging conversation for the three user modes to confirm the responses feel meaningfully different without becoming verbose or performative.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T12
  Executor notes: After-execute human actions remain surfaced and not performed: apply the Supabase migration through the team's deployment process after review/merge, and manually review live/staging conversations for the three user modes.
  Files changed:
    - .DS_Store
    - .megaplan/plans/sprint-1b-discord-resident/execution_trace.jsonl
    - .megaplan/plans/sprint-1b-discord-resident/final.md
    - .megaplan/plans/sprint-1b-discord-resident/finalize.json
    - .megaplan/plans/sprint-1b-discord-resident/review.json
    - .megaplan/plans/sprint-1b-discord-resident/review_v4_raw.txt
    - .megaplan/plans/sprint-1b-discord-resident/state.json
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
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_10.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_11.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_12.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_2.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_3.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_4.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_5.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_6.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_7.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_8.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_9.json
    - .megaplan/plans/sprint-3-multi-epic/execution_trace.jsonl
    - .megaplan/plans/sprint-3-multi-epic/final.md
    - .megaplan/plans/sprint-3-multi-epic/finalize.json
    - .megaplan/plans/sprint-3-multi-epic/review.json
    - .megaplan/plans/sprint-3-multi-epic/state.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_execute_v2.json
    - .megaplan/plans/sprint-4-sprint-mode/.plan.lock
    - .megaplan/plans/sprint-4-sprint-mode/critique_output.json
    - .megaplan/plans/sprint-4-sprint-mode/critique_v1.json
    - .megaplan/plans/sprint-4-sprint-mode/execution.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_audit.json
    - .megaplan/plans/sprint-4-sprint-mode/execution_batch_1.json
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
    - agent_kit/__pycache__/__init__.cpython-312.pyc
    - agent_kit/__pycache__/__init__.cpython-314.pyc
    - agent_kit/__pycache__/body.cpython-312.pyc
    - agent_kit/__pycache__/body.cpython-314.pyc
    - agent_kit/__pycache__/end_of_turn.cpython-312.pyc
    - agent_kit/__pycache__/end_of_turn.cpython-314.pyc
    - agent_kit/__pycache__/envelope.cpython-311.pyc
    - agent_kit/__pycache__/envelope.cpython-312.pyc
    - agent_kit/__pycache__/envelope.cpython-314.pyc
    - agent_kit/__pycache__/envelope.cpython-38.pyc
    - agent_kit/__pycache__/epic_routing.cpython-311.pyc
    - agent_kit/__pycache__/epic_routing.cpython-312.pyc
    - agent_kit/__pycache__/epic_routing.cpython-314.pyc
    - agent_kit/__pycache__/gating.cpython-311.pyc
    - agent_kit/__pycache__/gating.cpython-312.pyc
    - agent_kit/__pycache__/gating.cpython-314.pyc
    - agent_kit/__pycache__/gating.cpython-38.pyc
    - agent_kit/__pycache__/ledger.cpython-312.pyc
    - agent_kit/__pycache__/ledger.cpython-314.pyc
    - agent_kit/__pycache__/logging.cpython-312.pyc
    - agent_kit/__pycache__/logging.cpython-314.pyc
    - agent_kit/__pycache__/loop.cpython-311.pyc
    - agent_kit/__pycache__/loop.cpython-312.pyc
    - agent_kit/__pycache__/loop.cpython-314.pyc
    - agent_kit/__pycache__/loop.cpython-38.pyc
    - agent_kit/__pycache__/ports.cpython-311.pyc
    - agent_kit/__pycache__/ports.cpython-312.pyc
    - agent_kit/__pycache__/ports.cpython-314.pyc
    - agent_kit/__pycache__/ports.cpython-38.pyc
    - agent_kit/__pycache__/prompts.cpython-311.pyc
    - agent_kit/__pycache__/prompts.cpython-312.pyc
    - agent_kit/__pycache__/prompts.cpython-314.pyc
    - agent_kit/__pycache__/prompts.cpython-38.pyc
    - agent_kit/__pycache__/resident.cpython-311.pyc
    - agent_kit/__pycache__/resident.cpython-314.pyc
    - agent_kit/__pycache__/resident.cpython-38.pyc
    - agent_kit/__pycache__/sprints.cpython-311.pyc
    - agent_kit/__pycache__/sprints.cpython-312.pyc
    - agent_kit/__pycache__/sprints.cpython-314.pyc
    - agent_kit/__pycache__/sprints.cpython-38.pyc
    - agent_kit/__pycache__/templates.cpython-312.pyc
    - agent_kit/__pycache__/templates.cpython-314.pyc
    - agent_kit/__pycache__/tool_kit.cpython-312.pyc
    - agent_kit/__pycache__/tool_kit.cpython-314.pyc
    - agent_kit/blob/__pycache__/__init__.cpython-312.pyc
    - agent_kit/blob/__pycache__/__init__.cpython-314.pyc
    - agent_kit/blob/__pycache__/supabase_storage.cpython-312.pyc
    - agent_kit/blob/__pycache__/supabase_storage.cpython-314.pyc
    - agent_kit/envelope.py
    - agent_kit/epic_routing.py
    - agent_kit/gating.py
    - agent_kit/loop.py
    - agent_kit/model/__pycache__/__init__.cpython-312.pyc
    - agent_kit/model/__pycache__/__init__.cpython-314.pyc
    - agent_kit/model/__pycache__/anthropic.cpython-312.pyc
    - agent_kit/model/__pycache__/anthropic.cpython-314.pyc
    - agent_kit/model/__pycache__/fake.cpython-312.pyc
    - agent_kit/model/__pycache__/fake.cpython-314.pyc
    - agent_kit/ports.py
    - agent_kit/prompts.py
    - agent_kit/sprints.py
    - agent_kit/store/__pycache__/__init__.cpython-312.pyc
    - agent_kit/store/__pycache__/__init__.cpython-314.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-311.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-312.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-314.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-38.pyc
    - agent_kit/store/__pycache__/supabase.cpython-311.pyc
    - agent_kit/store/__pycache__/supabase.cpython-312.pyc
    - agent_kit/store/__pycache__/supabase.cpython-314.pyc
    - agent_kit/store/__pycache__/supabase.cpython-38.pyc
    - agent_kit/store/migrations/sqlite/006_sprints.sql
    - agent_kit/store/migrations/sqlite/007_message_search.sql
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
    - agent_kit/tools/__pycache__/__init__.cpython-312.pyc
    - agent_kit/tools/__pycache__/__init__.cpython-314.pyc
    - agent_kit/tools/__pycache__/communication.cpython-312.pyc
    - agent_kit/tools/__pycache__/communication.cpython-314.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-311.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-312.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-314.pyc
    - agent_kit/tools/__pycache__/editorial.cpython-38.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-311.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-312.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-314.pyc
    - agent_kit/tools/__pycache__/editorial_reads.cpython-38.pyc
    - agent_kit/tools/__pycache__/feedback.cpython-311.pyc
    - agent_kit/tools/__pycache__/feedback.cpython-312.pyc
    - agent_kit/tools/__pycache__/feedback.cpython-314.pyc
    - agent_kit/tools/__pycache__/images.cpython-312.pyc
    - agent_kit/tools/__pycache__/images.cpython-314.pyc
    - agent_kit/tools/editorial.py
    - agent_kit/tools/editorial_reads.py
    - agent_kit/tools/feedback.py
    - agent_kit/transport/__pycache__/__init__.cpython-314.pyc
    - agent_kit/transport/__pycache__/discord.cpython-314.pyc
    - arnold/.DS_Store
    - arnold/__pycache__/__init__.cpython-312.pyc
    - arnold/__pycache__/__init__.cpython-314.pyc
    - arnold/__pycache__/__main__.cpython-314.pyc
    - arnold/__pycache__/cli.cpython-312.pyc
    - arnold/__pycache__/cli.cpython-314.pyc
    - arnold_v2.egg-info/PKG-INFO
    - arnold_v2.egg-info/SOURCES.txt
    - arnold_v2.egg-info/dependency_links.txt
    - arnold_v2.egg-info/entry_points.txt
    - arnold_v2.egg-info/requires.txt
    - arnold_v2.egg-info/top_level.txt
    - megaplan/.DS_Store
    - megaplan/__pycache__/__init__.cpython-314.pyc
    - megaplan/arnold/__pycache__/__init__.cpython-314.pyc
    - prompts/system.md
    - supabase/.DS_Store
    - supabase/migrations/202604300006_006_sprints.sql
    - supabase/migrations/202604300007_007_message_search.sql
    - tests/.DS_Store
    - tests/__pycache__/__init__.cpython-312.pyc
    - tests/__pycache__/__init__.cpython-314.pyc
    - tests/__pycache__/helpers.cpython-312.pyc
    - tests/__pycache__/helpers.cpython-314.pyc
    - tests/__pycache__/store_contract.cpython-312.pyc
    - tests/__pycache__/store_contract.cpython-314.pyc
    - tests/__pycache__/store_contract_v1b.cpython-312.pyc
    - tests/__pycache__/store_contract_v1b.cpython-314.pyc
    - tests/__pycache__/test_anthropic_model.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_anthropic_model.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_anthropic_replay.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_anthropic_replay.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_body_parser.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_body_parser.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_cli.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_cli.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_coalescer.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_coalescer.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_communication_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_communication_resident.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_create_message_synthesize_flag.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_create_message_synthesize_flag.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_discord_ingestion_ledger.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_ingestion_ledger.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_discord_ingestion_persist_first.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_ingestion_persist_first.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_discord_transport.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_discord_transport.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_duplicate_inbound_dropped.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_duplicate_inbound_dropped.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_loop.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_loop.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_polish_loop.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_polish_loop.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_end_of_turn.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_end_of_turn.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_end_of_turn.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_envelope.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_envelope.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_envelope.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_image_attachment_pipeline.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_image_attachment_pipeline.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_image_tools.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_image_tools.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_ledger.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_ledger.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_loop_vision_blocks.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_loop_vision_blocks.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_megaplan_arnold_import.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_megaplan_arnold_import.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_mid_turn_messages.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_mid_turn_messages.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_no_leaked_secrets.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_no_leaked_secrets.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_ports_v1b.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_ports_v1b.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_reconciler.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_reconciler.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_resident.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_resident_recovery.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_resident_recovery.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_run_turn.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_run_turn.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_run_turn_hooks.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_run_turn_hooks.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_send_message_resident.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_send_message_resident.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprint2b_llm_eval_scaffolding.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprint2b_llm_eval_scaffolding.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-311.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprint3_multi_epic.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sprints.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sprints.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprints.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sprints.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store.cpython-311-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sqlite_store.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_sqlite_store.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_sqlite_store.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store_v1b.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_sqlite_store_v1b.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_status_formatter.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_status_formatter.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_status_lifecycle.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_status_lifecycle.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-311-pytest-8.3.5.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_supabase_store.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_supabase_store.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_system_prompt.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_system_prompt.cpython-312-pytest-9.0.3.pyc
    - tests/__pycache__/test_system_prompt.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_system_prompt.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_tool_kit.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_tool_kit.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_tool_kit_external_queue.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_tool_kit_external_queue.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_update_message.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_update_message.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_voice_pipeline.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_voice_pipeline.cpython-314-pytest-9.0.3.pyc
    - tests/__pycache__/test_whitelist.cpython-311-pytest-9.0.2.pyc
    - tests/__pycache__/test_whitelist.cpython-314-pytest-9.0.3.pyc
    - tests/test_editorial_polish_tools.py
    - tests/test_sprints.py
    - tests/test_sqlite_store.py
    - tests/test_supabase_adapters.py
    - tests/test_system_prompt.py

## Watch Items

- Do not invoke nested megaplan tooling; treat repository mentions of megaplan as implementation context only.
- Epic selection must happen before `run_turn` acquires the epic lock, or any later switch path must be explicitly lock-safe and tested.
- Inbound Discord messages may already be persisted under a synthetic/default key; if so, reassign both payload and stored row before queueing/running the selected real epic turn.
- Define `most recently edited epic` from the real schema/spec before implementation. Candidate fields may include `epics.updated_at`, latest message timestamp, or last bot-applied mutation timestamp.
- Ambiguous messages should select a real epic only when exactly one safe qualifying default exists within 24 hours; otherwise ask for clarification.
- Explicit epic names and correction phrases override recency and must not be mistaken for user mode signals.
- Switch announcements must include the destination epic title only on actual epic changes, not every routed message.
- Search/list tools must go through `Store` in `agent_kit/ports.py`; no Supabase-only helper or direct tool SQL.
- SQLite and Supabase result shapes must remain compatible enough for shared tests and model/tool callers.
- Full-text search must respect existing user/conversation/epic visibility boundaries and avoid cross-user leakage.
- Reference resolution should prefer structured outbound metadata when present but must pass raw-text fixtures for existing stored messages.
- Mode behavior should be distinct but not performative: Deep-thinking measured/substantive, Brainstorming exploratory, Executing direct/minimal.
- Do not commit, log, or embed the redacted Supabase service-role key; use existing environment configuration for Supabase tests.
- Debt watch: avoid worsening known attachment-ingestion recovery gaps; Sprint 3 should not promise deterministic storage reissue without durable payload source material.
- LLM-graded evals must be deterministic and cheap enough for normal verification where the repo supports that.

## Sense Checks

- **SC1** (T1): Did the audit identify the exact pre-turn insertion point, the real schema timestamp to use for recency, the gap threshold/mode stickiness rules, and whether message reassignment is required?
  Executor note: Confirmed by code path: `ResidentRunner.handle_transport_message` now selects the epic before `MessageCoalescer.add`; dispatch later calls `run_turn` with that selected epic.

- **SC2** (T2): Do the Store protocol method signatures and result shapes contain enough metadata for disambiguation while remaining portable across SQLite and Supabase?
  Executor note: The Store-shaped spy test confirms the tool-facing result path uses portable Store method output rather than adapter internals.

- **SC3** (T3): Do both migrations add indexed full-text search for `messages.content` using each store's native approach without bypassing existing visibility assumptions?
  Executor note: Both existing migrations remain in place; focused search tests and relevant adapter suites passed after the rework.

- **SC4** (T4): Do SQLite and Supabase implementations return compatible, deterministic results for list/search calls, including stable tie-breakers and any required reassignment behavior?
  Executor note: Relevant SQLite and Supabase adapter tests passed with deterministic list/search behavior intact.

- **SC5** (T5): Can an ambiguous message with five active epics route to the single most recently edited active epic within 24 hours before resident coalescing and before the lock is acquired?
  Executor note: The 30-scenario routing fixture still passes in `tests/test_sprint3_multi_epic.py`, including five-active-epic single-recent default cases.

- **SC6** (T6): Are `run_turn`, persisted inbound rows, queued payloads, locks, outbound rows, and switch announcements all using the same selected epic ID/title?
  Executor note: Added coverage for bundled payloads: all queued inbound rows are reassigned and coalesced under the selected epic before any turn dispatch.

- **SC7** (T7): Are the new read tools registered through the existing tool system and calling only Store protocol methods with no adapter-specific SQL in tool handlers?
  Executor note: Added a Store-spy `search_messages` registry invocation test; it asserts the handler calls only `context.store.search_messages` with the supplied arguments.

- **SC8** (T8): Does the resolver correctly handle numbered lists, bullets, headings, mixed prose/list structures, and ambiguous `that point` cases against only the last outbound bot message in scope?
  Executor note: Reference resolver fixtures continued to pass in the focused Sprint 3 suite.

- **SC9** (T9): Are mode signals separated from epic routing, and does the prompt/policy path receive distinct inputs for Deep-thinking, Brainstorming, and Executing plus the correct gap acknowledgment state?
  Executor note: Mode detection and gap prompt assertions continued to pass in the focused Sprint 3 suite.

- **SC10** (T10): Does `show me what you know about X` resolve the right epic/message evidence and include every spec-required summary section without unsupported claims?
  Executor note: The self-understanding seven-section assertion continued to pass in the focused Sprint 3 suite.

- **SC11** (T11): Do the added/extended tests cover store search, routing/lock safety, row attachment, unsafe switches, reference resolution, mode detection, switch announcements, summaries, and the required eval thresholds?
  Executor note: Tests now cover the reviewer-specific routing/lock row attachment case and Store-portable message search in addition to the prior Sprint 3 acceptance fixtures.

- **SC12** (T12): Did the focused tests, relevant integration tests, LLM-graded evals, throwaway reproduction script, and broader repo test/lint suite pass after any fixes and reruns?
  Executor note: Focused, relevant integration, repro-script, and broad verification passed except for the known deleted-artifact secret scan; rerun excluding that test passed 150 tests with 2 skipped.

- **SC13** (T13): Were all before_execute user_actions programmatically verified before execution proceeded?
  Executor note: No live Supabase credential verification was performed because credentials are not configured here; no secrets were added or logged.

- **SC14** (T14): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: The remaining human actions are explicitly reported: deploy Supabase migration after review/merge and manually assess user-mode response feel in live/staging.

## Meta

Execute in dependency order and keep the routing/locking invariant central: the selected epic ID must be known before `run_turn` loads context or mutates state. Prefer small deterministic helpers for epic selection, reference resolution, and mode detection so the behavior is unit-testable instead of buried only in prompts. Treat `planning-bot-spec.md` as behavioral authority where the approved plan leaves questions open; when the spec is flexible, document the chosen interpretation in code/tests. Keep Supabase secrets out of all files and logs, and do SQLite verification first so implementation can proceed even if Supabase credentials are unavailable.
