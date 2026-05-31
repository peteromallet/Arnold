# arnold-paf salvage bundle (20260531-211812)

This preserves the unique, non-arnold-epic payload from the dirty arnold-paf worktree before cleanup.

- Source worktree: /Users/peteromalley/Documents/.megaplan-worktrees/arnold-paf
- Source branch: arnold-paf
- Excluded branch: arnold-epic (left untouched)
- Shared base: 04a87ebb3a737ce199248a18f031ea681aa65f3a

Files:
- tracked-unique.patch: dirty tracked changes whose paths were not changed by arnold-epic since the shared base, excluding .megaplan/plans generated receipts.
- untracked/: untracked files that do not exist in arnold-epic, excluding temporary helper scripts.
- untracked-files.txt: manifest of copied untracked files.

Apply later after arnold-epic lands or is explicitly opened for reconciliation.
