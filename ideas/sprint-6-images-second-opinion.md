# Sprint 6 — Image generation and second opinion

Bot can generate images as referenceable epic objects (extending user-uploaded foundation from Sprint 1b), and audit epics via a second model (OpenAI GPT-5.5).

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to Images, Second Opinion Mode, second_opinions table sections.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Table: second_opinions; images table already exists from Sprint 1b
- OpenAI API integration — image generation (gpt-image-2) + chat for second opinions (gpt-5.5)
- `generate_image` tool — prompt construction from epic context, quality logic (low/medium/high), auto-generated reference_key, description capture; populates images row with source='agent_generated'
- Body-reference syntax: ![description](image:reference_key) → resolved to storage_url at render
- Image regeneration: new row, older version deactivated if reference_key reused
- `request_second_opinion` tool — structured output prompt with scoring rubric (0-10), distillation
- Auto-second-opinion at state-advance gates (default-on, user can decline)
- Score-based behavior — score <5 triggers re-framing suggestion
- Proposed-checklist-items workflow for second opinion findings

## Key Data Model

### second_opinions
id, epic_id, requested_at, requested_by (user|auto_state_gate), focus_areas, raw_response, score (int 0-10), summary, verdict, resulting_checklist_item_ids (uuid array), model_used

## Acceptance Criteria

- "draw the data flow" (mocked) → generate_image called (mocked OpenAI), images row created with source=agent_generated, then send_image posts to Discord. Two separate tool calls in audit.
- Body ![flow](image:img_data_flow) → render_epic resolves to storage_url (works for both sources)
- Regeneration with same reference_key → new row active, prior deactivated
- "get a second opinion" (mocked) → second_opinions row with score
- Score <5 → bot's next response includes re-framing suggestion (LLM-graded)
- Score 6 with 3 holes → bot proposes 3 checklist items

## Tests
- Unit: score-based re-framing trigger; structured-output parsing; quality auto-selection; reference_key uniqueness
- Integration: full image generation flow with body reference (mocked OpenAI + Storage); regeneration with deactivation; full second opinion flow with checklist proposal
