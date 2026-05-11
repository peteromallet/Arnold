"""CLI handler dispatch for ``megaplan ticket ...`` subcommands.

Each handler unpacks an :class:`argparse.Namespace` and delegates to the
canonical operations in :mod:`megaplan.tickets`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from megaplan.tickets import (
    addressed as _core_addressed,
    dismiss as _core_dismiss,
    edit as _core_edit,
    link as _core_link,
    list_tickets as _core_list,
    new as _core_new,
    reopen as _core_reopen,
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

    try:
        _core_new(args.title, body=body, tags=tags)
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
}