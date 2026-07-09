"""Focused tests for the S2.5 boundary evidence checker rules (T4).

These tests verify that ``check_workflow_source`` emits the four
boundary diagnostic codes (AWF246–AWF249) correctly and respects the
two non-smuggling invariants: boundary evidence cannot mask missing
source-topology proof, and boundary evidence cannot create a row absent
from parsed ``.pypeline`` topology.

Coverage targets:
- source-topology alone insufficient (AWF246)
- missing contract / evidence (AWF246, AWF247)
- evidence without source (AWF248)
- stale boundary evidence (AWF249)
- smuggling invariant: boundary evidence cannot satisfy or create an
  absent ``.pypeline`` source row

A2 failing-fixture scenario locators (reviewer-visible without
structural-audit output):

- **AWF247 (no-durable-evidence fixture):**
  ``test_source_with_contracts_but_no_evidence_produces_awf247`` —
  source topology present, boundary contracts supplied, but no durable
  boundary evidence (receipts/findings).

- **AWF248 / smuggling fixture:**
  ``test_boundary_receipt_without_source_topology_produces_awf248`` —
  boundary evidence whose row_id has no match in parsed topology.
  ``test_boundary_evidence_cannot_create_absent_source_row`` —
  boundary evidence for rows absent from source must not create
  source rows; orphan evidence produces AWF248 and AWF245 only fires
  for implemented rows.
"""

from __future__ import annotations

import pytest

from arnold.manifest.refs import SourceSpan
from arnold.workflow import check_workflow_source
from arnold.workflow.boundary_evidence import (
    AuthorityRecord,
    BoundaryContract,
    BoundaryOutcome,
    BoundaryPhase,
    BoundaryReceipt,
    FindingSeverity,
    SemanticFinding,
)
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

_SOURCE_NO_FRONT_HALF = """\
from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_EXECUTE

@workflow(id="plain", version="s2")
def plain_flow(brief: str) -> None:
    SOURCE_EXECUTE(id="run", brief=brief)
"""


# ── helpers ─────────────────────────────────────────────────────────────────


def _bc(row_id: str, boundary_id: str, phase: BoundaryPhase) -> BoundaryContract:
    """Make a minimal BoundaryContract for a front-half row."""
    return BoundaryContract(
        boundary_id=boundary_id,
        workflow_id="megaplan-review",
        row_id=row_id,
        phase=phase,
        required_artifacts=(),
        receipt_required=True,
    )


def _receipt(
    boundary_id: str,
    row_id: str,
    *,
    artifact_refs: tuple[str, ...] = (),
    state_observation: dict | None = None,
    outcome: BoundaryOutcome = BoundaryOutcome.COMPLETE,
    history_ref: str | None = None,
    phase_result_ref: str | None = None,
    authority_required: bool = False,
    details: dict | None = None,
) -> BoundaryReceipt:
    """Make a healthy BoundaryReceipt."""
    authority: tuple[AuthorityRecord, ...] = ()
    if authority_required:
        authority = (AuthorityRecord(actor="gatekeeper", role="reviewer"),)
    return BoundaryReceipt(
        boundary_id=boundary_id,
        workflow_id="megaplan-review",
        row_id=row_id,
        artifact_refs=artifact_refs,
        state_observation=state_observation or {},
        outcome=outcome,
        history_ref=history_ref,
        phase_result_ref=phase_result_ref or f"phase/{boundary_id}.json",
        authority_records=authority,
        details=details or {},
    )


def _evidence_for(row_id: str) -> SemanticEvidence:
    """Make a SemanticEvidence record for a row."""
    return SemanticEvidence(
        diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
        source_span=SourceSpan("test.pypeline", 1, 1, 1, 10),
        construct_type=ConstructType.PREP,
        row_id=row_id,
    )


# ── AWF246 / AWF247 : missing contracts or evidence ─────────────────────────


