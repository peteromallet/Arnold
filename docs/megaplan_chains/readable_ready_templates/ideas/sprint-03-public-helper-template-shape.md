# Sprint 3: Public Helper And Template Shape

Implement Sprint 3 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Make emitted Python look like maintainable workflow-builder code rather than a
copied graph dump.

## Scope

- Introduce shared ready-template helpers:
  `ready_workflow`, `ready_node`, `finalize_ready_template`, `bind_input`,
  `bind_output`.
- Settle the helper lifecycle. Either `bind_input`/`bind_output` are
  post-finalize contract-aware operations, or `finalize_metadata()` preserves
  them with tests.
- Add focused tests proving `set_input()` mutates the compiled API for
  helper-bound inputs before generated templates emit public input bindings.
- Remove local `_node` helper boilerplate from newly generated strict-ready
  templates.
- Enforce generated-template anatomy: imports, constants, metadata, optional
  blocks, `build()`.
- Add selective constant hoisting for public defaults, model names, output
  prefixes, guide strengths, and repeated presets.
- Add section comments for large generated workflows.
- Add style diagnostics for local helpers, long one-line node calls, unformatted
  output, and excessive generated variable names.
- Keep semantic variable naming conservative, deterministic, and parity-safe.

## Success Criteria

- New generated templates use shared helpers.
- Helper/input lifecycle is frozen before generated public input emission.
- Output is formatted and sectioned.
- Public helper API has focused tests.
- Generated code quality warnings exist before mass regeneration.
