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

## Source-File CLI

For Python-shaped V1 source files, use file-first commands. The authored `.py`
file remains the source; generated manifests are backend outputs.

```bash
arnold workflow check workflow.py
arnold workflow compile workflow.py --out manifest.json
arnold workflow inspect workflow.py
arnold workflow explain workflow.py
arnold workflow graph workflow.py --format mermaid
```

- `check` prints human diagnostics by default and exits non-zero when the source
  is invalid. Use `--format json` for a machine-readable envelope.
- `compile` writes canonical manifest JSON to `--out` on success. On failure it
  exits non-zero and, with `--diagnostics-json PATH|-`, writes structured
  diagnostics without creating or truncating the requested output file.
- `inspect` emits a source-oriented summary: workflow identity, components,
  routes, policies, and source spans. JSON output is available with
  `--format json`.
- `explain` prints an ordered narrative of the authored control flow with line
  numbers and component references.

### JSON diagnostics envelope

```json
{
  "ok": false,
  "source": {"kind": "python", "path": "workflow.py"},
  "diagnostics": [
    {
      "file": "workflow.py",
      "line": 9,
      "col": 35,
      "severity": "error",
      "code": "AWF010_RESERVED_CALL_KEYWORD",
      "message": "...",
      "suggestion": "..."
    }
  ]
}
```

The envelope is stable for agent consumption. Fields `line` and `col` are
omitted (or `null`) when a diagnostic has no source span; callers must not
fabricate locations.

`--module ...` remains available for legacy builder-target workflows and is
unchanged.

## Graph Rendering

Render the authored topology without editing generated files:

```bash
arnold workflow graph workflow.py --format dot
arnold workflow graph workflow.py --format mermaid
arnold workflow graph workflow.py --format json
```

`dot` produces a Graphviz diagram, `mermaid` produces a `flowchart TD` diagram,
and `json` emits a stable node/edge/source-span payload. All three are derived
from the compiled manifest but annotated with authored source spans where
available.

## Shipped Example

A minimal shipped pipeline lives at `examples/workflow_authoring/hello/`. It
shows a V1-authored `workflow.py`, typed `components.py`, and `SKILL.md`:

```bash
arnold workflow check examples/workflow_authoring/hello/workflow.py
arnold workflow compile examples/workflow_authoring/hello/workflow.py --out /tmp/hello.json
arnold workflow explain examples/workflow_authoring/hello/workflow.py
```

## Negative Examples

V1 intentionally rejects far-out control flow. A `for` loop inside a workflow
function produces an `AWF002_UNSUPPORTED_SYNTAX` diagnostic with a source
location and a fix pointer, not a silently broken manifest:

```bash
arnold workflow check tests/fixtures/workflow_authoring/invalid_unsupported_control_flow.py
```
