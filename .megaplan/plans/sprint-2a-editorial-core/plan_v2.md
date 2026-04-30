# Implementation Plan: Sprint 2a — Editorial Core (rev 2)

## Overview

Sprint 2a gives Arnold a *document* to edit. Today the codebase has an `epics` table (`supabase/migrations/202604300001_001_core.sql`), a turn loop (`agent_kit/loop.py`) that requires `epic_id` to acquire `epic_locks` before any model call, a `Store` protocol (`agent_kit/ports.py`) backed by SQLite + Postgres adapters, and a `system_logs` sink. The only registered tools are `send_message`, `set_activity`, `defer_to_caller`, `view_image`, `send_image`, `update_image_metadata`.

This sprint adds (1) two new tables (`checklist_items`, `epic_events`); (2) a body parser/serializer with section addressing; (3) Store CRUD for epics/checklist/events; (4) ~10 new tools (`create_epic`, `edit_epic`, `revert`, `render_epic`, plus reads); (5) a no-epic turn-mode so `create_epic` is callable from a fresh state; (6) a turn-end `epic_outline` log.

Constraints worth pinning up front (now reflecting critique fixes):

- **Bootstrap path:** `run_turn(epic_id=None)` is now a first-class mode. Lock acquisition is skipped; the inbound message and the `bot_turns` row are created with `epic_id=NULL` (both columns are already nullable per `supabase/migrations/202604300001_001_core.sql:22, :50`). When `create_epic` fires, it stamps `context.metadata['epic_id']`, then UPDATEs the inbound message and the turn to point at the new epic. (FLAG-001, issue_hints-1, callers.)
- **Parser split:** `parse(body)` is **lenient** — it accepts any input, including bodies missing `# Title`, bodies with no `##` headings (whole body is `_preamble`), and legacy/malformed content. Only **`validate_for_write(parsed)`** is strict and is called only by write paths. (FLAG-002, correctness-1.)
- **`_preamble` includes the `# Title` line** per spec §2606. The preamble is the raw text from the start of the body up to (but not including) the first `##` line. Replacing `_preamble` with `'# New Title\n'` therefore updates the title; removing the `# Title` line via a preamble write is rejected by `validate_for_write` with `body_missing_required_section: title`. (issue_hints-2.)
- **Title/goal columns are parser-derived only.** `create_epic` and `edit_epic` write `epics.title` and `epics.goal` exclusively from `parsed.title` and `parsed.goal_first_paragraph`. Raw `title`/`goal` arguments are template inputs only. (correctness-3.)
- **`reverted_to` events store full pre-revert state.** `prior_state = {'body': pre_revert_body, 'checklist': [...], 'reverted_transaction_id': txn, 'reverted_event_ids': [...]}` so backward replay across reverts is correct. (FLAG-003, correctness-2.)
- **Read tools register with `operation_kind='read'`.** Write tools default `operation_kind='write'`. (scope-1.)
- **`edit_epic.changes.meta` is rejected** with `meta_not_supported`: title/goal are derived columns; bot must edit `body.sections._preamble` (for title) or `body.sections.Goal` (for goal). (scope-2.)
- **Mutually exclusive body ops.** `new_content`, `sections`, `append`, `remove_sections`, `rename_section`, and `reorder` are mutually exclusive in a single `edit_epic.body`; mixing returns `body_op_conflict`.
- **`expected_diff` equivalence:** `\n` line endings, strip trailing whitespace per line, drop trailing blank lines (spec §494).
- **Out of scope:** sprints, sprint_items, codebases, code_artifacts, feedback, second_opinions, image generation. `edit_epic.changes.sprints` and `changes.state` return `not_yet_supported`.
- CLAUDE.md forbids creating a `megaplan/` directory; the existing one is harness state, not a target.

Six phases. Phases 1–3 land schema, parser, and store surface. Phase 4 lands tools. Phase 5 wires the loop bootstrap and outline log. Phase 6 covers the integration fixture.

