"""Focused tests for the S2 row-evidence checker rule (T2).

These tests verify that ``check_workflow_source`` emits
``AWF245_ROW_EVIDENCE_INSUFFICIENCY`` whenever an implemented front-half
row (prep / plan / critique / gate / revise) lacks structured semantic
evidence, and that the API / serialization contracts hold.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arnold.manifest.refs import SourceSpan
from arnold.workflow import check_workflow_source
from arnold.workflow.diagnostics import DiagnosticCode
from arnold.workflow.semantic_evidence import (
    ConstructType,
    S2_CRITIQUE_ROW_ID,
    S2_GATE_ROW_ID,
    S2_PLAN_ROW_ID,
    S2_PREP_ROW_ID,
    S2_REVISE_ROW_ID,
    SemanticEvidence,
)

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
