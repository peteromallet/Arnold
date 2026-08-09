# Final judgment

Use three durable keep lines only:

- `origin/main` — general code
- `origin/editible-install` — deploy-mirror state
- `origin/fix/r7-fresh-child-launch-20260805` — active R5–R7/vj24 epic work

Create one temporary recovery ref, `recovery/box-cleanup-20260807`, that reaches every box-only tip. Keep it until all selected commits are merged and the bundles are independently restored. Never merge this synthetic recovery ref itself.

Use the authoritative 60-tree box deletion set, not the broader 71-tree count. Counts are audit expectations, never deletion inputs.

## 1. Verdict on the 12 decision items

| Item | Verdict | Judgment |
|---|---|---|
| `megaplan/custody-control-plane/m10-safe-retry-recovery-and-effects` | Backup, then delete remote ref | The remote ref is fully contained in `origin/main`. Deleting it cannot remove `bc0c600c` from the box. Keep the box tree until schedules and dependents are migrated. |
| `local/extension-foundation-completion` | Keep — human-gated | Known real but incomplete work. Bundle now. Do not merge unfinished history or delete it. My recommendation is to finish it on its own line, then fold intentionally. |
| `epic/extension-reality-m1-trust-model-truth` | Keep — human-gated | Bundle with the extension lineage. A human must determine whether it is a required ancestor or an abandoned experiment. |
| `epic/extension-reality-m3-export-readiness-convergence` | Keep — human-gated | Same decision gate; likely overlaps the other extension/export lineage and must not be merged blindly. |
| `megaplan/m3-export-readiness-20260710-0146` | Keep — human-gated | Bundle now. Human chooses the canonical maximal lineage before any fold or deletion. |
| `cloud/vibecomfy-trust-correctness-2026-07/sprint-1` | Keep — human-gated | Its 721 commits and cross-project flavor make blind merging inappropriate. My eventual recommendation is backup-then-delete if inspection confirms it is unrelated to Arnold, but no automatic deletion. |
| `preserved-arnold-megaplan-vendor-pre-m11-20260731` | Keep | Deliberate vendor recovery snapshot. Retain until a file-level manifest proves every required vendor artifact exists on origin. |
| `arnold-9f9982c855...` | Backup, then delete — gated | First make `2bd0b2d34` fully self-contained, preserve every object named by the runtime-cutover artifacts, disable its alternate temporarily, and pass `git fsck`. Remove the owned worktree before deleting `9f9982c855`. |
| `/workspace/0` | Backup, then delete | Record metadata and checksum and copy it without printing its contents. Delete only after process/config/reference scans find no consumer. |
| `arnold-runtime-50ef856df5` / `arnold-runtime-7dab2f2645` | Backup, then delete as a unit | Preserve both through origin and a verified bundle. After liveness/reference checks, delete dependent `7dab2f2645` first, then object-source `50ef856df5`. |
| `arnold-5bf11d5a5600` | Backup, then delete as a unit | Old M10/receipt work with no other references. Bundle all refs and dirty state, remove its two worktrees, prune, then delete the owner. |
| R5 epic predecessor tree | Keep | It owns active-plan WBC worktrees. Fold WBC commits into the R7 line now, but retain the tree and worktrees until the active R7 epic no longer consumes them. |

The five large divergent lineages are therefore a hard human gate, not cleanup candidates.

## Additional merge judgment

These are the intended integrations:

- Into the active R7 line:

  - All nine listed R5–R7/vj24 origin WIP branches
  - The six critique-ledger plan-lineage branches
  - Local `fix/critique-vj24-c116-authority-20260805`
  - Local `fix/critique-vj24-c116-selector-20260805`
  - Box tips `72b5b0bd4c`, `8e80ecc95`, `3bea921ad`, `079927677`
  - The eight additional active-epic worktree tips
  - WBC tips `c116f38cc` and `5a64bdd10`
  - `codex/simple-three-hour-fixer-live-20260727`
  - `fix/resident-hermes-resume-recovery`

