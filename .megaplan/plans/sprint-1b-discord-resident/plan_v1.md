# Implementation Plan: Sprint 1b — Discord resident mode + robustness

## Overview

Sprint 1a delivered the substrate: `Store`, `Model`, `Transport`, `Blob` ports (`agent_kit/ports.py`), a SQLite store with `external_requests` ledger (`agent_kit/store/sqlite.py`, `agent_kit/store/migrations/sqlite/001_core.sql`), an idempotency-key Ledger (`agent_kit/ledger.py`), and an invocation-mode `run_turn` driving Anthropic via tool-use (`agent_kit/loop.py`, `agent_kit/model/anthropic.py`). The CLI reserves `--store supabase` but errors out (`arnold/cli.py:65`).

Sprint 1b adds a *second* implementation behind each port, then builds resident-mode lifecycle on top:

1. **Supabase store** — Postgres parity for the SQLite migration; same `tests/store_contract.py` runs green against both. Plus an `images` table (not yet in SQLite either — added to both stores in this sprint).
2. **Supabase storage blob adapter** — second `Blob` impl using Supabase Storage with deterministic paths.
3. **Discord transport** — push-style transport via discord.py; whitelist enforced; voice + image attachments downloaded eagerly to Storage.
4. **Resident loop runner** — owns turn lifecycle: coalescing window, restart recovery, mid-turn handling, live status message. Wraps existing `run_turn`; does not replace it.
5. **External request reconciliation** — replaces the `reconcile_on_boot` stub with per-provider reconciliation (Anthropic/OpenAI idempotency replay, Discord post-hoc lookup, Groq/Storage deterministic re-issue).
6. **Image tools** — `list_images`, `view_image`, `send_image`, `update_image_metadata` registered alongside existing communication tools.
7. **Voice transcription** — Groq Whisper, called by the Discord transport before message persistence; transcript becomes `messages.content`.

The whole point of this sprint is *port discipline*: nothing in `agent_kit/loop.py` or the existing tools should have to change to accommodate Discord. New behavior lives in adapters and a thin resident orchestrator.

**Key constraints:**
- Existing SQLite contract tests (`tests/store_contract.py`, `tests/test_sqlite_store.py`) must keep passing untouched.
- The Sprint 1a idempotency-key formula uses a `system_seq` ordinal extension (`agent_kit/ledger.py:1-12`); reconciliation must use the *same* derivation.
- The advisory epic lock pattern from Sprint 1a (Postgres advisory lock for Supabase, table row for SQLite) needs implementation on the Supabase side.
- Resident-mode mid-turn behavior is not an `agent_kit/loop.py` change — `run_turn` stays single-input. The resident orchestrator persists mid-turn messages, annotates the status, then injects them via the next-turn prompt or by appending to the in-flight `triggered_by_message_ids` after the turn completes.

---

## Phase 1: Foundation — dependencies, schema, contract tests

### Step 1: Add Sprint 1b dependencies (`pyproject.toml`)
**Scope:** Small
1. **Add** `discord.py`, `supabase`, `groq`, `httpx` to runtime `dependencies`.
2. **Add** `pytest-asyncio` to the `test` extra.
3. **Confirm** `setuptools.packages.find` still excludes `tests/` — currently fine.

### Step 2: Create Supabase migration for Sprint 1a parity (`supabase/migrations/`)
**Scope:** Medium
1. **Initialize** the Supabase project layout: `supabase/config.toml` and `supabase/migrations/`. Capture local DB URL conventions in a short `supabase/README.md` section in `planning-bot-spec.md`-adjacent location *only if absent*; otherwise reuse spec section "Local Development and Migrations" (`planning-bot-spec.md:2513`). Do not create new top-level docs.
2. **Author** `supabase/migrations/<timestamp>_001_core.sql` mirroring `agent_kit/store/migrations/sqlite/001_core.sql:1` — tables `epics`, `bot_turns`, `messages`, `tool_calls`, `system_logs`, `epic_locks`, `external_requests`. Postgres differences: `JSONB` instead of `TEXT` for json columns, `timestamptz` defaults via `now()`, `BOOLEAN` (not `INTEGER`/`CHECK`), `gen_random_uuid()`-based PKs (still `TEXT` to match SQLite ids), enums via `CHECK` constraints (keep simple — no `CREATE TYPE`). Same indexes.
3. **Add** Postgres advisory-lock helper RPC `acquire_epic_lock(epic_id text, holder_id text, ttl_seconds int)` that does `INSERT ... ON CONFLICT DO UPDATE` on `epic_locks` with the same expiry semantics as `SQLiteStore.acquire_epic_lock` (`agent_kit/store/sqlite.py:257`). Do *not* use Postgres native `pg_advisory_lock` here — the row-based lock is observable and survives across connections, which matters for the recovery scan.

