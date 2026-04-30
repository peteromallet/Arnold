# Sprint 1a — agent_kit core + invocation mode

Build the foundational Python package for Arnold, a Discord planning bot. This sprint proves the substrate against the cheapest possible adapter (CLI over SQLite) before Discord/Supabase land in Sprint 1b.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to it for complete data model schemas, tool signatures, and architectural details.**

## Supabase (for later sprints)
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- `agent_kit/` package skeleton:
  - `ports.py` — Transport, Store, Model, Blob protocol definitions (abstract interfaces)
  - `loop.py` — transport-agnostic `run_turn` function
  - `tool_kit.py` — tool registry + audit-wrap decorator
  - `ledger.py` — event store skeleton
- `Envelope` dataclass + JSON schema (outcome: completed/blocked_on_caller/errored/aborted, events array, state_delta, reply)
- CLI transport adapter (pull mode): `arnold turn --epic <id> --input "text"` command; NDJSON event streaming with `--stream-events`; exit codes per envelope outcome (0=completed, 2=blocked, 1=errored, 3=aborted)
- SQLite store adapter: schema for epics, messages, bot_turns, tool_calls, system_logs tables (resident-mode-only columns nullable); migrations under `agent_kit/store/migrations/sqlite/`
- Anthropic model adapter: Claude Opus 4.7 wired to the loop
- Centralized logger module writing to system_logs via the Store port
- Agentic loop skeleton: receive → reason → respond, returns an envelope
- Minimal tool surface: `send_message` (writes to reply buffer in invocation mode), `set_activity` (emits event)
- Test harness: pytest setup, ephemeral SQLite per test, mocked Anthropic client

## Key Data Model Tables (this sprint)

### epics
id, title, goal, body (markdown), state (shaping|sprinting|planned|paused|archived), created_at, last_edited_at, last_active_at, planned_at

### messages
id, epic_id, direction (inbound|outbound), content, sent_at, discord_message_id (unique), has_code_attachment, has_image_attachment, in_burst_with, was_voice_message, audio_storage_url, transcription_metadata

### bot_turns
id, epic_id, triggered_by_message_ids (uuid array), prompt_snapshot, prompt_version, reasoning, final_output_message_id, status_message_id, status (in_progress|completed|failed|abandoned), state_at_turn, started_at, completed_at, model_version

### tool_calls
id, turn_id, tool_name, operation_kind (read|write), arguments (json), result (json), called_at, duration_ms

### system_logs
id, level (debug|info|warn|error), category, event_type, message, details (json), turn_id, epic_id, occurred_at

## Acceptance Criteria

- `arnold turn --epic <id> --input "hello"` returns a valid envelope on stdout; exit code 0 for completed, 2 for blocked_on_caller, 1 for errored, 3 for aborted
- Every Anthropic call recorded in bot_turns; every tool call recorded in tool_calls; envelope events array matches tool_calls rows
- Same input + same store state + same model seed → identical state_delta (deterministic-structure test)
- Python `run_turn(...)` produces a byte-equivalent envelope to the CLI for the same input
- `--stream-events` emits NDJSON to stderr with one event per tool call; final envelope on stdout matches
- Test suite runs green via pytest against ephemeral SQLite

## Tests

- Unit: envelope schema validation; Store port contract tests against SQLite impl; tool_kit audit-wrap atomicity
- Integration: full receive→reason→respond loop with mocked Anthropic; verify envelope contents and DB state
- Integration: CLI ↔ Python equivalence — invoke same input both ways, assert envelopes match (modulo non-deterministic reply text)

## Tech Stack
- Python 3.11+
- pytest for testing
- anthropic SDK for Claude Opus 4.7
- SQLite for local store
- Click or argparse for CLI
- dataclasses for data structures
