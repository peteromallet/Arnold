# M1 - Semantic Checker Baseline

## Objective

Build the first production semantic checker and make the current
`workflow.pypeline` fail for the right reasons. This milestone prevents the
epic from starting with another native-looking wrapper.

## Anchors

- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-current-codebase-map.md`
- `docs/arnold/megaplan-native-oracle-synthesis.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`

## Files To Change And Instructions

- Add a semantic checker under an appropriate Arnold/Megaplan testable module.
  It must run against canonical `.pypeline` source and installed-package source.
- Add checker diagnostics for:
  - component-call skeletons;
  - `handler_ref` / `route_bindings`;
  - policy-as-route-table;
  - projected-native proof;
  - handler `current_state` / `next_step` / `route_signal` ownership;
  - runtime route dispatch via `route_dispatch` or manifest backend edge maps.
- Add row-evidence schema scaffolding for traceability rows.
- Add a baseline gap report documenting which current rows are source-owned,
  policy-owned, or still component/handler/runtime-owned.
- Add a compatibility-path inventory covering `workflow.py`, `build_pipeline()`,
  compatibility shells, manifest backend, route dispatch, auto, CLI handlers,
  direct handlers, and installed package paths.

## Verifiable Completion Criterion

- The current `workflow.pypeline` fails the semantic checker.
- At least one negative fixture represents the current component-call skeleton.
- The checker emits machine-readable evidence or failure records by row.
- The checker runs against checkout source and an installed package artifact.
- No later milestone can mark a row `implemented` without row-evidence schema.

## Native Parity Alignment

- This milestone should not extract product semantics yet.
- It is valid only if it prevents a future false closeout based on path
  existence, source shape, or generated reports.

