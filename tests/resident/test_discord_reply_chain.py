from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentRequest,
    FakeAgentRunner,
    FakeAgentStep,
)
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.cli import _resident_read_reply_chain
from arnold_pipelines.megaplan.resident.discord import _capture_discord_reply_chain
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.provenance import (
    DELEGATION_CONTEXT_ENV,
    encoded_provenance,
)
from arnold_pipelines.megaplan.resident.reply_chain import (
    REPLY_CAPTURE_MAX_ANCESTORS,
    build_reply_provenance,
    encode_reply_cursor,
    render_reply_context,
)
from arnold_pipelines.megaplan.schemas import Message
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput
from arnold_pipelines.megaplan.types import CliError


def _raw_chain(count: int) -> dict:
    return {
        "ancestors": [
            {
                "depth": depth,
                "message_id": f"discord-{depth}",
                "author_id": f"author-{depth}",
                "content": f"ancestor body {depth}",
                "status": "available",
                "parent_message_id": (
                    f"discord-{depth + 1}" if depth < count else None
                ),
            }
            for depth in range(1, count + 1)
        ],
        "chain_complete": True,
        "capture_truncated": False,
        "termination_reason": "root",
    }


def _message_with_chain(count: int) -> Message:
    provenance = build_reply_provenance(
        source_message_id="discord-current",
        source_author_id="current-author",
        conversation_key="discord:dm:current-author",
        scope={"dm_user_id": "current-author"},
        raw_chain=_raw_chain(count),
        reference_message_id=f"discord-1" if count else None,
        reference_author_id=None,
        reference_content=None,
    )
    return Message(
        id="resident-current",
        conversation_id="conversation-current",
        direction="inbound",
        content="current user body",
        discord_message_id="discord-current",
        discord_reply_provenance=provenance,
    )


@pytest.mark.parametrize("ancestor_count", [0, 1, 2, 3, 4])
def test_prompt_preloads_zero_through_three_ancestors_only(ancestor_count: int) -> None:
    rendered = render_reply_context(_message_with_chain(ancestor_count))

    assert "Current Discord message id: discord-current" in rendered
    assert "Current author id: current-author" in rendered
    assert rendered.endswith("Content truncated: no\ncurrent user body")
    assert rendered.count("- Discord message id: discord-") == min(ancestor_count, 3)
    for depth in range(1, min(ancestor_count, 3) + 1):
        assert f"Ancestor {depth}" in rendered
        assert f"ancestor body {depth}" in rendered
    if ancestor_count == 0:
        assert "No parent message" in rendered
    if ancestor_count > 3:
        assert "Older captured ancestors not preloaded: 1" in rendered
        assert "call `read_reply_chain` with this cursor" in rendered
        assert "ancestor body 4" not in rendered


def test_prompt_visibly_renders_missing_cycle_and_legacy_provenance() -> None:
    missing = _message_with_chain(0)
    missing.discord_reply_provenance = build_reply_provenance(
        source_message_id="discord-current",
        source_author_id="current-author",
        conversation_key="discord:dm:current-author",
        scope={},
        raw_chain={
            "ancestors": [
                {
                    "message_id": "deleted-parent",
                    "status": "unavailable",
                    "unavailable_reason": "missing_deleted_or_inaccessible",
                }
            ],
            "chain_complete": False,
            "termination_reason": "ancestor_unavailable",
        },
        reference_message_id="deleted-parent",
        reference_author_id=None,
        reference_content=None,
    )
    cycle = _message_with_chain(0)
    cycle.discord_reply_provenance = build_reply_provenance(
        source_message_id="discord-current",
        source_author_id="current-author",
        conversation_key="discord:dm:current-author",
        scope={},
        raw_chain={
            "ancestors": [
                {
                    "message_id": "discord-current",
                    "status": "cycle_detected",
                    "unavailable_reason": "reply_pointer_cycle",
                }
            ],
            "chain_complete": False,
            "termination_reason": "cycle_detected",
        },
        reference_message_id="discord-current",
        reference_author_id=None,
        reference_content=None,
    )
    legacy = Message(
        id="legacy",
        conversation_id="conversation-current",
        direction="inbound",
        content="legacy body",
        discord_message_id="legacy-discord",
    )

    assert "missing_deleted_or_inaccessible" in render_reply_context(missing)
    assert "cycle_detected" in render_reply_context(cycle)
    assert "legacy_source_provenance_unavailable" in render_reply_context(legacy)


