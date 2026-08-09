# Arnold branch cleanup 2026-08-07 — mechanical action plan

## Reference docs — read these first, in order

This plan is one doc in a pack. Use the others as follows:

1. **`branch-cleanup-judgment-20260807.md`** — the "why": gpt-5.6-sol's merge/delete verdict that this plan executes. When a task's intent is unclear, read the corresponding judgment section. This plan may reference it as "the judgment."
2. **`branch-cleanup-agent-brief-20260807.md`** — your operating brief. Read it before starting. It names the doc locations, the **build branch `fixer/critique-epoch-invalidation-20260806`** (the active epic's box-local working branch, HEAD `f5a38311`, box-only — build from it, preserve it, never delete/reset/force-push), and the full "never do" list.
3. **`megaplan-fixer-briefing-20260807.md`** — the standard you're held to. Every Codex sense-check prompt must anchor against its fixer invariants (evidence not status prose; no competing fixers; durably move the chain; surface structural issues; edit only the approved runtime; push before live).
4. **`megaplan-reference-architecture-20260807.md`** — the full intended design, when you need detail beyond the briefing.
5. **`arnold-end-state-20260807.md`** — the target state this cleanup serves.

**Doc ground rules:** read `megaplan-fixer-briefing-20260807.md` + `megaplan-reference-architecture-20260807.md` from the reachable locations below (check both); if unreachable, record `INTENDED-DESIGN-DOC-MISSING: <path>` for the operator and do NOT substitute the drifted checkout as intended design. The origin keep-line `refs/heads/fix/r7-fresh-child-launch-20260805` is the R7 integration target and is distinct from the box-local build branch `fixer/critique-epoch-invalidation-20260806` (protected by OID `f5a38311d`).

## Operating contract

This plan is intentionally fail-closed. The judgment does not contain the literal authoritative 60-tree survey, most of the named Mac and box branch inventory, schedule IDs/revisions, the Mac transport, or the independent-backup destination. Flash must never reconstruct those facts by guessing. An operator must place the survey export described below at the exact input path before TASK-1. If it is absent or inconsistent, TASK-1 halts and nothing beyond creation of the recovery directory and lock is changed.

Run every command block as one block. `set -euo pipefail` is mandatory. A nonzero exit, an unexpected row, or a failed comparison means: append a terse failure record to the action ledger if possible, halt, and report. Do not skip the failed command and do not advance to the next task.

Access conventions used below are literal:

- Host operations use `ssh root@159.69.51.216 '...'`.
- Operations inside the running container use `docker exec megaplan-cloud-agent-resident-only bash -lc '...'` (or `docker exec -i ... bash -s` for a literal script body).
- Mac operations use the exact SSH target frozen in `mac-ssh-target.txt`; TASK-1 refuses to proceed unless BatchMode SSH and the exact Mac repository path work. No Mac command is inferred from the cloud box.

Fixed paths and names:

```text
host recovery root: /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
host input pack:    /root/arnold-branch-cleanup-20260807-input
container root:     /var/tmp/arnold-branch-cleanup-20260807
container:          megaplan-cloud-agent-resident-only
origin recovery:    refs/heads/recovery/box-cleanup-20260807
R7 keep ref:        refs/heads/fix/r7-fresh-child-launch-20260805
main keep ref:      refs/heads/main
deploy keep ref:    refs/heads/editible-install
```

The input pack is immutable survey data, not an execution script. `INPUT-SHA256SUMS` must cover every other input file. TSVs have no header, use one literal tab between fields, and may not contain blank lines, comments, shell expansions, tabs within values, or newline-bearing paths. It must contain:

```text
INPUT-SHA256SUMS
box-import-seeds.tsv
box-delete-seeds.tsv
origin-delete-seeds.tsv
local-delete-seeds.tsv
worktrees-seeds.tsv
protected-paths.tsv
integration-r7-seeds.tsv
integration-main-seeds.tsv
integration-editible-seeds.tsv
patch-equivalences.tsv
stale-pins.tsv
failed-clones.tsv
reference-files.tsv
cutover-artifacts.tsv
schedule-migrations.tsv
schedule-admin-path.txt
schedule-lock-path.txt
schedule-verification-command.txt
health-verification-commands.tsv
deletion-order.tsv
mac-precleanup-20260807.bundle
mac-ssh-target.txt
mac-repo-path.txt
mac-recovery-root.txt
secondary-rclone-destination.txt
```

The row schemas are fixed:

```text
box-import-seeds.tsv:
  source_path  source_ref  expected_commit_prefix  import_ref
box-delete-seeds.tsv (exactly 60 rows):
  literal_path  expected_HEAD_prefix_or_-  owner_path_or_-  alternates_source_or_-  disposition
origin-delete-seeds.tsv:
  expected_remote_commit_prefix  full_refs/heads/name
local-delete-seeds.tsv:
  expected_commit_prefix  local_branch_name  preserving_full_origin_ref  delete_mode(d|D)
worktrees-seeds.tsv:
  site(box|mac)  owner_repo  literal_worktree_path  expected_HEAD_prefix  class  dirty_policy(clean|required-backup)
protected-paths.tsv:
  site(host|box|mac)  literal_path  reason
integration-{r7,main,editible}-seeds.tsv:
  batch_number  order_number  source_label  source_locator  expected_commit_prefix  operation(merge|cherry-pick|patch-equivalent)  equivalent_destination_oid_or_-
patch-equivalences.tsv:
  source_full_oid  destination_full_oid  stable_patch_id  destination_keep_ref
stale-pins.tsv (exactly 7 rows):
  literal_host_path  expected_sha256  expected_octal_mode
failed-clones.tsv (exactly 2 rows):
  literal_container_path  expected_tree_manifest_sha256
reference-files.tsv:
  site(host|box|mac)  literal_file_or_directory  class(systemd|cron|environment|schedule|supervisor|runtime)
cutover-artifacts.tsv:
  literal_path_inside_2bd_repo  expected_sha256
schedule-migrations.tsv:
  schedule_id  expected_revision  operation(update|archive|tombstone)  literal_patch_file  expected_new_revision  expected_target_or_-
health-verification-commands.tsv:
  check_name  site(host|box)  exact_read_only_command  expected_stdout_regex
deletion-order.tsv:
  integer_sequence  kind(pin|failed-clone|non-git|remote-ref|mac-worktree|mac-branch|standalone|linked-worktree|owner)  literal_target  expected_full_oid_or_sha256_or_-  owner_or_-  unit_name
```

The five hard-human-gated refs and the vendor snapshot are never deletion inputs in this plan:

```text
refs/heads/local/extension-foundation-completion
refs/heads/epic/extension-reality-m1-trust-model-truth
refs/heads/epic/extension-reality-m3-export-readiness-convergence
refs/heads/megaplan/m3-export-readiness-20260710-0146
refs/heads/cloud/vibecomfy-trust-correctness-2026-07/sprint-1
refs/heads/preserved-arnold-megaplan-vendor-pre-m11-20260731
```

Together with the three keep refs and the recovery ref, these are the ten protected origin refs. A count is only an audit assertion. Every fetch, integration, quarantine, branch deletion, and tree deletion consumes a literal frozen manifest row.

No command in this plan runs `git gc`, `git maintenance run`, `git prune`, or `git repack` except the one explicit `git repack -a -d` for `2bd0b2d34`. Every disposable repository is configured with `gc.auto=0` and `maintenance.auto=false` before fetches.

---

## Phase A — recovery, timer correction, state backup, and liveness; no deletion

### TASK-1 — Establish the fail-closed run, validate the operator input pack, and install the Codex gate wrapper

**OWNER — FLASH**

**COMMANDS**

Host preflight and immutable input copy:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
umask 077
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
INPUT=/root/arnold-branch-cleanup-20260807-input
CONTAINER=megaplan-cloud-agent-resident-only

install -d -m 0700 "$HROOT"
mkdir "$HROOT/.execution-lock"
printf 'started_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$HROOT/action-ledger.tsv"
chmod 0600 "$HROOT/action-ledger.tsv"

test "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = true
test -d "$INPUT"
cd "$INPUT"
sha256sum -c INPUT-SHA256SUMS

required='INPUT-SHA256SUMS box-import-seeds.tsv box-delete-seeds.tsv origin-delete-seeds.tsv local-delete-seeds.tsv worktrees-seeds.tsv protected-paths.tsv integration-r7-seeds.tsv integration-main-seeds.tsv integration-editible-seeds.tsv patch-equivalences.tsv stale-pins.tsv failed-clones.tsv reference-files.tsv cutover-artifacts.tsv schedule-migrations.tsv schedule-admin-path.txt schedule-lock-path.txt schedule-verification-command.txt health-verification-commands.tsv deletion-order.tsv mac-precleanup-20260807.bundle mac-ssh-target.txt mac-repo-path.txt mac-recovery-root.txt secondary-rclone-destination.txt'
for f in $required; do test -f "$INPUT/$f"; done

test "$(awk 'NF{n++} END{print n+0}' "$INPUT/box-delete-seeds.tsv")" -eq 60
test "$(awk 'NF{n++} END{print n+0}' "$INPUT/stale-pins.tsv")" -eq 7
test "$(awk 'NF{n++} END{print n+0}' "$INPUT/failed-clones.tsv")" -eq 2
awk -F '\t' 'NF!=4{exit 1}' "$INPUT/box-import-seeds.tsv"
awk -F '\t' 'NF!=5{exit 1}' "$INPUT/box-delete-seeds.tsv"
awk -F '\t' 'NF!=2{exit 1}' "$INPUT/origin-delete-seeds.tsv"
awk -F '\t' 'NF!=4{exit 1}' "$INPUT/local-delete-seeds.tsv"
awk -F '\t' 'NF!=6{exit 1}' "$INPUT/worktrees-seeds.tsv"
awk -F '\t' 'NF!=6{exit 1}' "$INPUT/deletion-order.tsv"
test "$(cut -f1 "$INPUT/box-delete-seeds.tsv" | sort | uniq -d | wc -l)" -eq 0

SECONDARY=$(tr -d '\r\n' <"$INPUT/secondary-rclone-destination.txt")
case "$SECONDARY" in *:*) ;; *) exit 1 ;; esac
case "$SECONDARY" in /*|file:*|local:*) exit 1 ;; esac
command -v rclone >/dev/null

install -d -m 0700 "$HROOT/input"
cp -a "$INPUT/." "$HROOT/input/"
chmod -R go-rwx "$HROOT/input"
sha256sum "$HROOT/input"/* >"$HROOT/input-freeze.sha256"
chmod 0400 "$HROOT/input-freeze.sha256"

install -d -m 0700 "$HROOT/configs" "$HROOT/git" "$HROOT/manifests" "$HROOT/quarantine" "$HROOT/evidence" "$HROOT/non-git" "$HROOT/prompts" "$HROOT/codex"
docker exec "$CONTAINER" bash -lc 'rm -rf -- /var/tmp/arnold-branch-cleanup-20260807.new; install -d -m 0700 /var/tmp/arnold-branch-cleanup-20260807.new'
docker cp "$HROOT/input/." "$CONTAINER:/var/tmp/arnold-branch-cleanup-20260807.new/input/"
docker exec "$CONTAINER" bash -lc 'mv /var/tmp/arnold-branch-cleanup-20260807.new /var/tmp/arnold-branch-cleanup-20260807; install -d -m 0700 /var/tmp/arnold-branch-cleanup-20260807/{bin,manifests,evidence,prompts,codex,git,backups,integration,verify}'

printf 'input_frozen_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$HROOT/action-ledger.tsv"
HOST
```

Container tool and intended-design-document reachability check. Absence of either document is recorded, as required, but the Codex prompts also carry the six fixer invariants verbatim:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
for x in git rg jq tar sha256sum codex; do command -v "$x" >/dev/null; done
cd "$CROOT/input"
sha256sum -c INPUT-SHA256SUMS >"$CROOT/evidence/input-check.txt"
for f in docs/megaplan-reference-architecture-20260807.md docs/megaplan-fixer-briefing-20260807.md; do
  if test -r "/workspace/arnold/$f"; then
    printf "reachable\t/workspace/arnold/%s\n" "$f"
  elif test -r "$CROOT/input/$f"; then
    printf "reachable\t%s/input/%s\n" "$CROOT" "$f"
  else
    printf "missing\t%s\n" "$f"
  fi
done >"$CROOT/evidence/intended-design-docs.tsv"
chmod 0600 "$CROOT/evidence/intended-design-docs.tsv"

test -x "$(tr -d "\r\n" <"$CROOT/input/schedule-admin-path.txt")"
git bundle verify "$CROOT/input/mac-precleanup-20260807.bundle" >"$CROOT/evidence/mac-bundle-verify.txt" 2>&1
'
```

Mac transport is a mandatory precondition because Mac-main integration and local cleanup cannot be executed from the cloud box without it:

```bash
MAC_TARGET=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-ssh-target.txt')
MAC_REPO=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-repo-path.txt')
test -n "$MAC_TARGET"
test "${MAC_REPO#/}" != "$MAC_REPO"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$MAC_TARGET" "test -d '$MAC_REPO/.git' -o -f '$MAC_REPO/.git'; git -C '$MAC_REPO' rev-parse --is-inside-work-tree"
```

Install the exact wrapper used for every Codex sense-check. This file edit does not send a prompt yet:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck >/dev/null; chmod 0700 /var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck' <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
CHECKPOINT=${1:?checkpoint name required}
FRAGMENT=${2:?prompt fragment required}
case "$CHECKPOINT" in CHECKPOINT-SENSECHECK-[0-9]*|FINAL-CODEX-AUDIT) ;; *) exit 2 ;; esac
test -r "$FRAGMENT"
PROMPT="$CROOT/prompts/${CHECKPOINT}.full.md"
RESULT="$CROOT/codex/${CHECKPOINT}.result.md"
LOG="$CROOT/codex/${CHECKPOINT}.log"
{
  cat <<'STANDARD'
You are the independent Codex validation gate for the Arnold branch-cleanup run. Work read-only. Do not edit files, update refs, start or stop services, launch a fixer, push, delete, prune, repack, or run Git GC.

Before evaluating evidence, read and cite both canonical intended-design documents if either reachable location contains them:
- /workspace/arnold/docs/megaplan-reference-architecture-20260807.md (or /var/tmp/arnold-branch-cleanup-20260807/input/docs/megaplan-reference-architecture-20260807.md)
- /workspace/arnold/docs/megaplan-fixer-briefing-20260807.md (or /var/tmp/arnold-branch-cleanup-20260807/input/docs/megaplan-fixer-briefing-20260807.md)

Anchor the validation against the six-plane intended architecture and especially the fixer invariants in megaplan-fixer-briefing-20260807.md. The checkpoint standard is: evidence, not status prose; no competing fixers; durably move the chain; surface structural issues; edit only the approved runtime; push before live. If a document is unreachable, include `INTENDED-DESIGN-DOC-MISSING: <path>` in the report so the operator can place it; do not silently substitute the drifted checkout as intended design.

Independently run the read-only checks requested below. Treat manifests, command output, and live state as evidence; do not accept a prior agent's success prose. A missing artifact, ambiguous result, unexpected live reference, or unverifiable claim is FAIL. Explain evidence and structural issues concisely.
STANDARD
  cat "$FRAGMENT"
  printf '\nYour final nonblank line must be exactly `%s: PASS` or `%s: FAIL`.\n' "$CHECKPOINT" "$CHECKPOINT"
} >"$PROMPT"

set +e
(cd "$CROOT" && codex exec --sandbox read-only --skip-git-repo-check --output-last-message "$RESULT" - <"$PROMPT") 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
test "$rc" -eq 0
last=$(awk 'NF{line=$0} END{print line}' "$RESULT")
test "$last" = "$CHECKPOINT: PASS"
WRAPPER
```

**DONE-CHECK**

- Host `.execution-lock` exists and was newly created.
- `INPUT-SHA256SUMS` verifies in both the host frozen copy and container copy.
- The authoritative box deletion input has exactly 60 unique literal paths; stale-pin and failed-clone inputs have exactly 7 and 2 rows.
- The container is running, the schedule-admin binary is executable, the Mac bundle verifies, BatchMode Mac access works, the second backup destination is non-local, and `run-sensecheck` has mode `0700`.
- `intended-design-docs.tsv` has exactly two rows, each saying either `reachable` or `missing`; missing is explicitly reportable, never silently ignored.

**PRECONDITION** — None. If the lock already exists, an operator must resolve the prior run; Flash must not remove it.

### TASK-2 — Resolve full OIDs, freeze all six mandatory manifests, and capture the no-touch baseline

**OWNER — FLASH**

**COMMANDS**

Resolve container-side manifests without updating any source ref, index, worktree, alternates file, or schedule:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
IN=$CROOT/input
OUT=$CROOT/manifests
install -d -m 0700 "$OUT"

full_commit() {
  repo=$1 ref=$2 prefix=$3
  test -d "$repo"
  oid=$(git -C "$repo" rev-parse --verify "$ref^{commit}")
  case "$oid" in "$prefix"*) ;; *) return 1 ;; esac
  test "${#oid}" -eq 40
  printf '%s' "$oid"
}

: >"$OUT/box-imports.tsv.tmp"
while IFS=$'\t' read -r source source_ref prefix import_ref; do
  test -n "$source"; test -n "$source_ref"; test -n "$prefix"
  case "$source" in /workspace/*) ;; *) exit 1 ;; esac
  case "$import_ref" in refs/heads/import/*) ;; *) exit 1 ;; esac
  oid=$(full_commit "$source" "$source_ref" "$prefix")
  printf '%s\t%s\t%s\t%s\n' "$source" "$source_ref" "$oid" "$import_ref" >>"$OUT/box-imports.tsv.tmp"
done <"$IN/box-import-seeds.tsv"
test "$(cut -f4 "$OUT/box-imports.tsv.tmp" | sort | uniq -d | wc -l)" -eq 0
mv "$OUT/box-imports.tsv.tmp" "$OUT/box-imports.tsv"

: >"$OUT/box-delete.tsv.tmp"
while IFS=$'\t' read -r path prefix owner alternate disposition; do
  case "$path" in /workspace/*) ;; *) exit 1 ;; esac
  test ! -L "$path"
  test "$(realpath -e "$path")" = "$path"
  if test "$prefix" = -; then oid=-; else oid=$(full_commit "$path" HEAD "$prefix"); fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$path" "$oid" "$owner" "$alternate" "$disposition" >>"$OUT/box-delete.tsv.tmp"
done <"$IN/box-delete-seeds.tsv"
test "$(awk 'NF{n++} END{print n+0}' "$OUT/box-delete.tsv.tmp")" -eq 60
test "$(cut -f1 "$OUT/box-delete.tsv.tmp" | sort | uniq -d | wc -l)" -eq 0
mv "$OUT/box-delete.tsv.tmp" "$OUT/box-delete.tsv"

origin_url=$(git -C /workspace/arnold remote get-url origin)
test -n "$origin_url"
printf '%s\n' "$origin_url" >"$OUT/origin-url.txt"
: >"$OUT/origin-delete.tsv.tmp"
while IFS=$'\t' read -r prefix full_ref; do
  case "$full_ref" in refs/heads/*) ;; *) exit 1 ;; esac
  mapfile -t found < <(git ls-remote --refs "$origin_url" "$full_ref" | awk '{print $1}')
  test "${#found[@]}" -eq 1
  oid=${found[0]}
  case "$oid" in "$prefix"*) ;; *) exit 1 ;; esac
  printf '%s\t%s\n' "$oid" "$full_ref" >>"$OUT/origin-delete.tsv.tmp"
done <"$IN/origin-delete-seeds.tsv"
mv "$OUT/origin-delete.tsv.tmp" "$OUT/origin-delete.tsv"

: >"$OUT/worktrees.box.tsv.tmp"
while IFS=$'\t' read -r site owner path prefix class dirty_policy; do
  test "$site" = box || continue
  case "$owner" in /workspace/*) ;; *) exit 1 ;; esac
  case "$path" in /workspace/*) ;; *) exit 1 ;; esac
  oid=$(full_commit "$path" HEAD "$prefix")
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$site" "$owner" "$path" "$oid" "$class" "$dirty_policy" >>"$OUT/worktrees.box.tsv.tmp"
done <"$IN/worktrees-seeds.tsv"
mv "$OUT/worktrees.box.tsv.tmp" "$OUT/worktrees.box.tsv"

cat >"$OUT/mandatory-prefixes.txt" <<'OIDS'
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
OIDS

cut -f1 "$OUT/box-imports.tsv" | sort -u >"$OUT/source-repositories.txt"
grep -qxF /workspace/arnold "$OUT/source-repositories.txt" || printf '/workspace/arnold\n' >>"$OUT/source-repositories.txt"
: >"$OUT/critical-mandatory-resolved.txt.tmp"
while IFS= read -r prefix; do
  : >"$OUT/.matches"
  while IFS= read -r repo; do
    oid=$(git -C "$repo" rev-parse --verify "$prefix^{commit}" 2>/dev/null || true)
    test -z "$oid" || printf '%s\n' "$oid" >>"$OUT/.matches"
  done <"$OUT/source-repositories.txt"
  sort -u "$OUT/.matches" -o "$OUT/.matches"
  test "$(awk 'NF{n++} END{print n+0}' "$OUT/.matches")" -eq 1
  cat "$OUT/.matches" >>"$OUT/critical-mandatory-resolved.txt.tmp"
done <"$OUT/mandatory-prefixes.txt"
cat "$OUT/critical-mandatory-resolved.txt.tmp" <(cut -f3 "$OUT/box-imports.tsv") | sort -u >"$OUT/critical-oids.txt"
rm -f "$OUT/.matches" "$OUT/critical-mandatory-resolved.txt.tmp"
test "$(awk 'NF{n++} END{print n+0}' "$OUT/critical-oids.txt")" -ge 21

for f in box-imports.tsv box-delete.tsv origin-delete.tsv worktrees.box.tsv critical-oids.txt origin-url.txt mandatory-prefixes.txt source-repositories.txt; do chmod 0400 "$OUT/$f"; done

# Baseline evidence. These are reads only.
git ls-remote --refs "$origin_url" | sort >"$CROOT/evidence/origin-refs.before.tsv"
find /workspace -maxdepth 1 -mindepth 1 -printf '%y\t%p\n' | sort >"$CROOT/evidence/workspace-paths.before.tsv"
find /workspace -path '*/objects/info/alternates' -type f -print0 | sort -z | xargs -0 -r sha256sum >"$CROOT/evidence/alternates.before.sha256"
git -C /workspace/arnold rev-parse HEAD >"$CROOT/evidence/workspace-arnold.HEAD.before"
git -C /workspace/arnold rev-parse --git-path index | xargs sha256sum >"$CROOT/evidence/workspace-arnold.index.before.sha256"
git -C /workspace/arnold for-each-ref --format='%(objectname)\t%(refname)' | sort >"$CROOT/evidence/workspace-arnold.refs.before.tsv"
git -C /workspace/arnold status --porcelain=v2 -z >"$CROOT/evidence/workspace-arnold.status.before.z"
find /workspace/arnold/.megaplan/resident/schedules -type f -print0 | sort -z | xargs -0 -r sha256sum >"$CROOT/evidence/schedules.before.sha256"
chmod -R go-rwx "$CROOT/manifests" "$CROOT/evidence"
CONTAINER
```

Resolve the Mac-only manifests read-only, then place them in the container. `MAC_TARGET` and `MAC_REPO` come only from the frozen input:

```bash
MAC_TARGET=$(ssh root@159.69.51.216 'tr -d "\r\n" </var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/input/mac-ssh-target.txt')
MAC_REPO=$(ssh root@159.69.51.216 'tr -d "\r\n" </var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/input/mac-repo-path.txt')
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$MAC_TARGET" 'bash -s' -- "$MAC_REPO" < <(
  ssh root@159.69.51.216 'cat /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/input/local-delete-seeds.tsv'
) > /tmp/local-delete.resolved.tsv <<'MAC_SCRIPT'
set -euo pipefail
repo=$1
while IFS=$'\t' read -r prefix branch preserving mode; do
  case "$mode" in d|D) ;; *) exit 1 ;; esac
  oid=$(git -C "$repo" rev-parse --verify "refs/heads/$branch^{commit}")
  case "$oid" in "$prefix"*) ;; *) exit 1 ;; esac
  printf '%s\t%s\t%s\t%s\n' "$oid" "$branch" "$preserving" "$mode"
