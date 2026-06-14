# Sprint 12B Cleanup Gate Inventory

This is the cleanup-only preflight for Sprint 12B. It is a review artifact, not
deletion approval. Later cleanup PRs must keep one cleanup category per PR and
must rerun the affected baseline if they land before Sprint 0 or mid-migration.

## Section 8A Deletion Gate

Before deleting any handler, schema/status value, migration-only column, or
store path, prove all of the following with source-backed searches:

1. No CLI parser registration, `COMMAND_HANDLERS` entry, or exported public
   module symbol still targets it.
2. No control intent, `_default_handlers` entry, DB control-message row shape,
   resident/admin/cloud tool, scheduler, debug path, progress emitter, or direct
   import still targets it.
3. No file-store, DB-store, `MultiStore`, or `Store` protocol method still
   reads, writes, serializes, replays, copies, or filters it.
4. No Supabase migration, check constraint, copy-table constant, contract test,
   resolver test, resident tool test, or replay fixture still locks it in.
5. Any pre-existing baseline failure is recorded before cleanup edits and kept
   separate from cleanup-caused regressions.

`UNUSED` or `AMBIGUOUS` labels are only candidate signals. They are never
deletion proof by themselves.

## Source Search Ledger

Commands run from a checkout of the megaplan repo:

- `python -m megaplan config show`
- `rg -n --glob '!megaplan/agent/**' "UNUSED|AMBIGUOUS" megaplan tests supabase docs README.md pyproject.toml`
- `rg -n --glob '!megaplan/agent/**' "turbo|robustness.*turbo|robustness" megaplan tests README.md docs pyproject.toml`
- `rg -n --glob '!megaplan/agent/**' "SUPPORTED_CONTROL_INTENTS|ControlIntent|pause_plan|cancel_run|manual_fix|request_inspect|run_sprint|resume_plan|approve_gate|reject_gate|_default_handlers|handle_[a-z_]+|__all__" megaplan tests supabase docs`
- `rg -n --glob '!megaplan/agent/**' "cloud_status|cloud_status_chain|cloud_start_chain|cloud_bootstrap|cloud_resume|cloud_logs|ToolOperationKind|register\\(|ToolRegistration|resident tool|operation_kind" megaplan tests docs`
- `rg -n --glob '!megaplan/agent/**' "ProgressEmitter|\\.emit\\(|phase_start\\(|phase_end\\(|batch_complete\\(|gate_pending\\(|gate_resolved\\(|plan_done\\(|plan_failed\\(|execution_blocked\\(|manual_fix_attached\\(|append_progress_event|put_control_message|claim_pending_control_messages|recover_stale_control_messages|mark_control_message_processed" megaplan tests`
- `rg -n --glob '!megaplan/agent/**' "debug|system_logs|SystemLog|record_system_log|list_system_logs|direct|emitter|emit" megaplan tests supabase docs`
- `sed -n '1,260p' megaplan/control.py`
- `sed -n '1,220p' megaplan/handlers/__init__.py`
- `sed -n '1,260p' megaplan/resident/tool_registry.py`
- `sed -n '1,260p' megaplan/resident/cloud.py`
- `sed -n '1,260p' megaplan/schemas/arnold.py`
- `sed -n '1,260p' megaplan/schemas/sprint1.py`
- `sed -n '240,310p' megaplan/store/db.py`
- `sed -n '292,390p' tests/test_db_store.py`
- `sed -n '3600,3925p' megaplan/store/db.py`
- `sed -n '1150,1245p' megaplan/store/base.py`
- `sed -n '2560,2955p' megaplan/store/file.py`
- `sed -n '1,220p' pyproject.toml`
- `sed -n '1,220p' megaplan/agent/pyproject.toml`
- `sed -n '1,230p' supabase/migrations/202605040000_megaplan_dbstore_foundation.sql`
- `sed -n '1,160p' supabase/migrations/202605060001_resident_orchestration.sql`
- `sed -n '1080,1330p' megaplan/cli.py`
- `sed -n '1640,1690p' megaplan/cli.py`
- `rg -n --glob '!megaplan/agent/**' "COMMAND_HANDLERS|handle_[a-z_]+|add_parser\\(|set_defaults\\(|choices=\\[|choices=\\(" megaplan/cli.py tests/test_audits.py`

