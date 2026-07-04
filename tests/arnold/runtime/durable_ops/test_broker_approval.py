from __future__ import annotations

import json

from arnold.pipeline.native.checkpoint import classify_resume_cursor
from arnold.runtime.durable_ops import (
    BROKER_APPROVAL_SUSPENSION_KIND,
    ApprovalLink,
    FileBackedDurableOpsStore,
    OperationRun,
    OperationState,
    apply_broker_approval_decision,
)
from arnold.security.approval import (
    apply_broker_approval_required,
    resolve_broker_approval,
)
from arnold.security.types import ActionResult, ActionVerdict


def _action_result(verdict: ActionVerdict, *, action_id: str = "act-1") -> ActionResult:
    return ActionResult(
        verdict=verdict,
        summary=f"{verdict.value} broker decision",
        action_id=action_id,
        effect_refs=("effect-1",),
        metadata={"repo": "example/repo", "branch": "feature"},
    )


def _contains_key(payload: object, key: str) -> bool:
    if isinstance(payload, dict):
        return key in payload or any(_contains_key(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_key(item, key) for item in payload)
    return False


def test_broker_approval_required_updates_run_metadata_and_transition() -> None:
    run = OperationRun(id="op-1", operation_type="git_force_push")
    link = ApprovalLink(
        provider_label="security_broker",
        external_confirmation_request_id="act-approval",
    )

    awaiting = apply_broker_approval_decision(
        run,
        "approval_required",
        action_result=_action_result(
            ActionVerdict.APPROVAL_REQUIRED,
            action_id="act-approval",
        ),
        approval_link=link,
        suspension_cursor_ref="/tmp/artifacts/resume_cursor.json",
    )

    assert awaiting.state is OperationState.AWAITING_APPROVAL
    assert awaiting.started_at is None
    assert awaiting.metadata["approval_link"] == link.to_json()
    assert awaiting.metadata["approval"] == link.to_json()
    assert awaiting.metadata["suspension_cursor_ref"] == "/tmp/artifacts/resume_cursor.json"
    assert awaiting.metadata["broker_action_id"] == "act-approval"
    assert awaiting.metadata["broker_approval"]["suspension_kind"] == (
        BROKER_APPROVAL_SUSPENSION_KIND
    )
    assert awaiting.metadata["effect"]["effect_refs"] == ["effect-1"]


def test_broker_approval_resolutions_map_to_operation_transitions() -> None:
    awaiting = OperationRun(
        id="op-2",
        operation_type="git_force_push",
        state=OperationState.AWAITING_APPROVAL,
    )

    approved = apply_broker_approval_decision(
        awaiting,
        "approve",
        action_result=_action_result(ActionVerdict.ALLOW),
    )
    denied = apply_broker_approval_decision(
        awaiting,
        "deny",
        action_result=_action_result(ActionVerdict.DENY),
    )
    cancelled = apply_broker_approval_decision(
        awaiting,
        "cancel",
        action_result=_action_result(ActionVerdict.DENY),
    )

    assert approved.state is OperationState.RUNNING
    assert approved.started_at is not None
    assert denied.state is OperationState.FAILED
    assert denied.completed_at is not None
    assert cancelled.state is OperationState.CANCELLED
    assert cancelled.completed_at is not None


def test_security_broker_approval_checkpoint_uses_human_gate_shape(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path / "store")
    created = store.create_operation_run(
        OperationRun(id="op-3", operation_type="git_force_push")
    )

    updated = apply_broker_approval_required(
        store,
        created.id,
        action_result=_action_result(
            ActionVerdict.APPROVAL_REQUIRED,
            action_id="act-gate",
        ),
        artifact_root=tmp_path / "artifacts",
    )

    checkpoint = json.loads((tmp_path / "artifacts" / "awaiting_user.json").read_text())
    cursor = json.loads((tmp_path / "artifacts" / "resume_cursor.json").read_text())

    assert updated.state is OperationState.AWAITING_APPROVAL
    assert classify_resume_cursor(tmp_path / "artifacts") == "native"
    assert checkpoint["pipeline"] == "security_broker"
    assert checkpoint["choices"] == ["approve", "deny", "cancel"]
    assert checkpoint["suspension_kind"] == BROKER_APPROVAL_SUSPENSION_KIND
    assert checkpoint["approval_link"] == updated.metadata["approval_link"]
    assert cursor["suspension_kind"] == BROKER_APPROVAL_SUSPENSION_KIND
    assert cursor["native"]["suspension_kind"] == BROKER_APPROVAL_SUSPENSION_KIND
    assert cursor["broker_action_id"] == "act-gate"
    assert updated.metadata["suspension_cursor_ref"] == str(
        tmp_path / "artifacts" / "resume_cursor.json"
    )
    assert not _contains_key(checkpoint, "user_approved_gate")
    assert not _contains_key(cursor, "user_approved_gate")
    assert not _contains_key(dict(updated.metadata), "user_approved_gate")


def test_security_broker_approval_resolution_updates_existing_run(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path / "store")
    created = store.create_operation_run(
        OperationRun(
            id="op-4",
            operation_type="git_force_push",
            state=OperationState.AWAITING_APPROVAL,
        )
    )

    updated = resolve_broker_approval(
        store,
        created.id,
        "approve",
        action_result=_action_result(ActionVerdict.ALLOW, action_id="act-approved"),
    )

    assert updated.state is OperationState.RUNNING
    assert updated.metadata["broker_approval"]["decision"] == "approve"
    assert updated.metadata["broker_action_id"] == "act-approved"


def test_security_broker_force_push_approval_required_persists_declared_metadata(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path / "store")
    created = store.create_operation_run(
        OperationRun(id="op-5", operation_type="git_force_push")
    )

    updated = apply_broker_approval_required(
        store,
        created.id,
        action_result=ActionResult(
            verdict=ActionVerdict.APPROVAL_REQUIRED,
            summary="git_force_push requires approval",
            action_id="act-force-push",
            metadata={
                "repo": "example/repo",
                "branch": "feature/demo",
                "action_type": "git_force_push",
                "force": True,
            },
        ),
        artifact_root=tmp_path / "artifacts",
    )

    checkpoint = json.loads((tmp_path / "artifacts" / "awaiting_user.json").read_text())
    cursor = json.loads((tmp_path / "artifacts" / "resume_cursor.json").read_text())
    broker_cursor = json.loads(cursor["resume_cursor"])

    assert updated.state is OperationState.AWAITING_APPROVAL
    assert checkpoint["artifact_stage"] == "git_force_push"
    assert checkpoint["broker_action_id"] == "act-force-push"
    assert checkpoint["effect"]["metadata"]["action_type"] == "git_force_push"
    assert checkpoint["effect"]["metadata"]["force"] is True
    assert broker_cursor["operation_id"] == "op-5"
    assert broker_cursor["suspension_kind"] == BROKER_APPROVAL_SUSPENSION_KIND
    assert broker_cursor["choices"] == ["approve", "deny", "cancel"]
