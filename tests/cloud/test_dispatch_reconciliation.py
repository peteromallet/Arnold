from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.controlled_final_launch import ControlledFinalLaunch
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt, reconcile_no_launch, require_production_worker_dispatch_runtime, WorkerAdmissionRequest
from arnold_pipelines.megaplan.cloud.worker_dispatch import LaunchResult, dispatch_with_admission
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome

from tests.cloud.dispatch_test_helpers import request


def test_truthful_no_launch_releases_only_with_persisted_evidence(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(
        receipt,
        ledger=ledger,
        physical_operation_evidence={
            "reservation_event_id": receipt.reservation_event_id,
            "admission_receipt_id": receipt.admission_receipt_id,
            "physical_door_id": receipt.physical_door_id,
            "launch_state_identity": "not_started",
            "observed_at": "2026-08-30T00:00:00+00:00",
        },
    )
    evidence_id = ledger.read_nbf_events()[-1]["payload"]["event_id"]
    outcome = reconcile_no_launch(receipt, evidence_event_ids=[evidence_id], ledger=ledger)
    assert outcome.kind == "no_launch"
    assert ledger.projection()["reservations"]


def test_dispatch_wires_receipt_bound_pre_entry_release(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    req = request(tmp_path, ledger=ledger)
    def launch(_context):
        raise AssertionError("pre-entry release must not enter the launch closure")

    def pre_entry(_context):
        marker_id = ledger.read_nbf_events()[-1]["payload"]["event_id"]
        return LaunchResult(False, {"evidence_event_ids": (marker_id,)})

    receipt = require_production_worker_dispatch_runtime(req)
    assert isinstance(receipt, WorkerAdmissionReceipt)
    launch.pre_entry = pre_entry
    outcome = dispatch_with_admission(req, launch, ledger=ledger, gate=lambda _request: receipt)
    assert outcome.kind == "unresolved_launch"
    reservations = ledger.projection()["reservations"]
    assert len(reservations) == 1
    assert next(iter(reservations.values()))["closed"] is False
    assert next(iter(reservations.values()))["accepted_launch"] is False
    assert not ledger.projection()["terminals"]


def _accepted_outcome(receipt: WorkerAdmissionReceipt) -> DispatchOutcome:
    return DispatchOutcome(
        kind="success",
        launch_state="accepted",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        dispatch_family_id=receipt.dispatch_family_id,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        selected_spec=receipt.normalized_spec,
        worker_identity={"host": "host", "pid": 123, "boot_id": "boot"},
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )


def test_reconcile_no_launch_rejects_selective_not_started_when_accepted_exists(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    first_id = ledger.read_nbf_events()[-1]["payload"]["event_id"]
    adapter.run(lambda _context: _accepted_outcome(receipt))
    with pytest.raises(ValueError, match="contradictory"):
        reconcile_no_launch(receipt, evidence_event_ids=[first_id], ledger=ledger)
    assert not any(
        item["payload"].get("resolution") == "released_no_launch"
        for item in ledger.read_nbf_events()
    )


def test_reconciliation_explicit_persisted_state_matrix(tmp_path: Path) -> None:
    for state in ("adapter_only", "entered", "accepted"):
        root = tmp_path / state
        ledger = IncidentLedger(root)
        receipt = require_production_worker_dispatch_runtime(request(root, ledger=ledger))
        assert isinstance(receipt, WorkerAdmissionReceipt)
        adapter = ControlledFinalLaunch(receipt, ledger=ledger)
        marker_id = ledger.read_nbf_events()[-1]["payload"]["event_id"]
        if state in {"entered", "accepted"}:
            adapter._persist("entered")
        if state == "accepted":
            adapter._persist(
                "accepted",
                worker_identity={"host": "host", "pid": 123, "boot_id": "boot"},
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:01+00:00",
            )
        if state == "adapter_only":
            with pytest.raises(ValueError, match="bound not_started"):
                reconcile_no_launch(receipt, evidence_event_ids=[marker_id], ledger=ledger)
        else:
            with pytest.raises(ValueError, match="contradictory"):
                reconcile_no_launch(receipt, evidence_event_ids=[marker_id], ledger=ledger)
        assert not ledger.projection()["reservations"][receipt.reservation_event_id if receipt.reservation_event_id in ledger.projection()["reservations"] else next(iter(ledger.projection()["reservations"]))].get("reconciliation")


def test_no_launch_commits_before_projection_and_replays_idempotently(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(
        receipt,
        ledger=ledger,
        physical_operation_evidence={
            "reservation_event_id": receipt.reservation_event_id,
            "admission_receipt_id": receipt.admission_receipt_id,
            "physical_door_id": receipt.physical_door_id,
            "launch_state_identity": "not_started",
            "observed_at": "2026-08-30T00:00:00+00:00",
        },
    )
    evidence_id = ledger.read_nbf_events()[-1]["payload"]["event_id"]
    first = reconcile_no_launch(receipt, evidence_event_ids=[evidence_id], ledger=ledger)
    before = len(ledger.read_nbf_events())
    second = reconcile_no_launch(receipt, evidence_event_ids=[evidence_id], ledger=ledger)
    assert second.reconciliation_event_id == first.reconciliation_event_id
    assert len(ledger.read_nbf_events()) == before
