# M3 - General Nested Workflow Invocation

## Objective

Generalize the nested workflow support proven by Megaplan so any native workflow
can invoke another native workflow as an invocable unit. The compiler, IR,
runtime, and graph projection should treat child workflows as first-class
composition nodes satisfying the M0 invocable interface, not as package-specific
behavior.

## Files To Change And Instructions

- `arnold/pipeline/native/decorators.py`
  Implement or finalize workflow metadata for stable unit IDs, declared inputs,
  declared outputs, and stable call-site diagnostics.
- `arnold/pipeline/native/compiler.py`
  Lower nested `@pipeline` / `@workflow` invocations into child workflow
  instructions with attached child programs and stable call-site path segments.
  Reject dynamic invocation forms that cannot be statically recovered.
  Add first-class runtime-list fanout support (`parallel_map` or equivalent)
  for selected critique/review checks and execute batches; literal-only
  `parallel([...])` / `native_panel(...)` support does not satisfy Megaplan's
  dynamic rows.
- `arnold.workflow.authoring` source frontend and
  `docs/arnold/python-shaped-authoring-contract.md`
  Implement the V2 source grammar and diagnostics needed for the same
  constructs. The native compiler/IR work is insufficient unless the
  Python-shaped authoring frontend accepts, rejects, and lowers the V2 source
  forms without executing workflow files.
- `arnold/pipeline/native/ir.py`
  Add or tighten first-class invocable/workflow metadata. Tooling should be able
  to query a unit's stable ID and declared interface without inspecting Python
  source.
- `arnold/pipeline/native/runtime.py`
  Execute child workflows with explicit parent-to-child input mapping and
  child-to-parent output merge semantics. Avoid ambient dict reach-through as
  the default contract.
- `arnold/pipeline/native/graph_projection.py`
  Project nested workflows in a way that preserves the compatibility shell
  without flattening away all composition information needed by tooling.
- `tests/arnold/pipeline/native/test_compiler.py`
  Cover nested workflow lowering, duplicate child names, stable IDs, unsupported
  dynamic invocation, cycle detection, child workflow metadata, runtime-list
  `parallel_map`, typed loop outcomes or accepted loop-exit substitute,
  declared policy-call metadata, and rejection of Megaplan-only helpers.
- `tests/arnold/workflow/` or the current source-frontend test location
  Add V2 authoring diagnostics and source fixtures for nested invocation,
  runtime-list maps, policy-call metadata, typed loop exits, dynamic dispatch
  rejection, cycle rejection, and wrapper rejection.
- `tests/arnold/pipeline/native/test_runtime.py`
  Cover parent/child execution, child state isolation, typed output merge,
  repeated child workflow use from multiple call sites, and depth-3 nesting.

## Verifiable Completion Criterion

- A workflow can invoke another workflow without wrapper glue.
- The same child workflow can appear at multiple call sites without ambiguous
  runtime identity.
- Unsupported dynamic dispatch and transitive self-inclusion cycles fail at
  compile/registration time with clear diagnostics.
- Parent workflows access child outputs only through the declared interface.
- Megaplan's M1 compositional declaration uses only the general support from
  this milestone after any temporary M1 support is removed.
- Megaplan fanout, execute batching, review fanout, typed loop exits, and
  policy calls use general native constructs. A bespoke Megaplan dynamic fanout
  helper is a blocking failure.
- The Python-shaped source frontend accepts the V2 constructs with stable
  provenance and rejects the V2 anti-patterns; compiler-only IR support is not
  enough to close this milestone.

## Native Representation Alignment

- Matrix rows owned or affected: Parallel critique lenses with fan-in; Tiebreaker researcher/challenger path; Dependency-aware execute batches; Review parallel checks/fan-in; Runtime-list iteration; Dynamic parallel map.
- Expected status change: Megaplan-only composition support must become general native support before rows can be considered implemented.
- Proof artifacts: nested invocation compiler/runtime tests, repeated child workflow tests, depth-3 nesting, runtime-list fanout fixtures for critique/review/execute, typed loop outcome fixtures, policy-call metadata fixtures, cycle/dynamic-dispatch rejection tests, and Megaplan-only helper rejection tests.
- False-pass guard: if fanout, tiebreaker, or execute batching work only through a bespoke Megaplan helper, the row remains a false pass.
- Deferrals: tree rendering/audit snapshots are M4; resume-from-path is M5; production worker hardening is platform M5.
- Canonical source paths/imports: M3 must remove or resolve every `TEMPORARY_MEGAPLAN_ONLY` compiler/runtime path listed by M1.

## Risks And Blockers

- Flattening child workflows for projection can accidentally destroy the
  composition information that M4 needs for static graph and tree traces.
- State merge semantics can become surprising if the child returns the entire
  copied parent state rather than explicit outputs.
- Multiple calls to the same workflow make bare name-based addressing unsafe.

## Dependencies

- Depends on M0, M1, and M2.
