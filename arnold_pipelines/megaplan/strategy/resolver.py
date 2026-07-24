"""Repository artifact resolution for strategy roadmap entries.

This module resolves ``ticket`` and ``epic`` references from a parsed
:class:`StrategyDocument` against the repository's actual artifact storage:

* **Tickets** are resolved through the existing ``.megaplan/tickets/*.md``
  file helpers — we walk all ticket files and match by ULID.
* **Epics** (initiatives) are resolved through the canonical
  ``.megaplan/initiatives/<slug>`` directory layout — we check that the
  directory exists and optionally read its title.

The resolver **never** reads the generated projection JSON
(``.megaplan/strategy.projection.json``) as an authority source.  It only
uses the repository's durable artifact storage.

Lifecycle validation
--------------------

Beyond existence and stale-title checks, the resolver performs lifecycle-aware
diagnostics using durable artifact and optional store surfaces:

* **Ticket status**: if a ticket in the roadmap has been ``dismissed`` or
  ``addressed``, a warning is emitted.  The ticket file is still a valid
  artifact (not a missing ref), but its presence in the roadmap is likely
  stale.
* **Superseded / promoted tickets**: if a ticket carries a ``promoted_to_epic``
  relationship link in its frontmatter, the resolver emits a warning that the
  ticket has been superseded and should be removed from the roadmap.
* **Completed epics**: if an epic (initiative) has reached a terminal state
  (``archived``) the resolver warns that it should no longer appear in an
  active roadmap.  State is read from the optional *store* parameter when
  available, otherwise the resolver falls back to durable file-system markers.
* **Duplicate intent (ticket + epic)**: when both a ticket entry **and** an
  epic entry for the same promoted work appear in the roadmap (the ticket has
  a ``promoted_to_epic`` link to that epic), a diagnostic is emitted because
  two entries represent the same logical work.

Projection constraint
---------------------

Roadmap entries in the projection are always limited to
``type/ref/title/horizon/source``.  The resolver never injects lifecycle
status or relationship provenance into roadmap entries or the projection.

Resolved references produce diagnostics:

* **Hard error** — the referenced artifact does not exist.
* **Warning** — the artifact exists but there is a lifecycle concern
  (dismissed/addressed ticket, completed epic, superseded ticket,
  duplicate-intent ticket+epic, or stale display title).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
)
from arnold_pipelines.megaplan.tickets.files import (
    iterate_ticket_files,
)
from arnold_pipelines.megaplan.tickets.relationships import (
    KIND_PROMOTED_TO_EPIC,
    parse_frontmatter_links,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_strategy(
    document: StrategyDocument,
    repo_root: str | Path,
    *,
    store: Any | None = None,
) -> StrategyDocument:
    """Resolve every roadmap entry reference against the repository.

    Parameters
    ----------
    document:
        A parsed :class:`StrategyDocument` (with or without prior diagnostics).
    repo_root:
        The repository root path.  ``.megaplan/tickets/`` and
        ``.megaplan/initiatives/`` are resolved relative to this root.
    store:
        Optional :class:`Store` instance for querying epic state and
        ticket-epic relationship rows.  When *None*, the resolver uses
        only durable filesystem artifacts.

    Returns
    -------
    StrategyDocument
        A new document with additional diagnostics appended for any
        resolution issues.  The original document's stable direction,
        roadmap entries, and existing diagnostics are preserved.
        The returned document is frozen — callers cannot mutate it.
    """
    diagnostics: list[StrategyDiagnostic] = list(document.diagnostics)

    # ---- build ticket index -------------------------------------------------
    # ticket_titles:  {ulid: title}
    # ticket_statuses: {ulid: status}
    # ticket_epic_links: {ulid: [TicketEpicLink, ...]}
    ticket_titles: dict[str, str] = {}
    ticket_statuses: dict[str, str] = {}
    ticket_epic_links: dict[str, list[Any]] = {}
    try:
        for _fpath, fm in iterate_ticket_files(repo_root):
            tid = fm.get("id")
            title = fm.get("title")
            if tid:
                if title:
                    ticket_titles[tid] = title
                status = fm.get("status")
                if isinstance(status, str) and status:
                    ticket_statuses[tid] = status

                # Parse epics links for promotion detection
                links = parse_frontmatter_links(fm, tid)
                if links:
                    ticket_epic_links[tid] = links
    except Exception:
        # Malformed ticket files should not crash the resolver.
        # Diagnostics for missing refs will be emitted downstream.
        pass

    # ---- build initiative index ---------------------------------------------
    initiative_titles: dict[str, str] = {}
    initiative_states: dict[str, str] = {}
    initiatives_dir = Path(repo_root) / ".megaplan" / "initiatives"
    if initiatives_dir.is_dir():
        for entry in initiatives_dir.iterdir():
            if not entry.is_dir():
                continue
            slug = entry.name
            readme = entry / "README.md"
            if readme.is_file():
                title = _read_readme_title(readme)
                if title:
                    initiative_titles[slug] = title

            # Try to read epic state from the initiative directory
            # (e.g. from a chain.yaml or COMPLETED marker)
            state = _read_initiative_state(entry, slug, store)
            if state:
                initiative_states[slug] = state

    # ---- resolve each entry -------------------------------------------------
    for horizon_entries in document.roadmap.values():
        for entry in horizon_entries:
            identity = entry.identity
            if identity.type == "ticket":
                _resolve_ticket_entry(
                    entry,
                    ticket_titles,
                    ticket_statuses,
                    ticket_epic_links,
                    diagnostics,
                )
            elif identity.type == "epic":
                _resolve_epic_entry(
                    entry,
                    initiative_titles,
                    initiative_states,
                    repo_root,
                    diagnostics,
                )

    # ---- duplicate-intent: ticket + epic for same promoted work -------------
    _check_promotion_duplicate_intent(
        document.roadmap, ticket_epic_links, diagnostics
    )

    return StrategyDocument(
        schema_version=document.schema_version,
        stable_direction=list(document.stable_direction),
        roadmap=_copy_roadmap(document.roadmap),
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# Ticket resolution
# ---------------------------------------------------------------------------


def _resolve_ticket_entry(
    entry: RoadmapEntry,
    ticket_titles: dict[str, str],
    ticket_statuses: dict[str, str],
    ticket_epic_links: dict[str, list[Any]],
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Resolve a single ticket roadmap entry against the ticket index."""
    ref = entry.identity.ref

    actual_title = ticket_titles.get(ref)
    if actual_title is None:
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Missing ticket reference: ticket '{ref}' not found "
                    f"in .megaplan/tickets/."
                ),
                source_location=entry.source_location,
            )
        )
        return

    # Stale title check: compare display_title to actual title.
    if entry.display_title != actual_title:
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Stale display title for ticket '{ref}': "
                    f"strategy says '{entry.display_title}', "
                    f"ticket title is '{actual_title}'."
                ),
                source_location=entry.source_location,
            )
        )

    # ---- Lifecycle: ticket status -------------------------------------------
    status = ticket_statuses.get(ref)
    _check_ticket_status(entry, ref, status, diagnostics)

    # ---- Lifecycle: superseded / promoted ticket ----------------------------
    _check_ticket_promotion(entry, ref, ticket_epic_links, diagnostics)