The literal `UNUSED|AMBIGUOUS` search returned no matches outside vendored
`megaplan/agent/**`. In this repo, the actionable ambiguous candidates are
therefore schema/status/control values whose live reachability must be proven
from code, migrations, and tests rather than from literal labels.

## Inventory

### Turbo-Mode Scaffolding

Candidate: unsupported `execution.robustness = "turbo"` / `--robustness turbo`
scaffolding.

Current proof:

- `tests/test_config.py:129` rejects `execution.robustness = "turbo"`.
- `megaplan/cli.py:1140` and `megaplan/cli.py:1312` constrain
  `--robustness` to `ROBUSTNESS_LEVELS`.
- The top-level non-vendored search found no top-level turbo runtime path.
- Vendored `megaplan/agent/**` was intentionally excluded; `turbo` there may
  be a legitimate provider/model string and is out of scope for cleanup PR 1.

Cleanup result: no top-level runtime, config default, CLI choice, or help branch
for `turbo` exists to delete. The only non-vendored `turbo` references are this
inventory and the invalid-value config test. Vendored Hermes references remain
out of scope.

### Handler Exports And CLI Wiring

Candidates: top-level handler exports and CLI command handlers.

Current proof:

- `megaplan/handlers/__init__.py:74` exports the public phase handlers:
  `handle_init`, `handle_plan`, `handle_prep`, `handle_critique`,
  `handle_revise`, `handle_gate`, `handle_finalize`, `handle_execute`,
  `handle_review`, `handle_override`, `handle_audit_verifiability`,
  `handle_verify_human`, `handle_tiebreaker_run`, and
  `handle_tiebreaker_decide`.
- `megaplan/cli.py:1454` maps public CLI commands in `COMMAND_HANDLERS`.
- `megaplan/cli.py:1228`, `megaplan/cli.py:1250`,
  `megaplan/cli.py:1273`, `megaplan/cli.py:1290`,
  `megaplan/cli.py:1307`, `megaplan/cli.py:1328`,
  `megaplan/cli.py:1336`, and `megaplan/cli.py:1437` register parser
  surfaces for these handlers.

Cleanup result: no exported handler passes the deletion gate. All exported
handlers remain public CLI/runtime API, so this cleanup PR deletes none.

### Control Intents

Candidates: schema-visible control intents not currently supported by the
processor.

Current proof:

- `megaplan/schemas/sprint1.py:46` defines `ControlIntent` values including
  `pause_plan`, `cancel_run`, `manual_fix`, and `request_inspect`.
- `megaplan/control.py:35` currently supports only `run_sprint`,
  `resume_plan`, `approve_gate`, and `reject_gate`.
- `megaplan/control.py:369` registers `_default_handlers` only for those four
  supported intents.
- `tests/contract/store_contract.py:365` creates a `pause_plan` control message
  in the store contract, so `pause_plan` is still a serialized store-contract
  value even though it has no processor handler.

Cleanup result: `pause_plan`, `cancel_run`, `manual_fix`, and
`request_inspect` are ambiguous cleanup candidates, not dead. `pause_plan` is
explicitly still test-covered as a DB/file-store value and must not be deleted
without replacing or updating the contract. The four supported processor
intents are live, so this cleanup PR deletes no control intents or handlers.

### Resident Tools And Cloud Operations

Candidates: resident tool names and constrained cloud operations.

Current proof:

- `megaplan/resident/profile.py:264` through `megaplan/resident/profile.py:284`
  register resident tools, including `approve_gate`, `reject_gate`,
  `run_sprint_on_cloud`, all cloud tool wrappers, and scheduled-check tools.
- `megaplan/resident/cloud.py:16` defines the live `CloudOperation` literal
  set: `cloud_status`, `cloud_status_chain`, `cloud_start_chain`,
  `cloud_bootstrap`, `cloud_resume`, and `cloud_logs`.
- `tests/test_resident_runtime_profile.py:193` asserts core resident tool
  availability, and `tests/test_resident_cloud_tools.py:45` exercises cloud
  tool persistence and progress behavior.

Deletion stance: no resident tool or cloud operation is deletion-approved by
this inventory. Later deletion must prove absence from profile registration,
input schemas, scheduler paths, cloud backend dispatch, store writes, and tests.

