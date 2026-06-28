# Arnold Package Authoring Contract

This page is the authoritative field-level contract for Arnold workflow pipeline
packages. It is derived from the reference package
`arnold_pipelines/evidence_pack/__init__.py` and from the discovery rules in
`arnold_pipelines/discovery.py`.

The contract is **workflow-first**: every package exposes a `build_pipeline()`
entrypoint that returns an explicit-node `arnold.workflow.Pipeline`. The runtime
lowers that pipeline to a neutral `WorkflowManifest` with deterministic hashes;
packages must not hand-author manifest objects or hashes as source.

## Field Table

| Field | Required | Description | Accepts |
|---|---|---|---|
| `name` | **required** | Public CLI-visible pipeline name. Must be a non-empty `str`, kept stable so discovery and deduplication work predictably. | `str` |
| `description` | **required** | Human-readable one-liner describing what the pipeline does. Shown in `doctor`, `list`, and Capsule projections. | `str` |
| `arnold_api_version` | **required** | Semver `major.minor` string declaring the Arnold SDK version this package targets. Must satisfy `1 ≤ major < CURRENT_MAJOR` (currently `CURRENT_MAJOR = 2`). | `str` (e.g. `"1.0"`) |
| `capabilities` | **required** | Labels used by the CLI, Capsule contracts, and registry filtering to classify what the pipeline can do. | `tuple[str, ...]` |
| `driver` | **required** | Declares the execution driver shape. Workflow-first packages use `("graph", "<kind>")` where `<kind>` describes the topology (e.g. `"linear"`, `"fanout+reduce"`, `"verify"`). | `tuple[str, ...]` |
| `entrypoint` | **required** | The callable that returns a `Pipeline`. Two formats are accepted: a bare name (e.g. `"build_pipeline"`) resolved from the module's top-level namespace, or a `"module:name"` string (e.g. `"arnold_pipelines.evidence_pack:build_pipeline"`) where the part after the colon is the bare name. | `str` (bare or `"module:name"`) |
| `build_pipeline` | **required** | The nullary (or effectively nullary) entrypoint callable. Must return an `arnold.workflow.Pipeline`. Aliased bindings are valid — the runtime validator uses `import` + `getattr`, not AST parsing. | `Callable[[], Pipeline]` |
| `default_profile` | **recommended** | The default profile name when the caller does not specify one. May be `None`. | `str` \| `None` |
| `supported_modes` | **recommended** | Tuple of mode strings the pipeline explicitly supports (e.g. `("code", "doc", "creative", "joke")`). For workflow-only packages this is typically `("graph",)` or a mode tuple that includes `"graph"`. | `tuple[str, ...]` |

Legacy-only fields (removed in the workflow-first contract):

- `native_program` — native execution plans are replaced by the neutral `WorkflowManifest` produced by `compile_pipeline`.
- `hooks` — package-level lifecycle hooks are replaced by runtime-neutral trace hooks and policy-driven suspension routes.
- `resume` — package-local resume drivers are replaced by the shared workflow runtime resume path.
- `build_continuation_pipeline` — continuation pipelines are replaced by explicit continuation `Pipeline` objects where needed.

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
`supported_modes` (for workflow-first packages, a non-empty tuple that includes
`"graph"`, e.g. `("graph",)`) so the package passes manifest-first discovery.
Packages that skip these fields will still work at runtime (the runtime
validator uses `import` + `getattr` and reports their absence as informational),
but will be rejected by the static manifest reader.

New packages must be workflow-first. Do not create legacy fallback builders,
compatibility namespaces, or temporary wrapper modules for new work.

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
  modules that should not appear in `arnold workflow list`.
- **`__init__.py`** is matched separately as a package entry point and is not
  affected by this rule.
- **Dotfiles** (`.gitkeep`, `.DS_Store`) are also skipped.

This rule is the canonical mechanism for keeping internal implementation
details out of the public pipeline registry. Package authors should use it
deliberately: name internal modules with a leading underscore when they must
live alongside discoverable packages in a scan root.

## Runtime Validation vs. Static Manifest Reading

The validator at `validate_package_module` (used by `workflow check`) imports
the module and inspects its attributes via `getattr`. This **deliberately**
diverges from `read_manifest` which uses `ast.parse` + `ast.literal_eval` and
never imports the module.

The runtime approach correctly resolves:

- **Aliased bindings**: `build_pipeline = _build_pipeline` works at runtime but
  would not be resolvable by AST literal scanning.
- **Computed attributes**: lazy-loading via `__getattr__` works at runtime but
  has no static representation.

This divergence is documented and intentional: static discovery is for
cataloguing and identity; runtime validation is for correctness checking.
Authors should ensure both paths succeed for their package.

At validation time the runtime checks that `build_pipeline()` returns an
`arnold.workflow.Pipeline`. A package that returns a graph-only or native-only
object without the explicit-node DSL will fail the check under the
workflow-first contract.

## Explicit-Node Authoring Example

A workflow-first package constructs explicit nodes and routes. The compiler
produces the manifest; the package must not hand-author `WorkflowManifest`,
`NativeProgram`, native-backed factories, builder objects, executor objects, or
`_forward_m2_m3` graph objects.

```python
from arnold.workflow import Pipeline, Step, Route, Capability


name = "hello-world"
description = "A minimal workflow-first package."
arnold_api_version = "1.0"
capabilities = ("example", "hello-world")
driver = ("graph", "linear")
entrypoint = "build_pipeline"
default_profile = None
supported_modes = ("graph",)


def build_pipeline() -> Pipeline:
    return Pipeline(
        id="hello-world",
        version="1.0",
        steps=(
            Step(id="greet", kind="agent"),
            Step(id="respond", kind="agent"),
        ),
        routes=(
            Route(id="greet-respond", source="greet", target="respond"),
        ),
        capabilities=(
            Capability(id="hello-world", route="default"),
        ),
    )
```

Pattern constructors from `arnold.patterns` may be used to build composite
blocks, but the final `build_pipeline()` return type must still be
`arnold.workflow.Pipeline`.

## Reference Package Summary

| Field | evidence_pack |
|---|---|---|
| `name` | `"evidence-pack"` |
| `description` | ✓ |
| `arnold_api_version` | `"1.0"` |
| `capabilities` | `("artifact-verification", "evidence-pack")` |
| `driver` | `("graph", "verify")` |
| `entrypoint` | `"build_pipeline"` |
| `build_pipeline` | workflow DSL factory |
| `default_profile` | `None` |
| `supported_modes` | `("graph",)` |

## Cross-References

- [`package-contract.md`](package-contract.md) — narrative contract for package
  layout, entrypoint rules, static identity, and Capsule interaction.
- [`workflow-authoring.md`](workflow-authoring.md) — hands-on guide for
  workflow-first packages and validating locally.
- [`python-shaped-authoring-contract.md`](python-shaped-authoring-contract.md)
  — the canonical V1 Python-shaped source grammar.
- [`arnold_pipelines/discovery.py`](../arnold_pipelines/discovery.py) —
  discovery helpers and builder-contract families (`workflow`, `native`,
  `deferred-native`).
