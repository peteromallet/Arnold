# Megaplan Persistence and Storage Audit

## Overview

This audit maps Megaplan's persisted domain objects, execution artifacts, resident Discord state, cloud orchestration state, generated assets, and export/migration surfaces to the storage backends that are visible in the repository. The goal is to make storage ownership explicit enough that follow-up work can close durable-auditability gaps without relying on tribal knowledge of local `.megaplan` directories, Supabase tables, or blob side effects.

The current implementation is hybrid. Arnold/editorial entities are represented by Pydantic mirrors in `megaplan/schemas/arnold.py` and Supabase migrations under `supabase/migrations/20260430*.sql`. Megaplan plan-state, migration, lease, control, progress, and resident/cloud orchestration entities are represented by `megaplan/schemas/sprint1.py`, the canonical `Store` protocol in `megaplan/store/base.py`, DBStore migrations under `supabase/migrations/202605*.sql`, and file-backed implementations mapped in this audit. Export is a first-class persistence surface because `megaplan/store/export.py` collects row JSON, plan artifact payloads, blob metadata, blob payloads, manifest errors, and tar or gzip output for an epic.

This document is intentionally source-backed. It does not claim that any live Supabase project has a table, bucket, policy, or object unless that state is represented by checked-in schema, migrations, code, or configuration.

## Scope Boundaries

In scope:

- Canonical `Store` entities and inputs from `megaplan/store/base.py`.
- Arnold V2/editorial overlap from `megaplan/schemas/arnold.py` and migrations `202604300001` through `202604300009`.
- Sprint 1/Megaplan plan, execution, cloud, resident, migration, lease, control, and progress models from `megaplan/schemas/sprint1.py` and migrations `202605040000`, `202605050001`, `202605050003`, and `202605060001`.
- Export and backup coverage from `megaplan/store/export.py`, including row JSON, `plan_artifacts/<plan_id>/<name>` members, `blobs/<blob_id>/meta.json`, `blobs/<blob_id>/payload.bin`, `manifest.json`, warning/error entries, tar output, and gzip output.
- FileStore roots, active plan directories, legacy `.megaplan/<project>/plans/<plan-id>/` layouts, `PlanRepository` artifact files, DBStore blob behavior, resident Discord ingestion, cloud launch/check-in/logging flows, local markers, receipts, generated binary/image/audio assets, and Supabase Storage candidates.

Out of scope:

- Verifying live production database contents, live bucket policies, live object retention, Discord API state, provider log retention, or Railway/Docker/SSH workspaces beyond checked-in code paths.
- Changing storage behavior. This audit is documentation-only.
- Treating Arnold/editorial tables as active Megaplan runtime owners where the repository only proves schema overlap. Those tables are mapped as source-backed persistence surfaces; runtime ownership must be confirmed in later implementation tickets.

## Settled Decisions

- **SD-001** — Treat checked-in code and migrations as the only audit evidence for storage coverage. _load_bearing: true_
  Rationale: The audit must stay reproducible and must not imply unverified live Supabase, Discord, cloud-provider, or blob-bucket state.

- **SD-002** — Include export paths as persistence coverage, not as an optional operational detail. _load_bearing: true_
  Rationale: `megaplan/store/export.py` is the repository-backed mechanism that can collect row JSON, plan artifacts, image blob metadata, image blob payloads, manifest warnings/errors, and tar/gzip outputs for an epic.

- **SD-003** — Mark Arnold V2/editorial tables as overlap/context unless a Megaplan runtime source path proves current ownership. _load_bearing: true_
  Rationale: The schema and migrations are real persistence surfaces, but this audit should not overclaim runtime behavior from schema names alone.

- **SD-004** — Treat active plan-tree files as first-class storage until code routes those artifact bodies through `Store`. _load_bearing: true_
  Rationale: `megaplan/store/plan_repository.py` intentionally reads and writes the current on-disk plan tree directly, so DB plan rows and `plan_artifacts` metadata cannot be assumed to cover every artifact body.

- **SD-005** — Treat Supabase Storage as env-selected runtime infrastructure, not schema-provisioned storage. _load_bearing: true_
  Rationale: `DBStore` selects `SupabaseStorageBlobStore` from environment variables, but the checked-in migrations do not create a bucket, policies, or required bucket configuration.

- **SD-006** — Treat resident cloud-log tool output as transient unless it is written as a store artifact, cloud-run status row, or explicit log row. _load_bearing: true_
  Rationale: `megaplan/resident/profile.py` and `megaplan/resident/cloud.py` persist summarized cloud results into `cloud_runs`, `progress_events`, and messages, but the `cloud_logs` tool response itself is not a durable provider-log archive.

- **SD-007** — Treat cloud provider logs, remote tmux logs, and local cloud markers as operational surfaces until a Store or blob archival path copies them. _load_bearing: true_
  Rationale: `megaplan/cloud/cli.py` and provider wrappers can upload inputs, start remote sessions, read status, and display redacted logs, but those code paths do not continuously mirror provider logs, remote workspaces, or marker files into DB/blob storage.

## Source-Evidence Rules

Use these rules for every row in the coverage matrix and gap list:

- Prefer canonical contracts first: `megaplan/store/base.py` defines the entities and operations that Megaplan treats as storage-backed.
- Pair schema models with migrations: `megaplan/schemas/arnold.py` and `megaplan/schemas/sprint1.py` describe record shape, while `supabase/migrations/*.sql` proves DB table and column coverage.
- Distinguish durable row storage from durable bytes. A table row with `storage_url`, `blob_id`, or metadata is not evidence that image/audio/binary bytes are durably archived unless code or migrations show the byte backend.
- Distinguish DB-backed plan summaries from full plan-tree artifacts. `plans` columns can hold latest JSON snapshots, while `plan_artifacts` and local plan files carry artifact bodies that require separate coverage checks.
- Treat export as a recovery/audit artifact with its own path map. A tar member in `megaplan/store/export.py` is evidence of exportability, not proof that the exported content is continuously mirrored.
- Treat idempotency, leases, scheduled jobs, progress events, and control messages as auditable event/control surfaces only to the extent that their tables and store methods preserve status, actor, payload, timestamps, and result fields.

## Source Inventory

This inventory is the evidence map for the audit. The coverage matrix cites these source surfaces when assigning a current table, local path, blob backend, or gap.

