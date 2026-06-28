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
from arnold.workflow.authoring import (
    GRAMMAR_VERSION,
    RESERVED_INTRINSIC_CALL_KEYWORDS,
    RESERVED_INTRINSIC_NAMES,
    RESERVED_SUBFLOW_CALL_KEYWORDS,
    RESERVED_STEP_CALL_KEYWORDS,
)


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
RESERVED_AUTHORING_STEP_CALL_KEYWORDS = RESERVED_STEP_CALL_KEYWORDS
RESERVED_AUTHORING_SUBFLOW_CALL_KEYWORDS = RESERVED_SUBFLOW_CALL_KEYWORDS
RESERVED_AUTHORING_INTRINSIC_CALL_KEYWORDS = RESERVED_INTRINSIC_CALL_KEYWORDS


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
    RESERVED_CALL_KEYWORD = "AWF010_RESERVED_CALL_KEYWORD"
    DYNAMIC_ROUTING_CONDITION = "AWF011_DYNAMIC_ROUTING_CONDITION"
    UNSUPPORTED_MUTATION = "AWF012_UNSUPPORTED_MUTATION"
    AMBIGUOUS_LOOP = "AWF013_AMBIGUOUS_LOOP"
    UNSUPPORTED_POLICY_CARRIER = "AWF014_UNSUPPORTED_POLICY_CARRIER"
    UNSUPPORTED_SUBFLOW_REFERENCE = "AWF015_UNSUPPORTED_SUBFLOW_REFERENCE"
    UNREACHABLE_CONTROL_PATH = "AWF016_UNREACHABLE_CONTROL_PATH"
    MISSING_FALLTHROUGH_ROUTE = "AWF017_MISSING_FALLTHROUGH_ROUTE"
    ROUTE_METADATA_MISMATCH = "AWF018_ROUTE_METADATA_MISMATCH"
    MALFORMED_POLICY_CONFIG = "AWF019_MALFORMED_POLICY_CONFIG"
    MALFORMED_CAPABILITY_METADATA = "AWF020_MALFORMED_CAPABILITY_METADATA"
    LOOP_POLICY_BINDING_MISMATCH = "AWF021_LOOP_POLICY_BINDING_MISMATCH"


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
    RESERVED_CALL_KEYWORD = "reserved_call_keyword"
    DYNAMIC_ROUTING_CONDITION = "dynamic_routing_condition"
    UNSUPPORTED_MUTATION = "unsupported_mutation"
    AMBIGUOUS_LOOP = "ambiguous_loop"
    UNSUPPORTED_POLICY_CARRIER = "unsupported_policy_carrier"
    UNSUPPORTED_SUBFLOW_REFERENCE = "unsupported_subflow_reference"
    UNREACHABLE_CONTROL_PATH = "unreachable_control_path"
    MISSING_FALLTHROUGH_ROUTE = "missing_fallthrough_route"
    ROUTE_METADATA_MISMATCH = "route_metadata_mismatch"
    MALFORMED_POLICY_CONFIG = "malformed_policy_config"
    MALFORMED_CAPABILITY_METADATA = "malformed_capability_metadata"
    LOOP_POLICY_BINDING_MISMATCH = "loop_policy_binding_mismatch"


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
    DiagnosticCodeSpec(
        code=DiagnosticCode.RESERVED_CALL_KEYWORD,
        family=DiagnosticFamily.RESERVED_CALL_KEYWORD,
        severity=DiagnosticSeverity.ERROR,
        message_template="component call uses a reserved authoring keyword as dataflow",
        remediation=(
            "use ordinary component input names for dataflow; reserved keywords are "
            "compiler-owned syntax"
        ),
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.DYNAMIC_ROUTING_CONDITION,
        family=DiagnosticFamily.DYNAMIC_ROUTING_CONDITION,
        severity=DiagnosticSeverity.ERROR,
        message_template="branch route condition is not statically enumerable",
        remediation="compare one prior decision output to one unique literal string per branch arm",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.UNSUPPORTED_MUTATION,
        family=DiagnosticFamily.UNSUPPORTED_MUTATION,
        severity=DiagnosticSeverity.ERROR,
        message_template="workflow source mutates a value needed for static control flow",
        remediation="assign each workflow local once and route on the original decision output",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.AMBIGUOUS_LOOP,
        family=DiagnosticFamily.AMBIGUOUS_LOOP,
        severity=DiagnosticSeverity.ERROR,
        message_template="loop control cannot be statically bounded",
        remediation=(
            "write loop(policy=<imported loop PolicyComponent>, reentry_id=<literal>) "
            "immediately before while True"
        ),
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.UNSUPPORTED_POLICY_CARRIER,
        family=DiagnosticFamily.UNSUPPORTED_POLICY_CARRIER,
        severity=DiagnosticSeverity.ERROR,
        message_template="policy declaration does not map to an existing manifest carrier",
        remediation="use a PolicyComponent with a supported policy_type such as retry or timing",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
        family=DiagnosticFamily.UNSUPPORTED_SUBFLOW_REFERENCE,
        severity=DiagnosticSeverity.ERROR,
        message_template="subflow reference does not map to a static manifest identity",
        remediation="use an imported SubflowComponent with a literal manifest_hash or resolver metadata",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.UNREACHABLE_CONTROL_PATH,
        family=DiagnosticFamily.UNREACHABLE_CONTROL_PATH,
        severity=DiagnosticSeverity.ERROR,
        message_template="source contains a path unreachable after terminal control flow",
        remediation="remove statements after branches where every arm exits control flow",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MISSING_FALLTHROUGH_ROUTE,
        family=DiagnosticFamily.MISSING_FALLTHROUGH_ROUTE,
        severity=DiagnosticSeverity.ERROR,
        message_template="branch route omits an explicit fallthrough arm",
        remediation="add an else arm so every branch path lowers to an explicit route",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.ROUTE_METADATA_MISMATCH,
        family=DiagnosticFamily.ROUTE_METADATA_MISMATCH,
        severity=DiagnosticSeverity.ERROR,
        message_template="lowered route metadata does not match the declared source contract",
        remediation="preserve route ids, labels, condition refs, and whitelisted metadata during lowering",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MALFORMED_POLICY_CONFIG,
        family=DiagnosticFamily.MALFORMED_POLICY_CONFIG,
        severity=DiagnosticSeverity.ERROR,
        message_template="policy component metadata is missing required static configuration",
        remediation="export a PolicyComponent with literal policy_type and policy fields",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MALFORMED_CAPABILITY_METADATA,
        family=DiagnosticFamily.MALFORMED_CAPABILITY_METADATA,
        severity=DiagnosticSeverity.ERROR,
        message_template="capability metadata is missing or malformed",
        remediation="declare literal capability metadata on the component export",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.LOOP_POLICY_BINDING_MISMATCH,
        family=DiagnosticFamily.LOOP_POLICY_BINDING_MISMATCH,
        severity=DiagnosticSeverity.ERROR,
        message_template="loop policy binding does not match the canonical loop carrier",
        remediation="bind loop policy to the canonical tail carrier without replacing existing policy fields",
    ),
)

