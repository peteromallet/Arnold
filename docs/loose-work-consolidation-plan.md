# Loose Work Consolidation Plan

Date: 2026-06-30

This branch consolidates useful loose VibeComfy work found during a read-only
cleanup survey. The live dirty checkouts are left untouched while their useful
payloads are copied into this scratch worktree and committed in reviewable units.

## Preserve And Land

| Work | Source | Landing route |
| --- | --- | --- |
| Skill split and RunPod acceptance suite | `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` | Import tracked changes plus source/docs/tests untracked files. Exclude `.codex_tmp/` and generated `artifacts/`. |
| Discovery widget recovery | `fix/discovery-widget-recovery` commit `e747a91f` | Cherry-pick or reapply onto this branch. |
| Agent edit dirty worktrees | `/private/tmp/vibecomfy-*` agent worktrees | Import each dirty diff as its own commit. Branch tips are already represented on `origin/main`; dirty diffs are the valuable part. |
| Fix45 dirty worktree | `/Users/peteromalley/Documents/reigh-workspace/vibecomfy-fix45-worktree` | Import tracked source/test diff. Exclude generated `.codex_tmp/` and `external_workflows`. |
| Local main dirty docs/cloud tweaks | `/Users/peteromalley/Documents/reigh-workspace/vibecomfy-discovery-widget-recovery` | Import after checking overlap with the Fix45 worktree. |

## Defer Or Delete After Approval

| Item | Recommendation |
| --- | --- |
| `.codex_tmp/` and `artifacts/` in the current checkout | Delete after useful conclusions land. |
| `.codex_tmp/` and `external_workflows` in `vibecomfy-fix45-worktree` | Delete after source/test work lands. |
| Clean duplicate branches `codex/authoring-contract-cleanup`, `codex/empty-plan-rpe-hardening`, `codex/guard-assessment-fixes`, `exp/unknown-showtext-risk` | Remove after approval. |
| Dirty-pinned `agent/*`, `codex/fix45-hivemind-ranking`, `fix/precedent-domain-filter` branches/worktrees | Remove only after this consolidation branch preserves their payloads and tests pass. |
| Draft PR #120 | Keep. Active remote PR. |

## Out Of Scope For This Branch

- `/Users/peteromalley/Documents/reigh-workspace/vibecomfy-backups` belongs to
  `banodoco/reigh-workspace`.
- `/Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run`
  belongs to `banodoco/reigh-app`.
- The configured cloud host was not reachable over SSH, so cloud workspaces were
  not inspected.
