# M5d Supervisor Extraction Map

Verified file map and function classification for the M5d supervisor-tier extraction.
Generated 2026-05-31. All line numbers verified against the current repository.

## Verified File Map

| Canonical Path | Purpose | LOC |
|---|---|---|
| `megaplan/chain/__init__.py` | Chain driver — YAML spec → milestone orchestration, autonomy ladder, PR lifecycle | 2,404 |
| `megaplan/chain/git_ops.py` | Git/GitHub helpers shared with chain (branch, PR, sync, dirty worktree) | 804 |
| `megaplan/bakeoff/__init__.py` | Bakeoff package init, `setup_bakeoff_parser`, CLI dispatch | 24 |
| `megaplan/bakeoff/cli.py` | Bakeoff CLI entry point (`run_bakeoff_cli`) | ~400 |
| `megaplan/bakeoff/orchestrator.py` | Bakeoff executor — per-profile plan init + drive + compare + merge | -- |
| `megaplan/bakeoff/judge.py` | Judge rubric, evaluation loop | -- |
| `megaplan/bakeoff/comparison.py` | Profile comparison, winner selection | -- |
| `megaplan/bakeoff/merge.py` | Merge winning branch back to base | -- |
| `megaplan/bakeoff/lifecycle.py` | Bakeoff planning lifecycle (init, drive, single/multi) | -- |
| `megaplan/bakeoff/handlers.py` | Bakeoff CLI sub-action handlers | -- |
| `megaplan/bakeoff/state.py` | Bakeoff persisted state, verdict tracking | -- |
| `megaplan/bakeoff/live_status.py` | Live status update loop for bakeoff | -- |
| `megaplan/bakeoff/worktree.py` | Worktree isolation for bakeoff profiles | -- |
| `megaplan/bakeoff/metrics.py` | Bakeoff evaluation metrics | -- |
| `megaplan/control_interface.py` | Domain-neutral control interface (`ControlTarget`, `ControlProjection`, `RunStateView`, `ControlTransition`, `read_valid_targets`, `apply_transition`) | 428 |
| `megaplan/planning/control_binding.py` | Planning-owned binding: maps neutral targets → planning state/actions (`STATE_*`, `force-proceed`) | 1,227 |
| `megaplan/cloud/supervise.py` | **Cloud chain supervisor** — one-shot tick logic; remains above supervisor tier | 775 |
| `megaplan/cloud/cli.py` | Cloud CLI + `_chain_start_command` and tmux session management | 1,437 |

## Chain Function Classification

Functions in `megaplan/chain/__init__.py` (2,404 LOC) classified by concern:

### 1. Shared Chain Spec/State Parsing (to be extracted to `megaplan/chain/spec.py`)

These are pure data-class and YAML-parsing functions with no orchestration logic. The supervisor chain runner will import these without touching the old orchestration path.

| Function / Class | Lines | Notes |
|---|---|---|
| `FailurePolicy` | 131–184 | Dataclass + `from_yaml()`; autonomy ladder config per failure type |
| `_optional_choice()` | 237–254 | Validation helper for YAML choice fields |
| `_optional_bool()` | 257–261 | Validation helper for YAML boolean fields |
| `MilestoneSpec` | 264–405 | Dataclass + `from_dict()`; all milestone fields including `depends_on` |
| `ChainSpec` | 407–581 | Dataclass + `from_dict()`; spec root including seed, milestones, policies |
| `ChainState` | 582–730 | Dataclass; persisted progress, retry counts, bump state, sync metadata |
| `_state_path_for()` | 731–735 | Compute `.chains/` state file path from spec path |
| `_legacy_state_path_for()` | 737–739 | Legacy state path migration |
| `load_spec()` | 741–749 | YAML → `ChainSpec` |
| `load_chain_state()` | 751–766 | JSON → `ChainState` with legacy fallback |
| `save_chain_state()` | 768–779 | `ChainState` → JSON persistence |
| `_runtime_policy_path_for()` | 781–795 | Runtime override policy path |
| `load_runtime_policy()` | 798–818 | JSON → runtime policy overrides |
| `save_runtime_policy()` | 821–831 | Runtime policy → JSON |
| `effective_chain_policy()` | 834–860 | Merge spec policy + runtime overrides |
| `_write_chain_policy_into_plan_meta()` | 863–928 | Propagate chain policy into plan `state.json` metadata |
| `validate_paths()` | 931–951 | Check seed plan dir, milestone idea files exist |
| `_warn_chain_fallback()` | 220–234 | Logging helper for chain fallback scenarios |
| `format_chain_status()` | 2045–2104 | Build status summary dict from spec + state |
| `_write_chain_status_pretty()` | 2107–2152 | Human-readable status output |

