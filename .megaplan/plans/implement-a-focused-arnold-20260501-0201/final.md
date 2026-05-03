# Execution Checklist

- [x] **T1:** Update project baseline metadata and image source contracts: require Python >=3.12 in pyproject.toml, preserve the canonical test extra, optionally add a non-breaking test-extra alias, add caller_uploaded to SQLite/Supabase image source constraints and image tool validation/list_images schema while preserving existing user_uploaded behavior.
  Executor notes: Updated pyproject metadata to require Python >=3.12 while preserving canonical `test` optional dependency. Added `caller_uploaded` as an accepted image source in SQLite and Supabase image-table constraints, `list_images` tool schema validation, and store reference-key generation with distinct `img_caller_upload` prefix while keeping `user_uploaded` behavior unchanged. Added focused regressions for `caller_uploaded` creation/filtering and image-tool schema path. Verification: `python -m pytest tests/test_sqlite_store_v1b.py tests/test_image_tools.py -q` passed (13 passed). Full suite `python -m pytest -q` ran: 195 passed, 2 skipped, 1 unrelated dirty-worktree failure in `tests/test_no_leaked_secrets.py`. Local interpreter is Python 3.11.11, below the new metadata baseline.
  Files changed:
    - pyproject.toml
    - agent_kit/store/migrations/sqlite/002_images.sql
    - supabase/migrations/202604300002_002_images.sql
    - agent_kit/tools/images.py
    - agent_kit/store/sqlite.py
    - agent_kit/store/supabase.py
    - tests/test_sqlite_store_v1b.py
    - tests/store_contract_v1b.py
    - tests/test_image_tools.py

- [x] **T2:** Implement a small LocalBlobStore using the existing Blob protocol, export it from agent_kit.blob, and wire CLI blob selection so SQLite CLI runs default to a deterministic local blob directory near the SQLite DB while Supabase mode continues to use SupabaseStorageBlob.from_env when attachments are present.
  Depends on: T1
  Executor notes: Implemented `LocalBlobStore` as a filesystem-backed Blob adapter using deterministic BlobRef-compatible keys, exported it from `agent_kit.blob`, and updated the Blob protocol to include the existing `idempotency_key` keyword used by storage callers. Wired CLI blob selection so SQLite turn invocations pass a `LocalBlobStore` rooted at `<sqlite-db>.blobs`, while Supabase turn invocations only construct `SupabaseStorageBlob.from_env()` when `attachments_present` is requested for the future attachment path. Verification: `python -m pytest tests/test_supabase_adapters.py tests/test_cli.py -q` passed (13 passed). Full suite `python -m pytest -q` ran: 197 passed, 2 skipped, 1 unrelated pre-existing dirty-worktree failure in `tests/test_no_leaked_secrets.py`. Local interpreter is Python 3.11.11, below the metadata baseline.
  Files changed:
    - agent_kit/blob/local.py
    - agent_kit/blob/__init__.py
    - agent_kit/ports.py
    - arnold/cli.py
    - tests/test_supabase_adapters.py

- [x] **T3:** Add reusable invocation image attachment normalization for Path, raw bytes, and (bytes, mime_type). Support PNG, JPEG, and WEBP up to 25MB; infer/sniff MIME types via filename and magic bytes; reject unknown raw bytes, unsupported media, audio, and detectable MIME mismatches with explicit unsupported media type errors.
  Depends on: T1, T2
  Executor notes: Added reusable invocation image attachment normalization in `agent_kit.attachments` for Path/str, raw bytes, and `(bytes, mime_type)`. It accepts PNG/JPEG/WEBP up to 25MB using filename inference plus magic-byte sniffing, rejects unsupported declared media including audio, rejects unknown raw bytes, and rejects detectable declared/sniffed MIME mismatches with `UnsupportedMediaTypeError`. Verification: `python -m pytest tests/test_image_tools.py tests/test_discord_transport.py tests/test_sprint6_images_second_opinion.py -q` passed (20 passed). Full suite was also run and still only failed at the pre-existing dirty-worktree leaked-secrets FileNotFoundError.
  Files changed:
    - agent_kit/attachments.py
    - tests/test_image_tools.py

