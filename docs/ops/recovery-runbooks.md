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
- Run `megaplan migrate-local-plans --source-home <home> --source-project <project> --project-dir <repo> --dry-run`.
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
- **First, run the supervisor:** `megaplan cloud supervise --chain` to get a safe diagnosis of runner liveness, current milestone/plan state, last log activity, sync state, and next action. The supervisor may safely restart a dead `megaplan-chain` tmux session or advance past a merged PR, but it will refuse to act when a human prerequisite is required, a quality gate is failing, or a PR is still open — it will surface those refusal reasons clearly and leave manual recovery as the next step.
- If the supervisor refused to act, proceed with the manual recovery steps below.
- Rebuild the worker image from a clean checkout.
- Retry with a minimal three-sprint chain spec.
- If dispatch is missing the trusted container environment variable, stop the run and fix the wrapper before retrying.

Post-recovery validation:
- Capture provider run id, image digest, command line, and final chain status.
- Run local cloud wrapper tests once available in the cloud coverage batch.

Concrete references:
- `megaplan/cloud_chain.py` and cloud wrapper tests.
- `megaplan/chain.py`: `chain start --spec` local entrypoint.

## Cloud Supervisor Tick

Evidence id: `OPS-CLOUD-SUPERVISOR`

Symptoms:
- `megaplan cloud supervise --chain` returns a refusal status (`supervisor_blocked`, `refused_reason` populated) without explanation of what the refusal means.
- An operator does not know whether it is safe to restart a chain runner or advance past a merged PR.
- The environment is missing the `megaplan-chain` tmux session, a quality gate is blocking, or a human prerequisite is unmet, and no safe restart path is clear.

Diagnosis:
- Run `megaplan cloud supervise --chain --cloud-yaml <yaml> [--remote-spec <path>]` to produce a one-shot tick report. The JSON stdout includes `effective_status`, `next_action`, `acted`, `refused_reason`, `runner`, `sync`, `pr`, and `logs` fields.
- Inspect `effective_status` and `next_action` to understand the chain's classified state and the supervisor's verdict.
- If `acted` is `false` and `refused_reason` is non-null, the supervisor detected a condition that requires human intervention (see refusal cases below).
- Examine the `runner` section for tmux session liveness and the `logs` section for `chain_log` mtime/size to gauge recent activity.

Reproduction setup:
- A cloud provider with `ssh_exec` capability is required.
- Chain state that triggers each refusal path: (a) a chain with a human prerequisite policy of `required` and an unmet action, (b) a chain with a validation policy of `required` and a failing quality gate, (c) a chain awaiting PR merge where `gh pr view --json state` reports `OPEN`, (d) a chain whose `megaplan-chain` tmux session is dead or missing (stale bookkeeping).
- Local tests in `tests/test_cloud_chain_status.py` cover each classification and action path without live cloud credentials.

Recovery steps:
- **Always run the supervisor first** to get a safe diagnosis before taking manual action. The supervisor is not a destructive repair tool — it will never force-push, reset branches, delete branches, invent human approvals, or bypass quality gates.
- **If the supervisor reports `acted: true`:** it has safely restarted a dead runner or advanced the chain past a merged PR. Re-run `megaplan cloud status --chain` and the supervisor tick to confirm the chain is now in a healthy state.
- **If the supervisor reports `acted: false` with `refused_reason`:**
  - *Human prerequisite blocked:* Use `megaplan user-action resolve <action-id>` or the relevant `chain override` command to satisfy the prerequisite, then re-run the supervisor.
  - *Quality gate blocked:* Address the failing validation (fix code, update tests, or accept with documented debt), then re-run the supervisor.
  - *PR not merged:* Wait for the PR merge or manually merge it, then re-run the supervisor; the supervisor will automatically advance past a merged PR on the next tick.
  - *Provider lacks ssh_exec / sync unavailable:* The supervisor cannot act without a remote execution channel; verify provider configuration and credentials.
  - *Runner alive but bookkeeping stale:* The chain state file is out of date but the runner is still active; inspect the runner directly rather than restarting.
  - *Stale bookkeeping restart failed:* The supervisor attempted to restart the tmux session but the remote command failed; check the remote host connectivity and tmux installation.
- **Manual approval boundary:** The supervisor will never green-light a blocked human prerequisite, waive a failing quality gate, or close/merge a PR. Those decisions remain with human operators.

Post-recovery validation:
- Re-run `megaplan cloud status --chain` and confirm `effective_status` is `running` or `complete`.
- Re-run the supervisor tick and confirm `acted` is `false` with `next_action` of `noop` (running chain) or `done` (complete chain) — no further action needed.
- Verify the `runner.session` is `megaplan-chain` and the `chain_log` mtime advances after one tick.
- Run `pytest tests/test_cloud_chain_status.py tests/test_cloud_chain_wrapper.py -q`.

Concrete references:
- `megaplan/cloud/supervise.py`: `cloud_supervise_tick()`, `_tick_report()`, safe action policy constants (`READ_ONLY_STATUSES`, `BLOCKED_REFUSAL_REASONS`).
- `megaplan/cloud/cli.py`: `_run_supervise_tick()`, `cloud_chain_status_payload()`, `_chain_start_command()`, `_tmux_chain_restart_command()`.
- `megaplan/chain.py`: `_capture_sync_state()`, `effective_chain_policy()`.
- `tests/test_cloud_chain_status.py`: supervisor tick test suite (test_supervise_tick_running_noop, test_supervise_tick_complete_done, test_supervise_tick_human_prerequisite_blocked, test_supervise_tick_quality_gate_blocked, test_supervise_tick_stale_dead_restart, test_supervise_tick_awaiting_pr_merged_advance, test_supervise_tick_awaiting_pr_unmerged_block).

