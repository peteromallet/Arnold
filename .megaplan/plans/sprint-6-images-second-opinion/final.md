# Execution Checklist

- [x] **T1:** Add `second_opinions` persistence and store support. Create SQLite and Supabase migration `008_second_opinions` with the approved columns and indexes; extend store ports/adapters with `create_second_opinion`, `list_second_opinions`, `set_second_opinion_checklist_items`, active image lookup helpers, active reference-key checks, and same-epic active image deactivation. Extend hot context with active image metadata and the latest two second-opinion summaries without image bytes.
  Executor notes: Added SQLite and Supabase `008_second_opinions` migrations with matching columns/checks and indexes; extended Store protocol plus SQLite/Supabase adapters with `create_second_opinion`, `list_second_opinions`, `set_second_opinion_checklist_items`, active image lookup/existence/deactivation helpers, and hot-context active image metadata plus latest two second-opinion summaries without raw response or bytes. Targeted adapter tests pass under Python 3.11. Full suite was run and reached 153 passed/2 skipped, with one unrelated failure in `tests/test_no_leaked_secrets.py` caused by pre-existing deleted tracked `.megaplan` execution batch files.
  Files changed:
    - agent_kit/store/migrations/sqlite/008_second_opinions.sql
    - supabase/migrations/202604300008_008_second_opinions.sql
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
    - agent_kit/ports.py
    - tests/test_sqlite_store_v1b.py
    - tests/test_ports_v1b.py
    - tests/test_supabase_adapters.py
    - tests/test_supabase_store.py

- [x] **T2:** Add injectable OpenAI operations. Add the OpenAI dependency if missing; create a narrow `openai_ops` port and real adapter for `generate_image(prompt, quality, size, idempotency_key)` using `gpt-image-2` and `request_second_opinion(payload, idempotency_key)` using `gpt-5.5`; thread optional `openai_ops` through `ToolContext` and `run_turn` so tests can inject fakes and the default test suite does not make live network calls.
  Depends on: T1
  Executor notes: Added OpenAI dependency, OpenAIOps port/result dataclasses, lazy OpenAIAdapter for gpt-image-2 and gpt-5.5, and threaded optional openai_ops through ToolContext/run_turn. Verified fake injection through run_turn and fake-client adapter tests; no live OpenAI calls.
  Files changed:
    - pyproject.toml
    - agent_kit/ports.py
    - agent_kit/openai_ops.py
    - agent_kit/tool_kit.py
    - agent_kit/loop.py
    - tests/test_openai_ops.py
    - tests/test_run_turn.py

- [x] **T3:** Implement synchronous external-effect ledger support for tool bodies. Add a helper that records an `external_requests` row with `status='pending'` before result-dependent OpenAI or Blob effects, passes an idempotency key where supported, and marks the row `confirmed` or `failed`. Preserve the existing post-commit `context.external_queue` behavior for Discord sends and other queued effects.
  Depends on: T1
  Executor notes: Added run_synchronous_external_effect. It records pending external_requests before invoking the effect with an idempotency key, then confirms or fails the row. Added rollback restoration for settled synchronous effects and preserved existing post-commit external_queue behavior.
  Files changed:
    - agent_kit/tool_kit.py
    - tests/test_tool_kit_external_queue.py

- [x] **T4:** Implement generated-image helpers and the `generate_image` tool. Add quality auto-selection, generated `img_<8 hex chars>` reference keys checked for active uniqueness, compact prompt construction from epic context and active image descriptions, default description derivation, reference-key validation, Blob upload through the synchronous ledger helper, `images` row creation with `source='agent_generated'`, and regeneration semantics that deactivate the prior active row before inserting the replacement. Return image metadata and external request IDs, and do not post to Discord from this tool.
  Depends on: T1, T2, T3
  Executor notes: Implemented generate_image with prompt construction from epic/body/active image metadata, quality/size selection, reference-key validation and active-unique auto-generation, synchronous OpenAI and Supabase Storage ledger effects, agent_generated image row creation, prior active same-key deactivation on regeneration, metadata/external IDs in result, and no Discord posting. Verified with focused image tool tests plus related regression slice.
  Files changed:
    - agent_kit/tools/images.py
    - tests/test_image_tools.py

- [x] **T5:** Resolve markdown body image references in `render_epic`. Convert `![caption](image:reference_key)` to `![caption](storage_url)` using the active image for the epic, for both `user_uploaded` and `agent_generated` rows. Leave raw `epics.body` unchanged, and return stable missing-reference placeholders plus `missing_image_references` for unresolved keys.
  Depends on: T1
  Executor notes: Updated render_epic to resolve active ![caption](image:reference_key) references to storage_url for uploaded and generated images. Raw epics.body remains unchanged; results include raw_body, resolved_image_references, and missing_image_references with stable placeholders.
  Files changed:
    - agent_kit/tools/editorial.py
    - tests/test_render_epic_image_references.py

