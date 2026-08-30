from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    WorkerAdmissionRequest,
    build_authorized_linked_child_request,
)
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome

from tests.cloud.dispatch_test_helpers import request


def test_linked_child_requires_terminal_parent_and_new_logical_id(tmp_path: Path) -> None:
    parent = request(tmp_path)
    child = build_authorized_linked_child_request(
        {**parent.__dict__, "terminal_outcome_event_id": "terminal"},
        selected_spec=parent.selected_spec,
        logical_dispatch_id="child",
        authorizing_event_id="authorization",
    )
    assert isinstance(child, WorkerAdmissionRequest)
    assert child.parent_logical_dispatch_id == parent.logical_dispatch_id
    assert child.authorizing_event_id == "authorization"


def test_linked_child_rejects_unresolved_parent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no-launch or unresolved"):
        build_authorized_linked_child_request(
            {"kind": "unresolved_launch"},
            selected_spec="codex:gpt-5.5",
            logical_dispatch_id="child",
            authorizing_event_id="authorization",
        )


def test_production_linked_child_requires_authoritative_ledger(tmp_path: Path) -> None:
    parent = request(tmp_path, production_intent=True)
    with pytest.raises(ValueError, match="authoritative ledger"):
        build_authorized_linked_child_request(
            {**parent.__dict__, "terminal_outcome_event_id": "terminal"},
            selected_spec=parent.selected_spec,
            logical_dispatch_id="child",
            authorizing_event_id="authorization",
        )


def test_production_linked_child_accepts_canonical_terminal_and_grant(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    parent = request(tmp_path, production_intent=True, logical_dispatch_id="parent", ledger=ledger)
    reservation_record = ledger.reserve(
        plan_id=parent.plan_id,
        phase=parent.phase,
        projection_key=parent.projection_key,
        semantic_dispatch_fingerprint="f" * 64,
        logical_dispatch_id=parent.logical_dispatch_id,
        dispatch_family_id=parent.dispatch_family_id,
        physical_door_id=parent.physical_door_id,
        selected_spec=parent.selected_spec,
        primary_spec=parent.selected_spec,
    )
    reservation = reservation_record["payload"]
    receipt_id = reservation["admission_receipt_id"]
    worker = {"host": "test-host", "pid": 1234, "boot_id": "boot-1"}
    marker = dict(
        reservation_event_id=reservation["event_id"],
        admission_receipt_id=receipt_id,
        physical_door_id=parent.physical_door_id,
    )
    ledger.append_controlled_adapter_state(**marker, launch_state_identity="not_started")
    ledger.append_controlled_adapter_state(**marker, launch_state_identity="entered")
    ledger.append_controlled_adapter_state(
        **marker,
        launch_state_identity="accepted",
        phase=parent.phase,
        selected_spec=parent.selected_spec,
        primary_spec=parent.selected_spec,
        logical_dispatch_id=parent.logical_dispatch_id,
        worker_identity=worker,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
    )
    outcome = DispatchOutcome(
        "success", "accepted", parent.plan_id, parent.phase,
        parent.dispatch_family_id, parent.logical_dispatch_id,
        receipt_id, "f" * 64, parent.selected_spec, worker, "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:01Z", success_payload={"ok": True},
    )
    terminal = ledger.append_terminal_outcome(
        outcome=outcome,
        reservation_event_id=reservation["event_id"],
        projection_key=parent.projection_key,
        physical_door_id=parent.physical_door_id,
        execution_context_identity=reservation.get("execution_context_identity", ""),
    )
    grant = ledger.append_authorization_granted(
        plan_id=parent.plan_id,
        phase=parent.phase,
        parent_logical_dispatch_id=parent.logical_dispatch_id,
        parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"],
        parent_dispatch_family_id=parent.dispatch_family_id,
        parent_physical_door_id=parent.physical_door_id,
    )
    child = build_authorized_linked_child_request(
        parent,
        selected_spec=parent.selected_spec,
        logical_dispatch_id="child",
        authorizing_event_id=grant["payload"]["event_id"],
        parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"],
        ledger=ledger,
    )
    assert child.parent_terminal_event_id == terminal["payload"]["terminal_outcome_id"]
    assert child.parent_physical_door_id == parent.physical_door_id
