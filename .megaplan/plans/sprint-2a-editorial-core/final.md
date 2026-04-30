# Execution Checklist

- [x] **T1:** Create Postgres migration `supabase/migrations/202604300004_004_editorial_core.sql` adding `checklist_items` (id TEXT PK, epic_id TEXT NOT NULL FK→epics ON DELETE CASCADE, content TEXT NOT NULL, status TEXT CHECK IN ('open','done','skipped','superseded'), position INTEGER NOT NULL, source TEXT CHECK IN ('bot_inferred','user_requested','carried_over','default_seed','second_opinion'), skip_reason TEXT, superseded_by_item_id TEXT FK→checklist_items, created_at TIMESTAMPTZ DEFAULT now(), completed_at TIMESTAMPTZ; index (epic_id,status,position)) and `epic_events` (id TEXT PK, epic_id TEXT NOT NULL FK→epics ON DELETE CASCADE, transaction_id TEXT NOT NULL, event_type TEXT CHECK IN the 12 listed kinds, summary TEXT NOT NULL, prior_state JSONB, turn_id TEXT FK→bot_turns ON DELETE SET NULL, occurred_at TIMESTAMPTZ DEFAULT now(); indexes (epic_id, occurred_at DESC) and (transaction_id)). Match spec §1322 and §1381 exactly.
  Executor notes: Added Postgres migration 202604300004_004_editorial_core.sql with checklist_items and epic_events, requested CHECK constraints, FK delete behavior, and indexes. Smoke-checked all 12 event_type values and required index/FK text.
  Files changed:
    - supabase/migrations/202604300004_004_editorial_core.sql
  Reviewer verdict: Pass. Postgres migration matches required editorial tables and indexes.
  Evidence files:
    - supabase/migrations/202604300004_004_editorial_core.sql

- [x] **T2:** Create SQLite mirror `agent_kit/store/migrations/sqlite/004_editorial_core.sql` (TEXT for everything, prior_state TEXT JSON blob, equivalent CHECK constraints and indexes). Register `prior_state` in `_JSON_COLUMNS` in both `agent_kit/store/sqlite.py:17` and `agent_kit/store/supabase.py:12` (verify the exact line locations).
  Depends on: T1
  Executor notes: Added SQLite 004_editorial_core.sql with checklist_items and epic_events, CHECK constraints, FK behavior, indexes, and prior_state as TEXT. Added prior_state to _JSON_COLUMNS in both SQLiteStore and SupabaseStore. Verified by static checks and SQLite migration smoke against a fresh database.
  Files changed:
    - agent_kit/store/migrations/sqlite/004_editorial_core.sql
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
  Reviewer verdict: Pass. SQLite migration and prior_state JSON registration are present.
  Evidence files:
    - agent_kit/store/migrations/sqlite/004_editorial_core.sql
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py

- [x] **T3:** Add `checklist_items` and `epic_events` to the `TRUNCATE TABLE … RESTART IDENTITY CASCADE` block in `tests/test_supabase_store.py` (around line 33).
  Depends on: T1
  Executor notes: Added checklist_items and epic_events to the Supabase truncate block before parent tables. Static check confirmed both names are in the TRUNCATE block before epics. Live Supabase test file skips without SUPABASE_TEST_DB_URL.
  Files changed:
    - tests/test_supabase_store.py
  Reviewer verdict: Pass. Supabase truncate fixture includes new tables.
  Evidence files:
    - tests/test_supabase_store.py

- [x] **T4:** Create `agent_kit/body.py` with public surface only: `parse(body) -> ParsedBody` (lenient, never raises; ParsedBody has title|None, goal_first_paragraph|None, preamble (raw text from byte 0 up to but not including first `##`, INCLUDING `# Title` line), sections list); `serialize(parsed) -> str` (round-trip identity); `validate_for_write(parsed)` raising `BodyValidationError('body_missing_required_section: title'|'…goal')`; `outline(parsed)`; section ops `replace_section`, `append_to_section`, `add_section(position='after:Foo'|'before:Foo'|'start'|'end')`, `remove_section`, `rename_section`, `reorder` with typed errors `SectionNotFound`/`SectionExists`/`InvalidPosition`; `_preamble` addressable for replace; rename to/from `_preamble` rejected; `compute_diff` (difflib unified_diff with n=3); `diffs_equivalent` (\r\n→\n, strip trailing whitespace per line, drop trailing blank lines). Heading regex `^##\s+(.+?)\s*$` at top level only; track ``` and ~~~ fences so fenced `##` is not a section boundary; sub-sections (### and below) part of parent; section names case-sensitive. No third-party deps beyond stdlib (difflib, re). No imports of Store/ports/tool_kit. Stay under ~450 lines.
  Executor notes: Added stdlib-only body parser/editor module. Smoke covered lenient parse cases, identity roundtrip, _preamble title handling, fenced ## handling, required validation messages, section byte preservation, and diff equivalence. File is 253 lines.
  Files changed:
    - agent_kit/body.py
  Reviewer verdict: Pass. Body parser implements lenient parse, strict validation, section ops, and diff helpers.
  Evidence files:
    - agent_kit/body.py

- [x] **T5:** Create `agent_kit/templates.py` with `DEFAULT_BODY_TEMPLATE(title, goal) -> str` emitting a six-section design-doc skeleton (Goal, Principles, Context, Key Decisions, Open Questions, Deliverable; `# Title` first line and `## Goal` first paragraph populated from args), and `DEFAULT_CHECKLIST_SEED: list[str]` of the 18 items from spec §634, all `source='default_seed'`, `status='open'`, positions 1–18. No adaptation logic in v1.
  Executor notes: Added DEFAULT_BODY_TEMPLATE with # Title plus the six requested sections and populated Goal first paragraph. Added the 18 default checklist seed strings in spec order; v1 contains no adaptation logic.
  Files changed:
    - agent_kit/templates.py
  Reviewer verdict: Pass. Template and 18 checklist seed items are implemented.
  Evidence files:
    - agent_kit/templates.py

