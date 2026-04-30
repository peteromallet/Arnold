# Implementation Plan: Sprint 1b — Discord resident mode + robustness

## Overview

Sprint 1a delivered the substrate: `Store`, `Model`, `Transport`, `Blob` ports (`agent_kit/ports.py`), a SQLite store with `external_requests` ledger (`agent_kit/store/sqlite.py`, `agent_kit/store/migrations/sqlite/001_core.sql`), an idempotency-key Ledger (`agent_kit/ledger.py`), and an invocation-mode `run_turn` driving Anthropic via tool-use (`agent_kit/loop.py`, `agent_kit/model/anthropic.py`). The CLI reserves `--store supabase` but errors out (`arnold/cli.py:65`).

Sprint 1b adds a *second* implementation behind each port and builds resident-mode lifecycle on top. Interface changes (Phase 2) land first; adapters and tests in later phases consume the new shape.

**Locked decisions** (carried from prior gate `settled_decisions`): SD-001 env-var Discord whitelist; SD-002 direct psycopg3 for store ops; SD-003 row-based `epic_locks`; SD-004 `images` table on both stores; SD-005 same-turn end-of-turn re-prompt for mid-turn handling, gating both final-text and explicit `send_message`; SD-006 `tests/store_contract.py` unchanged + new `tests/store_contract_v1b.py`; SD-007 `PushTransport` Protocol alongside `Transport`; SD-008 image/voice scoped to Discord this sprint; SD-009 `ToolContext` gains optional `transport`/`blob`/`external_queue`; SD-010 audit wrapper keeps tool body inside `store.transaction()`, only post-commit network callables queued; SD-011 `external_requests` gets nullable `request_body`; SD-012 Discord ingestion-side IO ledgered with `discord_message_id`-keyed idempotency; SD-013 `Blob.exists` and `PushTransport.fetch_recent_messages` published in the protocols.

**New design decisions in this revision (addressing iteration-3 flags):**

- **Inbound `messages` row persists FIRST.** For every Discord DM (text, voice, image), `DiscordTransport.on_message` writes the `messages` row with the unique `discord_message_id` BEFORE any external IO runs. This satisfies spec lines 79 and 2455-2459: gateway-replay duplicates collide on the unique constraint immediately, and recovery sees persisted-but-unprocessed messages even if attachment processing crashes. The initial row carries placeholders (`content=""` for voice, `was_voice_message=True`/`has_image_attachment=True` flags set at create time so recovery sees the intent). Storage upload, Groq transcription, image-row creation all run AFTER the row is committed, then `Store.update_message(message_id, ...)` fills in `content`, `audio_storage_url`, `transcription_metadata` once those calls succeed.
- **`Store.update_message(message_id, **changes)` added.** Three flows need it: resident `send_message` (fill `discord_message_id` post-confirm), voice ingestion (fill transcription/audio fields post-Groq), and the resident status-message lifecycle. Single new Protocol method, implemented in both stores.
- **SQLite synthetic-id generation is opt-in.** `SQLiteStore.create_message` (`agent_kit/store/sqlite.py:101`) currently auto-generates `inv_<turn_id>_<N>` for any outbound row with a `bot_turn_id` and no `discord_message_id`. Add a `synthesize_outbound_id: bool = True` parameter — invocation-mode `send_message` passes `True` (preserves Sprint 1a behavior); resident-mode `send_message` passes `False` so the row is created with `discord_message_id=NULL` and later updated via `update_message`.
- **Inbound persistence + ingestion-ledger pending rows are written in one transaction.** A crash between persisting the message and starting Storage/Groq leaves a consistent state: the `messages` row is durable AND the pending ledger rows that describe the intended external work are durable, so the reconciler can finish or orphan them deterministically.

**Secrets policy.** The Supabase service-role JWT pasted into the idea block must NEVER be committed. All adapters read keys from env vars only. The user must rotate that key.

**Scope discipline.** Discord-only this sprint. Invocation-mode attachments and `transcribe_voice` tool stay deferred (Step 22).

---

## Phase 1: Foundation — dependencies, schema, secrets

### Step 1: Add Sprint 1b dependencies (`pyproject.toml`)
**Scope:** Small
1. **Add** to runtime `dependencies`: `discord.py`, `supabase`, `groq`, `httpx`, `psycopg[binary]>=3.1`.
2. **Add** to the `test` extra: `pytest-asyncio`.

### Step 2: Secrets handling (`/.gitignore`)
**Scope:** Small
1. **Create/update** `.gitignore` to exclude `.env`, `.env.local`, `supabase/.branches/*`.
2. **Validate** in CI/test bootstrap that no committed file matches the leaked JWT prefix `[REDACTED_SUPABASE_JWT_PREFIX]` (cheap grep guard).
3. **Action item** for the user: rotate the Supabase service-role key supplied in plain text.

### Step 3: Supabase migration mirroring Sprint 1a (`supabase/migrations/<ts>_001_core.sql`)
**Scope:** Medium
1. **Initialize** `supabase/config.toml` and `supabase/migrations/`.
2. **Author** `<ts>_001_core.sql` mirroring `agent_kit/store/migrations/sqlite/001_core.sql:1`. Postgres differences: `JSONB` for json columns, `timestamptz` defaults via `now()`, `BOOLEAN`, `TEXT` PKs, enums as `CHECK`. Same indexes.
3. **Add** `epic_locks` table with the same row-based pattern as SQLite (SD-003).

### Step 4: Add `images` table + `request_body` column to both stores
**Scope:** Small
1. **Add** `supabase/migrations/<ts>_002_images.sql` and `agent_kit/store/migrations/sqlite/002_images.sql` per spec data model (`planning-bot-spec.md:1439`). Index `(epic_id, created_at DESC)`, partial unique on `(epic_id, reference_key) WHERE active = true`, `(epic_id, source)`.
2. **Add** `<ts>_003_external_requests_body.sql` (Supabase) and `agent_kit/store/migrations/sqlite/003_external_requests_body.sql` adding nullable `request_body` (JSONB on Postgres, TEXT-as-JSON on SQLite). Add `request_body` to `_JSON_COLUMNS` (`agent_kit/store/sqlite.py:17`).
3. **Confirm** `SQLiteStore.apply_migrations` (`agent_kit/store/sqlite.py:50`) picks up the new files.

---

## Phase 2: Interface changes (must precede adapter work)

### Step 5: Extend `Model.complete_turn` and persist replay material (`agent_kit/ports.py`, `agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`, `agent_kit/loop.py`, `agent_kit/ledger.py`)
**Scope:** Small
1. **Add** `idempotency_key: str | None = None` to `Model.complete_turn` (`agent_kit/ports.py:182`). `AnthropicModel` forwards it via `extra_headers={"Idempotency-Key": idempotency_key}`. `FakeModel` accepts and ignores.
2. **Update** `Ledger.record_pending` (`agent_kit/ledger.py:31`) and `Store.insert_pending` (`agent_kit/ports.py:144`) to accept `request_body: JSONDict | None = None`. Both store impls persist it.
3. **In `run_turn`** (`agent_kit/loop.py:101`), build the canonical request body `{"model": model_id, "messages": list(messages), "tools": list(registry.definitions()), "max_tokens": ANTHROPIC_MAX_TOKENS}` and pass it as `request_body`. Persist `system_seq=model_call_seq` in `request_summary` for diagnostic use.

### Step 6: Add resident hooks to `run_turn`; gate `send_message` against mid-turn (`agent_kit/loop.py`)
**Scope:** Medium
1. **Add** keyword arguments to `run_turn`:
   - `triggered_by_message_ids: Sequence[str] | None = None` — when supplied, skip the inline `create_message` and pass the IDs straight to `create_turn`.
   - `recovered_input_messages: Sequence[JSONDict] | None = None` — full persisted message rows whose `content` strings (in `sent_at` order) form the model's first user prompt.
   - `on_turn_start: Callable[[JSONDict], None] | None = None` — invoked synchronously after `create_turn` returns the row, before the first model call.
   - `mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None = None` — invoked at TWO checkpoints: (a) when the model has produced `final_text` and before the auto-`send_message`; (b) before executing any tool whose name is `send_message`. When non-None messages are returned, `run_turn` synthesizes a `[Mid-turn messages — arrived after this turn started]` block, calls `update_turn(turn_id, triggered_by_message_ids=existing+new_ids)`, appends to `messages`, and re-enters the model loop without finalizing.
2. **Keep** invocation-mode behavior identical when these kwargs are `None` — `tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_envelope.py` continue passing unmodified.

