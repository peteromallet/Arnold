# Sprint 3 — Multi-epic + message search

Bot manages multiple epics intelligently and supports user corrections. Adds epic selection heuristic, switching, full-text search, reference resolution, and user modes.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to Epic Selection, References to Bot's Recent Output, User Modes, Showing the Bot's Understanding sections.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Epic selection heuristic — 24h most-recent default; bot picks most recently edited epic within 24h on ambiguous messages
- Epic switching with announcements (outbound message contains epic title when switching)
- `list_epics`, `search_epics`, `search_messages` tools
- Full-text search index on messages.content
- Ambiguity handling — bot asks when epic context is unclear
- Reference resolution — "the second one" / "that point" parsed against last outbound bot message
- Conversation gap acknowledgment
- User mode reading — concrete behaviors per mode:
  - Deep-thinking: persona dialed down, measured and substantive
  - Brainstorming: more energy, exploratory
  - Executing: direct, minimal elaboration

## Acceptance Criteria

- 5 epics active → bot picks most recently edited within 24h on ambiguous messages (LLM-graded eval: ≥27/30 correct on canned scenarios)
- "the second one" / "that point" reference resolution against last bot message (unit tests: ≥9/10 on varied last-message structures)
- Switching epics triggers announcement with epic title in outbound message
- "show me what you know about X" → structured summary with all relevant sections
- Full-text search across messages returns relevant matches (10 canned queries with expected hit IDs)

## Tests
- Unit: epic selection heuristic across epic-set fixtures; reference resolver against varied bot output; mode signal detection
- Integration: multi-epic switching, search retrieval against seeded message corpus
- LLM-graded eval: ambiguity handling — bot asks (vs guesses) on 10 deliberately ambiguous cases
