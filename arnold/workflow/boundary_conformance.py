"""Generic in-memory verifier for graph-shaped workflows with boundary contracts.

This module provides a declarative, read-only conformance engine that checks
whether a graph-shaped workflow's declared boundary contracts, receipts,
evidence, durable effects, and template/profile metadata are internally
consistent and conformant.

It does **not** import from ``arnold_pipelines.megaplan`` — it is a generic
workflow-level tool built on :class:`BoundaryContract`,
:class:`BoundaryReceipt`, :class:`BoundaryEvidence`, :class:`BoundaryGraph`,
and the template/profile vocabulary from :mod:`arnold.workflow.boundary_templates`.

Key design invariants
---------------------

* **Read-only**: The verifier does not mutate contracts, receipts, evidence,
  or any plan state. It produces :class:`ConformanceViolation` records.
* **Graph-aware**: Boundaries are verified in the context of their declared
  dependencies, fan-out/fan-in topology (via :class:`BoundaryGraph`), and
  cross-boundary references.
* **Durable-effect aware**: Declared effects (required artifacts, expected
  state deltas, receipt/authority requirements) are checked against provided
  evidence and receipts.
* **Template/profile aware**: Each boundary can be checked against a
  :class:`BoundaryTemplateKind` profile for required-field completeness.

Usage
-----

.. code-block:: python

    from arnold.workflow.boundary_conformance import (
        WorkflowBoundarySpec,
        verify_boundary_conformance,
    )

    result = verify_boundary_conformance(
        workflow_id="my.workflow",
        boundaries={
            "b1": WorkflowBoundarySpec(
                boundary_id="b1",
                contract=my_contract,
                receipt=my_receipt,
                evidence=(my_evidence,),
                template_kind="revision_boundary",
            ),
        },
    )
    if not result.conformant:
        for v in result.violations:
            print(v.description)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from arnold.workflow.boundary_evidence import (
    BoundaryContract,
    BoundaryEvidence,
    BoundaryGraph,
    BoundaryOutcome,
    BoundaryReceipt,
    SemanticFinding,
)
from arnold.workflow.boundary_templates import (
    BoundaryTemplateKind,
    TemplateVersionPin,
    check_contract_conformance,
    check_template_upgrade,
    classify_boundary_kind,
    get_required_fields,
)
from arnold.workflow.boundary_evidence import TemplateCompatibility


# ── Conformance violation vocabulary ──────────────────────────────────────


class ConformanceViolationKind(StrEnum):
    """Stable identifiers for boundary conformance violation categories.

    Each member describes a distinct class of mismatch between declared
    contracts, provided evidence/receipts, graph topology, and template
    profile metadata.
    """

    # ── Contract-level ───────────────────────────────────────────────────
    MISSING_REQUIRED_FIELD = "missing_required_field"
    """A required field (top-level or ``details.``-nested) is absent or empty."""

    TEMPLATE_PROFILE_MISMATCH = "template_profile_mismatch"
    """The contract does not conform to its declared template profile kind."""

    # ── Receipt-level ────────────────────────────────────────────────────
    RECEIPT_REQUIRED_BUT_MISSING = "receipt_required_but_missing"
    """The contract requires a receipt (``receipt_required=True``) but none was provided."""

    RECEIPT_WORKFLOW_MISMATCH = "receipt_workflow_mismatch"
    """Receipt ``workflow_id`` does not match the contract or the workflow under verification."""

    RECEIPT_BOUNDARY_MISMATCH = "receipt_boundary_mismatch"
    """Receipt ``boundary_id`` does not match the contract's ``boundary_id``."""

    RECEIPT_ARTIFACT_MISMATCH = "receipt_artifact_mismatch"
    """Receipt ``artifact_refs`` do not cover the contract's ``required_artifacts``."""

    RECEIPT_OUTCOME_UNEXPECTED = "receipt_outcome_unexpected"
    """Receipt outcome is not a terminal or acceptable outcome for this boundary."""

    # ── Authority-level ──────────────────────────────────────────────────
    AUTHORITY_REQUIRED_BUT_MISSING = "authority_required_but_missing"
    """The contract requires authority (``authority_required=True``) but the receipt lacks authority records."""

    # ── Evidence-level ───────────────────────────────────────────────────
    EVIDENCE_MISSING_FOR_CONTRACT = "evidence_missing_for_contract"
    """The contract declares requirements but no evidence was provided for this boundary."""

    EVIDENCE_WORKFLOW_MISMATCH = "evidence_workflow_mismatch"
    """Evidence ``workflow_id`` does not match the contract or the workflow under verification."""

    EVIDENCE_BOUNDARY_MISMATCH = "evidence_boundary_mismatch"
    """Evidence ``boundary_id`` does not match the contract's ``boundary_id``."""

    # ── Durable-effect level ─────────────────────────────────────────────
    DURABLE_EFFECT_UNVERIFIED = "durable_effect_unverified"
    """A durable effect declared in the contract has no corresponding evidence or receipt."""

    PHASE_RESULT_UNVERIFIED = "phase_result_unverified"
    """The contract requires a phase result (``phase_result_required=True``) but no receipt phase result ref was provided."""

    # ── Graph-topology level ─────────────────────────────────────────────
    GRAPH_DANGLING_DEPENDENCY = "graph_dangling_dependency"
    """A boundary declares a dependency on another boundary that is not present in the workflow."""

    GRAPH_DANGLING_FAN_OUT = "graph_dangling_fan_out"
    """A boundary declares a fan-out target that is not present in the workflow."""

    GRAPH_DANGLING_FAN_IN = "graph_dangling_fan_in"
    """A boundary declares a fan-in source that is not present in the workflow."""

    GRAPH_DANGLING_JOIN = "graph_dangling_join"
    """A boundary declares a join target that is not present in the workflow."""

    GRAPH_DANGLING_CROSS_WORKFLOW = "graph_dangling_cross_workflow"
    """A boundary declares a cross-workflow reference that cannot be resolved."""

    # ── Semantic-finding level ───────────────────────────────────────────
    SEMANTIC_FINDING_UNRESOLVED = "semantic_finding_unresolved"
    """A semantic finding references a boundary or contract that does not exist in the workflow."""


