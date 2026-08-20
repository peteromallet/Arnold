# Arnold Loose-Work Consolidation Plan

Date: 2026-08-14
Repo: `/Users/peteromalley/Documents/Arnold` (origin: github.com/peteromallet/Arnold)
Status: awaiting per-item approval before execution

## 1. Rationale

The headline risk is NOT stale branches: the 20-commit active branch is pushed, and
9 of 11 local branches are fully merged residue. The real exposures, in order:

1. **7 uncommitted modified files in the current checkout** — a coherent "delete
   layered dispatch / arnold-repair-loop → arnold-babysitter" cleanup that exists
   ONLY in the working tree (not staged, not committed, not stashed, not pushed).
   One `git checkout .` away from gone. This is item zero.
2. **A stale in-progress cherry-pick** (`.git/sequencer`) — both queued commits
   (`f69bf6c880`, `abce65bef8`) are already ancestors of HEAD; `--continue` would
   fail with empty-commit errors. Must be cleared with `--quit` (never `--abort`,
   which would yank the branch back 24 commits to stale sequencer head `36a1098871`).
3. **222 stale remote-tracking refs** from five decommissioned agentbox remotes
   (`box-wa` x188, `box-r7` x5, `box-4ed` x1, `cloud` x7, `machine` x2). Only 96
   commits are not reachable from origin, and all are superseded July box
   self-repair-runtime work that main's Aug-12/13 rewrite iterated past.
4. **2 removable clean worktrees** — one detached scratch checkout, one on the
   fully-merged `editible-install` branch.
