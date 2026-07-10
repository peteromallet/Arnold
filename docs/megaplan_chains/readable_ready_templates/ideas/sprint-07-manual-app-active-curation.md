# Sprint 7: Manual And App-Active Curation

Implement Sprint 7 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Bring important manual/app-active routes to the higher elegance bar.

## Scope

- Declare or verify the exact app-active/required workflow list before curation.
- Build or use manual repair tooling with marker parsing, dry-run AST rewrites,
  per-file review packets, and separate mechanical vs semantic modes.
- Curate LTX first/last and other app-active video routes.
- Hoist constants and section long `build()` functions.
- Replace remaining avoidable positional handles.
- Add or repair public inputs and output artifacts.
- Extract repeated semantic subgraphs into named functions/blocks only when they
  make the caller easier to read and have testable inputs, outputs,
  requirements, and parity.
- Validate runtime contracts and app-specific semantic contracts.
- Update Reigh/vibe comfy consuming expectations where needed.

## Success Criteria

- App-active templates are readable, inspectable, and elegant Python.
- Public input/output contracts match Reigh/vibe comfy needs.
- No opaque subgraph remains in app-active strict-ready workflows.
- Manual-template repair changes are reviewable and split between mechanical and
  semantic edits.
