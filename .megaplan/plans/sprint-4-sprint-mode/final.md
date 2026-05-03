# Execution Checklist

- [x] **T1:** Add SQLite and Supabase sprint migrations for `sprints` and `sprint_items`, including status checks, timestamps, item fields, read indexes, and partial unique queued-position constraints.
  Executor notes: Verified the migration coverage through the focused adapter/migration tests under Python 3.11.11; the existing SQLite and Supabase sprint migration assertions passed.

- [x] **T2:** Extend the store port plus SQLite and Supabase adapters with sprint CRUD, sprint item replacement/listing, and helper loading of sprints with items. Update hot context to include sprint snapshots and an all-sprints-pending/no-queued flag.
  Depends on: T1
  Executor notes: Verified sprint CRUD, item replacement/listing, helper loading, and hot-context sprint flags through the focused store tests under Python 3.11.11.

- [x] **T3:** Implement deterministic sprint domain logic in `agent_kit/sprints.py`: payload normalization, validation, PM-task-level item checks, default lock-in assignment, queue/pend/reorder operations, gapless positions, and structured sprint-change summaries.
  Depends on: T2
  Executor notes: Fixed explicit lock-in validation so unknown sprint numbers, duplicate queued assignments, and queued/pending conflicts fail before mutation. Added deterministic lock-in confirmation parsing and tests. The temporary reproduction script confirmed an unknown explicit lock-in sprint now raises `SprintValidationError`.
  Files changed:
    - agent_kit/sprints.py
    - tests/test_sprints.py

- [x] **T4:** Implement deterministic gating and lockdown scanning: `shaping -> sprinting`, `sprinting -> planned`, PM-handoff heuristic, checklist rules, at-least-one-sprint rule, queued/pending invariants, and unresolved-decision phrase blocking outside `Open Questions` and fenced code.
  Depends on: T2, T3
  Executor notes: Focused Sprint 4 tests verify shaping/planned gate blockers and lockdown phrase behavior, including Open Questions and fenced-code exemptions.

- [x] **T5:** Wire `edit_epic` to accept top-level `force`, `changes.sprints`, and `changes.state.target`; run gates before writes unless forced; apply body/checklist/sprint/state writes transactionally; set `planned_at` when entering `planned`; record `sprints_change`, `sprint_status_change`, `state_change`, and `forced_handoff` events with blocker details and prior-state snapshots.
  Depends on: T3, T4
  Executor notes: Focused Sprint 4 tests verify `edit_epic` state advancement, forced handoff logging, sprint writes, lock-in, and `planned_at` assignment. The new lock-in validation is exercised through `edit_epic` and rolls back cleanly on invalid payloads.
  Files changed:
    - tests/test_sprints.py

- [x] **T6:** Preserve revert semantics for Sprint 4 events by replaying stored prior epic state, prior sprint rows, and prior sprint item rows for `sprints_change`, `sprint_status_change`, `state_change`, and `forced_handoff`.
  Depends on: T5
  Executor notes: Revert coverage in the Sprint 4 tests confirms sprint queue/reorder history is restored from stored prior sprint snapshots without disturbing the existing revert path.

- [x] **T7:** Update editorial read and time-travel tools so `get_epic` returns current sprints with items and `get_epic_at_time` reconstructs sprint/status/state history from event replay, matching the same snapshots used by revert.
  Depends on: T5, T6
  Executor notes: Focused tests confirm `get_epic` returns current sprints and `get_epic_at_time` exposes historical sprint state from replay snapshots.

- [x] **T8:** Update invocation envelope generation so completed turns reload actual post-turn state, populate `StateDelta.state_transition` and `StateDelta.sprint_changes`, and adjust `agent_kit/envelope.schema.json` only if the existing schema is insufficient.
  Depends on: T5
  Executor notes: Envelope tests in the focused run confirm completed invocation envelopes report actual post-turn state plus `state_transition` and `sprint_changes` after Sprint 4 edits.

- [x] **T9:** Update Arnold prompts and phase-aware end-of-turn checks for the two-beat sprint lock-in flow, blocker surfacing with address/skip/force options, post-handoff queue/pend/reorder commands, sprinting/planned progress findings, and all-pending planned-state user-facing notes.
  Depends on: T2, T5, T8
  Executor notes: System prompt and end-of-turn focused tests passed, covering the sprint flow guidance and phase-aware checks already present in the prompt/context path.

