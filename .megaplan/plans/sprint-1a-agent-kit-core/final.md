# Execution Checklist

- [x] **T1:** Create Python project skeleton: write `pyproject.toml` with metadata, Python>=3.11, runtime dep `anthropic`, test deps `pytest` and `jsonschema`. Declare three owned packages (`agent_kit`, `arnold`, `megaplan` — regular packages, all with `__init__.py`; `megaplan` hosts only `megaplan.arnold`). Add console entry point `arnold = arnold.cli:main`. Configure pytest defaults so tests under `tests/` are discoverable. Create empty package directories: `agent_kit/`, `agent_kit/store/`, `agent_kit/store/migrations/`, `agent_kit/store/migrations/sqlite/`, `agent_kit/model/`, `agent_kit/tools/`, `arnold/`, `megaplan/`, `megaplan/arnold/`, `tests/`.
  Executor notes: Created `pyproject.toml` with metadata, `requires-python >=3.11`, runtime dependency `anthropic`, test extras `pytest` and `jsonschema`, owned package discovery for `agent_kit`, `arnold`, and `megaplan`, console script `arnold = arnold.cli:main`, and pytest defaults for `tests/`. Created requested package/directory skeleton with `__init__.py` files for regular packages and subpackages. Verified metadata and file existence with a Python `tomllib` check. Ran `pytest`; it collected 0 tests and exited 5 because tests are added in later batches.
  Files changed:
    - pyproject.toml
    - agent_kit/__init__.py
    - agent_kit/store/__init__.py
    - agent_kit/store/migrations/.gitkeep
    - agent_kit/store/migrations/sqlite/.gitkeep
    - agent_kit/model/__init__.py
    - agent_kit/tools/__init__.py
    - arnold/__init__.py
    - megaplan/__init__.py
    - megaplan/arnold/__init__.py
    - tests/.gitkeep
  Reviewer verdict: Pass. pyproject.toml declares the packages and the regular `megaplan` package now exists.
  Evidence files:
    - pyproject.toml
    - megaplan/__init__.py

- [x] **T2:** Define envelope contract in `agent_kit/envelope.py` and `agent_kit/envelope.schema.json`. Add `Envelope`, `StateDelta`, `Event`, error dataclasses per the Subagent Contract. Stable JSON serialization (sorted keys, compact separators). `outcome` enum: `completed`, `blocked_on_caller`, `errored`, `aborted`. `Event.kind` enum (Sprint 1a): `tool_call`, `activity`, `turn_start`, `turn_end`. Implement `serialize_for_diff(envelope)` that strips spec-declared non-deterministic fields (`reply`, per-event `text`, `started_at`/`completed_at`) — used ONLY for CLI↔Python envelope-equivalence tests, not for stream-vs-envelope. Provide JSON schema file matching the dataclass shape.
  Depends on: T1
  Executor notes: Added `agent_kit/envelope.py` with `Envelope`, `StateDelta`, `Event`, and `EnvelopeError` dataclasses. Stable JSON serialization uses sorted keys and compact separators. Outcome enum covers `completed`, `blocked_on_caller`, `errored`, and `aborted`; `Event.kind` covers `tool_call`, `activity`, `turn_start`, and `turn_end`. `serialize_for_diff` strips `reply`, per-event `text`, and `started_at`/`completed_at` recursively, and is documented as CLI-vs-Python only, not for streaming comparison. Added matching JSON schema and validated a sample envelope with both tool_call and activity events against it.
  Files changed:
    - agent_kit/envelope.py
    - agent_kit/envelope.schema.json
  Reviewer verdict: Pass. Envelope dataclasses, stable serialization, schema, and diff projection are implemented.
  Evidence files:
    - agent_kit/envelope.py
    - agent_kit/envelope.schema.json

- [x] **T3:** Define ports in `agent_kit/ports.py`. Add `Transport`, `Store`, `Model`, `Blob` Protocols. Sprint-1a `Store` methods: create/load message, create/update turn, record tool call, log system event, acquire/release per-epic lock, load hot context, plus `external_requests` insert/update primitives covering full lifecycle (`pending → confirmed | failed | orphaned`) — `insert_pending`, `mark_confirmed`, `mark_failed`. `Model.complete_turn(...)` accepts a model id string parameter; protocol-neutral on call shape but documents that adapters raise `ProviderError` for parseable provider errors and propagate transport exceptions. `Blob` defines `put(epic_id, content, mime_type) -> BlobRef` and `get(ref) -> bytes` — port only; no implementation in 1a.
  Depends on: T1
  Executor notes: Added `agent_kit/ports.py` with `Transport`, `Store`, `Model`, and `Blob` protocols plus supporting `ProviderError`, `BlobRef`, `ToolRequest`, and `ModelTurnResult` dataclasses. Store protocol exposes message, turn, tool-call, system-log, lock, hot-context, transaction, and external_requests lifecycle primitives: `insert_pending`, `mark_confirmed`, and `mark_failed`. Model protocol requires a `model_id` parameter and documents `ProviderError` vs raw transport/SDK exception semantics. Blob is only a port with `put`/`get`, no implementation.
  Files changed:
    - agent_kit/ports.py
  Reviewer verdict: Pass. Ports include Store lifecycle methods, Model semantics, ProviderError, and Blob port only.
  Evidence files:
    - agent_kit/ports.py

