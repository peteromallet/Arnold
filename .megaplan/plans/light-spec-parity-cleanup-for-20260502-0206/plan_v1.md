# Implementation Plan: Light Spec Parity Cleanup

## Overview
The goal is a narrow parity cleanup between `planning-bot-spec.md` and the current implementation. The repo already implements `from arnold import run_turn, Envelope`, CLI event streaming to `stderr`, invocation image-only attachments, `generate_image` as create/store-only, and the `system_seq` idempotency formula in `agent_kit/ledger.py`. The main work is to fix contradictory spec text and add only low-risk tool-name aliases where existing Store behavior already supports them.

The worktree is dirty, including many unrelated `.megaplan/`, generated, and implementation files. The implementation should touch only `planning-bot-spec.md`, `agent_kit/tools/editorial_reads.py`, and focused tests unless inspection during execution proves a nearby test file is the better location. Do not refactor Store/ports, implement HTTP/FastAPI/asyncpg, or alter unrelated dirty files.

## Main Phase

### Step 1: Patch public API and stream wording (`planning-bot-spec.md`)
**Scope:** Small
1. Replace the Callable API Python example import with `from arnold import run_turn, Envelope`.
2. Make invocation event stream wording consistently say CLI streams progress NDJSON to `stderr`, while the final envelope stays on `stdout`.
3. Update the execution-mode table and envelope `events` field semantics where they still refer to live events on `stdout`.

### Step 2: Align image and attachment semantics (`planning-bot-spec.md`)
**Scope:** Small
1. Fix `send_image` / `generate_image` wording so `generate_image` creates the image, writes Storage plus `images`, and returns image metadata only.
2. Ensure all user-facing surfacing language says `send_image` posts to Discord in resident mode or emits an `attached_image` envelope event in invocation mode.
3. Remove remaining text implying `generate_image` posts to Discord as part of its own effect, including the Idempotency and Recovery example.
4. Update invocation attachment wording to match the current tranche: CLI/Python support image attachments only; invocation audio is explicitly deferred. HTTP remains deferred and should not imply current image/audio multipart support.

### Step 3: Align external request idempotency text (`planning-bot-spec.md`)
**Scope:** Small
1. Update the `external_requests` readiness-gate formula for system requests to include `system_seq`, matching `agent_kit/ledger.py`:
   ```text
   sha256(turn_id:system:provider:endpoint:system_seq)[:16]
   ```
2. Keep the existing tool-call formula intact:
   ```text
   sha256(turn_id:tool_call_id:provider:endpoint:canonical_request_summary)[:16]
   ```
3. Mention `system_seq` as a per-turn ordinal for system-level external calls where `tool_call_id` is null.

### Step 4: Reconcile lightweight read-tool names (`agent_kit/tools/editorial_reads.py`)
**Scope:** Medium
1. Add exact aliases only where behavior is already backed by existing Store methods:
   - `get_checklist(epic_id, status?)` -> `context.store.list_checklist_items(epic_id, status=status)`.
   - `get_sprints(epic_id)` -> `context.store.list_sprints_with_items(epic_id)`.
   - `recent_messages(epic_id, n=10)` -> a thin read over existing hot-context/recent-message data, returning the same recent conversation rows the loop already loads.
2. Register all three as `operation_kind="read"` and add schemas consistent with local `additionalProperties: False` style.
3. Do not add `transcribe_voice` as a tool in this pass. Update the spec to describe it as automatic resident ingestion behavior and mark invocation audio/transcription as deferred, because the current implementation performs voice transcription in `agent_kit/transport/discord.py` rather than through a bot-callable tool.
4. Preserve existing canonical tools (`get_epic`, `search_messages`, etc.) and avoid renaming or replacing them.

### Step 5: Add focused regression coverage (`tests/`)
**Scope:** Small
1. Add or extend tests near `tests/test_editorial_loop.py` or `tests/test_sprints.py` to assert the new aliases are registered, read-only, and return checklist/sprint/recent-message payloads from existing store data.
2. Add a small public API assertion near `tests/test_megaplan_arnold_import.py` or a new focused test to confirm `arnold.run_turn` and `arnold.Envelope` export the intended callable API.
3. Keep tests independent of network, Supabase, Discord, Groq, and OpenAI.

### Step 6: Validate narrowly, then broadly enough
**Scope:** Small
1. Run cheap targeted tests first:
   ```bash
   python -m pytest tests/test_editorial_loop.py tests/test_sprints.py tests/test_megaplan_arnold_import.py tests/test_cli.py tests/test_ledger.py tests/test_image_tools.py
   ```
2. If failures indicate the chosen alias-test file is too broad or slow, run the specific affected test nodes while iterating, then repeat the targeted set.
3. Optionally run the full suite only if targeted tests pass and time allows, because this is mostly spec parity plus read aliases.

## Execution Order
1. Update `planning-bot-spec.md` first, because most requested issues are documentation parity and the exact intended language guides the alias work.
2. Add the trivial read aliases after confirming existing Store methods cover them without Store/ports changes.
3. Add tests for aliases and public exports last, then run targeted checks.

## Validation Order
1. Verify docs with `rg` for stale phrases: `from megaplan.arnold`, stream events on `stdout`, `generate_image` creates and sends, invocation audio support language, and old system idempotency formula.
2. Run focused alias/API tests.
3. Run CLI, ledger, and image tests to catch regressions in the surfaces whose spec text changed.
