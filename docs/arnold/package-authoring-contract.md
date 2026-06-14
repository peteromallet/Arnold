# Arnold Package Authoring Contract

This page is the authoritative field-level contract for Arnold pipeline
package modules. It is derived from the two reference packages —
`arnold/pipelines/evidence_pack/__init__.py` and
`arnold/pipelines/megaplan/__init__.py` — and from the discovery rules in
`arnold/pipeline/discovery/manifest.py` and
`arnold/pipelines/megaplan/_pipeline/registry.py`.

## Field Table

| Field | Required | Description | Accepts |
|---|---|---|---|
| `name` | **required** | Public CLI-visible pipeline name. Must be a non-empty `str`, kept stable so discovery and deduplication work predictably. | `str` |
| `description` | **required** | Human-readable one-liner describing what the pipeline does. Shown in `doctor`, `list`, and Capsule projections. | `str` |
| `arnold_api_version` | **required** | Semver `major.minor` string declaring the Arnold SDK version this package targets. Must satisfy `1 ≤ major < CURRENT_MAJOR` (currently `CURRENT_MAJOR = 2`). | `str` (e.g. `"1.0"`) |
| `capabilities` | **required** | Labels used by the CLI, Capsule contracts, and registry filtering to classify what the pipeline can do. | `tuple[str, ...]` |
| `driver` | **required** | Declares the execution driver shape. Accepts a plain string or a tuple of strings. Evidence-pack uses `"in_process"` (bare string); Megaplan uses `("megaplan", "planning")` (tuple). | `str` \| `tuple[str, ...]` |
| `entrypoint` | **required** | The callable that returns a `Pipeline`. Two formats are accepted: a bare name (e.g. `"build_pipeline"`) resolved from the module's top-level namespace, or a `"module:name"` string (e.g. `"arnold.pipelines.evidence_pack:build_pipeline"`) where the part after the colon is the bare name. Evidence-pack uses the colon form; Megaplan uses a bare name. | `str` (bare or `"module:name"`) |
| `build_pipeline` | **required** | The nullary (or effectively nullary) entrypoint callable. Must be importable and callable with no arguments from the registry's perspective. Aliased bindings (e.g. `build_pipeline = build_initial_pipeline`) are valid — the runtime validator uses `import` + `getattr`, not AST parsing. | `Callable[[], Pipeline]` |
| `default_profile` | **recommended** | The default profile name when the caller does not specify one. May be `None`. Evidence-pack omits this field; Megaplan declares `default_profile: str \| None = None`. | `str` \| `None` |
| `supported_modes` | **recommended** | Tuple of mode strings the pipeline explicitly supports (e.g. `("code", "doc", "creative", "joke")`). Evidence-pack omits this field; Megaplan declares it. | `tuple[str, ...]` |
| `hooks` | **recommended** | A module-level `Hooks` class or instance implementing lifecycle callbacks (`on_step_start`, `on_step_end`, `on_suspension`, etc.). Evidence-pack exposes `EvidencePackHooks`; Megaplan does not expose hooks at module level (hooks are internal). | `type[ExecutorHooks]` |
| `resume` | **recommended** | A module-level resume driver (function or callable class) that accepts a suspension artifact and returns a resume result. Evidence-pack exposes `resume_evidence_pack`, `EvidencePackResumeError`, and `EvidencePackResumeResult`; Megaplan does not expose resume at module level (resume is internal). | `Callable[..., ResumeResult]` |
| `build_continuation_pipeline` | **recommended** | An optional nullary callable that returns a `Pipeline` graph for resuming a previously suspended run. Evidence-pack exports this; Megaplan does not. | `Callable[[], Pipeline]` |

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
`supported_modes` as **recommended**, not required, because:

- `evidence_pack` omits both fields yet is a fully functional pipeline package.
- `megaplan` omits module-level `hooks` and `resume` yet is the canonical
  reference package.
- Making them required would force changes to existing reference packages,
  violating the M2 assumption that reference surfaces are authoritative.

**Practical rule for authors:** Declare `default_profile` (even as `None`) and
`supported_modes` (even as an empty tuple) so the package passes manifest-first
discovery. Packages that skip these fields will still work at runtime (the
runtime validator uses `import` + `getattr` and reports their absence as
informational), but will be rejected by the static manifest reader.

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
the module and inspects its attributes via `getattr`. This **deliberately
diverges** from `read_manifest` which uses `ast.parse` + `ast.literal_eval` and
never imports the module.

The runtime approach correctly resolves:

- **Aliased bindings**: `build_pipeline = build_initial_pipeline` (evidence_pack)
  works at runtime but would not be resolvable by AST literal scanning.
- **Computed attributes**: Megaplan's `__getattr__` lazy-loading works at
  runtime but has no static representation.

This divergence is documented and intentional: static discovery is for
cataloguing and identity; runtime validation is for correctness checking.
Authors should ensure both paths succeed for their package.

## Reference Package Summary

| Field | evidence_pack | megaplan |
|---|---|---|
| `name` | `"evidence-pack"` | `"megaplan"` |
| `description` | ✓ | ✓ |
| `arnold_api_version` | `"1.0"` | `"1.0"` |
| `capabilities` | `("artifact-verification", "evidence-pack")` | `("planning", "execution", "review")` |
| `driver` | `"in_process"` (str) | `("megaplan", "planning")` (tuple) |
| `entrypoint` | `"arnold.pipelines.evidence_pack:build_pipeline"` (module:name) | `"build_pipeline"` (bare) |
| `build_pipeline` | aliased (`= build_initial_pipeline`) | wrapper function |
| `default_profile` | absent | `None` |
| `supported_modes` | absent | `("code", "doc", "creative", "joke")` |
| `hooks` | `EvidencePackHooks` | absent (internal) |
| `resume` | ✓ | absent (internal) |
| `build_continuation_pipeline` | ✓ | absent |

## Cross-References

- [`package-contract.md`](package-contract.md) — narrative contract for package
  layout, entrypoint rules, static identity, and Capsule interaction.
- [`authoring-guide.md`](authoring-guide.md) — hands-on guide for scaffolding
  modules, building graphs, and validating locally.
- [`arnold/pipeline/discovery/manifest.py`](../arnold/pipeline/discovery/manifest.py) —
  static manifest reader and `REQUIRED_FIELDS` definition.
- [`arnold/pipelines/megaplan/_pipeline/registry.py`](../arnold/pipelines/megaplan/_pipeline/registry.py) —
  discovery scanner with the underscore skip rule (line 904).
