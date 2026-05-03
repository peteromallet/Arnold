# Implementation Plan: Sprint 4 Sprint Mode And Handoff Gating

## Overview
Arnold already has the Sprint 2 editorial core: markdown body helpers in `agent_kit/body.py`, `edit_epic` in `agent_kit/tools/editorial.py`, store ports/adapters in `agent_kit/ports.py`, `agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`, SQLite/Supabase migrations, prompts, invocation envelopes, and editorial read/time-travel tools. The main write insertion point is explicit: `edit_epic` currently rejects both `changes.sprints` and `changes.state` at `agent_kit/tools/editorial.py:133`, so Sprint 4 should remove that guard and add server-side sprint writes plus gated state transitions.

The critique flags do not show that the plan targeted the wrong root cause. The root write path is still `edit_epic`; the missing pieces are downstream visibility surfaces. Sprint 4 state transitions and sprint changes must be observable through invocation envelopes and existing read/replay tools, or callable clients and users can see stale state even when the database write succeeds.

The simplest direct approach is to keep `edit_epic` as the single write surface, add store-level sprint CRUD methods, enforce lifecycle invariants server-side, and then wire every existing observation path: hot context, read tools, time-travel replay, revert, and invocation envelopes.

## Phase 1: Data Model And Store Port

### Step 1: Add sprint migrations (`agent_kit/store/migrations/sqlite/006_sprints.sql`, `supabase/migrations/202604300006_006_sprints.sql`)
**Scope:** Medium
1. Create `sprints` and `sprint_items` with the specified fields and status checks.
2. Add a partial unique index for queued positions: SQLite `CREATE UNIQUE INDEX ... WHERE status = 'queued'`; Postgres/Supabase same partial unique index.
3. Add read indexes on `sprints(epic_id, sprint_number)`, `sprints(epic_id, status, queue_position)`, and `sprint_items(sprint_id, position)`.

### Step 2: Extend the store protocol (`agent_kit/ports.py`)
**Scope:** Medium
1. Add sprint methods near the existing epic/checklist methods at `agent_kit/ports.py:249`: `create_sprint`, `load_sprint`, `list_sprints`, `update_sprint`, `delete_sprint`, `replace_sprint_items`, `list_sprint_items`, and a helper that returns sprints with items for an epic.
2. Keep these methods low-level and predictable; validation belongs in the Sprint 4 domain/tool layer, not in adapters.

### Step 3: Implement SQLite and Supabase adapters (`agent_kit/store/sqlite.py`, `agent_kit/store/supabase.py`)
**Scope:** Medium
1. Add `_SPRINT_COLUMNS` and `_SPRINT_ITEM_COLUMNS` beside `_EPIC_COLUMNS` at `agent_kit/store/sqlite.py:1210` and the equivalent Supabase constants.
2. Implement sprint CRUD around the existing patterns for `checklist_items` at `agent_kit/store/sqlite.py:682` and Supabase equivalent.
3. Update `load_hot_context` at `agent_kit/store/sqlite.py:362` and `agent_kit/store/supabase.py:188` to include current sprints and items so the model can reason about queued/pending state.
4. Extend store contract tests so SQLite and Supabase fake adapter behavior stay aligned.

## Phase 2: Deterministic Sprint Domain Logic

### Step 4: Add a sprint domain module (`agent_kit/sprints.py`)
**Scope:** Large
1. Implement normalization and validation for sprint payloads: sprint number uniqueness, allowed statuses, item complexity/status values, queued sprint position requirement, pending reason capture, and PM-task-level item checks.
2. Implement default lock-in assignment: first sprint queued at the next available position, remaining sprints pending with a supplied or default pending reason.
3. Implement queue operations for post-handoff updates: queue a sprint, pend a sprint, and reorder queued sprints with gapless positions.
4. Return structured sprint-change summaries so `edit_epic` can put them in tool results, audit events, and invocation envelopes.

### Step 5: Add gate evaluators (`agent_kit/gating.py`)
**Scope:** Large
1. Implement `evaluate_state_transition(epic, body, checklist, sprints, target_state)` with explicit blockers.
2. Enforce `shaping -> sprinting`: body length >500, `Goal` and `Deliverable` sections exist, and checklist is mostly resolved using the spec rule of fewer than 3 open items unless open items have material content.
3. Enforce `sprinting -> planned`: at least one sprint, all sprints queued or pending, queued sprints have unique queue positions, pending sprints have pending reasons or a recorded no-reason value, checklist statuses are only `done`, `skipped`, or `superseded`, and body passes a deterministic PM-handoff heuristic.
4. Keep the PM-handoff heuristic concrete and testable: require non-placeholder Goal/Deliverable, at least one decision/principle/context section with substantive content, no unresolved lockdown phrase outside Open Questions, and PM-level sprint items. Do not add a live LLM dependency for server enforcement unless explicitly chosen later.