### 2. Supervisor Orchestration (to be re-expressed in `megaplan/supervisor/chain_runner.py`)

These implement the autonomy ladder, milestone sequencing, outcome handling, and the main `run_chain()` loop. The new supervisor re-implements this logic using neutral `RunOutcome` and `ControlTarget` vocabulary.

| Function | Lines | Notes |
|---|---|---|
| `_bump_one_tier()` | 112–127 | Pure helper: bump a value one tier in an ordered tuple |
| `_plan_state()` | 955–1009 | Read plan state via `auto._status()` subprocess |
| `_init_plan()` | 1011–1080 | Init a new plan for a milestone via `auto._run_megaplan()` |
| `_warn_vendor_ignored_for_locked_profile()` | 1082–1121 | Warn when a vendor override is ignored due to a locked profile |
| `_drive_plan()` | 1124–1144 | Drive a plan to completion via `auto.drive()` |
| `_execution_batch_sort_key()` | 1147–1152 | Sort key for execution batch directories |
| `_latest_execute_result()` | 1154–1180 | Read latest `execute_result.json` from plan dir |
| `_shadow_milestone_completion_verdict()` | 1183–1272 | Compute + persist milestone-level completion verdict (fail-open) |
| `_latest_execution_batch_all_tasks_done()` | 1274–1322 | Check if all tasks in latest execution batch are done |
| `_mark_blocked_execute_as_executed()` | 1325–1339 | Write `STATE_EXECUTED` state for blocked-but-tasks-done milestone |
| `_recover_blocked_execute_if_tasks_done()` | 1342–1374 | Blocked execute recovery: if all tasks done, mark executed; else escalate |
| `_drive_plan_with_blocked_execute_recovery()` | 1377–1400 | Drive plan, then apply blocked-execute recovery if outcome is blocked/worker_blocked |
| `_milestone_retry_cap()` | 1403–1417 | Compute retry cap (2 default, 1 for apex/extreme) |
| `_apply_ladder_action()` | 1420–1474 | Execute a ladder action (stop/skip/retry/bump_profile/bump_robustness) |
| `_handle_outcome()` | 1477–1557 | Core outcome → decision translation: advance/stop/retry/skip, walking the ladder |
| `_maybe_file_ladder_ticket()` | 1635–1674 | Auto-file a ladder-exhaustion ticket when milestone halts after full ladder walk |
| `run_chain()` | 1677–2028 | **Main entry**: seed phase → milestone loop → PR lifecycle → events → result |
| `_result()` | 2031–2042 | Build the JSON-serializable result dict returned by `run_chain()` |

### 3. PR Actor (to be extracted to `megaplan/supervisor/pr_merge.py`)

PR handling is embedded inside `run_chain()` (lines 1756–1988) and delegates to `megaplan/chain/git_ops.py` helpers. The new supervisor extracts this into a standalone actor.

| Concern | Lines in `run_chain()` | Git helpers used |
|---|---|---|
| PR await + merge-on-green check | 1758–1792 | `_pr_state()` |
| PR creation (branch, push, `gh pr create`) | 1810–1903 | `_checkout_milestone_branch()`, `_capture_sync_state()`, `_ensure_milestone_pr()` |
| Post-advance PR finalization + auto-merge | 1951–1988 | `_commit_and_push_phase()`, `_capture_sync_state()`, `_pr_state()`, `_mark_pr_ready()`, `_enable_auto_merge()` |