done
MAC_SCRIPT
```

If the executor cannot support the process-substitution transport above, it must not improvise. Use this equivalent fixed transport:

```bash
ssh root@159.69.51.216 'cp /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/input/local-delete-seeds.tsv /tmp/local-delete-seeds.tsv'
MAC_TARGET=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-ssh-target.txt')
MAC_REPO=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-repo-path.txt')
scp /tmp/local-delete-seeds.tsv "$MAC_TARGET:/tmp/arnold-local-delete-seeds-20260807.tsv"
ssh "$MAC_TARGET" "MAC_REPO='$MAC_REPO' bash -s" > /tmp/local-delete.resolved.tsv <<'MAC'
set -euo pipefail
while IFS=$'\t' read -r prefix branch preserving mode; do
  case "$mode" in d|D) ;; *) exit 1 ;; esac
  oid=$(git -C "$MAC_REPO" rev-parse --verify "refs/heads/$branch^{commit}")
  case "$oid" in "$prefix"*) ;; *) exit 1 ;; esac
  printf '%s\t%s\t%s\t%s\n' "$oid" "$branch" "$preserving" "$mode"
done </tmp/arnold-local-delete-seeds-20260807.tsv
MAC
ssh root@159.69.51.216 'docker cp /tmp/local-delete.resolved.tsv megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/local-delete.tsv; chmod 0600 /tmp/local-delete.resolved.tsv; cp /tmp/local-delete.resolved.tsv /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/manifests/local-delete.tsv'
```

Use exactly one of the two Mac transport blocks, never both. Then combine and freeze worktree rows, copy manifests/evidence to the host, and checksum them:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
test -s "$CROOT/manifests/local-delete.tsv"
cat "$CROOT/manifests/worktrees.box.tsv" >"$CROOT/manifests/worktrees.tsv"
# Mac worktree rows are resolved by TASK-8 before any Mac mutation and appended only after exact OID checks.
chmod 0400 "$CROOT/manifests/local-delete.tsv" "$CROOT/manifests/worktrees.tsv"
cd "$CROOT/manifests"
sha256sum box-imports.tsv box-delete.tsv origin-delete.tsv local-delete.tsv worktrees.tsv critical-oids.txt >MANIFEST-SHA256SUMS
chmod 0400 MANIFEST-SHA256SUMS
'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/. "$HROOT/manifests/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/. "$HROOT/evidence/"; chmod -R go-rwx "$HROOT/manifests" "$HROOT/evidence"'
```

**DONE-CHECK**

- `box-imports.tsv`, `box-delete.tsv`, `origin-delete.tsv`, `local-delete.tsv`, `worktrees.tsv`, and `critical-oids.txt` exist at both recovery roots and are checksum-frozen.
- Every Git hash in them is 40 lowercase hex characters (except literal `-` for a non-Git tree).
- `box-delete.tsv` contains exactly 60 unique literal paths.
- Each of the 21 mandatory prefixes resolves to exactly one full commit; `critical-oids.txt` additionally contains every imported tip.
- Baselines exist for origin refs, `/workspace` top-level paths, alternates, `/workspace/arnold` HEAD/index/refs/status, and the schedule-store file hashes.
- No source ref, index, worktree, alternates file, schedule, pin, or service has been modified.

**PRECONDITION** — TASK-1.

### TASK-3 — CHECKPOINT-SENSECHECK-1: validate inventory completeness and the Phase-A no-touch baseline

**OWNER — CODEX-VALIDATES**

**COMMANDS**

This is a Flash-to-Codex prompt. The installed wrapper requires Codex to read and reference `docs/megaplan-reference-architecture-20260807.md` and `docs/megaplan-fixer-briefing-20260807.md` from either reachable location, anchors against the fixer-briefing invariants (evidence not status prose; no competing fixers; durably move the chain; surface structural issues; edit the approved runtime; push before live), and records either missing doc for the operator.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-1.fragment.md >/dev/null' <<'PROMPT'
Validate the frozen survey before any timer or Git mutation. Independently verify:
1. The exact authoritative box deletion manifest has 60 unique, existing, canonical literal paths; it is not the broader 71-tree survey.
2. Every row is classified, owners/worktrees/alternates form a coherent dependency graph, and deletion-order.tsv orders dependents before owners.
3. All 21 mandatory prefixes resolve uniquely to the recorded full OIDs, and every box-import tip is in critical-oids.txt.
4. The ten protected origin refs (three keep refs, recovery ref name, five human-gated refs, vendor snapshot) are absent from every delete manifest.
5. `/workspace/arnold`, active R7 plus its three worktrees (including 77b76e3a4), the active critique-ledger tree, R5/WBC, R6, every live/canary tree including the 4ed98585 live line, and b38460e4d3 while it owns a live worktree are absent from deletion inputs.
6. The nine R5-R7/vj24 origin WIP refs, six critique-ledger refs, two local critique refs, four named box tips, eight extra active-epic tips, two WBC tips, codex/simple-three-hour-fixer-live-20260727, and fix/resident-hermes-resume-recovery are all explicitly routed to R7 in the integration inventory.
7. Main and editible selections match the judgment, while all backup-only groups are excluded from integration. The five divergent lineages have recovery coverage and no automatic fold/delete action.
8. Baseline evidence is internally consistent and shows no deletion or mutation yet.
Fail on a missing source row, unresolved category, duplicate path/import ref, abbreviated final OID, missing Mac transport/bundle, or any protected target in a delete set.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-1 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-1.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-1.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-1.result.md")" = "CHECKPOINT-SENSECHECK-1: PASS"'
```

**DONE-CHECK** — The last nonblank line of the retained Codex result is exactly `CHECKPOINT-SENSECHECK-1: PASS`.

**PRECONDITION** — TASK-2. On FAIL, halt and report; do not repoint the timer.

### TASK-4 — Snapshot the resident timer and transactionally repoint its service to the `-r6` pin

**OWNER — FLASH**

**COMMANDS**

All operations in this task are host-side. The error trap restores only the exact drop-in being changed. It never removes a stale pin and never stops the existing ad-hoc schedule loop.

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
umask 077
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
UNIT=megaplan-resident-schedule-runner.service
TIMER=megaplan-resident-schedule-runner.timer
DROPIN=/etc/systemd/system/megaplan-resident-schedule-runner.service.d/10-r6-pin.conf
PIN=/usr/local/bin/arnold-resident-schedule-run-once-r6
CONTAINER=megaplan-cloud-agent-resident-only

test -d "$HROOT/.execution-lock"
test -x "$PIN"
grep -Fq 'megaplan-cloud-agent-resident-only' "$PIN"
test "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = true

systemctl cat "$UNIT" >"$HROOT/configs/megaplan-resident-schedule-runner.before.txt"
systemctl show "$UNIT" >"$HROOT/configs/megaplan-resident-schedule-runner.before.properties"
systemctl cat "$TIMER" >"$HROOT/configs/megaplan-resident-schedule-runner.timer.before.txt"
systemctl show "$TIMER" >"$HROOT/configs/megaplan-resident-schedule-runner.timer.before.properties"
install -m 0600 "$PIN" "$HROOT/configs/arnold-resident-schedule-run-once-r6.before"
pgrep -af 'resident.*schedule|schedule.*resident' >"$HROOT/evidence/ad-hoc-schedule-processes.before.txt" || true
chmod 0600 "$HROOT/evidence/ad-hoc-schedule-processes.before.txt"

old_exists=0
if test -e "$DROPIN"; then
  old_exists=1
  install -m 0600 "$DROPIN" "$HROOT/configs/10-r6-pin.conf.preexisting"
fi
rollback() {
  if test "$old_exists" -eq 1; then
    install -D -m 0644 "$HROOT/configs/10-r6-pin.conf.preexisting" "$DROPIN"
  else
    rm -f -- "$DROPIN"
  fi
  systemctl daemon-reload
}
trap rollback ERR

install -d -m 0755 /etc/systemd/system/megaplan-resident-schedule-runner.service.d
tmp="$DROPIN.new.20260807"
printf '%s\n' '[Service]' 'ExecStart=' 'ExecStart=/usr/local/bin/arnold-resident-schedule-run-once-r6' >"$tmp"
chmod 0644 "$tmp"
mv -f -- "$tmp" "$DROPIN"
systemctl daemon-reload

effective=$(systemctl show -p ExecStart --value "$UNIT")
printf '%s\n' "$effective" >"$HROOT/evidence/timer-effective-execstart.after.txt"
test "$(printf '%s' "$effective" | grep -oF '/usr/local/bin/arnold-resident-schedule-run-once-r6' | wc -l)" -eq 1
test "$(printf '%s' "$effective" | grep -oF 'ExecStart=' | wc -l)" -le 1

systemctl reset-failed "$UNIT"
before_invocation=$(systemctl show -p InvocationID --value "$UNIT")
systemctl start "$UNIT"
after_invocation=$(systemctl show -p InvocationID --value "$UNIT")
test -n "$after_invocation"
test "$after_invocation" != "$before_invocation"
test "$(systemctl show -p Result --value "$UNIT")" = success
test "$(systemctl show -p ExecMainStatus --value "$UNIT")" = 0
test "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = true

printf '%s\n' "$after_invocation" >"$HROOT/evidence/r6-invocation-1.id"
systemctl show "$UNIT" >"$HROOT/evidence/megaplan-resident-schedule-runner.after.properties"
journalctl -u "$UNIT" --since '10 minutes ago' --no-pager >"$HROOT/evidence/megaplan-resident-schedule-runner.first-run.journal"
pgrep -af 'resident.*schedule|schedule.*resident' >"$HROOT/evidence/ad-hoc-schedule-processes.after.txt" || true
cmp -s "$HROOT/evidence/ad-hoc-schedule-processes.before.txt" "$HROOT/evidence/ad-hoc-schedule-processes.after.txt" || {
  # A changed listing is evidence for Codex, not permission to stop anything.
  printf 'ad_hoc_process_listing_changed\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$HROOT/action-ledger.tsv"
}

sha256sum "$HROOT/configs"/* >"$HROOT/configs/SHA256SUMS"
chmod 0600 "$HROOT/configs/SHA256SUMS" "$HROOT/evidence"/*
printf 'timer_repointed_r6\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$after_invocation" >>"$HROOT/action-ledger.tsv"
trap - ERR
HOST
```

