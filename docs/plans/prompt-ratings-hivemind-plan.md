# Prompt Response Public Rating + Debug ZIP Upload — Implementation Plan

## Decisions

1. **Dedicated table** in the Hivemind Supabase Postgres database for prompt ratings.
2. **Hivemind edge function** as the write path. It accepts the rating metadata and an optional ZIP bundle, uploads the ZIP to Supabase Storage, and inserts the row.
3. **Two-step UX:**
   - Step 1: rate the response 1–10, with an optional comment.
   - Step 2: ask whether to share the debug/workflow pack publicly. This is a checkbox that defaults to unchecked and remembers its last state. It has its own optional comment.
4. **Raw ZIP** is uploaded only when the user explicitly checks the box in step 2. The ZIP is shared publicly via a public Supabase Storage URL.
5. **Safety controls** from Codex review: rate limits, ZIP magic-byte / size / file-count validation, idempotency keys, cleanup on partial failure, and CSRF-size guards.

## User experience

After every assistant response in the VibeComfy agent-edit chat panel, a small rating widget appears **below that response for 60 seconds**.

### Step 1 — Rate the response

- Question: *“How would you rate this response?”*
- Buttons **1** through **10**.
- Optional comment textarea.
- On clicking a number, the rating is locked in and Step 2 appears inline.

### Step 2 — Share the debug pack

- Checkbox: *“I’m happy to provide a public pack that includes my workflow and results for others to learn from.”*
- The checkbox is **unchecked by default**.
- The last user choice is persisted in `localStorage`, so if they uncheck it once it stays unchecked for future ratings.
- Optional comment textarea for pack context.
- Submit button (enabled once Step 1 is done).

### After submit

- If the checkbox is checked, the existing issue-report ZIP is built and uploaded in the background; the UI shows upload progress / thanks.
- If the checkbox is unchecked, only the rating + comments are submitted.
- The widget hides after submission.

### Settings / re-enable

- A ComfyUI setting `VibeComfy.ShowResponseRatings` lets users disable/enable the whole widget.
- If the user dismisses the widget entirely, the setting can re-enable it.

## Architecture overview

```
VibeComfy frontend (ComfyUI browser extension)
  │
  ├─ renders two-step rating widget in panel_thread.js
  ├─ builds ZIP via collectIssueReportFiles() → buildZipBlob()  (only if requested)
  └─ POST /vibecomfy/agent-edit/rating  (JSON + base64 ZIP)
        │
        ▼
VibeComfy backend (aiohttp route on ComfyUI PromptServer)
  ├─ accepts application/json
  ├─ validates input and ZIP limits
  ├─ forwards to Hivemind edge function with X-Contributor-Key
  └─ no DB write here
        │
        ▼
Hivemind Supabase Edge Function: functions/v1/submit-vibecomfy-rating
  ├─ authenticates contributor key against contributors table
  ├─ if pack_shared=true: uploads ZIP to Storage bucket "vibecomfy-reports"
  ├─ inserts metadata into vibecomfy_ratings table
  ├─ cleans up the uploaded Storage object if the DB insert fails
  └─ returns { ok, rating_id, report_url? }
        │
        ▼
Supabase Postgres (Hivemind DB)
  └─ table: vibecomfy_ratings
```

## Data model

New table in the Hivemind Supabase project (`schema/002_vibecomfy_ratings.sql`):

```sql
CREATE TABLE vibecomfy_ratings (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id        text NOT NULL,
  turn_id           text NOT NULL,
  response_id       text NOT NULL,         -- stable composite, e.g. "<session_id>/<turn_id>"
  rating            smallint NOT NULL CHECK (rating BETWEEN 1 AND 10),
  comment           text,
  pack_shared       boolean NOT NULL DEFAULT false,
  pack_comment      text,
  report_url        text,                  -- public Storage URL, null if pack_shared=false
  report_path       text,                  -- internal Storage path, null if pack_shared=false
  contributor_key_hash text NOT NULL,      -- SHA-256 of the authenticated contributor key
  metadata          jsonb NOT NULL DEFAULT '{}'::jsonb,
  client_created_at timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX vibecomfy_ratings_response_id_idx ON vibecomfy_ratings (response_id);
CREATE INDEX vibecomfy_ratings_created_at_idx ON vibecomfy_ratings (created_at);

ALTER TABLE vibecomfy_ratings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "vibecomfy_ratings_public_read" ON vibecomfy_ratings FOR SELECT USING (true);
```

