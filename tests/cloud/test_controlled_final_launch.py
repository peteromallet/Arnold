from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.controlled_final_launch import ControlledFinalLaunch
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt

from tests.cloud.dispatch_test_helpers import request


WORKER = {"host": "host", "pid": 123, "boot_id": "boot"}


def test_controlled_launch_persists_order_and_is_single_use(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    assert adapter.run(lambda _context: WORKER) == WORKER
    adapter.close()
    restarted = ControlledFinalLaunch(receipt, ledger=ledger)
    with pytest.raises(RuntimeError):
        restarted.run(lambda _context: WORKER)
    states = [
        record["payload"]["launch_state_identity"]
        for record in ledger.read_nbf_events()
        if record["payload"].get("event_type") == "controlled_adapter_state"
    ]
    assert states == ["not_started", "entered", "accepted", "closed"]
