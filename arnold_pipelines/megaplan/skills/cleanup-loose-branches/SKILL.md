---
name: cleanup-loose-branches
description: >
  Survey every place loose work hides in a git repo — starting with the
  current checkout's own uncommitted/untracked/unpushed work, then local
  branches, all worktrees (`.megaplan-worktrees`, `.megaplan/bakeoffs/*`,
  agent-tool worktrees), stashes, detached HEADs, interrupted rebases/merges,
  submodules, remote branches on origin and other remotes, fork PR refs,
  sibling repo variants, other clones of this repo elsewhere on disk,
  the megaplan-cloud machine (Hetzner box) and every workspace on it, and
  GitHub Codespaces — classify each as
  land-on-main / delete / parked with reasoning, and act only on explicit
  per-item approval. Use when the user says "clean up loose branches",
  "prune branches", "what branches can I delete", "clean up worktrees",
  "review my stashes", "what's lying around in this repo", or asks for
  branch / worktree / stash housekeeping.
---

# cleanup-loose-branches

> **TL;DR** — First durably pause any Megaplan chain actively preparing in the target repo → survey every loose-work location read-only → fan out DeepSeek subagents to classify each as land / cherry-pick / delete / keep → write a consolidation plan → execute it (useful work onto a branch, everything else staged *ready-to-delete*). Nothing is deleted without your explicit per-item OK.

## Phase 0 — stop active plan preparation first

On first invocation, before surveying or launching cleanup investigators, identify every
Megaplan chain in the target repo whose persisted active phase is `prep`. Durably pause
each one through the supported chain control surface:

```bash
python -P -m arnold_pipelines.megaplan chain pause \
  --spec <initiative-chain.yaml> \
  --project-dir <target-repo> \
  --reason "Loose-work cleanup requires a stable repository snapshot" \
  --actor cleanup-loose-branches
```

Then query chain status and require returned/persisted evidence that the chain and current
plan are paused before continuing. Report the chain spec, plan name, prior phase, pause
result, and verification result. If the chain finishes or leaves `prep` during the pause,
re-read status and report the actual state; do not claim it was paused. If durable pause
cannot be verified, stop the cleanup and report the blocker.

Scope this containment narrowly: pause only chains actively preparing against the target
repo. Do not pause unrelated repositories, already executing/reviewing chains, resident
agents, or cloud sessions. Never use `kill`, `pkill`, `killall`, tmux cleanup, or process
termination as a substitute. Do not resume a chain automatically when cleanup finishes;
resumption requires an explicit user instruction.

## The four cleanup phases — do this, in order

Run Phase 0, then these four phases in order. **Lean on DeepSeek subagents in every phase** — they are
the cheap default for reading wide, understanding nuances, and untangling supersession,
not a heavyweight escalation. Flip "should a subagent do this?" into "is there any reason
it can't?" Start the survey immediately — don't ask "want me to look around?" or "should I
make recommendations?"

1. **Survey (read-only).** Sweep every place loose work hides — current working tree,
   worktrees, branches, stashes, remotes/PRs, interrupted ops, submodules, detached HEADs,
   sibling repos, other clones, the megaplan-cloud machine, codespaces. Produce the raw
   map. *Subagents: fan the survey sections across DeepSeek agents so the main thread stays
   lean — one agent per area, read-only.*
2. **Investigate & classify (DeepSeek fan-out → go/no-go).** For every item with real
   ambiguity (supersession, "is this useful?", conflict surface, cloud-only work), fan out
   read-only DeepSeek briefs — one decision area per agent — to convert uncertainty into a
   verdict. Collapse the whole survey into a decisive table: land / cherry-pick / delete /
   keep. The goal of investigation is a go/no-go decision, not more notes. *Subagents: the
   most subagent-heavy phase.*
3. **Strategy (write the merge plan).** Write a durable consolidation plan: where every
   valuable piece lands, the merge order, how to handle complex/overlapping merges (shared
   bases, divergent test contracts), and what's junk-ready vs. keep. The plan doc — not the
   chat — is the source of truth. *Subagents: use DeepSeek to map supersession and conflict
   surfaces, and to draft the plan.*
4. **Execute (run the merges).** Work the plan, lowest blast-radius first. Land every useful
   piece onto the consolidation branch (merge/cherry-pick/PR until tests pass). Everything
   else is **staged ready-to-delete — not deleted**: deletion waits for explicit per-item
   approval. *Subagents: hand the heavy merge/conflict/test loops to agents in parallel
   where the work is independent.*

Stop and ask the user at two points only: the Phase 2 → Phase 3 handoff (before you commit
to a consolidation strategy), and before any destructive action in Phase 4.

**Goal:** land every loose piece of work on `main` or drop it. Never delete without explicit per-item approval.

**The bias is STRONGLY toward landing on `main`.** The target end-state is: everything valuable is on `main`, and the only things not on `main` have a *specific, stated, good reason* (genuinely abandoned, superseded by better work, or a deliberate not-yet-ready effort the user named). "It would take a lot of work to consolidate" is **not** a good reason — it is the expected cost of this skill. **Be happy to spend lots of time refactoring, untangling, resolving conflicts, rewriting tests, and reconciling divergent work to get it onto `main`.** A clean `main` that absorbs the loose work is worth hours of careful consolidation. Parking work on a branch "for later" is the lazy outcome and usually the wrong one — prefer to do the integration now. Reach for subagents (`subagent-launcher`) to parallelize the heavy investigation so the effort is cheap, but do not let the *size* of a consolidation talk you out of it.

**Dirty work is not "preserved" as the outcome — it is merged or dropped.** When this skill says to preserve uncommitted work, that means **make a temporary safety checkpoint before risky integration**, not "park it on a WIP branch and call the cleanup done." The decision you owe the user is: **how will this dirty payload land on `main`, or what exact parts are junk to delete?** For every dirty checkout/worktree, classify paths into mergeable units, identify junk with positive evidence, plan the integration order, and run the needed merge/test/fix loop. A checkpoint branch, patch, or scratch worktree is only a seatbelt while merging; it is not a final recommendation.

**What "loose work" means — read this first.** Loose work is **anything that exists in only one place.** The name says "branches" but branches are the *least* of it. Rank by how easily it is lost, highest first:

1. **Uncommitted changes in the current checkout's working tree** — committed nowhere, pushed nowhere. One `git checkout .` away from gone. THE most exposed work in any repo, and the one a "branch survey" skips by construction. **Always survey this. It is item zero, not out of scope.**
2. **Untracked files** (`git ls-files --others`) — same exposure, plus invisible to `git diff`.
3. **Uncommitted work in other worktrees** — same as #1 but easier to forget because it's not your current directory.
4. **Committed but unpushed** — survives local mistakes, dies with the disk.
5. **Pushed but only on a branch / single clone / single cloud volume** — the actual "loose branch."

A branch named `main` with a dirty tree is **not** outside this skill's scope. Neither is your own current checkout. If you ever find yourself thinking "that's just the main checkout's dirty state, not my problem," stop — that is the exact failure this skill exists to prevent. Account for **every** tier above before you claim the survey is done.