## M1 Cloud-Safe Repair Substrate — Rollback and Preflight

Evidence id: `OPS-M1-REPAIR-ROLLBACK`

The M1 cloud-safe repair substrate adds observe-only resolver evidence, shared
repair locking, canonical redaction, feature flags, and a human-blocker
classifier.  This runbook covers rollback and preflight operations for the M1
substrate without expanding into later autonomous repair layers (M2+).

### Flag Disablement

All behaviour-changing flags are **off by default**.  The observe-only resolver
and redaction are **on by default** because they are additive diagnostics and
security boundaries.

| Flag | Env Var | M1 Default | Purpose |
|---|---|---|---|
| resolver-observe | `ARNOLD_RESOLVER_OBSERVE` | `1` (on) | Capture resolver evidence alongside legacy decisions. |
| resolver-enforcement | `ARNOLD_RESOLVER_ENFORCEMENT` | `0` (off) | Make resolver output authoritative for target selection / state clearing. |
| escalation-ledger | `ARNOLD_ESCALATION_LEDGER` | `0` (off) | Enable append-only escalation ledger writes. |
| autonomy | `ARNOLD_AUTONOMY` | `0` (off) | Enable autonomous trigger / meta / auditor actions. |
| redaction | `ARNOLD_REDACTION_ENABLED` | `1` (on) | Redact secrets from persisted and outbound artifacts. |

To disable the observe-only resolver (return to purely legacy behaviour):

```bash
export ARNOLD_RESOLVER_OBSERVE=0
```

To opt out of redaction (emergency debug only — redacted data may contain
secrets):

```bash
export ARNOLD_REDACTION_ENABLED=0
```

To selectively enable an off-by-default flag for testing:

```bash
export ARNOLD_ESCALATION_LEDGER=1
export ARNOLD_AUTONOMY=0          # keep autonomy gated
```

All flags accept `0`, `false`, `no`, or `off` (case-insensitive) to disable.
Unset or empty values use the M1 default.  The centralised flag module is
`arnold_pipelines/megaplan/cloud/feature_flags.py` — all consumers import
from there rather than calling `os.getenv` directly.

### Wrapper Refresh / Restore

M1 introduces shared Python modules (`repair_contract`, `repair_lock`,
`current_target`, `human_blockers`, `redact`, `feature_flags`) alongside
updated wrappers under `arnold_pipelines/megaplan/cloud/wrappers/`.

After deploying an Arnold source update, refresh the executable wrappers on
the cloud machine:

```bash
# From the Arnold editable-install checkout
cd /workspace/arnold

# Copy each wrapper to /usr/local/bin and make executable
for wrapper in \
  arnold-repair-loop \
  arnold-watchdog \
  arnold-progress-auditor \
  arnold-discord-dm \
  arnold-kimi-goal-operator; do
  cp "arnold_pipelines/megaplan/cloud/wrappers/$wrapper" "/usr/local/bin/$wrapper"
  chmod +x "/usr/local/bin/$wrapper"
done
```

**Important:** The editable-install sync (watchdog source sync) updates the
Python package under the Arnold checkout but does **not** refresh
`/usr/local/bin` wrappers.  Wrapper redeployment is a manual step after every
merge that changes wrapper scripts or the shared cloud Python modules they
depend on via `PYTHONPATH`.

To restore a known-good wrapper from git (discard local edits):

```bash
cd /workspace/arnold
git checkout <known-good-ref> -- arnold_pipelines/megaplan/cloud/wrappers/
# Then re-copy to /usr/local/bin as above
```

Verify the wrapper is on the expected version:

```bash
head -5 /usr/local/bin/arnold-repair-loop
md5sum /usr/local/bin/arnold-repair-loop
```

### Old Sidecar Compatibility Checks

M1 preserves the existing mutable sidecar format.  The following artifacts are
the canonical compatibility sources:

| Artifact | Path | Writer |
|---|---|---|
| Repair data | `<marker_dir>/repair-data/<session>.repair-data.json` | `arnold-repair-loop` |
| Needs-human marker | `<marker_dir>/repair-data/<session>.needs-human.json` | `arnold-repair-loop` |
| Repair progress | `<marker_dir>/<session>.repair-progress.json` | `arnold-repair-loop` |
| Chain-health progress | `<marker_dir>/<session>.chain-health.progress.json` | `arnold-watchdog` |
| Session marker | `<marker_dir>/<session>.json` | `arnold-watchdog` |

Default `<marker_dir>`: `/workspace/.megaplan/cloud-sessions`

To check that old sidecars are still readable by M1 consumers:

```bash
# Validate a repair-data file against the M1 contract
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_contract import load_json, validate_repair_data
data = load_json('/workspace/.megaplan/cloud-sessions/repair-data/<session>.repair-data.json')
errors = validate_repair_data(data)
if errors:
    print('VALIDATION ERRORS:', errors)
else:
    print('Sidecar valid under M1 contract')
"

# Inspect a needs-human marker for legacy key presence
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_contract import load_json
nh = load_json('/workspace/.megaplan/cloud-sessions/repair-data/<session>.needs-human.json')
print('Keys present:', sorted(nh.keys()))
print('Plan name:', nh.get('plan_name') or nh.get('current_plan_name'))
"

# Check that needs-human markers include the M1 additive current-pointer fields
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_contract import load_json
nh = load_json('/workspace/.megaplan/cloud-sessions/repair-data/<session>.needs-human.json')
for key in ('current_plan_name', 'target_id', 'authoritative_source', 'current'):
    present = key in nh
    print(f'{key}: {\"present\" if present else \"missing (legacy-only sidecar)\"}')
"
```

The M1 substrate adds additive `current_plan_name`, `target_id`,
`authoritative_source`, and nested `current` fields to needs-human markers.
These are **additive** — legacy watchdog readers that only inspect `plan_name`
or `summary` are unaffected.

### Repair Lock Drain / Inspection

M1 uses an atomic `mkdir` lock directory with owner metadata.  The lock lives
at:

```
<marker_dir>/<session>.repair-loop.lock/
└── owner.json
```

Default: `/workspace/.megaplan/cloud-sessions/<session>.repair-loop.lock/`

**Inspect a repair lock without mutating it:**

```bash
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_lock import inspect_repair_lock
import os

lock_dir = '/workspace/.megaplan/cloud-sessions/<session>.repair-loop.lock'
result = inspect_repair_lock(lock_dir, is_pid_live=lambda pid: os.kill(pid, 0) if pid > 0 else False)
print(f'Status: {result.status}')
if result.owner:
    print(f'Owner PID: {result.owner.get(\"pid\")}')
    print(f'Started: {result.owner.get(\"started_at\")}')
    print(f'Timeout (s): {result.owner.get(\"timeout_seconds\")}')
if result.stale_evidence:
    print(f'Stale reasons: {result.stale_evidence.get(\"reasons\")}')
"
```

**Interpretation:**

| Status | Meaning | Action |
|---|---|---|
| `missing` | No lock exists; repair is free to start. | Nothing needed. |
| `acquired` | The current process holds the lock. | Normal — repair is in progress. |
| `busy` | Another live process holds the lock. | Wait for the holder to finish. Do **not** delete the lock directory. |
| `stale` | Lock exists but owner PID is dead or timeout expired. | Record evidence before manual cleanup. See stale-lock procedure below. |

**Stale-lock evidence preservation and cleanup:**

The M1 lock subsystem **never silently deletes stale locks**.  A stale lock is
evidence of a potential race condition or crashed repair attempt.  Before
removing a stale lock:

```bash
# 1. Capture evidence
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_lock import inspect_repair_lock
import json, os
lock_dir = '/workspace/.megaplan/cloud-sessions/<session>.repair-loop.lock'
result = inspect_repair_lock(lock_dir, is_pid_live=lambda pid: os.kill(pid, 0) if pid > 0 else False)
print(json.dumps({'status': result.status, 'owner': result.owner, 'stale_evidence': result.stale_evidence}, indent=2))
" > /tmp/stale-lock-evidence-<session>.json

# 2. Confirm no active repair loop is running
ps aux | grep arnold-repair-loop | grep -v grep

# 3. Only then remove
rm -rf /workspace/.megaplan/cloud-sessions/<session>.repair-loop.lock
```

To drain (wait for a busy lock to clear):

```bash
# Poll every 10 seconds for up to 5 minutes
for i in $(seq 1 30); do
  if [[ ! -d /workspace/.megaplan/cloud-sessions/<session>.repair-loop.lock ]]; then
    echo "Lock cleared after $((i * 10))s"
    break
  fi
  sleep 10
done
```

### Watchdog Restart

The resident watchdog runs inside a tmux session named `watchdog` on the cloud
container.  To restart it:

```bash
# 1. Attach to the container (provider-specific)
#    For SSH provider:  ssh <host> docker exec -it <container> bash
#    For local provider: docker compose -p <project> exec agent bash

# 2. Kill the existing watchdog tmux session
tmux kill-session -t watchdog 2>/dev/null || true
#    Alternatively, kill the watchdog process directly:
pkill -f '/usr/local/bin/arnold-watchdog' 2>/dev/null || true

# 3. Wait for cleanup
sleep 2

# 4. Start a fresh watchdog session
setsid bash -lc '/usr/local/bin/arnold-watchdog >> /workspace/watchdog-supervisor.log 2>&1' \
  </dev/null >/dev/null 2>&1 &

# 5. Verify the watchdog is running
tmux ls 2>/dev/null | grep watchdog
ps aux | grep arnold-watchdog | grep -v grep

# 6. Trigger an immediate one-shot scan to confirm health
/usr/local/bin/arnold-watchdog --once
```

The watchdog writes to `/workspace/watchdog.log` (scan logs) and
`/workspace/watchdog-report.json` (latest structured report).  Inspect these
after restart:

```bash
tail -20 /workspace/watchdog.log
python3 -m json.tool /workspace/watchdog-report.json | head -40
```

Key watchdog env vars that affect restart behaviour:

| Variable | Default | Meaning |
|---|---|---|
| `CLOUD_WATCHDOG_INTERVAL_SECS` | `3600` | Seconds between scans. |
| `CLOUD_WATCHDOG_LOG` | `/workspace/watchdog.log` | Scan log path. |
| `CLOUD_WATCHDOG_REPORT_PATH` | `/workspace/watchdog-report.json` | Latest report. |
| `ARNOLD_REPAIR_TRIGGER_ENABLED` | `0` | Must be `1` for repair dispatch. |
| `CLOUD_WATCHDOG_PUSH_REPAIRS` | `0` | Set to `1` to push repair commits. |
| `CLOUD_WATCHDOG_SYNC_ENABLED` | `1` | Set to `0` to skip editable-install sync. |

### Validation Commands

After any flag change, wrapper refresh, lock cleanup, or watchdog restart, run
the M1 substrate test suite to confirm the substrate is healthy:

```bash
cd /workspace/arnold

# Core M1 contract and lock tests
pytest tests/cloud/test_repair_contract.py tests/cloud/test_repair_lock.py -v

# Feature flag defaults and opt-out behaviour
pytest tests/cloud/test_feature_flags.py -v

# Redaction (security boundary)
pytest tests/cloud/test_redaction.py -v

# Current-target resolver evidence
pytest tests/cloud/test_current_target.py -v

# Human-blocker classifier
pytest tests/cloud/test_human_blockers.py -v

# Wrapper integration (repair loop, watchdog, auditor, discord)
pytest tests/cloud/test_watchdog_wrappers.py -v --timeout=120

# Recurrence wiring
pytest tests/cloud/test_repair_recurrence.py -v

# Discord DM redaction and rendering
pytest tests/arnold_pipelines/megaplan/test_discord_dm.py -v

# Full M1 substrate (all cloud tests)
pytest tests/cloud/ tests/arnold_pipelines/megaplan/test_discord_dm.py -v --timeout=120
```

A healthy M1 substrate should pass all tests except pre-existing baseline
failures.  If `test_watchdog_manual_review_plan_state_reports_needs_human_not_complete`
or `test_watchdog_manual_review_chain_state_reports_needs_human_not_complete`
fail, those are known env-sensitive baseline failures unrelated to M1.

### Concrete References

- Flags: `arnold_pipelines/megaplan/cloud/feature_flags.py` — `resolver_observe_enabled()`, `resolver_enforcement_enabled()`, `escalation_ledger_enabled()`, `autonomy_enabled()`, `redaction_enabled()`.
- Contract: `arnold_pipelines/megaplan/cloud/repair_contract.py` — `load_json()`, `atomic_write_json()`, `validate_repair_data()`, `save_repair_data()`.
- Lock: `arnold_pipelines/megaplan/cloud/repair_lock.py` — `acquire_repair_lock()`, `release_repair_lock()`, `inspect_repair_lock()`, `repair_lock()` context manager.
- Resolver: `arnold_pipelines/megaplan/cloud/current_target.py` — `resolve_current_target()`.
- Blockers: `arnold_pipelines/megaplan/cloud/human_blockers.py` — `classify_needs_human_blocker()`, `write_needs_human_marker_payload()`, `EscalationLedgerWriter`.
- Redaction: `arnold_pipelines/megaplan/cloud/redact.py` — `redact_text()`, `redact_payload()`, `redact_stream()`, `redaction_enabled()`.
- Wrappers: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`, `arnold-repair-loop`, `arnold-progress-auditor`, `arnold-discord-dm`.
- Tests: `tests/cloud/test_repair_contract.py`, `test_repair_lock.py`, `test_feature_flags.py`, `test_redaction.py`, `test_current_target.py`, `test_human_blockers.py`, `test_watchdog_wrappers.py`, `test_repair_recurrence.py`.

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

## M4 Human Workflow And Cloud Hardening — Runbook

Evidence id: `OPS-M4-HUMAN-WORKFLOW`

The M4 milestone turns escalation from "we sent a DM" into an answerable,
authorized, resumable workflow with delivery state, current-target matching,
supersession, confirmation gates, and an append-only escalation lifecycle
ledger.  This runbook covers preflight, safe testing, inspection, rollback,
and sidecar compatibility for the M4 human workflow.

### Preflight

Before enabling M4 escalation in production, verify the substrate is healthy:

```bash
cd /workspace/arnold

# 1. Core M4 contract, lifecycle, and pointer tests
pytest tests/cloud/test_repair_contract.py tests/cloud/test_human_blockers.py -v

# 2. Discord DM rendering and redaction
pytest tests/arnold_pipelines/megaplan/test_discord_dm.py -v

# 3. Wrapper integration (repair-loop + watchdog)
pytest tests/cloud/test_watchdog_wrappers.py -v

# 4. Resident authorization and escalation reply handling
pytest tests/resident/test_authorizer.py tests/resident/test_escalation_reply.py -v

# 5. Resident Discord outbound parsing
pytest tests/resident/test_discord_outbound.py -v

