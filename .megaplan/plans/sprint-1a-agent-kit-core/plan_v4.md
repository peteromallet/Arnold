# Implementation Plan: Sprint 1a Agent Kit Core + Invocation Mode

## Overview
The repository is documentation-only (`planning-bot-spec.md` plus `ideas/`). Sprint 1a bootstraps a Python 3.11 package matching the spec's locked Sprint 1a surface: `agent_kit` with `ports.py`, `loop.py`, `tool_kit.py`, `ledger.py`; the locked public Python import path `from megaplan.arnold import run_turn, arun_turn, Envelope`; an `arnold` CLI; SQLite store; Anthropic model adapter (offline-mockable); the minimal tool surface `send_message`, `set_activity`, `defer_to_caller`.

Use `argparse` and the `anthropic` SDK behind a `Model` port so tests run fully offline. Do **not** commit the Supabase service key from the idea file anywhere; SQLite is the only store implementation in this sprint.

**Settled scope (carried forward, do not relitigate):**
- Attachments are deferred to Sprint 1b per user-resolved tiebreaker (SD-010). The `Blob` port ships in 1a so 1b can drop in implementations; no `--attach`, no Python `attachments=`, no `LocalBlobStore`, no attachment ingestion or tests.
- `megaplan` is a regular owned package with its own `__init__.py` (SD-011); the megaplan harness this repo runs inside is a separate distribution and does not collide.
- `external_requests` ships in 1a with the loop recording the main Anthropic call (SD-012); reconciliation logic lands in 1b.

**This revision:** completes the `external_requests` schema to match the spec exactly (so 1b reconciliation needs no migration churn) and distinguishes the lifecycle states `pending`, `confirmed`, `failed`, `orphaned` so observable provider errors are not indistinguishable from crash-before-confirmation rows.

## Phase 1: Project Skeleton, Public Contract, and Ports

### Step 1: Add Python project metadata (`pyproject.toml`)
**Scope:** Small
1. Define package metadata, Python `>=3.11`, runtime dependency on `anthropic`, test deps on `pytest` and `jsonschema`.
2. Declare three import packages owned by this repo: `agent_kit`, `arnold`, and `megaplan` (regular package with own `__init__.py`, hosting only `megaplan.arnold`). **Not** a PEP 420 namespace package.
3. Console script entry point `arnold = arnold.cli:main`.
4. Configure pytest defaults so tests are discoverable under `tests/`.

### Step 2: Define envelope contract (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Medium
1. Add `Envelope`, `StateDelta`, `Event`, and error dataclasses matching the spec's Subagent Contract.
2. Stable JSON serialization (sorted keys, compact separators).
3. `outcome` enum: `completed`, `blocked_on_caller`, `errored`, `aborted`.
4. `serialize_for_diff(envelope)` strips spec-declared non-deterministic fields (`reply`, per-event `text`, `started_at`/`completed_at`). Used **only** for CLI↔Python envelope-equivalence tests, not for stream-vs-envelope comparison.
5. JSON schema and validation tests in `tests/test_envelope.py`.

### Step 3: Define ports (`agent_kit/ports.py`)
**Scope:** Medium
1. Add `Transport`, `Store`, `Model`, and `Blob` Protocols.
2. `Store` Sprint-1a methods: create/load message, create/update turn, record tool call, log system event, acquire/release per-epic lock, load hot context, and `external_requests` insert/update primitives covering the full spec lifecycle (`pending → confirmed | failed | orphaned`).
3. `Model.complete_turn(...)` accepts a model id string parameter and returns a result that the loop can inspect for provider-error vs success — the adapter signals the difference (provider returned an error response → `ProviderError` with `error_details`; transport/SDK exception → raised exception). The protocol is therefore neutral about how the model is called but explicit about how errors are surfaced.
4. `Blob` defines `put(epic_id, content, mime_type) -> BlobRef` and `get(ref) -> bytes`. **No implementation in 1a** — port only.

