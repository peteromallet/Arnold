from __future__ import annotations

from typing import Any, Mapping, Sequence

from megaplan.schemas import Sprint, SprintItem
from megaplan.schemas.base import utc_now

from ..base import SprintItemInput, SprintWithItems
from .common import _new_id


class FileSprintMixin:
    def create_sprint(
        self,
        *,
        epic_id: str,
        sprint_number: int,
        name: str,
        goal: str,
        status: str = "proposed",
        queue_position: int | None = None,
        pending_reason: str | None = None,
        target_weeks: int = 2,
        idempotency_key: str | None = None,
    ) -> Sprint:
        sprint = Sprint(
            id=_new_id("sprint"),
            epic_id=epic_id,
            sprint_number=sprint_number,
            name=name,
            goal=goal,
            status=status,
            revision=0,
            queue_position=queue_position,
            pending_reason=pending_reason,
            target_weeks=target_weeks,
            created_at=utc_now(),
            updated_at=utc_now(),
            queued_at=utc_now() if status == "queued" else None,
        )
        self._save_model(self._sprint_path(epic_id, sprint.id), sprint, journal_root=self._journal_root_for_epic(epic_id))
        return sprint

    def load_sprint(self, sprint_id: str) -> Sprint | None:
        path = self._find_sprint_path(sprint_id)
        return self._load_model(path, Sprint) if path is not None else None

    def list_sprints(self, epic_id: str, *, status: str | None = None) -> list[Sprint]:
        sprints = self._sprints(epic_id)
        if status is not None:
            sprints = [sprint for sprint in sprints if sprint.status == status]
        return sprints

    def list_sprint_items(self, sprint_id: str) -> list[SprintItem]:
        sprint = self.load_sprint(sprint_id)
        if sprint is None:
            return []
        items = self._iter_models(self._sprint_items_dir(sprint.epic_id, sprint.id), SprintItem)
        return sorted(items, key=lambda item: (item.position, item.id))

    def list_sprints_with_items(self, epic_id: str) -> list[SprintWithItems]:
        result: list[SprintWithItems] = []
        for sprint in self.list_sprints(epic_id):
            result.append(
                SprintWithItems.model_validate(
                    {
                        **sprint.model_dump(mode="json"),
                        "items": [item.model_dump(mode="json") for item in self.list_sprint_items(sprint.id)],
                    }
                )
            )
        return result

    def update_sprint(self, sprint_id: str, *, expected_revision: int, idempotency_key: str | None = None, **changes: Any) -> Sprint:
        path = self._find_sprint_path(sprint_id)
        if path is None:
            raise FileNotFoundError(sprint_id)
        sprint = self._load_model(path, Sprint)
        assert sprint is not None
        data = sprint.model_dump()
        self._require_expected_revision(sprint.revision, expected_revision)
        data["revision"] = sprint.revision + 1
        data.update(changes)
        data["updated_at"] = utc_now()
        if data.get("status") == "queued" and not data.get("queued_at"):
            data["queued_at"] = utc_now()
        updated = Sprint.model_validate(data)
        self._save_model(path, updated, journal_root=self._journal_root_for_epic(updated.epic_id))
        return updated

    def delete_sprint(self, sprint_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        path = self._find_sprint_path(sprint_id)
        if path is None:
            return
        self._delete_tree(path.parent)

    def replace_sprint_items(self, sprint_id: str, items: Sequence[SprintItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[SprintItem]:
        sprint = self.load_sprint(sprint_id)
        if sprint is None:
            raise FileNotFoundError(sprint_id)
        items = [
            SprintItemInput.model_validate(item.model_dump() if isinstance(item, SprintItemInput) else item)
            for item in items
        ]
        items_dir = self._sprint_items_dir(sprint.epic_id, sprint.id)
        created: list[SprintItem] = []
        next_position = 1
        for entry in items:
            item = SprintItem(
                id=entry.id or _new_id("sitem"),
                sprint_id=sprint_id,
                content=entry.content,
                estimated_complexity=entry.estimated_complexity,
                status=entry.status,
                source_section=entry.source_section,
                position=entry.position or next_position,
                created_at=entry.created_at or utc_now(),
            )
            next_position = item.position + 1
            created.append(item)
        self._delete_tree(items_dir)
        for item in created:
            self._save_model(items_dir / f"{item.id}.json", item, journal_root=self._journal_root_for_epic(sprint.epic_id))
        return sorted(created, key=lambda item: (item.position, item.id))

    def set_sprint_queue(
        self,
        epic_id: str,
        ordered_sprint_ids: Sequence[str],
        pending: Mapping[str, str],
        *,
        idempotency_key: str | None = None,
    ) -> list[Sprint]:
        ordered_ids = [str(sprint_id) for sprint_id in ordered_sprint_ids]
        pending_map = {str(sprint_id): str(reason) for sprint_id, reason in pending.items()}
        if len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("Duplicate queued sprint IDs are not allowed")
        overlap = set(ordered_ids) & set(pending_map)
        if overlap:
            raise ValueError(f"Sprints cannot be both queued and pending: {sorted(overlap)}")
        sprints = self.list_sprints(epic_id)
        known_ids = {sprint.id for sprint in sprints}
        unknown = sorted((set(ordered_ids) | set(pending_map)) - known_ids)
        if unknown:
            raise FileNotFoundError(f"Unknown sprint IDs for epic {epic_id!r}: {unknown}")
        missing_reason_ids = sorted(sprint_id for sprint_id, reason in pending_map.items() if not reason.strip())
        if missing_reason_ids:
            raise ValueError(f"Pending sprints require a reason: {missing_reason_ids}")
        result: list[Sprint] = []
        with self.transaction(epic_id):
            for sprint in sprints:
                data = sprint.model_dump()
                if sprint.id in ordered_ids:
                    data["status"] = "queued"
                    data["queue_position"] = ordered_ids.index(sprint.id) + 1
                    data["pending_reason"] = None
                    data["queued_at"] = utc_now()
                elif sprint.id in pending_map:
                    data["status"] = "pending"
                    data["queue_position"] = None
                    data["pending_reason"] = pending_map[sprint.id]
                    data["queued_at"] = None
                else:
                    data["queue_position"] = None
                    data["pending_reason"] = None
                    data["queued_at"] = None
                    if data["status"] in {"queued", "pending"}:
                        data["status"] = "proposed"
                data["revision"] = sprint.revision + 1
                data["updated_at"] = utc_now()
                updated = Sprint.model_validate(data)
                self._save_model(self._sprint_path(epic_id, sprint.id), updated, journal_root=self._journal_root_for_epic(epic_id))
                result.append(updated)
        return sorted(result, key=lambda sprint: (sprint.queue_position or 9999, sprint.sprint_number, sprint.id))