def test_source_without_boundary_contracts_produces_awf246() -> None:
    """A source with implemented prep+plan steps but no supplied boundary
    contracts must produce AWF246 for every front-half row that lacks a contract.

    To activate boundary diagnostics, we supply a piece of boundary
    evidence that belongs to a row NOT in the source (which also triggers
    AWF248).  The boundary check then flags every implemented row that
    lacks a matching contract."""
    orphan_receipt = _receipt("orphan_boundary", "s2.orphan.1")
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=(),
        boundary_evidence=(orphan_receipt,),
    )

    assert not result.ok
    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.BOUNDARY_CONTRACT_MISSING in diag_codes

    awf246_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_CONTRACT_MISSING
    ]
    assert len(awf246_diags) == 2  # prep + plan


def test_source_with_contracts_but_no_evidence_produces_awf247() -> None:
    """Canonical A2 AWF247 fixture: source topology plus contracts without
    durable boundary evidence.

    Supplying boundary contracts but no boundary evidence must produce
    AWF247 for each implemented row that has a contract but no receipts/findings."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(),
    )

    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.BOUNDARY_EVIDENCE_MISSING in diag_codes
    assert DiagnosticCode.BOUNDARY_CONTRACT_MISSING not in diag_codes

    awf247_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_MISSING
    ]
    assert len(awf247_diags) == 2

    row_ids = {d.details.get("row_id") for d in awf247_diags}
    assert S2_PREP_ROW_ID in row_ids
    assert S2_PLAN_ROW_ID in row_ids


def test_partial_contracts_flag_only_uncovered_rows_awf246() -> None:
    """When only some front-half rows have contracts, AWF246 is emitted
    only for the uncovered rows."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(),
    )

    awf246_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_CONTRACT_MISSING
    ]
    assert len(awf246_diags) == 1  # only plan is missing
    assert S2_PLAN_ROW_ID in awf246_diags[0].message

    awf247_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_MISSING
    ]
    assert len(awf247_diags) == 1  # prep has contract but no evidence
    assert S2_PREP_ROW_ID in awf247_diags[0].message


def test_valid_receipts_suppress_awf247() -> None:
    """When every implemented row has both a contract and a valid receipt,
    no AWF246/AWF247/AWF249 diagnostics should fire."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipts = (
        _receipt("prep_to_plan", S2_PREP_ROW_ID),
        _receipt("plan_to_critique", S2_PLAN_ROW_ID),
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=receipts,
    )

    for code in (
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    ):
        assert code not in {d.code for d in result.diagnostics}, (
            f"unexpected boundary diagnostic {code.value}"
        )


# ── AWF248 : evidence without matching source topology ─────────────────────


def test_boundary_receipt_without_source_topology_produces_awf248() -> None:
    """Canonical A2 AWF248 fixture: boundary evidence absent from parsed
    source topology.

    A BoundaryReceipt whose row_id has no match in parsed topology must
    produce AWF248."""
    receipt = _receipt("gate_to_revise", S2_GATE_ROW_ID)
    result = check_workflow_source(
        _SOURCE_TEMPLATE,  # only has prep+plan, not gate
        source_path="test.pypeline",
        boundary_contracts=(
            _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
            _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
            _bc(S2_GATE_ROW_ID, "gate_to_revise", BoundaryPhase.GATE),
        ),
        boundary_evidence=(receipt,),
    )

    awf248_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE
    ]
    assert len(awf248_diags) == 1
    assert "gate_to_revise" in awf248_diags[0].message


def test_semantic_finding_without_source_topology_produces_awf248() -> None:
    """A SemanticFinding whose boundary_id has no matching source row must
    produce AWF248."""
    finding = SemanticFinding(
        finding_id="F-orphan-1",
        boundary_id="revise_to_critique",
        description="no source topology for revise",
        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE,  # no revise row
        source_path="test.pypeline",
        boundary_contracts=(
            _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
            _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
            _bc(S2_REVISE_ROW_ID, "revise_to_critique", BoundaryPhase.REVISE),
        ),
        boundary_evidence=(finding,),
    )

    awf248_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE
    ]
    assert len(awf248_diags) >= 1
    assert any("revise_to_critique" in d.message for d in awf248_diags)


def test_orphan_finding_without_any_contract_produces_awf248() -> None:
    """A SemanticFinding that has no matching contract at all must still
    produce AWF248 (orphan evidence)."""
    finding = SemanticFinding(
        finding_id="F-orphan-2",
        boundary_id="nonexistent_boundary",
        description="no contract and no source",
        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=(
            _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
            _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
        ),
        boundary_evidence=(finding,),
    )

    awf248_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE
    ]
    assert len(awf248_diags) >= 1
    assert any("nonexistent_boundary" in d.message for d in awf248_diags)


def test_boundary_evidence_ignored_when_no_contracts_or_evidence() -> None:
    """When neither boundary_contracts nor boundary_evidence is supplied,
    boundary diagnostics are entirely inert."""
    result = check_workflow_source(
        _SOURCE_NO_FRONT_HALF,
        source_path="plain.pypeline",
    )
    # No boundary diagnostics should appear (only AWF245 if applicable, but
    # this source has no S2 front-half rows so nothing fires).
    boundary_codes = {
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    }
    assert not boundary_codes.intersection({d.code for d in result.diagnostics})


# ── AWF249 : stale boundary evidence ────────────────────────────────────────


def test_receipt_with_state_mismatch_produces_awf249() -> None:
    """A boundary receipt whose state_observation mismatches the contract's
    expected_state_delta is stale and must produce AWF249."""
    contracts = (
        BoundaryContract(
            boundary_id="prep_to_plan",
            workflow_id="megaplan-review",
            row_id=S2_PREP_ROW_ID,
            phase=BoundaryPhase.PREP,
            required_artifacts=("research.md",),
            expected_state_delta={"current_phase": "prep"},
            receipt_required=True,
        ),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    # Receipt for prep claims state is "plan" but contract expects "prep"
    stale_receipt = _receipt(
        "prep_to_plan",
        S2_PREP_ROW_ID,
        artifact_refs=("research.md",),
        state_observation={"current_phase": "plan"},  # mismatch!
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(stale_receipt, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1
    assert "prep_to_plan" in awf249_diags[0].message
    assert "stale" in awf249_diags[0].message.lower()


def test_receipt_with_missing_artifacts_produces_awf249() -> None:
    """A boundary receipt missing required artifacts is stale."""
    contracts = (
        BoundaryContract(
            boundary_id="prep_to_plan",
            workflow_id="megaplan-review",
            row_id=S2_PREP_ROW_ID,
            phase=BoundaryPhase.PREP,
            required_artifacts=("research.md", "brief.md"),
            receipt_required=True,
        ),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt_missing_artifacts = _receipt(
        "prep_to_plan",
        S2_PREP_ROW_ID,
        artifact_refs=("research.md",),  # missing brief.md
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_missing_artifacts, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1
    assert "prep_to_plan" in awf249_diags[0].message


def test_receipt_with_history_mismatch_produces_awf249() -> None:
    """A receipt whose history_ref doesn't match the contract's
    expected_history_entry triggers AWF249."""
    contracts = (
        BoundaryContract(
            boundary_id="prep_to_plan",
            workflow_id="megaplan-review",
            row_id=S2_PREP_ROW_ID,
            phase=BoundaryPhase.PREP,
            expected_history_entry="prep_completed",
            receipt_required=True,
        ),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt_wrong_history = _receipt(
        "prep_to_plan",
        S2_PREP_ROW_ID,
        history_ref="wrong_history_entry",
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_wrong_history, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1


def test_receipt_with_missing_phase_result_ref_produces_awf249() -> None:
    """When a contract requires phase_result_required but the receipt omits
    phase_result_ref, the receipt is stale."""
    contracts = (
        BoundaryContract(
            boundary_id="prep_to_plan",
            workflow_id="megaplan-review",
            row_id=S2_PREP_ROW_ID,
            phase=BoundaryPhase.PREP,
            phase_result_required=True,
            receipt_required=True,
        ),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    # Construct receipt directly (helper replaces None with a default)
    receipt_no_phase = BoundaryReceipt(
        boundary_id="prep_to_plan",
        workflow_id="megaplan-review",
        row_id=S2_PREP_ROW_ID,
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_no_phase, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1


def test_receipt_with_missing_authority_produces_awf249() -> None:
    """When a contract requires authority_required but the receipt has no
    authority_records, the receipt is stale."""
    contracts = (
        BoundaryContract(
            boundary_id="prep_to_plan",
            workflow_id="megaplan-review",
            row_id=S2_PREP_ROW_ID,
            phase=BoundaryPhase.PREP,
            authority_required=True,
            receipt_required=True,
        ),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt_no_auth = _receipt(
        "prep_to_plan",
        S2_PREP_ROW_ID,
        authority_required=False,  # no authority records
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_no_auth, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1


def test_receipt_with_stale_details_produces_awf249() -> None:
    """A receipt whose details contain expired/stale markers triggers AWF249."""
    contracts = (
        BoundaryContract(
            boundary_id="prep_to_plan",
            workflow_id="megaplan-review",
            row_id=S2_PREP_ROW_ID,
            phase=BoundaryPhase.PREP,
            receipt_required=True,
        ),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt_stale_details = _receipt(
        "prep_to_plan",
        S2_PREP_ROW_ID,
        details={"freshness": "stale", "observation": "expired"},
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_stale_details, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1


def test_receipt_with_workflow_id_mismatch_produces_awf249() -> None:
    """A receipt whose workflow_id doesn't match the contract produces AWF249."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt_wrong_wf = BoundaryReceipt(
        boundary_id="prep_to_plan",
        workflow_id="wrong-workflow",  # mismatch
        row_id=S2_PREP_ROW_ID,
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_wrong_wf, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1
    assert "workflow_id mismatch" in awf249_diags[0].details.get("receipt_issues", ())[0]


