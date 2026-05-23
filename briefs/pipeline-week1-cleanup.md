# Pipeline Week 1 Cleanup

## Outcome

Make pipeline modules describe topology, not compatibility shims or inline
workflow mechanics.

## Scope

In scope:

- Remove planning compatibility shims entirely.
- Keep `compile_planning_pipeline()` as the only planning compiler.
- Split doc and creative pipeline step shells into dedicated modules.
- Make the creative pipeline table-driven.
- Remove duplicate judges artifact path plumbing.
- Update focused tests and docs that referenced removed shim APIs.

Out of scope:

- Unrelated execution, review, worker, profile, and ticket changes already
  present in the worktree.
- Broad desloppify queue work.
- Public backward-compat wrappers for the removed planning APIs.

## Locked Decisions

- No shims.
- No compatibility wrappers.
- No legacy overlay path.
- First-class `doc` and `creative` pipelines are the mode path.
- Pipeline `__init__.py` files should primarily expose metadata and
  `build_pipeline()`.

## Done Criteria

- Targeted pipeline tests pass.
- `rg` finds no in-tree imports of `compile_pipeline_for`, `mode_overlay`,
  `robustness_overlay`, `with_prep_overlay`, `with_feedback_overlay`,
  `_step_for`, or `_RuntimeStep`, except historical docs that are explicitly
  updated or clearly archived.
- Unrelated dirty files are left untouched.
