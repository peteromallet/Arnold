# Loose-work consolidation plan — 2026-07-10

## Purpose and guardrail

The current Arnold checkout and Hetzner volume contain source, tests, plans,
stashes, checkpoints, and generated run state. This plan makes every payload
accountable. Useful code and durable intent land on `editible-install`, are
pushed, and then refresh inactive Arnold cloud workspaces from that exact remote
tip. `main` remains the eventual canonical merge target. Deletions, stash drops,
worktree removals, and cloud-volume cleanup remain separately approval-gated.

## Local source of truth

| Payload | Evidence | Landing decision |
| --- | --- | --- |
| Current `main` dirty payload | 45 tracked paths; source/tests/docs; 529 additions and 232 deletions | Preserve in a scratch checkpoint, then land through `editible-install`. |
| Local `main` commits | `84841d6e4` patch-unique; `61ce72a55` and `6229e6ff0` patch-equivalent to `origin/main` | Rebase/cherry-pick the Grok endpoint commit only; let the duplicate patches be absorbed by `origin/main`. |
| Untracked initiative and seven design/repair documents | Durable North Star, chain, brief, research, parity plans | Commit on the consolidation branch after content review. |
| `.tmp/` | 8.7 MB of agent briefs/results/model output | Treat as reproducible scratch evidence; retain outside Git until the consolidation PR is accepted, then delete only with approval. |
| Two `.megaplan/*.patch` files | Native implementation/test diffs | Compare patch IDs against `origin/main`; cherry-pick any uncovered source/test hunk, otherwise mark delete-ready. |

## Local branches and worktrees

| Item | Verdict | Dependency |
| --- | --- | --- |
| `editible-install` + `/private/tmp/arnold-fix` | Keep: 19 patch-unique commits and draft PR #203 | Resolve/land the active PR before changing the branch or worktree. |
| `push-editible-mergefix` + detached worktree | Keep pending the `editible-install` decision | Its four patch-unique commits stack on `editible-install`; extract/land only the delta that survives PR reconciliation. |
| `push-main-mergefix` + two detached `/private/tmp/arnold-push-main*` worktrees | Delete-ready after local main is reconciled | No patch is unique to `origin/main`. |
| `worktree-watchdog-snapshot-staleness` + `.claude` worktree | Delete-ready | `cherry +0` versus `main`; its patch is already landed. |

## Hetzner inventory

The live `megaplan-cloud-agent` at `159.69.51.216` has four active tmux
sessions and the following in-scope Arnold workspaces. Active sessions and
dirty workspace payloads must not be reset or removed.

| Workspace / payload | Verdict | Landing or preservation route |
| --- | --- | --- |
| `/workspace/megaplan-native-parity-corrective/Arnold` | Highest risk: 40 dirty paths, 7 stashes, 1 unpushed commit | Export each stash and the dirty source/plan delta; integrate code/intention on the consolidation branch before any cleanup. |
| `/workspace/extension-reality-chain-restart-continuation/arnold` | Keep: dirty code/tests, 1 stash, active branch | Preserve branch/stash; reconcile only after its live chain is no longer active. |
| `/workspace/canonical-run-state-control-plane/arnold` | Keep: dirty incident state plus 1 stash | Separate generated incident ledger from source before deciding whether any stash hunk lands. |
| `/workspace/arnold-chain-guard-fix` and `arnold-chain-guard-min` | Land/reconcile: dirty guard-fix checkout and one unpushed guard commit | Compare against current main and `editible-install`; cherry-pick an uncovered guard fix with focused tests. |
| `/workspace/extension-reality-m3-m4-recovery` | Keep and port: one unpushed recovery commit | Push or cherry-pick its recovery commit before any workspace change. |
| `/workspace/progress-auditor-stage-metrics/Arnold` | Investigate: source change plus run state | Split `cli/status_view.py` from generated ledger/runtime files; land the source delta if unique. |
| `/workspace/arnold`, `custody-control-plane-*`, `superfixer-*`, north-star, canonical and other dirty `main`/`editible-install` checkouts | Keep; likely run-state residue | First preserve their ledger/log diff fingerprints. Only reset after active-session confirmation and source comparison. |
| `/workspace/arnold-cloud-dirty-checkpoint-20260709` | Preserve | It is a named cloud checkpoint; do not treat it as junk. |
| backup directories | Preserve | `loose-work-backups`, `arnold-consolidation-checkpoints`, `arnold-dirty-backups`, and `arnold-hotfix-backups` are explicit recovery artifacts. |

Non-Arnold VibeComfy and Reigh workspaces are out of scope and remain untouched.

## Execution order

1. Create a scratch worktree from `origin/editible-install`; copy the current
   local dirty source/docs/tests into it and record hashes, leaving the live
   checkout byte-identical.
2. Fetch/rebase the scratch integration source onto `origin/editible-install`;
   retain only patch-unique local commits and resolve the dirty delta into
   logical commits.
3. Export all cloud stashes and dirty diffs to timestamped evidence files on the
   cloud volume; classify generated ledger/log output separately from source/docs/tests.
4. Port proven-unique cloud source in this order: guard fixes, recovery commit,
   progress-auditor source, then native-parity source/intention. Run focused tests after each.
5. Push the resulting `editible-install` tip. Do not rely on a local-only
   checkpoint as the final preservation state.
6. On the Hetzner box, for each inactive Arnold workspace that should remain,
   `fetch origin --prune`, check out `editible-install`, and fast-forward it to
   the exact pushed tip. Do not change a workspace with a live tmux session;
   those remain `keep` until their chain finishes. Confirm the shared
   `/workspace/arnold` editable source also resolves at the pushed tip.
7. Merge `editible-install` into `main` through its PR/normal merge route once
   the active stack is resolved.
8. After cloud refresh and main merge, request
   per-item approval to drop stashes, delete residual branches, remove clean
   worktrees, and archive/delete generated cloud state.

## Explicit deletion gates

No destructive step is authorized until the corresponding payload is pushed or
proven generated/redundant. The first approval batch will enumerate each branch,
worktree, stash, checkpoint directory, and cloud workspace with its unique-work
summary.
