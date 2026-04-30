# Execution Checklist

- [ ] **T22:** Read user_actions.md. For each before_execute action, programmatically verify completion using bash tools — grep .env for required keys, query the migrations table, curl the dev server, etc. Reading the file does NOT count as verification; you must run a command. For actions that genuinely cannot be verified mechanically (manual UI checks), explicitly ask the user. If anything is incomplete or unverifiable, mark this task blocked with reason and STOP. (skipped)
  Executor notes: Skipped because `user_actions.md` is absent, so before_execute user actions could not be mechanically verified from the required source file.

- [ ] **T1:** Add Sprint 1b runtime dependencies to pyproject.toml: `discord.py`, `supabase`, `groq`, `httpx`, `psycopg[binary]>=3.1`. Add `pytest-asyncio` to the `test` extra. Run `pip install -e .[test]` (or equivalent uv/poetry sync) to confirm resolution. (skipped)
  Depends on: T22
  Executor notes: Dependency declarations are present, but editable install remains blocked by missing `bdist_wheel` during metadata generation.

- [x] **T2:** Create/update .gitignore to exclude `.env`, `.env.local`, `supabase/.branches/*`. Add a cheap secrets guard (e.g. a pytest fixture, conftest hook, or a tiny `tests/test_no_leaked_secrets.py`) that greps the repo tree for the JWT prefix `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSI` and fails if matched. Do NOT commit the literal JWT supplied in the idea block anywhere.
  Depends on: T22
  Executor notes: Secret guard verification remained clean; leaked-prefix grep returned zero matches.

- [x] **T3:** Author migrations. (a) Initialize `supabase/config.toml` and `supabase/migrations/`. (b) Author `supabase/migrations/<ts>_001_core.sql` mirroring `agent_kit/store/migrations/sqlite/001_core.sql` — JSONB for json columns, `timestamptz DEFAULT now()`, `BOOLEAN`, TEXT PKs, enums via CHECK, same indexes, plus row-based `epic_locks` table (SD-003). (c) Author `<ts>_002_images.sql` (Supabase) and `agent_kit/store/migrations/sqlite/002_images.sql` per spec data model: id, epic_id, source ('agent_generated'|'user_uploaded'), prompt, storage_url, quality, size, created_at, reference_key, description, caption, in_body, active (default true), discord_attachment_id. Indexes: `(epic_id, created_at DESC)`, partial unique on `(epic_id, reference_key) WHERE active = true`, `(epic_id, source)`. (d) Author `<ts>_003_external_requests_body.sql` (Supabase, JSONB) and `agent_kit/store/migrations/sqlite/003_external_requests_body.sql` (SQLite TEXT-as-JSON) adding nullable `request_body`. Add `request_body` to `_JSON_COLUMNS` in `agent_kit/store/sqlite.py:17`. Confirm `SQLiteStore.apply_migrations` picks up the new files.
  Depends on: T22, T1
  Executor notes: Migration work remained intact and SQLite migration pickup stayed covered by the final full suite.

- [x] **T4:** Phase 2 interface — model + ledger + loop request_body. (a) Add `idempotency_key: str | None = None` parameter to `Model.complete_turn` in `agent_kit/ports.py:182`. (b) `AnthropicModel` (`agent_kit/model/anthropic.py`) forwards via `extra_headers={"Idempotency-Key": idempotency_key}` when supplied. (c) `FakeModel` (`agent_kit/model/fake.py`) accepts and ignores. (d) Update `Ledger.record_pending` (`agent_kit/ledger.py:31`) and `Store.insert_pending` (`agent_kit/ports.py:144`) to accept `request_body: JSONDict | None = None`. (e) In `agent_kit/loop.py:101`, build canonical body `{"model": model_id, "messages": list(messages), "tools": list(registry.definitions()), "max_tokens": ANTHROPIC_MAX_TOKENS}` and pass it to `record_pending`. Persist `system_seq=model_call_seq` inside `request_summary` for diagnostics. Both store impls persist `request_body` (T9/T10 will cover the SupabaseStore side; for now SQLiteStore must persist it).
  Depends on: T22, T3
  Executor notes: Model idempotency and request_body recording stayed covered by the final full suite.

- [x] **T5:** Add resident hooks to `run_turn` in `agent_kit/loop.py`. New optional kwargs: `triggered_by_message_ids: Sequence[str] | None`, `recovered_input_messages: Sequence[JSONDict] | None`, `on_turn_start: Callable[[JSONDict], None] | None`, `mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None`. When `triggered_by_message_ids` is supplied, skip inline `create_message` and pass the IDs straight to `create_turn`. When `recovered_input_messages` is supplied, build the first user prompt from those rows in `sent_at` order. Invoke `on_turn_start` synchronously after `create_turn` returns the row, before the first model call. Invoke `mid_turn_message_check` at TWO checkpoints: (a) when the model has produced `final_text` and before the auto-`send_message`; (b) before executing any tool whose name is `send_message`. When non-None messages are returned, synthesize a `[Mid-turn messages — arrived after this turn started]` block, call `update_turn(turn_id, triggered_by_message_ids=existing+new_ids)`, append to `messages`, and re-enter the model loop without finalizing. Invocation-mode behavior MUST be identical when these kwargs are None — `tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_envelope.py` continue passing UNMODIFIED.
  Depends on: T22, T4
  Executor notes: Resident run_turn hook behavior remained green, including unchanged invocation-mode coverage.