def test_receipt_with_row_id_mismatch_produces_awf249() -> None:
    """A receipt whose row_id doesn't match the implemented row produces AWF249."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt_wrong_row = _receipt(
        "prep_to_plan",
        S2_PLAN_ROW_ID,  # wrong row for prep boundary
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(receipt_wrong_row, valid_receipt),
    )

    awf249_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_STALE
    ]
    assert len(awf249_diags) == 1


# ── smuggling invariants ────────────────────────────────────────────────────


def test_boundary_evidence_cannot_satisfy_awf245() -> None:
    """Even when valid boundary receipts exist, if row evidence is missing
    then AWF245 must still fire. Boundary evidence cannot mask missing
    source-topology proof."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipts = (
        _receipt("prep_to_plan", S2_PREP_ROW_ID),
        _receipt("plan_to_critique", S2_PLAN_ROW_ID),
    )
    # No row evidence supplied — AWF245 should fire despite valid receipts
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=receipts,
        evidence=(),  # no row evidence
    )

    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY in diag_codes, (
        "AWF245 must fire even when boundary evidence is valid"
    )
    # Boundary checks should not fire for rows that have valid receipts
    assert DiagnosticCode.BOUNDARY_CONTRACT_MISSING not in diag_codes
    assert DiagnosticCode.BOUNDARY_EVIDENCE_MISSING not in diag_codes
    assert DiagnosticCode.BOUNDARY_EVIDENCE_STALE not in diag_codes