- [x] **T4:** Wire Python invocation attachments into run_turn/arun_turn and actual public exports. Require blob when attachments are supplied; if attachments are provided without epic_id, return an errored Envelope with error.code attachments_require_epic and create no orphan image/blob state. For valid attachments, create the inbound invocation message first, store blobs, create caller_uploaded image rows, mark the message has_image_attachment, and make uploaded images discoverable through existing image tools before model execution.
  Depends on: T3
  Executor notes: Added `attachments=` support to `run_turn`/`arun_turn` via `run_turn` kwargs using the existing image attachment normalizer. Attachment calls without `epic_id` return an errored Envelope with `error.code == "attachments_require_epic"` before creating messages, turns, images, or blob writes; calls without `blob` return `attachments_require_blob`; calls with pre-existing triggered message IDs return `attachments_require_invocation` to avoid silently ignoring supplied files. Valid direct invocation attachments create the inbound message first, store blobs, create `caller_uploaded` image rows, mark the inbound message `has_image_attachment`, and populate hot context before model execution. Verification: targeted affected modules passed; full suite rerun still has only the known dirty-worktree leaked-secrets FileNotFoundError.
  Files changed:
    - agent_kit/loop.py
    - tests/test_run_turn.py

- [x] **T5:** Wire CLI attachment support end to end: add repeatable arnold turn --attach <path>, normalize paths, select the correct blob adapter, pass attachments/blob into run_turn, preserve --stream-events behavior, and make --attach without --epic surface the attachments_require_epic envelope error rather than creating state.
  Depends on: T4
  Executor notes: Added repeatable `arnold turn --attach PATH`, normalizing CLI paths with `expanduser().resolve()`, selecting the existing CLI blob adapter with `attachments_present=bool(attachments)`, and passing attachments/blob into `run_turn` without changing `--stream-events` event forwarding. Added CLI regressions proving SQLite `--attach` with an explicit epic creates a `caller_uploaded` image row, marks the inbound message image-attached, and writes the local blob; `--attach` without `--epic` returns an errored envelope with `error.code == "attachments_require_epic"` and creates no messages, images, turns, or blob directory. Verification: targeted affected suites passed; full suite rerun still has only the known dirty-worktree leaked-secrets FileNotFoundError.
  Files changed:
    - arnold/cli.py
    - tests/test_cli.py

- [x] **T6:** Fix resident send_image to post real Discord files. In resident mode require context.blob, construct BlobRef from the image row, fetch bytes through Blob.get, pass concrete in-memory file payloads to PushTransport.post_message, convert them to discord.File in DiscordTransport, update outbound message discord_message_id after confirmation, and persist only JSON-safe metadata in external_requests.request_body/request_summary.
  Depends on: T2
  Executor notes: Resident `send_image` now requires `context.blob`, constructs a `BlobRef` from the image row, fetches bytes via `Blob.get`, passes in-memory `FileUpload` payloads to `PushTransport.post_message`, and keeps persisted Discord external request bodies byte-free by storing only file metadata. `DiscordTransport.post_message` now converts `FileUpload` payloads to `discord.File`, and the outbound message row is updated with the confirmed Discord message id. Verification: `python -m pytest tests/test_image_tools.py tests/test_discord_transport.py tests/test_sprint6_images_second_opinion.py -q` passed (20 passed). Full suite was also run and still only failed at the pre-existing dirty-worktree leaked-secrets FileNotFoundError.
  Files changed:
    - agent_kit/ports.py
    - agent_kit/tools/images.py
    - agent_kit/transport/discord.py
    - tests/test_image_tools.py
    - tests/test_discord_transport.py
    - tests/test_sprint6_images_second_opinion.py