# ── Conformance violation record ──────────────────────────────────────────


@dataclass(frozen=True)
class ConformanceViolation:
    """A single conformance failure detected during verification.

    Each violation records the boundary where the failure was detected,
    the kind of failure, a human-readable description, and structured
    detail for downstream consumers.
    """

    boundary_id: str
    """The boundary where the violation was detected."""

    kind: ConformanceViolationKind
    """The category of violation."""

    description: str
    """Human-readable description of the failure."""

    detail: Mapping[str, Any] = field(default_factory=dict)
    """Structured detail (e.g. missing field names, expected vs actual values)."""

    def __post_init__(self) -> None:
        if not self.boundary_id:
            raise ValueError("ConformanceViolation.boundary_id must be non-empty")
        if not self.description:
            raise ValueError("ConformanceViolation.description must be non-empty")
        # Freeze detail mapping
        if self.detail:
            from types import MappingProxyType

            object.__setattr__(
                self, "detail",
                MappingProxyType({str(k): _freeze_value(v) for k, v in self.detail.items()}),
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe violation payload."""
        return {
            "boundary_id": self.boundary_id,
            "kind": self.kind.value,
            "description": self.description,
            "detail": _thaw_value(self.detail),
        }


# ── Conformance result ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ConformanceResult:
    """Overall result of a workflow boundary conformance verification.

    Produced by :func:`verify_boundary_conformance` and consumed by
    operator tooling, status snapshots, and auditor reports.
    """

    workflow_id: str
    """The workflow that was verified."""

    violations: tuple[ConformanceViolation, ...] = ()
    """All conformance violations detected, in deterministic order."""

    boundary_count: int = 0
    """Number of boundaries in the verified workflow."""

    receipt_count: int = 0
    """Number of boundaries that provided a receipt."""

    evidence_count: int = 0
    """Number of boundaries that provided at least one piece of evidence."""

    @property
    def conformant(self) -> bool:
        """``True`` when zero violations were detected."""
        return len(self.violations) == 0

    @property
    def violation_count(self) -> int:
        """Total number of violations."""
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe conformance result payload."""
        return {
            "workflow_id": self.workflow_id,
            "conformant": self.conformant,
            "violation_count": self.violation_count,
            "boundary_count": self.boundary_count,
            "receipt_count": self.receipt_count,
            "evidence_count": self.evidence_count,
            "violations": [v.to_dict() for v in self.violations],
        }


# ── Workflow boundary specification ──────────────────────────────────────


@dataclass(frozen=True)
class WorkflowBoundarySpec:
    """Input specification for a single boundary in a workflow graph.

    Bundles the contract, optional receipt, optional evidence items,
    optional template kind, declared dependencies, and optional graph
    topology metadata for a single boundary vertex.
    """

    boundary_id: str
    """Unique identifier for this boundary within the workflow."""

    contract: BoundaryContract
    """The declared boundary contract (required effects, artifacts, authority)."""

    receipt: BoundaryReceipt | None = None
    """Optional receipt proving the boundary completed with coherent effects."""

    evidence: tuple[BoundaryEvidence, ...] = ()
    """Optional raw evidence items associated with this boundary."""

    template_kind: BoundaryTemplateKind | str | None = None
    """Optional template profile kind for required-field conformance checking."""

    dependencies: tuple[str, ...] = ()
    """Boundary IDs that this boundary depends on (must exist in the workflow)."""

    graph_spec: BoundaryGraph | None = None
    """Optional declared dependency/join/fan-out graph topology metadata."""

    def __post_init__(self) -> None:
        if not self.boundary_id:
            raise ValueError("WorkflowBoundarySpec.boundary_id must be non-empty")
        object.__setattr__(
            self, "evidence",
            tuple(
                e if isinstance(e, BoundaryEvidence) else BoundaryEvidence(**e)
                for e in self.evidence
            ),
        )
        object.__setattr__(
            self, "dependencies",
            tuple(str(d) for d in self.dependencies),
        )
        if self.template_kind is not None and not isinstance(self.template_kind, BoundaryTemplateKind):
            object.__setattr__(self, "template_kind", BoundaryTemplateKind(self.template_kind))


# ── Verification entry point ─────────────────────────────────────────────


def verify_boundary_conformance(
    workflow_id: str,
    boundaries: Mapping[str, WorkflowBoundarySpec],
    *,
    template_kinds: Mapping[str, BoundaryTemplateKind | str] | None = None,
    version_pins: Mapping[str, TemplateVersionPin] | None = None,
) -> ConformanceResult:
    """Verify graph-shaped workflow boundary conformance in memory.

    Checks every boundary in *boundaries* for:
    * Contract-template conformance (required-field completeness).
    * Native-platform-only metadata without a shared template profile.
    * Template-version pin compatibility against current profiles.
    * Receipt presence, coherence, and authority.
    * Evidence presence and coherence.
    * Durable-effect verification (artifacts, state deltas, phase results).
    * Graph-topology integrity (dangling dependencies, fan-out/fan-in refs).

    Args:
        workflow_id: The workflow identifier being verified.
        boundaries: Mapping of ``boundary_id`` → :class:`WorkflowBoundarySpec`.
        template_kinds: Optional mapping of ``boundary_id`` → template kind
            to use for conformance checking.  Overrides
            ``WorkflowBoundarySpec.template_kind`` when both are provided.
        version_pins: Optional mapping of ``boundary_id`` → version pin
            to check for template-version compatibility.  When a pin is
            present, the verifier confirms the pinned version is compatible
            with the current template profile for that boundary's kind.

    Returns:
        A :class:`ConformanceResult` with all violations found.

    Raises:
        ValueError: If *workflow_id* is empty.
    """
    if not workflow_id:
        raise ValueError("workflow_id must be non-empty")

    violations: list[ConformanceViolation] = []
    boundary_ids = frozenset(boundaries.keys())
    receipt_count = 0
    evidence_count = 0

    # Resolve template_kinds mapping — merge parameter with spec-level hints
    resolved_templates: dict[str, BoundaryTemplateKind] = {}
    for bid, spec in boundaries.items():
        tk = None
        if template_kinds and bid in template_kinds:
            tk = template_kinds[bid]
        elif spec.template_kind is not None:
            tk = spec.template_kind
        if tk is not None:
            resolved_templates[bid] = BoundaryTemplateKind(tk)

    # ── Pre-loop: native-platform-only metadata detection ─────────────────
    for boundary_id, spec in sorted(boundaries.items()):
        resolved_kind = resolved_templates.get(boundary_id)
        _check_native_platform_only_metadata(
            spec.contract, boundary_id, resolved_kind, violations,
        )

    for boundary_id, spec in sorted(boundaries.items()):
        contract = spec.contract
        receipt = spec.receipt
        evidence_items = spec.evidence
        graph_spec = spec.graph_spec
        deps = spec.dependencies

        # ── 1. Contract-template conformance ─────────────────────────────
        kind = resolved_templates.get(boundary_id)
        if kind is not None:
            missing_fields = check_contract_conformance(contract, kind)
            if missing_fields:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
                        description=(
                            f"Contract for boundary '{boundary_id}' is missing required fields "
                            f"for template kind '{kind.value}': {', '.join(missing_fields)}"
                        ),
                        detail={
                            "template_kind": kind.value,
                            "missing_fields": list(missing_fields),
                        },
                    )
                )

        # Also check for generic contract completeness independent of template
        _check_contract_basics(contract, boundary_id, violations)

        # ── 1b. Template-version compatibility ────────────────────────────
        if version_pins and boundary_id in version_pins:
            _check_template_version_compatibility(
                boundary_id, version_pins[boundary_id], violations,
            )

        # ── 2. Receipt checks ────────────────────────────────────────────
        if contract.receipt_required:
            if receipt is None:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.RECEIPT_REQUIRED_BUT_MISSING,
                        description=(
                            f"Contract for boundary '{boundary_id}' requires a receipt "
                            f"(receipt_required=True) but no receipt was provided."
                        ),
                        detail={"receipt_required": True},
                    )
                )

        if receipt is not None:
            receipt_count += 1
            _check_receipt_coherence(contract, receipt, boundary_id, workflow_id, violations)

        # ── 3. Evidence checks ───────────────────────────────────────────
        if evidence_items:
            evidence_count += 1
            for ev in evidence_items:
                _check_evidence_coherence(contract, ev, boundary_id, workflow_id, violations)
        else:
            # Evidence is only flagged as missing when there are declared
            # requirements that are NOT already satisfied by the receipt.
            # If a receipt covers all required artifacts, authority, and
            # phase result, separate evidence is not strictly required.
            _needs_evidence = False
            if contract.required_artifacts:
                if receipt is None:
                    _needs_evidence = True
                else:
                    covered = set(receipt.artifact_refs)
                    if not set(contract.required_artifacts).issubset(covered):
                        _needs_evidence = True
            if contract.phase_result_required:
                if receipt is None or receipt.phase_result_ref is None:
                    _needs_evidence = True
            if contract.authority_required:
                if receipt is None or not receipt.authority_records:
                    _needs_evidence = True

            if _needs_evidence:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.EVIDENCE_MISSING_FOR_CONTRACT,
                        description=(
                            f"Contract for boundary '{boundary_id}' declares requirements "
                            f"(artifacts, phase result, or authority) that are not fully "
                            f"satisfied by a receipt and no evidence was provided."
                        ),
                        detail={
                            "required_artifacts": list(contract.required_artifacts),
                            "phase_result_required": contract.phase_result_required,
                            "authority_required": contract.authority_required,
                        },
                    )
                )

        # ── 4. Authority checks ──────────────────────────────────────────
        if contract.authority_required:
            if receipt is None:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.AUTHORITY_REQUIRED_BUT_MISSING,
                        description=(
                            f"Contract for boundary '{boundary_id}' requires authority "
                            f"(authority_required=True) but no receipt (and thus no authority records) "
                            f"was provided."
                        ),
                        detail={"authority_required": True},
                    )
                )
            elif not receipt.authority_records:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.AUTHORITY_REQUIRED_BUT_MISSING,
                        description=(
                            f"Contract for boundary '{boundary_id}' requires authority "
                            f"(authority_required=True) but the receipt contains no authority records."
                        ),
                        detail={
                            "authority_required": True,
                            "receipt_authority_count": 0,
                        },
                    )
                )

        # ── 5. Durable-effect verification ───────────────────────────────
        _check_durable_effects(
            contract, receipt, evidence_items, boundary_id, violations,
        )

        # ── 6. Phase result verification ─────────────────────────────────
        if contract.phase_result_required:
            if receipt is None:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.PHASE_RESULT_UNVERIFIED,
                        description=(
                            f"Contract for boundary '{boundary_id}' requires a phase result "
                            f"(phase_result_required=True) but no receipt was provided."
                        ),
                        detail={"phase_result_required": True},
                    )
                )
            elif receipt.phase_result_ref is None:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.PHASE_RESULT_UNVERIFIED,
                        description=(
                            f"Contract for boundary '{boundary_id}' requires a phase result "
                            f"(phase_result_required=True) but the receipt has no phase_result_ref."
                        ),
                        detail={
                            "phase_result_required": True,
                            "phase_result_ref": None,
                        },
                    )
                )

        # ── 7. Dependency checks ─────────────────────────────────────────
        for dep_id in deps:
            if dep_id not in boundary_ids:
                violations.append(
                    ConformanceViolation(
                        boundary_id=boundary_id,
                        kind=ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY,
                        description=(
                            f"Boundary '{boundary_id}' declares a dependency on "
                            f"'{dep_id}', which is not present in the workflow."
                        ),
                        detail={
                            "declared_dependency": dep_id,
                            "available_boundaries": sorted(boundary_ids),
                        },
                    )
                )

        # ── 8. Graph-topology checks (BoundaryGraph) ─────────────────────
        if graph_spec is not None:
            _check_graph_topology(
                graph_spec, boundary_id, boundary_ids, violations,
            )

    return ConformanceResult(
        workflow_id=workflow_id,
        violations=tuple(violations),
        boundary_count=len(boundaries),
        receipt_count=receipt_count,
        evidence_count=evidence_count,
    )


