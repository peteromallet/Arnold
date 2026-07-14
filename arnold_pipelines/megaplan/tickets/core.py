"""Core ticket operations — mode-aware dispatch.

Local-only mode: writes/reads ``.megaplan/tickets/*.md`` files only.
Store-configured mode: writes files **and** mirrors through the
:class:`~megaplan.store.base.Store` ticket protocol.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ulid import ULID

from arnold_pipelines.megaplan.schemas import Ticket, TicketEpicLink
from arnold_pipelines.megaplan.store import Store

from .files import (
    _FRONTMATTER_FIELDS,
    iterate_ticket_files,
    read_ticket_file,
    slugify,
    ticket_file_path,
    tickets_dir,
    write_ticket_file,
)
from .identity import repo_codebase_identity, repo_owner_name, repo_root_sha


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------


def is_cloud_store(store: Store) -> bool:
    """Return *True* when *store* supports facade-backed ticket operations.

    This is the **single canonical predicate** used by every operation to
    decide whether to hit a Store backend in addition to the file system.
    """
    from arnold_pipelines.megaplan.store.db import DBStore  # lazy to avoid import cycles
    from arnold_pipelines.megaplan.store.file import FileStore
    from arnold_pipelines.megaplan.store.multi import MultiStore

    return isinstance(store, DBStore | FileStore | MultiStore)


# ---------------------------------------------------------------------------
# Store resolution
# ---------------------------------------------------------------------------


def _resolve_store() -> Store | None:
    """Return the currently configured store, or *None* for local-only.

    Reuses megaplan's existing ``build_store`` convention: checks
    ``MEGAPLAN_BACKEND`` env and ``--backend`` CLI args by inspecting
    the CLI context if available, otherwise falls back to env.
    """
    backend = os.environ.get("MEGAPLAN_BACKEND")
    if backend == "db":
        from arnold_pipelines.megaplan.store import DBStore, require_actor_id, resolve_actor_id

        actor_id = require_actor_id(resolve_actor_id(None))
        return DBStore(actor_id=actor_id)
    return None


# ---------------------------------------------------------------------------
# Source derivation
# ---------------------------------------------------------------------------


def _derive_source() -> tuple[str, str | None, str | None]:
    """Return ``(source, filed_in_turn_id, filed_by_actor_id)``.

    - ``MEGAPLAN_TURN_ID`` set  → ``source = 'agent'``, ``filed_in_turn_id`` populated.
    - Unset                     → ``source = 'human'``.
    - ``MEGAPLAN_ACTOR_ID``     → ``filed_by_actor_id`` populated.
    """
    turn_id = os.environ.get("MEGAPLAN_TURN_ID")
    actor_id = os.environ.get("MEGAPLAN_ACTOR_ID")
    if turn_id:
        return ("agent", turn_id, actor_id or None)
    return ("human", None, actor_id or None)


# ---------------------------------------------------------------------------
# Codebase identity resolution
# ---------------------------------------------------------------------------


def _resolve_codebase_id(store: Store | None, cwd: Path | None = None) -> str | None:
    """Determine the codebase identity from the current working directory.

    Returns a ``codebase_id`` string, or *None* if we're in local-only mode
    and identity doesn't matter for file-only storage.
    """
    if store is None or not is_cloud_store(store):
        return None  # local-only: no codebase_id needed
    try:
        sha = repo_root_sha(cwd)
    except Exception:
        sha = None

    if sha:
        existing = store.resolve_codebase_by_root_sha(sha)
        if existing:
            return existing.id
    return None


def _ensure_codebase(
    store: Store,
    cwd: Path | None = None,
) -> str:
    """Ensure a ``codebases`` row exists for the current repo and return its id.

    Auto-registers if needed (with ``root_commit_sha`` populated).
    Only meaningful in cloud mode; raises in local-only.
    """
    assert is_cloud_store(store)
    identity = repo_codebase_identity(cwd)
    existing = store.resolve_codebase_by_root_sha(identity.root_commit_sha)
    if existing:
        return existing.id

    cb = store.upsert_codebase(
        owner=identity.owner,
        name=identity.name,
        default_branch=identity.default_branch,
        root_commit_sha=identity.root_commit_sha,
    )
    return cb.id


# ---------------------------------------------------------------------------
# Public API — create
# ---------------------------------------------------------------------------


def new(
    title: str,
    *,
    body: str = "",
    tags: Sequence[str] | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> str:
    """Create a new ticket and return its ULID.

    Parameters
    ----------
    title:
        Ticket title (required).
    body:
        Markdown body.  ``"-"`` means read from stdin (empty input is rejected).
    tags:
        Optional tags.
    store:
        Explicit store.  If *None*, resolved from environment.
    cwd:
        Working directory for git operations.

    Returns
    -------
    str
        The ULID of the newly created ticket (printed to stdout).
    """
    # Handle stdin body
    if body == "-":
        body = sys.stdin.read()
        if not body.strip():
            raise ValueError("stdin body is empty — body is required")

    if store is None:
        store = _resolve_store()

    source, turn_id, actor_id = _derive_source()
    ticket_id = str(ULID())
    slug = slugify(title)
    now = datetime.now(timezone.utc)

    # Determine codebase_id (cloud mode only)
    codebase_id: str | None
    if store is not None and is_cloud_store(store):
        codebase_id = _ensure_codebase(store, cwd)
    else:
        codebase_id = None

    # Build record dict for file
    record: dict[str, Any] = {
        "id": ticket_id,
        "title": title,
        "status": "open",
        "source": source,
        "tags": list(tags or []),
        "filed_by_actor_id": actor_id,
        "filed_in_turn_id": turn_id,
        "codebase_id": codebase_id,
        "created_at": now,
        "last_edited_at": now,
        "resolution_note": None,
        "addressed_at": None,
        "epics": [],
        "__body__": body,
    }

    # Write file (both modes)
    if cwd:
        repo_root = str(cwd)
    else:
        repo_root = os.getcwd()
    fpath = ticket_file_path(repo_root, ticket_id, slug)
    write_ticket_file(fpath, record)

    # Store-backed facade: write Store row
    if store is not None and is_cloud_store(store) and codebase_id:
        store.create_ticket(
            codebase_id=codebase_id,
            title=title,
            body=body,
            source=source,
            tags=list(tags or []),
            filed_by_actor_id=actor_id,
            filed_in_turn_id=turn_id,
            slug=slug,
            ticket_id=ticket_id,
        )

    # Print only the ULID to stdout (per spec)
    print(ticket_id, flush=True)
    return ticket_id


# ---------------------------------------------------------------------------
# Public API — list
# ---------------------------------------------------------------------------


def list_tickets(
    *,
    status: str | None = None,
    tags: Sequence[str] | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
    json_output: bool = False,
) -> list[dict[str, Any]]:
    """List tickets, optionally filtered.

    In local-only mode reads from ``.megaplan/tickets/*.md``.
    In store-backed facade mode queries the Store.
    """
    if store is None:
        store = _resolve_store()

    results: list[dict[str, Any]] = []

    if store is not None and is_cloud_store(store):
        codebase_id = _resolve_codebase_id(store, cwd)
        tickets = store.list_tickets(
            codebase_id=codebase_id,
            status=status,
            tags=tags,
        )
        for t in tickets:
            d = {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "source": t.source,
                "tags": t.tags,
                "slug": t.slug,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "last_edited_at": t.last_edited_at.isoformat() if t.last_edited_at else None,
                "resolution_note": t.resolution_note,
            }
            # Enrich with file body if available
            if cwd:
                fpath = ticket_file_path(cwd, t.id, t.slug)
                fm = read_ticket_file(fpath)
                if fm:
                    d["body"] = fm.get("__body__", "")
            results.append(d)
    else:
        repo_root = str(cwd) if cwd else os.getcwd()
        for fpath, fm in iterate_ticket_files(repo_root):
            if status and fm.get("status") != status:
                continue
            if tags:
                file_tags = set(fm.get("tags") or [])
                if not file_tags.intersection(tags):
                    continue
            from .relationships import parse_frontmatter_links, serialize_links_to_frontmatter

            ticket_id = fm.get("id")
            epics_normalized: list[dict[str, Any]] = []
            if isinstance(ticket_id, str) and ticket_id:
                links = parse_frontmatter_links(fm, ticket_id)
                epics_normalized = serialize_links_to_frontmatter(links)
            d: dict[str, Any] = {
                "id": ticket_id,
                "title": fm.get("title"),
                "status": fm.get("status"),
                "source": fm.get("source"),
                "tags": fm.get("tags", []),
                "slug": slugify(fm.get("title", "")),
                "created_at": _iso(fm.get("created_at")),
                "last_edited_at": _iso(fm.get("last_edited_at")),
                "resolution_note": fm.get("resolution_note"),
                "body": fm.get("__body__", ""),
                "epics": epics_normalized,
            }
            results.append(d)

    if json_output:
        import json

        print(json.dumps(results, indent=2, default=str))
    return results


# ---------------------------------------------------------------------------
# Public API — search (cross-project, multi-keyword, sortable)
# ---------------------------------------------------------------------------


_SORT_KEYS = {"created", "edited", "length", "title"}


def search(
    keywords: Sequence[str] | None = None,
    *,
    keywords_all: bool = False,
    status: str | None = None,
    tags: Sequence[str] | None = None,
    projects: Sequence[str | Path] | None = None,
    all_projects: bool = False,
    sort: str = "created",
    order: str = "desc",
    limit: int | None = None,
    snippet: bool = False,
    snippet_width: int = 120,
    store: Store | None = None,
    cwd: Path | None = None,
) -> list[dict[str, Any]]:
    """Search tickets across local files and/or the cloud DB.

    Scope resolution
    ----------------
    * ``projects`` given → restrict to those repos (path or known-name).
    * ``all_projects`` → every known repo (local) or every codebase (cloud).
    * neither → current repo only (default).

    Keyword matching is case-insensitive substring across title + body +
    tags + resolution_note.  Default is OR (any keyword matches); set
    ``keywords_all=True`` for AND semantics.

    Returns a list of result dicts.  Each result includes a ``project``
    field (path string or ``owner/name``) when results span multiple
    projects, plus a ``snippet`` field when *snippet* is true and at
    least one keyword matched.
    """
    if sort not in _SORT_KEYS:
        raise ValueError(f"sort must be one of {_SORT_KEYS!r}, got {sort!r}")
    if order.lower() not in {"asc", "desc"}:
        raise ValueError(f"order must be 'asc' or 'desc', got {order!r}")

    if store is None:
        store = _resolve_store()

    kw_list = [k for k in (keywords or []) if k]

    results: list[dict[str, Any]] = []

    if store is not None and is_cloud_store(store):
        codebase_ids: list[str] | None = None
        # Map projects → codebase_ids
        if projects:
            ids: list[str] = []
            for p in projects:
                resolved = _resolve_project_to_codebase(store, p)
                if resolved:
                    ids.append(resolved)
            codebase_ids = ids or [""]  # empty → guaranteed no rows
        elif not all_projects:
            cur_id = _resolve_codebase_id(store, cwd)
            if cur_id:
                codebase_ids = [cur_id]
            # else: leave as None (matches none) — but keep behaviour where
            # missing codebase falls through to "nothing" rather than "all".
            else:
                codebase_ids = [""]

        tickets = store.list_tickets(
            codebase_ids=codebase_ids,
            status=status,
            tags=tags,
            keywords=kw_list or None,
            keywords_all=keywords_all,
            sort=sort,
            order=order,
            limit=limit,
        )
        # Pre-load codebases for project labelling
        cb_cache: dict[str, str] = {}
        for t in tickets:
            project_label = ""
            if t.codebase_id:
                if t.codebase_id not in cb_cache:
                    cb = store.load_codebase(t.codebase_id)
                    cb_cache[t.codebase_id] = (
                        f"{cb.owner}/{cb.name}" if cb and cb.owner and cb.name else t.codebase_id
                    )
                project_label = cb_cache[t.codebase_id]
            d = {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "source": t.source,
                "tags": t.tags,
                "slug": t.slug,
                "codebase_id": t.codebase_id,
                "project": project_label,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "last_edited_at": t.last_edited_at.isoformat() if t.last_edited_at else None,
                "resolution_note": t.resolution_note,
                "body": t.body or "",
            }
            if snippet and kw_list:
                d["snippet"] = _make_snippet(t.body or "", t.title or "", kw_list, snippet_width)
            results.append(d)
        return results

    # ----- local-only mode -----
    scan_roots = _resolve_scan_roots(projects=projects, all_projects=all_projects, cwd=cwd)

    for repo_root in scan_roots:
        project_label = _project_label_for(repo_root)
        for fpath, fm in iterate_ticket_files(repo_root):
            if status and fm.get("status") != status:
                continue
            if tags:
                file_tags = set(fm.get("tags") or [])
                if not file_tags.intersection(tags):
                    continue
            title = fm.get("title") or ""
            body = fm.get("__body__") or ""
            tag_blob = " ".join(fm.get("tags") or [])
            res_note = fm.get("resolution_note") or ""
            if kw_list:
                haystack = (title + "\n" + body + "\n" + tag_blob + "\n" + res_note).lower()
                matches = [kw.lower() in haystack for kw in kw_list]
                if keywords_all:
                    if not all(matches):
                        continue
                else:
                    if not any(matches):
                        continue
            d = {
                "id": fm.get("id"),
                "title": title,
                "status": fm.get("status"),
                "source": fm.get("source"),
                "tags": fm.get("tags", []),
                "slug": slugify(title),
                "codebase_id": fm.get("codebase_id"),
                "project": project_label,
                "created_at": _iso(fm.get("created_at")),
                "last_edited_at": _iso(fm.get("last_edited_at")),
                "resolution_note": fm.get("resolution_note"),
                "body": body,
                "epics": fm.get("epics", []),
            }
            if snippet and kw_list:
                d["snippet"] = _make_snippet(body, title, kw_list, snippet_width)
            results.append(d)

    # In-process sort for local mode (matches DB ORDER BY semantics)
    sort_key = {
        "created": lambda d: d.get("created_at") or "",
        "edited": lambda d: d.get("last_edited_at") or "",
        "length": lambda d: len(d.get("body") or ""),
        "title": lambda d: (d.get("title") or "").lower(),
    }[sort]
    results.sort(key=sort_key, reverse=(order.lower() == "desc"))
    if limit is not None:
        results = results[:limit]
    return results


def _resolve_project_to_codebase(store: Store, project: str | Path) -> str | None:
    """Resolve a project spec to a codebase_id (cloud).

    Accepts: an ``owner/name`` string, a bare ``name`` (must be unique),
    or a filesystem path (uses git root_commit_sha lookup).
    """
    spec = str(project)
    # Path-like first
    p = Path(spec).expanduser()
    if p.is_dir():
        try:
            sha = repo_root_sha(p)
        except Exception:
            sha = None
        if sha:
            cb = store.resolve_codebase_by_root_sha(sha)
            if cb:
                return cb.id
    # owner/name
    if "/" in spec:
        owner, name = spec.split("/", 1)
        cb = store.find_codebase(owner, name)
        if cb:
            return cb.id
    # bare name — scan list_codebases
    matches = [c for c in store.list_codebases() if (c.name or "").lower() == spec.lower()]
    if len(matches) == 1:
        return matches[0].id
    return None


def _resolve_scan_roots(
    *,
    projects: Sequence[str | Path] | None,
    all_projects: bool,
    cwd: Path | None,
) -> list[Path]:
    """Determine which repo roots to walk for local-mode search."""
    from .registry import list_repos, resolve_project

    if projects:
        out: list[Path] = []
        for p in projects:
            resolved = resolve_project(str(p))
            if resolved and (resolved / ".megaplan" / "tickets").is_dir():
                out.append(resolved)
        return out
    if all_projects:
        return [
            Path(r["path"])
            for r in list_repos()
            if (Path(r["path"]) / ".megaplan" / "tickets").is_dir()
        ]
    here = Path(cwd) if cwd else Path(os.getcwd())
    return [here]


def _project_label_for(repo_root: Path) -> str:
    """Best-effort label: ``owner/name`` from remote, else basename of path."""
    try:
        owner, name = repo_owner_name(repo_root)
    except Exception:
        owner, name = None, None
    if owner and name:
        return f"{owner}/{name}"
    return repo_root.name


def _make_snippet(body: str, title: str, keywords: Sequence[str], width: int) -> str:
    """Return a single-line snippet centred on the first keyword hit."""
    text = (title + " — " + body) if body else title
    flat = " ".join(text.split())  # collapse whitespace
    low = flat.lower()
    idx = -1
    for kw in keywords:
        i = low.find(kw.lower())
        if i >= 0 and (idx < 0 or i < idx):
            idx = i
    if idx < 0:
        return flat[: width] + ("…" if len(flat) > width else "")
    half = width // 2
    start = max(0, idx - half)
    end = min(len(flat), start + width)
    snippet = flat[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(flat):
        snippet = snippet + "…"
    return snippet


def show(
    ticket_id: str,
    *,
    store: Store | None = None,
    cwd: Path | None = None,
    json_output: bool = False,
) -> dict[str, Any] | None:
    """Show a single ticket by id."""
    if store is None:
        store = _resolve_store()

    if store is not None and is_cloud_store(store):
        t = store.load_ticket(ticket_id)
        if t is None:
            return None
        result: dict[str, Any] = {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "source": t.source,
            "tags": t.tags,
            "slug": t.slug,
            "codebase_id": t.codebase_id,
            "filed_by_actor_id": t.filed_by_actor_id,
            "filed_in_turn_id": t.filed_in_turn_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "last_edited_at": t.last_edited_at.isoformat() if t.last_edited_at else None,
            "resolution_note": t.resolution_note,
            "addressed_at": t.addressed_at.isoformat() if t.addressed_at else None,
        }
        # Enrich body from file and normalise epics
        if cwd:
            fpath = ticket_file_path(cwd, t.id, t.slug)
            fm = read_ticket_file(fpath)
            if fm:
                result["body"] = fm.get("__body__", "")
                result["epics"] = _normalize_epics_output(fm, t.id)
        if json_output:
            import json

            print(json.dumps(result, indent=2, default=str))
        return result
    else:
        repo_root = str(cwd) if cwd else os.getcwd()
        for fpath, fm in iterate_ticket_files(repo_root):
            if fm.get("id") == ticket_id:
                result = {
                    "id": fm.get("id"),
                    "title": fm.get("title"),
                    "status": fm.get("status"),
                    "source": fm.get("source"),
                    "tags": fm.get("tags", []),
                    "slug": slugify(fm.get("title", "")),
                    "codebase_id": fm.get("codebase_id"),
                    "filed_by_actor_id": fm.get("filed_by_actor_id"),
                    "filed_in_turn_id": fm.get("filed_in_turn_id"),
                    "created_at": _iso(fm.get("created_at")),
                    "last_edited_at": _iso(fm.get("last_edited_at")),
                    "resolution_note": fm.get("resolution_note"),
                    "addressed_at": _iso(fm.get("addressed_at")),
                    "body": fm.get("__body__", ""),
                    "epics": _normalize_epics_output(fm, ticket_id),
                }
                if json_output:
                    import json

                    print(json.dumps(result, indent=2, default=str))
                return result
        return None


# ---------------------------------------------------------------------------
# Public API — edit
# ---------------------------------------------------------------------------


def edit(
    ticket_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    status: str | None = None,
    add_tag: str | None = None,
    remove_tag: str | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Edit a ticket's fields.  Frontmatter always updated; DB updated in cloud mode."""
    if store is None:
        store = _resolve_store()

    repo_root = str(cwd) if cwd else os.getcwd()

    # Find the file
    found_path: Path | None = None
    found_fm: dict | None = None
    for fpath, fm in iterate_ticket_files(repo_root):
        if fm.get("id") == ticket_id:
            found_path = fpath
            found_fm = fm
            break

    if found_fm is None:
        return None

    # Apply changes
    if title is not None:
        found_fm["title"] = title
        # Update slug in the filename
        new_slug = slugify(title)
        if new_slug != found_fm.get("slug", slugify(found_fm.get("title", ""))):
            found_fm["slug"] = new_slug
            new_fpath = ticket_file_path(repo_root, ticket_id, new_slug)
            if found_path:
                found_path.rename(new_fpath)
                found_path = new_fpath

    if body is not None:
        found_fm["__body__"] = body

    if status is not None:
        found_fm["status"] = status

    if add_tag is not None:
        tags = list(found_fm.get("tags") or [])
        if add_tag not in tags:
            tags.append(add_tag)
            found_fm["tags"] = tags

    if remove_tag is not None:
        tags = list(found_fm.get("tags") or [])
        if remove_tag in tags:
            tags.remove(remove_tag)
            found_fm["tags"] = tags

    found_fm["last_edited_at"] = datetime.now(timezone.utc)

    # Write file
    if found_path:
        write_ticket_file(found_path, found_fm)

    # Store-backed facade: update Store row
    if store is not None and is_cloud_store(store):
        db_changes: dict[str, Any] = {}
        if title is not None:
            db_changes["title"] = title
            db_changes["slug"] = slugify(title)
        if body is not None:
            db_changes["body"] = body
        if status is not None:
            db_changes["status"] = status
        if add_tag is not None or remove_tag is not None:
            # Build new tags list
            tags_now = list(found_fm.get("tags") or [])
            db_changes["tags"] = tags_now
        if db_changes:
            store.update_ticket(ticket_id, **db_changes)

    return found_fm


# ---------------------------------------------------------------------------
# Public API — link / unlink
# ---------------------------------------------------------------------------


def link(
    ticket_id: str,
    epic_id: str,
    *,
    resolves: bool = False,
    kind: str = "associated",
    provenance: str | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Link a ticket to an epic.  Updates frontmatter ``epics`` list and Store link."""
    if store is None:
        store = _resolve_store()

    repo_root = str(cwd) if cwd else os.getcwd()

    # Find and update file
    found_path: Path | None = None
    found_fm: dict | None = None
    for fpath, fm in iterate_ticket_files(repo_root):
        if fm.get("id") == ticket_id:
            found_path = fpath
            found_fm = fm
            break

    if found_fm is None:
        return None

    from .relationships import parse_frontmatter_links, serialize_links_to_frontmatter

    # Parse existing links (normalises legacy entries)
    links = parse_frontmatter_links(found_fm, ticket_id)
    # Remove existing entry for this epic if present (idempotent re-link)
    links = [link for link in links if link.epic_id != epic_id]
    # Build new link
    new_link = TicketEpicLink(
        ticket_id=ticket_id,
        epic_id=epic_id,
        resolves_on_complete=resolves,
        kind=kind,
        provenance=provenance,
        linked_at=datetime.now(timezone.utc),
    )
    links.append(new_link)
    found_fm["epics"] = serialize_links_to_frontmatter(links)
    found_fm["last_edited_at"] = datetime.now(timezone.utc)

    if found_path:
        write_ticket_file(found_path, found_fm)

    # Store-backed facade: Store link
    if store is not None and is_cloud_store(store):
        store.link_ticket_to_epic(
            ticket_id=ticket_id,
            epic_id=epic_id,
            resolves_on_complete=resolves,
            kind=kind,
            provenance=provenance,
        )

    return found_fm


def unlink(
    ticket_id: str,
    epic_id: str,
    *,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Unlink a ticket from an epic.  Updates frontmatter and Store link."""
    if store is None:
        store = _resolve_store()

    repo_root = str(cwd) if cwd else os.getcwd()

    found_path: Path | None = None
    found_fm: dict | None = None
    for fpath, fm in iterate_ticket_files(repo_root):
        if fm.get("id") == ticket_id:
            found_path = fpath
            found_fm = fm
            break

    if found_fm is None:
        return None

    from .relationships import parse_frontmatter_links, serialize_links_to_frontmatter

    # Parse existing links (normalises legacy entries), filter out target epic
    links = parse_frontmatter_links(found_fm, ticket_id)
    links = [link for link in links if link.epic_id != epic_id]
    found_fm["epics"] = serialize_links_to_frontmatter(links)
    found_fm["last_edited_at"] = datetime.now(timezone.utc)

    if found_path:
        write_ticket_file(found_path, found_fm)

    # Store-backed facade: remove Store link
    if store is not None and is_cloud_store(store):
        store.unlink_ticket_from_epic(ticket_id=ticket_id, epic_id=epic_id)

    return found_fm


# ---------------------------------------------------------------------------
# Public API — status transitions
# ---------------------------------------------------------------------------


def _change_status(
    ticket_id: str,
    new_status: str,
    *,
    note: str | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Common status-change helper.  Flips status in file + Store."""
    if store is None:
        store = _resolve_store()

    repo_root = str(cwd) if cwd else os.getcwd()

    found_path: Path | None = None
    found_fm: dict | None = None
    for fpath, fm in iterate_ticket_files(repo_root):
        if fm.get("id") == ticket_id:
            found_path = fpath
            found_fm = fm
            break

    if found_fm is None:
        return None

    found_fm["status"] = new_status
    found_fm["last_edited_at"] = datetime.now(timezone.utc)
    if new_status == "addressed":
        found_fm["addressed_at"] = datetime.now(timezone.utc)
        if note:
            found_fm["resolution_note"] = note
    elif new_status == "dismissed":
        if note:
            found_fm["resolution_note"] = note
    elif new_status == "open":
        found_fm["addressed_at"] = None
        found_fm["resolution_note"] = None

    if found_path:
        write_ticket_file(found_path, found_fm)

    # Store-backed facade: update Store row
    if store is not None and is_cloud_store(store):
        db_changes: dict[str, Any] = {"status": new_status}
        if new_status == "addressed":
            db_changes["addressed_at"] = datetime.now(timezone.utc)
            if note:
                db_changes["resolution_note"] = note
        elif new_status == "dismissed":
            if note:
                db_changes["resolution_note"] = note
        elif new_status == "open":
            db_changes["resolution_note"] = None
            db_changes["addressed_at"] = None
        store.update_ticket(ticket_id, **db_changes)

    return found_fm


def addressed(
    ticket_id: str,
    *,
    note: str | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Mark a ticket as addressed."""
    return _change_status(ticket_id, "addressed", note=note, store=store, cwd=cwd)


def dismiss(
    ticket_id: str,
    *,
    reason: str | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Mark a ticket as dismissed."""
    return _change_status(ticket_id, "dismissed", note=reason, store=store, cwd=cwd)


def reopen(
    ticket_id: str,
    *,
    store: Store | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Reopen a previously addressed/dismissed ticket."""
    return _change_status(ticket_id, "open", store=store, cwd=cwd)


# ---------------------------------------------------------------------------
# Auto-address hook
# ---------------------------------------------------------------------------


def address_resolved_by_epic(
    epic_id: str,
    *,
    store: Store | None = None,
    repo_root: str | Path | None = None,
) -> list[str]:
    """Flip every open ticket linked to *epic_id* with ``resolves_on_complete=true``
    to ``'addressed'``.

    Parameters
    ----------
    epic_id:
        The epic that just completed.
    store:
        Explicit store (resolved from env if *None*).
    repo_root:
        Path to the repo for file walking.  If *None* or the
        ``.megaplan/tickets/`` directory does not exist, the file
        walk is skipped cleanly.

    Returns
    -------
    list[str]
        The ULIDs of tickets that were updated (empty if none).
        Idempotent — only ``status='open'`` tickets are affected.
    """
    if store is None:
        store = _resolve_store()

    updated: list[str] = []

    # Store-backed facade mode: backend update (idempotent)
    if store is not None and is_cloud_store(store):
        updated = store.address_tickets_resolved_by_epic(epic_id)

    # File walk (both modes, but only if repo_root is set and dir exists)
    if repo_root is not None:
        # We still walk in cloud mode because files may exist even when DB
        # is the primary store — the file is always written.
        if not tickets_dir(repo_root).is_dir():
            return updated

        from .relationships import auto_address_predicate, parse_frontmatter_links

        for fpath, fm in iterate_ticket_files(repo_root):
            if fm.get("status") != "open":
                continue
            ticket_id = fm.get("id")
            if not isinstance(ticket_id, str) or not ticket_id:
                continue
            links = parse_frontmatter_links(fm, ticket_id)
            matched = any(
                link.epic_id == epic_id and auto_address_predicate(link)
                for link in links
            )
            if not matched:
                continue
            fm["status"] = "addressed"
            fm["addressed_at"] = datetime.now(timezone.utc)
            fm["resolution_note"] = f"Resolved by epic {epic_id} completing."
            fm["last_edited_at"] = datetime.now(timezone.utc)
            write_ticket_file(fpath, fm)
            tid = fm.get("id")
            if tid and tid not in updated:
                updated.append(tid)

    return updated


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _normalize_epics_output(
    fm: dict[str, Any],
    ticket_id: str,
) -> list[dict[str, Any]]:
    """Normalize epics frontmatter through relationship adapter for output.

    Ensures ``kind`` and ``provenance`` are always present in JSON output,
    without copying artifact status into strategy.
    """
    from .relationships import parse_frontmatter_links, serialize_links_to_frontmatter

    links = parse_frontmatter_links(fm, ticket_id)
    return serialize_links_to_frontmatter(links)


def _iso(val: object) -> str | None:
    """Convert a datetime to ISO string, or return *None*."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val else None


# ---------------------------------------------------------------------------
# create_ticket alias (used by planner / agent contexts)
# ---------------------------------------------------------------------------

create_ticket = new
