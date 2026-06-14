# M5: Branch Retirement And Compatibility Cutover

## Outcome

Retire or park old branches/worktrees safely after useful content has landed, been deferred, or been explicitly rejected.

This is the cleanup sprint that makes the repository state match the plan.

## Scope

IN:

- Re-check branch retirement criteria in `docs/elegant-arnold-megaplan-split-plan.md`.
- Preserve dirty worktrees/stashes that still matter.
- Delete or archive branches only when criteria are satisfied and the user approves destructive cleanup.
- Update compatibility docs and remaining allowlists.
- Remove stale generated artifacts accidentally left in source trees.

OUT:

- No new architecture.
- No broad refactors.
- No destructive branch deletion without explicit approval.

## Locked Decisions

- `feat/arnold-clean-extraction` is the clean base.
- Broad quarry branches are not merge bases.
- Destructive git cleanup requires explicit user approval.

## Done Criteria

1. Branch/worktree/stash disposition is current and explicit.
2. Any branch proposed for deletion satisfies the documented criteria.
3. Compatibility docs reflect what remains supported.
4. Worktree is clean and `python -m pytest tests/arnold -q` passes.

## Megaplan Sizing

Recommended run: `solo/light/low`

Rationale: this is mostly mechanical verification and cleanup behind objective gates. Use a cheap driver; escalate only if a branch contains unexpected architectural payload.
