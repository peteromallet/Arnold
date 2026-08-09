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
from .relationships import (
    KIND_ASSOCIATED,
    KIND_PROMOTED_TO_EPIC,
    KIND_RESOLVES_ON_COMPLETE,
    RELATIONSHIP_KINDS,
    auto_address_predicate,
    parse_frontmatter_links,
    serialize_links_to_frontmatter,
)

__all__ = [
    "KIND_ASSOCIATED",
    "KIND_PROMOTED_TO_EPIC",
    "KIND_RESOLVES_ON_COMPLETE",
    "PromotionConflictError",
    "PromotionResult",
    "RELATIONSHIP_KINDS",
    "TicketNotFoundError",
    "address_resolved_by_epic",
    "addressed",
    "auto_address_predicate",
    "create_ticket",
    "dismiss",
    "edit",
    "is_cloud_store",
    "link",
    "list_tickets",
    "new",
    "parse_frontmatter_links",
    "promote_ticket",
    "reopen",
    "search",
    "serialize_links_to_frontmatter",
    "show",
    "unlink",
]