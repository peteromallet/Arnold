# Implementation Plan: Sprint 3 — Multi-Epic + Message Search

## Overview
Implement multi-epic conversation handling so Arnold can choose, switch, summarize, and search epics/messages while respecting corrections and user modes. The full behavioral authority remains `planning-bot-spec.md`, especially Epic Selection, References to Bot's Recent Output, User Modes, and Showing the Bot's Understanding.

The critique changes the implementation approach in two important ways. First, epic selection cannot live only inside prompt/model response planning because the current flow locks the initial `epic_id` before context loading: `agent_kit/transport/discord.py` persists inbound messages, `agent_kit/resident.py` coalesces by payload `epic_id`, and `agent_kit/loop.py` locks that `epic_id`. Selection must therefore happen before `run_turn`, or a switch path must update message/turn routing and acquire the selected epic lock. Second, message search must go through the `Store` protocol in `agent_kit/ports.py` with both SQLite and Supabase implementations, not a Supabase-only helper.

## Phase 1: Audit and Pin Contracts

### Step 1: Audit spec and current routing contract (`planning-bot-spec.md`, `agent_kit/transport/discord.py`, `agent_kit/resident.py`, `agent_kit/loop.py`)
**Scope:** Small
1. Inspect the named spec sections in `planning-bot-spec.md` and extract required behavior for epic selection, references, modes, summaries, switching announcements, and gap acknowledgment.
2. Trace the current inbound path in `agent_kit/transport/discord.py`, especially `_message_epic_id(message)` and `DiscordTransport.on_message`.
3. Trace turn grouping in `agent_kit/resident.py`, especially `ArnoldResident.handle_transport_message` and payload coalescing by `payload["epic_id"]`.
4. Trace lock acquisition and hot-context loading in `agent_kit/loop.py`, especially `run_turn(epic_id=epic_id)`.
5. Record the exact pre-turn insertion point where a selected real epic can replace the synthetic/default conversation key before the lock is acquired.

### Step 2: Audit store abstraction and migrations (`agent_kit/ports.py`, `agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`, `agent_kit/store/migrations/sqlite/001_core.sql`, `supabase/migrations/202604300001_001_core.sql`)
**Scope:** Small
1. Inspect `agent_kit/ports.py` for the current `Store` protocol and existing read-tool method patterns.
2. Inspect `agent_kit/store/sqlite.py` and `agent_kit/store/supabase.py` to confirm mirrored adapter conventions.
3. Inspect SQLite and Supabase migrations to identify the `messages` and `epics` schema, available timestamps, status fields, and migration naming style.
4. Confirm whether inbound message rows can be reassigned to a selected epic after initial persistence; if no method exists, plan the smallest store method needed for message epic reassignment.

## Phase 2: Store-Portable Search Foundation

### Step 3: Extend the Store protocol for epic/message reads (`agent_kit/ports.py`)
**Scope:** Medium
1. Add Store protocol methods for `list_epics`, `search_epics`, and `search_messages` using existing async/sync style in `agent_kit/ports.py`.
2. Include stable result shapes with IDs, title/content snippets, status, timestamps, direction, rank where applicable, and enough metadata for disambiguation.
3. Add a minimal `reassign_message_epic` or equivalent method only if the routing audit shows inbound rows are persisted before final selection and cannot otherwise be attached to the selected epic.

### Step 4: Add full-text search to both stores (`agent_kit/store/migrations/sqlite/`, `supabase/migrations/`)
**Scope:** Medium
1. Add a SQLite migration under `agent_kit/store/migrations/sqlite/` using FTS5 or the repository's established SQLite full-text pattern for `messages.content`.
2. Add a Supabase migration under `supabase/migrations/` using PostgreSQL full-text search with a GIN index on `messages.content` or a generated/search vector column.
3. Keep search visibility scoped the same way as existing message reads, respecting user/conversation/epic boundaries already enforced by the store.
4. Avoid direct tool-level SQL; all reads should call the Store protocol.

### Step 5: Implement store methods in both adapters (`agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`)
**Scope:** Medium
1. Implement `list_epics`, `search_epics`, and `search_messages` in `agent_kit/store/sqlite.py`.
2. Implement matching behavior in `agent_kit/store/supabase.py`.
3. Keep ranking deterministic enough for canned tests; use store-native full-text rank where available and stable tie-breakers such as timestamp/message ID.
4. Implement message epic reassignment in both adapters if required by Step 2.

## Phase 3: Pre-Turn Epic Routing and Lock Safety

### Step 6: Add deterministic epic routing before turn creation (`agent_kit/resident.py`, new helper module if appropriate)
**Scope:** Medium
1. Add an epic-selection helper that runs before `ArnoldResident.handle_transport_message` coalesces queued payloads and before `agent_kit/loop.py` acquires a lock.
2. Inputs should include user message text, author/conversation identity, recent active epics from Store, current resident/default epic context, and prior selected epic if available.
3. Behavior:
   - Explicit epic names or correction phrases override recency.
   - Ambiguous messages use the most recently edited active epic within 24 hours when there is exactly one qualifying default.
   - If no qualifying or safe candidate exists, keep the conversation on the current/default context and produce a clarification request rather than mutating a real epic.
4. If the selected epic differs from the initially persisted payload epic, update the payload and persisted inbound message row before queuing/running the turn.