### Step 7: Mode-divergent `send_message` / `set_activity` / `send_image` via injected dependencies (`agent_kit/tool_kit.py`, `agent_kit/tools/communication.py`)
**Scope:** Small
1. **Extend** `ToolContext` (`agent_kit/tool_kit.py:29`) with optional `transport: PushTransport | None = None`, `blob: Blob | None = None`, `external_queue: list[tuple[ExternalSpec, Callable]] | None = None`. Default `None` preserves invocation-mode shape.
2. **Update** `send_message` (`agent_kit/tools/communication.py:53`):
   - **Invocation** (`transport is None`): call `store.create_message(..., synthesize_outbound_id=True)` — preserves Sprint 1a synthetic-id behavior.
   - **Resident** (`transport is not None`): call `store.create_message(..., synthesize_outbound_id=False)` so the row is committed with `discord_message_id=NULL`. Append `(ExternalSpec(provider="discord", endpoint="POST /channels/.../messages", request_summary={"content_preview": content[:100], "channel_id": ..., "message_row_id": <id>}), callable)` to `context.external_queue`. The callable: posts via `transport.post_message(...)`, then `store.update_message(message_row_id, discord_message_id=<discord_id>)`, returns `(discord_id, response_summary)` for the wrapper to mark confirmed.
3. **Update** `set_activity` (`agent_kit/tools/communication.py:75`) to also call `store.update_turn(turn_id, current_activity=description)`.

### Step 8: Audit wrapper — preserve atomicity, queue external IO post-commit (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. **Restructure** `audit_wrap` (`agent_kit/tool_kit.py:107`):
   ```python
   def invoke(context, arguments):
       context.external_queue = []
       with context.store.transaction():
           raw_result = entry.func(context, **arguments)
           result = _normalize_result(raw_result)
           tool_call = context.store.record_tool_call(...)
           pending_ids = []
           for spec, _callable in context.external_queue:
               request_id, _ = ledger.record_pending(
                   provider=spec.provider, endpoint=spec.endpoint,
                   request_summary=spec.request_summary,
                   request_body=spec.request_body,
                   turn_id=context.turn_id, tool_call_id=tool_call["id"],
               )
               pending_ids.append(request_id)
       # Transaction has committed.
       for (spec, fn), request_id in zip(context.external_queue, pending_ids):
           try:
               provider_id, response_summary = fn()
               ledger.mark_confirmed(request_id, provider_id, response_summary)
           except Exception as exc:
               ledger.mark_failed(request_id, error_details={"type": type(exc).__name__, "message": str(exc)})
               raise
       return ToolInvocation(...)
   ```
2. **Tools that don't append to `external_queue`** (the existing tools and the invocation-mode path) behave identically. The Sprint 1a rollback test at `tests/test_tool_kit.py:27` is preserved verbatim.

### Step 9: Extend `Store`, `Blob`, and add `PushTransport` Protocol (`agent_kit/ports.py`)
**Scope:** Small
1. **Add** to the `Store` Protocol:
   - `find_abandoned_turns(older_than_seconds: int) -> list[JSONDict]`
   - `find_pending_external_requests(older_than_seconds: int) -> list[JSONDict]`
   - `mark_orphaned(request_id: str, *, error_details: JSONDict) -> JSONDict`
   - `find_unprocessed_messages(epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[JSONDict]`
   - `load_messages(message_ids: Sequence[str]) -> list[JSONDict]`
   - **`update_message(message_id: str, **changes: Any) -> JSONDict`** — partial update for `discord_message_id`, `content`, `audio_storage_url`, `transcription_metadata`, `has_image_attachment`. Closes FLAG-014 / all_locations.
   - Image methods: `create_image(...)`, `load_image(image_id)`, `list_images(...)`, `update_image(...)`.
   - `create_message` gains a `synthesize_outbound_id: bool = True` parameter — closes correctness / callers.
   - `insert_pending` gains `request_body: JSONDict | None = None` (already covered in Step 5).
2. **Add** `Blob.exists(ref: BlobRef) -> bool` to the `Blob` Protocol.
3. **Add** a separate `PushTransport` Protocol with `start(handler) -> None`, `stop()`, `post_message(channel_id, content, *, files=None) -> JSONDict`, `edit_message(channel_id, message_id, content) -> JSONDict`, `download_attachment(url) -> bytes`, `fetch_recent_messages(channel_id: str, since: str, until: str) -> list[JSONDict]`.

