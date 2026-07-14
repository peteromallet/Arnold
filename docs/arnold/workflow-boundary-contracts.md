# Workflow Boundary Contracts

Boundary contracts make durable workflow commitments explicit. A boundary
declares what artifacts must be produced, what state deltas are expected,
whether authority is required, and what evidence must be recorded before a
workflow transition can be considered complete. Conformance verification
checks these declarations against actual receipts and evidence without
mutating plan state.

## Adding A Boundary Contract

Every boundary starts with a `BoundaryContract` instance from
`arnold.workflow`:

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

A boundary contract lives beside the workflow definition, not inside it.
Contracts are declarative data — they do not route, dispatch, or mutate
state. They are the single source of truth that downstream consumers
(semantic-health checks, repair loops, auditors, and conformance
verification) read.

### Required Fields Per Contract Shape

Not every contract needs the same fields. A pure artifact handoff needs
a sender and receiver; an approval boundary needs an authority scope.
Use the reusable template profile system to get the right required-field
set for your boundary shape (see Selecting Reusable Templates below).

## Selecting Reusable Templates

The `arnold.workflow.boundary_templates` module provides ten canonical
template profiles. Each profile has a stable `BoundaryTemplateKind`
identifier, a frozenset of required fields, and a representative
`BoundaryContract` instance.

| Template Kind | Purpose |
|---|---|
| `revision_boundary` | Rework-cycle declarative evidence |
| `validation_boundary` | Validation-gate declarative evidence |
| `artifact_handoff_boundary` | Producer→consumer artifact transfer |
| `artifact_promotion` | Scratch→canonical artifact elevation |
| `approval_boundary` | Approval gate with required authority |
| `human_approval_waiver` | Deferred human-in-the-loop gate |
| `external_effect` | Side-effect emission as declarative contract |
| `execution_custody` | Custody handoff with fresh session |
| `graph_join_fanout` | Declared dependency and fan topology |
| `external_witness` | External attestation evidence |

Select a template by kind:

```python
from arnold.workflow import (
    BoundaryTemplateKind,
    get_template,
    get_required_fields,
    select_template,
)

# Get the canonical template instance
template = get_template(BoundaryTemplateKind.REVISION_BOUNDARY)

# Get just the required-field profile
fields = get_required_fields(BoundaryTemplateKind.REVISION_BOUNDARY)
# frozenset({'boundary_id', 'workflow_id', 'row_id', 'phase',
#            'required_artifacts', 'expected_state_delta',
#            'details.revision_kind', 'details.revision_log_ref'})

# Select and customize a template in one call (higher-level API)
selection = select_template(
    BoundaryTemplateKind.APPROVAL_BOUNDARY,
    boundary_id="my.workflow.approval",
    workflow_id="my.workflow",
    required_artifacts=("plan_doc.json", "review_verdict.json"),
    details={"approval_scope": "plan_finalization"},
)
# selection.kind    -> BoundaryTemplateKind.APPROVAL_BOUNDARY
# selection.template -> customized BoundaryContract
# selection.required_fields -> required-field frozenset for this kind

# Classify an existing contract
from arnold.workflow import classify_boundary_kind
kind = classify_boundary_kind(my_contract)
# Returns BoundaryTemplateKind if matched, None otherwise
```

All selection helpers are read-only and do not mutate contracts.

## Extending Templates

A reusable template is a starting point, not a straitjacket. Create a
concrete contract by copying the template and overriding the fields your
boundary needs:

```python
from dataclasses import replace
from arnold.workflow import get_template, BoundaryTemplateKind

base = get_template(BoundaryTemplateKind.APPROVAL_BOUNDARY)

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
```

Because `BoundaryContract` is a frozen dataclass, `dataclasses.replace`
is the recommended way to derive a concrete contract from a template.
Add domain-specific fields inside `details` — never promote them into
the core `BoundaryContract` schema.

### Extension Policy

A template's required-field profile is the minimum set. Your concrete
contract may add extra `details.*` keys for domain-specific needs, but
it must still satisfy the template's required fields. Conformance checks
verify that every required field is present and non-empty.

Templates that carry `authority_required=True` (approval, human-waiver,
execution-custody) must provide authority records through the receipt.
Templates that carry `receipt_required=True` (validation, promotion)
must provide a `BoundaryReceipt` that covers the declared artifacts.

