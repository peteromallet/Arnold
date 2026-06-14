# Arnold Authoring Guide

Arnold is the module-oriented face of Megaplan pipelines. Use it when a workflow
should be discoverable as a named module, runnable from the CLI, inspectable by
the pipeline checker, and documented for agents through a sibling `SKILL.md`.

This page is authored guidance. Code-owned field lists, schema surfaces, defect
templates, command inventories, and vocabulary live in the generated reference:
[`docs/reference/arnold-projections.md`](../reference/arnold-projections.md).

## Choose the Right Artifact

Author a pipeline module when the workflow has a stable graph and can be
expressed as typed stages. Author a prompt or skill-only extension when the
existing planning pipeline already has the right control flow and only needs
domain instructions. Build a Capsule when you need a replayable outward
projection of an epic's exported evidence. Build a Warrant only when the source
projection is complete enough to sign.

Those boundaries matter because the three terminal sinks have different trust
contracts:

- Builder modules describe executable behavior and are validated by pipeline
  discovery and graph checks.
- Capsules package exported evidence and declared contract facts into
  content-addressed records.
- Warrants sign a frozen source projection and must reject incomplete source
  inventory before any signing key is used.

## Scaffold a Module

Start with the documented Arnold command:

```bash
arnold pipelines new my-module --driver graph
```

The command creates a Python module under `megaplan/pipelines/` and a sibling
`SKILL.md` directory. `--driver graph` is the accepted driver today; the command
is intentionally explicit so later driver shapes have room to appear without
changing the current scaffold.

The generated module is a small graph builder. Replace the placeholder
description, prompt path, and pipeline stages, then keep the module-level
metadata accurate enough for no-import discovery. The canonical package and
manifest facts are generated in the Arnold projection reference rather than
copied here by hand.

## Build the Graph

Prefer `Pipeline.builder(...)` for normal module authoring. It keeps stage
construction readable and still returns the plain frozen `Pipeline` type used by
the executor.

```python
from pathlib import Path

from megaplan._pipeline.types import Pipeline

_PIPELINE_DIR = Path(__file__).parent / "my-module"

name = "my-module"
description = "Review a draft and emit a revised Markdown artifact."
driver = ("graph", "dispatch+emit")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("document-review",)


def build_pipeline() -> Pipeline:
    return (
        Pipeline.builder(
            name,
            description=description,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        .agent("review", prompt="prompts/review.md", inputs=["draft"])
        .agent("revise", prompt="prompts/revise.md", inputs=["review"])
        .build()
    )
```

Use the lower-level `Stage` and `Edge` dataclasses only when the builder cannot
express the shape cleanly. If a stage emits typed recommendations, route with
gate edges instead of ad hoc string labels so contract checks and future replay
tools can reason about the topology.

## Keep Metadata Boring

Discovery reads manifest-like module metadata without importing the module when
manifest-first discovery is enabled. Keep top-level metadata simple literals:
strings, tuples, and dict/list values that can be parsed statically. Do not hide
metadata behind function calls, environment reads, or imports.

If the module needs dynamic inputs at runtime, declare the stable facts anyway
and let unresolved dynamic inputs show up in the static behavioral manifest. An
explicit unresolved input is better than an accidental import-time side effect.

## Validate Locally

Run the checker after every structural edit:

```bash
megaplan pipelines check my-module
arnold pipelines check my-module
```

Use `doctor` when discovery itself is surprising:

```bash
megaplan pipelines doctor
arnold pipelines doctor
```

The checker validates executable graphs and judge manifests. The generated
reference lists the current defect surfaces and CLI facts; this guide only
explains when to use them.

## Package Evidence Deliberately

Capsules are not a replacement for the old deterministic epic export. The
Capsule build path consumes the export, stores records through the
content-addressed Capsule writer, and references Evidence payloads by path and
hash instead of inlining their bytes. By default, export errors stop the build.
Use degraded output only when the caller intentionally accepts an incomplete
projection:

```bash
MEGAPLAN_M7_SINKS=1 megaplan epic capsule build EPIC_ID
MEGAPLAN_M7_SINKS=1 megaplan epic capsule build EPIC_ID --allow-degraded
```

