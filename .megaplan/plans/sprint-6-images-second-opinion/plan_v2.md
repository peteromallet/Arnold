# Implementation Plan: Sprint 6 Images And Second Opinion

## Overview
Arnold already has the Sprint 1b image foundation: `images` migrations exist, `agent_kit/tools/images.py` has `list_images`, `view_image`, `send_image`, and `update_image_metadata`, and both stores implement basic image CRUD. The Sprint 6 gaps are generated-image operations, `image:` reference resolution in `render_epic`, `second_opinions` persistence, OpenAI-backed second-opinion tooling, score-driven reframing, and proposed checklist items.

The critique does not show that the plan targets the wrong code or root cause. It shows two missing integration details in the right implementation area: result-dependent external effects need `external_requests` coverage despite not fitting the existing `context.external_queue` post-commit pattern, and confirmed second-opinion checklist items need a real link path back to `second_opinions.resulting_checklist_item_ids`. The revised plan keeps the same repo touch points but makes those two mechanics explicit.

## Phase 1: Foundation - DB, Store, Provider Injection

### Step 1: Add second-opinion persistence (`supabase/migrations/`, `agent_kit/store/migrations/sqlite/`)
**Scope:** Small
1. Add migration `008_second_opinions` for SQLite and Supabase with `id`, `epic_id`, `requested_at`, `requested_by`, `focus_areas`, `raw_response`, `score`, `summary`, `verdict`, `resulting_checklist_item_ids`, and `model_used`.
2. Add indexes on `(epic_id, requested_at desc)` and `score`.
3. Store arrays using existing adapter conventions: JSON text in SQLite; JSON-compatible or native array data in Supabase based on the current adapter style.

### Step 2: Extend store contracts (`agent_kit/ports.py`, `agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`)
**Scope:** Medium
1. Add `create_second_opinion`, `list_second_opinions`, and `set_second_opinion_checklist_items`.
2. Add image lookup helpers needed by generation and rendering: active image by `(epic_id, reference_key)`, active reference-key existence checks, and active-row deactivation before reference-key reuse.
3. Extend `load_hot_context` with active image metadata and the latest two second-opinion summaries. Do not include image bytes.
4. Keep existing partial unique image index as the database backstop for one active row per `(epic_id, reference_key)`.

### Step 3: Add injectable OpenAI operations (`pyproject.toml`, new `agent_kit/openai_ops.py`, `agent_kit/ports.py`, `agent_kit/tool_kit.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Add the `openai` dependency if absent.
2. Define a narrow injectable operation port for Sprint 6:
   - `generate_image(prompt, quality, size, idempotency_key) -> bytes plus provider metadata`
   - `request_second_opinion(payload, idempotency_key) -> parsed payload, raw response, provider metadata`
3. Add optional `openai_ops` to `ToolContext` and `run_turn`; default to the real adapter outside tests.
4. Tests inject fake OpenAI operations. The default test suite must not make live network calls.

### Step 4: Add synchronous external-effect ledger support (`agent_kit/ledger.py`, `agent_kit/tool_kit.py`, `agent_kit/ports.py`)
**Scope:** Medium
1. Add a tool-facing helper for result-dependent effects that cannot use `context.external_queue` because the tool needs provider output before it can write the domain row.
2. The helper records an `external_requests` row with `status='pending'` before each OpenAI or Storage effect, passes an idempotency key to providers that support it, then marks the row `confirmed` or `failed`.
3. Use this helper in `generate_image` for OpenAI image generation and Storage upload, and in `request_second_opinion` for the GPT-5.5 call.
4. Preserve existing `context.external_queue` behavior for post-commit effects such as `send_image` Discord posting.
5. Add tests that assert `external_requests` rows exist and are confirmed/failed for mocked OpenAI and Storage effects.

## Phase 2: Image Generation And Rendering

### Step 5: Implement generation helpers (`agent_kit/tools/images.py`)
**Scope:** Medium
1. Add quality selection helpers: explicit `quality` wins; rough/draft/sketch language maps to `low`; final/deliverable/text-heavy requests map to `high`; default is `medium`.
2. Add agent reference-key generation: `img_<8 hex chars>`, checked for active uniqueness within the epic.
3. Build the provider prompt from user prompt plus compact epic context: title, goal, body outline, and existing active image descriptions.
4. Derive a concise default description from the prompt and image purpose.

### Step 6: Add `generate_image` tool (`agent_kit/tools/images.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Register `generate_image(epic_id, prompt, quality?, size?, reference_key?, caption?)`.
2. Validate `reference_key` with `REFERENCE_KEY_RE`.
3. Use the synchronous external ledger helper to call OpenAI `gpt-image-2` and upload bytes via the `Blob` port.
4. Create an `images` row with `source='agent_generated'`, prompt, selected quality, size, reference key, description, caption, storage URL, and `active=true`.
5. If the reference key is reused, deactivate the prior active image row in the same DB transaction before inserting the new row.
6. Return `image_id`, `reference_key`, `storage_url`, `quality`, `size`, `description`, and external request IDs. Do not post to Discord; `send_image` remains a separate audited tool call.

### Step 7: Resolve body image references (`agent_kit/tools/editorial.py`)
**Scope:** Small
1. Update `render_epic` so markdown output resolves `![caption](image:reference_key)` to `![caption](storage_url)` using the active image row for that epic.
2. Leave raw `epics.body` untouched.
3. For missing keys, render a stable broken-reference placeholder and include `missing_image_references` in the tool result.
4. Use the same resolver for `user_uploaded` and `agent_generated` sources.

