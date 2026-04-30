# Implementation Plan: Sprint 3 — Multi-Epic + Message Search

## Overview
Implement multi-epic conversation handling so the bot can choose, switch, summarize, and search epics and messages while respecting user corrections and modes. The spec authority is `planning-bot-spec.md`, especially the sections named in the brief: Epic Selection, References to Bot's Recent Output, User Modes, and Showing the Bot's Understanding.

I could not inspect the repository in this sandbox because shell execution returned no output, so the first implementation step must pin exact file names before coding. The plan assumes an existing bot runtime with message persistence in Supabase, an LLM/tool registry, and test coverage for conversation flows.

## Phase 1: Audit Current Bot Shape

### Step 1: Locate runtime, persistence, and prompt touch points
**Scope:** Small
1. Inspect `planning-bot-spec.md` and identify normative behavior for epic selection, reference resolution, user modes, and understanding summaries.
2. Use repository search to locate:
   - Message ingestion and outbound response creation.
   - Epic persistence and update timestamp fields.
   - Tool/function registry exposed to the LLM.
   - Prompt/system-instruction construction.
   - Existing Supabase migrations and seed/test database setup.
3. Record exact insertion points before editing. Expected touch points are likely:
   - Bot conversation orchestrator.
   - Supabase data access layer.
   - Tool definitions/handlers.
   - Prompt or policy builder.
   - Unit and integration test suites.

### Step 2: Confirm data model assumptions
**Scope:** Small
1. Verify the names and semantics of epic tables, message tables, outbound/inbound message direction fields, and edited timestamp fields.
2. Confirm whether `epics.updated_at`, `epics.last_message_at`, or an equivalent column should drive the 24h most-recent heuristic.
3. Confirm whether bot outbound messages are already stored with structured metadata, because reference resolution is easier and more reliable if the last bot output can be parsed from stored structure rather than raw text only.

## Phase 2: Database + Search Foundation

### Step 3: Add full-text search support for message content
**Scope:** Medium
1. Add a Supabase migration that creates a full-text search vector/index over `messages.content`.
2. Prefer generated `tsvector` column or expression GIN index using the repository's existing migration style.
3. Add a database function or query helper for ranked message search if the codebase already centralizes SQL/RPC search behavior.
4. Preserve row-level/security behavior used by the existing message queries.

### Step 4: Add search/list data access APIs
**Scope:** Medium
1. Implement data access helpers for:
   - `list_epics`: active/recent epics with IDs, titles, status, and timestamps.
   - `search_epics`: title/summary/metadata search, ranked enough for tool use.
   - `search_messages`: full-text search across message content returning stable message IDs, epic IDs, timestamps, direction, snippets, and rank.
2. Keep helpers thin and deterministic; do not bury LLM policy in database code.
3. Add seed fixtures for at least five active epics and a canned message corpus with expected hit IDs.

## Phase 3: Tooling + Runtime Behavior

### Step 5: Register `list_epics`, `search_epics`, and `search_messages` tools
**Scope:** Medium
1. Add tool schemas in the existing tool registry with narrow inputs and predictable outputs.
2. Include enough fields for the LLM to disambiguate epics without leaking unnecessary internal data.
3. Add tool-handler tests that verify filtering, ranking, and output shape.

### Step 6: Implement epic selection heuristic
**Scope:** Medium
1. Add a deterministic epic-selection module used before or during response planning.
2. Behavior:
   - If the user explicitly names or selects an epic, use that epic.
   - If the message is ambiguous and there is a most recently edited active epic within the last 24 hours, choose that epic.
   - If no recent epic qualifies, or several candidates are plausibly referenced, ask a clarification question instead of guessing.
3. Make the 24h window configurable in tests but fixed in production config unless the repo already has feature config.
4. Ensure corrections like “no, I meant Project B” update the selected epic context and do not keep applying work to the prior epic.

