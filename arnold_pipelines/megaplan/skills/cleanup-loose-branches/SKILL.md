---
name: cleanup-loose-branches
description: >
  Force every loose piece of git work, locally and on the Hetzner cloud
  worker, to a binary outcome: merge and push it to the real base branch, or
  delete it with a strong reason. Survey dirty working trees, untracked
  files, unpushed commits, branches, worktrees, stashes, detached HEADs, and
  interrupted operations; use DeepSeek subagents for ambiguous merge-vs-delete
  calls; and perform destructive actions only after explicit approval.
---

# cleanup-loose-branches

## Goal

This skill exists to finish the cleanup, not to admire the mess.

For every loose item, ask one question: **does this land on the base branch?**

- **Yes:** merge it, push it, then delete the leftover branch/worktree/stash.
- **No:** delete it, with a strong reason: abandoned, superseded, duplicate, or junk.

`KEEP` is rare. It is only for an explicitly active item or an interrupted operation that must be resolved first. The end-state is strict: **nothing loose remains.**

## Rules

1. Dirty work is in scope. Uncommitted changes, untracked files, and unpushed commits must land or be deleted.
2. A checkpoint is a seatbelt, not an outcome. A WIP branch, patch file, or scratch worktree does not count as cleanup.
3. Survey first, destroy later. The survey phase is read-only. Branch deletion, stash drop, worktree removal, reset, and remote deletion require explicit approval for that item.
4. The remote machine counts. Loose work on the Hetzner worker gets the same merge-or-delete treatment as local work.
5. `KEEP-UNTIL-X` must name a concrete unblocker and a re-trigger. "Discuss later" is not allowed.
6. The final report must cross-reference every surveyed row and show it as landed, deleted, or still blocked for one named reason.

## Phase 1 - Survey everything

Resolve the base branch and fetch first:

```bash
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
BASE=${BASE:-main}
git fetch --all --prune --quiet 2>/dev/null || true
```

### Local survey

Run these in order. Dirty state comes first because it is easiest to lose.

```bash
# 1. Current checkout: dirty, untracked, unpushed
git status --short --branch
git diff --stat HEAD
git ls-files --others --exclude-standard
git log --oneline @{u}..HEAD 2>/dev/null || true

# 2. Worktrees
git worktree list --porcelain
find "$PWD" -maxdepth 4 -type d \( -name '.megaplan-worktrees' -o -name 'worktrees' \) 2>/dev/null

# 3. Local branches
git for-each-ref \
  --format='%(refname:short)|%(upstream:short)|%(upstream:track)|%(committerdate:relative)|%(contents:subject)' \
  refs/heads/

# 4. Stashes
git stash list --format='%gd|%cr|%s'
for s in $(git stash list --format='%gd'); do git stash show --stat "$s"; done

# 5. Detached HEADs and interrupted operations
git symbolic-ref -q HEAD || git rev-parse --short HEAD
ls .git/MERGE_HEAD .git/CHERRY_PICK_HEAD .git/REVERT_HEAD .git/REBASE_HEAD 2>/dev/null
ls -d .git/rebase-apply .git/rebase-merge .git/sequencer 2>/dev/null
```

For each worktree or branch that looks live, inspect it directly:

```bash
git -C <path> status --short --branch
git -C <path> diff --stat HEAD
git -C <path> ls-files --others --exclude-standard
git -C <path> log --oneline @{u}..HEAD 2>/dev/null || true
git rev-list --left-right --count "$BASE...<branch>"
git cherry "$BASE" "<branch>" | grep -c '^+' || true
git diff --stat "$BASE...<branch>"
git merge-tree "$(git merge-base "$BASE" "<branch>")" "$BASE" "<branch>" | grep -c '<<<<<<<' || true
```

If the current checkout is dirty and valuable, make a temporary checkpoint before you touch it. Capture both tracked and untracked material, then continue to the merge-or-delete decision:

```bash
git diff HEAD > /tmp/cleanup-working-tree.patch
git ls-files --others --exclude-standard > /tmp/cleanup-untracked.txt
tar -czf /tmp/cleanup-untracked.tgz $(git ls-files --others --exclude-standard) 2>/dev/null || true
```

Those files are temporary. Delete them after the row is safely landed or deleted.

### Remote Hetzner worker survey

The remote machine is part of the skill:

- `ssh root@159.69.51.216`
- `docker exec megaplan-cloud-agent bash -lc '...'`

You must inspect `/workspace/arnold`, the known epic workspaces, and any other git checkout under `/workspace/*`, including worktrees. Start by expecting at least:

