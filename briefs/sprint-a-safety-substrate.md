# Sprint A — Worktree Execute Safety Substrate And Migration Prep

## Outcome

Prepare Megaplan for a hard migration from batch execute to worktree-native
execute by landing the non-execution substrate first: schema markers, custody
registry primitives, patch bundle capture/validation helpers, old-plan migration
commands, and read-only custody/orphan reporting.

This sprint must not replace execute yet. It creates the safe foundation that
Sprint B will consume.

## Locked Direction

Use the decisions in ticket
`.megaplan/tickets/01KS3DCH9Y1NTMTWH18S98RZT4-per-task-worktree-execute-model-replace-batches-with-isolated-per-task-scratch-w.md`
as settled product direction.

Do not re-litigate:

- worktree-native execute is the target;
- no long-lived `batch|worktree` runtime switch;
- task worktrees are local scratch;
- milestone branch is the integration surface;
- patch bundles are first-class durability artifacts;
- Git is authoritative for facts, coordinator registry for decisions, GitHub
  for remote lifecycle, sentinels as evidence only;
- old batch plans must be diagnosed, restarted, or closed explicitly.

## Scope In

1. Add state/schema markers needed to distinguish legacy batch execute from
   worktree-native execute. Existing plans should be readable enough to produce
   diagnostics.
2. Add coordinator-owned custody registry primitives under:

   ```text
   .megaplan/worktrees/registry/<run-id>.jsonl
   .megaplan/worktrees/patches/<run-id>/
   .megaplan/worktrees/custody-reports/<run-id>/
   .megaplan-worktrees/<run-id>/task-T1/
   ```

   Registry entries should be append-only JSONL with `prev_hash` and
   `entry_hash`.
3. Add patch bundle helper APIs for coordinator-side capture and validation.
   Workers must not supply patch files.
4. Implement temporary-index capture for tracked and untracked changes into one
   full-index binary patch.
5. Add validation helpers that reject absolute paths, `..`, symlink escapes,
   submodule-internal edits, and oversized binary hunks before apply.
6. Wire named secret scanner policy around `gitleaks`:
   - PR/pushed mode fails closed when unavailable or failing;
   - local-only mode can explicitly skip and records the skip.
7. Add `megaplan migrate-plan <plan> --diagnose|--restart|--close`.
8. Add read-only custody/orphan reporting sufficient to show managed worktrees,
   registry entries, patch bundles, and obvious drift. Report only; do not
   delete anything in this sprint.
9. Add `.megaplan-worktrees/` to init/gitignore behavior if not already covered.

## Scope Out

- Do not replace batch execute yet.
- Do not implement task worktree execution.
- Do not implement branch/PR lifecycle changes.
- Do not implement conflict-resolution commands.
- Do not add parallelism.
- Do not refactor Hermes sandbox/global state except where a narrow helper needs
  to avoid new coupling.
- Do not attempt multi-repo task routing, submodule patching, LFS optimization,
  stacked PRs, or bakeoff promotion changes.

## Done Criteria

1. Legacy batch plans are detected and produce a clear migration diagnostic.
2. `migrate-plan --diagnose`, `--restart`, and `--close` have focused tests.
3. Patch capture helper has real-Git tests for:
   - tracked modification;
   - untracked file;
   - rename;
   - mode change where platform supports it;
   - binary file.
4. Patch validation rejects traversal and symlink escape cases before any apply.
5. Registry append produces hash-linked JSONL entries and detects tampering in a
   focused test.
6. Custody/orphan report is read-only and never deletes work.
7. Existing `tests/test_init_in_worktree.py` and `tests/test_chain_in_worktree.py`
   still pass.

## Touchpoints

- `megaplan/execute/`
- `megaplan/_core/`
- `megaplan/store/plan_repository.py`
- `megaplan/cli.py`
- new worktree/custody helper module if useful
- tests under `tests/`

## Anti-Scope

Do not make broad cleanup decisions from branch-name patterns.
Do not allow model-writable files to grant cleanup authority.
Do not accept worker-written patch files.
Do not silently restart old batch plans under worktree semantics.
