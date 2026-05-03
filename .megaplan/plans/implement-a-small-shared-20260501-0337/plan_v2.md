# Implementation Plan: Shared Resident Chat Runtime

## Overview
Create a small local Python package shared by `/Users/peteromalley/Documents/arnold-v2` and `/Users/peteromalley/Documents/Veas`, focused only on resident-chat infrastructure. The package should not absorb Arnold’s domain loop, prompts, store schemas, tools, or Veas’s mediation logic. The useful common layer is: typed env/settings primitives, Discord DM/channel helpers or adapters, typing helpers, burst coalescing, lightweight provider health checks, and startup diagnostics helpers.

Critique check: the open flags do not point to the wrong root cause or wrong code. They refine the plan’s extraction boundary. The package still makes sense, but the Discord abstraction must explicitly cover Arnold’s channel send/edit/file-upload/status-edit needs, and the package must be Python 3.11-compatible because Veas supports Python 3.11.

Current touch points:
- Arnold’s Discord transport is in `agent_kit/transport/discord.py`, including DM ingestion, real-epic creation before message insert, sync wrappers over Discord async methods, typing, channel resolution, file uploads, status edits, and attachment helpers.
- Arnold’s resident orchestration is in `agent_kit/resident.py`, including `MessageCoalescer`, status/typing behavior, and the event-loop fix using `asyncio.to_thread(run_turn, ...)` when Discord is running.
- Arnold resident env checks are in `arnold/cli.py`.
- Veas has parallel Discord infrastructure in `app/services/discord.py`, burst coalescing in `app/services/debouncer.py`, startup wiring in `app/main.py`, typed settings in `app/config.py`, and health checks in `app/routers/health.py`.
- Both worktrees are dirty. Preserve existing user changes and avoid broad formatting or unrelated cleanup.

Plan name: `shared-resident-chat-runtime`

## Phase 1: Package Skeleton And Compatibility

### Step 1: Add the shared package (`/Users/peteromalley/Documents/resident_chat_runtime/`)
**Scope:** Small
1. Create a sibling local package with `pyproject.toml` and package namespace `resident_chat_runtime`.
2. Set `requires-python = ">=3.11"` and avoid Python 3.12-only syntax or stdlib APIs so Veas remains installable in its supported Python floor.
3. Keep dependencies minimal: `httpx`; make `websockets` and `discord.py` optional usage dependencies because Arnold and Veas already depend on them differently.
4. Add modules with narrow intent:
   - `resident_chat_runtime/env.py` for dotenv loading, required-env checks, CSV env parsing, alternative-required env groups, and safe diagnostics.
   - `resident_chat_runtime/coalescing.py` for a generic async burst coalescer that can support Arnold’s epic/message dispatch and Veas’s user/message callback.
   - `resident_chat_runtime/discord_rest.py` for async Discord REST helpers used by Veas: bot auth headers, DM channel creation, DM text send, typing, reaction, and channel message fetch.
   - `resident_chat_runtime/discord_gateway.py` for a small callback-driven Gateway loop that handles heartbeat, reconnect logging, event dispatch, and shutdown.
   - `resident_chat_runtime/discord_channel.py` for Arnold’s discord.py channel/client adapter helpers: resolve channel, send channel message, send channel message with files, edit channel message, trigger typing, and fetch recent channel messages.
   - `resident_chat_runtime/async_bridge.py` for guarded sync-over-async execution that rejects calls from the same running event loop and can submit to a known Discord loop from other threads.
   - `resident_chat_runtime/health.py` for lightweight cached HTTP provider checks.
   - `resident_chat_runtime/startup.py` for startup diagnostics helpers that log configured provider, required env status, and background task starts without printing secrets.

### Step 2: Add shared-package tests (`resident_chat_runtime/tests/`)
**Scope:** Small
1. Add tests for Python 3.11-compatible APIs: env parsing, required/alternative env diagnostics, coalescing debounce/hard-cap behavior, async bridge same-loop rejection, Discord REST URL/header shaping, Discord channel adapter file/edit call shaping with fakes, and cached health result behavior.
2. Keep tests independent of Arnold and Veas database/domain models.

## Phase 2: Preserve Arnold Live Fixes While Reusing Infrastructure

