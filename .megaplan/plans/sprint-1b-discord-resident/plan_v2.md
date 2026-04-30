# Implementation Plan: Sprint 1b — Discord resident mode + robustness

## Overview

Sprint 1a delivered the substrate: `Store`, `Model`, `Transport`, `Blob` ports (`agent_kit/ports.py`), a SQLite store with `external_requests` ledger (`agent_kit/store/sqlite.py`, `agent_kit/store/migrations/sqlite/001_core.sql`), an idempotency-key Ledger with a `system_seq` extension (`agent_kit/ledger.py:1`), and an invocation-mode `run_turn` driving Anthropic via tool-use (`agent_kit/loop.py`, `agent_kit/model/anthropic.py`). The CLI reserves `--store supabase` but errors out (`arnold/cli.py:65`).

Sprint 1b adds a *second* implementation behind each port, then builds resident-mode lifecycle on top. Two design changes are load-bearing and must land before the adapter work: (a) `Model.complete_turn` gains an `idempotency_key` parameter so the existing ledger row can be replayed; (b) `run_turn` gains hooks (`on_turn_start`, `on_pre_finalize`) and an optional `triggered_by_message_ids`/`recovered_input` shape so resident orchestration can post a status message and run the spec's same-turn end-of-turn check without forking the loop.

**Locked product decisions** (from gate `settled_decisions`): env-var Discord whitelist; direct psycopg3 for Supabase store ops (supabase-py only for Storage); row-based `epic_locks` on Postgres; `images` table added to both stores. Mid-turn handling **is not** a follow-up turn — it is the spec's same-turn end-of-turn re-prompt (`planning-bot-spec.md:822-843`) implemented via the new `on_pre_finalize` hook.

**Secrets policy.** The Supabase service-role JWT supplied in the idea block must NEVER be committed to migrations, tests, fixtures, docs, plan artifacts, or this repo. All adapters read keys from env vars only. The user should rotate that key — it has appeared in plain text in plan inputs.

**Scope discipline.** Image work this sprint is Discord-only: ingestion of user-uploaded images via the Discord transport, plus the four image *tools*. Invocation-mode attachments (`run_turn(..., attachments=...)`, `--attach`, `LocalBlobStore`) remain accepted Sprint 1a debt and are explicitly NOT in this sprint — recorded in the deferral note in Step 21. Voice support is also Discord-only ingestion this sprint; a `transcribe_voice` tool and the non-voice-audio adversarial path (`planning-bot-spec.md:2634`) are deferred.

**Contract test stability.** `tests/store_contract.py` is **not modified** in this sprint (issue_hints-1) — it ships unchanged from Sprint 1a and runs green against both stores. New Sprint 1b functionality (ledger reconciliation queries, image CRUD, abandoned-turn finder) gets a *separate* `tests/store_contract_v1b.py` so the original-suite-runs-unchanged property the spec calls out is observable.

---

## Phase 1: Foundation — dependencies, schema, secrets

### Step 1: Add Sprint 1b dependencies (`pyproject.toml`)
**Scope:** Small
1. **Add** to runtime `dependencies`: `discord.py`, `supabase`, `groq`, `httpx`, `psycopg[binary]>=3.1` (FLAG correctness-1).
2. **Add** to the `test` extra: `pytest-asyncio`.
3. **Confirm** `setuptools.packages.find` is unchanged.

