"""Ticket promotion orchestration.

Promotes a ticket into a canonical epic backed by an initiative folder.
The ticket is **retained** (never deleted); its ULID is never reused as
the epic ID.  The epic ID is the **initiative slug** — the canonical
identifier for the promoted work (North Star identity rule).

Promotion coordinates five concerns:

1. **Load and retain the source ticket** — the ticket file is read but
   never deleted or modified in its identity fields.
2. **Initiative resolution** — reuse an existing initiative folder whose
   slug exactly matches the candidate derived from the ticket title, or
   create a canonical initiative folder.  A strong fuzzy match with a
   *different* slug is a precise conflict.
3. **Epic creation/reuse** — create a store epic whose ``id`` is the
   initiative slug (never the ticket ULID), or reuse an existing one.
4. **Relationship provenance** — link the ticket to the epic with
   ``kind='promoted_to_epic'`` and a ``provenance`` traceability string.
   ``resolves_on_complete`` is set only for resolving promotion semantics.
5. **Strategy roadmap** — when a ``.megaplan/STRATEGY.md`` exists, the
   ticket's roadmap entry is replaced by an epic entry in the same horizon
   via the pure mutation helpers.  Non-roadmap tickets are not forced into
   the strategy.

Retries are idempotent for the same ticket + initiative, or fail with a
named conflict when the ticket is already promoted to a different epic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.layout import (
    STRATEGY_PATH,
    initiative_root,
    search_initiatives,
    slugify_initiative,
    strategy_file_path,
)
from arnold_pipelines.megaplan.schemas import Epic, TicketEpicLink
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.store.base import Store
from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapHorizon,
    StrategyDiagnostic,
)
from arnold_pipelines.megaplan.strategy.mutations import promote_ticket_to_epic
from arnold_pipelines.megaplan.tickets.files import (
    iterate_ticket_files,
    write_ticket_file,
)
from arnold_pipelines.megaplan.tickets.relationships import (
    KIND_PROMOTED_TO_EPIC,
    parse_frontmatter_links,
    serialize_links_to_frontmatter,
)

# Lazy imports to avoid potential circular-import issues at module load.
# ``core`` imports from ``relationships`` and ``files`` lazily already.


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROVENANCE_PROMOTION: str = "promotion"
"""Provenance tag for links created by the promotion orchestrator."""

_FUZZY_MATCH_THRESHOLD: float = 0.85
"""Above this score, a fuzzy initiative match with a *different* slug is a conflict."""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PromotionConflictError(Exception):
    """Raised when promotion cannot proceed due to a precise, named conflict.

    Attributes
    ----------
    conflict_type:
        A short machine-readable identifier for the conflict kind
        (``"fuzzy_initiative_match"`` or ``"already_promoted_to_different_epic"``).
    details:
        Additional structured context about the conflict.
    """

    def __init__(
        self,
        message: str,
        *,
        conflict_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.conflict_type = conflict_type
        self.details = details or {}


class TicketNotFoundError(LookupError):
    """Raised when the source ticket cannot be located in files or store."""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class PromotionResult:
    """Structured outcome of a ticket promotion."""

    ticket_id: str
    initiative_slug: str
    epic: Epic
    link: TicketEpicLink | None = None
    strategy_updated: bool = False
    strategy_diagnostics: list[StrategyDiagnostic] = field(default_factory=list)
    initiative_created: bool = False
    epic_created: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_ticket_file(
    repo_root: str,
    ticket_id: str,
) -> tuple[Path | None, dict[str, Any] | None]:
    """Return ``(path, frontmatter)`` for *ticket_id*, or ``(None, None)``."""
    for fpath, fm in iterate_ticket_files(repo_root):
        if fm.get("id") == ticket_id:
            return fpath, fm
    return None, None


def _provenance_string(ticket_id: str) -> str:
    """Return a deterministic provenance string for a promotion link."""
    return f"{PROVENANCE_PROMOTION}:{ticket_id}"


def _ensure_store(
    store: Store | None,
    repo_root: str,
) -> Store:
    """Return *store* or create a local :class:`FileStore` for local-only mode."""
    if store is not None:
        return store
    from arnold_pipelines.megaplan.store.file import FileStore

    return FileStore(
        root=Path(repo_root) / ".megaplan" / "store",
        repo_root=repo_root,
    )


def _gather_existing_links(
    found_fm: dict[str, Any] | None,
    ticket_id: str,
    store: Store | None,
) -> list[TicketEpicLink]:
    """Collect existing ticket-epic links from file frontmatter and store."""
    links: list[TicketEpicLink] = []
    if found_fm is not None:
        links.extend(parse_frontmatter_links(found_fm, ticket_id))
    # Avoid double-counting for FileStore (which reads from the same file).
    from arnold_pipelines.megaplan.store.file import FileStore as _FileStore

    if store is not None and not isinstance(store, _FileStore):
        from arnold_pipelines.megaplan.tickets.core import is_cloud_store

        if is_cloud_store(store):
            try:
                links.extend(store.list_ticket_epic_links(ticket_id=ticket_id))
            except Exception:
                pass
    return links


def _check_conflicts(
    links: list[TicketEpicLink],
    ticket_id: str,
    initiative_slug: str,
) -> None:
    """Raise :class:`PromotionConflictError` if the ticket is already promoted elsewhere."""
    for link in links:
        if link.kind == KIND_PROMOTED_TO_EPIC and link.epic_id != initiative_slug:
            raise PromotionConflictError(
                f"Ticket '{ticket_id}' is already promoted to epic "
                f"'{link.epic_id}'.  Cannot promote to '{initiative_slug}'.  "
                f"Unlink the existing promotion first or reuse that epic.",
                conflict_type="already_promoted_to_different_epic",
                details={
                    "ticket_id": ticket_id,
                    "existing_epic_id": link.epic_id,
                    "target_epic_id": initiative_slug,
                },
            )


def _find_matching_link(
    links: list[TicketEpicLink],
    epic_id: str,
    resolves_on_complete: bool,
) -> TicketEpicLink | None:
    """Return an existing ``promoted_to_epic`` link to *epic_id* with matching resolves flag."""
    for link in links:
        if (
            link.epic_id == epic_id
            and link.kind == KIND_PROMOTED_TO_EPIC
            and link.resolves_on_complete == resolves_on_complete
        ):
            return link
    return None


def _write_link_to_file(
    found_path: Path,
    found_fm: dict[str, Any],
    ticket_id: str,
    epic_id: str,
    resolves_on_complete: bool,
) -> TicketEpicLink:
    """Write a ``promoted_to_epic`` link to the ticket frontmatter file."""
    links = parse_frontmatter_links(found_fm, ticket_id)
    # Remove existing entry for this epic (idempotent re-link / upgrade).
    links = [link for link in links if link.epic_id != epic_id]
    new_link = TicketEpicLink(
        ticket_id=ticket_id,
        epic_id=epic_id,
        resolves_on_complete=resolves_on_complete,
        kind=KIND_PROMOTED_TO_EPIC,
        provenance=_provenance_string(ticket_id),
        linked_at=utc_now(),
    )
    links.append(new_link)
    found_fm["epics"] = serialize_links_to_frontmatter(links)
    found_fm["last_edited_at"] = utc_now()
    write_ticket_file(found_path, found_fm)
    return new_link


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def promote_ticket(
    ticket_id: str,
    *,
    initiative_slug: str | None = None,
    epic_title: str | None = None,
    epic_goal: str | None = None,
    epic_body: str | None = None,
    resolves_on_complete: bool = True,
    horizon: RoadmapHorizon | None = None,
    home_backend: str = "file",
    store: Store | None = None,
    cwd: Path | None = None,
    idempotency_key: str | None = None,
    skip_strategy: bool = False,
) -> PromotionResult:
    """Promote *ticket_id* into a canonical epic backed by an initiative.

    The ticket is retained — never deleted.  The epic ID is the initiative
    slug, never the ticket ULID.  A ``promoted_to_epic`` relationship link
    is recorded with deterministic provenance.  When a strategy document
    exists, the ticket's roadmap entry is replaced by an epic entry in the
    same horizon.

    Parameters
    ----------
    ticket_id:
        The ULID of the source ticket.
    initiative_slug:
        Explicit initiative slug to use as the epic ID.  When *None*
        (default), the slug is derived from the ticket title via
        :func:`slugify_initiative`.
    epic_title:
        Override for the epic title.  Defaults to the ticket title.
    epic_goal:
        Override for the epic goal.  Defaults to the ticket title.
    epic_body:
        Override for the epic body.  Defaults to the ticket body.
    resolves_on_complete:
        When *True* (default), completing the epic auto-addresses the
        ticket.  Set to *False* for a non-resolving promotion.
    horizon:
        Explicit roadmap horizon for the strategy entry.  When *None*
        (default), the ticket's current horizon is inherited, or ``"Next"``
        if the ticket is not on the roadmap.
    home_backend:
        The ``home_backend`` for the created epic (default ``"file"``).
    store:
        Optional store for epic persistence.  When *None*, a local
        :class:`FileStore` is created under ``.megaplan/store``.
    cwd:
        Repository root.  Defaults to the current working directory.
    idempotency_key:
        Idempotency key for the ``create_epic`` call.  Defaults to
        ``"promote:{ticket_id}:{slug}"``.
    skip_strategy:
        When *True*, skip the strategy roadmap update entirely.

    Returns
    -------
    PromotionResult
        Structured outcome including the epic, link, and strategy diagnostics.

    Raises
    ------
    TicketNotFoundError
        If the ticket cannot be found in files or the store.
    PromotionConflictError
        If the ticket is already promoted to a different epic, or if a
        strong fuzzy initiative match exists under a different slug.
    """
    repo_root = str(cwd) if cwd else os.getcwd()

    # ---- 1. Load and retain the source ticket -------------------------------
    found_path, found_fm = _find_ticket_file(repo_root, ticket_id)

    ticket_title: str | None = None
    ticket_body: str = ""

    if found_fm is not None:
        ticket_title = str(found_fm.get("title") or "")
        ticket_body = str(found_fm.get("__body__") or "")
    else:
        # Fall back to the store if the ticket is not in the file system.
        resolved_store = store if store is not None else None
        if resolved_store is not None:
            try:
                ticket = resolved_store.load_ticket(ticket_id)
            except Exception:
                ticket = None
            if ticket is not None:
                ticket_title = ticket.title
                ticket_body = ticket.body

    if not ticket_title:
        raise TicketNotFoundError(
            f"Ticket '{ticket_id}' not found in files under '{repo_root}'"
            f"{' or in the store' if store is not None else ''}."
        )

    # ---- 2. Determine the initiative slug -----------------------------------
    slug = initiative_slug or slugify_initiative(ticket_title)

    # ---- 3. Resolve initiative (reuse or create) ----------------------------
    initiative_created = False
    init_root = initiative_root(repo_root, slug)
    if not init_root.exists():
        # Search for genuinely matching initiatives under a different slug.
        matches = search_initiatives(repo_root, ticket_title)
        for match in matches:
            if match.get("slug") != slug and match.get("match_score", 0) >= _FUZZY_MATCH_THRESHOLD:
                raise PromotionConflictError(
                    f"Initiative '{match['slug']}' (title: {match.get('title') or '?'}) "
                    f"already exists with a strong match (score: "
                    f"{match.get('match_score', 0):.2f}) for ticket '{ticket_id}'. "
                    f"Pass initiative_slug='{match['slug']}' to reuse it, or remove "
                    f"the existing initiative if it is unrelated.",
                    conflict_type="fuzzy_initiative_match",
                    details={
                        "ticket_id": ticket_id,
                        "existing_slug": match.get("slug"),
                        "candidate_slug": slug,
                        "match_score": match.get("match_score"),
                    },
                )
        # Create canonical initiative folder with a README.
        init_root.mkdir(parents=True, exist_ok=True)
        readme = init_root / "README.md"
        readme.write_text(
            f"# {ticket_title}\n\nPromoted from ticket {ticket_id}.\n",
            encoding="utf-8",
        )
        initiative_created = True

    # ---- 4. Create/reuse store epic (ID = initiative slug) ------------------
    store = _ensure_store(store, repo_root)
    epic_created = False
    epic = store.load_epic(slug)
    if epic is None:
        _title = epic_title or ticket_title
        _goal = epic_goal or ticket_title
        _body = epic_body if epic_body is not None else ticket_body
        _idem = idempotency_key or f"promote:{ticket_id}:{slug}"
        epic = store.create_epic(
            title=_title,
            goal=_goal,
            body=_body,
            state="shaping",
            home_backend=home_backend,
            epic_id=slug,
            idempotency_key=_idem,
        )
        epic_created = True

    # ---- 5. Record promoted_to_epic provenance ------------------------------
    existing_links = _gather_existing_links(found_fm, ticket_id, store)
    _check_conflicts(existing_links, ticket_id, slug)

    # Idempotency: skip re-link if a matching promoted_to_epic link exists.
    link_record = _find_matching_link(existing_links, slug, resolves_on_complete)

    if link_record is None:
        # Write the link to the file frontmatter (if the ticket file exists).
        if found_path is not None and found_fm is not None:
            link_record = _write_link_to_file(
                found_path,
                found_fm,
                ticket_id,
                slug,
                resolves_on_complete,
            )

        # Write the link to the store (for cloud-backed stores).
        from arnold_pipelines.megaplan.tickets.core import is_cloud_store

        if is_cloud_store(store):
            store.link_ticket_to_epic(
                ticket_id=ticket_id,
                epic_id=slug,
                resolves_on_complete=resolves_on_complete,
                kind=KIND_PROMOTED_TO_EPIC,
                provenance=_provenance_string(ticket_id),
            )
            # Read back the store link if we don't have one from the file.
            if link_record is None:
                store_links = store.list_ticket_epic_links(
                    ticket_id=ticket_id,
                    epic_id=slug,
                )
                if store_links:
                    link_record = store_links[0]

    # ---- 6. Update strategy roadmap -----------------------------------------
    strategy_updated = False
    strategy_diagnostics: list[StrategyDiagnostic] = []

    if not skip_strategy:
        strat_path = strategy_file_path(repo_root)
        if strat_path.exists():
            from arnold_pipelines.megaplan.strategy import (
                parse_strategy,
                serialize_strategy,
            )

            content = strat_path.read_text(encoding="utf-8")
            document = parse_strategy(content, str(STRATEGY_PATH))
            epic_display = epic_title or epic.title or ticket_title
            updated_doc = promote_ticket_to_epic(
                document,
                ticket_ref=ticket_id,
                epic_ref=slug,
                epic_display_title=epic_display,
                horizon=horizon,
            )
            serialized = serialize_strategy(updated_doc)
            strat_path.write_text(serialized, encoding="utf-8")
            strategy_updated = True
            strategy_diagnostics = list(updated_doc.diagnostics)

    # ---- 7. Return result ---------------------------------------------------
    return PromotionResult(
        ticket_id=ticket_id,
        initiative_slug=slug,
        epic=epic,
        link=link_record,
        strategy_updated=strategy_updated,
        strategy_diagnostics=strategy_diagnostics,
        initiative_created=initiative_created,
        epic_created=epic_created,
    )
