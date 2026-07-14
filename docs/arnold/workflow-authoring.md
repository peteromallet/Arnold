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

## Tree Traces And Audit Skeletons

Every workflow attempt records a tree-shaped trace with stable path-addressed
correlation. The trace is produced by the native runtime and is serializable
without capturing live Python frames. Key trace fields:

- ``attempt_id`` — UUID hex string unique per attempt.
- ``run_path`` — trace-addressable path of the step in the invocation tree.
- ``parent_run_path`` — path of the parent workflow or iteration context.
- ``call_site_path`` — the authored literal ``id=`` that created this step.
- ``step_path`` — full trace tree coordinate.
- ``attempt_start``, ``step_outcome``, ``attempt_end`` — timing and outcome.

The audit skeleton is the evidence layer for conformance verification, not a
debug log. See [`audit.py`](../../arnold/pipeline/native/audit.py) for the
`AuditRecord` dataclass and `AuditHooks` producer.

## Path Resume

Resume targets a specific call-site path in the trace tree, not a bare stage
name. Paths are tree-shaped (e.g., ``root/second-review/review-verdict``) and
derived from authored ``id=`` values. Resume uses ``start_from_trace`` from
``arnold.pipeline.native`` with a target path and trace directory.

Path identity is stable across refactors and does not depend on runtime object
identity. Replay reuses the same static path plus recorded iteration
coordinates. See [`python-shaped-authoring-contract.md`](python-shaped-authoring-contract.md)
for the stable-path-identity rules.

## Platform Boundaries

Workflow source owns topology, stable identity, declared schemas, and policy
references. The platform (native runtime, executor, worker fleet, artifact
store) owns credential resolution, model binding, worker dispatch, artifact
storage, suspension/resume mechanics, and policy enforcement.

Workflow source must not:
- Read environment variables for secrets.
- Assume local filesystem paths survive worker migration.
- Call into worker-fleet or credential APIs.
- Dispatch to model providers directly from handler bodies.

Instead, declare intent as metadata. See
[`package-authoring-contract.md`](package-authoring-contract.md) for the
full platform-boundary contract.

## Boundary Contracts

Workflow boundaries — the handoffs between producers and consumers, gates that
require authority, and checkpoints where artifacts must be durable — are
declared through `BoundaryContract` instances from `arnold.workflow`. A
boundary contract makes explicit what artifacts must be produced, what state
deltas are expected, whether authority is required, and what evidence must be
recorded before a transition is considered complete.

### Defining A Boundary Contract

```python
from arnold.workflow import BoundaryContract, BoundaryPhase

review_gate = BoundaryContract(
    boundary_id="review.gate",
    workflow_id="my.workflow",
    row_id="my.workflow.review.gate.1",
    phase=BoundaryPhase.GATE,
    required_artifacts=("reviewed_output.json",),
    expected_state_delta={"review_stage": "gated"},
    phase_result_required=True,
    receipt_required=True,
)
```

Contracts are declarative data — they do not route, dispatch, or mutate state.
They live beside the workflow definition and are read by downstream consumers
(semantic-health checks, repair loops, auditors, conformance verification).

### Selecting Reusable Templates

Rather than hand-author every required field, use the reusable template system
in `arnold.workflow.boundary_templates`. Ten canonical profiles cover common
boundary shapes:

| Template Kind | Required-Field Highlights |
|---|---|
| `revision_boundary` | `revision_kind`, `revision_log_ref` |
| `validation_boundary` | `validation_kind`, `receipt_required` |
| `artifact_handoff_boundary` | `handoff_from`, `handoff_to`, `artifact_policy_ref` |
| `artifact_promotion` | `effect_id`, `promotion_kind`, `artifact_policy_ref` |
| `approval_boundary` | `approval_scope`, `authority_required` |
| `human_approval_waiver` | `approval_scope`, `suspension_route_id`, `resume_policy_ref` |
| `external_effect` | `effect_kind`, `effect_id` |
| `execution_custody` | `custody_scope`, `fresh_session` |
| `graph_join_fanout` | `fan_out_refs`, `fan_in_ref`, `join_requirements` |
| `external_witness` | `witness_ref`, `witness_kind` |

Select and extend a template:

```python
from dataclasses import replace
from arnold.workflow import (
    BoundaryTemplateKind,
    get_template,
    get_required_fields,
    check_contract_conformance,
)

# Get the canonical template
base = get_template(BoundaryTemplateKind.APPROVAL_BOUNDARY)

# Extend with domain-specific fields (in details, not core schema)
my_approval = replace(
    base,
    boundary_id="my.workflow.approval",
    workflow_id="my.workflow",
    row_id="my.workflow.approval.1",
    required_artifacts=("plan_doc.json", "review_verdict.json"),
    details={
        **base.details,
        "approval_scope": "plan_finalization",
    },
)

# Verify conformance against the template profile
missing = check_contract_conformance(
    my_approval,
    BoundaryTemplateKind.APPROVAL_BOUNDARY,
)
assert not missing, f"Missing: {missing}"
```

