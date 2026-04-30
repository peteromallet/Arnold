# Implementation Plan: Sprint 2b Editorial Polish

## Overview
Sprint 2b adds the editorial-assistant layer on top of the existing Sprint 2a document editor: durable feedback, agent observations, body search/outline tools, end-of-turn checks, show-changes behavior, and richer prompt guidance.

The existing repo shape is still the right implementation target. The critique flags do not show the plan was aimed at the wrong root cause; they expose two wiring gaps in the same architecture: cross-epic feedback must load even when there is no active epic, and prompt plumbing must update the full model boundary, not only the Anthropic adapter. The revised plan keeps the direct approach: extend the current `Store` protocol, tool registry, body parser helpers, and `run_turn` loop instead of adding a separate memory or prompt subsystem.

Two constraints matter most:
- Global `style` and `process` feedback is cross-epic and must load every turn, including new-epic and no-epic turns.
- The system prompt is part of the model-call contract and audit record, so `agent_kit/ports.py`, `agent_kit/model/fake.py`, `agent_kit/model/anthropic.py`, and the ledger `request_body` in `agent_kit/loop.py` must change together.

## Phase 1: Foundation - Schema, Store Contract, and Hot Context

### Step 1: Add the unified feedback table (`agent_kit/store/migrations/sqlite/005_editorial_polish.sql`, `supabase/migrations/202604300005_005_editorial_polish.sql`)
**Scope:** Medium
1. **Create** the `feedback` table with the full Sprint 2b schema: `id`, `kind`, `content`, `source`, `source_message_id`, `epic_id`, `turn_id`, `context_snapshot`, `active`, `deactivation_reason`, `resolved`, `resolution_note`, `resolved_at`, `created_at`, `last_referenced_at`, `last_applied_at`.
2. **Constrain** `kind` to `style|process|epic_specific|friction|ambiguity|tool_failure|confusion|pattern_noticed` and `source` to `user_volunteered|agent_proposed_user_confirmed|explicit_save_request|agent_observation`.
3. **Index** active style/process feedback, epic-specific feedback by `epic_id`, and unresolved observations by `epic_id/resolved/created_at`.

### Step 2: Extend store protocols and adapters (`agent_kit/ports.py`, `agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`)
**Scope:** Medium
1. **Add** store methods for `create_feedback`, `update_feedback`, `load_feedback`, `list_feedback`, and `list_observations`.
2. **Update** JSON handling for `context_snapshot` in both adapters.
3. **Change** `load_hot_context` to accept `epic_id: str | None`, not only `str`.
4. **Always load** active `style` and `process` feedback in `load_hot_context(None)` and `load_hot_context(epic_id)`.
5. **Additionally load** active `epic_specific` feedback and last 5 unresolved observations only when an `epic_id` is present.
6. **Preserve** existing keys: `epic`, `recent_messages`, and `recent_tool_calls`.

### Step 3: Wire no-epic hot context through the loop (`agent_kit/loop.py`, `tests/test_run_turn.py`)
**Scope:** Small
1. **Replace** the hard-coded no-epic context fallback with `store.load_hot_context(active_epic_id)` even when `active_epic_id` is `None`.
2. **Update** prompt snapshots and `_summarize_hot_context` to include active feedback and unresolved observation counts.
3. **Test** that a no-epic/new-epic turn receives active style/process feedback in the fake model call.

## Phase 2: Body Search and Read Tools

### Step 4: Add body search helpers (`agent_kit/body.py`, `tests/test_body_parser.py`)
**Scope:** Small
1. **Enhance** outline support to include `###` and deeper subheadings under each parent `##` section.
2. **Implement** search results with 1-based line numbers, matching line, context window, and section attribution.
3. **Use** parser-derived section boundaries so fenced code blocks stay consistent with existing body semantics.

### Step 5: Register read tools (`agent_kit/tools/editorial_reads.py`, `tests/test_editorial_polish_tools.py`)
**Scope:** Small
1. **Add** `get_body_outline(epic_id)`.
2. **Add** `search_in_body(epic_id, query, context_lines=2)`.
3. **Return** consistent `epic_not_found` and empty-result shapes.
4. **Export** both tools in `__all__`; existing `agent_kit/loop.py` imports should register them.

## Phase 3: Feedback and Observation Tools

### Step 6: Add feedback tools (`agent_kit/tools/feedback.py`, `tests/test_editorial_polish_tools.py`)
**Scope:** Medium
1. **Implement** `save_feedback(kind, content, epic_id?, source_message_id?, source, context_snapshot?)` for `style|process|epic_specific` only.
2. **Implement** `apply_feedback(feedback_id)` to update `last_applied_at` and `last_referenced_at`.
3. **Implement** `deactivate_feedback(feedback_id, reason)` to set `active=false` and `deactivation_reason`.
4. **Implement** `list_feedback(kind?, active_only=true, epic_id?)`.
5. **Omit** the older spec’s `priority` filter unless clarified, because the supplied Sprint 2b table schema has no `priority` column.

### Step 7: Add agent observation tools (`agent_kit/tools/feedback.py`, `agent_kit/loop.py`, `tests/test_editorial_polish_tools.py`)
**Scope:** Medium
1. **Implement** `record_observation(kind, content, epic_id?)` for `friction|ambiguity|tool_failure|confusion|pattern_noticed` only.
2. **Auto-fill** `source='agent_observation'`, `turn_id=context.turn_id`, current `epic_id`, and `context_snapshot` from turn metadata.
3. **Implement** `list_observations(kind?, epic_id?, resolved?, limit=20)` filtering rows where `source='agent_observation'`.
4. **Implement** `mark_observation_resolved(observation_id, resolution_note)` to set `resolved=true`, `resolution_note`, and `resolved_at` after validating the row is an observation.
5. **Import** `agent_kit.tools.feedback` in `agent_kit/loop.py` so the tools register in both modes.

