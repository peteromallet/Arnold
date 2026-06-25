# Goal: Cleanup, Then Workflow Manifest Runtime

## Rules

- Complete both epics in order: cleanup first, workflow manifest runtime second. The second epic must build directly on top of the completed cleanup result.
- Do not treat either epic as exploration, partial cleanup, or best effort. Keep going until both are complete, validated, merged, and unblocked.
- Use a fresh git worktree for each epic. Keep the editable install pointed at the active worktree.
- Use Codex subagents through the subagent launcher to investigate failures, repair behavior, update tests, and validate fixes.
- If anything blocks progress, fix the root cause and continue: harness, Arnold editable install, tests, scripts, docs, generated assets, wheel build, chain state, local environment, or target code.
- Preserve existing profile model selections exactly. Do not change, upgrade, simplify, swap, or normalize models.

## First Epic: Cleanup / Single Root

```text
/Users/peteromalley/Documents/Arnold/.megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml
```

Finish this first. Clean-break posture: eliminate the duplicate Megaplan implementation root, keep no permanent shims, make the canonical package authoritative, and close loose work decisively. Do not move on until the cleanup result is validated and becomes the actual base for the next epic.

## Second Epic: Workflow Manifest Runtime

```text
/Users/peteromalley/Documents/Arnold/.megaplan/briefs/workflow-manifest-runtime/chain.yaml
```

Run this only from the completed cleanup result. Manifest-first posture: the durable contract is the workflow manifest plus runtime/kernel behavior, not a product-specific hidden runner or compatibility bridge. Reconcile old native-pipeline assumptions at the source and continue.

## Execution

1. Create a cleanup worktree from `native-python-working-tree`.
2. Point the Arnold editable install at that worktree and run the cleanup chain.
3. Use status, logs, tests, git state, chain state, and Codex subagents to fix blockers until cleanup is complete.
4. Establish the completed cleanup result as the workflow manifest base.
5. Create a fresh workflow manifest worktree from that cleanup result, point the Arnold editable install at it, and run the second chain.
6. Keep going until both epics are complete and validated.

Do not pause after cleanup as if it were the end state. The intended progression is cleanup first, then workflow manifest runtime immediately on top.