`metadata` can hold app version, ComfyUI version, idempotency key, and other non-sensitive context.

## Edge function design

New files in the Hivemind repo:

- `supabase/functions/submit-vibecomfy-rating/index.ts`
- `supabase/functions/submit-vibecomfy-rating/protocol.ts`

Responsibilities:
1. Accept `POST` only.
2. Require header `X-Contributor-Key: hm_<64 hex>`.
3. Authenticate by SHA-256 hashing the key and looking up `contributors` (same pattern as `contribute`).
4. Parse JSON body:
   - `rating` (integer 1–10) — required
   - `comment` (optional string)
   - `pack_shared` (boolean) — required
   - `pack_comment` (optional string)
   - `session_id` (string)
   - `turn_id` (string)
   - `response_id` (string, must be `"<session_id>/<turn_id>"`)
   - `client_created_at` (optional ISO timestamp)
   - `metadata` (optional JSON object)
   - `pack_zip_base64` (base64-encoded ZIP) — required only if `pack_shared=true`
5. If `include_pack=true`:
   - Validate ZIP magic bytes, reject non-ZIP or zip-bombs.
   - Enforce max compressed size (64 MiB) and max uncompressed size / file count.
   - Reject path-traversal entries.
   - Upload to Supabase Storage bucket `vibecomfy-reports` under path `YYYY/MM/DD/<uuid>.zip`.
6. Insert a row into `vibecomfy_ratings`.
7. If DB insert fails after Storage upload succeeds, delete the uploaded object.
8. Return `201 { ok: true, rating_id, report_url? }` or structured error.

Validation rules:
- `rating` integer 1–10.
- `session_id` / `turn_id` non-empty URL-safe strings.
- `response_id` must equal `"<session_id>/<turn_id>"`.
- `pack_shared` boolean.
- If `pack_shared=true`, `pack_zip_base64` must be present, valid base64, and decode to a ZIP file.
- Max ZIP size is configurable (default 10 MiB for the VibeComfy backend, 64 MiB for the edge function).
- Max comment length 2000 characters each.

## VibeComfy frontend flow

Files: `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`

1. **Lifecycle hook:** when a terminal response event fires (`OK_CANDIDATE_RESPONSE`, `EDIT_CLARIFY_RESPONSE`, `NOOP_RESPONSE`, `CLARIFY_ONLY_RESPONSE`), record `panel.state.ratingWindow = { turnId, arrivalTime: Date.now(), timerId }`.
2. **Timer:** a single `setTimeout` clears `ratingWindow` after 60 seconds and schedules a `THREAD` re-render.
3. **Widget render:** `renderChatBubbleNode` in `panel_thread.js` appends the widget only to the latest agent bubble when `msg.turn_id === ratingWindow.turnId` and within the 60-second window.
4. **Step 1 UI:** 1–10 buttons + optional `rating_comment`.
5. **Step 2 UI:** appears after a rating is selected.
   - Checkbox: *“I’m happy to provide a public pack that includes my workflow and results for others to learn from.”*
   - Default state from `localStorage` key `vibecomfy.includePackPublicly` (persisted across sessions).
   - Optional `pack_comment` textarea.
   - Submit button.
