# Loose Work Consolidation Plan

Date: 2026-06-25

## Rationale

This repo is mid-epic cleanup. The branch table is not the main risk by itself:
the highest-risk work is the dirty `main` checkout, which contains valuable
custom-node-resolution work that is not committed anywhere. The active epic
branches also share setup commits and overlap semantically in agent panel
contracts, frontend ownership, and compatibility ledgers.

Goal: preserve every valuable payload, land it on `main` through a reviewable
consolidation path, then delete only branches/worktrees with positive evidence
that nothing unique remains.

## Landscape

| Work | Current state | Verdict |
| --- | --- | --- |
| Current `main` checkout | Dirty, no local commits ahead of `origin/main`; 25 tracked files changed plus 6 untracked files | Preserve first as `checkpoint/custom-node-resolution-main-dirty-20260625`; separate landing path |
| `epic/fresh-cleanup-epics-setup` | 2 commits ahead of `main`; pinned worktree has dirty `GOAL.md` edits | Land once, including the dirty goal-file corrections, then delete |
| `epic/messaging-boundary-cleanup-v2/work` | 16 ahead / 0 behind; clean worktree; no existing PR found in local GH query | Land, after removing accidental `custom_nodes.lock` placeholder change |
| `epic/pristine-agent-architecture-followup/work` | 7 ahead / 0 behind; dirty `custom_nodes.lock` placeholder change | Keep and land after messaging, resolving semantic overlap deliberately |
| `epic/pristine-agent-architecture-followup/m1-main-preservation-audit` | Same commit as `main`; cherry +0; no unique files | Delete after approval |
| `vibecomfy-backups` | Sibling directory, not a git repo | Ignore for branch cleanup |

## Valuable Work And Destination

| Work | Lands as |
| --- | --- |
| Custom-node-resolution dirty tree | First checkpoint branch, then its own PR/consolidation after the two agent architecture epics |
| Setup goal/North Star/chain files | Merge into consolidation branch before both active epics |
| Messaging boundary v2 | Merge/PR after setup; keep `TranscriptMessage`, `ResponseDetail`, `ExecutionEvent`, and `AuditArtifact` projection boundary |
| Pristine followup | Rebase/cherry-pick/merge after messaging; keep non-message contract guardrails, ownership extraction, artifact/ledger docs, and tests |

## Delete After Preservation

| Item | Positive evidence |
| --- | --- |
| `epic/pristine-agent-architecture-followup/m1-main-preservation-audit` | `git rev-list --left-right --count main...branch` is `0 0`; `git cherry main branch` is +0; tip is `30e7990d`, same as `main` |
| `epic/fresh-cleanup-epics-setup` | Its two commits are ancestors of both active work branches; delete only after setup files and dirty `GOAL.md` corrections land |
| Active worktrees for setup/messaging/pristine | Remove only after their payloads land and their working trees are clean |

## Critical Corrections

- Both the dirty current checkout and the pristine worktree change
  `custom_nodes.lock` from real WanVideoWrapper SHA
  `df8f3e49daaad117cf3090cc916c83f3d001494c` to literal `pinnedsha`.
  Treat this as junk unless separately justified. Do not land it as part of
  messaging or pristine.
- The current `main` dirty tree is not cleanup residue. It is active
  custom-node-resolution work: missing-node resolver, install confirmation route,
  browser `requires_custom_nodes` lifecycle, workflow ingestion scripts, and
  related tests.
- The two active epic branches are complementary, not duplicates. They overlap in
  docs, contracts, tests, `agent_status_poller.js`, and `vibecomfy_roundtrip.js`.
  Direct `merge-tree` shows changed-in-both files but no textual conflict markers;
  semantic review is still required.
- The first DeepSeek fan-out failed because the Hermes terminal process tool hit
  an Arnold import error before producing reports. The replacement Codex
  read-only investigations produced the usable verdicts.

## Execution Order

1. Preserve current dirty `main` without disturbing the live checkout.
   Preferred route: create `checkpoint/custom-node-resolution-main-dirty-20260625`
   in a scratch worktree or otherwise verify the original diff hash remains
   `942e8a337fd95cde8454202aeba12bd0997b9a93` after snapshot.
2. Create a fresh consolidation branch from current `origin/main`.
3. Port/commit the setup worktree's dirty `GOAL.md` corrections:
   `PYTHONPATH=/Users/peteromalley/Documents/Arnold` and removal of stale prep
   text from the pristine followup goal.
4. Merge `epic/fresh-cleanup-epics-setup`.
5. Merge `epic/messaging-boundary-cleanup-v2/work`, excluding or reverting
   `custom_nodes.lock`.
6. Run focused messaging tests:
   `tests/browser/projection_boundary_helpers.test.mjs`,
   `tests/browser/payload_contracts.test.mjs`,
   `tests/browser/agent_edit_lifecycle_transcript.test.mjs`,
   `tests/test_comfy_nodes_agent_contracts.py`,
   and `tests/test_comfy_nodes_agent_edit.py`.
7. Layer `epic/pristine-agent-architecture-followup/work`, excluding or reverting
   `custom_nodes.lock`. Preserve messaging's transcript/detail semantics while
   keeping pristine's ownership extraction and guardrails.
8. Run focused pristine and overlap tests:
   `tests/test_pristine_architecture_guardrails.py`,
   `tests/test_agent_edit_compatibility_ledger.py`,
   `tests/browser/agent_status_poller.test.mjs`,
   `tests/browser/agent_candidate_actions.test.mjs`,
   `tests/browser/frontend_ownership_regression.test.mjs`,
   plus the messaging tests again.
9. Run the broad practical suite and `git diff --check`.
10. Push the consolidation branch and open a draft PR.
11. Only after the PR is recoverable and verified, delete redundant branches and
    remove clean worktrees with explicit approval.

## Confidence And Open Questions

High confidence:

- Do not delete the dirty current checkout.
- Land messaging boundary v2; it fulfills the original boundary goal.
- Land pristine followup; it fulfills non-message followup hardening, but not as
  an unreviewed blind merge.
- Delete `m1-main-preservation-audit` after approval.

Open questions to close during execution:

- Whether custom-node-resolution should land before or after the architecture
  consolidation. Current recommendation is after, because it is separate work
  but overlaps agent-edit files.
- Whether the broad browser smoke failures noted in pristine M4 are still
  present after consolidation or already fixed elsewhere.
- Whether GitHub PR state for these new branches exists; local `gh` queries
  intermittently failed inside one Codex subagent, while the main thread had GH
  access earlier.

## Provenance

- DeepSeek fan-out attempted at `/tmp/vibecomfy-loose-branches-20260625-113022`;
  no usable reports were produced before the fan was killed.
- Codex read-only reports:
  - `/tmp/vibecomfy-loose-branches-20260625-113022/results/01-messaging-boundary.codex.txt`
  - `/tmp/vibecomfy-loose-branches-20260625-113022/results/02-pristine-followup.codex.txt`
  - `/tmp/vibecomfy-loose-branches-20260625-113022/results/03-current-main-dirty.codex.txt`
  - `/tmp/vibecomfy-loose-branches-20260625-113022/results/04-overlap-merge-strategy.codex.txt`
