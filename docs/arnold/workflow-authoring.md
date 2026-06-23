# Workflow Authoring Contract

The canonical V1 source contract for new Python-shaped workflow authoring is
[`python-shaped-authoring-contract.md`](python-shaped-authoring-contract.md).
That source grammar is versioned as
``arnold.workflow.authoring.v1``.

The explicit-node ``arnold.workflow`` DSL is backend compiler data. A
Python-shaped workflow source file lowers into ``arnold.workflow.Pipeline`` and
then into a neutral ``WorkflowManifest`` with deterministic hashes. Shipped
packages may still expose a ``build_pipeline()`` entrypoint returning a
``Pipeline`` while the frontend compiler lands, but the DSL objects are not the
user-facing V1 grammar.

## Backend DSL Shape

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

``Pipeline`` is explicit-node backend data. ``WorkflowManifest`` is compiler
output. Packages must not hand-author manifest hashes, runtime state, or
``WorkflowManifest`` objects as package source.

Python-shaped V1 source must not hand-author this explicit-node DSL either. It
uses imports from ``arnold.workflow.authoring`` plus typed component imports as
described in the Python-shaped contract, and the compiler produces the DSL
object before manifest lowering.

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

## Stable Backend Surface

The explicit-node backend surface is intentionally small and pure data:

- ``arnold.workflow``: ``Pipeline``, ``Step``, ``Route``, ``Input``, ``Output``,
  ``Capability``, ``compile_pipeline``, ``inspect_manifest``, ``dry_run``,
  ``to_dot``, ``to_yaml``.

These modules must not import ``arnold.execution`` or product-specific modules.
They reject live callables, closures, bound methods, and callable instances.
Python-shaped source adds a stricter static import boundary: workflow files may
import only compiler intrinsics from ``arnold.workflow.authoring`` and typed
workflow components.

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
