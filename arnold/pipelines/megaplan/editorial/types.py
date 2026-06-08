"""Small shared types for editorial APIs.

Editorial modules should depend on the Store protocol and explicit operation
inputs. They should not reach into Supabase clients, raw epic files, Arnold
runtime modules, or plan-tree artifacts.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from arnold.pipelines.megaplan.store import Store, Transaction

EpicId: TypeAlias = str
ActorId: TypeAlias = str


@dataclass(frozen=True)
class EditorialOperation:
    store: Store
    epic_id: EpicId
    actor_id: ActorId
    idempotency_key: str | None = None
    turn_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def transaction(self) -> AbstractContextManager[Transaction]:
        return self.store.transaction(epic_id=self.epic_id)


@dataclass(frozen=True)
class EditorialResult:
    epic_id: EpicId
    actor_id: ActorId
    changed: bool
    transaction_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
