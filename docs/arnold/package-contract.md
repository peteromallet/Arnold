# Arnold Package Contract

An Arnold package is a discoverable pipeline module plus its adjacent agent
instructions. The contract is intentionally small: the package must expose
stable metadata for no-import discovery, return a projected
`arnold.pipeline.types.Pipeline` with a **non-null** `native_program` from
its entrypoint, and keep human/agent-facing guidance in `SKILL.md`.

Generated details for manifest fields, discovery facts, dispositions, schemas,
and CLI inventories are maintained in
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).
The authoritative field-level contract (with per-field types, required/recommended
status, and reference-package coverage) is at
[`package-authoring-contract.md`](package-authoring-contract.md).
This page describes the authoring contract around those facts.

## Layout

The normal package shape is:

```text
arnold_pipelines/megaplan/pipelines/
  my_module.py
  my-module/
    SKILL.md
    prompts/
      review.md
      revise.md
```

The Python filename uses underscores because it is a module. The CLI name uses
hyphens because that is what users and agents type. Discovery canonicalizes the
name, so choose one readable slug and keep the module, package directory, and
metadata aligned.

Sibling-file modules are also supported for simpler packages. In either shape,
`SKILL.md` should live where discovery can associate it with the module. The
generated package contract reference records the exact reader behavior.

## Required Module Shape

A package module should keep these concepts visible at top level:

- the public Arnold name and description;
- the Arnold API version;
- the driver declaration (`("native", "<kind>")` for native-first packages);
- the entrypoint function name;
- supported modes (must include `"native"`);
- optional default profile, recommended profiles, and capability labels;
- an entrypoint that compiles a native program and returns a projected
  `arnold.pipeline.types.Pipeline` with a non-null `native_program`.

Keep these values static. Discovery must be able to inspect the package without
executing arbitrary code. Runtime work belongs inside phases, not in module
metadata.

## Native-First Execution

The canonical package declares topology via `@pipeline`, `@phase`,
`@decision`, and `parallel(...)` decorators, compiles the native program
with `compile_pipeline()`, and projects it into a `Pipeline` shell via
`project_graph()`. The runtime executes the native program directly. The
projected shell satisfies discovery and validation — it is **not** the
final compositional surface.

```python
from arnold.pipeline.native import compile_pipeline, phase, pipeline, project_graph
from arnold.pipeline.types import Pipeline


@phase(name="start")
def start(ctx: object) -> Any:
    return {"status": "ready"}


@phase(name="finish")
def finish(ctx: object) -> Any:
    return {"status": "done"}


@pipeline(name="my-pipeline", description="start → finish")
def my_pipeline_native(ctx: object) -> Any:
    yield start(ctx)
    yield finish(ctx)


def build_pipeline() -> Pipeline:
    native = compile_pipeline(my_pipeline_native)
    return project_graph(native, key_mode="phase")
```

Packages must **not** return `NativeProgram` builder objects, executor
objects, `_forward_m2_m3` graph objects, or graph-only `Pipeline` objects
without a native program from `build_pipeline()`. Do not hand-author
`WorkflowManifest` — it is compiler output only.

## Entrypoint Rules

The entrypoint should be nullary from the registry's perspective. CLI-specific
values belong at the command boundary or in `StepContext`, not in the registry
builder signature. That preserves a stable package identity: the module can be
discovered, checked, and included in Capsule Definition identity without knowing
which run-time flags a user will pass later.

When a pipeline needs mode-specific behavior, prefer prompt variants,
`ctx.mode`, profile slots, or explicit state inputs over changing the native
declaration at import time.

## Static Identity

Arnold distinguishes static behavioral identity from trusted runtime topology.
Static identity is discovered without importing the package and includes source,
skill, resource, helper, declared-input, and unresolved-dynamic-input
projections. Runtime topology is produced only when a trusted caller explicitly
builds the pipeline.

Package authors should therefore make two things easy:

- no-import discovery can find enough stable metadata to name and describe the
  package;
- trusted builds can construct the same native program repeatedly from the same
  package bytes and declared resources.

Avoid top-level side effects, global mutation, environment-dependent metadata,
and network or filesystem probes during import. If a phase needs the filesystem,
do that work inside the phase's function body and make the relevant file paths
explicit inputs.

## Resource Ownership

Prompts, local helper files, and package instructions are part of package
behavior. Keep them under the sibling package directory when possible. This
makes author intent clear and lets static identity include the files that
actually shape execution.

Do not duplicate package facts in multiple places. The module owns executable
metadata. `SKILL.md` owns agent-facing guidance. Generated references own exact
field inventories.

## Validation Contract

`arnold pipelines check --module <package>:build_pipeline` is the package's
basic compatibility gate. It must be able to load the package, build the
projected `Pipeline`, and verify that `native_program` is non-null.

`arnold pipelines doctor` is a discovery tool. Use it when a package is skipped
or rejected before native-program validation begins.

## Capsule Contract Interaction

Capsule Contracts consume package identity facts but do not relax the package
contract. A Capsule may record static behavioral hash, runtime topology hash,
manifest ABI, port expectations, Evidence refs, repo commit, tool versions,
model versions, environment variable requirements, and secret-shape
declarations. Optional environment requirements are checked only when the
Capsule declares them and the caller supplies matching runtime context.

The practical rule for authors is simple: declare requirements only when they
are real replay constraints. Do not read process environment or secret values
inside package metadata to make a Capsule look more complete.

## Compatibility Policy

**Canonical surface**: `arnold pipelines <subcommand>` is the canonical Arnold
CLI for native-first packages. `megaplan pipelines <subcommand>` is a legacy
compatibility path; it continues to work during the migration but new authoring
guidance and conformance checks target the Arnold namespace and the native-first
contract.

Graph-first packages, `--driver graph`, `arnold.workflow.Pipeline` authoring,
package-level `hooks`, `resume` drivers, and `build_continuation_pipeline`
entrypoints are deprecated. New packages must be native-first; legacy packages
should migrate to native declarations plus projected `Pipeline` shells.

Forward-compatible projection schemas ignore unknown keys, but package modules
should not rely on that to smuggle behavior through undocumented metadata. Add
new public package facts deliberately, update the generator when they are
code-owned, and keep authored docs focused on intent and native declarations.

## M6 Dispatch Substrate Boundary

The `native_program` attached to the projected `Pipeline` is a **dispatch
substrate** — it proves the package is executable by the native runtime, but
it does not define the final visible compositional semantics. Panel synthesis,
join delegation, parallel merge strategy, subpipeline ownership, and Capsule
projection are deferred to later Megaplan layers above the dispatch boundary.

Package authors should treat `native_program` as the execution-level contract
and avoid overclaiming composition guarantees in metadata or docs.
