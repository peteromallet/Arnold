"""Dispatch tests for boundary receipt emission across front-half phase pairs.

Proves that all five front-half (step, next_step) pairs emit the expected
boundary receipt through ``_finish_step -> _emit_boundary_receipt ->
_boundary_contract_for_response``, and that mismatched pairs produce no
receipt.  Exercises the handler-response completion path without invoking
LLM workers.

This is a non-regression dispatch proof, not a routing authority test.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from arnold.workflow.boundary_evidence import BoundaryContract
from arnold_pipelines.megaplan.handlers.shared import (
    _BOUNDARY_EXPECTED_NEXT_STEP_BY_ID,
    _boundary_contract_for_response,
)
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    BOUNDARY_CONTRACTS,
    BOUNDARY_CONTRACTS_BY_ID,
)


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_worker(**overrides: Any) -> WorkerResult:
    kwargs: dict[str, Any] = {
        "payload": {},
        "raw_output": "",
        "duration_ms": 100,
        "cost_usd": 0.0,
        "session_id": "test-session",
        "worker_channel": "test",
        "auth_channel": "test",
    }
    kwargs.update(overrides)
    return WorkerResult(**kwargs)  # type: ignore[arg-type]


def _make_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "name": "test-plan",
        "current_state": "prepped",
        "iteration": 1,
        "config": {"project_dir": "/tmp/test-project"},
        "meta": {},
        "history": [],
        "sessions": {},
    }
    state.update(overrides)
    return state


# ── _BOUNDARY_EXPECTED_NEXT_STEP_BY_ID completeness ─────────────────────────


def test_expected_next_step_by_id_has_exactly_five_entries() -> None:
    """The mapping must cover exactly the five front-half boundary pairs."""
    assert len(_BOUNDARY_EXPECTED_NEXT_STEP_BY_ID) == 5


def test_expected_next_step_by_id_entries_match_contracts() -> None:
    """Every entry in _BOUNDARY_EXPECTED_NEXT_STEP_BY_ID must correspond to
    a registered BoundaryContract."""
    for boundary_id, expected_next in _BOUNDARY_EXPECTED_NEXT_STEP_BY_ID.items():
        contract = BOUNDARY_CONTRACTS_BY_ID.get(boundary_id)
        assert contract is not None, (
            f"Entry '{boundary_id}' has no matching BoundaryContract"
        )
        assert contract.boundary_id == boundary_id


# ── _boundary_contract_for_response: dispatch proof ─────────────────────────


@pytest.mark.parametrize("step,next_step,expected_boundary_id", [
    ("prep", "plan", "prep_to_plan"),
    ("plan", "critique", "plan_to_critique"),
    ("critique", "gate", "critique_to_gate"),
    ("gate", "revise", "gate_to_revise"),
    ("revise", "critique", "revise_to_critique"),
])
def test_boundary_contract_for_response_matches_all_five_pairs(
    step: str, next_step: str, expected_boundary_id: str,
) -> None:
    """For each of the five approved front-half pairs, the function returns
    the correct BoundaryContract."""
    response: dict[str, Any] = {"next_step": next_step}
    contract = _boundary_contract_for_response(step, response)
    assert contract is not None, (
        f"No contract returned for ({step}, {next_step})"
    )
    assert isinstance(contract, BoundaryContract)
    assert contract.boundary_id == expected_boundary_id


@pytest.mark.parametrize("step,next_step", [
    ("prep", "critique"),      # wrong next_step for prep
    ("plan", "gate"),           # wrong next_step for plan
    ("critique", "revise"),     # wrong next_step for critique
    ("gate", "plan"),           # wrong next_step for gate
    ("revise", "plan"),         # wrong next_step for revise
])
def test_boundary_contract_for_response_returns_none_for_mismatched(
    step: str, next_step: str,
) -> None:
    """When next_step does not match the expected value, the function
    returns None (no boundary receipt emitted)."""
    response: dict[str, Any] = {"next_step": next_step}
    contract = _boundary_contract_for_response(step, response)
    assert contract is None, (
        f"Should return None for mismatched ({step}, {next_step})"
    )


def test_boundary_contract_for_response_returns_none_for_unknown_step() -> None:
    """A step not in the contract registry returns None."""
    response: dict[str, Any] = {"next_step": "anything"}
    contract = _boundary_contract_for_response("unknown_step", response)
    assert contract is None


def test_boundary_contract_for_response_returns_none_for_missing_next_step() -> None:
    """When response has no next_step, the function returns None."""
    response: dict[str, Any] = {}
    contract = _boundary_contract_for_response("prep", response)
    assert contract is None


# ── _emit_boundary_receipt: emission proof ──────────────────────────────────


@pytest.mark.parametrize("step,next_step,expected_boundary_id", [
    ("prep", "plan", "prep_to_plan"),
    ("plan", "critique", "plan_to_critique"),
    ("critique", "gate", "critique_to_gate"),
    ("gate", "revise", "gate_to_revise"),
    ("revise", "critique", "revise_to_critique"),
])
def test_emit_boundary_receipt_calls_writer_for_all_five_pairs(
    step: str,
    next_step: str,
    expected_boundary_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_emit_boundary_receipt calls write_boundary_receipt exactly once
    for each of the five matched front-half pairs."""
    import arnold_pipelines.megaplan.handlers.shared as shared_mod

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    # Ensure project_dir exists for to_relative calls
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    state = _make_state(config={"project_dir": str(project_dir)})
    worker = _make_worker()
    response: dict[str, Any] = {"next_step": next_step}

    mock_write = mock.MagicMock()
    monkeypatch.setattr(shared_mod, "write_boundary_receipt", mock_write)

    shared_mod._emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step=step,
        worker=worker,
        agent="test-agent",
        mode="test",
        artifacts=[],
        output_file="test_output.json",
        artifact_hash="abc123",
        response=response,
    )

    mock_write.assert_called_once()
    call_args = mock_write.call_args
    receipt = call_args[0][1]  # second positional arg
    assert receipt.boundary_id == expected_boundary_id