## Phase 4: Prompt and Model Boundary

### Step 8: Build explicit prompt content (`agent_kit/templates.py`, `planning-bot-spec.md`, `tests/test_anthropic_model.py`)
**Scope:** Medium
1. **Add** a concrete system prompt builder covering persona, communication style, feedback discipline, body search workflow, checklist depth guidance for all 18 items, showing changes, end-of-turn checks, and self-observation guidance.
2. **Keep** prompt text source-controlled and testable rather than scattered inline in `agent_kit/loop.py`.
3. **Update** `DEFAULT_PROMPT_VERSION` in `agent_kit/loop.py` to a Sprint 2b version string.

### Step 9: Update the complete-turn contract (`agent_kit/ports.py`, `agent_kit/model/fake.py`, `agent_kit/model/anthropic.py`, `agent_kit/ledger.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. **Add** a `system: str | None` parameter to the `Model.complete_turn` protocol in `agent_kit/ports.py`.
2. **Update** `FakeModel.complete_turn` to accept and record `system` for scripted integration assertions.
3. **Update** `AnthropicModel.complete_turn` to pass `system` as the Anthropic Messages API top-level system prompt.
4. **Update** the loop’s Anthropic `request_body` and `request_summary` to include the system prompt or prompt version so audit/replay reflects what was actually sent.
5. **Update** `agent_kit/ledger.py` replay calls to pass the stored `system` value back into the model adapter.
6. **Adjust** existing model tests for the new parameter without changing their behavioral intent.

## Phase 5: End-of-Turn Checks and Show-Changes Behavior

### Step 10: Implement end-of-turn checks (`agent_kit/loop.py`, `tests/test_run_turn_hooks.py`, `tests/test_mid_turn_messages.py`)
**Scope:** Medium
1. **Add** a pure helper that evaluates the five categories: no message sent, no tool calls/progress, empty response, body unchanged when expected, and checklist stall.
2. **Guarantee** a default acknowledgment when substantive tool work would finish without an outbound `send_message`.
3. **Treat** empty model output without substantive work as the existing `empty_model_response` error path.
4. **Log** non-blocking check findings to `system_logs` for testable observability.
5. **Keep** existing mid-turn message enforcement intact and covered by tests.

### Step 11: Verify show-changes behavior (`agent_kit/tools/editorial.py`, `tests/test_editorial_polish_loop.py`)
**Scope:** Small
1. **Keep** diffs in `edit_epic` tool results and audit records.
2. **Use** system prompt instruction and scripted model tests to require concise change summaries after body edits.
3. **Avoid** response post-processing that rewrites model prose.

## Phase 6: Integration Tests and Optional Evals

### Step 12: Unit-test deterministic pieces (`tests/test_body_parser.py`, `tests/test_editorial_polish_tools.py`, `tests/test_sqlite_store.py`, `tests/test_supabase_store.py`)
**Scope:** Medium
1. **Test** `search_in_body` line numbers, context windows, section attribution, no-match behavior, and fenced-code edge cases.
2. **Test** `get_body_outline` section names, line counts, and subheadings.
3. **Test** feedback writes, invalid kind/source rejection, `apply_feedback`, deactivation, observation write defaults, and observation resolution.
4. **Test** store contract coverage for SQLite and Supabase feedback behavior.

### Step 13: Add scripted loop integrations (`tests/test_editorial_polish_loop.py`, `tests/test_editorial_loop.py`, `tests/test_run_turn.py`)
**Scope:** Medium
1. **Verify** `change the part about X` records `search_in_body -> get_epic(sections=[...]) -> edit_epic` in `tool_calls`.
2. **Verify** `Show me the epic` records `render_epic`.
3. **Verify** explicit save writes feedback immediately.
4. **Verify** agent-proposed-user-confirmed feedback flow across two turns.
5. **Verify** feedback save -> apply -> next-turn hot context includes updated feedback.
6. **Verify** no-epic turns still receive active style/process feedback.
7. **Verify** observation recorded -> hot context includes it -> resolved -> hot context excludes it.
8. **Verify** the default acknowledgment fires after substantive work without `send_message`.

### Step 14: Add optional LLM-graded eval scaffolding (`tests/fixtures/`, optional eval runner)
**Scope:** Medium
1. **Create** fixture sets for 20 style-violation turns and 20 body-filler turns.
2. **Gate** live evals behind an explicit marker or environment variable so normal offline pytest remains deterministic.
3. **Use** deterministic tests for feedback kind detection unless an existing LLM-eval harness is already present.

## Execution Order
1. Add migrations and store methods, including `load_hot_context(None)`.
2. Update loop hot-context loading so global feedback is present before tool behavior depends on it.
3. Add body helpers and read tools.
4. Add feedback and observation tools.
5. Add prompt builder, then update the full model boundary and ledger request/replay shape together.
6. Add end-of-turn checks after prompt/model plumbing is stable.
7. Finish with scripted integrations and optional eval scaffolding.

## Validation Order
1. `pytest tests/test_body_parser.py tests/test_editorial_polish_tools.py`
2. `pytest tests/test_sqlite_store.py tests/test_supabase_adapters.py tests/test_supabase_store.py`
3. `pytest tests/test_anthropic_model.py tests/test_anthropic_replay.py tests/test_run_turn.py`
4. `pytest tests/test_editorial_loop.py tests/test_editorial_polish_loop.py tests/test_mid_turn_messages.py tests/test_run_turn_hooks.py`
5. Full `pytest` once targeted checks pass.
6. Optional marked LLM evals only when model credentials are available.
