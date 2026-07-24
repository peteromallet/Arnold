# Loose Work Cleanup - 2026-07-05

## Landed Locally

- Local item-zero dirty work was checkpointed onto `main` as `937d8302`.
- `origin/editible-install` was merged into `main` as `9c423980`.
- Native platform follow-up stack `origin/megaplan/m1-side-effect-reconcile-and-20260704-1634` through `origin/megaplan/m6-platform-docs-conformance-20260705-0039` was merged into `main` as `eb446b4f`.
- Cloud `/workspace/arnold` `.pypeline` support was already covered by the m6 merge; remaining generated hash/docs updates were ported as `242380f6`.
- Useful survivor from `integrate-cloud-hardening-20260703` was salvaged as `a13b9abc`; stale implementation hunks were superseded by newer cloud status/repair contracts.
- Merge contract fixes were committed as `e948d38d`; focused verification passed: `520 passed`.
- Local `editible-install` now points at the same commit as local `main` after this pass.
- Final cloud `editible-install` check found the `.pypeline` source-compiler/CLI support dirty in `/workspace/arnold`; those blobs were already present on local `main`. The cloud checkout was backed up, then reset to pushed `origin/editible-install`.
- GitHub `main` and `editible-install` were pushed to the consolidated commit.

## Delete-Ready After Approval

Positive evidence: `git cherry main <ref>` is `+0` after consolidation.

- Local branches: `codex/supervise-repair-queue`, `megaplan/m2-routing-validator-and-20260703-1535-push`, `resident-status-snapshot`.
- Remote branches: `origin/editible-install`, `origin/resident-status-snapshot`.
- Old native-composition autopublish stack: `origin/megaplan/m0-composition-contract-and-20260702-1541`, `origin/megaplan/m1-megaplan-compositional-20260703-0954`, `origin/megaplan/m2-routing-validator-and-20260703-1535`, `origin/megaplan/m3-general-nested-workflow-20260703-1708`, `origin/megaplan/m4-tree-graph-trace-and-audit-20260703-2220`, `origin/megaplan/m5-composite-resume-and-start-20260704-0019`, `origin/megaplan/m6-composition-docs-and-20260704-0158`.
- New native-platform autopublish stack now merged: `origin/megaplan/m1-side-effect-reconcile-and-20260704-1634`, `origin/megaplan/m2-security-broker-and-20260704-1739`, `origin/megaplan/m3-shared-library-packs-and-20260704-1943`, `origin/megaplan/m4-durable-substrate-and-20260704-2124`, `origin/megaplan/m5-worker-fleet-supervision-20260704-2252`, `origin/megaplan/m6-platform-docs-conformance-20260705-0039`.
- `origin/preserve/cloud-arnold-chain-init-20260703-015121` and `origin/preserve/native-python-m7-audit-20260703-0152` are patch-equivalent to consolidated `main`.

## Second-Pass Salvage Verdicts

The parked refs below were rechecked after consolidation with direct `git diff main <ref>` comparisons. They may still show `git cherry` `+N` because patch IDs changed across conflict resolution, file moves, generated artifacts, or deliberately stale branches. No additional source salvage is recommended.

