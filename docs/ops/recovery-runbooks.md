# Sprint 7 Recovery Runbooks

These runbooks cover the known hardening scenarios for local FileStore, DBStore, legacy local plan migration, export backup, and cloud chain operations.

## Stuck FileStore Transaction Journal

Evidence id: `OPS-JOURNAL-RECOVERY`

Symptoms:
- Writes under `.megaplan/` appear partially applied.
- A journal directory or pending transaction file remains after a crash.
- Subsequent commands fail during `_commit_write()` or transaction recovery.

Diagnosis:
- Inspect the project store root from `MultiStore.canonical_filestore_root(<project-dir>)`.
- Check for journal files under the FileStore journal root used by `megaplan._core.io.prepare_journal_transaction()`, `commit_journal_transaction()`, and `recover_journal()`.
- Run the command that failed with `MEGAPLAN_BACKEND=file` to confirm the issue is local store state, not DB routing.

Reproduction setup:
- Create a file-backed epic, start a write through `FileStore._commit_write()`, and interrupt after journal preparation but before commit.
- Practical local evidence is covered by file-store journal tests and the standard full-suite command.

Recovery steps:
- Stop active megaplan processes for the project.
- Back up the entire FileStore root.
- Run a read-only command such as `megaplan epic snapshot <epic-id>` to trigger journal recovery paths.
- If recovery cannot complete, inspect the staged payload and either complete the move into the target path or remove the incomplete transaction after preserving a copy.

Post-recovery validation:
- Run `pytest tests/test_file_store.py -q`.
- Run `megaplan epic snapshot <epic-id>` and verify the snapshot JSON includes the expected latest rows/artifacts.
- Confirm no journal transaction remains for the recovered write.

Concrete references:
- `megaplan/store/file.py`: `FileStore._commit_write()`, `FileStore.transaction()`.
- `megaplan/_core/io.py`: `prepare_journal_transaction()`, `commit_journal_transaction()`, `recover_journal()`.

## Abandoned `migration_run`

Evidence id: `OPS-MIGRATION-RUN-RESUME`

Symptoms:
- `megaplan epic migrate <id> --to db` reports an active or incomplete migration.
- The source epic is not fully tombstoned or target rows are partially copied.
- `migration_runs.phase` is not `complete` or `aborted` and `completed_at` is empty.

Diagnosis:
- Run `megaplan epic migrate --resume <migration-id> --actor <actor>`.
- Inspect `migration_run.manifest`, `copied_ids`, `blob_copy_progress`, `holder_id`, and `expires_at`.
- Confirm no newer migration exists for the same epic.

Reproduction setup:
- Create a migration with `MultiStore.migrate_epic()`, interrupt between copy phases, then resume.
- Local coverage exists in `tests/test_multi_store.py` migration resume cases.

Recovery steps:
- If the lease is expired, resume with `megaplan epic migrate --resume <migration-id> --actor <actor>`.
- If another holder is active, wait for `expires_at` or investigate that worker before stealing work.
- If copied rows exist in the target, rely on idempotent copy helpers and continue the same migration id rather than starting a new migration.

Post-recovery validation:
- Run `pytest tests/test_multi_store.py -q`.
- Verify `phase == "complete"` and `completed_at` is set.
- Load the epic through `MultiStore.load_epic(<id>)` and confirm `home_backend` matches the target.

Concrete references:
- `megaplan/store/multi.py`: `migrate_epic()`, `resume_migration()`, `_migration_entities()`.
- `megaplan/store/db.py`: `create_migration_run()`, `update_migration_run()`, `claim_expired_migration()`.

## Orphaned `execution_lease`

Evidence id: `OPS-EXECUTION-LEASE-EXPIRED`

Symptoms:
- Migration or execution preflight reports active execution leases.
- A plan appears idle but `get_active_lease(<plan-id>)` returns a holder.

Diagnosis:
- Inspect the lease holder, `heartbeat_at`, and `expires_at`.
- Determine whether the worker process is still alive.
- Confirm the lease belongs to the expected plan and epic before clearing or waiting.

Reproduction setup:
- Acquire a lease with `FileStore.acquire_execution_lease()` or `DBStore.acquire_execution_lease()` and do not heartbeat.
- Local migration preflight coverage exists in `tests/test_multi_store.py`.

