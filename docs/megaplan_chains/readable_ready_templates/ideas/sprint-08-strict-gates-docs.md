# Sprint 8: Strict Gates And Documentation Finalization

Implement Sprint 8 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Make the new standard durable.

## Scope

- Promote high-confidence diagnostics from warnings to strict-ready errors.
- Add CI gates for required/app-active templates.
- Add broader CI checks for generated-template style where stable.
- Finalize README, authoring docs, template porting workbench docs, adding
  templates docs, and agent skill copies.
- Add example-driven acceptance tests:
  discover, inspect, set inputs, compile, dry-run/run, locate artifacts.
- Document remaining exceptions with owners and follow-up tickets.

## Success Criteria

- Future imports default to the clean path.
- Required/app-active workflows cannot regress into hidden widgets, unnamed
  outputs, missing public inputs, or opaque subgraphs.
- Agents have one documented path from raw workflow to ready template.
- Remaining non-compliant templates are explicitly categorized as reference,
  supplemental, blocked, or scratchpad-only.