- Into `origin/main`:

  - Mac-main commits, oldest first: `20cb1a8eb`, `9bf8e0556`, `26fecb4d2`
  - The 11 named non-vj24 Mac unique branches and all 56 remaining true-unique Mac branches
  - Box runtime heads `44e249df3` and `972e78a1d` and their selected fixes
  - The seven notable unique box clones, deduplicating overlapping tips
  - These pre-epic WIP branches:  
    `fix/cloud-resident-timeout-optin-merged-20260720`,  
    `fix/simple-fixer-durable-runner-exit-20260729`,  
    `fix/finalize-strict-dependency-reasons-20260726`,  
    `fix/runtime-provenance-historical-shannon-compat-20260726`,  
    `fix/superfixer-historical-failure-custody-20260716`,  
    `repair/durable-cloud-runtime-20260726`,  
    `runtime/custody-older-engine-fixes-92aee998`
  - From the small-origin-WIP group:  
    `fix/watchdog-repair-loop-unraisable-ba423`,  
    `fix/stale-legacy-allowlist-98e`,  
    `fix/tiebreaker-cli-surfaces-20260731`

- Into `origin/editible-install`:

  - `/workspace/arnold`’s deploy-specific lineage at `480b607653`
  - The deploy result of the resident/runtime changes merged into main
  - Do not merge data-store files, resident state, schedules, credentials, or generated runtime artifacts.

- Backup, then delete without merging:

  - The nine pre-epic megaplan plan branches
  - `run/custody-m10-stable-runtime-20260726`
  - Both local-main checkpoint branches
  - `archive/custody-overnight-repairs-8ec28d68-20260723`
  - `agent/amend-m11-recovery-tickets-20260729`
  - All other members of the approximately 51-branch small-origin-WIP group
  - The remaining box-only candidate clones not selected above

This avoids filling `main` with obsolete operational/checkpoint history while retaining it in bundles.

# 2. Ordered execution plan

## Phase A — do now: recovery and timer correction, no deletion

### A1. Freeze exact manifests

Create TSV manifests containing full 40-character hashes and literal paths:

- `box-imports.tsv`: source path, source ref/`HEAD`, expected SHA, import ref
- `box-delete.tsv`: literal path, expected HEAD, owner, alternates source, disposition
- `origin-delete.tsv`: expected remote SHA and full ref
- `local-delete.tsv`: expected SHA, branch, preserving origin ref
- `worktrees.tsv`: owner, worktree path, expected HEAD
- `critical-oids.txt`: every mandatory box-only OID

The mandatory list must include at least:

```text
f5a38311d
eaf4457d7
7d8426ca
3299a4f076
44e249df3
972e78a1d
8e80ecc95
72b5b0bd4c
3bea921ad
079927677
4e5760643
28a60ce79
1a9538f47
189ea0b73
4b84dfbc3
e3782faf9
2354ffee4
81def9a83
c116f38cc
5a64bdd10
480b607653
```

Resolve every prefix to a full OID in its source repository. Include every additional tip from the 25 box-only clone set.

### A2. Snapshot the timer configuration and repoint it

```bash
set -euo pipefail

cleanup_id=arnold-branch-cleanup-20260807
cleanup_root=/var/lib/arnold/megaplan-resident-recovery/$cleanup_id

sudo install -d -m 0700 \
  "$cleanup_root/configs" \
  "$cleanup_root/git" \
  "$cleanup_root/manifests" \
  "$cleanup_root/quarantine"

sudo systemctl cat megaplan-resident-schedule-runner.service \
  >"$cleanup_root/configs/megaplan-resident-schedule-runner.before.txt"

sudo systemctl show megaplan-resident-schedule-runner.service \
  >"$cleanup_root/configs/megaplan-resident-schedule-runner.before.properties"

sudo install -d \
  /etc/systemd/system/megaplan-resident-schedule-runner.service.d

sudo sh -c 'umask 022
printf "%s\n" \
  "[Service]" \
  "ExecStart=" \
  "ExecStart=/usr/local/bin/arnold-resident-schedule-run-once-r6" \
  > /etc/systemd/system/megaplan-resident-schedule-runner.service.d/10-r6-pin.conf'

sudo systemctl daemon-reload
sudo systemctl reset-failed megaplan-resident-schedule-runner.service
sudo systemctl start megaplan-resident-schedule-runner.service

systemctl show \
  -p ExecStart \
  megaplan-resident-schedule-runner.service

sudo journalctl \
  -u megaplan-resident-schedule-runner.service \
  --since "10 minutes ago" \
  --no-pager
```

