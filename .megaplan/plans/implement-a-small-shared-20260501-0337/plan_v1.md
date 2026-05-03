# Implementation Plan: Shared Resident Chat Runtime

## Overview
Create a small local Python package shared by `/Users/peteromalley/Documents/arnold-v2` and `/Users/peteromalley/Documents/Veas`, focused only on resident-chat infrastructure. The package should not absorb Arnold’s domain loop, prompts, store schemas, tools, or Veas’s mediation logic. The useful common layer is: typed env/settings primitives, Discord REST/Gateway helpers, typing/DM/channel helpers, generic burst coalescing, lightweight provider health checks, and startup diagnostics helpers.

Current touch points:
- Arnold’s Discord transport is in `agent_kit/transport/discord.py`, including DM ingestion, real-epic creation before message insert, sync wrappers over Discord async methods, typing, channel resolution, and attachment helpers.
- Arnold’s resident orchestration is in `agent_kit/resident.py`, including `MessageCoalescer`, status/typing behavior, and the event-loop fix using `asyncio.to_thread(run_turn, ...)` when Discord is running.
- Arnold resident env checks are in `arnold/cli.py`.
- Veas has parallel Discord infrastructure in `app/services/discord.py`, burst coalescing in `app/services/debouncer.py`, startup wiring in `app/main.py`, typed settings in `app/config.py`, and health checks in `app/routers/health.py`.
- Both worktrees are dirty. Preserve existing user changes and avoid broad formatting or unrelated cleanup.

Plan name: `shared-resident-chat-runtime`

## Phase 1: Package Skeleton And Local Dependencies

### Step 1: Add the shared package (`/Users/peteromalley/Documents/resident_chat_runtime/`)
**Scope:** Small
1. Create a sibling local package with `pyproject.toml` and a package namespace such as `resident_chat_runtime`.
2. Keep dependencies minimal: `httpx`; make `websockets` and `discord.py` optional usage dependencies because Arnold and Veas already depend on them differently.
3. Add modules with narrow intent:
   - `resident_chat_runtime/env.py` for dotenv loading, required-env checks, CSV env parsing, and provider-settings dataclasses.
   - `resident_chat_runtime/coalescing.py` for a generic async burst coalescer that can support Arnold’s sync-style dispatch and Veas’s async user/message callback.
   - `resident_chat_runtime/discord_rest.py` for async Discord REST helpers: bot auth headers, DM channel creation, send message, send typing, add reaction, fetch channel messages.
   - `resident_chat_runtime/discord_gateway.py` for a small callback-driven Gateway client that handles heartbeat, reconnect logging, event dispatch, and shutdown.
   - `resident_chat_runtime/health.py` for lightweight cached HTTP provider checks.
   - `resident_chat_runtime/startup.py` for startup diagnostics helpers that log configured provider, required env status, and background task starts without printing secrets.

### Step 2: Add shared-package tests (`resident_chat_runtime/tests/`)
**Scope:** Small
1. Port the generic behavior tests first: env parsing, required-env diagnostics, coalescing debounce/hard-cap behavior, Discord REST URL/header shaping, cached health result behavior.
2. Keep tests independent of Arnold and Veas database/domain models.

## Phase 2: Preserve Arnold Live Fixes While Reusing Infrastructure

### Step 3: Refactor Arnold’s Discord infrastructure (`agent_kit/transport/discord.py`)
**Scope:** Medium
1. Keep domain-specific ingestion in Arnold: store writes, ledger entries, voice/image persistence, Groq transcription, and `_ensure_message_epic_id` stay in `agent_kit/transport/discord.py`.
2. Replace duplicated generic pieces with shared helpers where this is behavior-preserving:
   - env whitelist parsing around lines 38 and 425.
   - Discord client/channel/send/typing helper behavior around lines 150-181 and 369-422, if it can be done without changing the `PushTransport` sync API.
3. Preserve the live fix that inbound text, voice, and image paths all call `_ensure_message_epic_id` before `store.create_message` at lines 142-147, 198-212, and 253-268.
4. Preserve the event-loop guard in `_run_coro` at lines 183-196 so sync Discord methods are not called from the Discord event loop. If the shared package introduces an abstraction, expose both async helpers and a sync bridge with the same guard semantics.
5. Add or keep tests proving real-epic creation before message insert and event-loop misuse fails loudly.

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
2. Replace generic REST helpers with shared `DiscordRestClient` or functions:
   - `_headers`, `init_client`, `_get_client`, `close_client`, `get_dm_channel_id`, `send_typing`, `send_text`, `add_reaction`, and recent-message fetch around lines 30-119 and 325-367.
3. Replace generic Gateway loop/heartbeat/reconnect plumbing around lines 194-253 with the shared Gateway class, keeping Veas handlers `_handle_message`, `_handle_message_update`, `_handle_message_delete`, and `_handle_reaction_add` as callbacks.
4. Preserve existing behavior that accepted partner DMs schedule delayed typing before `process_inbound` at lines 255-267.

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
2. Update lockfiles only if the repo workflow requires it and the command succeeds locally.
3. Avoid moving files between Arnold and Veas; this should be a shared package plus thin integration edits.

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
1. Run import/package checks in both repos, such as `python -m pytest tests/test_megaplan_arnold_import.py` in Arnold if still relevant and a comparable `python -m pytest tests/test_tool_schemas_importable.py` in Veas.
2. Run full test suites only if the focused checks pass and runtime is acceptable; otherwise report the exact failing focused tests as blockers.

## Execution Order
1. Build and test the shared package in isolation.
2. Wire Arnold first because it contains the required live fixes and richer resident runtime constraints.
3. Wire Veas second, only replacing duplicate infrastructure where the adapter stays thin.
4. Update dependency metadata after imports are stable.
5. Run focused tests in both repos, then broader smoke tests.

## Files Expected To Change
- `/Users/peteromalley/Documents/resident_chat_runtime/pyproject.toml`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/__init__.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/env.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/coalescing.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/discord_rest.py`
- `/Users/peteromalley/Documents/resident_chat_runtime/resident_chat_runtime/discord_gateway.py`
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
No tests were run during this planning pass; repository inspection only.

## Blockers
No hard blocker identified. Main risk is the large existing dirty worktree in both repos, especially target files already modified in Arnold and Veas. Implementation must inspect diffs before each edit and avoid reverting or overwriting unrelated user changes.