| Domain | Entity / artifact / event | Canonical code source | Source-backed DB table or migration | Notes for coverage rows |
|---|---|---|---|---|
| Store contract | Storage protocol, idempotency key helper, transaction shape, optimistic conflict/lock/lease errors | `megaplan/store/base.py` | `db_idempotency_keys`, `epic_locks`, `execution_leases`, `migration_runs` from `202604300001_001_core.sql` and `202605040000_megaplan_dbstore_foundation.sql` | Establishes canonical operations and failure modes that FileStore/DBStore must satisfy. |
| Arnold/editorial core | `Epic` body/state/revision/home backend | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` epic/body methods | `epics` in `202604300001_001_core.sql`; `home_backend`, `migrated_to`, `revision` added by `202605040000_megaplan_dbstore_foundation.sql` | Body is a DB text column in schema; local file equivalents and DBStore routing are mapped below. |
| Conversation turns | `BotTurn` prompt snapshots, reasoning, status, state-at-turn, model version, output/status message refs | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` turn methods | `bot_turns` in `202604300001_001_core.sql` | Covers durable bot-turn metadata and prompt snapshots, not necessarily raw external model traces. |
| Messages | Inbound/outbound Discord/user/bot messages, attachment flags, voice/audio metadata, conversation linkage, idempotency keys | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` message methods | `messages` in `202604300001_001_core.sql`; FTS index in `202604300007_007_message_search.sql`; `conversation_id` and `idempotency_key` added by `202605060001_resident_orchestration.sql` | Audio/image attachment bytes require separate blob/backend evidence; row fields are metadata. |
| Tool calls | Tool name, operation kind, arguments, result, duration | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` tool-call methods | `tool_calls` in `202604300001_001_core.sql` | Base migration restricts operation kinds to `read`/`write`; Arnold schema also lists cloud/control kinds, so DB compatibility work must verify drift. |
| System logs | Level, category, event type, details, turn/epic refs | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` log methods | `system_logs` in `202604300001_001_core.sql` | Durable row log coverage exists for system/application/tool/LLM/external/recovery events that callers actually write. |
| External request ledger | Provider endpoint, request summary/body, status, provider response summary, attempts, errors | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` external request methods | `external_requests` in `202604300001_001_core.sql`; `request_body` added by `202604300003_003_external_requests_body.sql` | Covers request ledgers for supported providers, including `supabase_storage`; raw response/body completeness depends on caller payloads. |
| Images and blobs | Image metadata, active reference, Discord attachment ID, blob backend/id/hash/size/content type | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` image methods | `images` in `202604300002_002_images.sql`; blob metadata columns and indexes in `202605050002_sprint5_editorial_schema.sql` | Table proves metadata coverage; byte storage requires the Supabase Storage/local blob backend mapping below. |
| Checklist/editorial events | Checklist items and epic event snapshots/hashes | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` checklist/event methods | `checklist_items` and `epic_events` in `202604300004_004_editorial_core.sql`; snapshot/hash columns in `202605050002_sprint5_editorial_schema.sql` | Event rows can be audit evidence when callers populate pre/post state and hashes. |
| Feedback | User-confirmed feedback and agent observations, source message/turn refs, active/resolved lifecycle | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` feedback methods | `feedback` in `202604300005_005_feedback.sql` | Required table is source-backed and appears in the coverage matrix. |
| Sprints | Sprint metadata, queue/pending status, revision | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` sprint methods | `sprints` in `202604300006_006_sprints.sql`; `revision` added by `202605040000_megaplan_dbstore_foundation.sql` | Migration status enum is narrower than Sprint schema (`running`, `failed`, `blocked`, `cancelled` also appear in code), so compatibility is a review point. |
| Sprint items | Sprint item content, complexity, status, source section, position | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` sprint item methods | `sprint_items` in `202604300006_006_sprints.sql` | Required table is source-backed and appears in the coverage matrix. |
| Second opinions | Requested-by, focus areas, raw response, score, summary, verdict, resulting checklist item IDs, model used | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` second-opinion methods | `second_opinions` in `202604300008_008_second_opinions.sql` | Required table is source-backed and appears in the coverage matrix; raw response is stored as text. |
| Codebase research | Codebase owner/name/default branch/scope/group/epic refs/access timestamps | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` codebase methods | `codebases` in `202604300009_009_codebase_research.sql` | Required table is source-backed and appears in the coverage matrix. |
| Code artifacts | Excerpts, summaries, API cache content, file path, line range, scope, metadata, expiry | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` code artifact methods | `code_artifacts` in `202604300009_009_codebase_research.sql` | Required table is source-backed and appears in the coverage matrix; content is text, not binary. |
| Megaplan plans | Plan state, config, sessions, versions, history, latest finalize/review/execution/failure, resume cursor | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` plan methods | `plans` in `202605040000_megaplan_dbstore_foundation.sql`; `resume_cursor` added by `202605050001_add_plan_resume_cursor.sql` | DB plan row covers structured summaries; local `PlanRepository` files and artifact bodies need separate rows. |
| Plan artifacts | Artifact refs/stats and typed artifact bodies: markdown, JSON, JSONL, raw text, lock, derived, receipts, execution traces, reviews, finalize snapshots | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` artifact methods | `plan_artifacts` in `202605040000_megaplan_dbstore_foundation.sql`; `content_bytes` added by `202605050003_plan_artifact_binary_content.sql` | DB columns cover text and byte payloads, but actual writer coverage and filename/role typing are partial. |
| Execution leases | Plan-level lease holder, worker kind, phase, heartbeat, expiry | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` lease methods | `execution_leases` in `202605040000_megaplan_dbstore_foundation.sql` | Durable lease row is operational state, not a historical execution log by itself. |
| Migration runs | File/DB migration phase, manifest, copied IDs, blob-copy progress, holder/expiry | `megaplan/schemas/sprint1.py`; migration methods in store implementations | `migration_runs` in `202605040000_megaplan_dbstore_foundation.sql` | Used to audit migration progress; export coverage is separate. |
| Automation actors | CLI/cloud/CI/admin/resident actors and granted epic IDs | `megaplan/schemas/sprint1.py` | `automation_actors` in `202605040000_megaplan_dbstore_foundation.sql`; resident actor inserted by `202605060001_resident_orchestration.sql` | Resident migration inserts `actor_kind='resident'`; schema enum listed in `sprint1.py` should be checked for drift. |
| Control messages | Actor intent, target, payload, idempotency, claim/process/result fields | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` control-message methods | `control_messages` in `202605040000_megaplan_dbstore_foundation.sql`; stale claim indexes in `202605060001_resident_orchestration.sql` | Covers durable command/control queue rows. |
| Progress events | Plan/sprint/epic progress kind, summary, details, idempotency, occurrence time | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` progress-event methods | `progress_events` in `202605040000_megaplan_dbstore_foundation.sql` | Covers structured progress events; raw logs/artifacts remain separate. |
| Resident conversations | Discord transport conversation key, guild/channel/thread/DM IDs, active epic, delivery cursor, metadata, message refs | `megaplan/schemas/arnold.py`; `megaplan/store/base.py` resident conversation methods | `resident_conversations` in `202605060001_resident_orchestration.sql` | Primary durable row for resident Discord ingestion and outbound cursor state. |
| Cloud runs | Resident/cloud operation, status, conversation/epic/sprint/plan refs, provider IDs, command/progress summaries, last status, metadata | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` cloud-run methods | `cloud_runs` in `202605060001_resident_orchestration.sql` | Covers launch/check-in metadata; provider logs and remote files need separate rows. |
| Scheduled jobs | Cloud checks, deferred turns, heartbeats, confirmation expiry, attempts, claim/fire/cancel/failure state | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py` scheduled-job methods | `scheduled_jobs` in `202605060001_resident_orchestration.sql` | Covers resident scheduler state and retry audit fields. |
| Epic migration/export bundle | Deterministic epic export rows, plan artifacts, image blob metadata/payload, manifest warnings/errors, tar/gzip output | `megaplan/store/export.py` | Uses store route and `_migration_entities`; writes filesystem tar/gzip output, not a DB table | Required export path coverage. Matrix rows distinguish exportable content from continuously durable content. |

## Local Persistence and Plan Artifacts

Local persistence has two overlapping but different surfaces:

- `FileStore` is the schema-shaped file backend in `megaplan/store/file.py`. It stores canonical entities as JSON records, framed JSONL event logs, and local blob directories under its configured root.
- `PlanRepository` is the active plan-tree adapter in `megaplan/store/plan_repository.py`. Its docstring states that it intentionally operates on the current on-disk plan tree instead of routing artifacts through `Store`, because workers and fixtures still expect a real filesystem directory.

Those surfaces must not be collapsed in the audit. A plan can have DB-visible state or FileStore-visible metadata while still depending on plan-tree artifact files that are only durable where that filesystem is durable.

### FileStore Root Layout

`FileStore(root)` resolves and creates a root path, constructs `LocalDirBlobStore(root / "blobs")`, and recovers journals at the root and under each epic directory. The current file-backed record layout is:

| FileStore entity group | Local path pattern | Source evidence | DB equivalent named in source inventory |
|---|---|---|---|
| Epics | `<store-root>/epics/<epic-id>/epic.json` | `FileStore._epic_path()` | `epics` |
| Epic body | `<store-root>/epics/<epic-id>/body.md` | `FileStore._body_path()` | `epics.body` |
| Checklist items | `<store-root>/epics/<epic-id>/checklist/<item-id>.json` | `FileStore._checklist_path()` | `checklist_items` |
| Epic event log | `<store-root>/epics/<epic-id>/events.jsonl` | `FileStore._events_path()` and `_commit_event()` | `epic_events` |
| Sprints | `<store-root>/epics/<epic-id>/sprints/<sprint-id>/sprint.json` | `FileStore._sprint_path()` | `sprints` |
| Sprint items | `<store-root>/epics/<epic-id>/sprints/<sprint-id>/items/<item-id>.json` | `FileStore._sprint_items_dir()` | `sprint_items` |
| Plans attached to an epic | `<store-root>/epics/<epic-id>/plans/<plan-id>/plan.json` | `FileStore._plan_dir()` and `_plan_path()` | `plans` |
| Plans attached to a sprint | `<store-root>/epics/<epic-id>/sprints/<sprint-id>/plans/<plan-id>/plan.json` | `FileStore._plan_dir()` and `_plan_path()` | `plans` |
| Orphan plans | `<store-root>/orphan_plans/<plan-id>/plan.json` | `FileStore._plan_dir()` and `_find_plan_path()` | `plans` with no `epic_id` |
| FileStore plan artifacts | `<store-root>/(orphan_plans|epics/.../plans)/<plan-id>/artifacts/<relative-name>` | `FileStore._plan_artifacts_dir()` and `_plan_artifact_path()` | `plan_artifacts` |
| Messages | `<store-root>/messages/<message-id>.json` | `FileStore._message_path()` | `messages` |
| Bot turns | `<store-root>/turns/<turn-id>.json` | `FileStore._turn_path()` | `bot_turns` |
| Tool calls | `<store-root>/tool_calls/<tool-call-id>.json` | `FileStore._tool_call_path()` | `tool_calls` |
| System logs | `<store-root>/system_logs/<log-id>.json` | `FileStore._system_log_path()` | `system_logs` |
| External requests | `<store-root>/external_requests/<request-id>.json` | `FileStore._external_request_path()` | `external_requests` |
| Image records | `<store-root>/images/<image-id>.json` | `FileStore._image_path()` | `images` |
| Feedback | `<store-root>/feedback/<feedback-id>.json` | `FileStore._feedback_path()` | `feedback` |
| Second opinions | `<store-root>/second_opinions/<opinion-id>.json` | `FileStore._second_opinion_path()` | `second_opinions` |
| Codebases | `<store-root>/codebases/<codebase-id>.json` | `FileStore._codebase_path()` | `codebases` |
| Code artifacts | `<store-root>/code_artifacts/<artifact-id>.json` | `FileStore._code_artifact_path()` | `code_artifacts` |
| Locks and leases | `<store-root>/locks/<epic-id>.json`, `<store-root>/leases/<plan-id>.json` | `FileStore._lock_path()` and `_lease_path()` | `epic_locks`, `execution_leases` |
| Control/progress/resident/cloud/scheduler rows | `<store-root>/<control_messages|progress_events|resident_conversations|cloud_runs|scheduled_jobs|automation_actors|migration_runs>/<id>.json` | FileStore path helpers for each directory | Matching Supabase tables in the source inventory |

`megaplan/_core/io.py` supplies the durability mechanism for this file mode. Journal prepare files live at `<journal-root>/_journal/tx-<tx-id>.prepare.json`; commit markers live at `<journal-root>/_journal/tx-<tx-id>.commit`; staged writes use hidden `.<name>.tx-<tx-id>.tmp` files; framed event logs append `_tx_begin` and `_tx_commit` markers around event records. Recovery replays prepared transactions with commit markers, discards uncommitted prepare files, and scrubs stale `*.staging` blob files.

### Local Blob Storage

File mode image/binary blobs use `LocalDirBlobStore` in `megaplan/store/blob.py`. Blob contents live at `<store-root>/blobs/<blob-id>/data.<ext>` with metadata in `<store-root>/blobs/<blob-id>/meta.json`. Blob writes also go through journal blob promotion: `data.staging` is written first, metadata is written to `meta.json`, and the staged payload is renamed to `data.<ext>` on commit.

This is durable only as local filesystem storage. The `images` record can carry `blob_backend`, `blob_id`, `blob_sha256`, `blob_size_bytes`, and `content_type`, but those metadata fields are not the bytes. The DB/blob section separately maps whether DB mode uses Supabase Storage, local DB blob fallback, or only metadata.

### Active Plan Directories

The runtime plan tree is initialized under `<project>/.megaplan/plans/<plan-name>/` by `megaplan/handlers/init.py`, which writes `state.json` and subsequent phase artifacts into that plan directory. `megaplan/_core/io.py` also defines canonical orphan plan roots at `~/.megaplan/<repo-storage-id>/orphan_plans` and searches both that canonical root and the legacy `<project>/.megaplan/plans` root. `PlanRepository.active_plan_dirs()` uses those search roots and treats a directory as a plan when it contains `state.json`.

The legacy import path is separate again. `megaplan/store/legacy_migration.py` reads source plans from `<source-home>/.megaplan/<source-project>/plans/<source-plan-id>/`, snapshots every file with size and SHA-256, creates a target plan with `meta.legacy_migration`, and copies each source file into FileStore plan artifacts through `write_plan_artifact()`.

### PlanRepository Typed Artifact Names

`PlanRepository` lists every file below a bound plan directory, but only some filenames are typed as `PlanArtifact` roles. The current filename-derived roles are:

| Plan-tree filename pattern | Role assigned by `PlanRepository` | Notes |
|---|---|---|
| `state.json`, `plan_v<N>.meta.json` | `plan_meta` | `state.json` is the live local plan state. |
| `plan_v<N>.md` | `plan_version` | `latest_plan_markdown_artifact()` resolves the newest version from `state.plan_versions`. |
| `prep.json` | `prep` | Creative/prep sidecar. |
| `review.json` | `review` | Latest review aggregate. |
| `review_v<N>_raw.txt` | `raw_worker_output` | Raw review worker output. |
| `gate.json` | `gate` | Gate decision aggregate. |
| `gate_signals_v<N>.json` | `gate_signals` | Mechanical gate signal payload. |
| `execution.json` | `execution` | Execution aggregate. |
| `execution_batch_<N>.json` | `execution_batch` | Batch-level execution aggregate. |
| `execution_audit.json` | `execution_audit` | Evidence validation output. |
| `execution_checkpoint.json` | `execution_checkpoint` | Resume/checkpoint artifact when present. |
| `execution_trace.jsonl` | `execution_trace` | Line-oriented execution trace artifact. |
| `execute_v<N>_raw.txt` | `raw_worker_output` | Raw execute worker output. |
| `finalize.json` | `finalize` | Finalize aggregate. |
| `finalize_snapshot.json` | `finalize_snapshot` | Snapshot copy written beside finalize output. |
| `critique*` | `critique` | Critique artifacts by prefix. |
| `faults.json` | `faults` | Fault summary artifact. |
| `step_receipt_*_v<N>.json` | `receipt` | Per-plan receipt copy. |
| `final.md` | `derived_final` | Rendered final document/checklist. |
| `directors_notes.json` | `directors_notes` | Creative notes sidecar. |
| `human_verifications.json` | `human_verifications` | Manual verification record. |
| `tiebreaker_decisions.json` | `tiebreaker_decisions` | Human tiebreaker decisions. |
| `tiebreaker_payload.json` | `tiebreaker_payload` | Tiebreaker payload when present. |
| `*.tmpl`, `*.template` | `template` | Prompt/template artifacts. |
| `research*`, `*.research.json` | `research` | Research artifacts by prefix/suffix. |

This role assignment is filename-based. Unknown filenames are still real files in the plan directory, but `PlanRepository.list_artifacts()` skips them because `_artifact_role()` returns `None`. That means local plan-tree storage can contain durable artifacts that are invisible to typed `PlanArtifact` metadata unless a future row or migration explicitly handles the filename.

### Receipts and Local Audit Mirrors

Receipt persistence is best-effort and file-local. `megaplan/receipts/writer.py` writes a per-plan copy to `<plan-dir>/step_receipt_<phase>_v<iteration>.json`, appends the same receipt to `${MEGAPLAN_AUDIT_DIR:-~/.megaplan/audit}/receipts.jsonl`, and optionally mirrors it to `<project-dir>/.megaplan/audit/receipts.jsonl` when `MEGAPLAN_REPO_AUDIT_MIRROR=1` or the repo audit directory already exists. `megaplan/receipts/query.py` reads the append-only JSONL audit log and projects timestamp, plan, phase, profile, model, duration, cost, scope-drift severity, and verdict.

These mirrors are useful audit evidence, but they are not a complete DB-backed durable audit trail by themselves. They can diverge from store state, and the writer catches exceptions without failing the phase.

### Export Tar Contents

`megaplan/store/export.py` creates a deterministic recovery/export bundle from store-owned epic data. Its tar member paths are:

- `rows/<name>.json` for `epic`, `body`, `checklist_items`, `sprints`, `sprint_items`, `plans`, `images`, `second_opinions`, `feedback`, `code_artifacts`, and `epic_events`.
- `plan_artifacts/<plan-id>/<artifact-name>` for every artifact returned by `_migration_entities()`.
- `blobs/<blob-id>/meta.json` and `blobs/<blob-id>/payload.bin` for exported image blobs when the source exposes a blob store and the blob can be read.
- `manifest.json` with `format: megaplan-epic-export-v1`, member metadata, warnings, and errors.

`write_epic_export_tar()` writes either a plain tar or deterministic gzip-wrapped tar to the requested output path. This is an export snapshot, not continuous storage. It proves the content is collectable at export time and records manifest errors for missing/corrupt blobs; it does not prove every plan-tree artifact body or every runtime log has already been mirrored to DB/blob storage.

### Local Coverage Finding

Local storage coverage is broad but split. FileStore records and blobs have explicit filesystem paths and journal recovery. Active plan directories have a rich artifact tree with typed filename heuristics. Legacy local plans can be imported into FileStore artifacts with provenance. Receipts are mirrored to local JSONL audit logs. Export can bundle rows, plan artifacts, blob metadata, blob payloads, and manifest errors.

The main local gap is artifact-body ownership: `PlanRepository` still writes many plan-tree artifacts directly to disk, and full artifact body coverage in DB/blob storage is partial until the writers, migration paths, and DB/blob backends prove that every required plan artifact, execution log, receipt, and generated binary/audio/image payload is copied into a durable auditable backend.

## DBStore, Idempotency, Blob Backends, and Migration Coverage

DB mode is implemented by `megaplan/store/db.py` against the Supabase/Postgres migrations listed in the source inventory. `DBStore` opens a psycopg connection from `SUPABASE_DB_URL`, sets the actor with `set_actor()`, and uses `autocommit=True` with explicit transactions for multi-statement atomicity. The database model is broad enough to mirror most FileStore JSON records, but byte durability depends on the specific column or blob backend used by each entity.

### DB Equivalents and Payload Shape

The table coverage is source-backed by `_COPY_TABLE_COLUMNS`, `_PLAN_COLUMNS`, `_PLAN_JSONB`, `_COPY_JSONB_COLUMNS`, migrations under `supabase/migrations`, and the DBStore CRUD methods:

| File/local source surface | DB equivalent | Stored payload shape | Coverage status |
|---|---|---|---|
| FileStore `epic.json` and `body.md` | `epics` | Scalar text/timestamps plus `body text`, `home_backend text`, `migrated_to text`, `revision integer` | DB row covers epic metadata and body text. |
| FileStore checklist JSON | `checklist_items` | Scalar fields with FK to `epics` | DB row equivalent exists. |
| FileStore `events.jsonl` | `epic_events` | Scalar fields plus `prior_state`, `pre_state`, `post_state` JSONB and canonical JSON/hash text columns | DB row can be replay/audit evidence when callers populate snapshots and hashes. |
| FileStore sprint and item JSON | `sprints`, `sprint_items` | Scalar fields, sprint `revision`, FK relations | DB row equivalent exists; enum drift noted in source inventory remains a compatibility check. |
| FileStore message/turn/tool/log/request JSON | `messages`, `bot_turns`, `tool_calls`, `system_logs`, `external_requests` | Text/scalars plus JSONB fields for prompt snapshots, warnings, request summaries/bodies, results, transcription metadata | DB row equivalent exists for metadata and structured payloads; raw provider logs and audio bytes are not proven by these rows. |
| Image JSON metadata | `images` | Text/scalars plus blob metadata columns: `blob_backend`, `blob_id`, `blob_sha256`, `blob_size_bytes`, `content_type` | Metadata-only unless paired with a readable object in the selected `BlobStore`. |
| FileStore feedback/opinion/codebase/code-artifact JSON | `feedback`, `second_opinions`, `codebases`, `code_artifacts` | Text/scalars plus JSONB for snapshots, focus areas, resulting item IDs, line range, metadata | DB row equivalent exists; `code_artifacts.content` and `second_opinions.raw_response` are text. |
| FileStore plan `plan.json` | `plans` | Scalar state columns plus JSONB for `config`, `sessions`, `plan_versions`, `history`, `meta`, `last_gate`, `active_step`, `clarification`, latest phase summaries, `resume_cursor` | DB row covers plan state and latest summaries, not every plan-tree file body unless mirrored into `plan_artifacts`. |
| FileStore plan artifacts | `plan_artifacts` | `content_text text`, `content_bytes bytea`, SHA-256, typed metadata; DBStore exposes binary content as `content_base64` when loading `PlanArtifact` models | Byte-capable DB table exists, but current coverage is partial because many active writers still use plan-tree files through `PlanRepository`. |
| FileStore leases/locks/migration/control/progress/resident/cloud/scheduler JSON | `execution_leases`, `epic_locks`, `migration_runs`, `control_messages`, `progress_events`, `resident_conversations`, `cloud_runs`, `scheduled_jobs`, `automation_actors` | Scalar and JSONB operational state | DB row equivalents exist for control/state tracking, not provider log payloads or local marker files. |
| Local image/blob bytes | Supabase Storage object or `LocalDirBlobStore` fallback | Object bytes outside SQL; DB row stores metadata and URL/id/hash | Byte-backed only if `BlobStore.put/get/stat` succeeds and metadata matches. |
| Message voice/audio attachment | `messages.audio_storage_url`, `transcription_metadata` | Text URL plus JSONB metadata | Metadata-only in checked-in DB coverage; no audio byte table or bucket migration is present. |

### Column Registries and Drift Boundaries

`_PLAN_COLUMNS` is the DBStore allowlist for plan row reads/writes. It includes `resume_cursor`, matching `202605050001_add_plan_resume_cursor.sql`, and marks the structured plan fields in `_PLAN_JSONB` so psycopg inserts them as JSONB. This gives DB mode first-class storage for plan state summaries, but the column registry does not by itself collect arbitrary files from `<plan-dir>`.

`_COPY_TABLE_COLUMNS` is the migration-copy allowlist for row-addressed tables. It covers Arnold/editorial tables, Sprint/Megaplan tables, resident/cloud tables, plan rows, and `plan_artifacts`. `_COPY_JSONB_COLUMNS` identifies fields that must be wrapped as JSONB during copy, including prompt snapshots, arguments/results, migration manifests, plan summaries, progress details, resident metadata, request bodies, image transcription metadata, and event snapshots.

`_ARTIFACT_VALID_FIELDS` is the model-load allowlist for `plan_artifacts`. It includes `content_base64` for the Pydantic `PlanArtifact` model even though the SQL column is `content_bytes bytea`; DBStore bridges that by base64-encoding `content_bytes` when loading artifacts and decoding `content_base64` when copying artifacts through migration. This bridge is evidence of byte-capable DB storage, but it is only exercised when artifact writes/copies actually go through DBStore.

### Idempotent Mutator Behavior

DBStore wraps every operation in `_IDEMPOTENT_MUTATORS` through `__getattribute__()`. Wrapped methods require an `idempotency_key` except `append_progress_event`, which can read the key from the event object. For each mutation, DBStore computes a stable request hash from the operation, positional arguments, and keyword arguments excluding the idempotency key, then writes `db_idempotency_keys` with `status='in_progress'`.

On replay, a completed row with the same actor, operation, and request hash returns the stored `response_json` decoded back into the appropriate Pydantic model/list/tuple where possible. Reusing a key with a different request raises an error. Failed mutations mark the ledger row `failed`. This gives DB mode a durable idempotency/audit ledger for mutators, but it is not a complete phase-execution receipt or artifact history by itself.

### DB Plan Artifact Bytes

DBStore `write_plan_artifact()` validates the relative artifact name, computes SHA-256, stores UTF-8 text in `content_text` when decodable, stores the raw bytes in `content_bytes`, and upserts on `(plan_id, name)`. `read_plan_artifact()` prefers `content_bytes`, falling back to encoded `content_text`; `list_plan_artifacts()` and `stat_plan_artifact()` report sizes from `octet_length(content_bytes)` or `octet_length(content_text)`.

The DB table can therefore hold arbitrary artifact bytes after migration `202605050003_plan_artifact_binary_content.sql`. The gap is writer coverage, not only schema capability: active phase handlers and `PlanRepository` still write many artifacts directly into plan directories, and DBStore’s role heuristics differ from `PlanRepository` for some names (`step_receipt` versus `receipt`, `execution_output` versus raw-output roles). Until those writers are routed through Store or mirrored reliably, DB byte capability remains partial coverage.

### Blob Backend Selection

DBStore chooses its blob backend at construction:

- If `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and either `SUPABASE_STORAGE_BUCKET` or `SUPABASE_BUCKET` are present, it uses `SupabaseStorageBlobStore`.
- Otherwise it uses `LocalDirBlobStore(os.environ.get("MEGAPLAN_DB_BLOB_ROOT", ".megaplan/db-blobs"))`.

