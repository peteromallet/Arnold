"""Shadow-only spec, binding, and evaluation infrastructure.

Shadow verdicts are informational and have no completion authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.workflow.completion.binding import CompletionBinding, SubjectInstanceId, bind
from arnold.workflow.completion.outcomes import CandidateOutcome
from arnold.workflow.completion.s2f import (
    DEFAULT_S2F_SCAN_DIRS,
    S2F_SCHEMA_MARKERS,
    S2FGapReport,
    S2FTemplatesUnavailable,
    generate_shadow_specs_from_s2f,
    s2f_discovery_gap_report,
)
from arnold.workflow.completion.spec import CompletionSpec, SubjectKind, make_completion_spec
from arnold.workflow.completion.source_declaration import SubjectDeclaration


@dataclass(frozen=True)
class ShadowVerdict:
    """The non-authoritative result for one shadow declaration."""

    declaration_id: str
    spec_hash: str
    binding_hash: str
    outcome: CandidateOutcome
    verdict_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization dict."""
        payload = {
            "declaration_id": self.declaration_id,
            "spec_hash": self.spec_hash,
            "binding_hash": self.binding_hash,
            "outcome": self.outcome.value,
        }
        if self.verdict_description:
            payload["verdict_description"] = self.verdict_description
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ShadowVerdict:
        """Reconstruct a verdict from serialized data."""
        return cls(
            declaration_id=str(data["declaration_id"]),
            spec_hash=str(data["spec_hash"]),
            binding_hash=str(data["binding_hash"]),
            outcome=CandidateOutcome(data["outcome"]),
            verdict_description=str(data.get("verdict_description", "")),
        )


def _spec_for_subject(declaration: SubjectDeclaration) -> CompletionSpec:
    """Generate one deterministic shadow spec."""
    return make_completion_spec(
        obligation_id=(
            f"shadow:{declaration.declaration_id}:{declaration.subject_instance_id}"
        ),
        subject_kind=declaration.subject_kind,
        canonical_name=declaration.source.canonical_name,
    )


def _validate_shadow_declaration(declaration: SubjectDeclaration) -> None:
    """Reject malformed declarations before contract generation."""
    if not isinstance(declaration, SubjectDeclaration):
        raise TypeError("shadow inventory entries must be SubjectDeclaration instances")
    if declaration.source.kind is None:
        raise ValueError("pure helpers must not enter a shadow inventory")
    if declaration.source.kind != declaration.subject_kind:
        raise ValueError("SubjectDeclaration.subject_kind must match SourceDeclaration.kind")


def _validated_shadow_declarations(
    inventory: tuple[SubjectDeclaration, ...],
) -> tuple[SubjectDeclaration, ...]:
    """Validate and return the complete inventory in its original order."""
    for declaration in inventory:
        _validate_shadow_declaration(declaration)
    return inventory


def generate_shadow_specs(
    inventory: tuple[SubjectDeclaration, ...],
) -> tuple[CompletionSpec, ...]:
    """Generate one shadow spec per declaration."""
    return tuple(
        _spec_for_subject(declaration)
        for declaration in _validated_shadow_declarations(inventory)
    )


def generate_shadow_bindings(
    specs: tuple[CompletionSpec, ...],
    instance_ids: tuple[SubjectInstanceId, ...],
) -> tuple[CompletionBinding, ...]:
    """Generate bindings for specs and their subject instances."""
    if len(specs) != len(instance_ids):
        raise ValueError(
            f"specs and instance_ids must have the same length: "
            f"{len(specs)} vs {len(instance_ids)}"
        )
    return tuple(bind(spec=spec, subject_instance_id=instance) for spec, instance in zip(specs, instance_ids))


@dataclass(frozen=True)
class ShadowEvaluation:
    """The complete informational result of one shadow pass."""

    specs: tuple[CompletionSpec, ...] = ()
    bindings: tuple[CompletionBinding, ...] = ()
    verdicts: tuple[ShadowVerdict, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization dict."""
        return {
            "specs": [spec.to_dict() for spec in self.specs],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "verdicts": [verdict.to_dict() for verdict in self.verdicts],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ShadowEvaluation:
        """Reconstruct an evaluation from serialized data."""
        return cls(
            specs=tuple(CompletionSpec.from_dict(item) for item in data.get("specs", [])),
            bindings=tuple(CompletionBinding.from_dict(item) for item in data.get("bindings", [])),
            verdicts=tuple(ShadowVerdict.from_dict(item) for item in data.get("verdicts", [])),
        )


def evaluate_shadow(
    inventory: tuple[SubjectDeclaration, ...],
) -> ShadowEvaluation:
    """Generate specs, bindings, and successful informational verdicts."""
    if not inventory:
        return ShadowEvaluation()
    specs = generate_shadow_specs(inventory)
    bindings = generate_shadow_bindings(
        specs, tuple(declaration.subject_instance_id for declaration in inventory)
    )
    verdicts = tuple(
        ShadowVerdict(
            declaration_id=declaration.declaration_id,
            spec_hash=spec.spec_hash,
            binding_hash=binding.binding_hash,
            outcome=CandidateOutcome.SUCCESS,
            verdict_description=(
                f"Shadow evaluation for {declaration.source.canonical_name} "
                f"({declaration.subject_kind.value})"
            ),
        )
        for declaration, spec, binding in zip(inventory, specs, bindings)
    )
    return ShadowEvaluation(specs=specs, bindings=bindings, verdicts=verdicts)