---

## Phase 3: Adapters

### Step 10: Implement `SupabaseStore` (`agent_kit/store/supabase.py` — new)
**Scope:** Large
1. **Build** `SupabaseStore` against the `Store` Protocol via direct `psycopg` (SD-002). Mirror `SQLiteStore` method-for-method (`agent_kit/store/sqlite.py:85-470`). JSONB returns dicts directly so no decode pass needed.
2. **`acquire_epic_lock`**: `INSERT INTO epic_locks ... ON CONFLICT (epic_id) DO UPDATE WHERE epic_locks.expires_at <= NOW() OR epic_locks.holder_id = EXCLUDED.holder_id` returning the actual holder.
3. **Implement** all new Sprint 1b methods from Step 9 — including `update_message` (one UPDATE statement, JSONB serialization for `transcription_metadata`).
4. **`create_message`** honors the `synthesize_outbound_id` flag: when `False`, leaves `discord_message_id` NULL on outbound rows.
5. **`insert_pending`** persists `request_body` as JSONB.

### Step 11: Mirror new Store methods in SQLite (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Add** all new methods (Step 9) to `SQLiteStore`.
2. **Modify** `_next_invocation_message_id` invocation in `create_message` (`agent_kit/store/sqlite.py:101`) to be gated by `synthesize_outbound_id: bool = True` parameter. Default preserves Sprint 1a behavior.
3. **Implement** `update_message(message_id, **changes)` — UPDATE with JSON-encode for `transcription_metadata` per `_JSON_COLUMNS` rules.

### Step 12: Supabase Storage blob adapter (`agent_kit/blob/supabase_storage.py` — new)
**Scope:** Small
1. **Implement** `SupabaseStorageBlob` against the now-extended `Blob` Protocol (`put`, `get`, `exists`). Deterministic paths: `images/{epic_id}/{idempotency_key}.{ext}`, `audio/{epic_id}/{idempotency_key}.ogg`.
2. **`exists(ref)`** issues a HEAD via the storage API.

### Step 13: Discord transport with persist-first ingestion (`agent_kit/transport/discord.py` — new)
**Scope:** Large
1. **Implement** `DiscordTransport` against `PushTransport`. Privileged `MESSAGE_CONTENT` intent. Auth via `DISCORD_BOT_TOKEN`. Whitelist via `DISCORD_USER_WHITELIST` env var.
2. **Constructor** takes `store`, `blob`, `ledger`, `groq_client`, `whitelist`. Ingestion ledger entries use `tool_call_id=None`, `turn_id=None`, idempotency key from new `ingest_message_id` branch in `derive_idempotency_key`: `sha256("ingest:" + discord_message_id + ":" + provider + ":" + endpoint)[:16]`.
3. **Non-DM channels** rejected silently. **Non-whitelisted DMs** write a `system_logs` row at `level='info'`, `category='application'`, `event_type='whitelist_rejected'`. No reply.
4. **`on_message` ingestion — persist FIRST, external IO SECOND, update THIRD.** Closes FLAG-013 / issue_hints / scope. The first transaction wraps both the `messages` insert AND the ingestion ledger pending rows so a crash before external IO leaves a recoverable state with both committed:
   - **Voice attachment** (`attachment.is_voice_message()`):
     1. **Transaction 1** (atomic): `store.create_message(direction='inbound', discord_message_id=<...>, was_voice_message=True, has_image_attachment=False, content="", audio_storage_url=None, transcription_metadata=None)` AND insert two pending ledger rows: `(provider='supabase_storage', endpoint='PUT audio/...', idempotency_key=ingest:<msg_id>:supabase_storage:...)` and `(provider='groq', endpoint='POST /audio/transcriptions', request_body={"model":"whisper-large-v3","audio_storage_url":<deterministic_path>}, idempotency_key=ingest:<msg_id>:groq:...)`. Commit.
     2. Download bytes via `httpx`. Upload to Storage at the deterministic path. Mark Storage ledger row confirmed.
     3. Call Groq with the storage URL. Mark Groq ledger row confirmed.
     4. `store.update_message(message_id, content=<transcription>, audio_storage_url=<url>, transcription_metadata=<groq response summary>)`.
   - **Image attachment**:
     1. **Transaction 1**: `store.create_message(direction='inbound', discord_message_id=<...>, has_image_attachment=True, was_voice_message=False)` AND insert pending ledger row `(provider='supabase_storage', endpoint='PUT images/...', request_body={"deterministic_path":...})`. Commit.
     2. Download bytes. Upload to Storage. Mark ledger row confirmed.
     3. `store.create_image(epic_id=..., source='user_uploaded', storage_url=..., discord_attachment_id=...)` (auto-assigns `img_user_upload_<N>`).
     4. (Optional) `store.update_message(message_id, content=<text body if any>)` if the Discord message had text alongside the image.
   - **Text-only**: single `store.create_message(direction='inbound', discord_message_id=<...>, content=<text>)`. No external IO, no ledger row. Done.
