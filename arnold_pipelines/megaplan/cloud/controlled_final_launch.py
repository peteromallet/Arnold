"""Persisted, single-use final-launch sequencing."""
from __future__ import annotations

from dataclasses import dataclass
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt, WorkerExecutionContextRef


@dataclass(frozen=True)
class LaunchStateRecord:
    state: str
    event_id: str
    receipt_id: str


class ControlledFinalLaunch:
    """The only primitive exposed to a production final-launch closure.

    The adapter writes ``not_started`` before exposing the closure, changes to
    ``entered`` immediately before calling it, and writes ``accepted`` as soon
    as the closure returns an accepted worker value.  Exceptions after entry
    are deliberately propagated so the shared seam can return an unresolved
    reservation instead of guessing that no process was created.
    """

    def __init__(self, receipt: WorkerAdmissionReceipt, *, ledger: IncidentLedger | None = None, actor: str = "controlled-final-launch") -> None:
        self.receipt = receipt
        self.ledger = ledger or IncidentLedger(Path(receipt.execution_context.ledger_root))
        self.actor = actor
        self._called = False
        self._state = "not_started"
        self.accepted_started_at: str | None = None
        self.accepted_finished_at: str | None = None
        self.accepted_worker_identity: Any = None
        prior = [
            record.get("payload", {})
            for record in self.ledger.read_nbf_events()
            if record.get("payload", {}).get("event_type") == "controlled_adapter_state"
            and record.get("payload", {}).get("reservation_event_id") == receipt.reservation_event_id
            and record.get("payload", {}).get("admission_receipt_id") == receipt.admission_receipt_id
        ]
        # A fresh adapter instance must not turn a restart into a second
        # physical launch.  Restore the strongest persisted state and expose
        # the same single-use guard that an in-process instance would have.
        for state in ("closed", "accepted", "entered", "not_started"):
            marker = next((item for item in prior if item.get("launch_state_identity") == state), None)
            if marker is None:
                continue
            self._state = state
            self._called = state in {"entered", "accepted", "closed"}
            if state in {"accepted", "closed"}:
                self.accepted_worker_identity = marker.get("worker_identity")
                self.accepted_started_at = marker.get("started_at")
                self.accepted_finished_at = marker.get("finished_at")
            break
        else:
            self._persist("not_started")

    @property
    def state(self) -> str:
        return self._state

    @property
    def context(self) -> WorkerExecutionContextRef:
        return self.receipt.execution_context

    def _persist(self, state: str, *, worker_identity: Any = None, started_at: str | None = None, finished_at: str | None = None) -> dict[str, Any]:
        if state == "entered" and self._state != "not_started":
            raise RuntimeError("controlled final launch entered out of order")
        if state == "accepted" and self._state != "entered":
            raise RuntimeError("controlled final launch accepted out of order")
        if state == "closed" and self._state != "accepted":
            raise RuntimeError("controlled final launch closed out of order")
        event = self.ledger.append_controlled_adapter_state(
            reservation_event_id=self.receipt.reservation_event_id,
            admission_receipt_id=self.receipt.admission_receipt_id,
            physical_door_id=self.receipt.physical_door_id,
            launch_state_identity=state,
            phase=self.receipt.phase,
            selected_spec=self.receipt.normalized_spec,
            primary_spec=self.receipt.normalized_spec,
            logical_dispatch_id=self.receipt.logical_dispatch_id,
            worker_identity=worker_identity,
            started_at=started_at,
            finished_at=finished_at,
            actor=self.actor,
        )
        self._state = state
        return event

    def run(self, launch: Callable[[WorkerExecutionContextRef], Any]) -> Any:
        if self._called:
            raise RuntimeError("controlled final launch closure may be called only once")
        if not callable(launch):
            raise TypeError("final launch must be callable")
        self._called = True
        self._persist("entered")
        # The receipt is part of the process boundary, not merely an argument
        # visible to an in-process test closure.  Put the exact immutable
        # context in the inherited environment while the final closure runs so
        # subprocess/managed-command launches and their running receipts carry
        # the same admission identity.  Restore the parent environment even
        # when the closure raises; a later logical dispatch must never inherit
        # a prior worker's receipt.
        with _execution_context_environment(self.context):
            value = launch(self.context)
        # Acceptance is a process-boundary fact.  Never manufacture the
        # supervisor's identity after a closure returns: a worker may have
        # exited, failed to start, or been delegated elsewhere.  Adapters must
        # return an explicit identity captured by the launcher (or a typed
        # LaunchResult carrying that identity) before this marker is written.
        started_at = getattr(value, "started_at", None) or datetime.now(timezone.utc).isoformat()
        finished_at = getattr(value, "finished_at", None) or datetime.now(timezone.utc).isoformat()
        worker_identity = getattr(value, "worker_identity", None)
        if isinstance(value, dict):
            started_at = value.get("started_at") or started_at
            finished_at = value.get("finished_at") or finished_at
            worker_identity = value.get("worker_identity") or worker_identity
            if worker_identity is None and all(key in value for key in ("host", "pid", "boot_id")):
                worker_identity = value
        # LaunchResult is imported lazily to avoid the worker_dispatch ↔
        # controlled adapter import cycle.
        from arnold_pipelines.megaplan.cloud.worker_dispatch import LaunchResult
        if isinstance(value, LaunchResult):
            if not value.accepted:
                self._persist("ambiguous")
                raise RuntimeError("launch result did not prove acceptance")
            started_at = value.started_at or started_at
            finished_at = value.finished_at or finished_at
            worker_identity = value.worker_identity or worker_identity
            if worker_identity is None and isinstance(value.value, dict) and all(
                key in value.value for key in ("host", "pid", "boot_id")
            ):
                worker_identity = value.value
        if not isinstance(worker_identity, dict):
            self._persist("ambiguous")
            raise RuntimeError("accepted launch requires explicit worker identity")
        if (
            not isinstance(worker_identity.get("host"), str)
            or not worker_identity.get("host")
            or not isinstance(worker_identity.get("boot_id"), str)
            or not worker_identity.get("boot_id")
            or isinstance(worker_identity.get("pid"), bool)
            or not isinstance(worker_identity.get("pid"), int)
            or worker_identity.get("pid") <= 0
        ):
            self._persist("ambiguous")
            raise RuntimeError("accepted launch worker identity is malformed")
        self.accepted_started_at = started_at
        self.accepted_finished_at = finished_at
        self.accepted_worker_identity = worker_identity
        self._persist("accepted", worker_identity=worker_identity, started_at=started_at, finished_at=finished_at)
        return value

    def close(self) -> None:
        if self._state == "accepted":
            self._persist("closed")



__all__ = ["ControlledFinalLaunch", "LaunchStateRecord"]


@contextmanager
def _execution_context_environment(context: WorkerExecutionContextRef):
    variable = "ARNOLD_WORKER_EXECUTION_CONTEXT"
    previous = os.environ.get(variable)
    os.environ.update(context.to_environment(variable=variable))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous
