from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from arnold.runtime.durable_ops import OperationState
from agentbox.config import AgentBoxConfig
from agentbox.guardian.handlers import (
    MEGAPLAN_CHAIN_OPERATION_TYPE,
    GuardianHandlerRegistry,
    MegaplanChainGuardianHandler,
    default_guardian_handler_registry,
)
from agentbox.guardian.model import (
    GuardianInspectionResult,
    GuardianMaterialTransition,
    GuardianOutcome,
)
from agentbox.operations import create_agentbox_operation, update_agentbox_operation


@dataclass(frozen=True)
class FakeClassification:
    operation_state: OperationState
    effective_status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_state": self.operation_state.value,
            "effective_status": self.effective_status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FakeSnapshot:
    operation_id: str
    classification: FakeClassification

    def summarize(self) -> str:
        return f"{self.operation_id}: {self.classification.effective_status}"


class FakeMegaplanChainAdapter:
    def __init__(
        self,
        *,
        classification: FakeClassification | None = None,
        tick_side_effect: Exception | None = None,
        resume_result: Any = None,
    ) -> None:
        self.classification = classification
        self.tick_side_effect = tick_side_effect
        self.resume_result = resume_result
        self.tick_calls: list[str] = []
        self.status_calls: list[str] = []
        self.resume_calls: list[str] = []
        self._run: Any | None = None

    def set_run(self, run: Any) -> None:
        self._run = run

    def tick(self, config: AgentBoxConfig, operation_id: str) -> Any:
        self.tick_calls.append(operation_id)
        if self.tick_side_effect is not None:
            raise self.tick_side_effect
        return self._run or SimpleNamespace(
            id=operation_id,
            state=OperationState.RUNNING if self.classification else OperationState.PENDING,
        )

    def status(self, config: AgentBoxConfig, operation_id: str) -> FakeSnapshot:
        self.status_calls.append(operation_id)
        assert self.classification is not None
        return FakeSnapshot(operation_id=operation_id, classification=self.classification)

    def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
        self.resume_calls.append(operation_id)
        if isinstance(self.resume_result, Exception):
            raise self.resume_result
        return self.resume_result or SimpleNamespace(id=operation_id, state=OperationState.RUNNING)


def _inspect(registry: GuardianHandlerRegistry, config: AgentBoxConfig, operation_id: str):
    handler = registry.get(MEGAPLAN_CHAIN_OPERATION_TYPE)
    return asyncio.run(handler.inspect(config, operation_id))


def test_default_registry_supports_only_megaplan_chain() -> None:
    registry = default_guardian_handler_registry()
    assert registry.supported_types == {MEGAPLAN_CHAIN_OPERATION_TYPE}


def test_handler_maps_complete_chain_to_completion(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    adapter = FakeMegaplanChainAdapter(
        classification=FakeClassification(
            operation_state=OperationState.SUCCEEDED,
            effective_status="complete",
            reason="all_milestones_completed",
        )
    )
    monkeypatch.setattr(
        "agentbox.guardian.handlers.load_operation_adapter", lambda _kind: adapter
    )
    create_agentbox_operation(
        config,
        "chain-complete",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-complete", state=OperationState.RUNNING)

    registry = default_guardian_handler_registry()
    result = _inspect(registry, config, "chain-complete")

    assert result.operation_id == "chain-complete"
    assert result.outcome is GuardianOutcome.OK
    assert result.material_transition is GuardianMaterialTransition.COMPLETED
    assert result.metadata["effective_status"] == "complete"


def test_handler_maps_failed_chain_to_failed(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    adapter = FakeMegaplanChainAdapter(
        classification=FakeClassification(
            operation_state=OperationState.FAILED,
            effective_status="failed",
            reason="plan_failed",
        )
    )
    monkeypatch.setattr(
        "agentbox.guardian.handlers.load_operation_adapter", lambda _kind: adapter
    )
    create_agentbox_operation(
        config,
        "chain-failed",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-failed", state=OperationState.RUNNING)

    registry = default_guardian_handler_registry()
    result = _inspect(registry, config, "chain-failed")

    assert result.outcome is GuardianOutcome.FAILED
    assert result.material_transition is GuardianMaterialTransition.FAILED


def test_handler_maps_needs_peter_chain_to_escalated(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    adapter = FakeMegaplanChainAdapter(
        classification=FakeClassification(
            operation_state=OperationState.AWAITING_APPROVAL,
            effective_status="awaiting_human_verify",
            reason="latest_verdict_human_verification_pending",
        )
    )
    monkeypatch.setattr(
        "agentbox.guardian.handlers.load_operation_adapter", lambda _kind: adapter
    )
    create_agentbox_operation(
        config,
        "chain-needs-peter",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-needs-peter", state=OperationState.RUNNING)

    registry = default_guardian_handler_registry()
    result = _inspect(registry, config, "chain-needs-peter")

    assert result.outcome is GuardianOutcome.ESCALATED
    assert result.material_transition is GuardianMaterialTransition.STALLED


def test_handler_maps_paused_chain_to_non_notifying_noop(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    adapter = FakeMegaplanChainAdapter(
        classification=FakeClassification(
            operation_state=OperationState.SUSPENDED,
            effective_status="paused",
            reason="plan_paused",
        )
    )
    monkeypatch.setattr(
        "agentbox.guardian.handlers.load_operation_adapter", lambda _kind: adapter
    )
    create_agentbox_operation(
        config,
        "chain-paused",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-paused", state=OperationState.RUNNING)

    registry = default_guardian_handler_registry()
    result = _inspect(registry, config, "chain-paused")

    assert result.outcome is GuardianOutcome.NOOP
    assert result.material_transition is GuardianMaterialTransition.PAUSED


def test_handler_maps_stale_chain_to_resumable_retry(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    adapter = FakeMegaplanChainAdapter(
        classification=FakeClassification(
            operation_state=OperationState.SUSPENDED,
            effective_status="stale_bookkeeping",
            reason="running_operation_without_live_runner",
        )
    )
    monkeypatch.setattr(
        "agentbox.guardian.handlers.load_operation_adapter", lambda _kind: adapter
    )
    create_agentbox_operation(
        config,
        "chain-stale",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-stale", state=OperationState.RUNNING)

    registry = default_guardian_handler_registry()
    result = _inspect(registry, config, "chain-stale")

    assert result.outcome is GuardianOutcome.RETRY
    assert result.material_transition is GuardianMaterialTransition.STALLED


def test_handler_skips_unsupported_operation_type(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    registry = GuardianHandlerRegistry()
    create_agentbox_operation(
        config,
        "host-1",
        operation_type="agentbox_host",
        command=("echo",),
    )

    handler = registry.get("agentbox_host")
    result = asyncio.run(handler.inspect(config, "host-1"))

    assert result.operation_id == "host-1"
    assert result.outcome is GuardianOutcome.NOOP
    assert "unsupported" in result.summary.lower()


def test_handler_resume_delegates_to_adapter(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    adapter = FakeMegaplanChainAdapter(
        classification=FakeClassification(
            operation_state=OperationState.RUNNING,
            effective_status="running",
            reason="runner_alive",
        )
    )
    monkeypatch.setattr(
        "agentbox.guardian.handlers.load_operation_adapter", lambda _kind: adapter
    )

    registry = default_guardian_handler_registry()
    handler = registry.get(MEGAPLAN_CHAIN_OPERATION_TYPE)
    asyncio.run(handler.resume(config, "chain-1"))

    assert adapter.resume_calls == ["chain-1"]