### Store Protocol, File Store, DB Store, And Progress

Candidates: control/progress store methods, system log paths, and direct
emitter paths.

Current proof:

- `megaplan/store/base.py:1044` through `megaplan/store/base.py:1065` define
  control-message protocol methods.
- `megaplan/store/base.py:1196` defines `append_progress_event`, and
  `megaplan/store/base.py:1202` defines `list_progress_events`.
- `megaplan/store/file.py:2568` through `megaplan/store/file.py:2654`
  implement file-store control message writes/claims/recovery/processed
  marking.
- `megaplan/store/file.py:2909` implements file-store progress appends.
- `megaplan/store/db.py:3136` through `megaplan/store/db.py:3192` implement
  DB control message writes/claims/recovery/processed marking.
- `megaplan/store/db.py:3576` implements DB progress appends.
- `megaplan/progress.py:108` defines `ProgressEmitter`; `megaplan/progress.py:174`
  through `megaplan/progress.py:199` define emitted event kinds.
- `megaplan/cli.py:1663` attaches `ProgressEmitter.from_env()` to CLI args,
  and `megaplan/execute/core.py:973` emits batch completion.
- `tests/test_store_contract_adapter.py:159` requires `put_control_message`,
  `claim_pending_control_messages`, and `append_progress_event` on the
  contract adapter surface.
- `tests/test_progress.py:24` and later tests exercise no-op, file-backed, and
  CLI lifecycle progress emission.

Deletion stance: these paths are live. Any deletion must prove contract,
file-store, DB-store, `MultiStore`, CLI, auto/execute, and progress tests no
longer require the method or event kind.

### Schema And Status Values

Candidates: schema/status literals and Supabase check constraints.

Current proof:

- `megaplan/schemas/arnold.py:25` through `megaplan/schemas/arnold.py:48`
  define Arnold/editorial literals including epic states, bot-turn statuses,
  tool operation kinds, log levels/categories, external request statuses, and
  sprint statuses.
- `megaplan/schemas/sprint1.py:18` through `megaplan/schemas/sprint1.py:66`
  define migration phases, plan artifact roles, worker kinds, scheduled job
  statuses/types, cloud run statuses/operations, control intents, progress
  event kinds, and automation actor kinds.
- `supabase/migrations/202605040000_megaplan_dbstore_foundation.sql:40`
  constrains `db_idempotency_keys.status`.
- `supabase/migrations/202604300001_001_core.sql:85` constrains system log
  levels.
- `supabase/migrations/202605060001_resident_orchestration.sql:36` through
  `supabase/migrations/202605060001_resident_orchestration.sql:98` lock
  resident transport, cloud run operation/status, and scheduled job values.

Cleanup result: no schema/status value is deletion-approved. Literal
`AMBIGUOUS` was not found; in this repo, AMBIGUOUS means externally suspected
schema/status/control values whose deadness must be proven from all storage,
resolver, migration, resident-tool, serialization, and replay paths. This batch
keeps all such values because the schema and migration constraints still lock
them in.

### Migration-Only Columns And Copy Constants

Candidates: DB copy constants and migration-private columns.

Current proof:

- `megaplan/store/db.py:240` through `megaplan/store/db.py:269` list
  `_COPY_TABLE_COLUMNS`.
- `megaplan/store/db.py:273` through `megaplan/store/db.py:282` list
  `_COPY_JSONB_COLUMNS`.
- `megaplan/store/db.py:3630` through `megaplan/store/db.py:3910` implement
  migration-run and idempotent copy helpers.
- `tests/test_db_store.py:292` asserts generic copy rejects `plan_artifacts`
  and requires `copy_plan_artifacts_idempotent`.
- `tests/test_db_store.py:332` and `tests/test_db_store.py:356` assert binary
  artifact copy and safe artifact path handling.
- `supabase/migrations/202605040000_megaplan_dbstore_foundation.sql:105`
  through `supabase/migrations/202605040000_megaplan_dbstore_foundation.sql:124`
  create `migration_runs` with `manifest`, `copied_ids`, and
  `blob_copy_progress`.

Deletion stance: no copy-table constant or migration-only column is
deletion-approved here. These are live migration/replay surfaces until a later
cleanup PR proves the store, migration, and contract tests no longer depend on
them.

### Pyproject Dedupe

