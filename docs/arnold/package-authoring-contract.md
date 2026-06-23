# Arnold Package Authoring Contract

This page is the authoritative field-level contract for Arnold workflow package
modules.  It is derived from the reference packages under
``arnold_pipelines/evidence_pack`` and ``arnold_pipelines/megaplan`` and from the
workflow manifest discovery rules.

## Workflow Authoring Contract

The V1 source contract for new Python-shaped workflows is
``arnold.workflow.authoring.v1``.  In that source shape, workflow imports are the
package's dependency graph and source of truth: workflow files import typed
module-level component exports and declare a workflow over those imports.  The
compiler lowers that constrained source to ``arnold.workflow.dsl.Pipeline`` and
then to ``WorkflowManifest`` data.

A package's current public entrypoint is still ``build_pipeline()``.  Discovery,
``arnold workflow check``, dry runs, and package registries continue to address
the package as ``<module>:build_pipeline``.  The entrypoint must remain
importable and callable from the registry's perspective; it may build the
explicit-node DSL directly today or, once the compiler is wired in, delegate to
the Python-shaped source compiler.  It must not treat generated catalogs or
manifest JSON as editable source.

``WorkflowManifest`` remains compiler output produced by
``arnold.workflow.compile_pipeline()``.  Generated component catalogs may exist
later for inspection, caching, packaging, or editor support, but they are
derived artifacts from typed component exports and workflow imports.  They are
not canonical workflow source and must not be hand-edited to define package
behavior.  See [`workflow-authoring.md`](workflow-authoring.md) and
[`python-shaped-authoring-contract.md`](python-shaped-authoring-contract.md) for
the full authoring boundary.

## Component Layout

Python-shaped workflow packages should keep authored components as module-level
typed exports.  Recommended package-local files are:

```text
arnold_pipelines/<package>/
  __init__.py              # metadata and build_pipeline()
  workflow.py              # imports components and declares workflow(...)
  steps.py                 # StepComponent exports
  prompts.py               # PromptComponent exports
  policies.py              # PolicyComponent exports
  schemas.py               # SchemaComponent exports
  subflows.py              # SubflowComponent exports
```

Kind-based files are a readability convention, not a resolver rule.  Feature
modules are also valid when they export typed component objects.  The contract is
the module-level export shape: step, prompt, policy, schema, and subflow
components must carry the component kind and stable provenance needed for static
validation without executing workflow source.

Workflow source should import these exports explicitly:

```python
from arnold.workflow.authoring import workflow
from .steps import plan, execute, review

workflow(
    id="my-pipeline",
    version="1.0",
    steps=[
        plan(id="plan"),
        execute(id="execute"),
        review(id="review"),
    ],
)
```

Do not route workflow authoring through root-package imports, star imports,
dynamic imports, legacy/native builders, or generated catalogs.  Aliased
component imports are allowed only when provenance preserves the original
``module:qualname`` and the local alias.

## Field Table

| Field | Required | Description | Accepts |
|---|---|---|---|
| ``name`` | **required** | Public pipeline name. Must be a non-empty ``str``, kept stable so discovery and deduplication work predictably. | ``str`` |
| ``description`` | **required** | Human-readable one-liner describing what the pipeline does. | ``str`` |
| ``arnold_api_version`` | **required** | Semver ``major.minor`` string declaring the Arnold SDK version this package targets. Must satisfy ``1 ≤ major < CURRENT_MAJOR``. | ``str`` (e.g. ``"1.0"``) |
| ``capabilities`` | **required** | Labels used by the CLI, contracts, and registry filtering to classify what the pipeline can do. | ``tuple[str, ...]`` |
| ``driver`` | **required** | Declares the execution driver shape. Accepts a plain string or a tuple of strings. | ``str`` or ``tuple[str, ...]`` |
| ``entrypoint`` | **required** | The callable that returns a ``Pipeline``. Two formats are accepted: a bare name (e.g. ``"build_pipeline"``) or a ``"module:name"`` string. | ``str`` |
| ``build_pipeline`` | **required** | The nullary (or effectively nullary) package entrypoint callable. It currently returns ``arnold.workflow.dsl.Pipeline`` and is the registry/CLI target. It may later delegate to the Python-shaped source compiler, but remains the package entrypoint rather than a generated catalog. | ``Callable[[], Pipeline]`` |
| ``default_profile`` | **recommended** | The default profile name when the caller does not specify one. May be ``None``. | ``str`` or ``None`` |
| ``supported_modes`` | **recommended** | Tuple of mode strings the pipeline explicitly supports. | ``tuple[str, ...]`` |

## Manifest Discovery

Static discovery reads module-level constants without importing the module.  The
reader uses ``ast.parse`` and ``ast.literal_eval``; computed attributes, aliases,
and ``__getattr__`` lazy-loading are only visible at runtime.  Authors should
keep the fields above as literal bindings so discovery succeeds.

The discovery scanner skips any file or directory whose name begins with ``_`` or
``.``.  Use ``_`` prefixes for private helpers and template modules that should
not appear in the public pipeline registry.

## Runtime Validation

The workflow CLI validates a builder target by importing the module and calling
``build_pipeline``:

```bash
arnold workflow check --module arnold_pipelines.evidence_pack:build_pipeline
```

This deliberately diverges from static discovery: runtime validation checks
correctness, while static discovery checks identity.

For Python-shaped packages, runtime validation still enters through
``build_pipeline``.  The workflow ``.py`` source and its imports define the
authored workflow; generated manifests and catalogs are checked as outputs of
that authoring path, not as replacement package sources.

## SKILL.md Expectations

Every discoverable package should ship a sibling ``SKILL.md`` that describes the
workflow's purpose, required capabilities, inputs/outputs, suspension and
resume semantics, and any human-in-the-loop expectations.  The skill file is
consumed by agentic callers and is not a substitute for the machine-readable
module metadata above, but it must stay consistent with the ``capabilities``,
``driver``, and ``build_pipeline`` contract.

## Cross-References

- [`package-contract.md`](package-contract.md) — narrative contract for package
  layout, entrypoint rules, static identity, and runtime interaction.
- [`workflow-authoring.md`](workflow-authoring.md) — explicit-node authoring
  contract and stable inspect/dry-run fields.
- [`python-shaped-authoring-contract.md`](python-shaped-authoring-contract.md)
  — V1 Python-shaped source grammar, component imports, diagnostics, and
  provenance rules.
- [`workflow-manifest.md`](workflow-manifest.md) — serialized manifest contract.
