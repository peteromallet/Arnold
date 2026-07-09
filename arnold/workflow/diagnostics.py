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
    """Stable diagnostic codes for static authoring checks."""

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
    MISSING_PROMPT_DEPENDENCY = "AWF022_MISSING_PROMPT_DEPENDENCY"
    MISSING_RESOURCE_DEPENDENCY = "AWF023_MISSING_RESOURCE_DEPENDENCY"
    MANUAL_GRAPH_NODES = "AWF200_MANUAL_GRAPH_NODES"
    MANUAL_PATH_STRINGS = "AWF201_MANUAL_PATH_STRINGS"
    VALIDATOR_DIRECTIVES = "AWF202_VALIDATOR_DIRECTIVES"
    DIRECT_MANIFEST_AUTHORING = "AWF203_DIRECT_MANIFEST_AUTHORING"
    NATIVE_PROGRAM_PROJECTION = "AWF204_NATIVE_PROGRAM_PROJECTION"
    MEGAPLAN_ONLY_HELPERS = "AWF205_MEGAPLAN_ONLY_HELPERS"
    TRACE_OBJECT_AUTHORING = "AWF206_TRACE_OBJECT_AUTHORING"
    DYNAMIC_DISPATCH = "AWF207_DYNAMIC_DISPATCH"
    SINGLE_HANDLER_WRAPPER = "AWF208_SINGLE_HANDLER_WRAPPER"
    RUNTIME_TOPOLOGY_MUTATION = "AWF209_RUNTIME_TOPOLOGY_MUTATION"
    MISSING_PARALLEL_MAP_REDUCER = "AWF210_MISSING_PARALLEL_MAP_REDUCER"
    INVALID_PARALLEL_MAP_ITEMS = "AWF211_INVALID_PARALLEL_MAP_ITEMS"
    INVALID_PARALLEL_MAP_PATH_TEMPLATE = "AWF212_INVALID_PARALLEL_MAP_PATH_TEMPLATE"
    UNDECLARED_LOOP_EXIT = "AWF213_UNDECLARED_LOOP_EXIT"
    INVALID_LOOP_BOUNDARY = "AWF214_INVALID_LOOP_BOUNDARY"
    UNDECLARED_POLICY_METADATA = "AWF215_UNDECLARED_POLICY_METADATA"
    INVALID_POLICY_METADATA = "AWF216_INVALID_POLICY_METADATA"
    INVALID_WORKFLOW_INVOCATION = "AWF217_INVALID_WORKFLOW_INVOCATION"
    INVALID_WORKFLOW_REFERENCE = "AWF218_INVALID_WORKFLOW_REFERENCE"
    INVALID_COMPOSITION_METADATA = "AWF219_INVALID_COMPOSITION_METADATA"
    MISSING_CALL_SITE_ID = "AWF220_MISSING_CALL_SITE_ID"
    AMBIGUOUS_CALL_SITE_ID = "AWF221_AMBIGUOUS_CALL_SITE_ID"
    NON_LITERAL_CALL_SITE_ID = "AWF222_NON_LITERAL_CALL_SITE_ID"
    DUPLICATE_CALL_SITE_PATH = "AWF223_DUPLICATE_CALL_SITE_PATH"
    MISSING_ITERATION_COORDINATE = "AWF224_MISSING_ITERATION_COORDINATE"
    INVALID_ITERATION_COORDINATE = "AWF225_INVALID_ITERATION_COORDINATE"
    MISSING_ITEM_COORDINATE = "AWF226_MISSING_ITEM_COORDINATE"
    REPLAY_PATH_MISMATCH = "AWF227_REPLAY_PATH_MISMATCH"
    INVALID_PARENT_PATH = "AWF228_INVALID_PARENT_PATH"
    INVALID_CALL_SITE_PATH = "AWF229_INVALID_CALL_SITE_PATH"
    CHILD_INPUT_SCHEMA_MISMATCH = "AWF230_CHILD_INPUT_SCHEMA_MISMATCH"
    CHILD_OUTPUT_SCHEMA_MISMATCH = "AWF231_CHILD_OUTPUT_SCHEMA_MISMATCH"
    PARALLEL_MAP_ITEM_SCHEMA_MISMATCH = "AWF232_PARALLEL_MAP_ITEM_SCHEMA_MISMATCH"
    PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH = "AWF233_PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH"
    LOOP_EXIT_SCHEMA_MISMATCH = "AWF234_LOOP_EXIT_SCHEMA_MISMATCH"
    POLICY_SCHEMA_MISMATCH = "AWF235_POLICY_SCHEMA_MISMATCH"
    WORKFLOW_INPUT_BINDING_MISMATCH = "AWF236_WORKFLOW_INPUT_BINDING_MISMATCH"
    WORKFLOW_OUTPUT_BINDING_MISMATCH = "AWF237_WORKFLOW_OUTPUT_BINDING_MISMATCH"
    RESUME_SCHEMA_MISMATCH = "AWF238_RESUME_SCHEMA_MISMATCH"
    COMPOSITION_EFFECT_SCHEMA_MISMATCH = "AWF239_COMPOSITION_EFFECT_SCHEMA_MISMATCH"
    UNRESOLVED_CALLEE_PROVENANCE = "AWF240_UNRESOLVED_CALLEE_PROVENANCE"
    BRANCH_VOCABULARY_MISMATCH = "AWF241_BRANCH_VOCABULARY_MISMATCH"
    RAW_STRING_ROUTE_BRANCH = "AWF242_RAW_STRING_ROUTE_BRANCH"
    LOWERED_TOPOLOGY_DISCARD = "AWF243_LOWERED_TOPOLOGY_DISCARD"
    HANDLER_PURITY_VIOLATION = "AWF244_HANDLER_PURITY_VIOLATION"
    ROW_EVIDENCE_INSUFFICIENCY = "AWF245_ROW_EVIDENCE_INSUFFICIENCY"
    BOUNDARY_CONTRACT_MISSING = "AWF246_BOUNDARY_CONTRACT_MISSING"
    BOUNDARY_EVIDENCE_MISSING = "AWF247_BOUNDARY_EVIDENCE_MISSING"
    BOUNDARY_EVIDENCE_WITHOUT_SOURCE = "AWF248_BOUNDARY_EVIDENCE_WITHOUT_SOURCE"
    BOUNDARY_EVIDENCE_STALE = "AWF249_BOUNDARY_EVIDENCE_STALE"
    UNKNOWN_OUTCOME_TYPE = "AWF250_UNKNOWN_OUTCOME_TYPE"
    INVALID_OUTCOME_MEMBER = "AWF251_INVALID_OUTCOME_MEMBER"
    TIEBREAKER_SHAPE_VIOLATION = "AWF252_TIEBREAKER_SHAPE_VIOLATION"


