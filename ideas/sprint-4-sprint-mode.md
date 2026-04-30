# Sprint 4 — Sprint mode and handoff gating

Epics can be taken through the full lifecycle to handoff-ready (planned) state, with sprints queued or pending. Every epic produces at least one sprint.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to Sprint Organization, State Advance Gating, Epic Abstraction Level sections.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Tables: sprints (with queue_position, pending_reason, status values), sprint_items
- edit_epic extension for sprints field including status transitions
- State advance gating logic — concrete conditions enforced server-side:
  - shaping → sprinting: body >500 chars, Goal + Deliverable sections, checklist mostly resolved
  - sprinting → planned: all sprints queued or pending, checklist done/skipped/superseded, PM-handoff fidelity
- Open-decisions lockdown scan: regex check for TBD/to be decided/to be determined/we'll see/figure out later/tunable/depends on what surfaces/can adjust later/decide later — matches outside Open Questions section block sprinting → planned unless force-through
- Blocker surfacing flow — list open items, offer skip/address/force
- Sprint shaping: propose → refine → finalize, items at PM-task level
- Every epic produces at least one sprint (including decision docs, conversation prep)
- Two-beat lock-in flow: confirmation → queue/pend assignment (first sprint queued, rest pending)
- Pending reason capture
- Queue reordering via natural language
- Force-through with logging (forced_handoff event)
- Phase-aware end-of-turn checks

## Key Data Model

### sprints
id, epic_id, sprint_number, name, goal, status (proposed|queued|pending|done), queue_position (nullable int), pending_reason (nullable), target_weeks (default 2), created_at, updated_at, queued_at
Unique constraint: (epic_id, queue_position) WHERE status='queued'

### sprint_items
id, sprint_id, content, estimated_complexity (small|medium|large), status (open|in_progress|done), source_section, position, created_at

## Acceptance Criteria

- Try to advance shaping → sprinting with body <500 chars → edit_epic fails with blockers list
- Force-through with force: true → succeeds, forced_handoff event logged
- Sprint shaping → sprints rows edited; lock-in moves to queued/pending
- Decision-doc epic → at least one sprint (test: create, take through lifecycle, assert ≥1 sprint)
- After lock-in: each sprint is queued (with queue_position) or pending (with pending_reason); epic → planned
- Two queued sprints can't share queue_position (DB constraint)
- Post-handoff: "queue sprint 2" → status flips, position assigned
- Post-handoff: "do sprint 3 first" → queue_positions adjusted, audit event logged
- Lockdown scan blocks when body contains "TBD" outside Open Questions; passes when in Open Questions

## Tests
- Unit: gating condition evaluation; confirmation parsing; queue/pend defaults; queue reordering; lockdown scan regex
- Integration: full epic lifecycle (create → shape → sprint → finalize → queue/pend → planned)
