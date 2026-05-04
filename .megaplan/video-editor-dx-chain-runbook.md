# Video Editor DX Megaplan Chain

Run one sprint at a time. Do not run these in parallel: Sprints 1, 4, and 5 all touch core timeline/store architecture.

## Launcher

Current working fallback:

```bash
PYENV_VERSION=3.11.11 PYTHONPATH=/Users/peteromalley/Documents/megaplan python -m megaplan config show
```

Use the editable Megaplan checkout at `/Users/peteromalley/Documents/megaplan` for all cloud commands. Older `uvx --from megaplan-harness megaplan` launchers may not include `cloud`, chain execution, or the current chain-state fixes.

## Serial Chain

1. Sprint 1: `.megaplan/video-editor-dx-sprint-01-idea.md`
2. Sprint 2: `.megaplan/video-editor-dx-sprint-02-idea.md`
3. Sprint 3: `.megaplan/video-editor-dx-sprint-03-idea.md`
4. Sprint 4: `.megaplan/video-editor-dx-sprint-04-idea.md`
5. Sprint 5: `.megaplan/video-editor-dx-sprint-05-idea.md`
6. Sprint 6: `.megaplan/video-editor-dx-sprint-06-idea.md`
7. Sprint 7: `.megaplan/video-editor-dx-sprint-07-idea.md`
8. Sprint 8: `.megaplan/video-editor-dx-sprint-08-idea.md`

Each sprint should start by reading the previous sprint's final notes/artifacts and should end with notes for the next sprint.

## Current Sprint 1 Local Run

Plan: `video-editor-dx-sprint-01`

State: `evaluated`

Result: Megaplan escalated after three thorough iterations. The plan improved from 10 flags to 3 flags, then regressed to 4 flags / 3 significant flags in iteration 3. Do not execute `plan_v3.md` as-is.

Useful artifacts:

- `.megaplan/plans/video-editor-dx-sprint-01/plan_v1.md`
- `.megaplan/plans/video-editor-dx-sprint-01/critique_v1.json`
- `.megaplan/plans/video-editor-dx-sprint-01/plan_v2.md`
- `.megaplan/plans/video-editor-dx-sprint-01/critique_v2.json`
- `.megaplan/plans/video-editor-dx-sprint-01/plan_v3.md`
- `.megaplan/plans/video-editor-dx-sprint-01/critique_v3.json`
- `.megaplan/plans/video-editor-dx-sprint-01/evaluation_v3.json`

Decision needed before continuing:

- Narrow Sprint 1 explicitly to a pure characterization/domain-boundary plan that preserves current UI load/save semantics, especially for clips with registry duration but missing `to`.
- Defer broad agent command result rewriting to Sprint 5, except for minimal diagnostics required to avoid lying about repaired `speed` writes.
- Treat AssetRegistry canonicalization and agent registry RPC writes as first-class scope if duration fallback depends on registry entries.

## Desired Cloud Command Shape

Use the cloud-capable Megaplan checkout:

```bash
PYENV_VERSION=3.11.11 PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  python -m megaplan cloud status --cloud-yaml .megaplan/video-editor-cloud.yaml
PYENV_VERSION=3.11.11 PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  python -m megaplan cloud attach --cloud-yaml .megaplan/video-editor-cloud.yaml
```

Cloud mode should run one sprint plan in `auto` mode with all phases routed to Codex. If project-level profiles are available, use `all-codex`; otherwise rely on the user config where every configured phase routes to Codex.

Project-level profile added at `.megaplan/profiles.toml` as `all-codex`.

## Friction Log

- The global `python` shim points at missing pyenv 3.8.10. Use `PYENV_VERSION=3.11.11` with `python -m megaplan`.
- Legacy fallback Codex planning has a persistent-session bug: `clarify` and `plan` share the same `codex_planner` session, but `codex exec resume` does not receive `--output-schema`, so `plan` can write markdown instead of JSON and fail parsing. Workaround: run `megaplan plan --plan <name> --agent codex --fresh` after `clarify`.
- Legacy fallback CLI gives no streaming phase progress for long Codex phases; only final success/failure is visible.
- The thorough legacy loop escalated without a clean way to ask for a targeted replan after max iterations. Available next steps are `override add-note`, `override force-proceed`, or `override abort`; there is no explicit `replan` command in this fallback CLI.
- Chain runtime state is now stored under `.megaplan/plans/.chains/` and should remain out of milestone branches.
- The cloud-capable/newer CLI should ideally support: automatic `--fresh` when resumed Codex phases cannot receive schema, phase heartbeats/log tails, project profile validation before deploy, and targeted replan after escalation.
