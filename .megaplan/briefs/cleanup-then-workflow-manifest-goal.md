# Goal: Complete Cleanup, Then Workflow Manifest Runtime

## Rules

- Drive both epics to completion in sequence. First complete the Arnold complete cleanup / Megaplan single-root epic. Then, on top of that completed result, complete the Workflow Manifest Runtime epic.
- Do not treat either epic as a partial implementation, exploration, or best-effort cleanup. Keep going until both epics are complete, validated, merged, and no known blockers remain.
- Work in a new git worktree for each epic. Do not run the implementation directly from the existing checkout.
- Start the cleanup epic from `native-python-working-tree`. After cleanup is complete, start the workflow manifest epic from the branch or merge result that contains the completed cleanup.
- Keep the editable install pointed at the active epic worktree while each chain runs.
- Always use Codex subagents, via the subagent launcher, to explore and fix issues. Use them to investigate failures, inspect relevant code, repair broken behavior, update tests, validate fixes, and resolve anything blocking progress.
- Unblock and fix whatever gets in the way. If the harness, editable install, local environment, tests, scripts, chain runner, target project, docs, generated assets, wheel build, runtime conformance, chain state, or supporting code are broken, inspect the failure, fix the root cause, and continue.
- Do not change the models used in the profiles. Preserve existing profile model selections exactly. Do not upgrade, simplify, swap, normalize, or otherwise alter model choices while completing either epic.
- Do not stop at "mostly done." Every remaining branch, worktree, shim, stale import, generated artifact, doc reference, package/wheel surface, blocker, and chain-state issue must be migrated, deleted, resolved, or reduced to a concrete blocker with owner and trigger.

## First Epic: Cleanup / Single Root

```text
/Users/peteromalley/Documents/Arnold/.megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml
```

Finish this epic first.

The attitude is clean-break and no excuses: eliminate the duplicate Megaplan implementation root, preserve no permanent shims, make the canonical package authoritative, and close loose work decisively. If the epic exposes broken assumptions in the harness, editable install, docs, tests, generated assets, symlink hygiene, or package layout, fix those root causes and keep going.

Do not move to the second epic until the cleanup chain is complete, the integrated checkout is validated, and the next base branch clearly contains the cleanup result.

## Second Epic: Workflow Manifest Runtime

```text
/Users/peteromalley/Documents/Arnold/.megaplan/briefs/workflow-manifest-runtime/chain.yaml
```

Run this epic only after the cleanup epic is complete.

The attitude is manifest-first and relentless: the durable contract is the workflow manifest and the runtime/kernel behavior around it, not a product-specific hidden runner or compatibility bridge. If older native-pipeline assumptions conflict with the cleanup result or manifest north star, reconcile them at the source and continue.

## Execution

- Create a new worktree for the cleanup epic.
- Verify the editable install points at that cleanup worktree.
- Launch the cleanup chain from its chain file.
- Use `megaplan chain status`, plan status, logs, tests, generated artifacts, git state, and chain state to keep the run moving.
- When anything fails, use Codex subagents and direct inspection to find and fix the root cause. Then resume the chain.
- After cleanup completes, merge or otherwise establish the completed cleanup result as the base for the workflow manifest runtime epic.
- Create a fresh worktree for the workflow manifest runtime epic from that completed cleanup base.
- Verify the editable install points at the workflow manifest worktree.
- Launch the workflow manifest chain from its chain file.
- Keep going until the second epic is also complete and validated.

Do not pause between epics as if the first one were the end state. The intended progression is cleanup first, then workflow manifest runtime immediately on top.