class DiagnosticFamily(StrEnum):
    """Required diagnostic families named by the authoring contract."""

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
    MISSING_PROMPT_DEPENDENCY = "missing_prompt_dependency"
    MISSING_RESOURCE_DEPENDENCY = "missing_resource_dependency"
    MANUAL_GRAPH_NODES = "manual_graph_nodes"
    MANUAL_PATH_STRINGS = "manual_path_strings"
    VALIDATOR_DIRECTIVES = "validator_directives"
    DIRECT_MANIFEST_AUTHORING = "direct_manifest_authoring"
    NATIVE_PROGRAM_PROJECTION = "native_program_projection"
    MEGAPLAN_ONLY_HELPERS = "megaplan_only_helpers"
    TRACE_OBJECT_AUTHORING = "trace_object_authoring"
    DYNAMIC_DISPATCH = "dynamic_dispatch"
    SINGLE_HANDLER_WRAPPER = "single_handler_wrapper"
    RUNTIME_TOPOLOGY_MUTATION = "runtime_topology_mutation"
    MISSING_PARALLEL_MAP_REDUCER = "missing_parallel_map_reducer"
    INVALID_PARALLEL_MAP_ITEMS = "invalid_parallel_map_items"
    INVALID_PARALLEL_MAP_PATH_TEMPLATE = "invalid_parallel_map_path_template"
    UNDECLARED_LOOP_EXIT = "undeclared_loop_exit"
    INVALID_LOOP_BOUNDARY = "invalid_loop_boundary"
    UNDECLARED_POLICY_METADATA = "undeclared_policy_metadata"
    INVALID_POLICY_METADATA = "invalid_policy_metadata"
    INVALID_WORKFLOW_INVOCATION = "invalid_workflow_invocation"
    INVALID_WORKFLOW_REFERENCE = "invalid_workflow_reference"
    INVALID_COMPOSITION_METADATA = "invalid_composition_metadata"
    MISSING_CALL_SITE_ID = "missing_call_site_id"
    AMBIGUOUS_CALL_SITE_ID = "ambiguous_call_site_id"
    NON_LITERAL_CALL_SITE_ID = "non_literal_call_site_id"
    DUPLICATE_CALL_SITE_PATH = "duplicate_call_site_path"
    MISSING_ITERATION_COORDINATE = "missing_iteration_coordinate"
    INVALID_ITERATION_COORDINATE = "invalid_iteration_coordinate"
    MISSING_ITEM_COORDINATE = "missing_item_coordinate"
    REPLAY_PATH_MISMATCH = "replay_path_mismatch"
    INVALID_PARENT_PATH = "invalid_parent_path"
    INVALID_CALL_SITE_PATH = "invalid_call_site_path"
    CHILD_INPUT_SCHEMA_MISMATCH = "child_input_schema_mismatch"
    CHILD_OUTPUT_SCHEMA_MISMATCH = "child_output_schema_mismatch"
    PARALLEL_MAP_ITEM_SCHEMA_MISMATCH = "parallel_map_item_schema_mismatch"
    PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH = "parallel_map_reducer_schema_mismatch"
    LOOP_EXIT_SCHEMA_MISMATCH = "loop_exit_schema_mismatch"
    POLICY_SCHEMA_MISMATCH = "policy_schema_mismatch"
    WORKFLOW_INPUT_BINDING_MISMATCH = "workflow_input_binding_mismatch"
    WORKFLOW_OUTPUT_BINDING_MISMATCH = "workflow_output_binding_mismatch"
    RESUME_SCHEMA_MISMATCH = "resume_schema_mismatch"
    COMPOSITION_EFFECT_SCHEMA_MISMATCH = "composition_effect_schema_mismatch"
    UNRESOLVED_CALLEE_PROVENANCE = "unresolved_callee_provenance"
    BRANCH_VOCABULARY_MISMATCH = "branch_vocabulary_mismatch"
    RAW_STRING_ROUTE_BRANCH = "raw_string_route_branch"
    LOWERED_TOPOLOGY_DISCARD = "lowered_topology_discard"
    HANDLER_PURITY_VIOLATION = "handler_purity_violation"
    ROW_EVIDENCE_INSUFFICIENCY = "row_evidence_insufficiency"
    BOUNDARY_CONTRACT_MISSING = "boundary_contract_missing"
    BOUNDARY_EVIDENCE_MISSING = "boundary_evidence_missing"
    BOUNDARY_EVIDENCE_WITHOUT_SOURCE = "boundary_evidence_without_source"
    BOUNDARY_EVIDENCE_STALE = "boundary_evidence_stale"
    UNKNOWN_OUTCOME_TYPE = "unknown_outcome_type"
    INVALID_OUTCOME_MEMBER = "invalid_outcome_member"
    TIEBREAKER_SHAPE_VIOLATION = "tiebreaker_shape_violation"


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


