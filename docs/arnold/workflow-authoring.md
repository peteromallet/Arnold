# Workflow Authoring Contract

The canonical authoring surface for Arnold workflows is ``arnold.workflow``.  A
shipped pipeline package exposes a ``build_pipeline()`` entrypoint that returns a
``arnold.workflow.Pipeline`` instance.  The compiler lowers that instance to a
neutral ``WorkflowManifest`` with deterministic hashes.

## Authoring Return Type

```python
from arnold.workflow import Pipeline, Step, Route, Input, Output, Capability


def build_pipeline() -> Pipeline:
    return Pipeline(
        id="example",
        version="1.0",
        steps=(
            Step(id="plan", kind="agent"),
            Step(id="review", kind="agent"),
        ),
        routes=(
            Route(id="plan-review", source="plan", target="review"),
        ),
    )
```

``WorkflowManifest`` is compiler output.  Packages must not hand-author manifest
hashes, runtime state, or ``WorkflowManifest`` objects as package source.

## Package Metadata And Discovery

A discoverable package must expose the module-level fields documented in
[`package-authoring-contract.md`](package-authoring-contract.md):

- ``name``, ``description``, ``arnold_api_version``, ``capabilities``, ``driver``,
  ``entrypoint``.
- ``build_pipeline`` callable returning ``workflow.Pipeline``.
- Optional ``default_profile`` and ``supported_modes``.

Packages must also ship a sibling ``SKILL.md`` describing the workflow's purpose,
inputs, outputs, capabilities, and suspension/resume semantics for agentic
consumers.

## Stable Authoring Surface

The public surface is intentionally small and pure data:

- ``arnold.workflow``: ``Pipeline``, ``Step``, ``Route``, ``Input``, ``Output``,
  ``Capability``, ``compile_pipeline``, ``inspect_manifest``, ``dry_run``,
  ``to_dot``, ``to_yaml``.

These modules must not import ``arnold.execution`` or product-specific modules.
They reject live callables, closures, bound methods, and callable instances.

## Inspect And Dry-Run Fields

The following fields are stable and safe to rely on across tools:

- ``inspect_manifest``: ``node_ids``, ``refs``, ``dependencies``, ``capabilities``,
  ``control_routes``, ``suspension_points``, ``unresolved_inputs``, ``source_spans``,
  ``hash_inputs``.
- ``dry_run``: ``id``, ``manifest_hash``, ``node_count``, ``edge_count``,
  ``possible_routes``, ``unresolved_inputs``, ``suspension_point_count``.

``to_dot`` and ``to_yaml`` are diagnostic-only formatting helpers; their exact
string output may change.

## Loop And Reentry

Recursive behavior must be expressed with explicit bounded control topology:

- ``WorkflowPolicy.loop.max_iterations`` supplies the finite bound.
- ``SuspensionRoute.reentry_id`` names the stable resume cursor.
- Arbitrary directed graph cycles are invalid.

## CLI Validation

Validate a shipped pipeline with the workflow CLI:

```bash
arnold workflow check --module arnold_pipelines.megaplan.pipelines.jokes:build_pipeline
arnold workflow dry-run --module arnold_pipelines.megaplan.pipelines.jokes:build_pipeline
arnold workflow run --module arnold_pipelines.megaplan.pipelines.jokes:build_pipeline --backend fake
```
