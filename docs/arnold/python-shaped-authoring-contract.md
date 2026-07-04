# Python-Shaped Workflow Authoring Contract

This document is the authoritative contract for Python-shaped Arnold
workflow source. The active grammar version is:

```text
arnold.workflow.authoring.v2
```

The `arnold.workflow.authoring.GRAMMAR_VERSION` constant reflects the active
grammar (`v2` as of M3). V1 linear source remains valid under V2; the compiler
records the grammar version per source file and V1 acceptance is a proper subset
of V2. This document describes both the V1 linear core and the implemented V2
composition extensions (nested workflow invocation, runtime-list fanout, typed
loop outcomes, declared policy calls, stable literal-ID path identity, and
wrapper rejection).

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
module-level object with a declared authoring kind and stable provenance.
The V2 grammar recognizes these component kinds (`arnold.workflow.authoring.ComponentKind`):

- `step`: a callable-shaped component that lowers to one workflow step.
- `prompt`: prompt text or prompt builder metadata referenced by a step.
- `policy`: bounded retry, budget, loop, fanout, timing, idempotency, effect,
  reducer, compensation, escalation, or authority policy data.
- `schema`: input, output, payload, or resume schema metadata.
- `subflow`: a nested workflow component that lowers to a manifest
  `SubpipelineRef`.
- `workflow`: an `@workflow`-decorated callable that may be invoked as an
  executable child workflow within a parent body. Distinct from `subflow` in
  that `workflow` carries the full V2 invocable interface (declared input/output
  schemas, stable ID, provenance).

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

- `grammar_version`: `arnold.workflow.authoring.v2`.
- Source file path.
- Source span for the workflow declaration.
- Source span for each imported component binding.
- Source span for each step call.
- Original component import `module:qualname`.
- Local alias, when an import uses `as`.
- Component kind and stable component ID.
- Generated DSL object ID and generated manifest node or edge ID.

V2 `ComponentProvenance` adds these fields beyond the V1 set:

- `call_site_path`: stable tree path segment derived from the authored literal
  `id=` at each child workflow call site. This is the canonical path identity
  source for nested composition.
- `parent_path`: parent workflow path when the component is invoked from within
  another workflow.
- `iteration_coordinate`: loop iteration index or `parallel_map` item coordinate
  (e.g., `"0"`, `"reviews/check-1"`), appended beneath the static call-site
  path.
- `policy_references`: tuple of named or inline policy object identifiers at the
  call site.

The explicit-node DSL and `WorkflowManifest` remain normalized compiler output,
but their `source_span` and serializable `metadata` fields must preserve these
coordinates where the target dataclasses provide slots.

## Diagnostics

V1 diagnostics are stable, machine-readable records. Each diagnostic must
include:

- `code`: a stable string code.
- `severity`: at least `error` or `warning`.
- `message`: human-readable text.
- `grammar_version`: the active grammar version (currently
  `arnold.workflow.authoring.v2`).
- `source_span`: when a concrete source location exists.
- Optional `import_module`, `import_name`, `local_name`, `component_kind`,
  `expected_kind`, and `provenance` fields.

The diagnostic code table implemented in `arnold.workflow.diagnostics.DiagnosticCode` covers:

- `AWF001_INVALID_IMPORT_SOURCE`
- `AWF002_UNSUPPORTED_SYNTAX`
- `AWF003_MISSING_WORKFLOW_DECLARATION`
- `AWF004_MULTIPLE_WORKFLOW_DECLARATIONS`
- `AWF005_UNKNOWN_COMPONENT`
- `AWF006_WRONG_COMPONENT_KIND`
- `AWF007_RESERVED_INTRINSIC_SHADOWING`
- `AWF008_ALIAS_PROVENANCE_LOSS`
- `AWF009_MALFORMED_COMPONENT_EXPORT`
- `AWF010`–`AWF023`: bounded control forms, routing, policy, subflow, and
  static dependency diagnostics.

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

