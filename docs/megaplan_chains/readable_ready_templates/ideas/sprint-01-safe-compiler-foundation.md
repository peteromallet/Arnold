# Sprint 1: Safe Compiler Foundation

Implement Sprint 1 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Make conversion safe to run repeatedly before changing generated output style
broadly.

## Scope

- Add a baseline inventory command or report for ready-template readability
  issues: positional outputs, `widget_N` fields, UUID class types, local helper
  copies, missing outputs, generated/manual/app-active categories.
- Add parity harnesses before emitter changes:
  original normalized API vs emitted-template compiled API, widget-value
  snapshots, output artifact counts, and representative fixtures.
- Inventory legacy `vibecomfy convert` behavior and add golden tests before
  changing either path.
- Migrate useful legacy behavior into canonical `port convert`, then remove the
  old command with a clear migration error. A failing command handler is allowed;
  a behavioral wrapper is not.
- Add atomic conversion writes: temp file, validate/parity check, then replace.
- Add dry-run/diff mode for regeneration.
- Refuse to overwrite `# vibecomfy: manual` templates.
- Define the initial regeneration manifest schema and inventory report.

## Required Fixtures

- One simple image workflow.
- One edit workflow.
- One audio/TTS workflow.
- One Wan video workflow.
- One LTX workflow.
- One workflow with unresolved/opaque subgraph behavior.

## Success Criteria

- Failed conversion cannot overwrite a checked-in template.
- Generated output can be parity-checked before promotion.
- Legacy conversion behavior migrated to the canonical path is documented and
  tested.
- The old converter invocation fails with a clear migration message and no
  behavioral wrapper.
- Every generated ready template has known source provenance or is flagged for
  manual/reference review before regeneration.
- Docs and skills say new work uses `port check` / `port convert`.
