from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ConfirmationManager, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.escalations import authorize_escalation_answer
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
from arnold_pipelines.megaplan.store import FileStore


class AuditSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def log_system_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


def test_escalation_reply_allows_delivered_responder_on_current_target(tmp_path: Path) -> None:
    _write_escalation(
        tmp_path,
        {"session": "demo", "event": "opened", "escalation_id": "esc-1", "target_id": "target-1", "dm_user_id": "user-1"},
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
    )
    _write_marker(tmp_path, "demo", "target-1")

    decision = authorize_escalation_answer(
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        subject=AuthorizationSubject(user_id="user-1", channel_id="channel-1"),
        action="escalation_reply",
        escalation_id="esc-1",
        repair_data_dir=tmp_path,
        audit_sink=AuditSink(),
    )

    assert decision.allowed is True
    assert decision.target is not None
    assert decision.target.message_ids == ("msg-1",)


def test_escalation_reply_rejects_wrong_user_and_audits(tmp_path: Path) -> None:
    _write_escalation(
        tmp_path,
        {"session": "demo", "event": "opened", "escalation_id": "esc-1", "target_id": "target-1", "dm_user_id": "user-1"},
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
    )
    _write_marker(tmp_path, "demo", "target-1")
    audit = AuditSink()

    decision = authorize_escalation_answer(
        authorizer=ResidentAuthorizer(ResidentConfig()),
        subject=AuthorizationSubject(user_id="user-2", channel_id="channel-1"),
        action="escalation_reply",
        escalation_id="esc-1",
        repair_data_dir=tmp_path,
        audit_sink=audit,
    )

    assert decision.allowed is False
    assert decision.reason == "responder_user_mismatch"
    assert audit.events[-1]["event_type"] == "escalation_answer_unauthorized"


def test_escalation_reply_rejects_wrong_channel_before_mutation(tmp_path: Path) -> None:
    _write_escalation(
        tmp_path,
        {"session": "demo", "event": "opened", "escalation_id": "esc-1", "target_id": "target-1", "dm_user_id": "user-1"},
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
    )
    _write_marker(tmp_path, "demo", "target-1")

    decision = authorize_escalation_answer(
        authorizer=ResidentAuthorizer(ResidentConfig()),
        subject=AuthorizationSubject(user_id="user-1", channel_id="channel-2"),
        action="escalation_reply",
        escalation_id="esc-1",
        repair_data_dir=tmp_path,
        audit_sink=AuditSink(),
    )

    assert decision.allowed is False
    assert decision.reason == "responder_channel_mismatch"


def test_escalation_reply_rejects_stale_current_target(tmp_path: Path) -> None:
    _write_escalation(
        tmp_path,
        {"session": "demo", "event": "opened", "escalation_id": "esc-1", "target_id": "target-1", "dm_user_id": "user-1"},
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
    )
    _write_marker(tmp_path, "demo", "target-2")

    decision = authorize_escalation_answer(
        authorizer=ResidentAuthorizer(ResidentConfig()),
        subject=AuthorizationSubject(user_id="user-1", channel_id="channel-1"),
        action="escalation_reply",
        escalation_id="esc-1",
        repair_data_dir=tmp_path,
        audit_sink=AuditSink(),
    )

    assert decision.allowed is False
    assert decision.reason == "stale_target_mismatch"


def test_escalation_reply_rejects_superseded_escalation(tmp_path: Path) -> None:
    _write_escalation(
        tmp_path,
        {"session": "demo", "event": "opened", "escalation_id": "esc-1", "target_id": "target-1", "dm_user_id": "user-1"},
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
        {"session": "demo", "event": "superseded", "escalation_id": "esc-1", "superseded_by": "esc-2"},
    )
    _write_marker(tmp_path, "demo", "target-1")

    decision = authorize_escalation_answer(
        authorizer=ResidentAuthorizer(ResidentConfig()),
        subject=AuthorizationSubject(user_id="user-1", channel_id="channel-1"),
        action="escalation_reply",
        escalation_id="esc-1",
        repair_data_dir=tmp_path,
        audit_sink=AuditSink(),
    )

    assert decision.allowed is False
    assert decision.reason == "escalation_superseded"


def test_escalation_resolution_free_text_requests_confirmation_without_mutation(tmp_path: Path) -> None:
    repair_data_dir = tmp_path / "repair-data"
    _write_escalation(
        repair_data_dir,
        {
            "session": "demo",
            "event": "opened",
            "escalation_id": "esc-1",
            "target_id": "target-1",
            "current_plan": "plan-1",
            "dm_user_id": "user-1",
            "resume_handler": "cloud_resume",
        },
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
    )
    _write_marker(repair_data_dir, "demo", "target-1")
    backend = RecordingCloudBackend()
    outbound = RecordingOutbound()
    runtime = _runtime(tmp_path, repair_data_dir=repair_data_dir, cloud_backend=backend, outbound=outbound)

    asyncio.run(
        runtime.receive(
            InboundEvent(
                idempotency_key="discord:message:answer-1",
                conversation_key="discord:dm:user-1",
                subject=AuthorizationSubject(user_id="user-1", channel_id="channel-1"),
                content="resume it",
                escalation_id="esc-1",
                resume_handler="cloud_resume",
                raw={"discord_message_id": "answer-1"},
            )
        )
    )

    assert outbound.sent
    assert outbound.sent[-1].content.startswith("Confirmation required: confirm escalation_resolve ")
    assert backend.calls == []
    assert (repair_data_dir / "demo.needs-human.json").exists()
    assert [record["event"] for record in _read_escalations(repair_data_dir)] == ["opened", "delivered"]


def test_confirmed_escalation_resolution_locks_clears_pointer_and_records_resume(tmp_path: Path) -> None:
    repair_data_dir = tmp_path / "repair-data"
    lock_dir = tmp_path / "demo.repair-loop.lock"
    _write_escalation(
        repair_data_dir,
        {
            "session": "demo",
            "event": "opened",
            "escalation_id": "esc-1",
            "target_id": "target-1",
            "current_plan": "plan-1",
            "dm_user_id": "user-1",
            "resume_handler": "cloud_resume",
        },
        {
            "session": "demo",
            "event": "delivered",
            "escalation_id": "esc-1",
            "channel_id": "channel-1",
            "message_ids": ["msg-1"],
            "dm_user_id": "user-1",
        },
    )
    _write_marker(repair_data_dir, "demo", "target-1")
    backend = RecordingCloudBackend()
    outbound = RecordingOutbound()
    runtime = _runtime(
        tmp_path,
        repair_data_dir=repair_data_dir,
        repair_lock_dir=lock_dir,
        cloud_backend=backend,
        outbound=outbound,
    )
    subject = AuthorizationSubject(user_id="user-1", channel_id="channel-1")

    asyncio.run(
        runtime.receive(
            InboundEvent(
                idempotency_key="discord:message:answer-1",
                conversation_key="discord:dm:user-1",
                subject=subject,
                content="resume it",
                escalation_id="esc-1",
                resume_handler="cloud_resume",
                raw={"discord_message_id": "answer-1"},
            )
        )
    )
    phrase = outbound.sent[-1].content.removeprefix("Confirmation required: ")

    asyncio.run(
        runtime.receive(
            InboundEvent(
                idempotency_key="discord:message:answer-2",
                conversation_key="discord:dm:user-1",
                subject=subject,
                content=phrase,
                escalation_id="esc-1",
                resume_handler="cloud_resume",
                raw={"discord_message_id": "answer-2"},
            )
        )
    )

    assert len(backend.calls) == 1
    assert backend.calls[0].operation == "cloud_resume"
    assert backend.calls[0].arguments["plan"] == "plan-1"
    assert backend.calls[0].confirmed is True
    assert not (repair_data_dir / "demo.needs-human.json").exists()
    assert not lock_dir.exists()
    events = _read_escalations(repair_data_dir)
    assert [record["event"] for record in events[-2:]] == ["answered", "resume_attempted"]
    assert events[-2]["responder_user_id"] == "user-1"
    assert events[-2]["message_id"] == "answer-2"
    assert events[-1]["action"] == "cloud_resume"
    assert events[-1]["resume_status"] == "running"


def _write_escalation(tmp_path: Path, *records: dict[str, Any]) -> None:
    ledger_dir = tmp_path / "escalations"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "escalations.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_marker(tmp_path: Path, session: str, target_id: str) -> None:
    (tmp_path / f"{session}.needs-human.json").write_text(
        json.dumps({"session": session, "target_id": target_id}),
        encoding="utf-8",
    )


def _read_escalations(repair_data_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (repair_data_dir / "escalations" / "escalations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _runtime(
    tmp_path: Path,
    *,
    repair_data_dir: Path,
    cloud_backend: "RecordingCloudBackend",
    outbound: "RecordingOutbound",
    repair_lock_dir: Path | None = None,
) -> ResidentRuntime:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        escalation_repair_data_dir=repair_data_dir,
        escalation_repair_lock_dir=repair_lock_dir,
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    store = FileStore(tmp_path / "store")
    authorizer = ResidentAuthorizer(config)
    return ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=ConfirmationManager(config),
            cloud_backend=cloud_backend,
        ),
        runner=ExplodingRunner(),
        outbound=outbound,
    )


class RecordingCloudBackend:
    def __init__(self) -> None:
        self.calls: list[CloudToolRequest] = []

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        self.calls.append(request)
        return CloudToolResult(classification="running", summary="cloud_resume: running")


class RecordingOutbound:
    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)


class ExplodingRunner:
    async def run(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("escalation resolution should not run the resident model")
