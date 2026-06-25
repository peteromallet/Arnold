# M0: Loose Work Baseline

## Outcome

The repo has a machine-checkable cleanup baseline before any single-root code migration begins. Every known loose-work item is either landed, archived, deleted, or explicitly classified as an operational temporary exception with a removal trigger.

## Scope

In:

- Verify local `main` contains the native Python completion merge and cleanup commits recorded in `docs/arnold/loose-work-cleanup-disposition-20260625.md`.
- Verify local git status is clean apart from intentional plan files.
- Reconfirm branch/worktree disposition for all Arnold-local branches, stashes, worktrees, detached heads, and generated chain state.
- Add a small script or documented command set that detects the recurring `_codex_skills/*/SKILL.md` symlink contamination before commits.
- Decide the external old snapshot: `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` should be pushed to `archive/typescript-bot-era`, verified, and then deleted locally unless the push fails.
- Keep `/Users/peteromalley/Documents/.megaplan-worktrees/native-python-pipelines-completion-thread2` only while the active external Reigh process still uses it. Record the PID/process trigger for deletion.

Out:

- Do not migrate Megaplan code in this milestone.
- Do not touch `banodoco/reigh-app` worktrees except to document that they are outside Arnold cleanup.
- Do not delete the old TypeScript snapshot without archiving if its commits are not reachable from a remote ref.

## Locked Decisions

- The completed native Python epic is already landed onto local `main`.
- The dirty `megaplan-single` implementation was rejected as unsafe.
- The single-root direction is correct and tracked by ticket `01KVZZ45DAZW9P5H4JA66JWNY3`.
- Old TypeScript Arnold is a different product history, not a source for Python Arnold code.

## Open Questions

- Has local `main` been pushed, or should the epic start from a named local integration branch?
- Is the active Reigh process still using `native-python-pipelines-completion-thread2` at execution time?

## Done Criteria

- A committed baseline report lists every remaining branch/worktree/snapshot and its action.
- `_codex_skills` symlink contamination is detectable and not present in git status.
- The old TypeScript snapshot is archived to a remote branch or blocked with a concrete error and next action.
- The current Arnold repo has no untracked/generated cleanup residue.