# 6. All changed modules compile cleanly
python -c "
import compileall
compileall.compile_dir('arnold_pipelines/megaplan/cloud', quiet=1)
compileall.compile_dir('arnold_pipelines/megaplan/resident', quiet=1)
print('All modules compile.')
"
```

A healthy M4 substrate passes all tests except pre-existing baseline failures.

Confirm that wrapper executables are on the M4 version after deployment:

```bash
md5sum /usr/local/bin/arnold-repair-loop /usr/local/bin/arnold-watchdog
head -5 /usr/local/bin/arnold-repair-loop
head -5 /usr/local/bin/arnold-watchdog
```

### Flag Enablement

M4 lifecycle writes are gated behind feature flags.  All behavior-changing
flags remain **off by default**.  The escalation ledger flag controls the new
append-only lifecycle sidecar:

| Flag | Env Var | M4 Default | Purpose |
|---|---|---|---|
| escalation-ledger | `ARNOLD_ESCALATION_LEDGER` | `0` (off) | Enable append-only `escalations/escalations.jsonl` lifecycle writes. |

Enable the escalation ledger for a test run:

```bash
export ARNOLD_ESCALATION_LEDGER=1
```

The flag is consumed centrally in
`arnold_pipelines/megaplan/cloud/feature_flags.py` via
`escalation_ledger_enabled()`.  When disabled, the `EscalationLedgerWriter`
silently no-ops all lifecycle writes — no records are created and no sidecar
files are touched.

The resident escalation reply path uses its own configuration via
`escalation_repair_data_dir` and `escalation_repair_lock_dir` in
`ResidentConfig` — these must point to the same repair-data directory the
cloud wrappers use so the resident can read delivered escalation records and
acquire the shared repair lock.

### Safe Test Escalation

Test M4 escalation without real Discord delivery by exercising the lifecycle
paths directly with the escalation ledger enabled:

```bash
cd /workspace/arnold

# Enable the ledger and run the human-blocker lifecycle tests
ARNOLD_ESCALATION_LEDGER=1 pytest tests/cloud/test_human_blockers.py -v

# Test the pointer supersession and clearing helpers
ARNOLD_ESCALATION_LEDGER=1 pytest tests/cloud/test_human_blockers.py -v \
  -k "supersede or clear"

# Verify the wrapper escalation paths (repair-loop and watchdog)
ARNOLD_ESCALATION_LEDGER=1 pytest tests/cloud/test_watchdog_wrappers.py -v

# Test resident-side authorization and escalation reply without live Discord
pytest tests/resident/test_authorizer.py tests/resident/test_escalation_reply.py -v
```

To manually simulate an escalation lifecycle for a session without running
the full repair loop:

```bash
PYTHONPATH=/workspace/arnold ARNOLD_ESCALATION_LEDGER=1 python3 -c "
from arnold_pipelines.megaplan.cloud.human_blockers import (
    EscalationLedgerWriter, compute_escalation_id
)
from pathlib import Path
import tempfile, os

sidecar = Path(tempfile.mkdtemp(prefix='m4-test-'))
writer = EscalationLedgerWriter(sidecar_dir=str(sidecar))
writer.enable(str(sidecar))

session = 'test-session-001'
target_id = 'plan:m4-human-workflow-and-cloud'
esc_id = compute_escalation_id(session, target_id=target_id)

# Opened
writer.write_opened(session, escalation_id=esc_id, target_id=target_id)

# Delivered (simulated — no real Discord call)
writer.write_delivered(session, escalation_id=esc_id,
    channel_id='test-channel', message_ids=['msg-1', 'msg-2'])

# Answered
writer.write_answered(session, escalation_id=esc_id,
    responder_user_id='test-user', channel_id='test-channel', message_id='msg-3')

# Resume attempted
writer.write_resume_attempted(session, escalation_id=esc_id,
    action='cloud_resume', resume_status='dispatched')

# Inspect the sidecar
sidecar_file = sidecar / 'escalations' / 'escalations.jsonl'
print(f'Sidecar: {sidecar_file}')
for line in sidecar_file.read_text().strip().split(chr(10)):
    print(line)
"
```

### Dry-Run Discord Delivery Evidence

The `arnold-discord-dm` wrapper and `send_discord_dm()` helper return
redacted delivery evidence without real Discord calls when the bot token is
unset or the helper is invoked in test mode.  Verify the evidence shape
without sending a real DM:

```bash
cd /workspace/arnold

# Run the Discord DM tests (these mock HTTP and verify redaction)
pytest tests/arnold_pipelines/megaplan/test_discord_dm.py -v

# Inspect what send_discord_dm returns on success:
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.discord_dm import send_discord_dm
# Without a real token this will fail at the HTTP layer, but the
# evidence structure is verified by the test suite above.
print('Delivery evidence shape: {message_ids, channel_id, message_count}')
print('Redaction is applied BEFORE any outbound send.')
print('Tokens, headers, and raw secret-bearing payloads are never returned.')
"
```

The returned delivery evidence is the **only** source of truth for whether an
escalation was answerable.  Webhook delivery is ancillary reporting only and
does not satisfy the M4 human escalation workflow because webhooks cannot map
replies to `escalation_id`.

To inspect delivery evidence that was already written to the ledger:

```bash
# Read delivered records for a session
PYTHONPATH=/workspace/arnold python3 -c "
import json
from pathlib import Path

sidecar = Path('/workspace/.megaplan/cloud-sessions/repair-data/escalations/escalations.jsonl')
if sidecar.exists():
    for line in sidecar.read_text().strip().split(chr(10)):
        rec = json.loads(line)
        if rec.get('event') == 'delivered':
            print(json.dumps(rec, indent=2))
else:
    print('No escalation sidecar found.')
"
```

### Non-Secret Inspection

All M4 lifecycle records and delivery evidence are redacted by the canonical
`redact_payload()` before persistence.  To safely inspect escalation state
without risk of exposing secrets:

```bash
cd /workspace/arnold

# 1. List all escalation lifecycle records for a session (redacted)
PYTHONPATH=/workspace/arnold python3 -c "
import json
from pathlib import Path