# ── Individual check functions ────────────────────────────────────────────


def _check_contract_basics(
    contract: BoundaryContract,
    boundary_id: str,
    violations: list[ConformanceViolation],
) -> None:
    """Check basic contract integrity independent of template profiles."""
    if not contract.required_artifacts and not contract.expected_state_delta:
        # Not necessarily a violation, but flag if both are empty and
        # receipt_required or authority_required is True — the contract
        # declares expectations but no durable effects.
        if contract.receipt_required or contract.authority_required:
            violations.append(
                ConformanceViolation(
                    boundary_id=boundary_id,
                    kind=ConformanceViolationKind.DURABLE_EFFECT_UNVERIFIED,
                    description=(
                        f"Contract for boundary '{boundary_id}' declares receipt/authority "
                        f"requirements but has no required artifacts or expected state delta — "
                        f"durable effects cannot be verified."
                    ),
                    detail={
                        "required_artifacts": [],
                        "expected_state_delta_empty": True,
                        "receipt_required": contract.receipt_required,
                        "authority_required": contract.authority_required,
                    },
                )
            )


def _check_receipt_coherence(
    contract: BoundaryContract,
    receipt: BoundaryReceipt,
    boundary_id: str,
    workflow_id: str,
    violations: list[ConformanceViolation],
) -> None:
    """Check that a receipt is coherent with its contract and the workflow."""
    # workflow_id match
    if receipt.workflow_id != workflow_id and receipt.workflow_id != contract.workflow_id:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.RECEIPT_WORKFLOW_MISMATCH,
                description=(
                    f"Receipt for boundary '{boundary_id}' has workflow_id "
                    f"'{receipt.workflow_id}', which matches neither the verification "
                    f"workflow '{workflow_id}' nor the contract workflow "
                    f"'{contract.workflow_id}'."
                ),
                detail={
                    "receipt_workflow_id": receipt.workflow_id,
                    "contract_workflow_id": contract.workflow_id,
                    "verification_workflow_id": workflow_id,
                },
            )
        )

    # boundary_id match
    if receipt.boundary_id != boundary_id and receipt.boundary_id != contract.boundary_id:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.RECEIPT_BOUNDARY_MISMATCH,
                description=(
                    f"Receipt for boundary '{boundary_id}' has boundary_id "
                    f"'{receipt.boundary_id}', which matches neither the spec "
                    f"boundary_id '{boundary_id}' nor the contract boundary_id "
                    f"'{contract.boundary_id}'."
                ),
                detail={
                    "receipt_boundary_id": receipt.boundary_id,
                    "contract_boundary_id": contract.boundary_id,
                    "spec_boundary_id": boundary_id,
                },
            )
        )

    # artifact coverage
    required = set(contract.required_artifacts)
    provided = set(receipt.artifact_refs)
    missing_artifacts = required - provided
    if missing_artifacts:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.RECEIPT_ARTIFACT_MISMATCH,
                description=(
                    f"Receipt for boundary '{boundary_id}' is missing required artifacts: "
                    f"{', '.join(sorted(missing_artifacts))}"
                ),
                detail={
                    "required_artifacts": list(contract.required_artifacts),
                    "receipt_artifacts": list(receipt.artifact_refs),
                    "missing": sorted(missing_artifacts),
                },
            )
        )

    # outcome check — non-terminal outcomes
    if receipt.outcome is not None:
        _non_terminal_outcomes = frozenset({
            BoundaryOutcome.INCOMPLETE,
            BoundaryOutcome.PARTIAL,
            BoundaryOutcome.AWAITING_EXTERNAL_EVIDENCE,
        })
        if receipt.outcome in _non_terminal_outcomes:
            violations.append(
                ConformanceViolation(
                    boundary_id=boundary_id,
                    kind=ConformanceViolationKind.RECEIPT_OUTCOME_UNEXPECTED,
                    description=(
                        f"Receipt for boundary '{boundary_id}' has non-terminal outcome "
                        f"'{receipt.outcome.value}', which indicates the boundary is not "
                        f"complete."
                    ),
                    detail={
                        "outcome": receipt.outcome.value,
                    },
                )
            )


