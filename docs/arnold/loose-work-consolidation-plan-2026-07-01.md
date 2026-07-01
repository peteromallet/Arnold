# Loose Work Consolidation Plan - 2026-07-01

## Rationale

This cleanup found that the highest-risk Arnold work is not an abandoned branch.
It is the current `main` checkout: 21 unpushed commits plus a large uncommitted
payload that relocates Megaplan artifacts, tightens conformance gates, and adds
AgentBox/cloud resident functionality.

The Hetzner worker is in scope. After local consolidation, the cloud
`/workspace/arnold` checkout must be on `editible-install`, contain the latest
Arnold code, and continue to run from an editable install.

## Landscape

| Work | Current state | Verdict |
| --- | --- | --- |
| Local `main` ahead commits | 21 commits ahead of `origin/main` | Land/push |
| Current dirty checkout | 300 tracked changed paths, 297 untracked files | Checkpoint, test, land |
| `stash@{0}` | Partial skill restore snapshot | Drop after checkpoint |
| `stash@{1}` | Tracked-file subset of dirty checkout | Drop after checkpoint |
| `editible-install` local | `cherry +0` vs local `main` | Delete after safe |
| `origin/editible-install` | Divergent cloud/watchdog line plus sync commits | Port useful commits or supersede with latest local code |
| `editible-install-local` worktree | Clean, one commit behind `origin/editible-install` | Remove after cloud line is superseded |
| `native-representation-alignment-inputs` | Clean reference worktree, one docs/layout commit | Park until briefs cleanup is complete |
| Recovery remotes | `cherry +0`, old snapshots | Delete after approval |
| Hetzner `/workspace/arnold` | `editible-install`, only dirty runtime log | Sync latest code here, keep active service |
| Hetzner VibeComfy workspaces | Dirty non-Arnold code | Preserve separately in VibeComfy cleanup |

## Execution Order

1. Record a safety checkpoint of the current Arnold checkout.
2. Stage and commit the complete local Arnold dirty payload.
3. Run focused tests for conformance, cloud, resident, and chain changes.
4. Push the resulting latest code to a durable branch.
5. Update `editible-install` to the same latest code and push it.
6. On Hetzner, fetch/reset `/workspace/arnold` to `origin/editible-install`.
7. Refresh the editable install in the cloud environment.
8. Verify the cloud checkout branch, commit, package import path, and resident process.
9. Only after explicit approval, delete stale local/remote branches and stashes.

## Delete Candidates Pending Approval

No destructive action is approved yet. Candidates:

- `stash@{0}` after the checkpoint commit exists.
- `stash@{1}` after the checkpoint commit exists.
- local `editible-install`.
- local `editible-install-local` branch and `/Users/peteromalley/Documents/Arnold-editible-install` worktree.
- remote `origin/recovery/native-python-m8-conformance-20260630`.
- remote `origin/recovery/native-python-working-tree-20260630`.
- remote `origin/editible-install` only if it is intentionally replaced by the new latest-code branch state.

## Provenance

Read-only DeepSeek fan-out results:

- `/tmp/arnold-loose-branches-20260701-030814/results/01-current-dirty-and-stashes.txt`
- `/tmp/arnold-loose-branches-20260701-030814/results/02-local-branches-worktrees.txt`
- `/tmp/arnold-loose-branches-20260701-030814/results/03-cloud-workspaces.txt`
