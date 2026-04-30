# Implementation Plan: Sprint 1a Agent Kit Core + Invocation Mode

## Overview
The repository is documentation-only (`planning-bot-spec.md` plus `ideas/`). Sprint 1a bootstraps a Python 3.11 package matching the spec's locked Sprint 1a surface: `agent_kit` with `ports.py`, `loop.py`, `tool_kit.py`, `ledger.py`; the locked public Python import path `from megaplan.arnold import run_turn, arun_turn, Envelope`; an `arnold` CLI; SQLite store; Anthropic model adapter (offline-mockable); the minimal tool surface `send_message`, `set_activity`, `defer_to_caller`.

Use `argparse` and the `anthropic` SDK behind a `Model` port so tests run fully offline. Do **not** commit the Supabase service key from the idea file anywhere; SQLite is the only store implementation in this sprint.

**Settled scope (carried forward, do not relitigate):**
- Attachments are deferred to Sprint 1b per SD-010. The `Blob` port ships in 1a; no `--attach`, no Python `attachments=`, no `LocalBlobStore`, no attachment ingestion or tests.
- `megaplan` is a regular owned package per SD-011.
- `external_requests` ships with the full spec schema in 1a per SD-013; reconciliation lands in 1b.
- Anthropic adapter raises `ProviderError` on observable provider errors (→ `mark_failed`); transport/SDK exceptions propagate (→ row stays `pending`) per SD-014.

**This revision** fixes two correctness issues introduced when the schema/lifecycle work landed: (a) idempotency-key collision when the loop makes multiple model calls in one turn (tool-use chaining), and (b) ambiguity about whether `set_activity` emits a `tool_call` or `activity` event.

## Phase 1: Project Skeleton, Public Contract, and Ports

### Step 1: Add Python project metadata (`pyproject.toml`)
**Scope:** Small
1. Define package metadata, Python `>=3.11`, runtime dependency on `anthropic`, test deps on `pytest` and `jsonschema`.
2. Declare three import packages owned by this repo: `agent_kit`, `arnold`, and `megaplan` (regular package with own `__init__.py`, hosting only `megaplan.arnold`).
3. Console script entry point `arnold = arnold.cli:main`.
4. Configure pytest defaults so tests are discoverable under `tests/`.

### Step 2: Define envelope contract (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Medium
1. Add `Envelope`, `StateDelta`, `Event`, and error dataclasses matching the spec's Subagent Contract.
2. Stable JSON serialization (sorted keys, compact separators).
3. `outcome` enum: `completed`, `blocked_on_caller`, `errored`, `aborted`.
4. `Event.kind` enum (Sprint 1a): `tool_call`, `activity`, `turn_start`, `turn_end`. The envelope `events` array is heterogeneous over these kinds; both contribute to acceptance ("envelope events array matches tool_calls rows" is interpreted as: every `tool_calls` row has a corresponding envelope event whose `tool_call_id` matches — that event may have `kind='tool_call'` or `kind='activity'` depending on the tool, see Step 9/10).
5. `serialize_for_diff(envelope)` strips spec-declared non-deterministic fields (`reply`, per-event `text`, `started_at`/`completed_at`). Used **only** for CLI↔Python envelope-equivalence tests, not for stream-vs-envelope comparison.
6. JSON schema and validation tests in `tests/test_envelope.py`.

### Step 3: Define ports (`agent_kit/ports.py`)
**Scope:** Medium
1. Add `Transport`, `Store`, `Model`, and `Blob` Protocols.
2. `Store` Sprint-1a methods: create/load message, create/update turn, record tool call, log system event, acquire/release per-epic lock, load hot context, and `external_requests` insert/update primitives covering the full spec lifecycle (`pending → confirmed | failed | orphaned`).
3. `Model.complete_turn(...)` accepts a model id string parameter. Adapter signals provider-error vs transport-failure via the `ProviderError` exception type (see Step 11). The protocol stays neutral on call shape but explicit on error surface.
4. `Blob` defines `put(epic_id, content, mime_type) -> BlobRef` and `get(ref) -> bytes`. **No implementation in 1a** — port only.