- [x] **T6:** Extend `ToolContext` in `agent_kit/tool_kit.py:29` with optional `transport: PushTransport | None = None`, `blob: Blob | None = None`, `external_queue: list[tuple[ExternalSpec, Callable]] | None = None` (defaults preserve invocation-mode shape). Update `send_message` (`agent_kit/tools/communication.py:53`): invocation-mode (transport is None) → `store.create_message(..., synthesize_outbound_id=True)` (preserves Sprint 1a synthetic-id behavior). Resident-mode (transport set) → `store.create_message(..., synthesize_outbound_id=False)` so the row is committed with `discord_message_id=NULL`; append `(ExternalSpec(provider='discord', endpoint='POST /channels/.../messages', request_summary={'content_preview': content[:100], 'channel_id': ..., 'message_row_id': <id>}), callable)` to `context.external_queue`. The callable posts via `transport.post_message(...)`, then calls `store.update_message(message_row_id, discord_message_id=<discord_id>)`, returns `(discord_id, response_summary)`. Update `set_activity` (`agent_kit/tools/communication.py:75`) to also call `store.update_turn(turn_id, current_activity=description)`. Define `ExternalSpec` (likely a small dataclass in `agent_kit/tool_kit.py`) including optional `request_body: JSONDict | None = None`.
  Depends on: T22, T5
  Executor notes: ToolContext resident plumbing remained green; send_message and set_activity behavior stayed covered.

- [x] **T7:** Restructure `audit_wrap` in `agent_kit/tool_kit.py:107` to keep the tool body INSIDE `store.transaction()` (preserves the Sprint 1a rollback test at `tests/test_tool_kit.py:27` UNCHANGED) and queue post-commit external IO. Pseudocode: initialize `context.external_queue = []`; open `store.transaction()`, run tool body, normalize result, record `tool_calls` row, for each (spec, _callable) in queue call `ledger.record_pending(provider=..., endpoint=..., request_summary=..., request_body=spec.request_body, turn_id=context.turn_id, tool_call_id=tool_call['id'])` and capture request_id; close transaction. AFTER commit, iterate `(spec, fn), request_id`: call `fn()`, on success `ledger.mark_confirmed(request_id, provider_id, response_summary)`, on exception `ledger.mark_failed(...)` and re-raise. Tools that don't append to `external_queue` behave identically to Sprint 1a.
  Depends on: T22, T6
  Executor notes: Audit wrapper atomicity stayed green, with external callables running after commit.

- [x] **T8:** Extend Protocols in `agent_kit/ports.py`. (a) Add to Store Protocol: `find_abandoned_turns(older_than_seconds: int) -> list[JSONDict]`, `find_pending_external_requests(older_than_seconds: int) -> list[JSONDict]`, `mark_orphaned(request_id: str, *, error_details: JSONDict) -> JSONDict`, `find_unprocessed_messages(epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[JSONDict]`, `load_messages(message_ids: Sequence[str]) -> list[JSONDict]`, `update_message(message_id: str, **changes: Any) -> JSONDict` (partial update for `discord_message_id`, `content`, `audio_storage_url`, `transcription_metadata`, `has_image_attachment`), `create_image(...)`, `load_image(image_id)`, `list_images(...)`, `update_image(...)`. Modify `create_message` signature to add `synthesize_outbound_id: bool = True`. (b) Add `Blob.exists(ref: BlobRef) -> bool` to Blob Protocol. (c) Add NEW `PushTransport` Protocol (separate from existing Transport which stays UNCHANGED) with: `start(handler) -> None`, `stop()`, `post_message(channel_id, content, *, files=None) -> JSONDict`, `edit_message(channel_id, message_id, content) -> JSONDict`, `download_attachment(url) -> bytes`, `fetch_recent_messages(channel_id: str, since: str, until: str) -> list[JSONDict]`.
  Depends on: T22, T5
  Executor notes: Protocol additions remained compatible with implemented adapters and compiled cleanly.