- [x] **T7:** Add first-class invocation attached_image event semantics while preserving audited tool_call events. Update envelope dataclasses/types/schema, any tool-kit event kind aliases, and event streaming helpers so invocation-mode send_image emits both the normal tool_call audit event and an attached_image event with image_id, caption, storage_url, reference_key, and media_type. Resident send_image must not emit attached_image.
  Depends on: T6
  Executor notes: Added first-class `attached_image` event semantics to envelope types/schema and the tool event plumbing. Invocation-mode `send_image` now preserves the normal audited `tool_call` event and then emits an `attached_image` event with `image_id`, `caption`, `storage_url`, `reference_key`, and `media_type`; event emission uses the same helper for streamed callbacks and final envelope storage. Resident `send_image` still emits only the audited `tool_call` event. Verification: targeted affected modules passed; full suite rerun still has only the known dirty-worktree leaked-secrets FileNotFoundError.
  Files changed:
    - agent_kit/envelope.py
    - agent_kit/envelope.schema.json
    - agent_kit/tool_kit.py
    - agent_kit/tools/images.py
    - tests/test_image_tools.py
    - tests/test_envelope.py

- [x] **T8:** Implement the set_typing tool and transport support. Register set_typing with an {on: boolean} schema; in invocation mode return an explicit no-op result while preserving normal tool_call auditing; in resident mode call a transport typing method when available and return {typing: on, mode: resident}.
  Depends on: T7
  Executor notes: Registered `set_typing` with schema `{on: boolean}` as a normal audited `tool_call`. Invocation mode returns `{"typing": on, "mode": "invocation", "noop": true}`. Resident mode calls `transport.set_typing(channel_id, on)` when available and returns `{"typing": on, "mode": "resident"}`. Extended `PushTransport` and `DiscordTransport` with `set_typing`; Discord sends a typing pulse for `on=true` and treats `on=false` as an explicit no-op. Added regressions for registration/schema, audit rows, invocation no-op, resident delegation, and protocol shape. Verification: targeted affected suites passed; full suite rerun still has only the known dirty-worktree leaked-secrets FileNotFoundError.
  Files changed:
    - agent_kit/ports.py
    - agent_kit/tools/communication.py
    - agent_kit/tools/__init__.py
    - agent_kit/transport/discord.py
    - tests/test_communication_resident.py
    - tests/test_ports_v1b.py

- [x] **T9:** Add focused regression coverage in existing test files for caller_uploaded filtering, LocalBlobStore, attachment normalization, Python and CLI attachment ingestion, epicless attachment rejection, resident send_image file bytes and JSON-safe ledger metadata, attached_image schema/stream parity, set_typing, whitelist rejection, status-message non-persistence, outbound message persistence, and status lifecycle semantics.
  Depends on: T5, T6, T7, T8
  Executor notes: Added focused regression coverage in existing test files for attached_image stream/final envelope schema parity, resident send_image file metadata JSON-safety and byte-free ledger persistence, declared/sniffed attachment MIME mismatch rejection, whitelist rejection no-state semantics, status-message non-persistence, outbound message Discord id persistence, and status lifecycle message history behavior. Existing prior-batch tests in the same touched modules already cover caller_uploaded filtering, LocalBlobStore, Python/CLI attachment ingestion, epicless attachment rejection, and set_typing. Verification: targeted affected module suite passed with 62 passed. Full suite was run and produced 208 passed, 2 skipped, 2 unrelated failures documented in deviations.
  Files changed:
    - tests/test_run_turn.py
    - tests/test_image_tools.py
    - tests/test_status_lifecycle.py
    - tests/test_whitelist.py