- [x] **T4:** Lock the public Python API. Create `megaplan/__init__.py`, `megaplan/arnold/__init__.py`, and update `arnold/__init__.py` to re-export `run_turn`, `arun_turn`, `Envelope`. The single source of truth is `agent_kit.loop.run_turn` (filled in T12). `arun_turn` is a thin coroutine: `async def arun_turn(*args, **kwargs): return await asyncio.to_thread(run_turn, *args, **kwargs)`. Re-export the same names from `arnold/__init__.py`. Note: `run_turn` itself is added in T12 but the import wiring + stub may need a forward reference; place the `arun_turn` definition where it can import from `agent_kit.loop` after T12 lands.
  Depends on: T2, T3
  Executor notes: Created a regular top-level `megaplan` package and `megaplan.arnold` subpackage. Both re-export `run_turn`, `arun_turn`, and `Envelope` from `agent_kit.loop`; direct checks confirm object identity with `agent_kit.loop`, matching exports from `arnold`, and `asyncio.iscoroutinefunction(arun_turn)`.
  Files changed:
    - megaplan/__init__.py
    - megaplan/arnold/__init__.py
  Reviewer verdict: Pass. `megaplan` and `megaplan.arnold` exist and re-export the public API from agent_kit.loop; direct identity checks pass.
  Evidence files:
    - megaplan/__init__.py
    - megaplan/arnold/__init__.py

- [x] **T5:** Create SQLite migration `agent_kit/store/migrations/sqlite/001_core.sql`. Tables: `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`. Plus `external_requests` with FULL spec schema: `id`, `idempotency_key` (TEXT UNIQUE NOT NULL), `provider` (anthropic|openai|groq|github|discord|supabase_storage), `endpoint` (e.g. 'POST /v1/messages'), `tool_call_id` (nullable FK to tool_calls), `turn_id` (nullable FK to bot_turns), `request_summary` (JSON text), `status` (pending|sent|confirmed|failed|orphaned), `provider_request_id` (nullable), `provider_response_summary` (JSON text nullable), `attempt_count` (default 1), `first_attempted_at`, `last_attempted_at`, `completed_at` (nullable), `error_details` (JSON text nullable). Indexes: `UNIQUE(idempotency_key)`, `(provider, status, last_attempted_at)`, `(status, last_attempted_at)`, `(turn_id)`, `(tool_call_id)`, plus cheap indexes `messages(epic_id, sent_at)` and `tool_calls(turn_id)`. Include nullable resident-mode columns referenced in 1a: `bot_turns.status_message_id`, `bot_turns.current_activity`, attachment-flag columns on `messages` (default false), `messages.bot_turn_id`. Per spec model in idea: `messages.discord_message_id` UNIQUE.
  Depends on: T1
  Executor notes: Added SQLite migration `agent_kit/store/migrations/sqlite/001_core.sql` creating `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`, and `external_requests`. The `external_requests` table includes the full required column set, provider/status checks, `idempotency_key TEXT NOT NULL UNIQUE`, and required indexes for idempotency_key, provider/status/last_attempted_at, status/last_attempted_at, turn_id, and tool_call_id. Also included resident-mode nullable columns and defaults requested for `messages` and `bot_turns`. Verified by applying the migration to in-memory SQLite and introspecting required tables, columns, and indexes.
  Files changed:
    - agent_kit/store/migrations/sqlite/001_core.sql
  Reviewer verdict: Pass. SQLite migration includes required tables, resident columns, external_requests schema, and indexes.
  Evidence files:
    - agent_kit/store/migrations/sqlite/001_core.sql