def _check_evidence_coherence(
    contract: BoundaryContract,
    evidence: BoundaryEvidence,
    boundary_id: str,
    workflow_id: str,
    violations: list[ConformanceViolation],
) -> None:
    """Check that an evidence record is coherent with its contract and the workflow."""
    if evidence.workflow_id != workflow_id and evidence.workflow_id != contract.workflow_id:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.EVIDENCE_WORKFLOW_MISMATCH,
                description=(
                    f"Evidence '{evidence.evidence_id}' for boundary '{boundary_id}' has "
                    f"workflow_id '{evidence.workflow_id}', which matches neither the "
                    f"verification workflow '{workflow_id}' nor the contract workflow "
                    f"'{contract.workflow_id}'."
                ),
                detail={
                    "evidence_id": evidence.evidence_id,
                    "evidence_workflow_id": evidence.workflow_id,
                    "contract_workflow_id": contract.workflow_id,
                    "verification_workflow_id": workflow_id,
                },
            )
        )

    if evidence.boundary_id != boundary_id and evidence.boundary_id != contract.boundary_id:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.EVIDENCE_BOUNDARY_MISMATCH,
                description=(
                    f"Evidence '{evidence.evidence_id}' for boundary '{boundary_id}' has "
                    f"boundary_id '{evidence.boundary_id}', which matches neither the spec "
                    f"boundary_id '{boundary_id}' nor the contract boundary_id "
                    f"'{contract.boundary_id}'."
                ),
                detail={
                    "evidence_id": evidence.evidence_id,
                    "evidence_boundary_id": evidence.boundary_id,
                    "contract_boundary_id": contract.boundary_id,
                    "spec_boundary_id": boundary_id,
                },
            )
        )