- [x] **T6:** Implement second-opinion parsing and `request_second_opinion`. Add `agent_kit/second_opinion.py` prompt construction from epic body, checklist, sprints, recent feedback, and optional focus/scoring inputs; parse structured output for score, strengths, holes, verdict, and summary; fail deterministically on malformed score/verdict/holes; convert significant holes into proposed checklist item objects without writing checklist rows. Register `request_second_opinion(epic_id, focus_areas?, scoring_override?, requested_by?)`, call OpenAI through the synchronous ledger helper, persist the `second_opinions` row, and return the row id, score, summary, verdict, holes, and proposed checklist items.
  Depends on: T1, T2, T3
  Executor notes: Implemented second-opinion payload construction, strict structured/text parsing, malformed-output rejection before persistence, proposed checklist item generation without checklist writes, request_second_opinion tool registration, synchronous OpenAI ledger call, and second_opinions row persistence with raw and parsed fields. Verified with focused second-opinion tests plus related regression slice.
  Files changed:
    - agent_kit/second_opinion.py
    - agent_kit/tools/second_opinion.py
    - agent_kit/loop.py
    - tests/test_second_opinion.py

- [x] **T7:** Link user-confirmed checklist items back to second opinions. Extend `edit_epic` checklist-add inputs with optional `source_second_opinion_id`, change checklist application to return created rows, include `created_checklist_items` and `created_checklist_item_ids` in the result, and when added items include a source second-opinion id, update `second_opinions.resulting_checklist_item_ids` in the same edit transaction.
  Depends on: T1, T6
  Executor notes: Extended edit_epic checklist-add handling to return created checklist rows and IDs, and to link created IDs back to source second_opinion.resulting_checklist_item_ids within the edit transaction. Added coverage for preserving existing linked IDs, excluding unlinked checklist additions, and rolling back checklist additions when the source second-opinion id is not valid for the epic. Focused editorial and related second-opinion/store tests pass; full pytest only fails on the pre-existing deleted .megaplan execution_batch_10.json FileNotFoundError in tests/test_no_leaked_secrets.py.
  Files changed:
    - agent_kit/tools/editorial.py
    - tests/test_editorial_loop.py
    - .megaplan/plans/sprint-6-images-second-opinion/execution_batch_4.json

- [x] **T8:** Wire prompt, score-driven response, and state-gate behavior. Update system prompt guidance so the bot surfaces score/verdict, proposes checklist items individually, never auto-edits from audit findings, and suggests reframing when score is below 5. Add deterministic end-of-turn coverage for score `<5` requiring a reframing suggestion in the next response path, and add default-on advisory second-opinion workflow at state-advance gates with a decline path such as `skip second opinion until I ask`.
  Depends on: T6, T7
  Executor notes: Updated system prompt guidance for second opinions and state gates; added deterministic low-score reframing enforcement for both final-text and explicit send_message paths; added state-transition advisory payload with decline suppression such as 'skip second opinion until I ask'. Focused affected modules pass. Full pytest was rerun and only fails on the pre-existing deleted .megaplan execution_batch_10.json FileNotFoundError in tests/test_no_leaked_secrets.py.
  Files changed:
    - agent_kit/end_of_turn.py
    - agent_kit/loop.py
    - agent_kit/tools/communication.py
    - agent_kit/tools/second_opinion.py
    - agent_kit/tools/editorial.py
    - prompts/system.md
    - tests/test_end_of_turn.py
    - tests/test_run_turn.py
    - tests/test_sprints.py
    - tests/test_system_prompt.py
    - .megaplan/plans/sprint-6-images-second-opinion/execution_batch_5.json

- [x] **T9:** Add and update focused Sprint 6 tests. Cover image quality selection, explicit override, reference-key validation and uniqueness, regeneration deactivation, render-time `image:` resolution, structured second-opinion parsing including malformed output, score `<5` reframing, score 6 with three holes producing three proposed checklist items, external request ledger rows for mocked OpenAI and Blob effects, checklist item creation/linking to `second_opinions`, full mocked image generation plus separate `send_image` audit calls, and full mocked second-opinion flow with checklist confirmation.
  Depends on: T4, T5, T6, T7, T8
  Executor notes: Added focused Sprint 6 tests for explicit image quality override, generated reference-key collision/uniqueness, malformed second-opinion verdict/holes parsing, full mocked image generation with render-time image: resolution and separate send_image audit rows, OpenAI/Blob/Discord external request ledger rows, and full mocked second-opinion checklist confirmation/linking. Targeted Sprint 6 and related regression modules pass. Full pytest was rerun and fails only on the previously reported tests/test_no_leaked_secrets.py FileNotFoundError for deleted .megaplan/plans/sprint-3-multi-epic/execution_batch_10.json; 185 tests passed and 2 skipped before that failure.
  Files changed:
    - tests/test_image_tools.py
    - tests/test_second_opinion.py
    - tests/test_sprint6_images_second_opinion.py

