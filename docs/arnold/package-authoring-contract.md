# Arnold Package Authoring Contract

This page is the authoritative field-level contract for Arnold native-first
pipeline packages. It is derived from the reference package
`arnold_pipelines/evidence_pack/__init__.py`, the template at
`arnold_pipelines/_template/`, and from the discovery rules in
`arnold_pipelines/discovery.py`.

The contract is **native-first**: every package exposes a `build_pipeline()`
entrypoint that compiles a native program and returns a projected
`arnold.pipeline.types.Pipeline` shell with a **non-null** `native_program`.
The runtime executes the native program directly. The projected shell exists
for discovery, validation, and static identity — it is **not** the final
compositional surface.

The `native_program` is a **dispatch substrate**, not a final composition
contract. Panel synthesis, join delegation, parallel merge strategy,
subpipeline ownership, and Capsule projection are deferred to later Megaplan
layers above the dispatch boundary. Packages prove they are native-runnable
by attaching a non-null `native_program`; they do not encode final visible
semantics at this layer.

## Field Table

| Field | Required | Description | Accepts |
|---|---|---|---|
| `name` | **required** | Public CLI-visible pipeline name. Must be a non-empty `str`, kept stable so discovery and deduplication work predictably. | `str` |
| `description` | **required** | Human-readable one-liner describing what the pipeline does. Shown in `doctor`, `list`, and Capsule projections. | `str` |
| `arnold_api_version` | **required** | Semver `major.minor` string declaring the Arnold SDK version this package targets. Must satisfy `1 ≤ major < CURRENT_MAJOR` (currently `CURRENT_MAJOR = 2`). | `str` (e.g. `"1.0"`) |
| `capabilities` | **required** | Labels used by the CLI, Capsule contracts, and registry filtering to classify what the pipeline can do. | `tuple[str, ...]` |
| `driver` | **required** | Declares the execution driver shape. Native-first packages use `("native", "<kind>")` where `<kind>` describes the projection strategy (e.g. `"project+validate"`). The first element **must** be `"native"`. | `tuple[str, ...]` |
| `entrypoint` | **required** | The callable that returns a `Pipeline`. Two formats are accepted: a bare name (e.g. `"build_pipeline"`) resolved from the module's top-level namespace, or a `"module:name"` string (e.g. `"arnold_pipelines.evidence_pack:build_pipeline"`) where the part after the colon is the bare name. | `str` (bare or `"module:name"`) |
| `build_pipeline` | **required** | The nullary (or effectively nullary) entrypoint callable. Must return an `arnold.pipeline.types.Pipeline` with a **non-null** `native_program`. Aliased bindings are valid — the runtime validator uses `import` + `getattr`, not AST parsing. | `Callable[[], Pipeline]` |
| `default_profile` | **recommended** | The default profile name when the caller does not specify one. May be `None`. | `str` \| `None` |
| `supported_modes` | **recommended** | Tuple of mode strings the pipeline explicitly supports. For native-first packages this **must** include `"native"` (e.g. `("native",)` or `("native", "code", "doc")`). | `tuple[str, ...]` |

Deprecated legacy fields (removed in the native-first contract):

- `driver=("graph", ...)` — graph-first driver declarations are not
  supported. New packages must use `driver=("native", "<kind>")`.
- `--driver graph` — graph scaffolding is an unsupported legacy path.
- `arnold.workflow.Pipeline` — explicit-node workflow DSL is replaced by
  native declarations plus projected `Pipeline` shells.
- `native_program = None` — null native programs fail validation. Every
  native-first package must produce a non-null program.
- `hooks` — package-level lifecycle hooks are replaced by runtime-neutral
  trace hooks and policy-driven suspension routes.
- `resume` — package-local resume drivers are replaced by the shared
  workflow runtime resume path.
- `build_continuation_pipeline` — continuation pipelines are replaced by
  explicit continuation `Pipeline` objects where needed.

## Manifest REQUIRED_FIELDS Divergence

The static manifest reader in `arnold/pipeline/discovery/manifest.py` defines
`REQUIRED_FIELDS` as:

```python
REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
)
```

This set is **stricter** than the authoring contract above. The manifest reader
requires `default_profile` and `supported_modes` as module-level constant
bindings, and will reject a package that omits them during no-import discovery.

The authoring contract deliberately treats `default_profile` and
`supported_modes` as **recommended**, not required, because some reference
packages omit them at the module level. Making them required would force
changes to existing reference packages.

**Practical rule for authors:** Declare `default_profile` (even as `None`) and
`supported_modes` (a non-empty tuple that includes `"native"`, e.g.
`("native",)`) so the package passes manifest-first discovery. Packages that
skip these fields will still work at runtime (the runtime validator uses
`import` + `getattr` and reports their absence as informational), but will be
rejected by the static manifest reader.

