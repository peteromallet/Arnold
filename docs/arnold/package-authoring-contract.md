# Arnold Package Authoring Contract

This page is the authoritative field-level contract for Arnold pipeline
package modules. It is derived from the two reference packages —
`arnold/pipelines/evidence_pack/__init__.py` and
`arnold/pipelines/megaplan/__init__.py` — and from the discovery rules in
`arnold/pipeline/discovery/manifest.py` and
`arnold/pipelines/megaplan/_pipeline/registry.py`.

The contract is **native-first**: every package compiles a `@pipeline`
declaration, projects it into a `Pipeline` graph shell, and attaches the
compiled `NativeProgram` as `native_program`. The graph shell is still
validated and may still be executed by the legacy graph executor, but the
native declaration is the canonical source of truth.

## Field Table

| Field | Required | Description | Accepts |
|---|---|---|---|
| `name` | **required** | Public CLI-visible pipeline name. Must be a non-empty `str`, kept stable so discovery and deduplication work predictably. | `str` |
| `description` | **required** | Human-readable one-liner describing what the pipeline does. Shown in `doctor`, `list`, and Capsule projections. | `str` |
| `arnold_api_version` | **required** | Semver `major.minor` string declaring the Arnold SDK version this package targets. Must satisfy `1 ≤ major < CURRENT_MAJOR` (currently `CURRENT_MAJOR = 2`). | `str` (e.g. `"1.0"`) |
| `capabilities` | **required** | Labels used by the CLI, Capsule contracts, and registry filtering to classify what the pipeline can do. | `tuple[str, ...]` |
| `driver` | **required** | Declares the execution driver shape. Native-first packages use `("native", "<kind>")` where `<kind>` describes the topology (e.g. `"linear"`, `"fanout+reduce"`, `"panel"`). | `tuple[str, ...]` |
| `entrypoint` | **required** | The callable that returns a `Pipeline`. Two formats are accepted: a bare name (e.g. `"build_pipeline"`) resolved from the module's top-level namespace, or a `"module:name"` string (e.g. `"arnold.pipelines.evidence_pack:build_pipeline"`) where the part after the colon is the bare name. Evidence-pack uses the colon form; Megaplan uses a bare name. | `str` (bare or `"module:name"`) |
| `build_pipeline` | **required** | The nullary (or effectively nullary) entrypoint callable. Must return a `Pipeline` shell with `native_program` set. Aliased bindings are valid — the runtime validator uses `import` + `getattr`, not AST parsing. | `Callable[[], Pipeline]` |
| `native_program` | **required** | The compiled `NativeProgram` produced by `compile_pipeline(...)`. It is attached to the returned `Pipeline` shell so the runtime can execute the native declaration directly. | `NativeProgram` |
| `default_profile` | **recommended** | The default profile name when the caller does not specify one. May be `None`. | `str` \| `None` |
| `supported_modes` | **recommended** | Tuple of mode strings the pipeline explicitly supports (e.g. `("code", "doc", "creative", "joke")`). For native-only packages this is typically `("native",)` or a mode tuple that includes `"native"`. | `tuple[str, ...]` |

Legacy-only fields (removed in the native-first contract):

- `hooks` — package-level lifecycle hooks are replaced by runtime-neutral `NativeRuntimeHooks` or trace hooks.
- `resume` — package-local resume drivers are replaced by the shared native runtime resume path.
- `build_continuation_pipeline` — continuation pipelines are replaced by native cursor resume.

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
`supported_modes` (for native-first packages, a non-empty tuple that includes
`"native"`, e.g. `("native",)`) so the package passes manifest-first discovery.
Packages that skip these fields will still work at runtime (the runtime
validator uses `import` + `getattr` and reports their absence as informational),
but will be rejected by the static manifest reader.

New packages must be native-first. Do not create `_legacy.py`, graph fallback
builders, compatibility namespaces, or temporary wrapper modules for new work.

## Registry Discovery: Underscore Skip Rule

The pipeline discovery scanner at
`arnold/pipelines/megaplan/_pipeline/registry.py:904` skips any file or
directory whose name begins with `_` or `.`:

```python
if entry.name.startswith("_") or entry.name.startswith("."):
    continue
```

This means:

- **`_template.py`** (and any `_`-prefixed module) is invisible to pipeline
  discovery. Use `_` prefixes for private helpers, base classes, and template
  modules that should not appear in `megaplan pipelines list`.
- **`__init__.py`** is matched separately as a package entry point (line 912)
  and is not affected by this rule.
- **Dotfiles** (`.gitkeep`, `.DS_Store`) are also skipped.

This rule is the canonical mechanism for keeping internal implementation
details out of the public pipeline registry. Package authors should use it
deliberately: name internal modules with a leading underscore when they must
live alongside discoverable packages in a scan root.

## Runtime Validation vs. Static Manifest Reading

The validator at `validate_package_module` (used by `pipelines check`) imports
the module and inspects its attributes via `getattr`. This **deliberately**
diverges from `read_manifest` which uses `ast.parse` + `ast.literal_eval` and
never imports the module.

The runtime approach correctly resolves:

- **Aliased bindings**: `build_pipeline = _build_pipeline` works at runtime but
  would not be resolvable by AST literal scanning.
- **Computed attributes**: Megaplan's `__getattr__` lazy-loading works at
  runtime but has no static representation.

This divergence is documented and intentional: static discovery is for
cataloguing and identity; runtime validation is for correctness checking.
Authors should ensure both paths succeed for their package.

At validation time the runtime also checks that `build_pipeline()` returns a
`Pipeline` whose `native_program` attribute is a `NativeProgram`. A package
that returns a graph-only pipeline without `native_program` will fail the
check under the native-first contract.

## Reference Package Summary

| Field | evidence_pack | megaplan |
|---|---|---|
| `name` | `"evidence-pack"` | `"megaplan"` |
| `description` | ✓ | ✓ |
| `arnold_api_version` | `"1.0"` | `"1.0"` |
| `capabilities` | `("artifact-verification", "evidence-pack")` | `("planning", "execution", "review")` |
| `driver` | `("native", "evidence-pack")` | `("native", "planning")` |
| `entrypoint` | `"arnold.pipelines.evidence_pack:build_pipeline"` (module:name) | `"build_pipeline"` (bare) |
| `build_pipeline` | native-backed factory | native-backed factory |
| `native_program` | ✓ | ✓ |
| `default_profile` | `None` | `None` |
| `supported_modes` | `("native",)` | `("native",)` |

## Cross-References

- [`package-contract.md`](package-contract.md) — narrative contract for package
  layout, entrypoint rules, static identity, and Capsule interaction.
- [`authoring-guide.md`](authoring-guide.md) — hands-on guide for scaffolding
  native-first packages and validating locally.
- [`arnold/pipeline/discovery/manifest.py`](../arnold/pipeline/discovery/manifest.py) —
  static manifest reader and `REQUIRED_FIELDS` definition.
- [`arnold/pipelines/megaplan/_pipeline/registry.py`](../arnold/pipelines/megaplan/_pipeline/registry.py) —
  discovery scanner with the underscore skip rule (line 904).
