# Loose Work Consolidation Plan

Date: 2026-06-16

## Rationale

This repository has little branch sprawl, but a lot of high-risk loose work in
dirty worktrees. The cleanup target is to preserve or land useful work first,
then delete branches, worktrees, and generated artifacts only after explicit
approval.

Item zero was checked first: the current `main` checkout is dirty, ahead of
`origin/main` by one commit, and contains the largest loose payload.

## Landscape

| Area | Current state | Verdict |
| --- | --- | --- |
| Current `main` checkout | 104 modified files, 1 deletion, 1066 untracked files, 1 unpushed commit | Preserve on a feature branch / PR before cleaning |
| `megaplan/m10-megaplan-flagship-app` | Draft PR #68, 0 changed files, empty unique commit, dirty worktree | Close/delete branch after duplicate dirty payload is preserved on `main` cleanup branch |
| `suspension-decision-routes-validation` | Branch points at `origin/main`, dirty validator/test worktree | Port dirty validator/test work, then remove worktree and branch |
| `suspension-decision-routes-validation-rerun2` | Branch points at `origin/main`, logs-only worktree | Remove worktree and branch after approval |
| Non-branch state | No stashes, no interrupted ops, no submodules, no sibling clones, no cloud config | Nothing to port except dirty/untracked artifacts |
| Codespaces | `gh codespace list` blocked by missing `codespace` scope | Manual/token check required before claiming none exist |

## Everything Valuable Lands Here

| Work | Evidence | Lands as |
| --- | --- | --- |
| Structured output template registry and handler | New `template_registry.py`, `handlers/structured_output.py`, related tests and handler/prompt changes | Feature PR from current dirty `main` checkout |
| MiMo/Kimi provider integration and model seam changes | `arnold/agent/providers/pool.py`, `model_seam.py`, `tests/test_kimi_install_smoke.py` | Same feature PR |
| Engine isolation simplification | `execution_environment.py` simplification, `test_engine_isolation.py`, deletion of old execution environment test | Same feature PR |
| CLI error extraction and authority/evidence updates | `auto.py`, `authority_readers.py`, recovery/evidence tests | Same feature PR |
| Shannon tmux-death detection and chain manifest updates | Dirty worktree payload is byte-identical in current `main` and the m10 worktree | Same feature PR from current `main`; m10 copy is duplicate |
| Suspension schema-key conformance validation | Dirty `validator.py` and `test_validator.py` in `suspension-decision-routes-validation` worktree, not present on current `main` | Separate small PR or cherry-pick/port into the feature branch after checkpointing |
| `.megaplan/mimo-boundary-investigation/` | 33 investigation result files, 184K | Preserve as evidence if still useful; otherwise archive/delete after approval |
| `.megaplan/tickets/` | 14 open ticket markdown files | Keep |
| `sync-skills.sh` | Untracked dev utility | Decide commit vs personal/untracked; do not delete by default |

## Everything Else Can Be Deleted After Approval

| Item | Positive evidence |
| --- | --- |
| Local branches `suspension-decision-routes-validation` and `suspension-decision-routes-validation-rerun2` | Both point at `origin/main`; `main..<branch>` is empty; `cherry +0` |
| Worktree `suspension-decision-routes-validation-rerun2` | No tracked diff; one untracked run log |
| `megaplan/m10-megaplan-flagship-app` branch and remote branch | PR #68 has 0 additions, 0 deletions, 0 changed files; unique commit is empty |
| PR #68 | Draft PR with no files/comments/reviews; branch commit carries no content |
| `chain.log` in m10 worktree | Runtime execution artifact |
| `.megaplan/system_logs/` in current checkout | 1015 generated JSON event logs, 4.0M |
| Worktree `.megaplan/run-logs/` and `.megaplan/system_logs/` | Generated run artifacts |
| `*.bak` files | Backup copies of tracked files |
| T19/T20 generated placeholder pipeline stubs | TODO-only generated placeholders, no real implementation |

## Corrections From Investigation

- The open draft PR rule alone would suggest keeping `megaplan/m10-megaplan-flagship-app`, but direct PR and diff checks show PR #68 is empty. The real dirty source changes in that worktree are byte-identical to the current dirty `main` checkout, so preserving the current checkout preserves them.
- The two suspension branches look safe to delete as branch refs, but one associated worktree has unique uncommitted validator/test work. The branch cleanup must not remove that worktree until the diff is ported or checkpointed.
- The main cleanup risk is not remote branch history. It is uncommitted source/test work in local checkouts.

## Execution Order

1. Checkpoint the current dirty `main` payload onto a feature branch without disturbing the live checkout, including valuable untracked source/tests/briefs and excluding generated logs/backups.
2. Port or checkpoint the suspension validator/test dirty diff.
3. Run focused tests for the checkpointed feature work and the suspension validator change.
4. Push the preservation branch or PR so useful work is recoverable remotely.
5. After explicit approval, delete generated logs/backups and remove logs-only worktrees.
6. After explicit approval, close/delete empty PR #68 and delete its local/remote branch.
7. After explicit approval, remove the suspension worktrees and delete the two suspension local branches.
8. Re-run `git status --short --branch`, `git branch`, `git branch -r`, and `git worktree list --porcelain` to prove the cleanup state.

## Open Questions

- Codespaces could not be surveyed because `gh codespace list` returned HTTP 403 for missing `codespace` scope. This requires either `gh auth refresh -h github.com -s codespace` or a browser check.
- Decide whether `.megaplan/mimo-boundary-investigation/` should be committed as evidence or deleted after an external/archive checkpoint.
- Decide whether `sync-skills.sh` is project tooling or a personal script.

## Provenance

Read-only DeepSeek fan-out ran from:

`/tmp/loose-branches-deepseek-20260616-100509`

Reports:

- `results/01-current-main-dirty-payload.txt`
- `results/02-m10-flagship-pr-branch.txt`
- `results/03-suspension-validation-worktrees.txt`
- `results/04-nonbranch-loose-state.txt`

All four agents completed successfully.
