"""Canonical lifecycle boundary for the Discord resident restart command."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentbox.reset_notifications import RESET_DELIVERY_EPHEMERAL_INTERACTION
from agentbox.services import DISCORD_RESIDENT_SERVICE, restart_service


RESTART_RESIDENT_COMMAND = "restart-resident"
RESTART_RESIDENT_DESCRIPTION = "Safely restart only the Discord resident process."
RESTART_RESIDENT_ACKNOWLEDGEMENT = (
    "Restart safety check started. The current resident turn can be interrupted, "
    "while resident-managed detached agents and tmux-backed Megaplan/cloud chains "
    "are preserved."
)


def restart_discord_resident(
    *, delivery_ownership: str | None = None
) -> Mapping[str, Any]:
    """Invoke the one guarded AgentBox resident lifecycle operation."""

    return restart_service(
        DISCORD_RESIDENT_SERVICE, notification_delivery_ownership=delivery_ownership
    )


__all__ = [
    "RESTART_RESIDENT_ACKNOWLEDGEMENT",
    "RESTART_RESIDENT_COMMAND",
    "RESTART_RESIDENT_DESCRIPTION",
    "RESET_DELIVERY_EPHEMERAL_INTERACTION",
    "restart_discord_resident",
]
