# Implementation Plan: Light Spec Parity Cleanup

## Overview
This revision keeps the same root cause: the current implementation and `planning-bot-spec.md` disagree in a few narrow places. No critique flags indicated the plan was targeting the wrong code or solving the wrong problem, so the approach remains a small spec parity pass plus only trivial read-tool aliases where existing Store behavior already backs the names.

The repository already exposes `run_turn` and `Envelope` from `arnold/__init__.py`, streams CLI progress events to `stderr` in `arnold/cli.py`, accepts invocation image attachments through `agent_kit/attachments.py` and `agent_kit/loop.py`, separates `generate_image` from `send_image` in `agent_kit/tools/images.py`, and derives system-request idempotency keys with `system_seq` in `agent_kit/ledger.py`. The plan should not touch Store/ports, HTTP/FastAPI/asyncpg, or unrelated dirty worktree files.

## Main Phase

### Step 1: Patch public API and stream wording (`planning-bot-spec.md`)
**Scope:** Small
1. Replace the Callable API Python example import with:
   ```python
   from arnold import run_turn, Envelope
   ```
2. Make invocation event stream wording consistently say CLI progress NDJSON goes to `stderr`, while the final envelope remains on `stdout`.
3. Update the execution-mode table and envelope `events` field semantics where they still describe live events as `stdout`.
4. Do not remove or change the `megaplan/arnold` compatibility shim or its tests; this is a public spec wording change, not a compatibility cleanup.

### Step 2: Align image and attachment semantics (`planning-bot-spec.md`)
**Scope:** Small
1. Fix `send_image` / `generate_image` wording so `generate_image` creates the image, writes Storage plus the `images` row, and returns image metadata only.
2. Ensure surfacing language says `send_image` posts to Discord in resident mode or emits an `attached_image` envelope event in invocation mode.
3. Remove remaining text implying `generate_image` posts to Discord as part of its own effect, including the Idempotency and Recovery example.
4. Update invocation attachment wording to match the implemented tranche: CLI/Python support image attachments only; invocation audio is explicitly deferred; HTTP remains future work and should not imply current multipart image/audio support.

### Step 3: Align external request idempotency text (`planning-bot-spec.md`)
**Scope:** Small
1. Update the system-request formula to match `agent_kit/ledger.py`:
   ```text
   sha256(turn_id:system:provider:endpoint:system_seq)[:16]
   ```
2. Preserve the tool-call formula based on `turn_id`, `tool_call_id`, provider, endpoint, and canonical request summary.
3. Define `system_seq` as a per-turn ordinal for system-level external calls where `tool_call_id` is null.

### Step 4: Reconcile lightweight tool-name parity (`agent_kit/tools/editorial_reads.py`, `planning-bot-spec.md`)
**Scope:** Medium
1. Add exact read aliases only when the implementation is one thin call over existing behavior:
   - `get_checklist(epic_id, status?)` -> `context.store.list_checklist_items(epic_id, status=status)`.
   - `get_sprints(epic_id)` -> `context.store.list_sprints_with_items(epic_id)`.
   - `recent_messages(epic_id, n=10)` -> return the recent conversation rows already exposed through `context.store.load_hot_context(epic_id)["recent_messages"]`, trimmed to `n`.
2. Register all three aliases as `operation_kind="read"` with local JSON-schema style (`additionalProperties: False`). Return payloads keyed by their tool names: `checklist`, `sprints`, and `recent_messages`.
3. Do not add `transcribe_voice` as a tool. Update the spec to describe voice transcription as automatic resident ingestion behavior, with invocation audio/transcription deferred.
4. Preserve existing canonical tools and behavior; these aliases must not rename, replace, or wrap Store/ports.

### Step 5: Add focused regression coverage (`tests/`)
**Scope:** Small
1. Add a focused test near the editorial read/sprint tests to assert `get_checklist`, `get_sprints`, and `recent_messages` are registered as read tools and return expected payloads from existing SQLite test data.
2. Add or extend a public API test to assert `arnold.run_turn` and `arnold.Envelope` export the intended callable API.
3. Keep tests local-only and independent of Supabase, Discord, Groq, OpenAI, and network.

### Step 6: Validate narrowly
**Scope:** Small
1. Use `rg` to verify stale spec phrases are gone or intentionally retained only in compatibility-test context:
   ```bash
   rg -n "from megaplan\.arnold|stdout \(NDJSON\)|emitted live on stdout|generate_image.*creates AND sends|image/audio|transcribe_voice" planning-bot-spec.md
   ```
2. Run focused tests first, using specific nodes if added:
   ```bash
   python -m pytest tests/test_megaplan_arnold_import.py tests/test_editorial_loop.py tests/test_sprints.py tests/test_cli.py tests/test_ledger.py tests/test_image_tools.py
   ```
3. If the alias tests land in a new file, include that file instead of relying on broad nearby suites.
4. Inspect the final diff to confirm only `planning-bot-spec.md`, the lightweight alias code if needed, and focused tests changed.

## Execution Order
1. Patch `planning-bot-spec.md` first so the source of truth matches implemented behavior.
2. Add read aliases only after confirming they remain thin calls over current Store behavior.
3. Add focused tests for the aliases and `arnold` exports.
4. Run targeted validation and inspect the diff for scope control.

## Validation Order
1. Start with `rg` checks over `planning-bot-spec.md` for stale parity problems.
2. Run focused unit tests for any alias/API changes.
3. Run CLI, ledger, and image tests to catch regressions in surfaces whose spec text changed.
4. Use `git diff -- planning-bot-spec.md agent_kit/tools/editorial_reads.py tests/...` rather than broad worktree cleanup, preserving unrelated dirty changes.