The effective `ExecStart` must name only the `-r6` pin. Confirm the run targets `megaplan-cloud-agent-resident-only`, not the stopped `megaplan-cloud-agent`.

Do not remove any stale pin yet. Do not stop the existing ad-hoc schedule loop during this correction.

### A3. Build origin and bundle recovery backstops

Do not add recovery refs inside live repositories. Fetch them read-only into a separate bare staging repository.

```bash
git init --bare "$cleanup_root/git/box-staging.git"
git -C "$cleanup_root/git/box-staging.git" remote add origin <origin-url>

while IFS=$'\t' read -r source source_ref expected_oid import_ref; do
  git -C "$cleanup_root/git/box-staging.git" \
    fetch --no-tags "$source" "$source_ref:$import_ref"

  actual_oid=$(
    git -C "$cleanup_root/git/box-staging.git" \
      rev-parse "$import_ref^{commit}"
  )

  test "$actual_oid" = "$expected_oid"
done <"$cleanup_root/manifests/box-imports.tsv"
```

Construct one recovery anchor whose parents are every imported tip:

```bash
mapfile -t cleanup_parents < <(
  git -C "$cleanup_root/git/box-staging.git" \
    for-each-ref --format='%(objectname)' refs/heads/import |
  sort -u
)

cleanup_parent_args=()
for cleanup_oid in "${cleanup_parents[@]}"; do
  cleanup_parent_args+=(-p "$cleanup_oid")
done

cleanup_empty_tree=$(
  git -C "$cleanup_root/git/box-staging.git" \
    hash-object -t tree -w --stdin </dev/null
)

cleanup_anchor=$(
  printf '%s\n' \
    'Arnold box recovery anchor before branch cleanup 2026-08-07' |
  git -C "$cleanup_root/git/box-staging.git" \
    -c user.name='Arnold Recovery' \
    -c user.email='arnold-recovery@localhost' \
    commit-tree "$cleanup_empty_tree" "${cleanup_parent_args[@]}"
)

git -C "$cleanup_root/git/box-staging.git" update-ref \
  refs/heads/recovery/box-cleanup-20260807 \
  "$cleanup_anchor"

git -C "$cleanup_root/git/box-staging.git" bundle create \
  "$cleanup_root/git/box-cleanup-20260807.bundle" \
  refs/heads/recovery/box-cleanup-20260807

git -C "$cleanup_root/git/box-staging.git" bundle verify \
  "$cleanup_root/git/box-cleanup-20260807.bundle"

git -C "$cleanup_root/git/box-staging.git" push origin \
  refs/heads/recovery/box-cleanup-20260807
```

In a fresh bare repository, fetch both the origin recovery ref and the bundle. Require every full OID in `critical-oids.txt` to exist and be an ancestor of the recovery anchor.

Also create an origin-wide pre-cleanup mirror bundle:

```bash
git clone --mirror <origin-url> \
  "$cleanup_root/git/origin-precleanup.git"

git -C "$cleanup_root/git/origin-precleanup.git" bundle create \
  "$cleanup_root/git/origin-precleanup-20260807.bundle" \
  --all

git -C "$cleanup_root/git/origin-precleanup.git" bundle verify \
  "$cleanup_root/git/origin-precleanup-20260807.bundle"

sha256sum "$cleanup_root"/git/*.bundle \
  >"$cleanup_root/git/SHA256SUMS"
```

Copy the bundles and checksums to a second failure domain, such as the Mac or encrypted object storage. A second directory on the same box is not an independent backup.

The correction remains explicit: preserve `44e249df3`; `4ed98585` itself is already on origin.

### A4. Back up non-Git state

Before removing any worktree, capture:

- `git status --porcelain=v2 -z`
- staged and unstaged binary patches
- untracked files
- file ownership, modes, ACLs and xattrs
- `.git` pointer and owner mapping

Back up the schedule store and unit/pin files with mode `0600`. Do not push `.cloud-hot-env`, resident state, schedules, or credentials to Git.

### A5. Record liveness

For every `-live` and `-canary` path, plus the two `arnold-runtime-*` trees, record:

- process CWDs, executables and open FDs
- running-container bind mounts
- systemd and cron references
- references in the two resident environment files
- schedule references
- active supervisor/runtime configuration