def test_prompt_marks_ancestor_and_current_content_truncation() -> None:
    message = _message_with_chain(1)
    message.content = "u" * 5000
    message.discord_reply_provenance["ancestors"][0]["content"] = "a" * 2000

    rendered = render_reply_context(message)

    assert "- Content truncated: yes" in rendered
    assert "[Current user message]\nContent truncated: yes" in rendered
    assert len(rendered) < 6000


def test_discord_adapter_traverses_exact_resolved_chain_and_detects_cycle() -> None:
    channel = SimpleNamespace(id="channel-1", parent=None)
    oldest = SimpleNamespace(
        id="p3",
        content="oldest",
        author=SimpleNamespace(id="a3"),
        channel=channel,
        reference=None,
    )
    middle = SimpleNamespace(
        id="p2",
        content="middle",
        author=SimpleNamespace(id="a2"),
        channel=channel,
        reference=SimpleNamespace(message_id="p3", channel_id="channel-1", resolved=oldest),
    )
    parent = SimpleNamespace(
        id="p1",
        content="parent",
        author=SimpleNamespace(id="a1"),
        channel=channel,
        reference=SimpleNamespace(message_id="p2", channel_id="channel-1", resolved=middle),
    )
    current = SimpleNamespace(
        id="current",
        content="reply",
        author=SimpleNamespace(id="me"),
        channel=channel,
        reference=SimpleNamespace(message_id="p1", channel_id="channel-1", resolved=parent),
    )

    captured = asyncio.run(_capture_discord_reply_chain(current))

    assert [row["message_id"] for row in captured["ancestors"]] == ["p1", "p2", "p3"]
    assert captured["chain_complete"] is True
    oldest.reference = SimpleNamespace(
        message_id="current", channel_id="channel-1", resolved=current
    )
    cycled = asyncio.run(_capture_discord_reply_chain(current))
    assert cycled["ancestors"][-1]["status"] == "cycle_detected"
    assert len(cycled["ancestors"]) == 4


def test_adapter_marks_missing_and_cross_scope_parents_without_arbitrary_fetch() -> None:
    class Channel:
        id = "channel-1"
        parent = None

        def __init__(self) -> None:
            self.fetches: list[int] = []

        async def fetch_message(self, message_id: int) -> object:
            self.fetches.append(message_id)
            raise LookupError("deleted")

    channel = Channel()
    missing = SimpleNamespace(
        id="current",
        channel=channel,
        reference=SimpleNamespace(message_id="123", channel_id="channel-1", resolved=None),
    )
    captured = asyncio.run(_capture_discord_reply_chain(missing))
    assert captured["ancestors"][0]["status"] == "unavailable"
    assert channel.fetches == [123]

    cross_scope = SimpleNamespace(
        id="current-2",
        channel=channel,
        reference=SimpleNamespace(message_id="456", channel_id="other-channel", resolved=None),
    )
    rejected = asyncio.run(_capture_discord_reply_chain(cross_scope))
    assert rejected["ancestors"][0]["status"] == "scope_rejected"
    assert channel.fetches == [123]


def _persist_chain(store: FileStore, conversation_id: str, discord_id: str, count: int) -> Message:
    message = _message_with_chain(count)
    return store.create_message(
        epic_id=None,
        conversation_id=conversation_id,
        direction="inbound",
        content=message.content,
        discord_message_id=discord_id,
        discord_reply_provenance=message.discord_reply_provenance,
        idempotency_key=f"persist-{discord_id}",
    )