### 4. Git/GH Helper Code (`megaplan/chain/git_ops.py`, 804 LOC)

These are shared helpers used by both old and new chain paths. The supervisor imports them directly.

| Function | Lines | Purpose |
|---|---|---|
| `_refresh_base_branch()` | 23–200 | `git fetch + checkout <base> + pull` |
| `_checkout_milestone_branch()` | 202–238 | `git checkout -b <milestone_branch>` |
| `_ensure_milestone_pr()` | 240–404 | `gh pr create` or find existing |
| `_dirty_worktree_paths()` | 406–553 | `git status --porcelain` → dirty paths |
| `_capture_sync_state()` | 556–630 | Snapshot branch/PR head, dirty flag, sync state |
| `_commit_and_push_phase()` | 632–706 | `git add -A`, `git commit`, `git push` for phase |
| `_mark_pr_ready()` | 708–709 | Mark PR as ready for review |
| `_enable_auto_merge()` | 712–746 | `gh pr merge --auto --squash` |
| `_pr_state()` | 749–775 | `gh pr view --json state` → merged/open/closed |
| `_reconcile_terminal_pr_state()` | 778–804 | Final PR reconciliation at chain end |

### 5. CLI Plumbing (old-only; routing point stays in `__init__.py`)

These remain in `megaplan/chain/__init__.py`. When `MEGAPLAN_SUPERVISOR_TIER=1`, `run_chain_cli` dispatches to the new supervisor for the `start` (default) action. `override` and `status` sub-actions stay on the old path.

| Function | Lines | Notes |
|---|---|---|
| `build_chain_parser()` | 2160–2268 | Argparse: `chain start`, `chain status`, `chain override` |
| `_add_chain_worktree_args()` | 2270–2308 | Shared `--in-worktree`/`--clean-worktree` args |
| `run_chain_cli()` | 2311–2398 | **Routing point**: dispatches to `run_chain()` (old) or supervisor (new) |
| `_emit_error()` | 2401–2404 | Format CLI error to JSON + exit code |
| `_carried_wip_paths()` | 1560–1576 | Filter `.megaplan/` from dirty worktree paths |
| `_assert_clean_base()` | 1579–1632 | Assert clean working base before milestone init |

## Old-Path Retention Note

**No code is deleted in M5d.** The old chain path (`megaplan/chain/__init__.py::run_chain()`) and old bakeoff path remain default-on and frozen. The new supervisor tier under `megaplan/supervisor/` is activated only by `MEGAPLAN_SUPERVISOR_TIER=1`. Retirement of the old path requires a later dual-green (old + new passing on the same corpus) plus an oracle pass. The shared spec/state extraction (`megaplan/chain/spec.py`) wraps or moves code without deleting it from the old module — the old path imports the shared module so flag-off behavior is byte-identical.

## Cloud-Above-Supervisor Boundary

**`megaplan/cloud/supervise.py` and `megaplan/cloud/cli.py` remain above the supervisor tier and are not ported in M5d.**

- Cloud wraps the supervisor as a long-lived tick host. `cloud_supervise_tick()` observes chain state and makes safe progress decisions (restart missing runners, surface recoverable blockers) without human approval.
- `_chain_tick_command()` in `megaplan/cloud/supervise.py` delegates to `megaplan.cloud.cli._chain_start_command()` to construct the canonical `megaplan chain start` command string.
- `_chain_start_command()` in `megaplan/cloud/cli.py` builds `MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec <path>`.
- Cloud is anti-scope for M5d: the supervisor tier sits *below* cloud's operator loop. Cloud documentation in `megaplan/cloud/supervise.py` is sufficient for the M5d boundary; no automated AST purity gate for cloud modules is added in this milestone (documented in SD1).
- Ticket `01KRNKTKF8S857SZNMYH5DQ20D` remains related to the cloud boundary but is not resolved by M5d because cloud remains above the supervisor tier and is not ported.
