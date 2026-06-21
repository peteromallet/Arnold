# Workflow Authoring Contract (M2)

The M2 explicit-node authoring surface lives in `arnold.workflow` and
`arnold.patterns`.  It is the canonical way to author workflow topology for the
`arnold.workflow.manifest.v1` contract.  Existing `arnold.pipeline` graph
builder docs are legacy and remain supported at runtime, but they are not the
M2 canonical authoring target.

## Authoring Return Type

A package's `build_pipeline()` entrypoint must return a
`arnold.workflow.Pipeline` instance:

```python
from arnold.workflow import Pipeline, Step, Route


def build_pipeline() -> Pipeline:
    return Pipeline(
        id="example",
        version="1.0",
        steps=[
            Step(id="plan", kind="agent"),
            Step(id="review", kind="agent"),
        ],
        routes=[
            Route(id="plan-review", source="plan", target="review"),
        ],
    )
```

`WorkflowManifest` is compiler output.  Packages must not hand-author manifest
hashes, runtime state, or `WorkflowManifest` objects as package source.

## Package Metadata And Discovery

A discoverable M2 package must expose the module-level fields documented in
[`package-authoring-contract.md`](package-authoring-contract.md):

- `name`, `description`, `arnold_api_version`, `capabilities`, `driver`,
  `entrypoint`.
- `build_pipeline` callable returning `workflow.Pipeline`.
- Optional `default_profile`, `supported_modes`, `hooks`, `resume`,
  `build_continuation_pipeline`.

Packages must also ship a sibling `SKILL.md` describing the workflow's purpose,
inputs, outputs, capabilities, and suspension/resume semantics for agentic
consumers.

## Stable Authoring Surface

The public M2 surface is intentionally small and pure data:

- `arnold.workflow`: `Pipeline`, `Step`, `Route`, `Input`, `Output`,
  `Capability`, refs, policies, `compile_pipeline`, `inspect_manifest`,
  `dry_run`.
- `arnold.patterns`: `agent`, `external_call`, `merge`, `subpipeline`,
  `branch`, `loop`, `fanout`, `panel`, `retry`, `human_gate`, `critique`,
  `review`, `revise`, `tournament`.

These modules must not import `arnold.execution` or product Megaplan modules.
They reject live callables, closures, bound methods, and callable instances.

## Provisional And Internal Markers

- Constructors marked **public** are stable authoring targets.
- Constructors marked **provisional** lower to explicit nodes/routes but may be
  refined by later milestones; use them with the expectation of minor shape
  changes.
- Helpers marked **internal** are not part of the public contract.

## Inspect And Dry-Run Fields

The following fields are stable and safe to rely on across tools:

- `inspect_manifest`: `node_ids`, `refs`, `dependencies`, `capabilities`,
  `control_routes`, `suspension_points`, `unresolved_inputs`, `source_spans`,
  `hash_inputs`.
- `dry_run`: `id`, `manifest_hash`, `node_count`, `edge_count`,
  `possible_routes`, `unresolved_inputs`, `suspension_point_count`.

`to_dot` and `to_yaml` are diagnostic-only formatting helpers; their exact
string output may change.

## Loop And Reentry

Recursive behavior must be expressed with explicit bounded control topology:

- `WorkflowPolicy.loop.max_iterations` supplies the finite bound.
- `SuspensionRoute.reentry_id` names the stable resume cursor.
- Arbitrary directed graph cycles are invalid.

## Legacy Graph Docs

Docs and examples that teach `PipelineBuilder`, `Stage`, public `Edge`, fluent
chaining, or decorators are non-canonical legacy `arnold.pipeline` graph-builder
docs, not the M2 explicit-node contract.  They remain available for existing
runtime packages but should not be used for new M2 authoring.
