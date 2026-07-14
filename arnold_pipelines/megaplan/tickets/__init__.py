"""Tickets — repo-scoped issue/problem notes.

Local-only mode:  ``.megaplan/tickets/{ulid}-{slug}.md`` files only.
Cloud-configured mode: same files **plus** a DB row in ``tickets``
(via :class:`~megaplan.store.db.DBStore`).
"""

from .core import (
    address_resolved_by_epic,
    addressed,
    create_ticket,
    dismiss,
    edit,
    is_cloud_store,
    link,
    list_tickets,
    new,
    reopen,
    search,
    show,
    unlink,
)
from .promotion import (
    PromotionConflictError,
    PromotionResult,
    TicketNotFoundError,
    promote_ticket,
)

__all__ = [
    "PromotionConflictError",
    "PromotionResult",
    "TicketNotFoundError",
    "address_resolved_by_epic",
    "addressed",
    "create_ticket",
    "dismiss",
    "edit",
    "is_cloud_store",
    "link",
    "list_tickets",
    "new",
    "promote_ticket",
    "reopen",
    "search",
    "show",
    "unlink",
]