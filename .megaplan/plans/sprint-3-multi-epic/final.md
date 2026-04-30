# Execution Checklist

- [ ] **T13:** Read user_actions.md. For each before_execute action, programmatically verify completion using bash tools — grep .env for required keys, query the migrations table, curl the dev server, etc. Reading the file does NOT count as verification; you must run a command. For actions that genuinely cannot be verified mechanically (manual UI checks), explicitly ask the user. If anything is incomplete or unverifiable, mark this task blocked with reason and STOP. (skipped)
  Executor notes: Skipped because the environment prevented re-verification: `pwd` failed with exit code -1, and the sandbox is read-only. Prior tracking shows U1 was mechanically checked and not satisfied, so no execution proceeded past this prerequisite.

- [ ] **T1:** Audit `planning-bot-spec.md` and the current routing/store code to pin Sprint 3 contracts: epic selection rules, reference behavior, user modes, understanding summaries, switch announcements, gap acknowledgment threshold, Discord inbound persistence, resident coalescing, `run_turn` lock acquisition, `Store` conventions, schema fields, migration style, and whether persisted inbound messages need reassignment after routing. (skipped)
  Depends on: T13
  Executor notes: Skipped because repository reads failed and T13 remains unresolved. Could not audit `planning-bot-spec.md` or routing/store code to identify insertion points, schema timestamps, gap/mode rules, or reassignment requirements.

- [ ] **T2:** Extend `agent_kit/ports.py` with Store protocol methods for `list_epics`, `search_epics`, and `search_messages`, using stable portable result shapes containing IDs, title/content snippets, status, timestamps, direction, rank where applicable, and disambiguation metadata. Add a minimal message epic reassignment method only if T1 confirms inbound rows are persisted before final selected-epic routing. (skipped)
  Depends on: T13, T1
  Executor notes: Skipped because `agent_kit/ports.py` could not be read or modified in the read-only/failing shell environment. T1 did not provide the required reassignment decision.

- [ ] **T3:** Add full-text search migrations for both stores: SQLite migration under `agent_kit/store/migrations/sqlite/` using FTS5 or the repo's established SQLite FTS pattern for `messages.content`, and Supabase migration under `supabase/migrations/` using PostgreSQL full-text search with a GIN index or generated/search-vector column. Keep visibility/scoping aligned with existing message reads. (skipped)
  Depends on: T13, T1, T2
  Executor notes: Skipped because migrations cannot be created in the read-only environment, and existing migration style/schema could not be inspected due shell failure.

- [ ] **T4:** Implement the new Store methods in `agent_kit/store/sqlite.py` and `agent_kit/store/supabase.py`, including deterministic ranking/tie-breakers and compatible result shapes. Implement message epic reassignment in both adapters if T2 added it. (skipped)
  Depends on: T13, T2, T3
  Executor notes: Skipped because SQLite/Supabase adapters cannot be inspected or edited. Store protocol and migration prerequisites are unavailable.

- [ ] **T5:** Implement deterministic pre-turn epic routing before resident payload coalescing and before `run_turn` lock acquisition. Inputs must include message text, author/conversation identity, recent active epics, current/default context, and previous selected epic. Explicit epic names/correction phrases override recency; ambiguous messages select the single most recently edited active epic within 24 hours; unclear context must produce clarification behavior instead of mutating a guessed real epic. (skipped)
  Depends on: T13, T1, T4
  Executor notes: Skipped because resident/routing code cannot be inspected or edited, and the pre-turn insertion point was not established by T1.

- [ ] **T6:** Wire selected-epic lock safety and switch announcements through `agent_kit/resident.py` and `agent_kit/loop.py`: call `run_turn(epic_id=...)` with the selected real epic, update queued payloads and persisted inbound rows before execution when routing changes, ensure outbound rows attach to the selected epic, reject or safely defer late unsafe epic switches, and include the destination epic title in outbound messages only when an actual switch occurs. (skipped)
  Depends on: T13, T5
  Executor notes: Skipped because `agent_kit/resident.py` and `agent_kit/loop.py` cannot be inspected or edited, and selected-epic routing from T5 is unavailable.

