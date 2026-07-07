#!/usr/bin/env python3
"""Insert S4 execute evidence tests into the row-evidence checker test file."""

insertion_point = "# ── S3 negative tests: old single-call wrapper"
new_block = """

# ── S4 execute evidence visibility ──────────────────────────────────────────
# Prove that S4 execute row IDs, construct types, and boundary phases are
# registered and visible to the semantic checker without false positives.


_EXECUTE_SOURCE_TEMPLATE = \"\"\"\\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_EXECUTE

@workflow(id="test", version="s4")
def test_flow(brief: str) -> None:
    SOURCE_EXECUTE(id="run", brief=brief)
\"\"\"


def test_execute_row_evidence_preserved_in_result() -> None:
    \"\"\"SemanticEvidence with S4_EXECUTE_ROW_ID and ConstructType.EXECUTE must
    be preserved in the checker result carrier without modification.\"\"\"
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
    \"\"\"S4 execute evidence records must round-trip through to_dict()
    without losing row identity or construct type.\"\"\"
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
    \"\"\"An execute-only source without evidence must NOT produce AWF245
    for the execute row — execute is not a front-half row until a boundary
    contract is registered for it.\"\"\"
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
    \"\"\"Supplying execute row evidence must not create AWF245 rows that are
    absent from parsed topology.\"\"\"
    source = \"\"\"\\
from __future__ import annotations

from arnold.workflow.authoring import workflow

@workflow(id="empty", version="s4")
def empty_flow(brief: str) -> None:
    pass
\"\"\"
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
    \"\"\"When both S2 front-half and S4 execute evidence are passed, the
    checker must preserve all evidence and only flag uncovered front-half rows.\"\"\"
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


"""

with open('tests/arnold/workflow/test_row_evidence_checker.py', 'r') as f:
    content = f.read()

if insertion_point in content:
    content = content.replace(insertion_point, new_block + insertion_point, 1)
    with open('tests/arnold/workflow/test_row_evidence_checker.py', 'w') as f:
        f.write(content)
    print("Inserted S4 tests successfully")
else:
    print("ERROR: insertion point not found")