### Step 7: Enforce selected-epic locking and switch announcements (`agent_kit/resident.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Ensure `run_turn(epic_id=...)` is called with the selected real epic ID after routing, so `agent_kit/loop.py` acquires the correct epic lock before loading context or applying edits.
2. If any later model/tool path can still request an epic switch, add a guarded switch path that releases/re-acquires locks or rejects mutation until the next correctly routed turn.
3. Track previous selected epic per conversation/user and add a switch announcement containing the destination epic title when the selected epic changes.
4. Test that messages and outbound rows are attached to the selected epic, not left on `discord_user_<author>` when a real epic is selected.

## Phase 4: Tools and Bot Understanding

### Step 8: Register read tools through Store (`agent_kit/tools/`, `agent_kit/ports.py`)
**Scope:** Medium
1. Locate the existing tool registry under `agent_kit/tools/` or the actual registry file found during audit.
2. Register `list_epics`, `search_epics`, and `search_messages` as read tools that call Store protocol methods only.
3. Return concise, stable result payloads suitable for model disambiguation and user-facing summaries.
4. Add tool-handler tests that run against fake Store plus adapter contract tests where the repository already has them.

### Step 9: Implement reference resolution against last bot output (`agent_kit/loop.py`, message/context helper modules, tests)
**Scope:** Medium
1. Add a resolver for references like “the second one”, “that point”, and “the last option”.
2. Resolve only against the most recent outbound bot message in the same conversation/selected epic context.
3. Prefer structured outbound metadata if already available; otherwise parse common raw-text structures: numbered lists, bullets, headings, and short option lists.
4. Return resolved target plus ambiguity state to the turn planner; ask for clarification when confidence is low.

### Step 10: Implement user mode reading and conversation gap acknowledgment (`agent_kit/loop.py`, prompt/policy builder files found during audit)
**Scope:** Medium
1. Add mode detection for Deep-thinking, Brainstorming, and Executing.
2. Feed mode into response policy:
   - Deep-thinking: persona dialed down, measured and substantive.
   - Brainstorming: more energy, exploratory.
   - Executing: direct, minimal elaboration.
3. Keep mode detection separate from epic routing so mode phrases do not become epic references.
4. Detect conversation gaps using the threshold from `planning-bot-spec.md` and add the specified acknowledgment only when applicable.

### Step 11: Implement “show me what you know about X” summaries (`agent_kit/tools/`, `agent_kit/loop.py`, summary/prompt files found during audit)
**Scope:** Medium
1. Add intent handling for understanding-summary requests.
2. Resolve `X` through explicit epic match, `search_epics`, and `search_messages` Store tools.
3. Return the structured sections required by `planning-bot-spec.md`.
4. Ground the summary in stored epic/message data and avoid unsupported synthesis.

## Phase 5: Tests and Evaluation

### Step 12: Add store contract and migration tests (`tests/`, `agent_kit/store/`)
**Scope:** Medium
1. Add or extend Store contract tests so `list_epics`, `search_epics`, `search_messages`, and any message reassignment method pass against both SQLite and Supabase adapters.
2. Seed at least five active epics and a message corpus with 10 expected search-query hit sets.
3. Verify SQLite local/invocation mode and Supabase mode behave consistently for read tools.

### Step 13: Add routing and lock-safety tests (`tests/`, `agent_kit/resident.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Test that ambiguous messages route to the most recently edited active epic within 24 hours before `run_turn` is called.
2. Test that the selected epic ID is the one passed into `run_turn` and therefore the one locked by `agent_kit/loop.py`.
3. Test that inbound and outbound message rows attach to the selected epic after routing.
4. Test that unsafe late epic switches do not mutate a different epic without the correct lock.

### Step 14: Add focused behavior tests (`tests/`)
**Scope:** Medium
1. Epic selection fixtures: five active epics, one recent qualifying default, no qualifying default, multiple plausible candidates, explicit correction.
2. Reference resolver fixtures: numbered list, bullets, headings, mixed prose/list, ambiguous “that point”.
3. Mode detection fixtures for Deep-thinking, Brainstorming, and Executing.
4. Switch announcement tests verifying the outbound message contains the destination epic title only on actual switches.

### Step 15: Add integration and LLM-graded evals (`tests/`, eval harness files found during audit)
**Scope:** Medium
1. Add integration tests for multi-epic switching, message search retrieval, and understanding summaries against seeded data.
2. Add 30 canned epic-selection scenarios and require at least 27 correct.
3. Add 10 deliberately ambiguous scenarios and grade that the bot asks rather than guesses.
4. Keep eval fixtures deterministic and cheap enough for normal verification where possible.

## Execution Order
1. Start with the audit of routing/locking and Store contracts because those determine the correct insertion points.
2. Add Store protocol methods, migrations, and adapter implementations before registering tools.
3. Implement pre-turn epic routing before changing prompt/model behavior, so selected epic IDs are locked and persisted correctly.
4. Register tools and summary behavior after portable search exists.
5. Add reference resolution, modes, and gap acknowledgment once routing context is reliable.
6. Finish with integration tests and LLM-graded evals after deterministic unit and Store contract tests pass.

## Validation Order
1. Run focused Store contract tests for SQLite first, then Supabase adapter tests using the repository's existing test setup.
2. Run routing/lock-safety tests before broader bot integration tests.
3. Run unit tests for epic selection, reference resolution, and mode detection.
4. Run integration tests for switching, search tools, and understanding summaries.
5. Run LLM-graded evals for epic selection and ambiguity handling.
6. Finish with the repository's broader test and lint suite.