`SupabaseStorageBlobStore` writes objects with HTTP `PUT` to `/storage/v1/object/<bucket>/<blob-id>`, reads with `GET`, returns public URLs by default, can request signed URLs, and deletes with `DELETE`. `LocalDirBlobStore` stores bytes as `<root>/<blob-id>/data.<ext>` with `<root>/<blob-id>/meta.json`.

No checked-in Supabase migration creates the Storage bucket or bucket policies. Therefore bucket existence, retention, access control, and lifecycle settings are outside current repository-derived evidence. The audit should classify Supabase Storage as an environment-selected blob candidate until infrastructure-as-code or migration evidence is added.

### Image, Binary, and Audio Coverage

`DBStore.attach_image()` hashes image bytes, writes them through `self.blobs.put()`, then creates an `images` row with `storage_url`, `blob_id`, `blob_sha256`, `blob_size_bytes`, and `content_type`. This is byte-backed only for images that enter through `attach_image()` or migration blob-copy paths. `create_image()` can still record a URL and blob metadata without proving byte archival.

Binary plan artifacts are byte-capable through `plan_artifacts.content_bytes`, but generated binary/image/audio assets outside `attach_image()` and `write_plan_artifact()` are not automatically covered. Audio/voice message persistence is metadata-only in the checked-in schema: `messages` has `audio_storage_url` and `transcription_metadata`, but there is no source-backed audio byte table, bucket migration, or audio blob copy path.