Recovery steps:
- Prefer waiting for TTL expiry.
- If the holder process is confirmed dead, run the operation again after expiry so the store ignores expired leases.
- Avoid deleting active leases for live workers.

Post-recovery validation:
- Run `pytest tests/test_multi_store.py -q`.
- Retry the blocked operation and confirm no active lease error.

Concrete references:
- `megaplan/store/file.py`: `acquire_execution_lease()`, `get_active_lease()`.
- `megaplan/store/db.py`: `acquire_execution_lease()`, `get_active_lease()`.
- `megaplan/store/multi.py`: migration preflight lease checks.

## Corrupt Or Missing Blob Payload Or Metadata

Evidence id: `OPS-BLOB-MISSING-CORRUPT`

Symptoms:
- `megaplan epic export <id>` fails with `export_failed`.
- Image references resolve incorrectly or blob metadata size/hash differs from payload.
- `LocalDirBlobStore.get(<blob-id>)` raises a missing-blob error.

Diagnosis:
- Run `megaplan epic export <id> --output /tmp/epic.tar` without `--allow-missing-blobs`.
- Inspect returned `details.errors` for `blob_id`, expected checksum, and actual error.
- For local blobs, inspect `<store-root>/blobs/<blob-id>/meta.json` and `data.*`.

Reproduction setup:
- Attach an image, delete its blob payload through `store.file.blobs.delete(image.blob_id)`, then run export.
- Covered by `tests/test_epic_cli.py::test_epic_export_missing_epic_and_missing_blob_behaviors`.

Recovery steps:
- Restore the missing payload and `meta.json` from backup if available.
- If the image is intentionally unavailable, export with `--allow-missing-blobs` and treat the warning as data-loss evidence.
- If a checksum mismatch exists, preserve both payloads and choose the one matching the image row metadata.

Post-recovery validation:
- Run `megaplan epic export <id> --output /tmp/epic.tar`.
- Run `tar -tf /tmp/epic.tar` and confirm `manifest.json` and expected `blobs/<blob-id>/payload.bin` exist.
- Run `pytest tests/test_epic_cli.py -q`.

Concrete references:
- `megaplan/store/blob.py`: `LocalDirBlobStore.get()`, `stat()`.
- `megaplan/store/export.py`: `collect_epic_export()`, `write_epic_export_tar()`.
- `megaplan/cli.py`: `handle_epic()` export branch.

## Failed Or Partial Legacy Local Plan Migration

Evidence id: `OPS-LEGACY-MIGRATION-PARTIAL`

Symptoms:
- `megaplan migrate-local-plans` reports `conflicts` or `errors`.
- Some source plan directories under `~/.megaplan/<project>/plans` are missing in the target.
- A rerun reports `changed_source` for an existing imported plan.

Diagnosis:
- Run with `--dry-run` first and compare `created`, `skipped`, `conflicts`, and `errors`.
- Inspect each target plan meta field `legacy_migration.source_project`, `source_plan_id`, and `snapshot_sha256`.
- Confirm the command used exactly one of `--source-project` or `--all-projects`.

Reproduction setup:
- Import a source plan, modify one source artifact, then rerun.
- Covered by `tests/test_epic_cli.py::test_migrate_local_plans_dry_run_does_not_write_and_import_preserves_nested_binary`.

Recovery steps:
- If the source changed intentionally, choose a new target plan id or remove the imported target plan after backing it up.
- If the source changed accidentally, restore the source directory to match the stored `snapshot_sha256` and rerun.
- For partial imports, rerun the same command; unchanged imported plans are skipped.

Post-recovery validation:
- Run `megaplan migrate-local-plans --source-home <home> --source-project <project> --target-project-dir <repo> --dry-run`.
- Confirm no conflicts or unexpected errors.
- Run `pytest tests/test_epic_cli.py -q`.

Concrete references:
- `megaplan/store/legacy_migration.py`: `migrate_local_plans()`, `_snapshot_plan_dir()`.
- `megaplan/cli.py`: `migrate-local-plans` parser and handler.

## Failed Export Or Unusable Backup Tar

Evidence id: `OPS-EXPORT-TAR-VALIDATION`

Symptoms:
- `tar -tf <backup.tar>` fails.
- `manifest.json` is missing or member checksums do not match.
- Repeated exports of unchanged state produce different tar bytes unexpectedly.

Diagnosis:
- Run `megaplan epic export <id> --output /tmp/epic.tar`.
- Inspect `manifest.json` and recompute SHA-256 for each tar member listed in `manifest.files`.
- Check whether the archive was gzip-compressed and open with `tar -tzf` when `--gzip` was used.

Reproduction setup:
- Create an epic with recursive binary artifacts and an image blob, export twice, and compare output checksums.
- Covered by `tests/test_epic_cli.py::test_epic_export_writes_deterministic_tar_and_gzip`.

Recovery steps:
- Re-export from the source store if available.
- If only a corrupt tar remains, extract readable members, compare them to `manifest.json`, and treat missing or mismatched members as data loss.
- Use `--allow-missing-blobs` only when accepting incomplete blob recovery.

Post-recovery validation:
- Run `tar -tf <backup.tar>`.
- Verify `manifest.json` checksums against actual member bytes.
- Run `pytest tests/test_epic_cli.py -q`.

Concrete references:
- `megaplan/store/export.py`: `write_epic_export_tar()`.
- `tests/test_epic_cli.py`: manifest checksum assertions.

## Cloud Chain Worker Stall

Evidence id: `OPS-CLOUD-CHAIN-STALL-MANUAL`

Symptoms:
- `megaplan cloud chain` starts but remote progress stops.
- Remote logs do not show `MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec ...`.
- A worker image builds but never starts the chain command.

Diagnosis:
- Collect provider logs and the cloud wrapper command line.
- Confirm credentials and provider region are valid.
- Confirm the generated spec contains three sprint entries for the live smoke when release signoff requires it.

Reproduction setup:
- Manual credentialed cloud evidence is required; local tests must not require provider credentials.
- Use the cloud smoke runbook added in the cloud coverage batch for live evidence capture.

Recovery steps:
- Rebuild the worker image from a clean checkout.
- Retry with a minimal three-sprint chain spec.
- If dispatch is missing the trusted container environment variable, stop the run and fix the wrapper before retrying.

Post-recovery validation:
- Capture provider run id, image digest, command line, and final chain status.
- Run local cloud wrapper tests once available in the cloud coverage batch.

Concrete references:
- `megaplan/cloud_chain.py` and cloud wrapper tests.
- `megaplan/chain.py`: `chain start --spec` local entrypoint.

## DB Artifact Binary Compatibility During File-To-DB Promotion

Evidence id: `OPS-DB-BINARY-ARTIFACT-PROMOTION`

Symptoms:
- Binary plan artifacts change bytes after migrating an epic from file to DB.
- `read_plan_artifact()` returns replacement characters or UTF-8 encoded text instead of original bytes.
- Exported DB-home artifacts differ from source FileStore artifacts.

Diagnosis:
- Compare `sha256` from `FileStore.stat_plan_artifact()` and `DBStore.stat_plan_artifact()`.
- Read both artifact payloads and compare bytes directly.
- Check that DB rows use `content_bytes` for non-UTF-8 payloads and legacy text rows still read via `content_text`.

Reproduction setup:
- Import or create a file-home epic with a nested non-UTF-8 artifact, then migrate it to DB.
- Covered by `tests/test_epic_cli.py::test_migrate_local_plans_all_projects_legacy_epic_and_db_promotion_preserve_binary` and DB artifact tests.

Recovery steps:
- If corruption occurred before the Sprint 7 migration, restore from FileStore or backup tar and rerun promotion with the current code.
- Do not repair binary data by decoding text rows with replacement characters.
- Re-export after promotion and compare checksums.

Post-recovery validation:
- Run `pytest tests/test_db_store.py -k artifact`.
- Run `pytest tests/test_multi_store.py -k "artifact or migrate"`.
- Run `megaplan epic export <id> --output /tmp/db-home.tar` and verify artifact member checksums.

Concrete references:
- `megaplan/store/db.py`: `write_plan_artifact()`, `read_plan_artifact()`, `copy_plan_artifacts_idempotent()`.
- `megaplan/store/multi.py`: `_artifact_model()`, `_copy_plan_artifacts_to_db()`.
- `supabase/migrations/202605050003_plan_artifact_binary_content.sql`.
