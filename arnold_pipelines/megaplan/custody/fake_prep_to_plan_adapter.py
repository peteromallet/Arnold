"""Fake prep_to_plan adapter spike routed through the shared WBC facade."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from arnold.workflow.boundary_evidence import BoundaryOutcome, BoundaryReceipt
from arnold.workflow.execution_attempt_ledger import LedgerEvent
from arnold_pipelines.megaplan.receipts.writer import write_boundary_receipt
from arnold_pipelines.megaplan.workflows.boundary_contracts import prep_to_plan

from .action_validator import ActionBoundaryContext
from .wbc_runtime import ImmutableAttemptArtifacts, PromotionMode, RuntimeProducerResult, WbcRuntimeProducerFacade

PREP_TO_PLAN_WRITER_ID = "megaplan.fake_adapter.prep_to_plan"
PREP_TO_PLAN_SURFACE = "megaplan.fake_adapter.prep_to_plan"
PREP_TO_PLAN_START_SOURCE_LOOKUP_KEY = "prep_to_plan:start"
PREP_TO_PLAN_COMPLETE_SOURCE_LOOKUP_KEY = "prep_to_plan:complete"


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({str(key): _freeze_json(item) for key, item in sorted(value.items())})


@dataclass(frozen=True)
class FakePrepToPlanDispatchResult:
    receipt: BoundaryReceipt
    user_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_payload", _freeze_mapping(self.user_payload))


@dataclass(frozen=True)
class FakePrepToPlanAttemptResult:
    reserve: RuntimeProducerResult
    start: RuntimeProducerResult
    complete: RuntimeProducerResult
    dispatch_result: FakePrepToPlanDispatchResult
    receipt_path: Path
    persisted_receipt: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_path", Path(self.receipt_path))
        object.__setattr__(self, "persisted_receipt", _freeze_mapping(self.persisted_receipt))


DispatchCallable = Callable[[RuntimeProducerResult], FakePrepToPlanDispatchResult]


class FakePrepToPlanAdapter:
    """Minimal adapter proving a prep_to_plan write path through the WBC facade."""

    def __init__(
        self,
        *,
        plan_dir: Path,
        facade: WbcRuntimeProducerFacade,
        project_dir: Path | None = None,
        writer_id: str = PREP_TO_PLAN_WRITER_ID,
        surface_name: str = PREP_TO_PLAN_SURFACE,
        expected_source_version: str = "source.v1",
    ) -> None:
        self._plan_dir = Path(plan_dir)
        self._facade = facade
        self._project_dir = None if project_dir is None else Path(project_dir)
        self._writer_id = str(writer_id)
        self._surface_name = str(surface_name)
        self._expected_source_version = str(expected_source_version)
        if self._facade.promotion_mode == PromotionMode.PROMOTE:
            raise ValueError("fake prep_to_plan adapter requires provider effects to stay disabled")

    @property
    def plan_dir(self) -> Path:
        return self._plan_dir

    @property
    def facade(self) -> WbcRuntimeProducerFacade:
        return self._facade

    def build_receipt(
        self,
        *,
        invocation_id: str,
        artifact_refs: tuple[str, ...] = ("research.md", "brief.md"),
        state_observation: Mapping[str, Any] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> BoundaryReceipt:
        observation = {
            "current_phase": prep_to_plan.phase.value,
            "current_state": "prepped",
            "next_step": "plan",
        }
        if state_observation:
            observation.update(dict(state_observation))
        return BoundaryReceipt(
            boundary_id=prep_to_plan.boundary_id,
            workflow_id=prep_to_plan.workflow_id,
            row_id=prep_to_plan.row_id,
            invocation_id=invocation_id,
            artifact_refs=artifact_refs,
            state_observation=observation,
            history_ref=prep_to_plan.expected_history_entry,
            phase_result_ref="phase_result.json" if prep_to_plan.phase_result_required else None,
            outcome=BoundaryOutcome.COMPLETE,
            details=details or {},
        )

    def run(
        self,
        *,
        attempt_id: str,
        start_event: LedgerEvent,
        complete_event: LedgerEvent,
        dispatch: DispatchCallable,
        start_action_context: ActionBoundaryContext,
        completion_action_context: ActionBoundaryContext,
        artifacts: ImmutableAttemptArtifacts | None = None,
        start_source_lookup_key: str = PREP_TO_PLAN_START_SOURCE_LOOKUP_KEY,
        complete_source_lookup_key: str = PREP_TO_PLAN_COMPLETE_SOURCE_LOOKUP_KEY,
    ) -> FakePrepToPlanAttemptResult:
        reserve = self._facade.reserve_attempt(
            attempt_id=attempt_id,
            writer_id=self._writer_id,
            surface_name=self._surface_name,
            source_lookup_key=start_source_lookup_key,
            expected_source_version=self._expected_source_version,
            action_context=start_action_context,
            artifacts=artifacts,
        )
        start = self._facade.start_attempt(
            attempt_id=attempt_id,
            event=start_event,
            writer_id=self._writer_id,
            surface_name=self._surface_name,
            source_lookup_key=start_source_lookup_key,
            expected_source_version=self._expected_source_version,
            action_context=start_action_context,
            artifacts=artifacts,
        )
        dispatch_result = dispatch(start)
        self._persist_receipt(dispatch_result.receipt)
        complete = self._facade.complete_attempt(
            attempt_id=attempt_id,
            event=complete_event,
            writer_id=self._writer_id,
            surface_name=self._surface_name,
            source_lookup_key=complete_source_lookup_key,
            expected_source_version=self._expected_source_version,
            action_context=completion_action_context,
            artifacts=artifacts,
        )
        receipt_path = self._receipt_path(dispatch_result.receipt.boundary_id)
        persisted_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        return FakePrepToPlanAttemptResult(
            reserve=reserve,
            start=start,
            complete=complete,
            dispatch_result=dispatch_result,
            receipt_path=receipt_path,
            persisted_receipt=persisted_receipt,
        )

    def _persist_receipt(self, receipt: BoundaryReceipt) -> None:
        if receipt.boundary_id != prep_to_plan.boundary_id:
            raise ValueError(
                f"fake prep_to_plan adapter requires boundary_id {prep_to_plan.boundary_id!r}, "
                f"got {receipt.boundary_id!r}"
            )
        if receipt.workflow_id != prep_to_plan.workflow_id:
            raise ValueError(
                f"fake prep_to_plan adapter requires workflow_id {prep_to_plan.workflow_id!r}, "
                f"got {receipt.workflow_id!r}"
            )
        write_boundary_receipt(self._plan_dir, receipt, project_dir=self._project_dir)
        receipt_path = self._receipt_path(receipt.boundary_id)
        if not receipt_path.exists():
            raise RuntimeError(f"boundary receipt {receipt.boundary_id!r} was not durably persisted")
        persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
        if persisted.get("boundary_id") != receipt.boundary_id:
            raise RuntimeError(
                f"boundary receipt reread mismatch: expected {receipt.boundary_id!r}, "
                f"observed {persisted.get('boundary_id')!r}"
            )

    def _receipt_path(self, boundary_id: str) -> Path:
        return self._plan_dir / "boundary_receipts" / f"{boundary_id}.json"


__all__ = [
    "DispatchCallable",
    "FakePrepToPlanAdapter",
    "FakePrepToPlanAttemptResult",
    "FakePrepToPlanDispatchResult",
    "PREP_TO_PLAN_COMPLETE_SOURCE_LOOKUP_KEY",
    "PREP_TO_PLAN_START_SOURCE_LOOKUP_KEY",
    "PREP_TO_PLAN_SURFACE",
    "PREP_TO_PLAN_WRITER_ID",
]