## Versioning Templates

Templates carry a `row_id` that serves as a stable version anchor. When
a template's required-field profile changes in a breaking way, the
`row_id` should be bumped (e.g. from `template.revision_boundary.1` to
`template.revision_boundary.2`). Downstream consumers use version-pin
helpers to detect and manage upgrades:

```python
from arnold.workflow import (
    pin_template_version,
    check_template_upgrade,
    deliberate_upgrade_template,
    TemplateVersionPin,
)

# Pin a workflow to the current template version
pin: TemplateVersionPin = pin_template_version(
    BoundaryTemplateKind.REVISION_BOUNDARY,
    workflow_id="my.workflow",
)

# Check for available upgrades
upgrade = check_template_upgrade(pin)
if upgrade.available:
    print(f"Upgrade available: {upgrade.from_row_id} -> {upgrade.to_row_id}")

# Deliberately upgrade after review
new_pin = deliberate_upgrade_template(pin)
```

Version pins are frozen dataclasses with `workflow_id`, `template_kind`,
`row_id`, and `pinned_at` fields. They carry a `required_fields` property
that resolves to the frozenset for the pinned kind. Pins are
serializable and compatible with `check_template_compatibility()` from
`arnold.workflow.boundary_evidence`.

## Emitting Receipts And Evidence

A boundary contract declares what must be produced. Receipts and
evidence prove it happened.

### Receipts

A `BoundaryReceipt` is a structured record that a boundary was satisfied:

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

Receipts are produced by transition writers at the point a boundary is
crossed. The receipt must:
- Match the contract's `boundary_id` and `workflow_id`.
- Cover every artifact in `required_artifacts`.
- Include a terminal `BoundaryOutcome` (`ACCEPTED`, `REJECTED`, or
  `WAIVED`).
- Include authority records when `authority_required=True`.

### Evidence

`BoundaryEvidence` records capture durable proof that a boundary step
executed. Evidence is accumulated across attempts and is read by
conformance verification:

```python
from arnold.workflow import BoundaryEvidence

evidence = BoundaryEvidence(
    boundary_id="review.gate",
    workflow_id="my.workflow",
    attempt_id="attempt-1",
    step_outcome="completed",
    artifact_hashes={"reviewed_output.json": "sha256:abc123"},
)
```

Evidence emission is the producer's responsibility: the step that
generates the artifact records the evidence. Conformance verification
checks that evidence exists for every declared durable effect.

## Conformance Verification

The generic in-memory verifier checks whether a graph-shaped workflow's
declared boundary contracts, receipts, evidence, and template profiles
are internally consistent:

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

`verify_boundary_conformance` is a read-only function. It produces
`ConformanceViolation` records across these categories:

- **Contract-level**: missing required fields, template profile mismatch.
- **Receipt-level**: missing receipt, workflow/boundary/artifact
  mismatch, unexpected outcome.
- **Authority-level**: authority required but missing.
- **Evidence-level**: missing evidence, workflow/boundary mismatch.
- **Durable-effect level**: unverified effects, unverified phase results.
- **Graph-topology level**: dangling dependencies, fan-out, fan-in,
  join, cross-workflow references.
- **Semantic-finding level**: unresolved semantic finding references.

Use `verify_single_boundary` for a single boundary and
`classify_and_verify_boundaries` to auto-classify boundaries by kind
before verification. Use `verify_semantic_findings_against_boundaries`
to cross-check semantic findings against declared boundaries.

## Keeping Domain Concerns In Adapters

The core boundary contract vocabulary in `arnold.workflow` is generic.
Domain-specific concepts belong in adapters, not in the core schema.

### What Lives In Core (`arnold.workflow`)

- `BoundaryContract`, `BoundaryReceipt`, `BoundaryEvidence`.
- `BoundaryTemplateKind` enum with ten generic profile kinds.
- Required-field profiles as frozensets.
- Template selection, classification, versioning, and upgrade helpers.
- Conformance verification logic.

None of these modules import from `arnold_pipelines.megaplan` or any
domain-specific package. They operate on the generic primitives alone.

### What Lives In Adapters (`arnold_pipelines.megaplan`)

- Domain-specific template kinds (`AdapterTemplateKind` StrEnum).
- Adapter-specific required-field profiles for Megaplan concepts
  (lifecycle transitions, reducers, chain milestones, PR transitions,
  partial acceptance, fixture compatibility, promotion sync).