def _check_ticket_status(
    entry: RoadmapEntry,
    ref: str,
    status: str | None,
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Emit warnings for dismissed or addressed tickets still in the roadmap."""
    if status is None:
        return

    if status == "dismissed":
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Dismissed ticket in roadmap: ticket '{ref}' "
                    f"('{entry.display_title}') has been dismissed.  "
                    f"Consider removing it from the roadmap."
                ),
                source_location=entry.source_location,
            )
        )
    elif status == "addressed":
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Addressed ticket in roadmap: ticket '{ref}' "
                    f"('{entry.display_title}') has been addressed.  "
                    f"Consider removing it from the roadmap."
                ),
                source_location=entry.source_location,
            )
        )


def _check_ticket_promotion(
    entry: RoadmapEntry,
    ref: str,
    ticket_epic_links: dict[str, list[Any]],
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Emit warnings when a ticket in the roadmap has been promoted to an epic."""
    links = ticket_epic_links.get(ref)
    if not links:
        return

    promoted_links = [
        l for l in links
        if getattr(l, "kind", None) == KIND_PROMOTED_TO_EPIC
    ]
    if not promoted_links:
        return

    promoted_epic_ids = [
        getattr(l, "epic_id", "?") for l in promoted_links
    ]
    epic_list = ", ".join(f"'{eid}'" for eid in promoted_epic_ids)

    diagnostics.append(
        StrategyDiagnostic(
            level="warning",
            message=(
                f"Superseded ticket in roadmap: ticket '{ref}' "
                f"('{entry.display_title}') has been promoted to epic(s) "
                f"{epic_list}.  The ticket entry should be removed from "
                f"the roadmap — the epic entry(ies) now represent this work."
            ),
            source_location=entry.source_location,
        )
    )


# ---------------------------------------------------------------------------
# Epic (initiative) resolution
# ---------------------------------------------------------------------------


def _resolve_epic_entry(
    entry: RoadmapEntry,
    initiative_titles: dict[str, str],
    initiative_states: dict[str, str],
    repo_root: str | Path,
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Resolve a single epic roadmap entry against the initiatives layout."""
    slug = entry.identity.ref

    # Check that the initiative directory exists.
    initiative_dir = Path(repo_root) / ".megaplan" / "initiatives" / slug
    if not initiative_dir.is_dir():
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Missing epic reference: initiative '{slug}' not found "
                    f"at .megaplan/initiatives/{slug}/."
                ),
                source_location=entry.source_location,
            )
        )
        return

    # Stale title check.
    actual_title = initiative_titles.get(slug)
    if actual_title is not None and entry.display_title != actual_title:
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Stale display title for epic '{slug}': "
                    f"strategy says '{entry.display_title}', "
                    f"initiative title is '{actual_title}'."
                ),
                source_location=entry.source_location,
            )
        )

    # ---- Lifecycle: epic completion -----------------------------------------
    state = initiative_states.get(slug)
    if state and state in ("archived",):
        diagnostics.append(
            StrategyDiagnostic(
                level="warning",
                message=(
                    f"Completed epic in roadmap: epic '{slug}' "
                    f"('{entry.display_title}') is in state '{state}'.  "
                    f"Consider removing it from the active roadmap."
                ),
                source_location=entry.source_location,
            )
        )


# ---------------------------------------------------------------------------
# Duplicate-intent detection (ticket + epic for same promoted work)
# ---------------------------------------------------------------------------


def _check_promotion_duplicate_intent(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]],
    ticket_epic_links: dict[str, list[Any]],
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Emit warnings when both a ticket and its promoted epic are in the roadmap.

    This detects the case where a ticket has been promoted to an epic, but
    both entries still appear in the roadmap — two entries representing the
    same logical work.
    """
    # Build a set of all (type, ref) identities present in the roadmap.
    roadmap_identities: set[tuple[str, str]] = set()
    for horizon_entries in roadmap.values():
        for entry in horizon_entries:
            roadmap_identities.add((entry.identity.type, entry.identity.ref))

    # For each ticket that has promoted_to_epic links, check if the epic
    # is also in the roadmap.
    for ticket_ref, links in ticket_epic_links.items():
        promoted_links = [
            l for l in links
            if getattr(l, "kind", None) == KIND_PROMOTED_TO_EPIC
        ]
        for link in promoted_links:
            epic_ref = getattr(link, "epic_id", None)
            if epic_ref and ("epic", epic_ref) in roadmap_identities:
                # Both ticket and epic are in the roadmap.
                # Find the horizons for a descriptive message.
                ticket_horizon = _find_entry_horizon(roadmap, "ticket", ticket_ref)
                epic_horizon = _find_entry_horizon(roadmap, "epic", epic_ref)
                diagnostics.append(
                    StrategyDiagnostic(
                        level="warning",
                        message=(
                            f"Duplicate intent: ticket '{ticket_ref}' "
                            f"(in '{ticket_horizon or '?'}') and its promoted "
                            f"epic '{epic_ref}' (in '{epic_horizon or '?'}') "
                            f"both appear in the roadmap.  Both entries "
                            f"represent the same logical work — remove the "
                            f"ticket entry to avoid duplicate planning."
                        ),
                        source_location=None,
                    )
                )


def _find_entry_horizon(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]],
    item_type: str,
    ref: str,
) -> str | None:
    """Find the horizon an entry appears in, or *None* if not present."""
    for horizon, entries in roadmap.items():
        for entry in entries:
            if entry.identity.type == item_type and entry.identity.ref == ref:
                return horizon
    return None