- [ ] **T7:** Register `list_epics`, `search_epics`, and `search_messages` read tools through the existing tool registry under `agent_kit/tools/` or the actual registry found during T1. Tool handlers must call only the Store protocol methods, return concise stable payloads for disambiguation/user summaries, and avoid direct adapter SQL or cross-user data exposure. (skipped)
  Depends on: T13, T4
  Executor notes: Skipped because the tool registry cannot be inspected or edited, and Store read methods from T4 are unavailable.

- [ ] **T8:** Implement reference resolution against the most recent outbound bot message in the same conversation/selected-epic context. Resolve phrases such as `the second one`, `that point`, and `the last option` using structured outbound metadata when available, otherwise parse common raw-text structures including numbered lists, bullets, headings, and short option lists. Return resolved target plus ambiguity state so low-confidence cases ask for clarification. (skipped)
  Depends on: T13, T6
  Executor notes: Skipped because outbound-message storage/resolution code cannot be inspected or edited, and selected-epic message scoping from T6 is unavailable.

- [ ] **T9:** Implement user mode detection and conversation gap acknowledgment in the prompt/policy builder path found during T1. Detect Deep-thinking, Brainstorming, and Executing separately from epic routing, pass distinct response policy inputs for each mode, decide stickiness according to the spec or T1 finding, and add the specified gap acknowledgment only when the configured threshold is crossed. (skipped)
  Depends on: T13, T1, T6
  Executor notes: Skipped because prompt/policy code cannot be inspected or edited, and T1 did not establish gap threshold or mode stickiness rules.

- [ ] **T10:** Implement `show me what you know about X` understanding summaries. Resolve `X` through explicit epic matching, `search_epics`, and `search_messages`; ground output in stored epic/message data; and return every structured section required by `planning-bot-spec.md` without unsupported synthesis. (skipped)
  Depends on: T13, T7, T9
  Executor notes: Skipped because summary/prompt/tool code cannot be inspected or edited, and search tools plus mode/prompt wiring are unavailable.

- [ ] **T11:** Add or extend focused project tests for the new behavior: Store contract/migration coverage for SQLite and Supabase adapters, seeded search corpus with 10 expected hit IDs, pre-turn routing and selected-epic lock safety, inbound/outbound row attachment, unsafe late-switch protection, epic selection fixtures with five active epics, reference resolver fixtures, mode detection fixtures, switch announcement assertions, multi-epic switching/search/summary integration, 30 canned epic-selection eval scenarios requiring at least 27 correct, and 10 ambiguity scenarios requiring clarification instead of guessing. (skipped)
  Depends on: T13, T3, T4, T5, T6, T7, T8, T9, T10
  Executor notes: Skipped because tests cannot be added in the read-only environment, and no Sprint 3 implementation tasks completed to test.

- [ ] **T12:** Run verification and fix until passing: run the most relevant existing Store contract tests first for SQLite, then Supabase adapter tests if credentials/config are available, then routing/lock-safety tests, unit tests for epic selection/reference resolution/mode detection, integration tests for switching/search tools/understanding summaries, LLM-graded evals for epic selection and ambiguity handling, and finally the repository's broader lint/test suite. Also write a short throwaway script that exercises the Sprint 3 routing/search/reference scenario end to end, run it, confirm behavior, and delete the script before finalizing. (skipped)
  Depends on: T13, T11
  Executor notes: Skipped because U1 is awaiting completion, T11 is skipped, shell execution failed, and the read-only sandbox prevents writing/running the required throwaway script. No verification suite could be run.

