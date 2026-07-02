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

## V2 Authoring Contract

Grammar version:

```text
arnold.workflow.authoring.v2
```

V2 extends V1 with composition features required for native Megaplan
representation. It is additive and forward-looking: V1 source remains valid
under V2, and the compiler records `grammar_version` per source file. V2
acceptance and rejection fixtures target later milestones (M3 and beyond), but
the syntax categories and doctrine below are normative for all V2
implementations.

### Accepted Syntax

The following source forms are accepted under `arnold.workflow.authoring.v2`.
Each category includes the minimum syntax shape expected by the compiler and the
contract-level guarantee that must hold.

#### `@step` And `@workflow` Decorators

`@step` is the preferred V2 name for a callable workflow step. `@phase` remains
a valid compatibility alias. The decorator must carry:

- `name`: display and IR name; defaults to the Python function name.
- `id`: stable semantic identity for the step across compilation, projection,
  trace, and replay.
- `inputs`: declared input schema metadata.
- `outputs`: declared output schema metadata.
- `description`: optional descriptive text.

`@workflow` is the preferred V2 name for a callable workflow. `@pipeline`
remains a valid compatibility alias. The decorator must carry:

- `name`: display and IR name; defaults to the Python function name.
- `id`: stable workflow identity.
- `inputs`: declared workflow input schema metadata.
- `outputs`: declared workflow output schema metadata.
- `description`: optional descriptive text.

Both decorators satisfy the invocable interface defined in
`docs/arnold/native-composition-contract.md`. The compiler must be able to read
decorator metadata without executing the decorated body.

```python
from arnold.pipeline import step, workflow

@step(id="plan", inputs={"brief"}, outputs={"plan_doc"})
def plan(brief: str) -> str: ...

@workflow(id="review_loop", inputs={"draft"}, outputs={"final"})
def review_loop(draft: str) -> str: ...
```

#### Nested Workflow Calls

A workflow body may call another `@workflow`-decorated workflow as a child.
Each child call introduces a distinct call-site identity. The compiler must:

- record the child workflow stable ID;
- derive a stable call-site path segment from the authored call position;
- validate that the parent's output-merge rules are declared, not implicit.

```python
@workflow(id="parent")
def parent():
    plan(id="plan")
    child_review(id="review")        # child workflow call site
    finalize(id="finalize")
```

#### Repeated Child Call Sites

The same child workflow may be called more than once within a parent. Each call
site receives a distinct path segment. Repeated invocable IDs are not an error;
ambiguity is resolved by the full tree path, not by requiring unique invocable
IDs.

```python
@workflow(id="multi_review")
def multi_review():
    review(id="review_draft")       # call site 1
    revise(id="revise")
    review(id="review_final")       # call site 2 — same invocable, different path
```

#### Runtime-List `parallel_map`

`parallel_map` (or an equivalent typed dynamic-map construct) accepts a runtime
collection and fans out the same step or child workflow over each item. The
accepted syntax must declare:

- **mapper**: the step or child workflow applied to each item.
- **reducer**: how per-item outputs are merged (declared, not implicit
  last-writer-wins).
- **item path template**: how each item's call-site path appends an iteration
  coordinate to the static fanout segment.
- **collection schema**: the expected input collection shape and per-item
  schema.

```python
@workflow(id="batch_review")
def batch_review(checks: list[Check]):
    parallel_map(
        items=checks,
        step=critique_lens,
        reducer=merge_findings,
        path_template="critique/{item_id}",
    )
```

The compiler must reject runtime-list fanout that uses Megaplan-only bespoke
helpers or string-constructed dispatch instead of a declared native construct.

#### Loop Exits

V2 accepts a bounded `break`/`continue` subset or equivalent typed loop
outcomes. Loop exits must be explicit in source, not hidden inside handler
return strings consumed by a generic router.

Accepted forms:

- `break` and `continue` inside a `loop` body, when the loop condition and exit
  labels are statically visible.
- Typed loop-outcome declarations (e.g., `LoopOutcome.DONE`,
  `LoopOutcome.RETRY`) returned by the loop body step.

```python
@workflow(id="review_loop")
def review_loop():
    for attempt in loop(max_iterations=3):
        review(id="review")
        if review.passed:
            break
        revise(id="revise")
```

Rejected forms (see below): magic-string handler loop exits, handler-local
routing, and untyped outcome conventions.

#### Policy-Call Metadata

Steps, child workflows, and dynamic-map call sites may declare policy metadata
at the call boundary. Accepted policy categories:

- **retry**: max attempts, backoff, retryable error classes.
- **timeout**: per-call deadline or wall-clock limit.
- **model routing**: model selection criteria or tier-based routing.
- **escalation**: escalation target and trigger conditions.
- **suspension**: suspend/resume eligibility and resume schema.
- **idempotency**: idempotency key derivation and effect classification.
- **effects**: declared side-effect categories for replay safety.

Policy metadata may be declared inline at the call site or by reference to a
named policy object. Handler-local profile selection, ad hoc routing, and
implicit policy conventions are rejected.

```python
@workflow(id="robust_review")
def robust_review():
    review(id="review",
           retry=RetryPolicy(max_attempts=3, backoff="exponential"),
           timeout=TimeoutPolicy(seconds=120),
           model_route=ModelRoute(tier="quality"))
```

#### Stable Path Identity

Every call site produces a stable path segment. The full path is tree-shaped,
derived from authored parent-to-child call sites. Rules:

- Child workflow calls append the call-site segment to the parent path.
- Repeated child calls append distinct segments for each call site.
- Loop iterations append a monotonic iteration coordinate beneath the static
  body path.
- `parallel_map` items append an item coordinate beneath the static fanout
  segment.
- Replay must reproduce the same static path plus recorded iteration
  coordinates.

Path identity is semantic, not instance-based. It does not depend on runtime
object identity, memory addresses, or ad hoc string construction.

### Rejected Syntax

The following source forms are rejected under `arnold.workflow.authoring.v2`.
The compiler must emit an `AWF2xx` diagnostic for each rejected category.
Rejection is absolute: no implementation may accept these forms as valid V2
source, even if they can be made to execute.

#### Manual Graph Nodes

Hand-authoring `Stage`, `Edge`, `Route`, `PipelineBuilder`, or generator-style
workflow bodies is rejected. The compiler owns topology; source must not bypass
it with explicit graph construction.

```python
# REJECTED — manual graph nodes
pipeline = Pipeline()
pipeline.add(Stage(name="plan", handler=plan_handler))
pipeline.add(Edge("plan", "execute"))
```

#### Manual Path Strings

String-constructed paths, whether literal or computed, are rejected. Path
identity must be derived from authored call sites, not from ad hoc string
assembly.

```python
# REJECTED — manual path string
path = f"review/{check_id}/critique"
```

#### Trace Objects

Hand-authoring trace schema objects, trace record layouts, or audit field
structures in workflow source is rejected. Trace emission is a runtime concern;
source declares topology and metadata, not serialization shapes.

#### Validator Directives

Embedding ad hoc validator control language or imperative patch-up code directly
in workflow source is rejected. Validators validate; they do not author
topology, override routing, or mutate state outside declared effect boundaries.

```python
# REJECTED — validator directive in source
validate(lambda state: state["score"] > 0.8, on_fail="escalate")
```

#### Direct Manifest Authoring

Hand-authoring `WorkflowManifest` JSON or Python objects is rejected. The
manifest is compiled output, never hand-authored source of truth.

#### `Pipeline.native_program` Source-Truth Projection

Treating `Pipeline.native_program` as the source-authoritative representation
of product semantics is rejected. `native_program` is a dispatch substrate and
compatibility shell; it is not canonical source truth. Any implementation that
derives topology, stable IDs, or composition identity primarily from
`native_program` rather than from decorated source is non-conformant.

#### Megaplan-Only Helpers

Bespoke Megaplan helper functions that encode routing, loop exits, fanout,
suspension, override, or state transitions inside handler bodies are rejected.
This includes but is not limited to:

- magic-string handler return values consumed by a generic router;
- handler-local profile or model routing (`get_profile_for_check(...)` inside a
  handler);
- Megaplan-only fanout helpers that bypass the native `parallel_map` construct;
- single-handler wrappers that claim a readable call to one handler-backed stage
  is sufficient for hidden Megaplan semantics;
- dynamic dispatch through handler registries or string-keyed lookup tables.

```python
# REJECTED — Megaplan-only helper hiding topology
async def review_handler(state):
    if state["score"] < 0.5:
        return "REVISE"       # magic string consumed by hidden router
    return "DONE"
```

### Diagnostics

V2 diagnostics extend the V1 diagnostic code table with `AWF200` through
`AWF299`. Each diagnostic must include:

- `grammar_version`: `arnold.workflow.authoring.v2`.
- V1-required fields (`code`, `severity`, `message`, `source_span`).
- Optional `call_site_path`, `invocable_id`, `policy_category`, and
  `rejection_category` fields.

Reserved code ranges:

- `AWF200`–`AWF209`: rejected syntax categories (manual graph nodes, path
  strings, trace objects, validator directives, direct manifest authoring,
  native-program projection, Megaplan-only helpers).
- `AWF210`–`AWF219`: malformed accepted syntax (missing `parallel_map` reducer,
  undeclared loop exit, undeclared policy metadata).
- `AWF220`–`AWF229`: path identity violations (ambiguous call-site path,
  missing iteration coordinate, replay path mismatch).
- `AWF230`–`AWF239`: schema compatibility violations at composition boundaries.

### Provenance Additions

V2 adds these provenance fields beyond V1 requirements:

- `call_site_path`: stable tree path segment for each child call.
- `parent_path`: parent workflow path when present.
- `iteration_coordinate`: loop iteration or dynamic-map item coordinate.
- `policy_references`: named or inline policy objects at each call site.
- `grammar_version`: `arnold.workflow.authoring.v2`.

### Acceptance Boundary

V2 acceptance fixtures must include both source-level examples and lowered
runtime/manifest evidence. Each accepted-syntax fixture must compile without
`AWF2xx` diagnostics and produce the expected topology, stable paths, and
provenance fields. Each rejected-syntax fixture must produce exactly one
`AWF2xx` diagnostic matching the rejection category.

V2 rejection fixtures must cover at minimum:

- magic-string handler loop exits;
- handler-local profile/model routing;
- bespoke Megaplan-only fanout helpers;
- direct manifest authoring;
- dynamic dispatch;
- cycles;
- single-handler wrappers for report-owned stages.

V2 does not require all accepted syntax to execute correctly at runtime in M0.
Compilation, diagnostic, and provenance correctness are sufficient for the
bridge milestone. Full runtime execution equivalence is owned by M3 and later.