**DONE-CHECK**

- `systemctl show -p ExecStart --value megaplan-resident-schedule-runner.service` contains exactly one `/usr/local/bin/arnold-resident-schedule-run-once-r6` command.
- The `-r6` pin is executable and names `megaplan-cloud-agent-resident-only`.
- A new nonempty invocation ID has `Result=success` and `ExecMainStatus=0`.
- Before/after unit, timer, pin, process-list, property, and journal evidence exists under the host recovery root.
- No stale pin or ad-hoc loop was removed or stopped.

**PRECONDITION** — TASK-3 PASS.

### TASK-5 — CHECKPOINT-SENSECHECK-2: independently validate timer correction and absence of duplicate execution

**OWNER — CODEX-VALIDATES**

**COMMANDS**

This Codex prompt uses the mandatory intended-design-doc and fixer-invariant anchor installed in TASK-1; missing docs must be named in the report.

```bash
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp "$HROOT/configs/." megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/host-configs/; docker cp "$HROOT/evidence/." megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/host-evidence/'
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-2.fragment.md >/dev/null' <<'PROMPT'
Independently validate the resident timer correction against intended runtime ownership. Inspect the copied unit snapshots, live effective unit, pin content, container state, invocation properties, and journal. Require exactly one effective ExecStart and that it is `/usr/local/bin/arnold-resident-schedule-run-once-r6`; require the pin to target only `megaplan-cloud-agent-resident-only`, not the stopped `megaplan-cloud-agent`. Confirm the first invocation completed successfully, no evidence indicates concurrent duplicate occurrence creation, and the pre-existing ad-hoc schedule loop was not stopped by this task. Confirm no stale pin, Git ref, worktree, alternates file, schedule store, or `/workspace/arnold` state was changed. Fail on ambiguity, a competing runner/fixer, a missing runtime target, or status prose unsupported by journal/properties.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-2 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-2.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-2.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-2.result.md")" = "CHECKPOINT-SENSECHECK-2: PASS"'
```

**DONE-CHECK** — Codex result ends exactly `CHECKPOINT-SENSECHECK-2: PASS`.

**PRECONDITION** — TASK-4. On FAIL, the TASK-4 saved config is the rollback source; halt and do not create/push recovery refs.

### TASK-6 — Build the isolated box recovery anchor, origin-wide bundle, and human-gated bundle

**OWNER — FLASH**

**COMMANDS**

All Git construction occurs in a new bare staging repository inside the container. No recovery ref is added to `/workspace/arnold` or any live repository.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
M=$CROOT/manifests
STAGE=$CROOT/git/box-staging.git
ORIGIN=$(cat "$M/origin-url.txt")
test ! -e "$STAGE"
git -c gc.auto=0 init --bare "$STAGE"
git -C "$STAGE" config gc.auto 0
git -C "$STAGE" config maintenance.auto false
git -C "$STAGE" remote add origin "$ORIGIN"

while IFS=$'\t' read -r source source_ref expected_oid import_ref; do
  git -C "$STAGE" -c gc.auto=0 fetch --no-tags "$source" "$source_ref:$import_ref"
  actual=$(git -C "$STAGE" rev-parse --verify "$import_ref^{commit}")
  test "$actual" = "$expected_oid"
done <"$M/box-imports.tsv"

mapfile -t parents < <(git -C "$STAGE" for-each-ref --format='%(objectname)' refs/heads/import/ | sort -u)
test "${#parents[@]}" -gt 0
args=()
for oid in "${parents[@]}"; do args+=(-p "$oid"); done
empty_tree=$(git -C "$STAGE" hash-object -t tree -w --stdin </dev/null)
anchor=$(
  printf '%s\n' 'Arnold box recovery anchor before branch cleanup 2026-08-07' |
  GIT_AUTHOR_DATE='2026-08-07T00:00:00Z' GIT_COMMITTER_DATE='2026-08-07T00:00:00Z' \
  git -C "$STAGE" -c user.name='Arnold Recovery' -c user.email='arnold-recovery@localhost' commit-tree "$empty_tree" "${args[@]}"
)
git -C "$STAGE" update-ref refs/heads/recovery/box-cleanup-20260807 "$anchor" ''
printf '%s\n' "$anchor" >"$M/recovery-anchor.oid"
chmod 0400 "$M/recovery-anchor.oid"

git -C "$STAGE" bundle create "$CROOT/git/box-cleanup-20260807.bundle" refs/heads/recovery/box-cleanup-20260807
git -C "$STAGE" bundle verify "$CROOT/git/box-cleanup-20260807.bundle" >"$CROOT/evidence/box-bundle-verify.txt" 2>&1

test -z "$(git ls-remote --refs "$ORIGIN" refs/heads/recovery/box-cleanup-20260807)"
git -C "$STAGE" push origin refs/heads/recovery/box-cleanup-20260807:refs/heads/recovery/box-cleanup-20260807
remote_anchor=$(git ls-remote --refs "$ORIGIN" refs/heads/recovery/box-cleanup-20260807 | awk '{print $1}')
test "$remote_anchor" = "$anchor"

MIRROR=$CROOT/git/origin-precleanup.git
test ! -e "$MIRROR"
git -c gc.auto=0 clone --mirror "$ORIGIN" "$MIRROR"
git -C "$MIRROR" config gc.auto 0
git -C "$MIRROR" config maintenance.auto false
git -C "$MIRROR" bundle create "$CROOT/git/origin-precleanup-20260807.bundle" --all
git -C "$MIRROR" bundle verify "$CROOT/git/origin-precleanup-20260807.bundle" >"$CROOT/evidence/origin-bundle-verify.txt" 2>&1

human_refs=(
  refs/heads/local/extension-foundation-completion
  refs/heads/epic/extension-reality-m1-trust-model-truth
  refs/heads/epic/extension-reality-m3-export-readiness-convergence
  refs/heads/megaplan/m3-export-readiness-20260710-0146
  refs/heads/cloud/vibecomfy-trust-correctness-2026-07/sprint-1
  refs/heads/preserved-arnold-megaplan-vendor-pre-m11-20260731
)
for ref in "${human_refs[@]}"; do git -C "$MIRROR" rev-parse --verify "$ref^{commit}" >/dev/null; done
git -C "$MIRROR" bundle create "$CROOT/git/human-gated-and-vendor-20260807.bundle" "${human_refs[@]}"
git -C "$MIRROR" bundle verify "$CROOT/git/human-gated-and-vendor-20260807.bundle" >"$CROOT/evidence/human-gated-bundle-verify.txt" 2>&1