- [x] **T14:** Surface after_execute user_actions to the user:
- U2: After code review/merge approval, apply the Supabase migration to the intended Supabase environment using the team's normal deployment process.
- U3: Manually review a short live or staging conversation for the three user modes to confirm the responses feel meaningfully different without becoming verbose or performative.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T12
  Executor notes: After-execute human actions were clearly surfaced without performing them: U2 requires applying the Supabase migration after code review/merge approval using the team deployment process; U3 requires manual live/staging review of the three user modes for product quality.
  Files changed:
    - .DS_Store
    - .megaplan/plans/sprint-3-multi-epic/.plan.lock
    - .megaplan/plans/sprint-3-multi-epic/critique_output.json
    - .megaplan/plans/sprint-3-multi-epic/critique_v1.json
    - .megaplan/plans/sprint-3-multi-epic/execution.json
    - .megaplan/plans/sprint-3-multi-epic/execution_audit.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_1.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_10.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_11.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_12.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_2.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_3.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_4.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_5.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_6.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_7.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_8.json
    - .megaplan/plans/sprint-3-multi-epic/execution_batch_9.json
    - .megaplan/plans/sprint-3-multi-epic/execution_trace.jsonl
    - .megaplan/plans/sprint-3-multi-epic/faults.json
    - .megaplan/plans/sprint-3-multi-epic/final.md
    - .megaplan/plans/sprint-3-multi-epic/finalize.json
    - .megaplan/plans/sprint-3-multi-epic/finalize_snapshot.json
    - .megaplan/plans/sprint-3-multi-epic/gate.json
    - .megaplan/plans/sprint-3-multi-epic/plan_v1.md
    - .megaplan/plans/sprint-3-multi-epic/plan_v1.meta.json
    - .megaplan/plans/sprint-3-multi-epic/plan_v2.md
    - .megaplan/plans/sprint-3-multi-epic/plan_v2.meta.json
    - .megaplan/plans/sprint-3-multi-epic/state.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_critique_v1.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_execute_v2.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_finalize_v2.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_plan_v1.json
    - .megaplan/plans/sprint-3-multi-epic/step_receipt_revise_v2.json
    - agent_kit/.DS_Store
    - agent_kit/__pycache__/end_of_turn.cpython-38.pyc
    - agent_kit/__pycache__/ledger.cpython-38.pyc
    - agent_kit/__pycache__/loop.cpython-38.pyc
    - agent_kit/__pycache__/ports.cpython-38.pyc
    - agent_kit/__pycache__/prompts.cpython-38.pyc
    - agent_kit/model/__pycache__/anthropic.cpython-38.pyc
    - agent_kit/store/__pycache__/sqlite.cpython-38.pyc
    - tests/.DS_Store
    - tests/__pycache__/test_anthropic_model.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_anthropic_replay.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_body_parser.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_editorial_loop.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_editorial_polish_loop.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_editorial_polish_tools.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_end_of_turn.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_ledger.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_mid_turn_messages.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_run_turn.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sprint2b_llm_eval_scaffolding.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_sqlite_store.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_supabase_adapters.cpython-38-pytest-8.3.5.pyc
    - tests/__pycache__/test_system_prompt.cpython-38-pytest-8.3.5.pyc

## Watch Items

- Do not invoke nested megaplan tooling; treat repository mentions of megaplan as implementation context only.
- Epic selection must happen before `run_turn` acquires the epic lock, or any later switch path must be explicitly lock-safe and tested.
- Inbound Discord messages may already be persisted under a synthetic/default key; if so, reassign both payload and stored row before queueing/running the selected real epic turn.
- Define `most recently edited epic` from the real schema/spec before implementation. Candidate fields may include `epics.updated_at`, latest message timestamp, or last bot-applied mutation timestamp.
- Ambiguous messages should select a real epic only when exactly one safe qualifying default exists within 24 hours; otherwise ask for clarification.
- Explicit epic names and correction phrases override recency and must not be mistaken for user mode signals.
- Switch announcements must include the destination epic title only on actual epic changes, not every routed message.
- Search/list tools must go through `Store` in `agent_kit/ports.py`; no Supabase-only helper or direct tool SQL.
- SQLite and Supabase result shapes must remain compatible enough for shared tests and model/tool callers.
- Full-text search must respect existing user/conversation/epic visibility boundaries and avoid cross-user leakage.
- Reference resolution should prefer structured outbound metadata when present but must pass raw-text fixtures for existing stored messages.
- Mode behavior should be distinct but not performative: Deep-thinking measured/substantive, Brainstorming exploratory, Executing direct/minimal.
- Do not commit, log, or embed the redacted Supabase service-role key; use existing environment configuration for Supabase tests.
- Debt watch: avoid worsening known attachment-ingestion recovery gaps; Sprint 3 should not promise deterministic storage reissue without durable payload source material.
- LLM-graded evals must be deterministic and cheap enough for normal verification where the repo supports that.

