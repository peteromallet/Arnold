# Implementation Plan: Sprint 6 Images And Second Opinion

## Overview
Arnold already has the Sprint 1b image foundation: `images` migrations exist, `agent_kit/tools/images.py` has `list_images`, `view_image`, `send_image`, and `update_image_metadata`, and both stores implement basic image CRUD. The gaps for Sprint 6 are: generated-image operations, `image:` reference resolution in `render_epic`, `second_opinions` persistence, OpenAI-backed second-opinion tooling, and prompt/end-of-turn behavior around score-driven reframing and proposed checklist items.

The lowest-risk path is to extend the existing tool/store patterns rather than create a separate subsystem. Keep provider calls injectable for tests, keep generated images and user uploads in the same `images` table, and make `generate_image` creation separate from `send_image` posting as required by the acceptance criteria.

## Phase 1: Foundation - DB, Ports, Provider Injection

### Step 1: Add second-opinion persistence (`supabase/migrations/`, `agent_kit/store/migrations/sqlite/`)
**Scope:** Small
1. Add migration `008_second_opinions` for SQLite and Supabase with the spec columns: `id`, `epic_id`, `requested_at`, `requested_by`, `focus_areas`, `raw_response`, `score`, `summary`, `verdict`, `resulting_checklist_item_ids`, `model_used`.
2. Add indexes on `(epic_id, requested_at desc)` and `score`.
3. Keep JSON/array handling consistent with current store conventions: SQLite stores arrays as JSON text, Supabase stores JSON-compatible values or Postgres arrays depending on existing adapter ergonomics.

### Step 2: Extend store contracts (`agent_kit/ports.py`, `agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`)
**Scope:** Medium
1. Add `create_second_opinion`, `list_second_opinions`, and `update_second_opinion` or a narrow `set_second_opinion_checklist_items` method.
2. Add image helper behavior needed by generation: list active image by `reference_key` within an epic, deactivate prior active rows before reusing a key, and preserve the existing partial unique index.
3. Extend `load_hot_context` to include active image metadata and the last two second-opinion summaries so the system prompt can reason about references and recent audits without loading image bytes.

### Step 3: Add OpenAI operation adapter (`pyproject.toml`, new `agent_kit/openai_ops.py`, `agent_kit/ports.py`, `agent_kit/tool_kit.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Add the `openai` dependency if the project does not already vendor it indirectly.
2. Define a small injectable operation port for Sprint 6 rather than overloading the main Anthropic `Model` port:
   - `generate_image(model, prompt, quality, size, idempotency_key?) -> bytes + provider metadata`
   - `second_opinion(model, messages/schema or prompt, idempotency_key?) -> structured response + raw response + provider metadata`
3. Add an optional `openai_ops` dependency to `ToolContext` and `run_turn`, with a default real adapter when not supplied.
4. Tests should pass fake OpenAI operations directly into `ToolContext` or `run_turn`; no live OpenAI calls in the default suite.

## Phase 2: Image Generation And Rendering

### Step 4: Implement generation helpers (`agent_kit/tools/images.py`)
**Scope:** Medium
1. Add quality selection helpers: explicit `quality` wins; otherwise infer `low` for rough/draft/sketch language, `high` for final/deliverable/text-heavy requests, and `medium` by default.
2. Add agent reference-key generation: `img_<8 hex chars>`, checked for active uniqueness within the epic.
3. Build the generation prompt from the user prompt plus compact epic context: title, goal, relevant body outline, and existing image descriptions. Do not include full image bytes.
4. Generate a default description from the prompt and intended purpose unless an explicit description field is introduced later.

### Step 5: Add `generate_image` tool (`agent_kit/tools/images.py`, `agent_kit/loop.py` imports)
**Scope:** Medium
1. Add schema for `generate_image(epic_id, prompt, quality?, size?, reference_key?, caption?)`.
2. Validate `reference_key` with the existing `REFERENCE_KEY_RE`.
3. Call OpenAI `gpt-image-2`, upload bytes through the existing `Blob` port, and create an `images` row with `source='agent_generated'`, prompt, quality, size, reference key, description, caption, and `active=true`.
4. If the supplied/reused reference key already has an active row for the same epic, deactivate that prior row in the same DB transaction before inserting the new one.
5. Return `image_id`, `reference_key`, `storage_url`, `quality`, `size`, and `description`. Do not post to Discord; `send_image` remains a separate audited tool call.

### Step 6: Resolve body image references (`agent_kit/tools/editorial.py`)
**Scope:** Small
1. Update `render_epic` so markdown output resolves `![caption](image:reference_key)` to `![caption](storage_url)` using the active image row for that epic.
2. Leave raw `epics.body` untouched.
3. For missing keys, render a stable broken-reference placeholder and include a `missing_image_references` field in the tool result so the bot can repair the body later.
4. Keep both user-uploaded and agent-generated images on the same resolution path.

