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

Resolved references produce diagnostics:

* **Hard error** — the referenced artifact does not exist.
* **Warning** — the artifact exists but its current title differs from the
  display title in the strategy Markdown (stale title).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

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


def resolve_strategy(
    document: StrategyDocument,
    repo_root: str | Path,
) -> StrategyDocument:
    """Resolve every roadmap entry reference against the repository.

    Parameters
    ----------
    document:
        A parsed :class:`StrategyDocument` (with or without prior diagnostics).
    repo_root:
        The repository root path.  ``.megaplan/tickets/`` and
        ``.megaplan/initiatives/`` are resolved relative to this root.

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
    ticket_titles: dict[str, str] = {}
    try:
        for _fpath, fm in iterate_ticket_files(repo_root):
            tid = fm.get("id")
            title = fm.get("title")
            if tid and title:
                ticket_titles[tid] = title
    except Exception:
        # Malformed ticket files should not crash the resolver.
        # Diagnostics for missing refs will be emitted downstream.
        pass

    # ---- build initiative index ---------------------------------------------
    initiative_titles: dict[str, str] = {}
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

    # ---- resolve each entry -------------------------------------------------
    for horizon_entries in document.roadmap.values():
        for entry in horizon_entries:
            identity = entry.identity
            if identity.type == "ticket":
                _resolve_ticket_entry(
                    entry, ticket_titles, diagnostics
                )
            elif identity.type == "epic":
                _resolve_epic_entry(
                    entry, initiative_titles, repo_root, diagnostics
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


# ---------------------------------------------------------------------------
# Epic (initiative) resolution
# ---------------------------------------------------------------------------


def _resolve_epic_entry(
    entry: RoadmapEntry,
    initiative_titles: dict[str, str],
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