---

## Phase 1: Schema — checklist_items, epic_events

### Step 1: Postgres migration (`supabase/migrations/202604300004_004_editorial_core.sql`)
**Scope:** Small
1. **Create** `checklist_items` matching spec §1322 exactly: `id TEXT PK`, `epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE`, `content TEXT NOT NULL`, `status TEXT CHECK IN ('open','done','skipped','superseded')`, `position INTEGER NOT NULL`, `source TEXT CHECK IN ('bot_inferred','user_requested','carried_over','default_seed','second_opinion')`, `skip_reason TEXT`, `superseded_by_item_id TEXT REFERENCES checklist_items(id)`, `created_at TIMESTAMPTZ DEFAULT now()`, `completed_at TIMESTAMPTZ`. Index `(epic_id, status, position)`.
2. **Create** `epic_events` matching spec §1381 exactly: `id TEXT PK`, `epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE`, `transaction_id TEXT NOT NULL`, `event_type TEXT CHECK IN ('body_edit','checklist_change','sprints_change','state_change','forced_handoff','created','code_referenced','codebase_added','image_generated','second_opinion_requested','reverted_to','sprint_status_change')`, `summary TEXT NOT NULL`, `prior_state JSONB`, `turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL`, `occurred_at TIMESTAMPTZ DEFAULT now()`. Indexes `(epic_id, occurred_at DESC)` and `(transaction_id)`.

### Step 2: SQLite mirror (`agent_kit/store/migrations/sqlite/004_editorial_core.sql`)
**Scope:** Small
1. **Mirror** the Postgres migration in SQLite (TEXT for everything; `prior_state` is a TEXT JSON blob, consistent with how `prompt_snapshot` etc. are handled in `001_core.sql`).
2. **Register** `prior_state` in the JSON-encoding sets at `agent_kit/store/sqlite.py:17` and `agent_kit/store/supabase.py:12`.

### Step 3: Update Supabase truncate fixture (`tests/test_supabase_store.py:33`)
**Scope:** Small
1. **Add** `checklist_items` and `epic_events` to the `TRUNCATE TABLE … RESTART IDENTITY CASCADE` block.

---

## Phase 2: Body parser/serializer

### Step 4: Parser module — lenient parse, strict validate (`agent_kit/body.py`)
**Scope:** Medium
1. **Public surface** (everything else `_private`):
   - `parse(body: str) -> ParsedBody` — **lenient**. Never raises. `ParsedBody`: `title: str | None`, `goal_first_paragraph: str | None`, `preamble: str` (raw text from byte 0 up to but not including the first `##` line; INCLUDES the `# Title` line and any blank/text lines after it), `sections: list[Section]` in order. `Section`: `name: str`, `content: str`, `subheadings: list[str]`, `line_count: int`. Title is extracted by scanning the preamble for the first non-blank line matching `^#\s+(.+?)\s*$`; if absent or empty, `title` is `None`. Goal is extracted by finding a section named exactly `Goal`, taking everything before the first blank line in its content (whitespace-stripped); if section absent or empty, `goal_first_paragraph` is `None`. Bodies with no `##` headings parse cleanly to `sections=[]` and `preamble=<entire body>`.
   - `serialize(parsed: ParsedBody) -> str` — round-trip identity for any output of `parse`. Emits `preamble` verbatim, then each `## Name\n<content>` in order.
   - `validate_for_write(parsed: ParsedBody) -> None` — **strict**, raises `BodyValidationError("body_missing_required_section: title")` if `parsed.title is None or empty`, `…goal` if `parsed.goal_first_paragraph is None or empty`. Called by every write path before `update_epic_body`.
   - `outline(parsed: ParsedBody) -> dict` — `{title, sections: [{name, line_count, subheadings}], total_lines}` for the outline log.
