# Arnold Package Authoring Contract

This page is the authoritative field-level contract for Arnold workflow package
modules.  It is derived from the reference packages under
``arnold_pipelines/evidence_pack`` and ``arnold_pipelines/megaplan`` and from the
workflow manifest discovery rules.

## Workflow Authoring Contract

The canonical authoring target is ``arnold.workflow.Pipeline``.  A package's
``build_pipeline()`` entrypoint must return a ``workflow.Pipeline`` instance
authored with stable node IDs and durable refs.  ``WorkflowManifest`` is the
compiler output produced by ``arnold.workflow.compile_pipeline()`` and must not
be hand-authored as package source.  See
[`workflow-authoring.md`](workflow-authoring.md) for the full authoring surface,
loop/reentry rules, and stable inspect/dry-run fields.

## Field Table

| Field | Required | Description | Accepts |
|---|---|---|---|
| ``name`` | **required** | Public pipeline name. Must be a non-empty ``str``, kept stable so discovery and deduplication work predictably. | ``str`` |
| ``description`` | **required** | Human-readable one-liner describing what the pipeline does. | ``str`` |
| ``arnold_api_version`` | **required** | Semver ``major.minor`` string declaring the Arnold SDK version this package targets. Must satisfy ``1 ≤ major < CURRENT_MAJOR``. | ``str`` (e.g. ``"1.0"``) |
| ``capabilities`` | **required** | Labels used by the CLI, contracts, and registry filtering to classify what the pipeline can do. | ``tuple[str, ...]`` |
| ``driver`` | **required** | Declares the execution driver shape. Accepts a plain string or a tuple of strings. | ``str`` or ``tuple[str, ...]`` |
| ``entrypoint`` | **required** | The callable that returns a ``Pipeline``. Two formats are accepted: a bare name (e.g. ``"build_pipeline"``) or a ``"module:name"`` string. | ``str`` |
| ``build_pipeline`` | **required** | The nullary (or effectively nullary) entrypoint callable. For M5 authoring it returns ``arnold.workflow.Pipeline``. Must be importable and callable with no arguments from the registry's perspective. | ``Callable[[], Pipeline]`` |
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
- [`workflow-manifest.md`](workflow-manifest.md) — serialized manifest contract.