### Migration Coverage

`MultiStore` migration copies metadata and artifacts in phases recorded in `migration_runs`: `planning`, `copying_meta`, `copying_blobs`, `verifying`, `cutting_over`, `tombstoning`, `complete`, or `aborted`. For DB targets, `_copy_metadata_to_db()` copies `epics`, `checklist_items`, `sprints`, `sprint_items`, `plans`, `images`, `second_opinions`, `feedback`, `code_artifacts`, and `epic_events` through DBStore `copy_rows_idempotent()`, then copies each plan's artifacts through `copy_plan_artifacts_idempotent()`.

Plan artifact migration builds `PlanArtifact` models from source `ArtifactRef` plus bytes. UTF-8 data goes into `content_text`; non-UTF-8 data goes into `content_base64` and is decoded into `content_bytes` by DBStore. Verification re-reads every copied artifact from the target and compares SHA-256. Image blob migration separately reads the source blob by `blob_id`, verifies `blob_sha256` metadata when present, writes the target blob if absent, reads it back, and records copy progress with source/target hashes and size.

The migration surface is strong for entities included in `_migration_entities()`: epic, checklist, sprints, sprint items, plans, plan artifacts known to the source store, images, second opinions, feedback, code artifacts, and epic events. It is not a blanket migration of active plan directories, provider logs, resident cloud log outputs, local receipt JSONL mirrors, arbitrary `.megaplan` marker files, or generated assets that are not represented as store plan artifacts or image blobs.

### DB/Blob Coverage Finding

DBStore supplies broad row equivalents for FileStore and Arnold/Sprint entities, durable idempotency rows for mutators, JSONB storage for structured state, `bytea` storage for plan artifacts, and a pluggable blob backend for image bytes. The main gaps are:

- Supabase Storage bucket creation/policy/retention is not represented by checked-in migrations or config.
- Image rows can be metadata-only unless bytes are written and verified through `BlobStore`.
- Audio attachment rows are metadata-only.
- Active plan-tree artifact writers still bypass Store in many paths, so `plan_artifacts.content_bytes` is not guaranteed to contain every phase artifact, execution trace, receipt, raw worker output, generated binary, or cloud/provider log.
- Migration coverage only includes entities returned by `_migration_entities()` and blob IDs attached to `images`; it does not prove archival of arbitrary local `.megaplan` files or cloud output.

## Resident Discord Ingestion, Cloud Tools, and Scheduler

Resident storage is centered on the shared `Store` contract, not on Discord itself. `megaplan/resident/runtime.py` persists inbound Discord events as conversations and messages, then records bot turns, tool calls, outbound messages, and conversation cursors. `megaplan/resident/profile.py` supplies the Megaplan-aware tool surface, including cloud launch/status/log operations. `megaplan/resident/scheduler.py` uses durable `scheduled_jobs` rows to run cloud check-ins, deferred turns, heartbeats, and confirmation expiry.

### Discord Conversation and Message Ingestion

`ResidentRuntime.receive()` first authorizes the inbound Discord subject. Allowed events are persisted by `_persist_inbound_event()`:

| Resident ingestion object | Store operation and table | Local/FileStore path | Persisted fields | Coverage note |
|---|---|---|---|---|
| Discord conversation target | `upsert_resident_conversation()` -> `resident_conversations` | `<store-root>/resident_conversations/<conversation-id>.json` | `transport='discord'`, `conversation_key`, `active_epic_id`, `guild_id`, `channel_id`, `thread_id`, `dm_user_id`, `metadata`, `last_active_at` | `202605060001_resident_orchestration.sql` creates the table and indexes transport/key, active epic, channel/thread, and DM user. |
| Inbound Discord message | `create_message(direction='inbound')` -> `messages` | `<store-root>/messages/<message-id>.json` | `conversation_id`, `epic_id`, `content`, `discord_message_id`, `idempotency_key`, attachment flags, voice/audio metadata | DB migration adds `messages.conversation_id` and `messages.idempotency_key`; Discord bytes are not stored by this row. |
| Conversation cursor update | `update_resident_conversation()` -> `resident_conversations` | Same conversation JSON file | `last_inbound_message_id`, `delivery_cursor`, `last_active_at` | Cursor rows are durable enough to resume ingestion state, but only for events that reached the runtime. |

The inbound idempotency key is the message idempotency key passed into `InboundEvent`. DBStore also has uniqueness for `messages.idempotency_key` and `(conversation_id, idempotency_key)`, so duplicate delivery can resolve to the same durable message row. FileStore records the same model in JSON files.

### Resident Turn, Tool, Denial, and System Log Persistence

After the coalescer flushes a burst, `_handle_batch()` writes a `bot_turns` row through `create_turn()` with `triggered_by_message_ids`, `prompt_snapshot`, `prompt_version`, `state_at_turn`, and `model_version`. The prompt snapshot includes the system prompt, message count, and tool catalog returned by `MegaplanResidentProfile.tools().as_schema_catalog()`. The turn is linked back to each inbound `messages` row via `bot_turn_id` and `in_burst_with`.

Tool execution is auditable at the store row level. `_record_tool_calls()` writes each agent tool record through `record_tool_call()` into `tool_calls` with `turn_id`, `tool_name`, `operation_kind`, `arguments`, `result`, and `duration_ms`. The final resident response is persisted as `messages.direction='outbound'`, linked to the `bot_turn_id`, sent through the outbound sink, and reflected back onto `resident_conversations.last_outbound_message_id` and `delivery_cursor`. `bot_turns.status`, `final_output_message_id`, and `message_sent` are then updated to completed; exceptions update the turn to failed with `warnings_issued`.

Authorization failures have two different storage outcomes:

- Inbound authorization denial in `ResidentRuntime.receive()` writes a `system_logs` row with `event_type='resident_inbound_denied'`, the denial reason, and the redacted audit payload when the authorizer returns audit data.
- Tool-action denial in `MegaplanResidentProfile._denied()` returns a `ToolResult` containing `authorization_denied`, `reason`, and `audit`. That denial is durable only if the agent loop records it as a tool call result; the profile helper itself does not separately write a `system_logs` row.

Resident scheduler events use `system_logs` directly for `resident_deferred_turn`, `resident_scheduler_heartbeat`, `resident_confirmation_expiry`, and `resident_cloud_check`.

### Profile Cloud Tools

`MegaplanResidentProfile._register_default_tools()` exposes cloud tools that map resident requests to checked-in cloud CLI wrappers:

| Resident profile tool | Source method | Store rows touched | Durable status |
|---|---|---|---|
| `cloud_status`, `cloud_status_chain` | `_cloud_status()`, `_cloud_status_chain()` | `cloud_runs` via `_load_or_create_cloud_run()` and `_persist_cloud_result()`; `progress_events` when an epic is attached | Summarized status is durable in `cloud_runs.last_status`, `progress_summary`, and optional progress rows. |
| `cloud_start_chain` | `_cloud_start_chain()` | Confirmation flow through `scheduled_jobs` when required; `cloud_runs.operation='chain'`; optional `progress_events` | Start intent and result summary are durable, but remote chain spec bytes and provider logs are not proven here. |
| `cloud_bootstrap` | `_cloud_bootstrap()` | Same confirmation and `cloud_runs.operation='bootstrap'` path | Start intent and result summary are durable; uploaded idea-file contents are not proven by the resident row. |
| `cloud_resume` | `_cloud_resume()` | Admin authorization; `cloud_runs.operation='resume'` | Resume summary/status is durable when the tool runs; local/remote execution artifacts remain separate. |
| `cloud_logs` | `_cloud_logs()` -> `CloudCliBackend` `cloud logs` | `cloud_runs.operation='status'`, `last_status.details.stdout/stderr/payload/argv` through `_persist_cloud_result()` | Tool result details can land in `cloud_runs.last_status`, but this is a bounded tool response, not a retained provider-log archive. |
| `schedule_cloud_check`, `cancel_cloud_check`, `list_cloud_checks` | `_schedule_cloud_check()`, `_cancel_cloud_check()`, `_list_cloud_checks()` | `scheduled_jobs` | Check-in scheduling state is durable and queryable. |

`_create_cloud_run()` writes `cloud_runs` with `operation`, `conversation_id`, `epic_id`, `sprint_id`, `plan_id`, `provider='megaplan-cloud-cli'`, `target_id`, `command_summary`, `metadata`, `idempotency_key`, and `started_by_actor_id`. `_persist_cloud_result()` updates `status`, `progress_summary`, `last_status`, `last_checked_at`, and `completed_at` for terminal/input-needed states. It also appends a `progress_events` row for runs with an `epic_id` using `progress_kind_for_classification()`.

Cloud-start confirmation is partially durable. `StoreBackedConfirmationManager.request_confirmation()` persists a `scheduled_jobs.job_type='confirmation_expiry'` row containing the confirmation payload and expiry time. Confirming, expiring, or cancelling the request updates that scheduled job. The pending confirmation phrase and metadata therefore survive process memory when the store backend is durable.

### Durable Scheduler and Cloud Check-Ins

`StoreScheduledJobBackend` claims due work through `claim_due_scheduled_jobs()`, marks successful jobs fired through `update_scheduled_job(status='fired')`, and retries or cancels failed jobs with `last_error`, `scheduled_for`, `attempt_count`, `claimed_by`, and `claimed_at`. The DB migration constrains `scheduled_jobs.job_type` to `cloud_check`, `deferred_turn`, `heartbeat`, and `confirmation_expiry`, and constrains status to `pending`, `claimed`, `fired`, `cancelled`, and `failed`.

`ResidentJobHandlers.handle_cloud_check()` loads the `cloud_runs` and `resident_conversations` rows named by the scheduled job, runs a constrained cloud status request, persists the result with the same `cloud_runs.last_status` shape used by profile tools, appends a `progress_events` row when the status changed or the run did not yet have `last_status`, and logs `resident_cloud_check` to `system_logs`. Running checks are rescheduled as a new `scheduled_jobs.cloud_check` row; terminal or input-needed checks create an outbound `messages` row, update the conversation cursor, mark the notification in `cloud_runs.metadata.notifications`, and send the outbound notification when an outbound sink is attached.

The durable scheduler therefore covers check-in state, notification state, and status transitions. It does not, by itself, persist raw provider log streams, remote workspace files, or generated cloud artifacts unless those outputs are summarized into `last_status`, emitted as outbound message content, appended as `progress_events`, or written through another artifact/blob path.

### Attachment, Audio, and Resident Cloud Log Gaps

Discord attachment and voice coverage is metadata-only in the resident ingestion path. `messages` can store `has_code_attachment`, `has_image_attachment`, `was_voice_message`, `audio_storage_url`, and `transcription_metadata`, but the runtime path inspected here does not fetch Discord attachment/image/audio bytes into `images`, `plan_artifacts`, Supabase Storage, or a local blob store. `audio_storage_url` may point at an external object, but checked-in migrations do not prove bucket creation, retention, or copy behavior for voice payloads.

Resident cloud-log coverage is also partial. `CloudCliBackend` captures stdout/stderr from `run_cloud_cli()` and returns them in `CloudToolResult.details`; profile and scheduler persistence can store that details object inside `cloud_runs.last_status`. That makes the latest tool result auditable as cloud-run metadata, but it is not equivalent to a durable log artifact with retention, pagination, redaction history, or provider-native log completeness. The cloud/execution mapping treats provider logs, tmux/session logs, `.megaplan/cloud-chain.log`, and marker files as separate storage surfaces.

### Resident Coverage Finding

Resident Discord orchestration has strong row-level coverage for conversations, inbound/outbound messages, bot turns, prompt snapshots, tool calls, system logs, cloud run summaries, scheduled check-ins, progress events, and outbound notification cursors. The main gaps are byte/log completeness: Discord image/code/audio attachment bytes are not proven durable by message metadata, tool-action denials rely on tool-call recording rather than direct system-log writes, `cloud_logs` is a summarized tool result rather than provider-log archival, and cloud start/check-in rows do not prove retention of remote inputs or generated cloud outputs.

## Cloud Runner, Chain State, Launch/Check-In Logs, and Execution Logs

Cloud runner storage spans three layers that should be audited separately:

- Cloud CLI/provider state: `megaplan/cloud/cli.py`, `megaplan/cloud/template.py`, and provider wrappers stage deploy directories, upload inputs, start tmux or container commands, read remote status, and print logs.
- Chain state: `megaplan/chain.py` persists milestone progress under `.megaplan/plans/.chains/` beside the chain spec and can read remote chain state through `cloud status --chain`.
- Plan execution artifacts: `megaplan/execute/core.py`, `megaplan/execute/timeout.py`, workers, and receipt writers create local plan artifacts such as `execution.json`, `execution_batch_<N>.json`, `execution_trace.jsonl`, `execution_audit.json`, raw worker output, `finalize.json`, `final.md`, and receipts.

The repository proves several durable local files and DB-capable summaries, but it does not prove continuous DB/blob archival for remote input files, provider logs, tmux logs, local cloud markers, or every execution trace.

### Cloud Deploy Directories and Local Cache

`megaplan cloud` uses `cloud.yaml` from `<project-root>/cloud.yaml` unless `--cloud-yaml` is supplied. The cloud spec in `megaplan/cloud/spec.py` records provider, repo URL/branch/workspace, mode (`auto`, `chain`, or `idle`), secrets, auto idea-file path, chain spec path, Railway/local/SSH settings, and toolchains.

The deploy directory is materialized by `materialize_deploy_dir()` and includes generated `Dockerfile`, `entrypoint.sh`, `healthserver.py`, `railway.toml`, optional `docker-compose.yaml`, and wrappers `mp-run`, `mp-supervise`, `mp-heartbeat`, and `mp-chain`.

| Provider / mode | Deploy/cache path | Remote/runtime path | Storage finding |
|---|---|---|---|
| Railway | Temporary local directory `megaplan-cloud-*` during build/deploy | Railway service volume/workspace from `spec.repo.workspace` | Deploy dir is ephemeral locally; provider state and logs live with Railway unless copied elsewhere. |
| Local Docker | `~/.megaplan/cloud/<compose_project>/` | Compose service with mounted `<deploy-dir>/<local.workdir>` | Persistent local deploy cache exists, but it is outside Store and is not exported by `megaplan/store/export.py`. |
| SSH Docker | `~/.megaplan/cloud/ssh-<host>/` plus remote `ssh.remote_dir` default `/tmp/megaplan-cloud` | Remote Docker container named by `ssh.container` | Local deploy cache and remote deploy dir are operational files, not DB/blob-backed artifacts. |
| Cloud markers | `~/.megaplan/cloud/markers/<sha16-of-cloud-yaml>/last_chain.json` | N/A | Marker contains the latest remote chain spec path and start time; deleting local cache can lose the default `cloud status --chain` lookup. |

`_clear_persistent_deploy_dir()` deletes local/SSH persistent deploy caches on destroy. Railway does not use a persistent local deploy dir. None of these cache or deploy paths are represented in Supabase migrations or Store methods.

### Cloud Input Uploads and Remote Workspaces

`cloud bootstrap <idea_file>` uploads the local idea file to `<workspace>/idea.txt`, then runs remote `megaplan init --project-dir <workspace> --idea-file <workspace>/idea.txt --auto-start`. That gives the remote plan access to the idea text, but there is no checked-in code that mirrors the uploaded idea file into a DB/blob row before the remote plan starts. It can appear in plan state/artifacts only if the init/runtime writes it there.

`cloud chain <spec> --idea-dir <dir>` reads the local chain spec, resolves each milestone idea path, uploads each local idea file to the milestone's configured remote `idea` path, uploads the chain spec to `<workspace>/chain.yaml`, and starts a detached `tmux` session named `megaplan-chain`. The command executed remotely is:

`MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec <workspace>/chain.yaml >> .megaplan/cloud-chain.log 2>&1`

This proves remote input materialization for explicit `cloud chain` and `cloud bootstrap` commands. It does not prove materialization for image-built `mode: auto` or `mode: chain` inputs. The rendered entrypoint checks `spec.auto.idea_file` or `spec.chain.spec`; if the file is missing, it warns and drops to an idle tmux shell. `materialize_deploy_dir()` does not copy those input files into the image or deploy directory.

### Chain State and Status

`megaplan/chain.py` persists chain progress under `.megaplan/plans/.chains/<spec-stem>-<sha12>.json` next to the chain spec. The state includes `current_milestone_index`, `current_plan_name`, `last_state`, PR number/state, and completed milestones. A legacy `chain_state.json` beside the spec is still read when the new `.chains` path is absent.

For `cloud status --chain`, `cloud_chain_status_payload()` resolves the remote spec from `--remote-spec`, the local marker `~/.megaplan/cloud/markers/<hash>/last_chain.json`, or `cloud.yaml` `mode: chain`. It then reads the remote chain state file computed from that remote spec path and reads the remote chain spec back into a temporary local file to produce the status payload. This means:

- The chain's authoritative progress is the remote `.megaplan/plans/.chains/*.json` file when the chain runs in the remote workspace.
- The local marker is only a pointer to the last remote spec path.
- The status payload is read/display output unless separately persisted by the resident `cloud_runs.last_status` path or another artifact writer.