### Step 3: Refactor Arnold’s Discord infrastructure (`agent_kit/transport/discord.py`)
**Scope:** Medium
1. Keep domain-specific ingestion in Arnold: store writes, ledger entries, voice/image persistence, Groq transcription, and `_ensure_message_epic_id` stay in `agent_kit/transport/discord.py`.
2. Replace duplicated generic pieces with shared helpers only where behavior is preserved:
   - env whitelist parsing around lines 38 and 425.
   - guarded sync-over-async execution around lines 183-196, using the shared async bridge while preserving current error semantics.
   - discord.py channel operations around lines 150-181 and 369-422, using `discord_channel.py` helpers that explicitly support `post_message(..., files=...)`, `edit_message(...)`, `set_typing(...)`, channel resolution, and recent message fetch.
3. Preserve the live fix that inbound text, voice, and image paths all call `_ensure_message_epic_id` before `store.create_message` at lines 142-147, 198-212, and 253-268.
4. Preserve file-upload behavior in `post_message(..., files=...)`; shared helpers must convert Arnold `FileUpload` values to `discord.File` or leave conversion in Arnold behind a tested helper boundary.
5. Preserve status edit behavior because `ResidentRunner._edit_status()` depends on `transport.edit_message(...)`.
6. Add or keep tests proving real-epic creation before message insert, sync method misuse from the Discord event loop fails loudly, file uploads are sent, and status edits still call Discord edit behavior.

### Step 4: Refactor Arnold coalescing and status behavior (`agent_kit/resident.py`)
**Scope:** Medium
1. Replace `MessageCoalescer` internals at lines 22-75 with the shared coalescer or a thin Arnold wrapper around it, preserving `MessageCoalescer` as a compatibility export for existing tests and imports.
2. Preserve `ResidentRunner.dispatch_turn` event-loop isolation at lines 163-166: resident turn execution must run in a worker thread when the Discord transport owns the event loop.
3. Preserve DM quiet-status mode at lines 195-202 and 235-236: Discord resident mode should use typing and avoid posting visible `Planning turn in progress.` messages.
4. Keep `format_status` in Arnold for now because its wording is product-specific and tests assert it in invocation-mode behavior.

### Step 5: Refactor Arnold env/startup diagnostics (`arnold/cli.py`)
**Scope:** Small
1. Replace `_load_dotenv` and `_missing_resident_env` at lines 247-278 with shared env helpers.
2. Keep Arnold-specific required variable names and Supabase service-key alternative logic.
3. Add startup diagnostics around resident startup at lines 154-210 that report configured provider readiness without logging secrets.

## Phase 3: Integrate Veas Only Where Duplication Drops

### Step 6: Refactor Veas Discord REST and Gateway helpers (`app/services/discord.py`)
**Scope:** Medium
1. Keep Veas-specific policy and mapping in place: partner seeding, whitelist behavior, Meta-shaped payload conversion, edit/delete/reaction database writes, and catch-up ingestion remain in `app/services/discord.py`.
2. Replace generic REST helpers with shared `discord_rest.py` helpers:
   - `_headers`, `init_client`, `_get_client`, `close_client`, `get_dm_channel_id`, `send_typing`, `send_text`, `add_reaction`, and recent-message fetch around lines 30-119 and 325-367.
3. Replace generic Gateway loop/heartbeat/reconnect plumbing around lines 194-253 with the shared Gateway class, keeping Veas handlers `_handle_message`, `_handle_message_update`, `_handle_message_delete`, and `_handle_reaction_add` as callbacks.
4. Preserve existing behavior that accepted partner DMs schedule delayed typing before `process_inbound` at lines 255-267.
5. Do not switch Veas to Arnold’s discord.py channel adapter; Veas should keep using REST helpers because that matches its current architecture.

### Step 7: Refactor Veas coalescing (`app/services/debouncer.py`)
**Scope:** Small
1. Wrap the shared coalescer in the existing `BurstCoalescer` class so existing imports from `app.services.debouncer` continue to work.
2. Preserve the public API: `add(user_id, message_id, user)`, `add_burst(user_id, message_ids, user)`, and `snapshot()`.
3. Preserve lock semantics for per-user concurrency, either inside the shared coalescer or in the wrapper.

### Step 8: Reuse shared health/startup helpers in Veas (`app/routers/health.py`, `app/main.py`, `app/config.py`)
**Scope:** Small
1. Keep Veas’s Pydantic `Settings` model as the source of truth in `app/config.py`; do not replace domain settings.
2. Replace only the generic cached Anthropic HTTP probe in `app/routers/health.py` with the shared cached provider check.
3. Use startup diagnostics in `app/main.py` around provider setup/background task creation without changing the startup order.