**Done when:** every row in the survey has been acted on or explicitly parked, the "Cleaned up / Kept / Still to decide" report has been printed, AND every tier of loose work above (including the current checkout's own uncommitted/untracked/unpushed work) has an explicit verdict. No silent drops, no items left in `uncertain`, no working-tree work left unaccounted for.

`keep` is only for: open/draft PR, protected branch, or current active work the user has not said is ready. A dirty worktree is **risk**, not a recommendation. If the user says "everything except X is in scope", dirty worktrees outside X still need a landing/deletion recommendation: preserve artifacts, port useful work, then delete after approval. Everything else with unique commits gets a landing rec (`merge-then-delete` / `PR-then-merge` / `cherry-pick-then-delete`) or `delete`. "Recent branch with work on it" is not a reason to `keep` — pick a landing route.

**"Is there other work too?" / "have you been thorough?" / "what about all the other branches?" — these mean you scoped too narrowly.** Don't re-assert the table; re-run the survey on the leftovers and classify them. The two pools most often missed: (a) the **current checkout's own uncommitted/untracked/unpushed work** (item zero), and (b) **non-branch loose state** — `.megaplan/tickets/` (deferred intent), stashes, other on-disk clones, and the megaplan-cloud machine (every per-chain workspace on the Hetzner box, not just the one in `cloud.yaml`). Treat dirty parked worktrees as in-scope unless the user explicitly named them active; name what you missed and *why* ("a branch listing can't show an uncommitted diff"). If you weren't thorough, say so and fix it — don't defend a partial sweep.

**`uncertain` is a last resort, not a default.** The final survey must turn every row into land / cherry-pick / delete / keep — "inspect" and "maybe" are failures, not recs. Reserve `uncertain` for the rare row you genuinely can't classify, and name the blocker plus the exact next investigation that would resolve it.

## Phase 1 — survey (read-only; lean on DeepSeek to read wide)

Fan the sections below across read-only DeepSeek subagents — one agent per area (worktrees, branches, stashes, cloud machine, …) — so the heavy reading happens off the main thread and only the *findings* come back. Resolve main, fetch, and build the worktree map first:

```bash
MAIN=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
MAIN=${MAIN:-main}
git fetch --all --prune --quiet 2>/dev/null
```

### The current checkout's own working tree (ITEM ZERO — most easily missed, highest exposure)

Do this **before** worktrees. The current checkout's uncommitted and untracked work is loose work that lives in exactly one place; a branch listing never shows it.

```bash
git status --short --branch                      # ahead/behind + dirty + untracked at a glance
git diff --stat HEAD                             # tracked uncommitted changes
git ls-files --others --exclude-standard         # untracked files (NOT shown by git diff)
git log --oneline @{u}..HEAD 2>/dev/null         # committed-but-unpushed commits
```

Then **isolate what is genuinely unique to this checkout** — work that exists on no branch, no other worktree, and no remote. The trap: a checkout's dirty diff often overlaps with worktrees forked from it, so most of it may be preserved elsewhere while a few files are unique and at risk:

```bash
# For each modified file, is its content reachable on any branch/worktree, or only here?
git diff HEAD --name-only | while read f; do
  git log --all --oneline -1 -- "$f" >/dev/null 2>&1 || true
done
# Most reliable: compare against any worktree forked from this checkout (see worktree section),
# and against $MAIN's tip: `git diff $MAIN -- <file>`. Files unique here = highest-risk row.
```

Surface this as explicit survey rows, not a footnote: **unique uncommitted work** (rec: merge into `$MAIN` via a consolidation branch/PR, or delete specific junk with evidence), **untracked keepers vs. junk** (logs/caches/`.megaplan-agentic` = junk; new source/tests/briefs = keepers), and **unpushed commits** (rec: push/merge, or note why held). Never recommend deleting or force-checking-out the current tree. If integration is risky, take a safety checkpoint first, then continue to the merge/drop decision.

**FOOTGUN — checkpointing the current checkout's dirty tree without disturbing it.** `git switch -c wip && git add -u && commit && git switch back` does **not** leave the dirty work behind — it *moves* it onto the new branch, and switching back leaves the original checkout **clean** (changes reverted, untracked keepers that got committed are removed). If the user is actively working in this checkout, that silently wipes their working state. Two safe patterns: (a) **record a fingerprint first** (`git diff HEAD | git hash-object --stdin` + the untracked list), do the snapshot-branch + push, then **restore**: `git checkout <wip-branch> -- . && git reset -q HEAD`, and verify the fingerprint matches; or (b) snapshot via a **scratch worktree** (`git worktree add /tmp/wip -b checkpoint/wip $MAIN`) and copy the dirty files in there, never touching the live checkout. Always verify the original tree is byte-identical afterward. Then use that checkpoint as an integration source; do not treat it as the cleanup result.

### Worktrees (FIRST among other worktrees — pinned branches can't be `-d`'d)

```bash
git worktree list --porcelain
ls -d "$PWD/.megaplan-worktrees"/* "$PWD/../"*"/.megaplan-worktrees"/* 2>/dev/null
find "$HOME/Documents/.megaplan-worktrees" "$HOME/.megaplan-worktrees" \
  -maxdepth 1 -mindepth 1 -type d 2>/dev/null
find "$PWD" -maxdepth 3 -type d \( -name '.worktrees' -o -name 'worktrees' \) 2>/dev/null
find "$PWD/.megaplan/bakeoffs" -maxdepth 3 -type d -name 'worktrees' 2>/dev/null
ls -d ~/.claude/projects/*/worktrees/* 2>/dev/null
```

**Do not trust `git worktree list` as complete.** It only shows worktrees registered
to the current repo's `.git/worktrees`. Megaplan and agent runs can leave standalone
or chained checkouts under a shared directory such as
`~/Documents/.megaplan-worktrees/<topic>` whose `.git` belongs to a different clone
or whose `origin` points to another local checkout. These are still loose work and
must be mini-surveyed. For every candidate directory above, accept both `.git`
directories and `.git` files:

```bash
for wt in "$HOME/Documents/.megaplan-worktrees"/* "$HOME/.megaplan-worktrees"/*; do
  git -C "$wt" rev-parse --git-dir >/dev/null 2>&1 || continue
  echo "== $wt =="
  git -C "$wt" remote -v
  git -C "$wt" rev-parse --show-toplevel
  git -C "$wt" branch --show-current
  git -C "$wt" log -1 --oneline
  git -C "$wt" status --porcelain
  git -C "$wt" ls-files --others --exclude-standard | head -80
done
```

If `remote get-url origin` is this repo, a local path to this repo, or a local path
to another checkout that ultimately points at this repo, classify it in this cleanup.
If it is a different repo, list it separately as "other repo loose work" and do not
merge it into the current repo. A directory can contain source/tests entirely as
untracked files; that is highest-risk loose work even when branch tables are clean.

Per registered or unregistered worktree: branch, origin chain, ahead/behind vs `$MAIN`
when it belongs to this repo, `git -C <path> status --porcelain`, and untracked file
summary. Dirty/untracked source = highest risk, flag red. Also note `prunable` entries
(`git worktree prune` fixes them).

**Build a `branch → worktree path` map now** — later sections check it to flag pinned branches (which refuse `git branch -d`).

### Local branches

```bash
git for-each-ref \
  --format='%(refname:short)|%(committerdate:iso8601)|%(committerdate:relative)|%(upstream:short)|%(upstream:track)|%(objectname:short)|%(contents:subject)' \
  refs/heads/
```

Per branch (skip `$MAIN`):
- ahead/behind: `git rev-list --left-right --count $MAIN...<br>`
- merged ancestor: `git merge-base --is-ancestor <br> $MAIN`
- **`cherry +N` (load-bearing — catches squash-merges and post-merge fixups):** `git cherry $MAIN <br> | grep -c '^+'`. Zero `+` = every patch already on main. Always compute before applying any merged-PR rule.
- conflicts: `git merge-tree $(git merge-base $MAIN <br>) $MAIN <br> | grep -c '<<<<<<<'`
- diff shape: `git diff --stat $MAIN...<br>`
- pinned: from the worktree map
- upstream `[gone]`: remote was deleted (PR auto-delete-on-merge)

### Stashes

```bash
git stash list --format='%gd|%cr|%s'
for s in $(git stash list --format='%gd'); do git stash show --stat "$s"; done
```

Cross-reference each stash's base branch against the branch table. A stash on a flagged-for-delete branch is the highest-risk row in the survey — surface the linkage; stash approval is always separate from branch approval.

### Remote branches + PR state

```bash
git branch -r --format='%(refname:short)|%(committerdate:iso8601)|%(committerdate:relative)'
gh pr list --state all --limit 200 \
  --json number,state,headRefName,baseRefName,title,updatedAt,isDraft,mergedAt,author > /tmp/prs.json
```

Join PRs by `headRefName`; most recent wins. If many `[gone]` upstreams, mention GitHub's auto-delete-head-branches setting.

### Interrupted operations (carry real work, not visible elsewhere)

```bash
ls .git/MERGE_HEAD .git/CHERRY_PICK_HEAD .git/REVERT_HEAD .git/REBASE_HEAD 2>/dev/null
ls -d .git/rebase-apply .git/rebase-merge .git/sequencer 2>/dev/null
```

Any hit → flag `keep` until user resolves the in-progress op. Show `git status` so the user can see what's mid-flight.

### Submodules

```bash
git submodule foreach --recursive \
  'echo "== $name =="; git status --porcelain; git stash list; git log --oneline @{u}.. 2>/dev/null'
```

Each submodule with dirty state, stashes, or unpushed commits gets its own row in the survey.

### Detached HEAD orphans

```bash
git fsck --unreachable --no-reflogs 2>/dev/null | grep -c '^unreachable commit'
```

Surface the count only; offer to dig in if the user's lost work.

### Untracked / patch / merge-tool leftovers

```bash
git ls-files --others --exclude-standard
find "$PWD" -maxdepth 3 -type f \
  \( -name '*.patch' -o -name '*.diff' \
     -o -name '*.orig' -o -name '*.BACKUP.*' -o -name '*.LOCAL.*' -o -name '*.REMOTE.*' -o -name '*.BASE.*' \) 2>/dev/null
```

`*.orig` / `*.BACKUP.*` / `*.LOCAL.*` / `*.REMOTE.*` / `*.BASE.*` are merge-tool leftovers — often partial work the user never finished resolving.

### Agent-history storage side effect

Loose-branch and worktree cleanup often involves many Hermes/Codex sessions and
wide tool output. If the machine is under disk pressure, check Hermes session
state before starting a long cleanup:

```bash
du -sh "$HOME/.hermes/state.db" "$HOME/.hermes/state.db-shm" "$HOME/.hermes/state.db-wal" 2>/dev/null
sqlite3 -readonly "$HOME/.hermes/state.db" \
  "SELECT name, ROUND(SUM(pgsize)/1024.0/1024.0,1) AS mib FROM dbstat GROUP BY name ORDER BY SUM(pgsize) DESC LIMIT 20;" 2>/dev/null
```

On this machine, `~/.hermes/state.db` grew to **7.9G** from CLI/tool history plus
FTS5 indexes (`messages_fts` and especially `messages_fts_trigram`). If the user
does not care about Hermes resume/search/insights history, the clean purge is to
stop Hermes, then remove the SQLite trio:

```bash
lsof +D "$HOME/.hermes" 2>/dev/null
rm -f "$HOME/.hermes/state.db" "$HOME/.hermes/state.db-shm" "$HOME/.hermes/state.db-wal"
```

To prevent it from coming back after the local Hermes patch that supports it, set:

```yaml
sessions:
  enabled: false
```

This is not branch cleanup and should not be mixed into destructive branch actions;
it is a disk-pressure guardrail to run only with explicit user approval.

### Tags, odd refs, fork PR refs

```bash
git for-each-ref \
  --format='%(refname:short)|%(objectname:short)|%(committerdate:relative)|%(contents:subject)' \
  refs/notes refs/replace refs/original 2>/dev/null
git ls-remote origin 'refs/pull/*/head' | head -20
gh pr list --state open --limit 100 \
  --json number,headRepositoryOwner,headRefName,baseRefName,title,isDraft,url
```

Tags, `refs/notes`, `refs/replace`, `refs/original`: surface as **context only — never delete candidates**. External-head PRs (forks): PR work to keep/review, not branch cleanup.

### Non-origin remotes

```bash
git remote -v
for r in $(git remote); do [ "$r" = origin ] || git branch -r --list "$r/*"; done
```

Treat `upstream`, personal forks, and leftover `_variant` remotes the same as origin: join PR state where applicable, classify per the same rules.

### Sibling Repo variants (`megaplan-2`, `repo.bak`, etc.)

```bash
REPO=$(basename "$PWD"); PARENT=$(dirname "$PWD")
find "$PARENT" -maxdepth 1 -mindepth 1 -type d \
  \( -iname "${REPO}-*" -o -iname "${REPO}_*" -o -iname "${REPO}.*" \
     -o -iname "${REPO} *" -o -iname "old-${REPO}" -o -iname "old_${REPO}" \
     -o -iname "*-${REPO}" -o -iname "*_${REPO}" \) \
  -not -path "$PWD" 2>/dev/null
```

For each candidate that's a git repo (`git -C <path> rev-parse --git-dir`) and shares this repo's origin, run this **mini-survey** (read-only, no `cd`):

```bash
git -C <path> remote get-url origin
git -C <path> rev-parse --abbrev-ref HEAD
git -C <path> log -1 --format='%cr %h %s'
git -C <path> status --porcelain
git -C <path> stash list
git -C <path> for-each-ref --format='%(refname:short)|%(upstream:track)|%(contents:subject)' refs/heads/
git -C <path> ls-files --others --exclude-standard | head -30
```

Each variant is its own section, not a row in the branch table.

### Other clones of this repo elsewhere on disk

```bash
ORIGIN=$(git remote get-url origin 2>/dev/null)
[ -n "$ORIGIN" ] && find ~/dev ~/Documents ~/src ~/code /tmp /Volumes 2>/dev/null \
  -maxdepth 6 -name config -path '*/.git/config' \
  | xargs grep -l "$ORIGIN" 2>/dev/null \
  | grep -v "^$PWD/"
```

For each `.git/config` hit, the clone is `dirname dirname <path>`. Run the same mini-survey as sibling variants.

### Megaplan cloud machine (Hetzner agentbox) + cloud workspaces

The cloud "machine" is a long-lived box (in this environment, a Hetzner VM via
`provider: ssh`) running the `megaplan-cloud-agent` container over a persistent
`/workspace` volume. **That volume holds many per-chain workspaces**
(`/workspace/<unique-per-chain>`), one per concurrent chain — each its own git
clone that can carry uncommitted work, untracked files, unpushed commits, and
cloud-only branches. Surveying only the single `repo.workspace` named in the
local `cloud.yaml` misses everything else on the box, so survey the **whole
machine**, not one workspace. The box outlasts any one `cloud.yaml` and may hold
loose work even when the current repo has none — so detect the **box directly**,
not just the config file.

Detect the config **and** the box (either can exist without the other):

```bash
ls "$PWD/cloud.yaml" "$PWD/.megaplan/cloud.yaml" "$PWD/.megaplan/cloud-"*.log 2>/dev/null
```

Resolve the ssh target from `cloud.yaml` (defaults match the working setup):

```bash
HOST=$(yq '.ssh.host' cloud.yaml 2>/dev/null)
SSH_USER=$(yq '.ssh.user // "root"' cloud.yaml 2>/dev/null)
PORT=$(yq '.ssh.port // 22' cloud.yaml 2>/dev/null)
IDENT=$(yq '.ssh.identity_file // ""' cloud.yaml 2>/dev/null)
CONTAINER=$(yq '.ssh.container // "megaplan-cloud-agent"' cloud.yaml 2>/dev/null)
# /workspace inside the container == ssh.workspace_dir on the host (default /opt/megaplan-cloud/workspace)
BOX="ssh -p ${PORT} ${IDENT:+-i $IDENT} ${SSH_USER}@${HOST} docker exec ${CONTAINER} bash -lc"
```

Reachability — try the orchestrator, then a direct ssh ping (the box can be up
even when the local `megaplan cloud` wiring isn't):

```bash
megaplan cloud status 2>&1 | head -40
$BOX 'echo ok' 2>&1 | head -5
```

- **Box reachable + container up** → survey the **entire machine** read-only.
  Enumerate every workspace (every dir under `/workspace`, not just the one in
  cloud.yaml), then mini-survey each git repo there exactly like a sibling
  variant, plus list the tmux sessions (each chain is its own loose-work
  candidate and may be mid-run):

  ```bash
  $BOX 'ls -1 /workspace 2>/dev/null'                       # every per-chain workspace on the box
  $BOX 'for ws in /workspace/*/; do
    git -C "$ws" rev-parse --git-dir >/dev/null 2>&1 || continue
    echo "== $ws =="
    git -C "$ws" remote -v
    git -C "$ws" rev-parse --abbrev-ref HEAD
    git -C "$ws" status --porcelain
    git -C "$ws" ls-files --others --exclude-standard | head -40
    git -C "$ws" stash list
    git -C "$ws" for-each-ref --format="%(refname:short)|%(upstream:track)|%(contents:subject)" refs/heads/
    git -C "$ws" log --oneline "@{u}.." 2>/dev/null | head -20   # committed-but-unpushed
  done'
  $BOX 'tmux ls 2>/dev/null'                                # live chain sessions (each may be mid-run)
  $BOX 'tail -40 /workspace/*/.megaplan/cloud-chain*.log 2>/dev/null'  # what is churning / interrupted
  ```
  (`megaplan cloud exec "<cmd>"` runs the same command through the orchestrator
  if it is wired; direct ssh is more reliable — see the `megaplan-cloud` skill.)

  Five risk buckets, one per workspace / chain: **dirty volume** (uncommitted or
  untracked source — highest risk), **committed-but-unpushed** (push never
  landed), **branch ahead of origin** (chain interrupted mid-push),
  **cloud-only branches** (never pushed at all), and **dormant chain workspaces**
  (no live tmux session, nothing pushed — pure loose volume). A workspace with a
  live tmux session and recent log lines is active work → `keep`; flag it, do not
  touch it.
- **Box up, container down** → the volume still holds work; start the container
  (`docker start "$CONTAINER"`) to inspect, or snapshot the volume — but **do not
  destroy** until every workspace is ported or declared junk.
- **Box not deployed / unreachable** → surface "dormant cloud — boot/deploy to
  inspect, or destroy if you're sure it's done." Do **not** boot just to survey
  without asking; booting is reversible, `destroy` is not.

Each cloud workspace is its own section. Recs: `port-and-down` /
`port-and-destroy` / `down` / `destroy` / `keep`. Port by pushing from inside the
container (`$BOX 'git -C /workspace/<ws> push origin <branch>'`) before any
`down`/`destroy`. `destroy` drops the provider volume — non-recoverable, same
blast radius as `rm -rf` on a sibling variant.

Also reconcile the **other direction** when a cloud workspace is done: if the
latest intended code now lives locally or on GitHub, make sure the Hetzner box is
not left running a stale checkout. First push the finished branch from the source
of truth, then update each inactive cloud workspace that should keep existing by
fetching and checking out that pushed tip inside the container. Do this only for
dormant/finished workspaces; active tmux sessions stay `keep` until they finish.

```bash
git push origin <finished-branch>
$BOX 'git -C /workspace/<ws> fetch origin --prune &&
      git -C /workspace/<ws> checkout <finished-branch> &&
      git -C /workspace/<ws> pull --ff-only origin <finished-branch>'
```

**Arnold-specific branch replacement check.** If the repo is Arnold, verify that
cloud workspaces no longer depend on the old `editable-install` branch once that
work has landed or been superseded. Treat any `/workspace/*` Arnold checkout still
on `editable-install`, or with `editable-install` as its configured branch, as a
cloud cleanup row: replace it with the intended branch (`main` or the new
consolidation branch), push/fetch the replacement tip, and only then mark the old
branch ready to delete. In the survey output, state explicitly: "`editable-install`
replaced on Hetzner: yes/no; remaining workspaces: <paths>."

### GitHub Codespaces

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
gh codespace list --json name,repository,gitStatus,lastUsedAt 2>/dev/null \
  | jq --arg r "$REPO" 'map(select(.repository == $r))'
```

Each Codespace's `gitStatus` shows unpushed commits / dirty state — same shape as cloud workspaces. Recs: `port-then-delete-codespace` / `delete-codespace` / `keep`.

## Phase 2 — investigate & classify (DeepSeek fan-out → go/no-go)

The survey gives you raw facts; this phase turns them into **decisions**. For any row where the first-pass call is "inspect" / "maybe" / "probably", fan the question out to read-only DeepSeek subagents and collapse the uncertainty into a go/no-go verdict. The goal is a decisive table — land / cherry-pick / delete / keep — not more notes.

**Deploy a subagent (`subagent-launcher` or Agent tool) for any medium-or-higher ambiguity.** Concrete triggers include: 5+ unique commits, conflicts, no PR but load-bearing-looking commits, stale-but-possibly-valuable work, dirty worktrees whose payload might overlap, branch name diverging from PR `headRefName`, unclear base branch, uncertain supersession, or any row where your first-pass recommendation would be "inspect" / "maybe" / "probably." Brief: branch/item, unique commits, key files, known facts, "is each commit already on main or the true base as a different SHA?", "what would be lost if dropped?", and "give a go/no-go recommendation." Surface its per-commit or per-payload verdict in the walk-through. If there is no meaningful ambiguity because direct evidence already proves `delete`, `merge`, `PR`, or `keep`, do not spawn an agent just to rubber-stamp it.

### Deep-investigation upgrades (multi-epic repos, heavy ambiguity)

The base survey assumes loose refs are mostly residue. In a repo mid-flight on one or more **megaplan
epics**, that assumption inverts: the branch list is largely *residual refs from completed/squash-merged
epics*, while the **real risk is unprotected uncommitted work sitting in worktrees** — sometimes the most
advanced work in the repo, on no branch and no remote. A single survey pass will misread this. The
discipline below was distilled from a real cleanup where the headline finding wasn't "stale branches" but
"an entire epic (M0–M5) existed only as a dirty worktree, triplicated across three checkouts." Use it
whenever the basic survey leaves you hedging.

1. **Epic awareness.** Before classifying, read the intent record: `docs/megaplan/epics/*/chain.yaml`,
   `EPIC.md`, milestone `*.md`, `briefs/`, `wakeup-note.md`, `how-to-follow-along.md`, and **`.megaplan/tickets/`**
   (open tickets often *are* the list of deferred work). Note that executed plans often ran on a cloud box,
   so `.megaplan/plans/` may be empty locally — say so rather than assuming no plan existed. For each epic,
   build an **intended-scope-vs-done** map (which milestones merged, which are incomplete, which were
   explicitly deferred). A "loose branch" whose epic is done is residue; a clean-looking epic may still
   *owe* unshipped milestones.

2. **Base-branch ≠ main.** Epics frequently use a long-lived integration branch as the PR base, not `main`.
   Compute `cherry`/ahead-behind/merged against each branch's **true PR base** (`gh pr ... --json baseRefName`),
   not just `$MAIN`. A milestone squash-merged into the integration branch shows `cherry +N` vs `main` yet is
   fully landed — deleting it is safe *only if the integration branch is preserved*. Always state that dependency.

3. **Worktree payload fingerprinting (duplicate/subset detection).** Don't stop at a dirty-file count.
   Fingerprint each worktree's uncommitted diff and compare across worktrees that share a tip or epic:
   ```bash
   git -C <wt> diff HEAD | git hash-object --stdin        # identical hash ⇒ byte-identical payload
   git -C <wt> ls-files --others --exclude-standard | sort # compare untracked sets too
   comm -23 <(sort A_untracked) <(sort B_untracked)        # empty ⇒ A ⊆ B (subset, not unique)
   ```
   This catches the trap where three worktrees look like "parallel epic work" but two are exact duplicates /
   subsets of a third. Classify each worktree's payload as **keeper / duplicate / subset / unrelated-churn**.

4. **Phase-1 completion gate.** Run *every* survey section before emitting the table — including the ones
   that come back empty (codespaces, other clones, tags, cloud). Presenting a table off a partial sweep is a
   failure mode; you don't know what you missed until each check has actually returned.

5. **Preserve-before-delete, no middle ground.** The goal is: *land everything valuable, then delete the
   rest with positive evidence.* Uncommitted worktree work is the highest-risk item and must be committed or
   ported **before** any deletion touches it. Never leave the repo in a half-cleaned state.

### Resolving ambiguity with a read-only DeepSeek fan-out (`subagent-launcher`)

When classification has medium-or-higher ambiguity — *is effort A superseded by effort B?*,
*is this epic actually complete?*, *what's the merge conflict surface?*, *do these tests pass?*,
*is this dirty worktree payload unique or duplicated elsewhere?* — fan the questions out to parallel
**DeepSeek V4 Pro** agents (the `subagent-launcher` skill: `fan.py` for ≥5 agents,
`launch_hermes_agent.py` for 1–4). One independent decision area per agent, run in parallel, no cross-talk.
The point is to cheaply convert uncertainty into a go/no-go cleanup recommendation; do not feel bad about
using agents when a direct survey leaves anything important unclear.
Best practices that earned their place:

- **Split by cleanup decision, not by command family.** Good briefs are scoped to one judgement area:
  an integration branch vs `main`, a large port branch, a stale docs-only branch, an open PR with a pinned
  worktree, or non-branch loose state. The goal is a verdict (`PR-then-merge`, `delete`, `keep until X lands`,
  `do not cherry-pick as-is`), not a transcript of every git command. A five-way fan-out that worked well:
  `01-integration-to-main`, `02-large-port-branch`, `03-stale-branch-family`, `04-open-pr-pinned-worktree`,
  `05-nonbranch-loose-state`.
- **Bake a hard read-only guardrail into *every* brief.** Spell out the allowed commands
  (`git status/diff/log/show/cherry/merge-base/merge-tree/ls-tree`, `cat/ls/grep/find`, and `git stash show -p`
  which is read-only) and the forbidden ones (any `commit/checkout/switch/merge/rebase/reset/stash apply-pop-drop/
  cherry-pick/branch -d/push/rm/mv/clean`, `write_file/patch`). These agents get `terminal` access with **no
  sandbox** — the guardrail is your only seatbelt. "Describe the mutation in your report instead of doing it."
- **Preload known facts and ask them to verify.** Include the first survey's branch/worktree facts, PR numbers,
  ahead/behind counts, commit subjects, and the specific uncertainty. This avoids wasting agent time on broad
  rediscovery and makes corrections more meaningful. Example question shapes:
  - "Is `<branch>` fully consumed by its true base branch, not just by `main`?"
  - "Is this docs-only residue safe to delete, or should any commit be rewritten as a fresh archival addendum?"
  - "Does the detached worktree preserve local-only work, or is it redundant with a remote ref?"
- **Use `--toolsets="terminal,file"`** so they can actually run git across worktrees (the `file` toolset alone
  can't run `git diff`). For test-running briefs, scope tightly: name the exact test files, exclude GPU/network/
  agentic suites, and tell them to skip anything that hangs.
- **Hand them the facts you already established** so they *verify* rather than re-derive — and still
  **cross-check their claims with a quick direct command.** Agents are occasionally wrong in load-bearing ways
  (in the reference run, one called untracked files "unique" when a 30-second `comm` proved they were a subset).
- **Demand decisiveness:** "ground every claim in command output; take a position; do not hedge; cap at N words."
- **Liveness-check 30–60s after launch** (`tail` the fan stderr for `[tool]`/`[done]` heartbeats); set
  `--task-timeout`. See the `subagent-launcher` skill's "Detecting hangs" section.
- **Iterate.** A first fan-out (e.g. lineage / integration / stashes / branch-ledger) usually leaves one hard
  unknown — dispatch a focused follow-up agent for it (e.g. a supersession verdict) rather than guessing.
- **Know the ceiling.** Read-only agents produce a high-confidence **risk map and task list**; they *cannot
  prove* an integration compiles or merges. That requires actually doing it in a throwaway worktree
  (Codex or a Claude `Agent` with write access), which is implementation, not survey. State this limit plainly.

Concrete fan-out skeleton:

```bash
RUN_DIR=/tmp/loose-branches-deepseek-$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN_DIR/briefs" "$RUN_DIR/results"
# Write one self-contained markdown brief per judgement area under "$RUN_DIR/briefs".
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir="$RUN_DIR/briefs" \
  --output-dir="$RUN_DIR/results" \
  --max-workers=5 \
  --model="deepseek:deepseek-v4-pro" \
  --toolsets="terminal,file" \
  --max-tokens=32768 \
  --task-timeout=900 \
  --project-dir="$PWD"
```

Minimal brief template:

```markdown
You are a read-only DeepSeek investigation agent for branch cleanup in <repo>.

Goal: decide <one cleanup decision>. Return a go/no-go recommendation: land, delete, cherry-pick,
keep-until-X, or explicitly park. Do not end at "needs inspection."

Known facts from the first survey:
- <branch/worktree/PR facts>
- <ahead/behind, cherry +N, conflict count, commit subjects>

READ-ONLY GUARDRAIL:
Allowed commands only: git status, diff, log, show, cherry, merge-base, merge-tree, rev-list,
branch/list, worktree list/prune --dry-run, stash list/show, ls-tree, cat/sed/grep/rg/find,
gh pr/codespace list/view, python one-liners that only read files.
Forbidden: commit, checkout/switch, merge, rebase, reset, stash apply/pop/drop, cherry-pick,
branch -d/-D, push, git worktree prune without --dry-run, rm/mv/write_file/patch, editing files.
If a mutation would be useful, describe it instead.

Questions to answer:
1. <the load-bearing decision>
2. <what would be lost if dropped>
3. <what positive evidence makes delete/keep/merge safe>

Output: <=800 words. Lead with verdict. Ground every claim in command output. Take a position.
```

After the fan-out finishes, **do not paste the raw reports as the answer.** Read them, then cross-check the
claims that would change a recommendation:

```bash
while read -r base br; do
  mb=$(git merge-base "$base" "$br")
  echo "## $base <- $br"
  git rev-list --left-right --count "$base...$br"
  git cherry "$base" "$br" | grep -c '^+' || true
  git merge-tree "$mb" "$base" "$br" | grep -c '<<<<<<<' || true
done <<'EOF'
main feature/foo
integration spent-child
EOF
```

Then synthesize a short updated verdict table. Name any recommendation that changed because of the fan-out
and why. If the fan-out finds a correction to the first survey (for example a missed third-party submodule,
a detached worktree that is redundant with a remote ref, or a docs-only branch that is stale enough not to
cherry-pick), update the durable plan doc (Phase 3) before asking for destructive approval.

### Classification rules

First match wins. Use the reason template verbatim, filling `<...>`:

| Signal | Rec | Reason template |
|---|---|---|
| Worktree has uncommitted changes | **keep** | "uncommitted work in worktree at `<path>`" |
| Open PR (not draft) | **keep** | "open PR #N: `<title>`" |
| Draft PR | **keep** | "draft PR #N — still in progress" |
| Interrupted rebase/merge/cherry-pick | **keep** | "in-progress `<op>`; resolve before cleanup" |
| Merged PR + `cherry +0` | **delete** | "PR #N merged `<date>`, no unique commits" |
| Merged PR + `cherry +N`, some commits valuable | **cherry-pick-then-delete** | "PR #N merged, `<M>`/`<N>` commits still matter — cherry-pick those" |
| Merged PR + `cherry +N`, all superseded | **delete** | "PR #N merged; remaining `<N>` commits superseded by main" |
| Merged PR + `cherry +N`, coherent new work | **PR-then-merge** | "PR #N merged, `<N>` coherent commits remain post-merge" |
| Closed PR + `cherry +0`, >30d | **delete** | "PR #N closed unmerged, no unique commits" |
| Closed PR + `cherry +N`, valuable | **PR-then-merge** | "PR #N closed unmerged; `<N>` unique commits still should land" |
| Closed PR + `cherry +N`, superseded | **delete** | "PR #N closed unmerged; unique commits superseded" |
| `cherry +0` (no PR) | **delete** | "squash-merged into `$MAIN`, no unique commits" |
| `--merged` ancestor of `$MAIN` | **delete** | "fully merged into `$MAIN`" |
| `[gone]` upstream + 0 ahead local | **delete** | "remote deleted, nothing local to lose" |
| Protected/release-like name | **keep** | "looks like a protected/release branch" |
| Pinned by clean worktree, valuable | **PR-then-merge** | "checked out at `<path>`; clean, land via PR" |
| <14d, ahead, small/clean diff | **merge-then-delete** | "recent valuable work, `<X>` ahead, merge-tree clean" |
| <14d, ahead, larger/riskier diff | **PR-then-merge** | "recent valuable work, `<X>` ahead; needs CI/review" |
| >90d, ahead, no PR, superseded | **delete** | "stale (`<N>`d), `<X>` ahead, no PR, superseded by main" |
| >90d, ahead, no PR, valuable | **PR-then-merge** | "stale (`<N>`d), but `<X>` unique commits still should land" |
| Anything else valuable | **PR-then-merge** | "`<X>` ahead / `<Y>` behind, last commit `<N>`d ago; land via PR" |
| Anything else superseded | **delete** | "`<X>` ahead / `<Y>` behind; superseded by main" |

When two rules could apply, prefer the more cautious landing route (`PR-then-merge` over direct merge, `cherry-pick-then-delete` over whole-branch merge). `delete` requires positive evidence.

**Local-vs-own-remote skew:** `--merged` ancestor + `[ahead N]` upstream usually means N commits were squash-merged and the remote branch is residual. `cherry +0` confirms. Reason: "ancestor of $MAIN; also N ahead of own remote (squash-merged), remote is residual."

### Survey + classification output

One table, sorted: `delete` → `cherry-pick-then-delete` → `merge-then-delete` → `PR-then-merge` → `keep` → `uncertain`, then age desc.

```
REC                       WHERE         BRANCH               AHEAD/BEHIND  AGE     PR
delete                    local+remote  fix/typo             0/0           merged  #412 ✓
  Change: README typo.
  Why: PR merged, no unique commits.

merge-then-delete         local+remote  fix/cli-null         1/0           2d      none
  Change: small CLI null guard.
  Why: low-risk, merge-tree clean.

PR-then-merge             local         feat/payments        23/4          3d      none
  Change: payment workflow + persistence.
  Why: larger work, needs CI/review before landing.
```

Symbols: `✓` merged, `✗` closed, `◐` open, `◌` draft.

Below the table:
- **Current checkout's working tree** (LIST FIRST — uncommitted unique work, untracked keepers vs. junk, unpushed commits; each with a merge/drop rec, plus any safety-checkpoint step needed before merging). If clean, say "working tree clean" explicitly — don't omit it.
- **Stashes** (numbered: age, base branch, files, line delta; flag linkage to flagged branches)
- **Prunable worktrees** (one-line `git worktree prune` fix)
- **Interrupted operations** (rebase/merge/cherry-pick state present)
- **Submodules** (per submodule with dirty/unpushed/stashes)
- **Untracked / patch / merge-tool leftover files**
- **Detached HEAD orphan count**
- **Sibling variants + other clones** (per-directory section)
- **Cloud machine + workspaces + Codespaces** (per-workspace section)
- **Counts:** "working tree: N unique-uncommitted / N untracked-keepers / N unpushed-commits — then N delete / N merge / N PR / N cherry-pick / N keep / N uncertain / N stashes / N variants / N cloud / N codespaces"

**Before you present:** confirm you ran item zero (current working tree) and can state its verdict. A survey table that omits the working tree is incomplete — that omission is the #1 way this skill fails the user.

End: hand off to **Phase 3** — write the consolidation plan for these verdicts, then **Phase 4** executes it. Wait for explicit go-ahead before acting.

## Phase 3 — strategy (write the merge plan)

For any non-trivial cleanup (multiple epics, uncommitted keepers, supersession decisions), **write a durable plan doc** (e.g. `docs/megaplan/loose-work-consolidation-plan.md`) — the artifact outlives the chat and makes the reasoning auditable. This is where you decide *how everything merges together* before you touch a branch. Use DeepSeek subagents to map supersession and the conflict surfaces you will hit, and to draft sections you're unsure about. Recommended sections:

1. **Rationale** — why this exists; the inverted-risk insight if it applies.
2. **The landscape** — the epics/efforts in play and how branches diverge.
3. **Everything valuable → where it lands** — a table: work | current state | lands as.
4. **Everything else → delete** — each with the positive evidence that makes it safe.
5. **Per-decision verdicts** — supersession / port-then-close / etc., with the agent evidence.
6. **Corrections forced by investigation** — record where deeper digging overturned a surface read
   (intellectual honesty; it shows the conclusions are earned, and stops the next reader re-making the error).
7. **Execution order** — safety checkpoint if needed → integrate valuable work → delete proven junk/residual refs, lowest blast radius first.
8. **Confidence & open questions** — split confident-conclusions from un-derisked ones; name the remaining
   unknowns and the next step that would close each.
9. **Provenance** — which agents ran, with paths to their raw outputs.

Leave explicit **placeholders** (`<!-- VERDICT PENDING -->`) for in-flight agent verdicts and fill them in as results land, fixing any downstream rows the verdict changes. The doc, not the chat, is the source of truth for what gets preserved and deleted.

### Complex merges — anticipate them in the plan

The plan is where you size up the hard integrations and choose the order, not where you discover them mid-merge. Patterns to resolve up front (the live playbook for each is the friction-guards list in Phase 4):

- **Overlapping branches that share a base** (e.g. several worktrees forked from the same dirty tree) cannot be blind-merged — plan to land the shared base first, then layer each branch's *unique* delta on top, testing between each.
- **Divergent test contracts** — when old tests and new code encode different intended behavior, decide in the plan which contract is current and note that tests get updated as part of that merge.
- **Stacked branches** — if a branch stacks on an explicitly active branch, plan to cherry-pick only the top useful commit(s) rather than merge the whole stack.
- **Generated files / artifacts** — flag anything that churns under hooks or tests so it gets included (or excluded) intentionally at execution time, not accidentally.
- **Supersession** — for each "is A superseded by B?" question the fan-out left open, write the verdict and the evidence into the plan before Phase 4 acts on it.

## Phase 4 — execute (run the merges; useful → on a branch, rest → ready-to-delete, NOT deleted)

Work the Phase 3 plan, lowest blast-radius first. **The end-state:** every useful piece of work is merged onto the consolidation branch (merge / cherry-pick / PR until the test suite passes), and everything else is **staged ready-to-delete — not deleted**. Deletion of branches, worktrees, sibling dirs, cloud volumes, and codespaces waits for explicit per-item approval with a unique-work summary. Nothing gets deleted silently or on a default. Hand the heavy merge / conflict / test loops to subagents in parallel where the work is independent.

For each item, present: **what it is**, **user-facing description**, **signals** (ahead/behind, PR, `cherry +N`, linked stash/worktree, would-merge-cleanly), **rec + why**, and **what's lost if dropped** (list commit subjects). Keep the description in product/user terms, not just file names: "adds retrospective audit reporting" is better than "touches `receipts/report.py`." Wait for that item's OK. Only "go through the rest with your recs as defaults" authorizes batch action, and stop on the first conflicting signal.

Use this compact walk-through shape when the user wants to review the list:

```text
branch-name
Change: one sentence in user-facing language.
Signals: 3 ahead / 0 behind, cherry +3, clean worktree, merge-tree clean.
Rec: merge into the consolidation branch, then delete branch.
Why: useful coherent work and lower risk than cherry-picking individual commits.
If dropped: <commit subject>; <commit subject>.
```

**Process items in this order — lowest blast radius first. Do not skip ahead.** Each block is a *menu*; apply only to items the user approved.

**1. Prunable worktree metadata (always safe)**
```bash
git worktree prune --verbose
```

**2. Delete local branches (already merged)** — `-d` not `-D`; surface refusals, ask before `-D`
```bash
git branch -d <branch>
```

**3. Delete remote branches** (batched)
```bash
git push origin --delete <br1> <br2> <br3>
```

**4. Worktrees with no uncommitted changes**
```bash
git worktree remove <path>                  # --force only with explicit "yes, lose changes"
git branch -d <branch>                      # if branch was pinned to that worktree
```

**5. Merge-then-delete approved branches**
```bash
git switch $MAIN && git pull --ff-only origin $MAIN
git merge --ff-only <branch>                # or repo's normal merge style
git push origin $MAIN
git branch -d <branch> && git push origin --delete <branch>
```

**5a. Consolidate multiple useful branches into one branch** — use this when the user wants a single new branch that gathers useful loose work before PR/merge. Land one branch at a time and verify after each merge before touching the next branch.

**Consolidation is real engineering work, and that is fine — budget for it.** Expect to spend significant time here: resolving non-trivial merge conflicts, reconciling two branches that edited the same files differently, picking the *intended* contract when old and new tests disagree, rewriting or updating tests, and re-running suites after each step. This is the point of the skill, not a detour from it. Overlapping branches that share a base (e.g. several worktrees forked from the same dirty tree) cannot be blind-merged — land the shared base first, then layer each branch's *unique* delta on top, testing between each. Do not shrink scope or park work to avoid the effort; the willingness to do hours of careful integration is exactly what gets everything onto `main`.

Recommended order:
1. Create a fresh consolidation branch from `$MAIN` once the user approves consolidation. If the current dirty checkout contains valuable work, first make a non-destructive safety checkpoint or scratch-worktree copy, then use that checkpoint as a source to merge selected units into the consolidation branch. The goal remains landing valuable work on `$MAIN`, not keeping the checkpoint.
2. Merge prerequisites and small shared fixes first.
3. Merge superseding branches instead of their obsolete ancestors.
4. Leave explicitly active worktrees alone; cherry-pick only their useful top-layer commits later.
5. For every dirty worktree in scope, decide whether the uncommitted payload is useful source, generated artifact, or junk. Useful source gets committed/cherry-picked/ported; generated artifacts are copied to a named artifact directory or intentionally committed if they are repo assets; junk is deleted only after approval.
6. Land useful artifacts (`.megaplan/tickets`, briefs, generated plans, skill files, test fixtures, evidence packs) by committing them into the consolidation branch or intentionally deleting them as junk with evidence. Temporary checkpoint copies are allowed before deletion, but the final state must say where each useful artifact landed.
7. After each merge, run the repo's focused tests first, then the broader suite that is practical for the repo. If tests fail, fix either the code or the test expectations before merging the next branch.
8. Commit each successful merge/checkpoint before starting the next branch. This makes failures attributable and avoids losing conflict-resolution work.
9. When all approved useful work is consolidated, run the full practical test suite one final time.
10. Push the consolidation branch to the remote, and preferably open a draft PR or record the pushed branch URL in the report. The consolidation branch is now the recoverable source of truth.
11. Only after the final tests pass and the consolidation branch is pushed/saved should you delete old branches, remove clean worktrees, or delete remote branches. If a source branch is pinned by a worktree, remove the clean worktree first; never force-remove dirty worktrees without explicit approval.
12. After deletion, re-run `git branch`, `git branch -r`, `git worktree list --porcelain`, and `git status --short --branch` to prove the cleanup actually landed and the checkout is clean.

```bash
git switch $MAIN
git pull --ff-only origin $MAIN
git switch -c consolidate/<topic-and-date>
git merge --no-ff <branch>
# resolve conflicts, then:
pytest <focused tests>
pytest
# fix failures before the next merge
```

Consolidation friction guards from real cleanup runs:
- `git rev-list --left-right --count $MAIN...<branch>` reports left side as commits only on `$MAIN` and right side as commits only on `<branch>`. Label them carefully: `behind=left`, `ahead=right`.
- In `zsh`, avoid using a variable named `path`; it shadows command lookup. Use `wt_path` or run loops under `bash`.
- Generated files may churn during commit hooks or tests. Check `git diff --stat` before committing/deleting; restore or include generated files intentionally, never accidentally.
- Remote branch deletion can partially fail when one ref is missing. Retry only the existing remote refs after checking `git branch -r`.
- Branches checked out in worktrees cannot be deleted. Verify the worktree is clean, remove the worktree, then delete the branch.
- When a branch stacks on top of an explicitly active branch, cherry-pick only the top useful commit(s) instead of merging the whole stack.
- When a source worktree has uncommitted work, make a temporary local source commit or a patch from selected paths before cherry-picking. Exclude raw run outputs, caches, pycache, and regenerated bundles unless they are intentional deliverables.
- If old tests and new code represent two different contracts, choose the current intended contract explicitly and update tests as part of the merge, rather than papering over both behaviors.

**6. PR-then-merge approved branches** — don't stop at "PR opened"; merge it after CI/review.
```bash
git switch <branch> && git rebase $MAIN
git push --force-with-lease origin <branch>
gh pr create --base $MAIN --head <branch>
```

**7. Cherry-pick approved commits, then delete**
```bash
git switch $MAIN && git pull --ff-only origin $MAIN
git cherry-pick <sha1> <sha2>
git push origin $MAIN
git branch -d <branch> || git branch -D <branch>
git push origin --delete <branch>
```

**8. Drop stashes (one at a time)**
```bash
git stash drop stash@{N}                    # or: git stash branch <name> stash@{N}
```

**9. Sibling variants & other on-disk clones — port-and-delete**
```bash
git remote add _variant <path> && git fetch _variant
git cherry-pick <sha>                       # or: git branch <new-name> _variant/<branch>
git remote remove _variant
# Only after explicit "yes, delete the directory":
rm -rf "<absolute path>"
```

**10. Cloud workspaces — port-and-down/destroy**
```bash
megaplan cloud exec "git -C $WS push origin <branch>"
# After confirming push landed:
megaplan cloud down                         # pause, keep volume
megaplan cloud destroy                      # drop volume — NOT recoverable
```

**11. Codespaces — port-then-delete**
```bash
gh codespace ssh -c <name> -- 'cd /workspaces/<repo> && git push origin <branch>'
gh codespace delete -c <name>
```

**12. Force-delete unmerged branches** — only with explicit "yes, lose these commits" per branch
```bash
git log --oneline $MAIN..<branch>           # show what's being lost first
git branch -D <branch>
# Commits remain reflog-reachable ~90 days.
```

## What NOT to do

- Never `git stash clear`, `git reflog expire`, `git gc --prune=now`, or `git push --force` (use `--force-with-lease`).
- Never silently `-D` a branch the user only OK'd under `-d`. Surface the refusal.
- Never delete `release/*`, `prod/*`, `staging/*`, `hotfix/*`, or the default branch.
- Never `rm -rf` a sibling variant, `megaplan cloud destroy`, or `gh codespace delete` without per-item approval and a unique-work summary. All non-reflog-recoverable.
- Never deploy a dormant cloud runner just to survey it — ask.
- Never let a "yes, delete branch X" cascade into dropping a stash/codespace/cloud branch that references X. All separate approvals.
- Never rewrite history (rebase, filter-branch, reset --hard on shared branches) as cleanup.

## Reporting format

```
Cleaned up:
  Local deleted:        N   (<list or "+N more">)
  Remote deleted:       N
  Worktrees removed:    N
  Stashes dropped:      N
  Worktree pruned:      N
  Merged to main:       N
  PRs opened:           N
  Cherry-picked:        N
  Sibling/clones:       ported N, removed N (<paths>)
  Cloud workspaces:     ported N, down N, destroyed N
  Codespaces:           ported N, deleted N

Kept:
  N open/draft PR    N protected    N active

Ready to delete (pending per-item approval):
  <bucket>: N — <reason>

Still to decide:
  <bucket>: N — <reason>
```

## Skip this skill when

- User wants disk file cleanup → `disk-cleanup`.
- User wants history rewrite or lost-commit recovery → reflog / `git fsck`, not branch hygiene.
- Not a git repo (`git rev-parse --git-dir` fails) → say so and stop.