sha256sum "$CROOT/git/box-cleanup-20260807.bundle" "$CROOT/git/origin-precleanup-20260807.bundle" "$CROOT/git/human-gated-and-vendor-20260807.bundle" >"$CROOT/git/SHA256SUMS"
chmod 0400 "$CROOT/git"/*.bundle "$CROOT/git/SHA256SUMS"
CONTAINER
```

Copy the bundles and anchor metadata to the host recovery root without touching live trees:

```bash
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/git/box-cleanup-20260807.bundle "$HROOT/git/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/git/origin-precleanup-20260807.bundle "$HROOT/git/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/git/human-gated-and-vendor-20260807.bundle "$HROOT/git/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/git/SHA256SUMS "$HROOT/git/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/recovery-anchor.oid "$HROOT/manifests/"; chmod 0400 "$HROOT/git"/* "$HROOT/manifests/recovery-anchor.oid"; printf "recovery_anchor_pushed\t%s\t%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(cat "$HROOT/manifests/recovery-anchor.oid")" >>"$HROOT/action-ledger.tsv"'
```

**DONE-CHECK**

- The origin recovery ref equals `recovery-anchor.oid` and was created by a non-force push.
- Every `refs/heads/import/*` tip is a parent of the synthetic anchor; the synthetic anchor itself has not been merged anywhere.
- The box, origin-wide, and human-gated/vendor bundles verify and have SHA-256 entries.
- `44e249df3...` is among the critical/imported objects. No action is required for `4ed98585...` beyond verifying its existing origin reachability.
- No ref was added to a live/source repository.

**PRECONDITION** — TASK-5 PASS.

### TASK-7 — Restore both recovery paths in empty repositories and copy bundles to a second failure domain

**OWNER — FLASH**

**COMMANDS**

Perform two independent empty-repository restores, one from origin and one only from the box bundle:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
M=$CROOT/manifests
ORIGIN=$(cat "$M/origin-url.txt")
ANCHOR=$(cat "$M/recovery-anchor.oid")
for name in origin-restore bundle-restore; do
  repo=$CROOT/verify/$name.git
  test ! -e "$repo"
  git -c gc.auto=0 init --bare "$repo"
  git -C "$repo" config gc.auto 0
  git -C "$repo" config maintenance.auto false
done
git -C "$CROOT/verify/origin-restore.git" fetch --no-tags "$ORIGIN" refs/heads/recovery/box-cleanup-20260807:refs/heads/recovery/box-cleanup-20260807
git -C "$CROOT/verify/bundle-restore.git" fetch --no-tags "$CROOT/git/box-cleanup-20260807.bundle" refs/heads/recovery/box-cleanup-20260807:refs/heads/recovery/box-cleanup-20260807

for repo in "$CROOT/verify/origin-restore.git" "$CROOT/verify/bundle-restore.git"; do
  test "$(git -C "$repo" rev-parse refs/heads/recovery/box-cleanup-20260807)" = "$ANCHOR"
  while IFS= read -r oid; do
    git -C "$repo" cat-file -e "$oid^{commit}"
    git -C "$repo" merge-base --is-ancestor "$oid" "$ANCHOR"
  done <"$M/critical-oids.txt"
  git -C "$repo" fsck --full >"$CROOT/evidence/$(basename "$repo").fsck.txt" 2>&1
done
CONTAINER
```

Copy to the predeclared non-local `rclone` destination, then pull back and verify rather than trusting upload status:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
umask 077
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
DEST=$(tr -d '\r\n' <"$HROOT/input/secondary-rclone-destination.txt")
case "$DEST" in *:*) ;; *) exit 1 ;; esac
case "$DEST" in /*|file:*|local:*) exit 1 ;; esac
REMOTE="$DEST/arnold-branch-cleanup-20260807"
rclone copy "$HROOT/git" "$REMOTE/git" --include '*.bundle' --include 'SHA256SUMS'
restore=$(mktemp -d /var/tmp/arnold-secondary-restore-20260807.XXXXXX)
trap 'rm -rf -- "$restore"' EXIT
rclone copy "$REMOTE/git" "$restore" --include '*.bundle' --include 'SHA256SUMS'
(cd "$restore" && sha256sum -c SHA256SUMS)
rclone check "$HROOT/git" "$REMOTE/git" --one-way --include '*.bundle' --include 'SHA256SUMS'
printf '%s\n' "$REMOTE" >"$HROOT/evidence/secondary-backup-location.txt"
chmod 0600 "$HROOT/evidence/secondary-backup-location.txt"
printf 'secondary_bundle_restore_verified\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$HROOT/action-ledger.tsv"
HOST
```

**DONE-CHECK**

- In both empty bare repositories, every full OID in `critical-oids.txt` exists as a commit and is an ancestor of the exact recovery anchor; both `fsck --full` commands succeed.
- The independently downloaded bundles match `SHA256SUMS` byte-for-byte.
- `rclone check` succeeds against a non-local destination. A second directory on the box is not accepted.

**PRECONDITION** — TASK-6. Any missing OID is an immediate halt-to-human; do not continue to backups or integrations.

### TASK-8 — Back up dirty Git state, schedule/state files, `/workspace/0`, alternates metadata, and Mac state

**OWNER — FLASH**

**COMMANDS**

Back up every box worktree row without printing file contents. Binary patches and untracked archives are mode `0600`:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
M=$CROOT/manifests
B=$CROOT/backups
install -d -m 0700 "$B/worktrees" "$B/non-git" "$B/alternates"

while IFS=$'\t' read -r site owner path oid class dirty_policy; do
  test "$site" = box || continue
  id=$(printf '%s' "$path" | sha256sum | awk '{print $1}')
  out=$B/worktrees/$id
  install -d -m 0700 "$out"
  test "$(git -C "$path" rev-parse HEAD)" = "$oid"
  printf '%s\n' "$path" >"$out/path.txt"
  printf '%s\n' "$owner" >"$out/owner.txt"
  git -C "$path" status --porcelain=v2 -z >"$out/status.porcelain-v2.z"
  git -C "$path" diff --binary >"$out/unstaged.patch"
  git -C "$path" diff --cached --binary >"$out/staged.patch"
  git -C "$path" ls-files --others --exclude-standard -z | tar -C "$path" --null --verbatim-files-from --no-recursion -T - -cpf "$out/untracked.tar"
  find "$path" -xdev -printf '%m\t%U\t%G\t%s\t%T@\t%p\n' >"$out/file-metadata.tsv"
  getfacl -R -p "$path" >"$out/acls.txt" 2>/dev/null || true
  getfattr -R -d -m- "$path" >"$out/xattrs.txt" 2>/dev/null || true
  if test -f "$path/.git"; then install -m 0600 "$path/.git" "$out/git-pointer.txt"; else printf 'git-dir\t%s\n' "$(git -C "$path" rev-parse --git-dir)" >"$out/git-pointer.txt"; fi
  git -C "$owner" worktree list --porcelain >"$out/owner-worktrees.txt"
  sha256sum "$out"/* >"$out/SHA256SUMS"
  chmod -R go-rwx "$out"
done <"$M/worktrees.tsv"

tar --acls --xattrs --numeric-owner -C /workspace/arnold -cpf "$B/non-git/resident-schedules.tar" .megaplan/resident/schedules
test -e /workspace/0
tar --acls --xattrs --numeric-owner -C /workspace -cpf "$B/non-git/workspace-0.tar" 0
find /workspace -path '*/objects/info/alternates' -type f -print0 | tar --null --verbatim-files-from -T - -cpf "$B/alternates/alternates-files.tar"
sha256sum "$B/non-git"/*.tar "$B/alternates/alternates-files.tar" >"$B/SHA256SUMS"
chmod -R go-rwx "$B"
CONTAINER
```

Back up the exact host reference files and unit/pin state with mode `0600`, without displaying contents:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
umask 077
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
OUT=$HROOT/non-git/host-reference-files
install -d -m 0700 "$OUT"
while IFS=$'\t' read -r site path class; do
  test "$site" = host || continue
  test -e "$path"
  id=$(printf '%s' "$path" | sha256sum | awk '{print $1}')
  tar --acls --xattrs --numeric-owner -cpf "$OUT/$id.tar" "$path"
done <"$HROOT/input/reference-files.tsv"
sha256sum "$OUT"/*.tar >"$OUT/SHA256SUMS"
chmod -R go-rwx "$HROOT/non-git"
docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/backups/. "$HROOT/non-git/container-backups/"
find "$HROOT/non-git" -type f -exec chmod 0600 {} +
HOST
```

Resolve and freeze every Mac worktree OID, then back up its status, patches, untracked files, metadata, `.git` pointer, and owner mapping under the Mac recovery root. Copy the resulting encrypted-or-`0600` archive to the host recovery root. This prompt-free worker command still uses only the frozen survey; it dispatches no subagent:

```bash
MAC_TARGET=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-ssh-target.txt')
MAC_REPO=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-repo-path.txt')
MAC_RECOVERY=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-recovery-root.txt')
scp /tmp/local-delete-seeds.tsv "$MAC_TARGET:/tmp/arnold-worktrees-seeds-20260807.tsv"
ssh root@159.69.51.216 'cp /root/arnold-branch-cleanup-20260807-input/worktrees-seeds.tsv /tmp/worktrees-seeds.tsv'
scp /tmp/worktrees-seeds.tsv "$MAC_TARGET:/tmp/arnold-worktrees-seeds-20260807.tsv"
ssh "$MAC_TARGET" "MAC_REPO='$MAC_REPO' MAC_RECOVERY='$MAC_RECOVERY' bash -s" <<'MAC'
set -euo pipefail
umask 077
install -d -m 0700 "$MAC_RECOVERY/worktrees"
: >"$MAC_RECOVERY/worktrees.mac.tsv"
while IFS=$'\t' read -r site owner path prefix class dirty_policy; do
  test "$site" = mac || continue
  test ! -L "$path"
  test "$(realpath "$path")" = "$path"
  oid=$(git -C "$path" rev-parse --verify HEAD^{commit})
  case "$oid" in "$prefix"*) ;; *) exit 1 ;; esac
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$site" "$owner" "$path" "$oid" "$class" "$dirty_policy" >>"$MAC_RECOVERY/worktrees.mac.tsv"
  id=$(printf '%s' "$path" | shasum -a 256 | awk '{print $1}')
  out=$MAC_RECOVERY/worktrees/$id
  install -d -m 0700 "$out"
  git -C "$path" status --porcelain=v2 -z >"$out/status.porcelain-v2.z"
  git -C "$path" diff --binary >"$out/unstaged.patch"
  git -C "$path" diff --cached --binary >"$out/staged.patch"
  git -C "$path" ls-files --others --exclude-standard -z | tar -C "$path" --null -T - -cpf "$out/untracked.tar"
  find "$path" -xdev -exec stat -f '%Lp\t%u\t%g\t%z\t%m\t%N' {} + >"$out/file-metadata.tsv"
  test ! -f "$path/.git" || cp -p "$path/.git" "$out/git-pointer.txt"
  git -C "$owner" worktree list --porcelain >"$out/owner-worktrees.txt"
  chmod -R go-rwx "$out"
done </tmp/arnold-worktrees-seeds-20260807.tsv
cp "$MAC_RECOVERY/worktrees.mac.tsv" /tmp/arnold-worktrees.mac.tsv
tar -C "$MAC_RECOVERY" -cpf "$MAC_RECOVERY/mac-worktree-state-20260807.tar" worktrees worktrees.mac.tsv
shasum -a 256 "$MAC_RECOVERY/mac-worktree-state-20260807.tar" >"$MAC_RECOVERY/mac-worktree-state-20260807.tar.sha256"
chmod 0600 "$MAC_RECOVERY/mac-worktree-state-20260807.tar" "$MAC_RECOVERY/mac-worktree-state-20260807.tar.sha256"
MAC
scp "$MAC_TARGET:/tmp/arnold-worktrees.mac.tsv" /tmp/worktrees.mac.tsv
scp "$MAC_TARGET:$MAC_RECOVERY/mac-worktree-state-20260807.tar" /tmp/mac-worktree-state-20260807.tar
scp "$MAC_TARGET:$MAC_RECOVERY/mac-worktree-state-20260807.tar.sha256" /tmp/mac-worktree-state-20260807.tar.sha256
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; install -m 0600 /tmp/mac-worktree-state-20260807.tar "$HROOT/non-git/"; install -m 0600 /tmp/mac-worktree-state-20260807.tar.sha256 "$HROOT/non-git/"; docker cp /tmp/worktrees.mac.tsv megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/worktrees.mac.tsv'
```

Append the resolved Mac rows, re-freeze `worktrees.tsv`, and rerun Codex checkpoint 1 because the mandatory worktree manifest is now complete:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
cat "$CROOT/manifests/worktrees.box.tsv" "$CROOT/manifests/worktrees.mac.tsv" >"$CROOT/manifests/worktrees.tsv.new"
mv "$CROOT/manifests/worktrees.tsv.new" "$CROOT/manifests/worktrees.tsv"
chmod 0400 "$CROOT/manifests/worktrees.tsv"
cd "$CROOT/manifests"
sha256sum box-imports.tsv box-delete.tsv origin-delete.tsv local-delete.tsv worktrees.tsv critical-oids.txt >MANIFEST-SHA256SUMS
chmod 0400 MANIFEST-SHA256SUMS
'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/worktrees.tsv "$HROOT/manifests/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/MANIFEST-SHA256SUMS "$HROOT/manifests/"'
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-1 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-1.fragment.md'
```

**DONE-CHECK**

- Every declared box and Mac worktree has a verified full HEAD OID and a backup directory/archive containing raw porcelain-v2 status, staged and unstaged binary patches, untracked archive, metadata, and owner mapping.
- The schedule store, `/workspace/0`, exact host reference files, and every alternates file are backed up without altering originals; all sensitive artifacts are mode `0600` under mode-`0700` roots.
- All backup SHA-256 checks verify; the recomputed `worktrees.tsv` is frozen at both roots; repeated `CHECKPOINT-SENSECHECK-1` still ends PASS.

**PRECONDITION** — TASK-7. If a dirty worktree lacks a verified binary/untracked backup, halt.

### TASK-9 — Observe liveness for 70 minutes across live/canary and runtime paths

**OWNER — FLASH**

**COMMANDS**

Create candidate lists mechanically. Protected live paths are recorded but never made deletion candidates. Any positive result for a deletion candidate is a hard stop.

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
awk -F "\t" '\''$1 ~ /-live(\/|$)|-canary(\/|$)|arnold-runtime-50ef856df5|arnold-runtime-7dab2f2645/ {print $1}'\'' "$CROOT/manifests/box-delete.tsv" | sort -u >"$CROOT/manifests/liveness-phase-a-delete-candidates.txt"
awk -F "\t" '\''$1=="box" && $2 ~ /-live(\/|$)|-canary(\/|$)|arnold-runtime-/ {print $2}'\'' "$CROOT/input/protected-paths.tsv" | sort -u >"$CROOT/manifests/liveness-phase-a-protected.txt"
chmod 0400 "$CROOT/manifests/liveness-phase-a-"*.txt
'
ssh root@159.69.51.216 'docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/liveness-phase-a-delete-candidates.txt /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/manifests/; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/liveness-phase-a-protected.txt /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/manifests/'
```

Install and run the fixed host collector. It records counts only and never prints environment/schedule contents:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
umask 077
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
SCRIPT=$HROOT/bin-liveness-scan
cat >"$SCRIPT" <<'SCAN'
#!/usr/bin/env bash
set -euo pipefail
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
CONTAINER=megaplan-cloud-agent-resident-only
OUT=$HROOT/evidence/liveness-phase-a.tsv
printf 'sample\tutc\tclass\tpath\thost_proc\tcontainer_proc\tdocker_mount\thost_ref\tcontainer_ref\n' >"$OUT"
for sample in $(seq 1 70); do
  utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  for class in delete protected; do
    list=$HROOT/manifests/liveness-phase-a-${class}-candidates.txt
    test "$class" != protected || list=$HROOT/manifests/liveness-phase-a-protected.txt
    test -f "$list" || continue
    while IFS= read -r path; do
      test -n "$path" || continue
      host_proc=0
      for link in /proc/[0-9]*/cwd /proc/[0-9]*/exe /proc/[0-9]*/fd/*; do
        target=$(readlink "$link" 2>/dev/null || true)
        case "$target" in "$path"|"$path"/*) host_proc=$((host_proc+1));; esac
      done
      container_proc=$(docker exec "$CONTAINER" bash -lc '\''p=$1; n=0; for l in /proc/[0-9]*/cwd /proc/[0-9]*/exe /proc/[0-9]*/fd/*; do t=$(readlink "$l" 2>/dev/null || true); case "$t" in "$p"|"$p"/*) n=$((n+1));; esac; done; printf "%s" "$n"'\'' _ "$path")
      docker_mount=$(docker inspect "$CONTAINER" | rg -c --fixed-strings -- "$path" || true)
      host_ref=0
      while IFS=$'\t' read -r site ref kind; do
        test "$site" = host || continue
        test -e "$ref" || continue
        hits=$(rg -l --hidden --fixed-strings -- "$path" "$ref" 2>/dev/null | wc -l)
        host_ref=$((host_ref+hits))
      done <"$HROOT/input/reference-files.tsv"
      container_ref=$(docker exec "$CONTAINER" bash -lc '\''p=$1; in=/var/tmp/arnold-branch-cleanup-20260807/input/reference-files.tsv; n=0; while IFS=$'\''\t'\'' read -r site ref kind; do test "$site" = box || continue; test -e "$ref" || continue; h=$(rg -l --hidden --fixed-strings -- "$p" "$ref" 2>/dev/null | wc -l); n=$((n+h)); done <"$in"; printf "%s" "$n"'\'' _ "$path")
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$sample" "$utc" "$class" "$path" "$host_proc" "$container_proc" "$docker_mount" "$host_ref" "$container_ref" >>"$OUT"
    done <"$list"
  done
  test "$sample" -eq 70 || sleep 60
done
chmod 0600 "$OUT"
SCAN
chmod 0700 "$SCRIPT"
systemd-run --unit=arnold-cleanup-liveness-phase-a-20260807 --property=Type=oneshot "$SCRIPT"
HOST
```

Poll without making a judgment; the collector itself samples for more than one hourly interval:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
for attempt in $(seq 1 75); do
  state=$(systemctl show -p ActiveState --value arnold-cleanup-liveness-phase-a-20260807.service)
  test "$state" = failed && exit 1
  test "$state" = inactive && break
  sleep 60
done
test "$(systemctl show -p Result --value arnold-cleanup-liveness-phase-a-20260807.service)" = success
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
test "$(awk -F '\t' 'NR>1 && $3=="delete" && ($5+$6+$7+$8+$9)>0{n++} END{print n+0}' "$HROOT/evidence/liveness-phase-a.tsv")" -eq 0
test "$(awk -F '\t' 'NR>1 && $3=="delete"{seen[$4 FS $1]=1} END{for(k in seen)n++; print n+0}' "$HROOT/evidence/liveness-phase-a.tsv")" -ge 70
printf 'phase_a_liveness_zero\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$HROOT/action-ledger.tsv"
HOST
```

**DONE-CHECK**

- There are 70 one-minute samples for every Phase-A deletion-candidate live/canary/runtime path.
- Every deletion-candidate process-CWD, executable, FD, Docker-mount, systemd/cron/environment/schedule/supervisor/runtime reference count is zero in every sample.
- Protected live paths are recorded separately and remain excluded from all deletion manifests regardless of their observed state.

**PRECONDITION** — TASK-8. Any positive count on a deletion candidate halts the run; it is not reclassified by Flash.

### TASK-10 — CHECKPOINT-SENSECHECK-3: Phase-A recovery/no-deletion gate

**OWNER — CODEX-VALIDATES**

**COMMANDS**

The prompt is wrapped with both intended-design docs and the six fixer invariants; any unreachable doc is explicitly reported.

```bash
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp "$HROOT/evidence/." megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/host-phase-a/; docker cp "$HROOT/manifests/." megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/host-manifests/'
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-3.fragment.md >/dev/null' <<'PROMPT'
Perform the Phase-A exit audit independently. Require all mandatory and imported OIDs to be reachable from the exact origin recovery anchor and restorable from the box bundle in an empty repository. Verify the origin-wide and human-gated bundles, local SHA-256 files, the independently downloaded second copy, and both fsck reports. Verify complete dirty/untracked/metadata backups and mode protection for schedule, state, environment, `/workspace/0`, pin, unit, and alternates metadata. Verify 70 minutes of zero liveness for every deletion candidate while protected live trees remain excluded. Re-read live timer state and require the r6 pin and resident-only container. Compare baseline evidence to current source refs/indices/worktree paths/alternates/schedules and prove that Phase A caused no tree/ref/schedule/stale-pin/alternates/GC deletion or mutation except the authorized timer drop-in and new origin recovery ref. Specifically prove `/workspace/arnold`, R7/R5/R6, WBC, critique-ledger, all live trees, and b38460e4d3 were untouched. Fail if 44e249df3 is absent; separately verify 4ed98585 is already origin-backed rather than demanding it as a box-only import.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-3 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-3.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-3.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-3.result.md")" = "CHECKPOINT-SENSECHECK-3: PASS"'
```

**DONE-CHECK** — Codex result ends exactly `CHECKPOINT-SENSECHECK-3: PASS`, establishing all Phase-A exit criteria and no deletion.

**PRECONDITION** — TASK-9. On FAIL, halt. Phase B may not start.

---

## Phase B — integrate selected work, migrate schedules, and remove the `2bd0b2d34` alternate dependency

### TASK-11 — Create three disposable integration clones and resolve every selected source tip

**OWNER — FLASH**

**COMMANDS**

`source_locator` values in the frozen integration inputs must have exactly one of these forms: `origin:refs/heads/<name>`, `mac:refs/heads/<name>`, or `recovery:<full-or-survey-prefix>`. Any other form halts. The resolver writes full OIDs; Flash never selects a tip.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
M=$CROOT/manifests
ORIGIN=$(cat "$M/origin-url.txt")
BASE=$CROOT/integration

for name in r7 main editible; do test ! -e "$BASE/$name"; done
git -c gc.auto=0 clone --no-tags "$ORIGIN" "$BASE/r7"
git -c gc.auto=0 clone --no-tags "$ORIGIN" "$BASE/main"
git -c gc.auto=0 clone --no-tags "$ORIGIN" "$BASE/editible"

for repo in "$BASE/r7" "$BASE/main" "$BASE/editible"; do
  git -C "$repo" config gc.auto 0
  git -C "$repo" config maintenance.auto false
  git -C "$repo" config user.name 'Arnold Cleanup Integration'
  git -C "$repo" config user.email 'arnold-cleanup@localhost'
  git -C "$repo" fetch --no-tags origin refs/heads/recovery/box-cleanup-20260807:refs/remotes/origin/recovery/box-cleanup-20260807
  git -C "$repo" fetch --no-tags "$CROOT/input/mac-precleanup-20260807.bundle" 'refs/heads/*:refs/remotes/mac/*'
done

git -C "$BASE/r7" switch -c integrate/r7-cleanup-20260807 origin/fix/r7-fresh-child-launch-20260805
git -C "$BASE/main" switch -c integrate/main-cleanup-20260807 origin/main
git -C "$BASE/editible" switch -c integrate/editible-install-cleanup-20260807 origin/editible-install

resolve_file() {
  repo=$1 input=$2 output=$3
  : >"$output.tmp"
  while IFS=$'\t' read -r batch order label locator prefix operation equivalent; do
    case "$batch:$order" in *[!0-9:]*|:|*:) exit 1 ;; esac
    case "$operation" in merge|cherry-pick|patch-equivalent) ;; *) exit 1 ;; esac
    case "$locator" in
      origin:refs/heads/*)
        ref=${locator#origin:refs/heads/}
        oid=$(git -C "$repo" rev-parse --verify "refs/remotes/origin/$ref^{commit}")
        ;;
      mac:refs/heads/*)
        ref=${locator#mac:refs/heads/}
        oid=$(git -C "$repo" rev-parse --verify "refs/remotes/mac/$ref^{commit}")
        ;;
      recovery:*)
        token=${locator#recovery:}
        oid=$(git -C "$repo" rev-parse --verify "$token^{commit}")
        git -C "$repo" merge-base --is-ancestor "$oid" refs/remotes/origin/recovery/box-cleanup-20260807
        ;;
      *) exit 1 ;;
    esac
    case "$oid" in "$prefix"*) ;; *) exit 1 ;; esac
    test "${#oid}" -eq 40
    if test "$operation" = patch-equivalent; then
      test "$equivalent" != -
      test "${#equivalent}" -eq 40
      git -C "$repo" cat-file -e "$equivalent^{commit}"
    else
      test "$equivalent" = -
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$batch" "$order" "$label" "$locator" "$oid" "$operation" "$equivalent" >>"$output.tmp"
  done <"$input"
  sort -t $'\t' -k1,1n -k2,2n "$output.tmp" >"$output"
  rm -f "$output.tmp"
  chmod 0400 "$output"
}

resolve_file "$BASE/r7" "$CROOT/input/integration-r7-seeds.tsv" "$M/integration-r7.tsv"
resolve_file "$BASE/main" "$CROOT/input/integration-main-seeds.tsv" "$M/integration-main.tsv"
resolve_file "$BASE/editible" "$CROOT/input/integration-editible-seeds.tsv" "$M/integration-editible.tsv"

grep -q $'\t20cb1a8eb' <(cut -f1-5 "$M/integration-main.tsv")
grep -q $'\t9bf8e0556' <(cut -f1-5 "$M/integration-main.tsv")
grep -q $'\t26fecb4d2' <(cut -f1-5 "$M/integration-main.tsv")
grep -q $'\t480b607653' <(cut -f1-5 "$M/integration-editible.tsv")
sha256sum "$M/integration-r7.tsv" "$M/integration-main.tsv" "$M/integration-editible.tsv" >"$M/INTEGRATION-SHA256SUMS"
chmod 0400 "$M/INTEGRATION-SHA256SUMS"
CONTAINER
```

Preserve the exact Mac-main tip on origin before any cherry-pick. This is a normal create-only push, never a force push:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
repo=$CROOT/integration/main
oid=$(git -C "$repo" rev-parse --verify 26fecb4d2^{commit})
test -z "$(git -C "$repo" ls-remote --refs origin refs/heads/recovery/mac-main-pre-realign-20260807)"
git -C "$repo" push origin "$oid:refs/heads/recovery/mac-main-pre-realign-20260807"
test "$(git -C "$repo" ls-remote --refs origin refs/heads/recovery/mac-main-pre-realign-20260807 | awk '\''{print $1}'\'')" = "$oid"
printf "%s\n" "$oid" >/var/tmp/arnold-branch-cleanup-20260807/manifests/mac-main-recovery.oid
chmod 0400 /var/tmp/arnold-branch-cleanup-20260807/manifests/mac-main-recovery.oid
'
```

**DONE-CHECK**

- The three disposable clones are based exactly on the current three origin keep refs and have automatic GC/maintenance disabled.
- Every selected integration source resolves to one full OID from origin, the Mac bundle, or the box recovery anchor.
- The three Mac-main commits occur in the main manifest, `480b607653...` occurs in the deploy manifest, and the exact `26fecb4d2...` tip is on `refs/heads/recovery/mac-main-pre-realign-20260807`.
- No live checkout was used or reset.

**PRECONDITION** — TASK-10 PASS.

### TASK-12 — Apply the R7 integration batches mechanically and test after each batch

**OWNER — FLASH**

**COMMANDS**

The following fixed runner is used separately for each destination. A conflict aborts the in-progress operation and exits; Flash must not resolve it.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/bin/apply-integration-manifest >/dev/null; chmod 0700 /var/tmp/arnold-branch-cleanup-20260807/bin/apply-integration-manifest' <<'RUNNER'
#!/usr/bin/env bash
set -euo pipefail
repo=${1:?repo}
manifest=${2:?manifest}
name=${3:?name}
evidence=/var/tmp/arnold-branch-cleanup-20260807/evidence
ledger="$evidence/integration-$name.tsv"
: >"$ledger"
current_batch=
run_tests() {
  batch=$1
  (cd "$repo" && python -m pytest -q) >"$evidence/tests-$name-batch-$batch.log" 2>&1
}
abort_op() {
  git -C "$repo" merge --abort >/dev/null 2>&1 || true
  git -C "$repo" cherry-pick --abort >/dev/null 2>&1 || true
}
trap abort_op ERR
while IFS=$'\t' read -r batch order label locator oid operation equivalent; do
  if test -n "$current_batch" && test "$batch" != "$current_batch"; then run_tests "$current_batch"; fi
  current_batch=$batch
  before=$(git -C "$repo" rev-parse HEAD)
  case "$operation" in
    merge)
      if git -C "$repo" merge-base --is-ancestor "$oid" HEAD; then
        result=already-ancestor
      else
        git -C "$repo" merge --no-ff --no-edit "$oid"
        result=merged
      fi
      ;;
    cherry-pick)
      if git -C "$repo" merge-base --is-ancestor "$oid" HEAD; then
        result=already-ancestor
      else
        git -C "$repo" cherry-pick "$oid"
        result=cherry-picked
      fi
      ;;
    patch-equivalent)
      source_patch=$(git -C "$repo" show --pretty=format: --no-ext-diff "$oid" | git patch-id --stable | awk '{print $1}')
      dest_patch=$(git -C "$repo" show --pretty=format: --no-ext-diff "$equivalent" | git patch-id --stable | awk '{print $1}')
      test -n "$source_patch"
      test "$source_patch" = "$dest_patch"
      grep -Fqx "$oid"$'\t'"$equivalent"$'\t'"$source_patch"$'\t'"$(case "$name" in r7) printf refs/heads/fix/r7-fresh-child-launch-20260805;; main) printf refs/heads/main;; editible) printf refs/heads/editible-install;; esac)" /var/tmp/arnold-branch-cleanup-20260807/input/patch-equivalences.tsv
      result=patch-equivalent
      ;;
  esac
  after=$(git -C "$repo" rev-parse HEAD)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$batch" "$order" "$oid" "$operation" "$result" "$before" "$after" >>"$ledger"
done <"$manifest"
test -z "$current_batch" || run_tests "$current_batch"
trap - ERR
RUNNER

docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
"$CROOT/bin/apply-integration-manifest" "$CROOT/integration/r7" "$CROOT/manifests/integration-r7.tsv" r7
git -C "$CROOT/integration/r7" status --porcelain=v1 | test "$(wc -l)" -eq 0
'
```

**DONE-CHECK**

- Every R7 row has a ledger result of `merged`, `cherry-picked`, `already-ancestor`, or checksum-verified `patch-equivalent`.
- Every logical batch has a passing `python -m pytest -q` log.
- The candidate is clean and contains the selected nine R5-R7/vj24 WIP lines, six critique-ledger lines, two local critique lines, four named box tips, eight active-epic worktree tips, both WBC tips, `codex/simple-three-hour-fixer-live-20260727`, and `fix/resident-hermes-resume-recovery`, as listed—not inferred.

**PRECONDITION** — TASK-11. Any conflict, empty patch ID, failed test, or missing row halts and is handed to a human; Flash does not edit conflicts.

### TASK-13 — Apply Mac-main and selected general-code batches to the disposable main clone

**OWNER — FLASH**

**COMMANDS**

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
# Codex will verify the first genuine Mac commits are ordered oldest-to-newest as 20cb1a8eb, 9bf8e0556, 26fecb4d2.
"$CROOT/bin/apply-integration-manifest" "$CROOT/integration/main" "$CROOT/manifests/integration-main.tsv" main
test -z "$(git -C "$CROOT/integration/main" status --porcelain=v1)"
# Data/state/secrets are forbidden in integration commits.
git -C "$CROOT/integration/main" diff --name-only origin/main...HEAD >"$CROOT/evidence/main-changed-paths.txt"
if rg -n '\''(^|/)(\.cloud-hot-env|credentials?|resident/state|resident/schedules)(/|$)|(^|/)(occurrences?|runtime-state)(/|$)'\'' "$CROOT/evidence/main-changed-paths.txt"; then exit 1; fi
'
```

**DONE-CHECK**

- The exact three Mac-main commits were processed oldest-to-newest.
- All 11 named non-vj24 Mac unique branches, all 56 remaining true-unique Mac branches, `44e249df3...`, `972e78a1d...`, selected resident/listener fixes, seven notable box clones, the seven named pre-epic WIP branches, and the three selected small-WIP fixes are represented by literal manifest rows and have successful ledger outcomes.
- The two Mac vj24 branches occur only in the R7 manifest.
- The main candidate is clean, tests passed after every batch, and no schedule/state/credential/generated-runtime path was introduced.

**PRECONDITION** — TASK-12. Any conflict or test failure halts.

### TASK-14 — Apply only deploy-mirror changes to the disposable `editible-install` clone

**OWNER — FLASH**

**COMMANDS**

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
"$CROOT/bin/apply-integration-manifest" "$CROOT/integration/editible" "$CROOT/manifests/integration-editible.tsv" editible
test -z "$(git -C "$CROOT/integration/editible" status --porcelain=v1)"
git -C "$CROOT/integration/editible" diff --name-only origin/editible-install...HEAD >"$CROOT/evidence/editible-changed-paths.txt"
grep -q '^' "$CROOT/evidence/editible-changed-paths.txt"
if rg -n '\''(^|/)(\.cloud-hot-env|credentials?|resident/state|resident/schedules)(/|$)|(^|/)(occurrences?|runtime-state|generated-runtime)(/|$)'\'' "$CROOT/evidence/editible-changed-paths.txt"; then exit 1; fi
git -C "$CROOT/integration/editible" cat-file -e 480b607653^{commit}
'
```

**DONE-CHECK**

- The `480b607653...` deploy-specific lineage and the deploy result of selected main resident/runtime changes have manifest/ledger coverage.
- Every batch passes the full test command.
- No data-store file, resident state, schedule, credential, secret, occurrence, or generated runtime artifact is in the candidate diff.

**PRECONDITION** — TASK-13. Any conflict or test failure halts.

### TASK-15 — CHECKPOINT-SENSECHECK-4: validate all three integration candidates before any keep-line push

**OWNER — CODEX-VALIDATES**

**COMMANDS**

The mandatory intended-design documents and all fixer invariants are injected by the wrapper. Codex must treat current-runtime contracts and the approved-runtime/push-before-live invariant as the review standard.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-4.fragment.md >/dev/null' <<'PROMPT'
Review the three disposable candidates independently before push. Recompute every ancestry result and stable patch-ID mapping; do not trust the integration ledger alone. Confirm each source is routed exactly as the judgment requires, maximal tips were used instead of blindly merging redundant ancestors, and the synthetic recovery anchor itself is not merged. Confirm the Mac-main three-commit order and exact recovery ref. Confirm backup-only operational/checkpoint branches are absent. Inspect candidate diffs for secrets, schedules, resident/data state, generated runtime artifacts, unintended cross-project code, and violations of current runtime contracts. Run or inspect the full tests for every batch and run focused tests where structural risk demands it. Confirm all work happened in `/var/tmp/.../integration/*`, never `/workspace/arnold` or a live checkout, and there was no force push. Fail on any unresolved conflict, unproven patch equivalence, missing named lineage, duplicate patch, forbidden path, failing test, or intended-design divergence.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-4 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-4.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-4.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-4.result.md")" = "CHECKPOINT-SENSECHECK-4: PASS"'
```

**DONE-CHECK** — Codex result ends exactly `CHECKPOINT-SENSECHECK-4: PASS`.

**PRECONDITION** — TASK-14. On FAIL, halt; do not push an integration or keep branch.

### TASK-16 — Publish integration branches, fast-forward the three keep refs, and realign Mac `main`

**OWNER — FLASH**

**COMMANDS**

Create the three integration branches on origin with ordinary pushes. Existing refs cause a halt rather than an overwrite:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
for spec in \
  'r7 refs/heads/integrate/r7-cleanup-20260807 refs/heads/fix/r7-fresh-child-launch-20260805' \
  'main refs/heads/integrate/main-cleanup-20260807 refs/heads/main' \
  'editible refs/heads/integrate/editible-install-cleanup-20260807 refs/heads/editible-install'
do
  set -- $spec
  name=$1 integration_ref=$2 keep_ref=$3
  repo=$CROOT/integration/$name
  test -z "$(git -C "$repo" ls-remote --refs origin "$integration_ref")"
  git -C "$repo" push origin "HEAD:$integration_ref"
  git -C "$repo" fetch --no-tags origin "$keep_ref:refs/remotes/origin/prepush-$name"
  git -C "$repo" merge-base --is-ancestor "refs/remotes/origin/prepush-$name" HEAD
  # This is a normal fast-forward push. It contains no --force option.
  git -C "$repo" push origin "HEAD:$keep_ref"
  test "$(git -C "$repo" ls-remote --refs origin "$keep_ref" | awk '{print $1}')" = "$(git -C "$repo" rev-parse HEAD)"
done
CONTAINER
```

If any normal keep-ref push is rejected by branch protection, halt and report the already-pushed integration ref so a human can merge it through the protected PR path. Do not retry with any force option.

After `origin/main` is updated, realign Mac `main` only if it is clean and still at the frozen pre-realign tip. Local `editible-install` is never reset or deleted:

```bash
MAC_TARGET=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-ssh-target.txt')
MAC_REPO=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-repo-path.txt')
MAC_OLD=$(docker exec megaplan-cloud-agent-resident-only bash -lc 'cat /var/tmp/arnold-branch-cleanup-20260807/manifests/mac-main-recovery.oid')
ssh "$MAC_TARGET" "MAC_REPO='$MAC_REPO' MAC_OLD='$MAC_OLD' bash -s" <<'MAC'
set -euo pipefail
git -C "$MAC_REPO" fetch origin
git -C "$MAC_REPO" switch main
test -z "$(git -C "$MAC_REPO" status --porcelain=v1)"
test "$(git -C "$MAC_REPO" rev-parse HEAD)" = "$MAC_OLD"
test "$(git -C "$MAC_REPO" rev-parse refs/remotes/origin/recovery/mac-main-pre-realign-20260807)" = "$MAC_OLD"
git -C "$MAC_REPO" reset --keep origin/main
test "$(git -C "$MAC_REPO" rev-parse HEAD)" = "$(git -C "$MAC_REPO" rev-parse origin/main)"
git -C "$MAC_REPO" show-ref --verify --quiet refs/heads/editible-install
MAC
```

Record the post-integration keep-ref OIDs; Phase C must not change them:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
ORIGIN=$(cat "$CROOT/manifests/origin-url.txt")
git ls-remote --refs "$ORIGIN" refs/heads/main refs/heads/editible-install refs/heads/fix/r7-fresh-child-launch-20260805 refs/heads/recovery/box-cleanup-20260807 refs/heads/recovery/mac-main-pre-realign-20260807 | sort >"$CROOT/evidence/keep-refs.after-integration.tsv"
'
```

**DONE-CHECK**

- Three origin integration refs exist and equal the tested candidate tips.
- Each keep ref equals its candidate tip through a normal fast-forward push or a human-completed protected PR; no force update occurred.
- Mac `main` equals `origin/main`, its old exact tip remains on the Mac recovery ref, its worktree was clean, and local `editible-install` still exists.
- No live box checkout was reset or switched.

**PRECONDITION** — TASK-15 PASS.

### TASK-17 — CHECKPOINT-SENSECHECK-5: verify landed keep lines from fresh clones

**OWNER — CODEX-VALIDATES**

**COMMANDS**

First create fresh read-only verification clones and run tests:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
ORIGIN=$(cat "$CROOT/manifests/origin-url.txt")
for name in r7 main editible; do
  path=$CROOT/verify/landed-$name
  test ! -e "$path"
  git -c gc.auto=0 clone --no-tags "$ORIGIN" "$path"
  git -C "$path" config gc.auto 0
  git -C "$path" config maintenance.auto false
done
git -C "$CROOT/verify/landed-r7" switch --detach origin/fix/r7-fresh-child-launch-20260805
git -C "$CROOT/verify/landed-main" switch --detach origin/main
git -C "$CROOT/verify/landed-editible" switch --detach origin/editible-install
for name in r7 main editible; do
  (cd "$CROOT/verify/landed-$name" && python -m pytest -q) >"$CROOT/evidence/fresh-$name-tests.log" 2>&1
done
git -C "$CROOT/verify/landed-main" cat-file -e 44e249df3^{commit}
git -C "$CROOT/verify/landed-main" cat-file -e 972e78a1d^{commit}
git -C "$CROOT/verify/landed-main" cat-file -e 20cb1a8eb^{commit}
git -C "$CROOT/verify/landed-main" cat-file -e 9bf8e0556^{commit}
git -C "$CROOT/verify/landed-main" cat-file -e 26fecb4d2^{commit}
git -C "$CROOT/verify/landed-editible" cat-file -e 480b607653^{commit}
CONTAINER
```

Then invoke Codex with the mandatory intended-design and fixer-invariant anchor:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-5.fragment.md >/dev/null' <<'PROMPT'
Independently audit the three landed keep refs from the fresh clones. Require all tests green. For every selected source tip, prove it is an ancestor of its designated keep ref or recompute and verify its explicit stable patch-ID mapping. Require the Mac-main commits and selected general fixes on main, 480b607653 deploy changes on editible-install, and all active-epic selections on R7. Verify backup-only histories and all state/secret artifacts were not merged. Verify the origin recovery ref and Mac recovery ref retain their exact OIDs. Verify all keep-ref updates were normal fast-forwards/protected PR merges, with no force push, and no live checkout was altered. Recheck intended architecture invariants rather than treating green tests alone as sufficient.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-5 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-5.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-5.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-5.result.md")" = "CHECKPOINT-SENSECHECK-5: PASS"'
```

**DONE-CHECK** — Fresh tests pass and Codex result ends `CHECKPOINT-SENSECHECK-5: PASS`.

**PRECONDITION** — TASK-16. On FAIL, halt before schedule mutation.

### TASK-18 — Transactionally migrate the resident schedule store through the supported admin CLI

**OWNER — FLASH**

**COMMANDS**

The frozen schedule manifest supplies exact IDs, revisions, patch files, new revisions, and targets. The admin binary and lock path are frozen literal absolute paths. No `sed`, raw JSON rewrite, or occurrence-history reinterpretation is allowed.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
ADMIN=$(tr -d '\r\n' <"$CROOT/input/schedule-admin-path.txt")
LOCK=$(tr -d '\r\n' <"$CROOT/input/schedule-lock-path.txt")
STORE=/workspace/arnold/.megaplan/resident/schedules
BACKUP=$CROOT/backups/non-git/resident-schedules.tar
test -x "$ADMIN"
case "$LOCK" in /*) ;; *) exit 1 ;; esac
test -f "$BACKUP"

rollback_store() {
  restore=$CROOT/backups/non-git/schedule-rollback
  rm -rf -- "$restore"
  install -d -m 0700 "$restore"
  tar -C "$restore" -xpf "$BACKUP"
  test -d "$restore/.megaplan/resident/schedules"
  old=$STORE.failed-20260807
  test ! -e "$old"
  mv "$STORE" "$old"
  mv "$restore/.megaplan/resident/schedules" "$STORE"
}

exec 9>"$LOCK"
flock -x 9
trap rollback_store ERR
install -d -m 0700 "$CROOT/evidence/schedule-receipts"
while IFS=$'\t' read -r id revision operation patch new_revision target; do
  case "$id" in sched_*) ;; *) exit 1 ;; esac
  case "$revision:$new_revision" in *[!0-9:]*|:|*:) exit 1 ;; esac
  test -f "$CROOT/input/$patch"
  case "$operation" in
    update)
      "$ADMIN" schedule update "$id" --if-revision "$revision" --patch "$CROOT/input/$patch" --json >"$CROOT/evidence/schedule-receipts/$id.json"
      ;;
    archive)
      "$ADMIN" schedule archive "$id" --if-revision "$revision" --patch "$CROOT/input/$patch" --json >"$CROOT/evidence/schedule-receipts/$id.json"
      ;;
    tombstone)
      "$ADMIN" schedule tombstone "$id" --if-revision "$revision" --patch "$CROOT/input/$patch" --json >"$CROOT/evidence/schedule-receipts/$id.json"
      ;;
    *) exit 1 ;;
  esac
  test "$(jq -r '.revision' "$CROOT/evidence/schedule-receipts/$id.json")" = "$new_revision"
done <"$CROOT/input/schedule-migrations.tsv"

for old in arnold-bc0c600c arnold-74b4e6b9 arnold-6ce6d4eb; do
  out=$CROOT/evidence/schedule-old-root-$old.matches
  set +e
  rg -n --fixed-strings -- "$old" "$STORE" >"$out"
  rc=$?
  set -e
  test "$rc" -eq 1
  test ! -s "$out"
done

verify_cmd=$(tr -d '\r\n' <"$CROOT/input/schedule-verification-command.txt")
test -n "$verify_cmd"
bash -lc "$verify_cmd" >"$CROOT/evidence/schedule-verification.after.json"
jq -e '.schedules[] | select(.id=="sched_superfixer_hourly_v2") | .state=="active"' "$CROOT/evidence/schedule-verification.after.json" >/dev/null
find "$STORE" -type f -print0 | sort -z | xargs -0 -r sha256sum >"$CROOT/evidence/schedules.after-migration.sha256"
trap - ERR
flock -u 9
CONTAINER
```

**DONE-CHECK**

- Every schedule command returned its exact expected new revision while holding the frozen schedule lock.
- The three exact `rg -n --fixed-strings` searches have exit code 1 and empty evidence files.
- `sched_superfixer_hourly_v2` is still active and points to the manifest-declared active R7/origin-backed target.
- No blanket text edit occurred; inactive schedules were changed only by supported archive/tombstone operations.

**PRECONDITION** — TASK-17 PASS. Any revision mismatch, CLI/schema error, remaining match, or rollback activation halts; retain all referenced trees.

### TASK-19 — CHECKPOINT-SENSECHECK-6: validate transactional schedule migration and zero old-root references

**OWNER — CODEX-VALIDATES**

**COMMANDS**

This prompt explicitly carries the intended-design/fixer-invariant standard through the wrapper.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-6.fragment.md >/dev/null' <<'PROMPT'
Independently validate the schedule migration. Read the intended-design schedule/control-plane invariants. Verify the pre-migration mode-preserving snapshot and lock, supported admin receipts, exact revision transitions, runnable definitions and heads, and active state/target of sched_superfixer_hourly_v2. Search the entire store yourself for `arnold-bc0c600c`, `arnold-74b4e6b9`, and `arnold-6ce6d4eb`; all searches must be empty, including immutable/history records. Check for duplicate occurrence creation and competing schedule runners. Confirm no schedule/state/credential content was committed or printed and no referenced tree has yet been removed. Fail if any old reference remains, any record was edited outside the supported transaction, or rollback state exists.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-6 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-6.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-6.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-6.result.md")" = "CHECKPOINT-SENSECHECK-6: PASS"'
```

**DONE-CHECK** — Codex result ends `CHECKPOINT-SENSECHECK-6: PASS`.

**PRECONDITION** — TASK-18. On FAIL, halt; no old schedule-root tree may be deleted.

### TASK-20 — Make `/workspace/arnold-2bd0b2d345022c8797f8e63998b93a08a8ae5954` self-contained

**OWNER — FLASH**

**COMMANDS**

This is the sole permitted repack in the entire plan. It first creates preservation refs for every valid Git object token named by the checksummed cutover artifacts, backs up the alternates file, repacks without `--local`, disables the recognized alternates filename, and runs full checks. Any failure restores the exact alternates file immediately and retains `9f9982c855`.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
REPO=/workspace/arnold-2bd0b2d345022c8797f8e63998b93a08a8ae5954
ALT=$(git -C "$REPO" rev-parse --git-path objects/info/alternates)
ALT_BACKUP=$CROOT/backups/2bd-alternates
DISABLED=${ALT}.disabled-arnold-cleanup-20260807
test -f "$ALT"
test ! -e "$DISABLED"
install -d -m 0700 "$ALT_BACKUP"
install -m 0600 "$ALT" "$ALT_BACKUP/alternates"
sha256sum "$ALT_BACKUP/alternates" >"$ALT_BACKUP/SHA256SUMS"

: >"$CROOT/manifests/2bd-cutover-objects.tsv"
index=0
while IFS=$'\t' read -r artifact expected_sha; do
  case "$artifact" in /*) path=$artifact ;; *) path=$REPO/$artifact ;; esac
  test -f "$path"
  test "$(sha256sum "$path" | awk '{print $1}')" = "$expected_sha"
  while IFS= read -r token; do
    oid=$(git -C "$REPO" rev-parse --verify "$token^{object}" 2>/dev/null || true)
    test -n "$oid" || continue
    index=$((index+1))
    ref=$(printf 'refs/cleanup/cutover-object-%04d' "$index")
    git -C "$REPO" update-ref "$ref" "$oid" ''
    printf '%s\t%s\t%s\n' "$artifact" "$oid" "$ref" >>"$CROOT/manifests/2bd-cutover-objects.tsv"
  done < <(rg -o --no-filename '[0-9a-f]{7,40}' "$path" | sort -u)
done <"$CROOT/input/cutover-artifacts.tsv"
test -s "$CROOT/manifests/2bd-cutover-objects.tsv"
sort -u "$CROOT/manifests/2bd-cutover-objects.tsv" -o "$CROOT/manifests/2bd-cutover-objects.tsv"

git -C "$REPO" repack -a -d
mv -- "$ALT" "$DISABLED"
restore_alt() { test -e "$ALT" || mv -- "$DISABLED" "$ALT"; }
trap restore_alt ERR

git -C "$REPO" fsck --full >"$CROOT/evidence/2bd-fsck-without-alternates.txt" 2>&1
git -C "$REPO" rev-list --objects --all >"$CROOT/evidence/2bd-objects.txt"
while IFS=$'\t' read -r artifact oid ref; do
  test "$(git -C "$REPO" rev-parse "$ref")" = "$oid"
  git -C "$REPO" cat-file -e "$oid^{object}"
done <"$CROOT/manifests/2bd-cutover-objects.tsv"
test ! -e "$ALT"
test -f "$DISABLED"

git -C "$REPO" bundle create "$CROOT/git/2bd-self-contained-20260807.bundle" --all
git -C "$REPO" bundle verify "$CROOT/git/2bd-self-contained-20260807.bundle" >"$CROOT/evidence/2bd-bundle-verify.txt" 2>&1
sha256sum "$CROOT/git/2bd-self-contained-20260807.bundle" >"$CROOT/git/2bd-self-contained-20260807.bundle.sha256"
trap - ERR
CONTAINER
```

Restore the new bundle in an empty repository while the alternates file remains disabled:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
repo=$CROOT/verify/2bd-restore.git
test ! -e "$repo"
git -c gc.auto=0 init --bare "$repo"
git -C "$repo" fetch --no-tags "$CROOT/git/2bd-self-contained-20260807.bundle" '\''refs/*:refs/*'\''
git -C "$repo" fsck --full >"$CROOT/evidence/2bd-empty-restore.fsck.txt" 2>&1
while IFS=$'\t' read -r artifact oid ref; do git -C "$repo" cat-file -e "$oid^{object}"; done <"$CROOT/manifests/2bd-cutover-objects.tsv"
'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/git/2bd-self-contained-20260807.bundle "$HROOT/git/"; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/git/2bd-self-contained-20260807.bundle.sha256 "$HROOT/git/"; chmod 0400 "$HROOT/git/2bd-self-contained-20260807.bundle"*'
```

**DONE-CHECK**

- Every valid Git object named by every checksummed cutover artifact has a recorded preservation ref and resolves with the recognized alternates file absent.
- `git fsck --full`, `rev-list --objects --all`, bundle verify, and empty-repository restore all succeed.
- The original alternates file is backed up mode `0600`; the active recognized name is absent and the exact disabled copy exists.
- `9f9982c855` and its worktree still exist; this task does not delete them.

**PRECONDITION** — TASK-19 PASS. On any failure, restore `alternates.disabled-arnold-cleanup-20260807` to `objects/info/alternates`, halt, and keep `9f9982c855`.

### TASK-21 — CHECKPOINT-SENSECHECK-7: Phase-B integration/dependency exit gate

**OWNER — CODEX-VALIDATES**

**COMMANDS**

The wrapper forces intended-design-doc reading/reference and all six fixer invariants.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-7.fragment.md >/dev/null' <<'PROMPT'
Perform the complete Phase-B exit audit. From fresh clones, prove every selected source tip is an ancestor of its intended keep line or has a recomputed stable patch-ID mapping plus recovery proof; require the Mac-main commits, 44e249df3, 972e78a1d, selected general fixes, R7/WBC/critique tips, and 480b607653 deploy work. Verify tests and forbidden-data exclusions. Independently search the whole schedule store for all three old roots and require zero matches plus an active, nonduplicating sched_superfixer_hourly_v2. With the 2bd alternates filename still disabled, run fsck, resolve all cutover refs, compare object inventory, and restore its bundle in an empty repository. Verify every mandatory box OID remains on the origin recovery ref and box bundle. Confirm no five human-gated ref was merged/deleted, no live checkout/container was changed, no force push occurred, and no GC/maintenance/prune ran. Evaluate against intended architecture and the fixer invariants, not merely status or test prose.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-7 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-7.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-7.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-7.result.md")" = "CHECKPOINT-SENSECHECK-7: PASS"'
```

**DONE-CHECK** — Codex result ends `CHECKPOINT-SENSECHECK-7: PASS` and every Phase-B exit criterion is evidenced.

**PRECONDITION** — TASK-20. On FAIL, halt; no Phase-C mutation may begin.

### TASK-22 — Stop at the five-lineage human gate and obtain a retain-only acknowledgement

**OWNER — FLASH**

**COMMANDS**

Create the handoff report mechanically. This plan provides no acknowledgement value that authorizes merge or deletion; the only acceptable acknowledgement retains all five for this cleanup.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
ORIGIN=$(cat "$CROOT/manifests/origin-url.txt")
OUT=$CROOT/evidence/human-gated-lineages.tsv
: >"$OUT"
refs=(
  refs/heads/local/extension-foundation-completion
  refs/heads/epic/extension-reality-m1-trust-model-truth
  refs/heads/epic/extension-reality-m3-export-readiness-convergence
  refs/heads/megaplan/m3-export-readiness-20260710-0146
  refs/heads/cloud/vibecomfy-trust-correctness-2026-07/sprint-1
)
for ref in "${refs[@]}"; do
  oid=$(git ls-remote --refs "$ORIGIN" "$ref" | awk '{print $1}')
  test "${#oid}" -eq 40
  test -z "$(awk -F '\t' -v r="$ref" '$2==r{print}' "$CROOT/manifests/origin-delete.tsv")"
  git -C "$CROOT/git/origin-precleanup.git" cat-file -e "$oid^{commit}"
  printf '%s\t%s\tKEEP-HUMAN-GATED\n' "$ref" "$oid" >>"$OUT"
done
test "$(awk 'NF{n++} END{print n+0}' "$OUT")" -eq 5
git bundle verify "$CROOT/git/human-gated-and-vendor-20260807.bundle" >"$CROOT/evidence/human-gated-bundle-reverify.txt" 2>&1
CONTAINER
```

Copy the report to the host and deliberately halt for the human handoff:

```bash
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/human-gated-lineages.tsv "$HROOT/evidence/"; printf "%s\n" "The five rows in evidence/human-gated-lineages.tsv remain bundled and on origin. This cleanup contains no merge or delete action for them. Review extension ancestry/export overlap and the 721-commit VibeComfy lineage separately." >"$HROOT/HUMAN-GATE-HANDOFF.txt"; chmod 0600 "$HROOT/HUMAN-GATE-HANDOFF.txt"; printf "human_gate_handoff\t%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$HROOT/action-ledger.tsv"; exit 75'
```

Exit 75 is the intentional stop. A human reviews the report and, to let unrelated safe cleanup continue while retaining all five, creates exactly:

```bash
ssh root@159.69.51.216 'umask 077; printf "%s\n" "RETAIN_ALL_FIVE_NO_AUTOMATIC_DELETE_OR_MERGE_20260807" >/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/HUMAN-GATE-ACK'
```

On resumption Flash runs only this check:

```bash
ssh root@159.69.51.216 'set -euo pipefail; test "$(cat /var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807/HUMAN-GATE-ACK)" = "RETAIN_ALL_FIVE_NO_AUTOMATIC_DELETE_OR_MERGE_20260807"'
```

**DONE-CHECK**

- The handoff has five full OIDs, each still on origin and in the verified human-gated bundle.
- A human-created ACK has exactly the retain-only string above.
- No merge or deletion of any of the five is authorized now or later by this plan.

**PRECONDITION** — TASK-21 PASS. Flash must stop at exit 75 and may resume only after the exact human ACK exists.

---

## Phase C — lease-protected ref deletion and dependency-ordered tree removal; no Git GC

### TASK-23 — Re-observe every deletion target for 70 minutes and record a second successful `-r6` invocation

**OWNER — FLASH**

**COMMANDS**

Build the Phase-C observation list from literal deletion inputs, adding only the two failed-clone rows and exact `/workspace/0`. The count is checked but is not used to discover deletion targets.

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
CROOT=/var/tmp/arnold-branch-cleanup-20260807
{
  cut -f1 "$CROOT/manifests/box-delete.tsv"
  cut -f1 "$CROOT/input/failed-clones.tsv"
  printf "/workspace/0\n"
} | sort -u >"$CROOT/manifests/liveness-phase-c-delete-candidates.txt"
while IFS= read -r p; do test -e "$p"; done <"$CROOT/manifests/liveness-phase-c-delete-candidates.txt"
chmod 0400 "$CROOT/manifests/liveness-phase-c-delete-candidates.txt"
'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/manifests/liveness-phase-c-delete-candidates.txt "$HROOT/manifests/"; cp "$HROOT/bin-liveness-scan" "$HROOT/bin-liveness-scan-phase-c"; sed -i "s/liveness-phase-a/liveness-phase-c/g" "$HROOT/bin-liveness-scan-phase-c"; chmod 0700 "$HROOT/bin-liveness-scan-phase-c"; systemd-run --unit=arnold-cleanup-liveness-phase-c-20260807 --property=Type=oneshot "$HROOT/bin-liveness-scan-phase-c"'
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
for attempt in $(seq 1 75); do
  state=$(systemctl show -p ActiveState --value arnold-cleanup-liveness-phase-c-20260807.service)
  test "$state" = failed && exit 1
  test "$state" = inactive && break
  sleep 60
done
test "$(systemctl show -p Result --value arnold-cleanup-liveness-phase-c-20260807.service)" = success
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
test "$(awk -F '\t' 'NR>1 && $3=="delete" && ($5+$6+$7+$8+$9)>0{n++} END{print n+0}' "$HROOT/evidence/liveness-phase-c.tsv")" -eq 0
while IFS= read -r path; do
  test "$(awk -F '\t' -v p="$path" 'NR>1 && $3=="delete" && $4==p{n++} END{print n+0}' "$HROOT/evidence/liveness-phase-c.tsv")" -eq 70
done <"$HROOT/manifests/liveness-phase-c-delete-candidates.txt"
HOST
```

Run and record the second distinct successful service invocation, without touching the ad-hoc loop:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
UNIT=megaplan-resident-schedule-runner.service
first=$(cat "$HROOT/evidence/r6-invocation-1.id")
systemctl start "$UNIT"
second=$(systemctl show -p InvocationID --value "$UNIT")
test -n "$second"
test "$second" != "$first"
test "$(systemctl show -p Result --value "$UNIT")" = success
test "$(systemctl show -p ExecMainStatus --value "$UNIT")" = 0
printf '%s\n' "$second" >"$HROOT/evidence/r6-invocation-2.id"
journalctl -u "$UNIT" --since '90 minutes ago' --no-pager >"$HROOT/evidence/megaplan-resident-schedule-runner.two-runs.journal"
printf 'phase_c_liveness_zero_and_r6_twice\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$second" >>"$HROOT/action-ledger.tsv"
HOST
```

Re-run exact schedule searches after the observation interval:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
STORE=/workspace/arnold/.megaplan/resident/schedules
for old in arnold-bc0c600c arnold-74b4e6b9 arnold-6ce6d4eb; do
  set +e; rg -n --fixed-strings -- "$old" "$STORE" >/var/tmp/arnold-branch-cleanup-20260807/evidence/phase-c-$old.matches; rc=$?; set -e
  test "$rc" -eq 1
done
'
```

**DONE-CHECK**

- Every literal Phase-C filesystem target has exactly 70 samples and zero process, FD, bind, systemd/cron/environment/schedule/supervisor/runtime hits.
- The three schedule-root searches remain empty.
- Two distinct `-r6` invocation IDs both have success/zero status, with no evidence of duplicate occurrence creation.

**PRECONDITION** — TASK-22 retain-only ACK. Any positive liveness result or schedule match halts all Phase-C deletion.

### TASK-24 — CHECKPOINT-SENSECHECK-8: authorize the exact Phase-C rows, not a count or discovery result

**OWNER — CODEX-VALIDATES**

**COMMANDS**

The wrapper again requires both intended-design documents and evaluates all six fixer invariants.

```bash
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp "$HROOT/evidence/liveness-phase-c.tsv" megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/'
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-8.fragment.md >/dev/null' <<'PROMPT'
Independently decide only PASS/FAIL for the frozen Phase-C deletion rows; do not add candidates. Require: tested origin and bundle recovery for every target OID; second-domain checksum proof; landed/patch-mapped selected integrations; zero schedule references; 70 zero-liveness samples per filesystem target; two successful r6 invocations; complete dirty/untracked/metadata backups; 2bd self-containment with alternates disabled; and dependency order with dependents before owners. Re-resolve every literal path/head/ref and every deletion lease now. Prove the ten protected refs, Mac recovery ref, five human-gated refs, vendor snapshot, `/workspace/arnold`, active R7/R5/R6/WBC/critique/live trees, and b38460e4d3-with-live-owner are excluded. Require the retain-only human ACK. Verify no Git GC/prune/maintenance command is queued. Fail on one missing OID, changed lease, positive reference, dirty state without backup, ambiguous path, unclassified row, or protected target.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-8 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-8.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-8.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-8.result.md")" = "CHECKPOINT-SENSECHECK-8: PASS"'
```

**DONE-CHECK** — Codex result ends `CHECKPOINT-SENSECHECK-8: PASS` and names the immutable manifest checksums it authorized.

**PRECONDITION** — TASK-23. On FAIL, halt; perform no quarantine, ref deletion, or worktree removal.

### TASK-25 — Quarantine the seven literal stale pins, two failed clones, and `/workspace/0`

**OWNER — FLASH**

**COMMANDS**

Move stale pins on the host using literal manifest rows; never glob. The active `-r6` pin must not be a row:

```bash
ssh root@159.69.51.216 'bash -s' <<'HOST'
set -euo pipefail
umask 077
HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807
Q=$HROOT/quarantine/pins
install -d -m 0700 "$Q"
: >"$HROOT/evidence/pin-quarantine.tsv"
while IFS=$'\t' read -r path expected_sha expected_mode; do
  test "$path" != /usr/local/bin/arnold-resident-schedule-run-once-r6
  test -f "$path"; test ! -L "$path"
  test "$(sha256sum "$path" | awk '{print $1}')" = "$expected_sha"
  test "$(stat -c %a "$path")" = "$expected_mode"
  target=$Q/$(basename "$path")
  test ! -e "$target"
  mv -- "$path" "$target"
  printf '%s\t%s\t%s\n' "$path" "$target" "$expected_sha" >>"$HROOT/evidence/pin-quarantine.tsv"
done <"$HROOT/input/stale-pins.tsv"
test "$(awk 'NF{n++} END{print n+0}' "$HROOT/evidence/pin-quarantine.tsv")" -eq 7
systemctl start megaplan-resident-schedule-runner.service
test "$(systemctl show -p Result --value megaplan-resident-schedule-runner.service)" = success
HOST
```

Quarantine the exact container artifacts after verifying backups, canonical paths, digests, mount absence, and the Phase-C zero-liveness evidence:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
Q=/workspace/.arnold-cleanup-quarantine-20260807
install -d -m 0700 "$Q"
: >"$CROOT/evidence/non-git-quarantine.tsv"

tree_digest() {
  path=$1
  tmp=$CROOT/evidence/tree-digest.tmp
  : >"$tmp"
  find "$path" -xdev -printf 'M\t%m\t%U\t%G\t%s\t%P\n' | sort >>"$tmp"
  find "$path" -xdev -type f -print0 | sort -z | xargs -0 -r sha256sum | sed "s#  $path/#  #" >>"$tmp"
  sha256sum "$tmp" | awk '{print $1}'
}

while IFS=$'\t' read -r path expected; do
  test ! -L "$path"
  test "$(realpath -e "$path")" = "$path"
  mountpoint -q "$path" && exit 1
  actual=$(tree_digest "$path")
  test "$actual" = "$expected"
  id=$(printf '%s' "$path" | sha256sum | awk '{print $1}')
  tar --acls --xattrs --numeric-owner -C / -cpf "$CROOT/backups/non-git/failed-clone-$id.tar" "${path#/}"
  target=$Q/$(basename "$path")
  test ! -e "$target"
  mv -- "$path" "$target"
  printf '%s\t%s\t%s\tPURGE\n' "$path" "$target" "$expected" >>"$CROOT/evidence/non-git-quarantine.tsv"
done <"$CROOT/input/failed-clones.tsv"

path=/workspace/0
test -f "$CROOT/backups/non-git/workspace-0.tar"
test "$(realpath -e "$path")" = "$path"
test ! -L "$path"
mountpoint -q "$path" && exit 1
target=$Q/0
test ! -e "$target"
mv -- "$path" "$target"
printf '%s\t%s\t%s\tPURGE\n' "$path" "$target" "$(sha256sum "$CROOT/backups/non-git/workspace-0.tar" | awk '{print $1}')" >>"$CROOT/evidence/non-git-quarantine.tsv"
chmod 0600 "$CROOT/evidence/non-git-quarantine.tsv" "$CROOT/backups/non-git"/*.tar
CONTAINER
```

**DONE-CHECK**

- Exactly seven checksum/mode-verified stale pins are in the recovery quarantine; `-r6` remains in place and runs green afterward.
- Both exact failed-clone paths and exact `/workspace/0` are absent from their original paths and present under `/workspace/.arnold-cleanup-quarantine-20260807` with verified backups.
- No content was printed. No glob supplied a deletion target. Nothing has yet been `rm -rf`'d.

**PRECONDITION** — TASK-24 PASS.

### TASK-26 — Delete only frozen origin refs with exact leases

**OWNER — FLASH**

**COMMANDS**

The loop consumes literal `origin-delete.tsv` rows. Any lease mismatch stops the row and the entire plan; it is never overridden.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
M=$CROOT/manifests
repo=$CROOT/integration/main
ORIGIN=$(cat "$M/origin-url.txt")
ledger=$CROOT/evidence/origin-ref-deletions.tsv
: >"$ledger"
protected='refs/heads/main refs/heads/editible-install refs/heads/fix/r7-fresh-child-launch-20260805 refs/heads/recovery/box-cleanup-20260807 refs/heads/recovery/mac-main-pre-realign-20260807 refs/heads/local/extension-foundation-completion refs/heads/epic/extension-reality-m1-trust-model-truth refs/heads/epic/extension-reality-m3-export-readiness-convergence refs/heads/megaplan/m3-export-readiness-20260710-0146 refs/heads/cloud/vibecomfy-trust-correctness-2026-07/sprint-1 refs/heads/preserved-arnold-megaplan-vendor-pre-m11-20260731'

m10_seen=0
while IFS=$'\t' read -r expected full_ref; do
  case " $protected " in *" $full_ref "*) exit 1 ;; esac
  current=$(git ls-remote --refs "$ORIGIN" "$full_ref" | awk '{print $1}')
  test "$current" = "$expected"
  git -C "$CROOT/git/origin-precleanup.git" cat-file -e "$expected^{commit}"
  if test "$full_ref" = refs/heads/megaplan/custody-control-plane/m10-safe-retry-recovery-and-effects; then
    m10_seen=1
    git -C "$repo" merge-base --is-ancestor "$expected" origin/main
  fi
  git -C "$repo" push --force-with-lease="$full_ref:$expected" origin ":$full_ref"
  test -z "$(git ls-remote --refs "$ORIGIN" "$full_ref")"
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$expected" "$full_ref" >>"$ledger"
done <"$M/origin-delete.tsv"
test "$m10_seen" -eq 1
CONTAINER
```

**DONE-CHECK**

- Every deleted origin ref had exactly the frozen current OID at deletion time, exists in the origin-wide bundle, and is absent afterward.
- The M10 safe-retry ref was proven contained in `origin/main` immediately before its deletion.
- All 11 explicitly protected refs (the ten cleanup refs plus Mac recovery) remain unchanged.
- The only force-like option was the exact deletion lease; no ref was force-updated.

**PRECONDITION** — TASK-25. Any changed/missing remote ref halts immediately, even if earlier rows were already lease-deleted.

### TASK-27 — Clean Mac worktrees before local branches, using only frozen rows

**OWNER — FLASH**

**COMMANDS**

Reverify the Mac state archive before mutation, then perform the surveyed order. The input must classify exactly two `unique-detached`, four `contained-detached`, and thirteen `broken-registration` rows; any other counts halt.

```bash
MAC_TARGET=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-ssh-target.txt')
MAC_REPO=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-repo-path.txt')
MAC_RECOVERY=$(ssh root@159.69.51.216 'tr -d "\r\n" </root/arnold-branch-cleanup-20260807-input/mac-recovery-root.txt')
scp /tmp/worktrees.mac.tsv "$MAC_TARGET:/tmp/arnold-worktrees.mac.resolved.tsv"
scp /tmp/local-delete.resolved.tsv "$MAC_TARGET:/tmp/arnold-local-delete.resolved.tsv"
ssh "$MAC_TARGET" "MAC_REPO='$MAC_REPO' MAC_RECOVERY='$MAC_RECOVERY' bash -s" <<'MAC'
set -euo pipefail
test "$(cd "$MAC_RECOVERY" && shasum -a 256 -c mac-worktree-state-20260807.tar.sha256 | wc -l)" -eq 1
test "$(awk -F '\t' '$5=="unique-detached"{n++} END{print n+0}' /tmp/arnold-worktrees.mac.resolved.tsv)" -eq 2
test "$(awk -F '\t' '$5=="contained-detached"{n++} END{print n+0}' /tmp/arnold-worktrees.mac.resolved.tsv)" -eq 4
test "$(awk -F '\t' '$5=="broken-registration"{n++} END{print n+0}' /tmp/arnold-worktrees.mac.resolved.tsv)" -eq 13

remove_class() {
  wanted=$1
  while IFS=$'\t' read -r site owner path oid class dirty_policy; do
    test "$class" = "$wanted" || continue
    test "$(git -C "$path" rev-parse HEAD)" = "$oid"
    case "$dirty_policy" in
      clean) test -z "$(git -C "$path" status --porcelain=v1)"; git -C "$owner" worktree remove "$path" ;;
      required-backup) test -f "$MAC_RECOVERY/mac-worktree-state-20260807.tar"; git -C "$owner" worktree remove --force "$path" ;;
      *) exit 1 ;;
    esac
    test ! -e "$path"
  done </tmp/arnold-worktrees.mac.resolved.tsv
}
remove_class unique-detached
remove_class contained-detached

git -C "$MAC_REPO" worktree prune --dry-run --verbose >"$MAC_RECOVERY/worktree-prune.dry-run.txt"
test "$(awk -F '\t' '$5=="broken-registration"{n++} END{print n+0}' /tmp/arnold-worktrees.mac.resolved.tsv)" -eq 13
while IFS=$'\t' read -r site owner path oid class dirty_policy; do
  test "$class" = broken-registration || continue
  grep -Fq -- "$path" "$MAC_RECOVERY/worktree-prune.dry-run.txt"
done </tmp/arnold-worktrees.mac.resolved.tsv
git -C "$MAC_REPO" worktree prune --verbose

remove_class branch-linked

while IFS=$'\t' read -r oid branch preserving mode; do
  test "$branch" != main
  test "$branch" != editible-install
  test "$(git -C "$MAC_REPO" rev-parse "refs/heads/$branch")" = "$oid"
  case "$mode" in
    d)
      git -C "$MAC_REPO" branch -d "$branch"
      ;;
    D)
      grep -q "^$oid"$'\t' "$MAC_RECOVERY/../arnold-branch-cleanup-20260807-input/patch-equivalences.tsv" 2>/dev/null || git -C "$MAC_REPO" bundle verify "$MAC_RECOVERY/../arnold-branch-cleanup-20260807-input/mac-precleanup-20260807.bundle" >/dev/null
      git -C "$MAC_REPO" branch -D "$branch"
      ;;
    *) exit 1 ;;
  esac
done </tmp/arnold-local-delete.resolved.tsv

git -C "$MAC_REPO" show-ref --verify --quiet refs/heads/main
git -C "$MAC_REPO" show-ref --verify --quiet refs/heads/editible-install
git -C "$MAC_REPO" worktree list --porcelain >"$MAC_RECOVERY/worktrees.after.txt"
MAC
```

**DONE-CHECK**

- The two unique detached trees were backed up and removed first, then four contained snapshots, then exactly 13 broken registrations, then branch-linked worktrees.
- `branch -d` was used for ancestry-contained branches; `branch -D` was used only for frozen patch-mapped/bundle-proven rows.
- Mac `main` and `editible-install` remain; main still equals origin/main.
- No count generated a target; every removed path/branch came from a literal resolved manifest row.

**PRECONDITION** — TASK-26. Any Mac transport drift, unexpected dirty state, dry-run mismatch, missing backup, or branch OID mismatch halts.

### TASK-28 — Quarantine eligible standalone box clones using exact paths and HEADs

**OWNER — FLASH**

**COMMANDS**

Only `kind=standalone` rows in the frozen deletion order are processed. Rename is on the same filesystem; no raw deletion occurs yet.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
: >"$CROOT/evidence/tree-quarantine.tsv"
while IFS=$'\t' read -r sequence kind path expected owner unit; do
  test "$kind" = standalone || continue
  test ! -L "$path"
  test "$(realpath -e "$path")" = "$path"
  test "$(git -C "$path" rev-parse HEAD)" = "$expected"
  mountpoint -q "$path" && exit 1
  grep -Fqx "$expected" "$CROOT/manifests/critical-oids.txt" || git -C "$CROOT/verify/bundle-restore.git" cat-file -e "$expected^{commit}"
  test "$(awk -F '\t' -v p="$path" 'NR>1 && $3=="delete" && $4==p && ($5+$6+$7+$8+$9)>0{n++} END{print n+0}' "$CROOT/evidence/liveness-phase-c.tsv")" -eq 0
  qparent=$(dirname "$path")/.arnold-cleanup-quarantine-20260807
  install -d -m 0700 "$qparent"
  target=$qparent/$(basename "$path")
  test ! -e "$target"
  mv -- "$path" "$target"
  test ! -e "$path"; test -d "$target"
  printf '%s\t%s\t%s\t%s\tPURGE\n' "$sequence" "$path" "$target" "$expected" >>"$CROOT/evidence/tree-quarantine.tsv"
done <"$CROOT/input/deletion-order.tsv"
chmod 0600 "$CROOT/evidence/tree-quarantine.tsv"
CONTAINER
```

**DONE-CHECK**

- Each standalone row had canonical exact path, exact HEAD, zero mount/liveness/reference evidence, and bundle/origin recovery proof.
- Original paths are absent and same-filesystem quarantine paths exist with the same Git HEAD.
- No protected or integration-selected tree was processed; no quarantined tree was purged yet.

**PRECONDITION** — TASK-27.

### TASK-29 — Remove dependents before owners, then quarantine owners in the mandatory unit order

**OWNER — FLASH**

**COMMANDS**

First enforce the dependency order encoded by the survey. The following unit names and relationships are mandatory; a missing unit is a halt, not a skip:

```bash
docker exec megaplan-cloud-agent-resident-only bash -lc '
set -euo pipefail
F=/var/tmp/arnold-branch-cleanup-20260807/input/deletion-order.tsv
seq_of() { awk -F "\t" -v u="$1" '\''$6==u{if(min==0||$1<min)min=$1} END{if(min==0)exit 1; print min}'\'' "$F"; }
last_of() { awk -F "\t" -v u="$1" '\''$6==u{if($1>max)max=$1} END{if(max==0)exit 1; print max}'\'' "$F"; }
test "$(last_of runtime-7dab2f2645)" -lt "$(seq_of runtime-50ef856df5)"
for u in 5bf11d5a 9f9982c855 74b4e6b9 bc0c600c 6ce6d4eb; do seq_of "$u" >/dev/null; done
test "$(last_of 4076d59ab4)" -lt "$(seq_of bc0c600c)"
test "$(last_of a1cbde99c3)" -lt "$(seq_of bc0c600c)"
'
```

Then process `linked-worktree` and `owner` rows strictly by numeric sequence. Worktrees are removed only through their owner repository. Owners are quarantined only after worktree-prune and remaining-alternate checks:

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
ORDER=$CROOT/input/deletion-order.tsv
sort -t $'\t' -k1,1n "$ORDER" >"$CROOT/evidence/deletion-order.sorted.tsv"
: >"$CROOT/evidence/worktree-owner-actions.tsv"

while IFS=$'\t' read -r sequence kind path expected owner unit; do
  case "$kind" in
    linked-worktree)
      test "$owner" != /workspace/arnold || grep -Fqx $'box\t/workspace/arnold\t'"$path" <(cut -f1-3 "$CROOT/manifests/worktrees.tsv")
      test ! -L "$path"
      test "$(realpath -e "$path")" = "$path"
      test "$(git -C "$path" rev-parse HEAD)" = "$expected"
      grep -Fq "worktree $path" < <(git -C "$owner" worktree list --porcelain)
      row=$(awk -F '\t' -v p="$path" '$3==p{print; n++} END{if(n!=1)exit 1}' "$CROOT/manifests/worktrees.tsv")
      dirty_policy=$(printf '%s\n' "$row" | cut -f6)
      id=$(printf '%s' "$path" | sha256sum | awk '{print $1}')
      test -f "$CROOT/backups/worktrees/$id/SHA256SUMS"
      (cd "$CROOT/backups/worktrees/$id" && sha256sum -c SHA256SUMS >/dev/null)
      if test "$dirty_policy" = clean; then
        test -z "$(git -C "$path" status --porcelain=v1)"
        git -C "$owner" worktree remove "$path"
      elif test "$dirty_policy" = required-backup; then
        git -C "$owner" worktree remove --force "$path"
      else
        exit 1
      fi
      test ! -e "$path"
      printf '%s\tlinked-worktree-removed\t%s\t%s\t%s\n' "$sequence" "$path" "$expected" "$unit" >>"$CROOT/evidence/worktree-owner-actions.tsv"
      ;;
    owner)
      test ! -L "$path"
      test "$(realpath -e "$path")" = "$path"
      test "$(git -C "$path" rev-parse HEAD)" = "$expected"
      git -C "$path" worktree prune --dry-run --verbose >"$CROOT/evidence/prune-$unit.dry-run.txt"
      test ! -s "$CROOT/evidence/prune-$unit.dry-run.txt"
      git -C "$path" worktree prune --verbose
      test "$(git -C "$path" worktree list --porcelain | grep -c '^worktree ' || true)" -eq 1

      if test "$unit" = 9f9982c855; then
        repo2=/workspace/arnold-2bd0b2d345022c8797f8e63998b93a08a8ae5954
        test ! -e "$(git -C "$repo2" rev-parse --git-path objects/info/alternates)"
        git -C "$repo2" fsck --full >/dev/null
      fi
      if test "$unit" = 74b4e6b9; then
        ! rg -l --fixed-strings 'arnold-74b4e6b9' /workspace/arnold/.megaplan/resident/schedules >/dev/null
      fi
      if test "$unit" = bc0c600c; then
        ! rg -l --fixed-strings 'arnold-bc0c600c' /workspace/arnold/.megaplan/resident/schedules >/dev/null
      fi
      if test "$unit" = 6ce6d4eb; then
        ! rg -l --fixed-strings 'arnold-6ce6d4eb' /workspace/arnold/.megaplan/resident/schedules >/dev/null
      fi

      objdir=$(git -C "$path" rev-parse --git-path objects)
      while IFS= read -r altfile; do
        test -f "$altfile" || continue
        if rg -q --fixed-strings -- "$objdir" "$altfile"; then exit 1; fi
      done < <(find /workspace -path '*/objects/info/alternates' -type f -print)

      qparent=$(dirname "$path")/.arnold-cleanup-quarantine-20260807
      install -d -m 0700 "$qparent"
      target=$qparent/$(basename "$path")
      test ! -e "$target"
      mv -- "$path" "$target"
      printf '%s\t%s\t%s\t%s\tPURGE\n' "$sequence" "$path" "$target" "$expected" >>"$CROOT/evidence/tree-quarantine.tsv"
      printf '%s\towner-quarantined\t%s\t%s\t%s\n' "$sequence" "$path" "$expected" "$unit" >>"$CROOT/evidence/worktree-owner-actions.tsv"
      ;;
  esac
