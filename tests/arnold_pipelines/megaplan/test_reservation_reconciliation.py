import pytest
from pathlib import Path
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.incident.schema import ReservationReconciled
from arnold_pipelines.megaplan.incident.schema import WorkerDisposition
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome

WORKER = {"host": "test-host", "pid": 1234, "boot_id": "boot-1"}


def test_positive_no_launch_reconciliation_only(tmp_path: Path):
    ledger = IncidentLedger(tmp_path); f="f"*64
    r=ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint=f, logical_dispatch_id="l", dispatch_family_id="fam")
    receipt = r["payload"]["admission_receipt_id"]
    marker = {"schema_version": 1, "event_type": "controlled_adapter_state", "event_id": "marker", "reservation_event_id": r["payload"]["event_id"], "admission_receipt_id": receipt, "physical_door_id": r["payload"]["physical_door_id"], "launch_state_identity": "not_started", "physical_operation_evidence": {"reservation_event_id": r["payload"]["event_id"], "admission_receipt_id": receipt, "physical_door_id": r["payload"]["physical_door_id"], "launch_state_identity": "not_started", "observed_at": "2026-01-01T00:00:00Z"}, "recorded_at": "2026-01-01T00:00:00Z", "actor": "test"}
    ledger._append_nbf(marker)
    x=ReservationReconciled("rec", "p", "ph", "pk", "l", receipt, r["payload"]["event_id"], f, "released_no_launch", "controlled_adapter", ("marker",), "not_started", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
    ledger.reconcile_reservation(x); assert ledger.projection()["reservations"]
    with pytest.raises(ValueError): ledger.reconcile_reservation(ReservationReconciled("rec2", "p", "ph", "pk", "l", receipt, r["payload"]["event_id"], f, "released_no_launch", "missing", ("x",), "entered", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test"))


def test_ambiguous_reconciliation_is_held(tmp_path):
    ledger=IncidentLedger(tmp_path); f="f"*64; r=ledger.reserve(plan_id="p",phase="ph",projection_key="pk",semantic_dispatch_fingerprint=f,logical_dispatch_id="l",dispatch_family_id="fam")
    receipt = r["payload"]["admission_receipt_id"]
    marker = {"schema_version": 1, "event_type": "controlled_adapter_state", "event_id": "amb", "reservation_event_id": r["payload"]["event_id"], "admission_receipt_id": receipt, "physical_door_id": r["payload"]["physical_door_id"], "launch_state_identity": "ambiguous", "recorded_at": "2026-01-01T00:00:00Z", "actor": "test"}
    ledger._append_nbf(marker)
    x=ReservationReconciled("rec", "p", "ph", "pk", "l", receipt, r["payload"]["event_id"], f, "permanent_hold_ambiguous", "adapter", ("amb",), "ambiguous", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
    ledger.reconcile_reservation(x); assert any(not v["closed"] for v in ledger.projection()["reservations"].values())


def test_recovered_disposition_links_existing_record_without_duplicate(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    fingerprint = "f" * 64
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint=fingerprint, logical_dispatch_id="log", dispatch_family_id="fam", selected_spec="spec")
    receipt = reservation["payload"]["admission_receipt_id"]
    ledger.append_controlled_adapter_state(reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=receipt, physical_door_id="default-door", launch_state_identity="not_started")
    ledger.append_controlled_adapter_state(reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=receipt, physical_door_id="default-door", launch_state_identity="entered")
    ledger.append_controlled_adapter_state(reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=receipt, physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="log", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    disposition = WorkerDisposition("disp", "in_band", "p", "ph", "fam", "log", receipt, fingerprint, "spec", "watchdog", "watch", "wedge", "SIGTERM", 1.0, WORKER, "2026-01-01T00:00:00Z", {"x": 1})
    ledger.append_disposition(disposition)
    outcome = DispatchOutcome("worker_disposition", "accepted", "p", "ph", "fam", "log", receipt, fingerprint, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", disposition_id="disp")
    terminal = ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=reservation["payload"]["event_id"], projection_key="pk")
    recovered = ReservationReconciled("recovered", "p", "ph", "pk", "log", receipt, reservation["payload"]["event_id"], fingerprint, "terminal_outcome_recovered", "ledger", (terminal["payload"]["event_id"], "disp"), "accepted", "2026-01-01T00:00:02Z", "2026-01-01T00:00:02Z", "test", worker_identity=WORKER, terminal_outcome_event_id=terminal["payload"]["terminal_outcome_id"])
    first = ledger.reconcile_reservation(recovered)
    assert ledger.reconcile_reservation(recovered) == first
    assert len(ledger.projection()["terminals"]) == 1


def test_invalid_replay_record_never_projects(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    ledger.events_path.parent.mkdir(parents=True, exist_ok=True)
    ledger.events_path.write_text('{"seq":1,"kind":"incident.nbf.admission_reserved","payload":{"schema_version":1,"event_type":"admission_reserved"}}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        ledger.projection()
