# Execution Checklist

- [x] **T1:** Patch `planning-bot-spec.md` for public API, event stream, image/tool surfacing, attachment, idempotency, and transcription parity: use `from arnold import run_turn, Envelope`; state CLI progress NDJSON goes to stderr and final envelope to stdout; make `generate_image` create/store/return metadata only and `send_image` surface images; update system idempotency to `sha256(turn_id:system:provider:endpoint:system_seq)[:16]`; document CLI/Python image attachments only, invocation audio deferred, HTTP future; describe voice transcription as automatic resident ingestion or deferred, not a bot-callable `transcribe_voice` tool.
  Executor notes: Patched planning-bot-spec.md to use `from arnold import run_turn, Envelope`; made invocation progress events consistently stderr with final envelope on stdout; clarified `generate_image` only creates/stores/returns metadata while `send_image` surfaces images; updated system external-request idempotency to include `system_seq`; changed invocation attachments to current CLI/Python image-only support with audio and HTTP multipart deferred; changed voice transcription wording to automatic resident ingestion and removed the bot-callable `transcribe_voice(audio_url)` tool signature. Verified with rg checks for stale import/stdout/generate_image/transcribe_voice/idempotency wording and inspected the scoped diff. Full-suite verification was run as requested and failed during collection in resident/Discord test modules; a whole-module diagnostic run showed `ModuleNotFoundError: No module named 'resident_chat_runtime.coalescing'` while importing `agent_kit.resident`, unrelated to this spec-only patch.
  Files changed:
    - planning-bot-spec.md

- [x] **T2:** Add only thin read aliases in `agent_kit/tools/editorial_reads.py`: `get_checklist(epic_id, status?)` backed by `context.store.list_checklist_items`; `get_sprints(epic_id)` backed by `context.store.list_sprints_with_items`; `recent_messages(epic_id, n=10)` backed by `context.store.load_hot_context(epic_id)["recent_messages"]`, trimmed to `n` and with any hot-context cap clearly reflected in the spec if larger `n` cannot be honored. Register all as `operation_kind="read"` with strict local JSON schemas and payload keys `checklist`, `sprints`, and `recent_messages`. Do not add `transcribe_voice`; do not refactor Store or ports.
  Depends on: T1
  Executor notes: Added thin read aliases in `agent_kit/tools/editorial_reads.py`: `get_checklist(epic_id, status?)` delegates to `context.store.list_checklist_items`; `get_sprints(epic_id)` delegates to `context.store.list_sprints_with_items`; `recent_messages(epic_id, n=10)` delegates to `context.store.load_hot_context(epic_id)["recent_messages"]` and caps returned rows at 10. All three are registered as `operation_kind="read"` with strict local schemas and payload keys `checklist`, `sprints`, and `recent_messages`. Updated `planning-bot-spec.md` to document the cap. Verified compile, alias registration/payload smoke, focused tests, JSON checkpoint validity, and scoped diff/status. Full suite still fails during collection on the pre-existing resident runtime import blocker.
  Files changed:
    - agent_kit/tools/editorial_reads.py
    - planning-bot-spec.md

- [x] **T3:** Extend existing focused tests, without creating new test files, to cover the new read aliases and public API exports. Add alias assertions near existing editorial read/sprint tests so `get_checklist`, `get_sprints`, and `recent_messages` are registered read tools and return expected payloads from existing SQLite-backed fixtures. Extend an existing public API or import compatibility test to assert `arnold.run_turn` and `arnold.Envelope` are exported.
  Depends on: T2
  Executor notes: Extended existing tests only. Added `test_arnold_exports_public_api` to `tests/test_megaplan_arnold_import.py` asserting `arnold.run_turn`, `arnold.arun_turn`, and `arnold.Envelope` match the agent_kit public API. Added `test_editorial_read_aliases_return_expected_payloads` to `tests/test_editorial_loop.py` covering `get_checklist` and `recent_messages` registration/payloads against a SQLite-backed fixture, including the hot-context cap. Added `get_sprints` registration/payload assertions in `tests/test_sprints.py` near existing sprint read-path coverage. Focused whole-file command passed: 19 passed. Full suite still fails during collection on the pre-existing resident runtime import blocker.
  Files changed:
    - tests/test_editorial_loop.py
    - tests/test_sprints.py
    - tests/test_megaplan_arnold_import.py

