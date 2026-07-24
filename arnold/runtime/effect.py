"""W11a — Effect-Ledger type skeleton (extended for M4 T14).

Defines the typed Effect dataclass intended for attachment as an optional,
unenforced field on state-write events.

Naming notes
------------
* ``idempotency_key`` is the external-act dedup key (e.g. "git push <sha>",
  "pr-create <slug>") used by the M4 RecoveryPolicy to suppress double-execute
  on replay.  This is distinct from any content-hash artifact-dedup used by
  the artifact store; the latter dedupes equal *content*, the former dedupes
  equal *external acts*.
* ``effect_taint`` is the Effect-scoped propagation marker (renamed from any
  earlier ``taint`` field) and is *not* the same concept as
  the pipeline envelope's ``taint`` field.  Pipeline-envelope taint
  is a per-step pipeline marker; Effect.effect_taint is per-effect.  They are
  kept as separate fields so an envelope-level taint upgrade does not silently
  mutate the recorded effect's taint, and vice versa.
* ``compensation`` carries the symbolic name of a compensating action.
  ``None`` means *not declared* (the caller never specified a compensation
  policy); the module-level sentinel ``NONCOMPENSABLE`` (a JSON-safe literal
  string ``"__noncompensable__"``) means *fire-and-forget* — the caller has
  explicitly declared that no compensation is possible or required.  The
  two cases must be distinguishable on replay.

Nothing in M1 enforces or branches on this field — enforcement is deferred
to M4.  This is intentionally distinct from the coarse ``effect_class``
literal stamp on the state-write payload (which is a plain string like
``"state_write"``).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Final, Optional


#: Sentinel string for fire-and-forget effects.  JSON-safe so it round-trips
#: through the state-WAL emission path without
#: special-casing.  ``compensation is None`` means *not declared*;
#: ``compensation == NONCOMPENSABLE`` means *explicitly noncompensable*.
NONCOMPENSABLE: Final[str] = "__noncompensable__"


class ReplayClass(str, enum.Enum):
    """How an effect behaves under replay."""

    pure = "pure"
    idempotent_keyed = "idempotent_keyed"
    at_most_once = "at_most_once"
    pivot = "pivot"


@dataclass
class Effect:
    """Typed effect descriptor attached to state-write events.

    Fields
    ------
    replay_class:
        One of ``{pure, idempotent_keyed, at_most_once, pivot}``.
    idempotency_key:
        A stable string key used for deduplication of *external acts* under
        ``idempotent_keyed`` replay.  Distinct from any content-hash artifact
        dedup.  ``None`` for non-keyed replay classes.
    compensation:
        ``None``  — compensation not declared (default).
        :data:`NONCOMPENSABLE` — fire-and-forget; explicitly no compensation.
        Any other string — opaque reference to a compensating action.
    provenance:
        Free-form dict carrying source attribution (e.g. ``{"module": "...",
        "caller": "..."}``).  Recorded but never used for control flow.
    effect_taint:
        Effect-scoped propagation marker, separate from
        pipeline envelope taint.  Empty string
        means *unset*.
    """

    replay_class: ReplayClass
    idempotency_key: Optional[str] = None
    compensation: Optional[str] = None
    provenance: dict = field(default_factory=dict)
    effect_taint: str = ""
