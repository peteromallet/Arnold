"""Canonical epic snapshot helpers shared by store backends."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Protocol

from arnold.pipelines.megaplan.schemas import EpicSnapshot


def _canonicalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _canonicalize(value.model_dump(mode="json"))
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


def canonical_json_dumps(value: Any) -> str:
    """Serialize JSON-like data deterministically with sorted keys and no drift."""
    return json.dumps(_canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_dumps(value).encode("utf-8")).hexdigest()


class SnapshotStore(Protocol):
    def load_epic(self, epic_id: str) -> Any | None:
        ...

    def load_body(self, epic_id: str) -> str:
        ...

    def list_checklist_items(self, epic_id: str, *, status: str | None = None) -> list[Any]:
        ...

    def list_sprints(self, epic_id: str, *, status: str | None = None) -> list[Any]:
        ...

    def list_sprint_items(self, sprint_id: str) -> list[Any]:
        ...

    def list_images(self, *, epic_id: str, source: str | None = None, active: bool | None = True) -> list[Any]:
        ...

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[Any]:
        ...


def _model_json(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value)


def capture_epic_snapshot(store: SnapshotStore, epic_id: str) -> EpicSnapshot:
    epic = store.load_epic(epic_id)
    if epic is None:
        raise FileNotFoundError(epic_id)
    checklist = sorted(
        store.list_checklist_items(epic_id),
        key=lambda item: (getattr(item, "position", 0), getattr(item, "id", "")),
    )
    sprints = sorted(
        store.list_sprints(epic_id),
        key=lambda sprint: (getattr(sprint, "sprint_number", 0), getattr(sprint, "id", "")),
    )
    sprint_items = sorted(
        [item for sprint in sprints for item in store.list_sprint_items(sprint.id)],
        key=lambda item: (getattr(item, "sprint_id", ""), getattr(item, "position", 0), getattr(item, "id", "")),
    )
    images = sorted(
        store.list_images(epic_id=epic_id, active=None),
        key=lambda image: (getattr(image, "reference_key", ""), getattr(image, "created_at", ""), getattr(image, "id", "")),
    )
    second_opinions = sorted(
        store.list_second_opinions(epic_id, limit=None),
        key=lambda opinion: (getattr(opinion, "requested_at", ""), getattr(opinion, "id", "")),
    )
    search_document = " ".join(
        part
        for part in (epic.title, epic.goal, store.load_body(epic_id))
        if part
    )
    return EpicSnapshot(
        epic_id=epic_id,
        revision=epic.revision,
        epic=_model_json(epic),
        body=store.load_body(epic_id),
        checklist_items=[_model_json(item) for item in checklist],
        sprints=[_model_json(sprint) for sprint in sprints],
        sprint_items=[_model_json(item) for item in sprint_items],
        images=[_model_json(image) for image in images],
        second_opinions=[_model_json(opinion) for opinion in second_opinions],
        search_document=search_document,
    )