Bounded control forms, policy references, subflows, and `loop`, `halt`,
`suspend`, and `transition` intrinsic semantics use V2 grammar
(`arnold.workflow.authoring.v2`) and are documented in the V2 Authoring
Contract section below. V1 linear source remains valid under V2 without
modification.

## V2 Authoring Contract

Grammar version:

```text
arnold.workflow.authoring.v2
```

V2 extends V1 with composition features required for native Megaplan
representation. It is additive: V1 source remains valid under V2, and the
compiler records `grammar_version` per source file. The syntax categories and
doctrine below are normative for all V2 implementations. V2 source compilation,
diagnostics, provenance, and native runtime execution of `parallel_map` and
nested workflows are implemented and tested as of M3.

### Accepted Syntax

The following source forms are accepted under `arnold.workflow.authoring.v2`.
Each category includes the minimum syntax shape expected by the compiler and the
contract-level guarantee that must hold.

#### `@step` And `@workflow` Decorators

`@step` and `@workflow` are native-shaped decorators imported from
`arnold.pipeline`. They declare callable components with stable identity,
declared schemas, and policy metadata. The compiler reads decorator metadata
statically without executing the decorated body.

`@step` declares a callable workflow step. Required and optional fields:

- `id` (required): stable semantic identity for the step across compilation,
  projection, trace, and replay.
- `inputs` (required): set of declared input schema field names.
- `outputs` (required): set of declared output schema field names.
- `description` (optional): descriptive text.

`@workflow` declares a callable child workflow that may be invoked as an
executable child within a parent body. Required and optional fields:

- `id` (required): stable workflow identity.
- `inputs` (required): set of declared workflow input schema field names.
- `outputs` (required): set of declared workflow output schema field names.
- `version` (optional): workflow version string.
- `policy` (optional): default policy metadata for the workflow.
- `description` (optional): descriptive text.

Both decorators satisfy the invocable interface defined in
`docs/arnold/native-composition-contract.md`. The compiled `NativeProgram`
records each decorated function as a `NativeFn` with stable `id`, input/output
schemas, and provenance metadata.

```python
from arnold.pipeline import step, workflow

@step(id="plan", inputs={"brief"}, outputs={"plan_doc"})
def plan(brief: str) -> str: ...

@workflow(id="review_loop", inputs={"draft"}, outputs={"final"}, version="1.0")
def review_loop(draft: str) -> str: ...
```

#### Nested Workflow Calls

A workflow body may call another `@workflow`-decorated workflow as an executable
child. Each child call must include a literal `id=` keyword argument that derives
a stable call-site path segment. The compiler must:

- extract the literal `id=` value and derive a stable call-site path segment
  from it (see "Stable Path Identity" below);
- record the child workflow's stable ID and declared input/output schemas;
- validate schema compatibility at the parent-child boundary (child input
  schema must be satisfiable by available parent state, child output schema
  must be compatible with parent merge expectations);
- emit a subpipeline instruction with `call_site_path` metadata and explicit
  `consumes`/`produces` bindings derived from child schemas.

Missing or non-literal `id=` values emit `AWF220`-series diagnostics rather
than falling back to qualname or source position.

```python
@workflow(id="parent", inputs={"brief"}, outputs={"report"})
def parent():
    plan(id="plan")
    review(id="review")        # child workflow call with literal id=
    finalize(id="finalize")
```

#### Repeated Child Call Sites

The same child workflow may be called more than once within a parent. Each call
site must have a distinct literal `id=`. The full tree path resolves identity;
repeated invocable IDs are not an error.

```python
@workflow(id="multi_review")
def multi_review():
    review(id="review_draft")       # call site 1 — id="review_draft"
    revise(id="revise")
    review(id="review_final")       # call site 2 — same invocable, different id
```

