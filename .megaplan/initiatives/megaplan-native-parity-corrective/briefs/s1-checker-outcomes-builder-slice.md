# S1 - Checker, Outcomes, Builder Slice

## Objective

Establish the anti-false-pass foundation in one busy sprint: semantic checker,
typed outcome/interface boundary, and a real source-derived runtime vertical
slice. This sprint absorbs the old M1, M2, and M3 without dropping any guardrail.

## Legacy 10-Sprint Source Mapping

- Absorbs `m1-semantic-checker-baseline.md`.
- Absorbs `m2-typed-outcomes-and-interfaces.md`.
- Absorbs `m3-canonical-builder-vertical-slice.md`.

The original briefs remain in this directory as source artifacts. Treat this
brief as the launch contract and the original three briefs as detailed scope
appendices.

## Anchors

- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-current-codebase-map.md`
- `docs/arnold/megaplan-native-oracle-synthesis.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`

## Work Required

- Build the first production semantic checker against canonical `.pypeline`
  source and installed-package source.
- Make the current component-call skeleton fail for the right reasons:
  component-call topology, `handler_ref`, `route_bindings`, policy-as-route
  table, projected-native proof, handler-owned `current_state` / `next_step` /
  `route_signal`, route dispatch, and manifest backend edge maps.
- Add row-evidence schema scaffolding. No later sprint may mark a row
  implemented without row-level source/policy/pure-body evidence.
- Add closed typed outcomes and retained-handler interfaces for gate,
  tiebreaker, review, override, suspension, halt, execute, and finalize.
- Confine raw string labels to compatibility serialization adapters.
- Add retained-handler purity/side-effect declarations and checker support.
- Make `.pypeline` lowering runtime-load-bearing for at least one real edge
  such as prep to plan. `build_pipeline()` must consume lowered topology for
  that slice or be replaced/quarantined for that slice.
- Add dead-delete mutation tests disabling old component-derived routing for
  the selected slice.
- Prove checkout source and installed package source behave the same for the
  selected slice.
- Produce baseline gap and compatibility inventory covering `workflow.py`,
  `build_pipeline()`, compatibility shells, manifest backend, route dispatch,
  auto, CLI handlers, direct handlers, and installed package paths.

## Verifiable Completion Criterion

- Current `workflow.pypeline` fails semantic checking before correction.
- At least one negative fixture captures the old component-call skeleton.
- The checker emits machine-readable evidence/failure records by row.
- Canonical source can branch on typed outcomes, and report-owned branches do
  not route on raw string literals.
- The selected runtime slice executes from lowered `.pypeline` topology.
- Disabling old component route bindings for that slice does not change the
  corrected deterministic trace.
- Runtime behavior, checker evidence, and installed-package evidence agree.

## Do Not Close If

- The checker only validates file existence or generated reports.
- `build_pipeline()` still silently rebuilds the selected slice from
  `components.py`.
- Any row gets an inherited `enabled` or `implemented` status from prior
  reports.
