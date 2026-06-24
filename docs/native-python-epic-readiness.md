# Native Python Pipelines Completion Epic Readiness

Working directory: `/Users/peteromalley/Documents/megaplan`  
Requested editable branch: `working-branch`  
Primary source files:
- `briefs/native-python-pipelines-completion/chain.yaml`
- `docs/arnold/pipelines/migration-completion-plan-v4.md`

## Verdict

**Not ready to run directly from the old cleanup branch. Needs cleanup/prep first.**

Blocking facts:

1. `python-shaped-workflow-authoring-cleanup` does **not** contain `briefs/native-python-pipelines-completion/chain.yaml`, the milestone briefs, or `docs/arnold/pipelines/migration-completion-plan-v4.md`.
2. The local `chain.yaml` exists only as an ignored working-tree file (`.gitignore:38: chain.yaml`). It is not committed on `python-shaped-workflow-authoring-cleanup` or `native-python-pipelines`.
3. The committed source plan and milestone briefs live on `native-python-pipelines`, not on `python-shaped-workflow-authoring-cleanup`.
4. The chain spec currently says `base_branch: main`, `merge_policy: auto`, `driver.auto_approve: true`, and `driver.require_clean_base: true`. If launched as-is, it targets `main`, not the cleanup branch.
5. The chain has no top-level `anchors.north_star`; current chain start code validates this before path validation and fails unless an anchor is added or the spec explicitly opts out with an acknowledgement.
6. The milestone briefs assume native-runtime code shapes present on `native-python-pipelines` but missing on `python-shaped-workflow-authoring-cleanup`, including `arnold/pipeline/native/compiler.py`, `arnold/pipelines/megaplan/pipeline.py`, `arnold/pipelines/megaplan/native_runner.py`, and `arnold/pipelines/evidence_pack/__init__.py`.

Structural read-only validation:

- `python -m arnold_pipelines.megaplan chain status --spec briefs/native-python-pipelines-completion/chain.yaml` parsed the ignored local spec and reported 8 pending milestones, `Base branch: main`.
- Direct parser inspection showed all 8 absolute `idea:` paths are missing in the current checkout.
- There is no `--dry-run` flag for `chain start`; no `chain start` was run.

## Branch strategy

The editable install branch is `python-shaped-workflow-authoring-cleanup`. Do not do the messy integration work directly on it. Instead:

1. Create a working integration branch named `native-python-working-tree` from `working-branch`.
2. Reconcile the `native-python-pipelines` donor work into `native-python-working-tree`.
3. Fix the epic spec, add the North Star, validate with `chain status`, and run milestones one at a time.
4. Only when the epic is complete and the branch is green do we merge `native-python-working-tree` back into `working-branch` so the editable install moves forward cleanly.

`working-branch` stays the single source of truth for the live editable install; `native-python-working-tree` is the scratch/integration surface.

## Epic Summary

Goal: finish the Arnold native Python pipeline migration so packages build native declarations, return projected `Pipeline` compatibility shells with `Pipeline.native_program`, run through native runtime/resume semantics, use native traces as test truth, and finally remove or explicitly shim graph-era surfaces only after import inventory proves it is safe.

Source plan: `docs/arnold/pipelines/migration-completion-plan-v4.md` on `native-python-pipelines`.

## North Star for this epic

The durable destination we are building toward:

> Arnold runs entirely on native Python pipelines. Every package builds native declarations and returns projected `Pipeline` compatibility shells via `Pipeline.native_program`. Execution, resume, and testing use native runtime semantics and native traces as truth. Graph-era surfaces are removed or explicitly shimmed only after import inventory proves it is safe.

This is the intent that every milestone brief and every milestone anchor must extend, not replace.

### Milestone map