New packages must be native-first. Do **not** create graph fallback builders,
compatibility namespaces, shim packages, or temporary wrapper modules for new
work.

## Registry Discovery: Underscore Skip Rule

The pipeline discovery scanner skips any file or directory whose name begins
with `_` or `.`:

```python
for entry in entries:
    if entry.name.startswith("_") or entry.name.startswith("."):
        continue
```

This means:

- **`_template.py`** (and any `_`-prefixed module) is invisible to pipeline
  discovery. Use `_` prefixes for private helpers, base classes, and template
  modules that should not appear in `arnold pipeline list`.
- **`__init__.py`** is matched separately as a package entry point and is not
  affected by this rule.
- **Dotfiles** (`.gitkeep`, `.DS_Store`) are also skipped.

This rule is the canonical mechanism for keeping internal implementation
details out of the public pipeline registry. Package authors should use it
deliberately: name internal modules with a leading underscore when they must
live alongside discoverable packages in a scan root.

## Runtime Validation vs. Static Manifest Reading

The validator at `validate_package_module` (used by `arnold pipelines check`)
imports the module and inspects its attributes via `getattr`. This
**deliberately** diverges from `read_manifest` which uses `ast.parse` +
`ast.literal_eval` and never imports the module.

The runtime approach correctly resolves:

- **Aliased bindings**: `build_pipeline = _build_pipeline` works at runtime but
  would not be resolvable by AST literal scanning.
- **Computed attributes**: lazy-loading via `__getattr__` works at runtime but
  has no static representation.

This divergence is documented and intentional: static discovery is for
cataloguing and identity; runtime validation is for correctness checking.
Authors should ensure both paths succeed for their package.

At validation time the runtime checks that `build_pipeline()` returns an
`arnold.pipeline.types.Pipeline` with a **non-null** `native_program`. A
package that returns a graph-only `Pipeline` without a native program, or
with a null `native_program`, will fail the check under the native-first
contract.

## Native-First Authoring Example

A native-first package declares phases and topology via decorators,
compiles the native program, and projects it into a `Pipeline` shell.
The package must not hand-author `WorkflowManifest`, `NativeProgram`
builder objects, executor objects, or `_forward_m2_m3` graph objects.

```python
from typing import Any

from arnold.pipeline import step, workflow, decision
from arnold.pipeline.native import compile_pipeline, parallel_map, project_graph
from arnold.pipeline.types import Pipeline

name = "hello-world"
description = "A compositional native-first package with nested workflows."
arnold_api_version = "1.0"
capabilities = ("example", "hello-world")
driver = ("native", "project+validate")
entrypoint = "build_pipeline"
default_profile = None
supported_modes = ("native",)
authoring_style = "compositional"


@step(
    name="greet",
    id="hello-world.greet",
    inputs={"type": "object", "required": ["name"]},
    outputs={"type": "object", "required": ["message"]},
)
def greet(ctx: object) -> Any:
    return {"message": "hello"}


@step(
    name="respond",
    id="hello-world.respond",
    inputs={"type": "object", "required": ["message"]},
    outputs={"type": "object", "required": ["reply"]},
)
def respond(ctx: object) -> Any:
    return {"reply": "world"}


@decision(name="approve", vocabulary={"ship", "revise"})
def approve(ctx: object) -> str:
    return "ship"


@workflow(
    name="hello-world",
    id="hello-world.root",
    inputs={"type": "object", "required": ["name"]},
    outputs={"type": "object", "required": ["reply"]},
)
def hello_world_native(ctx: object) -> Any:
    state = yield greet(ctx, id="greet-step", outputs={"message": "message"})
    state = yield respond(ctx, id="respond-step", outputs={"reply": "reply"})
    return state


def build_pipeline() -> Pipeline:
    native = compile_pipeline(hello_world_native)
    return project_graph(native, key_mode="phase")
```

The returned `Pipeline` carries a non-null `native_program`. Pattern
constructors from `arnold.pipeline.native` (`parallel`, `parallel_map`,
`decision`, `start_from_trace`) may be used to build composite topologies
inside the `@workflow`-decorated generator.

## M6 Dispatch Substrate Boundary

M6 is a **dispatch substrate** milestone. The `native_program` produced by
`build_pipeline()` proves the package is executable by the native runtime,
but the final visible compositional semantics — panel synthesis rules, join
delegation strategies, parallel merge behaviour, subpipeline ownership
contracts, and Capsule projection shapes — are deferred to later Megaplan
layers above the dispatch boundary.

