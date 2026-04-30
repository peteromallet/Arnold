# Implementation Plan: Sprint 2a — Editorial Core

## Overview

Sprint 2a is the first sprint that gives Arnold a *document* to edit. Today (post Sprint 1b) the codebase has:
- An `epics` table (already created in `supabase/migrations/202604300001_001_core.sql`) with `id, title, goal, body, state, *_at` columns. Title and goal are stored as plain columns. **No body parser yet** — the `tests/store_contract.py` fixture inserts an epic with `body='# Title'` directly.
- A loop (`agent_kit/loop.py`) that drives a model, registers tools (`agent_kit/tool_kit.py`), records every tool call and external request, and emits events through `on_event`. The only registered tools today are `send_message`, `set_activity`, `defer_to_caller`, and image-related tools.
- A `Store` protocol (`agent_kit/ports.py`) backed by SQLite (`agent_kit/store/sqlite.py`) for invocation mode and Postgres (`agent_kit/store/supabase.py`) for resident mode. The Store has *no* methods for epics, checklist items, or epic events yet — those appear in `load_hot_context` only by raw SQL inside Supabase.
- A `system_logs` table and a `log()` helper (`agent_kit/logging.py`) already wired into the loop.

Sprint 2a's job: introduce the body-as-structured-document abstraction, a 12-item-ish tool surface for editing it, the `epic_events` audit table that powers transactional revert and time-travel reads, and a default checklist seed. Everything is **invocation-mode only** (resident mode keeps working but doesn't need new behaviour). All tests run against SQLite by default; the Supabase variant runs only when `SUPABASE_TEST_DB_URL` is set.

Constraints worth naming up front:
- The body parser is the single source of truth for `epics.title` and `epics.goal`. There is no other path that updates those columns. (Spec §1311–1320.)
- Mutually-exclusive body operations: a single `edit_epic.body` payload picks **one** of `new_content`, `sections`, `append`, `remove_sections`, `rename_section`, or `reorder` — server rejects mixed payloads.
- Section names are case-sensitive. Pre-section content is `_preamble`. Code fences with `##` inside are *not* section delimiters.
- `expected_diff` comparison is "byte-exact after normalising line endings to `\n` and stripping trailing whitespace per line" (spec §494).
- Sprint 2a does NOT touch sprints/sprint_items, codebases, code_artifacts, feedback, second_opinions, or images — those land in later sprints. The `edit_epic.changes.sprints` and `state.target` paths are deliberately deferred to Sprint 4 and should return a `not_yet_supported` error if the bot tries them.
- CLAUDE.md forbids creating a `megaplan/` directory; an existing one is harness state, not a target for edits.

The plan is six phases. Phases 1–3 land the schema, parser, and store surface (no tools yet). Phase 4 lands the tool registrations against that surface. Phase 5 wires the turn-end outline log. Phase 6 covers the integration fixture and acceptance criteria.

---

## Phase 1: Schema — checklist_items, epic_events

### Step 1: Add Postgres migration (`supabase/migrations/202604300004_004_editorial_core.sql`)
**Scope:** Small
1. **Create** `checklist_items` matching spec §1322 exactly: `id TEXT PK`, `epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE`, `content TEXT NOT NULL`, `status TEXT CHECK IN ('open','done','skipped','superseded')`, `position INTEGER NOT NULL`, `source TEXT CHECK IN ('bot_inferred','user_requested','carried_over','default_seed','second_opinion')`, `skip_reason TEXT`, `superseded_by_item_id TEXT REFERENCES checklist_items(id)`, `created_at TIMESTAMPTZ DEFAULT now()`, `completed_at TIMESTAMPTZ`. Index `(epic_id, status, position)`.
2. **Create** `epic_events` matching spec §1381 exactly: `id TEXT PK`, `epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE`, `transaction_id TEXT NOT NULL`, `event_type TEXT CHECK IN ('body_edit','checklist_change','sprints_change','state_change','forced_handoff','created','code_referenced','codebase_added','image_generated','second_opinion_requested','reverted_to','sprint_status_change')`, `summary TEXT NOT NULL`, `prior_state JSONB`, `turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL`, `occurred_at TIMESTAMPTZ DEFAULT now()`. Indexes `(epic_id, occurred_at DESC)` and `(transaction_id)`.

### Step 2: Add SQLite mirror (`agent_kit/store/migrations/sqlite/004_editorial_core.sql`)
**Scope:** Small
1. **Mirror** the Postgres migration in SQLite syntax (TEXT for everything, no JSONB — `prior_state` becomes TEXT holding a JSON string, consistent with how `prompt_snapshot` etc. are handled in `001_core.sql`).
2. **Register** new JSON-encoded columns in `_JSON_COLUMNS` for both `agent_kit/store/sqlite.py:17` and `agent_kit/store/supabase.py:12` so update helpers serialise `prior_state` correctly.

