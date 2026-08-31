"""Persisted, single-use final-launch sequencing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt, WorkerExecutionContextRef, LaunchResult


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

    def __init__(self, receipt: WorkerAdmissionReceipt, *, ledger: IncidentLedger | None = None, actor: str = "controlled-final-launch", physical_operation_evidence: dict[str, Any] | None = None) -> None:
        self.receipt = receipt
        self.ledger = ledger or IncidentLedger(Path(receipt.execution_context.ledger_root))
        self.actor = actor
        self.physical_operation_evidence = physical_operation_evidence
        self._called = False
        self._state = "not_started"
        self.accepted_started_at: str | None = None
        self.accepted_finished_at: str | None = None
        self.accepted_worker_identity: Any = None
        # ``ambiguous`` was written by pre-attempt-6 adapters.  It is not a
        # lifecycle state: keep the four-state projection intact and retain a
        # separate, durable hold so a reopen can never manufacture a fresh
        # ``not_started`` marker or expose the launch closure.
        self._permanent_hold_ambiguous = False
        self._permanent_hold_outcome: Any = None
        # Reopen is a full-history validation boundary.  Never select a
        # strongest marker from a contradictory persisted sequence.
        self.ledger.projection()
        matching = [
            record.get("payload", {})
            for record in self.ledger.read_nbf_events()
            if (
                record.get("payload", {}).get("reservation_event_id")
                == receipt.reservation_event_id
                and record.get("payload", {}).get("admission_receipt_id")
                == receipt.admission_receipt_id
            )
        ]
        prior = [
            payload for payload in matching
            if payload.get("event_type") == "controlled_adapter_state"
            and payload.get("launch_state_identity") != "ambiguous"
        ]
        # Reopen from the ordered terminal marker.  Selecting the strongest
        # marker would silently resurrect a stale accepted/closed state after
        # a malformed or conflicting append.
        if prior:
            marker = prior[-1]
            self._state = str(marker.get("launch_state_identity"))
            self._called = self._state in {"entered", "accepted", "closed"}
            if self._state in {"accepted", "closed"}:
                self.accepted_worker_identity = marker.get("worker_identity")
                self.accepted_started_at = marker.get("started_at")
                self.accepted_finished_at = marker.get("finished_at")
        ambiguous_marker = any(
            payload.get("event_type") == "controlled_adapter_state"
            and (
                payload.get("launch_state_identity") == "ambiguous"
                or payload.get("permanent_hold_ambiguous") is True
            )
            for payload in matching
        )
        ambiguous_reconciliation = any(
            payload.get("event_type") == "reservation_reconciled"
            and (
                payload.get("resolution") == "permanent_hold_ambiguous"
                or payload.get("launch_state_identity") == "ambiguous"
                or payload.get("permanent_hold_ambiguous") is True
            )
            for payload in matching
        )
        if ambiguous_marker or ambiguous_reconciliation:
            self._permanent_hold_ambiguous = True
            # The typed outcome is deliberately derived from the original
            # receipt.  This keeps provider/route and execution-context fields
            # stable across byte-identical reopens; a reconciliation identity
            # is included when one was already persisted.
            from arnold_pipelines.megaplan.cloud.worker_dispatch import _unresolved_outcome
            self._permanent_hold_outcome = _unresolved_outcome(receipt)
            reconciliation = next(
                (
                    payload for payload in matching
                    if payload.get("event_type") == "reservation_reconciled"
                    and payload.get("resolution") == "permanent_hold_ambiguous"
                ),
                None,
            )
            if reconciliation:
                from dataclasses import replace
                self._permanent_hold_outcome = replace(
                    self._permanent_hold_outcome,
                    reconciliation_event_id=str(
                        reconciliation.get("reconciliation_id")
                        or reconciliation.get("event_id")
                    ),
                )
            self._called = True
        elif not prior:
            self._persist("not_started")

    @property
    def state(self) -> str:
        return self._state

    @property
    def context(self) -> WorkerExecutionContextRef:
        return self.receipt.execution_context

    @property
    def permanent_hold_ambiguous(self) -> bool:
        """Whether legacy history permanently holds this reservation."""
        return self._permanent_hold_ambiguous

    @property
    def permanent_hold_outcome(self) -> Any:
        """The stable typed unresolved outcome for a legacy hold, if any."""
        return self._permanent_hold_outcome

    def _raise_permanent_hold(self) -> None:
        from arnold_pipelines.megaplan.types import CliError
        raise CliError(
            "scheduling_condition",
            "controlled final launch is permanently held for ambiguous legacy history",
            extra={
                "reason": "permanent_hold_ambiguous",
                "dispatch_outcome": self._permanent_hold_outcome.to_dict(),
                "reservation_event_id": self.receipt.reservation_event_id,
                "admission_receipt_id": self.receipt.admission_receipt_id,
                "physical_door_id": self.receipt.physical_door_id,
                "execution_context": self.context.to_dict(),
            },
        )

    def _persist(self, state: str, *, worker_identity: Any = None, started_at: str | None = None, finished_at: str | None = None) -> dict[str, Any]:
        if self._permanent_hold_ambiguous and state != "not_started":
            self._raise_permanent_hold()
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
            physical_operation_evidence=(
                self.physical_operation_evidence if state == "not_started" else None
            ),
            actor=self.actor,
        )
        self._state = state
        return event

    def run(self, launch: Callable[[WorkerExecutionContextRef], Any]) -> Any:
        if self._permanent_hold_ambiguous:
            # Keep the historical exception boundary used by dispatchers, but
            # include the exact typed hold for callers that need to reconcile
            # it.  Crucially this occurs before callable validation/entry and
            # therefore cannot trigger WBC, provider, or relaunch effects.
            self._raise_permanent_hold()
        if self._called:
            raise RuntimeError("controlled final launch closure may be called only once")
        if not callable(launch):
            raise TypeError("final launch must be callable")
        self._called = True
        self._persist("entered")
        try:
            value = launch(self.context)
        except Exception as exc:
            from arnold_pipelines.megaplan.cloud.worker_dispatch import _outcome_from_terminal_exception
            value = _outcome_from_terminal_exception(
                exc,
                self.receipt,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            )
            if value is None:
                raise
        if not self._is_accepted_result(value):
            raise TypeError(
                "final launch must return DispatchOutcome or a typed worker result"
            )
        context_value = value.value if hasattr(value, "value") and hasattr(value, "accepted") else value
        payload = getattr(context_value, "payload", None)
        if isinstance(payload, dict) and isinstance(payload.get("dispatch_outcome"), dict):
            context_value = payload["dispatch_outcome"]
        started_at = getattr(context_value, "started_at", None) or datetime.now(timezone.utc).isoformat()
        finished_at = getattr(context_value, "finished_at", None) or datetime.now(timezone.utc).isoformat()
        worker_identity = getattr(context_value, "worker_identity", None)
        if isinstance(value, LaunchResult):
            worker_identity = value.worker_identity or worker_identity
            started_at = value.started_at or started_at
            finished_at = value.finished_at or finished_at
        if isinstance(context_value, dict):
            started_at = context_value.get("started_at") or started_at
            finished_at = context_value.get("finished_at") or finished_at
            worker_identity = context_value.get("worker_identity") or worker_identity
        if not isinstance(worker_identity, dict):
            if self.receipt.production_intent:
                raise TypeError("accepted production launch result must carry authoritative worker identity")
            from arnold_pipelines.megaplan.cloud.worker_dispatch import _worker_identity
            worker_identity = dict(_worker_identity(None))
        self.accepted_started_at = started_at
        self.accepted_finished_at = finished_at
        self.accepted_worker_identity = worker_identity
        self._persist("accepted", worker_identity=worker_identity, started_at=started_at, finished_at=finished_at)
        return value

    @staticmethod
    def _is_accepted_result(value: Any) -> bool:
        from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
        from arnold_pipelines.megaplan.cloud.worker_dispatch import LaunchResult

        if isinstance(value, LaunchResult):
            return value.accepted and ControlledFinalLaunch._is_accepted_result(value.value)

        if isinstance(value, DispatchOutcome):
            return value.kind not in {"no_launch", "unresolved_launch"}
        if isinstance(value, dict):
            try:
                decoded = DispatchOutcome.from_dict(value)
            except (TypeError, ValueError):
                return False
            return decoded.kind not in {"no_launch", "unresolved_launch"}
        if isinstance(value, tuple) and len(value) == 4:
            worker = value[0]
            from arnold_pipelines.megaplan.cloud.worker_dispatch import _worker_result_is_failure_shaped
            if _worker_result_is_failure_shaped(worker):
                return False
            return (
                type(worker).__name__ == "WorkerResult"
                and type(worker).__module__.endswith("workers._impl")
            )
        if type(value).__name__ == "ManagedCommandResult" and type(value).__module__.endswith("worker_dispatch"):
            return True
        if type(value).__name__ == "WorkerResult":
            from arnold_pipelines.megaplan.cloud.worker_dispatch import _worker_result_is_failure_shaped
            if _worker_result_is_failure_shaped(value):
                return False
        return (
            type(value).__name__ == "WorkerResult"
            and type(value).__module__.endswith("workers._impl")
        )

    def close(self) -> None:
        if self._state == "accepted":
            self._persist("closed")



__all__ = ["ControlledFinalLaunch", "LaunchStateRecord"]