### Step 4: Lock public Python API (`megaplan/__init__.py`, `megaplan/arnold/__init__.py`, `arnold/__init__.py`)
**Scope:** Small
1. `agent_kit.loop.run_turn` (filled in Step 12) is the single source of truth.
2. Re-export `run_turn`, `arun_turn`, and `Envelope` from `megaplan.arnold`.
3. `arun_turn` is a thin `asyncio.to_thread(run_turn, ...)` coroutine.
4. Re-export the same names from `arnold/__init__.py`.

## Phase 2: SQLite Store, Ledger, and Logging

### Step 5: Create SQLite migrations (`agent_kit/store/migrations/sqlite/001_core.sql`)
**Scope:** Medium
1. Create Sprint 1a tables: `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`.
2. Create `external_requests` with the full spec schema:
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
4. Other cheap indexes: `messages(epic_id, sent_at)`, `tool_calls(turn_id)`.
5. Include nullable resident-mode columns referenced by Sprint 1a (`status_message_id`, `current_activity`, message attachment-flag columns left default-false, `bot_turn_id` on `messages`).

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

### Step 7: Add ledger skeleton (`agent_kit/ledger.py`)
**Scope:** Small
1. `Ledger` class wrapping `Store`'s `external_requests` primitives:
   - `record_pending(provider, endpoint, request_summary, *, turn_id, tool_call_id=None, system_seq=None) -> (request_id, idempotency_key)`.
   - `mark_confirmed(request_id, provider_request_id, provider_response_summary)`.
   - `mark_failed(request_id, error_details)`.
2. **Idempotency key derivation** — extends the spec formula with a per-turn sequence discriminator for system requests so multi-call tool-use turns do not collide on `UNIQUE(idempotency_key)`:
   - Tool-call-driven requests (unchanged from spec): `sha256(turn_id + ":" + tool_call_id + ":" + provider + ":" + endpoint + ":" + canonical_args)[:16]`.
   - System requests: `sha256(turn_id + ":system:" + provider + ":" + endpoint + ":" + str(system_seq))[:16]`. `system_seq` is the 1-based ordinal of the system call within the turn (1 for the first model call, 2 for the second, …). The loop owns the counter (Step 12). Document this as an explicit, intentional extension of the spec's bare formula in the module docstring; Sprint 1b reconciliation must use the same formula. The user-question for spec confirmation is recorded below.
3. `reconcile_on_boot(store)` — documented no-op stub emitting one `info` `system_logs` row; per-provider reconciliation logic lands in Sprint 1b.
4. The `Ledger` does **not** auto-assign `system_seq`; the caller (`run_turn`) passes it explicitly so the loop's ordering is the authority.

### Step 8: Add centralized logger (`agent_kit/logging.py`)
**Scope:** Small
1. `log(store, level, category, event_type, message, **context)` writes through the `Store` to `system_logs`.
2. Use it for model-call metadata, tool-call errors, lock contention; never `print` outside the CLI's stdout/stderr contract.

## Phase 3: Tool Kit and Tools

### Step 9: Build tool registry and audit wrapper (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. Registry mapping tool names to Python callables and JSON-schema metadata. Each registry entry includes `event_kind: Literal['tool_call', 'activity']` (default `'tool_call'`) so the audit wrapper knows which envelope event kind to emit for that tool.
2. **Audit wrapper invariant:** every successful tool invocation writes exactly one `tool_calls` row **and** appends exactly one envelope `Event`. The event's `kind` comes from the registry entry — `'tool_call'` for ordinary tools, `'activity'` for `set_activity`. The same `Event` instance is delivered to `on_event`, written to NDJSON streaming, and stored in the envelope's `events` array (no per-channel mutation). Each event carries `tool_call_id` so tests can join envelope events to `tool_calls` rows regardless of `kind`.
3. DB-mutating tools share one `store.transaction()` for the mutation plus the `tool_calls` row.
4. `tests/test_tool_kit.py`: rollback tests (failure leaves neither the mutation nor the audit row); event-kind tests (registry-driven dispatch produces the right `kind` and a single event per call).

