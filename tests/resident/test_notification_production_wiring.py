from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import runtime_attestation
from arnold_pipelines.megaplan.resident.cli import _resident_discord
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.delivery_effects import (
    DeliveryChannel,
    DeliveryTarget,
)
from arnold_pipelines.megaplan.resident.discord import (
    DiscordOutboundSink,
    ResidentDiscordService,
)
from arnold_pipelines.megaplan.resident.runtime import OutboundMessage
from arnold_pipelines.megaplan.store import FileStore


class _Channel:
    def __init__(self, *, applied_timeout: bool = False) -> None:
        self.calls = 0
        self.applied_timeout = applied_timeout

    async def send(self, content: str, **kwargs: Any) -> Any:
        self.calls += 1
        if self.applied_timeout:
            raise TimeoutError("provider accepted the write but acknowledgement was lost")
        return SimpleNamespace(id=f"discord-{self.calls}")


class _Client:
    def __init__(self, channel: _Channel) -> None:
        self.channel = channel

    def get_channel(self, channel_id: int) -> _Channel:
        return self.channel


def _build_real_production_sink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> DiscordOutboundSink:
    captured: list[ResidentDiscordService] = []
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-production-token")
    monkeypatch.setattr(
        runtime_attestation,
        "require_configured_runtime_launch",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        ResidentDiscordService,
        "run",
        lambda service: captured.append(service),
    )
    result = _resident_discord(
        tmp_path,
        FileStore(tmp_path / "resident-store"),
        ResidentConfig(mode="production", discord_bot_role="production"),
        dry_run=False,
    )
    assert result["stopped"] is True
    assert len(captured) == 1
    sink = captured[0].runtime.outbound
    assert isinstance(sink, DiscordOutboundSink)
    assert sink.delivery_effects is not None
    assert (
        tmp_path
        / "resident-store"
        / "delivery_effects"
        / "delivery-effects.sqlite3"
    ).is_file()
    return sink


def _autonomous_message(key: str = "stable-occurrence") -> OutboundMessage:
    return OutboundMessage(
        conversation_key="discord:guild:1:channel:2",
        content="one durable operational notification",
        idempotency_key=key,
        metadata={
            "delivery_kind": "autonomous_scheduled",
            "operational_delivery": True,
        },
    )


def test_real_production_constructor_delivers_once_across_200_polls_and_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _Channel()
    first = _build_real_production_sink(tmp_path, monkeypatch)
    first.bind_client(_Client(channel))

    async def poll(sink: DiscordOutboundSink, count: int) -> None:
        for _ in range(count):
            await sink.send(_autonomous_message())

    asyncio.run(poll(first, 100))
    first.delivery_effects.close()

    restarted = _build_real_production_sink(tmp_path, monkeypatch)
    restarted.bind_client(_Client(channel))
    asyncio.run(poll(restarted, 100))

    assert channel.calls == 1
    restarted.delivery_effects.close()


def test_real_production_constructor_records_applied_timeout_as_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _Channel(applied_timeout=True)
    first = _build_real_production_sink(tmp_path, monkeypatch)
    first.bind_client(_Client(channel))

    with pytest.raises(RuntimeError, match="routing unavailable"):
        asyncio.run(first.send(_autonomous_message("applied-timeout")))
    first.delivery_effects.close()

    restarted = _build_real_production_sink(tmp_path, monkeypatch)
    restarted.bind_client(_Client(channel))
    with pytest.raises(RuntimeError, match="routing unavailable"):
        asyncio.run(restarted.send(_autonomous_message("applied-timeout")))

    assert channel.calls == 1
    accepted = restarted.delivery_effects.protocol.accepted_outcome_for_glek(
        restarted.delivery_effects._build_effect_identity(
            # Mirror the production sink's stable effect identity.
            DeliveryTarget(
                channel=DeliveryChannel.RESIDENT,
                parent_id="discord:guild:1:channel:2",
                target_id="applied-timeout",
                action="send",
            )
        ).global_logical_effect_key
    )
    assert accepted is not None
    assert accepted.outcome_kind == "INDETERMINATE"
    restarted.delivery_effects.close()


def test_adapter_failure_never_falls_through_to_direct_discord(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _Channel()
    sink = _build_real_production_sink(tmp_path, monkeypatch)
    sink.bind_client(_Client(channel))

    async def broken_adapter(**_kwargs: Any) -> Any:
        raise RuntimeError("effect store unavailable")

    monkeypatch.setattr(sink.delivery_effects, "deliver_async", broken_adapter)
    with pytest.raises(RuntimeError, match="routing unavailable"):
        asyncio.run(sink.send(_autonomous_message("adapter-failure")))

    assert channel.calls == 0
    sink.delivery_effects.close()


def test_interactive_reply_remains_an_explicit_direct_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _Channel()
    sink = _build_real_production_sink(tmp_path, monkeypatch)
    sink.bind_client(_Client(channel))
    message = OutboundMessage(
        conversation_key="discord:guild:1:channel:2",
        content="ordinary reply",
        idempotency_key="interactive-reply",
        metadata={"delivery_kind": "interactive_reply"},
    )

    asyncio.run(sink.send(message))

    assert channel.calls == 1
    assert message.metadata.get("delivery_effects_routed") is None
    sink.delivery_effects.close()


def test_production_notification_wiring_inventory_is_closed() -> None:
    repo = Path(__file__).resolve().parents[2]
    production_roots = (repo / "arnold_pipelines", repo / "agentbox")
    constructors: list[tuple[Path, ast.Call]] = []
    sweeps: list[tuple[Path, ast.Call]] = []
    for root in production_roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name == "DiscordOutboundSink":
                    constructors.append((path.relative_to(repo), node))
                elif name == "sweep_managed_agent_deliveries":
                    sweeps.append((path.relative_to(repo), node))

    # The only standalone constructor is an explicitly named manual test
    # helper. The resident production constructor must inject the owner.
    assert {str(path) for path, _ in constructors} == {
        "agentbox/notify.py",
        "arnold_pipelines/megaplan/resident/cli.py",
    }
    resident_calls = [
        node
        for path, node in constructors
        if str(path) == "arnold_pipelines/megaplan/resident/cli.py"
    ]
    assert len(resident_calls) == 1
    assert "delivery_effects" in {keyword.arg for keyword in resident_calls[0].keywords}

    assert len(sweeps) == 2
    assert all(
        "delivery_effects" in {keyword.arg for keyword in call.keywords}
        for _path, call in sweeps
    )


def test_operational_sink_without_effect_owner_is_action_off() -> None:
    channel = _Channel()
    sink = DiscordOutboundSink(
        _Client(channel),
        delivery_environment="production",
        bot_role="production",
    )

    with pytest.raises(RuntimeError, match="no durable DeliveryEffects owner"):
        asyncio.run(sink.send(_autonomous_message("missing-owner")))

    assert channel.calls == 0
