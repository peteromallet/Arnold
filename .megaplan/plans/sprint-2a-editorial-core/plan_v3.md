# Implementation Plan: Sprint 2a — Editorial Core (rev 3)

## Overview

Sprint 2a gives Arnold a *document* to edit. Today the codebase has an `epics` table (`supabase/migrations/202604300001_001_core.sql`), a turn loop (`agent_kit/loop.py`) that requires `epic_id` to acquire `epic_locks` before any model call, a `Store` protocol (`agent_kit/ports.py`) backed by SQLite + Postgres adapters, an `Envelope` dataclass (`agent_kit/envelope.py:48`) and JSON schema (`agent_kit/envelope.schema.json:29`) that both require a non-empty `epic_id` string, a CLI (`arnold/cli.py:45`) with `--epic` required, and a `system_logs` sink. The only registered tools are `send_message`, `set_activity`, `defer_to_caller`, `view_image`, `send_image`, `update_image_metadata`.

This sprint adds (1) two new tables (`checklist_items`, `epic_events`); (2) a body parser/serializer with section addressing; (3) Store CRUD for epics/checklist/events; (4) ~10 new tools (`create_epic`, `edit_epic`, `revert`, `render_epic`, plus reads); (5) a no-epic turn-mode threaded consistently through the loop, Store protocol, Envelope, JSON schema, and CLI; (6) a turn-end `epic_outline` log.

Constraints worth pinning up front (now reflecting all critique fixes):