### Step 3: Update test truncate list (`tests/test_supabase_store.py:33`)
**Scope:** Small
1. **Add** `checklist_items` and `epic_events` to the `TRUNCATE TABLE … RESTART IDENTITY CASCADE` block so the contract test stays green between Supabase runs.

---

## Phase 2: Body parser/serializer

### Step 4: Create the parser module (`agent_kit/body.py`)
**Scope:** Medium
1. **Implement** a pure module with no Store coupling. Public surface (everything else `_private`):
   - `parse(body: str) -> ParsedBody` where `ParsedBody` is a dataclass with `title: str | None`, `goal_first_paragraph: str | None`, `sections: list[Section]` (in order), `preamble: str` (text between title line and the first `##`, addressable as section name `_preamble` for read/write ops).
   - `Section`: `name: str`, `content: str` (the lines after the `## Heading`, NOT including the heading line; trailing newline normalised), `subheadings: list[str]` (raw `### …` lines for outline), `line_count: int`.
   - `serialize(parsed: ParsedBody) -> str` — round-trip identity for any input that passed `parse()` cleanly.
   - `outline(parsed: ParsedBody) -> dict` — returns `{title, sections: [{name, line_count, subheadings}], total_lines}` for outline log + `get_body_outline`.
2. **Enforce** the heading rules from spec §503–514:
   - First non-blank line *must* be `# <title>` (single `#`); otherwise raise `BodyParseError("body_missing_required_section: title")`.
   - Section delimiters are lines that match `^##\s+(.+?)\s*$` (level-2 only). Level-3+ headings stay inside their parent section.
   - **Code-fence guard:** track ``` and ~~~ fences during the line scan; `##` inside a fenced block is treated as content, not a delimiter. Indented (4-space) code blocks are rare in this corpus — *don't* implement that edge case for v1; document the gap in a comment on the fence-tracking helper.
   - Section names case-sensitive; whitespace stripped from the heading text.
3. **Implement** section operations as functions on `ParsedBody` (in-place returns of new `ParsedBody`): `replace_section(name, content)`, `append_to_section(name, content)`, `add_section(name, content, position='after:Foo'|'before:Foo'|'start'|'end')`, `remove_section(name)`, `rename_section(from_, to)`, `reorder(new_order: list[str])`. Each raises a typed error (`SectionNotFound`, `SectionExists`, `InvalidPosition`) the tool layer maps to JSON error payloads.
4. **Implement** `validate_required(parsed: ParsedBody)` that the tool layer calls *after* applying changes and *before* writing: must contain `# title` (non-empty), and a `## Goal` section whose first non-blank paragraph is non-empty. Raise `BodyValidationError("body_missing_required_section: title"|"goal")`.
5. **Implement** `compute_diff(old: str, new: str) -> str` — wraps `difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile='before', tofile='after', n=3)` and joins. **Implement** `diffs_equivalent(a: str, b: str) -> bool` that normalises both sides per spec §494 (line-endings → `\n`, strip trailing whitespace per line, drop trailing blank lines) before equality comparison.

### Step 5: Create the default-template + checklist-seed module (`agent_kit/templates.py`)
**Scope:** Small
1. **Constant** `DEFAULT_BODY_TEMPLATE(title: str, goal: str) -> str` — emits exactly:
   ```
   # {title}

   ## Goal

   {goal}

   ## Principles

   ## Context

   ## Key Decisions

   ## Open Questions

   ## Deliverable
   ```
   (Six default sections per spec §466 + §524.)
2. **Constant** `DEFAULT_CHECKLIST_SEED: list[str]` — the 18 items from spec §634, all with `source='default_seed'`, status `'open'`, positions 1–18.
3. **Adaptation logic stays out of Sprint 2a's tool layer.** The seed is unconditional; the bot adapts during conversation by calling `edit_epic({checklist: {update|remove|add: …}})`. (Acceptance criterion: "default checklist seeded with 18 items".)

