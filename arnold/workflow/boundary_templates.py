"""Megaplan-neutral reusable BoundaryContract template/profile definitions and selection helpers.

This module provides canonical template profiles for common workflow boundary
shapes using only :class:`BoundaryContract` primitives from
:mod:`arnold.workflow.boundary_evidence`.  It does **not** import from
``arnold_pipelines.megaplan`` — domain-specific adapters map their concepts
onto these generic profiles.

Template profiles covered:

* **Revision feedback** — rework-cycle declarative evidence (``revision_boundary``).
* **Validation results** — validation-gate declarative evidence (``validation_boundary``).
* **Artifact handoff / promotion** — producer→consumer artifact transfer and
  scratch→canonical artifact elevation (``artifact_handoff_boundary``,
  ``artifact_promotion``).
* **Approval / waiver** — approval gate with required authority and
  deferred human-in-the-loop waiver (``approval_boundary``,
  ``human_approval_waiver``).
* **External effects** — side-effect emission as declarative contract
  (``external_effect``).
* **Execution custody** — custody handoff with fresh session
  (``execution_custody``).
* **Graph join / fan-out** — declared dependency and fan topology
  (``graph_join_fanout``).
* **External witness** — external attestation evidence
  (``external_witness``).

Selection helpers allow downstream code to retrieve a canonical template
by kind, check a concrete contract against its declared profile, and
classify an existing :class:`BoundaryContract` into one of the known
profile kinds.

.. note::

    Fields prefixed with ``details.`` in required-field profiles refer to
    keys nested inside the ``details`` mapping of a
    :class:`BoundaryContract`.  Helper functions resolve these nested keys
    when checking conformance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from arnold.workflow.boundary_evidence import (
    BoundaryContract,
    BoundaryPhase,
    TemplateCompatibility,
    TemplateCompatibilityResult,
    check_template_compatibility,
)

# ── Template profile kind identifiers ───────────────────────────────────────


class BoundaryTemplateKind(StrEnum):
    """Stable identifiers for reusable boundary template profile kinds.

    Each member corresponds to a canonical :class:`BoundaryContract`
    template shape with a documented required-field profile and a
    representative template instance.
    """

    REVISION_BOUNDARY = "revision_boundary"
    """Revision feedback boundary: rework-cycle declarative evidence."""

    VALIDATION_BOUNDARY = "validation_boundary"
    """Validation results boundary: validation-gate declarative evidence."""

    ARTIFACT_HANDOFF_BOUNDARY = "artifact_handoff_boundary"
    """Artifact handoff boundary: producer→consumer artifact transfer."""

    ARTIFACT_PROMOTION = "artifact_promotion"
    """Artifact promotion boundary: scratch→canonical artifact elevation."""

    APPROVAL_BOUNDARY = "approval_boundary"
    """Approval boundary: approval gate with required authority."""

    HUMAN_APPROVAL_WAIVER = "human_approval_waiver"
    """Human approval/waiver boundary: deferred human-in-the-loop gate."""

    EXTERNAL_EFFECT = "external_effect"
    """External effect boundary: side-effect emission as declarative contract."""

    EXECUTION_CUSTODY = "execution_custody"
    """Execution custody boundary: custody handoff with fresh session."""

    GRAPH_JOIN_FANOUT = "graph_join_fanout"
    """Graph join/fan-out boundary: declared dependency and fan topology."""

    EXTERNAL_WITNESS = "external_witness"
    """External witness boundary: external attestation evidence."""


class WbcInventoryInvariant(StrEnum):
    """Inventory-backed WBC runtime proof requirements."""

    START_BEFORE_DISPATCH = "start_before_dispatch"
    EXACTLY_ONE_TERMINAL = "exactly_one_terminal"
    GRANT_LEASE_GATE = "grant_lease_gate"
    EXACT_VERSION_LOOKUP = "exact_version_lookup"
    CAUSAL_EVIDENCE = "causal_evidence"
    POST_TRANSITION_REREAD = "post_transition_reread"


class InventoryRowCompleteness(StrEnum):
    """Typed completeness state for generated inventory rows."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    ABSENT = "absent"


@dataclass(frozen=True)
class InventoryRowAssessment:
    """Source-of-truth assessment for one logical inventory row set."""

    completeness: InventoryRowCompleteness
    reasons: tuple[str, ...] = ()
    missing_invariants: tuple[WbcInventoryInvariant, ...] = ()
    producer_category: str | None = None
    row_kind: str | None = None
    matched_row_count: int = 0


