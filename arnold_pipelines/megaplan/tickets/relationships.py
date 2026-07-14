"""Centralized ticket-epic relationship semantics.

Reads and writes for ticket–epic relationships (frontmatter and store rows)
are routed through this module so that normalization, legacy compatibility,
and auto-address gating are defined in one place.

Relationship kinds
------------------
* ``associated`` — the ticket relates to the epic but does not auto-address.
* ``promoted_to_epic`` — the ticket was promoted **into** this epic.
* ``resolves_on_complete`` — the ticket is linked such that completing the
  epic marks the ticket addressed.  The ``resolves_on_complete`` boolean
  on the model is the sole gate for auto-addressing.

Legacy normalisation
--------------------
Frontmatter entries written before the kind/provenance schema were introduced
carry only ``epic_id`` and ``resolves_on_complete``.  When we read those
legacy entries we normalise them to ``kind='associated'``, ``provenance=None``
unless the ``resolves_on_complete`` boolean is set (in which case the kind
becomes ``'resolves_on_complete'``).  All new writes include explicit kind
and provenance.

Auto-address gate
-----------------
The auto-address hook (``address_tickets_resolved_by_epic``) gates **only** on
the boolean ``resolves_on_complete`` field — never on ``kind``.  This is
enforced by the predicate returned from this module and consumed by both
the FileStore and DBStore implementations.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.schemas import TicketEpicLink
from arnold_pipelines.megaplan.schemas.base import utc_now

# ---------------------------------------------------------------------------
# Relationship kind constants
# ---------------------------------------------------------------------------

KIND_ASSOCIATED: str = "associated"
"""Standard associated relationship (no auto-address)."""

KIND_PROMOTED_TO_EPIC: str = "promoted_to_epic"
"""Ticket was promoted into this epic."""

KIND_RESOLVES_ON_COMPLETE: str = "resolves_on_complete"
"""Ticket auto-addresses when the epic completes."""

RELATIONSHIP_KINDS: frozenset[str] = frozenset(
    {KIND_ASSOCIATED, KIND_PROMOTED_TO_EPIC, KIND_RESOLVES_ON_COMPLETE}
)
"""Every recognised relationship kind."""


# ---------------------------------------------------------------------------
# Normalisation / parsing
# ---------------------------------------------------------------------------


def _parse_datetime(value: object) -> Any:
    """Parse a datetime-like value, returning a datetime or None."""
    from datetime import datetime

    from arnold_pipelines.megaplan.store._file.common import _parse_datetime as _impl

    return _impl(value)


def parse_frontmatter_links(
    record: Mapping[str, Any],
    ticket_id: str,
) -> list[TicketEpicLink]:
    """Parse and normalise ``epics`` frontmatter entries into TicketEpicLink rows.

    Legacy entries (no ``kind`` or ``provenance`` key) are normalised:
    * If ``resolves_on_complete`` is truthy → ``kind='resolves_on_complete'``,
      ``provenance=None``.
    * Otherwise → ``kind='associated'``, ``provenance=None``.

    New-style entries preserve their explicit kind and provenance.
    """
    links: list[TicketEpicLink] = []
    for entry in record.get("epics") or []:
        if not isinstance(entry, Mapping):
            continue
        epic_id = entry.get("epic_id")
        if not isinstance(epic_id, str) or not epic_id:
            continue

        resolves = bool(entry.get("resolves_on_complete"))

        # Normalise kind for legacy entries that lack it
        raw_kind = entry.get("kind")
        if isinstance(raw_kind, str) and raw_kind in RELATIONSHIP_KINDS:
            kind = raw_kind
        elif resolves:
            kind = KIND_RESOLVES_ON_COMPLETE
        else:
            kind = KIND_ASSOCIATED

        # Normalise provenance
        raw_prov = entry.get("provenance")
        provenance: str | None
        if isinstance(raw_prov, str) and raw_prov:
            provenance = raw_prov
        else:
            provenance = None

        linked_at = _parse_datetime(entry.get("linked_at")) or utc_now()

        links.append(
            TicketEpicLink(
                ticket_id=ticket_id,
                epic_id=epic_id,
                resolves_on_complete=resolves,
                kind=kind,
                provenance=provenance,
                linked_at=linked_at,
            )
        )
    return links


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def serialize_links_to_frontmatter(
    links: Sequence[TicketEpicLink],
) -> list[dict[str, Any]]:
    """Convert TicketEpicLink rows to the ``epics`` frontmatter payload.

    Every entry includes ``kind`` and ``provenance`` so that round-trips
    are clean and legacy readers benefit from the normalised data.
    """
    return [
        {
            "epic_id": link.epic_id,
            "resolves_on_complete": link.resolves_on_complete,
            "kind": link.kind,
            "provenance": link.provenance,
            "linked_at": link.linked_at,
        }
        for link in links
    ]


# ---------------------------------------------------------------------------
# Auto-address gate
# ---------------------------------------------------------------------------


def auto_address_predicate(link: TicketEpicLink) -> bool:
    """Return *True* when *link* qualifies the ticket for auto-address.

    **The gate is only the ``resolves_on_complete`` boolean** — ``kind``
    is deliberately not consulted so that a legacy entry carrying
    ``resolves_on_complete=True`` (and normalised to any kind) still
    triggers auto-address.
    """
    return bool(link.resolves_on_complete)