### Step 3: Add `images` table to both stores (`supabase/migrations/`, `agent_kit/store/migrations/sqlite/`)
**Scope:** Small
1. **Add** `supabase/migrations/<timestamp>_002_images.sql` and `agent_kit/store/migrations/sqlite/002_images.sql` with columns from spec data model (`planning-bot-spec.md:1439`): `id`, `epic_id`, `source` (`agent_generated`|`user_uploaded`), `prompt` (nullable), `storage_url`, `quality`, `size`, `created_at`, `reference_key`, `description`, `caption`, `in_body`, `active` (default true), `discord_attachment_id`.
2. **Index** `(epic_id, created_at DESC)`, partial unique on `(epic_id, reference_key) WHERE active = true`, `(epic_id, source)`. (For SQLite, partial unique index works via `CREATE UNIQUE INDEX ... WHERE active = 1`.)
3. **Confirm** the SQLiteStore migration loop picks up `002_images.sql` automatically (`agent_kit/store/sqlite.py:50` does `glob('*.sql')` sorted).

### Step 4: Extend the store contract test for Sprint 1b coverage (`tests/store_contract.py`)
**Scope:** Small
1. **Append** a section to `run_store_contract` that exercises: `insert_pending` → `mark_confirmed` round-trip, idempotency-key uniqueness, `mark_failed`, the new image CRUD methods (defined in Step 7), and abandoned-turn recovery query (define a new `Store.find_abandoned_turns(older_than_seconds)` method in Step 5/Step 7).
2. **Keep** the existing assertions intact — both `tests/test_sqlite_store.py` and the new Supabase test file run the same suite.

---

## Phase 2: Supabase adapters

### Step 5: Extend `Store` and `Blob` ports for Sprint 1b methods (`agent_kit/ports.py`)
**Scope:** Small
1. **Add** to `Store` Protocol (`agent_kit/ports.py:63`): `find_abandoned_turns(older_than_seconds: int) -> list[JSONDict]`, `find_pending_external_requests(older_than_seconds: int) -> list[JSONDict]`, `mark_orphaned(request_id: str, *, error_details: JSONDict) -> JSONDict`, `find_unprocessed_messages(epic_id: str | None = None) -> list[JSONDict]`, plus image methods: `create_image(...)`, `load_image(image_id)`, `list_images(epic_id, source=None, active_only=True)`, `update_image(image_id, **changes)`.
2. **Tighten** the `Transport` Protocol with explicit push/pull split: `mode: Literal["push","pull"]` attribute and `start(handler) -> None` / `stop()` / `post_message(channel_id, content, ...) -> JSONDict` / `edit_message(channel_id, message_id, content) -> JSONDict` / `download_attachment(url) -> bytes`. The CLI's existing pull-shaped `Transport.receive` is a thin wrapper; keep both shapes.
3. **Note** the spec compatibility: same protocol shape for both Discord and any future invocation transport (`planning-bot-spec.md:414`).

### Step 6: Implement Supabase store (`agent_kit/store/supabase.py`)
**Scope:** Large
1. **Build** `SupabaseStore` class implementing the full `Store` Protocol. Use `supabase` Python client for queries; for `transaction()` use a thin `psycopg`/`postgrest` RPC pattern — Supabase REST does not expose multi-statement transactions, so wrap atomic operations as Postgres functions exposed via RPC, OR use a direct `psycopg` connection alongside. Pick **direct `psycopg` connection** (cleaner; matches recovery scan needs); supabase-py is used only for Storage in Step 8.
2. **Mirror** the SQLite implementation method-for-method (`agent_kit/store/sqlite.py:85-470`). The JSON column normalization mirrors the `_JSON_COLUMNS` set (`agent_kit/store/sqlite.py:17-30`) — JSONB values come back as Python dicts directly, so the decode step becomes a no-op for those columns.
3. **Implement** `acquire_epic_lock` via `INSERT INTO epic_locks ... ON CONFLICT (epic_id) DO UPDATE WHERE expires_at <= NOW()` returning whether the row is held by `holder_id`. Same 60s timeout semantics (`planning-bot-spec.md:418-425`).
4. **Implement** `find_abandoned_turns(older_than_seconds=300)` — selects `bot_turns` with `status='in_progress'` and `started_at < NOW() - interval`. Capped at 5 minutes per spec; image-generated turns at 7 minutes are out of scope (no images yet generated in this sprint).
5. **Implement** `mark_orphaned` writing `status='orphaned'` and a row in `system_logs` at `warn` / category `recovery`.
6. **Implement** the new image CRUD methods. `create_image` auto-assigns reference_key when omitted: for `source='user_uploaded'`, look up `MAX(reference_key)` matching pattern `img_user_upload_%` for the epic and increment.

