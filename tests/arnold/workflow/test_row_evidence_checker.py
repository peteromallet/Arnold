"""Focused tests for the S2 row-evidence checker rule (T2).

These tests verify that ``check_workflow_source`` emits
``AWF245_ROW_EVIDENCE_INSUFFICIENCY`` whenever an implemented front-half
row (prep / plan / critique / gate / revise) lacks structured semantic
evidence, and that the API / serialization contracts hold.
"""

from __future__ import annotations

import json
from pathlib import Path

import arnold.workflow as workflow
from arnold.manifest.refs import SourceSpan
from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryOutcome, BoundaryReceipt
from arnold.workflow import check_workflow_source
from arnold.workflow.diagnostics import DiagnosticCode
from arnold.workflow.semantic_evidence import (
    ConstructType,
    S2_CRITIQUE_ROW_ID,
    S2_GATE_ROW_ID,
    S2_PLAN_ROW_ID,
    S2_PREP_ROW_ID,
    S2_REVISE_ROW_ID,
    S3_TIEBREAKER_RESEARCHER_ROW_ID,
    S3_TIEBREAKER_CHALLENGER_ROW_ID,
    S3_TIEBREAKER_SYNTHESIS_ROW_ID,
    S3_TIEBREAKER_DECISION_ROW_ID,
    S4_EXECUTE_ROW_ID,
    SemanticEvidence,
)
from arnold_pipelines.megaplan.workflows import planning
import arnold.workflow.source_compiler as source_compiler

M3_FIXTURE_DIR = Path("tests/fixtures/workflow_authoring/m3")

# ── minimal source templates ────────────────────────────────────────────────

_SOURCE_TEMPLATE = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    SOURCE_PREP,
    SOURCE_PLAN,
    SOURCE_CRITIQUE,
    SOURCE_GATE,
    SOURCE_REVISE,
)

@workflow(id="test", version="s2")
def test_flow(brief: str) -> None:
    prep_signal = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_signal)
