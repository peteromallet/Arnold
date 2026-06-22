"""Read helpers for Store-backed editorial context."""

from __future__ import annotations

from arnold_pipelines.megaplan.store import HotContext, Store


def load_hot_context(store: Store, epic_id: str | None, *, actor_id: str | None = None) -> HotContext:
    del actor_id
    return store.load_hot_context(epic_id)