| Milestone | Plain-English goal | Classification | Depends on current branch state? |
| --- | --- | --- | --- |
| `m1-platform-contract` | Add `Pipeline.native_program`, make executor/registry/validator/CLI prefer native, keep bundle fallback temporarily. | Risky foundation. Touches public types, hashing/serialization assumptions, executor, registry, CLI. | Yes. Missing from cleanup; exists substantially on `native-python-pipelines`. |
| `m2-megaplan-subpipelines-layout` | Normalize `writing_panel_strict` and `select_tournament` package paths before behavior migrations. | Mostly mechanical but import-sensitive. | Yes. Requires M1 contract and existing Megaplan package layout. |
| `m3-root-and-shared-package-migrations` | Migrate `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, and `deliberation` to final native-backed contract. | Risky broad migration. Runtime behavior can be structurally correct but semantically wrong. | Strongly. Cleanup branch lacks native package infrastructure. |
| `m3-5-canonical-megaplan-migration` | Migrate canonical `megaplan` runtime, `native_runner.py`, and `auto.py` off stage-order/bundle heuristics. | Highest-risk runtime milestone. | Strongly. Cleanup branch lacks the target files; `native-python-pipelines` has them. |
| `m4-evidence-pack-native-migration` | Move `evidence_pack` to shared native execution/resume while preserving review/attestation behavior. | High-risk runtime/resume milestone. | Strongly. Cleanup branch lacks `arnold/pipelines/evidence_pack`; donor branch has it. |
| `m5-native-test-and-golden-trace-cleanup` | Replace graph-parity tests and graph goldens with native-truth suites, keeping at most one intentional legacy baseline. | Risky cleanup, sequenced after runtime stability. | Yes. Must wait until M3.5 and M4 are stable. |
| `m6-docs-and-scaffolds-native-first` | Update docs, generated docs, authoring helpers, and templates to teach native-first only. | Mostly mechanical after M5, with drift risk. | Yes. Should follow actual code state, not lead it. |
| `m7-megaplan-relocation-and-final-purge` | Inventory legacy imports/flags, move remaining live `_pipeline/` behavior, delete only proven-dead graph-era surfaces. | Destructive/high-risk final purge. | Yes. Must not start before inventory and prior milestones. |

Mechanical-ish milestones: M2 and M6.  
Risky milestones: M1, M3, M3.5, M4, M5, M7.  
Milestones that directly depend on branch state: all of them, because cleanup lacks the native-runtime substrate and the epic source artifacts.

## Branch And Spec Readiness Details

`chain.yaml` currently declares:

- `base_branch: main`
- `merge_policy: auto`
- `driver.auto_approve: true`
- `driver.require_clean_base: true`
- `driver.robustness: thorough`
- per-milestone `profile: partnered-5`
- M3.5, M4, M7 use `robustness: extreme`, `depth: max`

Consequences:

- It is not configured to run from `python-shaped-workflow-authoring-cleanup`.
- Auto-merge plus auto-approve is too aggressive for this destructive migration unless the base branch and prerequisites are unquestionably right.
- `require_clean_base` will try to enforce clean milestone bases; stale local chain state or dirty worktrees make this fragile.
- The spec should move under a committed briefs directory and should not depend on an ignored `chain.yaml`.

Known artifact problems:

- `briefs/native-python-pipelines-completion/chain.yaml` is ignored by `.gitignore` and untracked.
- `native-python-pipelines` contains `briefs/native-python-pipelines-completion/.megaplan/plans/.chains/chain-329de243c34c.json`, a committed generated chain-state artifact with `current_milestone_index: 0`. This should not be part of a clean launch source.
- The actual committed milestone briefs are on `native-python-pipelines`; `python-shaped-workflow-authoring-cleanup` has none of them.

## Branch Cleanup Table

Ancestry checks used:
- merged into cleanup/main via `git merge-base --is-ancestor`
- patch equivalence via `git cherry`
- PR state via `gh pr list`
- worktree status via `git worktree list --porcelain` and targeted `git status`

No branches were merged, deleted, reset, or checked out.

| Branch/ref | Status | Action |
| --- | --- | --- |
| `python-shaped-workflow-authoring-cleanup` | Active requested base; pushed at `57eec327`; contains M1-M8 authoring cleanup and anchors merge, but no native completion artifacts. | Keep. Do not launch native completion from it until prerequisite artifacts/code are ported and spec base is fixed. |
| `python-shaped-workflow-authoring` | Ancestor of cleanup; no patch-unique commits vs cleanup. | Safe delete after confirming no external reference. |
| `python-shaped-workflow-authoring-m1-contract-grammar` | PR #96 merged, but local branch has 1 extra commit adding `.megaplan/system_logs/*.json`; remote version is ancestor of cleanup. | Delete local extra log commit or archive logs, then delete branch. Remote safe after normal branch cleanup. |
| `python-shaped-workflow-authoring-m2-compiler-core` | PR #97 merged; ancestor of cleanup; no patch-unique work. | Safe delete local/remote. |
| `python-shaped-workflow-authoring-m3-control-flow` | PR #98 merged; ancestor of cleanup; no patch-unique work. | Safe delete local/remote. |
| `python-shaped-workflow-authoring-m4-megaplan-migration` | PR #100 merged; ancestor of cleanup; no patch-unique work. | Safe delete local/remote. |
| `python-shaped-workflow-authoring-m5-validator-cli` | PR #103 merged; ancestor of cleanup; no patch-unique work. | Safe delete local/remote. |
| `python-shaped-workflow-authoring-m6-explain-shipped` | PR #104 merged; ancestor of cleanup; no patch-unique work. | Safe delete local/remote. |
| `python-shaped-workflow-authoring-m7-runtime-conformance` | PR #105 merged; ancestor of cleanup; pinned by worktree `/Users/peteromalley/Documents/.megaplan-worktrees/python-shaped-workflow-authoring`, clean. | Remove worktree if no longer needed, then safe delete local/remote. |
| `python-shaped-workflow-authoring-m8-generated-assets` | PR #107 merged; ancestor of cleanup; no patch-unique work. | Safe delete local/remote. |
| `native-python-pipelines` / `origin/native-python-pipelines` | Key donor branch at `b6b4022f`; not merged into cleanup or main. Contains source plan, milestone briefs, native runtime substrate, and large implementation delta: 487 files changed vs cleanup. | Keep. This is the prerequisite/donor branch for any native completion launch. Do not delete. Decide whether to rebase/port onto cleanup or launch from a new integration branch based on it. |
| `native-python-epic` | Ancestor of `native-python-pipelines`; not merged into cleanup/main. | Safe to delete after retaining `native-python-pipelines`. |
| `native-python-m2-parity-pilot` / `origin/native-python-m2-parity-pilot` | PR #70 merged to main; ancestor of main, cleanup, and `native-python-pipelines`. | Safe delete local/remote. |
| `native-python-runtime-m1-foundation` | Branch commits are ancestors of main/cleanup/native donor, but pinned worktree `/Users/peteromalley/Documents/.megaplan-worktrees/native-python-runtime-m1-foundation` has extensive dirty/untracked state. | Do not delete worktree yet. Triage or checkpoint dirty work first; branch ref is safe only after that. |
| `native-python-epic-m3-hooks` / `origin/native-python-epic-m3-hooks` | PR #74 merged into `native-python-pipelines`, but branch is not an ancestor and has patch-unique handoff/artifact commits vs donor. | Not needed before launch if `native-python-pipelines` is retained. Review/preserve handoff artifacts if desired, then delete. |
| `native-python-m3-megaplan-hooks` / `origin/native-python-m3-megaplan-hooks` | Open draft PR #72 against `native-python-pipelines`; older duplicate/parallel line with 11 patch-unique commits vs donor. | Treat as stale/abandoned unless PR #72 is intentionally revived. Do not merge before epic without a targeted review; close/delete after confirming supersession. |
| `native-python-epic-m4-main-megaplan` | PR #75 merged into `native-python-pipelines`; local branch is behind origin by 2; patch-unique vs donor due squash/lineage differences. | No pre-epic merge needed. Delete after confirming no unique artifacts needed. |
| `native-python-epic-m4-engine` | Pinned by `/Users/peteromalley/Documents/.megaplan-worktrees/native-python-pipelines`; related to M4 line, not merged to cleanup/main. | Keep only if that worktree is still a reference. Otherwise delete after comparing with `native-python-pipelines`. |
| `native-python-m5-run` | Ancestor of `native-python-pipelines`; no patch-unique work vs donor. | Safe delete local branch. |
| `native-python-m5a-parallel-panels` / `origin/native-python-m5a-parallel-panels` | PR #78 merged into `native-python-pipelines`; local branch is ahead 1 and pinned by dirty worktree `/Users/peteromalley/Documents/.megaplan-worktrees/native-pipeline-epic-run6` with many modified/untracked files. | Do not delete yet. Preserve or intentionally drop the dirty worktree first. Remote is merged; local needs triage. |
| `native-python-epic-m4-engine` worktree alias | `/Users/peteromalley/Documents/.megaplan-worktrees/native-python-pipelines` is clean at `474d1fa3`. | Stale reference candidate; remove only after donor branch decision. |
| `native-pipeline-epic` worktree | Clean worktree at `native-python-epic`, ancestor of donor. | Safe remove after keeping donor. |

Related stashes:

- `stash@{1}` on `native-python-pipelines`: skill typechanges.
- `stash@{2}` on `native-python-pipelines`: require_clean_base M1 platform contract.
- `stash@{3}` on `native-python-pipelines`: pre-merge engine WIP.
- `stash@{4}` on `native-python-m5a-parallel-panels`: native_panel WIP before T3.
- `stash@{6}` on `native-python-m3-megaplan-hooks`: WIP on donor branch before epic launch.

These stashes are not safe to drop until reviewed. They may contain exactly the kind of loose prerequisite work that would otherwise be lost during branch cleanup.

## Recommended Launch Sequence

1. **Stop treating the current checkout as the launch base.** Switch deliberately to a clean launch branch only after deciding the base. Current checkout is `anchors-north-star-refinement`, not `python-shaped-workflow-authoring-cleanup`.
2. **Create `native-python-working-tree` from `python-shaped-workflow-authoring-cleanup`** and do all integration/reconciliation there. Do not run directly from cleanup yet.
3. **Port or merge the `native-python-pipelines` donor branch into that integration branch**, resolving the 487-file delta intentionally. At minimum, port the native runtime substrate and the source docs/briefs; do not blindly import committed generated chain state.
4. **Make the epic inputs committed and clean.**
   - Commit `briefs/native-python-pipelines-completion/chain.yaml` or move the chain under `.megaplan/briefs/native-python-pipelines-completion/chain.yaml`.
   - Commit the 8 milestone briefs.
   - Commit `docs/arnold/pipelines/migration-completion-plan-v4.md`.
   - Remove committed `.megaplan/plans/.chains/*` state from source briefs.
5. **Fix the chain spec before launch.**
   - Set `base_branch: working-branch` or the new integration branch, not `main`.
   - Add `anchors.north_star` pointing at a committed North Star doc, or explicitly set `driver.require_anchor: false` plus `driver.missing_anchor_ack`.
   - Reconsider `merge_policy: auto` and `driver.auto_approve: true`; this epic has destructive milestones and should likely start with review gates until M1/M3.5/M4 are proven.
6. **Triage dirty native worktrees and native stashes before deleting branches.**
   - Highest priority: `native-python-m5a-parallel-panels` dirty worktree and `native-python-runtime-m1-foundation` dirty worktree.
   - Review `stash@{1}`, `stash@{2}`, `stash@{3}`, `stash@{4}`, and `stash@{6}`.
7. **After integration, run parser/status validation again** from the intended branch:
   - `python -m arnold_pipelines.megaplan chain status --spec <committed-chain.yaml>`
   - direct spec parser check that every `idea:` path exists
   - no `chain start` until status, anchors, base branch, and worktree cleanliness are correct.
8. **Then launch one milestone only first**, with explicit operator review:
   - `python -m arnold_pipelines.megaplan chain start --spec <spec> --one`
   - only after the above fixes, and only from the chosen clean base/integration branch.

Safest base branch: **`native-python-working-tree`, created from `working-branch` with `native-python-pipelines` intentionally reconciled into it**. At the end of the epic, merge `native-python-working-tree` back into `working-branch` so the editable install advances cleanly. Running from `main` would ignore the requested editable branch; running from the old cleanup branch as-is is missing the native substrate and source artifacts.

## Applied Prep State

As of the prep pass that created this note:

- `working-branch` is the editable-install base branch.
- `native-python-working-tree` branches from `working-branch`.
- `briefs/native-python-pipelines-completion/chain.yaml` is intended to be committed as a real source spec, not left as ignored local state.
- The native completion chain should target `native-python-working-tree`, declare `anchors.north_star: NORTHSTAR.md`, use relative `idea:` paths, and keep review gates enabled until the risky runtime milestones are proven.