- [x] **T10:** Run validation and inspect scope. First run the targeted suite: python -m pytest tests/test_cli.py tests/test_run_turn.py tests/test_image_tools.py tests/test_discord_transport.py tests/test_communication_resident.py tests/test_envelope.py tests/test_status_lifecycle.py tests/test_whitelist.py -q. Then run python -m pytest -q. Also write a short throwaway script that exercises the specific attachment/send_image/event behavior changed here, run it, and delete it. If tests fail, read the error, fix the implementation, and rerun until passing or clearly document unrelated failures. Inspect the diff to confirm no FastAPI/asyncpg migration or unrelated dirty worktree changes were introduced.
  Depends on: T9
  Executor notes: Targeted suite passed: `python -m pytest tests/test_cli.py tests/test_run_turn.py tests/test_image_tools.py tests/test_discord_transport.py tests/test_communication_resident.py tests/test_envelope.py tests/test_status_lifecycle.py tests/test_whitelist.py -q` -> 51 passed. Full suite was run: `python -m pytest -q` -> 209 passed, 2 skipped, 1 unrelated failure in `tests/test_no_leaked_secrets.py::test_leaked_supabase_service_role_jwt_prefix_is_absent` caused by FileNotFoundError for the pre-existing deleted `.megaplan/plans/sprint-3-multi-epic/execution_batch_10.json`. Wrote and ran `tmp_t10_attachment_send_image_repro.py`, which exercised invocation image attachment ingestion, invocation `send_image` attached_image event streaming/final envelope parity, and resident `send_image` in-memory file payload plus JSON-safe ledger metadata; it passed and was deleted. Diff/scope inspection found no `FastAPI`, `fastapi`, or `asyncpg` references in `agent_kit`, `arnold`, `pyproject.toml`, `supabase`, or `tests`; no broader architecture migration was introduced. Local interpreter remains Python 3.11.11, below the project metadata baseline.
  Files changed:
    - .megaplan/plans/implement-a-focused-arnold-20260501-0201/execution_batch_7.json

## Watch Items

- Do not invoke the megaplan CLI, read the megaplan skill, or start a nested planning harness; treat megaplan mentions as repository context only.
- Preserve unrelated dirty worktree changes; inspect before editing touched files and never revert changes you did not make.
- Invocation attachment parity is image-only for this tranche; do not build full audio/Groq attachment flow unless it is already trivially supported by existing code.
- Keep optional dependency extra test canonical; any test-extra alias must be additive and non-breaking.
- Attachments require an explicit epic_id; epicless attachment calls must return attachments_require_epic and create no image/blob rows.
- Raw bytes must be identified by PNG/JPEG/WEBP magic bytes; do not guess MIME type for unknown bytes.
- For (bytes, mime_type), reject detectable byte/MIME mismatches instead of silently trusting metadata.
- caller_uploaded is invocation-specific; preserve user_uploaded behavior for Discord resident uploads.
- Resident send_image raw file bytes must remain in memory only; persisted external request request_body/request_summary must contain JSON-safe metadata without bytes.
- Resident send_image must construct BlobRef from image epic_id/storage_url/media type before Blob.get; do not pass storage_url directly to Blob.get.
- attached_image is for invocation-mode user-facing image output only; preserve tool_call audit events and rows.
- Streamed events from on_event/--stream-events must match final Envelope.events for attached_image.
- Whitelist rejection should not create messages rows; status content should not pollute message history.
- Do not implement the broader FastAPI/asyncpg migration in this tranche.
- If the local Python interpreter is below 3.12, report that environment limitation while keeping metadata correct.

## Sense Checks

- **SC1** (T1): Does project metadata require Python 3.12+, keep test as the canonical optional dependency, and accept caller_uploaded everywhere image source constraints/tool schemas require it without changing user_uploaded behavior?
  Executor note: Yes. Metadata now requires Python >=3.12; the canonical optional dependency remains `test`; `caller_uploaded` is accepted in SQLite/Supabase image source constraints and `list_images` validation, with `user_uploaded` behavior preserved and covered by tests.

- **SC2** (T2): Can SQLite CLI invocation store and retrieve image blobs through a small LocalBlobStore using BlobRef-compatible keys, while Supabase mode still uses the existing Supabase blob implementation?
  Executor note: Yes. SQLite CLI turns now receive a `LocalBlobStore` rooted next to the SQLite DB, and `LocalBlobStore` can put/get/exists BlobRef-compatible keys. Supabase blob construction remains `SupabaseStorageBlob.from_env()` for the future `attachments_present` path and is not forced for ordinary Supabase CLI turns without attachments.