## Phase 4: Dependency Wiring

### Step 9: Add local path dependency in both repos (`pyproject.toml`)
**Scope:** Small
1. Add a local dependency that works from both repos, likely `resident-chat-runtime @ file:///Users/peteromalley/Documents/resident_chat_runtime`, because the shared package sits outside both repositories.
2. Ensure Arnold’s `>=3.12` and Veas’s `>=3.11` constraints both accept the shared package.
3. Update lockfiles only if the repo workflow requires it and the command succeeds locally.
4. Avoid moving files between Arnold and Veas; this should be a shared package plus thin integration edits.

## Phase 5: Validation

### Step 10: Run focused tests first
**Scope:** Small
1. Shared package: run its unit tests, for example `python -m pytest /Users/peteromalley/Documents/resident_chat_runtime/tests`.
2. Arnold focused tests:
   - `python -m pytest tests/test_discord_transport.py tests/test_resident.py tests/test_coalescer.py tests/test_status_lifecycle.py tests/test_communication_resident.py`
3. Veas focused tests:
   - `python -m pytest tests/test_discord.py tests/test_debouncer.py tests/test_health.py tests/test_config.py`

### Step 11: Run broader smoke checks if focused tests pass
**Scope:** Small
1. Run import/package checks in both repos, such as `python -m pytest tests/test_megaplan_arnold_import.py` in Arnold if still relevant and `python -m pytest tests/test_tool_schemas_importable.py` in Veas.
2. Run full test suites only if the focused checks pass and runtime is acceptable; otherwise report the exact failing focused tests as blockers.

## Execution Order
1. Build and test the Python 3.11-compatible shared package in isolation.
2. Wire Arnold first because it contains the required live fixes and richer resident runtime constraints.
3. Wire Veas second, only replacing duplicate infrastructure where the adapter stays thin.
4. Update dependency metadata after imports are stable.
5. Run focused tests in both repos, then broader smoke tests.

## Validation Order
1. Start with shared-package tests for env, coalescing, async bridge, Discord REST, Discord channel adapter, and health helpers.
2. Run Arnold Discord/resident focused tests, especially file upload, status edit, event-loop guard, and quiet DM status behavior.
3. Run Veas Discord/debouncer/health/config focused tests.
4. Run import smoke tests in both repos.

## Files Expected To Change
- `/Users/peteromalley/Documents/resident_chat_runtime/pyproject.toml`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/__init__.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/env.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/coalescing.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/discord_rest.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/discord_gateway.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/discord_channel.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/async_bridge.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/health.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/startup.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/tests/...`
- `/Users/peteromalley/Documents/arnold-v2/pyproject.toml`
- `/Users/peteromalley/Documents/arnold-v2/agent_kit/transport/discord.py`
- `/Users/peteromalley/Documents/arnold-v2/agent_kit/resident.py`
- `/Users/peteromalley/Documents/arnold-v2/arnold/cli.py`
- `/Users/peteromalley/Documents/arnold-v2/tests/test_discord_transport.py`
- `/Users/peteromalley/Documents/arnold-v2/tests/test_resident.py`
- `/Users/peteromalley/Documents/arnold-v2/tests/test_coalescer.py`
- `/Users/peteromalley/Documents/Veas/pyproject.toml`
- `/Users/peteromalley/Documents/Veas/app/services/discord.py`
- `/Users/peteromalley/Documents/Veas/app/services/debouncer.py`
- `/Users/peteromalley/Documents/Veas/app/routers/health.py`
- `/Users/peteromalley/Documents/Veas/app/main.py`
- `/Users/peteromalley/Documents/Veas/tests/test_discord.py`
- `/Users/peteromalley/Documents/Veas/tests/test_debouncer.py`
- `/Users/peteromalley/Documents/Veas/tests/test_health.py`

## Tests Run During Planning
No tests were run during this planning/revision pass; repository inspection and critique incorporation only.

## Blockers
No hard blocker identified. Main risk is the large existing dirty worktree in both repos, especially target files already modified in Arnold and Veas. Implementation must inspect diffs before each edit and avoid reverting or overwriting unrelated user changes.
