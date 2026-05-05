from __future__ import annotations

import inspect

import megaplan.auto as auto
from megaplan.editorial.reads import load_hot_context
from megaplan.store.base import HotContext


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        self.calls.append(epic_id)
        return HotContext()


def test_load_hot_context_delegates_to_store_only() -> None:
    store = FakeStore()

    context = load_hot_context(store, "epic-1", actor_id="actor")

    assert isinstance(context, HotContext)
    assert store.calls == ["epic-1"]

    load_hot_context(store, None, actor_id="actor-2")
    assert store.calls == ["epic-1", None]


def test_auto_has_no_active_manual_hot_context_composition_call_site() -> None:
    source = inspect.getsource(auto)

    assert "load_hot_context(" not in source
    assert "recent_messages=" not in source
    assert "active_feedback=" not in source
