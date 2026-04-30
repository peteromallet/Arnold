# Implementation Plan: Sprint 1a Agent Kit Core + Invocation Mode

## Overview
The repository is documentation-only (`planning-bot-spec.md` plus `ideas/`). Sprint 1a bootstraps a Python 3.11 package matching the spec's locked Sprint 1a surface: `agent_kit` with `ports.py`, `loop.py`, `tool_kit.py`, `ledger.py`; the locked public Python import path `from megaplan.arnold import run_turn, arun_turn, Envelope`; an `arnold` CLI; SQLite store; Anthropic model adapter (offline-mockable); the minimal tool surface `send_message`, `set_activity`, `defer_to_caller`.

Use `argparse` and the `anthropic` SDK behind a `Model` port so tests run fully offline. Do **not** commit the Supabase service key from the idea file anywhere; SQLite is the only store implementation in this sprint.

**Scope narrowing (this revision):** Per the user's sprint idea, *attachments* are out of scope for Sprint 1a. The `Blob` port is defined (the idea lists it) but no `LocalBlobStore`, `--attach`, Python `attachments=`, or attachment ingestion ships in 1a. The CLI and `run_turn` do not accept attachment arguments. Attachment ingestion (images and audio transcription) lands in Sprint 1b together with the Discord transport that requires it. This resolves the recurring attachment-semantics tension between spec and idea by deferring to the narrower idea.

**Ledger scope (this revision):** The `agent_kit/ledger.py` skeleton ships, the `external_requests` table is created, and `run_turn` writes one `external_requests` row per main Anthropic call (`tool_call_id=null`, `provider='anthropic'`) — `pending` before the call, `confirmed` after. No reconciliation logic; that ships with Sprint 1b.

## Phase 1: Project Skeleton, Public Contract, and Ports

### Step 1: Add Python project metadata (`pyproject.toml`)
**Scope:** Small
1. Define package metadata, Python `>=3.11`, runtime dependency on `anthropic`, test dependencies on `pytest` and `jsonschema`.
2. Declare three import packages owned by this repo: `agent_kit`, `arnold`, and `megaplan` (regular package with own `__init__.py`, hosting only `megaplan.arnold`). Decision: regular owned package, **not** a PEP 420 namespace package — this repo is `arnold-v2` and has no other `megaplan/` directory; the megaplan *harness* the repo runs inside is a separate distribution and does not collide at import time inside this project's venv.
3. Add console script entry point `arnold = arnold.cli:main`.
4. Configure pytest defaults so tests are discoverable under `tests/`.

### Step 2: Define envelope contract (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Medium
1. Add `Envelope`, `StateDelta`, `Event`, and error dataclasses matching the spec's Subagent Contract.
2. Implement stable JSON serialization with sorted keys and compact separators.
3. `outcome` enum: `completed`, `blocked_on_caller`, `errored`, `aborted`.
4. Provide a `serialize_for_diff(envelope)` helper that strips fields the spec marks non-deterministic (`reply`, per-event `text`, `started_at`/`completed_at` timestamps). This helper is used **only** for CLI↔Python envelope-equivalence tests, **not** for stream-vs-envelope event comparison (see Step 16).
5. JSON schema and validation tests in `tests/test_envelope.py`.

### Step 3: Define ports (`agent_kit/ports.py`)
**Scope:** Medium
1. Add `Transport`, `Store`, `Model`, and `Blob` Protocols.
2. `Store` Sprint-1a methods: create/load message, create/update turn, record tool call, log system event, acquire/release per-epic lock, load hot context, and `external_requests` insert/update primitives.
3. `Model.complete_turn(...)` accepts a model id string parameter; the model id is **not** baked into the protocol.
4. `Blob` defines `put(epic_id, content, mime_type) -> BlobRef` and `get(ref) -> bytes`. **No implementation ships in 1a** — the port is defined so Sprint 1b can drop in `LocalBlobStore` / `SupabaseBlobStore` without touching the protocol.

