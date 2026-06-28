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

## Reading Explain Output

`explain` is a generated diagnostic view of `workflow.py`. It is useful when
reviewing what the compiler understood from the authored source, but it is not a
source file, manifest contract, or runtime entrypoint.

Human output lists the workflow identity followed by ordered entries:

```text
Workflow shipped-jokes (1.0)
1 [step] draft
2 [step] tighten
3 [step] emit
```

Nested authored control flow is rendered with indentation. Branch entries own
branch-arm children, and loop entries own the body entries inferred from source.
The JSON form keeps the same relationship in `children` arrays so tools can walk
the authored shape without reverse-engineering text output:

```bash
arnold workflow explain workflow.py --format json
```

Step entries include authored IDs, component references, source spans, and input
bindings where available. Branch-arm entries include the condition literal (or
`else`) and their nested children. Loop entries include generated loop metadata
such as `max_iterations` and `reentry_id` when the source provided it.

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
and `json` emits a node/edge payload with source annotations. All three are
generated from the compiled manifest and annotated with authored source topology
where available.

## Pattern-Based Explicit-Node Example

Pattern constructors return pure lowerable values. Compose them into a
`Pipeline` before returning from `build_pipeline()`:

```python
from arnold.workflow import Pipeline, Route
from arnold.patterns import agent


def build_pipeline() -> Pipeline:
    plan = agent(
        "plan",
        task="Plan the implementation",
        prompt_ref="arnold.example:plan",
    )
    code = agent(
        "code",
        task="Implement the plan",
        prompt_ref="arnold.example:code",
    )
    review = agent(
        "review",
        task="Review the implementation",
        prompt_ref="arnold.example:review",
    )

    return Pipeline(
        id="plan-code-review",
        version="1.0",
        steps=(plan, code, review),
        routes=(
            Route(id="plan-code", source="plan", target="code"),
            Route(id="code-review", source="code", target="review"),
        ),
    )
```

See [`pattern-stability-matrix.md`](pattern-stability-matrix.md) for the
stability of individual constructors.

## Graph Annotations

Graph annotations are read-only diagnostic enrichments. They are built beside the
compiled manifest so manifest identity and runtime behavior stay unchanged.

- DOT branch edges prefer authored condition literals in labels, while retaining
  compiler condition references as fallback context.
- Mermaid output may group branch arms and loop bodies in lightweight subgraphs
  to make nested source structure visible.
- JSON output keeps manifest-derived `nodes` and `edges`, then adds a
  `source_topology` section with authored node annotations, branch arms, loop
  boundaries, source spans, nesting depth, reentry IDs, and loop exits where
  known.

Consumers that need durable runtime identity should use the compiled manifest.
Consumers that need to help an author understand `workflow.py` can use graph or
explain output as generated views.

## Shipped Pipeline Gallery

A minimal shipped pipeline lives at `examples/workflow_authoring/hello/`. It
shows a V1-authored `workflow.py`, typed `components.py`, and `SKILL.md`:

```bash
arnold workflow check examples/workflow_authoring/hello/workflow.py
arnold workflow compile examples/workflow_authoring/hello/workflow.py --out /tmp/hello.json
arnold workflow explain examples/workflow_authoring/hello/workflow.py
```

Additional shipped authoring scaffolds live under
`examples/workflow_authoring/shipped/`:

- `jokes/`: linear `draft -> tighten -> emit`.
- `creative/`: linear `prep -> execute_creative -> critique_creative ->
  revise_creative -> finalize`.
- `live_supervisor/`: linear `classify -> diagnose -> repair_decision ->
  recheck_emit`.

Each scaffold is an authoring example made of `workflow.py`, imported
`StepComponent` definitions in `components.py`, and a sibling `SKILL.md`. They
show how shipped pipelines can be represented within the V1 source grammar; they
do not replace product-specific runtime code or add fanout semantics to V1.

## Negative Examples

V1 intentionally rejects unsupported control flow. A `for` loop inside a
workflow function produces an `AWF002_UNSUPPORTED_SYNTAX` diagnostic with a
source location and a fix pointer, not a silently broken manifest:

```bash
arnold workflow check tests/fixtures/workflow_authoring/invalid_unsupported_control_flow.py
```

Fanout-shaped examples remain outside the V1 grammar. Fixtures such as
`invalid_parallel_fanout.py`, `invalid_dynamic_component_construction.py`, and
`invalid_nested_subflow.py` document the current boundary with stable AWF
diagnostics and source spans. Existing `doc`, `select-tournament`, and
`writing-panel` patterns that require parallel fanout or dynamic composition
should remain explicit backend/runtime implementations until the authoring
grammar grows a dedicated construct for them.
