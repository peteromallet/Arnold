# Execution Checklist

- [x] **T1:** Create the sibling shared package at `/Users/peteromalley/Documents/resident_chat_runtime` with Python `>=3.11` metadata and narrow infrastructure modules only: env diagnostics, async burst coalescing, Discord REST helpers, Discord gateway loop, discord.py channel adapter helpers including send/edit/file upload/typing/fetch, guarded async bridge, cached provider health checks, and startup diagnostics. Add focused package tests for those shared primitives using fakes and no Arnold or Veas domain imports.
  Executor notes: Shared package remains Python >=3.11 and infrastructure-only. Added direct coverage for the new shared `AsyncBurstCoalescer.snapshot()` and `CachedHealthCheck.clear()/has_cached_result()` helpers used by Veas compatibility wrappers. Shared tests now pass with 17 tests, and compileall passes.
  Files changed:
    - /Users/peteromalley/Documents/resident_chat_runtime/src/resident_chat_runtime/coalescing.py
    - /Users/peteromalley/Documents/resident_chat_runtime/src/resident_chat_runtime/health.py
    - /Users/peteromalley/Documents/resident_chat_runtime/tests/test_coalescing.py
    - /Users/peteromalley/Documents/resident_chat_runtime/tests/test_health.py

- [x] **T2:** Integrate the shared package into Arnold minimally. Refactor `agent_kit/transport/discord.py`, `agent_kit/resident.py`, and `arnold/cli.py` to reuse shared helpers while preserving Arnold domain behavior: real epic creation before inbound text/image/voice message insert, file upload sends, status edits, guarded sync-over-async failure from the Discord event loop, worker-thread resident turn execution when Discord owns the loop, and quiet Discord DM in-progress status behavior using typing instead of visible `Planning turn in progress.` messages. Update focused Arnold tests only where needed to lock these behaviors.
  Depends on: T1
  Executor notes: Arnold integration was revalidated. Focused Arnold tests passed: Discord transport, resident runner, coalescer, status lifecycle, and communication resident behavior. Full Arnold suite was rerun; the only failure remains the unrelated dirty `.megaplan` FileNotFoundError in `test_no_leaked_secrets`.
  Files changed:
    - /Users/peteromalley/Documents/arnold-v2/agent_kit/transport/discord.py
    - /Users/peteromalley/Documents/arnold-v2/agent_kit/resident.py
    - /Users/peteromalley/Documents/arnold-v2/arnold/cli.py
    - /Users/peteromalley/Documents/arnold-v2/tests/test_discord_transport.py
    - /Users/peteromalley/Documents/arnold-v2/tests/test_resident.py
    - /Users/peteromalley/Documents/arnold-v2/tests/test_image_attachment_pipeline.py
    - /Users/peteromalley/Documents/arnold-v2/tests/test_voice_pipeline.py

- [x] **T3:** Integrate the shared package into Veas only where it reduces duplicated infrastructure. Refactor `app/services/discord.py` to use shared REST and gateway helpers while keeping Veas policy, partner mapping, whitelist behavior, DB writes, catch-up ingestion, edit/delete/reaction handlers, and delayed typing behavior unchanged. Wrap shared coalescing inside `app/services/debouncer.py` while preserving the existing public API and per-user concurrency semantics. Reuse shared cached provider health and startup diagnostics in `app/routers/health.py` and `app/main.py` without replacing Veas Pydantic settings or changing startup order. Update focused Veas tests only where needed to preserve behavior.
  Depends on: T1
  Executor notes: Veas is no longer skipped. `app/services/discord.py` now uses shared Discord REST request shaping and shared gateway dispatch while keeping Veas partner whitelist, DB writes, reaction/edit/delete handlers, catch-up ingestion, and delayed typing local. `BurstCoalescer` delegates timing to shared coalescing while preserving `add`, `add_burst`, `snapshot`, and `_bursts.clear()` compatibility caught by the full suite. Health caching and startup diagnostics use shared helpers without changing Pydantic settings or startup order. Veas focused and full suites pass.
  Files changed:
    - /Users/peteromalley/Documents/Veas/app/main.py
    - /Users/peteromalley/Documents/Veas/app/routers/health.py
    - /Users/peteromalley/Documents/Veas/app/services/debouncer.py
    - /Users/peteromalley/Documents/Veas/app/services/discord.py

