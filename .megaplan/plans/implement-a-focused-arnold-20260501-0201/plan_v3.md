# Implementation Plan: Focused Arnold Spec-Parity Tranche

## Overview
This revision keeps the focused tranche and addresses the remaining critique without changing the target architecture. The remaining flags do not indicate the plan is aimed at the wrong code or root cause; they identify three concrete execution details that must be specified before implementation: raw `bytes` attachment MIME detection, JSON-safe Discord upload ledger payloads, and actual public package targets.

The runtime seams remain the right ones: `agent_kit.loop.run_turn` for invocation entry, `arnold/cli.py` for CLI wiring, `agent_kit.tools.images.send_image` for cross-mode image output, `agent_kit.transport.discord.DiscordTransport` for resident posting, `agent_kit.envelope`/`agent_kit/envelope.schema.json` for event contracts, and SQLite/Supabase migrations for image source constraints. The plan should not introduce the broader FastAPI/asyncpg migration.

Settled scope decisions:
- Invocation attachment parity in this tranche is image-only. Do not implement full audio/Groq CLI attachment flow unless a trivial existing path appears.
- Keep the optional dependency extra `test` canonical. Add a `test-extra` alias only if useful and non-breaking.
- Prefer first-class `attached_image` invocation events, but preserve `tool_call` audit rows.
- Do not implement the broader FastAPI/asyncpg migration.

## Phase 1: Baseline And Shared Contracts

### Step 1: Establish the Python/test baseline (`pyproject.toml`)
**Scope:** Small
1. Change `requires-python` from `>=3.11` to `>=3.12`.
2. Keep `[project.optional-dependencies].test` as the canonical test extra.
3. Optionally add a non-breaking `test-extra` alias containing the same dependencies if it helps external callers, but do not rename or remove `test`.
4. Run a cheap metadata/import check and note if the local interpreter is below Python 3.12 before relying on full-suite results.

### Step 2: Update image source compatibility (`agent_kit/store/migrations/sqlite/002_images.sql`, `supabase/migrations/202604300002_002_images.sql`, `agent_kit/tools/images.py`, image tests)
**Scope:** Medium
1. Add `caller_uploaded` as an accepted image source everywhere source values are constrained or validated.
2. Update `LIST_IMAGES_SCHEMA` to allow `caller_uploaded` and add tests proving `list_images(source='caller_uploaded')` works.
3. Review image metadata/render tests that branch on source and update expectations only where source filtering or display is affected.
4. Preserve existing `user_uploaded` behavior for Discord resident uploads; caller-uploaded images are a new invocation-specific source, not a replacement.
5. If the migration system needs forward migrations for existing DBs, add an additive migration path; otherwise update baseline migrations used by tests and document that this tranche targets current clean test DB initialization.

### Step 3: Add a local blob adapter for invocation mode (`agent_kit/blob/local.py`, `agent_kit/blob/__init__.py`, `arnold/cli.py`, tests)
**Scope:** Medium
1. Implement a simple filesystem `LocalBlobStore` using the existing `Blob` protocol: `put`, `get`, and `exists` return/use `BlobRef` keys compatible with current `view_image` and `send_image` patterns.
2. Store blobs under a deterministic local root for SQLite CLI runs, for example a `--blob-dir` argument defaulting near the SQLite DB path.
3. Keep Supabase CLI mode wired to `SupabaseStorageBlob.from_env()` if `--store supabase` is selected and attachments are present.
4. Add focused tests for local blob put/get/exists and for CLI attachment setup under SQLite.

## Phase 2: Invocation Attachment Passing

### Step 4: Add image attachment normalization (`agent_kit/attachments.py` or a small local module)
**Scope:** Medium
1. Normalize the supported invocation inputs: `Path`, raw `bytes`, and `(bytes, mime_type)`.
2. Accept image MIME types supported by this tranche: PNG, JPEG, and WEBP up to 25MB.
3. For `Path`, infer MIME type from filename and validate or fill gaps with magic-byte sniffing.
4. For raw `bytes`, require magic-byte detection of PNG, JPEG, or WEBP. Detect PNG via `89 50 4E 47 0D 0A 1A 0A`, JPEG via `FF D8 FF`, and WEBP via `RIFF....WEBP`. Reject unknown raw bytes with an explicit unsupported media type error.
5. For `(bytes, mime_type)`, require the declared MIME type to be one of the supported image types and, when magic bytes are recognizable, reject mismatches rather than silently storing incorrect metadata.
6. Reject audio attachments and other unsupported files with explicit errors indicating this tranche supports invocation image attachments only.
7. Keep the module small and reusable by CLI and Python API; avoid introducing a broad storage abstraction beyond the existing `Blob` protocol.