## Sense Checks

- **SC1** (T1): Did the audit identify the exact pre-turn insertion point, the real schema timestamp to use for recency, the gap threshold/mode stickiness rules, and whether message reassignment is required?
  Executor note: No. The audit could not be performed because repository reads failed.

- **SC2** (T2): Do the Store protocol method signatures and result shapes contain enough metadata for disambiguation while remaining portable across SQLite and Supabase?
  Executor note: No. Store protocol signatures/result shapes were not added or verified.

- **SC3** (T3): Do both migrations add indexed full-text search for `messages.content` using each store's native approach without bypassing existing visibility assumptions?
  Executor note: No. SQLite and Supabase full-text search migrations were not added or verified.

- **SC4** (T4): Do SQLite and Supabase implementations return compatible, deterministic results for list/search calls, including stable tie-breakers and any required reassignment behavior?
  Executor note: No. SQLite and Supabase list/search implementations were not added or verified.

- **SC5** (T5): Can an ambiguous message with five active epics route to the single most recently edited active epic within 24 hours before resident coalescing and before the lock is acquired?
  Executor note: No. Pre-turn epic routing was not implemented or verified.

- **SC6** (T6): Are `run_turn`, persisted inbound rows, queued payloads, locks, outbound rows, and switch announcements all using the same selected epic ID/title?
  Executor note: No. Selected-epic lock safety, row attachment, and switch announcements were not wired or verified.

- **SC7** (T7): Are the new read tools registered through the existing tool system and calling only Store protocol methods with no adapter-specific SQL in tool handlers?
  Executor note: No. The read tools were not registered or verified.

- **SC8** (T8): Does the resolver correctly handle numbered lists, bullets, headings, mixed prose/list structures, and ambiguous `that point` cases against only the last outbound bot message in scope?
  Executor note: No. Reference resolution was not implemented or verified.

- **SC9** (T9): Are mode signals separated from epic routing, and does the prompt/policy path receive distinct inputs for Deep-thinking, Brainstorming, and Executing plus the correct gap acknowledgment state?
  Executor note: No. Mode detection and gap acknowledgment were not implemented or verified.

- **SC10** (T10): Does `show me what you know about X` resolve the right epic/message evidence and include every spec-required summary section without unsupported claims?
  Executor note: No. Understanding summaries were not implemented or verified.

- **SC11** (T11): Do the added/extended tests cover store search, routing/lock safety, row attachment, unsafe switches, reference resolution, mode detection, switch announcements, summaries, and the required eval thresholds?
  Executor note: No. Sprint 3 tests were not added or verified.

- **SC12** (T12): Did the focused tests, relevant integration tests, LLM-graded evals, throwaway reproduction script, and broader repo test/lint suite pass after any fixes and reruns?
  Executor note: No. Verification did not run; U1 is awaiting completion and shell execution failed.

- **SC13** (T13): Were all before_execute user_actions programmatically verified before execution proceeded?
  Executor note: No. The prior mechanical check found U1 incomplete/unverified, and this session could not re-check it.

- **SC14** (T14): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: Yes. U2 and U3 were surfaced as human follow-up actions, and neither was performed by the executor.

## Meta

Execute in dependency order and keep the routing/locking invariant central: the selected epic ID must be known before `run_turn` loads context or mutates state. Prefer small deterministic helpers for epic selection, reference resolution, and mode detection so the behavior is unit-testable instead of buried only in prompts. Treat `planning-bot-spec.md` as behavioral authority where the approved plan leaves questions open; when the spec is flexible, document the chosen interpretation in code/tests. Keep Supabase secrets out of all files and logs, and do SQLite verification first so implementation can proceed even if Supabase credentials are unavailable.