- [x] **T4:** Wire the local path dependency in both repos. Add `resident-chat-runtime @ file:///Users/peteromalley/Documents/resident_chat_runtime` or an equivalent local path dependency to Arnold and Veas dependency metadata, preserving Arnold's Python `>=3.12` compatibility and Veas's Python `>=3.11` compatibility. Update lockfiles only if required by the repo workflow and only after imports are stable.
  Depends on: T1, T2, T3
  Executor notes: Veas now declares `resident-chat-runtime @ file:///Users/peteromalley/Documents/resident_chat_runtime` while preserving Python >=3.11, and `uv.lock` contains the matching `directory = "../resident_chat_runtime"` entries. Arnold already declares the same local path dependency while preserving Python >=3.12. Both repo venvs show installed `direct_url.json` pointing at the sibling package; source validation used `PYTHONPATH` to avoid stale non-editable installs.
  Files changed:
    - /Users/peteromalley/Documents/arnold-v2/pyproject.toml
    - /Users/peteromalley/Documents/Veas/pyproject.toml
    - /Users/peteromalley/Documents/Veas/uv.lock

- [x] **T5:** Run validation and produce the execution closeout. Run shared package tests, focused Arnold tests (`python -m pytest tests/test_discord_transport.py tests/test_resident.py tests/test_coalescer.py tests/test_status_lifecycle.py tests/test_communication_resident.py`), focused Veas tests (`python -m pytest tests/test_discord.py tests/test_debouncer.py tests/test_health.py tests/test_config.py`), then broader import smoke checks if focused tests pass. Also write a short throwaway script or scripts outside tracked test files to exercise the key runtime bug fixes, run them, and delete them. If any test fails, inspect the error, fix the code, and rerun until passing or report the concrete blocker. Final closeout must include plan name `shared-resident-chat-runtime`, files changed, tests run, and blockers if any.
  Depends on: T1, T2, T3, T4
  Executor notes: Final validation was rerun after rework. Shared tests passed, Arnold focused tests passed, Veas focused tests passed, Veas full suite passed with 222 passed and 3 skipped, and the throwaway smoke script exercised the same-loop guard plus Veas shared coalescer/gateway dispatch and was deleted. Arnold full suite was rerun and still has only the unrelated `.megaplan` missing-file failure noted above.

## Watch Items

- Do not invoke the `megaplan` CLI, read or activate the `megaplan` skill, start nested plans, or edit `.megaplan/` artifacts; repository mentions of megaplan are implementation context only.
- Both Arnold and Veas worktrees are dirty. Inspect relevant diffs before edits and preserve unrelated user changes; never revert or broad-format unrelated files.
- The shared package must stay infrastructure-only. Do not move Arnold prompts, tools, schemas, resident domain loop, store models, ledger logic, persistence, Groq transcription, attachment persistence, or Veas mediation/policy/database logic into it.
- The shared package must support Python 3.11. Avoid Python 3.12-only syntax and APIs even though Arnold itself requires Python 3.12.
- Arnold Discord helpers must preserve channel send, send with files, edit status message, typing, channel resolution, and recent message fetch behavior. File upload and status edit regressions are high-risk.
- Arnold inbound Discord text, image, and voice paths must create or reuse a real epic before inserting inbound messages.
- Arnold must not call sync Discord transport methods from the Discord event loop. Same-loop sync-over-async misuse should fail loudly, and resident turn execution should remain isolated with worker-thread execution when needed.
- Arnold Discord DM resident mode should suppress visible in-progress `Planning turn in progress.` messages and use typing for in-progress feedback; do not accidentally remove invocation-mode status behavior.
- Veas must remain REST/gateway based and must keep existing behavior for outbound sends, typing, reactions, gateway ingestion, catch-up ingestion, message edit/delete handling, partner whitelist mapping, and delayed typing before processing accepted partner DMs.
- Coalescing behavior must remain equivalent in both repos: rapid messages group, hard-cap timing flushes, existing Arnold `MessageCoalescer` and Veas `BurstCoalescer` public APIs continue to work.
- Startup diagnostics and health checks must not log secrets or expose raw tokens. Use safe configured/missing status only.
- Use local path dependency wiring that works from both `/Users/peteromalley/Documents/arnold-v2` and `/Users/peteromalley/Documents/Veas`; update lockfiles only if the local workflow requires it and succeeds.
- Focused tests should run before broad suites so failures localize quickly. Do not mask focused failures with unrelated broad-suite noise.
- Existing debt around Discord attachment storage reconciliation is out of scope; do not make it worse or promise deterministic recovery for crash-before-upload without durable payload source material.