def test_boundary_evidence_cannot_create_absent_source_row() -> None:
    """Canonical A2 smuggling invariant: boundary evidence for rows absent
    from parsed source topology must not create source rows.

    The evidence is orphaned (AWF248) and no AWF245 is emitted for the
    absent row because it was never implemented."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
        _bc(S2_GATE_ROW_ID, "gate_to_revise", BoundaryPhase.GATE),
        _bc(S2_CRITIQUE_ROW_ID, "critique_to_gate", BoundaryPhase.CRITIQUE),
        _bc(S2_REVISE_ROW_ID, "revise_to_critique", BoundaryPhase.REVISE),
    )
    # Receipts for ALL five rows even though source only has prep+plan
    receipts = (
        _receipt("prep_to_plan", S2_PREP_ROW_ID),
        _receipt("plan_to_critique", S2_PLAN_ROW_ID),
        _receipt("critique_to_gate", S2_CRITIQUE_ROW_ID),
        _receipt("gate_to_revise", S2_GATE_ROW_ID),
        _receipt("revise_to_critique", S2_REVISE_ROW_ID),
    )

    result = check_workflow_source(
        _SOURCE_TEMPLATE,  # only prep + plan
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=receipts,
    )

    # AWF245 must fire for prep and plan since no row evidence was supplied
    awf245_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY
    ]
    assert len(awf245_diags) == 2  # only prep+plan, not critique/gate/revise

    row_ids_in_awf245 = {d.details.get("row_id") for d in awf245_diags}
    assert row_ids_in_awf245 == {S2_PREP_ROW_ID, S2_PLAN_ROW_ID}
    # Critique, gate, revise must NOT appear in AWF245 — they aren't implemented
    for absent_row in (S2_CRITIQUE_ROW_ID, S2_GATE_ROW_ID, S2_REVISE_ROW_ID):
        assert absent_row not in row_ids_in_awf245, (
            f"boundary evidence created an absent row {absent_row!r}"
        )

    # Orphan receipts for critique/gate/revise should produce AWF248
    awf248_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE
    ]
    assert len(awf248_diags) == 3  # critique, gate, revise receipts are orphans


def test_full_row_evidence_suppresses_awf245_while_boundary_checks_work() -> None:
    """When both row evidence and valid boundary receipts exist, neither
    AWF245 nor AWF246/AWF247/AWF249 fire."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    evidence = (
        _evidence_for(S2_PREP_ROW_ID),
        _evidence_for(S2_PLAN_ROW_ID),
    )
    receipts = (
        _receipt("prep_to_plan", S2_PREP_ROW_ID),
        _receipt("plan_to_critique", S2_PLAN_ROW_ID),
    )

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=receipts,
        evidence=evidence,
    )

    assert result.ok


def test_semantic_finding_forwards_boundary_diagnostic() -> None:
    """A SemanticFinding with a boundary diagnostic code attached to a valid
    row should forward that diagnostic to the checker output."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    finding = SemanticFinding(
        finding_id="F-stale-1",
        boundary_id="prep_to_plan",
        description="prep receipt is stale",
        severity=FindingSeverity.ERROR,
        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    )
    # Also supply a valid receipt for plan
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(finding, valid_receipt),
    )

    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.BOUNDARY_EVIDENCE_STALE in diag_codes
    # Plan should not be affected (its receipt is valid)
    assert DiagnosticCode.BOUNDARY_EVIDENCE_MISSING not in diag_codes


def test_semantic_finding_with_boundary_contract_missing_code() -> None:
    """A SemanticFinding reporting BOUNDARY_CONTRACT_MISSING for a
    valid row should forward AWF246."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    finding = SemanticFinding(
        finding_id="F-missing-contract-1",
        boundary_id="prep_to_plan",
        description="contract for prep boundary is missing",
        diagnostic_code=DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(finding, valid_receipt),
    )

    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.BOUNDARY_CONTRACT_MISSING in diag_codes