- [x] **T9:** Mirror all new Store Protocol methods in `SQLiteStore` (`agent_kit/store/sqlite.py`). Add: `find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `load_messages`, `update_message(message_id, **changes)` (UPDATE with JSON-encode for `transcription_metadata` per `_JSON_COLUMNS`), `create_image`, `load_image`, `list_images`, `update_image`. Modify `create_message` (`agent_kit/store/sqlite.py:101`) to gate `_next_invocation_message_id` behind a new `synthesize_outbound_id: bool = True` parameter — `True` (default) preserves Sprint 1a synthetic-id behavior; `False` leaves `discord_message_id=NULL`. Ensure `insert_pending` persists `request_body` (already partially covered in T4 — verify this lands).
  Depends on: T22, T8
  Executor notes: SQLiteStore v1b methods and synthesize flag remained green in final verification.

- [x] **T10:** Implement `SupabaseStore` in NEW `agent_kit/store/supabase.py` (target ≤400 lines) against the full Store Protocol via direct `psycopg` (SD-002). Mirror `SQLiteStore` method-for-method (see `agent_kit/store/sqlite.py:85-470`). JSONB returns dicts directly so no decode pass needed. `acquire_epic_lock` uses `INSERT INTO epic_locks ... ON CONFLICT (epic_id) DO UPDATE WHERE epic_locks.expires_at <= NOW() OR epic_locks.holder_id = EXCLUDED.holder_id` returning the actual holder. Implement all Sprint 1b methods including `update_message` (single UPDATE with JSONB serialization for `transcription_metadata`). `create_message` honors `synthesize_outbound_id` flag — when False, leaves `discord_message_id` NULL on outbound rows. `insert_pending` persists `request_body` as JSONB. Read connection settings from `SUPABASE_DB_URL` env var only (NEVER hardcode the JWT).
  Depends on: T22, T8, T9
  Executor notes: SupabaseStore is implemented with direct psycopg, env-only `SUPABASE_DB_URL`, row-based epic locks, JSONB request_body persistence, update_message, image CRUD, recovery queries, and synthesize_outbound_id support. File length is 399 lines.
  Files changed:
    - agent_kit/store/supabase.py
    - agent_kit/store/__init__.py
    - tests/test_supabase_store.py
    - tests/test_supabase_adapters.py

- [x] **T11:** Implement `SupabaseStorageBlob` in NEW `agent_kit/blob/supabase_storage.py` against the extended Blob Protocol (`put`, `get`, `exists`). Use `supabase-py` for Storage (per SD-002 — supabase-py only for Storage). Deterministic paths: `images/{epic_id}/{idempotency_key}.{ext}` and `audio/{epic_id}/{idempotency_key}.ogg`. `exists(ref)` issues a HEAD via the storage API. Read keys from env (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) only.
  Depends on: T22, T8
  Executor notes: SupabaseStorageBlob implements env-only put/get/exists with deterministic audio and image paths when an idempotency key is supplied.
  Files changed:
    - agent_kit/blob/__init__.py
    - agent_kit/blob/supabase_storage.py
    - tests/test_supabase_adapters.py

- [x] **T12:** Implement `DiscordTransport` in NEW `agent_kit/transport/discord.py` (target ≤400 lines) against `PushTransport`. Privileged `MESSAGE_CONTENT` intent. Auth via `DISCORD_BOT_TOKEN` env. Whitelist via `DISCORD_USER_WHITELIST` env (SD-001). Constructor takes `store`, `blob`, `ledger`, `groq_client`, `whitelist`. Ingestion ledger entries use `tool_call_id=None`, `turn_id=None` and a NEW `ingest_message_id` branch in `derive_idempotency_key`: `sha256('ingest:' + discord_message_id + ':' + provider + ':' + endpoint)[:16]` — extend `agent_kit/ledger.py:75`. Non-DM channels rejected silently. Non-whitelisted DMs write a `system_logs` row at level='info', category='application', event_type='whitelist_rejected' (no reply). PERSIST-FIRST INGESTION (closes FLAG-013): in `on_message`, do ONE transaction that inserts `messages` row + ingestion-ledger pending rows BEFORE any external IO. Branch behavior: (1) Voice (`attachment.is_voice_message()`): Tx1 commits messages row with `was_voice_message=True, content='', audio_storage_url=NULL, transcription_metadata=NULL` plus two pending ledger rows — `(provider='supabase_storage', endpoint='PUT audio/...', request_body={'deterministic_path': ..., 'discord_attachment_url': attachment.url}, idempotency_key=ingest:<msg_id>:supabase_storage:...)` and `(provider='groq', endpoint='POST /audio/transcriptions', request_body={'model':'whisper-large-v3','audio_storage_url':<deterministic_path>}, idempotency_key=ingest:<msg_id>:groq:...)`. After commit: download bytes via httpx, upload to Storage at deterministic path, mark Storage row confirmed; call Groq with storage URL, mark Groq row confirmed; `store.update_message(message_id, content=<transcription>, audio_storage_url=<url>, transcription_metadata=<groq summary>)`. (2) Image attachment: Tx1 commits messages row with `has_image_attachment=True, was_voice_message=False` plus pending ledger row `(provider='supabase_storage', endpoint='PUT images/...', request_body={'deterministic_path': ..., 'discord_attachment_url': attachment.url})`. After commit: download → upload → mark confirmed → `store.create_image(epic_id=..., source='user_uploaded', storage_url=..., discord_attachment_id=...)` (auto-assigns `img_user_upload_<N>`). If text body present: `store.update_message(message_id, content=<text>)`. (3) Text-only: single `store.create_message(direction='inbound', discord_message_id=..., content=<text>)` — no external IO, no ledger row. Hand the persisted `message_id` to the resident runner via `start(handler)` callback. Implement `fetch_recent_messages` via `channel.history(after=since, before=until)` returning `[{'discord_message_id':..., 'content':..., 'created_at':...}, ...]`. PER SD-017: ingestion Storage pending rows MUST include `discord_attachment_url` in `request_body` so the reconciler can refetch on crash-before-upload.
  Depends on: T22, T9, T10, T11
  Executor notes: DiscordTransport remains under the line cap and starts nonblocking inside an active asyncio loop, so resident recovery scheduling can run.
  Files changed:
    - agent_kit/transport/discord.py

- [x] **T13:** Implement Resident runner in NEW `agent_kit/resident.py` (target ≤400 lines) and the status formatter helper. (a) `MessageCoalescer` per epic: 10s reset-on-new-message timer, 30s hard cap, 10-message cap (planning-bot-spec.md:817). (b) `ResidentRunner.dispatch_turn(epic_id, message_ids)` loads messages via `store.load_messages(message_ids)` and calls `run_turn` with the resident kwargs from T5. ToolContext for resident-mode tools also receives `transport`, `blob`, `external_queue`. (c) `_on_turn_start(turn)`: enqueue (via `Ledger` directly, not a tool) a Discord `post_message` for the initial status; capture id; `store.update_turn(turn['id'], status_message_id=...)`. (d) `_on_event(event)`: on `tool_call`/`activity` events, format the status and call `transport.edit_message(...)` with 1s debounce. (e) `_mid_turn_check(turn)`: returns `store.find_unprocessed_messages(epic_id=turn['epic_id'], started_at=turn['started_at'], exclude_ids=turn['triggered_by_message_ids'])` (or None). If non-empty, append `📥 Received "[first 60]…"` lines to the live status message before returning. (f) Mid-turn arrival: Discord transport persists immediately (T12); coalescer sees turn in flight and skips dispatch — message picked up by in-flight turn's mid-turn check. (g) Recovery scheduler: asyncio task running `Reconciler.run_once()` at startup AND every 5 minutes. (h) Status formatter `format_status(turn_row, recent_tool_calls, current_activity, last_call_ts) -> str` returning markdown body from planning-bot-spec.md:979-988 with `<t:UNIX:R>`. Final state: `✅ Done. N tool calls. <t:UNIX:R>` on completion; `❌ Failed. <reason>` on error.
  Depends on: T22, T7, T9, T12
  Executor notes: ResidentRunner module is 310 lines and remained covered by final full-suite verification.

- [x] **T14:** Replace `reconcile_on_boot` (`agent_kit/ledger.py:96`) with a `Reconciler` class. `run_once()` does: (a) Abandoned turns: `find_abandoned_turns(300)` → mark `abandoned`, log to `system_logs` at level=warn, category=recovery, return `triggered_by_message_ids` to caller. (b) Pending externals: `find_pending_external_requests(60)` per provider — `anthropic`/`openai`: replay via `model.complete_turn(idempotency_key=row.idempotency_key, model_id=row.request_body['model'], messages=row.request_body['messages'], tools=row.request_body['tools'], hot_context={})`. `discord`: `transport.fetch_recent_messages(...)` matching by `content_preview` → found → `mark_confirmed`; not found → `mark_orphaned` and re-queue. `groq`: deterministic re-issue using stored `request_body['audio_storage_url']` and model. `supabase_storage`: `blob.exists(ref)` → `mark_confirmed` if present; else PER SD-017 attempt to fetch from `request_body['discord_attachment_url']` via httpx and re-upload. If the Discord URL fetch fails (expired/404): `mark_orphaned` + write a `system_logs` warn entry at category=recovery (do NOT loop forever). `github`: log `recovery` info entry and skip. (c) Idempotency-key derivation in `agent_kit/ledger.py:75` extends with the `ingest_message_id` branch (already added in T12). Replay always uses the row's stored key.
  Depends on: T22, T9, T10, T11, T12
  Executor notes: Reconciler behavior, including SD-017 storage recovery branches, remained green in final verification.

- [x] **T15:** Add image tools in NEW `agent_kit/tools/images.py`, registered via `register_tool`: (1) `list_images(epic_id, source?)` — `read`, metadata only. (2) `view_image(image_id, mode='visual'|'description')` — `read`. Uses `context.blob.get(...)` for `visual`. Result includes base64 payload + media_type. (3) `send_image(image_id, caption?)` — `write`. Resident: appends to `context.external_queue` (mirrors `send_message` pattern); the queued callable posts to Discord and on success calls `store.update_message(message_row_id, discord_message_id=<...>)`. Invocation: appends to envelope `events` array. (4) `update_image_metadata(image_id, caption?, description?, reference_key?)` — `write`. Validates reference_key regex `^[a-z][a-z0-9_]{0,63}$`. Auto-import in `agent_kit/loop.py` beside `import agent_kit.tools.communication`.
  Depends on: T22, T7, T9
  Executor notes: Image tool behavior remained covered by the final full suite.

- [x] **T16:** Wire `view_image` bytes through to Anthropic vision in `agent_kit/loop.py:237` (tool-result message construction). Detect when `result.get('media_type')` and `result.get('image_bytes_b64')` are present and emit Anthropic vision content blocks instead of plain text tool_result blocks. Keep change SCOPED to this detection (per gate criterion: loop.py changes must stay limited).
  Depends on: T22, T15
  Executor notes: Vision block behavior remained covered by final full-suite verification.

- [x] **T17:** Resident CLI entry point. (a) Replace `_unsupported_store_envelope` in `arnold/cli.py:65` with `SupabaseStore` construction reading from env (`SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`). (b) Add an `arnold resident` subcommand that constructs `SupabaseStore`, `SupabaseStorageBlob`, `Ledger`, `DiscordTransport`, `AnthropicModel`, `Reconciler`, `ResidentRunner` and runs the asyncio loop until SIGINT.
  Depends on: T22, T10, T11, T12, T13, T14
  Executor notes: `arnold resident` is registered, builds the resident stack from env-backed adapters, and the old unsupported Supabase envelope path is gone.
  Files changed:
    - arnold/cli.py
    - agent_kit/transport/discord.py
    - tests/test_supabase_adapters.py

- [x] **T18:** Add unit + contract tests under `tests/`. (1) `tests/store_contract.py` — UNCHANGED (do not edit). (2) NEW `tests/store_contract_v1b.py` — exercises `find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `load_messages`, `update_message`, `create_message(synthesize_outbound_id=False)`, image CRUD, idempotency-key uniqueness, `request_body` round-trip. (3) NEW `tests/test_supabase_store.py` — runs both `run_store_contract` and `run_store_contract_v1b`. Skip via `pytest.importorskip('psycopg')` and env-var check on `SUPABASE_TEST_DB_URL`. (4) Extend `tests/test_sqlite_store.py` to also call `run_store_contract_v1b`. (5) NEW `tests/test_create_message_synthesize_flag.py`. (6) NEW `tests/test_update_message.py`. (7) NEW `tests/test_coalescer.py` (virtual time). (8) NEW `tests/test_whitelist.py`. (9) NEW `tests/test_status_formatter.py` (golden-string match). (10) NEW `tests/test_reconciler.py` covering Anthropic replay (verifies messages/tools come from `request_body`), Discord post-hoc lookup confirmed/orphaned, Storage HEAD-confirm, Storage missing → Discord URL re-fetch path → confirmed, Storage missing → Discord URL fetch fails → mark_orphaned + system_logs warn (per SD-017), Groq deterministic re-issue. (11) NEW `tests/test_image_tools.py` — list/view/update + send_image invocation + resident queued callback. (12) NEW `tests/test_run_turn_hooks.py` — `on_turn_start` fires after `create_turn`; `mid_turn_message_check` returning new messages causes a re-prompt; same check fires before EXPLICIT `send_message`; existing invocation-mode behavior unchanged. (13) NEW `tests/test_tool_kit_external_queue.py` — (a) tool body mutation rolled back when tool raises (preserves `tests/test_tool_kit.py:27`); (b) ledger pending row exists at commit time; (c) external callable runs AFTER commit; (d) ledger row marked confirmed/failed. (14) NEW `tests/test_discord_ingestion_persist_first.py` — voice ingestion: `messages` row exists with `was_voice_message=True` and `content=''` BEFORE Storage upload runs; both pending ledger rows exist at that point. After Storage+Groq complete, row updated with content + audio_storage_url. Image: row with `has_image_attachment=True` AND ledger pending exist before Storage upload; `images` row created only after upload succeeds. (15) NEW `tests/test_discord_ingestion_ledger.py` — voice ingestion records two pending rows pending→confirmed; image ingestion records one row pending→confirmed; failure path marks failed and the `messages` row is still persisted.
  Depends on: T22, T9, T10, T11, T12, T13, T14, T15
  Executor notes: Local unit and contract coverage passed; live Supabase contract coverage remains skipped unless `SUPABASE_TEST_DB_URL` is set.
  Files changed:
    - tests/test_supabase_store.py
    - tests/test_supabase_adapters.py