Any positive hit makes the tree a KEEP for this cleanup. A zero-hit tree must remain observed over at least one full active schedule interval before removal.

### Phase A must not touch

- `/workspace/arnold` refs, index, checkout, schedules or data
- The active R7 install or its three worktrees
- The active critique-ledger worktree
- `4ed98585...-live`, its venv, or containers
- WBC trees or the R5 owner
- Any branch ref or filesystem tree
- Any stale pin
- Any alternates file
- Any Git GC

### Phase A exit criteria

- Every mandatory OID is reachable from the origin recovery ref.
- Every mandatory OID restores from the bundle in an empty repository.
- Bundle checksums exist in two failure domains.
- Timer service resolves to `-r6` and completes successfully.
- Full manifests have no duplicate or unclassified path.
- No deletion has occurred.

## Phase B — short term: integrate unique work and remove dependencies

### B1. Integrate only from disposable clones

Never perform integration in `/workspace/arnold` or a live runtime checkout.

```bash
git clone <origin-url> /var/tmp/arnold-cleanup-integration
git -C /var/tmp/arnold-cleanup-integration fetch origin \
  recovery/box-cleanup-20260807

git -C /var/tmp/arnold-cleanup-integration switch -c \
  integrate/r7-cleanup-20260807 \
  origin/fix/r7-fresh-child-launch-20260805
```

Merge maximal active-line tips with `--no-ff`, not the synthetic recovery anchor:

```bash
git merge-base --is-ancestor <tip-a> <tip-b>
git merge --no-ff --no-edit <maximal-tip>
```

If an old branch has a patch-equivalent change already present, record the stable patch-ID mapping rather than duplicating it. Resolve conflicts in favor of current runtime contracts while explicitly porting the intended fix.

Run the repository’s required tests after each logical batch. Push an integration branch first. Update a keep line only through a normal fast-forward push or protected-branch PR—never force-push.

### B2. Integrate Mac main and unique branches

First preserve the exact Mac main tip:

```bash
git push origin \
  26fecb4d2:refs/heads/recovery/mac-main-pre-realign-20260807
```

On a branch based on current `origin/main`, cherry-pick the three genuinely unique commits oldest-to-newest:

```bash
git cherry-pick 20cb1a8eb 9bf8e0556 26fecb4d2
```

Merge the remaining Mac unique branches by maximal tip into a main integration branch. Route the two vj24 branches to the R7 integration branch.

Only after the resulting commits or equivalent patches are on `origin/main`, fetch on the Mac and realign main:

```bash
git fetch origin
git switch main
git status --short
git reset --keep origin/main
```

`git reset --keep` must see a clean, backed-up worktree and the exact old tip must still exist under the recovery ref.

Keep local `editible-install`.

### B3. Integrate live box deltas

Route:

- R7/WBC/critique tips → active R7 line
- `44e249df3`, `972e78a1d`, applicable resident/listener fixes → `main`
- Deploy-specific `480b607653` changes → `editible-install`
- Never merge schedule data, resident state, blobs or secrets.

Do not reset any live box checkout after its commits land. Landing on origin is preservation, not authorization to change the running tree.

### B4. Repoint the schedule store

Snapshot the entire store first. Use the repository’s transactional schedule-admin path; do not use blanket `sed -i` over occurrence history.

Repoint every runnable definition and head referring to:

- `arnold-bc0c600c...`
- `arnold-74b4e6b9...`
- `arnold-6ce6d4eb...`

to the active R7 install or an origin-backed successor. Keep `sched_superfixer_hourly_v2` active; archive or tombstone inactive schedules through the supported store operation.

Verification:

```bash
schedule_store=/workspace/arnold/.megaplan/resident/schedules

rg -n --fixed-strings 'arnold-bc0c600c' "$schedule_store"
rg -n --fixed-strings 'arnold-74b4e6b9' "$schedule_store"
rg -n --fixed-strings 'arnold-6ce6d4eb' "$schedule_store"
```

All three searches must be empty before their trees are removed. If immutable store records cannot be migrated safely, keep the corresponding tree; do not reinterpret historical references as harmless.

### B5. Make `2bd0b2d34` self-contained

First identify every valid Git object named by the cutover artifacts and give it a preservation ref. Then repack without `--local`:

```bash
git -C /workspace/arnold-2bd0b2d345022c8797f8e63998b93a08a8ae5954 \
  repack -a -d
```

Back up its alternates file, temporarily move it out of the recognized name, and verify:

```bash
git -C <2bd-path> fsck --full
git -C <2bd-path> rev-list --objects --all >/var/tmp/2bd-objects.txt
```

The repository and every cutover-object preservation ref must resolve while the alternates file is disabled. If anything fails, restore the file immediately and keep `9f9982c855`.

### Phase B must not touch

- Live working directories or running containers
- Any tree referenced by the schedule store
- Any owner before every dependent is gone
- The five human-gated lineages
- The R5/WBC and R7 working trees
- Recovery bundles/backstops
- Remote refs through force-push

### Phase B exit criteria

- Selected source tips are ancestors of their keep line, or have an explicit patch-ID mapping plus recovery proof.
- Origin contains the Mac-main work.
- All box-only mandatory OIDs remain on origin and in the bundle.
- Old schedule-root searches return no matches.
- `2bd0b2d34` passes without alternates.
- Tests pass on fresh clones of all modified keep lines.

## Phase C — ordered deletion

### C1. Quarantine stale pins and trivial artifacts

After at least two successful timer invocations through `-r6`, move the seven stale pins to the recovery quarantine using their literal names. Do not glob.

Move and then delete the two exact failed-clone directories.

Back up `/workspace/0`, scan references without printing its contents, then remove it if unreferenced.

### C2. Delete remote refs with leases

Delete contained origin refs—including the M10 safe-retry remote ref—using the expected SHA:

```bash
while IFS=$'\t' read -r expected_oid full_ref; do
  git push \
    --force-with-lease="$full_ref:$expected_oid" \
    origin \
    ":$full_ref"
done <origin-delete.tsv
```

This is a deletion lease, not a force update. Any changed remote ref stops the row.

Never include:

- The ten origin keep refs
- The five human-gated refs
- `recovery/box-cleanup-20260807`
- Any WIP ref not yet integrated or bundle-proven

### C3. Clean local Mac worktrees before branches

Order:

1. Back up and remove the two unique detached trees.
2. Remove the four origin-contained detached snapshots.
3. Prune the 13 already-broken worktree registrations.
4. Remove branch-linked worktrees.
5. Delete contained branches with `git branch -d`.
6. Use `git branch -D` only where cherry-picking prevents ancestry and both the recovery proof and patch mapping exist.

```bash
git worktree prune --dry-run --verbose
git worktree remove <literal-worktree-path>
git branch -d <contained-branch>
```

Never delete local `main` or local `editible-install`.

### C4. Delete standalone box clones

Immediately eligible after backup and liveness proof:

- Refined authoritative contained-clone set
- Bundle-proven box-only clone set not selected for integration
- Failed-clone artifacts

Before each raw tree deletion:

```bash
test ! -L <literal-path>
test "$(realpath -e <literal-path>)" = "<expected-absolute-path>"
test "$(git -C <literal-path> rev-parse HEAD)" = "<expected-full-oid>"
mountpoint -q <literal-path> && exit 1
```

Also require zero process, container-bind, environment, systemd and schedule references.

Rename into a same-filesystem quarantine first where space allows. Use `rm -rf --one-file-system` only with the exact quarantined path—never a glob or unresolved variable.

### C5. Delete dependents, then owners

Required order:

1. `arnold-runtime-7dab2f2645`
2. `arnold-runtime-50ef856df5`

Then independent owner units:

1. Remove both `5bf11d5a` worktrees.
2. Prune the owner.
3. Delete `5bf11d5a`.

For `9f9982c855`:

1. Confirm `2bd0b2d34` works with alternates disabled.
2. Back up and remove the one `9f9982c855` worktree.
3. Prune.
4. Delete `9f9982c855`.

For `74b4e6b9`:

1. Confirm its unique branches are merged or archive-proven.
2. Confirm zero schedule references.
3. Remove four worktrees.
4. Prune.
5. Delete the owner.

For `bc0c600c`:

1. Integrate/archive and remove alternate-dependent `4076d59ab4` and `a1cbde99c3`.
2. Confirm zero schedule references.
3. Back up all 14 worktree tips and dirty state.
4. Remove worktrees through `git worktree remove`.
5. Prune.
6. Delete the owner.