def test_read_reply_chain_paginates_bounds_and_rejects_cross_conversation(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    first = store.upsert_resident_conversation(
        ResidentConversationInput(conversation_key="discord:dm:user-1", dm_user_id="user-1")
    )
    second = store.upsert_resident_conversation(
        ResidentConversationInput(conversation_key="discord:dm:user-2", dm_user_id="user-2")
    )
    source = _persist_chain(store, first.id, "source-discord", 17)
    other = _persist_chain(store, second.id, "other-discord", 1)
    config = ResidentConfig(allowed_user_ids=("user-1",))
    authorizer = ResidentAuthorizer(config)
    profile = MegaplanResidentProfile(store=store, authorizer=authorizer, config=config)
    cursor = encode_reply_cursor(source.id, 3)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("read_reply_chain", {"cursor": cursor, "limit": 10}),
            FakeAgentStep.call(
                "read_reply_chain", {"source_message_id": other.id, "limit": 2}
            ),
            FakeAgentStep.final("done"),
        ]
    )
    request = AgentRequest(
        conversation_id=first.id,
        messages=({"role": "user", "content": "read older replies"},),
        system_prompt=profile.system_prompt(),
        subject=AuthorizationSubject(user_id="user-1"),
        launch_origin={"source_record_id": source.id},
    )

    response = asyncio.run(runner.run(request, profile.tools()))

    page = response.tool_calls[0].result
    assert page["ok"] is True
    assert page["data"]["count"] == 10
    assert page["data"]["ancestors"][0]["depth"] == 4
    assert page["data"]["ancestors"][-1]["depth"] == 13
    assert page["data"]["has_more"] is True
    assert page["data"]["more_ancestors_remain"] is True
    assert page["data"]["next_cursor"]
    rejection = response.tool_calls[1].result
    assert rejection["ok"] is False
    assert rejection["data"]["error"] == "cross_conversation_rejected"


def test_reply_provenance_survives_store_restart_and_exact_lookup(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = FileStore(root)
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1:thread:t1",
            guild_id="g1",
            channel_id="c1",
            thread_id="t1",
        )
    )
    source = _persist_chain(store, conversation.id, "restart-source", 4)

    reloaded = FileStore(root)
    restored = reloaded.find_conversation_message_by_discord_id(
        conversation.id, "restart-source"
    )

    assert restored is not None
    assert restored.id == source.id
    assert [row["message_id"] for row in restored.discord_reply_provenance["ancestors"]] == [
        "discord-1",
        "discord-2",
        "discord-3",
        "discord-4",
    ]
    assert "read_reply_chain" in render_reply_context(restored)
    replayed = reloaded.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="changed replay payload",
        discord_message_id="restart-source",
        discord_reply_provenance={"schema_version": "changed-replay"},
        idempotency_key="persist-restart-source",
    )
    assert replayed.id == restored.id
    assert replayed.discord_reply_provenance == restored.discord_reply_provenance
    with pytest.raises(ValueError, match="immutable inbound Discord provenance"):
        reloaded.update_message(
            restored.id,
            discord_reply_provenance={"schema_version": "tampered"},
        )


def test_capture_depth_is_hard_bounded() -> None:
    message = _message_with_chain(REPLY_CAPTURE_MAX_ANCESTORS + 5)
    assert len(message.discord_reply_provenance["ancestors"]) == REPLY_CAPTURE_MAX_ANCESTORS
    assert message.discord_reply_provenance["capture_truncated"] is True
    assert message.discord_reply_provenance["chain_complete"] is False


def test_constrained_cli_read_uses_immutable_conversation_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileStore(tmp_path / "store")
    first = store.upsert_resident_conversation(
        ResidentConversationInput(conversation_key="discord:dm:111", dm_user_id="111")
    )
    second = store.upsert_resident_conversation(
        ResidentConversationInput(conversation_key="discord:dm:222", dm_user_id="222")
    )
    source = _persist_chain(store, first.id, "123456789012345678", 6)
    outside = _persist_chain(store, second.id, "223456789012345678", 1)
    monkeypatch.setenv(
        DELEGATION_CONTEXT_ENV,
        encoded_provenance(
            {
                "applicability": "applicable",
                "transport": "discord",
                "resident_conversation_id": first.id,
                "source_record_id": source.id,
                "conversation_key": "discord:dm:111",
                "discord_message_id": "123456789012345678",
                "reply_to_message_id": "123456789012345678",
            }
        ),
    )

    page = _resident_read_reply_chain(
        store,
        source_message_id=None,
        cursor=encode_reply_cursor(source.id, 3),
        limit=2,
    )

    assert [row["depth"] for row in page["ancestors"]] == [4, 5]
    assert page["has_more"] is True
    with pytest.raises(CliError, match="outside the active conversation"):
        _resident_read_reply_chain(
            store,
            source_message_id=outside.id,
            cursor=None,
            limit=2,
        )
    with pytest.raises(CliError, match="between 1 and 10"):
        _resident_read_reply_chain(
            store,
            source_message_id=source.id,
            cursor=None,
            limit=11,
        )