### Step 2: Document secrets policy (`planning-bot-spec.md` is canonical; no new docs)
**Scope:** Small
1. **Add** to the project root `.gitignore` (or create) entries for `.env`, `.env.local`, and any `supabase/.branches/*`.
2. **State** in the resident-CLI docstring (Step 19) that `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`, `DISCORD_BOT_TOKEN`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` are env-only and must not be hard-coded. Migrations and tests must use `os.environ[...]` or fixtures, never literal keys (FLAG-006).
3. **Action item** for the user (also recorded in `questions`): rotate the Supabase service-role key supplied in the idea block, since it appeared in plain text.

### Step 3: Supabase migration mirroring Sprint 1a (`supabase/migrations/<ts>_001_core.sql`)
**Scope:** Medium
1. **Initialize** `supabase/config.toml` and `supabase/migrations/`. (No new top-level docs.)
2. **Author** `<ts>_001_core.sql` mirroring `agent_kit/store/migrations/sqlite/001_core.sql:1`. Postgres differences: `JSONB` for json columns, `timestamptz` defaults via `now()`, `BOOLEAN` (not `INTEGER`/`CHECK`), keep `TEXT` PKs for cross-store id parity, enums as `CHECK` constraints. Same indexes.
3. **Add** the `epic_locks` table with the same row-based pattern as SQLite (gate `SD-003`).

### Step 4: Add `images` table to both stores (`supabase/migrations/`, `agent_kit/store/migrations/sqlite/`)
**Scope:** Small
1. **Add** `supabase/migrations/<ts>_002_images.sql` and `agent_kit/store/migrations/sqlite/002_images.sql` per spec data model (`planning-bot-spec.md:1439`): `id`, `epic_id`, `source` (`agent_generated`|`user_uploaded`), `prompt`, `storage_url`, `quality`, `size`, `created_at`, `reference_key`, `description`, `caption`, `in_body`, `active`, `discord_attachment_id`.
2. **Index** `(epic_id, created_at DESC)`, partial unique on `(epic_id, reference_key) WHERE active = true`, `(epic_id, source)`. SQLite uses `WHERE active = 1`.
3. **Confirm** `SQLiteStore.apply_migrations` (`agent_kit/store/sqlite.py:50`) picks up the new file via the existing sorted glob.

---

## Phase 2: Interface changes (must precede adapter work)

### Step 5: Extend `Model.complete_turn` to accept `idempotency_key` (`agent_kit/ports.py`, `agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`, `agent_kit/loop.py`)
**Scope:** Small
1. **Add** `idempotency_key: str | None = None` to `Model.complete_turn` (`agent_kit/ports.py:182`). Update `AnthropicModel.complete_turn` to forward it via `extra_headers={"Idempotency-Key": idempotency_key}` on `client.messages.create(...)` (`agent_kit/model/anthropic.py:37`). Update `FakeModel.complete_turn` to accept and ignore it.
2. **Update** `run_turn` (`agent_kit/loop.py:117`) to pass `_idempotency_key` (already returned from `ledger.record_pending`) to `model.complete_turn`. This closes FLAG-007 / correctness-2.
3. **Persist** the `system_seq` ordinal into `external_requests.request_summary` (e.g., `request_summary["system_seq"] = model_call_seq`) at `agent_kit/loop.py:103` so `Reconciler` can reconstruct the key for replay (callers-3).

### Step 6: Add resident hooks to `run_turn` (`agent_kit/loop.py`)
**Scope:** Medium
1. **Add** keyword arguments to `run_turn`:
   - `triggered_by_message_ids: Sequence[str] | None = None` — when supplied, skip the inline `create_message` (resident has already persisted) and pass the IDs to `create_turn`.
   - `recovered_input_messages: Sequence[JSONDict] | None = None` — full persisted message rows whose `content` strings are concatenated (in `sent_at` order) into the model's first user prompt; required for the resident path AND for recovery (callers-1).
   - `on_turn_start: Callable[[JSONDict], None] | None = None` — invoked synchronously after `create_turn` succeeds with the freshly created turn row, **before** the first model call. Resident uses this to post the initial status message and persist `bot_turns.status_message_id` (closes FLAG-004 / scope-1).
   - `on_pre_finalize: Callable[[JSONDict], list[JSONDict] | None] | None = None` — invoked when the model has produced `final_text` and before any final `send_message` fires. Receives the in-progress turn dict; returns either `None` (proceed to finalize) or a list of mid-turn message rows. When messages are returned, `run_turn` synthesizes a `[Mid-turn messages — arrived after this turn started]` user-message block (spec text from `planning-bot-spec.md:824`), calls `update_turn(turn_id, triggered_by_message_ids=existing+new_ids)` to retroactively widen the trigger list, appends to `messages`, and re-enters the model loop (no `send_message` yet). Closes FLAG-001, issue_hints-2, scope-2.
2. **Keep** the existing `agent_kit/loop.py` invocation-mode happy path identical when these kwargs are `None` — the CLI tests in `tests/test_cli.py`, `tests/test_run_turn.py` must continue passing unmodified (gate must-criterion).

### Step 7: Make `send_message` / `set_activity` / `send_image` mode-divergent via injected dependencies (`agent_kit/tool_kit.py`, `agent_kit/tools/communication.py`)
**Scope:** Medium
1. **Extend** `ToolContext` (`agent_kit/tool_kit.py:29`) with optional fields:
   - `transport: PushTransport | None = None` — supplied by the resident runner; absent in invocation mode.
   - `blob: Blob | None = None` — supplied for image tools that need bytes.
   - `external_queue: list[Callable[[], None]] | None = None` — see Step 8.
2. **Update** `send_message` (`agent_kit/tools/communication.py:53`) to branch on `context.transport`:
   - Invocation (`transport is None`): existing behavior — append to `reply_buffer`, write outbound row with synthetic id.
   - Resident: build the outbound `messages` row WITHOUT `discord_message_id` first (so the audit transaction commits cleanly), then enqueue a post-commit callback (Step 8) that posts to Discord via `transport.post_message(...)`, updates `messages.discord_message_id`, and ledger-confirms. Returns the row id; the actual Discord id is filled in after commit. Closes FLAG-002 / callers-2 / all_locations-1.
3. **Update** `set_activity` (`agent_kit/tools/communication.py:75`) to also call `store.update_turn(turn_id, current_activity=description)` (spec: `planning-bot-spec.md:1001`) so the next status edit reflects it.

### Step 8: Externalize external IO from the audit transaction (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. **Restructure** `audit_wrap` (`agent_kit/tool_kit.py:107`) so DB writes commit *before* network IO, per spec ordering (`planning-bot-spec.md:2473-2480`). Closes correctness-3.
   - Stage A (no transaction): tool body runs; if it needs external IO, it appends a callable to `context.external_queue`. Tool returns its `result` and (optionally) a list of pending external-request specs.
   - Stage B (transaction): wrapper inserts `external_requests` rows for each spec via `Ledger`, then writes `tool_calls` row, then commits.
   - Stage C (no transaction): wrapper executes the queued callables sequentially. Each callable returns a `(provider_request_id, response_summary)` tuple or raises; wrapper marks the corresponding ledger row `confirmed`/`failed`. Network IO never holds a DB transaction open.
2. **Note** that this change is invisible to existing tools (they don't queue anything); only `send_message` (resident), `send_image`, voice transcription, and Storage uploads use the queue. Existing `tests/test_tool_kit.py` keeps passing.

### Step 9: Extend `Store` and add a thin `PushTransport` Protocol (`agent_kit/ports.py`)
**Scope:** Small
1. **Add** to the `Store` Protocol (`agent_kit/ports.py:63`):
   - `find_abandoned_turns(older_than_seconds: int) -> list[JSONDict]`
   - `find_pending_external_requests(older_than_seconds: int) -> list[JSONDict]`
   - `mark_orphaned(request_id: str, *, error_details: JSONDict) -> JSONDict`
   - `find_unprocessed_messages(epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[JSONDict]` — used by `on_pre_finalize`.
   - `load_messages(message_ids: Sequence[str]) -> list[JSONDict]` — used by recovery to rebuild input.
   - Image methods: `create_image(...)`, `load_image(image_id)`, `list_images(epic_id, source=None, active_only=True)`, `update_image(image_id, **changes)`.
2. **Add** a separate `PushTransport` Protocol (do NOT modify the existing `Transport` Protocol — the CLI continues to bypass it). Methods: `start(handler) -> None`, `stop()`, `post_message(channel_id, content, *, files=None) -> JSONDict`, `edit_message(channel_id, message_id, content) -> JSONDict`, `download_attachment(url) -> bytes`. This avoids the call-site upheaval flagged by all_locations-2.

---

## Phase 3: Adapters

### Step 10: Implement `SupabaseStore` (`agent_kit/store/supabase.py` — new)
**Scope:** Large
1. **Build** `SupabaseStore` against the `Store` Protocol using a direct `psycopg` connection (gate `SD-002`). Mirror `SQLiteStore` method-for-method (`agent_kit/store/sqlite.py:85-470`). JSONB returns dict directly so no decode pass needed.
2. **`acquire_epic_lock`** uses `INSERT INTO epic_locks ... ON CONFLICT (epic_id) DO UPDATE WHERE epic_locks.expires_at <= NOW() OR epic_locks.holder_id = EXCLUDED.holder_id` returning the actual holder. Same 60s timeout as SQLite (gate `SD-003`).
3. **Implement** the new Sprint 1b methods from Step 9 (`find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `load_messages`, image CRUD). `create_image` auto-generates `reference_key` for `source='user_uploaded'` by selecting `MAX(reference_key)` matching `img_user_upload_%` for the epic.