### Step 10: Implement minimal tools (`agent_kit/tools/communication.py`)
**Scope:** Medium
1. `send_message(content, attach_files=None)` — registered with `event_kind='tool_call'`. Append to the turn's reply buffer, write outbound `messages` row with synthetic `discord_message_id`, return that id. The audit wrapper writes the `tool_calls` row and emits one `tool_call` event. (`attach_files` accepted for spec parity; no-op in 1a.)
2. `set_activity(description)` — registered with `event_kind='activity'`. Validate `len <= 80` (truncate longer with a warning logged). The audit wrapper writes the `tool_calls` row (so the audit invariant holds) and emits exactly one `activity` event (per spec mode-divergent semantics). **Does not** mutate `bot_turns.current_activity` in invocation mode and **does not** emit a separate `tool_call` event.
3. `defer_to_caller(questions, reason=None)` — registered with `event_kind='tool_call'`. Set turn outcome to `blocked_on_caller`, populate envelope `questions`, write the `tool_calls` row, emit one `tool_call` event, stop the loop cleanly.
4. Acceptance restated: every `tool_calls` row has exactly one envelope event with the same `tool_call_id`. The event's `kind` is `'tool_call'` for `send_message`/`defer_to_caller` and `'activity'` for `set_activity`.

## Phase 4: Model Adapter and Turn Loop

### Step 11: Implement model port adapters (`agent_kit/model/anthropic.py`, `agent_kit/model/fake.py`)
**Scope:** Medium
1. `AnthropicModel(model_id="claude-opus-4-7")` constructor argument; never hardcoded. CLI reads `ARNOLD_MODEL_ID` from env in `arnold/cli.py` only.
2. Convert registered tools into Anthropic tool definitions.
3. Error surface: provider returned a parseable error response → adapter raises `ProviderError(error_details=<dict>, provider_request_id=<str|None>)`. Transport/SDK exception → propagate unchanged.
4. Summarise request/response into `bot_turns.prompt_snapshot` and `bot_turns.reasoning`; never log secrets.
5. `FakeModel(seed=...)` returns deterministic, scripted multi-step tool-use sequences (it must support more than one model call per turn so tests can exercise tool-use chaining and verify the ledger sequence discriminator). It can also script `ProviderError` or generic exceptions.

### Step 12: Implement `run_turn` (`agent_kit/loop.py`)
**Scope:** Large
1. Acquire per-epic lock; if contended return `errored` envelope with `error.code='epic_locked'`.
2. Persist inbound message; create `bot_turns` row with `status='in_progress'`. **No attachment processing in 1a.**
3. Load minimal hot context (epic row, recent messages, recent tool calls).
4. **Model-call loop with sequenced ledger:** maintain a `model_call_seq = 0` counter for this turn. For each main `Model.complete_turn(...)` call:
   1. Increment `model_call_seq`.
   2. Call `Ledger.record_pending(provider='anthropic', endpoint='POST /v1/messages', turn_id=<turn>, tool_call_id=None, system_seq=model_call_seq, request_summary={...})`. The resulting idempotency key is `sha256(turn_id + ':system:anthropic:POST /v1/messages:' + str(model_call_seq))[:16]`, guaranteeing uniqueness across model calls in this turn.
   3. Issue the model call. On success → `mark_confirmed(...)`. On `ProviderError` → `mark_failed(error_details=...)` and end the turn `errored`. On any other exception → leave the row `pending` for 1b reconciliation, end the turn `errored`.