- `/workspace/arnold`
- `/workspace/python-shaped-workflow-authoring`
- `/workspace/vibecomfy-god-file-splits`
- `/workspace/vibecomfy-per-workflow-window-chat-20260628`

Discover every checkout:

```bash
ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
set -euo pipefail
find /workspace -mindepth 1 -maxdepth 3 -type d \
| while read -r d; do git -C \"\$d\" rev-parse --show-toplevel 2>/dev/null || true; done \
| sort -u
"'
```

Survey every discovered repo with the same parity checks you use locally:

```bash
ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
set -euo pipefail
survey_repo() {
  repo=\$1
  echo ===== \$repo =====
  git -C \"\$repo\" remote -v || true
  git -C \"\$repo\" status --short --branch || true
  git -C \"\$repo\" diff --stat HEAD || true
  git -C \"\$repo\" ls-files --others --exclude-standard || true
  git -C \"\$repo\" log --oneline @{u}..HEAD 2>/dev/null || true
  git -C \"\$repo\" for-each-ref \
    --format='\''%(refname:short)|%(upstream:short)|%(upstream:track)|%(committerdate:relative)|%(contents:subject)'\'' \
    refs/heads/ || true
  git -C \"\$repo\" stash list || true
  git -C \"\$repo\" worktree list --porcelain || true
  test -f \"\$repo/.git/MERGE_HEAD\" && echo in-progress:MERGE_HEAD
  test -f \"\$repo/.git/CHERRY_PICK_HEAD\" && echo in-progress:CHERRY_PICK_HEAD
  test -f \"\$repo/.git/REVERT_HEAD\" && echo in-progress:REVERT_HEAD
  test -f \"\$repo/.git/REBASE_HEAD\" && echo in-progress:REBASE_HEAD
  test -d \"\$repo/.git/rebase-apply\" && echo in-progress:rebase-apply
  test -d \"\$repo/.git/rebase-merge\" && echo in-progress:rebase-merge
  test -d \"\$repo/.git/sequencer\" && echo in-progress:sequencer
}
for repo in \$(find /workspace -mindepth 1 -maxdepth 3 -type d \
  | while read -r d; do git -C \"\$d\" rev-parse --show-toplevel 2>/dev/null || true; done \
  | sort -u); do
  survey_repo \"\$repo\"
done
"'
```

Remote worktrees that are not obvious from the main repo still count:

```bash
ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
find /workspace -type d \( -name .megaplan-worktrees -o -name worktrees \) -print 2>/dev/null
"'
```

For every returned path, run the same `git -C <path> status`, `diff --stat`, `ls-files --others`, and `log @{u}..HEAD` checks.

## Phase 2 - Judge every row

Do not leave the survey as a pile of facts. Every row gets a verdict.

### Merge

Use `YES-MERGE` when the item contains wanted work:

- useful uncommitted or untracked files
- unique commits that should land
- a stash with real work not present elsewhere
- a remote checkout ahead of upstream with wanted changes
- messy work that is still the best version of the idea

Say exactly how it lands:

- merge branch to `BASE`
- cherry-pick specific commits to `BASE`
- port selected files into a temporary consolidation branch, then merge and push
- consolidate several loose items together, then merge and push

### Delete

Use `DELETE` when you have a real reason:

- already consumed by `BASE` or an equivalent landed branch
- exact duplicate of work preserved elsewhere
- superseded by better landed work
- generated residue or obvious junk
- low-signal abandoned residue after inspection found no unique value

Deletion requires positive evidence. "Old" is not enough by itself.

### Keep, but only until X

Use `KEEP-UNTIL-X` only when:

- the user explicitly says the item is still active, or
- the repo is mid-merge/rebase/cherry-pick/revert and must be resolved first

Every `KEEP-UNTIL-X` row must name:

- the unblocker
- the re-trigger condition
- who or what owns that next step

Example: `KEEP-UNTIL-X: resolve remote rebase in /workspace/python-shaped-workflow-authoring, then rerun this skill before any branch deletion.`

## Phase 3 - Use DeepSeek when the call needs judgement

Dispatch a DeepSeek subagent when the row is valuable but unclear:

- dirty worktree with unclear signal
- branch with many commits or conflict risk
- stale branch that might still hide missing work
- overlap across local and remote checkouts
- uncertainty about whether work is already superseded
- uncertainty about the safest landing plan

For one to four rows, use `launch_hermes_agent.py`. For larger batches, fan out.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=/tmp/cleanup-briefs \
  --output-dir=/tmp/cleanup-results \
  --max-workers=5 \
  --toolsets="file,web,terminal" \
  --task-timeout=1800 \
  --project-dir="$PWD"
```

Brief shape:

```markdown
You are a read-only DeepSeek cleanup judge for <repo>.