### Step 4: Lock public Python API (`megaplan/__init__.py`, `megaplan/arnold/__init__.py`, `arnold/__init__.py`)
**Scope:** Small
1. `agent_kit.loop.run_turn` (filled in Step 11) is the single source of truth.
2. Re-export `run_turn`, `arun_turn`, and `Envelope` from `megaplan.arnold` so `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves exactly as the spec requires.
3. `arun_turn` is a thin `asyncio.to_thread(run_turn, ...)` coroutine with identical signature/semantics. Async-native rewrite is out of scope for Sprint 1a (all I/O is local SQLite plus mocked model in tests).
4. Re-export the same names from `arnold/__init__.py` so the CLI package shares the locked surface.

## Phase 2: SQLite Store, Ledger, and Logging

### Step 5: Create SQLite migrations (`agent_kit/store/migrations/sqlite/001_core.sql`)
**Scope:** Medium
1. Create Sprint 1a tables: `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`, and a Sprint-1a-minimal `external_requests` (`id`, `tool_call_id` nullable, `provider`, `idempotency_key`, `status`, `request_summary`, `created_at`, `last_attempted_at`, `confirmed_at`, `provider_metadata` JSON).
2. JSON text columns for arrays/json with application-layer validation.
3. Include nullable resident-mode columns referenced by Sprint 1a (`status_message_id`, `current_activity`, message attachment-flag columns left default-false, `bot_turn_id` on `messages`).
4. Cheap indexes: `messages(epic_id, sent_at)`, `tool_calls(turn_id)`, `external_requests(status, last_attempted_at)`.

### Step 6: Implement SQLite store adapter (`agent_kit/store/sqlite.py`)
**Scope:** Large
1. Auto-apply migrations for a DB path or live connection.
2. Per-epic lock via `epic_locks` row with 60s timeout surfaced as an `epic_locked` errored envelope.
3. Persist inbound messages, outbound invocation messages (synthetic `discord_message_id = inv_<turn_id>_<n>`), bot turns, tool calls, system logs.
4. `transaction()` context manager so tool audit rows and DB mutations commit atomically; the tool wrapper (Step 9) uses it.
5. `external_requests` CRUD: `insert_pending(...)`, `mark_confirmed(...)`. No reconciliation logic.

### Step 7: Add ledger skeleton (`agent_kit/ledger.py`)
**Scope:** Small
1. `Ledger` class wrapping `Store`'s `external_requests` primitives: `record_pending(provider, idempotency_key, request_summary, tool_call_id=None) -> request_id` and `mark_confirmed(request_id, provider_metadata)`.
2. `reconcile_on_boot(store)` is a documented no-op stub that emits one `info` `system_logs` row; per-provider reconciliation lands in Sprint 1b.
3. `run_turn` (Step 11) calls `ledger.record_pending(provider='anthropic', tool_call_id=None, ...)` immediately before each main Anthropic `Model.complete_turn(...)` call and `mark_confirmed(...)` immediately after. This satisfies the spec's invariant that the loop's main LLM request is recorded as a system-level `external_requests` row even when the tool surface itself makes no external calls.
4. Decision recorded: per-provider reconciliation logic, idempotency-key replay, and post-hoc reconciliation passes are Sprint 1b.

### Step 8: Add centralized logger (`agent_kit/logging.py`)
**Scope:** Small
1. `log(store, level, category, event_type, message, **context)` writes through the `Store` to `system_logs`.
2. Use it for model-call metadata, tool-call errors, and lock contention; never `print` outside the CLI's stdout/stderr contract.

## Phase 3: Tool Kit and Tools

### Step 9: Build tool registry and audit wrapper (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. Registry mapping tool names to Python callables and JSON-schema metadata.
2. Audit wrapper records `tool_calls` rows with arguments, result, duration, `operation_kind`, and emits a corresponding `Event` into the in-memory event list. The exact event object appended to the envelope is the **same object** delivered to `on_event` and emitted to NDJSON streaming — no per-channel mutation.
3. DB-mutating tools share one `store.transaction()` for the mutation plus the `tool_calls` row.
4. `tests/test_tool_kit.py`: rollback tests where injected failure leaves neither the mutation nor the audit row.

### Step 10: Implement minimal tools (`agent_kit/tools/communication.py`)
**Scope:** Medium
1. `send_message(content, attach_files=None)`: append to the turn's reply buffer, write outbound `messages` row with synthetic `discord_message_id`, return that id. Emit a `tool_call` event. (`attach_files` is accepted as the spec parameter shape but is a no-op in 1a since attachments are out of scope.)
2. `set_activity(description)`: validate `len <= 80` (truncate longer with a warning logged), and **only** emit an `activity` event. Per spec mode-divergent semantics, do **not** mutate `bot_turns.current_activity` in invocation mode.
3. `defer_to_caller(questions, reason=None)`: set turn outcome to `blocked_on_caller`, populate envelope `questions`, write the `tool_calls` row, stop the loop cleanly.
4. Each tool call appears in both `tool_calls` and the envelope `events` array.

## Phase 4: Model Adapter and Turn Loop

### Step 11: Implement model port adapters (`agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`)
**Scope:** Medium
1. `AnthropicModel(model_id="claude-opus-4-7")` constructor argument; the adapter never hardcodes the id. The CLI reads `ARNOLD_MODEL_ID` from env in `arnold/cli.py` only.
2. Convert registered tools into Anthropic tool definitions.
3. Summarise request/response into `bot_turns.prompt_snapshot` and `bot_turns.reasoning`; never log secrets.
4. `FakeModel(seed=...)` returns a deterministic, scripted sequence of tool-use turns; all integration tests use it so the suite stays offline.

### Step 12: Implement `run_turn` (`agent_kit/loop.py`)
**Scope:** Large
1. Acquire per-epic lock; if contended return `errored` envelope with `error.code='epic_locked'`.
2. Persist inbound message; create `bot_turns` row with `status='in_progress'`. **No attachment processing in 1a.**
3. Load minimal hot context (epic row, recent messages, recent tool calls).
4. Wrap each main `Model.complete_turn(...)` call with `Ledger.record_pending(provider='anthropic', tool_call_id=None, idempotency_key=<deterministic>, request_summary=<short>)` before, `mark_confirmed(...)` after. On model exception, the `external_requests` row stays `pending` for Sprint 1b reconciliation; the turn's envelope is `errored`.
5. Execute requested tools through the audit wrapper until the model returns final text, calls `defer_to_caller`, or errors.
6. If the model returns final text without calling `send_message`, synthesize one `send_message` so `reply` is never empty for `completed`.
7. Compute `state_delta` as a stable empty artifact delta with byte-deterministic structure.
8. Mark turn `completed` / `failed` / `abandoned`, release lock, return byte-stable `Envelope`.
9. Support `on_event` callback called once per appended event in envelope order.
10. **Abort path:** install a cooperative cancellation flag (set by `arnold.cli` on `SIGINT` or by the Python caller via an optional `cancel_event: threading.Event` argument). Between tool steps, check the flag; if set, mark `bot_turns.status='abandoned'`, release the lock, and return an envelope with `outcome='aborted'`. The `bot_turns` row's `abandoned` status and the envelope's `aborted` outcome coexist by design — the row records "this turn was cut short", the envelope records "the caller cancelled". A valid envelope still prints to stdout.

## Phase 5: CLI Invocation Surface

### Step 13: Add CLI package (`arnold/cli.py`)
**Scope:** Medium
1. Implement `arnold turn --epic <id> [--input "text" | --from-stdin] [--stream-events] [--store sqlite|supabase] [--db PATH] [--model-id ID]`. **No `--attach` flag in 1a.**
2. Install a `SIGINT` handler that sets the cancellation flag passed to `run_turn`, producing an envelope with `outcome='aborted'`.
3. Serialize the final envelope as JSON on stdout for **every** outcome, including `errored` and `aborted`.
4. When `--stream-events` is set, emit each event to stderr as one NDJSON line at the moment it is appended to the envelope's `events` list. The streamed lines are byte-identical to the envelope's `events` array (same JSON encoder, same objects, same order).
5. Exit codes: `completed=0`, `errored=1`, `blocked_on_caller=2`, `aborted=3`.
6. `--store supabase` returns `errored` envelope (`error.code='unsupported_store'`) until Sprint 1b — never silently fall back.
7. CLI is a thin wrapper: option parsing, store/model construction, signal handling, envelope/exit-code serialization. All orchestration in `agent_kit.loop`.

## Phase 6: Verification

### Step 14: Unit tests (`tests/test_envelope.py`, `tests/test_tool_kit.py`, `tests/store_contract.py`, `tests/test_sqlite_store.py`)
**Scope:** Medium
1. Validate envelope dataclass serialization against the JSON schema.
2. Structure `tests/store_contract.py` as a parametrized, store-agnostic contract suite taking a `store_factory` fixture; `tests/test_sqlite_store.py` parametrizes it with the SQLite factory. Sprint 1b reuses the module unchanged with a Supabase factory.
3. Verify tool audit atomicity (mutation + `tool_calls` row commit-or-roll-back together) and event shape.
4. Cover `external_requests` insert/confirm primitives.

### Step 15: Integration tests (`tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_megaplan_arnold_import.py`, `tests/test_ledger.py`)
**Scope:** Large
1. Full receive → reason → respond cycle with `FakeModel` driving scripted tool calls. Assert one `bot_turns` row per turn, one `tool_calls` row per executed tool, envelope `events` matches `tool_calls`.
2. **Determinism:**
   - `state_delta` byte-identical across two runs with same input + same SQLite state + same `FakeModel(seed=...)`. Unconditional.
   - `serialize_for_diff(envelope)` byte-equivalent between Python `run_turn(...)` and CLI `arnold turn ...` for the same fixture. Raw envelope is **not** byte-compared because `reply` and event `text` are spec-declared non-deterministic.
3. **Streaming equivalence:** with `--stream-events`, parse each NDJSON stderr line and assert the parsed list is byte-identical to the envelope's `events` array (no `serialize_for_diff` projection — they are the same objects encoded by the same encoder; any difference is a real bug).
4. **All four exit codes** exercised end-to-end, each driven by `FakeModel` scripting:
   - `completed`: model returns final text → exit 0.
   - `errored`: tool raises → exit 1, valid envelope on stdout.
   - `blocked_on_caller`: model calls `defer_to_caller` → exit 2, envelope `questions` populated.
   - `aborted`: cancellation flag set mid-loop → exit 3, valid envelope on stdout, `bot_turns.status='abandoned'`, envelope `outcome='aborted'`.
5. **Ledger:** assert one `external_requests` row per main Anthropic call with `tool_call_id IS NULL`, `provider='anthropic'`, status transitioning `pending → confirmed`. On forced model exception assert the row remains `pending` and the turn ends `errored`.
6. Import-path test: `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves to the same callables as `agent_kit.loop`; `arun_turn` is a coroutine.
7. Finish with full `pytest`.

