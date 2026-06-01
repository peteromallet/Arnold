# M6: Package Rename And CLI Surface

## Outcome

Make `arnold` the canonical Python package and command surface, with `megaplan` exposed as Arnold's built-in robust planning/execution plugin.

## Scope

In:
- Update package layout and build metadata.
- Update console scripts and module entry points.
- Update imports to `arnold.*`.
- Update docs, examples, tests, and generated references.
- Ensure `arnold pipelines list`, `arnold run megaplan`, `arnold auto megaplan`, and `python -m arnold` work.
- If retained, keep `megaplan` only as a thin console forwarder/deprecation surface, not an importable package shim.
- Update cloud template rendering, chain command construction, and bakeoff subprocess commands to use canonical Arnold CLI or deliberate forwarder.

Out:
- Do not change architecture boundaries while doing broad rename.
- Do not reintroduce `megaplan` Python package compatibility.

## Locked Decisions

- Canonical package name is `arnold`.
- Canonical plugin name is `megaplan`.
- Generic Arnold runtime modules cannot import from `arnold.pipelines.megaplan`.

## Required Outputs

- Distribution-name decision and rationale: `arnold`, `arnold-ai`, or another package-index-safe name.
- Console-forwarder disposition for `megaplan`, including whether it survives long term and which compatibility tests cover it.

## Constraints

- This is broad but mechanical. It must happen after policy extraction.
- String-level gates must catch stale `megaplan init`, `megaplan auto`, `megaplan status`, `megaplan chain`, `python -m megaplan`, `.megaplan/plans`, `.megaplan/bakeoffs`, and `MEGAPLAN_*` in generic runtime targets.
- Plugin-local migration docs and deliberate compatibility surfaces may contain old strings explicitly.

## Done Criteria

- `python -m arnold` works.
- `arnold pipelines list` shows `megaplan`.
- `arnold run megaplan --describe` works.
- `arnold auto megaplan` works.
- `arnold megaplan <subcommand>` works if the plugin-direct command surface is retained.
- No source imports from the old top-level `megaplan.*` package remain. Plugin-internal code uses `arnold.pipelines.megaplan.*`; generic Arnold runtime modules still cannot import that namespace.
- Cloud/chain/bakeoff command construction is tested against canonical CLI or deliberate forwarder.
- Docs present a coherent Arnold/Megaplan model.

## Touchpoints

- `pyproject.toml`
- package directories
- CLI modules and scripts
- cloud templates/wrappers
- chain and bakeoff subprocess commands
- docs and tests

## Anti-Scope

- Do not refactor behavior while doing import renames.
- Do not leave duplicate packages with divergent code.