### Step 4: Lock public Python API (`megaplan/__init__.py`, `megaplan/arnold/__init__.py`, `arnold/__init__.py`)
**Scope:** Small
1. `agent_kit.loop.run_turn` (filled in Step 12) is the single source of truth.
2. Re-export `run_turn`, `arun_turn`, and `Envelope` from `megaplan.arnold` so `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves exactly as the spec requires.
3. `arun_turn` is a thin `asyncio.to_thread(run_turn, ...)` coroutine with identical signature/semantics.
4. Re-export the same names from `arnold/__init__.py` so the CLI package shares the locked surface.

## Phase 2: SQLite Store, Ledger, and Logging

### Step 5: Create SQLite migrations (`agent_kit/store/migrations/sqlite/001_core.sql`)
**Scope:** Medium
1. Create Sprint 1a tables: `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`.
2. Create `external_requests` with the **full spec schema** (no field omissions — keeps 1b reconciliation drop-in compatible):
   - `id`, `idempotency_key` (TEXT, UNIQUE, NOT NULL)
   - `provider` (TEXT — `'anthropic'|'openai'|'groq'|'github'|'discord'|'supabase_storage'`)
   - `endpoint` (TEXT — e.g. `'POST /v1/messages'`)
   - `tool_call_id` (TEXT, nullable FK to `tool_calls`; NULL for system-level calls)
   - `turn_id` (TEXT, nullable FK to `bot_turns`)
   - `request_summary` (JSON text — request shape, not full body)
   - `status` (TEXT — `'pending'|'sent'|'confirmed'|'failed'|'orphaned'`)
   - `provider_request_id` (TEXT, nullable)
   - `provider_response_summary` (JSON text, nullable)
   - `attempt_count` (INTEGER, default 1)
   - `first_attempted_at`, `last_attempted_at`, `completed_at` (timestamps; `completed_at` nullable)
   - `error_details` (JSON text, nullable)
3. Indexes per spec: `UNIQUE(idempotency_key)`, `(provider, status, last_attempted_at)`, `(status, last_attempted_at)`, `(turn_id)`, `(tool_call_id)`.
4. JSON text columns for arrays/json with application-layer validation.
5. Include nullable resident-mode columns referenced by Sprint 1a (`status_message_id`, `current_activity`, message attachment-flag columns left default-false, `bot_turn_id` on `messages`).
6. Other cheap indexes: `messages(epic_id, sent_at)`, `tool_calls(turn_id)`.

### Step 6: Implement SQLite store adapter (`agent_kit/store/sqlite.py`)
**Scope:** Large
1. Auto-apply migrations for a DB path or live connection.
2. Per-epic lock via `epic_locks` row with 60s timeout surfaced as an `epic_locked` errored envelope.
3. Persist inbound messages, outbound invocation messages (synthetic `discord_message_id = inv_<turn_id>_<n>`), bot turns, tool calls, system logs.
4. `transaction()` context manager so tool audit rows and DB mutations commit atomically.
5. `external_requests` CRUD covering the full lifecycle:
   - `insert_pending(...)` — writes `status='pending'`, idempotency_key, request_summary, attempt_count=1, first_attempted_at=last_attempted_at=now.
   - `mark_confirmed(request_id, provider_request_id, provider_response_summary)` — sets `status='confirmed'`, `completed_at=now`.
   - `mark_failed(request_id, error_details)` — sets `status='failed'`, populates `error_details`, sets `completed_at=now`.
   - No reconciliation logic; the spec's `orphaned` transition lands in 1b but the column accepts the value so 1b can write it without migration.

### Step 7: Add ledger skeleton (`agent_kit/ledger.py`)
**Scope:** Small
1. `Ledger` class wrapping `Store`'s `external_requests` primitives:
   - `record_pending(provider, endpoint, request_summary, *, turn_id, tool_call_id=None) -> (request_id, idempotency_key)`. The idempotency key follows the spec exactly: for tool-call-driven requests, `sha256(turn_id + ":" + tool_call_id + ":" + provider + ":" + endpoint + ":" + canonical_args)[:16]`; for system requests, `sha256(turn_id + ":system:" + provider + ":" + endpoint)[:16]`.
   - `mark_confirmed(request_id, provider_request_id, provider_response_summary)`.
   - `mark_failed(request_id, error_details)`.
2. `reconcile_on_boot(store)` — documented no-op stub emitting one `info` `system_logs` row; per-provider reconciliation logic lands in Sprint 1b.
3. `run_turn` (Step 12) calls `record_pending(provider='anthropic', endpoint='POST /v1/messages', turn_id=<turn>, tool_call_id=None, request_summary=...)` immediately before each main Anthropic `Model.complete_turn(...)` call. After the call:
   - On success → `mark_confirmed(...)`.
   - On observable provider error (the adapter raised `ProviderError` carrying `error_details`) → `mark_failed(...)`. The turn ends `errored`.
   - On crash/transport exception → row stays `pending` for Sprint 1b reconciliation. The turn ends `errored`.
4. Decision recorded: per-provider reconciliation logic and the recovery scan are Sprint 1b; the schema and three-state lifecycle ship today so 1b only adds reconciliation, not columns.

### Step 8: Add centralized logger (`agent_kit/logging.py`)
**Scope:** Small
1. `log(store, level, category, event_type, message, **context)` writes through the `Store` to `system_logs`.
2. Use it for model-call metadata, tool-call errors, lock contention; never `print` outside the CLI's stdout/stderr contract.

## Phase 3: Tool Kit and Tools

### Step 9: Build tool registry and audit wrapper (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. Registry mapping tool names to Python callables and JSON-schema metadata.
2. Audit wrapper records `tool_calls` rows with arguments, result, duration, `operation_kind`, and emits a corresponding `Event` into the in-memory event list. The exact event object is the same instance appended to the envelope, delivered to `on_event`, and emitted to NDJSON streaming — no per-channel mutation.
3. DB-mutating tools share one `store.transaction()` for the mutation plus the `tool_calls` row.
4. `tests/test_tool_kit.py`: rollback tests where injected failure leaves neither the mutation nor the audit row.

### Step 10: Implement minimal tools (`agent_kit/tools/communication.py`)
**Scope:** Medium
1. `send_message(content, attach_files=None)`: append to the turn's reply buffer, write outbound `messages` row with synthetic `discord_message_id`, return that id. Emit a `tool_call` event. (`attach_files` accepted for spec parity; no-op in 1a.)
2. `set_activity(description)`: validate `len <= 80` (truncate longer with a warning logged); emit an `activity` event only. Do **not** mutate `bot_turns.current_activity` in invocation mode.
3. `defer_to_caller(questions, reason=None)`: set turn outcome to `blocked_on_caller`, populate envelope `questions`, write the `tool_calls` row, stop the loop cleanly.
4. Each tool call appears in both `tool_calls` and the envelope `events` array.

## Phase 4: Model Adapter and Turn Loop

### Step 11: Implement model port adapters (`agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`)
**Scope:** Medium
1. `AnthropicModel(model_id="claude-opus-4-7")` constructor argument; never hardcoded. CLI reads `ARNOLD_MODEL_ID` from env in `arnold/cli.py` only.
2. Convert registered tools into Anthropic tool definitions.
3. **Error surface:** the adapter distinguishes two failure modes. (a) The Anthropic API returned a structured error response (4xx/5xx body parsed) → adapter raises `ProviderError(error_details=<dict>, provider_request_id=<str|None>)`. (b) The SDK or transport raised before/instead of a parseable response (network, timeout, malformed) → the underlying exception propagates unchanged. The loop maps (a) to `mark_failed` and (b) to crash-pending semantics.
4. Summarise request/response into `bot_turns.prompt_snapshot` and `bot_turns.reasoning`; never log secrets.
5. `FakeModel(seed=...)` returns deterministic, scripted tool-use sequences. It also supports scripting either failure mode for tests (raise `ProviderError` or raise a generic exception).

### Step 12: Implement `run_turn` (`agent_kit/loop.py`)
**Scope:** Large
1. Acquire per-epic lock; if contended return `errored` envelope with `error.code='epic_locked'`.
2. Persist inbound message; create `bot_turns` row with `status='in_progress'`. **No attachment processing in 1a.**
3. Load minimal hot context (epic row, recent messages, recent tool calls).
4. For each main `Model.complete_turn(...)` call: call `Ledger.record_pending(provider='anthropic', endpoint='POST /v1/messages', turn_id=<turn>, tool_call_id=None, request_summary={...})` first; on success call `mark_confirmed(...)`; on `ProviderError` call `mark_failed(error_details=...)` and end the turn `errored`; on any other exception, leave the row `pending` for 1b reconciliation and end the turn `errored`.
5. Execute requested tools through the audit wrapper until the model returns final text, calls `defer_to_caller`, or errors.
6. If the model returns final text without calling `send_message`, synthesize one `send_message` so `reply` is never empty for `completed`.
7. Compute `state_delta` as a stable empty artifact delta with byte-deterministic structure.
8. Mark turn `completed` / `failed` / `abandoned`, release lock, return byte-stable `Envelope`.
9. `on_event` callback called once per appended event in envelope order.
10. **Abort path:** install a cooperative cancellation flag (set by `arnold.cli` on `SIGINT` or by the Python caller via an optional `cancel_event: threading.Event` argument). Between tool steps, check the flag; if set, mark `bot_turns.status='abandoned'`, release the lock, and return an envelope with `outcome='aborted'`. Both `bot_turns.status='abandoned'` (records "turn cut short") and envelope `outcome='aborted'` (records "caller cancelled") coexist by design. A valid envelope still prints to stdout.

## Phase 5: CLI Invocation Surface

### Step 13: Add CLI package (`arnold/cli.py`)
**Scope:** Medium
1. Implement `arnold turn --epic <id> [--input "text" | --from-stdin] [--stream-events] [--store sqlite|supabase] [--db PATH] [--model-id ID]`. **No `--attach` flag in 1a (SD-010).**
2. Install a `SIGINT` handler that sets the cancellation flag passed to `run_turn`, producing an envelope with `outcome='aborted'`.
3. Serialize the final envelope as JSON on stdout for **every** outcome.
4. When `--stream-events` is set, emit each event to stderr as one NDJSON line at the moment it is appended to the envelope's `events` list. Streamed lines are byte-identical to the envelope's `events` array (same encoder, same objects, same order).
5. Exit codes: `completed=0`, `errored=1`, `blocked_on_caller=2`, `aborted=3`.
6. `--store supabase` returns `errored` envelope (`error.code='unsupported_store'`) until Sprint 1b.
7. CLI is a thin wrapper: option parsing, store/model construction, signal handling, envelope/exit-code serialization. All orchestration lives in `agent_kit.loop`.

## Phase 6: Verification

### Step 14: Unit tests (`tests/test_envelope.py`, `tests/test_tool_kit.py`, `tests/store_contract.py`, `tests/test_sqlite_store.py`)
**Scope:** Medium
1. Validate envelope dataclass serialization against the JSON schema.
2. `tests/store_contract.py` is a parametrized, store-agnostic suite taking a `store_factory` fixture; `tests/test_sqlite_store.py` parametrizes it with the SQLite factory. Sprint 1b reuses the module unchanged with a Supabase factory.
3. Verify tool audit atomicity (mutation + `tool_calls` row commit-or-roll-back together) and event shape.
4. Cover the full `external_requests` lifecycle: `insert_pending`, `mark_confirmed`, `mark_failed`. Assert idempotency-key uniqueness constraint rejects duplicates. Assert all spec columns exist (`endpoint`, `turn_id`, `provider_request_id`, `provider_response_summary`, `attempt_count`, `completed_at`, `error_details`).

### Step 15: Integration tests (`tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_megaplan_arnold_import.py`, `tests/test_ledger.py`)
**Scope:** Large
1. Full receive → reason → respond cycle with `FakeModel` driving scripted tool calls. One `bot_turns` row per turn, one `tool_calls` row per executed tool, envelope `events` matches `tool_calls`.
2. **Determinism:**
   - `state_delta` byte-identical across two runs with same input + same SQLite state + same `FakeModel(seed=...)`. Unconditional.
   - `serialize_for_diff(envelope)` byte-equivalent between Python `run_turn(...)` and CLI `arnold turn ...` for the same fixture. Raw envelope is **not** byte-compared (`reply` and event `text` are non-deterministic per spec).
3. **Streaming equivalence:** with `--stream-events`, parse each NDJSON stderr line and assert the parsed list is byte-identical to the envelope's `events` array (no projection).
4. **All four exit codes** exercised end-to-end via `FakeModel` scripting:
   - `completed` → exit 0.
   - `errored` (tool raises) → exit 1, valid envelope on stdout.
   - `blocked_on_caller` (`defer_to_caller`) → exit 2, envelope `questions` populated.
   - `aborted` (cancellation flag set mid-loop) → exit 3, valid envelope, `bot_turns.status='abandoned'`, envelope `outcome='aborted'`.
5. **Ledger lifecycle (three cases):**
   - **Success path:** one `external_requests` row per main Anthropic call with `tool_call_id IS NULL`, `provider='anthropic'`, `endpoint='POST /v1/messages'`, `turn_id` matches the `bot_turns` row, idempotency_key is the spec-defined SHA256[:16], status transitions `pending → confirmed`, `provider_response_summary` populated.
   - **Provider-error path:** `FakeModel` scripted to raise `ProviderError(error_details={...})`; assert the row is `status='failed'`, `error_details` populated, `completed_at` set, and the turn ends `errored`.
   - **Crash path:** `FakeModel` scripted to raise a plain `RuntimeError`; assert the row remains `status='pending'` with `error_details IS NULL` (so 1b reconciliation can distinguish it from the failed case), and the turn ends `errored`.
6. Import-path test: `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves to the same callables as `agent_kit.loop`; `arun_turn` is a coroutine.
7. Finish with full `pytest`.