Package authors should:
- Treat `native_program` as the execution-level contract.
- Not overclaim final composition guarantees in package metadata or docs.
- Expect future Megaplan layers to add composition semantics without
  requiring package rewrites.

## Platform Boundaries For Package Authors

Package authors operate within explicit platform boundaries that separate
workflow semantics from execution mechanics. These boundaries are enforced
by the native runtime and the composition contract — do not cross them in
package code.

### What The Package Owns

The package module owns:
- **Topology** — the declared workflow graph, executable units, and branch points.
- **Stable identity** — the `id=` values on every invocable and call site.
- **Declared schemas** — `inputs` and `outputs` at every invocable boundary.
- **Policy references** — named policy objects bound at call sites.
- **Metadata** — `name`, `description`, `arnold_api_version`, `capabilities`,
  `driver`, `entrypoint`, `supported_modes`.

### What The Platform Owns

The platform (native runtime, executor, artifact store, worker fleet) owns:
- **Credential resolution** — API keys, secrets, environment injection.
- **Model binding** — resolving profiles to concrete model invocations.
- **Worker dispatch** — queuing, fleet allocation, co-location decisions.
- **Artifact storage** — content-addressed persistence, replication, cleanup.
- **Suspension/resume mechanics** — checkpoint writes, cursor advancement,
  trace reconstruction.
- **Policy enforcement** — timeout timers, retry loops, escalation routing.

### Crossing The Boundary

Package code that reads environment variables for secrets, assumes local
filesystem paths survive worker migration, calls into worker-fleet APIs,
or dispatches to model providers directly is crossing the platform boundary.
Such code will fail validation under `authoring_style = "compositional"`.

## Pack Identity, Dependencies, And Pins

Shared packs are package resources, not checkout-relative folders. A pack that
is consumed by another workflow must declare:

| Field | Requirement |
| --- | --- |
| Pack ID | Stable identifier scoped to the package, for example `megaplan.shared.v1`. |
| Version | Semver or immutable artifact version that appears in rollout records. |
| Dependency metadata | Required pack IDs, version constraints, source distribution, and owner. |
| Resource paths | `importlib.resources`-addressable files for source, docs, handlers, fixtures, and policy artifacts. |
| Lockfile pin | Exact wheel filename/hash and pack version used by an operator rollout. |

Authors may re-pin or upgrade a pack only by changing the lockfile entry and
recording the structural diff evidence that was rerun: topology, policy,
source-path reconciliation, fixture inclusion, and installed-wheel conformance.
Do not treat an editable checkout as a production pin.

## Structural Reconciliation For Pack Changes

Before a package or shared pack is promoted beyond local development:

1. Confirm every dependency resolves through package metadata and
   `importlib.resources`.
2. Compare the compiled topology and rendered policy against the previous pin.
3. Run cycle and depth checks on workflow calls and pack dependency edges.
4. Verify intentional loops use bounded loop or reentry carriers rather than
   arbitrary graph cycles.
5. Record any deliberate re-pin or upgrade with the old pin, new pin, reason,
   and proof command.

These checks preserve the composition contract: package metadata describes
identity and dependencies, while workflow source and declared policy remain the
semantic carriers.

Instead, declare intent (credential requirements, artifact content types,
target worker pool hints) as metadata and let the platform execute.

## Cross-References

## Reference Package Summary

| Field | evidence_pack (migrated) | _template (native-first) |
|---|---|---|
| `name` | `"evidence-pack"` | `"my-pipeline"` |
| `description` | ✓ | ✓ |
| `arnold_api_version` | `"1.0"` | `"1.0"` |
| `capabilities` | `("artifact-verification", "evidence-pack")` | `("skeleton",)` |
| `driver` | `("native", "verify")` | `("native", "project+validate")` |
| `entrypoint` | `"build_pipeline"` | `"build_pipeline"` |
| `build_pipeline` | native program + projected shell | native program + projected shell |
| `default_profile` | `None` | `None` |
| `supported_modes` | `("native",)` | `("native",)` |

- [`package-contract.md`](package-contract.md) — narrative contract for package
  layout, entrypoint rules, static identity, and Capsule interaction.
- [`authoring-guide.md`](authoring-guide.md) — hands-on guide for
  native-first packages and validating locally.
- [`creating-a-new-pipeline.md`](creating-a-new-pipeline.md) — copy-paste
  guide for scaffolding a new native-first pipeline.
- [`arnold_pipelines/discovery.py`](../arnold_pipelines/discovery.py) —
  discovery helpers and builder-contract families (`native`, `workflow`,
  `deferred-native`).