### Step 7: Mirror new Store methods in SQLite (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Add** `find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `create_image`, `load_image`, `list_images`, `update_image` matching the Supabase signatures.
2. **Update** `_JSON_COLUMNS` if any image json fields are added (none in current schema; just `reference_key`/strings).
3. **Run** the new contract tests.

### Step 8: Supabase Storage blob adapter (`agent_kit/blob/supabase_storage.py` — new)
**Scope:** Small
1. **Implement** `SupabaseStorageBlob` against the `Blob` Protocol (`agent_kit/ports.py:193`). `put` uses deterministic key `images/{epic_id}/{idempotency_key}.{ext}` (or `audio/{epic_id}/{idempotency_key}.ogg` for voice) — required for retry-overwrite semantics (`planning-bot-spec.md:1612`).
2. **Wire** through `external_requests` ledger as a `provider='supabase_storage'` entry before each upload.

### Step 9: Wire up Supabase store in CLI (`arnold/cli.py`)
**Scope:** Small
1. **Replace** the `_unsupported_store_envelope` short-circuit at `arnold/cli.py:65` with construction of `SupabaseStore` from env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, or `SUPABASE_DB_URL` for direct psycopg).
2. **Add** `tests/test_cli.py` cases for `--store supabase` happy path against a fixture/mocked store factory.

### Step 10: Run the contract tests against both stores (`tests/test_supabase_store.py` — new)
**Scope:** Small
1. **Add** `tests/test_supabase_store.py` mirroring `tests/test_sqlite_store.py:11`. Use a `pytest.fixture` that creates a transactional savepoint per test against a local Supabase (configured via `SUPABASE_TEST_DB_URL`); skip the test module via `pytest.importorskip("psycopg")` and an env-var check when unset, so CI can run without infra in default mode.
2. **Verify** `pytest tests/test_sqlite_store.py tests/test_supabase_store.py` both pass.

---

## Phase 3: Discord transport + resident loop

### Step 11: Discord transport adapter (`agent_kit/transport/discord.py` — new)
**Scope:** Large
1. **Implement** `DiscordTransport` (`Transport` Protocol, `mode='push'`) with discord.py's `commands.Bot`. Set up the privileged `MESSAGE_CONTENT` intent (`planning-bot-spec.md:2731`).
2. **Implement** `on_message` handler:
   a. Reject messages from non-DM channels (`message.channel.type != DMChannel`) silently.
   b. Reject messages from non-whitelisted user IDs by writing a `system_logs` entry at `info` level with category `application` and event_type `whitelist_rejected` — no Discord reply (per acceptance criteria: "no response, log entry").
   c. For voice attachments (Discord exposes the `voice_message` flag on attachments), download via `attachment.url`, upload to Supabase Storage, call `groq.audio.transcriptions.create(model="whisper-large-v3", file=...)`. The transcript becomes `messages.content`. Set `was_voice_message=true`, `audio_storage_url=<storage_url>`, `transcription_metadata={response details}`. (Spec: `planning-bot-spec.md:865-878`.)
   d. For image attachments, download bytes, upload to Storage, create `images` row with `source='user_uploaded'`, auto-assigned `reference_key`. Set `messages.has_image_attachment=true`, link via `discord_attachment_id`. (Spec: `planning-bot-spec.md:1184-1203`.)
   e. **Persist messages with unique discord_message_id immediately** — before any coalescing or LLM call. The DB unique constraint protects against gateway replay (spec: `planning-bot-spec.md:2453-2461`).
3. **Whitelist source:** env var `DISCORD_USER_WHITELIST` as a comma-separated list of Discord user IDs. Cached at startup; reload on `SIGHUP` is out of scope.
4. **Implement** `post_message`/`edit_message` returning the Discord `message_id` for the loop to record in `bot_turns.status_message_id` and `messages.discord_message_id`. Both go through the `external_requests` ledger as `provider='discord'`.
5. **Auth:** read `DISCORD_BOT_TOKEN` from env.