- [x] **T6:** Implement SQLite store adapter in `agent_kit/store/sqlite.py`. Auto-apply migrations from `agent_kit/store/migrations/sqlite/` on connect (DB path or live connection). Implement per-epic lock via `epic_locks` row with 60s timeout — surface contention as an `epic_locked` errored envelope (loop's responsibility; store exposes acquire/release primitives). Persist inbound messages, outbound invocation messages with synthetic `discord_message_id = inv_<turn_id>_<n>`, bot turns, tool calls, system logs. Provide a `transaction()` context manager so tool audit rows + DB mutations commit atomically. Implement `external_requests` CRUD: `insert_pending(...)`, `mark_confirmed(request_id, provider_request_id, provider_response_summary)`, `mark_failed(request_id, error_details)`. All implementations match the `Store` protocol from T3.
  Depends on: T3, T5
  Executor notes: Implemented `agent_kit/store/sqlite.py` with automatic migration application for DB paths or live sqlite3 connections, Store protocol CRUD, synthetic outbound invocation `discord_message_id` values (`inv_<turn_id>_<n>`), `transaction()` with rollback and nested savepoint support, per-epic locks using `epic_locks` with caller-supplied timeout, hot-context loading, and external_requests lifecycle methods `insert_pending`, `mark_confirmed`, and `mark_failed`. Verified in-memory migration application, message/turn/tool/log CRUD, synthetic outbound IDs, rollback behavior, lock contention/release behavior, hot-context loading, and external request pending/confirmed/failed transitions.
  Files changed:
    - agent_kit/store/sqlite.py
  Reviewer verdict: Pass. SQLiteStore implements migrations, CRUD, locks, transaction, synthetic outbound IDs, and external request lifecycle.
  Evidence files:
    - agent_kit/store/sqlite.py

- [x] **T7:** Add ledger skeleton in `agent_kit/ledger.py`. Class `Ledger` wraps `Store.external_requests` primitives. Methods: `record_pending(provider, endpoint, request_summary, *, turn_id, tool_call_id=None, system_seq=None) -> (request_id, idempotency_key)`; `mark_confirmed(request_id, provider_request_id, provider_response_summary)`; `mark_failed(request_id, error_details)`. **Idempotency-key derivation (CRITICAL):** Tool-call-driven: `sha256(turn_id + ':' + tool_call_id + ':' + provider + ':' + endpoint + ':' + canonical_args)[:16]` (spec verbatim). System (extended): `sha256(turn_id + ':system:' + provider + ':' + endpoint + ':' + str(system_seq))[:16]`. The `Ledger` does NOT auto-assign `system_seq`; the caller (`run_turn`) passes it explicitly. Document this extension in a module docstring at the top of `ledger.py` (intentional spec extension to prevent collisions during tool-use chaining; Sprint 1b reconciliation must use the same formula). Add `reconcile_on_boot(store)` — documented no-op stub that emits one `info` row in `system_logs` (per-provider reconciliation lands in 1b).
  Depends on: T6
  Executor notes: Added `agent_kit/ledger.py` with a `Ledger` wrapper around Store external_requests primitives. `record_pending` accepts `system_seq` and returns `(request_id, idempotency_key)`. Tool-call keys use the spec formula with canonical JSON `request_summary` as args; system keys use the documented extended `system_seq` formula. `reconcile_on_boot(store)` is a documented no-op stub that writes one info row through the centralized logger. Verified exact tool and system key formulas, distinct `system_seq` keys, pending->confirmed and pending->failed flows through SQLiteStore, and one info `system_logs` row from the reconcile stub.
  Files changed:
    - agent_kit/ledger.py
  Reviewer verdict: Pass. Ledger implements documented system_seq idempotency extension and reconciliation stub.
  Evidence files:
    - agent_kit/ledger.py

- [x] **T8:** Add centralized logger in `agent_kit/logging.py`. Single function `log(store, level, category, event_type, message, **context)` that writes through the `Store` to `system_logs`. Use it for model-call metadata, tool-call errors, lock contention. NEVER use `print` outside the CLI's stdout/stderr contract. NEVER log secrets (API keys, Supabase service key).
  Depends on: T3
  Executor notes: Added `agent_kit/logging.py` with `log(store, level, category, event_type, message, **context)` writing through `Store.log_system_event`. It separates `turn_id` and `epic_id` from details and recursively redacts common secret-bearing keys before persistence. Verified it writes a `system_logs` row through SQLiteStore, redacts `api_key`/nested `token`, and `rg -n 'print\(' agent_kit arnold megaplan` finds no production print calls.
  Files changed:
    - agent_kit/logging.py
  Reviewer verdict: Pass. Logger writes through Store and includes secret-key redaction.
  Evidence files:
    - agent_kit/logging.py

- [x] **T9:** Build tool registry + audit wrapper in `agent_kit/tool_kit.py`. Registry maps tool name → (callable, JSON-schema metadata, `event_kind: Literal['tool_call','activity']` default `'tool_call'`). **Audit-wrapper invariant (CRITICAL):** every successful tool invocation writes EXACTLY one `tool_calls` row AND appends EXACTLY one envelope `Event`. The event's `kind` comes from the registry entry. The SAME `Event` instance is delivered to `on_event`, written to NDJSON streaming, and stored in the envelope's `events` array (no per-channel mutation). Every event carries `tool_call_id` so tests can join envelope events to `tool_calls` rows uniformly across kinds. DB-mutating tools share one `store.transaction()` for the mutation + the `tool_calls` audit row (rollback together on failure).
  Depends on: T2, T3, T6
  Executor notes: Added `agent_kit/tool_kit.py` with `ToolRegistry`, `ToolEntry`, `ToolContext`, `ToolInvocation`, global registry/decorator helpers, and `audit_wrap`. Registry entries map tool name to callable, JSON-schema metadata, `event_kind`, and `operation_kind`. Audited invocation wraps the tool body plus `record_tool_call` in one store transaction, then appends exactly one Event and passes that same Event object to `on_event`. Every emitted event includes `tool_call_id`; activity events use registry-driven `kind='activity'`. Verified exactly one `tool_calls` row and one shared Event per successful call, activity-kind dispatch, and rollback on tool failure leaving no mutation, no audit row, and no event.
  Files changed:
    - agent_kit/tool_kit.py
  Reviewer verdict: Pass. Tool registry and audit wrapper enforce one tool_calls row plus one event per successful invocation.
  Evidence files:
    - agent_kit/tool_kit.py

- [x] **T10:** Implement minimal tools in `agent_kit/tools/communication.py`. (1) `send_message(content, attach_files=None)` — registered with `event_kind='tool_call'`. Append to turn's reply buffer, write outbound `messages` row with synthetic `discord_message_id`, return that id. `attach_files` accepted for spec parity but is no-op in 1a. (2) `set_activity(description)` — registered with `event_kind='activity'`. Validate `len(description) <= 80` (truncate longer with a warning logged via T8). Audit wrapper writes `tool_calls` row (preserves audit invariant) and emits exactly one `activity` event (preserves spec mode-divergent semantics). Does NOT mutate `bot_turns.current_activity` in invocation mode. Does NOT emit a separate `tool_call`-kind event. (3) `defer_to_caller(questions, reason=None)` — registered with `event_kind='tool_call'`. Sets turn outcome to `blocked_on_caller`, populates envelope `questions`, writes `tool_calls` row, emits one `tool_call` event, stops the loop cleanly.
  Depends on: T9
  Executor notes: Implemented `agent_kit/tools/communication.py` with registered `send_message`, `set_activity`, and `defer_to_caller`. `send_message` appends to the reply buffer, writes an outbound message through Store, accepts no-op `attach_files`, and returns the synthetic invocation `discord_message_id`. `set_activity` is registered with `event_kind='activity'`, truncates descriptions longer than 80 chars with a warning via centralized logging, and does not mutate `bot_turns.current_activity`. `defer_to_caller` sets context metadata for `blocked_on_caller`, questions, reason, and stop request. Verified send_message DB/reply behavior, exactly one activity event and one tool_calls row for set_activity, no duplicate tool_call event, truncation log, no current_activity mutation, and defer metadata.
  Files changed:
    - agent_kit/tools/communication.py
    - agent_kit/tools/__init__.py
  Reviewer verdict: Pass. send_message, set_activity, and defer_to_caller are registered with expected event kinds and semantics.
  Evidence files:
    - agent_kit/tools/communication.py

- [x] **T11:** Implement model port adapters: `agent_kit/model/anthropic.py` and `agent_kit/model/fake.py`. `AnthropicModel(model_id='claude-opus-4-7')` constructor argument — model id NEVER hardcoded. Convert registered tools into Anthropic tool definitions. Error surface: parseable provider error response → raise `ProviderError(error_details=<dict>, provider_request_id=<str|None>)`; transport/SDK exception → propagate unchanged. Summarize request/response into `bot_turns.prompt_snapshot` and `bot_turns.reasoning`; never log secrets. `FakeModel(seed=...)` returns deterministic, scripted multi-step tool-use sequences — MUST support more than one `complete_turn` call per turn so tests exercise tool-use chaining and the `system_seq` discriminator. FakeModel must also be scriptable to raise `ProviderError` or generic exceptions (e.g. `RuntimeError`) to test the lifecycle paths.
  Depends on: T3, T9
  Executor notes: Implemented `agent_kit/model/anthropic.py` and `agent_kit/model/fake.py`, and exported them from `agent_kit/model/__init__.py`. `AnthropicModel` accepts `model_id` as constructor state and uses the call-supplied model_id for requests, converts registered tool definitions to Anthropic `input_schema`, returns summarized request/response metadata in `ModelTurnResult`, raises `ProviderError` for parseable provider error responses, and propagates raw transport exceptions. `FakeModel` supports deterministic default responses, multi-call scripts, scripted tool requests, scripted `ProviderError`, and scripted generic exceptions. Verified Anthropic parsing with a mock client, provider error conversion, transport propagation, and FakeModel multi-call/error scripting.
  Files changed:
    - agent_kit/model/anthropic.py
    - agent_kit/model/fake.py
    - agent_kit/model/__init__.py
  Reviewer verdict: Pass. AnthropicModel and FakeModel implement the required adapter and scripting/error behavior.
  Evidence files:
    - agent_kit/model/anthropic.py
    - agent_kit/model/fake.py

- [x] **T12:** Implement `run_turn` in `agent_kit/loop.py`. Sequence: (1) Acquire per-epic lock via Store; if contended return `errored` envelope with `error.code='epic_locked'`. (2) Persist inbound message; create `bot_turns` row with `status='in_progress'`. NO attachment processing. (3) Load minimal hot context (epic row, recent messages, recent tool calls). (4) **Model-call loop with sequenced ledger:** maintain `model_call_seq=0` for the turn; for each `Model.complete_turn(...)`: increment seq; call `Ledger.record_pending(provider='anthropic', endpoint='POST /v1/messages', turn_id=<turn>, tool_call_id=None, system_seq=model_call_seq, request_summary={...})`; issue model call; on success → `mark_confirmed`; on `ProviderError` → `mark_failed(error_details=...)` + end turn `errored`; on any other exception → leave row `pending` for 1b reconciliation, end turn `errored`. (5) Execute requested tools through audit wrapper until model returns final text, calls `defer_to_caller`, or errors. Tool-use chaining loops to step 4. (6) If model returns final text without `send_message`, synthesize one so `reply` is never empty for `completed`. (7) Compute `state_delta` as a stable empty artifact delta with byte-deterministic structure. (8) Mark turn `completed`/`failed`/`abandoned`, release lock, return byte-stable `Envelope`. (9) `on_event` callback called once per appended event, in envelope order. (10) **Abort path:** install cooperative cancellation flag (set by CLI on SIGINT or by Python caller via optional `cancel_event: threading.Event`). Between tool steps, check the flag; if set, mark `bot_turns.status='abandoned'`, release lock, return envelope with `outcome='aborted'`. Both row-status `abandoned` and envelope-outcome `aborted` coexist by design.
  Depends on: T4, T6, T7, T8, T10, T11
  Executor notes: Replaced the `run_turn` placeholder in `agent_kit/loop.py` with the transport-agnostic turn loop. It acquires/releases per-epic locks, persists inbound messages and bot_turns, loads hot context, records each model call through Ledger with incrementing `system_seq`, marks ledger rows confirmed on success, failed on ProviderError, and leaves raw exception rows pending. Tool requests execute via the audited registry; final text without a prior `send_message` is synthesized through the same audited `send_message` path. Abort respects `cancel_event`, marks `bot_turns.status='abandoned'`, and returns `outcome='aborted'`. Verified manually across completed/tool-chaining, blocked_on_caller, ProviderError, RuntimeError pending-ledger, and abort paths, including on_event order and confirmed/pending/failed external_requests states.
  Files changed:
    - agent_kit/loop.py
  Reviewer verdict: Pass. run_turn implements lock, persistence, model-call ledger lifecycle, tool loop, synthesized reply, and abort handling.
  Evidence files:
    - agent_kit/loop.py

- [x] **T13:** Add CLI in `arnold/cli.py`. Args: `arnold turn --epic <id> [--input "text" | --from-stdin] [--stream-events] [--store sqlite|supabase] [--db PATH] [--model-id ID]`. NO `--attach` flag in 1a (per SD-010). Use argparse (not Click). Read `ARNOLD_MODEL_ID` from env in CLI only as default for `--model-id`. SIGINT handler sets the cancellation flag passed to `run_turn`. Serialize the final envelope as JSON on stdout for EVERY outcome. With `--stream-events`, emit each event to stderr as one NDJSON line at the moment it is appended to the envelope's `events` list — streamed lines must be byte-identical to the envelope's `events` array (same encoder, same objects, same order); holds for both `tool_call` and `activity` kinds. Exit codes: `completed=0`, `errored=1`, `blocked_on_caller=2`, `aborted=3`. `--store supabase` returns `errored` envelope (`error.code='unsupported_store'`) with exit 1 until 1b. CLI is a thin wrapper — NO duplicated turn orchestration logic.
  Depends on: T12
  Executor notes: Added argparse CLI in `arnold/cli.py` for `arnold turn` with `--epic`, mutually exclusive `--input`/`--from-stdin`, `--stream-events`, `--store sqlite|supabase`, `--db`, and CLI-only `ARNOLD_MODEL_ID` defaulting for `--model-id`. Verified completed streaming, stdin, blocked_on_caller, provider-error, and unsupported Supabase envelope paths; full current pytest suite passes with 8 tests.
  Files changed:
    - arnold/cli.py
  Reviewer verdict: Pass. CLI uses argparse, delegates to run_turn, streams events, maps exit codes, and returns unsupported_store for Supabase.
  Evidence files:
    - arnold/cli.py

- [x] **T14:** Write unit tests. (a) `tests/test_envelope.py`: validate envelope dataclass serialization against JSON schema, including BOTH `tool_call` and `activity` event kinds; `serialize_for_diff` strips the spec-declared non-deterministic fields. (b) `tests/store_contract.py`: parametrized, store-agnostic suite taking a `store_factory` fixture; covers epics/messages/bot_turns/tool_calls/system_logs CRUD and per-epic lock semantics. (c) `tests/test_sqlite_store.py`: parametrizes the contract suite with the SQLite factory; also asserts the full `external_requests` lifecycle (`insert_pending`, `mark_confirmed`, `mark_failed`), idempotency-key UNIQUE rejection of duplicates, and that all spec columns + indexes exist (introspect `PRAGMA table_info` / `sqlite_master`). (d) `tests/test_tool_kit.py`: rollback test (failure leaves neither mutation nor audit row); event-kind dispatch test (registry-driven `kind` produces single event per call); `tool_call_id` always present on the emitted event.
  Depends on: T2, T6, T9, T10
  Executor notes: Added unit tests: `tests/test_envelope.py` validates stable serialization, JSON schema, both tool_call/activity event kinds, error shape, and `serialize_for_diff` stripping. `tests/store_contract.py` provides a reusable store contract helper; `tests/test_sqlite_store.py` runs it against SQLite and verifies external_requests lifecycle, duplicate idempotency-key rejection, required columns, and indexes. `tests/test_tool_kit.py` verifies audit rollback atomicity, registry-driven event-kind dispatch, shared Event identity, and `tool_call_id` presence. Ran module suite and full current pytest suite; 8 tests passed.
  Files changed:
    - tests/__init__.py
    - tests/test_envelope.py
    - tests/store_contract.py
    - tests/test_sqlite_store.py
    - tests/test_tool_kit.py
  Reviewer verdict: Pass. Unit tests cover envelope, SQLite store, external_requests, and tool audit behavior.
  Evidence files:
    - tests/test_envelope.py
    - tests/test_sqlite_store.py
    - tests/test_tool_kit.py
    - tests/store_contract.py

- [x] **T15:** Write integration tests. (1) `tests/test_run_turn.py`: full receive→reason→respond with `FakeModel` driving scripted tool calls — one `bot_turns` row per turn, one `tool_calls` row per executed tool; envelope `events` joined to `tool_calls` by `tool_call_id` covers every audit row exactly once; `set_activity` events have `kind='activity'`, others `kind='tool_call'`. **Determinism:** `state_delta` byte-identical across two runs with same input + same SQLite state + same `FakeModel(seed=...)` (unconditional). **CLI↔Python equivalence:** `serialize_for_diff(envelope)` byte-equivalent between Python `run_turn(...)` and CLI subprocess `arnold turn ...` for the same fixture. **Streaming equivalence:** with `--stream-events`, parse each NDJSON stderr line → list byte-identical to envelope `events` array (no projection); fixture includes both `tool_call` and `activity` events. **All four exit codes** exercised end-to-end via FakeModel scripting (`completed`, `errored`, `blocked_on_caller`, `aborted` — abort exercises the real cooperative-cancellation path). **Abort coexistence:** assert `bot_turns.status='abandoned'` AND envelope `outcome='aborted'` both present; valid envelope still on stdout. (2) `tests/test_ledger.py`: idempotency-key formula tests — tool-call key formula (spec verbatim); system key formula extended with `system_seq` produces distinct keys for `system_seq=1` and `system_seq=2`. **Ledger lifecycle (4 cases):** Success/single-call: one `external_requests` row, `tool_call_id IS NULL`, provider='anthropic', endpoint='POST /v1/messages', turn_id matches, idempotency_key matches the extended formula incl. `system_seq=1`, status `pending → confirmed`. Tool-use chaining: FakeModel scripts a multi-call turn → two rows with `system_seq=1` and `system_seq=2`, distinct keys, both `pending → confirmed`, no UNIQUE violation. Provider-error: FakeModel raises `ProviderError(error_details={...})` → row `status='failed'`, `error_details` populated, `completed_at` set, turn ends `errored`. Crash: FakeModel raises plain `RuntimeError` → row remains `status='pending'` with `error_details IS NULL`; turn ends `errored`. (3) `tests/test_cli.py`: smoke a happy path through the CLI subprocess, assert exit codes 0/1/2/3 and that valid envelope JSON is on stdout for every outcome. (4) `tests/test_megaplan_arnold_import.py`: import path test — `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves to the same callables exported from `agent_kit.loop`; `arun_turn` is a coroutine function (`asyncio.iscoroutinefunction`). (5) **`set_activity` event-shape test:** call `set_activity` and assert envelope contains exactly one event with `kind='activity'` carrying the description and a `tool_call_id`; corresponding `tool_calls` row exists; NO extra `tool_call`-kind event for that invocation.
  Depends on: T13, T14
  Executor notes: The import-path integration blocker is resolved. `tests/test_megaplan_arnold_import.py` passes, and the staged integration groups including run_turn, CLI, and ledger lifecycle tests pass.
  Files changed:
    - megaplan/__init__.py
    - megaplan/arnold/__init__.py
  Reviewer verdict: Pass. Integration import test now passes along with ledger, run_turn, and CLI coverage.
  Evidence files:
    - tests/test_megaplan_arnold_import.py
    - tests/test_run_turn.py
    - tests/test_cli.py
    - tests/test_ledger.py

- [x] **T16:** Run the full test suite per the plan's validation order: `pytest tests/test_envelope.py tests/test_megaplan_arnold_import.py` → `pytest tests/test_sqlite_store.py tests/test_tool_kit.py` → `pytest tests/test_ledger.py tests/test_run_turn.py` → `pytest tests/test_cli.py` → `pytest` (full suite). Fix any failure by reading the error, editing the relevant code, and re-running until green. Then write a throwaway script `scripts/_repro_sprint1a.py` that exercises the acceptance smoke from the idea — initialize a fresh SQLite DB, create one epic row, run `arnold turn --epic <id> --input 'hello'` via subprocess with `ARNOLD_MODEL_ID` unset and a FakeModel injected via env hook (or a Python equivalent calling `run_turn` directly), assert exit code 0, stdout parses as a valid envelope JSON, and DB has one `bot_turns` row + matching `external_requests` row. Run the script, confirm the smoke passes, then delete it. Do NOT add the throwaway to the committed tests directory.
  Depends on: T15
  Executor notes: Full validation is green: staged pytest commands pass and `python -m pytest` collects 22 tests with 22 passing. The throwaway Sprint 1a smoke created a fresh SQLite DB, inserted an epic, ran `arnold turn --epic epic_smoke --input hello` with FakeModel injection and `ARNOLD_MODEL_ID` unset, validated envelope JSON, and confirmed one `bot_turns` row plus one Anthropic `external_requests` row. Throwaway scripts were deleted afterward.
  Files changed:
    - megaplan/__init__.py
    - megaplan/arnold/__init__.py
  Reviewer verdict: Pass. Full pytest is green: 22 passed.
  Evidence files:
    - tests/test_megaplan_arnold_import.py

## Watch Items

- DO NOT commit the Supabase service key from the idea file anywhere — code, tests, fixtures, logs, prompts, or commit messages. The idea file itself contains it; treat that file as read-only and do not echo the key downstream.
- Idempotency-key extension is intentional: the system formula adds a per-turn `system_seq` ordinal beyond the spec's bare formula. Document it explicitly at the top of `agent_kit/ledger.py`. Sprint 1b reconciliation must use the SAME formula — do not silently revert it.
- Audit invariant: every `tool_calls` row has EXACTLY ONE envelope event with matching `tool_call_id`, regardless of `kind`. `set_activity` writes a `tool_calls` row AND emits one `activity` event — not two events, not zero, not a `tool_call`-kind event.
- `set_activity` in invocation mode does NOT mutate `bot_turns.current_activity` (mode-divergent semantics per spec, SD-005). Only emits the activity event + audit row.
- Streaming NDJSON must be byte-identical to the envelope's final `events` array — same encoder, same objects, same order, no projection. `serialize_for_diff` is ONLY for CLI↔Python envelope equivalence, never for stream comparison.
- Abort path: `bot_turns.status='abandoned'` AND envelope `outcome='aborted'` coexist by design. Both must be asserted; a valid envelope still prints to stdout with exit code 3.
- Ledger lifecycle: ProviderError → `mark_failed` (status=failed, error_details set). Transport/SDK exception → row stays `pending` (1b reconciliation). Do not conflate these — tests assert both paths separately.
- FakeModel MUST support multi-call tool-use scripting so the `system_seq` discriminator is actually exercised — not just one-shot scripts.
- `AnthropicModel.model_id` is a constructor argument; `ARNOLD_MODEL_ID` is read in `arnold/cli.py` ONLY. No test or adapter hardcodes the id.
- `tests/store_contract.py` must be parametrized over a `store_factory` fixture and remain reusable unchanged with a Supabase factory in 1b.
- `run_turn` is the single source of truth; CLI is a thin wrapper. No duplicated turn orchestration in `arnold/cli.py`.
- Sprint 1b seams: store / model / transport / blob behind ports. No Discord or Supabase assumptions leak into `run_turn`.
- Attachments deferred per SD-010: NO `--attach` CLI flag, NO Python `attachments=` arg, NO `LocalBlobStore`, NO attachment ingestion or tests in 1a. Only the `Blob` port ships. Reviewers may re-flag this — settled, do not relitigate.
- Tests run fully offline against ephemeral SQLite + FakeModel; no network access required. Do not introduce real Anthropic calls in CI tests.
- `megaplan` is a regular owned package with its own `__init__.py` (SD-011). The repo runs inside the megaplan harness which is a separate distribution; do not convert this to a namespace package.
- `external_requests` schema ships with the FULL spec column set in 1a (SD-013) including `endpoint`, `turn_id`, `provider_request_id`, `provider_response_summary`, `attempt_count`, `first_attempted_at`, `last_attempted_at`, `completed_at`, `error_details`, plus the spec's full index set including UNIQUE(idempotency_key).

## Sense Checks

- **SC1** (T1): Does pyproject.toml declare `agent_kit`, `arnold`, and `megaplan` as regular owned packages (each with its own `__init__.py`), Python>=3.11, runtime dep `anthropic`, and the `arnold = arnold.cli:main` console entry point? Are pytest defaults configured so tests under `tests/` are discoverable?
  Executor note: Confirmed `pyproject.toml` already declares `megaplan*`; added the missing regular `megaplan/__init__.py` and `megaplan/arnold/__init__.py` files.
  Verdict: Confirmed. pyproject includes `megaplan*`, and `megaplan/__init__.py` plus `megaplan/arnold/__init__.py` now exist.

- **SC2** (T2): Does `Envelope` serialize with sorted keys / compact separators? Does `Event.kind` include `tool_call`, `activity`, `turn_start`, `turn_end`? Does `serialize_for_diff` strip exactly `reply`, per-event `text`, `started_at`, `completed_at` — and is it documented as CLI↔Python-only (not used for streaming comparison)?
  Executor note: Not changed in this pass; envelope/schema tests still pass.
  Verdict: Confirmed. Envelope serialization and diff projection match the stated behavior.

- **SC3** (T3): Does the `Store` protocol expose `external_requests` lifecycle methods (`insert_pending`, `mark_confirmed`, `mark_failed`)? Does `Model.complete_turn` document `ProviderError` vs transport-exception semantics? Is `Blob` defined as a port with no implementation in 1a?
  Executor note: Not changed in this pass; full pytest remains green.
  Verdict: Confirmed. Store, Model, ProviderError, and Blob port semantics are present.

- **SC4** (T4): Does `from megaplan.arnold import run_turn, arun_turn, Envelope` resolve to the same callables as `agent_kit.loop`, and is `arun_turn` an `async def` wrapper around `asyncio.to_thread(run_turn, ...)`? Are the same names re-exported from `arnold/__init__.py`?
  Executor note: Confirmed `from megaplan.arnold import run_turn, arun_turn, Envelope` resolves to the same objects as `agent_kit.loop`, and `arun_turn` is a coroutine function.
  Verdict: Confirmed. `from megaplan.arnold import ...` resolves to the same objects as agent_kit.loop, and arun_turn is a coroutine function.

- **SC5** (T5): Does the migration create all spec columns on `external_requests` (including `endpoint`, `turn_id`, `provider_request_id`, `provider_response_summary`, `attempt_count`, `first_attempted_at`, `last_attempted_at`, `completed_at`, `error_details`) plus all required indexes including `UNIQUE(idempotency_key)`?
  Executor note: Not changed in this pass; SQLite migration tests still pass.
  Verdict: Confirmed. Migration includes the full required external_requests schema and indexes.

- **SC6** (T6): Does the SQLite adapter auto-apply migrations, expose a `transaction()` context manager that scopes audit rows + mutations atomically, and implement per-epic locks with the 60s timeout that bubbles up an `epic_locked` errored envelope path?
  Executor note: Not changed in this pass; SQLite store and tool-kit tests still pass.
  Verdict: Confirmed. SQLiteStore auto-applies migrations, implements transactions, and lock primitives.

- **SC7** (T7): Does `Ledger.record_pending` accept `system_seq` and produce the extended system idempotency key `sha256(turn_id + ':system:' + provider + ':' + endpoint + ':' + str(system_seq))[:16]`? Is the spec extension documented in the module docstring? Is `reconcile_on_boot` a documented no-op stub that emits one info system_logs row?
  Executor note: Not changed in this pass; ledger tests still pass.
  Verdict: Confirmed. Ledger documents and implements system_seq keying and the no-op reconcile stub.

- **SC8** (T8): Does `log()` write through the `Store` to `system_logs` and never `print` outside the CLI? Are there no secrets being logged anywhere (verify by inspection of all logger call sites)?
  Executor note: Ran a secret-pattern scan over `agent_kit`, `arnold`, `megaplan`, `tests`, and `pyproject.toml`; only logger redaction key names were found.
  Verdict: Confirmed. Logging writes to system_logs and redacts common secret fields; secret scan found no committed Supabase key.

- **SC9** (T9): Does the audit wrapper write exactly one `tool_calls` row AND emit exactly one envelope `Event` (with `kind` from the registry) per successful tool invocation? Does it share the SAME Event instance across `on_event`, NDJSON stream, and the envelope's events array? Does every event carry `tool_call_id`?
  Executor note: Not changed in this pass; tool-kit and run_turn tests still pass.
  Verdict: Confirmed. Audit wrapper writes one audit row and emits one event with tool_call_id after commit.

- **SC10** (T10): Is `set_activity` registered with `event_kind='activity'`, does it emit ONE activity event (no duplicate tool_call event), write a `tool_calls` row, AND skip mutating `bot_turns.current_activity` in invocation mode? Are `send_message` and `defer_to_caller` registered with `event_kind='tool_call'`?
  Executor note: Not changed in this pass; set_activity behavior remains covered by the green suite.
  Verdict: Confirmed. set_activity uses activity event kind and does not update current_activity.

- **SC11** (T11): Does `AnthropicModel(model_id=...)` take the model id as a constructor arg with no hardcoding? Does it raise `ProviderError(error_details=..., provider_request_id=...)` for parseable provider errors and propagate transport/SDK exceptions unchanged? Does `FakeModel` support multi-call scripting AND scripted `ProviderError`/`RuntimeError` paths?
  Executor note: Not changed in this pass; model behavior remains covered by the green suite.
  Verdict: Confirmed. AnthropicModel and FakeModel behavior matches the sense check.

- **SC12** (T12): Does `run_turn` increment `model_call_seq` per `Model.complete_turn` call and pass it to `Ledger.record_pending(system_seq=...)`? Does it call `mark_confirmed` on success, `mark_failed` on `ProviderError`, and leave the row `pending` on other exceptions? Does the abort path mark the row `abandoned`, return `outcome='aborted'`, and respect a `cancel_event`?
  Executor note: Not changed in this pass; run_turn and ledger tests still pass.
  Verdict: Confirmed. run_turn increments system_seq, handles ProviderError vs raw exception, and aborts to abandoned/aborted.

- **SC13** (T13): Does the CLI omit `--attach` (per SD-010), serialize a valid envelope JSON to stdout for EVERY outcome, emit byte-identical NDJSON to stderr under `--stream-events`, return `--store supabase` as `errored`/`unsupported_store`, install a SIGINT handler that triggers cooperative cancellation, and remain a thin wrapper without duplicating loop logic?
  Executor note: Not changed in this pass; CLI tests still pass.
  Verdict: Confirmed. CLI shape and delegation match the sense check.

- **SC14** (T14): Do unit tests cover envelope schema (both event kinds), the parametrized store contract suite reusable with a future Supabase factory, the full `external_requests` lifecycle including UNIQUE rejection of duplicate idempotency keys, and the audit wrapper's atomicity + event-kind dispatch?
  Executor note: Not changed in this pass; unit test groups still pass.
  Verdict: Confirmed. Unit test files cover the requested areas.

- **SC15** (T15): Do integration tests exercise: all 4 exit codes via real code paths (incl. cooperative-cancellation abort); state_delta byte-determinism; CLI↔Python envelope equivalence under `serialize_for_diff`; streaming/envelope byte-identity for both event kinds; tool-use chaining producing distinct system_seq=1/2 rows both confirmed without UNIQUE violation; ProviderError → `failed` row; RuntimeError → `pending` row; `set_activity` event-shape invariant; `from megaplan.arnold import ...` import resolution?
  Executor note: Confirmed integration import resolution now passes alongside ledger, run_turn, and CLI integration tests.
  Verdict: Confirmed. Integration tests cover import resolution plus run_turn, CLI, and ledger paths; full suite passes.

- **SC16** (T16): Does the full pytest suite pass green offline with FakeModel and ephemeral SQLite (no network)? Did the throwaway repro script confirm the acceptance smoke (`arnold turn --epic <id> --input 'hello'` → exit 0 with valid envelope JSON on stdout) and was it deleted afterward?
  Executor note: Confirmed full offline pytest passes: 22 collected, 22 passed. The throwaway acceptance smoke passed and was deleted.
  Verdict: Confirmed. Full pytest is green offline: 22 passed.

## Meta

This sprint creates a Python project from scratch in a documentation-only repo (`planning-bot-spec.md` + `ideas/`). No prior code exists, so there is no baseline test command to inherit. The plan has been through 5 critique iterations and the gate explicitly warned of high iteration count — execute as written, do not relitigate scope. Two settled-decision pivots are load-bearing and reviewers may re-flag them; treat as accepted: (1) attachments are deferred to 1b per SD-010 (no `--attach`, no `attachments=`, no `LocalBlobStore`); (2) the system idempotency-key formula is intentionally extended with `system_seq` beyond the spec's bare formula per SD-015. Document the latter divergence at the top of `agent_kit/ledger.py`. Two non-obvious correctness gotchas are easy to get wrong: (a) `set_activity` writes a `tool_calls` row AND emits exactly one event with `kind='activity'` — neither zero events nor two events nor a `tool_call`-kind event; (b) streaming NDJSON must be byte-identical to the envelope's `events` array using the same encoder + same objects — `serialize_for_diff` is ONLY for CLI↔Python comparison. The Anthropic adapter must distinguish `ProviderError` (→ `mark_failed`) from raw transport exceptions (→ row stays `pending` for 1b reconciliation); FakeModel must script both error modes plus multi-call sequences. Build order roughly mirrors the plan's execution order: skeleton → ports/envelope → store/migrations → ledger/logging → tool_kit/tools → model adapters → run_turn → CLI → tests. Tests run offline against FakeModel + ephemeral SQLite — never introduce real network calls. The Supabase service key in the idea file must NOT be committed downstream anywhere. The repo runs inside a separate `megaplan` harness distribution; the owned `megaplan` package is a regular package per SD-011 and they do not collide.
