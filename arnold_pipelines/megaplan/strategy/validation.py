"""Strategy document validation.

This module validates a parsed :class:`StrategyDocument` for format-level
and structural correctness.  It checks:

* Duplicate ``(type, ref)`` identities across horizons (hard error).
* Ticket refs that are not valid ULIDs (hard error).
* Epic refs that are not canonical initiative slugs (hard error).
* Unsupported item types (hard error — belt-and-suspenders with the parser).
* Missing or empty refs (hard error).

The validator does **not** check artifact existence or stale display titles —
those are handled by :mod:`arnold_pipelines.megaplan.strategy.resolver`.

The validator always returns a new :class:`StrategyDocument` with additional
diagnostics appended.  The original document is never mutated.
"""

from __future__ import annotations

import re
from typing import Dict, List

from arnold_pipelines.megaplan.layout import slugify_initiative
from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
)

# ---------------------------------------------------------------------------
# ULID format
# ---------------------------------------------------------------------------

# ULIDs are 26 characters of Crockford base32 (I, L, O, U excluded).
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

# Epic slugs: lowercase, may contain hyphens, dots, and alphanumeric chars.
# Must survive a round-trip through slugify_initiative unchanged.
_EPIC_SLUG_RE = re.compile(r"^[a-z][a-z0-9._-]*$", re.ASCII)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_strategy(document: StrategyDocument) -> StrategyDocument:
    """Validate *document* and return a new document with additional diagnostics.

    Parameters
    ----------
    document:
        A parsed :class:`StrategyDocument`.  Existing diagnostics are
        preserved.

    Returns
    -------
    StrategyDocument
        A new frozen document with validation diagnostics appended.
    """
    diagnostics: list[StrategyDiagnostic] = list(document.diagnostics)

    # Collect all roadmap entries across horizons with their horizon tag.
    all_entries: list[tuple[RoadmapHorizon, RoadmapEntry]] = []
    for horizon, entries in document.roadmap.items():
        for entry in entries:
            all_entries.append((horizon, entry))

    # ---- 1. Duplicate (type, ref) across horizons ---------------------------
    _check_duplicates(all_entries, diagnostics)

    # ---- 2. Ref format validation --------------------------------------------
    _validate_refs(all_entries, diagnostics)

    return StrategyDocument(
        schema_version=document.schema_version,
        stable_direction=list(document.stable_direction),
        roadmap=_copy_roadmap(document.roadmap),
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def _check_duplicates(
    all_entries: list[tuple[RoadmapHorizon, RoadmapEntry]],
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Emit hard errors for duplicate ``(type, ref)`` pairs across any horizon."""
    seen: dict[tuple[str, str], RoadmapEntry] = {}
    for _horizon, entry in all_entries:
        key = (entry.identity.type, entry.identity.ref)
        if key in seen:
            first = seen[key]
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Duplicate roadmap entry: '{key[0]}:{key[1]}' "
                        f"appears in both '{first.horizon}' and "
                        f"'{entry.horizon}' horizons.  Each (type, ref) "
                        f"pair must be unique across all horizons."
                    ),
                    source_location=entry.source_location,
                )
            )
        else:
            seen[key] = entry


# ---------------------------------------------------------------------------
# Ref format validation
# ---------------------------------------------------------------------------


def _validate_refs(
    all_entries: list[tuple[RoadmapHorizon, RoadmapEntry]],
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Validate ref format for every roadmap entry."""
    for _horizon, entry in all_entries:
        identity = entry.identity
        item_type = identity.type
        ref = identity.ref

        # Empty or whitespace-only ref.
        if not ref.strip():
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Missing reference in roadmap entry "
                        f"'{item_type}:{ref or '<empty>'}'.  "
                        f"Every entry must have a non-empty ref."
                    ),
                    source_location=entry.source_location,
                )
            )
            continue

        if item_type == "ticket":
            _validate_ticket_ref(ref, entry, diagnostics)
        elif item_type == "epic":
            _validate_epic_ref(ref, entry, diagnostics)
        else:
            # Unsupported item type — parser should catch this, but belt-and-suspenders.
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Unsupported item type '{item_type}' in roadmap entry.  "
                        f"Only 'ticket' and 'epic' are valid in v1."
                    ),
                    source_location=entry.source_location,
                )
            )


def _validate_ticket_ref(
    ref: str,
    entry: RoadmapEntry,
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Validate that *ref* is a well-formed ULID."""
    if not _ULID_RE.match(ref):
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Invalid ticket ref '{ref}': ticket refs must be "
                    f"valid 26-character ULIDs (Crockford base32, uppercase)."
                ),
                source_location=entry.source_location,
            )
        )


def _validate_epic_ref(
    ref: str,
    entry: RoadmapEntry,
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Validate that *ref* is a canonical initiative slug.

    A canonical slug round-trips unchanged through :func:`slugify_initiative`,
    i.e. ``slugify_initiative(ref) == ref``.
    """
    # Fast pre-check: basic character set and minimum length.
    if not _EPIC_SLUG_RE.match(ref) or len(ref) < 2:
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Invalid epic ref '{ref}': epic refs must be canonical "
                    f"initiative slugs (lowercase, alphanumeric with hyphens/dots, "
                    f"at least 2 characters)."
                ),
                source_location=entry.source_location,
            )
        )
        return

    # Round-trip through slugify_initiative to confirm canonicity.
    try:
        canonical = slugify_initiative(ref)
    except (ValueError, TypeError):
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Invalid epic ref '{ref}': slugify_initiative rejected "
                    f"the ref as non-canonical."
                ),
                source_location=entry.source_location,
            )
        )
        return

    if canonical != ref:
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Non-canonical epic ref '{ref}': the canonical form is "
                    f"'{canonical}'.  Use the canonical slug in roadmap entries."
                ),
                source_location=entry.source_location,
            )
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_roadmap(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]],
) -> dict[RoadmapHorizon, list[RoadmapEntry]]:
    """Shallow-copy the roadmap dict (entries themselves are frozen)."""
    return {horizon: list(entries) for horizon, entries in roadmap.items()}