5. Execute requested tools through the audit wrapper until the model returns final text, calls `defer_to_caller`, or errors. Tool-use chaining loops back to step 4.
6. If the model returns final text without calling `send_message`, synthesize one `send_message` so `reply` is never empty for `completed`.
7. Compute `state_delta` as a stable empty artifact delta with byte-deterministic structure.
8. Mark turn `completed` / `failed` / `abandoned`, release lock, return byte-stable `Envelope`.
9. `on_event` callback called once per appended event in envelope order.
10. **Abort path:** install a cooperative cancellation flag (set by `arnold.cli` on `SIGINT` or by the Python caller via an optional `cancel_event: threading.Event` argument). Between tool steps, check the flag; if set, mark `bot_turns.status='abandoned'`, release the lock, and return an envelope with `outcome='aborted'`. Both row-status `abandoned` and envelope-outcome `aborted` coexist by design. Valid envelope still prints to stdout.

## Phase 5: CLI Invocation Surface

### Step 13: Add CLI package (`arnold/cli.py`)
**Scope:** Medium
1. `arnold turn --epic <id> [--input "text" | --from-stdin] [--stream-events] [--store sqlite|supabase] [--db PATH] [--model-id ID]`. **No `--attach` flag in 1a (SD-010).**
2. SIGINT handler sets the cancellation flag passed to `run_turn`.
3. Serialize the final envelope as JSON on stdout for **every** outcome.
4. When `--stream-events` is set, emit each event to stderr as one NDJSON line at the moment it is appended to the envelope's `events` list. Streamed lines byte-identical to the envelope's `events` array (same encoder, same objects, same order). This holds for both `tool_call` and `activity` event kinds.
5. Exit codes: `completed=0`, `errored=1`, `blocked_on_caller=2`, `aborted=3`.
6. `--store supabase` returns `errored` envelope (`error.code='unsupported_store'`) until Sprint 1b.
7. CLI is a thin wrapper.

## Phase 6: Verification

### Step 14: Unit tests (`tests/test_envelope.py`, `tests/test_tool_kit.py`, `tests/store_contract.py`, `tests/test_sqlite_store.py`)
**Scope:** Medium
1. Validate envelope dataclass serialization against the JSON schema, including both `tool_call` and `activity` event kinds.
2. `tests/store_contract.py` is a parametrized, store-agnostic suite taking a `store_factory` fixture; `tests/test_sqlite_store.py` parametrizes it with the SQLite factory. Sprint 1b reuses the module unchanged with a Supabase factory.
3. Verify tool audit atomicity (mutation + `tool_calls` row commit-or-roll-back together); verify the audit wrapper emits exactly one event per tool call with the registry-declared `kind`.
4. Cover the full `external_requests` lifecycle: `insert_pending`, `mark_confirmed`, `mark_failed`. Assert idempotency-key uniqueness constraint rejects duplicates. Assert all spec columns exist.
5. **Idempotency-key derivation tests** in `tests/test_ledger.py`: assert tool-call key formula (spec verbatim); assert system key formula extended with `system_seq` produces distinct keys for `system_seq=1` and `system_seq=2` with the same other inputs.

### Step 15: Integration tests (`tests/test_run_turn.py`, `tests/test_cli.py`, `tests/test_megaplan_arnold_import.py`, `tests/test_ledger.py`)
**Scope:** Large
1. Full receive → reason → respond cycle with `FakeModel` driving scripted tool calls. One `bot_turns` row per turn, one `tool_calls` row per executed tool. Envelope `events` joined to `tool_calls` by `tool_call_id` covers every audit row exactly once; events for `set_activity` have `kind='activity'`, others `kind='tool_call'`.
2. **Determinism:**
   - `state_delta` byte-identical across two runs with same input + same SQLite state + same `FakeModel(seed=...)`. Unconditional.
   - `serialize_for_diff(envelope)` byte-equivalent between Python `run_turn(...)` and CLI `arnold turn ...` for the same fixture.