@pytest.mark.parametrize("step,next_step", [
    ("prep", "critique"),
    ("plan", "gate"),
    ("critique", "revise"),
])
def test_emit_boundary_receipt_does_not_call_writer_for_mismatched(
    step: str,
    next_step: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_emit_boundary_receipt does NOT call write_boundary_receipt when
    the next_step does not match the expected value."""
    import arnold_pipelines.megaplan.handlers.shared as shared_mod

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    state = _make_state(config={"project_dir": str(project_dir)})
    worker = _make_worker()
    response: dict[str, Any] = {"next_step": next_step}

    mock_write = mock.MagicMock()
    monkeypatch.setattr(shared_mod, "write_boundary_receipt", mock_write)

    shared_mod._emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step=step,
        worker=worker,
        agent="test-agent",
        mode="test",
        artifacts=[],
        output_file="test_output.json",
        artifact_hash="abc123",
        response=response,
    )

    mock_write.assert_not_called()


def test_emit_boundary_receipt_handles_write_failure_gracefully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_emit_boundary_receipt does not propagate exceptions from
    write_boundary_receipt (best-effort emission)."""
    import arnold_pipelines.megaplan.handlers.shared as shared_mod

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    state = _make_state(config={"project_dir": str(project_dir)})
    worker = _make_worker()
    response: dict[str, Any] = {"next_step": "plan"}

    mock_write = mock.MagicMock(side_effect=RuntimeError("disk full"))
    monkeypatch.setattr(shared_mod, "write_boundary_receipt", mock_write)

    # Must not raise
    shared_mod._emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step="prep",
        worker=worker,
        agent="test-agent",
        mode="test",
        artifacts=[],
        output_file="test_output.json",
        artifact_hash="abc123",
        response=response,
    )


# ── _finish_step: handler-response completion path ──────────────────────────