2. **Heading rules** (spec §503–514):
   - Section delimiters match `^##\s+(.+?)\s*$` at top level only. Level-3+ headings stay inside their parent section as content.
   - **Code-fence guard:** track ``` and ~~~ fences during the scan; `##` inside a fenced block is content, not a delimiter. Indented code blocks aren't tracked (rare in this corpus; document the gap inline).
   - Section names are case-sensitive; whitespace stripped from heading text.
3. **Section operations** (`replace_section`, `append_to_section`, `add_section(position='after:Foo'|'before:Foo'|'start'|'end')`, `remove_section`, `rename_section`, `reorder(new_order)`): pure functions on `ParsedBody`, return new `ParsedBody`. Each raises typed errors (`SectionNotFound`, `SectionExists`, `InvalidPosition`) the tool layer maps to JSON error payloads.
   - `_preamble` is addressable as a section name across these ops: `replace_section('_preamble', new_text)` overwrites the entire preamble (so `replace_section('_preamble', '# New Title\n')` updates the title; this is the spec §2606 path). `append_to_section('_preamble', …)` appends. `remove_section('_preamble')` clears the preamble to empty string. `rename_section` from/to `_preamble` is rejected with `InvalidPosition` (the preamble is a structural slot, not a renamable section).
4. **Diff helpers:**
   - `compute_diff(old: str, new: str) -> str` — `''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile='before', tofile='after', n=3))`.
   - `diffs_equivalent(a: str, b: str) -> bool` — normalises both sides per spec §494: `\r\n → \n`, strip trailing whitespace per line, drop trailing blank lines, then byte-equal compare.
5. **No third-party deps** beyond stdlib (`difflib`, `re`). No imports of Store, ports, or tool_kit — keep this module pure.

### Step 5: Default template + checklist seed (`agent_kit/templates.py`)
**Scope:** Small
1. **`DEFAULT_BODY_TEMPLATE(title, goal) -> str`** — emits the six-section design-doc skeleton (`# {title}\n\n## Goal\n\n{goal}\n\n## Principles\n\n## Context\n\n## Key Decisions\n\n## Open Questions\n\n## Deliverable\n`).
2. **`DEFAULT_CHECKLIST_SEED: list[str]`** — the 18 items from spec §634, all `source='default_seed'`, `status='open'`, positions 1–18.
3. **No adaptation logic** in v1 (settled decision SD-003); the bot adapts via post-create `edit_epic` calls.

### Step 6: Parser unit tests (`tests/test_body_parser.py`)
**Scope:** Medium
1. **Round-trip identity** for ≥6 fixtures: preamble-only (no `##`), single section, six-section design-doc, body with `### Authentication` sub-headings, body with a fenced code block containing `## Step 1`, body with non-empty preamble before first `##`. Assert `serialize(parse(b)) == b`.
2. **Section ops** (each variant): only the targeted section changes; every other section's serialised form is byte-equal.
3. **`_preamble` covers the title:** `replace_section(parse(body), '_preamble', '# New Title\n')` round-trips through `parse` to a body whose `parsed.title == 'New Title'`. Removing the `# Title` line via `replace_section('_preamble', '')` round-trips to `parsed.title is None`, and `validate_for_write` raises `body_missing_required_section: title` on the result.
4. **Lenient parse:** parsing `''`, `'just text\n'`, `'## Goal\n\ngoal\n'` (no title), `'# Title\n'` (no Goal section), `'# Title\n\n## NotGoal\n\nx\n'` (no `## Goal`) all return `ParsedBody` without raising. `validate_for_write` rejects each with the appropriate `body_missing_required_section` error.
5. **Code-fence guard:** body with ` ```\n## Inside\n``` ` parses as a single preamble (no section split).
6. **Diff equivalence:** `diffs_equivalent` returns True when only difference is `\r\n` vs `\n`, trailing spaces, or trailing blank lines; False on real content delta.

---

## Phase 3: Store surface for epics, checklist, events

