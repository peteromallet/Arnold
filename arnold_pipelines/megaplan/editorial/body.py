"""Store-backed epic body editing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from arnold_pipelines.megaplan.store import Store, deterministic_idempotency_key

from ._events import capture_snapshot, dump_record, get_field, record_event, require_epic, transaction_id
from .errors import EditorialValidationError
from .lockdown import ensure_unlocked_for_edit

SectionMode = Literal["replace", "append", "prepend", "delete"]


@dataclass(frozen=True)
class BodySection:
    title: str
    normalized_title: str
    heading_line: int
    start: int
    end: int


def _validate_body(body: str) -> None:
    if not isinstance(body, str) or not body.strip():
        raise EditorialValidationError("Epic body cannot be empty")


def read_body(*, store: Store, epic_id: str) -> str:
    return store.load_body(epic_id)


def _sections(body: str) -> list[BodySection]:
    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", body))
    sections: list[BodySection] = []
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        title = match.group(2).strip()
        sections.append(
            BodySection(
                title=title,
                normalized_title=title.casefold(),
                heading_line=body[: match.start()].count("\n") + 1,
                start=match.end(),
                end=next_start,
            )
        )
    return sections


def _find_unique_section(body: str, heading: str) -> BodySection:
    normalized = heading.strip().casefold()
    if not normalized:
        raise EditorialValidationError("Section heading cannot be empty")
    matches = [section for section in _sections(body) if section.normalized_title == normalized]
    if not matches:
        raise EditorialValidationError("Section heading not found", details={"heading": heading})
    if len(matches) > 1:
        raise EditorialValidationError(
            "Section heading is duplicated",
            details={"heading": heading, "lines": [section.heading_line for section in matches]},
        )
    return matches[0]


def _section_edit(body: str, *, heading: str, content: str, mode: SectionMode) -> str:
    if mode not in {"replace", "append", "prepend", "delete"}:
        raise EditorialValidationError("Unsupported section edit mode", details={"mode": mode})
    section = _find_unique_section(body, heading)
    current = body[section.start : section.end]
    if mode == "delete":
        replacement = "\n"
    else:
        if not content.strip():
            raise EditorialValidationError("Section content cannot be empty", details={"heading": heading})
        normalized_content = content.strip("\n")
        if mode == "replace":
            replacement = f"\n{normalized_content}\n"
        elif mode == "append":
            replacement = f"{current.rstrip()}\n{normalized_content}\n"
        else:
            replacement = f"\n{normalized_content}\n{current.lstrip()}"
    updated = body[: section.start] + replacement + body[section.end :]
    _validate_body(updated)
    return updated


def update_body(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    body: str,
    expected_revision: int,
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> Any:
    _validate_body(body)
    epic = require_epic(store, epic_id)
    ensure_unlocked_for_edit(epic_state=str(get_field(epic, "state")), operation="body_edit")
    prior_body = store.load_body(epic_id)
    idem = idempotency_key or deterministic_idempotency_key(
        "editorial-body",
        epic_id,
        actor_id,
        expected_revision,
        sha256(body.encode("utf-8")).hexdigest(),
    )
    with store.transaction(epic_id=epic_id) as tx:
        pre_snapshot = capture_snapshot(store, epic_id)
        updated = store.update_body(epic_id, body, expected_revision=expected_revision, idempotency_key=idem)
        record_event(
            store=store,
            epic_id=epic_id,
            transaction_id_value=transaction_id(store, epic_id, tx, idem),
            event_type="body_edit",
            summary=f"{actor_id} updated epic body",
            prior_state={"epic": dump_record(epic), "body": prior_body},
            pre_snapshot=pre_snapshot,
            turn_id=turn_id,
            idempotency_key=idem,
        )
    return updated


def edit_section(
    *,
    store: Store,
    epic_id: str,
    actor_id: str,
    heading: str,
    content: str = "",
    mode: SectionMode = "replace",
    expected_revision: int,
    turn_id: str | None = None,
    idempotency_key: str | None = None,
) -> Any:
    current_body = store.load_body(epic_id)
    next_body = _section_edit(current_body, heading=heading, content=content, mode=mode)
    return update_body(
        store=store,
        epic_id=epic_id,
        actor_id=actor_id,
        body=next_body,
        expected_revision=expected_revision,
        turn_id=turn_id,
        idempotency_key=idempotency_key,
    )
