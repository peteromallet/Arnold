# Implementation Plan: Sprint 2b Editorial Polish

## Overview
The repo already has Sprint 2a editorial foundations in place: markdown body parsing in `agent_kit/body.py`, read/write epic tools in `agent_kit/tools/editorial_reads.py` and `agent_kit/tools/editorial.py`, audited tool execution in `agent_kit/tool_kit.py`, hot-context loading in both store adapters, and turn orchestration in `agent_kit/loop.py`. Sprint 2b should build directly on those seams instead of introducing a parallel memory or editing path.

The simplest implementation is one new persistence slice (`feedback` table + store methods), one new tool module for feedback/observations, small extensions to body read tools, and loop/model prompt wiring that makes the behavior visible to the agent. Keep the table unified exactly as specified: user feedback and agent observations share storage, but use separate tool entry points because their lifecycle and confirmation rules differ.

## Phase 1: Foundation - Schema, Store Contract, and Body Search

### Step 1: Add the unified feedback table (`agent_kit/store/migrations/sqlite/005_editorial_polish.sql`, `supabase/migrations/202604300005_005_editorial_polish.sql`)
**Scope:** Medium
1. **Create** the `feedback` table with the full Sprint 2b schema.
2. **Constrain** `kind` and `source` to the specified values.
3. **Index** active style/process feedback, epic-specific feedback, and unresolved observations.

### Step 2: Extend store protocols and adapters (`agent_kit/ports.py`, `agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`)
**Scope:** Medium
1. **Add** store methods for feedback CRUD and observation listing.
2. **Update** JSON handling for `context_snapshot`.
3. **Extend** `load_hot_context(epic_id)` with active feedback and last 5 unresolved observations.
4. **Preserve** current hot-context keys for compatibility.

### Step 3: Add body search helpers (`agent_kit/body.py`)
**Scope:** Small
1. **Enhance** outline support to include `###` and deeper subheadings.
2. **Implement** search results with 1-based line numbers, matching line, context window, and section attribution.
3. **Use** parser-derived section boundaries so fenced code blocks stay correct.

### Step 4: Register read tools (`agent_kit/tools/editorial_reads.py`)
**Scope:** Small
1. **Add** `get_body_outline(epic_id)`.
2. **Add** `search_in_body(epic_id, query, context_lines=2)`.
3. **Return** consistent `epic_not_found` and empty-result shapes.

## Phase 2: Feedback and Observation Tools

### Step 5: Add feedback tools (`agent_kit/tools/feedback.py`)
**Scope:** Medium
1. **Implement** `save_feedback`, `apply_feedback`, `deactivate_feedback`, and `list_feedback`.
2. **Reject** observation kinds in user-feedback tools.
3. **Omit** `priority` unless clarified, because the provided table schema has no priority column.

### Step 6: Add agent observation tools (`agent_kit/tools/feedback.py`)
**Scope:** Medium
1. **Implement** `record_observation`, `list_observations`, and `mark_observation_resolved`.
2. **Auto-fill** `source='agent_observation'`, `turn_id`, current `epic_id`, and `context_snapshot`.
3. **Import** the module in `agent_kit/loop.py` for registration.

## Phase 3: Prompt, Hot Context, and End-of-Turn Checks

### Step 7: Build explicit prompt/hot-context content (`agent_kit/templates.py`, `agent_kit/loop.py`, `agent_kit/model/anthropic.py`)
**Scope:** Medium
1. **Add** a concrete system prompt covering persona, communication style, feedback discipline, body search workflow, checklist depth guidance, showing changes, and observations.
2. **Pass** it to Anthropic as `system` content.
3. **Update** `DEFAULT_PROMPT_VERSION` to Sprint 2b.
4. **Expose** active feedback and unresolved observations in model-facing hot context.

### Step 8: Implement end-of-turn checks (`agent_kit/loop.py`)
**Scope:** Medium
1. **Add** a pure helper for the five categories.
2. **Guarantee** default acknowledgment when substantive tool work would finish without `send_message`.
3. **Log** non-blocking check findings to `system_logs`.
4. **Keep** existing mid-turn enforcement intact.

### Step 9: Enforce show-changes through behavior and tests
**Scope:** Small
1. **Keep** diffs in tool results/audit.
2. **Use** prompt instruction and scripted integration tests for concise change summaries.
3. **Avoid** brittle response post-processing.

## Phase 4: Tests and Evaluation Fixtures

### Step 10: Unit-test deterministic pieces
**Scope:** Medium
1. **Test** search, outline, feedback tools, observation tools, and end-of-turn helper logic.

### Step 11: Extend store contract tests
**Scope:** Medium
1. **Verify** SQLite/Supabase feedback CRUD, JSON round-trip, hot-context loading, and resolved-observation exclusion.

### Step 12: Add scripted loop integrations
**Scope:** Medium
1. **Verify** required tool-call sequences, explicit save, confirmation save flow, hot-context reload, observation lifecycle, `render_epic`, and default acknowledgment.

### Step 13: Add optional LLM-graded eval scaffolding
**Scope:** Medium
1. **Create** style/body-filler fixtures.
2. **Gate** live evals behind marker/env var so offline pytest stays green.

## Execution Order
1. Migrations and store methods.
2. Body helpers and read tools.
3. Feedback/observation tools.
4. Hot context and prompt plumbing.
5. End-of-turn checks.
6. Scripted integrations, then optional eval scaffolding.

## Validation Order
1. `pytest tests/test_body_parser.py tests/test_editorial_polish_tools.py`
2. `pytest tests/test_sqlite_store.py tests/test_supabase_adapters.py tests/test_supabase_store.py`
3. `pytest tests/test_editorial_loop.py tests/test_run_turn.py tests/test_mid_turn_messages.py tests/test_run_turn_hooks.py`
4. Full `pytest`.
