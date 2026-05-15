# Sprint 4 Chunk F — Polish + docs + release

Full Sprint-4 plan at `briefs/sprint-4-elegance.md`. Final chunk after
A (typed edges), B (handler ports), C (auto runtime), D (subloop +
override), E (WORKFLOW deletion).

## What ships in Chunk F

1. **`docs/pipeline-architecture.md`** — the elegance writeup.
   Sections:
   - Primitive surface (Step / Stage / Pipeline / Edge / Overlay /
     Verdict / StepContext / StepResult / ParallelStage).
   - Three orthogonal extension axes (mode → PromptRegistry; slot →
     Profile; Overlay → graph transform).
   - Runtime layering (executor + RuntimePolicy modules).
   - Subloop + Override edge model.
   - How a new mode is added in <20 lines.
   - How `WORKFLOW` is derived from the Pipeline.
   - Worked example: build a 3× critique→revise pipeline from scratch.

2. **Update `docs/pipeline-resume.md`** for the typed-edge shape.

3. **Update `briefs/STATUS.md`** — Sprint 4 commit ledger, final
   pipeline test inventory, post-Sprint-4 caveats.

4. **Five new elegance-property tests**:
   - `tests/test_no_subprocess_shims.py` — grep-based.
   - `tests/test_no_string_packed_edge_labels.py` — grep-based.
   - `tests/test_auto_walks_pipeline.py` — checks `auto.py` imports
     + uses `run_pipeline_with_policy`.
   - `tests/test_subloop_and_override_branches.py` — introspects
     executor source.
   - `tests/test_workflow_dict_derived_from_pipeline.py` — asserts
     the inversion via attribute check on `WORKFLOW`.

5. **Tag the commit** as `v0.21.0` on `decomp/main`. **Do not** push
   to remote unless the user requests it.

## Out of scope

- New planning features.

## Constraints

- All Sprint 1–3 tests + all Sprint 4 A–E tests still pass.
- Live `megaplan` must keep working.
- All commits on `decomp/main`.

## Acceptance

- The 5 elegance-property tests pass.
- `docs/pipeline-architecture.md` exists and reads as a cohesive
  document.
- `briefs/STATUS.md` reflects Sprint 4 complete.
- A commit tagged `v0.21.0` exists on `decomp/main`.

## Operating principles

Same as Chunks A–E.