"""

# ── helpers ─────────────────────────────────────────────────────────────────


def _evidence_for(row_id: str, *, code: DiagnosticCode | None = None) -> SemanticEvidence:
    return SemanticEvidence(
        diagnostic_code=code or DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
        source_span=SourceSpan("test.pypeline", 1, 1, 1, 10),
        construct_type=ConstructType.PREP,
        row_id=row_id,
    )


def _load_m3_sidecar(case_name: str) -> dict[str, object]:
    with (M3_FIXTURE_DIR / f"{case_name}.expected.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _diagnostic_payloads(result: object) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for diagnostic in result.diagnostics:
        payload: dict[str, object] = {
            "code": diagnostic.code.value,
            "message": diagnostic.message,
        }
        if diagnostic.import_ref is not None:
            payload["import_ref"] = {
                "module": diagnostic.import_ref.module,
                "qualname": diagnostic.import_ref.qualname,
            }
        if diagnostic.component_ref is not None:
            payload["component_ref"] = diagnostic.component_ref
        if diagnostic.source_span is not None:
            payload["source_span"] = {
                "path": diagnostic.source_span.path,
                "start_line": diagnostic.source_span.start_line,
                "start_column": diagnostic.source_span.start_column,
                "end_line": diagnostic.source_span.end_line,
                "end_column": diagnostic.source_span.end_column,
            }
        payloads.append(payload)
    return payloads


def _run_s5_fixture(case_name: str):
    source_path = M3_FIXTURE_DIR / f"{case_name}.py"
    original_topology_contract = source_compiler._megaplan_review_topology_contract
    original_route_surface = source_compiler._megaplan_policy_route_surface
    try:
        if case_name == "invalid_m3_handler_owned_review_cap":
            source_compiler._megaplan_review_topology_contract = lambda: {
                "retry_and_cap": {"cap_thresholds": {"max_review_rework_cycles": 1}},
            }
        elif case_name == "invalid_m3_hidden_finalize_fallback":
            source_compiler._megaplan_policy_route_surface = (
                lambda export_name: {}
                if export_name == "FINALIZE_POLICY"
                else original_route_surface(export_name)
            )
        return workflow.check_workflow_file(source_path)
    finally:
        source_compiler._megaplan_review_topology_contract = original_topology_contract
        source_compiler._megaplan_policy_route_surface = original_route_surface


def _receipt_for_contract(boundary_contract) -> BoundaryReceipt:
    authority_records = ()
    if boundary_contract.authority_required:
        authority_records = (
            AuthorityRecord(actor="review-policy", role="authority"),
        )
    return BoundaryReceipt(
        boundary_id=boundary_contract.boundary_id,
        workflow_id=boundary_contract.workflow_id,
        row_id=boundary_contract.row_id,
        artifact_refs=boundary_contract.required_artifacts,
        state_observation=boundary_contract.expected_state_delta,
        outcome=BoundaryOutcome.COMPLETE,
        history_ref=boundary_contract.expected_history_entry,
        phase_result_ref=(
            f"phase/{boundary_contract.boundary_id}.json"
            if boundary_contract.phase_result_required
            else None
        ),
        authority_records=authority_records,
    )


# ── core checker rule tests ─────────────────────────────────────────────────


def test_front_half_rows_without_evidence_produce_awf245() -> None:
    """A source with implemented prep + plan steps but no evidence must
    produce AWF245 for every front-half row that lacks evidence."""
    result = check_workflow_source(_SOURCE_TEMPLATE, source_path="test.pypeline")

    assert not result.ok
    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY in diag_codes

    # Both prep and plan should trigger the diagnostic.
    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]
    assert len(awf245_diags) == 2  # prep + plan

    missing_row_ids = {
        S2_PREP_ROW_ID,
        S2_PLAN_ROW_ID,
    }
    for diag in awf245_diags:
        assert any(row_id in diag.message for row_id in missing_row_ids)


def test_front_half_rows_with_evidence_pass() -> None:
    """When every implemented front-half row has a matching evidence record
    the checker must not emit AWF245."""
    evidence = (
        _evidence_for(S2_PREP_ROW_ID, code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY),
        _evidence_for(S2_PLAN_ROW_ID, code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY),
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE, source_path="test.pypeline", evidence=evidence,
    )

    # Should be OK (no parse errors in this simple source, and evidence covers
    # both front-half rows).
    assert result.ok
    assert result.evidence == evidence


def test_partial_evidence_flags_missing_rows_only() -> None:
    """Evidence covering only some front-half rows must flag only the
    uncovered rows."""
    evidence = (_evidence_for(S2_PREP_ROW_ID),)
    result = check_workflow_source(
        _SOURCE_TEMPLATE, source_path="test.pypeline", evidence=evidence,
    )

    assert not result.ok
    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]
    assert len(awf245_diags) == 1  # only plan is missing
    assert S2_PLAN_ROW_ID in awf245_diags[0].message
    assert S2_PREP_ROW_ID not in awf245_diags[0].message


def test_no_front_half_rows_passes_without_evidence() -> None:
    """A source with no S2 front-half constructs must pass even when no
    evidence is supplied (no false positives)."""
    source = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_EXECUTE

@workflow(id="plain", version="s2")
def plain_flow(brief: str) -> None:
    SOURCE_EXECUTE(id="run", brief=brief)
"""
    result = check_workflow_source(source, source_path="plain.pypeline")
    assert result.ok


def test_evidence_alone_cannot_create_missing_front_half_rows() -> None:
    """Supplying row evidence for an unrelated source must not create
    AWF245 rows that are absent from parsed topology."""
    source = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_EXECUTE

@workflow(id="plain", version="s2")
def plain_flow(brief: str) -> None:
    SOURCE_EXECUTE(id="run", brief=brief)
"""
    evidence = (
        _evidence_for(S2_PREP_ROW_ID),
        _evidence_for(S2_PLAN_ROW_ID),
        _evidence_for(S2_CRITIQUE_ROW_ID),
        _evidence_for(S2_GATE_ROW_ID),
        _evidence_for(S2_REVISE_ROW_ID),
    )

    result = check_workflow_source(
        source,
        source_path="plain.pypeline",
        evidence=evidence,
    )

    assert result.ok
    assert result.evidence == evidence


def test_canonical_authoring_components_emit_awf245_for_unique_front_half_rows() -> None:
    """The canonical AUTHORING_* source must detect prep/plan/critique/gate/revise
    plus the four S3 tiebreaker phases exactly once each, including critique via the
    reducer call and repeated revise call sites."""
    result = check_workflow_source(
        planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"),
        source_path=planning.AUTHORING_SOURCE_PATH,
    )

    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]

    assert len(awf245_diags) == 9  # 5 S2 + 4 S3
    assert {
        diag.details["row_id"] for diag in awf245_diags
    } == {
        S2_PREP_ROW_ID,
        S2_PLAN_ROW_ID,
        S2_CRITIQUE_ROW_ID,
        S2_GATE_ROW_ID,
        S2_REVISE_ROW_ID,
        S3_TIEBREAKER_RESEARCHER_ROW_ID,
        S3_TIEBREAKER_CHALLENGER_ROW_ID,
        S3_TIEBREAKER_SYNTHESIS_ROW_ID,
        S3_TIEBREAKER_DECISION_ROW_ID,
    }
    assert any(diag.component_ref and "AUTHORING_CRITIQUE" in diag.component_ref for diag in awf245_diags)
    assert any(diag.component_ref and "AUTHORING_REVISE" in diag.component_ref for diag in awf245_diags)
    assert any(diag.component_ref and "TIEBREAKER_RESEARCHER" in diag.component_ref for diag in awf245_diags)
    assert any(diag.component_ref and "TIEBREAKER_DECISION" in diag.component_ref for diag in awf245_diags)


# ── API / serialization behaviour ───────────────────────────────────────────


def test_evidence_is_preserved_in_result() -> None:
    """Evidence records passed to check_workflow_source must be preserved
    in the result carrier without modification."""
    evidence = (
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("src.pypeline", 10, 1, 10, 20),
            construct_type=ConstructType.GATE,
            row_id=S2_GATE_ROW_ID,
        ),
    )
    result = check_workflow_source(
        "from arnold.workflow.authoring import workflow\n"
        "@workflow(id='x', version='1')\n"
        "def f(): pass\n",
        source_path="src.pypeline",
        evidence=evidence,
    )
    assert result.evidence == evidence
    assert len(result.evidence) == 1
    assert result.evidence[0].row_id == S2_GATE_ROW_ID


def test_evidence_to_dict_round_trip_for_checker_output() -> None:
    """Evidence records attached to a checker result must round-trip
    through to_dict() without losing row identity or construct type."""
    evidence = (
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("checker_test.pypeline", 5, 1, 5, 15),
            construct_type=ConstructType.CRITIQUE,
            row_id=S2_CRITIQUE_ROW_ID,
        ),
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("checker_test.pypeline", 7, 1, 7, 15),
            construct_type=ConstructType.REVISE,
            row_id=S2_REVISE_ROW_ID,
        ),
    )
    result = check_workflow_source(
        "from arnold.workflow.authoring import workflow\n"
        "@workflow(id='x', version='1')\n"
        "def f(): pass\n",
        source_path="checker_test.pypeline",
        evidence=evidence,
    )

    payloads = [e.to_dict() for e in result.evidence]
    assert len(payloads) == 2
    assert payloads[0]["row_id"] == S2_CRITIQUE_ROW_ID
    assert payloads[0]["construct_type"] == "critique"
    assert payloads[1]["row_id"] == S2_REVISE_ROW_ID
    assert payloads[1]["construct_type"] == "revise"


def test_diagnostic_details_include_component_ref() -> None:
    """AWF245 diagnostics must carry the component_ref of the offending
    step so consumers can trace back to the import."""
    result = check_workflow_source(_SOURCE_TEMPLATE, source_path="test.pypeline")
    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]
    assert len(awf245_diags) >= 1
    component_refs = {d.component_ref for d in awf245_diags if d.component_ref}
    assert len(component_refs) >= 1
    # Both prep and plan should have component refs ending with the component name.
    for ref in component_refs:
        assert "SOURCE_PREP" in ref or "SOURCE_PLAN" in ref


def test_check_workflow_file_passes_evidence_through() -> None:
    """check_workflow_file must forward evidence to check_workflow_source
    and produce the same result shape."""
    import tempfile, os

    evidence = (_evidence_for(S2_PREP_ROW_ID), _evidence_for(S2_PLAN_ROW_ID))
    source = _SOURCE_TEMPLATE

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(source)
        tmp_path = tmp.name

    try:
        from arnold.workflow import check_workflow_file

        result = check_workflow_file(tmp_path, evidence=evidence)
        assert result.ok
        assert result.evidence == evidence
    finally:
        os.unlink(tmp_path)


# ── S3 tiebreaker shape violation tests ──────────────────────────────────────

_TIEBREAKER_SOURCE_TEMPLATE = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    TIEBREAKER_RESEARCHER,
    TIEBREAKER_CHALLENGER,
    TIEBREAKER_SYNTHESIS,
    TIEBREAKER_DECISION,
)

@workflow(id="test", version="s3")
def test_flow(brief: str) -> None:
    research_findings = TIEBREAKER_RESEARCHER(
        id="tiebreaker_researcher",
        gate_payload=brief,
    )
    challenge_findings = TIEBREAKER_CHALLENGER(
        id="tiebreaker_challenger",
        research_findings=research_findings,
    )
    tiebreaker_payload = TIEBREAKER_SYNTHESIS(
        id="tiebreaker_synthesis",
        research_findings=research_findings,
        challenge_findings=challenge_findings,
    )
    decision = TIEBREAKER_DECISION(
        id="tiebreaker_decision",
        tiebreaker_payload=tiebreaker_payload,
    )
"""