Then delete `6ce6d4eb` after its schedule-reference count is zero.

Do not delete these owner units during the active epic:

- R7 owner or any of its three worktrees, including `77b76e3a4`
- R5 predecessor or WBC worktrees
- R6 lineage owner/worktree
- `/workspace/arnold`
- `b38460e4d3` while any owned `-live` worktree is live

For `/workspace/arnold`-owned stale worktrees, a late `git worktree remove` is permissible only after backup and liveness proof. Never raw-delete them or rewrite/reset the parent checkout.

### C6. GC remains deferred

Do not run `git gc --prune=now` anywhere during deletion.

In particular, no GC on:

- `/workspace/arnold`
- Active R7/R5/R6 repositories
- Any `-live` tree
- Any remaining alternates source
- Any owner still carrying worktrees

Default `git gc` may run later on non-live retained repositories after the rollback window. Full-clone deletion already frees their object storage.

### Phase C exit criteria

- Every deleted item has a manifest row with expected SHA, backup, origin proof and action time.
- No stale worktree registration points to a deleted path.
- No alternates file points to a deleted object store.
- No schedule definition points to a deleted tree.
- Keep refs and recovery refs are unchanged.
- Active containers, listener and R7 epic remain healthy.

## Phase D — verification and closeout

Run these checks from fresh clones, not live installs:

- All three keep lines clone and pass tests.
- Active-line source tips are reachable or patch-mapped.
- `44e249df3`, `972e78a1d`, Mac-main commits and selected general fixes are preserved on `main`.
- Deploy changes are present on `editible-install`.
- Every mandatory box OID restores from the bundle.
- Bundle SHA-256 checks match the second copy.
- `git worktree prune --dry-run` reports nothing unexpected.
- No alternates file names a removed directory.
- Docker bind mounts resolve.
- The resident listener is responsive.
- The timer invokes the `-r6` pin successfully.
- At least one due execution of `sched_superfixer_hourly_v2` succeeds without duplicate occurrence creation.
- The active critique-ledger plan continues advancing.
- Journal logs contain no new missing-path, JSON-decode, container-target or editable-install failures.

Keep `recovery/box-cleanup-20260807` until all mandatory box work has landed on a keep line or the operator explicitly accepts bundle-only archival. A separate origin pre-cleanup recovery anchor, if created, can expire after 30 days of clean operation. Do not expire the five human-gated branches.

# 3. Principal risks and rollback

- **A deleted ref changed after the survey:** deletion leases reject it. Re-survey that ref; never override the lease.
- **A bundle omitted an alternate object:** the empty-repository restore test catches it. Restore/retain the alternate and recreate the bundle.
- **A worktree has dirty or untracked state:** refuse removal until binary patches and an untracked-file archive are verified.
- **A path is still executed intermittently:** container, `/proc`, service, environment and schedule scans must all be clear over a full schedule interval.
- **Timer repoint causes duplicate execution:** restore the saved unit/drop-in, daemon-reload, and rely on the still-running ad-hoc loop while diagnosing.
- **Schedule migration corrupts state:** take the resident schedule lock, restore the mode-preserving snapshot atomically, and keep all referenced trees.
- **A deleted remote branch is needed:** fetch its exact SHA from `origin-precleanup-20260807.bundle` and recreate the ref with an absent-ref lease.
- **A deleted standalone tree is needed:** recreate the owner from the bundle/origin first, restore dirty-state archives, then recreate dependent worktrees and alternates.
- **A deleted owner breaks dependents:** restore in reverse deletion order—owner/object source first, then alternates, then linked worktrees.
- **Historical LFS/submodule/vendor data is missing:** Git bundles do not preserve external LFS objects or untracked vendor files. Verify those separately before deleting their only checkout.
- **Secrets leak through recovery artifacts:** schedule/env/state archives stay encrypted or mode `0600`; never push them to origin.

The non-negotiable stop condition is simple: if a candidate cannot be restored from origin plus a tested bundle, or its liveness/dependency status is not zero, it is not deleted.
> **Authority status: non-authoritative.** This document is historical/design record, not a live-authority operator surface (T44 zero-authority migration).