### Step 5: Wire Python invocation attachments (`agent_kit/loop.py`, `arnold/__init__.py`, `megaplan/arnold/__init__.py` if re-export signatures need coverage, tests/test_run_turn.py`)
**Scope:** Medium
1. Extend `run_turn` and `arun_turn` with `attachments=None` and require `blob` when attachments are provided.
2. Target actual public surfaces present in this repository. Do not reference or create an `arnold_sdk` package unless implementation discovery shows it exists and is already part of the package surface.
3. Define epicless behavior explicitly: if `attachments` are provided and `epic_id is None`, return an `Envelope` with `outcome='errored'` and `error.code='attachments_require_epic'`. Do not create orphan image rows or synthetic epic scopes.
4. For valid image attachments, create the inbound invocation message first, store blobs via `Blob.put(epic_id, bytes, mime_type)`, create `images` rows with `source='caller_uploaded'`, set `messages.has_image_attachment=true`, and then create the turn/model prompt.
5. Include attachment metadata in the prompt snapshot/hot context only as needed for the model to discover images through existing tools; do not auto-render uploaded images in the reply envelope.
6. Add Python API tests showing caller-uploaded images exist before model execution and are visible via `list_images(source='caller_uploaded')`.

### Step 6: Wire CLI `--attach` end to end (`arnold/cli.py`, tests/test_cli.py`)
**Scope:** Medium
1. Add repeatable `arnold turn --attach <path>`.
2. Build and pass the correct blob adapter: `LocalBlobStore` for SQLite, `SupabaseStorageBlob` for Supabase.
3. Pass normalized attachments into `run_turn` along with `blob`.
4. Test an end-to-end SQLite CLI run with a small image attachment, fake model, local blob dir, and resulting envelope.
5. Test that `--attach` without `--epic` exits with the explicit `attachments_require_epic` envelope error.

## Phase 3: Image Output And Events

### Step 7: Make resident `send_image` post real Discord files (`agent_kit/tools/images.py`, `agent_kit/transport/discord.py`, `agent_kit/ports.py`, tests/test_image_tools.py`, tests/test_discord_transport.py`)
**Scope:** Medium
1. In resident mode, require `context.blob` for `send_image` and construct a `BlobRef(epic_id=image['epic_id'], key=image['storage_url'], mime_type=_media_type(...))` before calling `Blob.get`.
2. Keep raw file bytes only in the in-memory external callback closure or transient upload payload. Do not place bytes in `ExternalSpec.request_summary` or `ExternalSpec.request_body`.
3. Persist only JSON-safe, replay-safe metadata in the Discord external request row: image id, reference key, blob key/storage URL, filename, MIME type, byte length, caption preview, channel id, and message row id.
4. Update `PushTransport.post_message(..., files=...)` expectations so files passed to the transport are concrete in-memory upload payloads, while durable ledger fields remain metadata-only.
5. Update `DiscordTransport.post_message()` and `_post_message()` to convert in-memory payloads into `discord.File` objects and call `channel.send(content=..., files=[...])`.
6. Preserve existing ledger behavior: outbound row first, pending external request before IO, row update after Discord confirmation, and confirmed/failed ledger settlement through `audit_wrap()`.
7. Add fake-transport tests asserting file bytes are passed to the transport, `external_requests.request_body` remains JSON-safe metadata without bytes, and message `discord_message_id` is updated after the callback.

### Step 8: Add first-class invocation `attached_image` events (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`, `agent_kit/tool_kit.py`, `agent_kit/tools/images.py`, tests/test_envelope.py`, tests/test_image_tools.py`, tests/test_cli.py`)
**Scope:** Medium
1. Extend envelope event kind definitions and schema enum to include `attached_image`.
2. Update any type aliases in `agent_kit/tool_kit.py` only if the registry needs to produce the new kind; keep ordinary audited image tool calls as `tool_call` rows/events.
3. Add a helper in the tool/event layer to append and stream extra events safely, so events added by `send_image` are both captured in `Envelope.events` and emitted through `on_event` / `--stream-events` in order.
4. In invocation-mode `send_image`, preserve the audited `tool_call` event and additionally emit an `attached_image` event with `details={image_id, caption, storage_url, reference_key, media_type}`.
5. In resident mode, do not emit `attached_image`; the Discord post is the user-facing image output.
6. Add schema validation and stream parity tests proving the final envelope events match streamed NDJSON events.

## Phase 4: Typing, Status, And Message Semantics

