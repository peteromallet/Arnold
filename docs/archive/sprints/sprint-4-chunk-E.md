# Sprint 4 Chunk E — Delete `WORKFLOW`

Full Sprint-4 plan at `.megaplan/briefs/sprint-4-elegance.md`. Chunk E is the
inversion. Comes after A (typed edges), B (handler ports), C (auto
runtime), D (subloop + override).

## Problem

After Chunk C, `auto.py` walks the Pipeline. But the legacy
`_workflow_for_robustness` in `megaplan/_core/workflow.py` still
consults `WORKFLOW` + `_ROBUSTNESS_OVERRIDES` to compute robustness
overlays. The Pipeline + Overlays should be the only source.

## What ships in Chunk E

1. **Invert `_workflow_for_robustness`.** Rewrite its body to derive
   from `compile_pipeline_for(robustness, creative=creative,
   with_prep=with_prep, with_feedback=with_feedback)` instead of
   merging `WORKFLOW` + overrides. The function signature stays
   identical for back-compat with the dozens of callers.

2. **Convert `WORKFLOW` to a derived view.** Replace the literal dict
   in `megaplan/_core/workflow_data.py` with a function
   `compute_workflow_dict() -> dict[str, list[Transition]]` that
   walks the base Pipeline and reverses the structural compilation.
   `WORKFLOW` becomes `WORKFLOW = compute_workflow_dict()` at module
   import time.

3. **Same for `_ROBUSTNESS_OVERRIDES`** — derive from a base Pipeline
   plus per-level Overlays.

4. **Flip the default of `MEGAPLAN_PIPELINE_AUTO`** to `"1"` (the
   Chunk-C migration gate). The legacy path stays accessible via
   `MEGAPLAN_PIPELINE_AUTO=0` for one release as an emergency hatch.

5. **Migrate the existing parity tests** to assert the inverted
   relationship: the Pipeline is the source, the dicts are the
   derived view. `tests/test_pipeline_planning_parity.py` cases stay
   passing; intent comment changes.

## Out of scope

- Polish + docs (Chunk F).

## Constraints

- `git grep -nw WORKFLOW megaplan/` should show only:
  - The derivation function + the `WORKFLOW = ...` assignment in
    `_core/workflow_data.py`.
  - Re-export sites (`_core/workflow.py`, `_core/__init__.py`).
  - The parity tests + the Pipeline compilation site.
- Full `pytest tests/` stays green.
- Live `megaplan` must keep working.

## Acceptance

- `_workflow_for_robustness` body no longer references the
  `WORKFLOW` dict directly. (grep test.)
- `_ROBUSTNESS_OVERRIDES` is built from overlays. (grep test.)
- All existing parity tests pass with the inverted direction.
- `MEGAPLAN_PIPELINE_AUTO=0 pytest tests/` still passes (emergency
  hatch works).
- `MEGAPLAN_PIPELINE_AUTO=1 pytest tests/` still passes (default
  path).

## Operating principles

Same as Chunks A–D.
