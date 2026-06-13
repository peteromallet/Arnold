# Sprint 6: Generated Template Regeneration

Implement Sprint 6 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Apply the new pipeline to existing generated templates category by category.

## Scope

- Populate the regeneration manifest before replacing any generated ready
  template. Each entry should include ready id, source path/hash, schema hashes,
  emitter version, overrides, marker, app-active/required status, and parity
  evidence.
- Regenerate generated image templates.
- Regenerate generated edit templates.
- Regenerate generated audio templates.
- Regenerate generated video templates in batches.
- Run parity, strict-ready warnings, formatting, and index checks per batch.
- Keep manual templates untouched except for explicitly approved repairs.
- Update template indexes and coverage manifests as needed.
- Use deterministic variable naming rules so unchanged source material does not
  produce noisy variable-name diffs.

## Success Criteria

- Generated templates no longer carry local helper boilerplate where strict-ready
  eligible.
- Avoidable `.out(n)` and schema-backed `widget_N` are substantially reduced.
- Generated templates compile equivalently to source material.
- No manual app-active workflow is overwritten.
- Regeneration provenance is present for every replaced generated template.