### Step 7: Extend `Store` protocol (`agent_kit/ports.py`)
**Scope:** Medium
1. **Add** typed methods (Protocol + both adapters):
   - `create_epic(*, title, goal, body, state='shaping') -> JSONDict` — single-row INSERT. Caller is the tool layer, which has already parsed and validated.
   - `load_epic(epic_id) -> JSONDict | None`
   - `update_epic(epic_id, **changes) -> JSONDict` — guarded UPDATE via the existing `_update` helper, restricted to a new `_EPIC_COLUMNS = {'title', 'goal', 'body', 'state', 'last_edited_at', 'last_active_at', 'planned_at'}` set. Used by `edit_epic` and `revert` for body+title+goal updates.
   - `seed_checklist(epic_id, items: list[dict]) -> list[JSONDict]` — bulk INSERT.
   - `list_checklist_items(epic_id, *, status: str | list[str] | None = None) -> list[JSONDict]`
   - `update_checklist_item(item_id, **changes) -> JSONDict` — guarded by `_CHECKLIST_COLUMNS = {'content', 'status', 'position', 'skip_reason', 'superseded_by_item_id', 'completed_at'}`.
   - `add_checklist_items(epic_id, items, start_position) -> list[JSONDict]`
   - `delete_checklist_items(item_ids) -> int`
   - `replace_checklist(epic_id, items) -> list[JSONDict]` — used by revert: DELETE all rows for `epic_id` then bulk INSERT from snapshot. Single transaction by virtue of the wrapping `store.transaction()`.
   - `record_epic_event(*, epic_id, transaction_id, event_type, summary, prior_state, turn_id) -> JSONDict` — append-only INSERT, no update path.
   - `list_epic_events(epic_id, *, since=None, until=None, kinds=None, limit=None) -> list[JSONDict]` — ordered `(occurred_at, id) ASC`. `get_history` reverses for display.
   - `latest_transaction_id(epic_id) -> str | None`
   - `events_by_transaction(transaction_id) -> list[JSONDict]`
   - `list_recent_turns(*, n=10, epic_id=None) -> list[JSONDict]` — `bot_turns` ordered `started_at DESC LIMIT n`, optional epic filter.
   - `search_tool_calls_by(*, tool_name=None, epic_id=None, since=None, limit=20) -> list[JSONDict]` — `tool_calls` joined to `bot_turns` for the epic filter.
   - `update_message(...)` already exists; we'll reuse it from the loop bootstrap (Step 14) to retro-stamp `epic_id` on the inbound message.
   - `update_turn(...)` already exists; reused to retro-stamp `epic_id` on the bot_turns row.

### Step 8: Implement on `SupabaseStore` (`agent_kit/store/supabase.py`)
**Scope:** Medium
1. **Mirror** the protocol additions with concrete SQL using the existing `_normalize`/`_json` helpers and `_new_id` (prefixes: `'epic'`, `'check'`, `'evt'`).
2. **Add** module-level constants `_EPIC_COLUMNS` and `_CHECKLIST_COLUMNS` next to existing `_MESSAGE_COLUMNS`/`_TURN_COLUMNS`/`_IMAGE_COLUMNS`. Wire `update_epic` and `update_checklist_item` through the existing `self._update` helper for column safety.
3. **Update `_TURN_COLUMNS`** to include `'epic_id'` so the loop bootstrap (Step 14) can retro-stamp the turn after `create_epic` fires.
4. **Update `_MESSAGE_COLUMNS`** to include `'epic_id'` for the same reason.

### Step 9: Implement on `SQLiteStore` (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Mirror** the same methods, the same `_EPIC_COLUMNS`/`_CHECKLIST_COLUMNS` constants, and the same `epic_id` additions to existing message/turn column sets.
2. **Add** `'prior_state'` to `_JSON_COLUMNS`.