done <"$CROOT/evidence/deletion-order.sorted.tsv"
CONTAINER
```

The frozen order must specifically produce:

1. `arnold-runtime-7dab2f2645` before `arnold-runtime-50ef856df5`.
2. Both `5bf11d5a` worktrees, then prune, then owner quarantine.
3. For `9f9982c855`, the one worktree, prune, then owner quarantine only after `2bd` passes without alternates.
4. For `74b4e6b9`, its four worktrees before owner and zero schedule refs.
5. For `bc0c600c`, alternate dependents `4076d59ab4` and `a1cbde99c3`, then all 14 backed-up worktrees, prune, then owner and zero schedule refs.
6. `6ce6d4eb` only after zero schedule refs.

No row may name the R7 owner/three worktrees including `77b76e3a4`, R5/WBC, R6, `/workspace/arnold`, or `b38460e4d3` while a live worktree exists.

**DONE-CHECK**

- The action ledger follows strictly increasing frozen sequence and the six mandatory unit relationships above.
- Every linked worktree was backup-verified and removed via `git worktree remove`; `/workspace/arnold`-owned stale worktrees were never raw-deleted.
- Every owner had only its primary worktree, a clean prune dry-run, no remaining alternate consumer, exact HEAD, zero liveness/schedule references, and recovery proof before same-filesystem quarantine.
- No owner/raw quarantine was purged yet; no `git gc` or object prune ran.

**PRECONDITION** — TASK-28. Any dependency, registration, alternate, head, backup, schedule, liveness, or path mismatch halts.

### TASK-30 — CHECKPOINT-SENSECHECK-9: verify quarantines, ref recovery, and live health before irreversible purge

**OWNER — CODEX-VALIDATES**

**COMMANDS**

The mandatory prompt anchor loads/references both intended-design docs and applies all six fixer invariants.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-9.fragment.md >/dev/null' <<'PROMPT'
Before any raw quarantine purge, independently audit every completed Phase-C action. Verify each remote deletion against its exact lease and origin-wide bundle restoration; all protected refs and recovery refs must remain exact. Verify Mac cleanup order/backups and retained main/editible. For every box target, match the literal manifest row, expected HEAD/digest, 70-minute zero-liveness evidence, backup checksums, quarantine location, and dependency order. Verify worktree removals and owner prune state, no remaining alternates consumer, zero old schedule roots, 2bd fsck without alternates, two-plus healthy r6 invocations, responsive listener/container, and unchanged active R7/R5/R6/WBC/critique/live trees. Re-run mandatory-OID restores from origin and bundle now. Confirm no Git GC/prune/maintenance occurred. Fail rather than authorizing purge if rollback from origin plus tested bundles and dirty-state archives is not complete.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-9 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-9.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-9.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-9.result.md")" = "CHECKPOINT-SENSECHECK-9: PASS"'
```