- [x] **T10:** Add focused unit, adapter, migration, envelope, read/replay, end-of-turn, and lifecycle tests for Sprint 4 behavior: gating, lockdown, force-through event logging, sprint CRUD, duplicate queued-position rejection, lock-in, decision-doc lifecycle, queue/reorder, read surfaces, and invocation deltas.
  Depends on: T1, T2, T3, T4, T5, T6, T7, T8, T9
  Executor notes: Added focused tests for explicit lock-in validation and confirmation parsing. The Sprint 4 test module now covers the reworked edge case plus existing lifecycle, force-through, queue/reorder, lockdown, and envelope behavior.
  Files changed:
    - tests/test_sprints.py

- [x] **T11:** Run validation and fix failures until green. Use targeted commands first: `pytest tests/test_lockdown.py tests/test_gating.py tests/test_sprints.py`, adapter/migration tests, visibility tests, lifecycle/editorial-loop tests, then full `pytest`. Also write a short throwaway script that reproduces the specific Sprint 4 lifecycle/gating behavior, run it to confirm the implementation, then delete it. Do not create additional test files in this final validation task.
  Depends on: T10
  Executor notes: Ran targeted Sprint 4/adapter/envelope/end-of-turn/prompt tests successfully under Python 3.11.11 and ran the full suite. Full suite has one unrelated pre-existing dirty-worktree failure in the no-secret scanner reading a deleted `.megaplan` file; no Sprint 4 tests failed. Temporary reproduction script was run and deleted.

- [x] **T12:** Surface after_execute user_actions to the user:
- U1: Apply the Supabase migration to the real Supabase project and verify it in the production/staging database using secure credentials outside the repo.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T11
  Executor notes: Manual after-execute action remains surfaced: a human must apply the Supabase migration to the hosted Supabase project and verify it using secure credentials outside the repo. I did not perform hosted Supabase operations.
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
    - .megaplan/plans/sprint-4-sprint-mode/faults.json
    - .megaplan/plans/sprint-4-sprint-mode/final.md
    - .megaplan/plans/sprint-4-sprint-mode/finalize.json
    - .megaplan/plans/sprint-4-sprint-mode/finalize_snapshot.json
    - .megaplan/plans/sprint-4-sprint-mode/gate.json
    - .megaplan/plans/sprint-4-sprint-mode/plan_v1.md
    - .megaplan/plans/sprint-4-sprint-mode/plan_v1.meta.json
    - .megaplan/plans/sprint-4-sprint-mode/plan_v2.md
    - .megaplan/plans/sprint-4-sprint-mode/plan_v2.meta.json
    - .megaplan/plans/sprint-4-sprint-mode/state.json
    - .megaplan/plans/sprint-4-sprint-mode/step_receipt_critique_v1.json
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
    - agent_kit/resident.py
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
    - tests/test_sprint3_multi_epic.py
    - tests/test_sqlite_store.py
    - tests/test_supabase_adapters.py
    - tests/test_system_prompt.py

## Watch Items

- Do not invoke the `megaplan` CLI, read the `megaplan` skill, or start nested planning. Treat megaplan references as context only.
- Do not commit, log, or request the redacted Supabase service key. Use local SQLite, migration text checks, and fake Supabase adapter tests unless credentials are provided through normal environment channels.
- FLAG-003 remains open: entering `planned` must set `epics.planned_at`, and hot context must expose the all-sprints-pending/no-queued condition so the user can be warned.
- Keep enforcement deterministic and server-side. Do not add live LLM calls to gating unless the user explicitly changes the requirement.
- `edit_epic` is the single Sprint 4 write surface. Avoid adding a separate sprint write tool unless implementation evidence proves the schema is unmanageable.
- Pending sprints need a populated `pending_reason`; if omitted, store an explicit default such as `no reason given` so acceptance checks are stable.
- Use the existing markdown body parser behavior for section attribution and fenced-code handling; avoid introducing an incompatible parser for lockdown scanning.
- Sprint event snapshots are the canonical source for both revert and `get_epic_at_time`; do not let those paths drift.
- Invocation callers must see real `state_after`, `state_transition`, and `sprint_changes`; do not leave envelopes echoing `state_before` after successful writes.
- Natural language commands like `queue sprint 2` are prompt/model behavior; server code should receive structured `edit_epic` arguments and enforce correctness.
- Debt watch items about unrelated attachment/storage recovery are out of scope; avoid touching those areas unless required by tests.
- Queue positions for queued sprints must be unique per epic and should be normalized gaplessly after reorder operations.