def _check_durable_effects(
    contract: BoundaryContract,
    receipt: BoundaryReceipt | None,
    evidence_items: tuple[BoundaryEvidence, ...],
    boundary_id: str,
    violations: list[ConformanceViolation],
) -> None:
    """Verify that declared durable effects have corresponding evidence."""
    if not contract.required_artifacts:
        return

    # Check if any required artifact is covered by receipt or evidence
    required = set(contract.required_artifacts)

    covered: set[str] = set()
    if receipt is not None:
        covered.update(receipt.artifact_refs)
    for ev in evidence_items:
        covered.update(ev.artifact_refs)

    uncovered = required - covered
    if uncovered:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.DURABLE_EFFECT_UNVERIFIED,
                description=(
                    f"Contract for boundary '{boundary_id}' requires artifacts "
                    f"{', '.join(sorted(uncovered))} that are not covered by any "
                    f"receipt or evidence."
                ),
                detail={
                    "required_artifacts": list(contract.required_artifacts),
                    "covered_by_receipt": (
                        list(receipt.artifact_refs) if receipt else []
                    ),
                    "covered_by_evidence": sorted(
                        set(a for ev in evidence_items for a in ev.artifact_refs)
                    ),
                    "uncovered": sorted(uncovered),
                },
            )
        )