### Step 12: Resident-mode runner with coalescing (`agent_kit/resident.py` — new)
**Scope:** Large
1. **Build** a `ResidentRunner` class that owns:
   - The Discord transport reference + a `MessageCoalescer` per-epic (defined inline).
   - The `Store`, `Model`, `Blob` instances.
   - A background recovery scheduler (asyncio task running every 5 minutes).
2. **Coalescing logic** (spec: `planning-bot-spec.md:817`):
   - Each new message resets the per-epic 10s timer; hard cap 30s OR 10 messages.
   - When the timer fires, all coalesced message IDs become `triggered_by_message_ids` for one `run_turn` call.
   - If a turn is in flight for that epic, new messages queue and arrive as "mid-turn" (Step 13).
3. **Wrap** `run_turn` with a status-message updater (Step 14). Pass an `on_event` callback into `run_turn` (`agent_kit/loop.py:75`) that:
   - On `tool_call` events, edits the Discord status message (debounced to 1s minimum gap, spec: `planning-bot-spec.md:1002`).
   - On `activity` events, updates the "Currently:" line.
4. **Inject input:** for now, concatenate the burst messages into the `input` string passed to `run_turn` (spec: invocation/CLI guidance `planning-bot-spec.md:813` says callers concatenate; resident bursts behave the same upstream of the LLM). Each coalesced message is already persisted; we just pass `triggered_by_message_ids` via a new optional kwarg in `run_turn` so `bot_turns.triggered_by_message_ids` reflects the burst.
5. **Modify** `run_turn` (`agent_kit/loop.py:21`) to accept `triggered_by_message_ids: Sequence[str] | None = None` and `pre_persisted: bool = False`. When provided, skip the inline `create_message` (resident has already persisted) and pass IDs straight to `create_turn`. CLI path keeps existing behavior.

### Step 13: Mid-turn message handling (`agent_kit/resident.py`)
**Scope:** Medium
1. **When** a new message arrives during a turn (lock held by another holder for the same epic), the runner:
   a. Persists the message (Step 11.e already handles this).
   b. Calls the status-updater to append `📥 Received "[first 60 chars]..."` (spec: `planning-bot-spec.md:995`).
   c. Stashes its `message_id` in an in-memory per-epic `pending_mid_turn_ids` list.
2. **End-of-turn check:** after `run_turn` returns from the wrapped engine but before the runner releases its bookkeeping, query `find_unprocessed_messages(epic_id)` for any not in `triggered_by_message_ids`. If present:
   - The runner kicks off a follow-up turn immediately (rather than implementing in-loop end-of-turn in `agent_kit/loop.py`). The follow-up turn's `triggered_by_message_ids` is the mid-turn list. The bot prompt for that turn carries the spec's `[Mid-turn messages — arrived after this turn started]` framing (spec: `planning-bot-spec.md:822`) prepended to the input.
   - This satisfies the acceptance criterion ("bot prompted with mid-turn messages") without rewriting `run_turn`.
3. **Append** processed mid-turn IDs to the prior turn's `triggered_by_message_ids` retroactively via `update_turn` if the bot's reasoning addressed them — out of scope for the deterministic path; record them as the *follow-up* turn's triggers.

### Step 14: Live status message (`agent_kit/resident.py`, `agent_kit/tools/communication.py`)
**Scope:** Medium
1. **At turn start** the runner posts the initial status to Discord, captures the message_id, calls `store.update_turn(turn_id, status_message_id=...)`.
2. **Status formatter** (pure function in the same file) returns the markdown body from spec `planning-bot-spec.md:979-988`. Inputs: tool count, last-3 tool rows from `tool_calls`, `bot_turns.current_activity`, last-call timestamp (Discord `<t:UNIX:R>`).
3. **Debounce:** runner maintains `last_edit_at` per turn; if `now - last_edit_at < 1s`, schedule a trailing edit (asyncio).
4. **Final state** on turn completion: `✅ Done. N tool calls. <t:UNIX:R>` (or `❌ Failed. ...`).
5. **`set_activity`** is unchanged at the tool level (`agent_kit/tools/communication.py:75`); the runner reads its event from the loop's `on_event` stream and pulls `bot_turns.current_activity` via `update_turn` mirror so the next status edit reflects it. Extend `set_activity` to call `store.update_turn(turn_id, current_activity=description)` so the column is populated (spec: `planning-bot-spec.md:1001`).

### Step 15: External request reconciliation (`agent_kit/ledger.py`)
**Scope:** Medium
1. **Replace** the stub `reconcile_on_boot` (`agent_kit/ledger.py:96`) with real logic:
   - Pull `find_pending_external_requests(60)` from the store.
   - Per-provider dispatch (spec: `planning-bot-spec.md:1599-1612`):
     - `anthropic` / `openai`: replay with same `Idempotency-Key` header. Update `confirmed`/`failed`.
     - `discord`: post-hoc lookup — list bot's recent DM messages in the user's channel within the request window (use `request_summary.window_start`/`window_end`), match by content prefix or by `request_summary.content_hash`. Mark `confirmed` if found; `orphaned` and re-queue otherwise.
     - `groq`: re-issue (deterministic).
     - `supabase_storage`: HEAD the deterministic path; mark `confirmed` if present; re-issue otherwise.
     - `github`: not exercised this sprint; leave a no-op branch with a TODO log.
2. **Wrap** in a `Reconciler` class taking `Store` + provider client registry, so the resident runner can call it on startup AND on the 5-minute timer (spec: `planning-bot-spec.md:2492`).
3. **Abandoned-turn pass:** add a sibling method `reconcile_abandoned_turns()` that calls `find_abandoned_turns(300)` and for each: `update_turn(turn_id, status='abandoned')`, log `recovery` event, then re-queue the turn's `triggered_by_message_ids` to the runner's per-epic coalescer (spec: `planning-bot-spec.md:2488`).
4. **Idempotency-key derivation** uses `derive_idempotency_key` from `agent_kit/ledger.py:75` unchanged — preserves the `system_seq` extension.

---

## Phase 4: Image tools and integration

### Step 16: Image tools (`agent_kit/tools/images.py` — new)
**Scope:** Medium
1. **Register** four tools using `register_tool` (`agent_kit/tool_kit.py:145`):
   - `list_images(epic_id, source?)` — `operation_kind='read'`, returns reference_keys + descriptions + captions + source (no bytes).
   - `view_image(image_id, mode='visual'|'description')` — `operation_kind='read'`. For `visual`, fetches bytes via the Blob adapter and returns base64-encoded payload; the loop's downstream Anthropic adapter (Step 17) is responsible for sending it to vision.
   - `send_image(image_id, caption?)` — `operation_kind='write'`. Resident: posts the image to Discord (records `external_requests` entry); appends to reply_buffer with a marker. Invocation: append to envelope `events` array (spec: `planning-bot-spec.md:1653`).
   - `update_image_metadata(image_id, caption?, description?, reference_key?)` — `operation_kind='write'`. Validates `reference_key` regex `^[a-z][a-z0-9_]{0,63}$` (spec: `planning-bot-spec.md:1223`).
2. **Auto-import** in `agent_kit/loop.py`'s top-of-module imports beside the existing `import agent_kit.tools.communication` (`agent_kit/loop.py:14`).

### Step 17: Wire view_image bytes through to Anthropic (`agent_kit/model/anthropic.py`)
**Scope:** Small
1. **Extend** the model adapter to accept tool-result blocks containing image data and re-encode them as Anthropic vision content blocks. Currently `messages.append({"role":"user","content":{"tool_name":..., "result":...}})` (`agent_kit/loop.py:237`). Special-case `view_image` results: when `result.image_bytes_b64` is present, emit a multi-block message (`text` block + `image` block) instead of the bare dict.
2. **Validate** by mocking the Anthropic client.

### Step 18: Resident CLI entry point (`arnold/cli.py`)
**Scope:** Small
1. **Add** `arnold resident` subcommand that constructs `SupabaseStore`, `SupabaseStorageBlob`, `DiscordTransport`, `AnthropicModel`, `ResidentRunner`. Runs `runner.run()` (asyncio loop) until SIGINT.
2. **Document** that this requires `DISCORD_BOT_TOKEN`, `DISCORD_USER_WHITELIST`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY` (spec: `planning-bot-spec.md:2713`). Failure to find any required var fails fast at startup with a clear error to `system_logs`.

---

## Phase 5: Tests

### Step 19: Unit tests (`tests/`)
**Scope:** Medium
1. **`tests/test_supabase_store.py`** — runs `run_store_contract` against Supabase impl. Skip when `SUPABASE_TEST_DB_URL` unset.
2. **`tests/test_coalescer.py`** — 5 messages in 8s coalesce into one trigger list; 30s cap fires at 30s; 10-message cap fires at 10. Pure logic; uses `asyncio` virtual time via `pytest-asyncio` and a fake clock.
3. **`tests/test_whitelist.py`** — Discord transport's whitelist filter; mocked `Message`s from allowed/disallowed user IDs; verifies log entry but no reply.
4. **`tests/test_status_formatter.py`** — given mocked `tool_calls` rows + `current_activity`, asserts the markdown matches the spec template (`planning-bot-spec.md:979`).
5. **`tests/test_reconciler.py`** — Anthropic replay with stubbed client confirms; Discord post-hoc lookup with stubbed history finds and marks confirmed; not-found marks `orphaned`. Idempotency key for the same `(turn, tool_call, provider, endpoint, args)` tuple stable across calls.
6. **`tests/test_image_tools.py`** — `list_images`, `view_image` (description-only path; `visual` path with mocked Blob), `update_image_metadata` reference_key validation, `send_image` invocation-mode envelope event.

### Step 20: Integration tests (`tests/`)
**Scope:** Medium
1. **`tests/test_resident_recovery.py`** — start ResidentRunner against in-memory SQLiteStore + a fake DiscordTransport that records inbound. Inject a mid-turn crash (cancel the turn task between body write and reply); on restart, recovery marks the prior turn `abandoned`, queues the trigger messages under a fresh turn. Assertions: previous turn `status='abandoned'`, new turn exists with same `triggered_by_message_ids`.
2. **`tests/test_voice_pipeline.py`** — DiscordTransport receives a fake voice attachment; mocked Groq returns a transcription; verifies `messages.was_voice_message=true`, content matches transcription, audio is in (mock) Storage.
3. **`tests/test_image_attachment_pipeline.py`** — DiscordTransport receives image attachment; mocked Storage; verifies `images` row created with `source='user_uploaded'`, `reference_key='img_user_upload_1'`, `messages.has_image_attachment=true`.
4. **`tests/test_status_message_lifecycle.py`** — drives a fake-model script (using existing `FakeModel`, `agent_kit/model/fake.py`) through 3 tool calls; asserts the FakeDiscordTransport sees: 1 send (initial status), N edits (debounced ≤ 4), 1 final edit with `✅ Done`. Throttling test (#10 from spec adversarial list `planning-bot-spec.md:2618`): 20 tool calls in 2s → ≤ 4 edits.
5. **`tests/test_mid_turn_messages.py`** — starts a turn; while it's executing tool calls, injects a second message; verifies status message gets the `📥 Received` annotation; after turn completes, a *follow-up* turn fires with the new message in its triggers.

### Step 21: Final verification
**Scope:** Small
1. **Run** `pytest` — full suite green, including original Sprint 1a tests untouched.
2. **Manual smoke** (info-priority, not pipeline-checked): `arnold resident` against staging Discord + staging Supabase; whitelisted DM responds within 30s; voice DM transcribes; image attachment lands in Storage with `images` row; mid-turn DM gets the 📥 annotation.

## Execution Order

1. **Phase 1** first — dependencies, migrations, and the contract test extension. These unblock everything downstream and let us validate the second store impl with the same suite.
2. **Phase 2** next — Supabase store + Storage adapter, then mirror the new Store methods in SQLite. Run the contract suite against both before moving on.
3. **Phase 3** — Discord transport in isolation (testable with mocked discord.py), then the ResidentRunner that ties transport + loop + status. Reconciler is built alongside because the runner needs it on startup.
4. **Phase 4** — image tools last, since they depend on the new images table (Phase 1) and the Blob adapter (Phase 2).
5. **Phase 5** — tests are interleaved per phase in practice, but the integration tests in Step 20 run last because they exercise the whole stack.

## Validation Order

1. Cheapest: existing `pytest tests/test_sqlite_store.py tests/test_run_turn.py tests/test_envelope.py tests/test_ledger.py` — proves Sprint 1a regressions.
2. New unit tests (Step 19) — pure-logic coverage of coalescer, whitelist, status formatter, reconciler, image tools.
3. Supabase contract test (`tests/test_supabase_store.py`) — proves port equivalence.
4. Resident integration tests (Step 20) — restart safety, voice, image, status lifecycle, mid-turn handling.
5. Manual smoke against staging Discord + Supabase — last, info-priority.