# ── Required-field profiles ─────────────────────────────────────────────────
# Each frozenset enumerates the BoundaryContract top-level fields *and*
# ``details.`` keys that must be populated for a contract of that shape.
# Profiles are declarative: they do not route or dispatch.


REQUIRED_FIELDS_REVISION_BOUNDARY: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "phase",
        "required_artifacts",
        "expected_state_delta",
        "details.revision_kind",
        "details.revision_log_ref",
    }
)

REQUIRED_FIELDS_VALIDATION_BOUNDARY: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "phase",
        "required_artifacts",
        "expected_state_delta",
        "phase_result_required",
        "receipt_required",
        "details.validation_kind",
    }
)

REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "required_artifacts",
        "details.handoff_from",
        "details.handoff_to",
        "details.artifact_policy_ref",
    }
)

REQUIRED_FIELDS_ARTIFACT_PROMOTION: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "required_artifacts",
        "expected_state_delta",
        "phase_result_required",
        "receipt_required",
        "details.effect_id",
        "details.artifact_policy_ref",
        "details.promotion_kind",
    }
)

REQUIRED_FIELDS_APPROVAL_BOUNDARY: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "required_artifacts",
        "authority_required",
        "details.approval_scope",
    }
)

REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "required_artifacts",
        "authority_required",
        "details.approval_scope",
        "details.suspension_route_id",
        "details.resume_policy_ref",
    }
)

REQUIRED_FIELDS_EXTERNAL_EFFECT: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "required_artifacts",
        "details.effect_kind",
        "details.effect_id",
    }
)

REQUIRED_FIELDS_EXECUTION_CUSTODY: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "phase",
        "required_artifacts",
        "authority_required",
        "details.custody_scope",
        "details.fresh_session",
    }
)

REQUIRED_FIELDS_GRAPH_JOIN_FANOUT: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "details.fan_out_refs",
        "details.fan_in_ref",
        "details.join_requirements",
    }
)

REQUIRED_FIELDS_EXTERNAL_WITNESS: frozenset[str] = frozenset(
    {
        "boundary_id",
        "workflow_id",
        "row_id",
        "required_artifacts",
        "details.witness_ref",
        "details.witness_kind",
    }
)

# ── Required-field profiles registry ────────────────────────────────────────

REQUIRED_FIELDS_BY_KIND: dict[BoundaryTemplateKind, frozenset[str]] = {
    BoundaryTemplateKind.REVISION_BOUNDARY: REQUIRED_FIELDS_REVISION_BOUNDARY,
    BoundaryTemplateKind.VALIDATION_BOUNDARY: REQUIRED_FIELDS_VALIDATION_BOUNDARY,
    BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY: REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY,
    BoundaryTemplateKind.ARTIFACT_PROMOTION: REQUIRED_FIELDS_ARTIFACT_PROMOTION,
    BoundaryTemplateKind.APPROVAL_BOUNDARY: REQUIRED_FIELDS_APPROVAL_BOUNDARY,
    BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER: REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER,
    BoundaryTemplateKind.EXTERNAL_EFFECT: REQUIRED_FIELDS_EXTERNAL_EFFECT,
    BoundaryTemplateKind.EXECUTION_CUSTODY: REQUIRED_FIELDS_EXECUTION_CUSTODY,
    BoundaryTemplateKind.GRAPH_JOIN_FANOUT: REQUIRED_FIELDS_GRAPH_JOIN_FANOUT,
    BoundaryTemplateKind.EXTERNAL_WITNESS: REQUIRED_FIELDS_EXTERNAL_WITNESS,
}

DEFAULT_WBC_INVENTORY_PATH = Path(__file__).resolve().parents[2] / "evidence" / "wbc-boundary-inventory.json"

_INCOMPLETE_SUPPORT_REASONS: dict[str, str] = {
    "partial": "support-manifest-only",
    "planned": "support-manifest-only",
    "unknown": "unknown",
    "warn_only": "warn-only",
    "warning_only": "warn-only",
    "fixture_only": "fixture-only",
    "manual": "manual",
    "schema_only": "schema-only",
    "support_manifest_only": "support-manifest-only",
}

