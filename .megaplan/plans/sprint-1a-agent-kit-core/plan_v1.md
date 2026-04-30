# Implementation Plan: Sprint 1a Agent Kit Core + Invocation Mode

## Overview
The repository is currently documentation-only: `planning-bot-spec.md` plus sprint idea files, with no Python package, CLI, tests, or project metadata. Sprint 1a should therefore bootstrap a small Python 3.11 package from scratch, anchored on the spec sections for Execution Modes, Subagent Contract, Callable API, Data Model, Tools, and Testing.

The simplest viable implementation is a real invocation-mode substrate with SQLite and a mocked-testable model boundary, not a Discord/Supabase preview. Use `argparse` for the CLI to avoid unnecessary framework dependency; use `anthropic` only behind a `Model` port so tests can run fully offline.

## Phase 1: Project Skeleton and Public Contract

### Step 1: Add Python project metadata (`pyproject.toml`)
**Scope:** Small
1. Define package metadata, Python `>=3.11`, runtime dependency on `anthropic`, test dependencies on `pytest` and `jsonschema`.
2. Add console script entry point `arnold = arnold.cli:main`.
3. Add pytest defaults, keeping tests discoverable under `tests/`.

### Step 2: Define envelope contract (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Medium
1. Add `Envelope`, `StateDelta`, and error dataclasses matching `planning-bot-spec.md:1786`.
2. Implement stable JSON serialization with sorted keys and compact separators so CLI/Python equivalence can compare bytes.
3. Add `outcome` enum values: `completed`, `blocked_on_caller`, `errored`, `aborted`.
4. Add schema validation tests in `tests/test_envelope.py`.

### Step 3: Define ports (`agent_kit/ports.py`)
**Scope:** Medium
1. Add `Transport`, `Store`, `Model`, and `Blob` protocols.
2. Keep protocol methods narrow and Sprint-1a-specific: create/load message, create/update turn, record tool call, log system event, lock epic, load hot context, and invoke model.
3. Model the Python public API as `agent_kit.loop.run_turn(...)`; optionally re-export it from `arnold/__init__.py` for the CLI package.

## Phase 2: SQLite Store and Audit Ledger

### Step 4: Create SQLite migrations (`agent_kit/store/migrations/sqlite/001_core.sql`)
**Scope:** Medium
1. Create Sprint 1a tables: `epics`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, plus `epic_locks` for invocation lock semantics.
2. Use SQLite-compatible representations for arrays/json: JSON text columns with validation at the application layer.
3. Include nullable resident-mode columns from the full spec where they are already referenced by turn/tool behavior, such as `status_message_id`, `current_activity`, and message attachment fields.
4. Add indexes from the spec where cheap and relevant.

### Step 5: Implement SQLite store adapter (`agent_kit/store/sqlite.py`)
**Scope:** Large
1. Apply migrations automatically for a DB path or connection.
2. Implement per-epic lock acquisition with an `epic_locks` row and a 60s timeout path surfaced as `epic_locked`.
3. Persist inbound messages, outbound invocation messages, bot turns, tool calls, and system logs.
4. Provide transaction helpers so tool audit rows and DB mutations commit atomically.
5. Add `tests/store_contract.py` and `tests/test_sqlite_store.py` against ephemeral SQLite databases.

### Step 6: Add centralized logger (`agent_kit/logging.py`)
**Scope:** Small
1. Implement `log(level, category, event_type, message, **context)` over the `Store` port.
2. Use it for model-call metadata and error paths; avoid production `print` outside CLI stdout/stderr contract.

## Phase 3: Tool Kit and Minimal Tools

### Step 7: Build tool registry and audit wrapper (`agent_kit/tool_kit.py`)
**Scope:** Medium
1. Add a registry that maps model tool names to Python callables and schema metadata.
2. Implement audit wrapping that records `tool_calls` with arguments, result, duration, operation kind, and event emission.
3. Ensure DB-mutating tools use one store transaction for mutation plus `tool_calls` row.
4. Add rollback tests where injected failure leaves neither the mutation nor the audit row.