6. **Settings:** register ComfyUI boolean setting `VibeComfy.ShowResponseRatings` to re-enable the widget if hidden.
7. **Submit:**
   - Build ZIP with `collectIssueReportFiles(panel)` → `buildZipBlob()` only if `pack_shared=true`.
   - POST JSON to `/vibecomfy/agent-edit/rating` with `pack_zip_base64` when sharing a pack.
   - Show states: submitting, thanks, or error with retry.

## VibeComfy backend route

File: `vibecomfy/comfy_nodes/agent/routes.py`

New route: `POST /vibecomfy/agent-edit/rating`

Responsibilities:
1. Accept `application/json`.
2. Validate fields and ZIP size limits before forwarding.
3. Forward to the Hivemind edge function `https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/submit-vibecomfy-rating` with the contributor key from env.
4. Return the edge function response to the frontend.

This keeps the contributor key server-side and gives VibeComfy a place to add logging/metrics later.

New helper module: `vibecomfy/comfy_nodes/agent/hivemind_feedback.py`

- Build the JSON payload from the aiohttp request.
- Call the Hivemind edge function via `urllib` (no extra dependency).
- Surface errors cleanly.

## Authentication

- Issue a dedicated contributor key for VibeComfy using the Hivemind script:
  ```bash
  python3 scripts/issue_contributor_key.py --name "VibeComfy" --kind agent
  ```
- Store the key server-side in VibeComfy as `HIVEMIND_CONTRIBUTOR_KEY`.
- The browser never sees the key.

## Privacy / raw sharing

- The debug pack is shared **only when the user explicitly checks the box** in Step 2.
- The checkbox label clearly states the pack includes the workflow and results and will be public.
- The pack is the raw issue-report ZIP produced by `collectIssueReportFiles()`.
- If the user unchecks the box, only the rating and comments are submitted; no ZIP is uploaded.
- The checkbox defaults to unchecked and remembers its last state.

## Files to modify

### Hivemind repo (`/Users/peteromalley/Documents/banodoco-workspace/hivemind`)
- `schema/002_vibecomfy_ratings.sql` — new table and RLS policy
- `supabase/functions/submit-vibecomfy-rating/index.ts` — new edge function entrypoint
- `supabase/functions/submit-vibecomfy-rating/protocol.ts` — validation helpers
- `tests/` — add Deno tests for the new edge function

### VibeComfy repo
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` — settings, consent, submit handler
- `vibecomfy/comfy_nodes/web/panel_thread.js` — two-step rating widget rendering
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js` — response arrival timing
- `vibecomfy/comfy_nodes/agent/routes.py` — new backend route
- `vibecomfy/comfy_nodes/agent/hivemind_feedback.py` — Hivemind edge-function client
- `.env.example` — `HIVEMIND_CONTRIBUTOR_KEY`, `HIVEMIND_SUBMIT_RATING_URL`, `VIBECOMFY_RATING_MAX_ZIP_BYTES`
- tests for the new route and client

## Testing plan

- **Hivemind edge function:**
  - Valid rating without pack → row inserted, no Storage object.
  - Valid rating with pack → row inserted, ZIP stored, public URL returned.
  - Invalid rating / missing required fields → 400.
  - Oversized / malformed ZIP → 413/400.
  - Bad contributor key → 401.
  - DB insert failure after Storage upload → Storage object cleaned up.
- **VibeComfy route:**
  - Valid request forwarded to Hivemind → returns rating_id.
  - Missing fields / oversized → returns 400.
- **Frontend:**
  - Widget appears only on latest agent bubble within 60 seconds of response arrival.
  - Step 2 appears after selecting a rating.
  - Checkbox state persists in localStorage.
  - Submit sends JSON with `pack_zip_base64` only when the checkbox is checked.

## Open questions / next steps

1. Confirm the Supabase Storage bucket name (`vibecomfy-reports`) and its public-read policy.
2. Confirm whether the bucket should enforce a content-type or file-extension policy.
3. Get a Hivemind contributor key issued for the VibeComfy deployment.
4. Confirm the exact `response_id` format (using `<session_id>/<turn_id>` for now).