### Step 6: Implement lockdown scanning (`agent_kit/lockdown.py` or in `agent_kit/gating.py`)
**Scope:** Medium
1. Use `agent_kit/body.py:52` parsing so section attribution matches existing markdown behavior.
2. Scan case-insensitively for: `TBD`, `to be decided`, `to be determined`, `we'll see`, `figure out later`, `figure it out`, `tunable`, `depends on what surfaces`, `can adjust later`, `decide later`.
3. Ignore matches in `Open Questions` and fenced code blocks. The body parser already tracks fences for headings at `agent_kit/body.py:227`; add a small reusable text iterator or local scanner that also suppresses fenced-code lines.
4. Return blockers with phrase, section, and line number.

## Phase 3: Wire `edit_epic`

### Step 7: Extend the tool schema and write path (`agent_kit/tools/editorial.py`)
**Scope:** Large
1. Add optional top-level `force` to `EDIT_EPIC_SCHEMA` at `agent_kit/tools/editorial.py:26`.
2. Remove the `not_yet_supported` guard at `agent_kit/tools/editorial.py:133`.
3. Support `changes.sprints` operations such as `replace`, `upsert`, `update`, `delete`, `lock_in`, `queue`, `pend`, and `reorder`.
4. Support `changes.state.target` for state advancement, with all gating run before writes unless `force: true`.
5. Keep body, checklist, sprint, and state writes in one transaction and record separate `epic_events` as appropriate: `sprints_change`, `sprint_status_change`, `state_change`, and `forced_handoff`.
6. Return `state_transition`, `sprint_changes`, and blockers in the `edit_epic` tool result so the loop and callable clients can expose what changed without re-inferring it from raw database rows.
7. On force-through, still compute blockers, apply the transition, and log `forced_handoff` with bypassed conditions.

### Step 8: Preserve revert semantics (`agent_kit/tools/editorial.py`)
**Scope:** Medium
1. Extend `revert` handling around the existing event replay logic so `sprints_change`, `sprint_status_change`, `state_change`, and `forced_handoff` can restore prior sprint rows and prior epic state.
2. Snapshot enough prior state before each sprint/status write to make revert reliable: prior epic state, prior sprint rows, and prior sprint item rows for touched sprints.

## Phase 4: Visibility Surfaces And Replay

### Step 9: Populate invocation envelopes (`agent_kit/loop.py`, `agent_kit/envelope.py`, `agent_kit/envelope.schema.json`)
**Scope:** Medium
1. Update the completed-turn envelope path so `state_after` is reloaded from the store instead of always echoing `state_before` on success.
2. Populate existing `StateDelta.state_transition` and `StateDelta.sprint_changes` fields from `edit_epic` tool results and/or audited tool events.
3. Update `agent_kit/envelope.schema.json` if the existing schema shape is too loose or incomplete for Sprint 4 deltas.
4. Add tests showing invocation-mode callers see `shaping -> sprinting`, `sprinting -> planned`, and sprint queue/reorder deltas in the returned envelope.

### Step 10: Extend editorial read tools and replay (`agent_kit/tools/editorial_reads.py`)
**Scope:** Medium
1. Add sprints with items to the normal `get_epic` payload, alongside body, checklist, title, goal, and state.
2. Extend `get_epic_at_time` reconstruction to replay `sprints_change`, `sprint_status_change`, `state_change`, `forced_handoff`, `reverted_to`, and `created` events.
3. Use the same event prior-state snapshots created in Step 8 so historical payloads and revert semantics agree.
4. Add tests that read current sprints after lock-in and reconstruct pre/post queue state from event history.

## Phase 5: Prompt And Turn Behavior

### Step 11: Update Arnold instructions (`prompts/system.md`)
**Scope:** Small
1. Add Sprint 4 tool-use guidance near the existing Sprint Organization section at `prompts/system.md:112` and `prompts/system.md:243`.
2. Teach the two-beat flow: first propose/finalize sprints and ask for confirmation, then call `edit_epic` with `lock_in` assigning first queued and rest pending.
3. Describe blocker surfacing: list blockers from `edit_epic`, offer address/skip/force-through, and call with `force: true` only after explicit user direction.
4. Add post-handoff queue commands: queue sprint N, pend sprint N with reason, and reorder queued sprints.

### Step 12: Make end-of-turn checks phase-aware (`agent_kit/end_of_turn.py`, `agent_kit/loop.py`)
**Scope:** Medium
1. Extend `evaluate_end_of_turn` at `agent_kit/end_of_turn.py:33` to receive epic state and sprint snapshots.
2. Add findings for sprinting/planned phases: sprinting turns that make no sprint progress when sprint action was expected, planned transitions without queued/pending sprint assignment, and all-pending planned state needing an explicit user-facing note.
3. Update the loop call site to pass sprint snapshots before/after, alongside the existing body/checklist snapshots.

## Phase 6: Tests And Validation

### Step 13: Add focused unit tests (`tests/test_sprints.py`, `tests/test_gating.py`, `tests/test_lockdown.py`)
**Scope:** Medium
1. Cover gating combinations, including body under 500 chars blocking `shaping -> sprinting`.
2. Cover force-through success and `forced_handoff` event logging.
3. Cover confirmation parsing and default queue/pend assignment.
4. Cover queue reordering math and duplicate queue-position rejection.
5. Cover lockdown regex phrases, section attribution, Open Questions exemption, and fenced-code exemption.

### Step 14: Add adapter, envelope, read, and migration tests (`tests/store_contract.py`, `tests/test_supabase_adapters.py`, `tests/test_sqlite_store.py`, `tests/test_envelope.py`, `tests/test_editorial_reads.py`)
**Scope:** Medium
1. Assert sprint CRUD works through the common store contract.
2. Assert the Supabase migration text contains the `sprints`, `sprint_items`, checks, indexes, and partial unique queued-position constraint.
3. Assert SQLite rejects two queued sprints with the same `queue_position` for one epic.
4. Assert completed invocation envelopes report the actual post-turn epic state and sprint changes.
5. Assert `get_epic` includes current sprints and `get_epic_at_time` reconstructs sprint/state history.

### Step 15: Add integration tests (`tests/test_sprint_mode_lifecycle.py`)
**Scope:** Large
1. Create an epic, enrich body/checklist, advance `shaping -> sprinting`, propose/refine/finalize sprints, lock in queue/pending assignments, and advance to `planned`.
2. Verify a decision-doc-shaped epic still produces at least one sprint.
3. Verify post-handoff `queue sprint 2` and `do sprint 3 first` update positions, log `sprint_status_change`, appear in `get_epic`, and appear in the invocation envelope.
4. Verify lockdown blocks `TBD` in Key Decisions and passes when the phrase is moved to Open Questions.

## Execution Order
1. Land migrations and store methods first so tests have durable primitives.
2. Add deterministic domain modules and unit tests before touching `edit_epic` orchestration.
3. Wire `edit_epic` once validators, sprint operations, and event snapshots are tested directly.
4. Wire visibility surfaces: hot context, envelopes, reads, replay, and revert.
5. Update prompts and end-of-turn checks after server behavior exists.
6. Finish with full lifecycle integration tests and the existing suite.

## Validation Order
1. Run targeted unit tests first: `pytest tests/test_lockdown.py tests/test_gating.py tests/test_sprints.py`.
2. Run adapter/migration tests: `pytest tests/test_sqlite_store.py tests/test_supabase_adapters.py tests/test_supabase_store.py`.
3. Run visibility tests: `pytest tests/test_envelope.py tests/test_editorial_reads.py tests/test_end_of_turn.py`.
4. Run lifecycle tests: `pytest tests/test_sprint_mode_lifecycle.py tests/test_editorial_loop.py`.
5. Run the full test suite with `pytest` after targeted tests pass.

## Notes On Simplicity
Keep all enforcement local and deterministic for this sprint. The spec mentions optional second-opinion checks, but the requested scope calls out concrete server-side conditions; adding live model calls inside gating would make core state transitions harder to test and operate. The model can still suggest force-through or request second opinions through existing prompt behavior, but the server gate should remain deterministic.

The envelope and read/replay additions are not scope growth. Sprint 4 changes the canonical lifecycle state and sprint queue; existing public surfaces must report that state accurately for the feature to be complete.
