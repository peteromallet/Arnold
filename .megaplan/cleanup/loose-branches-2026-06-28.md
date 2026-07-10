# Loose Branch Cleanup Decision Record - 2026-06-28

## Final kept/merged work

- `a5ddbbce` (`Consolidate watchdog and agentic pipeline fixes`): kept dirty main work covering watchdog, agent edit, graph inspection, porting/widget-shape fixes, docs, and tests.
- `84326529` (`Merge phase2 reorg loose work`): merged local `worktree-phase2-reorg` into `main`, including the accepted agent `edit.py` split, porting emitter/apply split, identity relocation, generated-node layout changes, and merge-resolution compatibility fixes.

`main` is pushed to `origin/main` at `84326529`.

## Verified live state

- `main` is clean and tracks `origin/main`.
- No stashes.
- Registered VibeComfy worktrees:
  - `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` on `main`
  - `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.claude/worktrees/phase2-reorg` on `worktree-phase2-reorg`
- External worktree `/Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run` is a different repository (`reigh-app`) and is excluded from VibeComfy cleanup.

## Validation after merge

- Agent-focused suite: `466 passed`.
- Porting edit suite: `278 passed, 3 skipped`.
- Broader targeted regression suite: `301 passed`, with one tolerated quarantined baseline failure in `tests/test_widget_shape_evidence.py::test_raw_scalar_widget_overflow_is_not_hidden_by_compacted_candidate_count`.
- `git diff --check`: clean.

## Dump candidates pending human confirmation

- `.claude/worktrees/phase2-reorg`: local worktree for payload already merged into `main`; clean and no longer needed after branch cleanup.
- local `worktree-phase2-reorg`: branch payload is merged into `main`; local branch is ahead of and behind `origin/worktree-phase2-reorg` because the remote was later advanced with a different stale milestone.
- `origin/worktree-phase2-reorg`: remote now points at `e3dd2626` (`m1-emitter: megaplan milestone (#115)`), a competing deeper emitter split. Local throwaway merge and subagent audit found high-conflict overlap with the already-accepted split, stale facade expectations, and no distinct runtime/product value worth merging wholesale.
- local `editible-install`: cloud editable-install sync branch at `716a8c00`; unique by ancestry only, useful patch payload superseded by `main`.
- `origin/editible-install`: remote copy of the same superseded editable-install sync branch.
- `origin/epic/god-file-splits/m2-agent-edit`: commits `43033912` and `8a299fad`; `43033912` has no tree changes, and `8a299fad` is a competing agent-edit split into an `agent_edit/` package. Throwaway merge and subagent audit found it conflicts with the accepted `edit_*` split and drops current behavior such as `_direct_existing_parameter_tweak_feedback`. Treat the package idea as a future fresh refactor proposal, not a branch to merge.

No branch, remote ref, or persistent worktree listed here has been deleted yet.