### Step 11: Mirror new Store methods in SQLite (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Add** all the same methods listed in Step 9 to `SQLiteStore`, using SQL idiomatic to SQLite (`datetime('now', '-X seconds')`, partial indexes, `INSERT OR IGNORE`).
2. **Run** the new contract tests from Step 16 against both stores.

### Step 12: Supabase Storage blob adapter (`agent_kit/blob/supabase_storage.py` — new)
**Scope:** Small
1. **Implement** `SupabaseStorageBlob` against the existing `Blob` Protocol (`agent_kit/ports.py:193`). Use `supabase` Python client (gate `SD-002`). Deterministic paths: `images/{epic_id}/{idempotency_key}.{ext}`, `audio/{epic_id}/{idempotency_key}.ogg`. Spec: `planning-bot-spec.md:1612`.
2. **Note** that the upload itself is wrapped through the Step 8 external queue when called from inside a tool; the Discord transport (Step 13) calls it directly during ingestion (no tool context).

### Step 13: Discord transport (`agent_kit/transport/discord.py` — new)
**Scope:** Large
1. **Implement** `DiscordTransport` against the new `PushTransport` Protocol with discord.py. Privileged `MESSAGE_CONTENT` intent (`planning-bot-spec.md:2731`). Auth via `DISCORD_BOT_TOKEN` env var.
2. **Whitelist:** parse `DISCORD_USER_WHITELIST` (comma-separated user IDs) at startup (gate `SD-001`). Non-DM channels rejected silently; non-whitelisted DMs write a `system_logs` row at `level='info'`, `category='application'`, `event_type='whitelist_rejected'` (acceptance criterion).
3. **`on_message` ingestion order** (every branch persists `messages` with the unique `discord_message_id` BEFORE any LLM call so duplicates collide on the index — spec `planning-bot-spec.md:2453`):
   a. Voice attachment (Discord's `attachment.is_voice_message()`): download bytes via `httpx`, upload to Supabase Storage at `audio/{epic_id}/{sha256(bytes)[:16]}.ogg`, call `groq.audio.transcriptions.create(model="whisper-large-v3", file=...)`, persist `messages` row with `was_voice_message=True`, `audio_storage_url=<url>`, `content=<transcription>`, `transcription_metadata=<groq response>`.
   b. Image attachment: download bytes, upload to Storage, `store.create_image(epic_id=..., source='user_uploaded', storage_url=..., discord_attachment_id=..., size=..., reference_key=None)` (auto-assigns `img_user_upload_<N>`), persist `messages` row with `has_image_attachment=True`.
   c. Text-only: persist `messages` row.
4. **Hand off** the persisted `message_id` to the resident runner via the `start(handler)` callback. Discord-side network IO outside this ingestion (post/edit) is invoked by Step 7's external queue and gets ledger entries; `system_seq` is irrelevant for these because `tool_call_id` is set.

### Step 14: Resident runner with coalescing, recovery, status (`agent_kit/resident.py` — new)
**Scope:** Large
1. **`MessageCoalescer`** per epic: 10s reset-on-new-message timer, 30s hard cap, 10-message cap (spec `planning-bot-spec.md:817`). When the timer fires AND no turn is in flight for the epic, dispatch.
2. **`ResidentRunner.dispatch_turn(epic_id, message_ids)`** acquires the epic lock indirectly through `run_turn`'s existing logic, then:
   - Calls `store.load_messages(message_ids)` to fetch persisted message contents.
   - Invokes `run_turn(epic_id=..., input=<unused — supplied via recovered_input_messages>, store=..., model=..., triggered_by_message_ids=message_ids, recovered_input_messages=loaded_messages, on_turn_start=self._on_turn_start, on_pre_finalize=self._on_pre_finalize, on_event=self._on_event)`.
3. **`_on_turn_start(turn)`**: post the initial status message via `transport.post_message(...)`, capture the Discord message_id, call `store.update_turn(turn['id'], status_message_id=...)`, record an `external_requests` row for the post (closes FLAG-004 / scope-1).
4. **`_on_event(event)`**: on `tool_call`/`activity` events, format the status (Step 15) and call `transport.edit_message(...)` with 1s debounce (`planning-bot-spec.md:1002`).
5. **`_on_pre_finalize(turn)`**: query `store.find_unprocessed_messages(epic_id=turn['epic_id'], started_at=turn['started_at'], exclude_ids=turn['triggered_by_message_ids'])`. Returns the list (or `None`). When new messages exist, the runner ALSO appends `📥 Received "[first 60]…"` lines to the live status message, then returns the messages so `run_turn` re-prompts the model with the spec block (FLAG-001 satisfied via the `run_turn` hook from Step 6).
6. **Mid-turn arrival concurrent with an in-flight turn**: the Discord transport's persistence step (Step 13.3) writes the row immediately. Coalescer notices a turn is in flight, so it does NOT start a new turn; the message is instead picked up by the in-flight turn's `on_pre_finalize` query.
7. **Recovery scheduler:** asyncio task running `Reconciler.run_once()` (Step 16) at startup and every 5 minutes (spec `planning-bot-spec.md:2492`). Re-queues abandoned turns' `triggered_by_message_ids` through the coalescer, which spawns a fresh turn (closes the kill-mid-turn acceptance criterion).

### Step 15: Status message formatter (`agent_kit/resident.py`)
**Scope:** Small
1. **Pure function** `format_status(turn_row, recent_tool_calls, current_activity, last_call_ts) -> str` returning the markdown body from spec `planning-bot-spec.md:979-988` with the Discord `<t:UNIX:R>` timestamp.
2. **Final state:** `✅ Done. N tool calls. <t:UNIX:R>` on completion; `❌ Failed. <reason>` on error (spec `planning-bot-spec.md:996`).

### Step 16: External-request reconciliation (`agent_kit/ledger.py`)
**Scope:** Medium
1. **Replace** the `reconcile_on_boot` stub (`agent_kit/ledger.py:96`) with a `Reconciler` class. Constructor takes `Store`, `Model`, `PushTransport | None`, `Blob | None`. `run_once()` does:
   - **Abandoned turns:** `find_abandoned_turns(300)` → mark `status='abandoned'`, log to `system_logs` at `warn` / `recovery`, return their `triggered_by_message_ids` to the caller (resident runner re-queues).
   - **Pending externals:** `find_pending_external_requests(60)` → per-provider dispatch (`planning-bot-spec.md:1599-1612`):
     - `anthropic` / `openai`: replay via `model.complete_turn(idempotency_key=row.idempotency_key, ...)` reconstructing args from `request_summary` (Step 5 enables this).
     - `discord`: call `transport.fetch_recent_messages(channel_id, since=row.first_attempted_at, until=row.last_attempted_at + 30s)` and match by content prefix from `request_summary`. Found → `mark_confirmed`. Not found → `mark_orphaned` and re-queue the underlying tool call's effect (resident runner inspects orphaned rows on its periodic pass).
     - `groq`: re-issue (deterministic) using stored audio URL.
     - `supabase_storage`: HEAD via `Blob.exists(path)` → `mark_confirmed` if present, else re-issue.
     - `github`: log a `recovery` info entry and skip (out of scope this sprint).
2. **Idempotency-key derivation** continues to use `derive_idempotency_key` (`agent_kit/ledger.py:75`) unchanged. Replay uses the *stored* `idempotency_key` from the row, not a re-derivation, so the formula's `system_seq` extension is irrelevant for replay (callers-3 satisfied because Step 5 also persists `system_seq` in `request_summary` for diagnostic purposes).

---

## Phase 4: Image tools and CLI wiring

### Step 17: Image tools (`agent_kit/tools/images.py` — new)
**Scope:** Medium
1. **Register** the four tools using `register_tool` (`agent_kit/tool_kit.py:145`):
   - `list_images(epic_id, source?)` — `read`, returns metadata only.
   - `view_image(image_id, mode='visual'|'description')` — `read`. `visual` path uses `context.blob.get(...)` to fetch bytes; result includes base64 payload + media_type.
   - `send_image(image_id, caption?)` — `write`. Resident: enqueues a Discord post via Step 8's queue. Invocation: appends to envelope `events` array (spec `planning-bot-spec.md:1653`).
   - `update_image_metadata(image_id, caption?, description?, reference_key?)` — `write`. Validates `reference_key` regex `^[a-z][a-z0-9_]{0,63}$` (spec `planning-bot-spec.md:1223`).
2. **Auto-import** in `agent_kit/loop.py` beside the existing `import agent_kit.tools.communication` (`agent_kit/loop.py:14`).

### Step 18: Wire `view_image` bytes through to Anthropic (`agent_kit/loop.py`, `agent_kit/model/anthropic.py`)
**Scope:** Small
1. **Detect** in the loop's tool-result message construction (`agent_kit/loop.py:237`) when `result.get("media_type")` and `result.get("image_bytes_b64")` are present (the `view_image` shape) and emit Anthropic vision content blocks: `[{"type":"text","text":...},{"type":"image","source":{"type":"base64","media_type":...,"data":...}}]`. Other tools' result shape is unchanged.

### Step 19: Resident CLI entry point (`arnold/cli.py`)
**Scope:** Small
1. **Replace** the `_unsupported_store_envelope` short-circuit (`arnold/cli.py:65`) with `SupabaseStore` construction from env vars (`SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`).
2. **Add** an `arnold resident` subcommand that constructs `SupabaseStore`, `SupabaseStorageBlob`, `DiscordTransport`, `AnthropicModel`, `ResidentRunner` and runs the asyncio loop until SIGINT. Required env vars are validated up front with a clear error to `system_logs`; missing vars exit non-zero.

---

## Phase 5: Tests and verification

### Step 20: Unit and contract tests (`tests/`)
**Scope:** Medium
1. **Leave** `tests/store_contract.py` UNCHANGED so the spec's "Sprint 1a contract suite reused unchanged" property is observable (issue_hints-1).
2. **`tests/store_contract_v1b.py`** (new) — exercises `find_abandoned_turns`, `find_pending_external_requests`, `mark_orphaned`, `find_unprocessed_messages`, `load_messages`, image CRUD, and the unique-idempotency-key constraint.
3. **`tests/test_supabase_store.py`** (new) — runs both `run_store_contract` (unchanged) AND `run_store_contract_v1b` against `SupabaseStore`. Skip module via `pytest.importorskip("psycopg")` and an env-var check on `SUPABASE_TEST_DB_URL`.
4. **`tests/test_sqlite_store.py`** — extend to also call `run_store_contract_v1b` (the existing v1a test stays as-is so the unchanged property stands).
5. **`tests/test_coalescer.py`** — virtual-time coalescer unit tests: 5 in 8s → 1 trigger; 30s cap; 10-message cap.
6. **`tests/test_whitelist.py`** — Discord transport whitelist filter writes the expected log row, no reply.
7. **`tests/test_status_formatter.py`** — golden-string match against the spec template.
8. **`tests/test_reconciler.py`** — Anthropic replay (stub `Model` records `idempotency_key`); Discord post-hoc lookup confirmed/orphaned paths; Storage HEAD-confirm.
9. **`tests/test_image_tools.py`** — `list_images`, `view_image` description+visual, `update_image_metadata` regex, `send_image` invocation event + resident queued callback.
10. **`tests/test_run_turn_hooks.py`** — `on_turn_start` fires after `create_turn`; `on_pre_finalize` returning new messages causes a re-prompt with the spec's block text and widens `triggered_by_message_ids`; existing invocation-mode behavior unchanged when hooks are `None`.
11. **`tests/test_tool_kit_external_queue.py`** — verifies Step 8's three-stage ordering: ledger-pending row exists before commit, DB transaction commits before queued callback fires, ledger row marked `confirmed` after callback returns.

### Step 21: Integration tests (`tests/`)
**Scope:** Medium
1. **`tests/test_resident_recovery.py`** — start `ResidentRunner` over in-memory `SQLiteStore` + a `FakeDiscordTransport`; cancel a turn mid-tool-call; on next `Reconciler.run_once`, prior turn is `abandoned`, fresh turn fires with same `triggered_by_message_ids`.
2. **`tests/test_voice_pipeline.py`** — `FakeDiscordTransport` delivers a voice attachment; mocked Groq returns transcription; `messages` row has `was_voice_message=True`, transcribed `content`, `audio_storage_url` set.
3. **`tests/test_image_attachment_pipeline.py`** — image attachment → `images` row with `source='user_uploaded'`, `reference_key='img_user_upload_1'`; subsequent attachment auto-assigns `img_user_upload_2`.
4. **`tests/test_status_lifecycle.py`** — `FakeModel` script with 3 tool calls produces: 1 initial post + ≤3 edits + 1 final `✅ Done. 3 tool calls.`; throttling test: 20 tool calls in 2s → ≤4 edits.
5. **`tests/test_mid_turn_messages.py`** — burst turn in flight; second message arrives mid-tool-call; status gets `📥 Received…`; the IN-FLIGHT turn's `triggered_by_message_ids` widens to include the new message; final reply addresses it (FakeModel script shapes the response).
6. **`tests/test_send_message_resident.py`** — resident `send_message` posts via `FakeDiscordTransport.post_message`, `messages.discord_message_id` is the returned Discord id, `external_requests` row transitions pending→confirmed, and the DB transaction does NOT remain open across the network call (assert `store.transaction_depth == 0` inside the queued callback).

### Step 22: Final verification and deferral note
**Scope:** Small
1. **Run** `pytest` — full suite green; existing Sprint 1a tests (`tests/test_envelope.py`, `tests/test_ledger.py`, `tests/test_run_turn.py`, `tests/test_sqlite_store.py`'s 1a tests, `tests/test_cli.py`, `tests/test_tool_kit.py`) untouched and passing.
2. **Append** a deferral note in the next sprint's `ideas/` file (or as a TODO comment in `agent_kit/loop.py` near the `input` parameter) capturing the still-open invocation-mode attachment debt: `--attach`, `run_turn(..., attachments=...)`, `LocalBlobStore`, caller-uploaded images per `planning-bot-spec.md:1895-1908` (FLAG-008 / issue_hints-3). Also note: `transcribe_voice` tool and non-voice-audio path (`planning-bot-spec.md:2634`) deferred (scope-3).
3. **Manual smoke** (info, not pipeline-checked): `arnold resident` against staging Discord + staging Supabase — whitelisted DM responds within 30s; voice DM transcribes; image attachment lands in Storage with `images` row; mid-turn DM gets the 📥 annotation in the live status message.

## Execution Order

1. **Phase 1** — deps, secrets policy, Supabase migration, images table on both stores.
2. **Phase 2** — interface changes FIRST: `Model.idempotency_key`, `run_turn` hooks, mode-divergent `ToolContext`, externalized audit transaction. These are prerequisites for both adapters and tests.
3. **Phase 3** — Supabase store (with new methods), Storage blob adapter, Discord transport, resident runner, reconciler (the runner needs the reconciler for startup recovery).
4. **Phase 4** — image tools and Anthropic vision wiring; resident CLI subcommand.
5. **Phase 5** — tests interleave per phase, but the integration tests in Step 21 land last because they exercise the whole stack.

## Validation Order

1. Cheapest first: existing Sprint 1a tests (must still pass unmodified).
2. New unit tests (Step 20): hooks, external queue ordering, coalescer, whitelist, status formatter, reconciler, image tools.
3. Sprint 1b contract test against both stores (Step 20.4 + Step 20.3).
4. Resident integration tests (Step 21): recovery, voice, image, status lifecycle, mid-turn, resident `send_message`.
5. Manual smoke against staging — last, info-priority.
