# Python-Shaped Workflow Authoring Contract

This document is the authoritative V1 contract for Python-shaped Arnold
workflow source. The grammar version is:

```text
arnold.workflow.authoring.v1
```

V1 is authoritative only for the first linear compiler slice. Megaplan native
representation conformance requires the V2 extensions for nested workflow
invocation, runtime-list fanout, typed loop outcomes, declared policy calls,
stable path identity, and wrapper rejection before composition-owned report rows
can close as implemented.

Python-shaped authoring is a source frontend over
`arnold.workflow.dsl.Pipeline` and the serialized `WorkflowManifest`. It is not
a new runtime. A workflow `.py` file is parsed and validated as source; the
compiler must not execute the file to discover topology.

The implementation source material named by the M1 brief under
`.megaplan/initiatives/workflow-manifest-runtime-cleanup/briefs/` is not available in this
checkout. This contract therefore proceeds from the available
`.megaplan/initiatives/python-shaped-workflow-authoring/briefs/m1-component-contract-grammar.md`,
the plan metadata, and the existing workflow DSL and manifest contracts.

## Source Shape

A V1 workflow source file is a normal Python module constrained to this grammar:

- An optional module docstring.
- `from __future__ import annotations`, if present, before other imports.
- `from arnold.workflow.authoring import workflow` and any other reserved
  compiler intrinsics defined by `arnold.workflow.authoring`.
- `from <component_module> import <component_name>` imports that resolve to
  typed workflow components.
- Literal module constants for workflow metadata, when needed by package
  discovery.
- Exactly one top-level workflow declaration using the reserved `workflow`
  intrinsic.
- A linear sequence of step declarations inside that workflow declaration for
  the first compiler slice.

The compiler records `grammar_version="arnold.workflow.authoring.v1"` in its
intermediate metadata and carries that value into generated fixture sidecars,
diagnostics, and manifest provenance.

## Workflow Syntax

The allowed V1 declaration is intentionally small:

```python
from arnold.workflow.authoring import workflow
from .steps import plan, execute, review

workflow(
    id="example",
    version="1.0",
    steps=[
        plan(id="plan"),
        execute(id="execute"),
        review(id="review"),
    ],
)
```

The equivalent decorator form is also valid V1 syntax when the decorated
function body is a linear sequence of step calls:

```python
from arnold.workflow.authoring import workflow
from .steps import plan, execute, review

@workflow(id="example", version="1.0")
def example():
    plan(id="plan")
    execute(id="execute")
    review(id="review")
```

The compiler lowers the ordered `steps` list to deterministic explicit-node DSL
data. The decorator form lowers identically after extracting the linear function
body into the same ordered step sequence:

- Each step call becomes an `arnold.workflow.dsl.Step`.
- Adjacent steps in the list become deterministic default `Route` values.
- The ordered collection becomes an `arnold.workflow.dsl.Pipeline`.
- `compile_pipeline()` lowers that DSL object to `WorkflowManifest`.

V1 linear source must not hand-author `Route`, `Pipeline`, or
`WorkflowManifest` objects. Those are backend data and compiler output.

## Component Contract

Workflow imports resolve to typed component exports. A component export is a
module-level object with a declared authoring kind and stable provenance. V1
recognizes these component kinds:

- `step`: a callable-shaped component that lowers to one workflow step.
- `prompt`: prompt text or prompt builder metadata referenced by a step.
- `policy`: bounded retry, budget, loop, fanout, timing, idempotency, effect,
  reducer, compensation, escalation, or authority policy data.
- `schema`: input, output, payload, or resume schema metadata.
- `subflow`: a nested workflow component that lowers to a manifest
  `SubpipelineRef`.

Component modules may be organized by kind, such as `steps.py`, `prompts.py`,
`policies.py`, `schemas.py`, and `subflows.py`, or by package-local feature.
The contract is the typed module-level export, not the filename. Package docs
may recommend kind-based files for readability, but validation must inspect the
exported component metadata.

A package may also use a local `components.py` module that re-exports typed
component descriptors for import ergonomics. This is a non-normative layout
convenience; it does not define a canonical directory structure or replace the
typed module-level export contract.

Component exports must provide enough information for static validation to know
their kind without executing workflow source. Later code may encode that with
dataclasses, frozen descriptors, or equivalent typed objects in
`arnold.workflow.authoring`, but V1 source cannot depend on generated catalogs
as editable truth.

## Import Rules

Workflow `.py` imports are the user-facing source of truth for dependencies.
The compiler validates imports from the parsed AST and resolver metadata.

Allowed imports:

- Reserved compiler intrinsics from `arnold.workflow.authoring`.
- Relative or absolute imports that resolve to typed workflow components.
- Aliased component imports, when provenance records the original
  `module:qualname` and the local alias.

Rejected imports:

- Runtime and execution modules, including `arnold.execution`.
- Legacy and native authoring surfaces, including `arnold.pipeline.native`,
  `_pipeline`, `stages`, native projection, and compatibility shims.
- Builder or fluent APIs, including public `Stage`, `Edge`, `PipelineBuilder`,
  `Pipeline.builder()`, decorators, and generator-style workflow bodies.
- Direct imports of `WorkflowManifest` or manifest constructors from workflow
  source.
