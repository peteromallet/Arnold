"""Pure mutation helpers for v1 strategy roadmap entries.

This module provides side-effect-free functions that mutate a parsed
:class:`StrategyDocument`'s roadmap entries.  All functions return new
documents — the originals are never modified.  Combined with
:func:`serialize_strategy`, these helpers form the authority-preserving
write path for automated roadmap changes (promotion, re-planning, etc.).

Design rules
------------

* **Authority-preserving**: mutations only add/remove/replace roadmap
  entries; they never modify stable-direction bodies, schema versions,
  or existing diagnostics (except to append new ones).
* **Horizon-independent**: horizons are independent of artifact type.
  Both ticket and epic entries can appear in any horizon.
* **No forced visibility**: removing or replacing a non-present entry
  is a clean no-op — no artifact is forced into the strategy.
* **Duplicate-intent diagnostics**: when a promotion would result in
  both a ticket and an epic entry for the same logical work, a
  diagnostic is emitted so the operator can clean up.
* **Projections are disposable**: these helpers never read or write
  ``.megaplan/strategy.projection.json``.  The projection is always
  regenerated from the canonical Markdown source.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
)

# ---------------------------------------------------------------------------
# Sentinel source location for mutation-generated entries
# ---------------------------------------------------------------------------

_MUTATION_PATH = "<strategy-mutation>"
"""Source path used for entries created by mutation helpers.