def _v2_spec(
    code: DiagnosticCode,
    family: DiagnosticFamily,
    message_template: str,
    remediation: str,
) -> DiagnosticCodeSpec:
    return DiagnosticCodeSpec(
        code=code,
        family=family,
        severity=DiagnosticSeverity.ERROR,
        message_template=message_template,
        remediation=remediation,
    )


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
    DiagnosticCodeSpec(
        code=DiagnosticCode.MISSING_PROMPT_DEPENDENCY,
        family=DiagnosticFamily.MISSING_PROMPT_DEPENDENCY,
        severity=DiagnosticSeverity.ERROR,
        message_template="step component declares a static prompt dependency that is not satisfied",
        remediation="attach a PromptComponent to the StepComponent or remove the static prompt_key metadata",
    ),
    DiagnosticCodeSpec(
        code=DiagnosticCode.MISSING_RESOURCE_DEPENDENCY,
        family=DiagnosticFamily.MISSING_RESOURCE_DEPENDENCY,
        severity=DiagnosticSeverity.ERROR,
        message_template="step component declares a static resource dependency that is not satisfied",
        remediation="declare the required resource in component metadata resources or remove the dependency",
    ),
    _v2_spec(
        DiagnosticCode.MANUAL_GRAPH_NODES,
        DiagnosticFamily.MANUAL_GRAPH_NODES,
        "manual graph nodes are outside the V2 authoring grammar",
        "declare topology with workflow source forms rather than Stage, Edge, or PipelineBuilder objects",
    ),
    _v2_spec(
        DiagnosticCode.MANUAL_PATH_STRINGS,
        DiagnosticFamily.MANUAL_PATH_STRINGS,
        "manual path strings are rejected under the V2 authoring grammar",
        "derive stable identity from authored call-site ids instead of string-built paths",
    ),
    _v2_spec(
        DiagnosticCode.VALIDATOR_DIRECTIVES,
        DiagnosticFamily.VALIDATOR_DIRECTIVES,
        "validator directives cannot author or rewrite V2 workflow topology",
        "keep validators out of workflow source and declare routing or effects explicitly",
    ),
    _v2_spec(
        DiagnosticCode.DIRECT_MANIFEST_AUTHORING,
        DiagnosticFamily.DIRECT_MANIFEST_AUTHORING,
        "workflow manifests are compiled output and cannot be hand-authored in V2 source",
        "author workflow source forms and let the compiler produce the manifest",
    ),
    _v2_spec(
        DiagnosticCode.NATIVE_PROGRAM_PROJECTION,
        DiagnosticFamily.NATIVE_PROGRAM_PROJECTION,
        "native_program projection cannot be treated as the V2 source of truth",
        "preserve topology and identity in authored source rather than reading them back from native_program",
    ),
    _v2_spec(
        DiagnosticCode.MEGAPLAN_ONLY_HELPERS,
        DiagnosticFamily.MEGAPLAN_ONLY_HELPERS,
        "Megaplan-only helpers are rejected under the general V2 authoring contract",
        "replace bespoke helpers with general workflow, loop, route, or parallel_map constructs",
    ),
    _v2_spec(
        DiagnosticCode.TRACE_OBJECT_AUTHORING,
        DiagnosticFamily.TRACE_OBJECT_AUTHORING,
        "trace objects and audit record schemas cannot be hand-authored in V2 source",
        "declare topology and metadata only; runtime trace shapes are compiler- and runtime-owned",
    ),
    _v2_spec(
        DiagnosticCode.DYNAMIC_DISPATCH,
        DiagnosticFamily.DYNAMIC_DISPATCH,
        "dynamic dispatch is outside the statically enumerable V2 grammar",
        "invoke imported steps or workflows directly with literal identities",
    ),
    _v2_spec(
        DiagnosticCode.SINGLE_HANDLER_WRAPPER,
        DiagnosticFamily.SINGLE_HANDLER_WRAPPER,
        "single-handler wrappers cannot stand in for explicit V2 workflow topology",
        "spell out the workflow structure instead of hiding it behind one wrapper call",
    ),
    _v2_spec(
        DiagnosticCode.RUNTIME_TOPOLOGY_MUTATION,
        DiagnosticFamily.RUNTIME_TOPOLOGY_MUTATION,
        "runtime topology mutation is rejected under the V2 authoring grammar",
        "keep workflow structure static and move runtime-only branching into declared routes",
    ),
    _v2_spec(
        DiagnosticCode.MISSING_PARALLEL_MAP_REDUCER,
        DiagnosticFamily.MISSING_PARALLEL_MAP_REDUCER,
        "parallel_map is missing a required reducer",
        "provide a literal reducer callable or imported reducer reference",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_PARALLEL_MAP_ITEMS,
        DiagnosticFamily.INVALID_PARALLEL_MAP_ITEMS,
        "parallel_map items must be a statically declared collection reference",
        "bind items to a declared parameter or prior output with a literal reference",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_PARALLEL_MAP_PATH_TEMPLATE,
        DiagnosticFamily.INVALID_PARALLEL_MAP_PATH_TEMPLATE,
        "parallel_map path_template must be a literal stable coordinate template",
        "use a literal path template or rely on the default item index coordinate",
    ),
    _v2_spec(
        DiagnosticCode.UNDECLARED_LOOP_EXIT,
        DiagnosticFamily.UNDECLARED_LOOP_EXIT,
        "loop exit is not declared by the accepted V2 loop boundary",
        "declare loop exits through the canonical loop policy and accepted exit syntax",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_LOOP_BOUNDARY,
        DiagnosticFamily.INVALID_LOOP_BOUNDARY,
        "loop boundary metadata is malformed for the V2 authoring grammar",
        "keep loop bounds, reentry ids, and exit conditions literal and compiler-visible",
    ),
    _v2_spec(
        DiagnosticCode.UNDECLARED_POLICY_METADATA,
        DiagnosticFamily.UNDECLARED_POLICY_METADATA,
        "policy metadata is referenced without a declared V2 policy carrier",
        "attach named policy metadata at the workflow, step, or child-call boundary",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_POLICY_METADATA,
        DiagnosticFamily.INVALID_POLICY_METADATA,
        "policy metadata is malformed for the V2 authoring contract",
        "use supported policy categories with literal configuration fields only",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_WORKFLOW_INVOCATION,
        DiagnosticFamily.INVALID_WORKFLOW_INVOCATION,
        "workflow invocation does not match the accepted V2 callable form",
        "call imported workflow components directly with literal ids and declared bindings",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_WORKFLOW_REFERENCE,
        DiagnosticFamily.INVALID_WORKFLOW_REFERENCE,
        "workflow reference cannot be resolved to an invocable V2 workflow component",
        "import a statically resolvable workflow component instead of building one dynamically",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_COMPOSITION_METADATA,
        DiagnosticFamily.INVALID_COMPOSITION_METADATA,
        "composition metadata is malformed for a V2 workflow boundary",
        "keep child-call metadata literal, scoped, and aligned with the declared interface",
    ),
    _v2_spec(
        DiagnosticCode.MISSING_CALL_SITE_ID,
        DiagnosticFamily.MISSING_CALL_SITE_ID,
        "call site is missing the literal id required for stable path identity",
        "add a literal id keyword to the step or workflow call site",
    ),
    _v2_spec(
        DiagnosticCode.AMBIGUOUS_CALL_SITE_ID,
        DiagnosticFamily.AMBIGUOUS_CALL_SITE_ID,
        "call site id does not uniquely determine a stable path",
        "use one unambiguous literal id segment per authored call site",
    ),
    _v2_spec(
        DiagnosticCode.NON_LITERAL_CALL_SITE_ID,
        DiagnosticFamily.NON_LITERAL_CALL_SITE_ID,
        "call site id must be a literal string in the V2 authoring grammar",
        "replace computed or indirect ids with literal call-site ids",
    ),
    _v2_spec(
        DiagnosticCode.DUPLICATE_CALL_SITE_PATH,
        DiagnosticFamily.DUPLICATE_CALL_SITE_PATH,
        "multiple call sites lower to the same stable path identity",
        "choose distinct authored ids so each call site has its own path segment",
    ),
    _v2_spec(
        DiagnosticCode.MISSING_ITERATION_COORDINATE,
        DiagnosticFamily.MISSING_ITERATION_COORDINATE,
        "repeated execution boundary is missing an iteration coordinate",
        "record a loop or fanout coordinate beneath the static call-site path",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_ITERATION_COORDINATE,
        DiagnosticFamily.INVALID_ITERATION_COORDINATE,
        "iteration coordinate is malformed for V2 replay identity",
        "use bracketed monotonic coordinates such as [0] or [n]",
    ),
    _v2_spec(
        DiagnosticCode.MISSING_ITEM_COORDINATE,
        DiagnosticFamily.MISSING_ITEM_COORDINATE,
        "parallel_map item is missing a stable item coordinate",
        "emit an item coordinate from the path_template or list index",
    ),
    _v2_spec(
        DiagnosticCode.REPLAY_PATH_MISMATCH,
        DiagnosticFamily.REPLAY_PATH_MISMATCH,
        "recorded replay path does not match the authored V2 path identity",
        "preserve the authored static path and recorded coordinates across replay",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_PARENT_PATH,
        DiagnosticFamily.INVALID_PARENT_PATH,
        "parent workflow path is malformed for V2 provenance",
        "propagate the parent path from authored call-site identity only",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_CALL_SITE_PATH,
        DiagnosticFamily.INVALID_CALL_SITE_PATH,
        "call_site_path provenance is malformed for the V2 authoring contract",
        "store slash-delimited authored id segments plus bracketed coordinates only",
    ),
    _v2_spec(
        DiagnosticCode.CHILD_INPUT_SCHEMA_MISMATCH,
        DiagnosticFamily.CHILD_INPUT_SCHEMA_MISMATCH,
        "parent bindings do not satisfy the child workflow input schema",
        "align parent-to-child bindings with the child workflow's declared inputs",
    ),
    _v2_spec(
        DiagnosticCode.CHILD_OUTPUT_SCHEMA_MISMATCH,
        DiagnosticFamily.CHILD_OUTPUT_SCHEMA_MISMATCH,
        "child workflow outputs do not match the declared merge contract",
        "merge only declared child outputs and keep their names or bindings consistent",
    ),
    _v2_spec(
        DiagnosticCode.PARALLEL_MAP_ITEM_SCHEMA_MISMATCH,
        DiagnosticFamily.PARALLEL_MAP_ITEM_SCHEMA_MISMATCH,
        "parallel_map item values do not satisfy the mapper input contract",
        "align the items collection schema with the mapper's declared input",
    ),
    _v2_spec(
        DiagnosticCode.PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH,
        DiagnosticFamily.PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH,
        "parallel_map reducer inputs do not match the mapper result schema",
        "reduce the ordered mapper result shape the reducer declares",
    ),
    _v2_spec(
        DiagnosticCode.LOOP_EXIT_SCHEMA_MISMATCH,
        DiagnosticFamily.LOOP_EXIT_SCHEMA_MISMATCH,
        "loop exit data does not satisfy the declared continuation or result schema",
        "keep loop exit payloads aligned with the declared loop boundary contract",
    ),
    _v2_spec(
        DiagnosticCode.POLICY_SCHEMA_MISMATCH,
        DiagnosticFamily.POLICY_SCHEMA_MISMATCH,
        "policy metadata does not satisfy the declared policy schema",
        "provide policy configuration fields that match the declared policy contract",
    ),
    _v2_spec(
        DiagnosticCode.WORKFLOW_INPUT_BINDING_MISMATCH,
        DiagnosticFamily.WORKFLOW_INPUT_BINDING_MISMATCH,
        "workflow call input bindings do not match the invoked interface",
        "bind only declared inputs and satisfy their required names and schemas",
    ),
    _v2_spec(
        DiagnosticCode.WORKFLOW_OUTPUT_BINDING_MISMATCH,
        DiagnosticFamily.WORKFLOW_OUTPUT_BINDING_MISMATCH,
        "workflow call output bindings do not match the invoked interface",
        "map only declared outputs and keep bound names unique and schema-compatible",
    ),
    _v2_spec(
        DiagnosticCode.RESUME_SCHEMA_MISMATCH,
        DiagnosticFamily.RESUME_SCHEMA_MISMATCH,
        "resume or suspension payloads do not match the declared schema boundary",
        "align suspension and resume refs with their declared payload schemas",
    ),
    _v2_spec(
        DiagnosticCode.COMPOSITION_EFFECT_SCHEMA_MISMATCH,
        DiagnosticFamily.COMPOSITION_EFFECT_SCHEMA_MISMATCH,
        "composition-side effect metadata does not satisfy the declared schema",
        "keep composition effect payloads within the declared workflow interface",
    ),
    _v2_spec(
        DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE,
        DiagnosticFamily.UNRESOLVED_CALLEE_PROVENANCE,
        "handler_ref cannot be resolved to a declared Megaplan handler",
        "ensure the handler is exported from arnold_pipelines.megaplan.handlers and declared in components metadata",
    ),
    _v2_spec(
        DiagnosticCode.BRANCH_VOCABULARY_MISMATCH,
        DiagnosticFamily.BRANCH_VOCABULARY_MISMATCH,
        "route branch vocabulary does not match the declared RUNTIME_BRANCH_VOCABULARY for the active step domain",
        "use only declared enum members whose values are present in the runtime branch vocabulary",
    ),
    _v2_spec(
        DiagnosticCode.RAW_STRING_ROUTE_BRANCH,
        DiagnosticFamily.RAW_STRING_ROUTE_BRANCH,
        "route branch comparison uses a raw string literal instead of a declared typed outcome enum member",
        "replace string-constant branch conditions with typed outcome enum member comparisons",
    ),
    _v2_spec(
        DiagnosticCode.LOWERED_TOPOLOGY_DISCARD,
        DiagnosticFamily.LOWERED_TOPOLOGY_DISCARD,
        "source-derived lowered topology is discarded in favour of component-only rebuild",
        "consume lowered steps and routes instead of rebuilding topology solely from ALL_STEP_COMPONENTS route metadata",
    ),
    _v2_spec(
        DiagnosticCode.HANDLER_PURITY_VIOLATION,
        DiagnosticFamily.HANDLER_PURITY_VIOLATION,
        "handler declared as pure phase body contains routing call markers or state-mutation side effects",
        "remove routing logic from pure handlers or reclassify them as report-semantic owners",
    ),
    _v2_spec(
        DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
        DiagnosticFamily.ROW_EVIDENCE_INSUFFICIENCY,
        "conformance row is marked proven but lacks structured semantic evidence records",
        "provide source span, construct type, positive test, negative fixture, and compatibility quarantine records for every proven row",
    ),
    _v2_spec(
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticFamily.BOUNDARY_CONTRACT_MISSING,
        "boundary-crossing row is missing a declared BoundaryContract",
        "provide a BoundaryContract with required artifacts, state delta, and phase result expectations for the boundary",
    ),
    _v2_spec(
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticFamily.BOUNDARY_EVIDENCE_MISSING,
        "source topology is present but matching boundary evidence is missing",
        "emit a BoundaryReceipt with artifact refs, state observation, history ref, and phase result ref after boundary completion",
    ),
    _v2_spec(
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticFamily.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        "boundary evidence record exists without a matching source-authoritative route",
        "ensure the boundary evidence references a source-visible topology route in .pypeline or named native subworkflow",
    ),
    _v2_spec(
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        DiagnosticFamily.BOUNDARY_EVIDENCE_STALE,
        "boundary evidence is present but state observation, history ref, or phase result ref is stale or incoherent",
        "update the receipt with current state observation, history entry reference, and phase result after each boundary crossing",
    ),
    _v2_spec(
        DiagnosticCode.UNKNOWN_OUTCOME_TYPE,
        DiagnosticFamily.UNKNOWN_OUTCOME_TYPE,
        "branch route comparison references an unknown outcome type",
        "import a closed outcome enum from an allowed outcome module",
    ),
    _v2_spec(
        DiagnosticCode.INVALID_OUTCOME_MEMBER,
        DiagnosticFamily.INVALID_OUTCOME_MEMBER,
        "branch route comparison references an invalid outcome member",
        "compare route branches to a declared member of the imported outcome enum",
    ),
    _v2_spec(
        DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION,
        DiagnosticFamily.TIEBREAKER_SHAPE_VIOLATION,
        "tiebreaker is not source-visible as four explicit researcher/challenger/synthesis/decision phases with row-level evidence",
        "replace a single TIEBREAKER_WORKFLOW call or handler wrapper with four individually authored step calls (researcher, challenger, synthesis, decision) each backed by structured semantic evidence",
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
    call_site_path: str | None = None
    invocable_id: str | None = None
    policy_category: str | None = None
    rejection_category: str | None = None
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
        if self.call_site_path is not None and not self.call_site_path:
            raise ValueError("call_site_path must be non-empty when provided")
        if self.invocable_id is not None and not self.invocable_id:
            raise ValueError("invocable_id must be non-empty when provided")
        if self.policy_category is not None and not self.policy_category:
            raise ValueError("policy_category must be non-empty when provided")
        if self.rejection_category is not None and not self.rejection_category:
            raise ValueError("rejection_category must be non-empty when provided")

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
        if self.call_site_path is not None:
            payload["call_site_path"] = self.call_site_path
        if self.invocable_id is not None:
            payload["invocable_id"] = self.invocable_id
        if self.policy_category is not None:
            payload["policy_category"] = self.policy_category
        if self.rejection_category is not None:
            payload["rejection_category"] = self.rejection_category
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
