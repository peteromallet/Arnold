# M4: Behavior Parity Surfaces

## Outcome

Supported Megaplan behavior is proven through canonical paths before deletion. Editable installs and built wheels resolve the same implementation root and discovery targets.

## Scope

In:

- Canonical CLI smoke for init/status/run/config and any current supported subcommands.
- Chain compatibility: load/save state, chain start/status/resume, remote sync snippets, PR helper flows, and cloud/supervisor one-liners.
- Resume/status compatibility for existing `.megaplan/plans` and `.megaplan/briefs` state produced before this cleanup.
- Worker compatibility: Codex, Hermes, Shannon, process env, and engine-write isolation gates.
- Discovery/package compatibility: every migrated Megaplan pipeline row points at shipped canonical modules and builder targets resolve in editable and wheel installs.
- Docs/skills/generated assets sweep so humans and agents use `python -m arnold_pipelines.megaplan`.
- Installed-wheel smoke tests that prove `arnold/pipelines/megaplan` is absent and all supported canonical entrypoints work.

Out:

- Do not delete the legacy root in this milestone unless all final deletion gates are already present and green.
- Do not reintroduce local host turn-cap behavior or other previously rejected dirty changes.

## Locked Decisions

- Package discovery must not depend on files excluded from wheels.
- Skills are execution surfaces and must be kept as strictly as CLI docs.
- Compatibility means behavior parity for supported workflows, not keeping every historical import alive.

## Done Criteria

- Canonical CLI, chain, resume/status, worker, discovery, docs, and wheel gates pass.
- `rg 'python -m arnold\\.pipelines\\.megaplan'` returns only historical archive/brief references that are explicitly allowed.
- Remaining temporary shims, if any, are pure forwarding files with removal phases.