Mutation-generated entries are not parsed from a file, so they carry a
sentinel source location.  This distinguishes them from author-authored
entries and makes it clear they were produced by automation.
"""


def _mutation_source_location() -> SourceLocation:
    """Return a sentinel SourceLocation for mutation-generated entries."""
    return SourceLocation(path=_MUTATION_PATH, line=0, column=0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_entry(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]],
    identity: StrategyIdentity,
) -> tuple[RoadmapHorizon | None, int | None]:
    """Find *identity* in *roadmap*.

    Returns ``(horizon, index)`` if found, or ``(None, None)`` if not.
    """
    target_key = (identity.type, identity.ref)
    for horizon, entries in roadmap.items():
        for idx, entry in enumerate(entries):
            key = (entry.identity.type, entry.identity.ref)
            if key == target_key:
                return horizon, idx
    return None, None


def _copy_roadmap(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]],
) -> dict[RoadmapHorizon, list[RoadmapEntry]]:
    """Shallow-copy the roadmap dict (entries themselves are frozen)."""
    return {horizon: list(entries) for horizon, entries in roadmap.items()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def add_roadmap_entry(
    document: StrategyDocument,
    entry: RoadmapEntry,
    horizon: RoadmapHorizon,
) -> StrategyDocument:
    """Add *entry* to *horizon*, returning a new document.

    If an entry with the same ``(type, ref)`` identity already exists in
    *any* horizon, the document is returned unchanged.  This makes
    repeated adds idempotent and prevents accidental duplicates across
    horizons.

    Parameters
    ----------
    document:
        The parsed strategy document.
    entry:
        The roadmap entry to add.  Its ``horizon`` field is ignored —
        the *horizon* parameter determines placement.
    horizon:
        The horizon to place the entry in (``Now``, ``Next``, ``Later``).

    Returns
    -------
    StrategyDocument
        A new document with the entry added, or the unchanged document
        if the identity was already present.
    """
    diagnostics: list[StrategyDiagnostic] = list(document.diagnostics)

    existing_horizon, _ = _find_entry(document.roadmap, entry.identity)
    if existing_horizon is not None:
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Roadmap entry '{entry.identity.type}:{entry.identity.ref}' "
                    f"already exists in horizon '{existing_horizon}'; "
                    f"ignoring add to '{horizon}'."
                ),
                source_location=entry.source_location,
            )
        )
        return StrategyDocument(
            schema_version=document.schema_version,
            stable_direction=list(document.stable_direction),
            roadmap=_copy_roadmap(document.roadmap),
            diagnostics=diagnostics,
        )

    new_roadmap = _copy_roadmap(document.roadmap)
    # Create a new entry with the correct horizon.
    entry_with_horizon = RoadmapEntry(
        identity=entry.identity,
        display_title=entry.display_title,
        horizon=horizon,
        source_location=entry.source_location,
    )
    new_roadmap[horizon].append(entry_with_horizon)

    return StrategyDocument(
        schema_version=document.schema_version,
        stable_direction=list(document.stable_direction),
        roadmap=new_roadmap,
        diagnostics=diagnostics,
    )


def remove_roadmap_entry(
    document: StrategyDocument,
    identity: StrategyIdentity,
) -> StrategyDocument:
    """Remove the entry matching *identity* from whichever horizon it appears in.

    If *identity* is not found in any horizon, the document is returned
    unchanged (idempotent removal).  This makes repeated removals safe
    and avoids forcing non-roadmap artifacts into the strategy.

    Parameters
    ----------
    document:
        The parsed strategy document.
    identity:
        The ``(type, ref)`` pair to remove.

    Returns
    -------
    StrategyDocument
        A new document with the entry removed, or the unchanged document
        if the identity was not found.
    """
    existing_horizon, existing_idx = _find_entry(document.roadmap, identity)
    if existing_horizon is None or existing_idx is None:
        # Not found — idempotent no-op.
        return StrategyDocument(
            schema_version=document.schema_version,
            stable_direction=list(document.stable_direction),
            roadmap=_copy_roadmap(document.roadmap),
            diagnostics=list(document.diagnostics),
        )

    new_roadmap = _copy_roadmap(document.roadmap)
    new_roadmap[existing_horizon].pop(existing_idx)

    return StrategyDocument(
        schema_version=document.schema_version,
        stable_direction=list(document.stable_direction),
        roadmap=new_roadmap,
        diagnostics=list(document.diagnostics),
    )


def replace_roadmap_entry(
    document: StrategyDocument,
    old_identity: StrategyIdentity,
    new_entry: RoadmapEntry,
    horizon: RoadmapHorizon,
) -> StrategyDocument:
    """Remove *old_identity* (if present) and add *new_entry* to *horizon*.

    If *old_identity* is not in the roadmap, only *new_entry* is added
    — no artifact is forced into the strategy (no forced visibility for
    non-roadmap tickets).  If *new_entry*'s identity already exists in any
    horizon, the add is idempotent.

    This is the low-level building block for promotion: replace a ticket
    entry with an epic entry in the same horizon.

    Parameters
    ----------
    document:
        The parsed strategy document.
    old_identity:
        The ``(type, ref)`` pair to remove (may not exist).
    new_entry:
        The roadmap entry to add.  Its ``horizon`` field is ignored —
        the *horizon* parameter determines placement.
    horizon:
        The horizon to place *new_entry* in.

    Returns
    -------
    StrategyDocument
        A new document with the replacement applied.
    """
    # Step 1: remove old identity (idempotent if not present).
    after_removal = remove_roadmap_entry(document, old_identity)

    # Step 2: add new entry (idempotent if already present).
    return add_roadmap_entry(after_removal, new_entry, horizon)


def make_roadmap_entry(
    type_: RoadmapItemType,
    ref: str,
    title: str,
    horizon: RoadmapHorizon | None = None,
) -> RoadmapEntry:
    """Build a :class:`RoadmapEntry` from its identity components.

    This is a convenience constructor for callers that only have the
    ``(type, ref, title)`` triple and want a fully-formed entry.  The
    generated entry carries the mutation sentinel source location.

    Parameters
    ----------
    type_:
        The artifact type (``"ticket"`` or ``"epic"``).
    ref:
        The unique artifact reference (e.g. a ULID or initiative slug).
    title:
        The human-readable display title.
    horizon:
        The horizon to assign.  When *None* the entry has no placement
        preference — callers must still supply a horizon when adding.

    Returns
    -------
    RoadmapEntry
        A frozen entry ready for use with :func:`add_roadmap_entry` or
        :func:`move_roadmap_entry`.
    """
    return RoadmapEntry(
        identity=StrategyIdentity(type=type_, ref=ref),
        display_title=title,
        horizon=horizon or "Now",  # sentinel; actual horizon comes from caller
        source_location=_mutation_source_location(),
    )


def move_roadmap_entry(
    document: StrategyDocument,
    identity: StrategyIdentity,
    target_horizon: RoadmapHorizon,
) -> StrategyDocument:
    """Move the entry identified by *identity* to *target_horizon*.

    Built on top of :func:`add_roadmap_entry` and
    :func:`remove_roadmap_entry` — no horizon-level logic is duplicated.
    The move is *identity-preserving*: only the horizon changes; the
    entry's ``display_title`` and ``source_location`` are carried forward
    unchanged.

    **Idempotency**: moving an entry to the horizon it already occupies is
    an explicit no-op.  A diagnostic is emitted so CLI callers receive
    clear feedback instead of silent success.

    **Missing-entry signaling**: when *identity* is not present in any
    roadmap horizon, the document is returned unchanged and a warning
    diagnostic is appended.  No entry is forced into any horizon.

    **Horizon independence**: the move does not inspect or depend on
    artifact type.  Both ``ticket`` and ``epic`` entries can freely move
    between any horizons.

    Parameters
    ----------
    document:
        The parsed strategy document.
    identity:
        The ``(type, ref)`` pair identifying the entry to move.
    target_horizon:
        The destination horizon (``Now``, ``Next``, or ``Later``).

    Returns
    -------
    StrategyDocument
        A new document with the entry relocated, or the unchanged document
        if the identity was not found or is already in the target horizon.
    """
    diagnostics: list[StrategyDiagnostic] = list(document.diagnostics)

    # ---- Locate the entry ---------------------------------------------------
    current_horizon, current_idx = _find_entry(document.roadmap, identity)
    if current_horizon is None:
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Cannot move '{identity.type}:{identity.ref}' to "
                    f"'{target_horizon}': entry is not present in any "
                    f"roadmap horizon."
                ),
                source_location=_mutation_source_location(),
            )
        )
        return StrategyDocument(
            schema_version=document.schema_version,
            stable_direction=list(document.stable_direction),
            roadmap=_copy_roadmap(document.roadmap),
            diagnostics=diagnostics,
        )

    # ---- Already in the target horizon: idempotent no-op --------------------
    if current_horizon == target_horizon:
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Entry '{identity.type}:{identity.ref}' is already in "
                    f"horizon '{target_horizon}'; move is a no-op."
                ),
                source_location=_mutation_source_location(),
            )
        )
        return StrategyDocument(
            schema_version=document.schema_version,
            stable_direction=list(document.stable_direction),
            roadmap=_copy_roadmap(document.roadmap),
            diagnostics=diagnostics,
        )

    # ---- Preserve the existing entry's attributes ---------------------------
    existing_entry = document.roadmap[current_horizon][current_idx]
    entry_for_target = RoadmapEntry(
        identity=existing_entry.identity,
        display_title=existing_entry.display_title,
        horizon=target_horizon,
        source_location=existing_entry.source_location,
    )

    # ---- Remove from current horizon (reuses remove_roadmap_entry) ----------
    after_removal = remove_roadmap_entry(document, identity)

    # ---- Add to target horizon (reuses add_roadmap_entry) -------------------
    result = add_roadmap_entry(after_removal, entry_for_target, target_horizon)

    # Merge diagnostics from the sub-operations.
    all_diagnostics = diagnostics + [
        d
        for d in result.diagnostics
        if d not in diagnostics and d not in document.diagnostics
    ]

    return StrategyDocument(
        schema_version=document.schema_version,
        stable_direction=list(document.stable_direction),
        roadmap=result.roadmap,
        diagnostics=all_diagnostics,
    )


def promote_ticket_to_epic(
    document: StrategyDocument,
    ticket_ref: str,
    epic_ref: str,
    epic_display_title: str,
    horizon: RoadmapHorizon | None = None,
) -> StrategyDocument:
    """Promote a ticket to an epic, replacing its roadmap entry.

    Promotion replaces the ticket's roadmap entry with a corresponding
    epic entry.  The replacement happens in-place — the epic inherits the
    ticket's horizon unless *horizon* is explicitly provided.

    **Duplicate-intent detection**: if both the ticket and a pre-existing
    epic entry are present in the roadmap (two entries for the same
    logical work), the ticket is removed, the epic is kept, and a
    diagnostic is emitted.

    **No forced visibility**: if the ticket is not in the roadmap
    (non-roadmap ticket), promotion adds *neither* the ticket *nor* the
    epic to the strategy.  Roadmap membership is strategic visibility, not
    existence.  A pre-existing epic entry remains idempotent (unchanged).

    Parameters
    ----------
    document:
        The parsed strategy document.
    ticket_ref:
        The ticket ULID being promoted.
    epic_ref:
        The canonical initiative slug (epic ID) for the new epic.
    epic_display_title:
        The display title for the new epic roadmap entry.
    horizon:
        The horizon to place the epic in, applied *only* when the promoted
        ticket is strategically visible.  When *None* (default), the
        ticket's current horizon is used.  If the ticket is not in the
        roadmap, the epic is never added (no forced visibility), so
        *horizon* is ignored.

    Returns
    -------
    StrategyDocument
        A new document with the promotion applied and any relevant
        diagnostics appended.
    """
    diagnostics: list[StrategyDiagnostic] = list(document.diagnostics)

    ticket_identity = StrategyIdentity(type="ticket", ref=ticket_ref)
    epic_identity = StrategyIdentity(type="epic", ref=epic_ref)

    ticket_horizon, _ = _find_entry(document.roadmap, ticket_identity)
    epic_horizon, _ = _find_entry(document.roadmap, epic_identity)

    # ---- Non-roadmap ticket: no forced visibility ---------------------------
    # If the promoted ticket is absent from every roadmap horizon, promotion
    # must NOT add either the ticket or the epic to the strategy.  Roadmap
    # membership is strategic visibility, not existence (SD2).  A pre-existing
    # epic entry remains idempotent (it is neither duplicated nor moved).
    if ticket_horizon is None:
        if epic_horizon is None:
            diagnostics.append(
                StrategyDiagnostic(
                    level="warning",
                    message=(
                        f"Ticket '{ticket_ref}' is not present in any roadmap "
                        f"horizon; promotion did not add epic '{epic_ref}' to "
                        f"the strategy (no forced visibility for non-roadmap "
                        f"tickets)."
                    ),
                    source_location=_mutation_source_location(),
                )
            )
        # Return a fresh, unchanged document (roadmap untouched).  No ticket is
        # forced in; no epic is added or moved.
        return StrategyDocument(
            schema_version=document.schema_version,
            stable_direction=list(document.stable_direction),
            roadmap=_copy_roadmap(document.roadmap),
            diagnostics=diagnostics,
        )

    # ---- Ticket is strategically visible: replace-in-same-horizon ----------
    # The epic inherits the ticket's horizon unless an explicit *horizon* is
    # provided.
    target_horizon: RoadmapHorizon = horizon if horizon is not None else ticket_horizon

    # ---- Duplicate-intent detection -----------------------------------------
    # Reaching here guarantees the ticket is present; if the epic is also
    # present, both represent the same logical work.
    if epic_horizon is not None:
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Duplicate intent detected: ticket '{ticket_ref}' "
                    f"and epic '{epic_ref}' both appear in the roadmap "
                    f"(ticket in '{ticket_horizon}', epic in '{epic_horizon}'). "
                    f"Promotion removed the ticket entry; the epic entry is "
                    f"preserved.  Review to ensure only one entry represents "
                    f"this work."
                ),
                source_location=_mutation_source_location(),
            )
        )

    # Build the new epic roadmap entry.
    epic_entry = RoadmapEntry(
        identity=epic_identity,
        display_title=epic_display_title,
        horizon=target_horizon,
        source_location=_mutation_source_location(),
    )

    # Step 1: remove ticket (idempotent if not present).
    after_removal = remove_roadmap_entry(document, ticket_identity)

    # Step 2: add epic entry (idempotent if already present).
    # We must also carry forward the duplicate-intent diagnostics.
    result = add_roadmap_entry(after_removal, epic_entry, target_horizon)

    # Merge our diagnostics with any from add_roadmap_entry.
    all_diagnostics = diagnostics + [
        d
        for d in result.diagnostics
        if d not in diagnostics and d not in document.diagnostics
    ]

    return StrategyDocument(
        schema_version=document.schema_version,
        stable_direction=list(document.stable_direction),
        roadmap=result.roadmap,
        diagnostics=all_diagnostics,
    )