def test_full_tiebreaker_shape_passes_without_awf252() -> None:
    """A source with all four tiebreaker phases visible must not emit AWF252."""
    result = check_workflow_source(
        _TIEBREAKER_SOURCE_TEMPLATE, source_path="test_full_tb.pypeline",
    )

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) == 0, (
        f"expected 0 AWF252 diagnostics, got {len(awf252_diags)}"
    )


def test_partial_tiebreaker_shape_produces_awf252() -> None:
    """A source with only some tiebreaker phases must emit AWF252 for each
    missing phase."""
    source = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    TIEBREAKER_RESEARCHER,
    TIEBREAKER_DECISION,
)

@workflow(id="test", version="s3")
def test_flow(brief: str) -> None:
    research_findings = TIEBREAKER_RESEARCHER(
        id="tiebreaker_researcher",
        gate_payload=brief,
    )
    decision = TIEBREAKER_DECISION(
        id="tiebreaker_decision",
        tiebreaker_payload=research_findings,
    )
"""
    result = check_workflow_source(source, source_path="test_partial_tb.pypeline")

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) == 2, (
        f"expected 2 AWF252 diagnostics (missing challenger + synthesis), "
        f"got {len(awf252_diags)}"
    )
    missing_phases = {d.details.get("missing_phase") for d in awf252_diags}
    assert missing_phases == {"tiebreaker_challenger", "tiebreaker_synthesis"}, (
        f"unexpected missing phases: {missing_phases}"
    )


def test_no_tiebreaker_phases_produces_no_awf252() -> None:
    """A source with no tiebreaker phases at all must not emit AWF252."""
    source = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    SOURCE_PREP,
)

@workflow(id="test", version="s3")
def test_flow(brief: str) -> None:
    prep_signal = SOURCE_PREP(id="prep", brief=brief)
"""
    result = check_workflow_source(source, source_path="test_no_tb.pypeline")

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) == 0, (
        f"expected 0 AWF252 diagnostics, got {len(awf252_diags)}"
    )


def test_awf252_diagnostic_carries_missing_phase_details() -> None:
    """AWF252 diagnostics must carry missing_row_id, missing_phase, and
    implemented_s3_rows in details."""
    source = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    TIEBREAKER_RESEARCHER,
)

@workflow(id="test", version="s3")
def test_flow(brief: str) -> None:
    research_findings = TIEBREAKER_RESEARCHER(
        id="tiebreaker_researcher",
        gate_payload=brief,
    )