The compiler keys repeated child stages by call-site identity (the authored
`id=`) rather than by bare child name, ensuring that two calls to the same
workflow produce distinct stages in graph projection.

#### Runtime-List `parallel_map`

`parallel_map` is a first-class native IR/runtime op (`ParallelMapInstruction`,
`op='parallel_map'`) distinct from static `parallel`. It accepts a runtime
collection and fans out the same step or child workflow over each item. The
accepted syntax must declare:

- **`id`**: a literal `id=` keyword that derives a stable call-site path
  segment for the fanout node (required, same literal-ID rule as nested
  workflow calls).
- **`items`**: the runtime collection (must be a declared input parameter or
  a variable resolvable to a list at compile time).
- **`step`** (mapper): the step or child workflow applied to each item.
- **`reducer`**: how per-item outputs are merged (declared, not implicit
  last-writer-wins).
- **`path_template`**: a literal string template (e.g., `"reviews/{item_id}"`
  or `"revise/{index}"`) that derives per-item call-site coordinates. Non-literal
  or missing templates emit `AWF212`.

```python
from arnold.pipeline import parallel_map

@workflow(id="batch_review")
def batch_review(briefs):
    findings = parallel_map(
        id="review-all",
        items=briefs,
        step=plan,
        reducer=review,
        path_template="reviews/{item_id}",
    )
```

The compiler lowers `parallel_map` to `NativeProgram.parallel_map_blocks`
with `ParallelMapInstruction` metadata carrying `call_site_path`,
`path_template`, `mapper_id`, and `reducer_id`. Runtime execution preserves
list order, derives per-item `call_site_path` from the template or index,
collects mapper results, invokes the reducer on both populated and empty
lists, and filters workflow-mapper outputs through declared child schemas
before parent merge.

The compiler must reject runtime-list fanout that uses Megaplan-only bespoke
helpers or string-constructed dispatch instead of the declared native
`parallel_map` construct. Dynamic mapper, reducer, or path-template forms are
rejected at compile time.

#### Loop Exits

V2 accepts `loop(policy=..., reentry_id=...)` from `arnold.workflow.authoring`
followed by a `while True:` body. Loop exits must be explicit in source — the
accepted form is `break` (and `continue` where the compiler can validate it).
Magic-string handler return values consumed by a generic router are rejected
(`AWF205_MEGAPLAN_ONLY_HELPERS`). The loop policy declares iteration bounds and
reentry identity:

```python
from arnold.workflow.authoring import loop, workflow

@workflow(id="review_loop")
def review_loop():
    loop(policy=bounded_review_loop, reentry_id="review-all")
    while True:
        verdict = review(id="review", evidence=findings, policy=review_timeout)
        if verdict == "approved":
            break
        revise(id="revise")
```

The compiler accepts `break` as an explicit loop exit and records the loop
policy metadata on the enclosing iteration construct. Undeclared loop exits,
cross-boundary loops, and untyped outcome conventions are rejected.

#### Policy-Call Metadata

Steps, child workflows, `parallel_map` nodes, and `loop` constructs may declare
policy metadata at the call boundary via a `policy=` keyword argument. The
policy value is a reference to a named policy object (a typed component export
with `ComponentKind.POLICY`). Accepted policy categories include:

- **retry**: max attempts, backoff, retryable error classes.
- **timeout**: per-call deadline or wall-clock limit.
- **model routing**: model selection criteria or tier-based routing.
- **loop**: iteration bounds and reentry identity (`loop(policy=...)`).
- **escalation**: escalation target and trigger conditions.
- **suspension**: suspend/resume eligibility and resume schema.

Policy metadata must be declared by reference to a named policy object.
Inline policy construction, handler-local profile selection, ad hoc routing,
and implicit policy conventions are rejected.

```python
@workflow(id="robust_review")
def robust_review():
    review(id="review", policy=review_timeout)
```