- **Bootstrap path threaded through every boundary.** `run_turn(epic_id: Optional[str] = None)`. The DB columns `messages.epic_id`, `bot_turns.epic_id`, and `system_logs.epic_id` are already nullable. Rev 3 also makes the public surface match: `Store.create_turn(epic_id: str | None)`, `Envelope.epic_id: str | None`, `envelope.schema.json` allows `null`, CLI `--epic` is optional, `loop.py` uses an `active_epic_id` local that is updated by `create_epic` before every envelope/abort return. (FLAG-001, FLAG-005, issue_hints-1, all_locations, correctness, callers-1, callers-2.)
- **Parser split:** `parse(body)` is **lenient** — accepts any input, never raises. **`validate_for_write(parsed)`** is **strict** and called only by write paths. (FLAG-002, correctness-1.)
- **`_preamble` includes the `# Title` line** per spec §2606. Replace via `replace_section('_preamble', '# New Title\n')` is the canonical title-edit path. (issue_hints-2 rev1.)
- **Title/goal columns are parser-derived only.** (correctness-3.)
- **`reverted_to` events store full pre-revert body, title, goal, and checklist snapshot in `prior_state`** so backward replay across reverts is correct. (FLAG-003, correctness-2.)
- **Read tools register with `operation_kind='read'`.** (scope-1.)
- **`edit_epic.changes.meta` is rejected** with `meta_not_supported`. (scope-2.)
- **Mutually-exclusive body ops** in a single `edit_epic.body` payload; mixing returns `body_op_conflict`.
- **`expected_diff` equivalence:** `\n` line endings, strip trailing whitespace per line, drop trailing blank lines (spec §494).
- **Out of scope:** sprints, sprint_items, codebases, code_artifacts, feedback, second_opinions, image generation. `edit_epic.changes.sprints` and `changes.state` return `not_yet_supported`.
- **`body_version` (spec §2606 example) is intentionally deferred.** The main Data Model (spec §1311–1320) does not define a `body_version` column. The audit trail in `epic_events.body_edit` already captures every body mutation atomically with title/goal updates, which satisfies the title/body sync acceptance test (#7) without introducing a new column. Adding `body_version` later is an additive migration. (issue_hints-2 rev2 — accepted tradeoff.)
- CLAUDE.md forbids creating a `megaplan/` directory; the existing one is harness state, not a target.

Six phases. Phases 1–3 land schema, parser, and store surface. Phase 4 lands tools. Phase 5 wires the loop bootstrap (now thread-complete across protocol/envelope/schema/CLI) and outline log. Phase 6 covers the integration fixture.

---

## Phase 1: Schema — checklist_items, epic_events

### Step 1: Postgres migration (`supabase/migrations/202604300004_004_editorial_core.sql`)
**Scope:** Small
1. **Create** `checklist_items` matching spec §1322: `id TEXT PK`, `epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE`, `content TEXT NOT NULL`, `status TEXT CHECK IN ('open','done','skipped','superseded')`, `position INTEGER NOT NULL`, `source TEXT CHECK IN ('bot_inferred','user_requested','carried_over','default_seed','second_opinion')`, `skip_reason TEXT`, `superseded_by_item_id TEXT REFERENCES checklist_items(id)`, `created_at TIMESTAMPTZ DEFAULT now()`, `completed_at TIMESTAMPTZ`. Index `(epic_id, status, position)`.
2. **Create** `epic_events` matching spec §1381: `id TEXT PK`, `epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE`, `transaction_id TEXT NOT NULL`, `event_type TEXT CHECK IN ('body_edit','checklist_change','sprints_change','state_change','forced_handoff','created','code_referenced','codebase_added','image_generated','second_opinion_requested','reverted_to','sprint_status_change')`, `summary TEXT NOT NULL`, `prior_state JSONB`, `turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL`, `occurred_at TIMESTAMPTZ DEFAULT now()`. Indexes `(epic_id, occurred_at DESC)` and `(transaction_id)`.

### Step 2: SQLite mirror (`agent_kit/store/migrations/sqlite/004_editorial_core.sql`)
**Scope:** Small
1. **Mirror** the Postgres migration (TEXT for everything; `prior_state` is a TEXT JSON blob).
2. **Register** `prior_state` in `_JSON_COLUMNS` at `agent_kit/store/sqlite.py:17` and `agent_kit/store/supabase.py:12`.

### Step 3: Update Supabase truncate fixture (`tests/test_supabase_store.py:33`)
**Scope:** Small
1. **Add** `checklist_items` and `epic_events` to the `TRUNCATE TABLE … RESTART IDENTITY CASCADE` block.

---

## Phase 2: Body parser/serializer

### Step 4: Parser module — lenient parse, strict validate (`agent_kit/body.py`)
**Scope:** Medium
1. **Public surface** (everything else `_private`):
   - `parse(body: str) -> ParsedBody` — **lenient**. Never raises. `ParsedBody`: `title: str | None`, `goal_first_paragraph: str | None`, `preamble: str` (raw text from byte 0 up to but not including the first `##` line, INCLUDING the `# Title` line and any leading text), `sections: list[Section]`. `Section`: `name`, `content`, `subheadings`, `line_count`. Title is the first non-blank preamble line matching `^#\s+(.+?)\s*$`; if absent or empty → `None`. Goal is the first paragraph (text before first blank line, whitespace-stripped) of the section named exactly `Goal`; if absent or empty → `None`. Bodies with no `##` headings: `sections=[]`, `preamble=<entire body>`.
   - `serialize(parsed: ParsedBody) -> str` — round-trip identity.
   - `validate_for_write(parsed: ParsedBody) -> None` — **strict**. Raises `BodyValidationError("body_missing_required_section: title")` or `…goal`. Called by every write path.
   - `outline(parsed: ParsedBody) -> dict` — `{title, sections: [{name, line_count, subheadings}], total_lines}`.
2. **Heading rules** (spec §503–514): `^##\s+(.+?)\s*$` at top level only; `###`+ stay inside parents; track ``` and ~~~ fences (indented code-block edge case documented but not handled in v1); section names case-sensitive.
3. **Section operations** as pure functions on `ParsedBody`: `replace_section`, `append_to_section`, `add_section(position='after:Foo'|'before:Foo'|'start'|'end')`, `remove_section`, `rename_section`, `reorder(new_order)`. Typed errors: `SectionNotFound`, `SectionExists`, `InvalidPosition`. `_preamble` is addressable: `replace_section('_preamble', '# New Title\n')` updates the title (spec §2606); `rename_section` from/to `_preamble` rejected.
4. **Diff helpers:** `compute_diff(old, new)` wraps `difflib.unified_diff(splitlines(keepends=True), …, n=3)`; `diffs_equivalent(a, b)` normalises per spec §494 (`\r\n→\n`, strip trailing whitespace per line, drop trailing blank lines).
5. **No third-party deps** beyond stdlib (`difflib`, `re`). No imports of Store/ports/tool_kit.

### Step 5: Default template + checklist seed (`agent_kit/templates.py`)
**Scope:** Small
1. **`DEFAULT_BODY_TEMPLATE(title, goal) -> str`** emits the six-section design-doc skeleton.
2. **`DEFAULT_CHECKLIST_SEED: list[str]`** — 18 items from spec §634, all `source='default_seed'`, `status='open'`, positions 1–18.
3. **No adaptation logic** in v1 (settled SD-004); the bot adapts via post-create `edit_epic` calls.

### Step 6: Parser unit tests (`tests/test_body_parser.py`)
**Scope:** Medium
1. **Round-trip identity** for ≥6 fixtures (preamble-only, single section, six-section template, sub-headings, fenced `## Step 1`, non-empty preamble before first `##`).
2. **Section ops** — only the targeted section changes; every other section's serialised form byte-equal.
3. **`_preamble` covers the title** — `replace_section('_preamble', '# New Title\n')` round-trips to `parsed.title=='New Title'`; replacing with `''` round-trips to `title=None` and `validate_for_write` raises `body_missing_required_section: title`.
4. **Lenient parse** — `''`, `'just text\n'`, `'## Goal\n\ngoal\n'` (no title), `'# Title\n'` (no Goal), `'# Title\n\n## NotGoal\n\nx\n'` all return `ParsedBody` without raising; `validate_for_write` rejects each.
5. **Code-fence guard** — body with ` ```\n## Inside\n``` ` parses as a single preamble.
6. **Diff equivalence** — true on `\r\n` vs `\n` / trailing-space / trailing-blank-line differences only; false on real content delta.

---

## Phase 3: Store surface for epics, checklist, events

### Step 7: Extend `Store` protocol (`agent_kit/ports.py`)
**Scope:** Medium
1. **Add** typed methods (Protocol + both adapters):
   - `create_epic(*, title, goal, body, state='shaping') -> JSONDict`
   - `load_epic(epic_id) -> JSONDict | None`
   - `update_epic(epic_id, **changes) -> JSONDict` — guarded by `_EPIC_COLUMNS = {'title', 'goal', 'body', 'state', 'last_edited_at', 'last_active_at', 'planned_at'}`.
   - `seed_checklist(epic_id, items: list[dict]) -> list[JSONDict]`
   - `list_checklist_items(epic_id, *, status=None) -> list[JSONDict]`
   - `update_checklist_item(item_id, **changes) -> JSONDict` — guarded by `_CHECKLIST_COLUMNS = {'content', 'status', 'position', 'skip_reason', 'superseded_by_item_id', 'completed_at'}`.
   - `add_checklist_items(epic_id, items, start_position) -> list[JSONDict]`
   - `delete_checklist_items(item_ids) -> int`
   - `replace_checklist(epic_id, items) -> list[JSONDict]` — DELETE all + bulk INSERT.
   - `record_epic_event(*, epic_id, transaction_id, event_type, summary, prior_state, turn_id) -> JSONDict`
   - `list_epic_events(epic_id, *, since=None, until=None, kinds=None, limit=None) -> list[JSONDict]` ordered `(occurred_at, id) ASC`.
   - `latest_transaction_id(epic_id) -> str | None`
   - `events_by_transaction(transaction_id) -> list[JSONDict]`
   - `list_recent_turns(*, n=10, epic_id=None) -> list[JSONDict]` — `bot_turns` ordered `started_at DESC LIMIT n`.
   - `search_tool_calls_by(*, tool_name=None, epic_id=None, since=None, limit=20) -> list[JSONDict]`.
2. **Update** `Store.create_turn` signature in the Protocol and both adapters to `epic_id: str | None` (callers-2). The DB column already permits NULL.
3. **Update** `Store.create_message`, `update_message`, `update_turn`, and `log_system_event` already accept `epic_id` parameters of type `str | None`; verify no type narrowing is required and adjust if needed.

### Step 8: Implement on `SupabaseStore` (`agent_kit/store/supabase.py`)
**Scope:** Medium
1. **Mirror** the protocol additions with concrete SQL using existing `_normalize`/`_json` helpers and `_new_id` (prefixes `'epic'`, `'check'`, `'evt'`).
2. **Add** module-level `_EPIC_COLUMNS` and `_CHECKLIST_COLUMNS` next to `_MESSAGE_COLUMNS`/`_TURN_COLUMNS`/`_IMAGE_COLUMNS`. Wire `update_epic` and `update_checklist_item` through `self._update`.
3. **Update `_TURN_COLUMNS`** to include `'epic_id'`. **Update `_MESSAGE_COLUMNS`** to include `'epic_id'`.
4. **Confirm** `create_turn` parameter type is `str | None` and the existing INSERT (`agent_kit/store/supabase.py:113`) already passes it through unchanged (Postgres allows NULL on `bot_turns.epic_id`).

### Step 9: Implement on `SQLiteStore` (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Mirror** Step 8: same methods, same `_EPIC_COLUMNS`/`_CHECKLIST_COLUMNS` constants, same `epic_id` additions to `_MESSAGE_COLUMNS`/`_TURN_COLUMNS`.
2. **Add** `'prior_state'` to `_JSON_COLUMNS`. **Confirm** `create_turn` accepts `epic_id: str | None`.

### Step 10: Extend the contract test (`tests/store_contract.py`)
**Scope:** Small
1. **Add** a tail block exercising the new surface: create an epic, seed checklist, append events with `transaction_id`s, list/filter events, query `latest_transaction_id`, verify ordering.
2. **Add** an explicit assertion that `create_turn(epic_id=None)` succeeds and the row stores NULL.

---

## Phase 4: Tools — `create_epic`, `edit_epic`, `revert`, `render_epic`, reads

### Step 11: Editorial write tools (`agent_kit/tools/editorial.py`)
**Scope:** Large
1. **Register each tool** via `@register_tool` with explicit JSON schemas and `operation_kind='write'`.
2. **`create_epic(context, title, goal)`** —
   - Build body via `templates.DEFAULT_BODY_TEMPLATE(title, goal)`.
   - `parsed = body.parse(rendered)`; `body.validate_for_write(parsed)` — on `BodyValidationError`, return `{"error": "body_missing_required_section", "field": …}`.
   - Inside `store.transaction()`:
     - `epic = store.create_epic(title=parsed.title, goal=parsed.goal_first_paragraph, body=rendered, state='shaping')` (correctness-3: parsed values, never raw args).
     - `store.seed_checklist(epic['id'], DEFAULT_CHECKLIST_SEED)`.
     - `store.record_epic_event(epic_id=epic['id'], transaction_id=uuid4().hex, event_type='created', summary='Epic created with default design-doc template', prior_state=None, turn_id=context.turn_id)`.
     - **Bootstrap retro-stamp:** `store.update_message(context.metadata['inbound_message_id'], epic_id=epic['id'])` and `store.update_turn(context.turn_id, epic_id=epic['id'])`. Set `context.metadata['epic_id'] = epic['id']`.
   - Return `{"epic_id", "title", "goal", "section_names", "checklist_count": 18, "transaction_id"}`.
3. **`edit_epic(context, epic_id, changes, change_summary, expected_diff?)`** —
   - **Reject** unsupported keys: `changes.sprints` / `changes.state` → `not_yet_supported`; `changes.meta` → `meta_not_supported` with hint to use `body.sections._preamble` (title) or `body.sections.Goal` (goal).
   - **Reject** mixed body ops (`new_content | sections | append | remove_sections | rename_section | reorder`) → `body_op_conflict`.
   - **Body path:** load → parse → apply op → serialise → `validate_for_write` → `compute_diff`. If `expected_diff` provided and `not diffs_equivalent(...)`, return `{"error":"expected_diff_mismatch", "actual_diff":...}` and **do not write**.
   - **Checklist path:** apply add/update/remove with snapshot capture for the event.
   - **Inside one `store.transaction()`** with `transaction_id = uuid4().hex`:
     - Body: `store.update_epic(epic_id, body=new_body, title=new_parsed.title, goal=new_parsed.goal_first_paragraph, last_edited_at=now())` + `record_epic_event(event_type='body_edit', prior_state={'body': old, 'title': old_title, 'goal': old_goal})`.
     - Checklist: per-item ops + `record_epic_event(event_type='checklist_change', prior_state={'items': [...full snapshot...]})`.
   - Return `{"transaction_id", "diff", "section_names", "change_summary"}`.
4. **`revert(context, epic_id, event_id?=None)`** —
   - Resolve target events via `events_by_transaction(latest_transaction_id(epic_id))` or `events_by_transaction(target_event.transaction_id)`.
   - **Capture pre-revert state:** `prior_state = {'body': current_body, 'title': current_title, 'goal': current_goal, 'checklist': [...full snapshot...], 'reverted_transaction_id': txn, 'reverted_event_ids': [...]}`. (FLAG-003.)
   - Apply each target event's `prior_state` in reverse: `body_edit` → `update_epic(...)`; `checklist_change` → `replace_checklist(...)`.
   - Append `reverted_to` event with the captured pre-revert `prior_state`.
   - Return `{"transaction_id", "reverted_event_count", "summary"}`.
5. **`render_epic(context, epic_id, format='markdown')`** — `'markdown'` returns the body as-is; `'html'` → `not_yet_supported`.

### Step 12: Editorial read tools (`agent_kit/tools/editorial_reads.py`)
**Scope:** Medium
1. **Register** each tool with **`operation_kind='read'`** (scope-1).
2. **`get_epic(epic_id, sections=None)`** — `parse(epic['body'])`; return `{title, goal, body_full, sections, section_names, state}`. Lenient parse handles legacy/malformed bodies.
3. **`get_section_names(epic_id)`** — `[s.name for s in parse(epic['body']).sections]`.
4. **`get_history(epic_id, kind=None, since=None)`** — `list_epic_events(...)` reversed.
5. **`get_self_understanding(epic_id)`** — `{goal, state, open_checklist_count, section_names, recent_events: last 3}`. Document inline that the spec §1068 7-section structure lights up incrementally.
6. **`get_epic_at_time(epic_id, timestamp)`** — backward replay from current state: walk events with `occurred_at > timestamp` in descending order; for each, undo using `prior_state` (`body_edit` → restore body; `checklist_change` → restore items; `reverted_to` → restore from captured pre-revert snapshot, FLAG-003 fix; `created` → return empty if rolling past it). Tied timestamps order by `(occurred_at, id) ASC`. Return `{body, checklist, reconstructed_at}`.
7. **`get_recent_turns(n=10, epic_id=None)`** — `store.list_recent_turns(...)`; for each turn attach `change_summary` aggregated from `epic_events.summary` rows with that `turn_id`.
8. **`search_tool_calls(tool_name=None, epic_id=None, since=None, limit=20)`** — delegates to `store.search_tool_calls_by(...)`.

### Step 13: Register tools in the loop import path (`agent_kit/loop.py:16`)
**Scope:** Small
1. **Add** `import agent_kit.tools.editorial  # noqa: F401` and `import agent_kit.tools.editorial_reads  # noqa: F401`.

---

## Phase 5: Loop bootstrap (threaded across all boundaries) + outline log

This phase explicitly enumerates every boundary that previously required a concrete `epic_id` and updates each one. The fix is one cohesive thread: `Optional[str]` from CLI → `run_turn` → `Store.create_turn` → `Envelope.epic_id` → JSON schema.

### Step 14: No-epic mode in the loop (`agent_kit/loop.py`)
**Scope:** Medium
1. **Signature:** change `run_turn(epic_id: str, ...)` → `run_turn(epic_id: str | None = None, ...)`.
2. **Lock acquisition (`agent_kit/loop.py:43–65`):** wrap `acquire_epic_lock` and the lock-contended early return in `if epic_id is not None:`. When `epic_id is None`, skip both — there's no row to lock.
3. **Active-epic local handoff:** introduce `active_epic_id: str | None = epic_id` as a local that travels with the turn. Every `_envelope(...)` and `_abort_turn(...)` call site (lines 50, 54, 80, 93, 175, 201, 268, 275, 301, 333, 344, 376) reads `active_epic_id` instead of the parameter `epic_id`. After every `registry.invoke` call, refresh: `active_epic_id = context.metadata.get('epic_id', active_epic_id)`. This guarantees that a turn that succeeds via `create_epic` returns an envelope with the new id, while a turn that errors before/without creating an epic returns an envelope with `epic_id=None`. (correctness, FLAG-001, issue_hints-1.)
4. **Inbound message creation (`agent_kit/loop.py:79–85`):** when `epic_id is None`, the message is created with `epic_id=None`. Capture `context.metadata['inbound_message_id'] = inbound['id']` so `create_epic` can retro-stamp it (Step 11.2).
5. **Turn creation (`agent_kit/loop.py:92–102`):** call `store.create_turn(epic_id=active_epic_id, …)`. The Protocol/adapters now type this as `str | None` (Step 7.2).
6. **Hot context (`agent_kit/loop.py:89`):** when `epic_id is None`, skip `load_hot_context` and synthesize `hot_context = {"epic": None, "recent_messages": [], "recent_tool_calls": []}`.
7. **Lock release:** existing release path runs only when `acquire_epic_lock` succeeded; the early-return-on-no-lock branch (Step 14.2) means we never attempt a release for the no-epic path.

### Step 15: Envelope + JSON schema accept `epic_id=None` (`agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Small
1. **Dataclass:** change `Envelope.epic_id: str` → `Envelope.epic_id: str | None = None` at `agent_kit/envelope.py:51`. The existing `_drop_none` in `to_dict()` (`agent_kit/envelope.py:112`) already strips `None` values from the JSON output, so a no-epic envelope serialises without an `epic_id` key. (FLAG-001, FLAG-005, issue_hints-1, all_locations.)
2. **JSON schema (`agent_kit/envelope.schema.json:7,29`):** remove `"epic_id"` from the top-level `required` array and change the `epic_id` property to `{"type": ["string", "null"], "minLength": 0}` so both omitted and present-but-null forms validate. Existing tests that assert `epic_id` is non-empty for normal turns still pass (those turns set the field).
3. **No new fields** needed; the envelope schema is already permissive about omitted optional keys via `_drop_none`.

### Step 16: CLI accepts `--epic` as optional (`arnold/cli.py`)
**Scope:** Small
1. **Argparse (`arnold/cli.py:45`):** change `turn.add_argument("--epic", required=True)` → `turn.add_argument("--epic", default=None)`.
2. **Run path (`arnold/cli.py:90`):** pass `epic_id=args.epic` (will be `None` if `--epic` is omitted).
3. **Exception envelope (`arnold/cli.py:99–112`):** change `epic_id=args.epic` to `epic_id=args.epic` (now `Optional[str]`); since `Envelope.epic_id` accepts `None` after Step 15.1, the error envelope serialises correctly. (callers-1.)
4. **Help text:** mention "omit `--epic` to start a new epic via natural language; the bot must call `create_epic` first."

### Step 17: Turn-end `epic_outline` log (`agent_kit/loop.py`)
**Scope:** Small
1. **At the end of `run_turn`**, after `update_turn(status='completed', …)` and before envelope return: if `active_epic_id is not None` AND any tool_call this turn had `tool_name in {'create_epic','edit_epic','revert'}`, then `parsed = body.parse(store.load_epic(active_epic_id)['body'])`, `details = body.outline(parsed)`, `log(store, 'info', 'application', 'epic_outline', f"Epic outline: {parsed.title or '(untitled)'}", details=details, turn_id=turn['id'], epic_id=active_epic_id)`.
2. **Skip** the log on `status='failed'` and on turns where `active_epic_id` is still `None` at the end (the bot replied without creating an epic).

---

## Phase 6: Integration test + regression verification

### Step 18: 10-turn fixture (`tests/test_editorial_loop.py`)
**Scope:** Medium
1. **Use** `FakeModel(script=…)` and `SQLiteStore`:
   - Turn 1: `run_turn(epic_id=None, input='Make me an auth flow design epic')` → tool_use `create_epic(title='Auth flow design', goal='Decide on auth provider and token storage')` → final text. Assert envelope `epic_id == new_id` (verifies `active_epic_id` handoff).
   - Turns 2–9: `run_turn(epic_id=<the new id>)` with `edit_epic` calls hitting **all six default sections** via `sections` ops, plus a `_preamble` replace that updates the title, plus an `append`, plus a `checklist.update` marking 3 items done. Include one `expected_diff` match and one mismatch.
   - Turn 10: `revert` (most recent transaction) → `send_message`.
2. **Assertions** — one per spec §131–142 acceptance criterion plus the critique-driven additions:
   - **Bootstrap envelope:** Turn 1 envelope has `epic_id == new_id` (proves `active_epic_id` was updated before the envelope was built); the inbound message and bot_turn rows have `epic_id` retro-stamped.
   - **Bootstrap CLI surface:** Run `python -m arnold turn --input 'create me an epic about Q1 OKRs'` (no `--epic`) via `subprocess`; assert exit code 0 and stdout JSON has `epic_id == <some non-empty string>`. Skip if `ARNOLD_FAKE_MODEL_SCRIPT` isn't supported in the env (use the existing `FakeModel` env var path from `arnold/cli.py:188`).
   - **Bootstrap envelope error path:** force a model error in a no-epic turn (FakeModel script that raises); assert the resulting envelope has `epic_id is None`, `outcome == 'errored'`, and the JSON schema validates. (correctness, callers-1.)
   - After Turn 1: `epics` row exists with parsed title/goal; 18 `checklist_items` with `source='default_seed'`; one `created` event.
   - All six default sections present after the loop; section-only edits leave other sections byte-identical (verified via `body_edit.prior_state`).
   - Whole-body `new_content` turn: `body_edit` event captured prior body; manual `revert(epic_id, event_id=that_event)` then `load_epic` returns prior body byte-equal.
   - "revert that" turn: most-recent transaction undone; new `reverted_to` event with `prior_state` containing body + title + goal + checklist (FLAG-003 verification).
   - `expected_diff` mismatch turn: tool result `error='expected_diff_mismatch'`; DB unchanged.
   - `expected_diff` match turn: writes commit normally.
   - Title-via-preamble turn: `epics.title` differs before/after; same transaction's `body_edit.prior_state` captured the old title.
   - `get_epic_at_time(epic_id, T_after_turn_5)` matches a hand-rolled replay.
   - `get_epic_at_time(epic_id, T_just_before_revert)` matches the pre-revert state (verifies FLAG-003 end-to-end).
   - `get_recent_turns(5)` returns 5 turns most-recent-first.
   - `search_tool_calls(tool_name='edit_epic', epic_id=…)` returns ≥3 rows.
   - `tool_calls.operation_kind` is `'read'` for read tools and `'write'` for write tools (scope-1).
   - `edit_epic(changes={'meta': {'title': 'X'}})` returns `error='meta_not_supported'` (scope-2).
   - One `system_logs` row per touching turn with `event_type='epic_outline'`, `category='application'`, `details.sections` containing all six default headings.

### Step 19: JSON schema regression test (`tests/test_envelope.py` or new)
**Scope:** Small
1. **Add** a test that constructs `Envelope(epic_id=None, ...)`, serialises via `to_json()`, and validates the result against `envelope.schema.json` using `jsonschema` (already in `[project.optional-dependencies].test`). Assert validation passes both with `epic_id` omitted (via `_drop_none`) and with `epic_id=null` if a future caller emits it explicitly.

### Step 20: Run the targeted tests, then full regression
**Scope:** Small
1. `pytest tests/test_body_parser.py -x`.
2. `pytest tests/test_envelope.py tests/test_sqlite_store.py tests/test_sqlite_store_v1b.py -x`.
3. `pytest tests/test_editorial_loop.py -x`.
4. `pytest -x` for the full suite (no Sprint 1a/1b regression — `test_resident*`, `test_discord_*`, `test_run_turn` variants, `test_cli`).
5. **Optional:** `SUPABASE_TEST_DB_URL=… pytest tests/test_supabase_store.py`.

---

## Execution Order

1. Schema first (Phase 1) — migrations unblock everything.
2. Body parser + templates with their unit tests (Phase 2). Pure code, fastest feedback. Land lenient `parse` + strict `validate_for_write` split before anything depends on it.
3. Store extensions (Phase 3) — column-safety constants + new methods + `create_turn(epic_id: str | None)` signature, exercised through the contract test.
4. Tools (Phase 4) — depends on parser + store. Write tools first, then reads (`operation_kind='read'`).
5. Loop bootstrap threaded through all boundaries (Phase 5: Steps 14 → 15 → 16 → 17 in order). Internal `active_epic_id` first; then envelope dataclass + JSON schema; then CLI; then outline log.
6. Integration fixture (Phase 6) — proves the whole pipeline + every critique fix end-to-end, including the bootstrap-API-consistency thread.

## Validation Order

1. `pytest tests/test_body_parser.py` — fastest feedback on parser edge cases.
2. `pytest tests/test_envelope.py` — confirms the envelope dataclass + JSON schema accept `epic_id=None`.
3. Contract tests (SQLite always, Supabase when DB available) — confirms `create_turn(epic_id=None)` and the new methods are consistent across adapters.
4. `pytest tests/test_editorial_loop.py` — the 10-turn integration with bootstrap envelope assertions, time-travel-across-revert, `_preamble`-title, `meta_not_supported`, and `operation_kind` checks.
5. `pytest -x` — full regression, including resident-mode and existing CLI tests.
