# Loose Work Cleanup - 2026-07-05

## Landed Locally

- Local item-zero dirty work was checkpointed onto `main` as `937d8302`.
- `origin/editible-install` was merged into `main` as `9c423980`.
- Native platform follow-up stack `origin/megaplan/m1-side-effect-reconcile-and-20260704-1634` through `origin/megaplan/m6-platform-docs-conformance-20260705-0039` was merged into `main` as `eb446b4f`.
- Cloud `/workspace/arnold` `.pypeline` support was already covered by the m6 merge; remaining generated hash/docs updates were ported as `242380f6`.
- Useful survivor from `integrate-cloud-hardening-20260703` was salvaged as `a13b9abc`; stale implementation hunks were superseded by newer cloud status/repair contracts.
- Merge contract fixes were committed as `e948d38d`; focused verification passed: `520 passed`.
- Local `editible-install` now points at the same commit as local `main`: `e948d38d`.

## Delete-Ready After Approval

Positive evidence: `git cherry main <ref>` is `+0` after consolidation.

- Local branches: `codex/supervise-repair-queue`, `megaplan/m2-routing-validator-and-20260703-1535-push`, `resident-status-snapshot`.
- Remote branches: `origin/editible-install`, `origin/resident-status-snapshot`.
- Old native-composition autopublish stack: `origin/megaplan/m0-composition-contract-and-20260702-1541`, `origin/megaplan/m1-megaplan-compositional-20260703-0954`, `origin/megaplan/m2-routing-validator-and-20260703-1535`, `origin/megaplan/m3-general-nested-workflow-20260703-1708`, `origin/megaplan/m4-tree-graph-trace-and-audit-20260703-2220`, `origin/megaplan/m5-composite-resume-and-start-20260704-0019`, `origin/megaplan/m6-composition-docs-and-20260704-0158`.
- New native-platform autopublish stack now merged: `origin/megaplan/m1-side-effect-reconcile-and-20260704-1634`, `origin/megaplan/m2-security-broker-and-20260704-1739`, `origin/megaplan/m3-shared-library-packs-and-20260704-1943`, `origin/megaplan/m4-durable-substrate-and-20260704-2124`, `origin/megaplan/m5-worker-fleet-supervision-20260704-2252`, `origin/megaplan/m6-platform-docs-conformance-20260705-0039`.
- `origin/preserve/cloud-arnold-chain-init-20260703-015121` and `origin/preserve/native-python-m7-audit-20260703-0152` are patch-equivalent to consolidated `main`.

## Park / Inspect, Not Delete Yet

- `origin/consolidate/repair-watchdog-tail-20260703`: still `cherry +19`. PR #134 was merged, but many remaining patches are not patch-equivalent after the new consolidation. Needs selective review, not wholesale merge.
- `integrate-cloud-hardening-20260703`: still reports `cherry +1` because only the useful non-stale slice was salvaged. Treat remaining branch as superseded/stale, but review before delete if you want proof per hunk.
- Archive/safety refs with unique patches: `origin/archive/cloud-tiered-m1-cloud-safe-repair-20260703`, `origin/archive/cloud-tiered-m2-correctness-20260703`, `origin/archive/engine-watchdog-runner-20260703`, `origin/archive/live-watchdog-supervisor-20260703`, `origin/archive/snapshot-arnold-m1-m6-wip-20260703`, `origin/archive/snapshot-arnold-m7-m8-wip-20260703`.
- Preserve refs with unique patches: `origin/preserve/cloud-native-composition-current-20260703-0355`, `origin/preserve/cloud-native-composition-evidence-20260703-0152`, `origin/preserve/cloud-native-composition-source-20260703-015147`, `origin/preserve/local-dirty-20260703-015050`, `origin/preserve/local-dirty-cloud-push-20260703`.

## Worktrees / Cloud

- Registered prunable worktree metadata: `/private/tmp/arnold-rootfix`.
- Clean detached tmp worktrees: `/private/tmp/arnold-cloud-fix`, `/private/tmp/arnold-editible-hotfix`.
- `Arnold-resident-status-snapshot` is obsolete by patch evidence but has dirty incident-ledger runtime files; remove only after approving loss of those generated events.
- Hetzner status reported 22 known cloud sessions complete and no mutating chain tmux sessions. Cloud workspaces still contain runtime dirt/logs; source work from `/workspace/arnold` was ported.
- Arnold-specific editable-install replacement: local yes (`editible-install -> e948d38d`); remote/cloud not updated in this pass.

## Local Junk Candidates, Not Deleted

- `node_modules/`
- `._*` AppleDouble files: `arnold_pipelines/megaplan/._auto.py`, `arnold_pipelines/megaplan/orchestration/._phase_result_classify.py`, `docs/._hetzner-watchdog-meta-loop.md`, `tests/arnold_pipelines/megaplan/._test_auto_recover_blocked.py`
- Scratch helpers: `_fix_normalized.py`, `_regenerate_fixtures.py`

## Verification

- `pytest tests/cloud/test_progress_auditor.py tests/cloud/test_watchdog_wrappers.py tests/cloud/test_cloud_chain_command.py tests/resident/test_megaplan_initiatives.py tests/arnold/workflow/test_source_compiler_api.py tests/cli/test_m5_workflow_source_cli.py`
- Result: `520 passed in 129.01s`.