## Execution Order
1. `pyproject.toml`, package directories, envelope contract.
2. Lock `megaplan.arnold` public surface alongside ports.
3. SQLite migrations (full `external_requests` schema), store, ledger skeleton, logger.
4. Tool registry, minimal tools.
5. Model adapter (with `ProviderError` discrimination) and `run_turn` (with abort path and three-state ledger wiring) before the CLI.
6. CLI as a thin serialization, signal-handling, exit-code layer.
7. Broad integration tests after unit-level store/tool behavior is proven.

## Validation Order
1. `pytest tests/test_envelope.py tests/test_megaplan_arnold_import.py`
2. `pytest tests/test_sqlite_store.py tests/test_tool_kit.py`
3. `pytest tests/test_run_turn.py tests/test_ledger.py`
4. `pytest tests/test_cli.py`
5. `pytest` for the full suite.

## Notes for Reviewers
- The Supabase service key in the idea file must **not** be committed anywhere downstream.
- Attachments deferred per SD-010 (settled scope decision); the `Blob` port survives so 1b can drop in implementations.
- `external_requests` ships with the full spec schema (idempotency key includes `endpoint` per spec) and three of the four lifecycle states (`pending`, `confirmed`, `failed`); `orphaned` is a valid value that 1b reconciliation will write — no migration needed.
- Provider errors observable from the Anthropic SDK end as `status='failed'` with `error_details`; only true crashes/transport exceptions leave rows `pending`. This makes 1b reconciliation able to tell the difference.
- Streaming NDJSON is byte-identical to the envelope's `events` array; `serialize_for_diff` is used only for CLI↔Python envelope equivalence.
- Abort: `bot_turns.status='abandoned'` + envelope `outcome='aborted'` coexist; valid envelope still prints with exit code 3.