3. **Streaming equivalence:** with `--stream-events`, parse each NDJSON stderr line and assert the parsed list is byte-identical to the envelope's `events` array (no projection). Test fixture includes both `tool_call` and `activity` events.
4. **All four exit codes** exercised end-to-end via `FakeModel` scripting (`completed`, `errored`, `blocked_on_caller`, `aborted`).
5. **Ledger lifecycle (three cases) plus tool-use chaining:**
   - **Success path, single model call:** one `external_requests` row with `tool_call_id IS NULL`, `provider='anthropic'`, `endpoint='POST /v1/messages'`, `turn_id` matches, idempotency_key is the spec-extended SHA256[:16] including `system_seq=1`, status `pending → confirmed`.
   - **Tool-use chaining (multi-call):** `FakeModel` scripted to return a tool-use turn that triggers a second model call. Assert two `external_requests` rows for the same turn with `system_seq=1` and `system_seq=2`, distinct idempotency keys, both transitioning `pending → confirmed`. Assert no `UNIQUE(idempotency_key)` violation.
   - **Provider-error path:** `FakeModel` scripted to raise `ProviderError(error_details={...})`; row is `status='failed'`, `error_details` populated, `completed_at` set, turn ends `errored`.
   - **Crash path:** `FakeModel` scripted to raise a plain `RuntimeError`; row remains `status='pending'` with `error_details IS NULL`; turn ends `errored`.
6. **`set_activity` event-shape test:** call `set_activity` and assert the envelope contains exactly one event with `kind='activity'` carrying the description and a `tool_call_id`; assert a corresponding `tool_calls` row exists; assert no extra `tool_call`-kind event was emitted for that invocation.
7. Import-path test: `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves to the same callables as `agent_kit.loop`.
8. Finish with full `pytest`.

## Execution Order
1. `pyproject.toml`, package directories, envelope contract.
2. Lock `megaplan.arnold` public surface alongside ports.
3. SQLite migrations (full `external_requests` schema), store, ledger skeleton (with sequenced idempotency-key formula), logger.
4. Tool registry (with `event_kind` per entry), minimal tools.
5. Model adapter (with `ProviderError` discrimination, multi-call-capable `FakeModel`) and `run_turn` (with abort path, sequenced ledger wiring, tool-use chaining loop).
6. CLI as a thin layer.
7. Broad integration tests including tool-use chaining and `set_activity` event shape.

## Validation Order
1. `pytest tests/test_envelope.py tests/test_megaplan_arnold_import.py`
2. `pytest tests/test_sqlite_store.py tests/test_tool_kit.py`
3. `pytest tests/test_ledger.py tests/test_run_turn.py`
4. `pytest tests/test_cli.py`
5. `pytest` for the full suite.

## Notes for Reviewers
- The Supabase service key in the idea file must **not** be committed anywhere downstream.
- Attachments deferred per SD-010.
- `external_requests` ships with the full spec schema and three lifecycle states wired (pending/confirmed/failed); `orphaned` valid in schema, written by 1b.
- **Idempotency-key extension:** the system formula adds a per-turn `system_seq` discriminator. This is an intentional extension of the spec's bare formula; without it, multi-call tool-use turns would collide on `UNIQUE(idempotency_key)`. Documented in `agent_kit/ledger.py` and asserted in `tests/test_ledger.py`.
- **`set_activity` event kind:** registered with `event_kind='activity'`; the audit wrapper writes a `tool_calls` row (preserving the audit invariant) and emits exactly one `activity` event (preserving the spec mode-divergent semantics). Tests assert both invariants.
- Streaming NDJSON byte-identical to the envelope's `events` array for both `tool_call` and `activity` kinds; `serialize_for_diff` only used for CLI↔Python envelope equivalence.
- Abort: row-status `abandoned` + envelope-outcome `aborted` coexist.