Treat `replay_ready=false` as meaningful. Current Capsule builds may preserve
evidence and contracts before all replay requirements are satisfiable.

## Sign Only Complete Sources

Warrants are signed attestations over source projections, not free-form
summaries. Build the source projection first, inspect its completeness, and
sign only when required fields are present. The inventory adapter is read-only:
missing or unsupported facts stay missing or unsupported rather than being
invented or written into receipts.

Configure the signing key with `MEGAPLAN_SIGNING_WARRANT_KEY` or pass an
explicit key through the API. Empty keys are errors.

## Register a Non-Model Adapter and Validate

Arnold pipelines can include non-model invocation kinds (e.g. ``"capability"``,
``"tool"``, ``"collector"``) alongside the reserved ``"model"`` slot.  The
default validation path is fail-closed: unknown invocation kinds are rejected.
Supply a caller-built ``StepInvocationAdapterRegistry`` to let non-model kinds
pass validation.

### Build an Adapter

An adapter satisfies the ``StepInvocationAdapter`` structural protocol — a
single ``invoke(invocation: StepInvocation) -> Any`` method:

```python
from arnold.pipeline.step_invocation import (
    StepInvocation,
    StepInvocationAdapter,
    StepInvocationAdapterRegistry,
)

class MyCapabilityAdapter:
    """An adapter that implements the StepInvocationAdapter protocol."""

    def invoke(self, invocation: StepInvocation):
        # Adapter config arrives in invocation.metadata["adapter_config"]
        config = invocation.metadata.get("adapter_config", {})
        artifact_root = config["artifact_root"]
        # ... produce evidence, write files, etc.
        return {"output": "result"}
```

### Register and Supply to Validation

Register the adapter and pass the registry to ``validate()`` or
``validate_invocation_requirements()``:

```python
from arnold.pipeline.validator import validate
from arnold.pipeline.step_invocation import StepInvocationAdapterRegistry

registry = StepInvocationAdapterRegistry()
registry.register("capability", MyCapabilityAdapter())

# The registry is a keyword-only argument — existing callers are unaffected
diagnostics = validate(pipeline, adapter_registry=registry)
assert diagnostics.ok, f"validation defects: {diagnostics.defects}"
```

- Duplicate registration raises ``ValueError`` (no silent overwrite).
- The ``"model"`` slot is reserved and starts with a placeholder; non-model
  adapters live alongside it without conflict.
- When *adapter_registry* is ``None`` a fresh fail-closed default is
  constructed — the reserved-model-only behaviour is preserved.

### Return Path Outputs and Evidence References

Adapter steps can return a ``StepResult`` carrying a file path in ``outputs``
and a typed ``EvidenceArtifactRef`` in ``contract_result.evidence_refs``.
Downstream consumers read the path and validate the reference metadata without
reading blob bytes:

```python
from pathlib import Path
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    StepResult,
)

class MyCapabilityStep:
    name = "capability-step"
    kind = "capability"

    def run(self, ctx):
        root = Path(ctx.artifact_root)
        root.mkdir(parents=True, exist_ok=True)
        output_path = root / "output.mp4"
        output_path.write_text("fake-bytes")

        evidence_ref = EvidenceArtifactRef(
            uri=str(output_path),
            content_type="video/mp4",
            digest="sha256:aaaa...",  # 64-char hex
            size_bytes=16,
            name="output.mp4",
        )

        contract = ContractResult(
            status=ContractStatus.COMPLETED,
            evidence_refs=(evidence_ref,),
            authority_level="***",
        )

        return StepResult(
            outputs={"artifact": str(output_path)},
            next="halt",
            contract_result=contract,
        )
```

``EvidenceArtifactRef`` fields: ``uri`` (required, string), ``content_type``
(required, string such as ``"video/mp4"``), ``digest`` (optional string),
``size_bytes`` (optional non-negative int), ``name`` (optional string).

## Register Media Content Validators

Arnold ships three built-in media content validators under
``arnold.pipeline.media_content``.  Call ``register_media_content_validators``
to install them into a ``ContentValidatorRegistry``:

```python
from arnold.pipeline.content_validation import ContentValidatorRegistry
from arnold.pipeline.media_content import register_media_content_validators

registry = ContentValidatorRegistry()
register_media_content_validators(registry)
```

The built-in validators are **reference-metadata-only** — they inspect
``content_type``, ``uri``, and optional ``digest``/``size_bytes``/``name``
without opening, parsing, fetching, or dereferencing the blob bytes:

- ``video/mp4`` — strict: requires exact content-type match, non-empty URI;
  validates digest/string, size_bytes/non-negative-int, name/string when present.
- ``audio/wav`` — strict: same shape as video/mp4.
- ``application/x-astrid-timeline`` — permissive: only content-type and URI
  are required; all other fields accepted without type checking.

Use the registry to validate evidence-ref metadata:

```python
blob_metadata = {
    "content_type": "video/mp4",
    "uri": "/tmp/artifacts/output.mp4",
    "digest": "a" * 64,
    "size_bytes": 16,
    "name": "output.mp4",
}
result = registry.validate("video/mp4", blob_metadata)
assert result.ok, f"validation failed: {result.diagnostics}"
```

The validators live under ``arnold.pipeline.media_content`` and have **zero
Megaplan imports**.  They are pure Arnold, importable in environments where
Megaplan is not installed.

## Run the Conformance Suite

``arnold.conformance`` is an importable suite of contract checks covering all
four AR1 domains — adapter protocol, contract schema, routing vocabulary, and
join delegation.  The package has **zero Megaplan imports** and can be imported
in any Arnold environment:

```python
from arnold.conformance import run_conformance_suite, assert_suite_compliant

# Every parameter is keyword-only and optional — sensible defaults apply
suite = run_conformance_suite(
    registry=my_adapter_registry,
    pipelines=[my_pipeline],
    adapter_smoke_kinds=[("capability", my_invocation)],
    adapter_round_trip_kinds=["capability"],
    sample_contracts=[my_contract_result],
    suite_id="my-consumer-conformance",
)

assert_suite_compliant(suite)
# or inspect individual checks:
for check in suite.checks:
    if not check.passed:
        print(f"FAIL [{check.check_id}] {check.message}")
```

The four domains:

1. **Adapter protocol** — fail-closed resolution, deterministic registered kinds,
   duplicate-rejection, smoke invocations, resolve → re-resolve round-trips.
2. **Contract schema** — JSON round-trip fidelity, schema-version skew detection
   (tampered versions must raise ``ValueError``), empty-schema-version acceptance.
3. **Routing vocabulary** — decision/override edge labels must be members of
   declared vocabularies; resolve-edge behaviour for normal/decision/override/halt
   and unmatched signals is verified.
4. **Join delegation** — ``PipelineHooks.join_parallel_results`` must delegate to
   ``stage.join``; child-result forwarding and context forwarding are verified.

When sub-surfaces are skipped (empty pipelines, no contracts, ``None`` hooks),
only the generic checks run — the suite never raises for missing inputs.

## No-Megaplan Media Path

Media content types (``video/mp4``, ``audio/wav``,
``application/x-astrid-timeline``) are registered as Arnold builtins in
``arnold.pipeline.types``.  Their validators, the adapter registry, and the
conformance suite all operate under ``arnold/`` without importing or
referencing Megaplan.  The media path is:

1. **Reference only** — validators inspect metadata fields (content type, URI,
   digest, size, name) and never dereference blob bytes.
2. **No ``megaplan`` wiring** — ``arnold.conformance``, ``arnold.pipeline.media_content``,
   and ``arnold.pipeline.step_invocation`` are importable in Arnold-only
   environments.  ``import arnold.conformance`` does not add ``"megaplan"`` to
   ``sys.modules``.
3. **C4-checkable** — media edges using ``Port(content_type="video/mp4")`` and
   ``PortRef(port_name=..., content_type="video/mp4")`` pass the C4 static
   checks when correctly bound.

## Media Cost Model (AR3)

The AR3 media cost model adds a neutral media-usage record and per-media-unit
pricing to Arnold pipelines.  Every path — adapter envelopes, model-step usage
extractor, generic executor hooks, and the separate agent loop — threads through
the same pure functions with no megapath imports and no blob inspection.

### MediaUsage