Candidates: duplicated agent dependency spelling/ownership between the
top-level package and vendored Hermes package.

Current proof:

- Top-level `pyproject.toml:18` keeps default runtime dependencies minimal:
  `pyyaml` and `pydantic`.
- Top-level `pyproject.toml:25` owns `db = ["psycopg[binary]>=3.1"]`.
- Top-level `pyproject.toml:28` owns the `[agent]` extra with Hermes runtime
  dependencies and keeps the published `megaplan-harness[agent]` install
  contract.
- Vendored `megaplan/agent/pyproject.toml:13` owns `hermes-agent` dependencies.

Cleanup result: top-level dependency spelling is canonicalized to
`pyyaml>=6.0`, and the duplicate unpinned `pyyaml` entry was removed from the
top-level `[agent]` extra because the base install already owns it. The vendored
Hermes `pyproject.toml` remains unchanged so standalone vendored Hermes startup
still declares its own `pyyaml` dependency.

## Pre-Cleanup Baseline

Baseline command:

```bash
pytest tests/test_config.py tests/test_store_contract_adapter.py tests/test_file_store.py tests/test_db_store.py tests/test_control.py tests/test_resident_runtime_profile.py tests/test_resident_cloud_tools.py
```

Baseline result: pending in this artifact until the command is run.

Baseline captured on 2026-05-07:

- Result: passed.
- Summary: `90 passed, 7 skipped in 0.95s`.
- Baseline failures: none.

Because this baseline was run before cleanup source edits, later cleanup PRs
should treat any new failure in this set as cleanup-caused unless independently
proven environmental.

## Sprint 12B Result

This batch is deferred/post-canary optional cleanup. It is not landing before
Sprint 0 or mid-migration, so baseline regeneration is not required for route
comparison or canary readiness. The focused baselines below were rerun to prove
the cleanup itself does not introduce regressions.

This cleanup batch did not remove handlers, schema/status values, control
intents, resident tools, store methods, DB copy constants, or Supabase shape.
The only source changes are the packaging dependency dedupe, the package build
exclude for archived agent auto-improve iteration symlinks, and this review
artifact.

No Supabase cleanup migration was created because there were no DB columns,
tables, indexes, enum/check values, or store serialization contracts changed.

Final validation captured on 2026-05-07:

- `PYENV_VERSION=3.11.11 python -m pytest tests/test_config.py tests/test_modes_helpers.py tests/test_profiles.py`
  - Result: `44 passed`.
- `PYENV_VERSION=3.11.11 python -m pytest tests/test_control.py tests/test_init_plan.py tests/test_execute.py tests/test_review.py tests/test_resident_runtime_profile.py tests/test_resident_cloud_tools.py`
  - Result: `147 passed, 46 warnings`.
- `PYENV_VERSION=3.11.11 python -m pytest tests/test_schemas.py tests/test_db_store.py tests/test_file_store.py tests/test_multi_store.py tests/test_store_contract_adapter.py`
  - Result: `92 passed, 7 skipped`.
- `PYENV_VERSION=3.11.11 python -m pytest tests/test_core_without_bakeoff.py tests/test_core_without_cloud.py tests/test_config.py`
  - Result: `34 passed`.
- `PYENV_VERSION=3.11.11 python -m pytest tests/test_db_store.py`
  - Result: `15 passed, 6 skipped`.
- `PYENV_VERSION=3.11.11 python -m pytest tests/test_control.py tests/test_store_contract_adapter.py tests/test_file_store.py tests/test_db_store.py`
  - Result: `48 passed, 7 skipped`.
- Fresh packaging smoke:
  `rm -rf /tmp/megaplan-agent-smoke dist && PYENV_VERSION=3.11.11 python -m build && PYENV_VERSION=3.11.11 python -m venv /tmp/megaplan-agent-smoke && /tmp/megaplan-agent-smoke/bin/python -m pip install -e '.[agent]' && /tmp/megaplan-agent-smoke/bin/python - <<'PY' ...`
  - Result: built `megaplan_harness-0.20.0.tar.gz` and
    `megaplan_harness-0.20.0-py3-none-any.whl`; fresh `[agent]` editable
    install succeeded; `_import_hermes_runtime()` and `import model_tools`
    succeeded with `agent smoke ok`.