### Step 6: Unit tests (`tests/test_body_parser.py`)
**Scope:** Medium
1. **Round-trip identity:** for ~6 hand-written fixture bodies (preamble-only, single section, six-section design-doc, body with `### Authentication` sub-headings under `## Key Decisions`, body with a fenced code block containing `## Step 1`, body with `_preamble` content before first `##`), assert `serialize(parse(body)) == body`.
2. **Section ops:** for each of `replace`, `append`, `add` (each position variant), `remove`, `rename`, `reorder` — assert the only changed section is the one targeted (byte-equal compare on every other section's serialised form).
3. **Required-element enforcement:** missing `#` line → `BodyValidationError(...title)`; empty `## Goal` first paragraph → `…goal`; `## Goal` present with content but only after another section → still passes (only first paragraph matters).
4. **Code-fence guard:** body with ``` ` ` `` ``\n## Inside\n` ` `` `` `` is parsed as a single preamble (no section split).
5. **Diff equivalence:** `diffs_equivalent` should return True when the only difference is `\r\n` vs `\n`, trailing spaces, or trailing newline; False when content actually differs.

---

## Phase 3: Store surface for epics, checklist, events

### Step 7: Extend the `Store` protocol (`agent_kit/ports.py`)
**Scope:** Medium
1. **Add** typed methods to the Protocol (and matching implementations in Steps 8–9):
   - `create_epic(*, title, goal, body, state='shaping') -> JSONDict` — single-row INSERT into `epics`. Server takes title/goal/body that the *caller has already constructed and parser-validated*; the Store does not parse.
   - `load_epic(epic_id) -> JSONDict | None`
   - `update_epic_body(epic_id, *, body, title, goal, last_edited_at) -> JSONDict` — single UPDATE; the tool layer calls this only after parse + validate succeed.
   - `seed_checklist(epic_id, items: list[dict]) -> list[JSONDict]` — bulk INSERT of `{content, status, position, source}` rows.
   - `list_checklist_items(epic_id, *, status: str | list[str] | None = None) -> list[JSONDict]`
   - `update_checklist_item(item_id, **changes) -> JSONDict`
   - `add_checklist_items(epic_id, items, start_position) -> list[JSONDict]`
   - `delete_checklist_items(item_ids) -> int`
   - `record_epic_event(*, epic_id, transaction_id, event_type, summary, prior_state, turn_id) -> JSONDict`
   - `list_epic_events(epic_id, *, since=None, kinds=None, limit=None) -> list[JSONDict]` (ordered `occurred_at, id` ascending — replay needs ascending; `get_history` reverses for display).
   - `latest_transaction_id(epic_id) -> str | None`
   - `events_by_transaction(transaction_id) -> list[JSONDict]`
2. **Why both `update_epic_body` AND `record_epic_event` in the same transaction** — see Step 11. The protocol just exposes the primitives; the tool layer composes them inside `store.transaction()`.

### Step 8: Implement on `SupabaseStore` (`agent_kit/store/supabase.py`)
**Scope:** Medium
1. **Mirror** the protocol additions with concrete SQL, using the same `_normalize`/`_json` helpers already in the module. `_new_id` prefixes: `'epic'`, `'check'`, `'evt'`.
2. **Use `store.transaction()`** internally for `seed_checklist` (no — single bulk insert is fine; the tool composes the larger transaction).

### Step 9: Implement on `SQLiteStore` (`agent_kit/store/sqlite.py`)
**Scope:** Medium
1. **Mirror** the same methods. Note the existing module already JSON-encodes `_JSON_COLUMNS`; add `'prior_state'` there. `epic_events.transaction_id` stays a TEXT (uuid hex string).

### Step 10: Extend `tests/store_contract.py`
**Scope:** Small
1. **Add** a tail block to `run_store_contract` that exercises the new surface against the existing `epic_1`: seed an event, append a checklist item, list events, and assert IDs/orderings. Both Supabase and SQLite contract tests pick this up automatically.

---

## Phase 4: Tools — `create_epic`, `edit_epic`, `revert`, `render_epic`, reads

### Step 11: Wire the editorial tool module (`agent_kit/tools/editorial.py`)
**Scope:** Large
1. **Register** each tool via `@register_tool` with explicit JSON schemas mirroring spec §1701 onward.
2. **`create_epic(context, title, goal)`** —
   - Construct body via `templates.DEFAULT_BODY_TEMPLATE(title, goal)`.
   - `parse` + `validate_required`; on failure return `{"error": "body_missing_required_section", "field": …}` (don't raise — the model needs to read the message).
   - Inside `store.transaction()`: `create_epic`, `seed_checklist(epic_id, DEFAULT_CHECKLIST_SEED)`, `record_epic_event(event_type='created', transaction_id=uuid4().hex, summary=f'Epic created with default design-doc template', prior_state=None, turn_id=context.turn_id)`.
   - Return `{"epic_id", "title", "goal", "section_names": […], "checklist_count": 18, "transaction_id"}`.
   - Update `context.metadata['epic_id']` so subsequent tools use the new epic without round-tripping through the model.
3. **`edit_epic(context, epic_id, changes, change_summary, expected_diff?)`** —
   - Reject unsupported keys: `changes.sprints` and `changes.state` return `{"error": "not_yet_supported", "field": "sprints"|"state"}` (Sprint 4 territory).
   - Reject mixed body operations: at most one of `new_content`, `sections` (with optional `position` for new sections), `append`, `remove_sections`, `rename_section`, `reorder` per call. (`sections` may have multiple section names; that's still one op.)
   - **Body path:** load current body, parse, apply the requested op(s), validate, serialise → `new_body`. Compute diff via `body.compute_diff(old, new)`. If `expected_diff` is provided and `not diffs_equivalent(expected_diff, actual_diff)`, return `{"error": "expected_diff_mismatch", "actual_diff": actual_diff}` and **do not write**.
   - **Checklist path:** apply `add` (with `start_position = len(existing_open_items) + 1` if no positions given, or honouring positions and shifting where needed), `update`, `remove`. Capture prior full checklist as `prior_state` for the event.
   - **Inside one `store.transaction()`:** `update_epic_body` (if body changed), `add/update/delete_checklist_items` (if checklist changed), and one `record_epic_event` per affected family — `body_edit` with `prior_state={'body': old_body}`, `checklist_change` with `prior_state={'items': [...]}` — all sharing the same `transaction_id = uuid4().hex`.
   - Return `{"transaction_id", "diff": actual_diff_or_empty, "section_names": [...], "change_summary": change_summary}`.
4. **`revert(context, epic_id, event_id?)`** —
   - No `event_id`: look up the most recent transaction via `latest_transaction_id`, fetch all its events.
   - With `event_id`: fetch that event and *all* events with the same transaction_id (to undo the whole edit_epic call, per spec §1399).
   - Apply each event's `prior_state` in reverse: `body_edit` → `update_epic_body(prior body)` (re-parse to refresh title/goal); `checklist_change` → wipe current items + re-insert from snapshot.
   - Append a single `reverted_to` event with new transaction_id and `prior_state={'reverted_transaction_id': original_txn_id, 'reverted_event_ids': [...]}` so revert is itself revertible.
   - Return `{"transaction_id", "reverted_event_count", "summary"}`.
5. **`render_epic(context, epic_id, format='markdown')`** — Sprint 2a only ships `'markdown'`; `'html'` returns `not_yet_supported`. For markdown: load body and return as-is (image reference resolution lands in Sprint 6; no-op here, but the parameter exists for forward compat).

### Step 12: Read tools (`agent_kit/tools/editorial_reads.py`)
**Scope:** Medium
1. **`get_epic(epic_id, sections?)`** — load body, parse, return `{title, goal, body_full (when sections is None), sections: {name: content, …} (when supplied), section_names: [...], state}`.
2. **`get_section_names(epic_id)`** — cheap; parse + return `[name, …]`.
3. **`get_history(epic_id, kind?, since?)`** — `list_epic_events` reversed (most recent first), filtered.
4. **`get_self_understanding(epic_id)`** — structured summary of epic (goal, state, open checklist items count, section names, last 3 events). The full 7-section snapshot per spec §1068 lands gradually; v1 returns the 5 fields above (document the gap inline).
5. **`get_epic_at_time(epic_id, timestamp)`** — list events with `occurred_at <= timestamp` ascending; reconstruct: start with `epics` row's *earliest* state (find the `created` event's `prior_state` is null, so use the row's body and reverse-apply forward — see Note below), then for each event apply the *opposite* of `prior_state`, no — actually: replay forward from creation. **Implementation choice:** snapshot-style. We don't store post-state per event, only prior_state, so we replay backwards from the *current* state: take current body/checklist, then for each event with `occurred_at > timestamp`, overlay its `prior_state` to undo it. The earliest event whose `occurred_at > timestamp` wins for each field. Return `{body, checklist, reconstructed_at: timestamp}`.
6. **`get_recent_turns(n=10, epic_id?)`** — query `bot_turns` ordered by `started_at DESC LIMIT n`. Add a `list_recent_turns` Store method or run raw SQL via a new Store helper. Returns each turn's id, started_at, status, triggered message snippets, and a `change_summary` aggregated from `epic_events.summary` for that turn_id.
7. **`search_tool_calls(tool_name?, epic_id?, since?, limit=20)`** — query `tool_calls` joined to `bot_turns` for `epic_id` filter. Add Store method `search_tool_calls`.

### Step 13: Register the new tools in the loop import path (`agent_kit/loop.py:16`)
**Scope:** Small
1. **Add** `import agent_kit.tools.editorial  # noqa: F401` and `import agent_kit.tools.editorial_reads  # noqa: F401` next to the existing `communication`/`images` imports so tools auto-register.

---

## Phase 5: Turn-end epic outline log

### Step 14: Emit `epic_outline` after every turn that touched an epic (`agent_kit/loop.py`)
**Scope:** Small
1. **At the end of `run_turn`**, after the final `update_turn(status='completed')` and before returning the envelope: if `context.metadata.get('epic_id')` is set AND any tool_call this turn had `tool_name in {'create_epic','edit_epic','revert'}` (cheap: walk `events` list which already contains tool_call entries), parse the current body and call `log(store, 'info', 'application', 'epic_outline', f"Epic outline: {title}", details=outline.dict, turn_id=turn['id'], epic_id=epic_id)`.
2. **Why "any tool that touched the epic"** — per spec §142 acceptance criterion, the row exists "after any turn that touched an epic." Pure-read turns don't need an outline log. Failure paths (`status='failed'`) skip the log; that's the honest signal.

---

## Phase 6: Integration test + acceptance verification

### Step 15: Create the 10-turn fixture conversation (`tests/test_editorial_loop.py`)
**Scope:** Medium
1. **Use** `FakeModel(script=…)` (already exists per `tests/test_run_turn.py:8`) with a 10-turn deterministic script that, in order:
   - Turn 1: tool_use `create_epic(title='Auth flow design', goal='Decide on auth provider and token storage')`.
   - Turns 2–9: a mix of `edit_epic` calls hitting **all six default sections** (`Goal`, `Principles`, `Context`, `Key Decisions`, `Open Questions`, `Deliverable`) at least once via `sections` ops, plus a couple of `append` calls and a `checklist.update` to mark items done. Include one `expected_diff` round trip and one expected_diff *mismatch* turn.
   - Turn 10: `revert` (most recent transaction), then `send_message`.
2. **Assertions** — one assertion per acceptance criterion in spec §131–142:
   - After turn 1: `epics` row exists with parsed title/goal; `checklist_items` count == 18; one `created` event.
   - After loop completes: every default section present; one section-only edit verified by re-parsing pre-state from `epic_events.prior_state` and confirming all *other* sections byte-identical.
   - Whole-body edit path (one of turns 2–9 uses `new_content`): a `body_edit` event captured the prior body; manual call to `revert(epic_id, event_id=that_event)` followed by `load_epic(...)` returns the prior body byte-equal.
   - "revert that" turn: most recent transaction undone; new `reverted_to` event present.
   - `expected_diff` mismatch turn: tool result contains `error='expected_diff_mismatch'` and DB state unchanged.
   - `expected_diff` match turn: writes commit normally.
   - Direct call to `get_epic_at_time(epic_id, timestamp_after_turn_5)` returns body + checklist matching what turn 5's post-state would have looked like (compute by replaying ourselves from events).
   - Direct call to `get_recent_turns(5)` returns 5 turns, most recent first.
   - Direct call to `search_tool_calls(tool_name='edit_epic', epic_id=…)` returns ≥3 rows.
   - At least one `system_logs` row per touching turn with `event_type='epic_outline'`, with `details.sections` containing all six default headings.

### Step 16: Run the targeted tests, then the full suite
**Scope:** Small
1. **Run** `pytest tests/test_body_parser.py tests/test_editorial_loop.py -x` first.
2. **Run** the full suite `pytest -x` to confirm no regression in Sprint 1a/1b tests (the contract tests in particular).
3. **Optionally** run `SUPABASE_TEST_DB_URL=… pytest tests/test_supabase_store.py` if a local Supabase is available (skipped otherwise — that's the existing behaviour).

---

## Execution Order

1. Schema first (Phase 1). Migrations are cheapest to land and unblock everything else.
2. Body parser + templates with their unit tests (Phase 2). Pure code, fast tests, no Store coupling — best ROI on early bugs.
3. Store extensions (Phase 3) — needed before any tool can write.
4. Tools (Phase 4) — once the parser and store are solid, this is mostly schema-validation + glue.
5. Outline log (Phase 5) — depends on tools existing.
6. Integration fixture (Phase 6) — proves the whole pipeline end-to-end.

## Validation Order

1. `pytest tests/test_body_parser.py` — fastest feedback on parser edge cases.
2. `pytest tests/store_contract.py`-driven tests (`tests/test_sqlite_store.py`, `tests/test_supabase_store.py` when DB available) — confirms the new Store surface is consistent across adapters.
3. `pytest tests/test_editorial_loop.py` — the 10-turn integration.
4. `pytest -x` — full regression.