_INVARIANT_FLAG_KEYS: dict[WbcInventoryInvariant, tuple[str, ...]] = {
    WbcInventoryInvariant.START_BEFORE_DISPATCH: (
        "start_before_dispatch",
        "start_before_dispatch_proven",
        "durable_start_before_dispatch",
        "started_before_dispatch",
    ),
    WbcInventoryInvariant.EXACTLY_ONE_TERMINAL: (
        "exactly_one_terminal",
        "exactly_one_terminal_proven",
        "single_terminal_outcome",
    ),
    WbcInventoryInvariant.GRANT_LEASE_GATE: (
        "grant_lease_gate",
        "grant_lease_gate_proven",
        "grant_lease_validation",
        "grant_and_lease_gate",
    ),
    WbcInventoryInvariant.EXACT_VERSION_LOOKUP: (
        "exact_version_lookup",
        "exact_version_lookup_proven",
        "exact_source_version_lookup",
    ),
    WbcInventoryInvariant.CAUSAL_EVIDENCE: (
        "causal_evidence",
        "causal_evidence_proven",
        "joined_causal_evidence",
    ),
    WbcInventoryInvariant.POST_TRANSITION_REREAD: (
        "post_transition_reread",
        "post_transition_reread_proven",
        "authoritative_reread",
        "post_write_reread",
    ),
}

# ── Canonical template instances ────────────────────────────────────────────
# Each template is a BoundaryContract instance with a neutral workflow_id and
# descriptive boundary_id.  Downstream adapters override fields as needed.


_revision_boundary_template = BoundaryContract(
    boundary_id="template.revision_boundary",
    workflow_id="arnold.workflow",
    row_id="template.revision_boundary.1",
    phase=BoundaryPhase.REVISE,
    required_artifacts=("revised_content.json",),
    expected_state_delta={"revision_stage": "revised"},
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Revision boundary template: rework-cycle declarative evidence.",
        "revision_kind": "revision",
        "revision_log_ref": "revision_log.md",
    },
)

_validation_boundary_template = BoundaryContract(
    boundary_id="template.validation_boundary",
    workflow_id="arnold.workflow",
    row_id="template.validation_boundary.1",
    phase=BoundaryPhase.GATE,
    required_artifacts=("validation_result.json",),
    expected_state_delta={"validation_stage": "validated"},
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Validation boundary template: validation-gate declarative evidence.",
        "validation_kind": "validation",
    },
)

_artifact_handoff_boundary_template = BoundaryContract(
    boundary_id="template.artifact_handoff_boundary",
    workflow_id="arnold.workflow",
    row_id="template.artifact_handoff_boundary.1",
    phase=None,
    required_artifacts=("<artifact_ref>",),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Artifact handoff boundary template: producer→consumer artifact transfer.",
        "handoff_from": "<producer_id>",
        "handoff_to": "<consumer_id>",
        "artifact_policy_ref": "arnold:artifact-contract",
    },
)

_artifact_promotion_template = BoundaryContract(
    boundary_id="template.artifact_promotion",
    workflow_id="arnold.workflow",
    row_id="template.artifact_promotion.1",
    phase=None,
    required_artifacts=("<artifact_ref>",),
    expected_state_delta={"promotion_stage": "scratch_to_canonical"},
    phase_result_required=True,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "Artifact promotion boundary template: scratch→canonical artifact elevation.",
        "effect_id": "artifact.promotion",
        "artifact_policy_ref": "arnold:artifact-contract",
        "promotion_kind": "artifact_promotion",
    },
)

_approval_boundary_template = BoundaryContract(
    boundary_id="template.approval_boundary",
    workflow_id="arnold.workflow",
    row_id="template.approval_boundary.1",
    phase=None,
    required_artifacts=("approval_record.json",),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=True,
    authority_required=True,
    details={
        "description": "Approval boundary template: approval gate with required authority.",
        "approval_scope": "approval:required",
    },
)

_human_approval_waiver_template = BoundaryContract(
    boundary_id="template.human_approval_waiver",
    workflow_id="arnold.workflow",
    row_id="template.human_approval_waiver.1",
    phase=None,
    required_artifacts=("approval_record.json",),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=True,
    authority_required=True,
    details={
        "description": "Human approval/waiver boundary template: deferred human-in-the-loop gate.",
        "approval_scope": "human:approval",
        "suspension_route_id": "human:deferred",
        "resume_policy_ref": "arnold:suspension",
    },
)

_external_effect_template = BoundaryContract(
    boundary_id="template.external_effect",
    workflow_id="arnold.workflow",
    row_id="template.external_effect.1",
    phase=None,
    required_artifacts=("<effect_artifact>",),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "External effect boundary template: side-effect emission as declarative contract.",
        "effect_kind": "external_effect",
        "effect_id": "<effect_id>",
    },
)

_execution_custody_template = BoundaryContract(
    boundary_id="template.execution_custody",
    workflow_id="arnold.workflow",
    row_id="template.execution_custody.1",
    phase=BoundaryPhase.EXECUTE,
    required_artifacts=("<custody_artifact>",),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=False,
    authority_required=True,
    details={
        "description": "Execution custody boundary template: custody handoff with fresh session.",
        "custody_scope": "execute:custody",
        "fresh_session": True,
    },
)