def test_semantic_finding_with_boundary_evidence_missing_code() -> None:
    """A SemanticFinding reporting BOUNDARY_EVIDENCE_MISSING for a valid
    row should forward AWF247."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    finding = SemanticFinding(
        finding_id="F-missing-evidence-1",
        boundary_id="prep_to_plan",
        description="evidence for prep boundary is missing",
        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(finding, valid_receipt),
    )

    diag_codes = {d.code for d in result.diagnostics}
    assert DiagnosticCode.BOUNDARY_EVIDENCE_MISSING in diag_codes


@pytest.mark.parametrize(
    ("finding_id", "description", "diagnostic_code"),
    (
        (
            "SH-prep_to_plan-receipt-missing",
            "prep boundary receipt is missing",
            DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        ),
        (
            "SH-prep_to_plan-phase-result-stale-phase",
            "prep boundary phase result is stale",
            DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        ),
        (
            "SH-prep_to_plan-state-history-drift",
            "prep boundary artifact/state evidence diverged",
            DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        ),
        (
            "SH-prep_to_plan-authority-scope-mismatch-0",
            "prep boundary authority evidence points at the wrong scope",
            DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        ),
        (
            "SH-prep_to_plan-child-output-without-promotion",
            "child outputs exist without reducer promotion evidence",
            DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        ),
        (
            "SH-prep_to_plan-promotion-without-child-evidence",
            "reducer promotion was recorded without child evidence",
            DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        ),
    ),
)
def test_semantic_health_negative_case_findings_forward_expected_boundary_codes(
    finding_id: str,
    description: str,
    diagnostic_code: DiagnosticCode,
) -> None:
    """Semantic-health negative fixture IDs must preserve their missing vs stale
    checker verdict when forwarded as boundary evidence."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    finding = SemanticFinding(
        finding_id=finding_id,
        boundary_id="prep_to_plan",
        description=description,
        severity=(
            FindingSeverity.ERROR
            if diagnostic_code is DiagnosticCode.BOUNDARY_EVIDENCE_MISSING
            else FindingSeverity.WARNING
        ),
        diagnostic_code=diagnostic_code,
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(finding, valid_receipt),
    )

    diag_codes = {d.code for d in result.diagnostics}
    assert diagnostic_code in diag_codes
    assert DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE not in diag_codes


def test_semantic_finding_with_non_boundary_diagnostic_is_not_fowarded() -> None:
    """A SemanticFinding whose diagnostic_code is not one of AWF246-AWF249
    should not produce a boundary diagnostic — it is treated as an
    informational finding that does not invalidate the receipt."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    finding = SemanticFinding(
        finding_id="F-info-1",
        boundary_id="prep_to_plan",
        description="informational observation",
        severity=FindingSeverity.INFO,
        diagnostic_code=DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,  # not a boundary code
    )
    valid_receipt = _receipt("plan_to_critique", S2_PLAN_ROW_ID)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(finding, valid_receipt),
    )

    # No boundary diagnostics because the finding code isn't in AWF246-AWF249 range
    # and prep row has a finding (skips AWF247 receipt check)
    boundary_codes = {
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    }
    # The finding is still consumed (it suppresses the AWF247 check for prep),
    # but none of the boundary codes should fire because the finding's code is
    # not in the allowed set.
    for code in boundary_codes:
        assert code not in {d.code for d in result.diagnostics}, (
            f"non-boundary finding should not emit {code.value}"
        )


# ── Result carrier / API behaviour ──────────────────────────────────────────


def test_boundary_evidence_preserved_in_result() -> None:
    """Boundary evidence records passed to check_workflow_source must be
    preserved in the result carrier without modification."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    receipt = _receipt("prep_to_plan", S2_PREP_ROW_ID)
    finding = SemanticFinding(
        finding_id="F-1",
        boundary_id="plan_to_critique",
        description="plan evidence is stale",
        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    )
    boundary_evidence = (receipt, finding)

    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=boundary_evidence,
    )

    assert result.boundary_evidence == boundary_evidence
    assert len(result.boundary_evidence) == 2
    assert isinstance(result.boundary_evidence[0], BoundaryReceipt)
    assert isinstance(result.boundary_evidence[1], SemanticFinding)