DIAGNOSTIC_SPECS = DIAGNOSTIC_CODE_SPECS
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

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe diagnostic payload with primitive values."""

        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "severity": self.severity.value,
            "grammar_version": self.grammar_version,
        }
        if self.source_span is not None:
            payload["source_span"] = {
                "path": self.source_span.path,
                "start_line": self.source_span.start_line,
                "start_column": self.source_span.start_column,
                "end_line": self.source_span.end_line,
                "end_column": self.source_span.end_column,
            }
        if self.import_ref is not None:
            payload["import_ref"] = {
                "module": self.import_ref.module,
                "qualname": self.import_ref.qualname,
            }
        if self.component_ref is not None:
            payload["component_ref"] = self.component_ref
        if self.remediation is not None:
            payload["remediation"] = self.remediation
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload


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


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(subvalue) for key, subvalue in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


__all__ = [
    "ALLOWED_FUTURE_IMPORTS",
    "ALLOWED_IMPORT_FORMS",
    "AUTHORING_INTRINSIC_MODULE",
    "AuthoringDiagnostic",
    "DIAGNOSTIC_CODE_BY_FAMILY",
    "DIAGNOSTIC_CODE_SPECS",
    "DIAGNOSTIC_SPECS",
    "DIAGNOSTIC_SPEC_BY_CODE",
    "DiagnosticCode",
    "DiagnosticCodeSpec",
    "DiagnosticFamily",
    "DiagnosticSeverity",
    "GRAMMAR_METADATA",
    "ImportForm",
    "RESERVED_AUTHORING_INTRINSICS",
    "RESERVED_AUTHORING_INTRINSIC_CALL_KEYWORDS",
    "RESERVED_AUTHORING_SUBFLOW_CALL_KEYWORDS",
    "RESERVED_AUTHORING_STEP_CALL_KEYWORDS",
    "diagnostic_spec",
]