## Sense Checks

- **SC1** (T1): Do both migration sets create `sprints` and `sprint_items` with matching checks, indexes, timestamps, and a partial unique index on `(epic_id, queue_position)` where status is `queued`?
  Executor note: Focused migration tests passed under Python 3.11.11, covering sprint tables, checks, indexes, timestamps, and queued-position uniqueness.

- **SC2** (T2): Can the common store interface create, load, list, update, delete, and item-replace sprints consistently across SQLite and Supabase adapters, and does hot context include sprint/items plus the all-pending/no-queued flag?
  Executor note: Focused store tests passed for sprint CRUD, item replacement/listing, loaded sprint snapshots, and the all-pending/no-queued hot-context flag.

- **SC3** (T3): Do sprint operations reject invalid payloads, assign lock-in defaults correctly, require pending reasons/defaults, maintain gapless queued positions, and return structured change summaries?
  Executor note: Sprint operations now reject invalid explicit lock-in assignments before mutation, keep pending reasons/defaults, preserve gapless queue behavior, and return structured change summaries in focused tests.

- **SC4** (T4): Do gates block underspecified `shaping -> sprinting`, enforce all `sprinting -> planned` invariants, require at least one sprint, and report lockdown phrase blockers with section and line number while exempting `Open Questions` and fenced code?
  Executor note: Gate and lockdown tests passed for underspecified shaping advancement, planned-state invariants, required sprints, phrase blocking, Open Questions exemption, and fenced-code exemption.

- **SC5** (T5): Does `edit_epic` remove the old unsupported guard, apply sprint/state writes atomically, set `planned_at`, return blockers and sprint/state deltas, and log `forced_handoff` with bypassed blockers when forced?
  Executor note: Focused tests passed for `edit_epic` sprint/state writes, `planned_at`, forced handoff logging, blockers, and rollback on invalid sprint input.

- **SC6** (T6): Can revert restore prior epic state, sprint rows, and sprint items for every new Sprint 4 event type without corrupting existing body/checklist revert behavior?
  Executor note: Focused tests passed for reverting sprint queue/reorder changes from prior sprint snapshots.

- **SC7** (T7): Do `get_epic` and `get_epic_at_time` expose current and historical sprint state accurately before and after lock-in, queue, pend, reorder, force, and revert events?
  Executor note: Focused tests passed for current `get_epic` sprint visibility and historical `get_epic_at_time` sprint reconstruction.

- **SC8** (T8): Do completed invocation envelopes reload real post-turn state and include `state_transition` plus `sprint_changes` for state advancement, lock-in, queue, and reorder operations?
  Executor note: Focused tests passed for invocation envelope `state_transition` and `sprint_changes` after Sprint 4 edits.

- **SC9** (T9): Do prompts and end-of-turn checks guide the two-beat flow, blocker options, queue/pend/reorder behavior, and all-pending planned-state warning without relying on unsupported tool shapes?
  Executor note: Prompt/end-of-turn focused tests passed; prompt text includes the two-beat lock-in flow, blocker options, queue/pend/reorder guidance, and all-pending warning behavior.

- **SC10** (T10): Do the added tests cover all acceptance criteria and the open critique item, while keeping helper tests deterministic and independent of production Supabase credentials?
  Executor note: Added direct tests for explicit lock-in validation and confirmation parsing; existing Sprint 4 tests cover the listed acceptance criteria without production Supabase credentials.

- **SC11** (T11): Do targeted tests, lifecycle/editorial-loop tests, the full suite, and the temporary reproduction script all pass after any necessary fixes, with the throwaway script deleted afterward?
  Executor note: Targeted validation passed and the temporary reproduction script was deleted. Full suite was run; one unrelated dirty-worktree no-secret scanner failure remains.

- **SC12** (T12): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: The hosted Supabase migration action is clearly identified as manual-only and was not performed in this session.

## Meta

Execute in dependency order: durable schema and store primitives first, deterministic sprint/gating logic second, `edit_epic` orchestration third, then visibility surfaces, prompts/end-of-turn behavior, and tests. The main implementation trap is treating Sprint 4 as only a database write: envelopes, hot context, read tools, replay, revert, and `planned_at` must all reflect the new sprint lifecycle. Keep the tool input structured and deterministic; natural-language interpretation belongs in the model loop and prompt guidance, not persistence adapters or gates.