_graph_join_fanout_template = BoundaryContract(
    boundary_id="template.graph_join_fanout",
    workflow_id="arnold.workflow",
    row_id="template.graph_join_fanout.1",
    phase=None,
    required_artifacts=(),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=False,
    authority_required=False,
    details={
        "description": "Graph join/fan-out boundary template: declared dependency and fan topology.",
        "fan_out_refs": ("<fan_out_ref>",),
        "fan_in_ref": "<fan_in_ref>",
        "join_requirements": ("<join_requirement>",),
    },
)

_external_witness_template = BoundaryContract(
    boundary_id="template.external_witness",
    workflow_id="arnold.workflow",
    row_id="template.external_witness.1",
    phase=None,
    required_artifacts=("<witness_artifact>",),
    expected_state_delta={},
    phase_result_required=False,
    receipt_required=True,
    authority_required=False,
    details={
        "description": "External witness boundary template: external attestation evidence.",
        "witness_ref": "<witness_ref>",
        "witness_kind": "external_attestation",
    },
)

# ── Template registry ───────────────────────────────────────────────────────

TEMPLATES_BY_KIND: dict[BoundaryTemplateKind, BoundaryContract] = {
    BoundaryTemplateKind.REVISION_BOUNDARY: _revision_boundary_template,
    BoundaryTemplateKind.VALIDATION_BOUNDARY: _validation_boundary_template,
    BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY: _artifact_handoff_boundary_template,
    BoundaryTemplateKind.ARTIFACT_PROMOTION: _artifact_promotion_template,
    BoundaryTemplateKind.APPROVAL_BOUNDARY: _approval_boundary_template,
    BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER: _human_approval_waiver_template,
    BoundaryTemplateKind.EXTERNAL_EFFECT: _external_effect_template,
    BoundaryTemplateKind.EXECUTION_CUSTODY: _execution_custody_template,
    BoundaryTemplateKind.GRAPH_JOIN_FANOUT: _graph_join_fanout_template,
    BoundaryTemplateKind.EXTERNAL_WITNESS: _external_witness_template,
}

# ── Selection helpers ───────────────────────────────────────────────────────


def get_template(kind: BoundaryTemplateKind | str) -> BoundaryContract:
    """Return the canonical :class:`BoundaryContract` template for *kind*.

    Args:
        kind: A :class:`BoundaryTemplateKind` member or its string value.

    Returns:
        The frozen template instance.

    Raises:
        KeyError: If *kind* is not a registered template kind.
    """
    kind = BoundaryTemplateKind(kind)
    return TEMPLATES_BY_KIND[kind]


def get_required_fields(kind: BoundaryTemplateKind | str) -> frozenset[str]:
    """Return the required-field profile for *kind*.

    Args:
        kind: A :class:`BoundaryTemplateKind` member or its string value.

    Returns:
        Frozen set of ``"field_name"`` and ``"details.nested_key"`` strings
        that must be populated for a contract of this kind.

    Raises:
        KeyError: If *kind* is not a registered template kind.
    """
    kind = BoundaryTemplateKind(kind)
    return REQUIRED_FIELDS_BY_KIND[kind]


def list_template_kinds() -> tuple[BoundaryTemplateKind, ...]:
    """Return all registered template profile kinds."""
    return tuple(TEMPLATES_BY_KIND.keys())


def _resolve_field(contract: BoundaryContract, field_path: str) -> Any:
    """Resolve a top-level or ``details.``-nested field from *contract*.

    Returns the field value, or a sentinel ``_MISSING`` when the value
    would be considered empty for required-field checking purposes.
    """
    if field_path.startswith("details."):
        key = field_path[len("details."):]
        return contract.details.get(key, _MISSING)
    return getattr(contract, field_path, _MISSING)


class _MissingSentinel:
    """Private sentinel for missing/unset required fields."""

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<missing>"


_MISSING = _MissingSentinel()