``MediaUsage`` is a frozen dataclass describing one media usage event:

.. code-block:: python

   from arnold.pipeline import MediaUsage

   usage = MediaUsage(
       unit="image",     # Semantic cost unit — open vocabulary
       count=2,          # int, float, or Decimal
       dimensions={"resolution": "1024x1024", "quality": "standard"},
   )

All fields:

* ``unit: str`` — semantic pricing unit string such as ``"image"``,
  ``"video_second"``, ``"audio_second"``, or ``"song"``.  This is an **open
  vocabulary**; it is intentionally separate from MIME/content-type strings
  (``image/*``, ``video/*``, etc.) used by
  :mod:`arnold.pipeline.media_content`.
* ``count: int | float | Decimal`` — number of units.  Normalised to
  ``Decimal`` via ``Decimal(str(count))`` before any pricing arithmetic,
  so ``float`` values (e.g. ``0.015``) produce exact ``Decimal``
  representations without binary-float drift.
* ``dimensions: Mapping[str, Any]`` — optional metadata (resolution, fps,
  duration, etc.).  Never inspected by pricing logic.
* ``raw_usage: Any | None`` — optional raw provider response blob;
  retained for debugging but never inspected by pricing logic.

### Semantic Cost Units vs Content Types

Cost units and content types are intentionally different domains:

* **Content types** (``video/mp4``, ``audio/wav``, ``image/png``) are
  validated by :mod:`arnold.pipeline.media_content` and appear on
  ``Port.content_type`` and ``PortRef.content_type`` fields.
* **Cost units** (``image``, ``video_second``, ``audio_second``, ``song``)
  are open semantic strings used by ``MediaUsage.unit`` and the media
  pricing table.

The C4 static-check media-pricing advisory maps content-type categories to
cost units for orientation only:

* ``image/*`` → ``image``
* ``video/*`` → ``video_second``
* ``audio/*`` → ``audio_second``

### MediaPricingEntry and Default Rows

``MediaPricingEntry`` is a frozen dataclass keyed by ``(provider, model, unit)``:

.. code-block:: python

   from arnold.pipeline import MediaPricingEntry
   from decimal import Decimal

   entry = MediaPricingEntry(
       provider="openai",
       model="dall-e-3",
       unit="image",
       cost_per_unit=Decimal("0.040"),
       source="official_docs_snapshot",
       source_url="https://openai.com/api/pricing/",
       pricing_version="ar3-media-snapshot-2026-06",
   )

``DEFAULT_MEDIA_PRICING`` ships three fixture rows (``dall-e-3 / image``,
``dall-e-3 / image_hd``, ``tts-1 / song``) marked as ``ar3-media-snapshot-2026-06``.
These are snapshots from published documentation, **not** guaranteed live rates.
Always allow override via the ``pricing_rows=`` keyword argument on
``compute_media_cost`` and ``account_media_cost_from_result``.

### compute_media_cost

The pure function ``compute_media_cost(provider, model, media_usage, *,
pricing_rows=DEFAULT_MEDIA_PRICING)`` returns one ``CostResult`` per
``MediaUsage`` item, in the same order:

.. code-block:: python

   from arnold.pipeline import MediaUsage, compute_media_cost

   usage = (
       MediaUsage(unit="image", count=1),
       MediaUsage(unit="image_hd", count=2),
   )
   results = compute_media_cost("openai", "dall-e-3", usage)
   for r in results:
       print(r.amount_usd, r.status, r.label)
   # 0.040 estimated  image (1)
   # 0.160 estimated  image_hd (2)

Pricing lookup is case-insensitive on provider and model; unit is matched
exactly (lowercased).  Items whose ``(provider, model, unit)`` has **no**
matching pricing row are returned with ``status='unknown'`` and
``amount_usd=None`` — never a silent zero, never an exception.

The returned ``CostResult`` carries:

* ``amount_usd: Decimal | None``
* ``status: CostStatus`` — ``"actual"``, ``"estimated"``, ``"included"``,
  or ``"unknown"``
* ``source: CostSource`` — provenance (``"official_docs_snapshot"``,
  ``"custom_contract"``, ``"none"``, etc.)
* ``label: str`` — human-readable unit + count
* ``fetched_at: datetime | None``
* ``pricing_version: str | None``
* ``notes: tuple[str, ...]``

### StepInvocationResult (Adapter Envelope)

Adapters that produce media output can return a ``StepInvocationResult``
envelope instead of a plain value:

.. code-block:: python

   from arnold.pipeline.step_invocation import (
       StepInvocationResult,
       unwrap_step_invocation_result,
   )
   from arnold.pipeline import MediaUsage

   class MyImageAdapter:
       def invoke(self, invocation):
           return StepInvocationResult(
               payload="image generation complete",
               media_usage=(MediaUsage(unit="image", count=1),),
           )

The envelope is **opt-in** — adapters that return plain values remain fully
compatible.  Consumers use ``unwrap_step_invocation_result`` to safely extract
``(payload, media_usage)`` regardless of which shape the adapter returned:

.. code-block:: python

   payload, media_usage = unwrap_step_invocation_result(adapter_result)
   # Plain return → (payload, ())
   # Envelope    → (payload, media_usage tuple)

When media usage is non-empty, ``AgentStep.run()`` and ``PanelReviewerStep.run()``
attach it to ``StepResult.hook_metadata['media_usage']``.  Steps without media
output (token/text-only) never emit the ``'media_usage'`` key.

### UsageExtraction (Model-Step Extractor)

Model steps can configure a ``_usage_extractor`` callable that receives
``(step_name, result_text)`` and returns either a plain ``dict`` (legacy) or
a ``UsageExtraction`` dataclass (structured, AR3+):

.. code-block:: python

   from arnold.pipeline import UsageExtraction, MediaUsage

   def my_extractor(step_name, result_text):
       return UsageExtraction(
           state_patch={"total_images": 3},
           media_usage=(
               MediaUsage(unit="image", count=3),
           ),
       )

``normalize_usage_extraction`` handles all three input shapes:

* ``UsageExtraction`` → ``(state_patch, media_usage)``
* ``dict`` (legacy) → ``(dict(extracted), ())`` — media usage **never**
  routed into hook metadata from legacy dicts
* Anything else → ``({}, ())`` — graceful degradation

The state patch produced by a ``UsageExtraction`` is **byte-identical** to
what the equivalent legacy dict would produce — the new path only adds the
``media_usage`` side channel.

### hook_metadata['media_usage'] (Carrier)

``StepResult.hook_metadata['media_usage']`` is the canonical carrier for
media usage in the executor pipeline.  It accumulates media usage from two
sources:

1. **Adapter envelope** — when the adapter returns a ``StepInvocationResult``
   with non-empty ``media_usage``.
2. **Model-step extractor** — when ``_usage_extractor`` returns a
   ``UsageExtraction`` with non-empty ``media_usage``.

Both sources are merged and attached only when the combined tuple is
non-empty.  Token/text-only steps never emit the key.

Downstream consumers (e.g. executor hooks) read it through:

.. code-block:: python

   from arnold.pipeline.hooks import account_media_cost_from_result

   cost_lines = account_media_cost_from_result(
       step_result,
       provider="openai",
       model="dall-e-3",
   )

The helper ``media_usage_from_hook_metadata`` normalises the value shape:

* ``None`` / absent → ``()``
* Single ``MediaUsage`` → one-element tuple
* ``list`` or ``tuple`` → validated tuple copy
* Malformed → ``TypeError`` (caught nonfatally by runtime hooks)

### Executor Hook Accounting (Opt-In)

``account_media_cost_from_result`` is a pure function that reads
``hook_metadata['media_usage']`` from a ``StepResult`` and returns
priced/unknown ``CostResult`` lines.  Hook implementations call it from
their ``on_step_end`` override:

.. code-block:: python

   from arnold.pipeline.hooks import NullExecutorHooks, account_media_cost_from_result
   from arnold.pipeline.executor import MediaCostAccumulator

   class MyHooks(NullExecutorHooks):
       def __init__(self):
           super().__init__()
           self.media = MediaCostAccumulator()

       def on_step_end(self, stage, ctx, result):
           self.media.account(result, provider="openai", model="dall-e-3")

   # After pipeline execution:
   for line in hooks.media.lines:
       print(line.amount_usd, line.status, line.label)

**Malformed metadata is handled nonfatally**: a ``TypeError`` in
``media_usage_from_hook_metadata`` is caught and a single ``CostResult``
with ``status='unknown'`` and a descriptive note is returned instead.
No exception propagates to abort the run.

When hooks are **not** configured (``NullExecutorHooks`` or ``hooks=None``),
no media accounting occurs and runs are unchanged — the helper is never
invoked.

### Agent-Loop Media Side Channel

The separate agent loop (``arnold/agent/run_agent.py``) has its own
media usage machinery that operates on tool-call identifiers rather
than ``StepResult.hook_metadata``:

* ``register_synthetic_tool_handler(tool_name, handler)`` — registers a
  synthetic tool handler that can produce ``ToolInvocationEnvelope`` results
  with ``media_usage``.
* ``_record_tool_call_media_usage(tool_call_id, media_usage)`` — stores
  normalised media usage keyed by tool-call ID, without touching the
  tool's text message content.
* ``get_tool_call_media_usage(tool_call_id)`` — returns the registered
  ``tuple[MediaUsage, ...]`` (or empty tuple for unknown IDs).

Known media amounts are added into ``session_estimated_cost_usd`` alongside
token costs.  Separate in-memory status/source/lines fields
(``session_media_cost_status``, ``session_media_cost_source``,
``session_media_cost_lines``) track media cost independently of token cost
(``session_cost_status`` / ``session_cost_source`` remain token-only for
backward compatibility).  These fields are session-summary only and are
**not** persisted to any database schema.

### Independent Media Budgets

Token and media costs are tracked on **independent** paths:

* Token cost: ``session_estimated_cost_usd``, ``session_cost_status``,
  ``session_cost_source``
* Media cost: ``session_media_cost_status``, ``session_media_cost_source``,
  ``session_media_cost_lines``

Known media amounts (``amount_usd is not None``) are added into the shared
``session_estimated_cost_usd`` total.  Unknown media lines are recorded in
``session_media_cost_lines`` but contribute nothing to the USD total
(no silent zero).  The status fields merge across multiple lines:
``"unknown"`` dominates when any line is unknown; ``"mixed"`` is used
when lines have different known statuses.

### C4 Media-Pricing Advisory (Static Check)

``run_c4_static_checks`` includes an advisory pass
(``_pass_media_pricing``) that scans every stage's ``produces`` and
``consumes`` ports for ``image/*``, ``video/*``, or ``audio/*`` content
types.  When a media category is detected:

* The pass maps it to a pricing unit (``image``, ``video_second``,
  ``audio_second``) and checks ``DEFAULT_MEDIA_PRICING`` coverage.
* Missing units produce **warnings** (never findings) with code
  ``missing_media_pricing``.
* An entirely empty pricing table produces an additional
  ``no_media_pricing_configured`` warning.
* Warnings are advisory only — ``StaticCheckReport.ok`` remains ``True``
  when only warnings are present, and ``arnold pipeline check`` exits 0.

### Example: Semantic Media Usage Without Blob Inspection

.. code-block:: python

   from arnold.pipeline import MediaUsage, compute_media_cost

   # Record that a step generated 3 standard images and 1 HD image.
   # No blobs are read — only the semantic counts matter.
   usage = (
       MediaUsage(unit="image", count=3),
       MediaUsage(unit="image_hd", count=1),
   )

   results = compute_media_cost("openai", "dall-e-3", usage)

   # Compute total known cost, flag unknown lines.
   total = None
   for line in results:
       if line.amount_usd is not None:
           total = (total or 0) + line.amount_usd
       else:
           print(f"  unknown: {line.notes}")

   # 3 × $0.040 + 1 × $0.080 = $0.200
   print(f"media cost: ${total} ({len(results)} lines)")

## Update Generated References Separately

When code-owned facts change, update the generated reference instead of editing
fact tables into these authored docs:

```bash
python scripts/generate_arnold_docs.py --write
python scripts/generate_arnold_docs.py --check
```

Authored pages should explain why and when to use a surface. Generated pages
should carry exact fields, constants, schemas, and inventories.
