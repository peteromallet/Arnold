# Implementation Plan: Sprint 1a Agent Kit Core + Invocation Mode

## Overview
The repository is currently documentation-only (`planning-bot-spec.md` plus sprint idea files). Sprint 1a bootstraps a Python 3.11 package from scratch around the spec's locked Sprint 1a contract: `agent_kit` with `ports.py`, `loop.py`, `tool_kit.py`, `ledger.py`; the locked public Python import path `from megaplan.arnold import run_turn, arun_turn, Envelope`; an `arnold` CLI; SQLite store; Anthropic model adapter (offline-mockable); the minimal tool surface `send_message`, `set_activity`, `defer_to_caller`; and invocation-mode attachment passing through a local `BlobStore`.

Use `argparse` (no Click) and the `anthropic` SDK behind a `Model` port so tests run fully offline. Do **not** commit the Supabase service key from the idea file anywhere; SQLite is the only store implementation in this sprint.

## Phase 1: Project Skeleton, Public Contract, and Ports

### Step 1: Add Python project metadata (`pyproject.toml`)
**Scope:** Small
1. Define package metadata, Python `>=3.11`, runtime dependency on `anthropic`, test dependencies on `pytest` and `jsonschema`.
2. Declare two import packages: `agent_kit` and `megaplan` (namespace-style for the `megaplan.arnold` re-export only).
3. Add console script entry point `arnold = arnold.cli:main`.
4. Configure pytest defaults so tests are discoverable under `tests/`.

### Step 2: Define envelope contract (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Medium
1. Add `Envelope`, `StateDelta`, `Event`, and error dataclasses matching the spec's Subagent Contract.
2. Implement stable JSON serialization with sorted keys and compact separators so deterministic fields can be byte-compared.
3. Add `outcome` enum values: `completed`, `blocked_on_caller`, `errored`, `aborted`.
4. Provide a `serialize_for_diff(envelope)` helper that strips fields the spec marks non-deterministic (`reply`, per-event `text`, timestamps such as `started_at`/`completed_at`, and any model-generated free text), used by tests for byte-equivalence assertions.
5. Add JSON schema and validation tests in `tests/test_envelope.py`.

### Step 3: Define ports (`agent_kit/ports.py`)
**Scope:** Medium
1. Add `Transport`, `Store`, `Model`, and `Blob` Protocols.
2. Keep `Store` methods narrow and Sprint-1a-specific: create/load message, create/update turn, record tool call, log system event, acquire/release per-epic lock, load hot context, and minimal `external_requests` insert/list/update primitives (the ledger surface is exposed but reconciliation logic is deferred — see Step 7).
3. `Model.complete_turn(...)` accepts a model id string parameter; the model id is **not** baked into the protocol.
4. `Blob` defines `put(epic_id, content, mime_type) -> BlobRef` and `get(ref) -> bytes`; the `BlobRef` includes the sha256 used for `(epic_id, sha256)` natural deduplication.

### Step 4: Lock public Python API (`megaplan/__init__.py`, `megaplan/arnold/__init__.py`, `arnold/__init__.py`)
**Scope:** Small
1. Implement `agent_kit.loop.run_turn` (filled in Step 11) as the single source of truth.
2. Re-export `run_turn`, `arun_turn`, and `Envelope` from `megaplan.arnold` so the spec's documented import path works exactly: `from megaplan.arnold import run_turn, arun_turn, Envelope`.
3. Implement `arun_turn` as a thin `asyncio.to_thread(run_turn, ...)` coroutine with identical signature and semantics, per the spec.
4. Re-export the same names from `arnold/__init__.py` so the CLI package shares the locked surface.

## Phase 2: SQLite Store, Ledger, and Logging

### Step 5: Create SQLite migrations (`agent_kit/store/migrations/sqlite/001_core.sql`)
**Scope:** Medium
1. Create Sprint 1a tables: `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`, and a minimal `external_requests` table with columns sufficient for invocation-mode insert/list/confirm (`id`, `tool_call_id`, `provider`, `idempotency_key`, `status`, `request_summary`, `created_at`, `last_attempted_at`, `confirmed_at`).
2. Use SQLite-compatible JSON text columns for arrays/json with application-layer validation.
3. Include nullable resident-mode columns referenced by Sprint 1a behavior (`status_message_id`, `current_activity`, message attachment fields, `bot_turn_id` on `messages`).
4. Add indexes from the spec where cheap and relevant (e.g., `messages(epic_id, sent_at)`, `tool_calls(turn_id)`, `external_requests(status, last_attempted_at)`).