def check_contract_conformance(
    contract: BoundaryContract,
    kind: BoundaryTemplateKind | str,
) -> tuple[str, ...]:
    """Check which required fields are missing from *contract* for *kind*.

    A field is considered missing when it is ``None``, empty string ``""``,
    an empty tuple ``()``, an empty mapping ``{}``, ``False`` (for boolean
    fields only when the profile requires ``True``), or the sentinel
    ``<missing>``.

    Args:
        contract: The concrete :class:`BoundaryContract` to check.
        kind: The profile kind to validate against.

    Returns:
        Tuple of missing field paths (empty if fully conformant).
    """
    kind = BoundaryTemplateKind(kind)
    required = get_required_fields(kind)
    missing: list[str] = []

    for field_path in sorted(required):
        value = _resolve_field(contract, field_path)
        if _is_empty_for_required(value):
            missing.append(field_path)

    # Special boolean handling: if the profile requires authority_required
    # or phase_result_required / receipt_required, False is considered missing.
    for bool_field in ("authority_required", "phase_result_required", "receipt_required"):
        if bool_field in required:
            value = getattr(contract, bool_field, None)
            if value is False:
                if bool_field not in missing:
                    missing.append(bool_field)

    return tuple(sorted(missing))


def _is_empty_for_required(value: Any) -> bool:
    """Return True when *value* would be considered empty for required-field checks."""
    if value is None:
        return True
    if isinstance(value, _MissingSentinel):
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, (tuple, list)) and len(value) == 0:
        return True
    if isinstance(value, Mapping) and len(value) == 0:
        return True
    return False


def classify_boundary_kind(
    contract: BoundaryContract,
) -> BoundaryTemplateKind | None:
    """Attempt to classify *contract* into one of the known template profile kinds.

    Classification uses heuristics based on ``details`` keys present in the
    contract.  It is best-effort and may return ``None`` when no single
    kind clearly matches.

    Args:
        contract: The :class:`BoundaryContract` to classify.

    Returns:
        The most likely :class:`BoundaryTemplateKind`, or ``None``.
    """
    details = dict(contract.details)
    boundary_id = (contract.boundary_id or "").lower()

    # Check for explicit kind hints in boundary_id
    kind_hints: dict[str, BoundaryTemplateKind] = {
        "revision": BoundaryTemplateKind.REVISION_BOUNDARY,
        "validation": BoundaryTemplateKind.VALIDATION_BOUNDARY,
        "handoff": BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY,
        "promotion": BoundaryTemplateKind.ARTIFACT_PROMOTION,
        "approval": BoundaryTemplateKind.APPROVAL_BOUNDARY,
        "waiver": BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER,
        "external_effect": BoundaryTemplateKind.EXTERNAL_EFFECT,
        "custody": BoundaryTemplateKind.EXECUTION_CUSTODY,
        "join": BoundaryTemplateKind.GRAPH_JOIN_FANOUT,
        "fanout": BoundaryTemplateKind.GRAPH_JOIN_FANOUT,
        "fan_out": BoundaryTemplateKind.GRAPH_JOIN_FANOUT,
        "witness": BoundaryTemplateKind.EXTERNAL_WITNESS,
    }
    for hint, kind in kind_hints.items():
        if hint in boundary_id:
            return kind

    # Check details keys for characteristic markers
    if "revision_kind" in details and "revision_log_ref" in details:
        return BoundaryTemplateKind.REVISION_BOUNDARY
    if "validation_kind" in details:
        return BoundaryTemplateKind.VALIDATION_BOUNDARY
    if "handoff_from" in details and "handoff_to" in details:
        return BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY
    if "promotion_kind" in details and "effect_id" in details:
        return BoundaryTemplateKind.ARTIFACT_PROMOTION
    if "suspension_route_id" in details and "resume_policy_ref" in details:
        return BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER
    if "approval_scope" in details and "suspension_route_id" not in details:
        return BoundaryTemplateKind.APPROVAL_BOUNDARY
    if "effect_kind" in details and "effect_id" in details:
        return BoundaryTemplateKind.EXTERNAL_EFFECT
    if "custody_scope" in details and "fresh_session" in details:
        return BoundaryTemplateKind.EXECUTION_CUSTODY
    if "fan_out_refs" in details or "fan_in_ref" in details:
        return BoundaryTemplateKind.GRAPH_JOIN_FANOUT
    if "witness_ref" in details and "witness_kind" in details:
        return BoundaryTemplateKind.EXTERNAL_WITNESS

    return None


@dataclass(frozen=True)
class TemplateSelection:
    """Result of selecting a template for a boundary use case.

    Produced by :func:`select_template` and consumed by authoring surfaces
    that need a template plus required-field profile in one call.
    """

    kind: BoundaryTemplateKind
    template: BoundaryContract
    required_fields: frozenset[str] = field(repr=False)