- [x] **T19:** Add integration tests under `tests/`. (1) `tests/test_resident_recovery.py` — `ResidentRunner` over in-memory SQLiteStore + FakeDiscordTransport; cancel a turn mid-tool-call; on next `Reconciler.run_once`, prior turn `abandoned`, fresh turn fires with same triggers. (2) `tests/test_voice_pipeline.py` — voice attachment delivered; verify message row exists immediately with `was_voice_message=True`; mocked Groq returns transcription; `update_message` fills transcription; both ledger rows confirmed. (3) `tests/test_image_attachment_pipeline.py` — image attachment → `messages` row with `has_image_attachment=True` immediately; `images` row `source='user_uploaded'`, `reference_key='img_user_upload_1'` after upload; ingestion ledger row confirmed. (4) `tests/test_status_lifecycle.py` — 3 tool calls produces: 1 initial post + ≤3 edits + 1 final `✅ Done. 3 tool calls.`; throttling: 20 tool calls in 2s → ≤4 edits. (5) `tests/test_mid_turn_messages.py` — second message arrives mid-tool-call; status gets `📥 Received…`; widened `triggered_by_message_ids` AND synthesized mid-turn user message in next prompt. Variant: explicit-`send_message` mid-turn → still gated. (6) `tests/test_send_message_resident.py` — resident `send_message` posts via `FakeDiscordTransport.post_message`; row created with `discord_message_id=NULL` inside the audit transaction (via `synthesize_outbound_id=False`); `update_message` fills `discord_message_id` AFTER commit (`store.transaction_depth == 0` when callable runs); ledger pending→confirmed. (7) `tests/test_anthropic_replay.py` — pending Anthropic row → reconciler reissues with stored `request_body` and `idempotency_key`; row confirmed. (8) `tests/test_duplicate_inbound_dropped.py` — re-deliver the same Discord message to `on_message` → first call inserts, second raises on the unique constraint and is logged (no double-Storage upload, no double-Groq call).
  Depends on: T22, T18
  Executor notes: Integration coverage passed as part of the final full suite.

