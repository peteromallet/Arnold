from __future__ import annotations

from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import Ticket, TicketEpicLink
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.tickets.relationships import auto_address_predicate

from ..base import StoreError
from .common import _new_id, _utc_key


class FileTicketMixin:
    def create_ticket(
        self,
        *,
        codebase_id: str,
        title: str,
        body: str = "",
        source: str = "human",
        tags: list[str] | None = None,
        filed_by_actor_id: str | None = None,
        filed_in_turn_id: str | None = None,
        slug: str,
        ticket_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ticket:
        codebase = self.load_codebase(codebase_id)
        resolved_codebase_id = codebase.id if codebase is not None else self._resolve_ticket_codebase().id
        if codebase_id != resolved_codebase_id:
            raise StoreError("FileStore ticket codebase_id must match the repository root codebase")
        ticket = Ticket(
            id=ticket_id or _new_id("ticket"),
            codebase_id=resolved_codebase_id,
            title=title,
            body=body,
            source=source,
            tags=tags or [],
            filed_by_actor_id=filed_by_actor_id,
            filed_in_turn_id=filed_in_turn_id,
            slug=slug,
            created_at=utc_now(),
            last_edited_at=utc_now(),
        )
        self._write_ticket_frontmatter(ticket)
        return ticket

    def load_ticket(self, ticket_id: str) -> Ticket | None:
        for _path, record in self._ticket_file_records():
            if record.get("id") == ticket_id:
                return self._ticket_from_frontmatter(record)
        return None

    def list_tickets(
        self,
        *,
        codebase_id: str | None = None,
        codebase_ids: Sequence[str] | None = None,
        status: str | None = None,
        tags: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        keywords_all: bool = False,
        sort: str = "created",
        order: str = "desc",
        limit: int | None = None,
    ) -> list[Ticket]:
        codebase_id_set = set(codebase_ids) if codebase_ids is not None else None
        tag_set = set(tags) if tags is not None else None
        lowered_keywords = [kw.lower() for kw in keywords or []]
        rows: list[Ticket] = []
        for ticket in self._tickets():
            if codebase_id_set is not None and ticket.codebase_id not in codebase_id_set:
                continue
            if codebase_id_set is None and codebase_id is not None and ticket.codebase_id != codebase_id:
                continue
            if status is not None and ticket.status != status:
                continue
            if tag_set is not None and not tag_set.intersection(ticket.tags):
                continue
            if lowered_keywords:
                searchable = " ".join(
                    [ticket.title, ticket.body, ticket.resolution_note or "", *ticket.tags]
                ).lower()
                matches = [kw in searchable for kw in lowered_keywords]
                if (keywords_all and not all(matches)) or (not keywords_all and not any(matches)):
                    continue
            rows.append(ticket)
        sort_key = {
            "created": lambda row: _utc_key(row.created_at),
            "edited": lambda row: _utc_key(row.last_edited_at),
            "length": lambda row: len(row.body or ""),
            "title": lambda row: row.title.lower(),
        }.get(sort, lambda row: _utc_key(row.created_at))
        rows.sort(key=sort_key, reverse=order.lower() != "asc")
        return rows[:limit] if limit is not None else rows

    def update_ticket(self, ticket_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Ticket:
        for path, record in self._ticket_file_records():
            if record.get("id") != ticket_id:
                continue
            ticket = self._ticket_from_frontmatter(record)
            data = ticket.model_dump()
            data.update(changes)
            data["last_edited_at"] = utc_now()
            if "codebase_id" in data and data["codebase_id"] != self._resolve_ticket_codebase().id:
                raise StoreError("FileStore ticket codebase_id must match the repository root codebase")
            updated = Ticket.model_validate(data)
            self._write_ticket_frontmatter(updated, path=path)
            return updated
        raise FileNotFoundError(self._ticket_path(ticket_id))

    def link_ticket_to_epic(
        self,
        *,
        ticket_id: str,
        epic_id: str,
        resolves_on_complete: bool = False,
        kind: str = "associated",
        provenance: str | None = None,
        idempotency_key: str | None = None,
    ) -> TicketEpicLink:
        for path, record in self._ticket_file_records():
            if record.get("id") != ticket_id:
                continue
            ticket = self._ticket_from_frontmatter(record)
            links = self._ticket_frontmatter_links(record)
            existing = next((link for link in links if link.epic_id == epic_id), None)
            linked_at = existing.linked_at if existing is not None else utc_now()
            link = TicketEpicLink(
                ticket_id=ticket_id,
                epic_id=epic_id,
                resolves_on_complete=resolves_on_complete,
                kind=kind,
                provenance=provenance,
                linked_at=linked_at,
            )
            links = [row for row in links if row.epic_id != epic_id]
            links.append(link)
            self._write_ticket_frontmatter(ticket, path=path, links=links)
            return link
        raise FileNotFoundError(self._ticket_path(ticket_id))

    def unlink_ticket_from_epic(
        self,
        *,
        ticket_id: str,
        epic_id: str,
        idempotency_key: str | None = None,
    ) -> None:
        for path, record in self._ticket_file_records():
            if record.get("id") != ticket_id:
                continue
            ticket = self._ticket_from_frontmatter(record)
            links = [link for link in self._ticket_frontmatter_links(record) if link.epic_id != epic_id]
            self._write_ticket_frontmatter(ticket, path=path, links=links)
            return

    def list_ticket_epic_links(
        self,
        *,
        ticket_id: str | None = None,
        epic_id: str | None = None,
    ) -> list[TicketEpicLink]:
        links = []
        for link in self._ticket_epic_links():
            if ticket_id is not None and link.ticket_id != ticket_id:
                continue
            if epic_id is not None and link.epic_id != epic_id:
                continue
            links.append(link)
        links.sort(key=lambda row: _utc_key(row.linked_at), reverse=True)
        return links

    def address_tickets_resolved_by_epic(self, epic_id: str) -> list[str]:
        addressed: list[str] = []
        for link in self.list_ticket_epic_links(epic_id=epic_id):
            if not auto_address_predicate(link):
                continue
            ticket = self.load_ticket(link.ticket_id)
            if ticket is None or ticket.status != "open":
                continue
            self.update_ticket(
                ticket.id,
                status="addressed",
                resolution_note=f"Resolved by epic {epic_id} completing.",
                addressed_at=utc_now(),
            )
            addressed.append(ticket.id)
        return addressed