## Phase 3: Second Opinion Tooling

### Step 7: Add structured parsing and scoring helpers (new `agent_kit/second_opinion.py`)
**Scope:** Medium
1. Build the GPT-5.5 prompt from epic body, checklist, sprints, recent feedback, and optional `focus_areas` / `scoring_override`.
2. Define the structured response schema around `score`, `strengths`, `holes`, `verdict`, and `summary`.
3. Add parser validation that clamps nothing silently: invalid score, missing verdict, or malformed holes should return a tool error rather than inventing data.
4. Add a helper to convert significant holes into proposed checklist item text without writing checklist rows automatically.

### Step 8: Implement `request_second_opinion` (`agent_kit/tools/second_opinion.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Register `request_second_opinion(epic_id, focus_areas?, scoring_override?, requested_by?)` with `requested_by` defaulting to `user` unless called by a state gate.
2. Call OpenAI `gpt-5.5`, store raw response, parsed score, summary, verdict, focus areas, and model string in `second_opinions`.
3. Return score, summary, verdict, holes, and `proposed_checklist_items`; leave `resulting_checklist_item_ids` empty until the user confirms items and `edit_epic` creates them.
4. Update prompt guidance in `prompts/system.md`: surface score/verdict, propose checklist items individually, never auto-edit the epic based solely on audit findings, and suggest reframing when score is below 5.

### Step 9: Wire score-based behavior (`agent_kit/end_of_turn.py`, `agent_kit/loop.py`, `prompts/system.md`)
**Scope:** Medium
1. Add deterministic helper coverage for “second opinion score <5 means the next response should include a reframing suggestion.”
2. Prefer prompt + hot-context guidance for response content, with a lightweight end-of-turn finding only if a turn just requested a second opinion and the outbound response omits the required reframe signal.
3. For score 5-6 with holes, ensure the tool result shape makes checklist proposals obvious to the model; integration tests can script the model to add exactly the proposed checklist items after user confirmation.

### Step 10: Auto-second-opinion gate support (`agent_kit/gating.py`, `agent_kit/tools/editorial.py`, `prompts/system.md`)
**Scope:** Medium
1. Surface “recent second opinion missing or stale” as advisory gate context for state advances, default-on but declinable by the user.
2. Do not block hard server-side state transitions solely because no second opinion exists unless the existing spec/tests require it; the idea says “default-on, user can decline,” so implement this as prompt/tool workflow rather than an unconditional DB gate.
3. Add tests for the decline path so user process feedback like “skip second opinion until I ask” can suppress the prompt-level suggestion.

## Phase 4: Tests And Validation

### Step 11: Add focused unit tests (`tests/test_image_tools.py`, new `tests/test_second_opinion.py`, `tests/test_end_of_turn.py`)
**Scope:** Medium
1. Test quality auto-selection, explicit override, reference-key validation, and generated-key uniqueness.
2. Test regeneration with the same reference key deactivates the prior active row and leaves the new row active.
3. Test structured-output parsing for valid and invalid GPT-5.5 responses.
4. Test score `<5` reframing trigger and score `6` with three holes producing three proposed checklist items.

### Step 12: Add integration tests (`tests/test_sprint6_images_second_opinion.py`)
**Scope:** Medium
1. Script “draw the data flow” so the model calls `generate_image`, then `send_image`; assert two separate `tool_calls` rows and an `images` row with `source='agent_generated'`.
2. Seed a body with `![flow](image:img_data_flow)` and assert `render_epic` resolves it to the active `storage_url` for both user-uploaded and agent-generated rows.
3. Mock OpenAI and Blob storage for the full image generation flow.
4. Script “get a second opinion” and assert a `second_opinions` row with score/model/raw response.
5. Script score 6 with three holes and user confirmation, then assert three checklist items are added via `edit_epic` and resulting IDs can be linked back to the second-opinion row.

## Execution Order
1. Land migrations and store methods first; run store-focused tests before touching model/tool behavior.
2. Add fake OpenAI operation injection before implementing tools, so no test path requires network access.
3. Implement `render_epic` resolution before full generation flow; it is cheap and independently testable.
4. Add `generate_image`, then the integration flow that proves `generate_image` and `send_image` are separate audit rows.
5. Add second-opinion persistence and parser, then wire prompt/end-of-turn behavior.
6. Finish with full Sprint 6 integration tests and existing suite regression.

## Validation Order
1. `pytest tests/test_image_tools.py tests/test_second_opinion.py`
2. `pytest tests/test_sprint6_images_second_opinion.py`
3. `pytest tests/test_editorial_loop.py tests/test_image_attachment_pipeline.py tests/test_end_of_turn.py`
4. Full `pytest` once targeted checks pass.