### Remote Logs, Provider Logs, and Redaction

Cloud logs are operational display paths:

| Log surface | Source path / command | Current retention evidence | Gap |
|---|---|---|---|
| Chain tmux output | Remote `.megaplan/cloud-chain.log` via shell redirection in `_run_chain_wrapper()` | Durable only on the remote workspace filesystem/volume | Not mirrored to `plan_artifacts`, `cloud_runs`, or blob storage by the wrapper. |
| Entrypoint output | `/var/log/entrypoint.log` inside the container from `entrypoint.sh.tmpl` | Container-local file | Not exported or DB-backed by checked-in code. |
| Supervisor output | `/workspace/supervise-<suffix>.log` from `mp-supervise` | Remote workspace file | Not automatically copied into Store. |
| Detached session log | `/workspace/<session>.log` from `mp-run` | Remote workspace file | Not automatically copied into Store. |
| Railway provider logs | `railway logs --service <service>` with `--lines 200` for no-follow | Provider CLI output; follow mode streams | No checked-in retention/export beyond Railway's own behavior. |
| Local Docker logs | `docker compose logs [-f] agent` or `--tail 200 agent` | Docker log driver/provider output | No Store/blob archival. |
| SSH Docker logs | `docker logs [-f|--tail 200] <container>` | Remote Docker log output | No Store/blob archival. |

`megaplan/cloud/redact.py` redacts configured secret assignments, literal secret values from `spec.secrets`, and common token patterns before displaying command/log output through `_write_redacted_output()` or `_logs_follow()`. This is redaction-at-display. The code does not create a redacted log artifact or prove that provider-native logs are redacted at rest.

### Cloud Launch, Status, and Resident Check-In Mapping

Cloud launch/check-in has a durable summary path when it is invoked through resident profile tools or scheduler jobs:

- `MegaplanResidentProfile._cloud_start_chain()`, `_cloud_bootstrap()`, `_cloud_resume()`, and `_cloud_logs()` create or reuse `cloud_runs` rows and persist `CloudToolResult` classification, summary, stdout/stderr/payload details, and check time into `cloud_runs.last_status`.
- Scheduler `cloud_check` jobs periodically run cloud status, update the same `cloud_runs` summary fields, append `progress_events` when status changes, create outbound notification `messages` for terminal or input-needed states, and log `resident_cloud_check`.
- Plain `megaplan cloud ...` CLI invocations outside resident tools do not themselves create `cloud_runs`, `scheduled_jobs`, or `progress_events`.

Therefore `cloud_runs` and `progress_events` are durable summaries, not complete copies of remote command inputs, remote `.megaplan` trees, tmux logs, provider logs, or generated cloud outputs.

### Execution Artifacts and Worker Session Logs

Execution artifacts are local plan-tree files unless explicitly mirrored through Store by a caller:

| Execution surface | Local path / backend | Source evidence | DB/blob status |
|---|---|---|---|
| Batch execution output | `<plan-dir>/execution_batch_<N>.json` | `_run_and_merge_batch()` writes `batch_artifact_path()` | DB-capable only if mirrored through `plan_artifacts`; active handler writes plan file directly. |
| Aggregate execution output | `<plan-dir>/execution.json` | Final-batch and aggregate execute handlers write it | Same local-first caveat. |
| Execution audit | `<plan-dir>/execution_audit.json` | `validate_execution_evidence()` output | Local artifact; no guaranteed DB mirror. |
| Finalize mirror after execute | `<plan-dir>/finalize.json`, `<plan-dir>/final.md` | Execute merge writes rendered final output | Local plan artifacts, exportable if Store sees them. |
| Execution trace | `<plan-dir>/execution_trace.jsonl` | `_append_trace_output()` and aggregate trace writes | Local JSONL; may contain worker trace output but not guaranteed provider/session completeness. |
| Raw worker output | `<plan-dir>/<step>_v<iteration>_raw.txt` | `store_raw_worker_output()` on failures/timeouts | Local artifact only unless mirrored. |
| Receipts | `<plan-dir>/step_receipt_execute_v<iteration>.json`, `${MEGAPLAN_AUDIT_DIR:-~/.megaplan/audit}/receipts.jsonl`, optional repo mirror | `write_receipt()` from execute handlers | Local audit mirrors; not complete DB audit trail. |
| Codex rollout session | `$CODEX_HOME/sessions/<YYYY>/<MM>/<DD>/rollout-*-<session-id>.jsonl` | Worker cost reader `_codex_session_jsonl_path()` | Used for cost deltas; not copied to plan artifacts or DB by this path. |
| Hermes session DB/logs | Hermes worker uses `SessionDB()` and AIAgent session persistence | `megaplan/hermes_worker.py` and `agent/run_agent.py` | Agent-runtime persistence, not Megaplan Store coverage unless explicitly exported. |

Execute handlers also update `state["sessions"]` with worker session IDs and append phase history with duration, cost, output file, artifact hash, finalize hash, approval mode, session mode/id, and optional raw-output file. This is useful plan-state audit metadata, but it is not a substitute for archival of the underlying session JSONL, provider logs, or remote execution outputs.

### Cloud Durability Risk Ranking

For the cloud/execution surface specifically:

- **High** — Provider and tmux logs are not guaranteed durable beyond provider/container/local log retention. `cloud logs`, `.megaplan/cloud-chain.log`, `/workspace/supervise-*.log`, `/workspace/<session>.log`, and `/var/log/entrypoint.log` need explicit archival if they are audit evidence.
- **High** — Remote inputs and generated outputs can exist only in the remote workspace. `cloud bootstrap` and `cloud chain` upload files, but no checked-in path mirrors uploaded idea files, chain specs, remote `.megaplan` trees, or generated assets into DB/blob storage.
- **Medium** — Local cloud markers are fragile. `~/.megaplan/cloud/markers/<hash>/last_chain.json` controls default chain status lookup, while the authoritative remote chain state is elsewhere.
- **Medium** — Execution traces and raw worker outputs are local plan-tree artifacts. They are file-durable but not guaranteed DB/blob durable because active handlers still write directly to the plan directory.
- **Low** — Redaction is display-time only. It reduces accidental leakage in CLI output but does not prove redacted provider logs at rest or durable redacted audit copies.

### Cloud/Execution Coverage Finding

Cloud runner coverage is strong for launching work and reconstructing summarized status: explicit chain/bootstrap commands upload inputs, remote chain state is persisted under `.megaplan/plans/.chains/`, local cloud cache and markers are deterministic, resident tools can summarize status into `cloud_runs`, and execute handlers write rich local artifacts. The durable-audit gap is that most cloud-specific bytes and logs remain outside Store: provider logs, tmux/session logs, remote input files, remote generated artifacts, local markers, and external session JSONL/DB files are not guaranteed DB/blob archived by the checked-in paths.

## Coverage Matrix

