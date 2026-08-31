"""Typed source and subject declaration schemas.

This module provides the frozen dataclass types for declaring where a
completion subject originates (the *source declaration*) and how it is
instantiated as a concrete subject (the *subject declaration*).

Both are designed for deterministic dict serialisation with factory
methods that can parse from dict, list, or native forms — supporting
the S2F template discovery protocol and the durability-classification
lint engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.workflow.completion.spec import SubjectKind

# ---------------------------------------------------------------------------
# SourceDeclaration — authored declaration metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceDeclaration:
    """Metadata about a single authored source declaration.

    A source declaration records *where* a declaration lives: its
    identifier, module path, line, the template/profile it came from,
    and whether the author marked it as durable.

    Instances are produced by scanning S2F templates and consumed by the
    durability-classification lint engine and shadow generator.
    """

    source_id: str
    """Unique identifier for this source declaration."""

    kind: SubjectKind | None
    """The durable :class:`SubjectKind`, or ``None`` for a pure helper.

    ``None`` deliberately represents a helper outside the completion
    subject taxonomy.  ``SubjectKind`` itself contains only the five
    durable kinds settled in SD-C1-001.
    """

    canonical_name: str
    """Canonical name / identifier for the subject (e.g. module+function)."""

    declared_durable: bool = False
    """Whether the author explicitly marked this subject as durable."""

    source_path: str = ""
    """Filesystem path to the source file that contains the declaration."""

    source_line: int = 0
    """Line number of the declaration in *source_path*."""

    template_ref: str = ""
    """Reference to the S2F template or profile that produced this declaration."""

    schema_version: str = "arnold.workflow.source_declaration.v1"
    """Schema version for forward-compatibility."""

    # Approved C1 authored-source shape.  The legacy identifiers above remain
    # the storage carrier used by the existing shadow adapter; these fields
    # are the normalized contract surface and are always populated together.
    source_kind: str | None = None
    declared_markers: frozenset[str] = frozenset()
    call_graph_targets: tuple[str, ...] = ()
    target_routes: tuple[str, ...] = ()
    authored_decorator: str | None = None
    metadata: dict[str, str] = None  # type: ignore[assignment]
    qualified_name: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", SubjectKind(self.kind))
        if self.kind is None and self.declared_durable:
            raise ValueError(
                "SourceDeclaration with kind=None cannot be declared durable"
            )
        if not self.source_id:
            raise ValueError("SourceDeclaration.source_id must be non-empty")
        if not self.canonical_name:
            if self.qualified_name:
                object.__setattr__(self, "canonical_name", self.qualified_name)
            else:
                raise ValueError("SourceDeclaration.canonical_name must be non-empty")
        if self.source_kind is None:
            object.__setattr__(
                self, "source_kind", self.kind.value if self.kind is not None else "helper"
            )
        if self.kind is None and self.source_kind != "helper":
            object.__setattr__(self, "kind", SubjectKind(self.source_kind))
        if not self.qualified_name:
            object.__setattr__(self, "qualified_name", self.canonical_name)
        object.__setattr__(self, "declared_markers", frozenset(str(v) for v in self.declared_markers))
        object.__setattr__(self, "call_graph_targets", tuple(str(v) for v in self.call_graph_targets))
        object.__setattr__(self, "target_routes", tuple(str(v) for v in self.target_routes))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization dict with primitive values."""
        payload: dict[str, Any] = {
            "source_id": self.source_id,
            "kind": self.kind.value if self.kind is not None else None,
            "canonical_name": self.canonical_name,
            "declared_durable": self.declared_durable,
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "declared_markers": sorted(self.declared_markers),
            "call_graph_targets": list(self.call_graph_targets),
            "target_routes": list(self.target_routes),
            "authored_decorator": self.authored_decorator,
            "metadata": dict(self.metadata),
            "qualified_name": self.qualified_name,
        }
        if self.source_path:
            payload["source_path"] = self.source_path
        if self.source_line:
            payload["source_line"] = self.source_line
        if self.template_ref:
            payload["template_ref"] = self.template_ref
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SourceDeclaration:
        """Reconstruct from a serialized dict."""
        return cls(
            source_id=str(data["source_id"]),
            kind=(
                SubjectKind(data["kind"])
                if data.get("kind") is not None
                else None
            ),
            canonical_name=str(data["canonical_name"]),
            declared_durable=bool(data.get("declared_durable", False)),
            source_path=str(data.get("source_path", "")),
            source_line=int(data.get("source_line", 0)),
            template_ref=str(data.get("template_ref", "")),
            schema_version=str(
                data.get("schema_version", "arnold.workflow.source_declaration.v1")
            ),
            source_kind=data.get("source_kind"),
            declared_markers=frozenset(data.get("declared_markers", ())),
            call_graph_targets=tuple(data.get("call_graph_targets", ())),
            target_routes=tuple(data.get("target_routes", ())),
            authored_decorator=data.get("authored_decorator"),
            metadata=dict(data.get("metadata", {})),
            qualified_name=str(data.get("qualified_name", data.get("canonical_name", ""))),
        )