### Step 9: Implement `set_typing` (`agent_kit/tools/communication.py`, `agent_kit/transport/discord.py`, `agent_kit/ports.py`, tests/test_communication_resident.py`)
**Scope:** Small
1. Register `set_typing` with a minimal schema such as `{"on": boolean}`.
2. In invocation mode, return an explicit no-op result and keep the normal audited `tool_call` event.
3. In resident mode, call a new transport typing method when available and return `{"typing": on, "mode": "resident"}`.
4. Add fake transport coverage for resident typing and invocation no-op/audit behavior.

### Step 10: Reconcile whitelist/status/message semantics (`agent_kit/transport/discord.py`, `agent_kit/resident.py`, `agent_kit/tools/communication.py`, tests/test_whitelist.py`, tests/test_status_lifecycle.py`, tests/test_status_formatter.py`)
**Scope:** Small
1. Keep non-whitelisted DMs from creating `messages` rows and keep `whitelist_rejected` logged. Align log category only if the existing comparison explicitly requires a different category; otherwise preserve current tested behavior.
2. Assert status messages are not stored in `messages`, only `bot_turns.status_message_id`, and final status edits still render terminal state.
3. Assert resident `send_message` writes exactly one outbound conversation row, delays `discord_message_id` until Discord confirms, and does not pollute message history with status content.
4. Add or adjust only focused regression tests for changed semantics.

## Phase 5: Regression And Guardrails

### Step 11: Add targeted regression tests (`tests/test_cli.py`, `tests/test_run_turn.py`, `tests/test_image_tools.py`, `tests/test_discord_transport.py`, `tests/test_communication_resident.py`, `tests/test_envelope.py`)
**Scope:** Medium
1. Cover Python image attachments for `Path`, raw `bytes` detected by magic bytes, and `(bytes, mime_type)`.
2. Cover raw `bytes` rejection when magic bytes do not identify PNG/JPEG/WEBP.
3. Cover declared MIME mismatch rejection for `(bytes, mime_type)` when detectable bytes disagree with the declared type.
4. Cover CLI `--attach` with SQLite plus `LocalBlobStore`.
5. Cover rejection for attachments without `epic_id`.
6. Cover `caller_uploaded` schema/tool filtering.
7. Cover resident `send_image` file upload bytes, `BlobRef` construction, and JSON-safe persisted Discord request body.
8. Cover invocation `send_image` producing both audit `tool_call` and caller-facing `attached_image` events, including streamed event parity.
9. Cover `set_typing` in invocation and resident modes.

### Step 12: Validate and inspect scope (`pyproject.toml`, touched tests, full suite, diff)
**Scope:** Small
1. Run the targeted suite first:
   ```bash
   python -m pytest tests/test_cli.py tests/test_run_turn.py tests/test_image_tools.py tests/test_discord_transport.py tests/test_communication_resident.py tests/test_envelope.py tests/test_status_lifecycle.py tests/test_whitelist.py -q
   ```
2. Run the full suite:
   ```bash
   python -m pytest -q
   ```
3. Inspect the diff to ensure no FastAPI/asyncpg migration was started, no non-existent package target was added, and unrelated dirty worktree changes were preserved.
4. If local Python is below 3.12, report that as an environment limitation while still keeping the project metadata/test-extra changes correct.

## Execution Order
1. Update baseline metadata and image source contracts first, because attachment ingestion depends on valid image rows and tool schemas.
2. Add `LocalBlobStore` before CLI `--attach`, so CLI attachment support is truly end to end under SQLite.
3. Implement attachment normalization before API wiring, including magic-byte detection for raw bytes and mismatch rejection for `(bytes, mime_type)`.
4. Implement Python attachment ingestion before CLI wiring, because CLI should be a thin adapter over the public API.
5. Fix resident `send_image` file upload with `BlobRef` handling and JSON-safe ledger metadata before changing invocation image event semantics.
6. Add `attached_image` event plumbing across dataclass, JSON schema, tool/event streaming, and tests in one step.
7. Implement `set_typing` and then reconcile status/whitelist/message semantics.
8. Finish with targeted tests, full suite, and diff inspection.

## Validation Order
1. Start with schema and focused unit tests for image source, local blob, and attachment normalization.
2. Run Python API tests for attachment ingestion before CLI tests.
3. Run resident fake-transport tests for `send_image`, including JSON-safe external request persistence, and `set_typing`.
4. Run envelope/schema/streaming tests for `attached_image`.
5. Run the targeted combined suite.
6. Run the full suite and inspect the final diff for scope discipline.