- `origin/consolidate/repair-watchdog-tail-20260703`: delete-ready for code purposes. Evidence-pack source/docs and wheel-smoke diagnostics are already on `main`; the remaining direct diff is older versions of `tests/cloud/test_cloud_chain_command.py`, `tests/cloud/test_progress_auditor.py`, and `tests/cloud/test_watchdog_wrappers.py` that would remove current compact-status, phase-model, incident-audit, and repair-data-payload contracts.
- `integrate-cloud-hardening-20260703`: delete-ready for code purposes. The useful non-stale hardening slice was salvaged as `a13b9abc`; the leftover unique patch is AppleDouble metadata only (`._auto.py`, `._phase_result_classify.py`, `._hetzner-watchdog-meta-loop.md`, `._test_auto_recover_blocked.py`).
- `origin/archive/cloud-tiered-m1-cloud-safe-repair-20260703` and `origin/archive/cloud-tiered-m2-correctness-20260703`: delete-ready for code purposes. Branch-only payload is chain runtime state plus `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`, which imports the deleted `arnold.pipelines.megaplan` legacy surface.
- `origin/archive/engine-watchdog-runner-20260703`: delete-ready for code purposes. Branch-only additions live under old `arnold/pipelines/...` and old runner/profile paths; current `main` has the surviving implementations under `arnold_pipelines.megaplan` and `arnold.execution`.
- `origin/archive/live-watchdog-supervisor-20260703`: delete-ready for code purposes. It would reintroduce old `arnold/pipelines/megaplan/...` plus vendored agent copies; current discovery/docs/tests cover the migrated live-supervisor path.
- `origin/preserve/cloud-native-composition-source-20260703-015147` and `origin/preserve/cloud-native-composition-current-20260703-0355`: delete-ready for code purposes. Branch-only source is `arnold/pipelines/deliberation`, `arnold/pipelines/folder_audit`, `_deliberation_example`, and `arnold_pipelines/megaplan/cli/arnold.py`; `docs/arnold/m6-deletion-list.md` explicitly marks those as archive/delete targets, and the archived copies exist under `docs/archive/m5/`.
- `origin/preserve/cloud-native-composition-evidence-20260703-0152`: archive-only runtime evidence. Delete-ready if historical chain/proof state is no longer needed; no source code to port.
- `origin/preserve/local-dirty-20260703-015050` and `origin/preserve/local-dirty-cloud-push-20260703`: delete-ready for code purposes. Direct diffs are older cloud repair/watchdog variants, M6-deleted legacy source, runtime chain evidence, or the `cli.arnold` shim already listed for deletion by M6.
- `origin/archive/snapshot-arnold-m1-m6-wip-20260703` and `origin/archive/snapshot-arnold-m7-m8-wip-20260703`: archive-only snapshots. Delete-ready if you do not need the historical safety snapshot; not useful as a merge source because they contain runtime state, old vendored agent trees, and M6-deleted legacy package surfaces.

## Remaining Not-Code-Keeper Items

These are not worth merging but are not deleted in this pass:

- Archive refs above if you want to retain their historical chain/runtime evidence.
- Remote archive/preserve refs that are historical evidence rather than source work.

## Worktrees / Cloud

- Prunable and temporary worktrees were removed/pruned.
- `Arnold-resident-status-snapshot` was removed after backing up its generated incident-ledger diff to `/tmp/arnold-loose-work-backups/resident-status-snapshot-20260705/diff.patch`.
- Hetzner status reported 22 known cloud sessions complete and no mutating chain tmux sessions. Cloud workspaces still contain runtime dirt/logs; source work from `/workspace/arnold` was ported.
- Arnold-specific editable-install replacement: local, GitHub, and cloud `/workspace/arnold` all point at the consolidated `editible-install`.

## Deleted As Redundant After Approval

- Local branches: `codex/supervise-repair-queue`, `megaplan/m2-routing-validator-and-20260703-1535-push`, `integrate-cloud-hardening-20260703`, `resident-status-snapshot`.
- Remote branches: `origin/resident-status-snapshot`, `origin/consolidate/repair-watchdog-tail-20260703`, old native-composition autopublish stack, merged native-platform autopublish stack, `origin/preserve/cloud-arnold-chain-init-20260703-015121`, `origin/preserve/native-python-m7-audit-20260703-0152`.
- Local junk candidates:
  - `node_modules/` untracked contents
  - `._*` AppleDouble files: `arnold_pipelines/megaplan/._auto.py`, `arnold_pipelines/megaplan/orchestration/._phase_result_classify.py`, `docs/._hetzner-watchdog-meta-loop.md`, `tests/arnold_pipelines/megaplan/._test_auto_recover_blocked.py`
  - Scratch helpers: `_fix_normalized.py`, `_regenerate_fixtures.py`

## Kept Deliberately

- `origin/archive/*` refs and remaining `origin/preserve/cloud-native-composition-*`, `origin/preserve/local-dirty-*` refs were kept because they are primarily archive/evidence safety refs. They are not merge sources, but deleting them would discard historical chain/proof state.

## Verification

- `pytest tests/cloud/test_progress_auditor.py tests/cloud/test_watchdog_wrappers.py tests/cloud/test_cloud_chain_command.py tests/resident/test_megaplan_initiatives.py tests/arnold/workflow/test_source_compiler_api.py tests/cli/test_m5_workflow_source_cli.py`
- Result: `520 passed in 129.01s`.
- Second-pass targeted verification: `pytest tests/test_pipelines_new.py tests/cloud/test_cloud_chain_command.py tests/cloud/test_progress_auditor.py tests/cloud/test_watchdog_wrappers.py -q`
- Result: `376 passed in 151.82s`.
- Final cloud `.pypeline` support verification: `pytest tests/arnold/workflow/test_source_compiler_api.py tests/cli/test_m5_workflow_source_cli.py -q`
- Result: `147 passed in 0.33s`.