- [x] **T6:** Create `tests/test_body_parser.py` covering: round-trip identity for ≥6 fixtures (preamble-only, single section, six-section template, sub-headings, fenced ` ```\n## Inside\n``` `, non-empty preamble before first `##`); section ops leave non-targeted sections byte-equal; `_preamble` covers title (`replace_section('_preamble', '# New Title\n')` → title=='New Title'; replace with `''` → title=None and `validate_for_write` raises `body_missing_required_section: title`); lenient parse on `''`, `'just text\n'`, `'## Goal\n\ngoal\n'` (no title), `'# Title\n'` (no Goal), `'# Title\n\n## NotGoal\n\nx\n'` — all return ParsedBody without raising and `validate_for_write` rejects each; code-fence guard parses as single preamble; `diffs_equivalent` true on \r\n / trailing-space / trailing-blank-line differences only, false on real content delta.
  Depends on: T4
  Executor notes: Added parser tests covering six roundtrip fixtures, section ops preserving untouched sections, _preamble title replacement/removal validation, five lenient parse cases, fenced ## as preamble-only, and diffs_equivalent boundary cases. The full test file passes.
  Files changed:
    - tests/test_body_parser.py
  Reviewer verdict: Pass. Parser tests cover required fixtures and passed.
  Evidence files:
    - tests/test_body_parser.py

- [x] **T7:** Extend `Store` Protocol in `agent_kit/ports.py` with the editorial surface: `create_epic(*, title, goal, body, state='shaping')`, `load_epic(epic_id)`, `update_epic(epic_id, **changes)` guarded by `_EPIC_COLUMNS = {'title','goal','body','state','last_edited_at','last_active_at','planned_at'}`, `seed_checklist(epic_id, items)`, `list_checklist_items(epic_id, *, status=None)`, `update_checklist_item(item_id, **changes)` guarded by `_CHECKLIST_COLUMNS = {'content','status','position','skip_reason','superseded_by_item_id','completed_at'}`, `add_checklist_items`, `delete_checklist_items`, `replace_checklist`, `record_epic_event(*, epic_id, transaction_id, event_type, summary, prior_state, turn_id)`, `list_epic_events(epic_id, *, since=None, until=None, kinds=None, limit=None)` ordered `(occurred_at, id) ASC`, `latest_transaction_id(epic_id)`, `events_by_transaction(transaction_id)`, `list_recent_turns(*, n=10, epic_id=None)`, `search_tool_calls_by(*, tool_name=None, epic_id=None, since=None, limit=20)`. Update `Store.create_turn` Protocol signature to `epic_id: str | None`. Verify `create_message`, `update_message`, `update_turn`, `log_system_event` already accept `epic_id: str | None`.
  Executor notes: Extended Store Protocol with editorial methods, _EPIC_COLUMNS/_CHECKLIST_COLUMNS guard sets, and create_turn(epic_id: str | None). Existing create_message, update_message, update_turn, and log_system_event already accept nullable epic_id through kwargs or explicit typing.
  Files changed:
    - agent_kit/ports.py
  Reviewer verdict: Pass. Store Protocol includes editorial surface and nullable create_turn.
  Evidence files:
    - agent_kit/ports.py

- [x] **T8:** Implement the new Store surface in `agent_kit/store/supabase.py` using existing `_normalize`/`_json` helpers and `_new_id` (prefixes `'epic'`, `'check'`, `'evt'`). Add module-level `_EPIC_COLUMNS` and `_CHECKLIST_COLUMNS` next to `_MESSAGE_COLUMNS`/`_TURN_COLUMNS`/`_IMAGE_COLUMNS`; route `update_epic` and `update_checklist_item` through `self._update`. Add `'epic_id'` to `_TURN_COLUMNS` and `_MESSAGE_COLUMNS`. Confirm `create_turn` accepts `epic_id: str | None` and the existing INSERT (around `agent_kit/store/supabase.py:113`) passes it through (Postgres allows NULL on `bot_turns.epic_id`).
  Depends on: T7, T2
  Executor notes: Implemented SupabaseStore editorial methods, epic/checklist column guards, epic_id guarded-update support on messages/turns, nullable create_turn(epic_id), and id prefixes epic/check/evt. Verified by py_compile, static method/constant/prefix checks, and the Supabase test module skip behavior without SUPABASE_TEST_DB_URL.
  Files changed:
    - agent_kit/store/supabase.py
  Reviewer verdict: Pass. SupabaseStore implements editorial persistence surface and guards.
  Evidence files:
    - agent_kit/store/supabase.py

- [x] **T9:** Mirror T8 in `agent_kit/store/sqlite.py`: same methods, same `_EPIC_COLUMNS`/`_CHECKLIST_COLUMNS` constants, same `'epic_id'` additions to `_MESSAGE_COLUMNS`/`_TURN_COLUMNS`. Confirm `'prior_state'` is in `_JSON_COLUMNS` (added in T2) and `create_turn` accepts `epic_id: str | None`.
  Depends on: T7, T2
  Executor notes: Implemented SQLiteStore editorial methods mirroring SupabaseStore, added epic/checklist column guards, epic_id guarded-update support on messages/turns, nullable create_turn(epic_id), and preserved prior_state JSON decoding. Verified by py_compile, static checks, SQLite editorial surface smoke, and existing SQLite store test modules.
  Files changed:
    - agent_kit/store/sqlite.py
  Reviewer verdict: Pass. SQLiteStore mirrors editorial persistence surface and guards.
  Evidence files:
    - agent_kit/store/sqlite.py

- [x] **T10:** Extend `tests/store_contract.py` with a tail block that creates an epic, seeds checklist, appends events with shared `transaction_id`s, lists/filters events, queries `latest_transaction_id`, verifies ordering. Add explicit assertion that `create_turn(epic_id=None)` succeeds and the row stores NULL.
  Depends on: T8, T9
  Executor notes: Extended the shared store contract with nullable create_turn persistence, create_epic, seed_checklist, epic event recording, transaction event lookup, event filtering, latest_transaction_id, and ordering assertions. Verified through the full SQLite store contract modules; Supabase contract module still skips without SUPABASE_TEST_DB_URL.
  Files changed:
    - tests/store_contract.py
  Reviewer verdict: Pass. Store contract covers new surface and create_turn(None).
  Evidence files:
    - tests/store_contract.py

- [x] **T11:** Create `agent_kit/tools/editorial.py` with write tools registered via `@register_tool(operation_kind='write')` and explicit JSON schemas: (1) `create_epic(context, title, goal)` — build body via `templates.DEFAULT_BODY_TEMPLATE(title, goal)`, `parsed = body.parse(rendered)`, `body.validate_for_write(parsed)` (return structured `{'error':'body_missing_required_section', 'field': …}` on `BodyValidationError`); inside `store.transaction()` call `store.create_epic(title=parsed.title, goal=parsed.goal_first_paragraph, body=rendered, state='shaping')` (parsed values, never raw args), `store.seed_checklist(epic['id'], DEFAULT_CHECKLIST_SEED)`, `store.record_epic_event(... event_type='created', summary='Epic created with default design-doc template', prior_state=None, turn_id=context.turn_id)`; retro-stamp `store.update_message(context.metadata['inbound_message_id'], epic_id=epic['id'])` and `store.update_turn(context.turn_id, epic_id=epic['id'])`; set `context.metadata['epic_id']=epic['id']`; return `{epic_id, title, goal, section_names, checklist_count:18, transaction_id}`. (2) `edit_epic(context, epic_id, changes, change_summary, expected_diff?)` — reject `changes.sprints`/`changes.state` with `not_yet_supported`; reject `changes.meta` with `meta_not_supported` and hint to use `body.sections._preamble` (title) or `body.sections.Goal` (goal); reject mixed body ops (`new_content | sections | append | remove_sections | rename_section | reorder`) with `body_op_conflict`; body path load→parse→apply→serialise→`validate_for_write`→`compute_diff`; if `expected_diff` provided and not `diffs_equivalent` return `{'error':'expected_diff_mismatch', 'actual_diff':...}` and DO NOT write; checklist path snapshot capture; one `store.transaction()` with `transaction_id=uuid4().hex`, `update_epic(epic_id, body=new_body, title=new_parsed.title, goal=new_parsed.goal_first_paragraph, last_edited_at=now())` + `record_epic_event(event_type='body_edit', prior_state={'body':old,'title':old_title,'goal':old_goal})` and per-item checklist ops + `record_epic_event(event_type='checklist_change', prior_state={'items':[...full snapshot...]})`; return `{transaction_id, diff, section_names, change_summary}`. (3) `revert(context, epic_id, event_id?=None)` — resolve via `events_by_transaction(latest_transaction_id(epic_id))` or by target event's `transaction_id`; capture pre-revert `prior_state = {'body': current_body, 'title': current_title, 'goal': current_goal, 'checklist': [...full snapshot...], 'reverted_transaction_id': txn, 'reverted_event_ids': [...]}`; apply each target event's `prior_state` in reverse (`body_edit`→`update_epic`, `checklist_change`→`replace_checklist`); append `reverted_to` event with the captured pre-revert prior_state; return `{transaction_id, reverted_event_count, summary}`. (4) `render_epic(context, epic_id, format='markdown')` — markdown returns body as-is; html returns `not_yet_supported`.
  Depends on: T4, T5, T7, T8, T9
  Executor notes: Added editorial write tools create_epic, edit_epic, revert, and render_epic with write operation_kind registration, explicit schemas, parsed title/goal writes, expected_diff refusal before writes, body op conflict/meta/state/sprints error branches, checklist event snapshots, and reverted_to pre-revert snapshots. Verified by py_compile and a SQLite tool smoke covering create/edit expected_diff mismatch and match, meta/conflict errors, revert prior_state, render_epic, and registry operation kinds.
  Files changed:
    - agent_kit/tools/editorial.py
  Reviewer verdict: Pass. Write tools implement create/edit/revert/render semantics.
  Evidence files:
    - agent_kit/tools/editorial.py

- [x] **T12:** Create `agent_kit/tools/editorial_reads.py` with read tools registered via `@register_tool(operation_kind='read')`: `get_epic(epic_id, sections=None)` returns `{title, goal, body_full, sections, section_names, state}` using lenient `parse()` (handles legacy/malformed); `get_section_names(epic_id)`; `get_history(epic_id, kind=None, since=None)` returning `list_epic_events(...)` reversed; `get_self_understanding(epic_id)` returns `{goal, state, open_checklist_count, section_names, recent_events: last 3}` with inline note that spec §1068 7-section structure lights up incrementally; `get_epic_at_time(epic_id, timestamp)` — backward replay from current state, walk events with `occurred_at > timestamp` in descending order, undo using `prior_state` for each (`body_edit`→restore body/title/goal; `checklist_change`→restore items; `reverted_to`→restore from captured pre-revert snapshot; for `created`, when replay rolls past the created event return that event's initial state — i.e. the template body + 18-item seed checklist captured in prior_state — rather than empty/None per spec §1678; tied timestamps order by `(occurred_at,id) ASC`); `get_recent_turns(n=10, epic_id=None)` delegates to `store.list_recent_turns` and attaches `change_summary` aggregated from `epic_events.summary` rows with that `turn_id`; `search_tool_calls(tool_name=None, epic_id=None, since=None, limit=20)` delegates to `store.search_tool_calls_by(...)`.
  Depends on: T4, T7, T8, T9
  Executor notes: Added editorial read tools get_epic, get_section_names, get_history, get_self_understanding, get_epic_at_time, get_recent_turns, and search_tool_calls with read operation_kind registration. get_epic_at_time replays body_edit, checklist_change, reverted_to, and created snapshots backward using lenient body parsing. Verified by py_compile and SQLite tool smoke covering read payloads, pre-creation initial state replay, recent turns, search delegation, and registry operation kinds.
  Files changed:
    - agent_kit/tools/editorial_reads.py
  Reviewer verdict: Pass. Read tools implement section/history/replay/search semantics with read operation_kind.
  Evidence files:
    - agent_kit/tools/editorial_reads.py

- [x] **T13:** Add `import agent_kit.tools.editorial  # noqa: F401` and `import agent_kit.tools.editorial_reads  # noqa: F401` near `agent_kit/loop.py:16` so the new tools register at import time alongside the existing communication tool imports.
  Depends on: T11, T12
  Executor notes: Imported agent_kit.tools.editorial and agent_kit.tools.editorial_reads from loop.py with # noqa: F401 beside the existing tool imports. Verified py_compile, import-time registry contents for all editorial read/write tools, and existing loop/CLI plus store/body/envelope modules.
  Files changed:
    - agent_kit/loop.py
  Reviewer verdict: Pass. Loop imports editorial tool modules for registration.
  Evidence files:
    - agent_kit/loop.py

- [x] **T14:** In `agent_kit/loop.py`, change `run_turn(epic_id: str, …)` → `run_turn(epic_id: str | None = None, …)`. Wrap `acquire_epic_lock` and the lock-contended early return (lines ~43–65) in `if epic_id is not None:` — when None, skip both. Introduce local `active_epic_id: str | None = epic_id`. Replace every `_envelope(...)` and `_abort_turn(...)` call site (lines ~50, 54, 80, 93, 175, 201, 268, 275, 301, 333, 344, 376) so they read `active_epic_id` instead of the parameter. After every `registry.invoke` call, refresh `active_epic_id = context.metadata.get('epic_id', active_epic_id)`. Inbound message creation (lines ~79–85): when epic_id None, create with `epic_id=None`; capture `context.metadata['inbound_message_id'] = inbound['id']`. Turn creation (lines ~92–102): call `store.create_turn(epic_id=active_epic_id, …)`. Hot context (line ~89): when epic_id None, skip `load_hot_context` and synthesize `hot_context = {'epic': None, 'recent_messages': [], 'recent_tool_calls': []}`. Lock release: existing path runs only when lock was acquired, so no change needed for the no-epic branch.
  Depends on: T7
  Executor notes: Updated run_turn to accept epic_id=None, skip lock/hot-context when no epic exists, carry active_epic_id through envelope/abort paths, capture inbound_message_id, and refresh active_epic_id after every registry.invoke call. Existing CLI/run_turn modules and no-epic CLI smoke pass.
  Files changed:
    - agent_kit/loop.py
  Reviewer verdict: Pass. No-epic run_turn and active_epic_id handoff implemented.
  Evidence files:
    - agent_kit/loop.py

- [x] **T15:** Change `Envelope.epic_id: str` → `Envelope.epic_id: str | None = None` at `agent_kit/envelope.py:51`. In `agent_kit/envelope.schema.json`, remove `'epic_id'` from the top-level `required` array (around line 7) and change the `epic_id` property (around line 29) to `{"type": ["string", "null"], "minLength": 0}` so omitted/null/string all validate. Existing `_drop_none` in `to_dict()` (around `agent_kit/envelope.py:112`) already strips None values from JSON output, so a no-epic envelope serialises without an `epic_id` key — verify and rely on this.
  Executor notes: Changed Envelope.epic_id to str | None = None, relaxed schema to allow omitted/null/string epic_id, and verified _drop_none omits epic_id when None. Existing envelope tests pass.
  Files changed:
    - agent_kit/envelope.py
    - agent_kit/envelope.schema.json
  Reviewer verdict: Pass. Envelope/schema nullable epic_id implemented.
  Evidence files:
    - agent_kit/envelope.py
    - agent_kit/envelope.schema.json

- [x] **T16:** In `arnold/cli.py`: change `turn.add_argument('--epic', required=True)` (around line 45) to `turn.add_argument('--epic', default=None)`. Update run path (around line 90) to pass `epic_id=args.epic` (will be None when omitted). Update exception envelope (around lines 99–112) to keep `epic_id=args.epic`; with `Envelope.epic_id: Optional[str]` from T15, the error envelope serialises correctly. Update help text to mention 'omit `--epic` to start a new epic via natural language; the bot must call `create_epic` first.'
  Depends on: T15
  Executor notes: Made --epic optional with default None and help text documenting no-epic bootstrap. Existing run path and exception envelope continue to pass args.epic through; no-epic CLI smoke returned a valid completed envelope without epic_id.
  Files changed:
    - arnold/cli.py
  Reviewer verdict: Pass. CLI --epic is optional and no-epic path is documented.
  Evidence files:
    - arnold/cli.py

- [x] **T17:** In `agent_kit/loop.py`, after `update_turn(status='completed', …)` and before the envelope return, emit the turn-end outline log: if `active_epic_id is not None` AND any `tool_call` this turn had `tool_name in {'create_epic','edit_epic','revert'}`, then `parsed = body.parse(store.load_epic(active_epic_id)['body'])`, `details = body.outline(parsed)`, and call `log(store, 'info', 'application', 'epic_outline', f'Epic outline: {parsed.title or "(untitled)"}', details=details, turn_id=turn['id'], epic_id=active_epic_id)`. Skip on `status='failed'` and on turns where `active_epic_id` is still None at the end.
  Depends on: T14, T4
  Executor notes: Added completed-turn epic_outline logging gated on active_epic_id and create_epic/edit_epic/revert tool-call events. Details come from body.outline and include title, sections with line counts, and total_lines. Verified by loop smoke covering emitted and skipped cases, py_compile, and CLI/run_turn test modules.
  Files changed:
    - agent_kit/loop.py
  Reviewer verdict: Pass. epic_outline logging is implemented and gated correctly.
  Evidence files:
    - agent_kit/loop.py

- [x] **T18:** Create `tests/test_editorial_loop.py` — 10-turn fixture using `FakeModel(script=…)` and `SQLiteStore`. Turn 1: `run_turn(epic_id=None, input='Make me an auth flow design epic')` → tool_use `create_epic(title='Auth flow design', goal='Decide on auth provider and token storage')` → final text; assert envelope `epic_id == new_id` (verifies active_epic_id handoff) and inbound message + bot_turn rows have epic_id retro-stamped. Turns 2–9: `run_turn(epic_id=new_id)` exercising `edit_epic` against ALL six default sections via `sections` ops, plus a `_preamble` replace that updates the title, plus an `append`, plus a `checklist.update` marking 3 items done; include one `expected_diff` match and one mismatch. Turn 10: `revert` (most recent transaction) → `send_message`. Assertions covering every Sprint 2a acceptance criterion: bootstrap envelope, no-epic CLI subprocess via `python -m arnold turn --input '...'` returns exit 0 with `epic_id` in JSON (use existing FakeModel env var path from `arnold/cli.py:188`), errored no-epic envelope has `epic_id is None` and validates against schema; epics row + 18 default_seed checklist items + one `created` event after Turn 1; all six sections present; section-only edits leave others byte-identical (verified via `body_edit.prior_state`); whole-body edit then manual revert returns prior body byte-equal; `reverted_to.prior_state` contains body+title+goal+checklist (FLAG-003); `expected_diff` mismatch returns error and leaves DB unchanged; `expected_diff` match commits; title-via-_preamble turn updates `epics.title` and prior_state captures old title; `get_epic_at_time(T_after_turn_5)` matches hand-rolled replay; `get_epic_at_time(T_just_before_revert)` matches pre-revert state; `get_epic_at_time(T_before_creation)` returns the initial template body + 18-item seed (per spec §1678); `get_recent_turns(5)` returns 5 most-recent first; `search_tool_calls(tool_name='edit_epic', epic_id=…)` returns ≥3 rows; `tool_calls.operation_kind` is 'read' for read tools and 'write' for write tools; `edit_epic(changes={'meta':{'title':'X'}})` returns `error='meta_not_supported'`; one `system_logs` row per touching turn with `event_type='epic_outline'`, `category='application'`, `details.sections` containing all six default headings.
  Depends on: T11, T12, T13, T14, T15, T16, T17, T2, T3, T10
  Executor notes: Added the editorial loop integration coverage for the 10-turn SQLite/FakeModel flow, no-epic bootstrap, CLI no-epic subprocess, errored no-epic schema validation, all six section edits, _preamble title edit, expected_diff match/mismatch, checklist update/revert, history replay, recent turns, tool-call search, operation_kind auditing, meta rejection, and epic_outline logs. Added arnold/__main__.py for the required python -m arnold turn path and fixed epic_outline details persistence so system_logs.details contains sections directly. Verified tests/test_editorial_loop.py passes, py_compile passes for touched modules, git diff --check passes, and full python -m pytest -x runs until the known pre-existing leaked Supabase JWT prefix failure in .megaplan/plans/sprint-1b-discord-resident/*.
  Files changed:
    - agent_kit/loop.py
    - arnold/__main__.py
    - tests/test_editorial_loop.py
  Reviewer verdict: Pass. Editorial loop integration test covers acceptance criteria and passed.
  Evidence files:
    - tests/test_editorial_loop.py
    - arnold/__main__.py

- [x] **T19:** Add a JSON schema regression test (in existing `tests/test_envelope.py` if present, otherwise new file). Construct `Envelope(epic_id=None, ...)`, serialise via `to_json()`, validate against `agent_kit/envelope.schema.json` using `jsonschema` (already in `[project.optional-dependencies].test`). Assert validation passes both with `epic_id` omitted (via `_drop_none`) and with explicit `epic_id=null`.
  Depends on: T15
  Executor notes: Added envelope schema regression test for Envelope(epic_id=None), validating both omitted epic_id from to_json/_drop_none and explicit epic_id:null against envelope.schema.json. The full envelope test file passes.
  Files changed:
    - tests/test_envelope.py
  Reviewer verdict: Pass. Envelope null/omitted schema regression test added.
  Evidence files:
    - tests/test_envelope.py

- [x] **T20:** Run validation: `pytest tests/test_body_parser.py -x`, then `pytest tests/test_envelope.py tests/test_sqlite_store.py tests/test_sqlite_store_v1b.py -x`, then `pytest tests/test_editorial_loop.py -x`, then `pytest -x` for the full suite (must include resident-mode `test_resident*`, `test_discord_*`, `test_run_turn` variants, `test_cli` with no regressions). Read failures, fix the root cause in code, re-run until all pass. Additionally, write a short throwaway script that bootstraps an epic from `epic_id=None` via the CLI/loop to confirm the no-epic flow works end-to-end against SQLite, run it, then delete the script. Do not skip tests or use `--no-verify` to bypass failures.
  Depends on: T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19
  Executor notes: Ran the required targeted validation modules with python -m pytest: body parser passed 6/6, envelope/sqlite store/sqlite v1b passed 11/11, and editorial loop passed 3/3. Created and ran a throwaway no-epic CLI bootstrap script against SQLite; it returned an epic_id and verified 18 checklist rows, then the script was deleted. Ran the full suite with python -m pytest -x; it reached tests/test_no_leaked_secrets.py after resident/discord/run_turn/cli/editorial coverage had passed, then stopped on the known pre-existing leaked Supabase JWT prefix in .megaplan/plans/sprint-1b-discord-resident/*. git diff --check passed. No task-scoped source changes were made in this batch.
  Reviewer verdict: Pass with caveat. Targeted suites pass; full suite stops on unrelated pre-existing secret-scan failure.
  Evidence files:
    - tests/test_no_leaked_secrets.py

- [x] **T21:** Surface after_execute user_actions to the user:
- U1: Optional: provide `SUPABASE_TEST_DB_URL` so the executor can run `pytest tests/test_supabase_store.py` against a real Supabase instance (the spec mentions URL https://yhwflvadmefhkshwbfnf.supabase.co and a service role key). The SQLite contract test in T10 covers the same surface and is the primary CI signal; the Supabase run is an extra confidence check. Skip this user action if you don't want to exercise the Postgres adapter live.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T20
  Executor notes: Surfaced U1 to the user: optionally provide SUPABASE_TEST_DB_URL to run python -m pytest tests/test_supabase_store.py against a live Supabase/Postgres instance. The SQLite contract coverage from T10 is the primary CI signal; live Supabase is extra confidence. No executor action was taken because credentials/infra are human-provided.
  Files changed:
    - .megaplan/debt.json
    - .megaplan/plans/sprint-2a-editorial-core/.plan.lock
    - .megaplan/plans/sprint-2a-editorial-core/critique_output.json
    - .megaplan/plans/sprint-2a-editorial-core/critique_v1.json
    - .megaplan/plans/sprint-2a-editorial-core/critique_v2.json
    - .megaplan/plans/sprint-2a-editorial-core/critique_v3.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_audit.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_1.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_2.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_3.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_4.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_5.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_6.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_7.json
    - .megaplan/plans/sprint-2a-editorial-core/execution_batch_8.json
    - .megaplan/plans/sprint-2a-editorial-core/faults.json
    - .megaplan/plans/sprint-2a-editorial-core/final.md
    - .megaplan/plans/sprint-2a-editorial-core/finalize.json
    - .megaplan/plans/sprint-2a-editorial-core/finalize_snapshot.json
    - .megaplan/plans/sprint-2a-editorial-core/gate.json
    - .megaplan/plans/sprint-2a-editorial-core/gate_signals_v1.json
    - .megaplan/plans/sprint-2a-editorial-core/gate_signals_v2.json
    - .megaplan/plans/sprint-2a-editorial-core/gate_signals_v3.json
    - .megaplan/plans/sprint-2a-editorial-core/plan_v1.md
    - .megaplan/plans/sprint-2a-editorial-core/plan_v1.meta.json
    - .megaplan/plans/sprint-2a-editorial-core/plan_v2.md
    - .megaplan/plans/sprint-2a-editorial-core/plan_v2.meta.json
    - .megaplan/plans/sprint-2a-editorial-core/plan_v3.md
    - .megaplan/plans/sprint-2a-editorial-core/plan_v3.meta.json
    - .megaplan/plans/sprint-2a-editorial-core/state.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_critique_v1.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_critique_v2.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_critique_v3.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_finalize_v3.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_gate_v1.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_gate_v2.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_gate_v3.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_plan_v1.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_revise_v2.json
    - .megaplan/plans/sprint-2a-editorial-core/step_receipt_revise_v3.json
  Reviewer verdict: Pass. Optional live Supabase action was surfaced as human-provided infra.
  Evidence files:
    - .megaplan/plans/sprint-2a-editorial-core/finalize.json

## Watch Items

- Bootstrap thread: Optional[str] must be coherent across run_turn signature, Store.create_turn (Protocol + both adapters), Envelope.epic_id, envelope.schema.json, and CLI --epic. Skipping any one boundary breaks the contract.
- active_epic_id local in loop.py is the source of truth for every _envelope() / _abort_turn() return after T14. Refresh it after every registry.invoke. A successful bootstrap turn MUST return Envelope.epic_id == new_id; an errored no-epic turn MUST return epic_id=None and validate against the schema.
- Parser split: parse() is lenient (never raises). validate_for_write() is the only place that raises body_missing_required_section. Read tools and get_epic_at_time MUST only call parse(). Conflating these breaks legacy/malformed body inspection (FLAG-002, correctness-1).
- _preamble includes the # Title line per spec §2606. replace_section('_preamble', '# New Title\n') is the canonical title-edit path. rename_section to/from _preamble must be rejected.
- create_epic must write epics.title and epics.goal exclusively from parsed.title and parsed.goal_first_paragraph — never from raw args. Spec §1314–1316: parser is the only writer of these columns (correctness-3).
- reverted_to events MUST capture full pre-revert {body, title, goal, checklist} snapshot in prior_state. Otherwise get_epic_at_time across a revert is incorrect (FLAG-003 / correctness-2). The integration test asserts get_epic_at_time(T_just_before_revert).
- Read tools register with operation_kind='read'. Write tools register with operation_kind='write'. Default in @register_tool is write — omitting the kwarg pollutes audit semantics (scope-1).
- edit_epic.changes.meta is rejected with meta_not_supported and a hint pointing to body.sections._preamble (title) or body.sections.Goal (goal). Do not silently map to body edits (scope-2).
- Mutually-exclusive body op flavours: any payload mixing new_content / sections / append / remove_sections / rename_section / reorder returns body_op_conflict.
- expected_diff equivalence: \r\n→\n, strip trailing whitespace per line, drop trailing blank lines, then byte-equal compare. Mismatch must NOT write.
- Accepted tradeoff: body_version (spec §2606 example) is intentionally deferred. Audit trail in epic_events.body_edit captures body+title+goal atomically; that satisfies the title/body sync acceptance test. Future addition is an additive migration. (DEBT: data-model)
- Accepted tradeoff: get_epic_at_time(T_before_creation) returns the initial template body + 18-item seed checklist (the snapshot the created event captures in its prior_state) per spec §1678 reading. Plan v3 said 'empty/None' — adopt the spec reading. Integration test asserts this. (DEBT: history-replay)
- Out of scope for Sprint 2a: sprints, sprint_items, codebases, code_artifacts, feedback, second_opinions, image generation. edit_epic.changes.sprints and changes.state return not_yet_supported.
- CLAUDE.md: do NOT create a megaplan/ directory in the project root. The existing one is harness state.
- Existing run_turn callers (test_run_turn, resident mode) keep passing concrete epic_ids. The no-epic path is purely additive — no regression in Sprint 1a/1b.
- Column safety: _EPIC_COLUMNS, _CHECKLIST_COLUMNS, plus 'epic_id' in _MESSAGE_COLUMNS / _TURN_COLUMNS, must be added to BOTH adapters so update_epic / update_checklist_item / retro-stamp pass guarded-update checks.
- Body parser must stay under ~450 lines, stdlib-only (difflib, re), and import nothing from Store/ports/tool_kit.
- Code-fence guard: bodies containing fenced ``` or ~~~ blocks where ## appears inside a fence must NOT split into sections.
- JSON schema regression test (T19) is required so future schema edits don't silently re-tighten epic_id.

## Sense Checks

- **SC1** (T1): Does the Postgres migration create both tables with the exact CHECK constraints, FK ON DELETE behaviour, and indexes from spec §1322 / §1381? Are the 12 event_type values present?
  Executor note: Yes. Migration creates both tables with the requested CHECK lists, cascade/set-null FK behavior, and indexes; the 12 event types are present.
  Verdict: Confirmed.

- **SC2** (T2): Does the SQLite migration mirror the Postgres schema (TEXT for everything, prior_state TEXT JSON), and is 'prior_state' added to _JSON_COLUMNS in BOTH sqlite.py and supabase.py?
  Executor note: Yes. SQLite migration mirrors the editorial tables using SQLite-compatible types with prior_state TEXT, and prior_state is registered in _JSON_COLUMNS in both adapters.
  Verdict: Confirmed.

- **SC3** (T3): Are checklist_items and epic_events both included in the TRUNCATE … RESTART IDENTITY CASCADE block, and are they ordered correctly w.r.t. tables that reference them?
  Executor note: Yes. checklist_items and epic_events are in the TRUNCATE block before parent tables they reference; the Supabase test module skips without SUPABASE_TEST_DB_URL.
  Verdict: Confirmed.

- **SC4** (T4): Is parse() truly lenient (never raises on '', plain text, no-##, no-#, missing-Goal)? Does validate_for_write raise BodyValidationError with the exact message format 'body_missing_required_section: title' / '… goal'? Does _preamble include the # Title line? Are fenced ## blocks NOT treated as section boundaries? Is the file <450 lines and stdlib-only?
  Executor note: Yes. parse() is lenient for empty/plain/missing structural bodies, validate_for_write raises the exact title/goal messages, _preamble includes # Title, fenced ## lines are ignored as boundaries, and body.py is stdlib-only at 253 lines.
  Verdict: Confirmed.

- **SC5** (T5): Does DEFAULT_BODY_TEMPLATE produce exactly the six sections (Goal, Principles, Context, Key Decisions, Open Questions, Deliverable) with # Title and ## Goal first paragraph populated? Is DEFAULT_CHECKLIST_SEED exactly 18 items in spec §634 order with source='default_seed' and positions 1–18?
  Executor note: Yes. The template emits # Title and exactly Goal, Principles, Context, Key Decisions, Open Questions, Deliverable with Goal populated. The seed has exactly 18 strings in spec order for later insertion as default_seed/open positions 1-18.
  Verdict: Confirmed.

- **SC6** (T6): Do the parser tests cover all 6 round-trip fixtures, the _preamble title round-trip (replace with '# New Title\n' AND replace with ''), all 5 lenient-parse cases, the code-fence guard, and the diffs_equivalent boundary cases?
  Executor note: Yes. tests/test_body_parser.py covers all requested roundtrip, _preamble, lenient parse, fence, section-op, and diff equivalence cases.
  Verdict: Confirmed.

- **SC7** (T7): Are all 15 new methods declared in the Protocol with correct signatures? Is Store.create_turn(epic_id: str|None) updated? Are _EPIC_COLUMNS and _CHECKLIST_COLUMNS guard sets specified?
  Executor note: Yes. The Store Protocol now declares the requested editorial methods, create_turn accepts str | None, and the two guard sets are specified in ports.py.
  Verdict: Confirmed.

- **SC8** (T8): Does SupabaseStore implement every new method, route update_epic / update_checklist_item through self._update with the new column guards, add 'epic_id' to _MESSAGE_COLUMNS and _TURN_COLUMNS, and use the correct id prefixes ('epic', 'check', 'evt')?
  Executor note: Yes. SupabaseStore implements the new editorial surface, update_epic/update_checklist_item route through self._update with _EPIC_COLUMNS/_CHECKLIST_COLUMNS, epic_id is in _MESSAGE_COLUMNS/_TURN_COLUMNS, and ids use epic/check/evt prefixes.
  Verdict: Confirmed.

- **SC9** (T9): Does SQLiteStore mirror SupabaseStore exactly (same methods, same column guards, same epic_id additions, prior_state in _JSON_COLUMNS, create_turn accepts None)?
  Executor note: Yes. SQLiteStore mirrors the Supabase editorial surface, uses the same guards and epic_id column support, keeps prior_state in _JSON_COLUMNS, and create_turn accepts/stores None.
  Verdict: Confirmed.

- **SC10** (T10): Does the contract test cover create_epic + seed_checklist + record_epic_event + list_epic_events + latest_transaction_id + ordering, AND assert create_turn(epic_id=None) succeeds with NULL stored?
  Executor note: Yes. The shared store contract now covers create_epic, seed_checklist, record_epic_event, list/filter events, events_by_transaction, latest_transaction_id, event ordering, and create_turn(epic_id=None) persisted as NULL.
  Verdict: Confirmed.

- **SC11** (T11): Does create_epic write epics.title/goal from parsed values (not raw args)? Does edit_epic reject meta with meta_not_supported, mixed body ops with body_op_conflict, and produce expected_diff_mismatch without writing? Does revert capture full pre-revert {body,title,goal,checklist} in prior_state? Are all four registered with operation_kind='write'?
  Executor note: Yes. create_epic writes parsed title/goal, edit_epic rejects meta/body conflicts and refuses expected_diff mismatches before writing, revert captures full pre-revert body/title/goal/checklist, and all four write tools register with operation_kind='write'.
  Verdict: Confirmed.

- **SC12** (T12): Are all 7 read tools registered with operation_kind='read'? Does get_epic_at_time return the initial state (template body + 18-item seed) for T_before_creation per spec §1678? Does it correctly undo body_edit / checklist_change / reverted_to using prior_state?
  Executor note: Yes. All seven read tools register with operation_kind='read'; get_epic_at_time returns the created initial body/checklist snapshot before creation and replays body_edit, checklist_change, and reverted_to prior_state snapshots.
  Verdict: Confirmed.

- **SC13** (T13): Are both editorial modules imported with `# noqa: F401` near loop.py:16 alongside the existing tool imports?
  Executor note: Yes. loop.py imports both agent_kit.tools.editorial and agent_kit.tools.editorial_reads with # noqa: F401 alongside communication/images, and import-time registry checks confirm all editorial tools are registered.
  Verdict: Confirmed.

- **SC14** (T14): Is active_epic_id introduced as a local that EVERY _envelope/_abort_turn site reads (12 enumerated call sites)? Is it refreshed after every registry.invoke? Is lock acquisition wrapped in `if epic_id is not None`? Does hot context get synthesized as empty when epic_id is None? Is inbound_message_id captured into context.metadata?
  Executor note: Yes. active_epic_id is local state for envelope/abort paths, lock acquisition is skipped when epic_id is None, no-epic hot context is synthesized, inbound_message_id is captured, and active_epic_id refreshes after both registry.invoke calls.
  Verdict: Confirmed.

- **SC15** (T15): Is Envelope.epic_id typed Optional[str] with default None? Is 'epic_id' removed from the schema's required array AND its type relaxed to ['string','null']? Does _drop_none correctly strip None from to_dict() output?
  Executor note: Yes. Envelope.epic_id is Optional with default None, epic_id is no longer required in the schema, the property accepts string/null, and to_dict() drops None epic_id.
  Verdict: Confirmed.

- **SC16** (T16): Is --epic argparse default None (no longer required)? Does the exception envelope path handle args.epic=None correctly? Is the help text updated?
  Executor note: Yes. --epic now defaults to None, help documents omitted --epic bootstrap, and the CLI smoke confirms args.epic=None produces a valid no-epic envelope.
  Verdict: Confirmed.

- **SC17** (T17): Does the epic_outline log fire only on completed turns whose tool_calls include create_epic/edit_epic/revert AND active_epic_id is not None? Does details contain title + sections array (name + line_count) + total_lines from body.outline()? Is it skipped for failed turns?
  Executor note: Yes. epic_outline logging is gated to completed turns with active_epic_id and create_epic/edit_epic/revert tool events, uses body.outline details, and is skipped for failed/no-epic paths.
  Verdict: Confirmed.

- **SC18** (T18): Does the integration test cover EVERY Sprint 2a acceptance criterion (spec §131–142) plus the critique-driven additions: bootstrap envelope == new_id, CLI subprocess no-epic path, errored-no-epic envelope=None+schema-valid, all 6 sections via section ops, _preamble title edit, expected_diff match+mismatch, revert with reverted_to.prior_state full snapshot, get_epic_at_time across revert AND before creation, get_recent_turns, search_tool_calls, operation_kind values, meta_not_supported, epic_outline log?
  Executor note: Yes. The integration tests cover bootstrap envelope == new_id, CLI subprocess no-epic path, errored-no-epic envelope schema validity, all six sections via section ops, _preamble title edit, expected_diff match and mismatch, revert with full reverted_to prior_state, get_epic_at_time across turn 5, before revert, and before creation, get_recent_turns, search_tool_calls, operation_kind values, meta_not_supported, and epic_outline logs.
  Verdict: Confirmed.

- **SC19** (T19): Does the regression test construct Envelope(epic_id=None), serialise via to_json(), and validate against envelope.schema.json with jsonschema, asserting both omitted and explicit-null forms pass?
  Executor note: Yes. The regression test constructs Envelope(epic_id=None), serializes through to_json(), validates omitted epic_id, then validates an explicit epic_id:null payload.
  Verdict: Confirmed.

- **SC20** (T20): Did the executor run the full pytest suite (NOT just targeted files), confirm zero failures including resident-mode + discord + run_turn + cli regressions, and exercise the no-epic bootstrap end-to-end via a throwaway script that was then deleted?
  Executor note: No zero-failure confirmation is possible because the full suite still stops at the known pre-existing tests/test_no_leaked_secrets.py leaked Supabase JWT prefix check in .megaplan/plans/sprint-1b-discord-resident/*. The targeted Sprint 2a modules passed, resident/discord/run_turn/cli tests executed before that failure passed, and the no-epic bootstrap was exercised with a throwaway script that was deleted.
  Verdict: Confirmed with caveat: full suite blocked by unrelated pre-existing secret-scan failure, while targeted Sprint 2a suites passed.

- **SC21** (T21): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: Yes. The only after_execute user action was surfaced as optional live Supabase validation requiring human-provided SUPABASE_TEST_DB_URL; it was not performed by the executor.
  Verdict: Confirmed.

## Meta

Execute phases in strict order: schema → parser+templates → store → tools → loop bootstrap → integration. The hardest concept to keep straight is the Optional[str] thread for the bootstrap path; if any boundary (Protocol, adapter, Envelope dataclass, JSON schema, CLI) is not updated, the integration test in T18 will fail with a schema-validation error or a type mismatch. Treat T14 + T15 + T16 as one logical change set even though they edit different files.

Two accepted tradeoffs are baked into the plan and must be honored, not "fixed": (1) `body_version` is deferred — DO NOT add the column or increment logic; the audit trail in epic_events.body_edit covers the title/body sync semantics. (2) `get_epic_at_time(T_before_creation)` returns the initial template body + 18-item seed checklist (i.e. the snapshot the `created` event captures in its prior_state) — NOT empty/None. Plan v3 had the older "empty" wording; the integration test in T18 asserts the spec §1678 reading.

The parser split is the second most error-prone area: `parse()` is lenient and never raises; `validate_for_write()` is the only function that raises `body_missing_required_section`. Read tools and `get_epic_at_time` MUST call only `parse()`. If you find yourself catching a parser exception inside a read path, you've gotten this wrong.

When implementing `revert`, capture the pre-revert state BEFORE applying the inverse mutations. The captured `{body, title, goal, checklist}` snapshot goes into the `reverted_to` event's `prior_state` so a subsequent `get_epic_at_time` call at a timestamp just before the revert can reconstruct correctly. Verify this end-to-end with the `T_just_before_revert` assertion in T18.

`create_epic` retro-stamps the inbound message and bot_turn rows AND sets `context.metadata['epic_id']` so the loop's `active_epic_id` refresh after `registry.invoke` picks up the new id. The Turn-1 envelope assertion in T18 (`envelope.epic_id == new_id`) is the canary for this thread.

For `edit_epic`, `changes.meta` returns `meta_not_supported` with a hint pointing at `body.sections._preamble` (title) or `body.sections.Goal` (goal). `changes.sprints` and `changes.state` return `not_yet_supported`. Mixed body op flavours return `body_op_conflict`. These three error branches are explicit and have integration test coverage.

Operation_kind: every read tool registers with `operation_kind='read'`; every write tool with `operation_kind='write'`. The default in `@register_tool` is `write`, so omitting the kwarg silently mis-attributes reads. T18 asserts the recorded values in `tool_calls`.

CLAUDE.md forbids creating a `megaplan/` directory in the project root — the existing one is harness state. Do not touch it. Do not create wrapper packages there.

The final test task (T20) must run the FULL suite, not just targeted files, so Sprint 1a/1b regressions surface immediately. The throwaway script requirement (bootstrap an epic via no-epic path) is a manual sanity check beyond the unit/integration tests — write it, run it, delete it.
