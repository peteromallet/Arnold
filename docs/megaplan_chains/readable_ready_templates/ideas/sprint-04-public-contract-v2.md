# Sprint 4: Public Inputs, Outputs, And Contract V2

Implement Sprint 4 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Make ready templates usable as public APIs without opening source.

This is the highest-risk API sprint. Start with a contract-shape freeze gate:
one canonical inspect JSON shape, one pre-run workflow contract shape, one
post-run artifact manifest shape, and documented behavior for legacy `inputs`.

## Scope

- Implement public input descriptors with type, default, required, range,
  aliases, target, and media semantics.
- Implement `bind_input` validation so bad targets fail early.
- Prove `set_input()` mutates the intended compiled API field.
- Implement public output/artifact descriptors via `bind_output`.
- Add additive contract fields: `public_inputs`, `public_outputs`,
  `graph_contract`.
- Keep legacy contract `inputs` intact during the migration window.
- Add contract v1/v2 round-trip and text/JSON CLI snapshot tests.
- Make `inspect --json` the canonical agent discovery surface.
- Make `doctor` and `port check` reuse the same structured model where relevant.
- Update list/inspect output so agents can discover inputs, outputs, model
  assets, custom nodes, artifact expectations, readiness class, app-active
  status, and blocked/reference markers.

## Success Criteria

- An agent can list settable inputs and expected outputs without reading Python.
- Public input aliases are explicit metadata.
- Output artifacts have stable semantic names.
- Pre-run output contracts and post-run artifact manifests are distinct.
- Old contract consumers keep working.