Goal: decide whether <item> should be YES-MERGE or DELETE.

Known facts:
- <path or branch>
- <ahead/behind, unique commits, dirty files, overlap>
- <what is uncertain>

Guardrail:
- Read-only commands only.
- Do not commit, switch, merge, rebase, reset, stash apply/pop/drop, delete, push, or edit files.

Questions:
1. Is this still valuable, or already superseded/junk?
2. If it lands, what is the safest merge plan?
3. If it is deleted, what exactly would be lost?
4. Give a firm verdict: YES-MERGE, DELETE, or rare KEEP-UNTIL-X.
```

Cross-check any load-bearing claim before you act.

## Phase 4 - Present the binary table

Use one decision table for the whole sweep:

```text
ITEM                         LOCATION              STATE              VERDICT         PLAN / REASON
dirty checkout               local:/workspace/...  dirty + ahead 2    YES-MERGE       port selected files, merge to main, push
feature/foo                  remote:/workspace/... branch ahead 5      YES-MERGE       rebase or cherry-pick, push, then delete branch
old/docs-spike               local                 branch, cherry +0   DELETE          already consumed by main
rebase in progress           remote:/workspace/... rebase-merge        KEEP-UNTIL-X    resolve rebase, rerun cleanup, then decide
```

Below the table, include:

- what would be lost for each `DELETE` row
- which rows were judged directly vs. by DeepSeek
- the unblocker for each `KEEP-UNTIL-X`

Then stop for approval before destructive actions.

## Phase 5 - Act after approval

Go from lower blast radius to higher blast radius. Never delete the source before the landed result is verified and pushed.

### Safe order

1. Prune stale worktree metadata.
2. Land approved `YES-MERGE` rows.
3. Run practical tests for the landed rows.
4. Push the target branch and verify the push succeeded.
5. Delete only the approved residue.
6. Re-survey and cross off every original row.

### Prune metadata

```bash
git worktree prune --verbose
```

### Land approved work

For a normal branch:

```bash
git switch "$BASE"
git pull --ff-only origin "$BASE"
git merge --no-ff <branch>
# if merge conflicts, stop and resolve; do not continue on autopilot
<run practical tests>
git push origin "$BASE"
test "$(git rev-parse HEAD)" = "$(git ls-remote origin "refs/heads/$BASE" | cut -f1)"
```

Only after the merge is tested and the push is confirmed may you delete the source:

```bash
git branch -d <branch>
git push origin --delete <branch>
```

For dirty working tree material, prefer a scratch worktree so you do not mutate the live checkout:

```bash
git worktree add /tmp/cleanup-merge "$BASE"
# port the approved files into /tmp/cleanup-merge, commit there, test there, push there
```

For remote rows, run the same flow inside the remote wrapper:

```bash
ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
cd <repo>
git switch <branch-or-base>
git status --short --branch
# apply the approved merge, cherry-pick, or file-port plan
# run practical tests
git push origin <target>
"'
```

Again: do not delete the remote source branch, stash, or worktree until the pushed result is confirmed.

### Delete approved residue

Examples:

```bash
git log --oneline "$BASE..<branch>"
git branch -D <branch>
git push origin --delete <branch>
git stash drop stash@{N}
git worktree remove <path>
rm -f /tmp/cleanup-working-tree.patch /tmp/cleanup-untracked.txt /tmp/cleanup-untracked.tgz
```

Remote:

```bash
ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
cd <repo>
git branch -D <branch>
git push origin --delete <branch>
git stash drop stash@{N}
git worktree remove <path>
"'
```

Never batch-delete items that were not individually approved.

## Phase 6 - Re-survey and close the loop

Rerun the local and remote survey commands. Then compare the results row-by-row against the original decision table.

Required close-out:

- every original row is marked `LANDED`, `DELETED`, or `STILL BLOCKED`
- every `KEEP-UNTIL-X` row still has one concrete unblocker
- the remote machine was rechecked, not assumed clean
- temporary checkpoint files were removed or intentionally retained for a named reason

Report shape:

```text
Surveyed:
- local checkout
- local worktrees
- local branches
- stashes
- interrupted states
- remote worker repos under /workspace/*

Decisions:
- YES-MERGE: N
- DELETE: N
- KEEP-UNTIL-X: N

Executed after approval:
- landed and pushed: N
- local branches deleted: N
- remote branches deleted: N
- stashes dropped: N
- worktrees removed: N

Cross-check:
- <row 1>: LANDED
- <row 2>: DELETED
- <row 3>: STILL BLOCKED - <exact blocker>
```

The right finish is boring: when someone asks "anything loose left?", the answer should be `no`, or one precisely named blocker.
