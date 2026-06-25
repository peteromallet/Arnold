# M5: Delete Legacy Root

## Outcome

The legacy `arnold/pipelines/megaplan` implementation root is gone or intentionally non-functional with a clear migration error. No business logic, generated residue, symlink churn, or stale bytecode remains under that path.

## Scope

In:

- Remove all remaining registered legacy implementation files.
- Remove or intentionally fail `arnold.pipelines.megaplan` imports according to the final contract.
- Delete temporary shims after their callers are migrated.
- Remove stale docs, generated assets, root `SKILL.md` files, `_codex_skills` symlinks, `__pycache__`, and deleted path references.
- Add final deletion/conformance gates: zero legacy imports except deletion tests, zero legacy business logic, clean wheel, clean docs/skills scan, clean git status.

Out:

- No permanent shims.
- No broad compatibility package.
- No last-minute behavior rewrites unrelated to deletion.

## Locked Decisions

- Final state is a clean break for `arnold.pipelines.megaplan`.
- The canonical package owns all supported behavior.
- The deletion gate is binary; partial deletion is not done.

## Done Criteria

- `arnold/pipelines/megaplan` is absent, or contains only the explicitly accepted migration-error stub.
- The legacy-file registry is empty or deleted.
- Built wheel excludes the legacy root and all canonical entrypoints work.
- Test/source/doc/skill scans show no unapproved legacy path usage.
- `git status --porcelain` shows no symlink/type churn.
