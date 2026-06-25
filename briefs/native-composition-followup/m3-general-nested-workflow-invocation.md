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
  dynamic invocation, cycle detection, and child workflow metadata.
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

## Risks And Blockers

- Flattening child workflows for projection can accidentally destroy the
  composition information that M4 needs for static graph and tree traces.
- State merge semantics can become surprising if the child returns the entire
  copied parent state rather than explicit outputs.
- Multiple calls to the same workflow make bare name-based addressing unsafe.

## Dependencies

- Depends on M0, M1, and M2.