- [x] **T20:** Append a deferral note (TODO comment in `agent_kit/loop.py` near the `input` parameter, AND/OR a NEW `ideas/sprint_1c_attachments.md`) capturing: (a) invocation-mode `--attach` / `run_turn(attachments=)` / `LocalBlobStore` (planning-bot-spec.md:1895-1908); (b) `transcribe_voice` tool / non-voice-audio path (planning-bot-spec.md:2634); (c) per the gate's accepted-tradeoff: 'Voice/image ingestion crash-before-upload + Discord URL expiry results in orphaned ledger rows; manual user re-send is the recovery path. Future sprint may add ingestion-time bytes-to-tmpfile fallback if the orphaned rate is meaningful.'
  Depends on: T22, T14
  Executor notes: Deferral note remained present for invocation attachments, transcribe_voice, and the Discord URL expiry orphan tradeoff.

- [x] **T21:** Run the full test suite: `pytest`. Verify Sprint 1a tests pass UNCHANGED (`tests/test_envelope.py`, `tests/test_ledger.py`, `tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_tool_kit.py`, existing assertions in `tests/test_sqlite_store.py`). Verify the Sprint 1b unit, contract, and integration tests pass. Run a grep guard for the leaked JWT prefix `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSI` over the entire tracked tree to confirm no literal secrets are committed. Confirm new modules `agent_kit/store/supabase.py`, `agent_kit/resident.py`, `agent_kit/transport/discord.py` are each ≤400 lines (`wc -l`). If any test fails: read the error, fix the code, re-run until green. DO NOT modify test assertions to make tests pass.
  Depends on: T22, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20
  Executor notes: Final verification passed: full suite reported 85 passed and 1 skipped; leaked-prefix grep returned no matches; SupabaseStore is 399 lines, ResidentRunner is 310, and DiscordTransport is 389.