- [x] **T10:** Run validation and fix failures until the Sprint 6 changes work. Run the targeted commands `pytest tests/test_image_tools.py tests/test_second_opinion.py`, `pytest tests/test_sprint6_images_second_opinion.py`, and `pytest tests/test_editorial_loop.py tests/test_image_attachment_pipeline.py tests/test_end_of_turn.py`, then run full `pytest`. Also write a short throwaway script that exercises the mocked generated-image plus body-reference path and mocked second-opinion checklist-linking path, run it to confirm the behavior, then delete the script. If any test or script fails, read the error, fix the code, and rerun the relevant validation.
  Depends on: T9
  Executor notes: Validation completed with mocked OpenAI/Blob/Discord paths. Fixed checklist append ordering so new checklist additions without explicit positions append after existing items in both SQLite and Supabase stores. Required targeted modules pass under Python 3.11 via `python -m pytest`. Throwaway reproduction script passed after the fix and was deleted. Full `python -m pytest` was rerun and has only the known pre-existing `tests/test_no_leaked_secrets.py` FileNotFoundError for deleted `.megaplan/plans/sprint-3-multi-epic/execution_batch_10.json`; Sprint 6 tests pass in the full run.
  Files changed:
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
    - .megaplan/plans/sprint-6-images-second-opinion/execution_batch_7.json

- [x] **T11:** Surface after_execute user_actions to the user:
- U1: Provide real OpenAI credentials and any required project/org environment settings for manual staging of `gpt-image-2` and `gpt-5.5` after mocked tests pass.
- U2: Apply the Supabase migration to the target staging/production project when ready for non-local validation.
- U3: Manually smoke test the staging bot with real Supabase/OpenAI/Discord credentials by generating an image, sending it to Discord, rendering a body reference, requesting a second opinion, and confirming proposed checklist items.
Do not perform them yourself — these require human action. Mark this task done once they have been clearly communicated.
  Depends on: T10
  Executor notes: Surfaced all after_execute human actions clearly: provide real OpenAI credentials/project/org settings for staging gpt-image-2 and gpt-5.5; apply the Supabase migration to the target staging/production project when ready; manually smoke test staging with real Supabase/OpenAI/Discord credentials by generating an image, sending it to Discord, rendering an image: body reference, requesting a second opinion, and confirming proposed checklist items. Did not perform these human-only staging/deployment actions.
  Files changed:
    - .megaplan/plans/sprint-6-images-second-opinion/execution_batch_8.json

## Watch Items

- Use `gpt-image-2` for image generation and `gpt-5.5` for second opinions exactly as specified.
- Tests must inject fake OpenAI operations; automated tests must not perform live OpenAI or network calls.
- For result-dependent external effects, create the `external_requests` pending row before OpenAI or Blob work starts, then confirm or fail it after the effect completes.
- Keep `send_image` as a separate audited tool call; `generate_image` must only generate, upload, and create the `images` row.
- When reusing an image `reference_key`, deactivate only the prior active row for the same epic/reference key and make the new row the resolver target.
- `render_epic` must not mutate raw epic body markdown; resolution happens only in rendered output/tool result.
- Missing `image:` references should not crash rendering; they should produce a stable placeholder and be reported in `missing_image_references`.
- Second-opinion malformed structured output must fail deterministically and must not invent a score, verdict, holes, or row.
- `request_second_opinion` proposes checklist items only; checklist rows are created later through user-confirmed `edit_epic`.
- Confirmed checklist items carrying `source_second_opinion_id` must update `second_opinions.resulting_checklist_item_ids` in the same edit transaction.
- Score below 5 must be visible in the next response path as a reframing suggestion, not just persisted in storage.
- Auto-second-opinion at state gates is advisory/default-on, not a hard blocker; user decline language must suppress the advisory workflow.
- Hot context may include active image metadata and recent second-opinion summaries, but never image bytes.
- Do not worsen known storage recovery debt: for new generated-image storage effects, the ledger should contain enough request metadata to understand failures, while avoiding false claims of deterministic replay if bytes are not durable.
- Prefer existing store/tool/audit patterns and keep unrelated refactors out of scope.

## Sense Checks

