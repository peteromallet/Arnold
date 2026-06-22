from __future__ import annotations

from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import ChecklistItem
from arnold_pipelines.megaplan.schemas.base import utc_now

from ..base import ChecklistItemInput
from .common import _new_id


class FileChecklistMixin:
    def seed_checklist(self, epic_id: str, items: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        seeded = [
            ChecklistItemInput(
                content=content,
                status="open",
                position=index,
                source="default_seed",
            )
            for index, content in enumerate(items, start=1)
        ]
        return self.add_checklist_items(epic_id, seeded)

    def list_checklist_items(self, epic_id: str, *, status: str | None = None) -> list[ChecklistItem]:
        items = self._checklist_items(epic_id)
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def add_checklist_items(self, epic_id: str, items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        existing = self._checklist_items(epic_id)
        next_position = max((item.position for item in existing), default=0) + 1
        created: list[ChecklistItem] = []
        for entry in items:
            entry = ChecklistItemInput.model_validate(entry.model_dump() if isinstance(entry, ChecklistItemInput) else entry)
            position = entry.position or next_position
            next_position = max(next_position, position + 1)
            created.append(
                ChecklistItem(
                    id=entry.id or _new_id("check"),
                    epic_id=epic_id,
                    content=entry.content,
                    status=entry.status,
                    position=position,
                    source=entry.source,
                    skip_reason=entry.skip_reason,
                    superseded_by_item_id=entry.superseded_by_item_id,
                    created_at=entry.created_at or utc_now(),
                    completed_at=entry.completed_at,
                )
            )
        journal_root = self._journal_root_for_epic(epic_id)
        with self.transaction(epic_id):
            for item in created:
                self._save_model(self._checklist_path(epic_id, item.id), item, journal_root=journal_root)
        self._normalize_checklist_positions(epic_id, moved=[(item.id, item.position) for item in created])
        by_id = {item.id: item for item in self._checklist_items(epic_id)}
        return [by_id[item.id] for item in created if item.id in by_id]

    def update_checklist_item(self, item_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> ChecklistItem:
        path = self._find_checklist_path(item_id)
        if path is None:
            raise FileNotFoundError(item_id)
        item = self._load_model(path, ChecklistItem)
        assert item is not None
        data = item.model_dump()
        moved_position = changes.get("position")
        data.update(changes)
        if data.get("status") == "done" and not data.get("completed_at"):
            data["completed_at"] = utc_now()
        updated = ChecklistItem.model_validate(data)
        self._save_model(path, updated, journal_root=self._journal_root_for_epic(updated.epic_id))
        self._normalize_checklist_positions(
            updated.epic_id,
            moved=[(updated.id, int(moved_position))] if moved_position is not None else None,
        )
        return self._load_model(path, ChecklistItem) or updated

    def delete_checklist_items(self, item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        affected_epics: set[str] = set()
        for item_id in item_ids:
            path = self._find_checklist_path(item_id)
            if path is not None:
                item = self._load_model(path, ChecklistItem)
                if item is not None:
                    affected_epics.add(item.epic_id)
                self._delete_file(path)
        for epic_id in affected_epics:
            self._normalize_checklist_positions(epic_id)

    def replace_checklist(self, epic_id: str, items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        items = [
            ChecklistItemInput.model_validate(item.model_dump() if isinstance(item, ChecklistItemInput) else item)
            for item in items
        ]
        for existing in self._checklist_items(epic_id):
            self._delete_file(self._checklist_path(epic_id, existing.id))
        return self.add_checklist_items(epic_id, items)

    def _normalize_checklist_positions(
        self,
        epic_id: str,
        *,
        moved: Sequence[tuple[str, int]] | None = None,
    ) -> list[ChecklistItem]:
        items = self._checklist_items(epic_id)
        by_id = {item.id: item for item in items}
        ordered = [item for item in sorted(items, key=lambda row: (row.position, row.created_at, row.id))]
        if moved:
            for item_id, requested_position in moved:
                item = by_id.get(item_id)
                if item is None:
                    continue
                ordered = [row for row in ordered if row.id != item_id]
                index = max(0, min(int(requested_position) - 1, len(ordered)))
                ordered.insert(index, item)
        normalized: list[ChecklistItem] = []
        for position, item in enumerate(ordered, start=1):
            if item.position == position:
                normalized.append(item)
                continue
            data = item.model_dump()
            data["position"] = position
            updated = ChecklistItem.model_validate(data)
            self._save_model(
                self._checklist_path(epic_id, updated.id),
                updated,
                journal_root=self._journal_root_for_epic(epic_id),
            )
            normalized.append(updated)
        return normalized