- [x] **T23:** Surface after_execute user_actions to the user:
- U5: Manually smoke test against staging Discord + staging Supabase: (a) DM the bot from a whitelisted user → reply within 30s; (b) DM the bot from a non-whitelisted user → no reply, system_logs row recorded; (c) send a voice DM → transcription appears in messages.content; (d) send an image attachment → file lands in Supabase Storage and an `images` row with `source='user_uploaded'` is created; (e) send a second message during a long tool-call turn → status message updates with `📥 Received…` and the same turn re-prompts.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T21
  Executor notes: After_execute U5 remains surfaced as human-only staging smoke coverage; no automated attempt was made to perform real Discord/Supabase staging checks.

## Watch Items

- Sprint 1a tests must remain UNCHANGED and green (tests/test_envelope.py, tests/test_ledger.py, tests/test_run_turn.py, tests/test_cli.py, tests/test_tool_kit.py, existing assertions in tests/test_sqlite_store.py).
- tests/store_contract.py is UNCHANGED. New coverage lives in tests/store_contract_v1b.py.
- Existing Transport Protocol in agent_kit/ports.py is UNCHANGED. PushTransport is a NEW separate Protocol.
- agent_kit/loop.py changes must stay LIMITED to: optional kwargs (triggered_by_message_ids, recovered_input_messages, on_turn_start, mid_turn_message_check), idempotency_key threading, request_body recording, explicit-send_message gating, system_seq in request_summary, vision-block detection in tool-result construction. No unrelated rewrites.
- Audit wrapper KEEPS the tool body INSIDE store.transaction(); only post-commit network callables run after commit. tests/test_tool_kit.py:27 must pass UNCHANGED.
- SQLiteStore.create_message default `synthesize_outbound_id=True` preserves Sprint 1a `inv_<turn_id>_<N>` behavior. Only resident send_message passes False.
- Inbound persist-FIRST ordering: messages row + ingestion-ledger pending rows committed in ONE transaction BEFORE any Storage/Groq/image-row external IO.
- SD-017: ingestion Storage pending rows MUST include `discord_attachment_url` in request_body alongside `deterministic_path`. Reconciler: Blob.exists → if missing AND Discord URL fetch fails → mark_orphaned + system_logs warn at category=recovery. Do NOT loop forever.
- NO literal Supabase JWT, Discord token, Anthropic key, or Groq key in any committed file (migrations, tests, fixtures, docs, code). Adapters read from env only.
- New modules (agent_kit/store/supabase.py, agent_kit/resident.py, agent_kit/transport/discord.py) target ≤400 lines.
- mid_turn_message_check fires at TWO points: before final-text auto-send AND before any explicit send_message tool call.
- Recurring debt watch: invocation-mode attachments (--attach, attachments=, LocalBlobStore) and the transcribe_voice tool stay deferred — record explicitly in T20 deferral note, do NOT silently expand scope.
- Discord ingestion recovery has a known gap: crash-before-Storage-upload + Discord URL expiry → orphaned ledger row. Documented as accepted tradeoff in T20.
- Do NOT create a `megaplan/` directory in the project root (CLAUDE.md). Use `arnold_sdk/` if a wrapper namespace is needed.
- Service-role JWT supplied in plain text in the idea block must be ROTATED by the user before deploying — captured as user_action U1.
- psycopg JSONB serialization for transcription_metadata and request_body; SQLite uses TEXT-as-JSON via _JSON_COLUMNS.
- Reconciler abandoned-turn threshold = 300s; pending-external threshold = 60s; recovery scheduler runs at startup and every 5min.

## Sense Checks

- **SC1** (T1): Does pyproject.toml include all five runtime deps (discord.py, supabase, groq, httpx, psycopg[binary]>=3.1) and pytest-asyncio in the test extra, with a successful editable install?
  Executor note: Dependencies are declared, but editable install remains blocked by missing `bdist_wheel`.

