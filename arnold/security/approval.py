"""Bridge broker approval decisions to durable operation state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from arnold.pipeline.native.checkpoint import (
    NATIVE_CURSOR_VERSION,
    persist_native_cursor,
)
from arnold.pipeline.steps.human_gate import write_human_gate_checkpoint
from arnold.runtime.durable_ops.approval import (
    BROKER_APPROVAL_SUSPENSION_KIND,
    ApprovalLink,
    BrokerApprovalDecision,
    apply_broker_approval_decision,
    broker_approval_effect_metadata,
)
from arnold.runtime.durable_ops.operation import OperationRun
from arnold.runtime.durable_ops.store import DurableOpsStore
from arnold.security.redaction import redact_mapping, redact_text
from arnold.security.types import ActionResult

__all__ = [
    "BrokerApprovalCheckpoint",
    "apply_broker_approval_required",
    "resolve_broker_approval",
    "write_broker_approval_checkpoint",
]


BROKER_APPROVAL_CHOICES = ("approve", "deny", "cancel")


@dataclass(frozen=True, slots=True)
class BrokerApprovalCheckpoint:
    """References written for a broker approval gate suspension."""

    approval_link: ApprovalLink
    checkpoint_path: Path
    cursor_path: Path
    resume_cursor: str
    checkpoint: dict[str, Any]

    @property
    def suspension_cursor_ref(self) -> str:
        return str(self.cursor_path)


def apply_broker_approval_required(
    store: DurableOpsStore,
    operation_id: str,
    *,
    action_result: ActionResult,
    artifact_root: str | Path,
    pipeline: str = "security_broker",
    stage: str | None = None,
    message: str | None = None,
) -> OperationRun:
    """Persist a broker approval gate and move the run to awaiting approval."""

    run = store.load_operation_run(operation_id)
    checkpoint = write_broker_approval_checkpoint(
        artifact_root,
        run=run,
        action_result=action_result,
        pipeline=pipeline,
        stage=stage,
        message=message,
    )
    updated = apply_broker_approval_decision(
        run,
        BrokerApprovalDecision.APPROVAL_REQUIRED,
        action_result=action_result,
        approval_link=checkpoint.approval_link,
        suspension_cursor_ref=checkpoint.suspension_cursor_ref,
        effect_metadata=_effect_metadata_for_checkpoint(action_result, checkpoint),
    )
    return store.update_operation_run(updated, expected_lock_version=run.lock_version)


def resolve_broker_approval(
    store: DurableOpsStore,
    operation_id: str,
    decision: BrokerApprovalDecision | str,
    *,
    action_result: ActionResult,
) -> OperationRun:
    """Apply an approve, deny, or cancel broker approval resolution."""

    normalized = BrokerApprovalDecision(decision)
    if normalized is BrokerApprovalDecision.APPROVAL_REQUIRED:
        raise ValueError("approval_required must use apply_broker_approval_required")
    run = store.load_operation_run(operation_id)
    updated = apply_broker_approval_decision(
        run,
        normalized,
        action_result=action_result,
        effect_metadata=broker_approval_effect_metadata(action_result),
    )
    return store.update_operation_run(updated, expected_lock_version=run.lock_version)


def write_broker_approval_checkpoint(
    artifact_root: str | Path,
    *,
    run: OperationRun,
    action_result: ActionResult,
    pipeline: str = "security_broker",
    stage: str | None = None,
    message: str | None = None,
) -> BrokerApprovalCheckpoint:
    """Write ``awaiting_user.json`` and native resume cursor for broker approval.

    The cursor uses the same graph-compatible human-gate fields as native
    human gates, with ``suspension_kind`` set to ``broker_approval_gate``.
    """

    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    approval_link = ApprovalLink(
        provider_label="security_broker",
        external_confirmation_request_id=action_result.action_id or uuid4().hex,
    )
    stage_name = stage or run.operation_type
    checkpoint_path = root / "awaiting_user.json"
    resume_cursor_payload = {
        "kind": "awaiting_user",
        "retry_strategy": "awaiting_user",
        "phase": stage_name,
        "operation_id": run.id,
        "suspension_kind": BROKER_APPROVAL_SUSPENSION_KIND,
        "approval_link": approval_link.to_json(),
        "broker_action_id": action_result.action_id,
        "choices": list(BROKER_APPROVAL_CHOICES),
    }
    resume_cursor = json.dumps(resume_cursor_payload, sort_keys=True)
    effect = broker_approval_effect_metadata(action_result)
    checkpoint = write_human_gate_checkpoint(
        checkpoint_path,
        pipeline=pipeline,
        version=NATIVE_CURSOR_VERSION,
        artifact_stage=stage_name,
        prompt=action_result.summary,
        stage=stage_name,
        choices=list(BROKER_APPROVAL_CHOICES),
        message=message
        or f"Broker approval required for operation '{run.id}'. Choose: approve, deny, cancel",
        approval_link=approval_link.to_json(),
        broker_action_id=action_result.action_id,
        effect=effect,
        suspension_kind=BROKER_APPROVAL_SUSPENSION_KIND,
    )
    cursor_path = persist_native_cursor(
        root,
        stage=f"{pipeline}__{stage_name}__broker_approval",
        pc=0,
        stages=[],
        loops={},
        frames={"__state__": {"operation_id": run.id}},
        resume_cursor=resume_cursor,
        cursor_id=uuid4().hex,
        reentry_stage=f"{pipeline}__{stage_name}__broker_approval",
        effect=effect,
        native_extra={"suspension_kind": BROKER_APPROVAL_SUSPENSION_KIND},
        suspension_kind=BROKER_APPROVAL_SUSPENSION_KIND,
        artifact_stage=stage_name,
        choices=list(BROKER_APPROVAL_CHOICES),
        approval_link=approval_link.to_json(),
        broker_action_id=action_result.action_id,
        contract_result={
            "status": "suspended",
            "payload": {"source": "awaiting_user.json"},
        },
    )
    return BrokerApprovalCheckpoint(
        approval_link=approval_link,
        checkpoint_path=checkpoint_path,
        cursor_path=cursor_path,
        resume_cursor=resume_cursor,
        checkpoint=redact_mapping(checkpoint),
    )


def _effect_metadata_for_checkpoint(
    action_result: ActionResult,
    checkpoint: BrokerApprovalCheckpoint,
) -> dict[str, Any]:
    effect = broker_approval_effect_metadata(action_result)
    effect.update(
        {
            "approval_link": checkpoint.approval_link.to_json(),
            "suspension_cursor_ref": redact_text(checkpoint.suspension_cursor_ref),
        }
    )
    return effect