## Sense Checks

- **SC1** (T1): Does the new shared package declare Python `>=3.11`, contain only generic resident-chat infrastructure primitives, and have focused tests proving env parsing, coalescing timing, async bridge guard behavior, Discord REST/header shaping, discord.py channel adapter send/edit/file behavior, gateway callback plumbing, health caching, and safe diagnostics?
  Executor note: Confirmed after rework: shared package still declares Python >=3.11, remains generic infrastructure only, and shared tests cover env/diagnostics, coalescing including snapshot, async bridge guard, Discord REST/channel/gateway helpers, and health caching including clear/cache-state behavior.

- **SC2** (T2): After Arnold integration, do tests and code inspection prove inbound text/image/voice still ensure a real epic before message insert, file uploads and status edits still reach Discord, same-loop sync Discord misuse fails loudly, resident turn execution stays off the Discord event loop, and Discord DM mode avoids visible in-progress status messages?
  Executor note: Arnold focused tests passed after rework, preserving real-epic inbound paths, Discord file/status/typing behavior, same-loop sync guard behavior, worker-thread turn isolation, and quiet DM typing behavior.

- **SC3** (T3): After Veas integration, are policy/database/partner mapping behaviors still local to Veas, REST/gateway behavior equivalent, delayed typing preserved, the debouncer API unchanged, and health/startup changes limited to generic helper reuse?
  Executor note: Confirmed by code boundaries and Veas tests: policy, partner mapping, DB writes, delayed typing, reaction/edit/delete handlers, and catch-up ingestion remain in Veas; shared code is used only for REST/gateway plumbing, coalescing timing, health caching, and safe diagnostics.

- **SC4** (T4): Can both Arnold and Veas import `resident_chat_runtime` through the local path dependency without violating Veas's Python 3.11 floor or Arnold's Python 3.12 metadata?
  Executor note: Both repos now declare the local path dependency without changing Python floors. Veas `uv.lock` contains the local directory dependency, and both venv direct-url metadata points at `/Users/peteromalley/Documents/resident_chat_runtime`; source validation used `PYTHONPATH` because current installs are non-editable.

- **SC5** (T5): Did the executor run the shared, Arnold focused, and Veas focused test commands plus applicable smoke checks, fix and rerun any failures, delete throwaway reproduction scripts, and report plan name, files changed, tests run, and blockers?
  Executor note: Ran shared tests, Arnold focused tests, Veas focused tests, Veas full suite, Arnold full suite, import/path smokes, and a throwaway smoke script. The script passed and was deleted. Remaining blocker is only Arnold's unrelated dirty `.megaplan` FileNotFoundError in the broad suite.

## Meta

Execution should proceed in the approved order: build the shared package first, integrate Arnold next because it carries the live correctness fixes, integrate Veas only where wrappers stay thin, then wire dependency metadata and validate. Treat the sibling package location `/Users/peteromalley/Documents/resident_chat_runtime` as the working default unless a real filesystem command fails. Keep the extraction boundary strict: shared code should be boring plumbing, while repo-specific persistence, policies, prompts, schemas, and product wording stay in their repos. Before editing each target file, inspect nearby existing changes so user-owned dirty work is preserved. Prefer small compatibility wrappers over broad rewrites, especially for `MessageCoalescer` and `BurstCoalescer`. The final closeout should be operational, not speculative: exact files changed, exact commands run, pass/fail status, and concrete blockers only.
