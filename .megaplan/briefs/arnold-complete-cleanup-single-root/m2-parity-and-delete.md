# M2: Parity And Delete

## Outcome

Supported Megaplan behavior is proven through canonical paths, then the legacy `arnold/pipelines/megaplan` implementation root is deleted or intentionally made non-functional with a clear migration error. No permanent shims remain.

## Scope

In:

- Canonical CLI smoke for init/status/run/config and supported subcommands.
- Chain compatibility: load/save state, chain start/status/resume, remote sync snippets, PR helper flows, and cloud/supervisor one-liners.
- Resume/status compatibility for existing `.megaplan/plans` and `.megaplan/briefs` state.
- Worker compatibility: Codex, Hermes, Shannon, process env, and engine-write isolation gates.
- Discovery/package compatibility: every migrated Megaplan pipeline row points at shipped canonical modules and builder targets resolve in editable and wheel installs.
- Docs/skills/generated assets sweep so humans and agents use `python -m arnold_pipelines.megaplan`.
- Installed-wheel smoke tests proving `arnold/pipelines/megaplan` is absent and all supported canonical entrypoints work.
- Remove all remaining legacy implementation files, temporary shims, stale docs, generated assets, root `SKILL.md` files, `_codex_skills` symlinks, `__pycache__`, and deleted path references.

Out:

- No permanent shims.
- No broad compatibility package.
- No last-minute behavior rewrites unrelated to deletion.
- Do not reintroduce previously rejected dirty changes such as local host turn-cap behavior.

## Done Criteria

- Canonical CLI, chain, resume/status, worker, discovery, docs, and wheel gates pass.
- `arnold/pipelines/megaplan` is absent, or contains only the explicitly accepted migration-error stub.
- Legacy registry is empty or deleted.
- Source/test/doc/skill scans show no unapproved legacy path usage.
- `git status --porcelain` shows no symlink/type churn.