- [x] **T4:** Run narrow validation and fix failures until clean. First run `rg -n "from megaplan\.arnold|stdout \(NDJSON\)|emitted live on stdout|generate_image.*creates AND sends|image/audio|transcribe_voice" planning-bot-spec.md` and confirm stale matches are gone or intentionally retained only as compatibility/deferred wording. Then run focused tests: `python -m pytest tests/test_megaplan_arnold_import.py tests/test_editorial_loop.py tests/test_sprints.py tests/test_cli.py tests/test_ledger.py tests/test_image_tools.py`. Also write a short throwaway script outside the repo test tree to exercise alias registration and payload shape, run it, then delete it. Inspect `git diff -- planning-bot-spec.md agent_kit/tools/editorial_reads.py tests/test_megaplan_arnold_import.py tests/test_editorial_loop.py tests/test_sprints.py` to ensure scope stayed limited and unrelated dirty changes were preserved.
  Depends on: T3
  Executor notes: Stale-phrase rg returned only intentional matches: negative wording that `transcribe_voice` is not bot-callable and deferred HTTP multipart image/audio wording. Focused pytest command passed: 41 passed. Temporary alias reproduction script outside the test tree ran successfully (`alias repro ok`) and was deleted. Scoped diff/status inspection showed the approved files in scope; `tests/test_sprints.py` remains untracked, so normal git diff omits it. Full suite was re-run and remains blocked by the pre-existing resident runtime collection error.

## Watch Items

- Preserve unrelated dirty worktree changes; do not run destructive git commands or broad cleanup.
- Do not invoke the megaplan CLI, read the megaplan skill, or start nested planning harnesses.
- Do not touch Store/ports, HTTP/FastAPI/asyncpg, transport surfaces, or compatibility shim tests except for narrow public API export assertions.
- FLAG-001: `recent_messages(epic_id, n)` cannot exceed the fixed hot-context recent-message window if backed only by `load_hot_context`; either cap/document that behavior or keep implementation honest without Store/ports refactor.
- Keep `megaplan.arnold` as compatibility context only; public spec import path should be `arnold`.
- `generate_image` must not be documented as surfacing/posting; `send_image` is the surfacing step.
- Invocation attachments currently mean image attachments for CLI/Python only; invocation audio and HTTP multipart remain deferred/future.
- `transcribe_voice` should not become a bot-callable tool in this pass.
- Tests should be local-only and avoid Supabase, Discord, Groq, OpenAI, and network dependencies.

## Sense Checks

- **SC1** (T1): Does the spec now consistently match implemented behavior for `arnold` imports, stderr/stdout event streams, image surfacing, image-only invocation attachments, deferred audio/HTTP, `system_seq` idempotency, and non-tool voice transcription?
  Executor note: Yes. The spec now matches the current implemented parity points for `arnold` imports, stderr progress events/stdout final envelope, `generate_image` versus `send_image`, CLI/Python image-only invocation attachments, deferred invocation audio/HTTP multipart, `system_seq` idempotency, and automatic resident voice transcription rather than a bot-callable transcription tool.

- **SC2** (T2): Are the added aliases strict read-only wrappers over existing Store/hot-context behavior, with no Store/ports refactor and with `recent_messages` behavior honestly constrained by the hot-context cap?
  Executor note: Yes. The aliases are strict read-only wrappers over existing Store/hot-context behavior, with no Store/ports refactor and no `transcribe_voice` tool. `recent_messages` is honestly capped to the existing hot-context window of 10 in code and spec wording.

- **SC3** (T3): Do existing test files now verify alias registration/payloads and `arnold.run_turn`/`arnold.Envelope` exports without adding new test files or network dependencies?
  Executor note: Yes. Existing test files now verify alias registration/payloads for `get_checklist`, `get_sprints`, and `recent_messages`, and verify `arnold.run_turn`/`arnold.Envelope` public exports without adding new test files or network dependencies.

- **SC4** (T4): Do the rg checks, focused pytest command, throwaway reproduction script, and final diff inspection all pass while keeping the changed-file scope limited to the approved files?
  Executor note: Yes for the requested narrow validation: rg had only intentional negative/deferred matches, focused pytest passed with 41 tests, the throwaway alias script passed and was deleted, and scoped diff/status stayed limited to approved files. The full suite remains blocked by the pre-existing resident runtime collection error.

## Meta

Execute this as a narrow parity cleanup, not a platform expansion. The only code change should be lightweight read alias registration if it stays as a thin wrapper over existing behavior. Treat the `recent_messages` critique as the main judgment call: do not imply arbitrary `n` support if the only allowed backing data is hot-context `LIMIT 10`; cap it or document the cap. Keep spec language precise about current support versus deferred surfaces, especially audio and HTTP.