Policy references are recorded in `ComponentProvenance.policy_references` and
on the corresponding native instruction metadata. Missing or malformed policy
metadata at policy-dependent call sites emits `AWF215`/`AWF216`.

#### Stable Path Identity

Every call site produces a stable path segment. The full path is tree-shaped,
derived solely from authored literal `id=` values. Rules:

- The only stable path source is the authored literal `id=` keyword at each
  call site. Missing or non-literal `id=` values emit `AWF220`-series
  diagnostics.
- Child workflow calls append the authored call-site `id=` segment to the
  parent path (e.g., `parent/review_draft`).
- Repeated child calls append distinct segments from distinct authored `id=`
  values — same invocable, different paths.
- `parallel_map` items append an item coordinate beneath the static fanout
  `id=` segment. The coordinate is derived from the `path_template` (e.g.,
  `reviews/check-1`) or a monotonic index when no template is provided.
- Loop iterations append a monotonic iteration coordinate beneath the static
  body path.
- Replay must reproduce the same static path plus recorded iteration
  coordinates.

Path identity is semantic and auditable from source alone. It does not depend
on runtime object identity, memory addresses, qualname strings, source-code
line ordering, or ad hoc string construction. This ensures stable path identity
across reorders, refactors, and replay.

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
`AWF239` (the `AWF240`–`AWF299` range is reserved for future milestones).
Each diagnostic must include:

- `grammar_version`: `arnold.workflow.authoring.v2`.
- V1-required fields (`code`, `severity`, `message`, `source_span`).
- Optional `call_site_path`, `invocable_id`, `policy_category`, and
  `rejection_category` fields.

#### Rejected Syntax (`AWF200`–`AWF209`)

| Code | Family | Description |
|------|--------|-------------|
| `AWF200_MANUAL_GRAPH_NODES` | `manual_graph_nodes` | Hand-authored `Stage`, `Edge`, `PipelineBuilder`, or generator bodies |
| `AWF201_MANUAL_PATH_STRINGS` | `manual_path_strings` | String-constructed or ad-hoc path assembly |
| `AWF202_VALIDATOR_DIRECTIVES` | `validator_directives` | Imperative validator control language in source |
| `AWF203_DIRECT_MANIFEST_AUTHORING` | `direct_manifest_authoring` | Hand-authored `WorkflowManifest` JSON or Python objects |
| `AWF204_NATIVE_PROGRAM_PROJECTION` | `native_program_projection` | `Pipeline.native_program` as source-authoritative representation |
| `AWF205_MEGAPLAN_ONLY_HELPERS` | `megaplan_only_helpers` | Bespoke helpers encoding routing, fanout, or loop exits in handler bodies |
| `AWF206_TRACE_OBJECT_AUTHORING` | `trace_object_authoring` | Hand-authored trace schema objects in workflow source |
| `AWF207_DYNAMIC_DISPATCH` | `dynamic_dispatch` | Handler registries, string-keyed lookup tables, or runtime callable resolution |
| `AWF208_SINGLE_HANDLER_WRAPPER` | `single_handler_wrapper` | Single-handler wrappers claiming a readable call to one handler-backed stage |
| `AWF209_RUNTIME_TOPOLOGY_MUTATION` | `runtime_topology_mutation` | Mutating topology or routing at runtime outside declared effect boundaries |

#### Malformed Accepted Syntax (`AWF210`–`AWF219`)

