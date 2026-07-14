"""Source compiler foundation for Python-shaped workflow authoring.

This module owns source-oriented parsing data, resolver boundaries, spans, and
result carriers.  It is intentionally separate from ``arnold.workflow.compiler``:
that module lowers explicit DSL objects to manifests, while this one parses
Python-shaped source into compiler-owned intermediate data.

Author-facing workflow source files use either the ``.py`` or ``.pypeline``
suffix.  Both suffixes carry Python-shaped AST source and are parsed
identically; source spans, diagnostics, and manifest identity are preserved
regardless of suffix.  The ``.pypeline`` suffix is the author-facing convention
for explicit-node product workflows.

Ownership:
    Source diagnostics are produced here before lowering.  Explicit-node data
    is owned by ``arnold.workflow.dsl``, manifest output by
    ``arnold.workflow.compiler``, and shared scalar ref/hash predicates by
    ``arnold.workflow.refs``.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

from arnold.manifest.manifests import (
    AuthorityRequirement,
    ControlTransitionSlot,
    FanoutPolicy,
    LoopPolicy,
    RetryPolicy,
    SubpipelineRef,
    SuspensionRoute,
    TimingPolicy,
    WorkflowManifest,
    WorkflowPolicy,
)
from arnold.manifest.refs import ImportRef, SourceSpan
from arnold.workflow.authoring import (
    ComponentContract,
    ComponentKind,
    ComponentProvenance,
    PolicyComponent,
    RESERVED_SUBFLOW_CALL_KEYWORDS,
    RESERVED_INTRINSIC_CALL_KEYWORDS,
    RESERVED_STEP_CALL_KEYWORDS,
    StepComponent,
    SubflowComponent,
)
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.diagnostics import (
    ALLOWED_FUTURE_IMPORTS,
    AuthoringDiagnostic,
    AUTHORING_INTRINSIC_MODULE,
    DiagnosticCode,
    DiagnosticSeverity,
    RESERVED_AUTHORING_INTRINSICS,
    diagnostic_spec,
)
from arnold.workflow.boundary_evidence import (
    BoundaryContract,
    BoundaryReceipt,
    SemanticFinding,
    boundary_contract_missing_topology_detail_keys,
)
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step
from arnold.workflow.refs import is_manifest_hash, is_ref
from arnold.workflow.semantic_evidence import (
    S5_FINALIZE_ARTIFACTS_ROW_ID,
    S5_FINALIZE_FALLBACK_ROW_ID,
    S5_FINAL_PROJECTION_ROW_ID,
    S5_REVIEW_CAP_AUTHORITY_ROW_ID,
    S5_REVIEW_CHILD_OUTPUTS_ROW_ID,
    S5_REVIEW_HUMAN_VERIFICATION_ROW_ID,
    S5_REVIEW_REDUCER_PROMOTION_ROW_ID,
    S5_REVIEW_REWORK_EFFECTS_ROW_ID,
    SemanticEvidence,
)

_DEFAULT_SOURCE_PATH = "<workflow-source>"
_SUPPORTED_SOURCE_SUFFIXES = frozenset({".py", ".pypeline"})
_SUPPORTED_STEP_POLICY_TYPES = frozenset(
    {"approval", "authority", "control-transition", "retry", "timing"}
)
_SUPPORTED_WORKFLOW_CONTROL_POLICY_TYPES = frozenset(
    {"approval", "authority", "control-transition", "retry", "suspension", "timing"}
)
_INVALID_REF = object()
_LOWERED_STEP_METADATA_KEYS = frozenset({"handler_ref", "terminal"})
_MANIFEST_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_OUTCOME_MODULES = frozenset({"arnold_pipelines.megaplan.outcomes"})
_MEGAPLAN_COMPONENT_MODULE = "arnold_pipelines.megaplan.workflows.components"
_MEGAPLAN_REVIEW_PANEL_EXPORTS = frozenset(
    {"REVIEW_PANEL_WORKFLOW", "SOURCE_REVIEW_PANEL_WORKFLOW"}
)
_MEGAPLAN_REVIEW_REDUCER_EXPORTS = frozenset({"REVIEW", "SOURCE_REVIEW", "AUTHORING_REVIEW"})
_MEGAPLAN_EXECUTE_BATCH_EXPORTS = frozenset(
    {"EXECUTE_BATCH_WORKFLOW", "SOURCE_EXECUTE_BATCH_WORKFLOW"}
)
_MEGAPLAN_EXECUTE_REDUCER_EXPORTS = frozenset({"EXECUTE", "SOURCE_EXECUTE", "AUTHORING_EXECUTE"})
_MEGAPLAN_FINALIZE_EXPORTS = frozenset({"FINALIZE", "SOURCE_FINALIZE", "AUTHORING_FINALIZE"})
_MEGAPLAN_REVIEW_POLICY_EXPORT = "REVIEW_POLICY"
_MEGAPLAN_FINALIZE_POLICY_EXPORT = "FINALIZE_POLICY"
_MEGAPLAN_REVIEW_WORKFLOW_EXPORT = "SOURCE_REVIEW_PANEL_WORKFLOW"
_MEGAPLAN_AUTHORING_SOURCE_FILE = "workflow.pypeline"
_MEGAPLAN_DECLARED_STEP_INTERFACES_EXPORT = "DECLARED_STEP_INTERFACES"
_MEGAPLAN_DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS_EXPORT = "DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS"
_MEGAPLAN_WORKFLOW_ID_BY_TOPOLOGY_EXPORT = {
    "SOURCE_EXECUTE_BATCH_WORKFLOW": "execute_batch",
    "SOURCE_REVIEW_PANEL_WORKFLOW": "review_panel",
    "SOURCE_TIEBREAKER_WORKFLOW": "tiebreaker_child",
}
_MEGAPLAN_S5_REVIEW_ROW_IDS = frozenset(
    {
        S5_REVIEW_CHILD_OUTPUTS_ROW_ID,
        S5_REVIEW_REDUCER_PROMOTION_ROW_ID,
        S5_REVIEW_REWORK_EFFECTS_ROW_ID,
        S5_REVIEW_CAP_AUTHORITY_ROW_ID,
        S5_REVIEW_HUMAN_VERIFICATION_ROW_ID,
    }
)
_MEGAPLAN_S5_ROW_IDS = frozenset(
    {
        *_MEGAPLAN_S5_REVIEW_ROW_IDS,
        S5_FINALIZE_ARTIFACTS_ROW_ID,
        S5_FINALIZE_FALLBACK_ROW_ID,
        S5_FINAL_PROJECTION_ROW_ID,
    }
)


class SourceCompileError(ValueError):
    """Raised when a source API requiring a valid source receives diagnostics."""

    def __init__(self, diagnostics: Sequence[AuthoringDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        message = "; ".join(
            f"{diagnostic.code.value}: {diagnostic.message}" for diagnostic in self.diagnostics
        )
        super().__init__(message or "workflow source compilation failed")


SourceCompilationError = SourceCompileError


class ComponentResolver(Protocol):
    """Resolver boundary for static component metadata."""

    def resolve(self, import_ref: ImportRef) -> ComponentContract | None:
        """Return a typed component contract for ``import_ref`` if available."""


@dataclass(frozen=True)
class ImportBinding:
    """A local name bound by an accepted static import."""

    local_name: str
    import_ref: ImportRef
    kind: str
    source_span: SourceSpan
    component: ComponentContract | None = None
    outcome_type: type[StrEnum] | None = None

    @property
    def component_ref(self) -> str:
        return self.import_ref.spec


@dataclass(frozen=True)
class StepInputBinding:
    """Parsed source-level keyword input binding."""

    name: str
    value_ref: str
    source_span: SourceSpan


@dataclass(frozen=True)
class StepOutputBinding:
    """Parsed source-level assignment output binding."""

    name: str
    source_span: SourceSpan


@dataclass(frozen=True)
class StepPolicyBinding:
    """Parsed source-level policy keyword binding."""

    keyword: str
    component_ref: str
    component: PolicyComponent
    source_span: SourceSpan


@dataclass(frozen=True)
class WorkflowPolicyBinding:
    """Parsed source-level workflow policy keyword binding."""

    keyword: str
    component_ref: str
    component: PolicyComponent
    source_span: SourceSpan


@dataclass(frozen=True)
class ParsedStepCall:
    """Parsed source-level workflow step call."""

    id: str
    local_name: str
    component_ref: str
    source_span: SourceSpan
    component: StepComponent
    arguments: Mapping[str, ast.AST] = field(default_factory=dict)
    inputs: tuple[StepInputBinding, ...] = ()
    outputs: tuple[StepOutputBinding, ...] = ()
    policies: tuple[StepPolicyBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "policies", tuple(self.policies))


@dataclass(frozen=True)
class ParsedSubflowCall:
    """Parsed source-level subflow call with static manifest identity."""

    id: str
    local_name: str
    component_ref: str
    source_span: SourceSpan
    component: SubflowComponent
    manifest_hash: str
    alias: str | None = None
    arguments: Mapping[str, ast.AST] = field(default_factory=dict)
    inputs: tuple[StepInputBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))
        object.__setattr__(self, "inputs", tuple(self.inputs))


@dataclass(frozen=True)
class ParsedNestedWorkflowCall:
    """Parsed executable child ``@workflow`` call with authored call-site identity."""

    id: str
    local_name: str
    component_ref: str
    source_span: SourceSpan
    component: ComponentContract
    child_workflow_id: str
    parent_path: str
    call_site_path: str
    input_schema: tuple[str, ...] = ()
    output_schema: tuple[str, ...] = ()
    arguments: Mapping[str, ast.AST] = field(default_factory=dict)
    inputs: tuple[StepInputBinding, ...] = ()
    outputs: tuple[StepOutputBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", tuple(self.input_schema))
        object.__setattr__(self, "output_schema", tuple(self.output_schema))
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))


@dataclass(frozen=True)
class ParsedParallelMapCall:
    """Parsed source-level dynamic fanout over a runtime collection."""

    id: str
    source_span: SourceSpan
    items_ref: str
    mapper_ref: str
    reducer_ref: str
    path_template: str
    iteration_coordinate: str
    inputs: tuple[StepInputBinding, ...] = ()
    outputs: tuple[StepOutputBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))


@dataclass(frozen=True)
class ParsedIntrinsicCall:
    """Parsed source-level compiler intrinsic call."""

    name: str
    arguments: Mapping[str, str]
    source_span: SourceSpan

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class ParsedUnsupportedStatement:
    """Parsed source-level statement that is recognized but not yet lowerable."""

    reason: str
    source_span: SourceSpan
    node: ast.AST


@dataclass(frozen=True)
class ParsedBranchCondition:
    """Parsed source-level literal equality route condition."""

    decision_output: str
    literal: str
    source_span: SourceSpan


@dataclass(frozen=True)
class ParsedBranchArm:
    """One if/elif/else arm parsed from source."""

    condition: ParsedBranchCondition | None
    body: ParsedSourceBlock
    source_span: SourceSpan
    terminal: bool = False


@dataclass(frozen=True)
class ParsedBranchBlock:
    """Parsed source-level branch block awaiting lowering."""

    decision_output: str
    arms: tuple[ParsedBranchArm, ...]
    source_span: SourceSpan
    merged_outputs: Mapping[str, SourceSpan] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arms", tuple(self.arms))
        object.__setattr__(self, "merged_outputs", MappingProxyType(dict(self.merged_outputs)))


@dataclass(frozen=True)
class ParsedLoopPolicy:
    """Parsed source-level loop policy marker for the next while True block."""

    policy_ref: str
    max_iterations: int
    reentry_id: str
    until_ref: str | None
    source_span: SourceSpan


@dataclass(frozen=True)
class ParsedLoopBlock:
    """Parsed source-level bounded loop block awaiting backedge lowering."""

    policy: ParsedLoopPolicy
    body: ParsedSourceBlock
    source_span: SourceSpan
    entry_statement: ParsedSourceStatement | None = None
    body_tail_statements: tuple[ParsedSourceStatement, ...] = ()
    follow_statement: ParsedSourceStatement | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "body_tail_statements", tuple(self.body_tail_statements))


ParsedSourceStatement = (
    ParsedStepCall
    | ParsedSubflowCall
    | ParsedNestedWorkflowCall
    | ParsedParallelMapCall
    | ParsedIntrinsicCall
    | ParsedUnsupportedStatement
    | ParsedBranchBlock
    | ParsedLoopBlock
)


@dataclass(frozen=True)
class ParsedSourceBlock:
    """Ordered source-level statements for a workflow body or direct steps list."""

    statements: tuple[ParsedSourceStatement, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "statements", tuple(self.statements))

    @property
    def steps(self) -> tuple[ParsedStepCall, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedStepCall)
        )

    @property
    def subflows(self) -> tuple[ParsedSubflowCall, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedSubflowCall)
        )

    @property
    def nested_workflows(self) -> tuple[ParsedNestedWorkflowCall, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedNestedWorkflowCall)
        )

    @property
    def parallel_maps(self) -> tuple[ParsedParallelMapCall, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedParallelMapCall)
        )

    @property
    def intrinsics(self) -> tuple[ParsedIntrinsicCall, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedIntrinsicCall)
        )

    @property
    def unsupported(self) -> tuple[ParsedUnsupportedStatement, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedUnsupportedStatement)
        )

    @property
    def branches(self) -> tuple[ParsedBranchBlock, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedBranchBlock)
        )

    @property
    def loops(self) -> tuple[ParsedLoopBlock, ...]:
        return tuple(
            statement
            for statement in self.statements
            if isinstance(statement, ParsedLoopBlock)
        )


StepCall = ParsedStepCall
SubflowCall = ParsedSubflowCall
IntrinsicCall = ParsedIntrinsicCall


@dataclass(frozen=True)
class WorkflowDeclaration:
    """The single workflow source form selected from a module."""

    source_form: str
    id: str
    version: str
    source_span: SourceSpan
    function_name: str | None = None
    parameters: tuple[str, ...] = ()
    source_block: ParsedSourceBlock = field(default_factory=ParsedSourceBlock)
    steps: tuple[ParsedStepCall, ...] = ()
    intrinsics: tuple[ParsedIntrinsicCall, ...] = ()
    policies: tuple[WorkflowPolicyBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "policies", tuple(self.policies))
        source_block = self.source_block
        if not source_block.statements and (self.steps or self.intrinsics):
            source_block = ParsedSourceBlock((*self.steps, *self.intrinsics))
            object.__setattr__(self, "source_block", source_block)
        object.__setattr__(self, "steps", source_block.steps)
        object.__setattr__(self, "intrinsics", source_block.intrinsics)


@dataclass(frozen=True)
class SourceScope:
    """Immutable names visible to a parsed workflow source."""

    imports: Mapping[str, ImportBinding] = field(default_factory=dict)
    parameters: tuple[str, ...] = ()
    locals: Mapping[str, SourceSpan] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "imports", MappingProxyType(dict(self.imports)))
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "locals", MappingProxyType(dict(self.locals)))


@dataclass(frozen=True)
class ParsedWorkflowSource:
    """Parsed source module plus source-oriented compiler state."""

    source: str
    source_path: str
    module: ast.Module
    scope: SourceScope
    workflow: WorkflowDeclaration | None
    diagnostics: tuple[AuthoringDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True)
class CheckWorkflowSourceResult:
    """Result carrier for source validation.

    Boundary contracts and evidence fields (`boundary_evidence`) are
    observability-only: they report whether durable side effects exist for
    implemented front-half rows, but they never own, alter, or substitute
    for product route topology.  Route selection remains the exclusive
    province of source-level route declarations and runtime signal handlers;
    boundary evidence cannot create, satisfy, or mask the absence of a
    source-level row.
    """

    parsed_source: ParsedWorkflowSource
    evidence: tuple[SemanticEvidence, ...] = ()
    boundary_evidence: tuple[BoundaryReceipt | SemanticFinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "boundary_evidence", tuple(self.boundary_evidence))

    @property
    def diagnostics(self) -> tuple[AuthoringDiagnostic, ...]:
        return self.parsed_source.diagnostics

    @property
    def ok(self) -> bool:
        return not self.diagnostics


@dataclass(frozen=True)
class LowerWorkflowSourceResult(CheckWorkflowSourceResult):
    """Result carrier for source-to-DSL lowering."""

    pipeline: Pipeline | None = None


@dataclass(frozen=True)
class CompileWorkflowSourceResult(LowerWorkflowSourceResult):
    """Result carrier for source-to-manifest compilation."""

    manifest: WorkflowManifest | None = None


@dataclass(frozen=True)
class _LoweredSourceBlock:
    steps: tuple[Step, ...]
    routes: tuple[Route, ...]
    entry_step_id: str | None
    exit_step_ids: tuple[str, ...]
    output_producers: Mapping[str, str]


@dataclass(frozen=True)
class _LoopBackedgeBinding:
    tail_step_id: str
    route_id: str
    label: str
    condition_ref: str
    source_span: SourceSpan
    component_ref: str


@dataclass(frozen=True)
class _ImplementedFrontHalfRow:
    row_id: str
    phase: str
    source_span: SourceSpan
    component_ref: str


@dataclass(frozen=True)
class StaticComponentResolver:
    """Concrete resolver that imports module-level authoring component exports."""

    def resolve(self, import_ref: ImportRef) -> ComponentContract | None:
        try:
            value = import_ref.resolve()
        except Exception:
            return None
        if isinstance(value, ComponentContract):
            return value
        return None


def source_span_for_node(source_path: str | Path | None, node: ast.AST) -> SourceSpan:
    """Convert an AST node span to the 1-based ``SourceSpan`` contract."""

    return SourceSpan(
        path=_coerce_source_path(source_path),
        start_line=getattr(node, "lineno", 1),
        start_column=getattr(node, "col_offset", 0) + 1,
        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        end_column=getattr(node, "end_col_offset", getattr(node, "col_offset", 0)) + 1,
    )


def check_workflow_file(
    source_path: str | Path,
    *,
    resolver: ComponentResolver | None = None,
    evidence: Sequence[SemanticEvidence] | None = None,
    boundary_contracts: Sequence[BoundaryContract] = (),
    boundary_evidence: Sequence[BoundaryReceipt | SemanticFinding] = (),
) -> CheckWorkflowSourceResult:
    path = Path(source_path)
    return check_workflow_source(
        path.read_text(encoding="utf-8"),
        source_path=path,
        resolver=resolver,
        evidence=evidence,
        boundary_contracts=boundary_contracts,
        boundary_evidence=boundary_evidence,
    )


def check_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
    evidence: Sequence[SemanticEvidence] | None = (),
    boundary_contracts: Sequence[BoundaryContract] = (),
    boundary_evidence: Sequence[BoundaryReceipt | SemanticFinding] = (),
) -> CheckWorkflowSourceResult:
    """Validate workflow source and optionally check boundary contracts/evidence.

    Parameters
    ----------
    source:
        Workflow source text (Python-shaped AST).
    source_path:
        Optional path for diagnostic source spans.  When omitted diagnostics
        reference ``<workflow-source>``.
    resolver:
        Optional component resolver.
    evidence:
        Optional row-level ``SemanticEvidence`` records.  The source-checking API
        is strict by default and emits AWF245 for implemented front-half rows
        missing matching evidence.  ``check_workflow_file`` passes ``None`` by
        default to preserve legacy source-only validation for file callers.
    boundary_contracts:
        ``BoundaryContract`` records describing expected durable side effects
        for each front-half row.  Missing contracts produce AWF246.
    boundary_evidence:
        ``BoundaryReceipt`` or ``SemanticFinding`` records carrying durable
        side-effect observations.  Missing evidence produces AWF247; orphan
        evidence (no matching source row) produces AWF248; stale/incoherent
        evidence produces AWF249.

    Notes
    -----
    Boundary contracts and evidence are **observability-only**: they report
    whether durable effects exist but never own, alter, or substitute for
    product route topology.  Route selection is the exclusive province of
    source-level route declarations and runtime handlers.
    """
    parsed_source = parse_workflow_source(source, source_path=source_path, resolver=resolver)
    evidence_records = tuple(evidence or ())
    boundary_contract_records = tuple(boundary_contracts)
    boundary_evidence_records = tuple(boundary_evidence)
    row_evidence_diagnostics = (
        _row_evidence_diagnostics(parsed_source, evidence_records, boundary_contract_records)
        if evidence is not None
        else ()
    )
    boundary_diagnostics = _boundary_evidence_diagnostics(
        parsed_source,
        boundary_contract_records,
        boundary_evidence_records,
    )
    tiebreaker_shape_diagnostics = _tiebreaker_shape_diagnostics(parsed_source)
    megaplan_topology_diagnostics = _megaplan_review_finalize_diagnostics(parsed_source)
    if (
        row_evidence_diagnostics
        or boundary_diagnostics
        or tiebreaker_shape_diagnostics
        or megaplan_topology_diagnostics
    ):
        parsed_source = replace(
            parsed_source,
            diagnostics=(
                *parsed_source.diagnostics,
                *row_evidence_diagnostics,
                *boundary_diagnostics,
                *tiebreaker_shape_diagnostics,
                *megaplan_topology_diagnostics,
            ),
        )
    return CheckWorkflowSourceResult(
        parsed_source=parsed_source,
        evidence=evidence_records,
        boundary_evidence=boundary_evidence_records,
    )


def _row_evidence_diagnostics(
    parsed_source: ParsedWorkflowSource,
    evidence: Sequence[SemanticEvidence],
    boundary_contracts: Sequence[BoundaryContract] = (),
) -> tuple[AuthoringDiagnostic, ...]:
    implemented_rows = _implemented_front_half_rows(parsed_source.workflow, boundary_contracts)
    if not implemented_rows:
        return ()
    evidenced_row_ids = {record.row_id for record in evidence if record.row_id}
    diagnostics: list[AuthoringDiagnostic] = []
    for row in implemented_rows:
        if row.row_id in evidenced_row_ids:
            continue
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
                (
                    f"implemented front-half row {row.row_id!r} lacks matching SemanticEvidence "
                    f"for phase {row.phase!r}"
                ),
                source_span=row.source_span,
                component_ref=row.component_ref,
                details={
                    "row_id": row.row_id,
                    "phase": row.phase,
                },
            )
        )
    return tuple(diagnostics)


# ── S3 tiebreaker row IDs ──────────────────────────────────────────────────
# These are the four tiebreaker phases that must all be source-visible
# when any tiebreaker is present in the workflow source.

_S3_TIEBREAKER_REQUIRED_ROW_IDS: tuple[str, ...] = (
    "s3.tiebreaker_researcher.1",
    "s3.tiebreaker_challenger.1",
    "s3.tiebreaker_synthesis.1",
    "s3.tiebreaker_decision.1",
)

_S3_TIEBREAKER_REQUIRED_ROW_SET: frozenset[str] = frozenset(_S3_TIEBREAKER_REQUIRED_ROW_IDS)

# Component ref suffix for the legacy single-call TIEBREAKER_WORKFLOW wrapper.
_TIEBREAKER_WORKFLOW_COMPONENT_REF = (
    "arnold_pipelines.megaplan.workflows.components:SOURCE_TIEBREAKER_WORKFLOW"
)


def _collect_tiebreaker_workflow_calls(
    block: "ParsedSourceBlock",
) -> list[str]:
    """Collect component_refs where SOURCE_TIEBREAKER_WORKFLOW is called."""
    calls: list[str] = []
    for statement in block.statements:
        if isinstance(statement, ParsedSubflowCall):
            if statement.component_ref == _TIEBREAKER_WORKFLOW_COMPONENT_REF:
                calls.append(statement.component_ref)
        elif isinstance(statement, ParsedNestedWorkflowCall):
            if statement.component_ref == _TIEBREAKER_WORKFLOW_COMPONENT_REF:
                calls.append(statement.component_ref)
        elif isinstance(statement, ParsedStepCall):
            if statement.component_ref == _TIEBREAKER_WORKFLOW_COMPONENT_REF:
                calls.append(statement.component_ref)
        elif isinstance(statement, ParsedBranchBlock):
            for arm in statement.arms:
                calls.extend(_collect_tiebreaker_workflow_calls(arm.body))
        elif isinstance(statement, ParsedLoopBlock):
            calls.extend(_collect_tiebreaker_workflow_calls(statement.body))
    return calls


def _tiebreaker_shape_diagnostics(
    parsed_source: "ParsedWorkflowSource",
) -> tuple["AuthoringDiagnostic", ...]:
    """Emit AWF252 when a tiebreaker is present but not all four phases are source-visible.

    A valid tiebreaker must have four individually authored step calls
    (researcher, challenger, synthesis, decision), each backed by structured
    semantic evidence.  A single TIEBREAKER_WORKFLOW subworkflow call or
    handler wrapper is not sufficient.
    """
    workflow = parsed_source.workflow
    if workflow is None:
        return ()

    implemented_rows = _implemented_front_half_rows(workflow)
    implemented_s3_row_ids = {
        row.row_id
        for row in implemented_rows
        if row.row_id in _S3_TIEBREAKER_REQUIRED_ROW_SET
    }

    # If no S3 tiebreaker rows are present at all, check for the old
    # single-call wrapper pattern.
    if not implemented_s3_row_ids:
        tiebreaker_wf_calls = _collect_tiebreaker_workflow_calls(workflow.source_block)
        if tiebreaker_wf_calls:
            return (
                _diagnostic(
                    DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION,
                    (
                        "SOURCE_TIEBREAKER_WORKFLOW single-call wrapper detected "
                        "without source-visible researcher/challenger/synthesis/decision "
                        "phases; replace the wrapper with four individually authored "
                        "step calls"
                    ),
                    source_span=workflow.source_span,
                    component_ref=_TIEBREAKER_WORKFLOW_COMPONENT_REF,
                    details={
                        "missing_phases": list(_S3_TIEBREAKER_REQUIRED_ROW_IDS),
                        "detected_component": _TIEBREAKER_WORKFLOW_COMPONENT_REF,
                    },
                ),
            )
        return ()

    # If we have some S3 rows, all four must be present.
    missing_row_ids = sorted(_S3_TIEBREAKER_REQUIRED_ROW_SET - implemented_s3_row_ids)
    if not missing_row_ids:
        # All four phases are present — no shape violation.
        return ()

    diagnostics: list[AuthoringDiagnostic] = []
    for row_id in missing_row_ids:
        phase = row_id.replace("s3.", "").replace(".1", "")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION,
                (
                    f"tiebreaker phase {phase!r} (row {row_id!r}) is missing from "
                    f"source; all four phases (researcher, challenger, synthesis, "
                    f"decision) must be source-visible with row-level evidence"
                ),
                source_span=workflow.source_span,
                details={
                    "missing_row_id": row_id,
                    "missing_phase": phase,
                    "implemented_s3_rows": sorted(implemented_s3_row_ids),
                },
            )
        )
    return tuple(diagnostics)


def _normalized_component_export_name(value: str) -> str:
    export_name = value.rsplit(":", 1)[-1]
    if export_name.startswith("SOURCE_"):
        export_name = export_name.removeprefix("SOURCE_")
    if export_name.startswith("AUTHORING_"):
        export_name = export_name.removeprefix("AUTHORING_")
    return export_name


def _normalized_topology_id(value: str) -> str:
    return value.replace("_", "-")


def _component_ref_matches_exports(component_ref: str, exports: set[str] | frozenset[str]) -> bool:
    return _normalized_component_export_name(component_ref) in {
        _normalized_component_export_name(export_name) for export_name in exports
    }


def _collect_parallel_map_calls(block: ParsedSourceBlock) -> tuple[ParsedParallelMapCall, ...]:
    calls: list[ParsedParallelMapCall] = []
    for statement in block.statements:
        if isinstance(statement, ParsedParallelMapCall):
            calls.append(statement)
        elif isinstance(statement, ParsedBranchBlock):
            for arm in statement.arms:
                calls.extend(_collect_parallel_map_calls(arm.body))
        elif isinstance(statement, ParsedLoopBlock):
            calls.extend(_collect_parallel_map_calls(statement.body))
    return tuple(calls)


def _component_calls_for_exports(
    block: ParsedSourceBlock,
    exports: set[str] | frozenset[str],
) -> tuple[ParsedStepCall | ParsedSubflowCall | ParsedNestedWorkflowCall, ...]:
    calls: list[ParsedStepCall | ParsedSubflowCall | ParsedNestedWorkflowCall] = []
    for statement in block.statements:
        if isinstance(statement, (ParsedStepCall, ParsedSubflowCall, ParsedNestedWorkflowCall)):
            if _component_ref_matches_exports(statement.component_ref, exports):
                calls.append(statement)
        elif isinstance(statement, ParsedBranchBlock):
            for arm in statement.arms:
                calls.extend(_component_calls_for_exports(arm.body, exports))
        elif isinstance(statement, ParsedLoopBlock):
            calls.extend(_component_calls_for_exports(statement.body, exports))
    return tuple(calls)


def _step_calls_for_exports(
    block: ParsedSourceBlock,
    exports: set[str] | frozenset[str],
) -> tuple[ParsedStepCall, ...]:
    calls: list[ParsedStepCall] = []
    for statement in block.statements:
        if isinstance(statement, ParsedStepCall) and _component_ref_matches_exports(
            statement.component_ref,
            exports,
        ):
            calls.append(statement)
        elif isinstance(statement, ParsedBranchBlock):
            for arm in statement.arms:
                calls.extend(_step_calls_for_exports(arm.body, exports))
        elif isinstance(statement, ParsedLoopBlock):
            calls.extend(_step_calls_for_exports(statement.body, exports))
    return tuple(calls)


def _review_parallel_map_calls(block: ParsedSourceBlock) -> tuple[ParsedParallelMapCall, ...]:
    return tuple(
        call
        for call in _collect_parallel_map_calls(block)
        if _component_ref_matches_exports(call.mapper_ref, _MEGAPLAN_REVIEW_PANEL_EXPORTS)
    )


def _visible_review_fan_in_call(
    calls: Sequence[ParsedParallelMapCall],
) -> ParsedParallelMapCall | None:
    for call in calls:
        if (
            _normalized_topology_id(call.id).endswith("review-fan-in")
            and _component_ref_matches_exports(call.reducer_ref, _MEGAPLAN_REVIEW_REDUCER_EXPORTS)
            and call.path_template == "review/{item_id}"
        ):
            return call
    return None


def _visible_review_rework_cycle_call(
    block: ParsedSourceBlock,
) -> ParsedParallelMapCall | None:
    execute_calls = [
        call
        for call in _collect_parallel_map_calls(block)
        if _normalized_topology_id(call.id).endswith("review-rework-execute-batches")
        and _component_ref_matches_exports(call.mapper_ref, _MEGAPLAN_EXECUTE_BATCH_EXPORTS)
        and _component_ref_matches_exports(call.reducer_ref, _MEGAPLAN_EXECUTE_REDUCER_EXPORTS)
    ]
    review_calls = [
        call
        for call in _review_parallel_map_calls(block)
        if _normalized_topology_id(call.id).endswith("review-rework-fan-in")
        and _component_ref_matches_exports(call.reducer_ref, _MEGAPLAN_REVIEW_REDUCER_EXPORTS)
    ]
    if execute_calls and review_calls:
        return review_calls[0]
    return None


@lru_cache(maxsize=1)
def _megaplan_authoring_source_path() -> Path | None:
    try:
        module = import_module(_MEGAPLAN_COMPONENT_MODULE)
    except Exception:
        return None
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str):
        return None
    source_path = Path(module_file).with_name(_MEGAPLAN_AUTHORING_SOURCE_FILE)
    return source_path if source_path.is_file() else None


@lru_cache(maxsize=1)
def _megaplan_literal_source_declarations() -> Mapping[str, Any]:
    source_path = _megaplan_authoring_source_path()
    if source_path is None:
        return MappingProxyType({})
    try:
        module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except Exception:
        return MappingProxyType({})

    declarations: dict[str, Any] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                declarations[target.id] = value
    return MappingProxyType(declarations)


def _megaplan_declared_step_interfaces() -> Mapping[str, Mapping[str, Any]]:
    declared = _megaplan_literal_source_declarations().get(
        _MEGAPLAN_DECLARED_STEP_INTERFACES_EXPORT,
        {},
    )
    return declared if isinstance(declared, Mapping) else MappingProxyType({})


def _megaplan_declared_workflow_topology_contracts() -> Mapping[str, Mapping[str, Any]]:
    declared = _megaplan_literal_source_declarations().get(
        _MEGAPLAN_DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS_EXPORT,
        {},
    )
    return declared if isinstance(declared, Mapping) else MappingProxyType({})


def _megaplan_step_declared_interface(component: StepComponent) -> Mapping[str, Any]:
    if component.provenance.module != _MEGAPLAN_COMPONENT_MODULE:
        return MappingProxyType({})
    step_id = component.id.removeprefix("megaplan:")
    declared = _megaplan_declared_step_interfaces().get(step_id, {})
    return declared if isinstance(declared, Mapping) else MappingProxyType({})


def _megaplan_export_metadata(export_name: str) -> Mapping[str, Any]:
    try:
        module = import_module(_MEGAPLAN_COMPONENT_MODULE)
    except Exception:
        return MappingProxyType({})
    export = getattr(module, export_name, None)
    metadata = getattr(export, "metadata", None)
    return metadata if isinstance(metadata, Mapping) else MappingProxyType({})


def _megaplan_policy_route_surface(export_name: str) -> Mapping[str, Any]:
    route_surface = _megaplan_export_metadata(export_name).get("route_surface")
    return route_surface if isinstance(route_surface, Mapping) else MappingProxyType({})


def _megaplan_workflow_topology_contract(export_name: str) -> Mapping[str, Any]:
    workflow_id = _MEGAPLAN_WORKFLOW_ID_BY_TOPOLOGY_EXPORT.get(export_name)
    if workflow_id is not None:
        declared = _megaplan_declared_workflow_topology_contracts().get(workflow_id, {})
        if isinstance(declared, Mapping):
            return declared
    topology_contract = _megaplan_export_metadata(export_name).get("topology_contract")
    return topology_contract if isinstance(topology_contract, Mapping) else MappingProxyType({})


def _megaplan_review_topology_contract() -> Mapping[str, Any]:
    return _megaplan_workflow_topology_contract(_MEGAPLAN_REVIEW_WORKFLOW_EXPORT)


def _megaplan_workflow_fanout_contract(export_name: str) -> Mapping[str, Any]:
    topology_contract = _megaplan_workflow_topology_contract(export_name)
    fanout_contract = topology_contract.get("fanout_contract")
    return fanout_contract if isinstance(fanout_contract, Mapping) else MappingProxyType({})


def _megaplan_workflow_fan_in_contract(export_name: str) -> Mapping[str, Any]:
    topology_contract = _megaplan_workflow_topology_contract(export_name)
    fan_in_contract = topology_contract.get("fan_in_contract")
    return fan_in_contract if isinstance(fan_in_contract, Mapping) else MappingProxyType({})


def _review_topology_contract_owns_cap_thresholds(contract: Mapping[str, Any]) -> bool:
    disallowed_keys = {
        "cap_thresholds",
        "max_review_rework_cycles",
        "max_rework_cycles",
        "review_cap_threshold",
        "rework_cycle_cap",
    }
    for key, value in contract.items():
        lowered_key = str(key).lower()
        if lowered_key in disallowed_keys or lowered_key.endswith("_threshold"):
            return True
        if lowered_key == "retry_and_cap" and isinstance(value, Mapping):
            for nested_key, nested_value in value.items():
                nested_lowered = str(nested_key).lower()
                if nested_lowered in disallowed_keys or nested_lowered.endswith("_threshold"):
                    return True
                if isinstance(nested_value, Mapping):
                    return True
        elif isinstance(value, Mapping) and _review_topology_contract_owns_cap_thresholds(value):
            return True
    return False


def _megaplan_surface_ref_exists(surface_ref: str) -> bool:
    if not surface_ref or "." not in surface_ref:
        return False
    try:
        module = import_module(_MEGAPLAN_COMPONENT_MODULE)
    except Exception:
        return False
    current: Any = module
    for segment in surface_ref.split("."):
        if isinstance(current, Mapping):
            current = current.get(segment, _INVALID_REF)
        else:
            current = getattr(current, segment, _INVALID_REF)
        if current is _INVALID_REF:
            return False
    return True


def _megaplan_policy_transition_exists(policy_export: str, transition_id: str) -> bool:
    if not transition_id:
        return False
    try:
        module = import_module(_MEGAPLAN_COMPONENT_MODULE)
    except Exception:
        return False
    policy = getattr(module, policy_export, None)
    config = getattr(policy, "config", None)
    if not isinstance(config, Mapping):
        return False
    transitions = config.get("control_transitions", ())
    if not isinstance(transitions, Sequence):
        return False
    return any(
        isinstance(transition, Mapping)
        and transition.get("transition_id") == transition_id
        for transition in transitions
    )


def _megaplan_review_finalize_diagnostics(
    parsed_source: "ParsedWorkflowSource",
) -> tuple["AuthoringDiagnostic", ...]:
    workflow = parsed_source.workflow
    if workflow is None:
        return ()

    review_parallel_maps = _review_parallel_map_calls(workflow.source_block)
    direct_review_calls = _component_calls_for_exports(
        workflow.source_block,
        _MEGAPLAN_REVIEW_PANEL_EXPORTS,
    )
    finalize_calls = _step_calls_for_exports(
        workflow.source_block,
        _MEGAPLAN_FINALIZE_EXPORTS,
    )
    if not review_parallel_maps and not direct_review_calls and not finalize_calls:
        return ()

    diagnostics: list[AuthoringDiagnostic] = []
    visible_review_fan_in = _visible_review_fan_in_call(review_parallel_maps)
    if review_parallel_maps and visible_review_fan_in is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.SINGLE_HANDLER_WRAPPER,
                (
                    "review fanout must expose a source-visible review-fan-in parallel_map "
                    "with REVIEW_PANEL_WORKFLOW child calls and SOURCE/AUTHORING_REVIEW reducer"
                ),
                source_span=review_parallel_maps[0].source_span,
                component_ref=review_parallel_maps[0].mapper_ref,
            )
        )
    if direct_review_calls and visible_review_fan_in is None:
        first_call = direct_review_calls[0]
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.SINGLE_HANDLER_WRAPPER,
                (
                    "review fanout must remain source-visible as parallel_map fan-in plus "
                    "reducer; direct REVIEW_PANEL_WORKFLOW call detected"
                ),
                source_span=first_call.source_span,
                component_ref=first_call.component_ref,
            )
        )

    if review_parallel_maps:
        review_policy_surface = _megaplan_policy_route_surface(_MEGAPLAN_REVIEW_POLICY_EXPORT)
        review_topology_contract = _megaplan_review_topology_contract()
        if (
            not isinstance(review_policy_surface.get("cap_thresholds"), Mapping)
            or not isinstance(review_policy_surface.get("blocked_and_advisory_outcomes"), Mapping)
            or not isinstance(review_policy_surface.get("force_proceed_authority"), Mapping)
            or _review_topology_contract_owns_cap_thresholds(review_topology_contract)
        ):
            anchor = visible_review_fan_in or review_parallel_maps[0]
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.HANDLER_PURITY_VIOLATION,
                    (
                        "review cap thresholds and cap-exhausted authority must be declared "
                        "on REVIEW_POLICY, not hidden in handler-owned review topology metadata"
                    ),
                    source_span=anchor.source_span,
                    component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_REVIEW_POLICY_EXPORT}",
                )
            )

    if finalize_calls:
        finalize_policy_surface = _megaplan_policy_route_surface(_MEGAPLAN_FINALIZE_POLICY_EXPORT)
        fallback_routes = finalize_policy_surface.get("fallback_routes")
        projection_routes = finalize_policy_surface.get("final_projection_routes")
        if (
            not isinstance(fallback_routes, Mapping)
            or "plan_contract_revise_needed" not in fallback_routes
            or not isinstance(projection_routes, Mapping)
            or "revise_fallback" not in projection_routes
        ):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.HANDLER_PURITY_VIOLATION,
                    (
                        "finalize fallback must be visible in FINALIZE_POLICY route surfaces "
                        "instead of relying on hidden handler fallback logic"
                    ),
                    source_span=finalize_calls[0].source_span,
                    component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_FINALIZE_POLICY_EXPORT}",
                )
            )

    return tuple(diagnostics)


def _boundary_evidence_diagnostics(
    parsed_source: ParsedWorkflowSource,
    boundary_contracts: Sequence[BoundaryContract],
    boundary_evidence: Sequence[BoundaryReceipt | SemanticFinding],
) -> tuple[AuthoringDiagnostic, ...]:
    """Check implemented front-half rows against boundary contracts and evidence.

    This function is a **read-only observer**: it inspects whether durable
    side effects (receipts, semantic-health findings, contracts) exist for
    each implemented front-half row, but it never owns, produces, or modifies
    product route topology.  A missing contract produces AWF246, missing
    evidence produces AWF247, orphan evidence (no matching source row)
    produces AWF248, and stale/incoherent evidence produces AWF249 — none
    of these diagnostics create or substitute for a source-level row.
    """
    if not boundary_contracts and not boundary_evidence:
        return ()

    implemented_rows = _implemented_boundary_rows(parsed_source.workflow, boundary_contracts)
    implemented_by_row_id = {row.row_id: row for row in implemented_rows}
    contracts_by_row_id = {
        contract.row_id: contract
        for contract in boundary_contracts
        if contract.row_id
    }
    contracts_by_boundary_id = {
        contract.boundary_id: contract for contract in boundary_contracts
    }

    receipt_index: dict[str, list[BoundaryReceipt]] = {}
    finding_index: dict[str, list[SemanticFinding]] = {}
    orphan_boundary_evidence: list[BoundaryReceipt | SemanticFinding] = []

    for record in boundary_evidence:
        contract = _boundary_contract_for_record(
            record,
            contracts_by_boundary_id=contracts_by_boundary_id,
            contracts_by_row_id=contracts_by_row_id,
        )
        if contract is None or contract.row_id not in implemented_by_row_id:
            orphan_boundary_evidence.append(record)
            continue
        if isinstance(record, BoundaryReceipt):
            receipt_index.setdefault(contract.boundary_id, []).append(record)
        else:
            finding_index.setdefault(contract.boundary_id, []).append(record)

    diagnostics: list[AuthoringDiagnostic] = []
    for row in implemented_rows:
        contract = contracts_by_row_id.get(row.row_id)
        if contract is None:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
                    (
                        f"implemented front-half row {row.row_id!r} lacks a matching "
                        f"BoundaryContract for phase {row.phase!r}"
                    ),
                    source_span=row.source_span,
                    component_ref=row.component_ref,
                    details={
                        "row_id": row.row_id,
                        "phase": row.phase,
                    },
                )
            )
            continue

        topology_issues = _boundary_topology_issues(
            contract=contract,
            row=row,
            parsed_source=parsed_source,
        )
        if topology_issues:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
                    (
                        f"boundary evidence for contract {contract.boundary_id!r} lacks a "
                        f"matching source-visible topology carrier for row {row.row_id!r}"
                    ),
                    source_span=row.source_span,
                    component_ref=row.component_ref,
                    details={
                        "boundary_id": contract.boundary_id,
                        "row_id": row.row_id,
                        "phase": row.phase,
                        "topology_issues": tuple(topology_issues),
                    },
                )
            )
            continue

        boundary_findings = tuple(finding_index.get(contract.boundary_id, ()))
        if boundary_findings:
            diagnostics.extend(
                _boundary_finding_diagnostics(
                    row=row,
                    contract=contract,
                    findings=boundary_findings,
                )
            )
            continue

        boundary_receipts = tuple(receipt_index.get(contract.boundary_id, ()))
        if not boundary_receipts:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    (
                        f"implemented front-half row {row.row_id!r} requires durable boundary "
                        f"evidence for contract {contract.boundary_id!r}"
                    ),
                    source_span=row.source_span,
                    component_ref=row.component_ref,
                    details={
                        "boundary_id": contract.boundary_id,
                        "row_id": row.row_id,
                        "phase": row.phase,
                    },
                )
            )
            continue

        receipt_issues = _boundary_receipt_issues(
            contract=contract,
            row=row,
            receipts=boundary_receipts,
        )
        if receipt_issues:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                    (
                        f"durable boundary evidence for contract {contract.boundary_id!r} is "
                        f"stale or incoherent with implemented row {row.row_id!r}"
                    ),
                    source_span=row.source_span,
                    component_ref=row.component_ref,
                    details={
                        "boundary_id": contract.boundary_id,
                        "row_id": row.row_id,
                        "phase": row.phase,
                        "receipt_issues": tuple(receipt_issues),
                    },
                )
            )

    for record in orphan_boundary_evidence:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
                _boundary_orphan_message(record),
                source_span=_boundary_anchor_source_span(parsed_source),
                details=_boundary_orphan_details(record),
            )
        )

    return tuple(diagnostics)


def _boundary_topology_issues(
    *,
    contract: BoundaryContract,
    row: _ImplementedFrontHalfRow,
    parsed_source: ParsedWorkflowSource,
) -> tuple[str, ...]:
    if contract.row_id not in _MEGAPLAN_S5_ROW_IDS:
        return ()

    issues = list(boundary_contract_missing_topology_detail_keys(contract))
    if issues:
        return tuple(issues)

    details = contract.details
    review_parallel_maps = _review_parallel_map_calls(parsed_source.workflow.source_block) if parsed_source.workflow else ()
    review_fan_in = _visible_review_fan_in_call(review_parallel_maps)
    review_rework = _visible_review_rework_cycle_call(parsed_source.workflow.source_block) if parsed_source.workflow else None
    review_policy_surface = _megaplan_policy_route_surface(_MEGAPLAN_REVIEW_POLICY_EXPORT)
    finalize_policy_surface = _megaplan_policy_route_surface(_MEGAPLAN_FINALIZE_POLICY_EXPORT)

    if contract.row_id == S5_REVIEW_CHILD_OUTPUTS_ROW_ID:
        if review_fan_in is None:
            issues.append("review_fan_in_missing")
        if details.get("fan_in_ref") != "review-fan-in":
            issues.append("fan_in_ref")
        if not _megaplan_surface_ref_exists(str(details.get("evidence_surface_ref"))):
            issues.append("evidence_surface_ref")
    elif contract.row_id == S5_REVIEW_REDUCER_PROMOTION_ROW_ID:
        if review_fan_in is None:
            issues.append("review_reducer_missing")
        else:
            expected_reducer = _normalized_component_export_name(str(details.get("reducer_ref")))
            actual_reducer = _normalized_component_export_name(review_fan_in.reducer_ref)
            if expected_reducer != actual_reducer:
                issues.append("reducer_ref")
    elif contract.row_id == S5_REVIEW_REWORK_EFFECTS_ROW_ID:
        if review_rework is None:
            issues.append("review_rework_topology_missing")
        if not _megaplan_surface_ref_exists(str(details.get("evidence_surface_ref"))):
            issues.append("evidence_surface_ref")
    elif contract.row_id == S5_REVIEW_CAP_AUTHORITY_ROW_ID:
        if not isinstance(review_policy_surface.get("cap_thresholds"), Mapping):
            issues.append("cap_thresholds")
        if not isinstance(review_policy_surface.get("force_proceed_authority"), Mapping):
            issues.append("force_proceed_authority")
        if _review_topology_contract_owns_cap_thresholds(_megaplan_review_topology_contract()):
            issues.append("handler_owned_cap_thresholds")
    elif contract.row_id == S5_REVIEW_HUMAN_VERIFICATION_ROW_ID:
        if not isinstance(review_policy_surface.get("human_verification"), Mapping):
            issues.append("human_verification")
    elif contract.row_id == S5_FINALIZE_ARTIFACTS_ROW_ID:
        if not isinstance(finalize_policy_surface.get("canonical_artifacts"), Mapping):
            issues.append("canonical_artifacts")
    elif contract.row_id == S5_FINALIZE_FALLBACK_ROW_ID:
        if not _megaplan_surface_ref_exists(str(details.get("evidence_surface_ref"))):
            issues.append("evidence_surface_ref")
        if not _megaplan_policy_transition_exists(
            _MEGAPLAN_FINALIZE_POLICY_EXPORT,
            str(details.get("projection_ref")),
        ):
            issues.append("projection_ref")
    elif contract.row_id == S5_FINAL_PROJECTION_ROW_ID:
        if not _megaplan_surface_ref_exists(str(details.get("evidence_surface_ref"))):
            issues.append("evidence_surface_ref")
        if not isinstance(finalize_policy_surface.get("final_projection_routes"), Mapping):
            issues.append("final_projection_routes")
    return tuple(issues)


def _boundary_contract_for_record(
    record: BoundaryReceipt | SemanticFinding,
    *,
    contracts_by_boundary_id: Mapping[str, BoundaryContract],
    contracts_by_row_id: Mapping[str, BoundaryContract],
) -> BoundaryContract | None:
    if isinstance(record, SemanticFinding):
        return contracts_by_boundary_id.get(record.boundary_id)
    contract = contracts_by_boundary_id.get(record.boundary_id)
    if contract is not None:
        return contract
    if record.row_id is None:
        return None
    return contracts_by_row_id.get(record.row_id)


def _boundary_finding_diagnostics(
    *,
    row: _ImplementedFrontHalfRow,
    contract: BoundaryContract,
    findings: Sequence[SemanticFinding],
) -> tuple[AuthoringDiagnostic, ...]:
    diagnostics: list[AuthoringDiagnostic] = []
    findings_by_code: dict[DiagnosticCode, list[SemanticFinding]] = {}
    for finding in findings:
        if finding.diagnostic_code is None:
            continue
        if finding.diagnostic_code not in {
            DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
            DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
            DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
            DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        }:
            continue
        findings_by_code.setdefault(finding.diagnostic_code, []).append(finding)

    for code in (
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    ):
        code_findings = findings_by_code.get(code)
        if not code_findings:
            continue
        diagnostics.append(
            _diagnostic(
                code,
                (
                    f"boundary finding(s) for contract {contract.boundary_id!r} report "
                    f"{code.value}"
                ),
                source_span=row.source_span,
                component_ref=row.component_ref,
                details={
                    "boundary_id": contract.boundary_id,
                    "row_id": row.row_id,
                    "phase": row.phase,
                    "finding_ids": tuple(finding.finding_id for finding in code_findings),
                    "finding_descriptions": tuple(
                        finding.description for finding in code_findings
                    ),
                },
            )
        )
    return tuple(diagnostics)


def _boundary_receipt_issues(
    *,
    contract: BoundaryContract,
    row: _ImplementedFrontHalfRow,
    receipts: Sequence[BoundaryReceipt],
) -> tuple[str, ...]:
    issues: list[str] = []
    required_artifacts = set(contract.required_artifacts)
    expected_state_delta = dict(contract.expected_state_delta)
    expected_history_entry = contract.expected_history_entry

    for receipt in receipts:
        if receipt.workflow_id != contract.workflow_id:
            issues.append(
                f"workflow_id mismatch: expected {contract.workflow_id!r}, got {receipt.workflow_id!r}"
            )
        if receipt.row_id not in (None, row.row_id):
            issues.append(
                f"row_id mismatch: expected {row.row_id!r}, got {receipt.row_id!r}"
            )
        missing_artifacts = sorted(required_artifacts.difference(receipt.artifact_refs))
        if missing_artifacts:
            issues.append(
                f"missing artifacts: {', '.join(repr(artifact) for artifact in missing_artifacts)}"
            )
        for key, expected_value in expected_state_delta.items():
            observed_value = receipt.state_observation.get(key)
            if observed_value != expected_value:
                issues.append(
                    f"state mismatch for {key!r}: expected {expected_value!r}, got {observed_value!r}"
                )
        if expected_history_entry is not None and receipt.history_ref != expected_history_entry:
            issues.append(
                f"history mismatch: expected {expected_history_entry!r}, got {receipt.history_ref!r}"
            )
        if contract.phase_result_required and not receipt.phase_result_ref:
            issues.append("missing phase_result_ref")
        if contract.authority_required and not receipt.authority_records:
            issues.append("missing authority_records")
        if _boundary_details_mark_stale(receipt.details):
            issues.append("receipt details report stale or expired observations")

    return tuple(dict.fromkeys(issues))


def _boundary_details_mark_stale(details: Mapping[str, Any]) -> bool:
    stale_strings = {
        "expired",
        "false",
        "invalid",
        "missing",
        "old",
        "outdated",
        "stale",
    }
    fresh_strings = {"current", "fresh", "ok", "pass", "passed", "true", "valid"}
    for key, value in details.items():
        lowered_key = str(key).lower()
        if isinstance(value, Mapping):
            if _boundary_details_mark_stale(value):
                return True
            continue
        if isinstance(value, (list, tuple)):
            if any(
                _boundary_details_mark_stale({"value": item})
                if isinstance(item, Mapping)
                else _boundary_scalar_marks_stale(lowered_key, item, stale_strings, fresh_strings)
                for item in value
            ):
                return True
            continue
        if _boundary_scalar_marks_stale(lowered_key, value, stale_strings, fresh_strings):
            return True
    return False


def _boundary_scalar_marks_stale(
    key: str,
    value: Any,
    stale_strings: set[str],
    fresh_strings: set[str],
) -> bool:
    if "stale" in key or "expired" in key:
        return bool(value)
    if "fresh" in key:
        if isinstance(value, bool):
            return not value
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in fresh_strings:
                return False
            if lowered in stale_strings:
                return True
    if "freshness" in key and isinstance(value, str):
        lowered = value.lower()
        if lowered in fresh_strings:
            return False
        if lowered in stale_strings:
            return True
    return False


def _boundary_anchor_source_span(parsed_source: ParsedWorkflowSource) -> SourceSpan:
    workflow = parsed_source.workflow
    if workflow is not None:
        return workflow.source_span
    return SourceSpan(
        path=parsed_source.source_path,
        start_line=1,
        start_column=1,
        end_line=1,
        end_column=1,
    )


def _boundary_orphan_message(record: BoundaryReceipt | SemanticFinding) -> str:
    if isinstance(record, BoundaryReceipt):
        return (
            f"boundary receipt for {record.boundary_id!r} does not have matching "
            "source topology in the supplied workflow"
        )
    return (
        f"boundary finding for {record.boundary_id!r} does not have matching "
        "source topology in the supplied workflow"
    )


def _boundary_orphan_details(
    record: BoundaryReceipt | SemanticFinding,
) -> Mapping[str, Any]:
    if isinstance(record, BoundaryReceipt):
        return {
            "boundary_id": record.boundary_id,
            "row_id": record.row_id,
            "evidence_kind": "boundary_receipt",
        }
    return {
        "boundary_id": record.boundary_id,
        "finding_id": record.finding_id,
        "diagnostic_code": (
            record.diagnostic_code.value
            if record.diagnostic_code is not None
            else None
        ),
        "evidence_kind": "semantic_finding",
    }


def _implemented_front_half_rows(
    workflow: WorkflowDeclaration | None,
    boundary_contracts: Sequence[BoundaryContract] = (),
) -> tuple[_ImplementedFrontHalfRow, ...]:
    if workflow is None:
        return ()
    row_specs = _front_half_row_specs(boundary_contracts)
    if not row_specs:
        return ()
    implemented_by_row_id: dict[str, _ImplementedFrontHalfRow] = {}
    _collect_front_half_rows(workflow.source_block, row_specs, implemented_by_row_id)
    return tuple(implemented_by_row_id.values())


def _collect_front_half_rows(
    block: ParsedSourceBlock,
    row_specs: Mapping[str, tuple[str, str]],
    implemented_by_row_id: dict[str, _ImplementedFrontHalfRow],
) -> None:
    for statement in block.statements:
        if isinstance(statement, ParsedStepCall):
            row_spec = row_specs.get(statement.component_ref)
            if row_spec is not None:
                row_id, phase = row_spec
                implemented_by_row_id.setdefault(
                    row_id,
                    _ImplementedFrontHalfRow(
                        row_id=row_id,
                        phase=phase,
                        source_span=statement.source_span,
                        component_ref=statement.component_ref,
                    ),
                )
        elif isinstance(statement, ParsedParallelMapCall):
            row_spec = row_specs.get(statement.reducer_ref)
            if row_spec is not None:
                row_id, phase = row_spec
                implemented_by_row_id.setdefault(
                    row_id,
                    _ImplementedFrontHalfRow(
                        row_id=row_id,
                        phase=phase,
                        source_span=statement.source_span,
                        component_ref=statement.reducer_ref,
                    ),
                )
        elif isinstance(statement, ParsedBranchBlock):
            for arm in statement.arms:
                _collect_front_half_rows(arm.body, row_specs, implemented_by_row_id)
        elif isinstance(statement, ParsedLoopBlock):
            _collect_front_half_rows(statement.body, row_specs, implemented_by_row_id)


def _front_half_row_specs(
    boundary_contracts: Sequence[BoundaryContract] = (),
) -> Mapping[str, tuple[str, str]]:
    """Build row_specs mapping component_ref → (row_id, phase) from boundary contracts.

    This is a neutral interface: callers inject their own BoundaryContract
    sequences.  The generic source compiler does not import
    ``arnold_pipelines.megaplan``.
    """
    if not boundary_contracts:
        return MappingProxyType({})
    front_half_phases = frozenset(
        {
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
            "tiebreaker_researcher",
            "tiebreaker_challenger",
            "tiebreaker_synthesis",
            "tiebreaker_decision",
        }
    )
    row_specs: dict[str, tuple[str, str]] = {}
    for contract in boundary_contracts:
        if contract.phase is None or contract.row_id is None:
            continue
        if contract.phase.value not in front_half_phases:
            continue
        phase_name = contract.phase.value.upper()
        # Prefixed exports (SOURCE_*, AUTHORING_*) plus the bare export name
        # so that components like TIEBREAKER_RESEARCHER (which don't follow
        # the SOURCE_/AUTHORING_ convention) are still detected.
        for export_name in (f"SOURCE_{phase_name}", f"AUTHORING_{phase_name}", phase_name):
            row_specs[
                f"arnold_pipelines.megaplan.workflows.components:{export_name}"
            ] = (contract.row_id, contract.phase.value)
    return MappingProxyType(row_specs)


def _implemented_boundary_rows(
    workflow: WorkflowDeclaration | None,
    boundary_contracts: Sequence[BoundaryContract] = (),
) -> tuple[_ImplementedFrontHalfRow, ...]:
    if workflow is None:
        return ()
    implemented_by_row_id = {
        row.row_id: row for row in _implemented_front_half_rows(workflow, boundary_contracts)
    }
    for row in _implemented_s5_boundary_rows(workflow):
        implemented_by_row_id.setdefault(row.row_id, row)
    return tuple(implemented_by_row_id.values())


def _implemented_s5_boundary_rows(
    workflow: WorkflowDeclaration,
) -> tuple[_ImplementedFrontHalfRow, ...]:
    rows: list[_ImplementedFrontHalfRow] = []
    review_parallel_maps = _review_parallel_map_calls(workflow.source_block)
    review_fan_in = _visible_review_fan_in_call(review_parallel_maps)
    review_rework = _visible_review_rework_cycle_call(workflow.source_block)
    finalize_calls = _step_calls_for_exports(workflow.source_block, _MEGAPLAN_FINALIZE_EXPORTS)
    review_policy_surface = _megaplan_policy_route_surface(_MEGAPLAN_REVIEW_POLICY_EXPORT)
    finalize_policy_surface = _megaplan_policy_route_surface(_MEGAPLAN_FINALIZE_POLICY_EXPORT)
    review_topology_contract = _megaplan_review_topology_contract()

    if review_fan_in is not None:
        rows.append(
            _ImplementedFrontHalfRow(
                row_id=S5_REVIEW_CHILD_OUTPUTS_ROW_ID,
                phase="review",
                source_span=review_fan_in.source_span,
                component_ref=review_fan_in.mapper_ref,
            )
        )
        rows.append(
            _ImplementedFrontHalfRow(
                row_id=S5_REVIEW_REDUCER_PROMOTION_ROW_ID,
                phase="review",
                source_span=review_fan_in.source_span,
                component_ref=review_fan_in.reducer_ref,
            )
        )
    if review_rework is not None and isinstance(review_policy_surface.get("rework_cycle"), Mapping):
        rows.append(
            _ImplementedFrontHalfRow(
                row_id=S5_REVIEW_REWORK_EFFECTS_ROW_ID,
                phase="review",
                source_span=review_rework.source_span,
                component_ref=review_rework.reducer_ref,
            )
        )
    if (
        review_fan_in is not None
        and isinstance(review_policy_surface.get("cap_thresholds"), Mapping)
        and isinstance(review_policy_surface.get("blocked_and_advisory_outcomes"), Mapping)
        and isinstance(review_policy_surface.get("force_proceed_authority"), Mapping)
        and not _review_topology_contract_owns_cap_thresholds(review_topology_contract)
    ):
        rows.append(
            _ImplementedFrontHalfRow(
                row_id=S5_REVIEW_CAP_AUTHORITY_ROW_ID,
                phase="review",
                source_span=review_fan_in.source_span,
                component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_REVIEW_POLICY_EXPORT}",
            )
        )
    if review_fan_in is not None and isinstance(review_policy_surface.get("human_verification"), Mapping):
        rows.append(
            _ImplementedFrontHalfRow(
                row_id=S5_REVIEW_HUMAN_VERIFICATION_ROW_ID,
                phase="review",
                source_span=review_fan_in.source_span,
                component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_REVIEW_POLICY_EXPORT}",
            )
        )
    if finalize_calls:
        finalize_source_span = finalize_calls[0].source_span
        if isinstance(finalize_policy_surface.get("canonical_artifacts"), Mapping):
            rows.append(
                _ImplementedFrontHalfRow(
                    row_id=S5_FINALIZE_ARTIFACTS_ROW_ID,
                    phase="finalize",
                    source_span=finalize_source_span,
                    component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_FINALIZE_POLICY_EXPORT}",
                )
            )
        if isinstance(finalize_policy_surface.get("fallback_routes"), Mapping):
            rows.append(
                _ImplementedFrontHalfRow(
                    row_id=S5_FINALIZE_FALLBACK_ROW_ID,
                    phase="finalize",
                    source_span=finalize_source_span,
                    component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_FINALIZE_POLICY_EXPORT}",
                )
            )
        if isinstance(finalize_policy_surface.get("final_projection_routes"), Mapping):
            rows.append(
                _ImplementedFrontHalfRow(
                    row_id=S5_FINAL_PROJECTION_ROW_ID,
                    phase="finalize",
                    source_span=finalize_source_span,
                    component_ref=f"{_MEGAPLAN_COMPONENT_MODULE}:{_MEGAPLAN_FINALIZE_POLICY_EXPORT}",
                )
            )
    return tuple(rows)


def lower_workflow_file(
    source_path: str | Path,
    *,
    resolver: ComponentResolver | None = None,
) -> Pipeline:
    path = Path(source_path)
    return lower_workflow_source(path.read_text(encoding="utf-8"), source_path=path, resolver=resolver)


def lower_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> Pipeline:
    lowered = _lower_workflow_source_result(source, source_path=source_path, resolver=resolver)
    if lowered.diagnostics or lowered.pipeline is None:
        raise SourceCompileError(lowered.diagnostics)
    return lowered.pipeline


def _lower_workflow_source_result(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> LowerWorkflowSourceResult:
    parsed_source = parse_workflow_source(source, source_path=source_path, resolver=resolver)
    pipeline: Pipeline | None = None
    diagnostics = list(parsed_source.diagnostics)
    if not diagnostics:
        pipeline, lower_diagnostics = _lower_parsed_source(parsed_source)
        diagnostics.extend(lower_diagnostics)
        if lower_diagnostics:
            pipeline = None
    if diagnostics != list(parsed_source.diagnostics):
        parsed_source = replace(parsed_source, diagnostics=tuple(diagnostics))
    return LowerWorkflowSourceResult(parsed_source=parsed_source, pipeline=pipeline)


def compile_workflow_file(
    source_path: str | Path,
    *,
    resolver: ComponentResolver | None = None,
) -> WorkflowManifest:
    path = Path(source_path)
    return compile_workflow_source(path.read_text(encoding="utf-8"), source_path=path, resolver=resolver)


def compile_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> WorkflowManifest:
    lowered = _lower_workflow_source_result(source, source_path=source_path, resolver=resolver)
    if lowered.diagnostics or lowered.pipeline is None:
        raise SourceCompileError(lowered.diagnostics)
    return compile_pipeline(lowered.pipeline)


def parse_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> ParsedWorkflowSource:
    path = _coerce_source_path(source_path)
    resolver = StaticComponentResolver() if resolver is None else resolver
    try:
        module = ast.parse(source, filename=path)
    except SyntaxError as exc:
        module = ast.Module(body=[], type_ignores=[])
        diagnostic = _diagnostic(
            DiagnosticCode.UNSUPPORTED_SYNTAX,
            "source is not valid Python syntax",
            source_span=SourceSpan(
                path=path,
                start_line=exc.lineno or 1,
                start_column=exc.offset or 1,
                end_line=exc.end_lineno or exc.lineno or 1,
                end_column=exc.end_offset or exc.offset or 1,
            ),
        )
        return ParsedWorkflowSource(
            source=source,
            source_path=path,
            module=module,
            scope=SourceScope(),
            workflow=None,
            diagnostics=(diagnostic,),
        )

    diagnostics: list[AuthoringDiagnostic] = []
    imports = _parse_imports(module, path, resolver, diagnostics)
    imports = _parse_local_native_components(module, path, imports, diagnostics)
    workflow = _parse_workflow_declaration(module, path, imports, diagnostics)
    local_outputs = {
        output.name: output.source_span
        for step in (() if workflow is None else workflow.steps)
        for output in step.outputs
    }
    scope = SourceScope(
        imports=imports,
        parameters=() if workflow is None else workflow.parameters,
        locals=local_outputs,
    )
    return ParsedWorkflowSource(
        source=source,
        source_path=path,
        module=module,
        scope=scope,
        workflow=workflow,
        diagnostics=tuple(diagnostics),
    )


def _parse_imports(
    module: ast.Module,
    source_path: str,
    resolver: ComponentResolver,
    diagnostics: list[AuthoringDiagnostic],
) -> dict[str, ImportBinding]:
    imports: dict[str, ImportBinding] = {}
    for statement in module.body:
        if isinstance(statement, ast.ImportFrom):
            if statement.module == "__future__":
                invalid_future_imports = [
                    alias.name for alias in statement.names if alias.name not in ALLOWED_FUTURE_IMPORTS
                ]
                if invalid_future_imports:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.INVALID_IMPORT_SOURCE,
                            "only future annotations imports are allowed in workflow source",
                            source_span=source_span_for_node(source_path, statement),
                        )
                    )
                continue
            if any(alias.name == "*" for alias in statement.names):
                module_name = _absolute_module_name(statement, source_path)
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.INVALID_IMPORT_SOURCE,
                        "star imports erase stable component provenance",
                        source_span=source_span_for_node(source_path, statement),
                        import_ref=_try_import_ref(module_name, "*"),
                    )
                )
                continue
            module_name = _absolute_module_name(statement, source_path)
            for alias in statement.names:
                local_name = alias.asname or alias.name
                import_ref = ImportRef(module=module_name, qualname=alias.name)
                if local_name in imports:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                            "imported workflow source name is rebound",
                            source_span=source_span_for_node(source_path, statement),
                            component_ref=imports[local_name].component_ref,
                        )
                    )
                    continue
                if module_name == AUTHORING_INTRINSIC_MODULE:
                    if alias.name not in RESERVED_AUTHORING_INTRINSICS:
                        diagnostics.append(
                            _diagnostic(
                                DiagnosticCode.INVALID_IMPORT_SOURCE,
                                "authoring imports may only name reserved compiler intrinsics",
                                source_span=source_span_for_node(source_path, statement),
                                import_ref=import_ref,
                            )
                        )
                        continue
                    if alias.asname is not None and alias.asname != alias.name:
                        diagnostics.append(
                            _diagnostic(
                                DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                                "reserved compiler intrinsic is rebound in workflow source",
                                source_span=source_span_for_node(source_path, statement),
                                component_ref=import_ref.spec,
                            )
                        )
                        continue
                    imports[local_name] = ImportBinding(
                        local_name=local_name,
                        import_ref=import_ref,
                        kind="intrinsic",
                        source_span=source_span_for_node(source_path, statement),
                    )
                    continue
                if module_name == "arnold.pipeline" and alias.name in {"step", "workflow", "parallel_map"}:
                    if alias.asname is not None and alias.asname != alias.name:
                        diagnostics.append(
                            _diagnostic(
                                DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                                "native authoring decorators cannot be aliased in workflow source",
                                source_span=source_span_for_node(source_path, statement),
                                component_ref=import_ref.spec,
                            )
                        )
                        continue
                    imports[local_name] = ImportBinding(
                        local_name=local_name,
                        import_ref=import_ref,
                        kind="intrinsic",
                        source_span=source_span_for_node(source_path, statement),
                    )
                    continue
                outcome_type = _resolve_outcome_import(module_name, alias.name)
                if outcome_type is not None:
                    if alias.asname is not None and alias.asname != alias.name:
                        diagnostics.append(
                            _diagnostic(
                                DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                                "outcome enum imports cannot be aliased in workflow source",
                                source_span=source_span_for_node(source_path, statement),
                                import_ref=import_ref,
                            )
                        )
                        continue
                    imports[local_name] = ImportBinding(
                        local_name=local_name,
                        import_ref=import_ref,
                        kind="outcome",
                        source_span=source_span_for_node(source_path, statement),
                        outcome_type=outcome_type,
                    )
                    continue
                if local_name in RESERVED_AUTHORING_INTRINSICS:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                            "component import shadows a reserved compiler intrinsic",
                            source_span=source_span_for_node(source_path, statement),
                            component_ref=import_ref.spec,
                        )
                    )
                    continue
                component = resolver.resolve(import_ref)
                if component is None:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.UNKNOWN_COMPONENT,
                            "imported component cannot be found in static resolver metadata",
                            source_span=source_span_for_node(source_path, statement),
                            import_ref=import_ref,
                        )
                    )
                    continue
                if alias.asname is not None and component.provenance.qualname != local_name:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.ALIAS_PROVENANCE_LOSS,
                            "aliased component import is missing original module:qualname provenance",
                            source_span=source_span_for_node(source_path, statement),
                            import_ref=import_ref,
                        )
                    )
                imports[local_name] = ImportBinding(
                    local_name=local_name,
                    import_ref=import_ref,
                    kind=component.kind.value,
                    source_span=source_span_for_node(source_path, statement),
                    component=component,
                )
        elif isinstance(statement, ast.Import):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.INVALID_IMPORT_SOURCE,
                    "root package imports are not valid workflow dependencies",
                    source_span=source_span_for_node(source_path, statement),
                    import_ref=_try_import_ref(statement.names[0].name, "__root__"),
                )
            )
        elif _contains_dynamic_import(statement):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "dynamic imports are not part of the static authoring grammar",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
    return imports


def _parse_local_native_components(
    module: ast.Module,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> dict[str, ImportBinding]:
    local_imports = dict(imports)
    for statement in module.body:
        if not isinstance(statement, ast.FunctionDef):
            continue
        step_decorator = _native_decorator_call(statement, imports, "step")
        workflow_decorator = _native_decorator_call(statement, imports, "workflow")
        if step_decorator is not None and workflow_decorator is not None:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.WRONG_COMPONENT_KIND,
                    "a local function cannot be both a step and workflow component",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
            continue
        if step_decorator is not None:
            component = _local_native_step_component(statement, step_decorator, source_path)
        elif workflow_decorator is not None:
            component = _local_native_workflow_component(statement, workflow_decorator, source_path)
        else:
            if not any(
                _is_workflow_call(decorator, imports)
                for decorator in statement.decorator_list
            ) and _contains_component_wrapper(statement, imports):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.SINGLE_HANDLER_WRAPPER,
                        "single-handler wrapper functions hide workflow topology",
                        source_span=source_span_for_node(source_path, statement),
                    )
                )
            continue
        local_imports[statement.name] = ImportBinding(
            local_name=statement.name,
            import_ref=ImportRef(module=_source_module_for_local_component(source_path), qualname=statement.name),
            kind=component.kind.value,
            source_span=source_span_for_node(source_path, statement),
            component=component,
        )
    return local_imports


def _contains_component_wrapper(
    function: ast.FunctionDef,
    imports: Mapping[str, ImportBinding],
) -> bool:
    for child in ast.walk(function):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Name):
            continue
        binding = imports.get(child.func.id)
        if binding is not None and binding.component is not None and binding.component.kind in {
            ComponentKind.STEP,
            ComponentKind.SUBFLOW,
            ComponentKind.WORKFLOW,
        }:
            return True
    return False


def _native_decorator_call(
    function: ast.FunctionDef,
    imports: Mapping[str, ImportBinding],
    name: str,
) -> ast.Call | None:
    for decorator in function.decorator_list:
        if isinstance(decorator, ast.Call):
            call = decorator
        elif isinstance(decorator, ast.Name):
            call = ast.Call(func=decorator, args=[], keywords=[])
        else:
            continue
        if not isinstance(call.func, ast.Name) or call.func.id not in imports:
            continue
        binding = imports[call.func.id]
        if (
            binding.import_ref.module == "arnold.pipeline"
            and binding.import_ref.qualname == name
            and binding.local_name == name
        ):
            return call
    return None


def _local_native_step_component(
    function: ast.FunctionDef,
    decorator: ast.Call,
    source_path: str,
) -> StepComponent:
    step_id = _string_keyword(decorator, "id") or function.name
    inputs = _literal_string_set_keyword(decorator, "inputs")
    outputs = _literal_string_set_keyword(decorator, "outputs")
    return StepComponent(
        id=step_id,
        provenance=ComponentProvenance(
            module=_source_module_for_local_component(source_path),
            qualname=function.name,
            export_name=function.name,
        ),
        metadata={
            "input_names": inputs,
            "output_names": outputs,
        },
    )


def _local_native_workflow_component(
    function: ast.FunctionDef,
    decorator: ast.Call,
    source_path: str,
) -> ComponentContract:
    workflow_id = _string_keyword(decorator, "id") or function.name
    inputs = _literal_string_set_keyword(decorator, "inputs")
    outputs = _literal_string_set_keyword(decorator, "outputs")
    return ComponentContract(
        id=workflow_id,
        kind=ComponentKind.WORKFLOW,
        provenance=ComponentProvenance(
            module=_source_module_for_local_component(source_path),
            qualname=function.name,
            export_name=function.name,
        ),
        metadata={
            "workflow_id": workflow_id,
            "input_names": inputs,
            "output_names": outputs,
        },
    )


def _literal_string_set_keyword(call: ast.Call, name: str) -> tuple[str, ...]:
    keyword = _keyword(call, name)
    if keyword is None:
        return ()
    value = keyword.value
    if not isinstance(value, (ast.Set, ast.List, ast.Tuple)):
        return ()
    items: list[str] = []
    for element in value.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            items.append(element.value)
    return tuple(items)


def _source_module_for_local_component(source_path: str) -> str:
    return Path(source_path).with_suffix("").as_posix().replace("/", ".").replace("-", "_")


def _parse_workflow_declaration(
    module: ast.Module,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowDeclaration | None:
    declarations: list[ast.Call | ast.FunctionDef | ast.AsyncFunctionDef] = []
    for statement in module.body:
        if isinstance(statement, ast.Expr) and _is_workflow_call(statement.value, imports):
            declarations.append(statement.value)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            _is_workflow_call(decorator, imports) for decorator in statement.decorator_list
        ):
            declarations.append(statement)
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in RESERVED_AUTHORING_INTRINSICS:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                            "reserved compiler intrinsic is rebound in workflow source",
                            source_span=source_span_for_node(source_path, statement),
                            component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{target.id}",
                        )
                    )
        elif _contains_manual_graph_authoring(statement):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.MANUAL_GRAPH_NODES,
                    "manual graph node authoring is rejected by the V2 source contract",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
        elif _contains_native_program_projection(statement):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.NATIVE_PROGRAM_PROJECTION,
                    "native program projection is not an authoring source form",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
        elif _contains_megaplan_only_helper(statement):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.MEGAPLAN_ONLY_HELPERS,
                    "Megaplan-only helper fanout must be expressed with general workflow constructs",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
        elif _contains_manual_path_construction(statement):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.MANUAL_PATH_STRINGS,
                    "manual call-site path construction is rejected by the V2 source contract",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
    if not declarations:
        fallback_span = (
            source_span_for_node(source_path, module.body[0])
            if module.body
            else SourceSpan(path=source_path, start_line=1, end_line=1, end_column=1)
        )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_WORKFLOW_DECLARATION,
                "module does not declare a workflow(...) source form",
                source_span=fallback_span,
            )
        )
        return None
    if len(declarations) > 1:
        native_declarations = [
            declaration
            for declaration in declarations
            if isinstance(declaration, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                _is_native_workflow_call(decorator, imports)
                for decorator in declaration.decorator_list
            )
        ]
        if len(native_declarations) == len(declarations):
            declaration = native_declarations[-1]
            return _parse_function_workflow(declaration, source_path, imports, diagnostics)
        first = declarations[1]
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MULTIPLE_WORKFLOW_DECLARATIONS,
                "module declares more than one workflow(...) source form",
                source_span=source_span_for_node(source_path, first),
            )
        )
        return None
    declaration = declarations[0]
    if isinstance(declaration, ast.Call):
        return _parse_direct_workflow(declaration, source_path, imports, diagnostics)
    return _parse_function_workflow(declaration, source_path, imports, diagnostics)


def _parse_direct_workflow(
    call: ast.Call,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowDeclaration | None:
    workflow_id = _string_keyword(call, "id")
    steps_keyword = _keyword(call, "steps")
    if workflow_id is None or steps_keyword is None or not isinstance(steps_keyword.value, ast.List):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow(...) declarations must include literal id and steps list",
                source_span=source_span_for_node(source_path, call),
            )
        )
        return None
    policies = _parse_workflow_policy_keywords(call, source_path, imports, diagnostics)
    if policies is None:
        return None
    statements = tuple(
        _parse_direct_workflow_step(element, source_path, imports, diagnostics)
        for element in steps_keyword.value.elts
    )
    statements = tuple(statement for statement in statements if statement is not None)
    return WorkflowDeclaration(
        source_form="direct",
        id=workflow_id,
        version=_string_keyword(call, "version") or "1.0",
        source_span=source_span_for_node(source_path, call),
        source_block=ParsedSourceBlock(statements),
        policies=policies,
    )


def _parse_direct_workflow_step(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> ParsedStepCall | ParsedSubflowCall | None:
    return _parse_component_call(node, source_path, imports, diagnostics)


def _parse_function_workflow(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowDeclaration | None:
    if isinstance(function, ast.AsyncFunctionDef):
        decorator = next(
            decorator for decorator in function.decorator_list if _is_workflow_call(decorator, imports)
        )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "async workflow functions are outside the V1 authoring grammar",
                source_span=source_span_for_node(source_path, function),
            )
        )
        workflow_id = _string_keyword(decorator, "id") or function.name
        return WorkflowDeclaration(
            source_form="function",
            id=workflow_id,
            version=_string_keyword(decorator, "version") or "1.0",
            source_span=source_span_for_node(source_path, function),
            function_name=function.name,
            parameters=_function_parameter_names(function),
            steps=(),
        )
    decorator = next(decorator for decorator in function.decorator_list if _is_workflow_call(decorator, imports))
    preexisting_wrapper_diagnostic = any(
        diagnostic.code is DiagnosticCode.SINGLE_HANDLER_WRAPPER
        for diagnostic in diagnostics
    )
    header_ok = _validate_workflow_decorator(decorator, source_path, diagnostics)
    policies = _parse_workflow_policy_keywords(decorator, source_path, imports, diagnostics)
    header_ok = policies is not None and header_ok
    header_ok = _validate_function_signature(function, source_path, diagnostics) and header_ok
    header_ok = _validate_v2_function_body_boundaries(function, source_path, diagnostics) and header_ok
    workflow_id = _string_keyword(decorator, "id")
    if workflow_id is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow decorators must include a literal id",
                source_span=source_span_for_node(source_path, function),
            )
        )
        workflow_id = function.name
        header_ok = False
    if preexisting_wrapper_diagnostic:
        header_ok = False
    version = _string_keyword(decorator, "version") or "1.0"
    parameters = _function_parameter_names(function)
    initial_scope_ok = _validate_initial_function_scope(parameters, imports, source_path, function, diagnostics)
    source_block, local_outputs = (
        _parse_function_body_block(function, source_path, imports, parameters, diagnostics)
        if header_ok and initial_scope_ok
        else (ParsedSourceBlock(), {})
    )
    source_block = _with_nested_workflow_parent_path(source_block, workflow_id)
    return WorkflowDeclaration(
        source_form="function",
        id=workflow_id,
        version=version,
        source_span=source_span_for_node(source_path, function),
        function_name=function.name,
        parameters=parameters,
        source_block=source_block,
        policies=() if policies is None else policies,
    )


def _with_nested_workflow_parent_path(
    block: ParsedSourceBlock,
    parent_path: str,
) -> ParsedSourceBlock:
    statements: list[ParsedSourceStatement] = []
    for statement in block.statements:
        if isinstance(statement, ParsedNestedWorkflowCall):
            statements.append(
                replace(
                    statement,
                    parent_path=parent_path,
                    call_site_path=f"{parent_path}/{statement.id}",
                )
            )
        elif isinstance(statement, ParsedBranchBlock):
            statements.append(
                replace(
                    statement,
                    arms=tuple(
                        replace(
                            arm,
                            body=_with_nested_workflow_parent_path(arm.body, parent_path),
                        )
                        for arm in statement.arms
                    ),
                )
            )
        elif isinstance(statement, ParsedLoopBlock):
            statements.append(
                replace(
                    statement,
                    body=_with_nested_workflow_parent_path(statement.body, parent_path),
                )
            )
        else:
            statements.append(statement)
    return ParsedSourceBlock(tuple(statements))


def _validate_workflow_decorator(
    decorator: ast.AST,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    if not isinstance(decorator, ast.Call):
        return False
    valid = True
    if decorator.args or any(keyword.arg is None for keyword in decorator.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow decorators must use literal keyword arguments only",
                source_span=source_span_for_node(source_path, decorator),
            )
        )
        valid = False
    allowed_keywords = {"id", "version", "policy", "policies", "inputs", "outputs"}
    for keyword in decorator.keywords:
        if keyword.arg not in allowed_keywords:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "workflow decorator keyword is outside the V1 authoring grammar",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            valid = False
            continue
        if keyword.arg in {"policy", "policies"}:
            continue
        if keyword.arg in {"inputs", "outputs"}:
            if not _is_literal_string_collection(keyword.value):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.UNSUPPORTED_SYNTAX,
                        "workflow input and output schemas must be literal string collections",
                        source_span=source_span_for_node(source_path, keyword.value),
                    )
                )
                valid = False
            continue
        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "workflow decorator metadata must be literal strings",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            valid = False
    return valid


def _is_literal_string_collection(node: ast.AST) -> bool:
    return isinstance(node, (ast.Set, ast.List, ast.Tuple)) and all(
        isinstance(element, ast.Constant) and isinstance(element.value, str)
        for element in node.elts
    )


def _validate_function_signature(
    function: ast.FunctionDef,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    args = function.args
    valid = True
    if (
        args.posonlyargs
        or args.vararg is not None
        or args.kwonlyargs
        or args.kwarg is not None
        or args.defaults
        or any(default is not None for default in args.kw_defaults)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow functions may only declare ordered positional parameters",
                source_span=source_span_for_node(source_path, function),
            )
        )
        valid = False
    return valid


def _validate_initial_function_scope(
    parameters: Sequence[str],
    imports: Mapping[str, ImportBinding],
    source_path: str,
    function: ast.FunctionDef,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    valid = True
    import_names = set(imports)
    for parameter in parameters:
        if parameter in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "workflow parameter shadows a reserved compiler intrinsic",
                    source_span=_parameter_span(source_path, function, parameter),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{parameter}",
                )
            )
            valid = False
        elif parameter in import_names:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "workflow parameter shadows an imported source name",
                    source_span=_parameter_span(source_path, function, parameter),
                    component_ref=imports[parameter].component_ref,
                )
            )
            valid = False
    return valid


def _validate_v2_function_body_boundaries(
    function: ast.FunctionDef,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    checks = (
        (
            _contains_megaplan_only_helper,
            DiagnosticCode.MEGAPLAN_ONLY_HELPERS,
            "Megaplan-only helper fanout must be expressed with general workflow constructs",
        ),
        (
            _contains_manual_path_construction,
            DiagnosticCode.MANUAL_PATH_STRINGS,
            "manual call-site path construction is rejected by the V2 source contract",
        ),
    )
    valid = True
    for statement in function.body:
        for predicate, code, message in checks:
            if predicate(statement):
                diagnostics.append(
                    _diagnostic(
                        code,
                        message,
                        source_span=source_span_for_node(source_path, statement),
                    )
                )
                valid = False
                break
    return valid


def _function_parameter_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    return tuple(argument.arg for argument in (*function.args.posonlyargs, *function.args.args))


def _parameter_span(source_path: str, function: ast.FunctionDef, parameter: str) -> SourceSpan:
    for argument in (*function.args.posonlyargs, *function.args.args):
        if argument.arg == parameter:
            return source_span_for_node(source_path, argument)
    return source_span_for_node(source_path, function)


def _parse_function_body_block(
    function: ast.FunctionDef,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[ParsedSourceBlock, Mapping[str, SourceSpan]]:
    return _parse_statement_block(
        function.body,
        source_path,
        imports,
        parameters,
        diagnostics,
        initial_local_outputs={},
        return_is_terminal=False,
    )[:2]


def _parse_statement_block(
    body: Sequence[ast.stmt],
    source_path: str,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    diagnostics: list[AuthoringDiagnostic],
    *,
    initial_local_outputs: Mapping[str, SourceSpan],
    return_is_terminal: bool,
    allow_output_rebinding: bool = False,
    allow_terminal_fallthrough: bool = False,
) -> tuple[ParsedSourceBlock, Mapping[str, SourceSpan], bool]:
    statements: list[ParsedSourceStatement] = []
    local_outputs: dict[str, SourceSpan] = dict(initial_local_outputs)
    terminal = False
    pending_loop_policy: ParsedLoopPolicy | None = None
    pending_invalid_loop_policy = False
    for statement in body:
        if terminal:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNREACHABLE_CONTROL_PATH,
                    "statement is unreachable because every branch exits control flow",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
            continue
        if pending_loop_policy is not None and not isinstance(statement, ast.While):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.AMBIGUOUS_LOOP,
                    "loop policy must be immediately followed by while True",
                    source_span=pending_loop_policy.source_span,
                    details={"policy_ref": pending_loop_policy.policy_ref},
                )
            )
            pending_loop_policy = None
        if pending_invalid_loop_policy and not isinstance(statement, ast.While):
            pending_invalid_loop_policy = False
        if isinstance(statement, ast.Assign):
            targets = _assignment_output_bindings(statement, source_path, diagnostics)
            duplicate_outputs = [
                output for output in targets if output.name in local_outputs
            ]
            if duplicate_outputs and not allow_output_rebinding:
                for output in duplicate_outputs:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.UNSUPPORTED_MUTATION,
                            f"control variable {output.name!r} cannot be rebound before routing",
                            source_span=source_span_for_node(source_path, statement),
                            details={"name": output.name},
                        )
                    )
                continue
            if _is_reserved_intrinsic_call(statement.value, imports):
                statements.append(
                    ParsedUnsupportedStatement(
                        reason="assigned_intrinsic_call",
                        source_span=source_span_for_node(source_path, statement.value),
                        node=statement,
                    )
                )
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.UNSUPPORTED_SYNTAX,
                        "compiler intrinsic calls must be bare workflow statements",
                        source_span=source_span_for_node(source_path, statement.value),
                    )
                )
                continue
            fanout = _parse_parallel_map_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
                output_bindings=targets,
            )
            if fanout is not None:
                statements.append(fanout)
                for output in targets:
                    local_outputs[output.name] = output.source_span
                continue
            step = _parse_component_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
                output_bindings=targets,
            )
            if step is not None:
                statements.append(step)
                for output in targets:
                    local_outputs[output.name] = output.source_span
            continue
        elif isinstance(statement, ast.Expr):
            if _is_loop_policy_marker_call(statement.value, imports):
                loop_policy = _parse_loop_policy_marker(
                    statement.value,
                    source_path,
                    imports,
                    diagnostics,
                )
                pending_loop_policy = loop_policy
                pending_invalid_loop_policy = loop_policy is None
                continue
            intrinsic = _parse_intrinsic_call(statement.value, source_path, imports, diagnostics)
            if intrinsic is not None:
                statements.append(intrinsic)
                if return_is_terminal and intrinsic.name == "halt":
                    terminal = True
                continue
            fanout = _parse_parallel_map_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
            )
            if fanout is not None:
                statements.append(fanout)
                continue
            step = _parse_component_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
            )
            if step is not None:
                statements.append(step)
            continue
        elif isinstance(statement, ast.Return) and _is_none_return_value(statement.value):
            if return_is_terminal:
                terminal = True
            continue
        elif isinstance(statement, ast.Return) and isinstance(statement.value, ast.Call):
            step = _parse_component_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
            )
            if step is not None:
                statements.append(step)
            if return_is_terminal:
                terminal = True
            continue
        elif isinstance(statement, ast.Return) and isinstance(statement.value, ast.Name):
            if return_is_terminal:
                terminal = True
            continue
        elif isinstance(statement, ast.Break):
            if return_is_terminal:
                terminal = True
                continue
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNDECLARED_LOOP_EXIT,
                    "break is only valid as an accepted loop exit inside a bounded loop body",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
            continue
        elif isinstance(statement, ast.If):
            branch, merged_outputs, branch_terminal = _parse_branch_block(
                statement,
                source_path,
                imports,
                parameters,
                local_outputs,
                diagnostics,
                allow_output_rebinding=allow_output_rebinding,
                allow_terminal_fallthrough=allow_terminal_fallthrough,
            )
            if branch is not None:
                statements.append(branch)
                local_outputs.update(merged_outputs)
                terminal = branch_terminal
            continue
        elif isinstance(statement, ast.While):
            loop_block = _parse_while_loop_contract(
                statement,
                source_path,
                imports,
                parameters,
                local_outputs,
                pending_loop_policy,
                pending_invalid_loop_policy,
                diagnostics,
            )
            pending_loop_policy = None
            pending_invalid_loop_policy = False
            if loop_block is not None:
                statements.append(loop_block)
                local_outputs.update(
                    _source_block_output_spans(loop_block.body, local_outputs)
                )
            continue
        else:
            statements.append(
                ParsedUnsupportedStatement(
                    reason="outside_linear_subset",
                    source_span=source_span_for_node(source_path, statement),
                    node=statement,
                )
            )
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "branching is outside the V1 linear workflow subset",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
            continue
    if pending_loop_policy is not None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy must be immediately followed by while True",
                source_span=pending_loop_policy.source_span,
                details={"policy_ref": pending_loop_policy.policy_ref},
            )
        )
    return ParsedSourceBlock(_with_loop_follow_statements(statements)), local_outputs, terminal


def _with_loop_follow_statements(
    statements: Sequence[ParsedSourceStatement],
) -> tuple[ParsedSourceStatement, ...]:
    linked: list[ParsedSourceStatement] = []
    for index, statement in enumerate(statements):
        if isinstance(statement, ParsedLoopBlock):
            follow_statement = statements[index + 1] if index + 1 < len(statements) else None
            linked.append(replace(statement, follow_statement=follow_statement))
        else:
            linked.append(statement)
    return tuple(linked)


def _parse_branch_block(
    statement: ast.If,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    local_outputs: Mapping[str, SourceSpan],
    diagnostics: list[AuthoringDiagnostic],
    *,
    allow_output_rebinding: bool = False,
    allow_terminal_fallthrough: bool = False,
) -> tuple[ParsedBranchBlock | None, Mapping[str, SourceSpan], bool]:
    initial_diagnostic_count = len(diagnostics)
    raw_arms = _branch_arms(statement)
    control_name: str | None = None
    seen_literals: set[str] = set()
    parsed_arms: list[ParsedBranchArm] = []
    nonterminal_new_outputs: list[set[str]] = []
    arm_output_maps: list[Mapping[str, SourceSpan]] = []
    branch_valid = True
    has_else = False

    for test, arm_body, arm_node in raw_arms:
        condition: ParsedBranchCondition | None = None
        if test is None:
            has_else = True
        else:
            condition = _parse_branch_condition(
                test,
                source_path,
                imports,
                local_outputs,
                diagnostics,
            )
            if condition is None:
                branch_valid = False
            else:
                if control_name is None:
                    control_name = condition.decision_output
                elif control_name != condition.decision_output:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.DYNAMIC_ROUTING_CONDITION,
                            "branch route comparisons must use one decision output",
                            source_span=condition.source_span,
                            details={
                                "expected": control_name,
                                "actual": condition.decision_output,
                            },
                        )
                    )
                    branch_valid = False
                if condition.literal in seen_literals:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.DYNAMIC_ROUTING_CONDITION,
                            "branch route comparisons must not repeat literal targets",
                            source_span=condition.source_span,
                            details={"literal": condition.literal},
                        )
                    )
                    branch_valid = False
                seen_literals.add(condition.literal)

        body_block, body_outputs, body_terminal = _parse_statement_block(
            arm_body,
            source_path,
            imports,
            parameters,
            diagnostics,
            initial_local_outputs=local_outputs,
            return_is_terminal=True,
            allow_output_rebinding=allow_output_rebinding,
            allow_terminal_fallthrough=allow_terminal_fallthrough,
        )
        parsed_arms.append(
            ParsedBranchArm(
                condition=condition,
                body=body_block,
                source_span=source_span_for_node(source_path, arm_node),
                terminal=body_terminal,
            )
        )
        arm_output_maps.append(body_outputs)
        if not body_terminal:
            nonterminal_new_outputs.append(set(body_outputs) - set(local_outputs))

    if control_name is None:
        branch_valid = False
    if (
        not has_else
        and branch_valid
        and not (allow_terminal_fallthrough and any(arm.terminal for arm in parsed_arms))
        and initial_diagnostic_count == 0
        and len(diagnostics) == initial_diagnostic_count
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_FALLTHROUGH_ROUTE,
                "branch routes require an else arm to avoid implicit fallthrough",
                source_span=source_span_for_node(source_path, statement),
            )
        )
        branch_valid = False
    elif not has_else:
        nonterminal_new_outputs.append(set())

    merged_outputs: dict[str, SourceSpan] = {}
    if nonterminal_new_outputs:
        common_outputs = set.intersection(*nonterminal_new_outputs)
        for name in common_outputs:
            for arm, arm_outputs in zip(parsed_arms, arm_output_maps):
                if not arm.terminal and name in arm_outputs:
                    merged_outputs[name] = arm_outputs[name]
                    break

    if not branch_valid:
        return None, {}, False

    return (
        ParsedBranchBlock(
            decision_output=control_name,
            arms=tuple(parsed_arms),
            source_span=source_span_for_node(source_path, statement),
            merged_outputs=merged_outputs,
        ),
        merged_outputs,
        has_else and all(arm.terminal for arm in parsed_arms),
    )


def _parse_loop_policy_marker(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> ParsedLoopPolicy | None:
    if not _is_reserved_intrinsic_call(node, imports):
        return None
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name)
    if node.func.id != "loop":
        return None
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy must use explicit keyword arguments",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    allowed_keywords = set(RESERVED_INTRINSIC_CALL_KEYWORDS["loop"])
    keyword_names = {keyword.arg for keyword in node.keywords}
    if keyword_names != allowed_keywords:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy syntax is loop(policy=<imported loop policy>, reentry_id=<literal>)",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None

    policy_keyword = _keyword(node, "policy")
    reentry_keyword = _keyword(node, "reentry_id")
    if policy_keyword is None or reentry_keyword is None:
        return None
    if (
        not isinstance(reentry_keyword.value, ast.Constant)
        or not isinstance(reentry_keyword.value.value, str)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop reentry_id must be a literal string",
                source_span=source_span_for_node(source_path, reentry_keyword.value),
            )
        )
        return None
    if not isinstance(policy_keyword.value, ast.Name):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy must reference an imported literal PolicyComponent",
                source_span=source_span_for_node(source_path, policy_keyword.value),
            )
        )
        return None

    binding = imports.get(policy_keyword.value.id)
    if (
        binding is None
        or binding.component is None
        or binding.component.kind is not ComponentKind.POLICY
        or not isinstance(binding.component, PolicyComponent)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy must reference an imported PolicyComponent",
                source_span=source_span_for_node(source_path, policy_keyword.value),
                component_ref=None if binding is None else binding.component_ref,
            )
        )
        return None
    policy = binding.component
    if policy.policy_type != "loop":
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy component must have policy_type='loop'",
                source_span=source_span_for_node(source_path, policy_keyword.value),
                component_ref=binding.component_ref,
                details={"policy_type": policy.policy_type},
            )
        )
        return None
    max_iterations = policy.config.get("max_iterations")
    if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy requires a positive literal max_iterations bound",
                source_span=source_span_for_node(source_path, policy_keyword.value),
                component_ref=binding.component_ref,
            )
        )
        return None
    until_ref = policy.config.get("until_ref")
    if until_ref is not None and not isinstance(until_ref, str):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "loop policy until_ref must be a literal string when provided",
                source_span=source_span_for_node(source_path, policy_keyword.value),
                component_ref=binding.component_ref,
            )
        )
        return None
    return ParsedLoopPolicy(
        policy_ref=binding.component_ref,
        max_iterations=max_iterations,
        reentry_id=reentry_keyword.value.value,
        until_ref=until_ref,
        source_span=source_span_for_node(source_path, node),
    )


def _is_loop_policy_marker_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    return (
        _is_reserved_intrinsic_call(node, imports)
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "loop"
    )


def _parse_while_loop_contract(
    statement: ast.While,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    local_outputs: Mapping[str, SourceSpan],
    pending_loop_policy: ParsedLoopPolicy | None,
    pending_invalid_loop_policy: bool,
    diagnostics: list[AuthoringDiagnostic],
) -> ParsedLoopBlock | None:
    if (
        not isinstance(statement.test, ast.Constant)
        or statement.test.value is not True
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "bounded loops must use while True with an adjacent literal loop policy",
                source_span=source_span_for_node(source_path, statement.test),
            )
        )
        return None
    if pending_invalid_loop_policy:
        return None
    if pending_loop_policy is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_LOOP,
                "while True loops require an adjacent literal loop policy",
                source_span=source_span_for_node(source_path, statement),
            )
        )
        return None
    if _diagnose_unsupported_loop_controls(statement.body, source_path, diagnostics):
        return None

    body_block, _, _ = _parse_statement_block(
        statement.body,
        source_path,
        imports,
        parameters,
        diagnostics,
        initial_local_outputs=local_outputs,
        return_is_terminal=True,
        allow_output_rebinding=True,
        allow_terminal_fallthrough=True,
    )
    entry_statement = body_block.statements[0] if body_block.statements else None
    return ParsedLoopBlock(
        policy=pending_loop_policy,
        body=body_block,
        source_span=source_span_for_node(source_path, statement),
        entry_statement=entry_statement,
        body_tail_statements=_source_block_tail_statements(body_block),
    )


def _diagnose_unsupported_loop_controls(
    body: Sequence[ast.stmt],
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    invalid = False
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.While):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.AMBIGUOUS_LOOP,
                        "nested while loops require a separate adjacent literal loop policy",
                        source_span=source_span_for_node(source_path, node),
                    )
                )
                invalid = True
            elif isinstance(node, ast.Continue):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.AMBIGUOUS_LOOP,
                        "bounded loop bodies do not support continue",
                        source_span=source_span_for_node(source_path, node),
                    )
                )
                invalid = True
            elif isinstance(node, ast.Return) and not _is_none_return_value(node.value):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.AMBIGUOUS_LOOP,
                        "bounded loop bodies only support return None as a terminal exit",
                        source_span=source_span_for_node(source_path, node.value),
                    )
                )
                invalid = True
    return invalid


def _is_none_return_value(node: ast.AST | None) -> bool:
    return node is None or (isinstance(node, ast.Constant) and node.value is None)


def _source_block_tail_statements(
    block: ParsedSourceBlock,
) -> tuple[ParsedSourceStatement, ...]:
    if not block.statements:
        return ()
    tail = block.statements[-1]
    if isinstance(tail, ParsedBranchBlock):
        tails: list[ParsedSourceStatement] = []
        for arm in tail.arms:
            if not arm.terminal:
                tails.extend(_source_block_tail_statements(arm.body))
        return tuple(tails)
    return (tail,)


def _source_block_output_spans(
    block: ParsedSourceBlock,
    initial_outputs: Mapping[str, SourceSpan],
) -> Mapping[str, SourceSpan]:
    outputs: dict[str, SourceSpan] = dict(initial_outputs)
    for statement in block.statements:
        if isinstance(statement, ParsedStepCall):
            for output in statement.outputs:
                outputs[output.name] = output.source_span
        elif isinstance(statement, ParsedNestedWorkflowCall):
            for output in statement.outputs:
                outputs[output.name] = output.source_span
        elif isinstance(statement, ParsedParallelMapCall):
            for output in statement.outputs:
                outputs[output.name] = output.source_span
        elif isinstance(statement, ParsedBranchBlock):
            outputs.update(statement.merged_outputs)
        elif isinstance(statement, ParsedLoopBlock):
            outputs.update(_source_block_output_spans(statement.body, outputs))
    return outputs


def _branch_arms(statement: ast.If) -> tuple[tuple[ast.AST | None, Sequence[ast.stmt], ast.stmt], ...]:
    arms: list[tuple[ast.AST | None, Sequence[ast.stmt], ast.stmt]] = []
    current: ast.If = statement
    while True:
        arms.append((current.test, current.body, current))
        if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            current = current.orelse[0]
            continue
        if current.orelse:
            arms.append((None, current.orelse, current.orelse[0]))
        break
    return tuple(arms)


def _parse_branch_condition(
    test: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    local_outputs: Mapping[str, SourceSpan],
    diagnostics: list[AuthoringDiagnostic],
) -> ParsedBranchCondition | None:
    if (
        not isinstance(test, ast.Compare)
        or not isinstance(test.left, ast.Name)
        or len(test.ops) != 1
        or not isinstance(test.ops[0], ast.Eq)
        or len(test.comparators) != 1
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.DYNAMIC_ROUTING_CONDITION,
                "branch route conditions must compare a decision output to a literal string",
                source_span=source_span_for_node(source_path, test),
            )
        )
        return None

    comparator = test.comparators[0]
    literal = _branch_comparator_literal(comparator, source_path, imports, diagnostics)
    if literal is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.DYNAMIC_ROUTING_CONDITION,
                "branch route comparisons must use a literal string target",
                source_span=source_span_for_node(source_path, test),
            )
        )
        return None
    if (
        isinstance(comparator, ast.Constant)
        and isinstance(comparator.value, str)
        and _is_megaplan_canonical_source(source_path)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.RAW_STRING_ROUTE_BRANCH,
                "canonical Megaplan route branches must use closed outcome enum members",
                source_span=source_span_for_node(source_path, comparator),
                details={"literal": comparator.value},
            )
        )
        return None

    decision_output = test.left.id
    if decision_output not in local_outputs:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.DYNAMIC_ROUTING_CONDITION,
                "branch route comparisons must use a prior decision output",
                source_span=source_span_for_node(source_path, test.left),
                details={"name": decision_output},
            )
        )
        return None

    return ParsedBranchCondition(
        decision_output=decision_output,
        literal=literal,
        source_span=source_span_for_node(source_path, test),
    )


def _resolve_outcome_import(module_name: str | None, qualname: str) -> type[StrEnum] | None:
    if module_name not in _ALLOWED_OUTCOME_MODULES:
        return None
    try:
        module = import_module(module_name)
    except Exception:
        return None
    value = getattr(module, qualname, None)
    if isinstance(value, type) and issubclass(value, StrEnum):
        return value
    return None


def _branch_comparator_literal(
    comparator: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> str | None:
    if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
        return comparator.value
    if not isinstance(comparator, ast.Attribute) or not isinstance(comparator.value, ast.Name):
        return None
    binding = imports.get(comparator.value.id)
    if binding is None or binding.kind != "outcome" or binding.outcome_type is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNKNOWN_OUTCOME_TYPE,
                "branch route comparison references an unknown outcome type",
                source_span=source_span_for_node(source_path, comparator.value),
                details={"name": comparator.value.id},
            )
        )
        return None
    try:
        member = binding.outcome_type[comparator.attr]
    except KeyError:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.INVALID_OUTCOME_MEMBER,
                "branch route comparison references an invalid outcome member",
                source_span=source_span_for_node(source_path, comparator),
                details={
                    "outcome_type": binding.import_ref.qualname,
                    "member": comparator.attr,
                },
            )
        )
        return None
    return str(member.value)


def _is_megaplan_canonical_source(source_path: str) -> bool:
    normalized = source_path.replace("\\", "/")
    return normalized.endswith("arnold_pipelines/megaplan/workflows/workflow.pypeline")


def _assignment_output_bindings(
    statement: ast.Assign,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepOutputBinding, ...]:
    if len(statement.targets) != 1:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow steps must assign outputs with a single assignment target",
                source_span=source_span_for_node(source_path, statement),
            )
        )
        return ()
    target = statement.targets[0]
    target_nodes: tuple[ast.AST, ...]
    if isinstance(target, ast.Name):
        target_nodes = (target,)
    elif isinstance(target, ast.Tuple) and target.elts and all(isinstance(element, ast.Name) for element in target.elts):
        target_nodes = tuple(target.elts)
    else:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow step outputs must be local names or tuples of local names",
                source_span=source_span_for_node(source_path, target),
            )
        )
        return ()

    seen: set[str] = set()
    outputs: list[StepOutputBinding] = []
    for node in target_nodes:
        assert isinstance(node, ast.Name)
        if node.id in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "workflow local output shadows a reserved compiler intrinsic",
                    source_span=source_span_for_node(source_path, node),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{node.id}",
                )
            )
            continue
        if node.id in seen:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "workflow local output names must be assigned exactly once",
                    source_span=source_span_for_node(source_path, node),
                )
            )
            continue
        seen.add(node.id)
        outputs.append(
            StepOutputBinding(
                name=node.id,
                source_span=source_span_for_node(source_path, node),
            )
        )
    return tuple(outputs)


def _parse_component_call(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    parameters: Sequence[str] = (),
    local_outputs: Mapping[str, SourceSpan] | None = None,
    output_bindings: Sequence[StepOutputBinding] = (),
) -> ParsedStepCall | ParsedSubflowCall | ParsedNestedWorkflowCall | None:
    if (
        isinstance(node, ast.Call)
        and not isinstance(node.func, ast.Name)
        and not isinstance(node.func, ast.Call)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.DYNAMIC_DISPATCH,
                "workflow components must be invoked by direct imported names",
                source_span=source_span_for_node(source_path, node.func),
            )
        )
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        binding = imports.get(node.func.id)
        if (
            binding is not None
            and binding.component is not None
            and binding.component.kind is ComponentKind.SUBFLOW
            and isinstance(binding.component, SubflowComponent)
        ):
            return _parse_subflow_call(
                node,
                binding,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
                output_bindings=output_bindings,
            )
        if (
            binding is not None
            and binding.component is not None
            and binding.component.kind is ComponentKind.WORKFLOW
        ):
            return _parse_nested_workflow_call(
                node,
                binding,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
                output_bindings=output_bindings,
            )
    return _parse_step_call(
        node,
        source_path,
        imports,
        diagnostics,
        parameters=parameters,
        local_outputs=local_outputs,
        output_bindings=output_bindings,
    )


def _parse_parallel_map_call(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    parameters: Sequence[str] = (),
    local_outputs: Mapping[str, SourceSpan] | None = None,
    output_bindings: Sequence[StepOutputBinding] = (),
) -> ParsedParallelMapCall | None:
    local_outputs = {} if local_outputs is None else local_outputs
    if not _is_native_parallel_map_call(node, imports):
        return None
    assert isinstance(node, ast.Call)
    valid = True
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.INVALID_WORKFLOW_INVOCATION,
                "parallel_map must use keyword-only V2 authoring arguments",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    id_keyword = _keyword(node, "id")
    fanout_id = _validated_string_ref_keyword(
        node,
        id_keyword,
        source_path,
        diagnostics,
        code=(
            DiagnosticCode.MISSING_CALL_SITE_ID
            if id_keyword is None
            else DiagnosticCode.NON_LITERAL_CALL_SITE_ID
        ),
        missing_message="parallel_map calls must include a literal id keyword",
        invalid_message="parallel_map call-site id must use the workflow ref alphabet",
    )
    valid = fanout_id is not None

    items_keyword = _keyword(node, "items")
    items_ref = _parallel_map_items_ref(items_keyword.value if items_keyword else None)
    if items_keyword is None or items_ref is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.INVALID_PARALLEL_MAP_ITEMS,
                "parallel_map items must reference a workflow parameter, local output, or literal collection ref",
                source_span=source_span_for_node(source_path, node if items_keyword is None else items_keyword.value),
            )
        )
        valid = False
    elif (
        items_ref not in set(parameters)
        and items_ref not in local_outputs
        and not is_ref(items_ref)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.INVALID_PARALLEL_MAP_ITEMS,
                "parallel_map items must be a statically declared collection reference",
                source_span=source_span_for_node(source_path, items_keyword.value),
                details={"items": items_ref},
            )
        )
        valid = False

    mapper_keyword = _keyword(node, "step")
    mapper_ref = _parallel_map_callable_ref(mapper_keyword.value if mapper_keyword else None, imports)
    if mapper_keyword is None or mapper_ref is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.PARALLEL_MAP_ITEM_SCHEMA_MISMATCH,
                "parallel_map step must reference an imported or local step/workflow component",
                source_span=source_span_for_node(source_path, node if mapper_keyword is None else mapper_keyword.value),
            )
        )
        valid = False

    reducer_keyword = _keyword(node, "reducer")
    reducer_ref = _parallel_map_callable_ref(reducer_keyword.value if reducer_keyword else None, imports)
    if reducer_keyword is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_PARALLEL_MAP_REDUCER,
                "parallel_map is missing a required reducer",
                source_span=source_span_for_node(source_path, node),
            )
        )
        valid = False
    elif reducer_ref is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.PARALLEL_MAP_REDUCER_SCHEMA_MISMATCH,
                "parallel_map reducer must reference an imported or local step/workflow component",
                source_span=source_span_for_node(source_path, reducer_keyword.value),
            )
        )
        valid = False

    path_keyword = _keyword(node, "path_template")
    path_template = ""
    if path_keyword is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_ITERATION_COORDINATE,
                "parallel_map requires a literal path_template with an item coordinate",
                source_span=source_span_for_node(source_path, node),
            )
        )
        valid = False
    elif isinstance(path_keyword.value, ast.Constant) and isinstance(path_keyword.value.value, str):
        path_template = path_keyword.value.value
        if "{item_id}" not in path_template and "{index}" not in path_template:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.MISSING_ITEM_COORDINATE,
                    "parallel_map path_template must include {item_id} or {index}",
                    source_span=source_span_for_node(source_path, path_keyword.value),
                )
            )
            valid = False
    else:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.INVALID_PARALLEL_MAP_PATH_TEMPLATE,
                "parallel_map path_template must be a literal stable coordinate template",
                source_span=source_span_for_node(source_path, path_keyword.value),
            )
        )
        valid = False

    if not valid:
        return None
    assert fanout_id is not None
    assert items_ref is not None
    assert mapper_ref is not None
    assert reducer_ref is not None
    value_ref = f"param:{items_ref}" if items_ref in set(parameters) else f"output:{items_ref}"
    if is_ref(items_ref) and items_ref not in set(parameters) and items_ref not in local_outputs:
        value_ref = items_ref
    return ParsedParallelMapCall(
        id=fanout_id,
        source_span=source_span_for_node(source_path, node),
        items_ref=items_ref,
        mapper_ref=mapper_ref,
        reducer_ref=reducer_ref,
        path_template=path_template,
        iteration_coordinate="{item_id}" if "{item_id}" in path_template else "{index}",
        inputs=(StepInputBinding("items", value_ref, source_span_for_node(source_path, items_keyword)),),
        outputs=tuple(output_bindings),
    )


def _parallel_map_items_ref(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _parallel_map_callable_ref(
    node: ast.AST | None,
    imports: Mapping[str, ImportBinding],
) -> str | None:
    if not isinstance(node, ast.Name):
        return None
    binding = imports.get(node.id)
    if binding is None or binding.component is None:
        return None
    if binding.component.kind in {ComponentKind.STEP, ComponentKind.WORKFLOW}:
        return binding.component_ref
    return None


def _parse_nested_workflow_call(
    node: ast.Call,
    binding: ImportBinding,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    parameters: Sequence[str] = (),
    local_outputs: Mapping[str, SourceSpan] | None = None,
    output_bindings: Sequence[StepOutputBinding] = (),
) -> ParsedNestedWorkflowCall | None:
    local_outputs = {} if local_outputs is None else local_outputs
    component = binding.component
    assert component is not None
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.AMBIGUOUS_CALL_SITE_ID,
                "nested workflow calls must use keyword-only arguments including literal id=",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
            )
        )
        return None

    id_keyword = _keyword(node, "id")
    call_site_id = _validated_string_ref_keyword(
        node,
        id_keyword,
        source_path,
        diagnostics,
        code=(
            DiagnosticCode.MISSING_CALL_SITE_ID
            if id_keyword is None
            else DiagnosticCode.NON_LITERAL_CALL_SITE_ID
        ),
        missing_message="nested workflow calls must include a literal id keyword",
        invalid_message="nested workflow call-site id must use the workflow ref alphabet",
        component_ref=binding.component_ref,
    )
    if call_site_id is None:
        return None

    input_schema = tuple(component.metadata.get("input_names", ()))
    output_schema = tuple(component.metadata.get("output_names", ()))
    inputs = _parse_subflow_inputs(
        node,
        source_path,
        imports=imports,
        parameters=parameters,
        local_outputs=local_outputs,
        diagnostics=diagnostics,
    )
    if inputs is None:
        return None
    if not _validate_nested_workflow_schema(
        node,
        source_path,
        binding,
        inputs,
        input_schema,
        output_bindings,
        output_schema,
        diagnostics,
    ):
        return None
    child_workflow_id = str(component.metadata.get("workflow_id", component.id))
    parent_path = _parent_path_for_call_site(source_path, node)
    return ParsedNestedWorkflowCall(
        id=call_site_id,
        local_name=node.func.id,
        component_ref=binding.component_ref,
        source_span=source_span_for_node(source_path, node),
        component=component,
        child_workflow_id=child_workflow_id,
        parent_path=parent_path,
        call_site_path=f"{parent_path}/{call_site_id}",
        input_schema=input_schema,
        output_schema=output_schema,
        arguments={keyword.arg: keyword.value for keyword in node.keywords if keyword.arg},
        inputs=inputs,
        outputs=tuple(output_bindings),
    )


def _validate_nested_workflow_schema(
    node: ast.Call,
    source_path: str,
    binding: ImportBinding,
    inputs: Sequence[StepInputBinding],
    input_schema: Sequence[str],
    output_bindings: Sequence[StepOutputBinding],
    output_schema: Sequence[str],
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    valid = True
    actual_inputs = {input_binding.name for input_binding in inputs}
    expected_inputs = set(input_schema)
    if expected_inputs and actual_inputs != expected_inputs:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.CHILD_INPUT_SCHEMA_MISMATCH,
                "nested workflow input bindings must exactly match the child workflow inputs",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
                details={
                    "expected_inputs": tuple(input_schema),
                    "actual_inputs": tuple(input_binding.name for input_binding in inputs),
                },
            )
        )
        valid = False
    if len(output_bindings) > len(output_schema):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.CHILD_OUTPUT_SCHEMA_MISMATCH,
                "nested workflow output bindings exceed the child workflow outputs",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
                details={
                    "expected_outputs": tuple(output_schema),
                    "actual_outputs": tuple(output.name for output in output_bindings),
                },
            )
        )
        valid = False
    return valid


def _parent_path_for_call_site(source_path: str, node: ast.AST) -> str:
    del source_path, node
    return "__parent__"


def _parse_subflow_call(
    node: ast.Call,
    binding: ImportBinding,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    parameters: Sequence[str] = (),
    local_outputs: Mapping[str, SourceSpan] | None = None,
    output_bindings: Sequence[StepOutputBinding] = (),
) -> ParsedSubflowCall | None:
    local_outputs = {} if local_outputs is None else local_outputs
    component = binding.component
    assert isinstance(component, SubflowComponent)
    if output_bindings:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
                "subflow calls do not produce assignable workflow-local outputs",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
                "subflow calls must use keyword-only authoring arguments",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
            )
        )
        return None
    if _contains_executable_subflow_code(node):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
                "subflow calls must reference a manifest identity, not executable child workflow code",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None

    id_keyword = _keyword(node, "id")
    subflow_id = _validated_string_ref_keyword(
        node,
        id_keyword,
        source_path,
        diagnostics,
        code=DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
        missing_message="subflow calls must include a literal id keyword",
        invalid_message="subflow id must use the workflow ref alphabet",
        component_ref=binding.component_ref,
    )
    if subflow_id is None:
        return None

    manifest_hash = _subflow_manifest_hash(node, component, source_path, binding, diagnostics)
    alias = _subflow_alias(node, source_path, diagnostics)
    inputs = _parse_subflow_inputs(
        node,
        source_path,
        imports=imports,
        parameters=parameters,
        local_outputs=local_outputs,
        diagnostics=diagnostics,
    )
    if manifest_hash is None or alias is _INVALID_REF or inputs is None:
        return None
    return ParsedSubflowCall(
        id=subflow_id,
        local_name=node.func.id,
        component_ref=binding.component_ref,
        source_span=source_span_for_node(source_path, node),
        component=component,
        manifest_hash=manifest_hash,
        alias=alias,
        arguments={keyword.arg: keyword.value for keyword in node.keywords if keyword.arg},
        inputs=inputs,
    )


def _contains_executable_subflow_code(node: ast.Call) -> bool:
    executable_keywords = {"workflow", "steps", "body", "source", "runner"}
    return any(keyword.arg in executable_keywords for keyword in node.keywords)


def _subflow_manifest_hash(
    node: ast.Call,
    component: SubflowComponent,
    source_path: str,
    binding: ImportBinding,
    diagnostics: list[AuthoringDiagnostic],
) -> str | None:
    keyword = _keyword(node, "manifest_hash")
    if keyword is not None:
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return _validated_subflow_manifest_hash(
                keyword.value.value,
                source_path,
                keyword,
                diagnostics,
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
                "subflow manifest_hash must be a literal or resolver-provided identity",
                source_span=source_span_for_node(source_path, keyword),
            )
        )
        return None
    manifest_hash = component.metadata.get("manifest_hash")
    if isinstance(manifest_hash, str):
        return _validated_subflow_manifest_hash(
            manifest_hash,
            source_path,
            node,
            diagnostics,
        )
    diagnostics.append(
        _diagnostic(
            DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
            "subflow manifest_hash must be a literal or resolver-provided identity",
            source_span=source_span_for_node(source_path, node),
        )
    )
    return None


def _validated_subflow_manifest_hash(
    manifest_hash: str,
    source_path: str,
    node: ast.AST,
    diagnostics: list[AuthoringDiagnostic],
) -> str | None:
    if is_manifest_hash(manifest_hash):
        return manifest_hash
    diagnostics.append(
        _diagnostic(
            DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
            "subflow manifest_hash must be a literal or resolver-provided identity",
            source_span=source_span_for_node(source_path, node),
        )
    )
    return None


def _subflow_alias(
    node: ast.Call,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> str | None:
    keyword = _keyword(node, "alias")
    if keyword is None:
        return None
    if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
        if is_ref(keyword.value.value):
            return keyword.value.value
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
                "subflow alias must use the workflow ref alphabet",
                source_span=source_span_for_node(source_path, keyword),
            )
        )
        return _INVALID_REF
    diagnostics.append(
        _diagnostic(
            DiagnosticCode.UNSUPPORTED_SUBFLOW_REFERENCE,
            "subflow alias must be a literal string when provided",
            source_span=source_span_for_node(source_path, keyword),
        )
    )
    return None


def _parse_subflow_inputs(
    node: ast.Call,
    source_path: str,
    *,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    local_outputs: Mapping[str, SourceSpan],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepInputBinding, ...] | None:
    inputs: list[StepInputBinding] = []
    valid = True
    parameter_names = set(parameters)
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg in RESERVED_SUBFLOW_CALL_KEYWORDS:
            continue
        if not isinstance(keyword.value, ast.Name):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "subflow keyword values must reference workflow parameters or prior local outputs",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            valid = False
            continue
        ref_name = keyword.value.id
        if ref_name in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "compiler intrinsics cannot be passed as dataflow values",
                    source_span=source_span_for_node(source_path, keyword.value),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{ref_name}",
                )
            )
            valid = False
            continue
        ref_binding = imports.get(ref_name)
        if ref_binding is not None and isinstance(ref_binding.component, PolicyComponent):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_CALL_KEYWORD,
                    "policy components must be passed with reserved policy= or policies= syntax",
                    source_span=source_span_for_node(source_path, keyword.value),
                    details={"keyword": keyword.arg},
                )
            )
            valid = False
            continue
        if ref_name in parameter_names:
            value_ref = f"param:{ref_name}"
        elif ref_name in local_outputs:
            value_ref = f"output:{ref_name}"
        else:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNKNOWN_COMPONENT,
                    "keyword dataflow reference is not a workflow parameter or prior local output",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            valid = False
            continue
        inputs.append(
            StepInputBinding(
                name=keyword.arg,
                value_ref=value_ref,
                source_span=source_span_for_node(source_path, keyword),
            )
        )
    return tuple(inputs) if valid else None


def _parse_step_call(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    parameters: Sequence[str] = (),
    local_outputs: Mapping[str, SourceSpan] | None = None,
    output_bindings: Sequence[StepOutputBinding] = (),
) -> StepCall | None:
    local_outputs = {} if local_outputs is None else local_outputs
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow steps must be direct component calls",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
                "component calls must use explicit keyword authoring arguments",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if node.args:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
                "component calls must use keyword-only authoring arguments",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    binding = imports.get(node.func.id)
    if binding is None or binding.component is None:
        if binding is not None and binding.kind == "intrinsic":
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "compiler intrinsic calls are not workflow component steps",
                    source_span=source_span_for_node(source_path, node),
                    component_ref=binding.component_ref,
                )
            )
            return None
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNKNOWN_COMPONENT,
                "step component is not imported in workflow source",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if binding.component.kind is not ComponentKind.STEP or not isinstance(binding.component, StepComponent):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.WRONG_COMPONENT_KIND,
                "component kind is not valid for a workflow step call",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
            )
        )
        return None
    id_keyword = _keyword(node, "id")
    step_id = _validated_string_ref_keyword(
        node,
        id_keyword,
        source_path,
        diagnostics,
        code=DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
        missing_message="component calls must include a literal id keyword",
        invalid_message="component call id must use the workflow ref alphabet",
        component_ref=binding.component_ref,
    )
    if step_id is None:
        return None
    policies = _parse_step_policy_keywords(node, source_path, imports, diagnostics)
    if policies is None:
        return None
    inputs = _parse_step_inputs(
        node,
        source_path,
        imports=imports,
        parameters=parameters,
        local_outputs=local_outputs,
        diagnostics=diagnostics,
    )
    if inputs is None:
        return None
    if not _validate_static_step_dependencies(node, binding, source_path, diagnostics):
        return None
    return StepCall(
        id=step_id,
        local_name=node.func.id,
        component_ref=binding.component_ref,
        source_span=source_span_for_node(source_path, node),
        component=binding.component,
        arguments={keyword.arg: keyword.value for keyword in node.keywords if keyword.arg},
        inputs=inputs,
        outputs=tuple(output_bindings),
        policies=policies,
    )


def _validate_static_step_dependencies(
    node: ast.Call,
    binding: ImportBinding,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    component = binding.component
    assert isinstance(component, StepComponent)
    valid = True
    metadata = component.metadata

    prompt_key = metadata.get("prompt_key")
    if isinstance(prompt_key, str) and prompt_key.strip() and component.prompt is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_PROMPT_DEPENDENCY,
                f"step component declares prompt_key {prompt_key!r} but has no static PromptComponent",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
                details={"prompt_key": prompt_key},
            )
        )
        valid = False

    required_resources = _static_resource_dependencies(metadata)
    available_resources = _static_resource_keys(metadata)
    missing_resources = tuple(
        resource for resource in required_resources if resource not in available_resources
    )
    if missing_resources:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_RESOURCE_DEPENDENCY,
                "step component declares static resources that are not present in metadata",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
                details={
                    "missing_resources": missing_resources,
                    "available_resources": tuple(sorted(available_resources)),
                },
            )
        )
        valid = False
    return valid


def _static_resource_dependencies(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    raw = metadata.get("resource_dependencies", ())
    if isinstance(raw, str):
        return (raw,) if raw else ()
    if not isinstance(raw, Sequence) or isinstance(raw, (bytes, bytearray, Mapping)):
        return ()
    return tuple(item for item in raw if isinstance(item, str) and item)


def _static_resource_keys(metadata: Mapping[str, Any]) -> frozenset[str]:
    raw = metadata.get("resources", {})
    if isinstance(raw, Mapping):
        return frozenset(key for key in raw if isinstance(key, str) and key)
    return frozenset()


def _parse_step_policy_keywords(
    node: ast.Call,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepPolicyBinding, ...] | None:
    policies: list[StepPolicyBinding] = []
    valid = True
    for keyword in node.keywords:
        if keyword.arg not in RESERVED_STEP_CALL_KEYWORDS or keyword.arg == "id":
            continue
        assert keyword.arg is not None
        if keyword.arg == "policy":
            parsed = _parse_single_step_policy(keyword, source_path, imports, diagnostics)
            if parsed is None:
                valid = False
            else:
                policies.append(parsed)
            continue
        if keyword.arg == "policies":
            parsed_many = _parse_multiple_step_policies(keyword, source_path, imports, diagnostics)
            if parsed_many is None:
                valid = False
            else:
                policies.extend(parsed_many)
            continue
        diagnostics.append(
            _reserved_step_keyword_diagnostic(keyword.arg, source_path, keyword)
        )
        valid = False
    return tuple(policies) if valid else None


def _parse_workflow_policy_keywords(
    node: ast.Call,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[WorkflowPolicyBinding, ...] | None:
    policies: list[WorkflowPolicyBinding] = []
    valid = True
    for keyword in node.keywords:
        if keyword.arg not in {"policy", "policies"}:
            continue
        if keyword.arg == "policy":
            parsed = _parse_single_workflow_policy(keyword, source_path, imports, diagnostics)
            if parsed is None:
                valid = False
            else:
                policies.append(parsed)
            continue
        parsed_many = _parse_multiple_workflow_policies(keyword, source_path, imports, diagnostics)
        if parsed_many is None:
            valid = False
        else:
            policies.extend(parsed_many)
    return tuple(policies) if valid else None


def _parse_multiple_workflow_policies(
    keyword: ast.keyword,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[WorkflowPolicyBinding, ...] | None:
    if not isinstance(keyword.value, (ast.List, ast.Tuple)):
        diagnostics.append(_workflow_policy_keyword_diagnostic("policies", source_path, keyword))
        return None
    policies: list[WorkflowPolicyBinding] = []
    valid = True
    for element in keyword.value.elts:
        parsed = _workflow_policy_binding_from_node(
            "policies",
            element,
            source_path,
            imports,
            diagnostics,
            invalid_span=element,
        )
        if parsed is None:
            valid = False
        else:
            policies.append(parsed)
    return tuple(policies) if valid else None


def _parse_single_workflow_policy(
    keyword: ast.keyword,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowPolicyBinding | None:
    return _workflow_policy_binding_from_node(
        "policy",
        keyword.value,
        source_path,
        imports,
        diagnostics,
        invalid_span=keyword,
    )


def _workflow_policy_binding_from_node(
    keyword_name: str,
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    invalid_span: ast.AST,
) -> WorkflowPolicyBinding | None:
    if not isinstance(node, ast.Name):
        diagnostics.append(_workflow_policy_keyword_diagnostic(keyword_name, source_path, invalid_span))
        return None
    binding = imports.get(node.id)
    if (
        binding is None
        or binding.component is None
        or not isinstance(binding.component, PolicyComponent)
    ):
        diagnostics.append(_workflow_policy_keyword_diagnostic(keyword_name, source_path, invalid_span))
        return None
    if binding.component.policy_type not in _SUPPORTED_WORKFLOW_CONTROL_POLICY_TYPES:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_POLICY_CARRIER,
                (
                    f"workflow policy type {binding.component.policy_type!r} does not map "
                    "to an existing workflow-level control carrier"
                ),
                source_span=source_span_for_node(source_path, invalid_span),
                details={"policy_type": binding.component.policy_type},
            )
        )
        return None
    if not _validate_retry_timing_policy_config(
        binding.component,
        source_path=source_path,
        node=invalid_span,
        diagnostics=diagnostics,
    ):
        return None
    return WorkflowPolicyBinding(
        keyword=keyword_name,
        component_ref=binding.component_ref,
        component=binding.component,
        source_span=source_span_for_node(source_path, node),
    )


def _workflow_policy_keyword_diagnostic(
    keyword_name: str,
    source_path: str,
    node: ast.AST,
) -> AuthoringDiagnostic:
    return _diagnostic(
        DiagnosticCode.RESERVED_CALL_KEYWORD,
        f"workflow policy keyword {keyword_name!r} must reference imported PolicyComponent names",
        source_span=source_span_for_node(source_path, node),
        details={"keyword": keyword_name},
    )


def _validate_retry_timing_policy_config(
    component: PolicyComponent,
    *,
    source_path: str,
    node: ast.AST,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    invalid_fields: list[str] = []
    config = component.config
    if component.policy_type == "retry":
        max_attempts = config.get("max_attempts", 1)
        backoff = config.get("backoff", "none")
        retry_on = config.get("retry_on", ())
        if not _is_positive_int(max_attempts):
            invalid_fields.append("max_attempts")
        if not isinstance(backoff, str):
            invalid_fields.append("backoff")
        if (
            isinstance(retry_on, (str, bytes))
            or not isinstance(retry_on, Sequence)
            or not all(isinstance(item, str) for item in retry_on)
        ):
            invalid_fields.append("retry_on")
    elif component.policy_type == "timing":
        timeout_seconds = config.get("timeout_seconds")
        deadline_ref = config.get("deadline_ref")
        ttl_seconds = config.get("ttl_seconds")
        if timeout_seconds is not None and not _is_positive_number(timeout_seconds):
            invalid_fields.append("timeout_seconds")
        if deadline_ref is not None and not isinstance(deadline_ref, str):
            invalid_fields.append("deadline_ref")
        if ttl_seconds is not None and not _is_positive_number(ttl_seconds):
            invalid_fields.append("ttl_seconds")
    if not invalid_fields:
        return True
    diagnostics.append(
        _diagnostic(
            DiagnosticCode.MALFORMED_POLICY_CONFIG,
            f"policy {component.id!r} has malformed {component.policy_type} config",
            source_span=source_span_for_node(source_path, node),
            details={
                "policy_type": component.policy_type,
                "invalid_fields": tuple(invalid_fields),
            },
        )
    )
    return False


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )


def _parse_multiple_step_policies(
    keyword: ast.keyword,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepPolicyBinding, ...] | None:
    if not isinstance(keyword.value, (ast.List, ast.Tuple)):
        diagnostics.append(_reserved_step_keyword_diagnostic("policies", source_path, keyword))
        return None
    policies: list[StepPolicyBinding] = []
    valid = True
    for element in keyword.value.elts:
        parsed = _policy_binding_from_node(
            "policies",
            element,
            source_path,
            imports,
            diagnostics,
            invalid_span=element,
        )
        if parsed is None:
            valid = False
        else:
            policies.append(parsed)
    return tuple(policies) if valid else None


def _parse_single_step_policy(
    keyword: ast.keyword,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> StepPolicyBinding | None:
    return _policy_binding_from_node(
        "policy",
        keyword.value,
        source_path,
        imports,
        diagnostics,
        invalid_span=keyword,
    )


def _policy_binding_from_node(
    keyword_name: str,
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    invalid_span: ast.AST,
) -> StepPolicyBinding | None:
    if not isinstance(node, ast.Name):
        diagnostics.append(_reserved_step_keyword_diagnostic(keyword_name, source_path, invalid_span))
        return None
    binding = imports.get(node.id)
    if (
        binding is None
        or binding.component is None
        or not isinstance(binding.component, PolicyComponent)
    ):
        diagnostics.append(_reserved_step_keyword_diagnostic(keyword_name, source_path, invalid_span))
        return None
    if binding.component.policy_type not in _SUPPORTED_STEP_POLICY_TYPES:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_POLICY_CARRIER,
                f"policy type {binding.component.policy_type!r} does not map to an existing manifest carrier",
                source_span=source_span_for_node(source_path, invalid_span),
                details={"policy_type": binding.component.policy_type},
            )
        )
        return None
    if not _validate_retry_timing_policy_config(
        binding.component,
        source_path=source_path,
        node=invalid_span,
        diagnostics=diagnostics,
    ):
        return None
    return StepPolicyBinding(
        keyword=keyword_name,
        component_ref=binding.component_ref,
        component=binding.component,
        source_span=source_span_for_node(source_path, node),
    )


def _reserved_step_keyword_diagnostic(
    keyword_name: str,
    source_path: str,
    node: ast.AST,
) -> AuthoringDiagnostic:
    return _diagnostic(
        DiagnosticCode.RESERVED_CALL_KEYWORD,
        f"step call keyword {keyword_name!r} is reserved for compiler-owned authoring syntax",
        source_span=source_span_for_node(source_path, node),
        details={"keyword": keyword_name},
    )


def _parse_step_inputs(
    node: ast.Call,
    source_path: str,
    *,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    local_outputs: Mapping[str, SourceSpan],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepInputBinding, ...] | None:
    inputs: list[StepInputBinding] = []
    valid = True
    parameter_names = set(parameters)
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg in RESERVED_STEP_CALL_KEYWORDS:
            continue
        if not isinstance(keyword.value, ast.Name):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "component keyword values must reference workflow parameters or prior local outputs",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            valid = False
            continue
        ref_name = keyword.value.id
        if ref_name in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "compiler intrinsics cannot be passed as dataflow values",
                    source_span=source_span_for_node(source_path, keyword.value),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{ref_name}",
                )
            )
            valid = False
            continue
        ref_binding = imports.get(ref_name)
        if ref_binding is not None and isinstance(ref_binding.component, PolicyComponent):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_CALL_KEYWORD,
                    "policy components must be passed with reserved policy= or policies= syntax",
                    source_span=source_span_for_node(source_path, keyword.value),
                    details={"keyword": keyword.arg},
                )
            )
            valid = False
            continue
        if ref_name in parameter_names:
            value_ref = f"param:{ref_name}"
        elif ref_name in local_outputs:
            value_ref = f"output:{ref_name}"
        else:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNKNOWN_COMPONENT,
                    "keyword dataflow reference is not a workflow parameter or prior local output",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            valid = False
            continue
        inputs.append(
            StepInputBinding(
                name=keyword.arg,
                value_ref=value_ref,
                source_span=source_span_for_node(source_path, keyword),
            )
        )
    return tuple(inputs) if valid else None


def _parse_intrinsic_call(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> IntrinsicCall | None:
    if not _is_reserved_intrinsic_call(node, imports):
        return None
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name)
    intrinsic_name = node.func.id
    if intrinsic_name == "workflow":
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow(...) is only valid as a source declaration",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "compiler intrinsic calls must use literal keyword arguments only",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None

    arguments: dict[str, str] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "compiler intrinsic arguments must be literal strings",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            return None
        if keyword.arg in arguments:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "compiler intrinsic arguments must not repeat keywords",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            return None
        arguments[keyword.arg] = keyword.value.value

    allowed_keywords = set(RESERVED_INTRINSIC_CALL_KEYWORDS[intrinsic_name])
    required_keywords = {
        "halt": {"id"},
        "suspend": {"route_id"},
        "transition": {"id", "type"},
    }[intrinsic_name]
    if set(arguments) - allowed_keywords or not required_keywords.issubset(arguments):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "compiler intrinsic call is outside the V1 authoring grammar",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    return IntrinsicCall(
        name=intrinsic_name,
        arguments=arguments,
        source_span=source_span_for_node(source_path, node),
    )


def _is_reserved_intrinsic_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    binding = imports.get(node.func.id)
    return (
        binding is not None
        and binding.kind == "intrinsic"
        and binding.import_ref.module == AUTHORING_INTRINSIC_MODULE
        and binding.import_ref.qualname == node.func.id
        and binding.local_name == node.func.id
    )


def _lower_parsed_source(
    parsed_source: ParsedWorkflowSource,
) -> tuple[Pipeline | None, tuple[AuthoringDiagnostic, ...]]:
    workflow = parsed_source.workflow
    if workflow is None:
        return None, ()
    diagnostics: list[AuthoringDiagnostic] = []
    lowered_block = _lower_source_block(
        workflow.source_block,
        source_form=workflow.source_form,
        initial_output_producers={},
        diagnostics=diagnostics,
    )
    if diagnostics:
        return None, tuple(diagnostics)
    routes = _bind_route_metadata(
        lowered_block.routes,
        workflow.source_block,
        diagnostics,
    )
    if diagnostics:
        return None, tuple(diagnostics)
    policy = _merge_workflow_policies(
        _lower_workflow_policy_bindings(workflow.policies),
        _lower_workflow_policy(workflow.intrinsics),
    )
    return Pipeline(
        id=workflow.id,
        version=workflow.version,
        steps=lowered_block.steps,
        routes=routes,
        policy=policy,
        source_span=workflow.source_span,
        metadata={"source_form": workflow.source_form},
    ), ()


def _lower_source_block(
    block: ParsedSourceBlock,
    *,
    source_form: str,
    initial_output_producers: Mapping[str, str],
    diagnostics: list[AuthoringDiagnostic],
) -> _LoweredSourceBlock:
    steps: list[Step] = []
    routes: list[Route] = []
    entry_step_id: str | None = None
    pending_exits: tuple[str, ...] = ()
    output_producers: dict[str, str] = dict(initial_output_producers)

    for statement in block.statements:
        if isinstance(statement, ParsedStepCall):
            step = _lower_step_call(statement, source_form, diagnostics)
            if entry_step_id is None:
                entry_step_id = step.id
            routes.extend(
                _default_route(source_id, step.id, statement.source_span, source_form)
                for source_id in pending_exits
            )
            steps.append(step)
            pending_exits = (step.id,)
            for output in statement.outputs:
                output_producers[output.name] = statement.id
        elif isinstance(statement, ParsedSubflowCall):
            step = _lower_subflow_call(statement, source_form)
            if entry_step_id is None:
                entry_step_id = step.id
            routes.extend(
                _default_route(source_id, step.id, statement.source_span, source_form)
                for source_id in pending_exits
            )
            steps.append(step)
            pending_exits = (step.id,)
        elif isinstance(statement, ParsedNestedWorkflowCall):
            step = _lower_nested_workflow_call(statement, source_form)
            if entry_step_id is None:
                entry_step_id = step.id
            routes.extend(
                _default_route(source_id, step.id, statement.source_span, source_form)
                for source_id in pending_exits
            )
            steps.append(step)
            pending_exits = (step.id,)
            for output in statement.outputs:
                output_producers[output.name] = statement.id
        elif isinstance(statement, ParsedParallelMapCall):
            step = _lower_parallel_map_call(statement, source_form)
            if entry_step_id is None:
                entry_step_id = step.id
            routes.extend(
                _default_route(source_id, step.id, statement.source_span, source_form)
                for source_id in pending_exits
            )
            steps.append(step)
            pending_exits = (step.id,)
            for output in statement.outputs:
                output_producers[output.name] = statement.id
        elif isinstance(statement, ParsedBranchBlock):
            branch = _lower_branch_block(
                statement,
                source_form=source_form,
                output_producers=output_producers,
                diagnostics=diagnostics,
            )
            if entry_step_id is None:
                entry_step_id = branch.entry_step_id
            steps.extend(branch.steps)
            routes.extend(branch.routes)
            pending_exits = branch.exit_step_ids
            for name in statement.merged_outputs:
                producer = branch.output_producers.get(name)
                if producer is not None:
                    output_producers[name] = producer
        elif isinstance(statement, ParsedLoopBlock):
            loop = _lower_source_block(
                statement.body,
                source_form=source_form,
                initial_output_producers=output_producers,
                diagnostics=diagnostics,
            )
            if entry_step_id is None:
                entry_step_id = loop.entry_step_id
            if loop.entry_step_id is not None:
                routes.extend(
                    _default_route(source_id, loop.entry_step_id, statement.source_span, source_form)
                    for source_id in pending_exits
                )
            backedge_condition_ref = _loop_backedge_condition_ref(statement.policy)
            loop_backedges = _loop_backedge_bindings(
                statement,
                loop,
                default_condition_ref=backedge_condition_ref,
                diagnostics=diagnostics,
            )
            loop_policy_backedges = (
                MappingProxyType({binding.tail_step_id: binding for binding in loop_backedges})
                if loop_backedges
                else MappingProxyType({})
            )
            steps.extend(
                _attach_loop_policy_to_step(
                    step,
                    statement.policy,
                    carrier_backedges=loop_policy_backedges,
                    fallback_carrier_id=loop.entry_step_id,
                    fallback_reentry_id=backedge_condition_ref,
                )
                for step in loop.steps
            )
            routes.extend(loop.routes)
            if loop.entry_step_id is not None:
                for binding in loop_backedges:
                    routes.append(
                        _loop_backedge_route(
                            statement,
                            source_id=binding.tail_step_id,
                            target_id=loop.entry_step_id,
                            label=binding.label,
                            condition_ref=binding.condition_ref,
                            source_form=source_form,
                            route_id=binding.route_id,
                        )
                    )
                if not loop_backedges and len(loop.exit_step_ids) == 1:
                    tail_step_id = loop.exit_step_ids[0]
                    routes.append(
                        _loop_backedge_route(
                            statement,
                            source_id=tail_step_id,
                            target_id=loop.entry_step_id,
                            label="reentry",
                            condition_ref=backedge_condition_ref,
                            source_form=source_form,
                        )
                    )
            pending_exits = loop.exit_step_ids
            output_producers.update(loop.output_producers)

    return _LoweredSourceBlock(
        steps=tuple(steps),
        routes=tuple(routes),
        entry_step_id=entry_step_id,
        exit_step_ids=pending_exits,
        output_producers=MappingProxyType(output_producers),
    )


def _lower_branch_block(
    branch: ParsedBranchBlock,
    *,
    source_form: str,
    output_producers: Mapping[str, str],
    diagnostics: list[AuthoringDiagnostic],
) -> _LoweredSourceBlock:
    steps: list[Step] = []
    branch_routes: list[Route] = []
    arm_routes: list[Route] = []
    exit_step_ids: list[str] = []
    branch_output_producers: dict[str, str] = {}
    decision_source = output_producers[branch.decision_output]
    has_else = any(arm.condition is None for arm in branch.arms)

    for arm in branch.arms:
        lowered_arm = _lower_source_block(
            arm.body,
            source_form=source_form,
            initial_output_producers=output_producers,
            diagnostics=diagnostics,
        )
        steps.extend(lowered_arm.steps)
        if lowered_arm.entry_step_id is not None:
            branch_routes.append(
                _branch_route(
                    branch,
                    arm,
                    source_id=decision_source,
                    target_id=lowered_arm.entry_step_id,
                    source_form=source_form,
                )
            )
        arm_routes.extend(lowered_arm.routes)
        if not arm.terminal:
            exit_step_ids.extend(lowered_arm.exit_step_ids)
            for name in branch.merged_outputs:
                producer = lowered_arm.output_producers.get(name)
                if producer is not None:
                    branch_output_producers.setdefault(name, producer)
    if not has_else and any(arm.terminal for arm in branch.arms):
        exit_step_ids.append(decision_source)

    return _LoweredSourceBlock(
        steps=tuple(steps),
        routes=(*branch_routes, *arm_routes),
        entry_step_id=steps[0].id if steps else None,
        exit_step_ids=tuple(exit_step_ids),
        output_producers=MappingProxyType(branch_output_producers),
    )


def _lower_step_call(
    step: ParsedStepCall,
    source_form: str,
    diagnostics: list[AuthoringDiagnostic],
) -> Step:
    metadata = _lower_step_metadata(step)
    return Step(
        id=step.id,
        kind=step.component.step_type,
        label=step.component.label,
        inputs=tuple(
            Input(
                name=input_binding.name,
                value_ref=input_binding.value_ref,
                source_span=input_binding.source_span,
            )
            for input_binding in step.inputs
        ),
        outputs=tuple(
            Output(
                name=output_binding.name,
                source_span=output_binding.source_span,
            )
            for output_binding in step.outputs
        ),
        capabilities=_lower_step_capabilities(step, diagnostics),
        policy=_lower_step_policy_bindings(step.policies),
        source_span=step.source_span,
        metadata={
            "component_ref": step.component_ref,
            "source_form": source_form,
            **metadata,
        },
    )


def _lower_step_metadata(step: ParsedStepCall) -> dict[str, Any]:
    declared = _megaplan_step_declared_interface(step.component)
    metadata: dict[str, Any] = {}
    for key in _LOWERED_STEP_METADATA_KEYS:
        value = declared.get(key, step.component.metadata.get(key))
        if key == "handler_ref" and isinstance(value, str) and value:
            metadata[key] = value
        elif key == "terminal" and isinstance(value, bool):
            metadata[key] = value
    policy_refs = declared.get("policy_refs")
    if isinstance(policy_refs, Sequence) and not isinstance(policy_refs, (str, bytes)):
        normalized = tuple(str(item) for item in policy_refs if isinstance(item, str) and item)
        if normalized:
            metadata["policy_refs"] = normalized
    override_actions = declared.get("override_actions")
    if isinstance(override_actions, Sequence) and not isinstance(override_actions, (str, bytes)):
        normalized = tuple(
            str(item) for item in override_actions if isinstance(item, str) and item
        )
        if normalized:
            metadata["override_actions"] = normalized
    return metadata


def _lower_step_capabilities(
    step: ParsedStepCall,
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[Capability, ...]:
    declared = _megaplan_step_declared_interface(step.component)
    raw_capabilities = declared.get(
        "capability_requirements",
        step.component.metadata.get("capability_requirements", ()),
    )
    if raw_capabilities in (None, ()):
        return ()
    if (
        isinstance(raw_capabilities, (str, bytes, Mapping))
        or not isinstance(raw_capabilities, Sequence)
    ):
        diagnostics.append(
            _capability_metadata_diagnostic(
                step,
                "capability_requirements metadata must be a sequence of capability mappings",
            )
        )
        return ()

    capabilities: list[Capability] = []
    for raw_capability in raw_capabilities:
        if not isinstance(raw_capability, Mapping):
            diagnostics.append(
                _capability_metadata_diagnostic(
                    step,
                    "capability requirement metadata must be a mapping",
                )
            )
            continue
        capability_id = raw_capability.get("id")
        route = raw_capability.get("route", "default")
        required = raw_capability.get("required", True)
        capability_metadata = raw_capability.get("metadata", {})
        if (
            not isinstance(capability_id, str)
            or not capability_id
            or not isinstance(route, str)
            or not route
            or not isinstance(required, bool)
            or not isinstance(capability_metadata, Mapping)
        ):
            diagnostics.append(
                _capability_metadata_diagnostic(
                    step,
                    "capability requirement metadata must declare string id, optional string route, and optional boolean required",
                )
            )
            continue
        try:
            capabilities.append(
                Capability(
                    id=capability_id,
                    route=route,
                    required=required,
                    source_span=step.source_span,
                    metadata=capability_metadata,
                )
            )
        except ValueError:
            diagnostics.append(
                _capability_metadata_diagnostic(
                    step,
                    "capability requirement metadata has invalid DSL field values",
                )
            )
    return tuple(capabilities)


def _capability_metadata_diagnostic(step: ParsedStepCall, message: str) -> AuthoringDiagnostic:
    spec = diagnostic_spec(DiagnosticCode.MALFORMED_CAPABILITY_METADATA)
    return AuthoringDiagnostic(
        code=DiagnosticCode.MALFORMED_CAPABILITY_METADATA,
        severity=spec.severity,
        message=message,
        source_span=step.source_span,
        component_ref=step.component_ref,
    )


def _lower_subflow_call(subflow: ParsedSubflowCall, source_form: str) -> Step:
    return Step(
        id=subflow.id,
        kind="subpipeline",
        label=subflow.component.label,
        inputs=tuple(
            Input(
                name=input_binding.name,
                value_ref=input_binding.value_ref,
                source_span=input_binding.source_span,
            )
            for input_binding in subflow.inputs
        ),
        source_span=subflow.source_span,
        subpipeline=SubpipelineRef(
            manifest_hash=subflow.manifest_hash,
            alias=subflow.alias,
        ),
        metadata={
            "component_ref": subflow.component_ref,
            "source_form": source_form,
        },
    )


def _lower_nested_workflow_call(nested: ParsedNestedWorkflowCall, source_form: str) -> Step:
    manifest_hash = "sha256:" + hashlib.sha256(
        f"{nested.component_ref}:{nested.child_workflow_id}".encode("utf-8")
    ).hexdigest()
    return Step(
        id=nested.id,
        kind="subpipeline",
        label=nested.component.label,
        inputs=tuple(
            Input(
                name=input_binding.name,
                value_ref=input_binding.value_ref,
                source_span=input_binding.source_span,
            )
            for input_binding in nested.inputs
        ),
        outputs=tuple(
            Output(
                name=output_binding.name,
                source_span=output_binding.source_span,
            )
            for output_binding in nested.outputs
        ),
        source_span=nested.source_span,
        subpipeline=SubpipelineRef(
            manifest_hash=manifest_hash,
            alias=nested.child_workflow_id,
        ),
        metadata={
            "component_ref": nested.component_ref,
            "source_form": source_form,
            "executable_workflow": True,
            "child_workflow_id": nested.child_workflow_id,
            "call_site_path": nested.call_site_path,
            "parent_path": nested.parent_path,
            "inputs_schema": nested.input_schema,
            "outputs_schema": nested.output_schema,
        },
    )


def _lower_parallel_map_call(fanout: ParsedParallelMapCall, source_form: str) -> Step:
    return Step(
        id=fanout.id,
        kind="parallel_map",
        inputs=tuple(
            Input(
                name=input_binding.name,
                value_ref=input_binding.value_ref,
                source_span=input_binding.source_span,
            )
            for input_binding in fanout.inputs
        ),
        outputs=tuple(
            Output(
                name=output_binding.name,
                source_span=output_binding.source_span,
            )
            for output_binding in fanout.outputs
        ),
        policy=WorkflowPolicy(
            fanout=FanoutPolicy(mode="dynamic", reducer_ref=fanout.reducer_ref),
        ),
        source_span=fanout.source_span,
        metadata={
            "source_form": source_form,
            "parallel_map": True,
            "items_ref": fanout.items_ref,
            "mapper_ref": fanout.mapper_ref,
            "reducer_ref": fanout.reducer_ref,
            "path_template": fanout.path_template,
            "iteration_coordinate": fanout.iteration_coordinate,
            "call_site_path": fanout.id,
        },
    )


def _lower_step_policy_bindings(policies: Sequence[StepPolicyBinding]) -> WorkflowPolicy | None:
    if not policies:
        return None
    retry: RetryPolicy | None = None
    timing: TimingPolicy | None = None
    authority: list[AuthorityRequirement] = []
    control_transitions: list[ControlTransitionSlot] = []
    for binding in policies:
        component = binding.component
        config = component.config
        if component.policy_type == "retry":
            retry = RetryPolicy(
                max_attempts=config.get("max_attempts", 1),
                backoff=config.get("backoff", "none"),
                retry_on=tuple(config.get("retry_on", ())),
            )
        elif component.policy_type == "timing":
            timing = TimingPolicy(
                timeout_seconds=config.get("timeout_seconds"),
                deadline_ref=config.get("deadline_ref"),
                ttl_seconds=config.get("ttl_seconds"),
            )
        elif component.policy_type in {"approval", "authority"}:
            authority.append(
                AuthorityRequirement(
                    authority_id=config.get("authority_id", component.id),
                    action=config.get("action", component.policy_type),
                    evidence_schema_hash=config.get("evidence_schema_hash"),
                    capability_id=config.get("capability_id"),
                )
            )
        elif component.policy_type == "control-transition":
            control_transitions.append(
                ControlTransitionSlot(
                    transition_id=config.get("transition_id", component.id),
                    transition_type=config.get("transition_type", "policy"),
                    trigger_ref=config.get("trigger_ref"),
                    target_ref=config.get("target_ref"),
                    payload_schema_hash=config.get("payload_schema_hash"),
                    policy_ref=config.get("policy_ref"),
                )
            )
    return WorkflowPolicy(
        retry=retry,
        timing=timing,
        control_transitions=tuple(control_transitions),
        authority=tuple(authority),
    )


def _lower_workflow_policy_bindings(
    policies: Sequence[WorkflowPolicyBinding],
) -> WorkflowPolicy | None:
    if not policies:
        return None
    retry: RetryPolicy | None = None
    timing: TimingPolicy | None = None
    authority: list[AuthorityRequirement] = []
    control_transitions: list[ControlTransitionSlot] = []
    suspension_routes: list[SuspensionRoute] = []
    for binding in policies:
        component = binding.component
        config = component.config
        if component.policy_type == "retry":
            retry = RetryPolicy(
                max_attempts=config.get("max_attempts", 1),
                backoff=config.get("backoff", "none"),
                retry_on=tuple(config.get("retry_on", ())),
            )
        elif component.policy_type == "timing":
            timing = TimingPolicy(
                timeout_seconds=config.get("timeout_seconds"),
                deadline_ref=config.get("deadline_ref"),
                ttl_seconds=config.get("ttl_seconds"),
            )
        elif component.policy_type in {"approval", "authority"}:
            authority.append(
                AuthorityRequirement(
                    authority_id=config.get("authority_id", component.id),
                    action=config.get("action", component.policy_type),
                    evidence_schema_hash=config.get("evidence_schema_hash"),
                    capability_id=config.get("capability_id"),
                )
            )
        elif component.policy_type == "control-transition":
            control_transitions.append(
                ControlTransitionSlot(
                    transition_id=config.get("transition_id", component.id),
                    transition_type=config.get("transition_type", "policy"),
                    trigger_ref=config.get("trigger_ref"),
                    target_ref=config.get("target_ref"),
                    payload_schema_hash=config.get("payload_schema_hash"),
                    policy_ref=config.get("policy_ref"),
                )
            )
        elif component.policy_type == "suspension":
            suspension_routes.append(
                SuspensionRoute(
                    route_id=config.get("route_id", component.id),
                    capability_id=config.get("capability_id"),
                    reentry_id=config.get("reentry_id"),
                    payload_schema_hash=config.get("payload_schema_hash"),
                    resume_schema_hash=config.get("resume_schema_hash"),
                    resume_schema_ref=config.get("resume_schema_ref"),
                    resume_payload_ref=config.get("resume_payload_ref"),
                )
            )
    return WorkflowPolicy(
        retry=retry,
        timing=timing,
        authority=tuple(authority),
        control_transitions=tuple(control_transitions),
        suspension_routes=tuple(suspension_routes),
    )


def _merge_workflow_policies(*policies: WorkflowPolicy | None) -> WorkflowPolicy | None:
    present = [policy for policy in policies if policy is not None]
    if not present:
        return None
    return WorkflowPolicy(
        budget=_last_policy_value(present, "budget"),
        retry=_last_policy_value(present, "retry"),
        loop=_last_policy_value(present, "loop"),
        fanout=_last_policy_value(present, "fanout"),
        timing=_last_policy_value(present, "timing"),
        idempotency=_last_policy_value(present, "idempotency"),
        effects=tuple(
            effect
            for policy in present
            for effect in policy.effects
        ),
        reducers=tuple(
            reducer
            for policy in present
            for reducer in policy.reducers
        ),
        compensation=_last_policy_value(present, "compensation"),
        escalation=_last_policy_value(present, "escalation"),
        control_transitions=tuple(
            transition
            for policy in present
            for transition in policy.control_transitions
        ),
        topology_overlays=tuple(
            overlay
            for policy in present
            for overlay in policy.topology_overlays
        ),
        suspension_routes=tuple(
            route
            for policy in present
            for route in policy.suspension_routes
        ),
        authority=tuple(
            requirement
            for policy in present
            for requirement in policy.authority
        ),
    )


def _last_policy_value(policies: Sequence[WorkflowPolicy], field_name: str) -> Any:
    for policy in reversed(policies):
        value = getattr(policy, field_name)
        if value is not None:
            return value
    return None


def _loop_backedge_bindings(
    loop_block: ParsedLoopBlock,
    lowered_loop: _LoweredSourceBlock,
    *,
    default_condition_ref: str,
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[_LoopBackedgeBinding, ...]:
    if lowered_loop.entry_step_id is None:
        return ()

    diagnostic_count = len(diagnostics)
    step_calls = _step_calls_by_id(loop_block.body)
    explicit_bindings: dict[str, _LoopBackedgeBinding] = {}
    for tail_step_id in lowered_loop.exit_step_ids:
        step_call = step_calls.get(tail_step_id)
        if step_call is None:
            continue
        matches: list[_LoopBackedgeBinding] = []
        for raw_binding in _raw_route_bindings_for_step(step_call, diagnostics):
            if raw_binding is None:
                continue
            target_ref = raw_binding.get("target_ref")
            if target_ref != lowered_loop.entry_step_id:
                continue
            binding_id = raw_binding.get("id")
            label = raw_binding.get("label", "default")
            condition_ref = raw_binding.get("condition_ref", default_condition_ref)
            if (
                not isinstance(binding_id, str)
                or not binding_id
                or not isinstance(label, str)
                or not label
                or not isinstance(condition_ref, str)
                or not condition_ref
            ):
                diagnostics.append(
                    _loop_policy_binding_diagnostic(
                        step_call,
                        "loop backedge route binding metadata must declare string id, label, target_ref, and condition_ref",
                    )
                )
                continue
            matches.append(
                _LoopBackedgeBinding(
                    tail_step_id=tail_step_id,
                    route_id=binding_id,
                    label=label,
                    condition_ref=condition_ref,
                    source_span=step_call.source_span,
                    component_ref=step_call.component_ref,
                )
            )
        if len(matches) > 1:
            diagnostics.append(
                _loop_policy_binding_diagnostic(
                    step_call,
                    "loop backedge route binding metadata is ambiguous for an explicit tail carrier",
                )
            )
        elif len(matches) == 1:
            explicit_bindings[tail_step_id] = matches[0]

    if len(diagnostics) != diagnostic_count:
        return ()
    if not explicit_bindings:
        return ()
    missing_tail_ids = [
        tail_step_id
        for tail_step_id in lowered_loop.exit_step_ids
        if tail_step_id not in explicit_bindings
    ]
    if missing_tail_ids:
        for tail_step_id in missing_tail_ids:
            step_call = step_calls.get(tail_step_id)
            if step_call is not None:
                diagnostics.append(
                    _loop_policy_binding_diagnostic(
                        step_call,
                        "loop backedge route binding metadata is missing for an explicit tail carrier",
                    )
                )
        return ()
    return tuple(explicit_bindings[tail_step_id] for tail_step_id in lowered_loop.exit_step_ids)


def _raw_route_bindings_for_step(
    step_call: ParsedStepCall,
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[Mapping[str, Any] | None, ...]:
    raw_bindings = step_call.component.metadata.get("route_bindings", ())
    if raw_bindings is None:
        return ()
    if not isinstance(raw_bindings, Sequence) or isinstance(raw_bindings, (str, bytes)):
        diagnostics.append(
            _loop_policy_binding_diagnostic(
                step_call,
                "route_bindings metadata must be a sequence of route binding mappings",
            )
        )
        return (None,)
    bindings: list[Mapping[str, Any] | None] = []
    for raw_binding in raw_bindings:
        if isinstance(raw_binding, Mapping):
            bindings.append(raw_binding)
        else:
            diagnostics.append(
                _loop_policy_binding_diagnostic(
                    step_call,
                    "route binding metadata must be a mapping",
                )
            )
            bindings.append(None)
    return tuple(bindings)


def _attach_loop_policy_to_step(
    step: Step,
    policy: ParsedLoopPolicy,
    *,
    carrier_backedges: Mapping[str, _LoopBackedgeBinding],
    fallback_carrier_id: str | None,
    fallback_reentry_id: str,
) -> Step:
    backedge = carrier_backedges.get(step.id)
    if backedge is None:
        if carrier_backedges or fallback_carrier_id is None or step.id != fallback_carrier_id:
            return step
        suspension_route = SuspensionRoute(
            route_id=f"{step.id}-reentry",
            reentry_id=fallback_reentry_id,
        )
    else:
        suspension_route = SuspensionRoute(
            route_id=backedge.condition_ref,
            reentry_id=backedge.condition_ref,
        )
    existing_policy = step.policy
    merged_policy = WorkflowPolicy(
        budget=None if existing_policy is None else existing_policy.budget,
        retry=None if existing_policy is None else existing_policy.retry,
        loop=LoopPolicy(
            max_iterations=policy.max_iterations,
            until_ref=policy.until_ref,
        ),
        fanout=None if existing_policy is None else existing_policy.fanout,
        timing=None if existing_policy is None else existing_policy.timing,
        idempotency=None if existing_policy is None else existing_policy.idempotency,
        effects=() if existing_policy is None else existing_policy.effects,
        reducers=() if existing_policy is None else existing_policy.reducers,
        compensation=None if existing_policy is None else existing_policy.compensation,
        escalation=None if existing_policy is None else existing_policy.escalation,
        control_transitions=(
            () if existing_policy is None else existing_policy.control_transitions
        ),
        topology_overlays=(
            () if existing_policy is None else existing_policy.topology_overlays
        ),
        authority=() if existing_policy is None else existing_policy.authority,
        suspension_routes=(
            (() if existing_policy is None else existing_policy.suspension_routes)
            + (suspension_route,)
        ),
    )
    if existing_policy is not None and existing_policy.loop is not None:
        return step
    return replace(step, policy=merged_policy)


def _loop_backedge_condition_ref(policy: ParsedLoopPolicy) -> str:
    policy_name = policy.policy_ref.rsplit(":", 1)[-1]
    return f"loop:{policy_name}:reentry:{policy.reentry_id}"


def _loop_backedge_route(
    loop: ParsedLoopBlock,
    *,
    source_id: str,
    target_id: str,
    label: str,
    condition_ref: str,
    source_form: str,
    route_id: str | None = None,
) -> Route:
    return Route(
        id=route_id or f"{source_id}-{target_id}",
        source=source_id,
        target=target_id,
        label=label,
        condition_ref=condition_ref,
        source_span=loop.source_span,
        metadata={
            "source_form": source_form,
            "loop_policy_ref": loop.policy.policy_ref,
        },
    )


def _default_route(
    source_id: str,
    target_id: str,
    source_span: SourceSpan,
    source_form: str,
) -> Route:
    return Route(
        id=f"{source_id}-{target_id}",
        source=source_id,
        target=target_id,
        source_span=source_span,
        metadata={"source_form": source_form},
    )


def _bind_route_metadata(
    routes: Sequence[Route],
    block: ParsedSourceBlock,
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[Route, ...]:
    step_calls = _step_calls_by_id(block)
    routes_by_visible_key: dict[tuple[str, str, str], list[Route]] = {}
    for route in routes:
        routes_by_visible_key.setdefault((route.source, route.target, route.label), []).append(route)

    replacements: dict[tuple[str, str, str], Route] = {}
    bound_route_ids: dict[str, tuple[str, str, str]] = {}
    for step_id, step_call in step_calls.items():
        raw_bindings = step_call.component.metadata.get("route_bindings", ())
        if raw_bindings is None:
            continue
        if not isinstance(raw_bindings, Sequence) or isinstance(raw_bindings, (str, bytes)):
            diagnostics.append(
                _route_metadata_diagnostic(
                    step_call,
                    "route_bindings metadata must be a sequence of route binding mappings",
                )
            )
            continue
        seen_keys: set[tuple[str, str, str]] = set()
        for raw_binding in raw_bindings:
            if not isinstance(raw_binding, Mapping):
                diagnostics.append(
                    _route_metadata_diagnostic(
                        step_call,
                        "route binding metadata must be a mapping",
                    )
                )
                continue
            binding_id = raw_binding.get("id")
            target_ref = raw_binding.get("target_ref")
            label = raw_binding.get("label", "default")
            condition_ref = raw_binding.get("condition_ref")
            if (
                not isinstance(binding_id, str)
                or not binding_id
                or not isinstance(target_ref, str)
                or not target_ref
                or not isinstance(label, str)
                or not label
                or (condition_ref is not None and not isinstance(condition_ref, str))
            ):
                diagnostics.append(
                    _route_metadata_diagnostic(
                        step_call,
                        "route binding metadata must declare string id, target_ref, label, and condition_ref",
                    )
                )
                continue

            visible_key = (step_id, target_ref, label)
            matching_routes = routes_by_visible_key.get(visible_key, [])
            if visible_key in seen_keys or len(matching_routes) > 1:
                diagnostics.append(
                    _route_metadata_diagnostic(
                        step_call,
                        "route binding metadata is ambiguous for a visible lowered route",
                    )
                )
                continue
            seen_keys.add(visible_key)
            if not matching_routes:
                diagnostics.append(
                    _route_metadata_diagnostic(
                        step_call,
                        "route binding metadata does not match a visible lowered route",
                    )
                )
                continue
            existing_key = bound_route_ids.get(binding_id)
            if existing_key is not None and existing_key != visible_key:
                diagnostics.append(
                    _route_metadata_diagnostic(
                        step_call,
                        "route binding metadata reuses a canonical route id",
                    )
                )
                continue
            bound_route_ids[binding_id] = visible_key
            route = matching_routes[0]
            replacements[visible_key] = replace(
                route,
                id=binding_id,
                condition_ref=condition_ref,
            )

    if diagnostics:
        return tuple(routes)
    return tuple(replacements.get((route.source, route.target, route.label), route) for route in routes)


def _step_calls_by_id(block: ParsedSourceBlock) -> dict[str, ParsedStepCall]:
    step_calls: dict[str, ParsedStepCall] = {}
    for statement in block.statements:
        if isinstance(statement, ParsedStepCall):
            step_calls[statement.id] = statement
        elif isinstance(statement, ParsedBranchBlock):
            for arm in statement.arms:
                step_calls.update(_step_calls_by_id(arm.body))
        elif isinstance(statement, ParsedLoopBlock):
            step_calls.update(_step_calls_by_id(statement.body))
    return step_calls


def _route_metadata_diagnostic(step: ParsedStepCall, message: str) -> AuthoringDiagnostic:
    return _diagnostic(
        DiagnosticCode.ROUTE_METADATA_MISMATCH,
        message,
        source_span=step.source_span,
        component_ref=step.component_ref,
    )


def _loop_policy_binding_diagnostic(
    step: ParsedStepCall,
    message: str,
) -> AuthoringDiagnostic:
    return _diagnostic(
        DiagnosticCode.LOOP_POLICY_BINDING_MISMATCH,
        message,
        source_span=step.source_span,
        component_ref=step.component_ref,
    )


def _branch_route(
    branch: ParsedBranchBlock,
    arm: ParsedBranchArm,
    *,
    source_id: str,
    target_id: str,
    source_form: str,
) -> Route:
    if arm.condition is None:
        label = "else"
        condition_ref = f"{source_id}.{branch.decision_output}.else"
    else:
        label = arm.condition.literal
        condition_ref = f"{source_id}.{branch.decision_output}.eq.{arm.condition.literal}"
    return Route(
        id=f"{source_id}-{target_id}",
        source=source_id,
        target=target_id,
        label=label,
        condition_ref=condition_ref,
        source_span=arm.source_span,
        metadata={"source_form": source_form},
    )


def _lower_workflow_policy(intrinsics: Sequence[IntrinsicCall]) -> WorkflowPolicy | None:
    if not intrinsics:
        return None
    control_transitions: list[ControlTransitionSlot] = []
    suspension_routes: list[SuspensionRoute] = []
    for intrinsic in intrinsics:
        args = intrinsic.arguments
        if intrinsic.name == "suspend":
            suspension_routes.append(
                SuspensionRoute(
                    route_id=args["route_id"],
                    capability_id=args.get("capability_id"),
                    reentry_id=args.get("reentry_id"),
                    payload_schema_hash=args.get("payload_schema_hash"),
                    resume_schema_hash=args.get("resume_schema_hash"),
                    resume_schema_ref=args.get("resume_schema_ref"),
                    resume_payload_ref=args.get("resume_payload_ref"),
                )
            )
        else:
            control_transitions.append(
                ControlTransitionSlot(
                    transition_id=args["id"],
                    transition_type="halt" if intrinsic.name == "halt" else args["type"],
                    trigger_ref=args.get("trigger_ref"),
                    target_ref=args.get("target_ref"),
                    payload_schema_hash=args.get("payload_schema_hash"),
                    policy_ref=args.get("policy_ref"),
                )
            )
    return WorkflowPolicy(
        control_transitions=tuple(control_transitions),
        suspension_routes=tuple(suspension_routes),
    )


def _keyword(call: ast.Call, name: str) -> ast.keyword | None:
    return next((keyword for keyword in call.keywords if keyword.arg == name), None)


def _string_keyword(call: ast.Call, name: str) -> str | None:
    keyword = _keyword(call, name)
    if (
        keyword is None
        or not isinstance(keyword.value, ast.Constant)
        or not isinstance(keyword.value.value, str)
    ):
        return None
    return keyword.value.value


def _validated_string_ref_keyword(
    call: ast.Call,
    keyword: ast.keyword | None,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
    *,
    code: DiagnosticCode,
    missing_message: str,
    invalid_message: str,
    component_ref: str | None = None,
) -> str | None:
    if keyword is None or not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
        diagnostics.append(
            _diagnostic(
                code,
                missing_message,
                source_span=source_span_for_node(source_path, call),
                component_ref=component_ref,
            )
        )
        return None
    value = keyword.value.value
    if is_ref(value):
        return value
    diagnostics.append(
        _diagnostic(
            code,
            invalid_message,
            source_span=source_span_for_node(source_path, keyword),
            component_ref=component_ref,
            details={"value": value},
        )
    )
    return None


def _is_workflow_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    binding = imports.get(node.func.id)
    return (
        binding is not None
        and binding.kind == "intrinsic"
        and binding.import_ref.module == AUTHORING_INTRINSIC_MODULE
        and binding.import_ref.qualname == "workflow"
        and binding.local_name == "workflow"
    ) or (
        binding is not None
        and binding.import_ref.module == "arnold.pipeline"
        and binding.import_ref.qualname == "workflow"
        and binding.local_name == "workflow"
    )


def _is_native_workflow_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    binding = imports.get(node.func.id)
    return (
        binding is not None
        and binding.import_ref.module == "arnold.pipeline"
        and binding.import_ref.qualname == "workflow"
        and binding.local_name == "workflow"
    )


def _is_native_parallel_map_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    binding = imports.get(node.func.id)
    return (
        binding is not None
        and binding.import_ref.module == "arnold.pipeline"
        and binding.import_ref.qualname == "parallel_map"
        and binding.local_name == "parallel_map"
    )


def _contains_dynamic_import(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and (
            (isinstance(child.func, ast.Name) and child.func.id == "__import__")
            or (
                isinstance(child.func, ast.Attribute)
                and child.func.attr == "import_module"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "importlib"
            )
        )
        for child in ast.walk(node)
    )


def _contains_manual_graph_authoring(node: ast.AST) -> bool:
    names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
    return bool({"Pipeline", "Stage", "Edge"} & names)


def _contains_native_program_projection(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.ImportFrom)
        and child.module == "arnold.pipeline.native.ir"
        and any(alias.name == "NativeProgram" for alias in child.names)
        for child in ast.walk(node)
    )


def _contains_megaplan_only_helper(node: ast.AST) -> bool:
    return any(isinstance(child, ast.AsyncFunctionDef) for child in ast.walk(node))


def _contains_manual_path_construction(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.JoinedStr):
            return True
        if (
            isinstance(child, ast.BinOp)
            and isinstance(child.op, ast.Add)
            and (
                _stringy_path_operand(child.left)
                or _stringy_path_operand(child.right)
            )
        ):
            return True
    return False


def _stringy_path_operand(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "/" in node.value
    )


def _try_import_ref(module: str, qualname: str) -> ImportRef | None:
    try:
        return ImportRef(module=module, qualname=qualname)
    except ValueError:
        return None


def _absolute_module_name(statement: ast.ImportFrom, source_path: str) -> str:
    if statement.level == 0:
        return statement.module or ""
    package_parts = _package_parts_for_source_path(source_path)
    if statement.level > 1:
        package_parts = package_parts[: 1 - statement.level]
    module_parts = tuple(part for part in package_parts if part not in {"", "."})
    if statement.module:
        module_parts = (*module_parts, *statement.module.split("."))
    return ".".join(module_parts)


def _package_parts_for_source_path(source_path: str) -> tuple[str, ...]:
    path = Path(source_path)
    if not path.is_absolute():
        return path.with_suffix("").parts[:-1]
    resolved = path.resolve()
    search_roots = [Path.cwd(), *(Path(entry or ".") for entry in sys.path)]
    for root in search_roots:
        try:
            relative = resolved.with_suffix("").relative_to(root.resolve())
        except ValueError:
            continue
        return relative.parts[:-1]
    return resolved.with_suffix("").parts[:-1]


def _coerce_source_path(source_path: str | Path | None) -> str:
    if source_path is None:
        return _DEFAULT_SOURCE_PATH
    return Path(source_path).as_posix()


def _diagnostic(
    code: DiagnosticCode,
    message: str,
    *,
    source_span: SourceSpan,
    import_ref: ImportRef | None = None,
    component_ref: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> AuthoringDiagnostic:
    spec = diagnostic_spec(code)
    return AuthoringDiagnostic(
        code=code,
        message=message,
        severity=DiagnosticSeverity.ERROR,
        source_span=source_span,
        import_ref=import_ref,
        component_ref=component_ref,
        remediation=spec.remediation,
        details={} if details is None else details,
    )


__all__ = [
    "CheckWorkflowSourceResult",
    "CompileWorkflowSourceResult",
    "_SUPPORTED_SOURCE_SUFFIXES",
    "ComponentResolver",
    "ImportBinding",
    "LowerWorkflowSourceResult",
    "ParsedBranchArm",
    "ParsedBranchBlock",
    "ParsedBranchCondition",
    "ParsedIntrinsicCall",
    "ParsedLoopBlock",
    "ParsedLoopPolicy",
    "ParsedParallelMapCall",
    "ParsedSourceBlock",
    "ParsedSourceStatement",
    "ParsedStepCall",
    "ParsedSubflowCall",
    "ParsedUnsupportedStatement",
    "ParsedWorkflowSource",
    "SourceCompilationError",
    "SourceCompileError",
    "SourceScope",
    "StaticComponentResolver",
    "StepCall",
    "StepInputBinding",
    "StepOutputBinding",
    "SubflowCall",
    "WorkflowDeclaration",
    "check_workflow_file",
    "check_workflow_source",
    "compile_workflow_file",
    "compile_workflow_source",
    "lower_workflow_file",
    "lower_workflow_source",
    "parse_workflow_source",
    "source_span_for_node",
]
