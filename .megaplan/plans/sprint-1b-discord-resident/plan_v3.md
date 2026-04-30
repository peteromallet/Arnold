# Implementation Plan: Sprint 1b — Discord resident mode + robustness

## Overview

Sprint 1a delivered the substrate: `Store`, `Model`, `Transport`, `Blob` ports (`agent_kit/ports.py`), a SQLite store with `external_requests` ledger (`agent_kit/store/sqlite.py`, `agent_kit/store/migrations/sqlite/001_core.sql`), an idempotency-key Ledger (`agent_kit/ledger.py`), and an invocation-mode `run_turn` driving Anthropic via tool-use (`agent_kit/loop.py`, `agent_kit/model/anthropic.py`). The CLI reserves `--store supabase` but errors out (`arnold/cli.py:65`).

Sprint 1b adds a *second* implementation behind each port and builds resident-mode lifecycle on top. The plan is layered: interface changes (Phase 2) land first so adapters and tests in later phases consume the new shape.

**Locked decisions** (carried from prior gate `settled_decisions`): env-var Discord whitelist (SD-001); direct psycopg3 for store ops (SD-002); row-based `epic_locks` (SD-003); `images` table on both stores (SD-004); spec's same-turn end-of-turn re-prompt for mid-turn handling (SD-005); `tests/store_contract.py` unchanged + new `tests/store_contract_v1b.py` (SD-006); new `PushTransport` Protocol alongside the existing `Transport` (SD-007); image and voice scoped to Discord only this sprint (SD-008); `ToolContext` gains optional `transport`/`blob`/`external_queue` (SD-009).

**New design decisions in this revision (addressing iteration-2 flags):**

