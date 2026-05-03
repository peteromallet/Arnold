"""Actor identity resolution utilities for the DBStore path."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from megaplan.schemas import AutomationActor
    from megaplan.store.db import DBStore


def resolve_actor_id(args: argparse.Namespace) -> str | None:
    return getattr(args, "actor", None) or os.environ.get("MEGAPLAN_ACTOR_ID")


def require_actor_id(actor_id: str | None, context: str = "DB writes") -> str:
    if actor_id is None:
        print(
            f"Error: actor ID required for {context}. "
            "Set MEGAPLAN_ACTOR_ID or pass --actor <id>.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return actor_id


def validate_actor_exists(store: DBStore, actor_id: str) -> AutomationActor:
    actor = store.load_automation_actor(actor_id)
    if actor is None:
        print(
            f"Error: actor {actor_id!r} not found in automation_actors table. "
            "Register it first with create_automation_actor().",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return actor


__all__ = ["resolve_actor_id", "require_actor_id", "validate_actor_exists"]