### Step 7: Add switching announcements
**Scope:** Small
1. Track previous active epic context per conversation/user.
2. When the selected epic changes, prepend or include a concise announcement containing the new epic title.
3. Test that switching messages include the title and non-switching messages do not repeatedly announce the same epic.

### Step 8: Implement reference resolution against last bot output
**Scope:** Medium
1. Add a resolver for references such as “the second one”, “that point”, “the last option”, and similar phrases.
2. Resolve against the most recent outbound bot message in the current conversation, preferring structured output metadata if available.
3. Parse common structures from raw text only where needed: numbered lists, bullets, headings, and short option lists.
4. Return a resolved target plus confidence/ambiguity status to the orchestrator.
5. Ask for clarification when the reference cannot be mapped confidently.

### Step 9: Add conversation gap acknowledgment
**Scope:** Small
1. Detect meaningful gaps since the last conversation turn using the timestamp threshold from `planning-bot-spec.md`.
2. Add a short acknowledgment only when the spec calls for it, avoiding repetitive acknowledgments inside active sessions.
3. Cover edge cases around first message, missing timestamps, and quick follow-ups.

### Step 10: Implement user mode reading
**Scope:** Medium
1. Add mode signal detection for Deep-thinking, Brainstorming, and Executing.
2. Feed the detected mode into prompt/runtime response policy:
   - Deep-thinking: less persona, measured and substantive.
   - Brainstorming: more energetic and exploratory.
   - Executing: direct, low elaboration.
3. Keep mode detection independent from epic selection so a mode phrase does not accidentally become an epic reference.
4. Add unit tests for direct mode commands and inferred mode cues if the spec requires inference.

### Step 11: Implement “show me what you know about X” summaries
**Scope:** Medium
1. Add intent handling for understanding-summary requests.
2. Resolve `X` to an epic, topic, or message set using explicit references, `search_epics`, and `search_messages`.
3. Return a structured summary with all relevant sections required by `planning-bot-spec.md`.
4. Include source-backed details from stored messages/epic metadata, not invented synthesis.

## Phase 4: Tests + Evaluation

### Step 12: Add focused unit tests
**Scope:** Medium
1. Epic selection fixtures:
   - Five active epics.
   - One most recently edited within 24h.
   - No qualifying recent epic.
   - Multiple plausible explicit/implicit candidates.
   - User correction after wrong or stale context.
2. Reference resolver fixtures:
   - Numbered list.
   - Bulleted list.
   - Headed sections.
   - Mixed prose plus list.
   - Ambiguous “that point”.
3. Mode detection fixtures for all three required modes.

### Step 13: Add integration tests
**Scope:** Medium
1. Seed Supabase/test DB with multiple epics and message corpus.
2. Test end-to-end multi-epic switching, including switch announcement text with epic title.
3. Test `search_messages` against 10 canned queries and expected hit IDs.
4. Test “show me what you know about X” produces the required structured sections.

### Step 14: Add LLM-graded eval scenarios
**Scope:** Medium
1. Add 30 canned epic-selection scenarios and require at least 27 correct.
2. Add 10 deliberately ambiguous cases and grade that the bot asks rather than guesses.
3. Keep eval fixtures deterministic and cheap to run locally where possible.

## Execution Order
1. Audit spec and exact repo touch points first.
2. Land DB migration and data access helpers before tool registration.
3. Add deterministic selection/reference/mode modules with unit tests before wiring them into the live bot flow.
4. Wire runtime behavior after the pure logic is covered.
5. Add integration tests and LLM evals last, once tool outputs and orchestration are stable.

## Validation Order
1. Run the cheapest focused unit tests for selection, reference resolution, and mode detection.
2. Run database migration tests or Supabase local reset against the seeded corpus.
3. Run integration tests for multi-epic switching and search tools.
4. Run LLM-graded evals for epic selection and ambiguity handling.
5. Finish with the repository’s broader test/lint suite.