**DONE-CHECK** — Codex result ends `CHECKPOINT-SENSECHECK-9: PASS`.

**PRECONDITION** — TASK-29. On FAIL, halt with quarantines intact; do not purge them.

### TASK-31 — Purge only exact `PURGE` quarantine rows; retain stale pins in recovery quarantine

**OWNER — FLASH**

**COMMANDS**

Purge raw tree/non-Git quarantines only. Each variable is first resolved and compared to an explicit allowed quarantine prefix; there is no glob and no unresolved target.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -s <<'CONTAINER'
set -euo pipefail
umask 077
CROOT=/var/tmp/arnold-branch-cleanup-20260807
ledger=$CROOT/evidence/purges.tsv
: >"$ledger"
for manifest in "$CROOT/evidence/non-git-quarantine.tsv" "$CROOT/evidence/tree-quarantine.tsv"; do
  while IFS=$'\t' read -r a b c d e; do
    if test "$manifest" = "$CROOT/evidence/non-git-quarantine.tsv"; then
      original=$a; target=$b; proof=$c; action=$d
    else
      sequence=$a; original=$b; target=$c; proof=$d; action=$e
    fi
    test "$action" = PURGE
    test ! -L "$target"
    resolved=$(realpath -e "$target")
    test "$resolved" = "$target"
    case "$target" in
      /workspace/.arnold-cleanup-quarantine-20260807/*|/workspace/*/.arnold-cleanup-quarantine-20260807/*) ;;
      *) exit 1 ;;
    esac
    mountpoint -q "$target" && exit 1
    rm -rf --one-file-system -- "$target"
    test ! -e "$target"
    printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$original" "$proof" >>"$ledger"
  done <"$manifest"
done
chmod 0600 "$ledger"
CONTAINER
```

Copy action evidence to the host; do not delete the seven pin quarantine files:

```bash
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; test "$(find "$HROOT/quarantine/pins" -maxdepth 1 -type f | wc -l)" -eq 7; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/evidence/. "$HROOT/evidence/"; printf "phase_c_purge_complete_no_gc\t%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$HROOT/action-ledger.tsv"'
```

**DONE-CHECK**

- Every and only `PURGE` row is absent at both original and quarantine path and has a timestamp/proof ledger row.
- The seven stale pins remain recoverable under the host recovery quarantine.
- No broad directory, unresolved variable, symlink, mount, protected tree, or filesystem glob was deleted.
- No Git GC, maintenance, repack, or prune command ran.

**PRECONDITION** — TASK-30 PASS.

### TASK-32 — CHECKPOINT-SENSECHECK-10: Phase-C exit gate

**OWNER — CODEX-VALIDATES**

**COMMANDS**

The wrapper supplies the two canonical docs and complete fixer-invariant standard.

```bash
docker exec -i megaplan-cloud-agent-resident-only bash -lc 'umask 077; tee /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-10.fragment.md >/dev/null' <<'PROMPT'
Audit Phase C after purge. Require one action row with expected SHA/OID, backup proof, origin/bundle proof, and timestamp for every deleted manifest item. Verify no stale worktree registration points to a removed path; no alternates file names a removed object store; no schedule definition/history names a removed tree; protected and recovery refs equal their post-integration OIDs; all five human-gated refs and vendor snapshot remain. Verify active containers/listener, R7 epic and critique ledger health, R5/WBC/R6 and every live path. Verify the r6 timer after stale-pin quarantine. Re-run empty origin/bundle restores for every mandatory OID and 2bd fsck without alternates. Search command/audit evidence for any Git GC, maintenance, prune, or unapproved repack. Fail on any missing proof, unexpected deletion, dangling dependency, schedule match, liveness regression, or intended-design violation.
PROMPT
docker exec megaplan-cloud-agent-resident-only bash -lc '/var/tmp/arnold-branch-cleanup-20260807/bin/run-sensecheck CHECKPOINT-SENSECHECK-10 /var/tmp/arnold-branch-cleanup-20260807/prompts/checkpoint-10.fragment.md'
ssh root@159.69.51.216 'set -euo pipefail; HROOT=/var/lib/arnold/megaplan-resident-recovery/arnold-branch-cleanup-20260807; docker cp megaplan-cloud-agent-resident-only:/var/tmp/arnold-branch-cleanup-20260807/codex/CHECKPOINT-SENSECHECK-10.result.md "$HROOT/codex/"; test "$(awk '\''NF{line=$0} END{print line}'\'' "$HROOT/codex/CHECKPOINT-SENSECHECK-10.result.md")" = "CHECKPOINT-SENSECHECK-10: PASS"'
```

**DONE-CHECK** — Codex result ends `CHECKPOINT-SENSECHECK-10: PASS`; all Phase-C exit criteria pass.

**PRECONDITION** — TASK-31. On FAIL, halt and use recorded recovery artifacts; do not run GC.