- **SC1** (T1): Do both SQLite and Supabase migrations create the same `second_opinions` shape and indexes, and do store adapters expose the new second-opinion and active-image operations consistently?
  Executor note: SQLite and Supabase migrations define the same `second_opinions` table shape and score/requested_by constraints, with `(epic_id, requested_at DESC)` and score indexes. Store protocol and both adapters expose consistent second-opinion create/list/checklist-link methods plus active-image list/lookup/existence/deactivation helpers; targeted tests verify SQLite behavior, Supabase SQL/migration shape, and protocol exposure.

- **SC2** (T2): Can tests pass fake OpenAI operations through `run_turn`/`ToolContext` without importing or calling the real OpenAI client?
  Executor note: Fake OpenAI operations pass through run_turn into ToolContext without constructing the real OpenAI client; adapter tests use fake client objects only.

- **SC3** (T3): For each OpenAI and Blob effect, is an `external_requests` row pending before the effect and confirmed or failed afterward, including failure paths?
  Executor note: Synchronous helper tests verify pending-before-effect visibility, idempotency key passing, confirmed and failed settlement paths, rollback settlement survival, and unchanged external_queue behavior.

- **SC4** (T4): Does `generate_image` create exactly one active `agent_generated` image row with prompt, quality, size, description, reference key, storage URL, and external request IDs while leaving Discord posting to `send_image`?
  Executor note: generate_image creates one active agent_generated row with prompt, quality, size, description, reference key, storage URL, and OpenAI/storage external request IDs; regeneration deactivates prior active same-key rows; Discord posting remains only in send_image.

- **SC5** (T5): Does `render_epic` resolve active `image:` references for both uploaded and generated images without changing the persisted epic body and with clear reporting for missing keys?
  Executor note: render_epic resolves active user_uploaded and agent_generated image references, leaves persisted body unchanged, and reports missing/inactive keys with stable placeholders.

- **SC6** (T6): Does `request_second_opinion` persist raw and parsed GPT-5.5 output on valid responses, reject malformed output without creating invented rows, and return proposed checklist items only?
  Executor note: request_second_opinion persists raw and parsed GPT-5.5 output on valid responses, rejects malformed score/verdict/holes before creating a second_opinions row, and returns proposed checklist item objects without writing checklist rows.

- **SC7** (T7): When confirmed checklist items include `source_second_opinion_id`, are created item IDs returned to the caller and linked back to `second_opinions.resulting_checklist_item_ids` atomically?
  Executor note: Confirmed checklist additions with source_second_opinion_id return created_checklist_items and created_checklist_item_ids to the caller, merge the new IDs into the originating second_opinions.resulting_checklist_item_ids inside the same edit transaction, and roll back the checklist insert when the source second-opinion id is invalid.

- **SC8** (T8): Do tested bot response paths include a reframing suggestion after a just-requested score below 5, and can the user decline state-gate second-opinion advice?
  Executor note: Yes. Tests cover reframing injection after just-requested scores below 5 on final-text and explicit send_message paths, and cover default-on state-gate second-opinion advice plus user decline via 'skip second opinion until I ask'.

- **SC9** (T9): Do the tests cover all acceptance criteria, including separate `generate_image` and `send_image` audit rows, regeneration, body reference resolution, second-opinion scoring, and checklist proposal/linking?
  Executor note: Yes. Tests now cover the Sprint 6 acceptance paths: generated-image quality/override/reference-key uniqueness/regeneration, render-time image: resolution, separate generate_image and send_image audit rows with mocked external ledgers, second-opinion parsing and malformed rejection, score-driven low-score response coverage from prior T8 tests, score 6 with three holes producing three proposed checklist items, and confirmed checklist item linking back to second_opinions.

- **SC10** (T10): Do targeted tests, full `pytest`, and the deleted throwaway reproduction script all pass after fixes, with no live OpenAI calls in the automated suite?
  Executor note: Targeted tests pass; the throwaway reproduction script passed and was deleted; automated OpenAI paths use injected fakes. Full pytest was rerun and fails only on the already-known pre-existing `.megaplan` deleted-file FileNotFoundError in `tests/test_no_leaked_secrets.py`, with 185 passed and 2 skipped.

- **SC11** (T11): Were all after_execute user_actions clearly surfaced to the user without the executor performing them?
  Executor note: Yes. U1, U2, and U3 were explicitly communicated as human-only after_execute actions, and none were performed by the executor.

## Meta

Execute in dependency order: persistence first, then injection and ledger, then tools, then response/gate behavior, then tests. The two highest-risk mechanics are the synchronous `external_requests` rows for effects whose outputs are needed inside the tool body, and the checklist confirmation path back to `second_opinions.resulting_checklist_item_ids`; keep both visible in code review. Use existing adapter conventions for JSON arrays and Blob URLs instead of inventing new storage semantics unless the current code forces it. Keep network-facing code behind injection and prove the default test path is fake-only.
