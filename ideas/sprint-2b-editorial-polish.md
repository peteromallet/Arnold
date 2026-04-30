# Sprint 2b — Editorial polish

Thoughtful behaviors that distinguish a real editorial assistant from a body editor. Adds feedback system, end-of-turn checks, search tools, and agent observations.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to How to Work Each Checklist Item, Feedback System, End-of-Turn Checks, Communication Style, Persona sections.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Table: feedback (single table for user feedback AND agent observations)
- Per-item depth guidance in system prompt for all 18 checklist items
- End-of-turn checks — five categories (no message sent, no tool calls, empty response, body unchanged when expected, checklist stall)
- Show-changes pattern in responses
- `search_in_body` tool — returns line numbers + surrounding context + section attribution
- `get_body_outline` tool — section names + line counts
- Feedback tools: save_feedback, apply_feedback, deactivate_feedback, list_feedback
- Agent observation tools: record_observation, list_observations, mark_observation_resolved
- Hot-context loading of active style + process feedback with last_applied_at AND recent unresolved observations
- Agent-proposed-user-confirmed flow for saving feedback
- Agent-only flow for observations (no user confirmation)

## Feedback Table
id, kind (style|process|epic_specific|friction|ambiguity|tool_failure|confusion|pattern_noticed), content, source (user_volunteered|agent_proposed_user_confirmed|explicit_save_request|agent_observation), source_message_id, epic_id, turn_id, context_snapshot (json: {user_message, bot_action_being_critiqued}), active (default true), deactivation_reason, resolved (default false), resolution_note, resolved_at, created_at, last_referenced_at, last_applied_at

Two semantic groups:
- User feedback (style, process, epic_specific) — active → deactivated; tracked via last_applied_at
- Agent observations (friction, ambiguity, tool_failure, confusion, pattern_noticed) — open → resolved; tracked via resolved_at

## Acceptance Criteria

- "change the part about X" → bot calls search_in_body, then get_epic for matching section, then edit_epic (verifiable via tool_calls sequence)
- get_body_outline returns section names + line counts matching actual body
- "stop apologizing" → bot proposes saving as style feedback, user confirms, row written; subsequent turn honors it via hot context
- "save this: keep messages under 200 words" → bot saves immediately (explicit save)
- apply_feedback(id) → last_applied_at updated
- record_observation(kind='friction', ...) → row written with turn_id and context_snapshot; surfaces in hot context next turn
- mark_observation_resolved(id, "user clarified") → resolved_at set, not in hot context
- "Show me the epic" → render_epic called
- End-of-turn check fires when bot tries to finish without sending message → default acknowledgment

## Tests
- Unit: search_in_body returns correct results; get_body_outline accuracy; feedback kind detection; end-of-turn check logic; observation writes
- Integration: feedback save → apply → reload; observation recorded → reload → resolved
- LLM-graded eval: 20 fixture turns with style violations; 20 turns checking body for filler