def select_template(
    kind: BoundaryTemplateKind | str,
    *,
    boundary_id: str | None = None,
    workflow_id: str | None = None,
    phase: BoundaryPhase | str | None = None,
    required_artifacts: tuple[str, ...] | None = None,
    expected_state_delta: Mapping[str, Any] | None = None,
    expected_history_entry: str | None = None,
    phase_result_required: bool | None = None,
    receipt_required: bool | None = None,
    authority_required: bool | None = None,
    details: Mapping[str, Any] | None = None,
) -> TemplateSelection:
    """Select and optionally customize a template for *kind*.

    Returns a :class:`TemplateSelection` containing the kind, the
    (possibly customized) template instance, and the required-field
    profile.

    When any override argument is provided, a new :class:`BoundaryContract`
    is constructed combining the canonical template fields with the
    overrides.  When no overrides are given the canonical template is
    returned unchanged.

    Args:
        kind: The :class:`BoundaryTemplateKind` to select.
        boundary_id: Override the template's ``boundary_id``.
        workflow_id: Override the template's ``workflow_id``.
        phase: Override the template's ``phase``.
        required_artifacts: Override the template's ``required_artifacts``.
        expected_state_delta: Override the template's ``expected_state_delta``.
        expected_history_entry: Override ``expected_history_entry``.
        phase_result_required: Override ``phase_result_required``.
        receipt_required: Override ``receipt_required``.
        authority_required: Override ``authority_required``.
        details: Merge into the template's ``details`` (shallow merge).

    Returns:
        A :class:`TemplateSelection` with the final template and profile.
    """
    kind = BoundaryTemplateKind(kind)
    template = get_template(kind)

    # If no overrides, return canonical
    has_overrides = any(
        v is not None
        for v in (
            boundary_id,
            workflow_id,
            phase,
            required_artifacts,
            expected_state_delta,
            expected_history_entry,
            phase_result_required,
            receipt_required,
            authority_required,
            details,
        )
    )
    if not has_overrides:
        return TemplateSelection(
            kind=kind,
            template=template,
            required_fields=get_required_fields(kind),
        )

    # Build customized template
    merged_details = dict(template.details)
    if details is not None:
        merged_details.update(details)

    customized = BoundaryContract(
        boundary_id=boundary_id if boundary_id is not None else template.boundary_id,
        workflow_id=workflow_id if workflow_id is not None else template.workflow_id,
        row_id=template.row_id,
        phase=phase if phase is not None else template.phase,
        required_artifacts=(
            required_artifacts
            if required_artifacts is not None
            else template.required_artifacts
        ),
        expected_state_delta=(
            expected_state_delta
            if expected_state_delta is not None
            else dict(template.expected_state_delta)
        ),
        expected_history_entry=(
            expected_history_entry
            if expected_history_entry is not None
            else template.expected_history_entry
        ),
        phase_result_required=(
            phase_result_required
            if phase_result_required is not None
            else template.phase_result_required
        ),
        receipt_required=(
            receipt_required if receipt_required is not None else template.receipt_required
        ),
        authority_required=(
            authority_required
            if authority_required is not None
            else template.authority_required
        ),
        details=merged_details,
    )

    return TemplateSelection(
        kind=kind,
        template=customized,
        required_fields=get_required_fields(kind),
    )


# ── Version pin and deliberate-upgrade compatibility helpers ──────────────────
# These reuse check_template_compatibility() from boundary_evidence to provide
# a pinned-version / deliberate-upgrade workflow for template profile evolution.


@dataclass(frozen=True)
class TemplateVersionPin:
    """A pinned version reference for a template profile kind.

    Downstream consumers use this to record which version of a template
    profile they were validated against, so they can detect breaking
    changes on upgrade.
    """

    kind: BoundaryTemplateKind
    version: str
    template_id: str | None = None
    pinned_at: str | None = None

    @property
    def required_fields(self) -> frozenset[str]:
        """The required-field profile at the time of pinning."""
        return get_required_fields(self.kind)


# Sentinel for absent pins
_NO_PIN = object()


def pin_template_version(
    kind: BoundaryTemplateKind | str,
    version: str,
    *,
    template_id: str | None = None,
) -> TemplateVersionPin:
    """Create a version pin for *kind* at *version*.

    Args:
        kind: The :class:`BoundaryTemplateKind` to pin.
        version: The version string to pin (e.g. ``"1.0.0"``).
        template_id: Optional template identifier (defaults to kind value).

    Returns:
        A frozen :class:`TemplateVersionPin`.
    """
    kind = BoundaryTemplateKind(kind)
    return TemplateVersionPin(
        kind=kind,
        version=version,
        template_id=template_id or kind.value,
    )


