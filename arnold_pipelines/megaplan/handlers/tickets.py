"""CLI handler dispatch for ``megaplan ticket ...`` subcommands.

Each handler unpacks an :class:`argparse.Namespace` and delegates to the
canonical operations in :mod:`megaplan.tickets`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.tickets import (
    addressed as _core_addressed,
    dismiss as _core_dismiss,
    edit as _core_edit,
    link as _core_link,
    list_tickets as _core_list,
    new as _core_new,
    reopen as _core_reopen,
    search as _core_search,
    show as _core_show,
    unlink as _core_unlink,
)


def handle_ticket_new(args: argparse.Namespace) -> int:
    """Create a ticket; prints only ULID + newline to stdout on success."""
    body: str = ""
    if getattr(args, "stdin_body", False):
        body = "-"
    elif args.body:
        body = args.body
    elif args.edit:
        body = "-"
        # --edit: open $EDITOR (deferred — body='' is valid for now)
    else:
        print("Error: one of -b BODY, --edit, or - is required.", file=sys.stderr)
        return 1

    tags = args.tags.split(",") if args.tags else None
    if tags:
        tags = [t.strip() for t in tags if t.strip()]

    # Resolve --project if given
    if args.project:
        from arnold_pipelines.megaplan.tickets.registry import resolve_project

        cwd = resolve_project(args.project)
        if cwd is None:
            print(f"Error: could not resolve project {args.project!r}", file=sys.stderr)
            return 1
    else:
        cwd = None

    try:
        _core_new(args.title, body=body, tags=tags, cwd=cwd)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def handle_ticket_list(args: argparse.Namespace) -> int:
    """List tickets, optionally filtered.  ``--json`` outputs valid JSON."""
    _core_list(
        status=args.status,
        tags=args.tags.split(",") if args.tags else None,
        json_output=args.json,
    )
    return 0


def handle_ticket_show(args: argparse.Namespace) -> int:
    """Show a single ticket by id.  ``--json`` outputs valid JSON."""
    result = _core_show(args.ticket_id, json_output=args.json)
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_edit(args: argparse.Namespace) -> int:
    """Edit a ticket's fields."""
    result = _core_edit(
        args.ticket_id,
        title=args.title,
        body=args.body,
        status=args.status,
        add_tag=args.add_tag,
        remove_tag=args.remove_tag,
    )
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_link(args: argparse.Namespace) -> int:
    """Link a ticket to an epic."""
    result = _core_link(
        args.ticket_id,
        args.epic_id,
        resolves=args.resolves,
    )
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_unlink(args: argparse.Namespace) -> int:
    """Unlink a ticket from an epic."""
    result = _core_unlink(args.ticket_id, args.epic_id)
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_addressed(args: argparse.Namespace) -> int:
    """Mark a ticket as addressed."""
    result = _core_addressed(args.ticket_id, note=args.note)
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_dismiss(args: argparse.Namespace) -> int:
    """Mark a ticket as dismissed."""
    result = _core_dismiss(args.ticket_id, reason=args.reason)
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_reopen(args: argparse.Namespace) -> int:
    """Reopen a previously addressed/dismissed ticket."""
    result = _core_reopen(args.ticket_id)
    if result is None:
        print(f"Ticket {args.ticket_id!r} not found.", file=sys.stderr)
        return 1
    return 0


def handle_ticket_search(args: argparse.Namespace) -> int:
    """Search tickets across local + cloud, multi-project, multi-keyword."""
    import json as _json

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
    results = _core_search(
        keywords=args.keywords or None,
        keywords_all=getattr(args, "keywords_all", False),
        status=args.status,
        tags=tags,
        projects=args.projects,
        all_projects=args.all_projects,
        sort=args.sort,
        order=("asc" if args.asc else "desc"),
        limit=args.limit,
        snippet=getattr(args, "snippet", True) and bool(args.keywords),
    )

    if args.json:
        print(_json.dumps(results, indent=2, default=str))
        return 0

    if not results:
        print("(no tickets matched)", file=sys.stderr)
        return 0

    multi_project = len({r.get("project") for r in results}) > 1
    # Width tuned for terminal output; readable, not pretty.
    for r in results:
        bits = [r.get("id") or "?"]
        if multi_project:
            bits.append((r.get("project") or "?")[:24])
        bits.append((r.get("status") or "?")[:10])
        title = (r.get("title") or "").replace("\n", " ")
        bits.append(title[:60])
        print("  ".join(bits))
        snip = r.get("snippet")
        if snip:
            print(f"    {snip}")
    return 0


TICKET_DISPATCH: dict[str, Any] = {
    "new": handle_ticket_new,
    "list": handle_ticket_list,
    "show": handle_ticket_show,
    "edit": handle_ticket_edit,
    "link": handle_ticket_link,
    "unlink": handle_ticket_unlink,
    "addressed": handle_ticket_addressed,
    "dismiss": handle_ticket_dismiss,
    "reopen": handle_ticket_reopen,
    "search": handle_ticket_search,
}
