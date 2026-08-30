from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.controlled_final_launch import ControlledFinalLaunch
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt, reconcile_no_launch, require_production_worker_dispatch_runtime, WorkerAdmissionRequest
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

from tests.cloud.dispatch_test_helpers import request


def test_truthful_no_launch_releases_only_with_persisted_evidence(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    evidence_id = ledger.read_nbf_events()[-1]["payload"]["event_id"]
    outcome = reconcile_no_launch(receipt, evidence_event_ids=[evidence_id], ledger=ledger)
    assert outcome.kind == "no_launch"
    assert ledger.projection()["reservations"]
