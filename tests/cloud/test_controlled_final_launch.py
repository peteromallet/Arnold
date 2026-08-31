from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.controlled_final_launch import ControlledFinalLaunch
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome

from tests.cloud.dispatch_test_helpers import request


WORKER = {"host": "host", "pid": 123, "boot_id": "boot"}


def test_controlled_launch_persists_order_and_is_single_use(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    typed = DispatchOutcome(
        kind="success",
        launch_state="accepted",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        dispatch_family_id=receipt.dispatch_family_id,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        selected_spec=receipt.normalized_spec,
        worker_identity=WORKER,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    assert adapter.run(lambda _context: typed) == typed
    adapter.close()
    restarted = ControlledFinalLaunch(receipt, ledger=ledger)
    with pytest.raises(RuntimeError):
        restarted.run(lambda _context: typed)
    states = [
        record["payload"]["launch_state_identity"]
        for record in ledger.read_nbf_events()
        if record["payload"].get("event_type") == "controlled_adapter_state"
    ]
    assert states == ["not_started", "entered", "accepted", "closed"]


def test_reopen_rejects_persisted_closed_first_history_before_state(tmp_path: Path) -> None:
    """Reopen validates the complete persisted sequence before selecting state."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        require_production_worker_dispatch_runtime,
    )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    identity = {"host": "host", "pid": 123, "boot_id": "boot"}

    # Write a deliberately malformed persisted history through the mechanism
    # journal: each record is schema-valid, but the ordered lifecycle is not.
    # This simulates legacy/corrupt storage that the normal append API refuses.
    def emit(state: str, suffix: str) -> None:
        payload = {
            "schema_version": 1,
            "event_type": "controlled_adapter_state",
            "event_id": f"reopen-{suffix}",
            "reservation_event_id": receipt.reservation_event_id,
            "admission_receipt_id": receipt.admission_receipt_id,
            "physical_door_id": receipt.physical_door_id,
            "launch_state_identity": state,
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "actor": "test",
        }
        if state == "accepted":
            payload.update(
                {
                    "phase": receipt.phase,
                    "selected_spec": receipt.normalized_spec,
                    "primary_spec": receipt.normalized_spec,
                    "logical_dispatch_id": receipt.logical_dispatch_id,
                    "worker_identity": identity,
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:00:01+00:00",
                }
            )
        ledger._journal.emit("incident.nbf", payload=payload)

    emit("closed", "closed-first")
    emit("not_started", "prefix")
    emit("entered", "entered")
    emit("accepted", "accepted")

    with pytest.raises(ValueError, match="closed before lifecycle start"):
        ledger.projection()
    # ControlledFinalLaunch must call the same full-history validation before
    # it can reopen/select a marker or expose a callable closure.
    with pytest.raises(ValueError, match="closed before lifecycle start"):
        ControlledFinalLaunch(receipt, ledger=ledger)


def test_reopen_holds_legacy_ambiguous_without_new_lifecycle_marker(tmp_path: Path) -> None:
    """Legacy ambiguity is a permanent hold, not a fifth lifecycle state."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        require_production_worker_dispatch_runtime,
    )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.incident.schema import ReservationReconciled
    from arnold_pipelines.megaplan.types import CliError

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    # This is the schema-valid legacy marker that the current append door no
    # longer emits.  It must remain replayable for old ledgers.
    ambiguous_id = "legacy-ambiguous"
    ledger._journal.emit(
        "incident.nbf",
        payload={
            "schema_version": 1,
            "event_type": "controlled_adapter_state",
            "event_id": ambiguous_id,
            "reservation_event_id": receipt.reservation_event_id,
            "admission_receipt_id": receipt.admission_receipt_id,
            "physical_door_id": receipt.physical_door_id,
            "launch_state_identity": "ambiguous",
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "actor": "legacy",
        },
    )
    reconciliation = ReservationReconciled(
        reconciliation_id="legacy-reconciliation",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        projection_key=receipt.projection_key,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        reservation_event_id=receipt.reservation_event_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        resolution="permanent_hold_ambiguous",
        evidence_kind="controlled_adapter",
        evidence_event_ids=(ambiguous_id,),
        launch_state_identity="ambiguous",
        observed_at="2026-01-01T00:00:00+00:00",
        recorded_at="2026-01-01T00:00:00+00:00",
        actor="legacy",
    )
    ledger.reconcile_reservation(reconciliation)

    before = ledger.read_nbf_events()
    first = ControlledFinalLaunch(receipt, ledger=ledger)
    after_first = ledger.read_nbf_events()
    second = ControlledFinalLaunch(receipt, ledger=ledger)
    after_second = ledger.read_nbf_events()

    assert first.permanent_hold_ambiguous is True
    assert second.permanent_hold_ambiguous is True
    assert first.state == second.state == "not_started"
    assert after_first == after_second == before
    assert first.permanent_hold_outcome == second.permanent_hold_outcome
    assert first.permanent_hold_outcome.kind == "unresolved_launch"
    assert first.permanent_hold_outcome.launch_state == "ambiguous"
    assert first.permanent_hold_outcome.provider == receipt.provider
    assert first.permanent_hold_outcome.route_liveness_identity == receipt.route_liveness_identity

    provider_calls: list[object] = []
    with pytest.raises(CliError) as raised:
        first.run(lambda context: provider_calls.append(context))
    assert raised.value.extra["reason"] == "permanent_hold_ambiguous"
    assert raised.value.extra["dispatch_outcome"] == first.permanent_hold_outcome.to_dict()
    assert provider_calls == []
    assert ledger.read_nbf_events() == before
    # The reservation remains an open reconciliation hold; it was not silently
    # released or relaunchable after reopening.
    projected = ledger.projection()["reservations"]
    assert next(iter(projected.values()))["reconciliation"] == "permanent_hold_ambiguous"
    assert next(iter(projected.values()))["closed"] is False