- **SC3** (T3): Do attachment normalization paths correctly accept PNG/JPEG/WEBP Path, raw bytes, and (bytes, mime_type), and explicitly reject unknown bytes, audio, oversized files, and declared MIME mismatches?
  Executor note: Yes. Normalization accepts PNG/JPEG/WEBP Path/str, raw bytes, and `(bytes, mime_type)`, enforces the 25MB cap, sniffs magic bytes, and rejects unknown bytes, declared audio/unsupported media, and declared MIME mismatches with `UnsupportedMediaTypeError` coverage in `tests/test_image_tools.py`.

- **SC4** (T4): Do run_turn/arun_turn create caller_uploaded image rows before model execution for valid attachments and return attachments_require_epic with no orphan state when epic_id is missing?
  Executor note: Yes. Valid direct invocation attachments are normalized, require a blob adapter, create the inbound message first, store blobs, create `caller_uploaded` image rows, mark the inbound message with `has_image_attachment`, and are visible in model hot context before execution. Epicless attachment calls return `attachments_require_epic` before any message, turn, image, or blob state is created.

- **SC5** (T5): Does arnold turn --attach work end to end for SQLite with an explicit epic, and does --attach without --epic surface the expected envelope error?
  Executor note: Yes. `arnold turn --attach` works end to end for SQLite with an explicit epic, storing a local blob and `caller_uploaded` image row; without `--epic`, it returns the `attachments_require_epic` envelope error and creates no attachment/message/turn state.

- **SC6** (T6): Does resident send_image fetch file bytes via BlobRef/Blob.get, pass concrete upload payloads to Discord transport, update the outbound message after confirmation, and keep persisted ledger JSON byte-free?
  Executor note: Yes. Resident `send_image` requires a blob adapter, fetches bytes through `Blob.get(BlobRef(...))`, passes `FileUpload` objects to the push transport, converts those to `discord.File` in `DiscordTransport`, updates the outbound message id after confirmation, and stores only JSON-safe file metadata in `external_requests.request_body`.

- **SC7** (T7): Do invocation send_image calls produce both audited tool_call behavior and schema-valid attached_image events, with final envelope events matching streamed events?
  Executor note: Yes. Invocation `send_image` emits the audited `tool_call` event and a schema-valid `attached_image` event with the required image metadata, through the same event emission path used by `on_event` and final envelopes. Resident `send_image` emits no `attached_image` event.

- **SC8** (T8): Is set_typing registered and audited, no-op successful in invocation mode, and delegated to transport typing behavior in resident mode?
  Executor note: Yes. `set_typing` is registered with the boolean schema and audited through normal `tool_call` rows, returns an explicit invocation no-op result, and delegates to resident transport typing support when present.

- **SC9** (T9): Are the added regressions focused on acceptance criteria in existing test files, without broad snapshots or unrelated new coverage noise?
  Executor note: Yes. The added regressions are narrow assertions in existing test files and avoid broad snapshots or unrelated new coverage.

- **SC10** (T10): Do the targeted suite and full suite pass, or are any remaining failures clearly unrelated and documented, with the final diff scoped away from FastAPI/asyncpg migration and unrelated worktree changes?
  Executor note: Targeted suite passes; full suite has one documented unrelated dirty-worktree failure in `tests/test_no_leaked_secrets.py` from a deleted `.megaplan` file. The temporary repro script passed and was removed. Scope inspection found no FastAPI/asyncpg migration references in the touched source/test areas.

## Meta

Execute in the approved order: contracts first, then local blob, normalization, Python API, CLI, resident send_image, event plumbing, set_typing, regressions, and validation. Keep changes narrow and inspect existing patterns before adding abstractions. The highest-risk areas are event streaming parity, JSON-safe Discord external request persistence, and avoiding orphan attachment state when epic_id is missing. Tests should be added to existing test files named in the plan; the final validation task should run the existing suites plus a temporary local reproduction script that is deleted after use.