### Step 10: Extend the contract test (`tests/store_contract.py`)
**Scope:** Small
1. **Add** a tail block to `run_store_contract` that exercises the new surface against `epic_1`: create a second epic via `store.create_epic`, seed checklist, append events with `transaction_id`s, list/filter events, query `latest_transaction_id`, and verify ordering. Both Supabase and SQLite contract tests pick this up automatically.

---

## Phase 4: Tools — `create_epic`, `edit_epic`, `revert`, `render_epic`, reads

### Step 11: Editorial write tools (`agent_kit/tools/editorial.py`)
**Scope:** Large
1. **Register each tool** via `@register_tool` with explicit JSON schemas and `operation_kind='write'`.
2. **`create_epic(context, title, goal)`** —
   - Build body via `templates.DEFAULT_BODY_TEMPLATE(title, goal)`.
   - `parsed = body.parse(rendered)`; `body.validate_for_write(parsed)` — on `BodyValidationError`, return `{"error": "body_missing_required_section", "field": …}` (don't raise; the model needs to read the message).
   - Inside `store.transaction()`:
     - `epic = store.create_epic(title=parsed.title, goal=parsed.goal_first_paragraph, body=rendered, state='shaping')` — title and goal come **only** from `parsed.*`, never from raw args (correctness-3).
     - `store.seed_checklist(epic['id'], DEFAULT_CHECKLIST_SEED)`.
     - `store.record_epic_event(epic_id=epic['id'], transaction_id=uuid4().hex, event_type='created', summary='Epic created with default design-doc template', prior_state=None, turn_id=context.turn_id)`.
     - **Bootstrap retro-stamp** (when context.metadata['epic_id'] was None): `store.update_message(context.metadata['inbound_message_id'], epic_id=epic['id'])` and `store.update_turn(context.turn_id, epic_id=epic['id'])`. Set `context.metadata['epic_id'] = epic['id']` for downstream tools in the same turn.
   - Return `{"epic_id", "title": parsed.title, "goal": parsed.goal_first_paragraph, "section_names": [...], "checklist_count": 18, "transaction_id"}`.
3. **`edit_epic(context, epic_id, changes, change_summary, expected_diff?)`** —
   - **Reject** unsupported keys: `changes.sprints` → `{"error": "not_yet_supported", "field": "sprints"}`; `changes.state` → `{"error": "not_yet_supported", "field": "state"}`; `changes.meta` → `{"error": "meta_not_supported", "hint": "title and goal are derived from body; edit body.sections._preamble for title or body.sections.Goal for goal"}` (scope-2).
   - **Reject** mixed body ops: at most one of `new_content | sections | append | remove_sections | rename_section | reorder` per call → `{"error": "body_op_conflict"}`.
   - **Body path:** `old = store.load_epic(epic_id)['body']`; `parsed = body.parse(old)`; apply the requested op; serialise → `new_body`. `body.validate_for_write(new_parsed)`. Compute `actual_diff = body.compute_diff(old, new_body)`. If `expected_diff` provided and `not body.diffs_equivalent(expected_diff, actual_diff)`, return `{"error": "expected_diff_mismatch", "actual_diff": actual_diff}` and **do not write**.
   - **Checklist path:** apply `add` (positions auto-assigned to `max(existing.position) + 1` if absent; else honour and shift), `update` (per-item, only `_CHECKLIST_COLUMNS`-allowed fields), `remove` (delete by id). Capture pre-op snapshot for the event.
   - **Inside one `store.transaction()`** with `transaction_id = uuid4().hex`:
     - Body: `store.update_epic(epic_id, body=new_body, title=new_parsed.title, goal=new_parsed.goal_first_paragraph, last_edited_at=now())` + `store.record_epic_event(event_type='body_edit', prior_state={'body': old, 'title': old_title, 'goal': old_goal}, summary=change_summary, transaction_id, turn_id=context.turn_id)`.
     - Checklist: apply per-item ops; `store.record_epic_event(event_type='checklist_change', prior_state={'items': [...full snapshot...]}, summary=change_summary, transaction_id, turn_id=context.turn_id)`.
   - Return `{"transaction_id", "diff": actual_diff_or_empty, "section_names": [...], "change_summary"}`.
4. **`revert(context, epic_id, event_id?=None)`** —
   - Resolve target events: no `event_id` → fetch `events_by_transaction(latest_transaction_id(epic_id))`. With `event_id` → fetch the event, then all events sharing its `transaction_id` (spec §1399).
   - **Capture pre-revert state** for the new event's `prior_state`: `{'body': current_body, 'title': current_title, 'goal': current_goal, 'checklist': [...current full snapshot...], 'reverted_transaction_id': txn, 'reverted_event_ids': [e.id for e in target_events]}`. This lets backward replay across this revert reconstruct correctly (FLAG-003, correctness-2).
   - Apply each target event's `prior_state` in reverse-occurred order: `body_edit` → `store.update_epic(epic_id, body=…, title=…, goal=…)`; `checklist_change` → `store.replace_checklist(epic_id, prior_items)`. (Other event types in the transaction — e.g., a future `state_change` — are no-ops in Sprint 2a; bot won't trigger them.)
   - Append a new `reverted_to` event with the captured pre-revert `prior_state` and a fresh `transaction_id`. The event is itself revertible because its `prior_state` carries the full pre-revert snapshot.
   - Return `{"transaction_id", "reverted_event_count", "summary": f'Reverted transaction {txn}'}`.