def _check_graph_topology(
    graph_spec: BoundaryGraph,
    boundary_id: str,
    boundary_ids: frozenset[str],
    violations: list[ConformanceViolation],
) -> None:
    """Check graph topology integrity for a single boundary's graph spec."""
    # Fan-out refs
    for fan_ref in graph_spec.fan_out_refs:
        if fan_ref not in boundary_ids:
            violations.append(
                ConformanceViolation(
                    boundary_id=boundary_id,
                    kind=ConformanceViolationKind.GRAPH_DANGLING_FAN_OUT,
                    description=(
                        f"Boundary '{boundary_id}' declares fan-out target "
                        f"'{fan_ref}', which is not present in the workflow."
                    ),
                    detail={
                        "fan_out_ref": fan_ref,
                        "available_boundaries": sorted(boundary_ids),
                    },
                )
            )

    # Fan-in ref
    if graph_spec.fan_in_ref is not None and graph_spec.fan_in_ref not in boundary_ids:
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.GRAPH_DANGLING_FAN_IN,
                description=(
                    f"Boundary '{boundary_id}' declares fan-in source "
                    f"'{graph_spec.fan_in_ref}', which is not present in the workflow."
                ),
                detail={
                    "fan_in_ref": graph_spec.fan_in_ref,
                    "available_boundaries": sorted(boundary_ids),
                },
            )
        )

    # Dependencies in graph_spec (separate from WorkflowBoundarySpec.dependencies)
    for dep in graph_spec.dependencies:
        if dep not in boundary_ids:
            violations.append(
                ConformanceViolation(
                    boundary_id=boundary_id,
                    kind=ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY,
                    description=(
                        f"Boundary '{boundary_id}' graph spec declares a dependency on "
                        f"'{dep}', which is not present in the workflow."
                    ),
                    detail={
                        "declared_dependency": dep,
                        "available_boundaries": sorted(boundary_ids),
                    },
                )
            )

    # Joins
    for join_ref in graph_spec.joins:
        if join_ref not in boundary_ids:
            violations.append(
                ConformanceViolation(
                    boundary_id=boundary_id,
                    kind=ConformanceViolationKind.GRAPH_DANGLING_JOIN,
                    description=(
                        f"Boundary '{boundary_id}' declares a join with "
                        f"'{join_ref}', which is not present in the workflow."
                    ),
                    detail={
                        "join_ref": join_ref,
                        "available_boundaries": sorted(boundary_ids),
                    },
                )
            )