5. **Hand off** the persisted `message_id` to the resident runner via the `start(handler)` callback.
6. **`fetch_recent_messages`** uses `channel.history(after=since, before=until)` and returns `[{"discord_message_id":..., "content":..., "created_at":...}, ...]`.

### Step 14: Resident runner (`agent_kit/resident.py` — new)
**Scope:** Large
1. **`MessageCoalescer`** per epic: 10s reset-on-new-message timer, 30s hard cap, 10-message cap (spec `planning-bot-spec.md:817`).
2. **`ResidentRunner.dispatch_turn(epic_id, message_ids)`** loads messages via `store.load_messages(message_ids)`, then invokes `run_turn` with the new resident kwargs (Step 6). `ToolContext` for resident-mode tools also receives `transport`, `blob`, `external_queue`.
3. **`_on_turn_start(turn)`**: enqueue (via `Ledger` directly, not a tool) a Discord `post_message` for the initial status; capture id; `store.update_turn(turn['id'], status_message_id=...)`.
4. **`_on_event(event)`**: on `tool_call`/`activity` events, format the status (Step 15) and call `transport.edit_message(...)` with 1s debounce.
5. **`_mid_turn_check(turn)`**: returns `store.find_unprocessed_messages(epic_id=turn['epic_id'], started_at=turn['started_at'], exclude_ids=turn['triggered_by_message_ids'])` (or `None`). If non-empty, append `📥 Received "[first 60]…"` lines to the live status message before returning the list.
6. **Mid-turn arrival**: Discord transport persists immediately (Step 13.4). Coalescer sees turn is in flight and skips dispatch; the message is picked up by the in-flight turn's mid-turn check.
7. **Recovery scheduler**: asyncio task running `Reconciler.run_once()` at startup AND every 5 minutes.

### Step 15: Status message formatter (`agent_kit/resident.py`)
**Scope:** Small
1. Pure function `format_status(turn_row, recent_tool_calls, current_activity, last_call_ts) -> str` returning the markdown body from `planning-bot-spec.md:979-988` with the Discord `<t:UNIX:R>` timestamp.
2. Final state: `✅ Done. N tool calls. <t:UNIX:R>` on completion; `❌ Failed. <reason>` on error.

### Step 16: External-request reconciliation (`agent_kit/ledger.py`)
**Scope:** Medium
1. **Replace** `reconcile_on_boot` (`agent_kit/ledger.py:96`) with a `Reconciler` class. `run_once()` does:
   - **Abandoned turns:** `find_abandoned_turns(300)` → mark `abandoned`, log to `system_logs` at `warn`/`recovery`, return `triggered_by_message_ids` to caller.
   - **Pending externals:** `find_pending_external_requests(60)` per-provider:
     - `anthropic` / `openai`: replay via `model.complete_turn(idempotency_key=row.idempotency_key, model_id=row.request_body["model"], messages=row.request_body["messages"], tools=row.request_body["tools"], hot_context={})`.
     - `discord`: `transport.fetch_recent_messages(...)` matching by `content_preview`. Found → `mark_confirmed`. Not found → `mark_orphaned` and re-queue.
     - `groq`: deterministic re-issue using stored `request_body["audio_storage_url"]` and model.
     - `supabase_storage`: `blob.exists(ref)` → `mark_confirmed` if present, else re-issue.
     - `github`: log `recovery` info entry and skip.
2. **Idempotency-key derivation** (`agent_kit/ledger.py:75`) extends with the `ingest_message_id` branch (Step 13.2). Replay always uses the row's stored key.

---

## Phase 4: Image tools and CLI wiring