| Code | Family | Description |
|------|--------|-------------|
| `AWF210_MISSING_PARALLEL_MAP_REDUCER` | `missing_parallel_map_reducer` | `parallel_map` call without a declared reducer |
| `AWF211_INVALID_PARALLEL_MAP_ITEMS` | `invalid_parallel_map_items` | Non-collection or unresolvable `items` argument |
| `AWF212_INVALID_PARALLEL_MAP_PATH_TEMPLATE` | `invalid_parallel_map_path_template` | Non-literal or malformed `path_template` |
| `AWF213_UNDECLARED_LOOP_EXIT` | `undeclared_loop_exit` | Loop exit without a statically visible `break`/`continue` or typed outcome declaration |
| `AWF214_INVALID_LOOP_BOUNDARY` | `invalid_loop_boundary` | Loop body crosses a composition boundary that must be statically scoped |
| `AWF215_UNDECLARED_POLICY_METADATA` | `undeclared_policy_metadata` | Policy-dependent construct with missing `policy=` metadata |
| `AWF216_INVALID_POLICY_METADATA` | `invalid_policy_metadata` | Malformed policy reference or incompatible policy category |
| `AWF217_INVALID_WORKFLOW_INVOCATION` | `invalid_workflow_invocation` | Child workflow call with invalid arguments or shape |
| `AWF218_INVALID_WORKFLOW_REFERENCE` | `invalid_workflow_reference` | Reference to a non-workflow component where a workflow is required |
| `AWF219_INVALID_COMPOSITION_METADATA` | `invalid_composition_metadata` | Malformed or missing composition metadata at a boundary |

#### Path Identity Violations (`AWF220`–`AWF229`)

| Code | Family | Description |
|------|--------|-------------|
| `AWF220_MISSING_CALL_SITE_ID` | `missing_call_site_id` | Child workflow call without a literal `id=` keyword |
| `AWF221_AMBIGUOUS_CALL_SITE_ID` | `ambiguous_call_site_id` | Non-unique call-site `id=` within the same parent scope |
| `AWF222_NON_LITERAL_CALL_SITE_ID` | `non_literal_call_site_id` | Computed, variable, or dynamic call-site `id=` value |
| `AWF223_DUPLICATE_CALL_SITE_PATH` | `duplicate_call_site_path` | Two distinct call sites resolving to the same tree path |
| `AWF224_MISSING_ITERATION_COORDINATE` | `missing_iteration_coordinate` | Loop or fanout iteration without a declared coordinate |
| `AWF225_INVALID_ITERATION_COORDINATE` | `invalid_iteration_coordinate` | Malformed or non-monotonic iteration coordinate |
| `AWF226_MISSING_ITEM_COORDINATE` | `missing_item_coordinate` | `parallel_map` item without a declared coordinate |
| `AWF227_REPLAY_PATH_MISMATCH` | `replay_path_mismatch` | Replay path does not reproduce the expected static path plus recorded coordinates |
| `AWF228_INVALID_PARENT_PATH` | `invalid_parent_path` | Parent workflow path reference is missing or invalid |
| `AWF229_INVALID_CALL_SITE_PATH` | `invalid_call_site_path` | Call-site path segment is malformed or empty |

#### Schema Compatibility (`AWF230`–`AWF239`)

| Code | Family | Description |
|------|--------|-------------|
| `AWF230_CHILD_INPUT_SCHEMA_MISMATCH` | `child_input_schema_mismatch` | Parent-provided inputs do not satisfy child declared input schema |
| `AWF231_CHILD_OUTPUT_SCHEMA_MISMATCH` | `child_output_schema_mismatch` | Child declared outputs do not satisfy parent merge expectations |
| `AWF232_PARALLEL_MAP_ITEM_SCHEMA_MISMATCH` | `parallel_map_item_schema_mismatch` | Collection item shape incompatible with mapper input schema |
| `AWF233_PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH` | `parallel_map_reducer_schema_mismatch` | Reducer output shape incompatible with declared output schema |
| `AWF234_LOOP_EXIT_SCHEMA_MISMATCH` | `loop_exit_schema_mismatch` | Loop exit payload does not match declared exit schema |
| `AWF235_POLICY_SCHEMA_MISMATCH` | `policy_schema_mismatch` | Policy metadata shape incompatible with the call site |
| `AWF236_WORKFLOW_INPUT_BINDING_MISMATCH` | `workflow_input_binding_mismatch` | Workflow input binding references an undeclared or wrong-type input |
| `AWF237_WORKFLOW_OUTPUT_BINDING_MISMATCH` | `workflow_output_binding_mismatch` | Workflow output binding references an undeclared or wrong-type output |
| `AWF238_RESUME_SCHEMA_MISMATCH` | `resume_schema_mismatch` | Resume payload schema incompatible with suspension point |
| `AWF239_COMPOSITION_EFFECT_SCHEMA_MISMATCH` | `composition_effect_schema_mismatch` | Declared composition effect incompatible with boundary schema |