# ── Convenience: verify a single boundary in isolation ────────────────────


def verify_single_boundary(
    boundary: WorkflowBoundarySpec,
    *,
    workflow_id: str = "arnold.workflow",
    template_kind: BoundaryTemplateKind | str | None = None,
    version_pin: TemplateVersionPin | None = None,
) -> ConformanceResult:
    """Verify a single boundary in isolation.

    Convenience wrapper around :func:`verify_boundary_conformance` for
    checking a lone boundary without graph topology.

    Args:
        boundary: The boundary specification to verify.
        workflow_id: Workflow identifier (defaults to ``"arnold.workflow"``).
        template_kind: Optional template profile kind for conformance checking.
        version_pin: Optional version pin for template-version compatibility checking.

    Returns:
        A :class:`ConformanceResult` for the single-boundary workflow.
    """
    tk_map: dict[str, BoundaryTemplateKind | str] | None = None
    if template_kind is not None:
        tk_map = {boundary.boundary_id: template_kind}
    elif boundary.template_kind is not None:
        tk_map = {boundary.boundary_id: boundary.template_kind}

    vp_map: dict[str, TemplateVersionPin] | None = None
    if version_pin is not None:
        vp_map = {boundary.boundary_id: version_pin}

    return verify_boundary_conformance(
        workflow_id=workflow_id,
        boundaries={boundary.boundary_id: boundary},
        template_kinds=tk_map,
        version_pins=vp_map,
    )


# ── Native-platform-only metadata detection ────────────────────────────────


_NATIVE_PLATFORM_ONLY_KEYS: frozenset[str] = frozenset({
    "native_platform_only",
    "native_platform_metadata",
})


def _check_native_platform_only_metadata(
    contract: BoundaryContract,
    boundary_id: str,
    resolved_template_kind: BoundaryTemplateKind | None,
    violations: list[ConformanceViolation],
) -> None:
    """Emit TEMPLATE_PROFILE_MISMATCH when a contract relies on native-platform-only
    metadata without also declaring a shared BoundaryTemplateKind profile.

    Design invariant (SD3): Megaplan-specific fields stay in adapter details
    and must not be promoted into generic core contracts.  A contract whose
    ``details`` contain ``native_platform_only`` (truthy) or
    ``native_platform_metadata`` is using platform-specific metadata; when
    it does **not** declare a shared template kind, the boundary cannot be
    generically verified and must be flagged.
    """
    if resolved_template_kind is not None:
        # A shared profile is declared — native-platform metadata is
        # allowed as supplementary adapter detail.
        return

    details = dict(contract.details)
    if not _NATIVE_PLATFORM_ONLY_KEYS.intersection(details):
        return

    native_only = details.get("native_platform_only", None)
    native_meta = details.get("native_platform_metadata", None)

    # Flag only when native_platform_only is explicitly truthy or when
    # native_platform_metadata is a non-empty mapping with no declared profile.
    # Use Mapping (not dict) because ``details`` values may be MappingProxyType.
    triggers = False
    if native_only:
        triggers = True
    if isinstance(native_meta, Mapping) and native_meta:
        triggers = True

    if not triggers:
        return

    violations.append(
        ConformanceViolation(
            boundary_id=boundary_id,
            kind=ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH,
            description=(
                f"Contract for boundary '{boundary_id}' uses native-platform-only "
                f"metadata ({', '.join(sorted(_NATIVE_PLATFORM_ONLY_KEYS.intersection(details)))}) "
                f"without declaring a shared BoundaryTemplateKind profile.  "
                f"Platform-specific metadata must be accompanied by a declared template kind "
                f"so the boundary can be generically verified."
            ),
            detail={
                "native_platform_only": bool(native_only),
                "has_native_platform_metadata": isinstance(native_meta, Mapping) and bool(native_meta),
                "resolved_template_kind": None,
            },
        )
    )