"""
    result = check_workflow_source(source, source_path="test_one_tb.pypeline")

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) == 3  # missing challenger, synthesis, decision

    for diag in awf252_diags:
        assert "missing_row_id" in diag.details
        assert "missing_phase" in diag.details
        assert "implemented_s3_rows" in diag.details
        assert diag.details["missing_row_id"].startswith("s3.")
        assert diag.details["missing_phase"].startswith("tiebreaker_")
        assert "s3.tiebreaker_researcher.1" in diag.details["implemented_s3_rows"]


# ── S4 execute evidence visibility ──────────────────────────────────────────
# Prove that S4 execute row IDs, construct types, and boundary phases are
# registered and visible to the semantic checker without false positives.


_EXECUTE_SOURCE_TEMPLATE = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_EXECUTE

@workflow(id="test", version="s4")
def test_flow(brief: str) -> None:
    SOURCE_EXECUTE(id="run", brief=brief)
"""


def test_execute_row_evidence_preserved_in_result() -> None:
    """SemanticEvidence with S4_EXECUTE_ROW_ID and ConstructType.EXECUTE must
    be preserved in the checker result carrier without modification."""
    evidence = (
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 10, 1, 10, 20),
            construct_type=ConstructType.EXECUTE,
            row_id=S4_EXECUTE_ROW_ID,
        ),
    )
    result = check_workflow_source(
        _EXECUTE_SOURCE_TEMPLATE,
        source_path="test.pypeline",
        evidence=evidence,
    )
    assert result.evidence == evidence
    assert len(result.evidence) == 1
    assert result.evidence[0].row_id == S4_EXECUTE_ROW_ID
    assert result.evidence[0].construct_type == ConstructType.EXECUTE


def test_execute_row_evidence_to_dict_round_trip() -> None:
    """S4 execute evidence records must round-trip through to_dict()
    without losing row identity or construct type."""
    evidence = (
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 5, 1, 5, 15),
            construct_type=ConstructType.EXECUTE,
            row_id=S4_EXECUTE_ROW_ID,
        ),
    )
    result = check_workflow_source(
        _EXECUTE_SOURCE_TEMPLATE,
        source_path="test.pypeline",
        evidence=evidence,
    )
    payloads = [e.to_dict() for e in result.evidence]
    assert len(payloads) == 1
    assert payloads[0]["row_id"] == S4_EXECUTE_ROW_ID
    assert payloads[0]["construct_type"] == "execute"


def test_execute_without_boundary_contract_does_not_produce_awf245() -> None:
    """An execute-only source without evidence must NOT produce AWF245
    for the execute row — execute is not a front-half row until a boundary
    contract is registered for it."""
    result = check_workflow_source(
        _EXECUTE_SOURCE_TEMPLATE, source_path="test.pypeline",
    )
    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]
    assert len(awf245_diags) == 0, (
        f"expected 0 AWF245 for execute-only source, got {len(awf245_diags)}"
    )
    assert result.ok


def test_execute_evidence_alone_cannot_create_missing_rows() -> None:
    """Supplying execute row evidence must not create AWF245 rows that are
    absent from parsed topology."""
    source = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_EXECUTE

@workflow(id="plain", version="s4")
def plain_flow(brief: str) -> None:
    SOURCE_EXECUTE(id="run", brief=brief)
"""
    evidence = (
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 1, 1, 1, 10),
            construct_type=ConstructType.EXECUTE,
            row_id=S4_EXECUTE_ROW_ID,
        ),
    )
    result = check_workflow_source(
        source,
        source_path="test.pypeline",
        evidence=evidence,
    )
    assert result.ok
    assert result.evidence == evidence


def test_execute_and_front_half_evidence_coexist() -> None:
    """When both S2 front-half and S4 execute evidence are passed, the
    checker must preserve all evidence and only flag uncovered front-half rows."""
    evidence = (
        _evidence_for(S2_PREP_ROW_ID, code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY),
        _evidence_for(S2_PLAN_ROW_ID, code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY),
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 3, 1, 3, 15),
            construct_type=ConstructType.EXECUTE,
            row_id=S4_EXECUTE_ROW_ID,
        ),
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE, source_path="test.pypeline", evidence=evidence,
    )
    assert result.ok
    assert len(result.evidence) == 3
    row_ids = {e.row_id for e in result.evidence}
    assert S4_EXECUTE_ROW_ID in row_ids
    assert S2_PREP_ROW_ID in row_ids
    assert S2_PLAN_ROW_ID in row_ids


# ── S3 negative tests: old single-call wrapper ───────────────────────────────
# Prove that boundary receipts and semantic-health findings cannot compensate
# for missing source-visible tiebreaker topology.


# Old-wrapper source: uses SOURCE_TIEBREAKER_WORKFLOW as a single subworkflow
# call instead of four individually authored step calls.
_OLD_WRAPPER_SOURCE = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    SOURCE_TIEBREAKER_WORKFLOW,
)

@workflow(id="test", version="s3")
def test_flow(brief: str) -> None:
    decision = SOURCE_TIEBREAKER_WORKFLOW(
        id="tiebreaker_child",
        gate_payload=brief,
    )
"""