### Step 6: Implement SQLite store adapter (`agent_kit/store/sqlite.py`)
**Scope:** Large
1. Apply migrations automatically for a DB path or live connection.
2. Implement per-epic lock acquisition with an `epic_locks` row and a 60s timeout path surfaced as an `epic_locked` errored envelope.
3. Persist inbound messages, outbound invocation messages (with synthetic `discord_message_id = inv_<turn_id>_<n>`), bot turns, tool calls, and system logs.
4. Provide a `transaction()` context manager so tool audit rows and DB mutations commit atomically; expose a hook the tool wrapper uses (Step 8).
5. Implement minimal `external_requests` CRUD (insert pending, mark confirmed) — used by the ledger skeleton in Step 7. Reconciliation logic is **out of scope** for Sprint 1a and explicitly deferred to Sprint 1b.

### Step 7: Add ledger skeleton (`agent_kit/ledger.py`)
**Scope:** Small
1. Provide `Ledger` class wrapping the `Store`'s `external_requests` primitives: `record_pending(tool_call_id, provider, idempotency_key, request_summary)` and `mark_confirmed(request_id, provider_metadata)`.
2. Add a `reconcile_on_boot(store)` no-op stub with a docstring stating Sprint 1b will implement per-provider reconciliation; emit an `info` `system_logs` row on call.
3. Wire `run_turn` (Step 11) to instantiate but not actively use the ledger for Sprint 1a's tool surface (none of `send_message`/`set_activity`/`defer_to_caller` make external calls in invocation mode); document this clearly so Sprint 1b only needs to flip on per-provider logic.
4. Decision recorded explicitly in code and in this plan: the `external_requests` table and ledger surface ship in Sprint 1a as scaffolding to satisfy the locked package layout; reconciliation behavior is Sprint 1b. This resolves the scope tension between the sprint idea and the full spec.

### Step 8: Add centralized logger (`agent_kit/logging.py`)
**Scope:** Small
1. Implement `log(store, level, category, event_type, message, **context)` that writes through the `Store` port to `system_logs`.
2. Use it for model-call metadata, tool-call errors, and lock contention; never `print` outside the CLI's stdout/stderr contract.

## Phase 3: Tool Kit, Tools, and Attachments

### Step 9: Build tool registry and audit wrapper (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. Add a registry that maps tool names to Python callables and JSON-schema metadata.
2. Implement an audit wrapper that records `tool_calls` rows with arguments, result, duration, `operation_kind`, and emits a corresponding `Event` into the in-memory event list for the envelope.
3. DB-mutating tools share one `store.transaction()` for the mutation plus the `tool_calls` row.
4. Add `tests/test_tool_kit.py` with rollback tests where injected failure leaves neither the mutation nor the audit row.

### Step 10: Implement minimal tools (`agent_kit/tools/communication.py`)
**Scope:** Medium
1. `send_message(content, attach_files=None)`: append to the turn's reply buffer, write outbound `messages` row with synthetic `discord_message_id`, and return that id. Emit a `tool_call` event.
2. `set_activity(description)`: validate `len <= 80` (truncate longer with a warning logged), and **only** emit an `activity` event. Per the spec's mode-divergent semantics, do **not** mutate `bot_turns.current_activity` in invocation mode.
3. `defer_to_caller(questions, reason=None)`: set the turn outcome to `blocked_on_caller`, populate envelope `questions`, write the `tool_calls` row, and stop the loop cleanly.
4. Confirm each tool call appears in both `tool_calls` and the envelope `events` array.