### Provenance Additions

V2 provenance is encoded in `arnold.workflow.authoring.ComponentProvenance`
with these fields beyond V1 requirements:

- `call_site_path` (`str | None`): stable tree path segment derived from the
  authored literal `id=` at each child call site. `None` for top-level
  declarations.
- `parent_path` (`str | None`): parent workflow path when the component is
  invoked from within another workflow. `None` for root workflows.
- `iteration_coordinate` (`str | None`): loop iteration index (e.g., `"2"`)
  or `parallel_map` item coordinate (e.g., `"reviews/check-1"`). `None` when
  not inside an iteration context.
- `policy_references` (`tuple[str, ...]`): tuple of named or inline policy
  object identifiers bound at the call site. Empty tuple when no policies are
  declared.
- `grammar_version`: `arnold.workflow.authoring.v2`.

### Acceptance Boundary

V2 acceptance fixtures must include both source-level examples and lowered
runtime/manifest evidence. Each accepted-syntax fixture must compile without
`AWF2xx` diagnostics and produce the expected topology, stable paths, and
provenance fields. Each rejected-syntax fixture must produce at least one
`AWF2xx` diagnostic matching the rejection category.

Implemented V2 fixtures cover these accepted families:

- Single `@workflow` with V2 grammar (M0 `valid_m0_single_workflow`).
- Nested child workflow invocation with literal `id=` (M0
  `valid_m0_nested_child_workflow` — deferred in M0, activated in M3).
- Repeated call sites with distinct literal `id=` values (M0
  `valid_m0_repeated_call_sites` — deferred in M0, activated in M3).
- `parallel_map` with `id=`, `items`, `step`, `reducer`, and `path_template`
  (M3 `valid_m3_parallel_map_loop_policy`).
- Loop with `break` exit and typed loop outcomes (M3
  `valid_m3_parallel_map_loop_policy`).
- Policy metadata at step call sites (`policy=review_timeout`) (M3
  `valid_m3_parallel_map_loop_policy`).
- Canonical Megaplan topology using general nested workflow and `parallel_map`
  constructs (M3 `valid_m3_canonical_megaplan_topology`).

Implemented rejection fixtures cover at minimum:

- Magic-string handler loop exits and handler-local profile/model routing
  (`AWF205_MEGAPLAN_ONLY_HELPERS`).
- Bespoke Megaplan-only fanout helpers bypassing `parallel_map`
  (`AWF205_MEGAPLAN_ONLY_HELPERS`).
- Direct manifest authoring (`AWF203_DIRECT_MANIFEST_AUTHORING`).
- Dynamic dispatch (`AWF207_DYNAMIC_DISPATCH`).
- Single-handler wrappers for report-owned stages
  (`AWF208_SINGLE_HANDLER_WRAPPER`).
- Non-literal path construction (`AWF201_MANUAL_PATH_STRINGS`).

V2 source compilation, diagnostic emission, and provenance field population
are implemented and tested. Runtime execution of `parallel_map` (collection
lookup, list ordering, per-item path derivation, mapper collection, reducer
invocation, schema-filtered merge) is implemented in the native runtime.
Full end-to-end runtime execution of all V2 constructs is owned by M4 and
later milestones; the M3 bridge milestone validates compiler correctness,
diagnostics, and provenance.