# ---------------------------------------------------------------------------
# Initiative state resolution
# ---------------------------------------------------------------------------


def _read_initiative_state(
    initiative_dir: Path,
    slug: str,
    store: Any | None = None,
) -> str | None:
    """Read the initiative/epic state from durable artifacts or store.

    When a *store* is provided we query the epic's ``state`` field
    (``shaping``, ``sprinting``, ``planned``, ``paused``, ``archived``).
    Otherwise we fall back to durable filesystem markers inside the
    initiative directory.
    """
    # Try the store first — it is the authoritative source for epic state.
    if store is not None:
        try:
            epic = _load_epic_from_store(store, slug)
            if epic is not None:
                state = getattr(epic, "state", None)
                if isinstance(state, str) and state:
                    return state
        except Exception:
            # Store lookup is best-effort; fall back to filesystem.
            pass

    # Fall back to filesystem markers.
    # Check for an explicit COMPLETED or ARCHIVED marker file.
    for marker_name in ("COMPLETED.md", "ARCHIVED.md", "COMPLETED", "ARCHIVED"):
        marker = initiative_dir / marker_name
        if marker.exists():
            return "archived"

    # Check chain.yaml for an archived state marker.
    chain_yaml = initiative_dir / "chain.yaml"
    if chain_yaml.is_file():
        try:
            import yaml

            chain = yaml.safe_load(chain_yaml.read_text(encoding="utf-8"))
            if isinstance(chain, Mapping):
                state = chain.get("state")
                if isinstance(state, str) and state:
                    return state
        except Exception:
            pass

    return None


def _load_epic_from_store(store: Any, slug: str) -> Any | None:
    """Try to load an epic by ID from *store*, returning *None* on failure."""
    try:
        return store.load_epic(slug)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_readme_title(readme_path: Path) -> str | None:
    """Extract the title from an initiative README.md.

    The title is the first ``# Title`` heading in the file.
    Returns *None* if the file cannot be read or has no title.
    """
    try:
        lines = readme_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            if title:
                return title
    return None


def _copy_roadmap(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]],
) -> dict[RoadmapHorizon, list[RoadmapEntry]]:
    """Shallow-copy the roadmap dict (entries themselves are frozen, so safe)."""
    return {horizon: list(entries) for horizon, entries in roadmap.items()}