def test_boundary_evidence_result_field_is_always_tuple() -> None:
    """The boundary_evidence field on CheckWorkflowSourceResult must always
    be a tuple, even when no boundary evidence is supplied."""
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
    )
    assert isinstance(result.boundary_evidence, tuple)
    assert result.boundary_evidence == ()


def test_check_workflow_file_forwards_boundary_params() -> None:
    """check_workflow_file must forward boundary_contracts and
    boundary_evidence to check_workflow_source."""
    import os
    import tempfile

    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    evidence = (
        _evidence_for(S2_PREP_ROW_ID),
        _evidence_for(S2_PLAN_ROW_ID),
    )
    receipts = (
        _receipt("prep_to_plan", S2_PREP_ROW_ID),
        _receipt("plan_to_critique", S2_PLAN_ROW_ID),
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(_SOURCE_TEMPLATE)
        tmp_path = tmp.name

    try:
        from arnold.workflow import check_workflow_file

        result = check_workflow_file(
            tmp_path,
            evidence=evidence,
            boundary_contracts=contracts,
            boundary_evidence=receipts,
        )
        assert result.ok
        assert result.evidence == evidence
        assert result.boundary_evidence == receipts
    finally:
        os.unlink(tmp_path)


def test_diagnostic_details_include_row_and_boundary_id() -> None:
    """Boundary diagnostics must carry row_id and boundary_id in their
    details for downstream consumers."""
    contracts = (
        _bc(S2_PREP_ROW_ID, "prep_to_plan", BoundaryPhase.PREP),
        _bc(S2_PLAN_ROW_ID, "plan_to_critique", BoundaryPhase.PLAN),
    )
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=contracts,
        boundary_evidence=(),
    )

    awf247_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_MISSING
    ]
    assert len(awf247_diags) == 2
    for diag in awf247_diags:
        assert "boundary_id" in diag.details
        assert "row_id" in diag.details
        assert "phase" in diag.details


def test_boundary_contract_missing_detail_carries_component_ref() -> None:
    """AWF246 diagnostics must carry component_ref so consumers can trace
    back to the import.

    Supply orphan boundary evidence to activate the boundary check so that
    AWF246 fires for implemented rows missing contracts."""
    orphan_receipt = _receipt("orphan_boundary", "s2.orphan.1")
    result = check_workflow_source(
        _SOURCE_TEMPLATE,
        source_path="test.pypeline",
        boundary_contracts=(),
        boundary_evidence=(orphan_receipt,),
    )

    awf246_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_CONTRACT_MISSING
    ]
    assert len(awf246_diags) == 2
    component_refs = {d.component_ref for d in awf246_diags if d.component_ref}
    assert len(component_refs) >= 1
    for ref in component_refs:
        assert "SOURCE_PREP" in ref or "SOURCE_PLAN" in ref


def test_boundary_evidence_without_source_detail_carries_evidence_kind() -> None:
    """AWF248 diagnostics must carry the evidence kind (boundary_receipt
    or semantic_finding) in their details."""
    orphan_receipt = _receipt("orphan_boundary", "s2.orphan.1")
    orphan_finding = SemanticFinding(
        finding_id="F-orphan",
        boundary_id="another_orphan",
        description="orphan finding",
    )

    result = check_workflow_source(
        _SOURCE_NO_FRONT_HALF,
        source_path="plain.pypeline",
        boundary_contracts=(),
        boundary_evidence=(orphan_receipt, orphan_finding),
    )

    awf248_diags = [
        d for d in result.diagnostics
        if d.code is DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE
    ]
    assert len(awf248_diags) == 2

    evidence_kinds = {d.details.get("evidence_kind") for d in awf248_diags}
    assert "boundary_receipt" in evidence_kinds
    assert "semantic_finding" in evidence_kinds
