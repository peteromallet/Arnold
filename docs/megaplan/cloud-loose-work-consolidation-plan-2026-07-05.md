# Cloud Loose Work Consolidation Plan - 2026-07-05

## Rationale

This plan covers the second-pass `cleanup-loose-branches` finding that the first cloud
survey only checked the obvious `/workspace/arnold` checkout and missed older Arnold
per-chain workspaces on the Hetzner agentbox.

The goal is to land or preserve every useful Arnold item, then delete only redundant
branches/workspaces/stashes after positive evidence. Nothing in this plan authorizes
dropping cloud stashes or removing cloud workspaces until the verification steps below
are complete.

## Current Local State

- Current checkout: `superfixer-reigh-epic-recovery`
- Local checkout status: clean
- `main` / `origin/main`: `e9d7d6ba`
- `editible-install` / `origin/editible-install`: `edc46d62`
- `superfixer-reigh-epic-recovery`: `a3d4d2d6`, local-only

## Primary Local Branch Verdicts

| Item | State | Verdict | Reason |
|---|---|---|---|
| `editible-install` | 7 patch-unique commits ahead of current `main`; merge-tree clean | Merge into `main`, test, push | Contains useful code/tests/skill updates not superseded by current `main`. |
| `superfixer-reigh-epic-recovery` | Local-only merge commit over stale base `387fcb0c`; `editible-install` is its parent | Do not merge directly; delete after `editible-install` lands | It adds no useful non-merge commit beyond `editible-install` and risks reverting newer `main` evidence if used as the merge vehicle. |
| `stash@{0}` local | `superfixer-local-before-merge` | Drop only after `editible-install` lands and tests pass | Code/test payload is covered by `editible-install`; extra ledger lines are generated demo/test telemetry. |
| `origin/megaplan/m6-platform-docs-conformance-20260705-0039` | Ancestor of `main`; `cherry +0` | Ready to delete after final push | Fully merged into `main`. |
| `origin/archive/*`, `origin/preserve/*` | Historical safety refs | Keep for now | They are archival evidence, not ordinary loose branches. Delete only under a separate archive-retention decision. |

## Hetzner Arnold Workspace Inventory

The broad cloud sweep found every git repo under `/workspace` and filtered Arnold
repos by origin `*Arnold.git*` or local origin `/workspace/arnold`.

| Workspace | Head / Branch | Dirty or Unique State | Verdict |
|---|---|---|---|
| `/workspace/arnold` | `editible-install` at `edc46d62` | Dirty only `.megaplan/incident-ledger/.events.seq` and `events.jsonl` | Generated residue. Do not port. Reset only after `editible-install` lands everywhere. |
| `/workspace/python-shaped-workflow-authoring` | `editible-install` at `ef733bc6`; origin `/workspace/arnold` | Commit already contained in local `main`/`editible-install`; untracked `NORTHSTAR.md`, `chain.yaml`, chain JSON, log | Preserve intent artifacts if not already archived; log is residue. Then safe to reset/remove. |
| `/workspace/workflow-boundary-contracts/Arnold` | `main` at `693c6cbb` | Untracked initiative docs for `progress-auditor-stage-metrics`, `sequential-model-fallbacks`, `workflow-boundary-contracts`; one local edit to `native-platform-followup/chain.yaml` | Durable docs are byte-identical to `/workspace/arnold` and tracked locally. Treat untracked copies as redundant. Investigate the tracked `chain.yaml` diff before reset. |
| `/workspace/native-composition-followup/Arnold` | `megaplan/m6-composition-docs-and-20260704-0158` at `867575b5` | Untracked incident ledger plus two substantial stashes | Do not delete/reset yet. Verify stashes patch-by-patch. |
| `/workspace/native-platform-followup/Arnold` | `megaplan/m6-platform-docs-conformance-20260705-0039` at `9b43e28d` | Generated log/runtime dirt plus one substantial stash | Do not delete/reset yet. Verify stash patch-by-patch. |
| `/workspace/native-python-pipelines-completion-parent-22937539/arnold` | `megaplan/m7-megaplan-relocation-and-20260702-0856` at `6bf9330c`, ahead 1 of its origin branch | Modified generated cloud logs and chain/epic state JSON | Likely generated state. Verify ahead commit is contained in local `main` before reset. |
| `/workspace/progress-auditor-stage-metrics/Arnold` | `editible-install` at `a1a3591b` | Dirty incident ledger only | Generated residue; safe after final source-of-truth push. |
| `/workspace/sequential-model-fallbacks/Arnold` | `editible-install` at `d4e22b00` | Dirty incident ledger only | Generated residue; safe after final source-of-truth push. |
| `/workspace/incident-control-plane/Arnold` | `main` at `87e27d78` | Clean | Already contained in local refs. Safe to refresh/remove after final confirmation. |
| `/workspace/superfixer-repair-custody/Arnold` | `main` at `692e7887` | Clean | Already contained in local refs. Safe to refresh/remove after final confirmation. |
| `/workspace/tiered-repair-hardening/Arnold` | `main` at `d47a4ce0` | One substantial stash | Do not delete/reset yet. Verify stash patch-by-patch. |

Non-Arnold cloud repos found (`VibeComfy`, `reigh-app`) are out of scope for this Arnold cleanup.

## Cloud Stashes Requiring Proof Before Delete

These are the remaining high-risk items:

| Workspace | Stash | User-facing payload | Required proof |
|---|---|---|---|
| `/workspace/native-composition-followup/Arnold` | `stash@{0}` | Native composition trace/audit/runtime/compiler work plus tests | Compare each code patch to current `main`/`editible-install`; if superseded, record the covering commits. |
| `/workspace/native-composition-followup/Arnold` | `stash@{1}` | Earlier composition contract/runtime/auto/chain changes plus manifest/proof-map state | Split code from generated state, then compare code to current refs. |
| `/workspace/native-platform-followup/Arnold` | `stash@{0}` | Side-effect reconciliation/idempotency work, audit/checkpoint/runtime/tests, plus large incident ledger | Compare code to current refs; treat incident ledger as generated unless it contains unique human-authored incidents. |
| `/workspace/tiered-repair-hardening/Arnold` | `stash@{0}` | Repair-loop current-target/human-blocker/repair-contract work plus tests | Compare code to current refs and the already-landed tiered repair commits. |

Recommended verification method:

1. Export each stash as a patch into a temporary local evidence directory, not into the repo root.
2. Split generated/log/ledger paths from source/test paths.
3. For source/test paths, compare against current `main`, `editible-install`, and relevant landed commits with `git range-diff`, `git patch-id --stable`, and targeted `rg` checks for introduced symbols/tests.
4. If every source/test hunk is covered, mark the stash `drop-ready`.
5. If any hunk is unique and useful, port it onto `main` after `editible-install` lands, with focused tests.

## Execution Order

1. Preserve/verify before mutation:
   - Export all four cloud stash patches to a timestamped backup directory.
   - Export `/workspace/python-shaped-workflow-authoring` untracked intent files.
   - Export the `/workspace/workflow-boundary-contracts/Arnold` `native-platform-followup/chain.yaml` diff.
2. Merge source-of-truth branch:
   - Switch local checkout to `main`.
   - Fast-forward/pull `origin/main`.
   - Merge `editible-install` into `main`.
   - Run focused tests for touched areas:
     - `tests/arnold_pipelines/megaplan/test_chain_worktree_safety.py`
     - `tests/cloud/test_status_snapshot.py`
     - `tests/cloud/test_watchdog_wrappers.py`
     - `tests/test_chain_completion_guard.py`
   - Run the broad practical Python test subset already used in the prior cleanup.
3. Push:
   - Push `main`.
   - Update/push `editible-install` to the same source-of-truth tip if the user wants both branches kept aligned.
4. Refresh cloud source-of-truth on Hetzner:
   - Fetch/reset `/workspace/arnold` only after making a backup of its current dirty ledger diff.
   - Set `/workspace/arnold` local `main` to `origin/main`.
   - Set `/workspace/arnold` local `editible-install` to `origin/editible-install`.
   - End with both cloud branches pointing at the same merged commit when `editible-install`
     is being kept as the editable install branch.
   - Confirm imports resolve from `/workspace/arnold`.
5. Verify cloud stash supersession:
   - Work through the four stash rows above.
   - Port any unique source/test hunks before dropping anything.
6. Cleanup after proof:
   - Drop only verified-superseded cloud stashes.
   - Reset/remove only inactive completed Arnold cloud workspaces whose code and durable docs are already on `main`.
   - Delete `superfixer-reigh-epic-recovery` locally after `editible-install` lands.
   - Drop local `stash@{0}` after `editible-install` lands and tests pass.
   - Delete merged remote `origin/megaplan/m6-platform-docs-conformance-20260705-0039`.

## Items Not Safe To Delete Yet

- Any of the four cloud stashes listed above.
- `/workspace/native-composition-followup/Arnold` until both stashes are proven superseded or ported.
- `/workspace/native-platform-followup/Arnold` until its stash is proven superseded or ported.
- `/workspace/tiered-repair-hardening/Arnold` until its stash is proven superseded or ported.
- The `workflow-boundary-contracts` tracked `native-platform-followup/chain.yaml` diff until it is confirmed as stale/superseded.

## Confidence

High confidence:

- `editible-install` should be merged into current `main`.
- `superfixer-reigh-epic-recovery` should not be the merge vehicle.
- Cloud generated incident ledgers/logs/runtime mirrors should not be treated as source.
- The large untracked initiative doc sets under `workflow-boundary-contracts` are already preserved locally.

Medium confidence pending verification:

- Cloud stashes are probably superseded by later landed milestone commits, but they are too large to drop without patch-level proof.
- `/workspace/python-shaped-workflow-authoring` untracked intent files are probably redundant, but they should be copied into the evidence backup before workspace cleanup.

## Final Gate

Before destructive cleanup, rerun:

```bash
git status --short --branch
git branch -a --contains <every-cloud-head-sha>
ssh root@159.69.51.216 "docker exec megaplan-cloud-agent bash -lc 'find /workspace -maxdepth 3 \\( -name .git -o -type f -name .git \\) -print | sort'"
python -m arnold_pipelines.megaplan cloud status --all --cloud-yaml .megaplan/initiatives/native-platform-followup/cloud.yaml --compact
```

Deletion is allowed only for rows that have either landed on `main` or have an explicit
generated/residue verdict with exported backup evidence.

## Required End State

This cleanup is not complete until:

- GitHub `main` contains the useful `editible-install` work and the cleanup plan.
- GitHub `editible-install` is updated to the same final commit, unless a later explicit
  decision says to retire that branch.
- Hetzner `/workspace/arnold` has local `main` and local `editible-install` fetched and
  reset to those pushed GitHub tips.
- `python -m arnold_pipelines.megaplan cloud status --all ... --compact` still reports
  no active Arnold run that would be harmed by the refresh.
- Cloud imports resolve from `/workspace/arnold` after the refresh.
