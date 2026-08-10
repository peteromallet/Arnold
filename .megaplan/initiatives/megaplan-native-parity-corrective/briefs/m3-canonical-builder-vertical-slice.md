# M3 - Canonical Builder Vertical Slice

## Objective

Make `.pypeline` lowering runtime-load-bearing before broad extraction.
`build_pipeline()` currently risks discarding lowered topology and rebuilding
runtime behavior from `components.py`; this milestone closes that false-pass
path for at least one real slice.

## Files To Change And Instructions

- `arnold_pipelines/megaplan/workflows/planning.py`
  Make `build_pipeline()` consume lowered `.pypeline` topology for a real edge
  such as prep to plan, or introduce a new canonical builder for that slice.
- Compatibility/projection code
  Ensure compatibility shells consume the source-derived slice or are explicitly
  marked legacy for that slice.
- Semantic checker
  Add dead-delete mutation tests disabling old component-derived routing for the
  selected slice.
- Installed package tests
  Prove the installed package follows the same source-derived slice.

## Verifiable Completion Criterion

- The selected slice executes from lowered `.pypeline` topology.
- Disabling old component route bindings for that slice does not change the
  corrected deterministic trace.
- Runtime behavior, checker evidence, and installed-package evidence agree.

## Native Parity Alignment

- This milestone is the guardrail against decorative source extraction. Broad
  source migration should not proceed until this slice proves the builder seam.