- Concrete `BoundaryContract` instances that map Megaplan workflow
  boundaries onto generic template profiles.
- Physical/external evidence mappings and partial acceptance rules.

Adapters import from `arnold.workflow.boundary_templates` and re-use the
generic helpers (`classify_boundary_kind`, `get_template`,
`check_contract_conformance`, etc.). They extend the generic surface
with domain-specific kinds and templates without modifying core schemas.

### The Detail Mapping Rule

When a domain concept needs extra fields, put them in the `details`
mapping of `BoundaryContract`:

```python
# In the adapter, NOT in core:
contract = replace(
    get_template(BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY),
    boundary_id="megaplan.promotion",
    workflow_id="arnold_pipelines.megaplan",
    details={
        "handoff_from": "scratch_area",
        "handoff_to": "canonical_store",
        "artifact_policy_ref": "megaplan-artifact-policy",
        # Megaplan-specific:
        "chain_milestone": "finalize",
        "pr_transition": "approve_and_merge",
    },
)
```

Core required-field profiles (e.g. `REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY`)
only check for `details.handoff_from`, `details.handoff_to`, and
`details.artifact_policy_ref`. Adapter-level required fields
(`details.chain_milestone`, `details.pr_transition`) are enforced by
adapter-specific checks, never by core conformance.

## Gating Native-Platform Runtime Conformance

The generic conformance verifier in `arnold.workflow.boundary_conformance`
is a pure in-memory engine. It does not depend on the native runtime
substrate (`arnold.pipeline.native`, `arnold.execution`).

Native-platform runtime conformance (full end-to-end verification with
live journal replay, artifact store resolution, and suspension/resume
semantics) is gated behind the runtime substrate readiness signal. Until
that substrate is available:

- **What works today**: Pure in-memory contract/receipt/evidence
  verification through `verify_boundary_conformance`. Template selection,
  version pinning, upgrade checks, and semantic-finding cross-checks.
  All read-only, no runtime dependency.

- **What is gated**: Runtime-integrated conformance that replays
  execution journals, resolves artifact stores, checks suspension/resume
  paths, or validates against live `WorkflowManifest` instances. These
  checks require a stable persistence backend and journal replay API.

To check if the native runtime substrate is ready before enabling
runtime conformance:

```python
# Placeholder for substrate readiness check.
# Replace with actual readiness signal when the substrate lands.
def _substrate_ready() -> bool:
    try:
        from arnold.execution.runner import run  # noqa: F401
        return True
    except ImportError:
        return False

if _substrate_ready():
    # Enable runtime-integrated conformance checks
    ...
```

The gating is intentional: pure conformance verification must work
without a running executor, artifact store, or journal backend. This
lets workflow authors get contract feedback at authoring time, before
any runtime integration.

## Checking Conformance At Authoring Time

Authors can verify boundary contracts during development without
standing up a full runtime:

```python
from arnold.workflow import (
    check_contract_conformance,
    get_required_fields,
    BoundaryTemplateKind,
)

# Check a single contract against its template
missing = check_contract_conformance(
    my_contract,
    BoundaryTemplateKind.REVISION_BOUNDARY,
)
if missing:
    print(f"Missing required fields: {missing}")
```

`check_contract_conformance` returns a tuple of missing required
field paths, or an empty tuple when the contract is conformant. It is
pure data validation — no imports, no IO, no mutation.

## Summary

1. **Define**: Create a `BoundaryContract` for each workflow boundary.
2. **Select**: Pick a reusable template kind that matches your boundary
   shape, or classify an existing contract.
3. **Extend**: Override template fields with `dataclasses.replace` and
   add domain details in the `details` mapping.
4. **Pin**: Version-pin your template with `pin_template_version` and
   check for upgrades with `check_template_upgrade`.
5. **Emit**: Produce `BoundaryReceipt` and `BoundaryEvidence` records
   at each boundary crossing.
6. **Verify**: Run `verify_boundary_conformance` to catch missing
   fields, mismatched receipts, unverified effects, and graph topology
   issues.
7. **Keep clean**: Put domain-specific concepts in adapter
   `details` mappings — never leak them into core schemas.
8. **Gate runtime**: Use pure in-memory verification now; integrate
   runtime checks when the native substrate is ready.
