from pathlib import Path
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.incident.schema import WorkerDisposition
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome

WORKER = {"host": "test-host", "pid": 1234, "boot_id": "boot-1"}


def test_disposition_terminal_links_existing_record_once(tmp_path: Path):
    ledger=IncidentLedger(tmp_path); f="f"*64
    r=ledger.reserve(plan_id="p",phase="ph",projection_key="pk",semantic_dispatch_fingerprint=f,logical_dispatch_id="log",dispatch_family_id="fam",selected_spec="spec")
    receipt = r["payload"]["admission_receipt_id"]
    d=WorkerDisposition("d","in_band","p","ph","fam","log",receipt,f,"spec","watchdog","k","wedge","SIGTERM",1,WORKER,"2026-01-01T00:00:00Z",{"x":1})
    ledger.append_disposition(d)
    ledger.append_controlled_adapter_state(reservation_event_id=r["payload"]["event_id"], admission_receipt_id=receipt, physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="log", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    o=DispatchOutcome("worker_disposition","accepted","p","ph","fam","log",receipt,f,"spec",WORKER,"2026-01-01T00:00:00Z","2026-01-01T00:00:01Z",disposition_id="d")
    first=ledger.append_terminal_outcome(outcome=o,reservation_event_id=r["payload"]["event_id"],projection_key="pk")
    second=ledger.append_terminal_outcome(outcome=o,reservation_event_id=r["payload"]["event_id"],projection_key="pk")
    assert first == second and len(ledger.projection()["terminals"]) == 1


def test_conflicting_terminal_kind_rejected(tmp_path):
    import pytest
    ledger=IncidentLedger(tmp_path); f="f"*64; r=ledger.reserve(plan_id="p",phase="ph",projection_key="pk",semantic_dispatch_fingerprint=f,logical_dispatch_id="log",dispatch_family_id="fam",selected_spec="spec")
    receipt = r["payload"]["admission_receipt_id"]
    ledger.append_controlled_adapter_state(reservation_event_id=r["payload"]["event_id"], admission_receipt_id=receipt, physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="log", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    ok=DispatchOutcome("success","accepted","p","ph","fam","log",receipt,f,"spec",WORKER,"2026-01-01T00:00:00Z","2026-01-01T00:00:01Z",success_payload={"ok":1})
    ledger.append_terminal_outcome(outcome=ok,reservation_event_id=r["payload"]["event_id"],projection_key="pk")
    fail=DispatchOutcome("ordinary_terminal_failure","accepted","p","ph","fam","log",receipt,f,"spec",WORKER,"2026-01-01T00:00:00Z","2026-01-01T00:00:01Z",terminal_failure={"error":"x"})
    with pytest.raises(ValueError): ledger.append_terminal_outcome(outcome=fail,reservation_event_id=r["payload"]["event_id"],projection_key="pk")