| Domain | Entity/artifact/event | Current source path | DB table/columns | Local path/backend | Blob/storage backend | Durable/auditable status | Known gap | Recommended owner/next action |
|---|---|---|---|---|---|---|---|---|
| Arnold V2/editorial | Epic state, body, checklist, event history | `megaplan/schemas/arnold.py`; `megaplan/store/base.py`; `supabase/migrations/202604300001_001_core.sql`; `202604300004_004_editorial_core.sql` | `epics` including `body`, `home_backend`, `migrated_to`, `revision`; `checklist_items`; `epic_events` with JSONB snapshots/hashes | FileStore `epics/<epic-id>/epic.json`, `body.md`, `checklist/`, `events.jsonl` | None for body/checklist/events | Durable in DB/FileStore when written through Store; event audit quality depends on populated snapshots | Arnold tables are overlap/context unless runtime ownership is proven for a flow | Store/schema owners: keep Arnold overlap explicit and add runtime-owner notes in tickets |
| Arnold V2/editorial | Feedback, sprints, sprint items | `megaplan/schemas/arnold.py`; migrations `202604300005_005_feedback.sql`, `202604300006_006_sprints.sql` | `feedback`; `sprints`; `sprint_items` | FileStore `feedback/`, `epics/<id>/sprints/<sprint-id>/sprint.json`, `items/` | None | Durable row/file coverage for structured records | Sprint status enum drift between schema and migration remains a compatibility risk | Store/schema owners: add schema/migration drift check and backfill plan if statuses expand |
| Arnold V2/editorial | Second opinions, codebases, code artifacts | `megaplan/schemas/arnold.py`; migrations `202604300008_008_second_opinions.sql`, `202604300009_009_codebase_research.sql` | `second_opinions.raw_response`, `focus_areas`, `resulting_checklist_item_ids`; `codebases`; `code_artifacts.content`, `line_range`, `metadata` | FileStore `second_opinions/`, `codebases/`, `code_artifacts/` | None | Durable text/JSONB row coverage | Binary/code attachments are not represented; code artifact content is text/cache data | Research/editorial owners: treat as text records and add blob rows only if binary research artifacts appear |
| Resident Discord ingestion | Conversation identity, Discord message IDs, inbound/outbound message rows | `megaplan/resident/runtime.py`; `megaplan/store/base.py`; migration `202605060001_resident_orchestration.sql` | `resident_conversations` with guild/channel/thread/DM IDs and cursor fields; `messages.conversation_id`, `discord_message_id`, `idempotency_key`, attachment/audio metadata | FileStore `resident_conversations/<id>.json`, `messages/<id>.json` | Metadata only unless an attachment/image blob is separately stored | Durable/auditable for IDs, message text, delivery cursor, and metadata | Attachment bytes and audio bytes are metadata-only in the proven path | Resident owner: add attachment/audio byte ingestion into image/blob or artifact storage |
| Resident runtime | Bot turns, prompt snapshots, tool calls, authorization denials, deferrals, system logs | `megaplan/resident/runtime.py`; `megaplan/resident/auth.py`; `megaplan/store/base.py` | `bot_turns`; `tool_calls`; `system_logs`; `scheduled_jobs` for deferrals/confirmation expiry | FileStore `turns/`, `tool_calls/`, `system_logs/`, `scheduled_jobs/` | None for raw tool/model traces | Durable structured audit rows when the runtime writes them | Raw model transcripts/provider traces are not guaranteed by bot-turn/tool rows | Resident/runtime owner: standardize event logging for denial/deferral/confirmation paths |
| Resident profile cloud tools | `_cloud_start_chain`, `_cloud_bootstrap`, `_cloud_resume`, `_cloud_logs` side effects | `megaplan/resident/profile.py`; `megaplan/resident/cloud.py` | `cloud_runs` for operation/status summaries; `progress_events`; outbound `messages`; occasional `system_logs` | FileStore `cloud_runs/`, `progress_events/`, `messages/` | None for the returned log text unless copied elsewhere | Durable for summarized operation state and outbound notifications | `_cloud_logs` output is transient tool response unless archived into a row/artifact | Resident/cloud owner: persist cloud-log responses as `plan_artifacts` or dedicated log artifacts with redaction metadata |
| Scheduler/cloud runs | Scheduled checks, heartbeats, confirmation expiry, status/check-in updates | `megaplan/resident/scheduler.py`; `megaplan/store/base.py`; migration `202605060001_resident_orchestration.sql` | `scheduled_jobs`; `cloud_runs.last_status`, `status`, `metadata`; `progress_events`; outbound `messages`; `system_logs` | FileStore `scheduled_jobs/`, `cloud_runs/`, `progress_events/`, `messages/`, `system_logs/` | None for provider logs | Durable for job lifecycle, retry state, and summarized cloud status | Check-ins preserve summaries, not provider log bodies or remote workspace outputs | Scheduler owner: add explicit archival hook when check-ins fetch log/output payloads |
| Cloud launch/bootstrap | Uploaded idea files, chain specs, remote workspace inputs | `megaplan/cloud/cli.py`; `megaplan/cloud/bootstrap.py`; `megaplan/chain.py` | None directly; resident-initiated launches may update `cloud_runs` and `progress_events` | Remote workspace files under provider deploy/workspace dirs; local deploy dirs generated by provider helpers | None unless separately mirrored | Operationally durable only on provider/workspace filesystem | Uploaded inputs can be unmirrored and lost with workspace/provider retention | Cloud owner: copy launch inputs into `plan_artifacts` or blob storage before/after upload |
| Cloud cache/markers | Local cloud cache, deploy metadata, chain marker lookup | `megaplan/cloud/cli.py`; `megaplan/cloud/config.py` | None directly | `~/.megaplan/cloud`, provider deploy dirs, `markers/<hash>/last_chain.json` | None | Local audit/lookup evidence only | Markers are local, fragile, and not a canonical DB state | Cloud owner: persist marker records as Store rows or exportable artifacts |
| Chain state/status | Chain specs, current chain status, chain state files | `megaplan/chain.py`; `megaplan/cloud/cli.py` | None directly; resident summaries may use `cloud_runs` | `.megaplan/plans/.chains/`; `.megaplan/cloud-chain.log`; remote chain workspace files | None | Durable where the plan/cloud filesystem survives | Chain state is not Store-backed by default | Chain/cloud owner: add chain-state artifact writer and DB/file-store migration path |
| Cloud logs/provider logs | Railway/Docker/SSH logs, tmux/session logs, redacted CLI display | `megaplan/cloud/providers/*.py`; `megaplan/cloud/redact.py`; `megaplan/cloud/cli.py` | None directly; summarized status can land in `cloud_runs.last_status` | `.megaplan/cloud-chain.log`, `/workspace/supervise-*.log`, `/workspace/<session>.log`, `/var/log/entrypoint.log`, provider log APIs | None unless caller writes a log artifact | Not guaranteed durable/auditable beyond provider or local retention | Display-time redaction is not redacted-at-rest archival | Cloud/platform owner: introduce log archive artifact with source, retention, and redaction fields |
| Plan state | Plan config/state/history/latest phase summaries/resume cursor | `megaplan/schemas/sprint1.py`; `megaplan/store/base.py`; `megaplan/store/db.py`; `megaplan/store/file.py` | `plans` with JSONB `config`, `sessions`, `plan_versions`, `history`, `meta`, latest review/gate/execution/finalize/failure, `resume_cursor` | FileStore `plans/<plan-id>/plan.json`; active `<project>/.megaplan/plans/<plan-name>/state.json`; canonical orphan plan roots | None | Durable structured plan state in DB/FileStore; active state is file-local | Active plan tree can diverge from DB summaries | Plan/runtime owner: route state updates through Store or add reconciliation checks |
| Plan artifacts | Plan Markdown, reviews, gates, finalize docs, directors notes, batch JSON | `megaplan/store/plan_repository.py`; `megaplan/store/base.py`; `megaplan/store/db.py` | `plan_artifacts` with role/name/mime/stats, `content_text`, `content_json`, `content_bytes`, `content_base64`, hashes | Active plan-dir files; FileStore `artifacts/<relative-name>` | DB `bytea`/base64 for artifact bytes; local/Supabase blob only if caller chooses blob route | Durable if mirrored into `plan_artifacts`; file-durable otherwise | `PlanRepository` writes many bodies directly to disk and role typing is filename-based | Plan/storage owner: make plan writers call Store artifact APIs and add unknown-file capture |
| Execution logs/artifacts | `execution.json`, `execution_batch_N.json`, `execution_audit.json`, `execution_trace.jsonl`, raw worker output | `megaplan/execute/core.py`; `megaplan/handlers/execute.py`; `megaplan/store/plan_repository.py` | `plan_artifacts` can store `execution`, `execution_batch`, `execution_audit`, `execution_trace`, raw outputs if mirrored; `plans.latest_execution` summary | Active plan-dir execution files and raw `execute_v<N>_raw.txt`; worker session IDs in `state.sessions` | Artifact bytes/text only when mirrored | Local plan-tree audit is strong; DB/blob durability is partial | External session JSONL/DB and provider logs are outside Store | Execute owner: archive raw outputs, traces, and external session refs through `plan_artifacts` |
| Receipts/audit logs | Step receipts, repo/home audit mirrors, cost/duration/verdict summary | `megaplan/receipts/writer.py`; `megaplan/receipts/query.py` | No dedicated receipt table; optional `plan_artifacts` if captured as receipt role | `<plan-dir>/step_receipt_<phase>_v<iteration>.json`; `${MEGAPLAN_AUDIT_DIR:-~/.megaplan/audit}/receipts.jsonl`; optional repo mirror `.megaplan/audit/receipts.jsonl` | None | Useful local append-only audit evidence | Best-effort writer can fail silently; not complete DB-backed audit | Audit owner: add receipt Store table or guaranteed receipt artifact ingestion |
| Binary/image assets | Images and generated binary payloads | `megaplan/store/base.py`; `megaplan/store/blob.py`; `megaplan/store/db.py`; migration `202605050002_sprint5_editorial_schema.sql`; `202605050003_plan_artifact_binary_content.sql` | `images` metadata/blob columns; `plan_artifacts.content_bytes`/`content_base64` for artifact binaries | FileStore `images/<id>.json`; `blobs/<blob-id>/meta.json` and `data.<ext>`; active plan-dir generated files | `LocalDirBlobStore`; `SupabaseStorageBlobStore` when env-selected; local DB blob fallback | Byte durability exists only when bytes are actually written to blob/artifact backend | Supabase bucket/config is env-driven, no checked-in bucket migration; many generated files remain local | Storage owner: provision bucket/config migration and require blob/artifact copy for generated assets |
| Audio/voice assets | Discord voice/audio metadata, transcription metadata | `megaplan/schemas/arnold.py`; `megaplan/resident/runtime.py` | `messages.audio_storage_url`, `audio_duration_seconds`, `transcription_text`, `transcription_metadata` | Message JSON in FileStore; no proven audio file path | Metadata URL only unless external storage is populated by caller | Durable metadata and transcript only | Audio bytes are not proven ingested into Store/blob | Resident/media owner: add audio byte fetch/store path or mark external URL retention explicitly |
| Supabase Storage/blob candidates | DB blob backend selection and local fallback | `megaplan/store/blob.py`; `megaplan/store/db.py` | Blob refs in `images`; binary artifact columns in `plan_artifacts` | `MEGAPLAN_DB_BLOB_ROOT` or `.megaplan/db-blobs`; FileStore `blobs/` | `SUPABASE_STORAGE_BUCKET` / Supabase Storage when configured | Backend-capable but configuration dependent | No source-backed bucket/policy migration or first-class required config | Storage/platform owner: add migrations/config validation for bucket, policies, and fallback root |
| Local `.megaplan` files | Runtime schemas, active plans, audit mirrors, local cloud cache | `megaplan/_core/io.py`; `megaplan/store/plan_repository.py`; `megaplan/cloud/config.py` | Mixed: DB may mirror some plan/artifact rows, but not runtime schema/cache files | `<project>/.megaplan/plans/`, `<project>/.megaplan/audit/`, repo/runtime `.megaplan/schemas`, `~/.megaplan/<repo-id>/orphan_plans`, `~/.megaplan/cloud` | None unless a file is copied to blob/artifact storage | Local filesystem durable only | Arbitrary local files can be missed by DB/export | Runtime owner: enumerate required local files and either ignore, export, or store them explicitly |
| Migration/import | Legacy local plan import and store-to-store copy progress | `megaplan/store/legacy_migration.py`; `megaplan/store/multi.py`; `megaplan/store/db.py`; `megaplan/store/export.py` | `migration_runs`; copied target rows in `plans`, `plan_artifacts`, image/blob metadata tables | Source `.megaplan/<project>/plans/<plan-id>/`; migration snapshots and copied artifacts | Blob-copy progress for images; artifact bytes when copied | Auditable for known migration entities and copied IDs | `_migration_entities()`/legacy import can miss unknown plan files, provider logs, remote inputs | Migration owner: add completeness report for unknown files and non-Store cloud/log surfaces |
| Export bundles | Epic export rows, plan artifacts, blob metadata/payloads, manifest warnings/errors, tar/gzip output | `megaplan/store/export.py` | Reads source tables/Store rows; no new DB table | User-chosen tar/gzip path; tar members `rows/`, `plan_artifacts/`, `blobs/`, `manifest.json` | Exports blob payloads when readable from source blob store | Snapshot is reproducible audit/recovery artifact at export time | Export is not continuous mirroring and only covers exported entity set | Export owner: extend manifest coverage and schedule periodic exports if used for durability |
| Control/progress/leases/idempotency | Control messages, progress events, execution leases, idempotency keys, locks | `megaplan/store/base.py`; `megaplan/store/db.py`; migration `202605040000_megaplan_dbstore_foundation.sql` | `control_messages`, `progress_events`, `execution_leases`, `db_idempotency_keys`, `epic_locks` | FileStore `control_messages/`, `progress_events/`, `leases/`, `locks/` | None | Durable operational state and idempotency audit where Store is used | Not a full execution/provider log trail | Store/runtime owner: keep event kinds/job types covered by regression tests and matrix updates |
| Cloud output/generated assets | Remote generated files, provider outputs, execution products | `megaplan/cloud/cli.py`; `megaplan/cloud/providers/*.py`; `megaplan/handlers/execute.py`; `megaplan/store/plan_repository.py` | Only if copied into `plan_artifacts`, `images`, or summarized in `plans`/`cloud_runs` | Remote workspace outputs; active plan-dir outputs; provider deploy dirs | Blob/artifact backend only when explicitly written | Partial and flow-dependent | Generated assets can remain only on remote/local filesystems | Cloud/execute owners: define generated-output inventory and mandatory artifact/blob archival hook |

