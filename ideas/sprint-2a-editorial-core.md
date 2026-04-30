# Sprint 2a — Editorial core

Bot maintains an epic body and checklist for one epic, with section-level body editing. Minimum to have an editorial conversation.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to it for complete details on Body Structure and Editing, Body Templates, The Checklist as Guide, and Data Model sections.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Tables: checklist_items, epic_events (with transaction_id)
- Body parser/serializer — markdown ↔ structured sections with ## heading delimiters; enforces heading hierarchy (# for title only, ## for sections, ### for sub-headings)
- Turn-end epic outline emitted to system_logs at info level
- Default body template (design doc) — Goal, Principles, Context, Key Decisions, Open Questions, Deliverable
- `edit_epic` tool — body (whole + section ops) + checklist; supports:
  - Write whole body
  - Write specific sections
  - Append to a section
  - Add new section with position
  - Rename/remove sections
  - `expected_diff` parameter for server-enforced diff verification (unified diff format)
- `create_epic`, `revert` (transaction-grouped), `render_epic` tools
- Read tools: `get_epic` (with section addressing), `get_section_names`, `get_history`, `get_self_understanding`
- History tools: `get_epic_at_time`, `get_recent_turns`, `search_tool_calls`
- Default checklist seed — 18 items with adaptation logic
- Title and goal are derived columns from body parsing (# Title and ## Goal first paragraph)

## Key Data Model

### checklist_items
id, epic_id, content, status (open|done|skipped|superseded), position, source (bot_inferred|user_requested|carried_over|default_seed|second_opinion), skip_reason, superseded_by_item_id, created_at, completed_at

### epic_events
id, epic_id, transaction_id (uuid), event_type, summary, prior_state (json), turn_id, occurred_at
Event types: body_edit, checklist_change, sprints_change, state_change, forced_handoff, created, code_referenced, codebase_added, image_generated, second_opinion_requested, reverted_to, sprint_status_change

## Body Parser Rules
- Section boundaries are ## headings (level-2 markdown)
- Section names are case-sensitive
- Pre-section content is "_preamble"
- Sub-sections (### and below) are part of parent section
- No ## headings → whole body is _preamble
- # Title and ## Goal are required structural elements; missing → write rejected
- Code blocks containing ## are NOT section boundaries

## Acceptance Criteria

- Create an epic via natural language → epics row created, default checklist seeded with 18 items, body initialized
- 10-turn scripted conversation (mocked Anthropic) produces body with all 6 default sections
- Section-level edit → only that section changes; other sections byte-identical
- Whole body edit → diff captured in event; revert restores prior version exactly
- "revert that" → most recent transaction undone, new reverted_to event logged
- expected_diff mismatch → server refuses write, returns actual diff
- expected_diff match → server commits normally
- get_epic_at_time(epic_id, T) → returns body/checklist state as of time T
- get_recent_turns(5) → returns 5 most recent turns with summaries
- search_tool_calls(tool_name='edit_epic', epic_id=X) → returns matching calls
- Turn-end system_logs row with event_type='epic_outline' containing title + section list + line counts

## Tests
- Unit: body parser (markdown → sections → markdown roundtrip is identity); section operations; edit_epic validation; transaction_id grouping; expected_diff comparison; epic-at-time replay
- Integration: 10-turn fixture conversation against local Supabase with mocked Anthropic; revert end-to-end