- **Tool atomicity preserved.** The audit wrapper continues to run the tool body inside `store.transaction()` exactly as today (`agent_kit/tool_kit.py:107`). What's new is a post-commit *external queue* for network IO: tools may append `(spec, callable)` pairs during execution; after the audit transaction commits, the wrapper invokes each callable and updates the ledger. Existing tests pass unchanged (`tests/test_tool_kit.py:27` rollback test still asserts the same property).
- **Anthropic replay material is durable.** A new nullable column `request_body JSONB` is added to `external_requests` (this sprint's migration). For providers requiring body replay (`anthropic`, `openai`), the loop persists the full canonical request body. The existing `request_summary` keeps its small-shape role per spec.
- **Mid-turn check covers explicit `send_message`.** `run_turn` invokes the unprocessed-messages check both at final-text time AND before each `send_message` tool call. Resident-mode `send_message` cannot post to Discord while unaddressed mid-turn messages exist; the loop instead retroactively widens `triggered_by_message_ids` and re-prompts the model.
- **Discord-ingestion IO is ledgered.** `DiscordTransport` takes a `Ledger` instance. Voice download, Storage upload, and Groq transcription each insert a pending `external_requests` row keyed off the inbound `discord_message_id` (no turn_id yet — ingestion runs before turn creation), and confirm/fail after the call. Recovery scan reconciles them like any other pending row.
- **`Blob` and `PushTransport` Protocols expose what the Reconciler calls.** `Blob.exists(ref)` is added. `PushTransport` includes `fetch_recent_messages(channel_id, since, until)`.

**Secrets policy.** The Supabase service-role JWT pasted into the idea block must NEVER be committed to migrations, tests, fixtures, docs, or this repo. All adapters read keys from env vars only. The user must rotate that key.

**Scope discipline.** This sprint stays Discord-only. Invocation-mode attachments (`--attach`, `run_turn(attachments=)`, `LocalBlobStore`) and the `transcribe_voice` tool / non-voice-audio adversarial path remain accepted Sprint 1a debt; explicit deferral note in Step 22.

---

## Phase 1: Foundation — dependencies, schema, secrets

### Step 1: Add Sprint 1b dependencies (`pyproject.toml`)
**Scope:** Small
1. **Add** to runtime `dependencies`: `discord.py`, `supabase`, `groq`, `httpx`, `psycopg[binary]>=3.1`.
2. **Add** to the `test` extra: `pytest-asyncio`.

### Step 2: Secrets handling (`/.gitignore`)
**Scope:** Small
1. **Create/update** `.gitignore` to exclude `.env`, `.env.local`, `supabase/.branches/*`.
2. **Validate** in CI/test bootstrap that no committed file matches the leaked JWT prefix `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSI` (cheap grep guard; pytest fixture or `tools/check_no_secrets.sh`).
3. **Action item** for the user (also recorded in `questions`): rotate the Supabase service-role key supplied in plain text in the idea block.

### Step 3: Supabase migration mirroring Sprint 1a (`supabase/migrations/<ts>_001_core.sql`)
**Scope:** Medium
1. **Initialize** `supabase/config.toml` and `supabase/migrations/`.
2. **Author** `<ts>_001_core.sql` mirroring `agent_kit/store/migrations/sqlite/001_core.sql:1`. Postgres differences: `JSONB` for json columns, `timestamptz` defaults via `now()`, `BOOLEAN` (not `INTEGER`/`CHECK`), keep `TEXT` PKs for cross-store id parity, enums as `CHECK` constraints. Same indexes.
3. **Add** the `epic_locks` table with the same row-based pattern as SQLite (SD-003).

### Step 4: Add `images` table + `request_body` column to both stores
**Scope:** Small
1. **Add** `supabase/migrations/<ts>_002_images.sql` and `agent_kit/store/migrations/sqlite/002_images.sql` per spec data model (`planning-bot-spec.md:1439`): `id`, `epic_id`, `source`, `prompt`, `storage_url`, `quality`, `size`, `created_at`, `reference_key`, `description`, `caption`, `in_body`, `active`, `discord_attachment_id`. Index `(epic_id, created_at DESC)`, partial unique on `(epic_id, reference_key) WHERE active = true`, `(epic_id, source)`.
2. **Add** `<ts>_003_external_requests_body.sql` (Supabase) and `agent_kit/store/migrations/sqlite/003_external_requests_body.sql` adding a nullable `request_body` column (JSONB on Postgres, TEXT-as-JSON on SQLite) to `external_requests`. This carries the full canonical request payload for providers that need body replay (FLAG-007 / correctness-2). Add `request_body` to `_JSON_COLUMNS` in `agent_kit/store/sqlite.py:17`.
3. **Confirm** `SQLiteStore.apply_migrations` (`agent_kit/store/sqlite.py:50`) picks up both new files via the existing sorted glob.

---

## Phase 2: Interface changes (must precede adapter work)

### Step 5: Extend `Model.complete_turn` with `idempotency_key`; persist replay material (`agent_kit/ports.py`, `agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`, `agent_kit/loop.py`, `agent_kit/ledger.py`)
**Scope:** Small
1. **Add** `idempotency_key: str | None = None` to `Model.complete_turn` (`agent_kit/ports.py:182`). `AnthropicModel` forwards it via `extra_headers={"Idempotency-Key": idempotency_key}` (`agent_kit/model/anthropic.py:37`). `FakeModel` accepts and ignores.
2. **Update** `Ledger.record_pending` (`agent_kit/ledger.py:31`) to accept an optional `request_body: JSONDict | None = None` and pass it to `Store.insert_pending`. Update `Store` Protocol (`agent_kit/ports.py:144`) and both store impls to accept and persist `request_body`.
3. **In `run_turn`** (`agent_kit/loop.py:101`), before each `model.complete_turn`, build the canonical request body `{"model": model_id, "messages": list(messages), "tools": list(registry.definitions()), "max_tokens": ANTHROPIC_MAX_TOKENS}` and pass it as `request_body` to `ledger.record_pending`. Also continue to pass `system_seq=model_call_seq` and persist `system_seq` in `request_summary` for diagnostic use. Closes FLAG-007 / correctness-2 / callers-3.

### Step 6: Add resident hooks to `run_turn` and gate `send_message` against mid-turn (`agent_kit/loop.py`)
**Scope:** Medium
1. **Add** keyword arguments to `run_turn`:
   - `triggered_by_message_ids: Sequence[str] | None = None` — when supplied, skip the inline `create_message` (resident has already persisted) and pass the IDs to `create_turn`.
   - `recovered_input_messages: Sequence[JSONDict] | None = None` — full persisted message rows whose `content` strings (in `sent_at` order) form the model's first user prompt.
   - `on_turn_start: Callable[[JSONDict], None] | None = None` — invoked synchronously after `create_turn` returns the row, before the first model call (closes FLAG-004 / scope-1).
   - `mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None = None` — replaces the prior `on_pre_finalize` name. Invoked at TWO checkpoints: (a) when the model has produced `final_text` and before the auto-`send_message`; (b) before executing any tool whose name is `send_message`. Returns either `None` (proceed) or a list of mid-turn message rows. When messages are returned, `run_turn`:
      - Synthesizes a `[Mid-turn messages — arrived after this turn started]` user-message block (spec `planning-bot-spec.md:824`).
      - Calls `update_turn(turn_id, triggered_by_message_ids=existing+new_ids)` to retroactively widen the trigger list.
      - Appends to `messages` and re-enters the model loop without finalizing or executing the deferred `send_message`.
2. **Gating implementation:** within the existing tool-request loop (`agent_kit/loop.py:193`), before calling `registry.invoke(tool_request.name, ...)` for `tool_request.name == "send_message"`, run the `mid_turn_message_check` and short-circuit to the re-prompt path when it returns messages. Closes FLAG-011 / scope.
3. **Keep** invocation-mode behavior identical when these kwargs are `None` — `tests/test_run_turn.py`, `tests/test_cli.py`, and `tests/test_envelope.py` continue to pass unmodified.

### Step 7: Mode-divergent `send_message`/`set_activity`/`send_image` via injected dependencies (`agent_kit/tool_kit.py`, `agent_kit/tools/communication.py`)
**Scope:** Small
1. **Extend** `ToolContext` (`agent_kit/tool_kit.py:29`) with optional fields: `transport: PushTransport | None = None`, `blob: Blob | None = None`, `external_queue: list[tuple[ExternalSpec, Callable]] | None = None`. Default `None` preserves invocation-mode shape.
2. **Update** `send_message` (`agent_kit/tools/communication.py:53`):
   - Invocation (`transport is None`): unchanged behavior — append to `reply_buffer`, write outbound row with synthetic id (`agent_kit/store/sqlite.py:101`).
   - Resident: write the outbound `messages` row inside the audit transaction WITHOUT `discord_message_id` (NULL allowed), then append a `(ExternalSpec(provider="discord", endpoint="POST /channels/.../messages", request_summary={"content_preview": content[:100], "channel_id": ...}), callable)` to `context.external_queue`. The callable: posts via `transport.post_message(...)`, updates `messages.discord_message_id` and returns `(provider_request_id, response_summary)` for the wrapper to mark confirmed.
3. **Update** `set_activity` (`agent_kit/tools/communication.py:75`) to also call `store.update_turn(turn_id, current_activity=description)` (spec `planning-bot-spec.md:1001`).

### Step 8: Audit wrapper — preserve atomicity, queue external IO post-commit (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. **Restructure** `audit_wrap` (`agent_kit/tool_kit.py:107`) into the following sequence. Existing test `tests/test_tool_kit.py:27` (failing tool's mutation rolls back) must keep passing.

   ```python
   def invoke(context, arguments):
       context.external_queue = []
       with context.store.transaction():
           raw_result = entry.func(context, **arguments)   # may mutate store
           result = _normalize_result(raw_result)
           tool_call = context.store.record_tool_call(...)
           pending_ids: list[str] = []
           for spec, _callable in context.external_queue:
               request_id, _ = ledger.record_pending(
                   provider=spec.provider, endpoint=spec.endpoint,
                   request_summary=spec.request_summary,
                   request_body=spec.request_body,
                   turn_id=context.turn_id, tool_call_id=tool_call["id"],
               )
               pending_ids.append(request_id)
       # Transaction has committed. Now run external IO.
       for (spec, fn), request_id in zip(context.external_queue, pending_ids):
           try:
               provider_id, response_summary = fn()
               ledger.mark_confirmed(request_id, provider_id, response_summary)
           except Exception as exc:
               ledger.mark_failed(request_id, error_details={"type": type(exc).__name__, "message": str(exc)})
               raise
       return ToolInvocation(...)
   ```
2. **Key invariant**: tool body still runs inside the transaction. DB mutations and `tool_calls` row commit atomically. Pending ledger rows are written in the SAME transaction (functionally equivalent to spec's "separate transaction" since they need to be durable before commit and we want them to roll back together with the tool_call row on failure). External callables run AFTER commit so network IO never holds the DB transaction open. Closes correctness-1 / FLAG-009 / callers / correctness-3.
3. **Tools that don't append to `external_queue` (the existing tools) behave identically** — the wrapper sees an empty queue and skips Stages 2/3.

### Step 9: Extend `Store`, `Blob`, and add `PushTransport` Protocol (`agent_kit/ports.py`)
**Scope:** Small
1. **Add** to the `Store` Protocol:
   - `find_abandoned_turns(older_than_seconds: int) -> list[JSONDict]`
   - `find_pending_external_requests(older_than_seconds: int) -> list[JSONDict]`
   - `mark_orphaned(request_id: str, *, error_details: JSONDict) -> JSONDict`
   - `find_unprocessed_messages(epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[JSONDict]`
   - `load_messages(message_ids: Sequence[str]) -> list[JSONDict]`
   - Image methods: `create_image(...)`, `load_image(image_id)`, `list_images(epic_id, source=None, active_only=True)`, `update_image(image_id, **changes)`.
   - Update `insert_pending` signature to include `request_body: JSONDict | None = None`.
2. **Add** `Blob.exists(ref: BlobRef) -> bool` (closes all_locations).
3. **Add** a separate `PushTransport` Protocol (do NOT mutate `Transport`). Methods: `start(handler) -> None`, `stop()`, `post_message(channel_id, content, *, files=None) -> JSONDict`, `edit_message(channel_id, message_id, content) -> JSONDict`, `download_attachment(url) -> bytes`, `fetch_recent_messages(channel_id: str, since: str, until: str) -> list[JSONDict]` (closes all_locations).

---

## Phase 3: Adapters

### Step 10: Implement `SupabaseStore` (`agent_kit/store/supabase.py` — new)
**Scope:** Large
1. **Build** `SupabaseStore` against the `Store` Protocol via direct `psycopg` (SD-002). Mirror `SQLiteStore` method-for-method (`agent_kit/store/sqlite.py:85-470`). JSONB returns dicts directly so no decode pass needed.
2. **`acquire_epic_lock`**: `INSERT INTO epic_locks ... ON CONFLICT (epic_id) DO UPDATE WHERE epic_locks.expires_at <= NOW() OR epic_locks.holder_id = EXCLUDED.holder_id` returning the actual holder. Same 60s timeout as SQLite (SD-003).
3. **Implement** all new Sprint 1b methods from Step 9. `create_image` auto-generates `reference_key` for `source='user_uploaded'` by selecting `MAX(reference_key)` matching `img_user_upload_%` for the epic.
4. **`insert_pending`** persists `request_body` as JSONB.

### Step 11: Mirror new Store methods in SQLite (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Add** the same methods (Step 9) to `SQLiteStore`.
2. **`request_body`** is stored as TEXT-encoded JSON in SQLite; ensure it's added to `_JSON_COLUMNS` (Step 4).

### Step 12: Supabase Storage blob adapter (`agent_kit/blob/supabase_storage.py` — new)
**Scope:** Small
1. **Implement** `SupabaseStorageBlob` against the now-extended `Blob` Protocol (`put`, `get`, `exists`). Use `supabase` Python client. Deterministic paths: `images/{epic_id}/{idempotency_key}.{ext}`, `audio/{epic_id}/{idempotency_key}.ogg` (spec `planning-bot-spec.md:1612`).
2. **`exists(ref)`** issues a HEAD via the storage API and returns the boolean.

### Step 13: Discord transport with ledgered ingestion (`agent_kit/transport/discord.py` — new)
**Scope:** Large
1. **Implement** `DiscordTransport` against `PushTransport` with discord.py. Privileged `MESSAGE_CONTENT` intent (`planning-bot-spec.md:2731`). Auth via `DISCORD_BOT_TOKEN`. Whitelist via `DISCORD_USER_WHITELIST` env var (SD-001).
2. **Constructor takes** `store`, `blob`, `ledger`, `groq_client`, `whitelist`. The transport does ingestion-side IO directly (it has no tool context) but must record each external call in `external_requests`. Ingestion ledger entries use `tool_call_id=None`, `turn_id=None`, and an idempotency key derived from the inbound `discord_message_id`: `sha256("ingest:" + discord_message_id + ":" + provider + ":" + endpoint)[:16]`. Extend `Ledger.derive_idempotency_key` (`agent_kit/ledger.py:75`) with an `ingest_message_id` branch. Closes FLAG-012 / issue_hints.
3. **Non-DM channels** rejected silently. **Non-whitelisted DMs** write a `system_logs` row at `level='info'`, `category='application'`, `event_type='whitelist_rejected'`. No reply.
4. **`on_message` ingestion** (every branch persists the `messages` row with the unique `discord_message_id` BEFORE any LLM invocation; spec `planning-bot-spec.md:2453`):
   - **Voice attachment** (`attachment.is_voice_message()`):
     1. Insert ledger pending row `(provider='supabase_storage', endpoint='PUT audio/...')`. Download bytes via `httpx`. Upload to Storage. Mark confirmed.
     2. Insert ledger pending row `(provider='groq', endpoint='POST /audio/transcriptions', request_body={"model":"whisper-large-v3","audio_storage_url":...})`. Call Groq. Mark confirmed/failed.
     3. Persist `messages` row with `was_voice_message=True`, `audio_storage_url`, `content=<transcription>`, `transcription_metadata=<groq response summary>`.
   - **Image attachment**: ledger pending `supabase_storage` upload, then `store.create_image(...)`, then persist `messages` row with `has_image_attachment=True`. Mark confirmed/failed for the upload.
   - **Text-only**: persist `messages` row.
5. **Hand off** the persisted `message_id` to the resident runner via the `start(handler)` callback.
6. **`fetch_recent_messages`** uses `channel.history(after=since, before=until)` and returns `[{"discord_message_id":..., "content":..., "created_at":...}, ...]` for reconciler use.

### Step 14: Resident runner (`agent_kit/resident.py` — new)
**Scope:** Large
1. **`MessageCoalescer`** per epic: 10s reset-on-new-message timer, 30s hard cap, 10-message cap (spec `planning-bot-spec.md:817`). When the timer fires AND no turn is in flight, dispatch.
2. **`ResidentRunner.dispatch_turn(epic_id, message_ids)`** loads messages via `store.load_messages(message_ids)`, then invokes `run_turn(epic_id=..., input=<unused — replaced by recovered_input_messages>, store=..., model=..., triggered_by_message_ids=message_ids, recovered_input_messages=loaded, on_turn_start=self._on_turn_start, mid_turn_message_check=self._mid_turn_check, on_event=self._on_event)`. Tool context for resident-mode tools also receives `transport`, `blob`, `external_queue` so `send_message`, `send_image`, `set_activity` route to Discord (closes callers-2 / FLAG-002).
3. **`_on_turn_start(turn)`**: enqueue (via the resident-specific path: not a tool, so no audit wrapper — runner uses `Ledger` directly) a Discord `post_message` for the initial status; capture id; `store.update_turn(turn['id'], status_message_id=...)`. Pending row tracked in `external_requests` (`tool_call_id=None`, `turn_id=turn['id']`).
4. **`_on_event(event)`**: on `tool_call`/`activity` events, format the status (Step 15) and call `transport.edit_message(...)` with 1s debounce.
5. **`_mid_turn_check(turn)`**: returns `store.find_unprocessed_messages(epic_id=turn['epic_id'], started_at=turn['started_at'], exclude_ids=turn['triggered_by_message_ids'])` (or `None`). If non-empty, append `📥 Received "[first 60]…"` lines to the live status message before returning the list. Same hook handles both the final-text case and the explicit-`send_message` case in `run_turn` (Step 6).
6. **Mid-turn arrival concurrent with an in-flight turn**: Discord transport persists the row immediately. Coalescer sees turn is in flight and does not start a new turn; the message is picked up by the in-flight turn's mid-turn check.
7. **Recovery scheduler**: asyncio task running `Reconciler.run_once()` (Step 16) at startup AND every 5 minutes (spec `planning-bot-spec.md:2492`). Re-queues abandoned turns' `triggered_by_message_ids` through the coalescer.

### Step 15: Status message formatter (`agent_kit/resident.py`)
**Scope:** Small
1. Pure function `format_status(turn_row, recent_tool_calls, current_activity, last_call_ts) -> str` returning the markdown body from `planning-bot-spec.md:979-988` with the Discord `<t:UNIX:R>` timestamp.
2. Final state: `✅ Done. N tool calls. <t:UNIX:R>` on completion; `❌ Failed. <reason>` on error.

### Step 16: External-request reconciliation (`agent_kit/ledger.py`)
**Scope:** Medium
1. **Replace** `reconcile_on_boot` (`agent_kit/ledger.py:96`) with a `Reconciler` class. Constructor takes `store`, `model`, `transport`, `blob`. `run_once()` does:
   - **Abandoned turns:** `find_abandoned_turns(300)` → mark `status='abandoned'`, log to `system_logs` at `warn`/`recovery`, return their `triggered_by_message_ids` to the caller (resident runner re-queues).
   - **Pending externals:** `find_pending_external_requests(60)` → per-provider dispatch (`planning-bot-spec.md:1599-1612`):
     - `anthropic` / `openai`: replay via `model.complete_turn(idempotency_key=row.idempotency_key, model_id=row.request_body["model"], messages=row.request_body["messages"], tools=row.request_body["tools"], hot_context={})`. Body comes from the durable `request_body` column added in Step 4 (closes FLAG-007 / correctness-2). Mark confirmed/failed.
     - `discord`: call `transport.fetch_recent_messages(channel_id=row.request_summary["channel_id"], since=row.first_attempted_at, until=row.last_attempted_at + 30s)` and match by `content_preview`. Found → `mark_confirmed`. Not found → `mark_orphaned` and re-queue the underlying tool call's effect (resident runner inspects orphaned rows on its periodic pass).
     - `groq`: deterministic re-issue using `row.request_body["audio_storage_url"]` and `row.request_body["model"]`.
     - `supabase_storage`: `blob.exists(ref)` → `mark_confirmed` if present, else re-issue.
     - `github`: log `recovery` info entry and skip (out of scope this sprint).
2. **Idempotency-key derivation** continues to use `derive_idempotency_key` (`agent_kit/ledger.py:75`) with the new `ingest_message_id` branch added in Step 13.2. Replay always uses the row's stored `idempotency_key` (not re-derivation).

---

## Phase 4: Image tools and CLI wiring

### Step 17: Image tools (`agent_kit/tools/images.py` — new)
**Scope:** Medium
1. **Register** four tools using `register_tool`:
   - `list_images(epic_id, source?)` — `read`, metadata only.
   - `view_image(image_id, mode='visual'|'description')` — `read`. Uses `context.blob.get(...)` for `visual`. Result includes base64 payload + media_type.
   - `send_image(image_id, caption?)` — `write`. Resident: appends `(ExternalSpec(provider="discord", endpoint="POST /channels/.../messages", ...), callable)` to `context.external_queue` (mirrors `send_message`). Invocation: appends to envelope `events` array (`planning-bot-spec.md:1653`).
   - `update_image_metadata(image_id, caption?, description?, reference_key?)` — `write`. Validates reference_key regex `^[a-z][a-z0-9_]{0,63}$`.
2. **Auto-import** in `agent_kit/loop.py` beside the existing `import agent_kit.tools.communication`.

### Step 18: Wire `view_image` bytes through to Anthropic (`agent_kit/loop.py`, `agent_kit/model/anthropic.py`)
**Scope:** Small
1. **Detect** in the loop's tool-result message construction (`agent_kit/loop.py:237`) when `result.get("media_type")` and `result.get("image_bytes_b64")` are present (the `view_image` shape) and emit Anthropic vision content blocks. Other tools' result shape is unchanged.

### Step 19: Resident CLI entry point (`arnold/cli.py`)
**Scope:** Small
1. **Replace** the `_unsupported_store_envelope` short-circuit (`arnold/cli.py:65`) with `SupabaseStore` construction from env (`SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`).
2. **Add** an `arnold resident` subcommand that constructs `SupabaseStore`, `SupabaseStorageBlob`, `Ledger`, `DiscordTransport`, `AnthropicModel`, `Reconciler`, `ResidentRunner` and runs the asyncio loop until SIGINT. Required env vars validated up front.

---

## Phase 5: Tests and verification

### Step 20: Unit and contract tests (`tests/`)
**Scope:** Medium
1. **Leave** `tests/store_contract.py` UNCHANGED.
2. **`tests/store_contract_v1b.py`** — exercises `find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `load_messages`, image CRUD, the unique-idempotency-key constraint, AND the new `request_body` round-trip.
3. **`tests/test_supabase_store.py`** — runs both `run_store_contract` (unchanged) AND `run_store_contract_v1b` against `SupabaseStore`. Skip module via `pytest.importorskip("psycopg")` and an env-var check on `SUPABASE_TEST_DB_URL`.
4. **`tests/test_sqlite_store.py`** — extend to also call `run_store_contract_v1b` (the existing v1a test stays untouched so the unchanged property stands).
5. **`tests/test_coalescer.py`** — virtual-time tests: 5 in 8s → 1 trigger; 30s cap; 10-message cap.
6. **`tests/test_whitelist.py`** — Discord transport whitelist filter writes the expected log row, no reply.
7. **`tests/test_status_formatter.py`** — golden-string match against the spec template.
8. **`tests/test_reconciler.py`** — Anthropic replay (stub `Model` records `idempotency_key` AND verifies `messages`/`tools` come from `request_body`); Discord post-hoc lookup confirmed/orphaned (uses stub `PushTransport.fetch_recent_messages`); Storage HEAD-confirm (uses stub `Blob.exists`); Groq deterministic re-issue.
9. **`tests/test_image_tools.py`** — `list_images`, `view_image` description+visual, `update_image_metadata` regex, `send_image` invocation event + resident queued callback.
10. **`tests/test_run_turn_hooks.py`** — `on_turn_start` fires after `create_turn`; `mid_turn_message_check` returning new messages causes a re-prompt with the spec block AND widens `triggered_by_message_ids`; the same check fires before an EXPLICIT `send_message` tool invocation in resident mode (asserted by counting model calls and tool invocations); existing invocation-mode behavior unchanged when hooks are `None`.
11. **`tests/test_tool_kit_external_queue.py`** — verifies (a) tool body mutation rolled back when tool raises (preserves `tests/test_tool_kit.py:27` invariant); (b) ledger pending row exists at commit time; (c) external callable runs AFTER commit (`store.transaction_depth == 0` at callable invocation); (d) ledger row marked `confirmed` after success, `failed` after callable raises.
12. **`tests/test_discord_ingestion_ledger.py`** — voice ingestion records two pending rows (`supabase_storage`, `groq`) keyed off `discord_message_id`, both transition pending→confirmed; image ingestion records one `supabase_storage` row pending→confirmed; failure path marks failed and the `messages` row is still persisted.

### Step 21: Integration tests (`tests/`)
**Scope:** Medium
1. **`tests/test_resident_recovery.py`** — start `ResidentRunner` over in-memory `SQLiteStore` + `FakeDiscordTransport`; cancel a turn mid-tool-call; on next `Reconciler.run_once`, prior turn is `abandoned`, fresh turn fires with same `triggered_by_message_ids`.
2. **`tests/test_voice_pipeline.py`** — `FakeDiscordTransport` delivers a voice attachment; mocked Groq returns transcription; `messages` row has `was_voice_message=True`, transcribed `content`, `audio_storage_url` set; both ingestion ledger rows confirmed.
3. **`tests/test_image_attachment_pipeline.py`** — image attachment → `images` row `source='user_uploaded'`, `reference_key='img_user_upload_1'`; subsequent attachment auto-assigns `img_user_upload_2`; ingestion ledger row confirmed.
4. **`tests/test_status_lifecycle.py`** — `FakeModel` script with 3 tool calls produces: 1 initial post + ≤3 edits + 1 final `✅ Done. 3 tool calls.`; throttling test: 20 tool calls in 2s → ≤4 edits.
5. **`tests/test_mid_turn_messages.py`** — burst turn in flight; second message arrives mid-tool-call; status gets `📥 Received…`; widened `triggered_by_message_ids` AND a synthesized mid-turn user message arrives in the model's next prompt; final reply addresses it. Variant: model issues an explicit `send_message` mid-turn → still gated by the check; no Discord post fires until the model finishes processing the mid-turn block.
6. **`tests/test_send_message_resident.py`** — resident `send_message` posts via `FakeDiscordTransport.post_message`; `messages.discord_message_id` populated AFTER commit (asserted via store hook); `external_requests` row transitions pending→confirmed; tool body's DB writes commit before the network call.
7. **`tests/test_anthropic_replay.py`** — pending Anthropic row → reconciler reissues with stored `request_body` and `idempotency_key`; stub Anthropic returns the deduplicated response; row marked confirmed.

### Step 22: Final verification and deferral note
**Scope:** Small
1. **Run** `pytest` — full suite green; existing Sprint 1a tests (`tests/test_envelope.py`, `tests/test_ledger.py`, `tests/test_run_turn.py`, the original cases in `tests/test_sqlite_store.py`, `tests/test_cli.py`, `tests/test_tool_kit.py`) pass UNCHANGED.
2. **Append** a deferral note (TODO comment in `agent_kit/loop.py` near the `input` parameter, OR a new `ideas/sprint_1c_attachments.md`) capturing: invocation-mode `--attach` / `run_turn(attachments=)` / `LocalBlobStore` (`planning-bot-spec.md:1895-1908`) AND `transcribe_voice` tool / non-voice-audio path (`planning-bot-spec.md:2634`).
3. **Manual smoke** (info, not pipeline-checked): `arnold resident` against staging Discord + staging Supabase — whitelisted DM responds within 30s; voice DM transcribes; image attachment lands in Storage with `images` row; mid-turn DM updates the status message in the same turn.

## Execution Order

1. **Phase 1** — deps, secrets, migrations (core + images + `request_body`).
2. **Phase 2** — interface changes (model `idempotency_key`, ledger `request_body` plumbing, `run_turn` hooks + send_message gating, ToolContext extension, audit wrapper external queue).
3. **Phase 3** — Supabase store, Storage blob (with `exists`), Discord transport (with ledgered ingestion + `fetch_recent_messages`), resident runner, reconciler.
4. **Phase 4** — image tools, Anthropic vision wiring, resident CLI subcommand.
5. **Phase 5** — tests interleave per phase; integration tests in Step 21 land last.

## Validation Order

1. Cheapest first: existing Sprint 1a tests (must still pass unmodified).
2. New unit tests (Step 20): hooks, external queue ordering with rollback, coalescer, whitelist, status formatter, reconciler, image tools, ingestion ledger.
3. Sprint 1b contract test against both stores.
4. Resident integration tests (Step 21): recovery, voice, image, status lifecycle, mid-turn (final-text + explicit-send_message paths), resident `send_message`, Anthropic replay.
5. Manual smoke against staging — last, info-priority.