### Step 8: Implement invocation communication tools (`agent_kit/tools/communication.py`)
**Scope:** Medium
1. `send_message(content, attach_files=None)`: append to reply buffer, create outbound `messages` row with synthetic `discord_message_id`, and return synthetic id.
2. `set_activity(description)`: truncate/validate short descriptions, update `bot_turns.current_activity` if stored, and emit an `activity` event.
3. `defer_to_caller(questions, reason=None)`: set turn outcome to `blocked_on_caller`, populate envelope questions, and stop the loop cleanly.
4. Confirm each tool call appears in both `tool_calls` and envelope `events`.

## Phase 4: Model Adapter and Turn Loop

### Step 9: Implement model port adapters (`agent_kit/model/anthropic.py`, tests with fake model)
**Scope:** Medium
1. Wrap Anthropic SDK calls behind `Model.complete_turn(...)` using model string `claude-opus-4-7` from the spec.
2. Convert registered tools into Anthropic tool definitions.
3. Keep request/response details summarised in `bot_turns.prompt_snapshot`, `bot_turns.reasoning`, and `system_logs` without leaking full secrets.
4. Use fake model classes in tests to return deterministic tool-use sequences.

### Step 10: Implement `run_turn` (`agent_kit/loop.py`)
**Scope:** Large
1. Acquire the per-epic lock, persist inbound message, create `bot_turns` row with `in_progress`.
2. Load minimal hot context: epic row plus recent messages/tool calls where available.
3. Call the `Model` adapter and execute requested tools until final response or blocking/error outcome.
4. Auto-call or synthesize a minimal final `send_message` if the model returns final text without explicitly calling `send_message`, so the envelope reply is never accidentally empty for completed turns.
5. Compute `state_delta` as the Sprint 1a empty artifact delta, with stable structure ready for Sprint 2 `epic_events` integration.
6. Mark turn completed/failed/abandoned, release the lock, and return a byte-stable `Envelope`.
7. Support `on_event` callback for streaming equivalence.

## Phase 5: CLI Invocation Surface

### Step 11: Add CLI package (`arnold/cli.py`, `arnold/__init__.py`)
**Scope:** Medium
1. Implement `arnold turn --epic <id> --input "text" [--from-stdin] [--stream-events] [--store sqlite] [--db PATH]`.
2. Serialize the final envelope as JSON on stdout for every outcome.
3. Emit NDJSON events to stderr only when `--stream-events` is set.
4. Map exit codes exactly: completed `0`, errored `1`, blocked_on_caller `2`, aborted `3`.
5. Keep Supabase store flag rejected with a clear `errored` envelope until Sprint 1b rather than silently pretending it works.

## Phase 6: Verification

### Step 12: Unit tests first (`tests/test_envelope.py`, `tests/test_tool_kit.py`, `tests/test_sqlite_store.py`)
**Scope:** Medium
1. Validate envelope dataclass serialization against the JSON schema.
2. Run store contract tests against ephemeral SQLite.
3. Verify tool audit atomicity and event shape.

### Step 13: Integration tests (`tests/test_run_turn.py`, `tests/test_cli.py`)
**Scope:** Large
1. Run full receive -> reason -> respond with mocked model tool calls.
2. Assert Anthropic/model invocation creates a `bot_turns` row and every tool creates a `tool_calls` row.
3. Assert envelope `events` match tool call rows for the turn.
4. Assert deterministic `state_delta` for same input/store state/model seed.
5. Assert Python `run_turn(...)` and CLI invocation produce byte-equivalent envelopes for the same fixture, modulo configured reply text normalization if the fake model intentionally varies prose.
6. Assert `--stream-events` stderr NDJSON lines match final envelope events.
7. Finish with `pytest`.

## Execution Order
1. Add `pyproject.toml`, package directories, and envelope/schema first because every later layer depends on stable serialization.
2. Build SQLite migrations and store contract before the loop so persistence bugs are isolated early.
3. Add tool registry and minimal tools before the model adapter so fake model tests can drive real tool execution.
4. Wire `run_turn` before the CLI; the CLI should be a thin serialization and exit-code layer.
5. Add broad integration tests only after unit-level store/tool behavior is proven.

## Validation Order
1. `pytest tests/test_envelope.py`
2. `pytest tests/test_sqlite_store.py tests/test_tool_kit.py`
3. `pytest tests/test_run_turn.py`
4. `pytest tests/test_cli.py`
5. `pytest` for the full suite

## Notes for Reviewers
This sprint should not use the provided Supabase service key. Supabase is explicitly later-sprint scope, and committing or relying on that key would be a security regression. SQLite is the only store implementation required here.