def _check_template_version_compatibility(
    boundary_id: str,
    version_pin: TemplateVersionPin,
    violations: list[ConformanceViolation],
) -> None:
    """Emit TEMPLATE_PROFILE_MISMATCH when a template version pin is
    incompatible with the current template profile.

    Uses :func:`check_template_upgrade` from
    :mod:`arnold.workflow.boundary_templates` to compare the pinned version
    against the current profile and flags breaking or incompatible changes.
    """
    result = check_template_upgrade(
        kind=version_pin.kind,
        from_version=version_pin.version,
        to_version=version_pin.version,
        template_id=version_pin.template_id,
    )

    if result.compatibility in (
        TemplateCompatibility.BREAKING_CHANGE,
        TemplateCompatibility.INCOMPATIBLE_RANGE,
    ):
        violations.append(
            ConformanceViolation(
                boundary_id=boundary_id,
                kind=ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH,
                description=(
                    f"Boundary '{boundary_id}' has an incompatible template version pin "
                    f"for kind '{version_pin.kind.value}' at version '{version_pin.version}': "
                    f"compatibility is '{result.compatibility.value}'."
                ),
                detail={
                    "template_kind": version_pin.kind.value,
                    "pinned_version": version_pin.version,
                    "compatibility": result.compatibility.value,
                    "template_id": version_pin.template_id,
                },
            )
        )


# ── Semantic finding cross-reference verification ─────────────────────────


def verify_semantic_findings_against_boundaries(
    findings: tuple[SemanticFinding, ...],
    boundaries: Mapping[str, WorkflowBoundarySpec],
) -> tuple[ConformanceViolation, ...]:
    """Verify that semantic findings reference boundaries that exist in the workflow.

    Each finding's ``boundary_id`` is checked against the set of known
    boundary IDs.  Findings referencing unknown boundaries are reported as
    ``SEMANTIC_FINDING_UNRESOLVED`` violations.

    Args:
        findings: Semantic findings to check.
        boundaries: The workflow boundary specifications.

    Returns:
        Tuple of violations (empty when all findings reference known boundaries).
    """
    violations: list[ConformanceViolation] = []
    boundary_ids = frozenset(boundaries.keys())

    for finding in findings:
        if finding.boundary_id not in boundary_ids:
            violations.append(
                ConformanceViolation(
                    boundary_id=finding.boundary_id,
                    kind=ConformanceViolationKind.SEMANTIC_FINDING_UNRESOLVED,
                    description=(
                        f"Semantic finding '{finding.finding_id}' references boundary "
                        f"'{finding.boundary_id}', which is not present in the workflow."
                    ),
                    detail={
                        "finding_id": finding.finding_id,
                        "referenced_boundary_id": finding.boundary_id,
                        "available_boundaries": sorted(boundary_ids),
                    },
                )
            )

    return tuple(violations)


# ── Convenience: auto-classify boundaries against templates ───────────────


def classify_and_verify_boundaries(
    workflow_id: str,
    boundaries: Mapping[str, WorkflowBoundarySpec],
    *,
    version_pins: Mapping[str, TemplateVersionPin] | None = None,
) -> ConformanceResult:
    """Auto-classify each boundary's template kind and verify conformance.

    Uses :func:`classify_boundary_kind` from
    :mod:`arnold.workflow.boundary_templates` to detect the likely template
    kind for each boundary, then runs full conformance verification.

    Args:
        workflow_id: The workflow identifier being verified.
        boundaries: Mapping of ``boundary_id`` → :class:`WorkflowBoundarySpec`.
        version_pins: Optional mapping of ``boundary_id`` → version pin
            for template-version compatibility checking.

    Returns:
        A :class:`ConformanceResult` with all violations found.
    """
    template_kinds: dict[str, BoundaryTemplateKind | str] = {}
    for bid, spec in boundaries.items():
        tk = spec.template_kind
        if tk is None:
            tk = classify_boundary_kind(spec.contract)
        if tk is not None:
            template_kinds[bid] = tk

    return verify_boundary_conformance(
        workflow_id=workflow_id,
        boundaries=boundaries,
        template_kinds=template_kinds if template_kinds else None,
        version_pins=version_pins,
    )


# ── Internal helpers ──────────────────────────────────────────────────────


def _freeze_value(value: Any) -> Any:
    """Recursively freeze a value for immutable storage."""
    from types import MappingProxyType

    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze_value(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(value)
    return value


def _thaw_value(value: Any) -> Any:
    """Recursively thaw an immutable value to mutable form for serialization."""
    from types import MappingProxyType

    if isinstance(value, (Mapping, MappingProxyType)):
        return {str(k): _thaw_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, frozenset)):
        return [_thaw_value(item) for item in value]
    return value


__all__ = [
    "ConformanceResult",
    "ConformanceViolation",
    "ConformanceViolationKind",
    "WorkflowBoundarySpec",
    "classify_and_verify_boundaries",
    "verify_boundary_conformance",
    "verify_semantic_findings_against_boundaries",
    "verify_single_boundary",
]