`check_contract_conformance` returns a tuple of missing required
field paths, or an empty tuple when conformant. It is pure data
validation — no imports, no IO, no mutation.

For a higher-level API that combines template selection with
customization, use `select_template`:

```python
from arnold.workflow import select_template, BoundaryTemplateKind

selection = select_template(
    BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY,
    boundary_id="my.workflow.handoff",
    workflow_id="my.workflow",
    required_artifacts=("output.json",),
    details={"handoff_from": "producer", "handoff_to": "consumer"},
)
# selection.template -> customized BoundaryContract
# selection.required_fields -> required-field frozenset for this kind
```

`select_template` returns a `TemplateSelection` with the kind, customized
template instance, and required-field profile in one call.

### Versioning Templates

Templates carry a stable `row_id` for version anchoring. Pin your workflow to
a template version and check for upgrades:

```python
from arnold.workflow import (
    pin_template_version,
    check_template_upgrade,
    deliberate_upgrade_template,
    BoundaryTemplateKind,
)

pin = pin_template_version(
    BoundaryTemplateKind.REVISION_BOUNDARY,
    workflow_id="my.workflow",
)

upgrade = check_template_upgrade(pin)
if upgrade.available:
    # Review the upgrade before applying it
    new_pin = deliberate_upgrade_template(pin)
```

Version pins are frozen dataclasses with `workflow_id`, `template_kind`,
`row_id`, and `pinned_at` fields. They carry a `required_fields` property
that resolves to the pinned kind's frozenset.

### Emitting Receipts And Evidence

When a workflow boundary is crossed, emit a `BoundaryReceipt` to record that
the contract was satisfied:

```python
from arnold.workflow import BoundaryReceipt, BoundaryOutcome

receipt = BoundaryReceipt(
    boundary_id="review.gate",
    workflow_id="my.workflow",
    outcome=BoundaryOutcome.ACCEPTED,
    artifact_refs=("reviewed_output.json",),
    phase_result_ref="review.gate.result",
)
```

Receipts must match the contract's `boundary_id` and `workflow_id`, cover all
`required_artifacts`, and include a terminal outcome. When
`authority_required=True`, receipts must also carry authority records.

Evidence (`BoundaryEvidence`) records durable proof that a boundary step
executed. Evidence is accumulated across attempts and read by conformance
verification.

### Conformance Verification

Verify that a workflow's boundary contracts, receipts, evidence, and template
profiles are internally consistent:

```python
from arnold.workflow import (
    WorkflowBoundarySpec,
    verify_boundary_conformance,
)

result = verify_boundary_conformance(
    workflow_id="my.workflow",
    boundaries={
        "b1": WorkflowBoundarySpec(
            boundary_id="b1",
            contract=review_gate,
            receipt=receipt,
            evidence=(evidence,),
            template_kind="revision_boundary",
        ),
    },
)

if not result.conformant:
    for v in result.violations:
        print(f"[{v.kind}] {v.description}")
```

`verify_boundary_conformance` is a read-only in-memory engine. It produces
violations across contract, receipt, authority, evidence, durable-effect,
graph-topology, and semantic-finding categories. It does not require a
running runtime, artifact store, or journal backend.

### Adapter Boundaries

The boundary vocabulary in `arnold.workflow` is generic. Domain-specific
concepts (Megaplan lifecycle transitions, chain milestones, PR transitions,
partial acceptance rules) belong in adapters, not in the core schema.

Adapters (`arnold_pipelines.megaplan.workflows.boundary_contracts`) import
from `arnold.workflow.boundary_templates` and re-use the generic helpers.
They add domain-specific template kinds and required-field profiles through
adapter-level `details.*` keys without modifying `BoundaryContract` fields.

When authoring a workflow, put extra domain fields in the `details` mapping.
Core required-field profiles only check for the keys declared in the generic
template — adapter checks enforce domain-specific requirements separately.

### Gating Native-Runtime Conformance

The generic conformance verifier is a pure in-memory engine. Full
runtime-integrated conformance (journal replay, artifact store resolution,
suspension/resume path checks) is gated behind the native runtime substrate
readiness signal. Until that substrate is available, pure in-memory
verification provides contract feedback at authoring time without requiring
a live executor or backend.

See [`workflow-boundary-contracts.md`](workflow-boundary-contracts.md) for
the complete boundary contract reference.

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