5. **`render_epic(context, epic_id, format='markdown')`** — `'markdown'` returns the body as-is (image-reference resolution is a Sprint 6 no-op). `'html'` → `{"error": "not_yet_supported"}`.

### Step 12: Editorial read tools (`agent_kit/tools/editorial_reads.py`)
**Scope:** Medium
1. **Register** each tool with **`operation_kind='read'`** (scope-1).
2. **`get_epic(epic_id, sections=None)`** — `parsed = body.parse(epic['body'])`. Return `{title: parsed.title, goal: parsed.goal_first_paragraph, body_full: epic['body'] if sections is None else None, sections: {name: content, …} when sections is supplied, section_names: [s.name for s in parsed.sections], state}`. Lenient parse means malformed bodies still load.
3. **`get_section_names(epic_id)`** — return `[s.name for s in body.parse(epic['body']).sections]`.
4. **`get_history(epic_id, kind=None, since=None)`** — `store.list_epic_events(...)` reversed (most recent first), optionally filtered.
5. **`get_self_understanding(epic_id)`** — return `{goal, state, open_checklist_count, section_names, recent_events: last 3}`. Document inline that the spec §1068 7-section structure (recent decisions, code refs, second opinions, etc.) lights up incrementally as later sprints land their tables.
6. **`get_epic_at_time(epic_id, timestamp)`** — backward replay from current state:
   - Load current `body, checklist`.
   - Fetch `list_epic_events(epic_id)` (full ascending list).
   - Walk the events whose `occurred_at > timestamp` in **descending** order; for each, undo using `prior_state`:
     - `body_edit`: `body = prior_state['body']`.
     - `checklist_change`: `checklist = prior_state['items']`.
     - `created`: this is the earliest possible state; if we're rolling past it, return empty/None body+checklist (caller asked for a time before the epic existed).
     - `reverted_to`: undo by restoring `prior_state['body']` and `prior_state['checklist']` (the captured pre-revert snapshot — Step 11.4 makes this work).
     - Other event_types (sprints, state, code_referenced, etc., none of which fire in Sprint 2a) fall through with a logged warning.
   - Tied timestamps order by `(occurred_at, id) ASC`; when walking descending, reverse that.
   - Return `{body, checklist, reconstructed_at: timestamp}`.
7. **`get_recent_turns(n=10, epic_id=None)`** — `store.list_recent_turns(...)`; for each turn, attach `change_summary` aggregated from `epic_events` rows with that `turn_id` (single `WHERE turn_id IN (...)` query joined client-side).
8. **`search_tool_calls(tool_name=None, epic_id=None, since=None, limit=20)`** — delegates to `store.search_tool_calls_by(...)`.