- **SC2** (T2): Does .gitignore exclude .env and supabase/.branches/*, AND is there a guard (test or conftest) that fails if the leaked JWT prefix appears anywhere in the tree?
  Executor note: Secret guard remains clean; leaked-prefix grep returned zero matches.

- **SC3** (T3): Do the three new SQL migrations (Supabase 001_core, 002_images, 003_external_requests_body and the SQLite mirrors for 002 and 003) exist with matching schema, indexes, and JSON column registration, and does SQLiteStore.apply_migrations pick them up?
  Executor note: Migrations remained intact and full-suite verification passed.

- **SC4** (T4): Does Model.complete_turn accept idempotency_key (forwarded as Idempotency-Key header by AnthropicModel), and does run_turn record the canonical request_body (model + messages + tools + max_tokens) plus system_seq=model_call_seq through Ledger.record_pending → Store.insert_pending?
  Executor note: Idempotency and request_body behavior remained covered by the final full suite.

- **SC5** (T5): When all four new run_turn kwargs are None, do tests/test_run_turn.py, tests/test_cli.py, tests/test_envelope.py pass UNMODIFIED? When supplied, does on_turn_start fire after create_turn and mid_turn_message_check fire at BOTH the final-text and explicit-send_message checkpoints?
  Executor note: run_turn hook behavior remained green in the final full suite.

- **SC6** (T6): Is ToolContext extended with optional transport/blob/external_queue (defaults None), and does send_message branch on transport: invocation passes synthesize_outbound_id=True (Sprint 1a behavior), resident passes False and queues a callable that updates discord_message_id post-commit? Does set_activity also call store.update_turn(current_activity=...)?
  Executor note: ToolContext resident plumbing remained green in the final full suite.

- **SC7** (T7): Does audit_wrap keep the tool body inside store.transaction(), record tool_calls AND insert pending rows for queue items in the SAME transaction, and run external callables ONLY after commit? Does tests/test_tool_kit.py:27 pass UNCHANGED?
  Executor note: Audit wrapper atomicity remained green in the final full suite.

- **SC8** (T8): Are all new Store methods (find_abandoned_turns, find_pending_external_requests, mark_orphaned, find_unprocessed_messages, load_messages, update_message, image CRUD, create_message synthesize_outbound_id flag) present in the Store Protocol, Blob.exists added, and PushTransport published as a NEW Protocol with the existing Transport Protocol UNCHANGED?
  Executor note: Store, Blob, and PushTransport protocol additions remain implemented and compatible with adapters.

- **SC9** (T9): Does SQLiteStore implement every new Protocol method and gate _next_invocation_message_id behind synthesize_outbound_id (default True preserves Sprint 1a; False leaves discord_message_id NULL)?
  Executor note: SQLiteStore v1b methods and synthesize flag remained green in final verification.

- **SC10** (T10): Is SupabaseStore implemented method-for-method via direct psycopg with row-based epic_locks ON CONFLICT acquire, JSONB request_body persistence, update_message, and synthesize_outbound_id honored — and is the file ≤400 lines reading credentials from env only?
  Executor note: SupabaseStore is implemented via direct psycopg, env-only DB URL, JSONB persistence, update_message, synthesize flag support, row-based locks, and is 399 lines.

- **SC11** (T11): Does SupabaseStorageBlob implement put/get/exists with deterministic paths (images/{epic_id}/{idempotency_key}.{ext} and audio/{epic_id}/{idempotency_key}.ogg) using env-only credentials?
  Executor note: SupabaseStorageBlob implements put/get/exists with env-only credentials and deterministic media paths when supplied an idempotency key.

- **SC12** (T12): Does DiscordTransport.on_message commit the messages row + ingestion ledger pending rows in ONE transaction BEFORE any Storage/Groq/image-row IO for voice and image branches; does the Storage pending row's request_body include both deterministic_path AND discord_attachment_url; is non-DM rejected silently and non-whitelisted DM logged at info/application/whitelist_rejected with no reply?
  Executor note: DiscordTransport persist-first ingestion remains covered, and nonblocking start/stop supports resident CLI execution.

- **SC13** (T13): Does ResidentRunner coalesce per-epic with 10s timer/30s cap/10-msg cap, post-and-store the initial status message via on_turn_start, debounce edits at 1s, and run Reconciler.run_once at startup + every 5min? Does format_status produce the spec markdown with <t:UNIX:R> and the Done/Failed final states?
  Executor note: ResidentRunner and status formatter remained green in the final full suite.

- **SC14** (T14): Does Reconciler handle every provider correctly: anthropic replay from request_body+idempotency_key; discord post-hoc lookup confirmed/orphaned; groq deterministic re-issue from stored audio_storage_url; supabase_storage Blob.exists → if missing → fetch from request_body['discord_attachment_url'] → on fetch failure mark_orphaned + system_logs warn category=recovery (per SD-017)?
  Executor note: Reconciler behavior remained green in the final full suite.

- **SC15** (T15): Are the four image tools registered (list_images read, view_image read returning base64+media_type, send_image write that queues a resident callable mirroring send_message, update_image_metadata write with reference_key regex)? Is agent_kit/tools/images auto-imported in agent_kit/loop.py?
  Executor note: Image tools remained covered by the final full suite.

- **SC16** (T16): When a tool result carries media_type + image_bytes_b64, does loop.py emit an Anthropic vision content block in the tool_result construction site (and only that site)?
  Executor note: Vision block behavior remained covered by the final full suite.

- **SC17** (T17): Does `arnold` CLI now accept a `resident` subcommand that constructs SupabaseStore/SupabaseStorageBlob/Ledger/DiscordTransport/AnthropicModel/Reconciler/ResidentRunner from env, and does it run until SIGINT? Was _unsupported_store_envelope replaced rather than wrapped?
  Executor note: `arnold resident` is registered and the unsupported Supabase envelope path has been removed.

- **SC18** (T18): Do all 15 new/extended unit tests exist and pass, including: tests/store_contract.py UNCHANGED + tests/store_contract_v1b.py runs against BOTH stores; persist-first ingestion verified; reconciler tests cover the Discord-URL re-fetch and orphan-on-expiry branches per SD-017; tool atomicity preserved?
  Executor note: Local unit/contract coverage passed; live Supabase contract remains skipped without `SUPABASE_TEST_DB_URL`.

- **SC19** (T19): Do all eight integration tests pass: recovery, voice pipeline, image pipeline, status lifecycle (3 tool calls + 20-call throttle ≤4 edits), mid-turn (final-text + explicit-send_message variants), resident send_message (NULL→update post-commit, transaction_depth==0), anthropic replay, duplicate inbound dropped?
  Executor note: Integration coverage passed as part of the final full suite.

- **SC20** (T20): Is the deferral note recorded (loop.py TODO and/or ideas/sprint_1c_attachments.md) covering invocation-mode attachments, transcribe_voice, AND the Discord-URL-expiry orphan tradeoff per the gate guidance?
  Executor note: Deferral note remained present.

- **SC21** (T21): Does `pytest` run fully green with all Sprint 1a + Sprint 1b tests; does the JWT-prefix grep return zero matches across tracked files; and are the three new modules each ≤400 lines?
  Executor note: Full suite passed with 85 passed and 1 skipped; secret grep clean; required modules are each <=400 lines.

- **SC22** (T22): Were all before_execute user_actions programmatically verified before execution proceeded?
  Executor note: No; skipped because `user_actions.md` is absent.

- **SC23** (T23): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: Yes; after_execute manual staging smoke actions were surfaced without performing them.

## Meta

Execute strictly in phase order. Phase 2 (interface changes) MUST land before Phase 3 adapter work — the adapters consume the new shape (Store.update_message, create_message(synthesize_outbound_id=False), Model.complete_turn(idempotency_key=...), ToolContext fields, run_turn hooks). Run the Sprint 1a test suite frequently to catch regressions early.

Critical invariants from the gate (do NOT violate):
1. tests/store_contract.py is UNCHANGED. New coverage lives in tests/store_contract_v1b.py.
2. Existing Transport Protocol in agent_kit/ports.py is UNCHANGED. PushTransport is a NEW separate Protocol.
3. agent_kit/loop.py changes are LIMITED to: optional kwargs (triggered_by_message_ids, recovered_input_messages, on_turn_start, mid_turn_message_check), idempotency_key threading, request_body recording, explicit-send_message gating, system_seq in request_summary, vision-block detection in tool-result construction. No other rewrites.
4. Audit wrapper KEEPS the tool body inside store.transaction(); only post-commit network callables run after commit. tests/test_tool_kit.py:27 must pass UNCHANGED.
5. SQLiteStore.create_message default `synthesize_outbound_id=True` preserves Sprint 1a `inv_<turn_id>_<N>` behavior. Only resident send_message passes False.
6. Inbound persist-FIRST ordering: messages row + ingestion-ledger pending rows committed in ONE transaction BEFORE any Storage/Groq/image-row external IO.
7. Per SD-017: ingestion Storage pending rows MUST include `discord_attachment_url` in request_body (alongside `deterministic_path`). Reconciler uses Blob.exists; if missing AND Discord URL fetch fails → mark_orphaned + system_logs warn at category=recovery. Do NOT promise unconditional reissue.
8. NO literal Supabase JWT, Discord token, Anthropic key, or Groq key in committed files. Adapters read from env only.
9. New modules (`agent_kit/store/supabase.py`, `agent_kit/resident.py`, `agent_kit/transport/discord.py`) target ≤400 lines.
10. Mid-turn check fires at TWO points: before final-text auto-send AND before any explicit send_message tool call.

Gotchas:
- The CLAUDE.md forbids creating a `megaplan/` directory in the project root — keep code in `agent_kit/`, `arnold/`, `arnold_sdk/`, `tests/`, `supabase/`.
- Do NOT recurse into the megaplan harness; you are already inside it.
- Discord attachment URLs may be signed and time-limited; treat URL fetch failure during recovery as expected → mark_orphaned (do NOT loop forever).
- The `system_seq` field continues to live in `request_summary` for replay diagnostics; `request_body` is the authoritative replay payload.
- When extending psycopg adapters, use JSONB serialization for transcription_metadata and request_body; SQLite uses TEXT-as-JSON via `_JSON_COLUMNS`.
- `pytest-asyncio` is needed for new async tests; gate Supabase contract test execution on `SUPABASE_TEST_DB_URL` env presence with `pytest.importorskip("psycopg")`.