### Step 11: Implement local Blob store and attachment ingestion (`agent_kit/blob/local.py`, `agent_kit/attachments.py`)
**Scope:** Medium
1. Provide a `LocalBlobStore` that writes blobs under a configurable directory keyed by `(epic_id, sha256)`, satisfying the `Blob` port.
2. Add `process_attachments(attachments, epic_id, store, blob)` that accepts the spec's Python types: `list[Path | bytes | tuple[bytes, mime_type]]`. For each:
   - Compute sha256, store via `Blob.put`, and insert a row into `messages.has_image_attachment` / `images` placeholder columns where applicable (Sprint 1a stores attachment metadata on the inbound `messages` row only — full `images` table lands later).
   - Detect content type via mime sniff with explicit override; reject unknown types with an `errored` envelope from `run_turn`.
   - Audio path: leave a clear `NotImplementedError` with an `errored` envelope and a `system_logs` warning that transcription lands in Sprint 1b. Document this limitation in the CLI `--help` text and the docstring of `run_turn`.
3. Image path: persist the blob and append an `[Attached image: <ref>]` marker to `input` so the fake model can observe it in tests; the bot's `list_images` tool ships in a later sprint.

## Phase 4: Model Adapter and Turn Loop

### Step 12: Implement model port adapters (`agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`)
**Scope:** Medium
1. Wrap the Anthropic SDK behind `Model.complete_turn(...)`. The model id is a constructor parameter (`AnthropicModel(model_id="claude-opus-4-7")`) and is also overridable via `ARNOLD_MODEL_ID` env var read **only** in `arnold/cli.py` — the adapter and tests never hardcode the id.
2. Convert registered tools into Anthropic tool definitions.
3. Summarize request/response details into `bot_turns.prompt_snapshot` and `bot_turns.reasoning`; never log secrets.
4. Provide `FakeModel` in `agent_kit/model/fake.py` that returns a deterministic, scripted sequence of tool-use turns keyed by a `seed` parameter, used by all integration tests so the suite stays offline.

### Step 13: Implement `run_turn` (`agent_kit/loop.py`)
**Scope:** Large
1. Acquire the per-epic lock; if contended, return an `errored` envelope with `error.code='epic_locked'`.
2. Persist inbound message, run `process_attachments` if `attachments` was passed, and create the `bot_turns` row with `status='in_progress'`.
3. Load minimal hot context (epic row, recent messages, recent tool calls) and call `Model.complete_turn`.
4. Execute requested tools through the audit wrapper until the model returns final text, calls `defer_to_caller`, or errors.
5. If the model returns final text without calling `send_message`, synthesize one `send_message` call so the envelope's `reply` is never accidentally empty for `completed` outcomes.
6. Compute `state_delta` as a stable empty artifact delta with deterministic byte structure ready for Sprint 2.
7. Mark the turn `completed` / `failed` / `abandoned`, release the lock, and return a byte-stable `Envelope`.
8. Support `on_event` callback for streaming, called once per appended event in the same order as the envelope's final `events` array.
9. **Abort path:** install a cooperative cancellation flag (set by `arnold.cli` on `SIGINT` or by the Python caller via a `cancel_event: threading.Event`-style optional argument). Between tool steps, check the flag; if set, mark the turn `abandoned`, release the lock, and return an envelope with `outcome='aborted'`. This makes the `aborted` exit code exercisable end-to-end, not just statically mapped.

## Phase 5: CLI Invocation Surface

### Step 14: Add CLI package (`arnold/cli.py`)
**Scope:** Medium
1. Implement `arnold turn --epic <id> [--input "text" | --from-stdin] [--attach PATH ...] [--stream-events] [--store sqlite|supabase] [--db PATH] [--model-id ID]`.
2. `--attach` is repeatable; each path is read into bytes and passed through to `run_turn(attachments=[...])`.
3. Install a `SIGINT` handler that sets the cancellation flag passed to `run_turn`, producing an `aborted` envelope.
4. Serialize the final envelope as JSON on stdout for every outcome, including errors.
5. Emit NDJSON events to stderr only when `--stream-events` is set; the printed events equal the envelope's `events` array exactly.
6. Map exit codes precisely: `completed=0`, `errored=1`, `blocked_on_caller=2`, `aborted=3`.
7. `--store supabase` returns an `errored` envelope (`error.code='unsupported_store'`) until Sprint 1b — never silently fall back.
8. The CLI is a thin wrapper: option parsing, store/model construction, signal handling, and envelope/exit-code serialization. All orchestration lives in `agent_kit.loop`.

## Phase 6: Verification