### Step 17: Image tools (`agent_kit/tools/images.py` — new)
**Scope:** Medium
1. **Register** four tools using `register_tool`:
   - `list_images(epic_id, source?)` — `read`, metadata only.
   - `view_image(image_id, mode='visual'|'description')` — `read`. Uses `context.blob.get(...)` for `visual`. Result includes base64 payload + media_type.
   - `send_image(image_id, caption?)` — `write`. Resident: appends to `context.external_queue` (mirrors `send_message`); the queued callable posts to Discord and on success calls `store.update_message(message_row_id, discord_message_id=<...>)`. Invocation: appends to envelope `events` array.
   - `update_image_metadata(image_id, caption?, description?, reference_key?)` — `write`. Validates reference_key regex `^[a-z][a-z0-9_]{0,63}$`.
2. **Auto-import** in `agent_kit/loop.py` beside `import agent_kit.tools.communication`.

### Step 18: Wire `view_image` bytes through to Anthropic (`agent_kit/loop.py`)
**Scope:** Small
1. **Detect** in the loop's tool-result message construction (`agent_kit/loop.py:237`) when `result.get("media_type")` and `result.get("image_bytes_b64")` are present and emit Anthropic vision content blocks.

### Step 19: Resident CLI entry point (`arnold/cli.py`)
**Scope:** Small
1. **Replace** `_unsupported_store_envelope` (`arnold/cli.py:65`) with `SupabaseStore` construction from env (`SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`).
2. **Add** an `arnold resident` subcommand constructing `SupabaseStore`, `SupabaseStorageBlob`, `Ledger`, `DiscordTransport`, `AnthropicModel`, `Reconciler`, `ResidentRunner` and runs the asyncio loop until SIGINT.

---

## Phase 5: Tests and verification