- Generated catalogs as editable source of truth.
- Untyped Python helpers, live callables, closures, bound methods, callable
  instances, or objects whose component kind cannot be resolved statically.

Aliases are permitted only for workflow components. The compiler must preserve
both the local binding and the original import provenance. Aliasing or rebinding
reserved compiler intrinsics is invalid.

## Intrinsics And Shadowing

`arnold.workflow.authoring` owns the reserved compiler intrinsics. V1 reserves
`workflow`; it also reserves `loop`, `halt`, `suspend`, and `transition` for
future grammar versions. Source code must not assign to, redefine, import over,
or alias a reserved intrinsic.

Examples of invalid shadowing:

```python
from arnold.workflow.authoring import workflow as wf
workflow = object()
```

The compiler must report intrinsic shadowing as a source diagnostic rather than
falling back to runtime import behavior.

## Rejected Source Families

The following source families are outside V1 even if they can be made to run in
Python:

- Legacy pipeline packages under `arnold.pipeline.native`.
- Product-specific `_pipeline` modules and compatibility bridges.
- `stages` modules that expose old native stage shapes.
- Builder/fluent graph construction APIs.
- Generator, coroutine, callback, or live callable workflow bodies.
- Decorator workflow bodies that are not a linear sequence of step calls.
- Hand-authored `WorkflowManifest` JSON or Python objects.
- Generated component catalogs edited as source.

Generated catalogs may exist later, but only as derived artifacts from typed
component exports and workflow imports.

## Provenance Requirements

Every compiled object must retain enough source provenance to explain where it
came from:

- `grammar_version`: `arnold.workflow.authoring.v1`.
- Source file path.
- Source span for the workflow declaration.
- Source span for each imported component binding.
- Source span for each step call.
- Original component import `module:qualname`.
- Local alias, when an import uses `as`.
- Component kind and stable component ID.
- Generated DSL object ID and generated manifest node or edge ID.

The explicit-node DSL and `WorkflowManifest` remain normalized compiler output,
but their `source_span` and serializable `metadata` fields must preserve these
coordinates where the target dataclasses provide slots.

## Diagnostics

V1 diagnostics are stable, machine-readable records. Each diagnostic must
include:

- `code`: a stable string code.
- `severity`: at least `error` or `warning`.
- `message`: human-readable text.
- `grammar_version`: `arnold.workflow.authoring.v1`.
- `source_span`: when a concrete source location exists.
- Optional `import_module`, `import_name`, `local_name`, `component_kind`,
  `expected_kind`, and `provenance` fields.

The diagnostic code table defined by later implementation must cover at least:

- Invalid import source.
- Unsupported syntax.
- Missing workflow declaration.
- Multiple workflow declarations.
- Unknown component.
- Wrong component kind.
- Reserved intrinsic shadowing.
- Alias or provenance loss.
- Missing or malformed component export metadata.

Diagnostic codes `AWF010` through `AWF017` are reserved for future bounded
control forms and `loop`, `halt`, `suspend`, or `transition` intrinsic
semantics in M3 and later. V1 implementations must not use those codes to
imply that the current grammar accepts the corresponding source forms.

Diagnostics must be emitted from static parsing and resolver checks. They must
not require importing or executing workflow source.

Static prompt and resource dependency failures that can be proven from typed
component metadata are AWF authoring diagnostics. They report the authored call
site and name the missing prompt or resource dependency. Prompt template
rendering errors, model/resource lookup failures, and other failures that
depend on runtime state remain runtime diagnostics rather than AWF source
diagnostics.

## Acceptance Boundary

The first compiler slice accepts a linear workflow with valid component imports
and deterministic adjacent routes. It rejects unsupported imports, intrinsic
shadowing, missing workflow declarations, generated-catalog source, and legacy
or native authoring sources.

M3 bounded control forms, policy references, subflows, and the future
`loop`, `halt`, `suspend`, and `transition` intrinsic semantics must use a new
grammar version, such as `arnold.workflow.authoring.v2`, rather than expanding
`arnold.workflow.authoring.v1` in place. Any current ungated parser acceptance
for those constructs is implementation debt for M3 and is not part of this V1
contract.

The V2 authoring contract is a required deliverable for native Megaplan
composition before report-owned rows can become conformant. It must define the
accepted source syntax, diagnostics, and provenance for:

- nested workflow invocation with stable call-site identity;
- runtime-list `parallel_map` or equivalent typed dynamic maps, including
  mapper, reducer, item path template, and collection schema;
- typed loop outcomes or the accepted `break`/`continue` subset;
- declared policy-call metadata for retry, timeout, model routing,
  escalation, suspension, idempotency, and effects at step, subworkflow, and
  dynamic-map call sites;
- stable path identity for child workflows, repeated child calls, loop
  iterations, and dynamic-map items;
- wrapper rejection rules proving a readable call to one handler-backed stage
  is not sufficient for hidden Megaplan semantics.

V2 acceptance fixtures must include both source-level examples and lowered
runtime/manifest evidence. V2 rejection fixtures must cover magic-string
handler loop exits, handler-local profile/model routing, bespoke Megaplan-only
fanout helpers, direct manifest authoring, dynamic dispatch, cycles, and
single-handler wrappers for report-owned stages.