### Step 15: Unit tests (`tests/test_envelope.py`, `tests/test_tool_kit.py`, `tests/store_contract.py`, `tests/test_sqlite_store.py`, `tests/test_blob_local.py`)
**Scope:** Medium
1. Validate envelope dataclass serialization against the JSON schema, including the `serialize_for_diff` deterministic projection.
2. Structure `tests/store_contract.py` as a parametrized, store-agnostic contract suite that takes a `store_factory` fixture; `tests/test_sqlite_store.py` parametrizes it with the SQLite factory. Sprint 1b reuses the same contract module unchanged with a Supabase factory.
3. Verify tool audit atomicity (mutation + `tool_calls` row commit-or-roll-back together) and event shape.
4. Verify `LocalBlobStore` deduplicates by `(epic_id, sha256)` and rejects unknown mime types.

### Step 16: Integration tests (`tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_attachments.py`, `tests/test_megaplan_arnold_import.py`)
**Scope:** Large
1. Run a full receive → reason → respond cycle with `FakeModel` driving scripted tool calls. Assert one `bot_turns` row per turn and one `tool_calls` row per executed tool, with envelope `events` matching `tool_calls` rows.
2. **Determinism:**
   - Assert that `state_delta` is byte-identical across two runs with the same input, same SQLite state, and same `FakeModel(seed=...)`. This holds unconditionally per the spec.
   - Assert that the `serialize_for_diff(envelope)` projection (which strips `reply`, per-event `text`, and timestamps) is byte-equivalent between Python `run_turn(...)` and CLI `arnold turn ...` for the same fixture. Do **not** assert byte equivalence over the raw envelope — that would over-assert, since `reply` and `events.text` are explicitly non-deterministic per spec.
3. Assert `--stream-events` stderr NDJSON lines equal the final envelope's `events` array (post-`serialize_for_diff` to absorb any transient text differences).
4. Assert exit codes for all four outcomes by scripting `FakeModel` to drive each: `completed`, `errored` (raise inside a tool), `blocked_on_caller` (call `defer_to_caller`), `aborted` (set the cancellation flag mid-loop and assert exit code 3 plus a valid envelope).
5. Attachment tests: pass an image bytes attachment via Python and via CLI `--attach`, assert the `LocalBlobStore` contains it, the inbound `messages` row reflects the attachment, and the envelope completes; pass an audio attachment and assert a graceful `errored` envelope citing Sprint 1b.
6. Import-path test: `from megaplan.arnold import run_turn, arun_turn, Envelope` succeeds and refers to the same callables exported by `agent_kit.loop`.
7. Finish with full `pytest`.

## Execution Order
1. Land `pyproject.toml`, package directories, and the envelope contract first — every later layer depends on stable serialization.
2. Lock the `megaplan.arnold` public surface alongside ports, before anything imports it, so the import path is wired from day one.
3. Build SQLite migrations, store, ledger skeleton, and logger before the loop so persistence bugs are isolated early.
4. Add the tool registry, minimal tools, and the local Blob/attachment pipeline before the model adapter so the `FakeModel` tests can drive real tool execution and attachments.
5. Wire `run_turn` (including abort path) before the CLI; the CLI is a thin serialization, signal-handling, and exit-code layer.
6. Add broad integration tests only after unit-level store/tool/blob behavior is proven.

## Validation Order
1. `pytest tests/test_envelope.py tests/test_megaplan_arnold_import.py`
2. `pytest tests/test_sqlite_store.py tests/test_tool_kit.py tests/test_blob_local.py`
3. `pytest tests/test_run_turn.py tests/test_attachments.py`
4. `pytest tests/test_cli.py`
5. `pytest` for the full suite.

## Notes for Reviewers
- The Supabase service key in the idea file must **not** be committed to code, tests, fixtures, logs, or downstream prompts.
- The `external_requests` ledger ships as scaffolding only; reconciliation logic is explicitly Sprint 1b.
- Audio attachments return a graceful `errored` envelope in Sprint 1a; transcription lands in Sprint 1b.
- Byte-equivalence is asserted on a deterministic projection of the envelope (`serialize_for_diff`) plus an unconditional byte-equivalence assertion on `state_delta` — this honors the spec's split between deterministic structure and non-deterministic free text.