## Risk-Ranked Gaps

### Critical

- **PERSIST-CRIT-001 — Plan artifact bodies and execution logs are still file-local in active flows.**
  `PlanRepository` writes rich plan-tree files directly under `.megaplan/plans/<plan>/`, including `execution.json`, `execution_batch_<N>.json`, `execution_trace.jsonl`, raw worker output, receipts, review/finalize artifacts, and derived final files. `plan_artifacts.content_bytes` is byte-capable, but the audit evidence shows partial writer coverage. A DB row can therefore describe a plan without containing the artifact bodies needed to reconstruct or audit execution.
  Recommendation: make active phase writers call a Store artifact API for every required artifact, preserve local file writes as a compatibility cache, and add a reconciliation check that fails when a typed plan-tree artifact is missing from `plan_artifacts`.

- **PERSIST-CRIT-002 — Cloud/provider logs and remote workspace outputs have no guaranteed durable archive.**
  Cloud flows can read provider logs, tmux logs, `.megaplan/cloud-chain.log`, `/workspace/supervise-*.log`, `/workspace/<session>.log`, `/var/log/entrypoint.log`, uploaded idea/chain inputs, remote `.megaplan` trees, and generated outputs, but those bytes are not guaranteed to be copied into DB/blob storage. `cloud_runs.last_status` and `progress_events` are durable summaries, not log retention.
  Recommendation: introduce a cloud log/output archival artifact type with source path, provider, capture time, redaction status, retention metadata, byte hash, and optional blob pointer; call it from launch, status/check-in, `cloud logs`, and terminal-run collection paths.

### High

- **PERSIST-HIGH-001 — Resident `cloud_logs` output is transient unless incidentally summarized.**
  `MegaplanResidentProfile._cloud_logs()` can persist a bounded `CloudToolResult.details` object into `cloud_runs.last_status`, but that is not a provider-log archive with pagination, retention, redaction history, or raw payload completeness.
  Recommendation: persist every resident cloud-log response as a `plan_artifacts` log artifact or a dedicated `cloud_run_logs` table keyed by `cloud_run_id`, with truncation and redaction metadata.

- **PERSIST-HIGH-002 — Discord attachment, image, and audio bytes are metadata-only in resident ingestion.**
  `messages` rows preserve Discord IDs, attachment flags, `audio_storage_url`, transcription text, and transcription metadata. The inspected resident ingestion path does not prove that Discord attachment/image/audio bytes are fetched into `images`, `plan_artifacts`, Supabase Storage, or local blob storage.
  Recommendation: add a resident media ingestion pipeline that downloads allowed Discord media, stores bytes through the selected blob backend, links message rows to `images` or artifact records, and records external URL retention assumptions.

- **PERSIST-HIGH-003 — Supabase Storage is env-selected but not first-class schema/config.**
  `DBStore` can select `SupabaseStorageBlobStore` through environment variables, otherwise falling back to `MEGAPLAN_DB_BLOB_ROOT` or `.megaplan/db-blobs`. Checked-in migrations do not prove bucket creation, policies, retention, or required configuration.
  Recommendation: add source-controlled storage provisioning and startup validation for required bucket names, policies, object prefixes, signed/public URL mode, and local fallback root; fail clearly when binary storage is configured incompletely.

- **PERSIST-HIGH-004 — Local receipt audit JSONL is useful but not a guaranteed DB-backed audit trail.**
  Receipts are written to plan-local JSON, home audit JSONL, and optional repo mirror JSONL on a best-effort path. The writer tolerates failures, and no dedicated DB table guarantees receipt identity, retention, or queryability.
  Recommendation: create a receipt table or mandatory receipt artifact ingestion path with unique identity fields for plan, phase, iteration, attempt, batch, actor, model, cost, duration, verdict, and hash.

### Medium

- **PERSIST-MED-001 — Local cloud markers are fragile state.**
  `~/.megaplan/cloud/markers/<hash>/last_chain.json` helps status lookup, but it is a local cache outside Store and outside export. Losing it can break convenient status resolution even when remote chain state still exists.
  Recommendation: write marker-equivalent state into Store-backed artifacts or `cloud_runs.metadata`, and treat local markers as a cache that can be rebuilt.

- **PERSIST-MED-002 — Legacy migration/import only covers known local plan files and Store migration entities.**
  Legacy migration snapshots source files and copies known artifacts, while `_migration_entities()` drives export/migration coverage. Unknown plan files, provider logs, remote inputs, remote generated outputs, external session DBs, and cloud markers can remain outside migration/export bundles.
  Recommendation: add migration/export completeness manifests that list unknown local files, skipped remote/cloud surfaces, missing blobs, and unsupported artifact roles, then require an explicit ignore or copy rule for each class.

- **PERSIST-MED-003 — Filename-heuristic artifact typing can miss drifted artifacts.**
  `PlanRepository` maps artifact roles from filename patterns. Unknown filenames can remain durable on disk but invisible to typed artifact listings, DB artifact migration, and matrix-driven audits.
  Recommendation: introduce an artifact registry shared by writers, `PlanRepository`, DBStore, migration, and export; add an `unknown_artifact` capture mode until all writers are registered.

- **PERSIST-MED-004 — Plan state summaries can diverge from plan-tree artifacts.**
  `plans` rows store rich JSONB summaries, but active plan files can be newer or more complete than DB summaries when code writes directly to disk. This affects latest review, execution, finalize, and resume state.
  Recommendation: add a reconciliation command or test helper that compares plan row summaries, artifact hashes, and local plan-tree files after each phase.

### Low

- **PERSIST-LOW-001 — Display-time redaction does not prove redacted storage.**
  Cloud redaction reduces CLI leakage, but source paths do not prove that archived logs are redacted at rest or that raw/redacted copies are tracked separately.
  Recommendation: add redaction metadata to any future log artifact and store both policy version and capture mode.

- **PERSIST-LOW-002 — Arnold/editorial ownership remains overlap/context in several rows.**
  Arnold V2 migrations and schemas are source-backed, but runtime ownership is not proven for every Megaplan behavior that shares a table name or concept.
  Recommendation: keep Arnold rows in the matrix as schema-backed overlap and require runtime owner evidence before assigning active Megaplan responsibility.

- **PERSIST-LOW-003 — Storage coverage can regress silently as new entity kinds appear.**
  New artifact roles, progress event kinds, resident job types, cloud tools, or Supabase tables can be added without an audit row, migration/export path, or blob-retention decision.
  Recommendation: add a storage-coverage regression checklist in tests or CI that compares Store methods, DB table allowlists, artifact role registries, resident job types, cloud tools, and export/migration entity lists against this matrix.

## Implementation Recommendations

1. **Unify plan artifact writes behind Store.**
   Implement a compatibility wrapper that writes existing plan-tree files and also writes `plan_artifacts` with role, MIME type, SHA-256, byte/text payload, phase, iteration, and source filename. Start with execution/finalize/review/receipt artifacts because they carry audit-critical evidence.

2. **Add a cloud log and output archival path.**
   Define a `cloud_log` or `cloud_output` artifact role, or add a `cloud_run_logs` table if query patterns require it. Capture provider, command, remote path, status class, capture time, truncation, redaction policy, content hash, and blob/artifact pointer. Wire it into `cloud logs`, scheduler cloud checks, terminal launch/check-in paths, and chain/bootstrap completion.

3. **Mirror cloud launch inputs and markers.**
   Before uploading an idea file or chain spec, write the input into a Store-backed artifact. After launch/status, write marker-equivalent state into `cloud_runs.metadata` or a chain-state artifact so `~/.megaplan/cloud/markers/<hash>/last_chain.json` is rebuildable rather than authoritative.

4. **Make resident media ingestion byte-backed.**
   For Discord attachments, images, and voice/audio, store bytes through the selected blob backend and link message rows to `images`, `plan_artifacts`, or a dedicated media artifact. Record content type, size, hash, Discord object ID, external URL, transcript metadata, and retention status.

5. **Provision and validate blob storage explicitly.**
   Add migrations/config for Supabase Storage bucket expectations or a checked-in startup validator that asserts bucket, policy, URL mode, object prefix, and fallback root. Treat missing binary storage configuration as a startup/config error when image/audio/binary ingestion is enabled.

6. **Promote receipts to durable Store-owned audit records.**
   Preserve JSONL mirrors as operator-friendly copies, but add a DB table or required artifact ingestion path for receipts. Include uniqueness constraints that prevent plan/phase/iteration/attempt or batch collisions.

7. **Extend migration/export manifests for completeness.**
   Include unknown plan-tree files, skipped artifact roles, missing blob payloads, provider-log exclusions, remote-input exclusions, and external session references in `manifest.json` or migration-run details. Make each exclusion explicit enough to become a follow-up ticket.

8. **Replace filename-only artifact typing with a shared registry.**
   Define artifact roles and filename patterns in one module consumed by writers, `PlanRepository`, DBStore, migration, export, and tests. Until every writer uses the registry, capture unknown files as `unknown_artifact` with source path and hash.

9. **Add storage coverage regression checks.**
   Add tests that fail when new Store entities, DB table copy columns, artifact roles, progress event kinds, resident scheduled job types, resident cloud tools, or Supabase migrations lack a matrix/export/migration/blob decision. The check should distinguish `metadata-only`, `DB row`, `DB byte`, `local file`, `local blob`, and `Supabase Storage` coverage.

10. **Define retention policy per storage class.**
    For DB rows, local files, Supabase objects, local DB blobs, provider logs, remote workspaces, receipts, and export bundles, document intended retention and deletion behavior. This should be source-controlled policy, not inferred from provider defaults.