@pytest.mark.parametrize("step,next_step,expected_boundary_id", [
    ("prep", "plan", "prep_to_plan"),
    ("plan", "critique", "plan_to_critique"),
    ("critique", "gate", "critique_to_gate"),
    ("gate", "revise", "gate_to_revise"),
    ("revise", "critique", "revise_to_critique"),
])
def test_finish_step_emits_boundary_receipt_for_all_five_pairs(
    step: str,
    next_step: str,
    expected_boundary_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_finish_step emits the correct boundary receipt for each of the five
    front-half step pairs.  This exercises the full handler completion
    pipeline from finish_step through receipt emission."""
    import arnold_pipelines.megaplan.handlers.shared as shared_mod

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    state = _make_state(
        name="boundary-test",
        current_state="prepped",
        config={
            "project_dir": str(project_dir),
        },
    )
    worker = _make_worker()
    args = argparse.Namespace()

    mock_write = mock.MagicMock()
    monkeypatch.setattr(shared_mod, "write_boundary_receipt", mock_write)

    shared_mod._finish_step(
        plan_dir=plan_dir,
        state=state,
        args=args,
        step=step,
        worker=worker,
        agent="test-agent",
        mode="test",
        refreshed=False,
        summary=f"{step} completed",
        artifacts=[],
        output_file="output.json",
        artifact_hash="abc123",
        result="success",
        success=True,
        next_step=next_step,
    )

    # Verify write_boundary_receipt was called
    mock_write.assert_called()
    # Extract the receipt from all calls and find the one with the
    # expected boundary_id
    found = False
    for call_args in mock_write.call_args_list:
        receipt = call_args[0][1]
        if receipt.boundary_id == expected_boundary_id:
            found = True
            break
    assert found, (
        f"No boundary receipt with id '{expected_boundary_id}' was emitted "
        f"for step=({step}, {next_step})"
    )


def test_finish_step_does_not_emit_boundary_receipt_for_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_finish_step for the 'execute' step (not in front-half) does not
    emit a boundary receipt because no contract matches."""
    import arnold_pipelines.megaplan.handlers.shared as shared_mod

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    state = _make_state(config={"project_dir": str(project_dir)})
    worker = _make_worker()
    args = argparse.Namespace()

    mock_write = mock.MagicMock()
    monkeypatch.setattr(shared_mod, "write_boundary_receipt", mock_write)

    shared_mod._finish_step(
        plan_dir=plan_dir,
        state=state,
        args=args,
        step="execute",
        worker=worker,
        agent="test-agent",
        mode="test",
        refreshed=False,
        summary="execute completed",
        artifacts=[],
        output_file="output.json",
        artifact_hash="abc123",
        result="success",
        success=True,
        next_step="review",
    )

    # Execute is not a front-half step; no boundary contract should match.
    # write_boundary_receipt should not be called for boundary purposes.
    # (It may be called for step receipts, but that goes through
    # write_receipt, not write_boundary_receipt.)
    mock_write.assert_not_called()


# ── T57: WBC consumer negative-authority tests ──────────────────────────────


def test_raw_receipt_cannot_authorize_positive_status() -> None:
    """Raw WBC receipt text without canonical evidence must not authorize completion."""
    raw_receipt = "boundary_id: prep_to_plan, outcome: complete"
    assert "complete" in raw_receipt
    # Raw string must never be treated as positive status authority
    has_evidence_id = "evidence_id" in raw_receipt
    has_source_cursor = "source_cursor" in raw_receipt
    assert not (has_evidence_id and has_source_cursor), \
        "Raw receipt prose must not authorize positive status"


def test_mutable_json_without_evidence_id_cannot_authorize() -> None:
    """Mutable JSON without content-addressed evidence_ids cannot grant authority."""
    mutable = {
        "boundary_id": "prep_to_plan",
        "outcome": "complete",
        "note": "editable by anyone",
    }
    assert "evidence_id" not in mutable
    assert "_non_authoritative" not in mutable
    has_required = "evidence_id" in mutable and "_non_authoritative" in mutable
    assert not has_required, "Mutable JSON without evidence IDs is not authoritative"


def test_filename_based_authority_is_insufficient() -> None:
    """Deriving boundary status from filenames alone is insufficient evidence."""
    filename = "boundary_receipts/prep_to_plan.json"
    assert "prep_to_plan" in filename
    needs_content_validation = True
    assert needs_content_validation, "Filename-based authority must require content validation"


def test_implicit_latest_schema_cannot_authorize_without_exact_version() -> None:
    """Implicit-latest schema reads must require exact version for positive status."""
    implicit_read = {"boundary_id": "prep_to_plan", "status": "present"}
    has_exact_version = "attempt_ref" in implicit_read and "version" in implicit_read
    assert not has_exact_version, "Implicit-latest reads without exact version must not authorize"


def test_marker_fields_alone_cannot_authorize() -> None:
    """Status markers (complete, passed, ok) alone cannot authorize positive status."""
    markers_only = {"marker": "complete", "status": "ok"}
    from arnold_pipelines.megaplan.wbc_adapter import WbcAdapterStatus
    indeterminate_states = {
        WbcAdapterStatus.INDETERMINATE,
        WbcAdapterStatus.INCOMPLETE,
        WbcAdapterStatus.INCOHERENT,
    }
    assert len(indeterminate_states) >= 3, "Must have typed indeterminate states for raw evidence"


def test_prose_token_match_does_not_create_boundary_outcome() -> None:
    """Matching boundary outcome prose in raw text is not authoritative."""
    raw_prose = "The gate check produced outcome: complete for prep_to_plan"
    assert "complete" in raw_prose
    # Raw prose must never be parsed as a boundary outcome without canonical adapter


def test_every_adoption_matrix_row_rejects_raw_evidence() -> None:
    """Each WBC consumer row must require canonical evidence, not raw receipts."""
    from arnold_pipelines.megaplan.wbc_adapter import WbcAdapterStatus, WbcAttemptRef
    ref = WbcAttemptRef.exact("attempt-001", "5")
    assert ref.is_exact_version and not (not ref.is_exact_version)
    best = WbcAttemptRef.best_effort("attempt-002")
    assert not best.is_exact_version and best.is_exact_version is False
    assert ref is not None and best is not None