## Execution Order
1. `pyproject.toml`, package directories, envelope contract.
2. Lock `megaplan.arnold` public surface alongside ports.
3. SQLite migrations, store, ledger skeleton, logger.
4. Tool registry, minimal tools.
5. Model adapter and `run_turn` (with abort path and main-LLM ledger wiring) before the CLI.
6. CLI as a thin serialization, signal-handling, exit-code layer.
7. Broad integration tests after unit-level store/tool behavior is proven.

## Validation Order
1. `pytest tests/test_envelope.py tests/test_megaplan_arnold_import.py`
2. `pytest tests/test_sqlite_store.py tests/test_tool_kit.py`
3. `pytest tests/test_run_turn.py tests/test_ledger.py`
4. `pytest tests/test_cli.py`
5. `pytest` for the full suite.

## Notes for Reviewers
- The Supabase service key in the idea file must **not** be committed to code, tests, fixtures, logs, or downstream prompts.
- Attachments are deferred to Sprint 1b (alongside Discord). The `Blob` port ships in 1a so 1b can land implementations without changing the protocol.
- `external_requests` records the main Anthropic call in 1a; per-provider reconciliation and the recovery scan land in 1b.
- Streaming NDJSON is byte-identical to the envelope's `events` array; the `serialize_for_diff` projection is used **only** for CLI↔Python envelope equivalence, not for stream comparisons.
- Abort: `bot_turns.status='abandoned'` + envelope `outcome='aborted'` coexist; envelope still prints to stdout with exit code 3.