def check_template_upgrade(
    kind: BoundaryTemplateKind | str,
    from_version: str,
    to_version: str,
    *,
    template_id: str | None = None,
) -> TemplateCompatibilityResult:
    """Check compatibility when upgrading *kind* from *from_version* to *to_version*.

    Compares the current required-field profile for *kind* against itself
    (since template profiles are defined per-kind, not per-version).  When
    the profile has not changed between versions the result is
    :attr:`TemplateCompatibility.EXACT_MATCH`.

    This is a convenience wrapper around
    :func:`arnold.workflow.boundary_evidence.check_template_compatibility`
    that resolves the required-field profiles from the template kind.

    Args:
        kind: The template profile kind.
        from_version: The version being upgraded from.
        to_version: The version being upgraded to.
        template_id: Optional template identifier.

    Returns:
        A :class:`TemplateCompatibilityResult` describing the upgrade path.
    """
    kind = BoundaryTemplateKind(kind)
    fields = get_required_fields(kind)
    tid = template_id or kind.value

    result = check_template_compatibility(
        template_id=tid,
        from_required_fields=fields,
        from_optional_fields=frozenset(),
        to_required_fields=fields,
        to_optional_fields=frozenset(),
        from_version=from_version,
        to_version=to_version,
    )

    # When the profile is identical between versions, it is an exact match
    # for same-version and a compatible extension for different versions
    # (since no fields were removed or tightened).
    if result.compatibility == TemplateCompatibility.EXACT_MATCH and from_version != to_version:
        object.__setattr__(result, "compatibility", TemplateCompatibility.COMPATIBLE_EXTENSION)

    return result


def deliberate_upgrade_template(
    kind: BoundaryTemplateKind | str,
    from_version: str,
    to_version: str,
    *,
    template_id: str | None = None,
    reason: str | None = None,
) -> TemplateCompatibilityResult:
    """Record a deliberate upgrade from *from_version* to *to_version*.

    When a breaking change is accepted deliberately (e.g. the consumer
    has been updated to satisfy new required fields), this records the
    upgrade with :attr:`TemplateCompatibility.DELIBERATE_UPGRADE` status.

    Args:
        kind: The template profile kind.
        from_version: The version being upgraded from.
        to_version: The version being upgraded to.
        template_id: Optional template identifier.
        reason: Optional human-readable reason for the deliberate upgrade.

    Returns:
        A :class:`TemplateCompatibilityResult` with DELIBERATE_UPGRADE status.
    """
    kind = BoundaryTemplateKind(kind)
    tid = template_id or kind.value

    return TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.DELIBERATE_UPGRADE,
        template_id=tid,
        from_version=from_version,
        to_version=to_version,
        details={"reason": reason} if reason else {},
    )