## Phase 3: Second Opinion Tooling And Checklist Linking

### Step 8: Add structured parsing and scoring helpers (new `agent_kit/second_opinion.py`)
**Scope:** Medium
1. Build the GPT-5.5 prompt from epic body, checklist, sprints, recent feedback, and optional focus/scoring overrides.
2. Define structured response parsing for `score`, `strengths`, `holes`, `verdict`, and `summary`.
3. Reject malformed output deterministically: invalid score, missing verdict, or malformed holes should return a tool error.
4. Convert significant holes into proposed checklist item objects without writing checklist rows automatically.

### Step 9: Implement `request_second_opinion` (`agent_kit/tools/second_opinion.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Register `request_second_opinion(epic_id, focus_areas?, scoring_override?, requested_by?)`; default `requested_by` to `user`.
2. Use the synchronous external ledger helper to call OpenAI `gpt-5.5`.
3. Store raw response, parsed score, summary, verdict, focus areas, requested_by, and model string in `second_opinions`.
4. Return `second_opinion_id`, score, summary, verdict, holes, and proposed checklist items. Leave `resulting_checklist_item_ids` empty until user-confirmed checklist rows are created.
5. Update `prompts/system.md` so the bot surfaces score/verdict, proposes checklist items individually, never auto-edits the epic from audit findings, and suggests reframing when score is below 5.

### Step 10: Link confirmed checklist items back to second opinions (`agent_kit/tools/editorial.py`, stores, tests)
**Scope:** Medium
1. Extend checklist add inputs accepted by `edit_epic` with optional `source_second_opinion_id` on added items.
2. Change `_apply_checklist_changes` to return created checklist rows instead of discarding `add_checklist_items` results.
3. Include `created_checklist_items` and `created_checklist_item_ids` in the `edit_epic` result.
4. When added checklist items carry `source_second_opinion_id`, update that `second_opinions.resulting_checklist_item_ids` with the created IDs in the same edit transaction.
5. Keep the workflow user-confirmed: `request_second_opinion` proposes; a later `edit_epic` call creates and links only the confirmed items.

### Step 11: Wire score-based and gate behavior (`agent_kit/end_of_turn.py`, `agent_kit/gating.py`, `prompts/system.md`)
**Scope:** Medium
1. Add deterministic helper coverage for score `<5` requiring a reframing suggestion in the next response path.
2. Use prompt + hot-context guidance for response content, with an end-of-turn finding only when a just-requested second opinion below 5 is followed by no reframe signal.
3. Surface missing/stale second opinion at state-advance gates as default-on advisory workflow, not a hard state blocker. The user can decline.
4. Add a decline-path test so process feedback like `skip second opinion until I ask` suppresses the advisory workflow.

## Phase 4: Tests And Validation

### Step 12: Add focused unit tests (`tests/test_image_tools.py`, new `tests/test_second_opinion.py`, `tests/test_end_of_turn.py`)
**Scope:** Medium
1. Test quality auto-selection, explicit override, reference-key validation, and generated-key uniqueness.
2. Test regeneration with the same reference key deactivates the prior active row and leaves the new row active.
3. Test structured-output parsing for valid and invalid GPT-5.5 responses.
4. Test score `<5` reframing trigger and score `6` with three holes producing three proposed checklist items.
5. Test external request rows for mocked OpenAI image, mocked Storage upload, and mocked GPT-5.5 second opinion.
6. Test `edit_epic` returns created checklist IDs and links IDs to `second_opinions.resulting_checklist_item_ids` when `source_second_opinion_id` is supplied.

### Step 13: Add integration tests (`tests/test_sprint6_images_second_opinion.py`)
**Scope:** Medium
1. Script `draw the data flow` so the model calls `generate_image`, then `send_image`; assert two separate `tool_calls` rows, an `images` row with `source='agent_generated'`, and external request rows for OpenAI/Storage.
2. Seed a body with `![flow](image:img_data_flow)` and assert `render_epic` resolves it to active `storage_url` for both user-uploaded and agent-generated rows.
3. Mock OpenAI and Blob storage for the full generation path.
4. Script `get a second opinion` and assert a `second_opinions` row with score/model/raw response plus an OpenAI external request row.
5. Script score 6 with three holes and user confirmation; assert three checklist items are added through `edit_epic` and their IDs are linked to the originating second opinion row.

## Execution Order
1. Land migrations and store methods first; run store-focused tests before provider/tool behavior.
2. Add fake OpenAI operation injection and synchronous external ledger helper before implementing `generate_image` or `request_second_opinion`.
3. Implement `render_epic` resolution before full image generation; it is cheap and independently testable.
4. Add `generate_image`, including external request coverage, then prove `generate_image` and `send_image` are separate audit rows.
5. Add second-opinion persistence/parser/tooling, then the checklist-linking change in `edit_epic`.
6. Wire prompt/end-of-turn/gate behavior after tool result shapes are stable.
7. Finish with Sprint 6 integration tests and full regression.

## Validation Order
1. `pytest tests/test_image_tools.py tests/test_second_opinion.py`
2. `pytest tests/test_sprint6_images_second_opinion.py`
3. `pytest tests/test_editorial_loop.py tests/test_image_attachment_pipeline.py tests/test_end_of_turn.py`
4. Full `pytest` once targeted checks pass.