# ---------------------------------------------------------------------------
# SubjectDeclaration — concrete subject instantiation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectDeclaration:
    """A concrete instantiation of a subject with its source and kind.

    A :class:`SubjectDeclaration` combines a :class:`SourceDeclaration`
    (where the subject comes from) with a :class:`SubjectKind` and the
    instance identifier for this particular occurrence.

    It is the canonical input to the shadow generator, binding engine,
    and durability classifier.
    """

    declaration_id: str
    """Unique identifier for this subject declaration."""

    source: SourceDeclaration
    """The source declaration that defines this subject."""

    subject_kind: SubjectKind
    """The :class:`SubjectKind` for this occurrence; it must match *source*."""

    subject_instance_id: str
    """Instance identifier for this particular occurrence."""

    is_durable: bool = False
    """Whether this occurrence is classified as durable (fully resolved)."""

    schema_version: str = "arnold.workflow.subject_declaration.v1"
    """Schema version for forward-compatibility."""

    declared_evidence_kinds: tuple[str, ...] = ()
    admission_context: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if isinstance(self.subject_kind, str):
            object.__setattr__(self, "subject_kind", SubjectKind(self.subject_kind))
        if isinstance(self.source, dict):
            object.__setattr__(self, "source", SourceDeclaration.from_dict(self.source))
        if not isinstance(self.source, SourceDeclaration):
            raise ValueError(
                "SubjectDeclaration.source must be a SourceDeclaration"
            )
        if not isinstance(self.subject_kind, SubjectKind):
            raise ValueError(
                "SubjectDeclaration.subject_kind must be a durable SubjectKind"
            )
        if self.source.kind is None:
            raise ValueError(
                "SubjectDeclaration cannot contract a pure helper "
                "(SourceDeclaration.kind is None)"
            )
        if self.source.kind != self.subject_kind:
            raise ValueError(
                "SubjectDeclaration.subject_kind must match "
                "SourceDeclaration.kind"
            )
        if not self.declaration_id:
            raise ValueError("SubjectDeclaration.declaration_id must be non-empty")
        if not self.subject_instance_id:
            raise ValueError("SubjectDeclaration.subject_instance_id must be non-empty")
        object.__setattr__(self, "declared_evidence_kinds", tuple(str(v) for v in self.declared_evidence_kinds))
        object.__setattr__(self, "admission_context", dict(self.admission_context or {}))

    @property
    def subject_id(self) -> str:
        """Stable subject identity alias used by the adapter contract.

        ``declaration_id`` remains the serialized v1 field; this alias lets
        discovery consumers use the contract's ``subject_id`` terminology
        without inventing a second identity.
        """
        return self.declaration_id

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization dict with primitive values."""
        payload: dict[str, Any] = {
            "declaration_id": self.declaration_id,
            "source": self.source.to_dict(),
            "subject_kind": self.subject_kind.value,
            "subject_instance_id": self.subject_instance_id,
            "is_durable": self.is_durable,
            "schema_version": self.schema_version,
            "declared_evidence_kinds": list(self.declared_evidence_kinds),
            "admission_context": dict(self.admission_context),
        }
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SubjectDeclaration:
        """Reconstruct from a serialized dict."""
        source_data = data.get("source", {})
        source = (
            SourceDeclaration.from_dict(source_data)
            if isinstance(source_data, dict)
            else source_data
        )
        return cls(
            declaration_id=str(data["declaration_id"]),
            source=source,
            subject_kind=SubjectKind(data["subject_kind"]),
            subject_instance_id=str(data["subject_instance_id"]),
            is_durable=bool(data.get("is_durable", False)),
            schema_version=str(
                data.get("schema_version", "arnold.workflow.subject_declaration.v1")
            ),
            declared_evidence_kinds=tuple(data.get("declared_evidence_kinds", ())),
            admission_context=dict(data.get("admission_context", {})),
        )


def source_declaration_from_dict(data: Mapping[str, Any]) -> SourceDeclaration:
    """Parse either the approved C1 shape or the internal carrier shape."""
    source_kind = data.get("source_kind")
    kind = data.get("kind")
    if kind is None and source_kind not in (None, "helper"):
        kind = source_kind
    qualified_name = str(data.get("qualified_name", data.get("canonical_name", "")))
    return SourceDeclaration(
        source_id=str(data.get("source_id", data.get("id", qualified_name))),
        kind=SubjectKind(kind) if kind is not None else None,
        canonical_name=qualified_name,
        declared_durable=bool(data.get("declared_durable", False)),
        source_path=str(data.get("source_path", "")),
        source_line=int(data.get("source_line", 0)),
        template_ref=str(data.get("template_ref", "")),
        schema_version=str(data.get("schema_version", "arnold.workflow.source_declaration.v1")),
        source_kind=source_kind,
        declared_markers=frozenset(data.get("declared_markers", ())),
        call_graph_targets=tuple(data.get("call_graph_targets", ())),
        target_routes=tuple(data.get("target_routes", ())),
        authored_decorator=data.get("authored_decorator"),
        metadata=dict(data.get("metadata", {})),
        qualified_name=qualified_name,
    )


def subject_declaration_from_dict(data: Mapping[str, Any]) -> SubjectDeclaration:
    """Parse the approved C1 subject declaration shape."""
    source_data = data.get("source", data)
    source = source_declaration_from_dict(source_data)
    subject_id = str(data.get("subject_id", data.get("declaration_id", "")))
    return SubjectDeclaration(
        declaration_id=subject_id,
        source=source,
        subject_kind=SubjectKind(data["subject_kind"]),
        subject_instance_id=str(data.get("subject_instance_id", subject_id)),
        is_durable=bool(data.get("is_durable", False)),
        schema_version=str(data.get("schema_version", "arnold.workflow.subject_declaration.v1")),
        declared_evidence_kinds=tuple(data.get("declared_evidence_kinds", ())),
        admission_context=dict(data.get("admission_context", {})),
    )


__all__ = [
    "SourceDeclaration", "SubjectDeclaration", "source_declaration_from_dict",
    "subject_declaration_from_dict",
]