### Step 13: Register the tools in the loop import path (`agent_kit/loop.py:16`)
**Scope:** Small
1. **Add** `import agent_kit.tools.editorial  # noqa: F401` and `import agent_kit.tools.editorial_reads  # noqa: F401` next to existing `communication`/`images` imports so tools auto-register.

---

## Phase 5: Loop bootstrap + turn-end outline log

### Step 14: No-epic turn mode (`agent_kit/loop.py:25` and surrounding)
**Scope:** Medium
1. **Make `epic_id` Optional** on `run_turn` and propagate through downstream code paths:
   - When `epic_id is None`: skip `store.acquire_epic_lock` entirely. Skip the lock-contended early return.
   - Inbound message creation (`agent_kit/loop.py:79–85`): `epic_id=None` is already nullable (`messages.epic_id` is FK with `ON DELETE SET NULL`, NULL allowed). Capture the resulting `inbound_message_id` in `context.metadata['inbound_message_id']` so `create_epic` can retro-stamp.
   - `store.create_turn(epic_id=None, …)` is allowed (`bot_turns.epic_id` already nullable). The turn row carries NULL until `create_epic` retro-stamps it.
   - `load_hot_context` is currently `load_hot_context(epic_id)` and dereferences `epic`; in no-epic mode, skip the call and pass `hot_context = {"epic": None, "recent_messages": [], "recent_tool_calls": []}` to the model.
   - After every tool invocation, if `context.metadata.get('epic_id')` flipped from None to a real id (set by `create_epic`'s post-commit hook in Step 11.2), the loop's lock-release path must skip — there was no lock to release.
2. **CLI plumbing (`arnold/cli.py`):** allow invoking with no `--epic-id` (or an explicit `--no-epic` flag); pass `epic_id=None` to `run_turn`. The system prompt for that branch should hint "no active epic — call `create_epic(title, goal)` first if the user is starting one."
3. **Existing callers** (`tests/test_run_turn.py`) keep passing an `epic_id` and continue to work unchanged. The no-epic path is purely additive.

### Step 15: Turn-end `epic_outline` log (`agent_kit/loop.py`)
**Scope:** Small
1. **At the end of `run_turn`**, after `update_turn(status='completed', …)` and before envelope return: if `context.metadata.get('epic_id')` is set AND any tool_call this turn had `tool_name in {'create_epic','edit_epic','revert'}` (walk `events`), then `parsed = body.parse(store.load_epic(epic_id)['body'])`, `details = body.outline(parsed)`, and call `log(store, 'info', 'application', 'epic_outline', f"Epic outline: {parsed.title or '(untitled)'}", details=details, turn_id=turn['id'], epic_id=epic_id)`.
2. **Failure paths** (`status='failed'`) skip the log. Pure-read turns and turns that never created an epic skip the log.

---

## Phase 6: Integration test + regression verification

### Step 16: 10-turn fixture (`tests/test_editorial_loop.py`)
**Scope:** Medium
1. **Use** `FakeModel(script=…)` (per `tests/test_run_turn.py:8`) and `SQLiteStore` with a deterministic 10-turn script:
   - Turn 1: `run_turn(epic_id=None, input='Make me an auth flow design epic')` → tool_use `create_epic(title='Auth flow design', goal='Decide on auth provider and token storage')` → final text.
   - Turns 2–9: `run_turn(epic_id=<the new id>)` with `edit_epic` calls hitting **all six default sections** at least once via `sections` ops, plus a `_preamble` replace that updates the title (asserts `epics.title` reflects the new value), plus an `append`, plus a `checklist.update` marking 3 items done. Include one `expected_diff` round-trip (matching) and one mismatch turn (asserts DB unchanged).
   - Turn 10: `revert` (most recent transaction) followed by `send_message`.
2. **Assertions** — one per spec §131–142 acceptance criterion plus the critique-driven additions:
   - After Turn 1: `epics` row exists with `title='Auth flow design'`, `goal='Decide on auth provider and token storage'`; 18 `checklist_items` with `source='default_seed'`; one `created` event; the inbound message and bot_turn both have `epic_id` retro-stamped.
   - After all turns: every default section present; section-only edits leave other sections byte-identical (verified by re-parsing prior_state captured in `body_edit` events).
   - Whole-body `new_content` turn: `body_edit` event captured prior body; manual `revert(epic_id, event_id=that_event)` then `load_epic` returns prior body byte-equal.
   - "revert that" turn: most-recent transaction undone; new `reverted_to` event present; `prior_state` contains body + checklist snapshots (FLAG-003 verification).
   - `expected_diff` mismatch turn: tool result has `error='expected_diff_mismatch'`; epics + checklist unchanged.
   - `expected_diff` match turn: writes commit normally.
   - **Title-via-preamble turn:** before/after `epics.title` differs; the same transaction's `body_edit` event captured the old title in `prior_state`.
   - `get_epic_at_time(epic_id, T_after_turn_5)` returns body + checklist matching a hand-rolled replay computed inside the test.
   - `get_epic_at_time(epic_id, T_just_before_revert)` returns body+checklist as it was right before the revert (verifies FLAG-003 fix end-to-end).
   - `get_recent_turns(5)` returns 5 turns most-recent-first.
   - `search_tool_calls(tool_name='edit_epic', epic_id=…)` returns ≥3 rows.
   - One `system_logs` row per touching turn with `event_type='epic_outline'`, `category='application'`, and `details.sections` containing all six default headings (after the relevant turns).
   - `tool_calls.operation_kind` for `get_epic`, `get_section_names`, `get_history`, etc. is `'read'`; for `create_epic`, `edit_epic`, `revert`, `render_epic` is `'write'` (scope-1 verification).
   - Calling `edit_epic(changes={'meta': {'title': 'X'}})` returns `error='meta_not_supported'` (scope-2 verification).

### Step 17: Run the targeted tests, then full regression
**Scope:** Small
1. `pytest tests/test_body_parser.py -x`.
2. `pytest tests/test_sqlite_store.py tests/test_sqlite_store_v1b.py -x` to confirm the new contract additions pass.
3. `pytest tests/test_editorial_loop.py -x`.
4. `pytest -x` for the full suite (no Sprint 1a/1b regression).
5. **Optional:** `SUPABASE_TEST_DB_URL=… pytest tests/test_supabase_store.py` if a local Supabase is available.

---

## Execution Order

1. Schema first (Phase 1) — migrations unblock everything.
2. Body parser + templates with their unit tests (Phase 2). Pure code, fastest feedback. Land lenient parse + strict validate split before building anything that depends on it.
3. Store extensions (Phase 3) — column-safety constants + new methods, exercised through the contract test.
4. Tools (Phase 4) — depends on parser + store. Write tools first (`create_epic`, `edit_epic`, `revert`, `render_epic`), then reads.
5. Loop bootstrap + outline log (Phase 5) — depends on tools. Bootstrap first (FLAG-001) so `create_epic` is callable; then outline log.
6. Integration fixture (Phase 6) — proves the whole pipeline + every critique fix end-to-end.

## Validation Order

1. `pytest tests/test_body_parser.py` — fastest feedback on parser edge cases (lenient/strict split, `_preamble` title).
2. Contract tests (`tests/test_sqlite_store.py`, `tests/test_supabase_store.py` when DB available) — confirms new Store surface is consistent across adapters and column-safety holds.
3. `pytest tests/test_editorial_loop.py` — the 10-turn integration with bootstrap, time-travel-across-revert, `_preamble`-title, and `meta_not_supported` assertions.
4. `pytest -x` — full regression.