def _make_boundary_receipt(boundary_id: str, row_id: str) -> "BoundaryReceipt":
    """Construct a minimal valid boundary receipt for a single S3 tiebreaker phase."""
    from arnold.workflow.boundary_evidence import (
        BoundaryOutcome,
        BoundaryReceipt,
    )
    return BoundaryReceipt(
        boundary_id=boundary_id,
        workflow_id="megaplan-review",
        row_id=row_id,
        invocation_id=f"inv-{boundary_id}",
        artifact_refs=(f"{boundary_id}_artifact.json",),
        phase_result_ref=f"phase_result_{boundary_id}",
        outcome=BoundaryOutcome.COMPLETE,
    )


def _make_semantic_finding(
    finding_id: str,
    boundary_id: str,
    description: str,
) -> "SemanticFinding":
    """Construct a minimal semantic-health finding."""
    from arnold.workflow.boundary_evidence import (
        FindingSeverity,
        SemanticFinding,
    )
    return SemanticFinding(
        finding_id=finding_id,
        boundary_id=boundary_id,
        description=description,
        severity=FindingSeverity.INFO,
    )


# Boundary receipts for all four S3 tiebreaker phases.
_S3_BOUNDARY_RECEIPTS = (
    _make_boundary_receipt(
        "tiebreaker_researcher_to_challenger",
        S3_TIEBREAKER_RESEARCHER_ROW_ID,
    ),
    _make_boundary_receipt(
        "tiebreaker_challenger_to_synthesis",
        S3_TIEBREAKER_CHALLENGER_ROW_ID,
    ),
    _make_boundary_receipt(
        "tiebreaker_synthesis_to_decision",
        S3_TIEBREAKER_SYNTHESIS_ROW_ID,
    ),
    _make_boundary_receipt(
        "tiebreaker_decision_to_parent",
        S3_TIEBREAKER_DECISION_ROW_ID,
    ),
)

# Semantic-health findings for all four S3 tiebreaker phases.
_S3_SEMANTIC_FINDINGS = (
    _make_semantic_finding(
        "find-researcher",
        "tiebreaker_researcher_to_challenger",
        "Researcher boundary healthy: research_findings.json present and coherent",
    ),
    _make_semantic_finding(
        "find-challenger",
        "tiebreaker_challenger_to_synthesis",
        "Challenger boundary healthy: challenge_findings.json present and coherent",
    ),
    _make_semantic_finding(
        "find-synthesis",
        "tiebreaker_synthesis_to_decision",
        "Synthesis boundary healthy: tiebreaker_payload.json present and coherent",
    ),
    _make_semantic_finding(
        "find-decision",
        "tiebreaker_decision_to_parent",
        "Decision boundary healthy: tiebreaker_decisions.json present and coherent",
    ),
)