5. **1 open PR (#326)** whose evidence branch (`recovery/box-cleanup-20260807`)
   holds the only copy of 3 defensive commits → keep until #326 merges.
6. **4 stashes** — 3 superseded/junk (drop), 1 small lint fix (keep, apply later).

## 2. The landscape

- `main` == `origin/main` @ 4a830c6ac9 (2d old). Current branch
  `fixer/megaplan-maintenance-20260813` is 24 ahead, fully pushed to
  `origin/fixer/megaplan-maintenance-20260813` (0 unpushed).
- Prior cleanups: 2026-07-29/31 post-M11 consolidation, 2026-08-07 box cleanup
  (anchor `recovery/box-cleanup-20260807` + `box-snapshot/*-20260807` tags + PR #326).
- Epic record: 47 tickets in `.megaplan/tickets/`, ~60 epics in `.megaplan/epics/`.
  Cloud machine: no `cloud.yaml` in Arnold; all agentbox remotes deleted. The box
  itself is decommissioned; only refs remain. Codespaces: none. Hermes state.db:
  208M (no action). Orphan commits: fsck too slow, not counted.

## 3. Everything valuable → where it lands

| Work | Current state | Lands as |
|---|---|---|
| 7-file layered-dispatch cleanup (scripts + tests, 46+/46-) | uncommitted, working tree only | **Checkpoint commit on current branch** (highest-risk item, do first) |
| `stash@{2}` shard007 lint fix (verifier.py `# noqa: TRY004` + test narrowing, 3 files) | stash, still valid (noqa absent from HEAD/main) | **Apply to branch after sequencer cleared**; keep `arnold/` + `arnold_pipelines/` shim pair in sync |
| `fix/r7-fresh-child-launch-20260805` test (39-line `test_clearance_accepts_carried_tradeoff...`) | only unique artifact; production code already on main via `9c41d05546` | **Cherry-pick test only** onto current branch, then delete branch |
| Untracked keepers: `.megaplan/` tickets/audits/briefs/evidence/initiatives, `AGENTS.md`, `docs/omp-replaces-hermes-*.md`, `docs/fixer-recovery-evidence/*` | untracked, uncommitted | **Commit** onto current branch (or consolidation commit) |
| PR #326 (integrate/cleanup-ports-20260809, open) | open PR, base main | **Keep**; merge via normal PR flow |

## 4. Everything else → delete (with positive evidence)

| Item | Evidence it's safe |
|---|---|
| 9 local branches (base/editable-install, editible-install, epic-rt1-fixer-20260806, epic-workspace-20260805, fixer/fixer-unification-20260807, main-unification, merge/rt1-workspace, merge/unification-20260809) | ancestors of main, cherry+0 (verified by agent + my survey); no PRs reference them |
| 222 stale remote refs (box-wa/box-r7/box-4ed/cloud/machine) | `box-wa/main` = 0 unique vs origin; 85 ancestors of main; the 96 non-origin commits are superseded July work on files main rewrote Aug 12-13 (28% of touched files deleted from main); box-snapshot tags + recovery anchor capture the box state |
| `origin/editible-install` (67 unique) | July repair-custody/bootstrap work; 14 commits have patch-equivalents on main; rest superseded by worktree-first runtime + re-landed custody work |
| `origin/omp-migration` (30 unique, orphan-history fork) | **KEEP** — complete oh-my-pi migration (B1-B13): `workers/omp.py` RPC worker, dispatch threading, model/credential translation, sandbox decision, fork-clean release; ran green at B13; sole copy of the implementation + plan docs (`docs/omp-replaces-hermes-plan.md`/`todo.md`, also present untracked in working tree). NOT superseded: main kept hermes worker + grok, but the migration direction is still carried in the live working tree. Reclassify from delete → keep (user-confirmed). If the direction resumes: PR-then-merge; otherwise stays as reference. Never delete without explicit approval |
| `origin/main-unification`, `origin/megaplan/megaplan-maintenance/m2-authority` | main-unification tip fully merged; m2-authority is milestone bookkeeping (7 one-line chain.yaml re-pins), 1254 behind |
| `origin/fix/r7-fresh-child-launch-20260805` (remote) | production code already on main; only the test is unique → cherry-pick test, then delete |
| stash@{0} chain-spec-content | reverse-apply check exit 0 — fully present in working tree/HEAD |
| stash@{1} pre-main-ff-preserve | base is ancestor of main; docs byte-identical to main; code older than main |
| stash@{3} cloud runtime debris | regenerable incident projections/events; durable signal already published to GH issues |
| Untracked junk: 57 patch/scratch entries (`$tmp/`, `.codex-tmp-timeout/`, `.tmp_*.patch`, `.r7-*.patch`), `runs/demo/.native_wbc/` | agent scratch / runtime debris |
| `.target_edit/` (7 vibecomfy test files) | belongs to another repo (vibecomfy); nothing in Arnold references it |

## 5. Per-decision verdicts

- **keep**: `main`, current branch `fixer/megaplan-maintenance-20260813`,
  `origin/recovery/box-cleanup-20260807` (sole copy of PR #326's 3 commits —
  verified `git branch -r --contains` returns only that branch), PR #326,
  `origin/omp-migration` (sole copy of the completed oh-my-pi migration —
  orphan-history fork, no common ancestor with main; user-confirmed keep),
  stash@{2}, worktree `/Users/peteromalley/Documents/Arnold` (active).
- **cherry-pick-then-delete**: r7 test commit portion.
- **remove-then-delete**: worktree `/private/tmp/arnold-head-check4` (detached,
  commit 35d854d666 ancestor of pushed branch) → prune; worktree
  `Arnold-resident-restart-fix` (clean, branch fully merged) → remove worktree,
  delete local `editible-install`.
- **delete-with-approval (rm -rf, separate approvals)**: `Arnold-box-bundles-20260807`
  (2.5G, redundant — all heads on origin; caveat: preserve `dirty/` untracked tar
  ~2MB), `Arnold-validation-checkpoints` (164M; caveat: 3 tickets cite receipt
  paths — preserve cited receipts), `arnold-cloud-evidence-2026-07-05` (2.2M;
  own MANIFEST says redundant), `Arnold-cleanup-checkpoints` (30M; documented
  second copy on cloud).
- **out of scope**: `~/Documents/.megaplan-worktrees/astrid-*` (different repo —
  Astrid; `astrid-timeline-vlm` has 111 dirty files, its own loose work).

## 6. Corrections forced by investigation

- Survey said current branch is "20 ahead" — actually **24** (branch advanced
  during the fan-out; pushed, 0 unpushed).
- Survey assumed the in-progress cherry-pick was live work — the agents proved
  both queued commits are **already ancestors of HEAD**, making the sequencer
  stale. `--quit` (not `--continue`/`--abort`) is the fix.
- Survey's "125 unique remote refs" was a naive `--no-merged main` count. Set
  difference vs ALL origin refs cuts the real unique content to **96 commits**,
  and those are superseded (not unlanded treasure): the box's own repair-runtime
  debugging, rewritten on main after Aug 12.
- `box-wa/main` looked like an 81-commit unlanded fork; actually **0 unique vs
  origin** — its commits live on other origin branches.
- **`origin/omp-migration` was initially classified delete-with-tag** (brief 02:
  "main kept Hermes + added grok, direction abandoned"). User pushback
  ("was there not an integration of OMP somewhere?") prompted direct
  verification: the branch is an **orphan-history snapshot fork** (root
  `401c8f8112` "baseline: pre-migration Arnold tree") containing the complete
  B1-B13 oh-my-pi migration (`workers/omp.py` RPC worker, credential/model
  translation, sandbox decision) that ran green at B13 — the sole copy of that
  implementation, with plan docs still carried live in the working tree.
  **Reclassified to keep.** The "no common ancestor with main" detail was the
  tell: merge-base fails (exit 1), so "5809 behind" was a meaningless divergence
  metric, not evidence of supersession.

## 7. Execution order (lowest blast radius first)

1. **Checkpoint the 7 dirty files** on the current branch (commit "delete layered
   dispatch / arnold-repair-loop → arnold-babysitter"). Verify no conflict with
   the cherry-pick (proved disjoint: cherry-pick touches parallel_critique/auto/
   override files only).
2. **Clear the stale sequencer**: `git cherry-pick --quit`. Verify HEAD/index/
   worktree untouched.
3. Commit untracked keepers (`.megaplan/`, AGENTS.md, docs plans).
4. Apply `stash@{2}` (verifier.py lint fix), keep shim pair in sync. Commit.
5. Cherry-pick the r7 test only (`77b76e3a48` test file), adjust if needed. Commit.
6. Push current branch; run focused tests (`pytest tests/...` touched areas).
7. **Delete 8 fully-merged local branches** (`git branch -d`); remove worktree
   `/private/tmp/arnold-head-check4`, delete local `editible-install` + remove its
   worktree (order: worktree first).
8. **Delete remote branches**: `origin/editible-install`, `origin/omp-migration`
   (after tagging `297823fcb0`), `origin/main-unification`,
   `origin/megaplan/megaplan-maintenance/m2-authority`,
   `origin/fix/r7-fresh-child-launch-20260805` — batched `git push origin --delete`.
   Keep `origin/recovery/box-cleanup-20260807` until PR #326 merges, then tag
   `9c76105c81` + delete.
9. **Delete the 222 stale remote-tracking refs**:
   `git branch -r | grep -vE '^  origin/' | xargs git branch -rd`
   (reversible ~90d via reflog; optional pre-tag `archive/box-wa-decommission-20260814`
   on `cloud/custody-superfixer-bc3f` lineage tips).
10. Drop stash@{0}, stash@{1}, stash@{3} (one at a time).
11. Verify: `git branch`, `git branch -r`, `git worktree list --porcelain`,
    `git status --short --branch` — all clean.
12. Sibling dir deletions (`rm -rf`) — ONLY with explicit per-item approval and
    unique-work summary; preserve cited receipt paths and `dirty/` untracked tars.

## 8. Confidence & open questions

- **High confidence**: 8 local branch deletions, worktree removals, stale-ref
  sweep, stash drops — direct evidence (cherry+0, ancestors, set-difference,
  reverse-apply).
- **High confidence**: current branch + PR #326 + recovery anchor kept.
- **Medium**: stash@{2} apply needs the test suite to confirm the lint narrowing
  still matches current verifier.py (shim pair).
- **Open**: whether the r7 39-line test still passes against main's rewritten
  critique_custody.py (main's copy diverged via 9c41d05546 lineage) — verify on
  cherry-pick; drop test if it conflicts with current semantics.
- **Open**: sibling dir deletions need the human's call on preserving cited
  receipt paths (3 tickets) and `Arnold-box-bundles-20260807/dirty/` untracked
  tars before rm.
- **Out of scope to resolve here**: Astrid worktree loose work
  (`astrid-timeline-vlm`, 111 dirty).

## 9. Provenance

- Survey: main-thread git commands (2026-08-14 15:2x), all read-only.
- Fan-out: `fan.py` @ /tmp/loose-branches-deepseek-20260814-152404, 6 briefs,
  model deepseek:deepseek-v4-pro, toolsets terminal,file, all status=ok:
  - 01-stale-box-refs.md (70 tool calls) — delete all 222 refs
  - 02-origin-strays.md (72) — keep recovery anchor; delete editible-install,
    omp-migration, main-unification, m2-authority, r7 remote
  - 03-local-branches.md (30) — 8 delete, 1 cherry-pick-then-delete, 2 keep
  - 04-stashes-untracked.md (56) — stash verdicts + untracked disposition
  - 05-worktrees-siblings.md (36) — worktree removal order + sibling dirs
  - 06-current-checkout.md (16) — checkpoint-then-continue; stale sequencer fix
- Cross-checks (main thread): HEAD==origin (db48c27fa1), sequencer commits in
  HEAD, box-wa/main 0-unique, PR#326 commits only on recovery branch.
