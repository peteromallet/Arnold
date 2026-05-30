"""W11a — Effect-Ledger type skeleton.

Defines the typed Effect dataclass (replay_class, idempotency_key, compensation)
intended for attachment as an optional, unenforced field on STATE_WRITTEN events.

Nothing in M1 enforces or branches on this field — enforcement is deferred to M4.
This is intentionally distinct from the coarse ``effect_class`` literal stamp on
the STATE_WRITTEN payload (which is a plain string like ``"state_write"``).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


class ReplayClass(str, enum.Enum):
    """How an effect behaves under replay."""

    pure = "pure"
    idempotent_keyed = "idempotent_keyed"
    at_most_once = "at_most_once"
    pivot = "pivot"


@dataclass
class Effect:
    """Typed effect descriptor attached to STATE_WRITTEN events.

    Fields
    ------
    replay_class:
        One of ``{pure, idempotent_keyed, at_most_once, pivot}``.
    idempotency_key:
        A stable string key used for deduplication under
        ``idempotent_keyed`` replay.  Distinct from any content-hash.
        ``None`` for non-keyed replay classes.
    compensation:
        An opaque reference to a compensating action (e.g. a rollback
        procedure name).  ``None`` when no compensation is defined.
    """

    replay_class: ReplayClass
    idempotency_key: Optional[str] = None
    compensation: Optional[str] = None