def test_old_wrapper_fails_even_with_boundary_receipts() -> None:
    """A source using SOURCE_TIEBREAKER_WORKFLOW as a single-call wrapper must
    emit AWF252 even when boundary receipts exist for all four S3 tiebreaker
    phases.  Boundary evidence cannot create or substitute for source-visible
    step topology."""
    from arnold_pipelines.megaplan.workflows.boundary_contracts import (
        BOUNDARY_CONTRACTS as _ALL_CONTRACTS,
    )
    # Only S3 contracts so we don't trigger unrelated boundary diagnostics.
    s3_contracts = tuple(
        c for c in _ALL_CONTRACTS
        if c.row_id and c.row_id.startswith("s3.")
    )

    result = check_workflow_source(
        _OLD_WRAPPER_SOURCE,
        source_path="test_old_wrapper.pypeline",
        boundary_contracts=s3_contracts,
        boundary_evidence=_S3_BOUNDARY_RECEIPTS,
    )

    # Must not be OK — the old wrapper is a shape violation.
    assert not result.ok, (
        "expected failure for old single-call wrapper, but result.ok is True"
    )

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) >= 1, (
        "expected at least 1 AWF252 diagnostic for old single-call wrapper, "
        f"got {len(awf252_diags)}"
    )

    # The diagnostic must reference the old wrapper component.
    wrapper_diag = awf252_diags[0]
    assert "SOURCE_TIEBREAKER_WORKFLOW" in (wrapper_diag.component_ref or ""), (
        f"expected AWF252 to reference SOURCE_TIEBREAKER_WORKFLOW, "
        f"got {wrapper_diag.component_ref!r}"
    )
    assert "missing_phases" in wrapper_diag.details, (
        "expected 'missing_phases' in AWF252 details"
    )
    assert len(wrapper_diag.details["missing_phases"]) == 4, (
        "expected all 4 S3 phases listed as missing"
    )


def test_old_wrapper_fails_even_with_semantic_findings() -> None:
    """A source using SOURCE_TIEBREAKER_WORKFLOW as a single-call wrapper must
    emit AWF252 even when semantic-health findings claim all four S3 boundaries
    are healthy.  Semantic findings cannot create or substitute for source-visible
    step topology."""
    from arnold_pipelines.megaplan.workflows.boundary_contracts import (
        BOUNDARY_CONTRACTS as _ALL_CONTRACTS,
    )
    s3_contracts = tuple(
        c for c in _ALL_CONTRACTS
        if c.row_id and c.row_id.startswith("s3.")
    )

    result = check_workflow_source(
        _OLD_WRAPPER_SOURCE,
        source_path="test_old_wrapper.pypeline",
        boundary_contracts=s3_contracts,
        boundary_evidence=_S3_SEMANTIC_FINDINGS,
    )

    assert not result.ok, (
        "expected failure for old single-call wrapper, but result.ok is True"
    )

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) >= 1, (
        "expected at least 1 AWF252 diagnostic for old single-call wrapper "
        "with semantic findings, got 0"
    )
    assert "SOURCE_TIEBREAKER_WORKFLOW" in (awf252_diags[0].component_ref or "")


def test_old_wrapper_fails_even_with_both_receipts_and_findings() -> None:
    """Even when both boundary receipts AND semantic-health findings are present
    for every S3 tiebreaker phase, the old SOURCE_TIEBREAKER_WORKFLOW single-call
    wrapper must still emit AWF252.  No combination of boundary/semantic evidence
    can compensate for missing source-visible topology."""
    from arnold_pipelines.megaplan.workflows.boundary_contracts import (
        BOUNDARY_CONTRACTS as _ALL_CONTRACTS,
    )
    s3_contracts = tuple(
        c for c in _ALL_CONTRACTS
        if c.row_id and c.row_id.startswith("s3.")
    )

    # Combine receipts and findings.
    combined_evidence = (*_S3_BOUNDARY_RECEIPTS, *_S3_SEMANTIC_FINDINGS)

    result = check_workflow_source(
        _OLD_WRAPPER_SOURCE,
        source_path="test_old_wrapper.pypeline",
        boundary_contracts=s3_contracts,
        boundary_evidence=combined_evidence,
    )

    assert not result.ok, (
        "expected failure for old single-call wrapper even with full boundary "
        "receipts + semantic findings, but result.ok is True"
    )

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) >= 1, (
        "expected at least 1 AWF252 diagnostic for old single-call wrapper "
        "with full boundary receipts + semantic findings, got 0"
    )
    assert "SOURCE_TIEBREAKER_WORKFLOW" in (awf252_diags[0].component_ref or "")

    # Confirm the boundary evidence is still preserved in the result carrier.
    assert result.boundary_evidence == combined_evidence, (
        "boundary evidence must be preserved in result"
    )


