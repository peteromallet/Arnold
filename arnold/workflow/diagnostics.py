"""Diagnostic and import contract data for Python-shaped workflow authoring.

This module is intentionally declarative. It gives the future source compiler
stable names, codes, and data shapes to emit after static parsing/resolution,
but it does not parse workflow source, validate AST nodes, or resolve imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from arnold.manifest.refs import ImportRef, SourceSpan
from arnold.workflow.authoring import GRAMMAR_VERSION, RESERVED_INTRINSIC_NAMES


GRAMMAR_METADATA = MappingProxyType(
    {
        "grammar_version": GRAMMAR_VERSION,
        "source_kind": "python-shaped-workflow",
        "module": "arnold.workflow.authoring",
    }
)


class ImportForm(StrEnum):
    """Import forms accepted by the V1 Python-shaped authoring grammar."""

    FUTURE_ANNOTATIONS = "future_annotations"
    AUTHORING_INTRINSIC = "authoring_intrinsic"
    COMPONENT_ABSOLUTE = "component_absolute"
    COMPONENT_RELATIVE = "component_relative"
    COMPONENT_ALIAS = "component_alias"


ALLOWED_IMPORT_FORMS = (
    ImportForm.FUTURE_ANNOTATIONS,
    ImportForm.AUTHORING_INTRINSIC,
    ImportForm.COMPONENT_ABSOLUTE,
    ImportForm.COMPONENT_RELATIVE,
    ImportForm.COMPONENT_ALIAS,
)

AUTHORING_INTRINSIC_MODULE = "arnold.workflow.authoring"
ALLOWED_FUTURE_IMPORTS = ("annotations",)
RESERVED_AUTHORING_INTRINSICS = RESERVED_INTRINSIC_NAMES


class DiagnosticSeverity(StrEnum):
    """Authoring diagnostic severity levels."""

    ERROR = "error"
    WARNING = "warning"


class DiagnosticCode(StrEnum):
    """Stable V1 diagnostic codes for static authoring checks."""

    INVALID_IMPORT_SOURCE = "AWF001_INVALID_IMPORT_SOURCE"
    UNSUPPORTED_SYNTAX = "AWF002_UNSUPPORTED_SYNTAX"
    MISSING_WORKFLOW_DECLARATION = "AWF003_MISSING_WORKFLOW_DECLARATION"
    MULTIPLE_WORKFLOW_DECLARATIONS = "AWF004_MULTIPLE_WORKFLOW_DECLARATIONS"
    UNKNOWN_COMPONENT = "AWF005_UNKNOWN_COMPONENT"
    WRONG_COMPONENT_KIND = "AWF006_WRONG_COMPONENT_KIND"
    RESERVED_INTRINSIC_SHADOWING = "AWF007_RESERVED_INTRINSIC_SHADOWING"
    ALIAS_PROVENANCE_LOSS = "AWF008_ALIAS_PROVENANCE_LOSS"
    MALFORMED_COMPONENT_EXPORT = "AWF009_MALFORMED_COMPONENT_EXPORT"


class DiagnosticFamily(StrEnum):
    """Required diagnostic families named by the V1 contract."""

    INVALID_IMPORT_SOURCE = "invalid_import_source"
    UNSUPPORTED_SYNTAX = "unsupported_syntax"
    MISSING_WORKFLOW_DECLARATION = "missing_workflow_declaration"
    MULTIPLE_WORKFLOW_DECLARATIONS = "multiple_workflow_declarations"
    UNKNOWN_COMPONENT = "unknown_component"
    WRONG_COMPONENT_KIND = "wrong_component_kind"
    RESERVED_INTRINSIC_SHADOWING = "reserved_intrinsic_shadowing"
    ALIAS_PROVENANCE = "alias_provenance"
    COMPONENT_EXPORT_METADATA = "component_export_metadata"


@dataclass(frozen=True)
class DiagnosticCodeSpec:
    """Machine-readable metadata for one stable diagnostic code."""

    code: DiagnosticCode
    family: DiagnosticFamily
    severity: DiagnosticSeverity
    message_template: str
    remediation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", DiagnosticCode(self.code))
        object.__setattr__(self, "family", DiagnosticFamily(self.family))
        object.__setattr__(self, "severity", DiagnosticSeverity(self.severity))


DIAGNOSTIC_CODE_SPECS = (
    DiagnosticCodeSpec(
        code=DiagnosticCode.INVALID_IMPORT_SOURCE,
        family=DiagnosticFamily.INVALID_IMPORT_SOURCE,
        severity=DiagnosticSeverity.ERROR,
        message_template="import source is not allowed by the V1 authoring grammar",
        remediation=(
            "import reserved intrinsics from arnold.workflow.authoring or typed "
            "workflow components from project modules"
        ),
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.UNSUPPORTED_SYNTAX,
        family=DiagnosticFamily.UNSUPPORTED_SYNTAX,
        severity=DiagnosticSeverity.ERROR,
        message_template="syntax is outside the V1 Python-shaped authoring grammar",
        remediation="use a single workflow(...) declaration with a literal linear steps list",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MISSING_WORKFLOW_DECLARATION,
        family=DiagnosticFamily.MISSING_WORKFLOW_DECLARATION,
        severity=DiagnosticSeverity.ERROR,
        message_template="module does not declare a workflow(...) source form",
        remediation="add exactly one top-level workflow(...) declaration",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MULTIPLE_WORKFLOW_DECLARATIONS,
        family=DiagnosticFamily.MULTIPLE_WORKFLOW_DECLARATIONS,
        severity=DiagnosticSeverity.ERROR,
        message_template="module declares more than one workflow(...) source form",
        remediation="keep a single top-level workflow(...) declaration per source file",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.UNKNOWN_COMPONENT,
        family=DiagnosticFamily.UNKNOWN_COMPONENT,
        severity=DiagnosticSeverity.ERROR,
        message_template="imported component cannot be found in static resolver metadata",
        remediation="export a typed component contract object from the imported module",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.WRONG_COMPONENT_KIND,
        family=DiagnosticFamily.WRONG_COMPONENT_KIND,
        severity=DiagnosticSeverity.ERROR,
        message_template="component kind is not valid for this workflow source position",
        remediation="use a component with the expected authoring kind",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
        family=DiagnosticFamily.RESERVED_INTRINSIC_SHADOWING,
        severity=DiagnosticSeverity.ERROR,
        message_template="reserved compiler intrinsic is shadowed, rebound, or aliased",
        remediation="import reserved intrinsics by their canonical names and do not reassign them",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.ALIAS_PROVENANCE_LOSS,
        family=DiagnosticFamily.ALIAS_PROVENANCE,
        severity=DiagnosticSeverity.ERROR,
        message_template="component alias is missing original import provenance",
        remediation="preserve the original module:qualname alongside the local alias",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
        family=DiagnosticFamily.COMPONENT_EXPORT_METADATA,
        severity=DiagnosticSeverity.ERROR,
        message_template="component export metadata is missing or malformed",
        remediation="export a typed arnold.workflow.authoring component contract object",
    ),
)

DIAGNOSTIC_CODE_BY_FAMILY = MappingProxyType(
    {spec.family: spec.code for spec in DIAGNOSTIC_CODE_SPECS}
)
DIAGNOSTIC_SPEC_BY_CODE = MappingProxyType({spec.code: spec for spec in DIAGNOSTIC_CODE_SPECS})


@dataclass(frozen=True)
class AuthoringDiagnostic:
    """Single stable diagnostic emitted for Python-shaped workflow source."""

    code: DiagnosticCode
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    grammar_version: str = GRAMMAR_VERSION
    source_span: SourceSpan | None = None
    import_ref: ImportRef | None = None
    component_ref: str | None = None
    remediation: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", DiagnosticCode(self.code))
        object.__setattr__(self, "severity", DiagnosticSeverity(self.severity))
        object.__setattr__(self, "details", _freeze_mapping(self.details))
        if not self.message:
            raise ValueError("message must be non-empty")
        if self.grammar_version != GRAMMAR_VERSION:
            raise ValueError(f"grammar_version must be {GRAMMAR_VERSION!r}")
        if self.component_ref is not None and not self.component_ref:
            raise ValueError("component_ref must be non-empty when provided")


def diagnostic_spec(code: DiagnosticCode | str) -> DiagnosticCodeSpec:
    """Return metadata for a stable diagnostic code."""

    return DIAGNOSTIC_SPEC_BY_CODE[DiagnosticCode(code)]


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze_value(subvalue) for key, subvalue in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


__all__ = [
    "ALLOWED_FUTURE_IMPORTS",
    "ALLOWED_IMPORT_FORMS",
    "AUTHORING_INTRINSIC_MODULE",
    "AuthoringDiagnostic",
    "DIAGNOSTIC_CODE_BY_FAMILY",
    "DIAGNOSTIC_CODE_SPECS",
    "DIAGNOSTIC_SPEC_BY_CODE",
    "DiagnosticCode",
    "DiagnosticCodeSpec",
    "DiagnosticFamily",
    "DiagnosticSeverity",
    "GRAMMAR_METADATA",
    "ImportForm",
    "RESERVED_AUTHORING_INTRINSICS",
    "diagnostic_spec",
]
