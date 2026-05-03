from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

from megaplan.schemas import BotTurn, ChecklistItem, Epic, EpicLock, Message, SystemLog, ToolCall, utc_now
from megaplan.store import ArnoldStoreAdapter, BlobStore, HotContext, LockConflict, Store


def _public_methods(cls: type[object]) -> set[str]:
    return {
        name
        for name, value in cls.__dict__.items()
        if callable(value) and not name.startswith("_")
    }


def _load_arnold_ports() -> object:
    path = Path(__file__).resolve().parents[1] / "arnold-source" / "agent_kit" / "ports.py"
    if not path.exists():
        pytest.skip(f"arnold-source fixture missing: {path}")
    spec = importlib.util.spec_from_file_location("_arnold_ports", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeStore:
    def __init__(self) -> None:
        self.transaction_epic_ids: list[str | None] = []
        self.messages: dict[str, Message] = {}

    @contextmanager
    def transaction(self, epic_id: str | None = None):
        self.transaction_epic_ids.append(epic_id)
        yield self

    def create_message(self, **fields: object) -> Message:
        message = Message(
            id="msg_1",
            epic_id=fields.get("epic_id"),
            direction=str(fields["direction"]),
            content=str(fields["content"]),
            bot_turn_id=fields.get("bot_turn_id"),
            discord_message_id=fields.get("discord_message_id"),
        )
        self.messages[message.id] = message
        return message

    def load_message(self, message_id: str) -> Message | None:
        return self.messages.get(message_id)

    def create_turn(self, **fields: object) -> BotTurn:
        return BotTurn(
            id="turn_1",
            epic_id=fields.get("epic_id"),
            triggered_by_message_ids=list(fields.get("triggered_by_message_ids", [])),
            status="in_progress",
            prompt_snapshot=fields.get("prompt_snapshot"),
        )

    def add_checklist_items(self, epic_id: str, items: object) -> list[ChecklistItem]:
        return [
            ChecklistItem(
                id=f"check_{index}",
                epic_id=epic_id,
                content=item.content,
                status=item.status,
                position=item.position or index,
                source=item.source,
            )
            for index, item in enumerate(items, start=1)
        ]

    def update_epic(self, epic_id: str, **changes: object) -> Epic:
        return Epic(
            id=epic_id,
            title=str(changes.get("title") or "Updated"),
            goal=str(changes.get("goal") or "Goal"),
            body=str(changes.get("body") or "# Updated"),
            state=str(changes.get("state") or "shaping"),
        )

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int) -> EpicLock:
        if holder_id == "blocked":
            raise LockConflict("held elsewhere")
        return EpicLock(
            epic_id=epic_id,
            holder_id=holder_id,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )

    def release_lock(self, epic_id: str, holder_id: str) -> None:
        return None

    def record_tool_call(self, **fields: object) -> ToolCall:
        return ToolCall(
            id="tool_1",
            turn_id=str(fields["turn_id"]),
            tool_name=str(fields["tool_name"]),
            operation_kind=str(fields["operation_kind"]),
            arguments=dict(fields["arguments"]),
            result=dict(fields["result"]),
            duration_ms=int(fields["duration_ms"]),
        )

    def log_system_event(self, **fields: object) -> SystemLog:
        return SystemLog(
            id="log_1",
            level=str(fields["level"]),
            category=str(fields["category"]),
            event_type=str(fields["event_type"]),
            message=str(fields["message"]),
            details=dict(fields.get("details") or {}),
            turn_id=fields.get("turn_id"),
            epic_id=fields.get("epic_id"),
        )

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        return HotContext(
            epic=Epic(
                id="epic_1",
                title="Title",
                goal="Goal",
                body="# Title",
                state="shaping",
            )
            if epic_id
            else None,
            recent_messages=list(self.messages.values()),
        )


def test_store_protocol_includes_refined_sprint_1_surface() -> None:
    expected_store_methods = {
        "transaction",
        "load_body",
        "update_body",
        "seed_checklist",
        "set_sprint_queue",
        "load_message",
        "record_tool_call",
        "log_system_event",
        "acquire_lock",
        "release_lock",
        "create_turn",
        "create_message",
        "load_hot_context",
        "create_plan",
        "write_plan_artifact",
        "acquire_execution_lease",
        "put_control_message",
        "claim_pending_control_messages",
        "append_progress_event",
    }
    assert expected_store_methods.issubset(_public_methods(Store))
    assert _public_methods(BlobStore) == {"put", "get", "url", "delete", "stat"}


def test_arnold_store_adapter_covers_live_arnold_store_surface() -> None:
    arnold_ports = _load_arnold_ports()
    missing = _public_methods(arnold_ports.Store) - _public_methods(ArnoldStoreAdapter)
    assert not missing


def test_arnold_store_adapter_preserves_bootstrap_seed_and_lock_compatibility() -> None:
    adapter = ArnoldStoreAdapter(_FakeStore())

    with adapter.transaction():
        pass
    assert adapter._store.transaction_epic_ids == [None]

    message = adapter.create_message(epic_id=None, direction="inbound", content="bootstrap")
    assert message["epic_id"] is None
    assert adapter.load_message(message["id"])["content"] == "bootstrap"

    turn = adapter.create_turn(epic_id=None, triggered_by_message_ids=[], prompt_snapshot={"phase": "bootstrap"})
    assert turn["epic_id"] is None

    updated = adapter.update_epic("epic_1", body="# Body", title="Body Title", goal="Body Goal")
    assert updated["body"] == "# Body"

    seeded = adapter.seed_checklist("epic_1", ["First", "Second"])
    assert [item["position"] for item in seeded] == [1, 2]
    assert [item["source"] for item in seeded] == ["default_seed", "default_seed"]

    tool_call = adapter.record_tool_call(
        turn_id="turn_1",
        tool_name="edit_epic",
        operation_kind="write",
        arguments={"body": "# Body"},
        result={"ok": True},
        duration_ms=1,
    )
    assert tool_call["arguments"]["body"] == "# Body"

    log = adapter.log_system_event(
        level="info",
        category="system",
        event_type="bootstrap",
        message="ok",
        details={"ok": True},
        epic_id=None,
    )
    assert log["details"]["ok"] is True

    assert adapter.acquire_epic_lock("epic_1", holder_id="holder_a") is True
    assert adapter.acquire_epic_lock("epic_1", holder_id="blocked") is False
    assert adapter.load_hot_context(None)["epic"] is None