def test_old_wrapper_awf252_not_silenced_by_row_evidence() -> None:
    """Supplying SemanticEvidence covering the four S3 tiebreaker row-IDs
    must NOT silence AWF252 when the source uses the old single-call wrapper.
    Row-level SemanticEvidence also cannot compensate for missing source-visible
    topology."""
    # Row evidence for all four S3 phases.
    row_evidence = (
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 1, 1, 1, 10),
            construct_type=ConstructType.TIEBREAKER_RESEARCHER,
            row_id=S3_TIEBREAKER_RESEARCHER_ROW_ID,
        ),
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 2, 1, 2, 10),
            construct_type=ConstructType.TIEBREAKER_CHALLENGER,
            row_id=S3_TIEBREAKER_CHALLENGER_ROW_ID,
        ),
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 3, 1, 3, 10),
            construct_type=ConstructType.TIEBREAKER_SYNTHESIS,
            row_id=S3_TIEBREAKER_SYNTHESIS_ROW_ID,
        ),
        SemanticEvidence(
            diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
            source_span=SourceSpan("test.pypeline", 4, 1, 4, 10),
            construct_type=ConstructType.TIEBREAKER_DECISION,
            row_id=S3_TIEBREAKER_DECISION_ROW_ID,
        ),
    )

    result = check_workflow_source(
        _OLD_WRAPPER_SOURCE,
        source_path="test_old_wrapper.pypeline",
        evidence=row_evidence,
    )

    assert not result.ok, (
        "expected failure for old single-call wrapper with row evidence, "
        "but result.ok is True"
    )

    awf252_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.TIEBREAKER_SHAPE_VIOLATION
    ]
    assert len(awf252_diags) >= 1, (
        "expected AWF252 even when SemanticEvidence covers all S3 row IDs, "
        f"got {len(awf252_diags)}"
    )

    # No AWF245 should be emitted for S3 rows — the old wrapper doesn't
    # produce _ImplementedFrontHalfRow entries for these phases, so row-evidence
    # checking doesn't flag them as missing.
    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]
    s3_awf245 = [
        d for d in awf245_diags
        if d.details.get("row_id", "").startswith("s3.")
    ]
    assert len(s3_awf245) == 0, (
        "old wrapper must not produce AWF245 for S3 phases "
        "(they are not source-visible as individual steps)"
    )


def test_s5_invalid_authoring_fixtures_match_sidecars() -> None:
    """S5 invalid fixtures must pin the intended review/finalize checker diagnostics."""
    for case_name in (
        "invalid_m3_single_handler_review_fanout",
        "invalid_m3_handler_owned_review_cap",
        "invalid_m3_hidden_finalize_fallback",
    ):
        expected = _load_m3_sidecar(case_name)["expected_diagnostics"]
        result = _run_s5_fixture(case_name)

        assert not result.ok, case_name
        assert _diagnostic_payloads(result) == expected


def test_s5_canonical_fixture_accepts_source_visible_review_finalize_evidence() -> None:
    """The canonical M3 fixture must satisfy the S5 boundary rows from source/policy
    topology without relying on legacy enabled-status shortcuts."""
    from arnold_pipelines.megaplan.workflows.boundary_contracts import (
        final_projection,
        finalize_artifacts,
        finalize_fallback,
        review_cap_authority,
        review_child_outputs,
        review_human_verification,
        review_reducer_promotion,
        review_rework_effects,
    )

    s5_contracts = (
        review_child_outputs,
        review_reducer_promotion,
        review_rework_effects,
        review_cap_authority,
        review_human_verification,
        finalize_artifacts,
        finalize_fallback,
        final_projection,
    )
    s5_receipts = tuple(_receipt_for_contract(contract) for contract in s5_contracts)

    result = workflow.check_workflow_file(
        M3_FIXTURE_DIR / "valid_m3_canonical_megaplan_topology.py",
        boundary_contracts=s5_contracts,
        boundary_evidence=s5_receipts,
    )

    s5_row_ids = {contract.row_id for contract in s5_contracts}
    assert not any(
        diagnostic.code in {
            DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
            DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
            DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
            DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        }
        and diagnostic.details.get("row_id") in s5_row_ids
        for diagnostic in result.diagnostics
    ), _diagnostic_payloads(result)
    assert DiagnosticCode.SINGLE_HANDLER_WRAPPER not in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert DiagnosticCode.HANDLER_PURITY_VIOLATION not in {
        diagnostic.code for diagnostic in result.diagnostics
    }
