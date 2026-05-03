# Implementation Plan: Focused Arnold Spec-Parity Tranche

## Overview
Arnold already has the core turn loop, SQLite store, Discord resident transport, image tooling, status lifecycle tests, CLI entrypoint, and public Python imports. The focused tranche should tighten current behavior against `planning-bot-spec.md` without doing the broader FastAPI/asyncpg migration.

Current gaps from inspection:
- `pyproject.toml` still advertises Python `>=3.11`; the spec calls for Python 3.12+.
- CLI/Python invocation APIs do not accept attachments yet (`arnold turn --attach`, `run_turn(..., attachments=...)`).
- `send_image` in resident mode queues file metadata but `DiscordTransport.post_message()` drops `files`, so no actual file is posted.
- `send_image` invocation mode currently returns a synthetic Discord id and normal tool event, but the spec wants an attached-image envelope event or an explicitly compatible event semantic.
- `set_typing` is missing from the tool registry.
- Whitelist/status/message semantics are mostly present, but need a pass to align categories, status-message non-persistence, Discord message/file behavior, and invocation-mode event semantics.

## Main Phase

### Step 1: Establish the Python/test baseline (`pyproject.toml`, CI-adjacent test docs if present)
**Scope:** Small
1. Change `requires-python` from `>=3.11` to `>=3.12`.
2. Confirm the supported test extra name. Prefer preserving the existing `[project.optional-dependencies].test` extra unless there is an existing caller expecting `test-extra`; if needed, add a compatibility alias such as `test-extra = [...]` rather than renaming and breaking current installs.
3. Run the cheapest metadata check first: `python -m pytest tests/test_cli.py tests/test_run_turn.py -q` under the available interpreter, and note if local Python is below 3.12.

### Step 2: Add invocation attachment ingestion (`arnold/cli.py`, `agent_kit/loop.py`, `agent_kit/ports.py`, store/image helpers as needed)
**Scope:** Medium
1. Add repeatable CLI `--attach <path>` parsing to `arnold turn` and pass normalized attachment descriptors into `run_turn`.
2. Extend `run_turn` / `arun_turn` with `attachments=` for Python callers. Support `Path`, raw `bytes`, and `(bytes, mime_type)` per spec.
3. Implement a small normalization module/function that resolves MIME type, enforces the 25MB cap, and classifies supported image/audio types.
4. For image attachments, write bytes to the configured `Blob` adapter, create `images` rows with `source='caller_uploaded'`, mark the invocation inbound message `has_image_attachment=true`, and make the image visible through `list_images(source='caller_uploaded')`.
5. For audio attachments, either wire transcription if an existing transcription provider is already available in invocation context, or implement the least-surprising explicit error/blocked behavior if the current invocation API lacks a provider. The plan assumes image support is required now and audio support is included only if the existing Groq path can be reused without new architecture.
6. Keep attachment ingestion before model execution so the model sees the same store state it would see after Discord image ingestion.

### Step 3: Make `send_image` actually post Discord files (`agent_kit/tools/images.py`, `agent_kit/transport/discord.py`, `agent_kit/ports.py`)
**Scope:** Medium
1. Require `context.blob` for resident-mode `send_image`, fetch bytes for the image `storage_url`, and queue a file payload containing filename, bytes, MIME type, and image metadata.
2. Update `PushTransport.post_message(..., files=...)` documentation/protocol expectations so files are concrete upload payloads, not just metadata.
3. Update `DiscordTransport.post_message()` and `_post_message()` to convert queued file payloads to `discord.File` objects and call `channel.send(content=..., files=[...])`.
4. Preserve ledger behavior: create the outbound `messages` row before external IO, record a pending Discord external request, update `discord_message_id` only after Discord confirms, and confirm/fail the ledger row through the existing audit wrapper.

### Step 4: Align invocation `send_image` event semantics (`agent_kit/envelope.py`, `agent_kit/tools/images.py`, tests)
**Scope:** Small
1. Add an envelope event semantic for invocation-mode image attachments. Preferred implementation: extend `EventKind` with `attached_image` and append an event with `details={image_id, caption, storage_url, reference_key, media_type}`.
2. Keep the existing audited tool call event unless it causes duplicate or confusing stream output; if both events remain, document/test that `tool_call` is audit, `attached_image` is caller-facing attachment output.
3. Ensure `--stream-events` emits the same events captured in `Envelope.events`.

### Step 5: Implement `set_typing` (`agent_kit/tools/communication.py`, `agent_kit/transport/discord.py`, `agent_kit/ports.py`, resident tests)
**Scope:** Small
1. Register `set_typing` with schema matching the spec (`on` boolean or equivalent on/off argument).
2. In invocation mode, make it succeed silently and emit a no-op/audit event.
3. In resident mode, call a transport method that triggers Discord typing where available; if direct sync typing is awkward in `discord.py`, implement it as a short typing pulse through the transport adapter and keep the tool result explicit (`{"typing": true, "mode": "resident"}`).
4. Add protocol and fake-transport support without making status-message logic depend on typing.

### Step 6: Reconcile whitelist/status/message semantics (`agent_kit/transport/discord.py`, `agent_kit/resident.py`, `agent_kit/tools/communication.py`, tests)
**Scope:** Medium
1. Confirm non-whitelisted DMs persist no `messages` row and log `whitelist_rejected`. Align the log category with the spec comparison if needed; current code uses `application`, while the existing unit expects that.
2. Confirm status messages remain out of `messages`, only `bot_turns.status_message_id` is stored, and final edits render terminal state.
3. Confirm resident `send_message` writes one outbound conversation row, waits for Discord confirmation before setting `discord_message_id`, and honors file attachment behavior for overlong messages only if already in scope. Do not implement broad message-splitting unless the comparison explicitly calls it out in a touched test.
4. Add focused regression tests for any semantics changed in this step rather than broad snapshot rewrites.

### Step 7: Regression tests and validation (`tests/test_cli.py`, `tests/test_run_turn.py`, `tests/test_image_tools.py`, `tests/test_discord_transport.py`, `tests/test_communication_resident.py`)
**Scope:** Medium
1. Add CLI tests for `--attach` image ingestion against SQLite with a fake/local blob adapter path if available; otherwise use a small test blob adapter passed through Python API and keep CLI coverage to argument validation until CLI blob selection exists.
2. Add Python API tests for `run_turn(..., attachments=[...])` creating `caller_uploaded` image rows before model execution.
3. Add resident `send_image` tests asserting file bytes reach the fake transport and Discord message id updates after the external callback.
4. Add invocation `send_image` tests asserting the caller-facing attached-image event appears in `Envelope.events` and streamed events.
5. Add `set_typing` tests for both invocation no-op/audit behavior and resident transport call behavior.
6. Run targeted tests first, then the full test suite: `python -m pytest tests/test_cli.py tests/test_run_turn.py tests/test_image_tools.py tests/test_discord_transport.py tests/test_communication_resident.py tests/test_status_lifecycle.py tests/test_whitelist.py -q`, then `python -m pytest -q`.

## Execution Order
1. Baseline packaging changes first, because Python version/extra naming affects how reviewers install and run tests.
2. Add attachment normalization and Python API support before CLI wiring; this gives the CLI a simple path to call.
3. Fix `send_image` resident upload plumbing before adjusting event semantics, so file posting correctness is separated from envelope shape.
4. Add `set_typing` after communication/image tool changes, reusing the same tool audit/event patterns.
5. Finish with whitelist/status/message semantic cleanup and focused regression tests.

## Validation Order
1. Run narrow tests for each changed behavior immediately after implementation.
2. Run the touched integration-style tests for CLI/Python equivalence and resident Discord fakes.
3. Run the full suite once all wiring is complete.
4. Inspect the diff to ensure the FastAPI/asyncpg migration is not started and unrelated dirty worktree changes are preserved.