def load_wbc_boundary_inventory(
    inventory_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Load the generated WBC boundary inventory if available."""
    path = Path(inventory_path) if inventory_path is not None else DEFAULT_WBC_INVENTORY_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def select_inventory_rows(
    inventory: Mapping[str, Any] | None,
    *,
    boundary_id: str | None = None,
    step_id: str | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Return generated inventory rows matching *boundary_id* or *step_id*."""
    if not inventory:
        return ()
    rows = inventory.get("rows", ())
    matched: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if boundary_id and row.get("boundary_id") == boundary_id:
            matched.append(row)
            continue
        if step_id and row.get("step_id") == step_id:
            matched.append(row)
    return tuple(matched)


def assess_inventory_rows(
    rows: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    *,
    required_invariants: tuple[WbcInventoryInvariant | str, ...] | list[WbcInventoryInvariant | str] = (),
) -> InventoryRowAssessment:
    """Assess whether generated inventory rows prove complete WBC adoption."""
    row_tuple = tuple(rows)
    if not row_tuple:
        return InventoryRowAssessment(completeness=InventoryRowCompleteness.ABSENT)

    authoritative = _choose_authoritative_inventory_row(row_tuple)
    row_kind = str(authoritative.get("row_kind", "") or "") or None
    producer_category = _normalize_optional(authoritative.get("producer_category"))
    support_status = _normalize_optional(authoritative.get("support_status"))
    reasons: set[str] = set()

    if row_kind == "manifest_entry" and bool(authoritative.get("support_is_non_authoritative")):
        reasons.add("support-manifest-only")

    if row_kind == "manifest_entry" and not authoritative.get("boundary_id"):
        producer_path = str(authoritative.get("producer_path", "") or "")
        step_name = str(authoritative.get("step_id", "") or "")
        if producer_path.startswith("arnold/workflow/") or step_name.startswith("arnold.workflow."):
            reasons.add("schema-only")
        else:
            reasons.add("support-manifest-only")

    if producer_category == "manual_emit":
        reasons.add("manual-emission")
    elif producer_category == "declared_only":
        reasons.add("declared-only")
    elif producer_category == "unknown":
        reasons.add("unknown")

    if support_status is not None and row_kind != "boundary_contract":
        mapped_reason = _INCOMPLETE_SUPPORT_REASONS.get(support_status)
        if mapped_reason:
            reasons.add(mapped_reason)

    support_verification = authoritative.get("support_verification")
    if isinstance(support_verification, Mapping):
        missing = support_verification.get("missing_requirements")
        if isinstance(missing, list) and missing:
            reasons.add("support-manifest-only")

    requested_invariants = {
        invariant if isinstance(invariant, WbcInventoryInvariant) else WbcInventoryInvariant(str(invariant))
        for invariant in required_invariants
    }
    explicit_invariants = _find_explicit_invariants(authoritative)
    invariants_to_check = requested_invariants | explicit_invariants
    missing_invariants = tuple(
        sorted(
            (
                invariant
                for invariant in invariants_to_check
                if not _inventory_invariant_proven(authoritative, invariant)
            ),
            key=lambda item: item.value,
        )
    )

    completeness = (
        InventoryRowCompleteness.INCOMPLETE
        if reasons or missing_invariants
        else InventoryRowCompleteness.COMPLETE
    )
    return InventoryRowAssessment(
        completeness=completeness,
        reasons=tuple(sorted(reasons)),
        missing_invariants=missing_invariants,
        producer_category=producer_category,
        row_kind=row_kind,
        matched_row_count=len(row_tuple),
    )


def _choose_authoritative_inventory_row(
    rows: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any]:
    def _rank(row: Mapping[str, Any]) -> tuple[int, str]:
        row_kind = str(row.get("row_kind", "") or "")
        if row_kind == "boundary_contract":
            return (0, row_kind)
        if row_kind == "manifest_entry":
            return (1, row_kind)
        return (2, row_kind)

    return sorted(rows, key=_rank)[0]


def _normalize_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _find_explicit_invariants(row: Mapping[str, Any]) -> set[WbcInventoryInvariant]:
    explicit: set[WbcInventoryInvariant] = set()
    for invariant, keys in _INVARIANT_FLAG_KEYS.items():
        if any(_lookup_nested_value(row, key) is not None for key in keys):
            explicit.add(invariant)
    return explicit


def _inventory_invariant_proven(
    row: Mapping[str, Any],
    invariant: WbcInventoryInvariant,
) -> bool:
    for key in _INVARIANT_FLAG_KEYS[invariant]:
        value = _lookup_nested_value(row, key)
        if value is not None:
            return bool(value)
    return False


def _lookup_nested_value(row: Mapping[str, Any], key: str) -> Any:
    direct = row.get(key)
    if direct is not None:
        return direct
    for container_key in ("inventory_proof", "support_verification", "evidence_flags"):
        container = row.get(container_key)
        if isinstance(container, Mapping) and key in container:
            return container.get(key)
        if isinstance(container, Mapping):
            nested = container.get("evidence_flags")
            if isinstance(nested, Mapping) and key in nested:
                return nested.get(key)
    return None


__all__ = [
    "DEFAULT_WBC_INVENTORY_PATH",
    "BoundaryTemplateKind",
    "InventoryRowAssessment",
    "InventoryRowCompleteness",
    "REQUIRED_FIELDS_BY_KIND",
    "REQUIRED_FIELDS_APPROVAL_BOUNDARY",
    "REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY",
    "REQUIRED_FIELDS_ARTIFACT_PROMOTION",
    "REQUIRED_FIELDS_EXECUTION_CUSTODY",
    "REQUIRED_FIELDS_EXTERNAL_EFFECT",
    "REQUIRED_FIELDS_EXTERNAL_WITNESS",
    "REQUIRED_FIELDS_GRAPH_JOIN_FANOUT",
    "REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER",
    "REQUIRED_FIELDS_REVISION_BOUNDARY",
    "REQUIRED_FIELDS_VALIDATION_BOUNDARY",
    "TEMPLATES_BY_KIND",
    "TemplateSelection",
    "TemplateVersionPin",
    "WbcInventoryInvariant",
    "assess_inventory_rows",
    "check_contract_conformance",
    "check_template_upgrade",
    "classify_boundary_kind",
    "deliberate_upgrade_template",
    "get_required_fields",
    "get_template",
    "list_template_kinds",
    "load_wbc_boundary_inventory",
    "pin_template_version",
    "select_inventory_rows",
    "select_template",
]