### Step 20: Unit and contract tests (`tests/`)
**Scope:** Medium
1. **`tests/store_contract.py`** — UNCHANGED.
2. **`tests/store_contract_v1b.py`** — exercises `find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `load_messages`, `update_message` (NEW), `create_message(synthesize_outbound_id=False)` (NEW), image CRUD, idempotency-key uniqueness, `request_body` round-trip.
3. **`tests/test_supabase_store.py`** — runs both `run_store_contract` and `run_store_contract_v1b`. Skip via `pytest.importorskip("psycopg")` and env-var check on `SUPABASE_TEST_DB_URL`.
4. **`tests/test_sqlite_store.py`** — extend to also call `run_store_contract_v1b`.
5. **`tests/test_create_message_synthesize_flag.py`** — `synthesize_outbound_id=True` (default) preserves Sprint 1a `inv_<turn_id>_<N>` behavior; `synthesize_outbound_id=False` leaves `discord_message_id=NULL`. Closes correctness / callers.
6. **`tests/test_update_message.py`** — partial updates fill `discord_message_id`, `content`, `audio_storage_url`, `transcription_metadata`, `has_image_attachment`; row identity unchanged.
7. **`tests/test_coalescer.py`** — virtual-time tests.
8. **`tests/test_whitelist.py`** — whitelist filter writes log row, no reply.
9. **`tests/test_status_formatter.py`** — golden-string match.
10. **`tests/test_reconciler.py`** — Anthropic replay (verifies `messages`/`tools` come from `request_body`); Discord post-hoc lookup confirmed/orphaned; Storage HEAD-confirm; Groq deterministic re-issue.
11. **`tests/test_image_tools.py`** — list/view/update + send_image invocation + resident queued callback.
12. **`tests/test_run_turn_hooks.py`** — `on_turn_start` fires after `create_turn`; `mid_turn_message_check` returning new messages causes a re-prompt; same check fires before EXPLICIT `send_message`; existing invocation-mode behavior unchanged.
13. **`tests/test_tool_kit_external_queue.py`** — (a) tool body mutation rolled back when tool raises (preserves `tests/test_tool_kit.py:27`); (b) ledger pending row exists at commit time; (c) external callable runs AFTER commit; (d) ledger row marked `confirmed`/`failed` after callable returns/raises.
14. **`tests/test_discord_ingestion_persist_first.py`** (NEW) — voice ingestion: `messages` row exists with `was_voice_message=True` and `content=""` BEFORE Storage upload runs; both pending ledger rows exist at that point. Then after Storage+Groq complete, the row is updated with `content=<transcription>` and `audio_storage_url`. Image ingestion: `messages` row with `has_image_attachment=True` AND ledger pending exist before Storage upload; `images` row created only after upload succeeds. Closes FLAG-013 / issue_hints / scope.
15. **`tests/test_discord_ingestion_ledger.py`** — voice ingestion records two pending rows pending→confirmed; image ingestion records one row pending→confirmed; failure path marks failed and the `messages` row is still persisted.

### Step 21: Integration tests (`tests/`)
**Scope:** Medium
1. **`tests/test_resident_recovery.py`** — `ResidentRunner` over in-memory `SQLiteStore` + `FakeDiscordTransport`; cancel a turn mid-tool-call; on next `Reconciler.run_once`, prior turn `abandoned`, fresh turn fires with same triggers.
2. **`tests/test_voice_pipeline.py`** — voice attachment delivered; verify message row exists immediately with `was_voice_message=True`; mocked Groq returns transcription; `update_message` fills transcription; both ledger rows confirmed.
3. **`tests/test_image_attachment_pipeline.py`** — image attachment → `messages` row with `has_image_attachment=True` immediately, then `images` row `source='user_uploaded'`, `reference_key='img_user_upload_1'` after upload; ingestion ledger row confirmed.
4. **`tests/test_status_lifecycle.py`** — 3 tool calls produces: 1 initial post + ≤3 edits + 1 final `✅ Done. 3 tool calls.`; throttling: 20 tool calls in 2s → ≤4 edits.
5. **`tests/test_mid_turn_messages.py`** — second message arrives mid-tool-call; status gets `📥 Received…`; widened `triggered_by_message_ids` AND synthesized mid-turn user message in next prompt. Variant: explicit-`send_message` mid-turn → still gated.
6. **`tests/test_send_message_resident.py`** — resident `send_message` posts via `FakeDiscordTransport.post_message`; asserts row created with `discord_message_id=NULL` inside the audit transaction (via `synthesize_outbound_id=False`); `update_message` fills `discord_message_id` AFTER commit (`store.transaction_depth == 0` when callable runs); ledger pending→confirmed.
7. **`tests/test_anthropic_replay.py`** — pending Anthropic row → reconciler reissues with stored `request_body` and `idempotency_key`; row confirmed.
8. **`tests/test_duplicate_inbound_dropped.py`** — re-deliver the same Discord message to `on_message` → first call inserts, second raises on the unique constraint and is logged (no double-Storage upload, no double-Groq call). Verifies the persist-first design's anti-duplicate property.

### Step 22: Final verification and deferral note
**Scope:** Small
1. **Run** `pytest` — full suite green; existing Sprint 1a tests pass UNCHANGED.
2. **Append** a deferral note (TODO comment in `agent_kit/loop.py` near the `input` parameter, OR `ideas/sprint_1c_attachments.md`) capturing: invocation-mode `--attach` / `run_turn(attachments=)` / `LocalBlobStore` (`planning-bot-spec.md:1895-1908`) AND `transcribe_voice` tool / non-voice-audio path (`planning-bot-spec.md:2634`).
3. **Manual smoke** (info, not pipeline-checked): `arnold resident` against staging — whitelisted DM responds within 30s; voice DM transcribes; image attachment lands in Storage with `images` row; mid-turn DM updates the status message in the same turn.

## Execution Order

1. **Phase 1** — deps, secrets, migrations.
2. **Phase 2** — interface changes (model `idempotency_key`, ledger `request_body`, `run_turn` hooks + send_message gating, `ToolContext` extension, audit wrapper external queue, `Store.update_message`, `create_message(synthesize_outbound_id)`).
3. **Phase 3** — Supabase store, Storage blob, Discord transport (persist-first ingestion), resident runner, reconciler.
4. **Phase 4** — image tools, Anthropic vision wiring, resident CLI subcommand.
5. **Phase 5** — tests interleave per phase; integration tests in Step 21 land last.

## Validation Order

1. Existing Sprint 1a tests (must still pass unmodified).
2. New unit tests (Step 20): hooks, external queue, `update_message`, `create_message` flag, coalescer, whitelist, status formatter, reconciler, image tools, persist-first ingestion, ledger.
3. Sprint 1b contract test against both stores.
4. Resident integration tests (Step 21): recovery, voice, image, status lifecycle, mid-turn (final-text + explicit-send_message), resident `send_message`, Anthropic replay, duplicate-inbound rejection.
5. Manual smoke against staging — last, info-priority.