sidecar_dir = Path('/workspace/.megaplan/cloud-sessions/repair-data')
esc_file = sidecar_dir / 'escalations' / 'escalations.jsonl'
if esc_file.exists():
    for line in esc_file.read_text().strip().split(chr(10)):
        rec = json.loads(line)
        # All records are pre-redacted — safe to print
        print(f\"event={rec.get('event')} escalation_id={rec.get('escalation_id')} session={rec.get('session')}\")
else:
    print('No escalation records.')
"

# 2. Inspect a needs-human pointer without mutating it
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_contract import load_json
nh = load_json('/workspace/.megaplan/cloud-sessions/repair-data/<session>.needs-human.json')
print('Keys:', sorted(nh.keys()))
print('Plan:', nh.get('current_plan_name') or nh.get('plan_name'))
print('Target:', nh.get('target_id'))
print('Escalation ID:', nh.get('escalation_id'))
print('Delivered channel:', nh.get('discord_escalation', {}).get('channel_id'))
"

# 3. Inspect escalation records for a specific escalation_id
PYTHONPATH=/workspace/arnold python3 -c "
import json
from pathlib import Path

esc_id = '<escalation-id>'  # e.g. esc-a1b2c3d4e5f6g7h8
sidecar = Path('/workspace/.megaplan/cloud-sessions/repair-data/escalations/escalations.jsonl')
if sidecar.exists():
    for line in sidecar.read_text().strip().split(chr(10)):
        rec = json.loads(line)
        if rec.get('escalation_id') == esc_id:
            print(json.dumps(rec, indent=2))
"

# 4. Audit authorization denials (resident-side)
#    Check the resident audit log for escalation_answer_unauthorized events.
#    The resident audit sink records denials with category='escalation' and
#    event_type='escalation_answer_unauthorized'.
```

**Safety note:** Never disable redaction (`ARNOLD_REDACTION_ENABLED=0`) for
routine inspection.  Redacted data may contain secrets.  Only disable
redaction in emergency debug scenarios where you explicitly accept the risk of
secret exposure.

### Pointer Supersession And Clearing vs Append-Only History

M4 maintains a strict separation between mutable pointers and the append-only
ledger:

| Artifact | Path | Behavior |
|---|---|---|
| Needs-human pointer (mutable) | `<marker_dir>/repair-data/<session>.needs-human.json` | Rewritten on supersession; deleted on clear. |
| Escalation ledger (append-only) | `<marker_dir>/repair-data/escalations/escalations.jsonl` | Never deleted; records accumulate forever. |
| Incident records (compatibility) | `<marker_dir>/repair-data/incidents/incidents.jsonl` | Existing `blocker_classified` records preserved. |

Default `<marker_dir>`: `/workspace/.megaplan/cloud-sessions`

**Supersede a pointer (new target, old escalation recorded as superseded):**

```bash
PYTHONPATH=/workspace/arnold ARNOLD_ESCALATION_LEDGER=1 python3 -c "
from arnold_pipelines.megaplan.cloud.human_blockers import (
    supersede_needs_human_marker, EscalationLedgerWriter, compute_escalation_id
)
from pathlib import Path

sidecar_dir = Path('/workspace/.megaplan/cloud-sessions/repair-data')
pointer_path = sidecar_dir / '<session>.needs-human.json'
repair_data_path = sidecar_dir / '<session>.repair-data.json'

writer = EscalationLedgerWriter(sidecar_dir=str(sidecar_dir))
writer.enable(str(sidecar_dir))

repair_payload = {
    'session': '<session>',
    'plan_name': '<new-plan-name>',
    'target_id': '<new-target-id>',
}

new_marker = supersede_needs_human_marker(
    pointer_path,
    repair_payload,
    repair_data_path=repair_data_path,
    discord_status='delivered',
    previous_escalation_id='esc-<old-id>',
    superseded_by='esc-<new-id>',
    ledger_writer=writer,
    reason='New escalation for updated target',
)
print('New pointer:', new_marker.get('target_id'))
print('Old escalation superseded in ledger — records preserved.')
"
```

**Clear a pointer (remove mutable marker, ledger untouched):**

```bash
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.human_blockers import clear_needs_human_marker

removed = clear_needs_human_marker(
    '/workspace/.megaplan/cloud-sessions/repair-data/<session>.needs-human.json'
)
print(f'Pointer removed: {removed}')
print('Ledger records are NOT affected by clearing the mutable pointer.')
"
```

**Key invariant:** Clearing or superseding the mutable pointer **never**
deletes or modifies records in the append-only `escalations/escalations.jsonl`
ledger.  The ledger is the durable audit trail; the pointer is a convenience
for current-target discovery.

### Rollback

M4 rollback reverts the wrapper scripts, shared Python modules, and flag
state to the pre-M4 behavior.  The escalation ledger sidecar is append-only
and can be left in place — it does not affect pre-M4 consumers.

**Step 1: Restore pre-M4 wrappers.**

```bash
cd /workspace/arnold
# Restore wrappers from the pre-M4 baseline commit
git checkout 437de55d8fa413a0c022f5d63008b800451d23aa -- \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog

# Re-copy to /usr/local/bin
for wrapper in arnold-repair-loop arnold-watchdog; do
  cp "arnold_pipelines/megaplan/cloud/wrappers/$wrapper" "/usr/local/bin/$wrapper"
  chmod +x "/usr/local/bin/$wrapper"
done
```

**Step 2: Restore pre-M4 Python modules.**

```bash
cd /workspace/arnold
# Restore cloud modules (human_blockers, repair_contract, feature_flags)
git checkout 437de55d8fa413a0c022f5d63008b800451d23aa -- \
  arnold_pipelines/megaplan/cloud/human_blockers.py \
  arnold_pipelines/megaplan/cloud/repair_contract.py \
  arnold_pipelines/megaplan/cloud/feature_flags.py

# Restore resident modules (auth, config, escalations, runtime, discord, agent_loop)
git checkout 437de55d8fa413a0c022f5d63008b800451d23aa -- \
  arnold_pipelines/megaplan/resident/auth.py \
  arnold_pipelines/megaplan/resident/config.py \
  arnold_pipelines/megaplan/resident/escalations.py \
  arnold_pipelines/megaplan/resident/runtime.py \
  arnold_pipelines/megaplan/resident/discord.py \
  arnold_pipelines/megaplan/resident/agent_loop.py

# Restore Discord DM helper
git checkout 437de55d8fa413a0c022f5d63008b800451d23aa -- \
  arnold_pipelines/megaplan/discord_dm.py
```

**Step 3: Disable M4 flags.**

```bash
unset ARNOLD_ESCALATION_LEDGER
# Or explicitly disable:
export ARNOLD_ESCALATION_LEDGER=0
```

**Step 4: Verify rollback.**

```bash
cd /workspace/arnold
# Pre-M4 tests should still pass (excluding known baseline failures)
pytest tests/cloud/test_repair_contract.py tests/cloud/test_feature_flags.py -v

# Wrappers should be on the pre-M4 version
md5sum /usr/local/bin/arnold-repair-loop /usr/local/bin/arnold-watchdog
```

**Note:** The `escalations/escalations.jsonl` sidecar file is not removed
during rollback — it is an append-only audit artifact that pre-M4 consumers
ignore.  If disk space is a concern, archive the file before removing it:

```bash
mv /workspace/.megaplan/cloud-sessions/repair-data/escalations/escalations.jsonl \
   /workspace/.megaplan/cloud-sessions/repair-data/escalations/escalations.jsonl.$(date +%Y%m%d).bak
```

### Old Sidecar Compatibility

M4 introduces a new `escalations` sidecar kind alongside the existing
`events`, `incidents`, and `attempts` sidecars.  Existing sidecars are
**untouched** by M4 changes.

**Existing sidecar artifacts (unchanged by M4):**

| Artifact | Path | Status |
|---|---|---|
| Repair events | `<marker_dir>/repair-data/events/events.jsonl` | Preserved — no M4 changes. |
| Incidents | `<marker_dir>/repair-data/incidents/incidents.jsonl` | Preserved — `blocker_classified` records remain compatible. |
| Attempts | `<marker_dir>/repair-data/attempts/attempts.jsonl` | Preserved — no M4 changes. |
| Escalations (new) | `<marker_dir>/repair-data/escalations/escalations.jsonl` | New in M4 — append-only, ignored by pre-M4 consumers. |
| Needs-human marker | `<marker_dir>/repair-data/<session>.needs-human.json` | Additive `escalation_id`, `target_id`, `discord_escalation` fields. |
| Repair data | `<marker_dir>/repair-data/<session>.repair-data.json` | No M4 schema changes. |

Default `<marker_dir>`: `/workspace/.megaplan/cloud-sessions`

**Verify old sidecars are still readable after M4 deployment:**

```bash
cd /workspace/arnold

# 1. Existing incident/event/attempt sidecars are unaffected
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_contract import (
    _SIDECAR_KINDS, append_jsonl_record
)
print('Registered sidecar kinds:', _SIDECAR_KINDS)
# 'escalations' is present alongside 'events', 'incidents', 'attempts'
"

# 2. Old blocker_classified records remain valid
PYTHONPATH=/workspace/arnold python3 -c "
import json
from pathlib import Path
incidents = Path('/workspace/.megaplan/cloud-sessions/repair-data/incidents/incidents.jsonl')
if incidents.exists():
    for line in incidents.read_text().strip().split(chr(10)):
        rec = json.loads(line)
        print(f\"kind={rec.get('kind')} session={rec.get('session')}\")
else:
    print('No incident records — nothing to check.')
"

# 3. Needs-human markers carry additive M4 fields alongside legacy keys
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.cloud.repair_contract import load_json
nh = load_json('/workspace/.megaplan/cloud-sessions/repair-data/<session>.needs-human.json')
legacy_keys = {'plan_name', 'summary', 'session', 'needs_human'}
m4_keys = {'escalation_id', 'target_id', 'discord_escalation', 'current_plan_name'}
print('Legacy keys present:', sorted(k for k in legacy_keys if k in nh))
print('M4 keys present:', sorted(k for k in m4_keys if k in nh))
print('All keys:', sorted(nh.keys()))
# Legacy readers that only inspect 'plan_name' or 'summary' are unaffected
# by the additive M4 fields.
"
```

**Compatibility guarantees:**

- Pre-M4 consumers that read `incidents/incidents.jsonl` are unaffected —
  `blocker_classified` records continue to be written by `write_classification()`.
- Pre-M4 consumers that read `needs-human.json` pointers see the same
  `plan_name`, `summary`, and `needs_human` keys they always did.
- The new `escalations/escalations.jsonl` sidecar is ignored by pre-M4
  consumers — it is a pure add.
- The `append_escalation_record()` helper uses the same `append_jsonl_record()`
  path as existing sidecars — sequence numbering and timestamp injection are
  identical.

### Resident-Side Escalation Inspection

The resident authorization and escalation reply path uses the shared
repair-data directory.  To inspect resident-side escalation state:

```bash
cd /workspace/arnold

# Check resident config for escalation paths
PYTHONPATH=/workspace/arnold python3 -c "
from arnold_pipelines.megaplan.resident.config import ResidentConfig
cfg = ResidentConfig.from_env()
print(f'escalation_repair_data_dir: {cfg.escalation_repair_data_dir}')
print(f'escalation_repair_lock_dir: {cfg.escalation_repair_lock_dir}')
"

# Run resident authorization and escalation reply tests
pytest tests/resident/test_authorizer.py tests/resident/test_escalation_reply.py -v
```

The resident validates these conditions before any state mutation on an
escalation answer:

1. **Authorization:** The responding user and channel must match the
   delivered escalation's `responder_user_id` and `channel_id` from the
   ledger.
2. **Current-target match:** The escalation must not be stale or superseded —
   the pointer's current `target_id` must match the escalation's `target_id`.
3. **Confirmation (for `escalation_resolve`):** High-impact resolution
   requires the responder to confirm with the exact confirmation phrase.
4. **Repair-lock acquisition:** The shared repair lock must be acquired
   before any pointer mutation or resume dispatch.

Denials are audited as `escalation_answer_unauthorized` system events.
Unconfirmed free text never mutates state — it only produces a confirmation
prompt.

### Validation Commands

After any M4 flag change, wrapper refresh, pointer supersession, or resident
reconfiguration, run the focused M4 test suite:

```bash
cd /workspace/arnold

# Core M4 contract and lifecycle tests
pytest tests/cloud/test_repair_contract.py tests/cloud/test_human_blockers.py -v

# Feature flags (escalation-ledger gating)
pytest tests/cloud/test_feature_flags.py -v

# Discord DM redaction and delivery evidence
pytest tests/arnold_pipelines/megaplan/test_discord_dm.py -v

# Wrapper integration (repair-loop + watchdog escalation paths)
pytest tests/cloud/test_watchdog_wrappers.py -v --timeout=120

# Resident authorization and escalation reply
pytest tests/resident/test_authorizer.py tests/resident/test_escalation_reply.py -v

# Resident Discord outbound parsing
pytest tests/resident/test_discord_outbound.py -v

# Full M4 focused suite
pytest tests/cloud/test_repair_contract.py \
       tests/cloud/test_human_blockers.py \
       tests/cloud/test_feature_flags.py \
       tests/cloud/test_watchdog_wrappers.py \
       tests/arnold_pipelines/megaplan/test_discord_dm.py \
       tests/resident/test_authorizer.py \
       tests/resident/test_escalation_reply.py \
       tests/resident/test_discord_outbound.py \
       -v --timeout=120
```

### Concrete References

- **Escalation ledger:** `arnold_pipelines/megaplan/cloud/human_blockers.py` —
  `EscalationLedgerWriter`, `compute_escalation_id()`, `write_opened()`,
  `write_delivered()`, `write_unavailable()`, `write_answered()`,
  `write_superseded()`, `write_timed_out()`, `write_resume_attempted()`.
- **Pointer helpers:** `arnold_pipelines/megaplan/cloud/human_blockers.py` —
  `supersede_needs_human_marker()`, `clear_needs_human_marker()`.
- **Classifier:** `arnold_pipelines/megaplan/cloud/human_blockers.py` —
  `classify_needs_human_blocker()`, `BlockerVerdict`, `HumanBlockerClassification`.
- **Sidecar contract:** `arnold_pipelines/megaplan/cloud/repair_contract.py` —
  `_SIDECAR_KINDS`, `append_escalation_record()`, `append_jsonl_record()`.
- **Discord DM:** `arnold_pipelines/megaplan/discord_dm.py` —
  `send_discord_dm()`, `render_discord_dm()`, redacted delivery evidence.
- **Resident auth:** `arnold_pipelines/megaplan/resident/auth.py` —
  `ActionKind` (`escalation_reply`, `escalation_resolve`),
  `CONFIRMED_HIGH_IMPACT_ACTIONS`.
- **Resident escalations:** `arnold_pipelines/megaplan/resident/escalations.py` —
  `authorize_escalation_answer()`, `EscalationTarget`, `EscalationAnswerDecision`.
- **Resident config:** `arnold_pipelines/megaplan/resident/config.py` —
  `escalation_repair_data_dir`, `escalation_repair_lock_dir`.
- **Feature flags:** `arnold_pipelines/megaplan/cloud/feature_flags.py` —
  `escalation_ledger_enabled()`, `ARNOLD_ESCALATION_LEDGER`.
- **Wrappers:** `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`,
  `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`.
- **Tests:** `tests/cloud/test_repair_contract.py`,
  `tests/cloud/test_human_blockers.py`,
  `tests/cloud/test_watchdog_wrappers.py`,
  `tests/arnold_pipelines/megaplan/test_discord_dm.py`,
  `tests/resident/test_authorizer.py`,
  `tests/resident/test_escalation_reply.py`,
  `tests/resident/test_discord_outbound.py`.
