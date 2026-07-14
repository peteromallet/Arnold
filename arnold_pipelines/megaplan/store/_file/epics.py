from __future__ import annotations

from datetime import UTC, datetime
import re
import sqlite3
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import normalize_text
from arnold_pipelines.megaplan.schemas import ChecklistItem, Epic, EpicEvent, EpicSnapshot, Image, SecondOpinion, Sprint, SprintItem
from arnold_pipelines.megaplan.schemas.base import utc_now

from ..base import EpicSummary, StoreError, validate_epic_update_fields
from ..snapshot import canonical_json_dumps, canonical_sha256, capture_epic_snapshot
from .common import _ACTIVE_EPIC_STATES, _new_id, _parse_datetime


class FileEpicMixin:
    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
        home_backend: str = "file",
        idempotency_key: str | None = None,
        epic_id: str | None = None,
    ) -> Epic:
        request_hash = None
        if idempotency_key is not None:
            request_hash = self._request_hash(
                "create_epic",
                (),
                {"title": title, "goal": goal, "body": body, "state": state, "home_backend": home_backend, "epic_id": epic_id},
            )
            replayed = self._load_epic_idempotency("create_epic", idempotency_key, request_hash)
            if replayed is not None:
                return replayed
        if epic_id is None:
            epic_id = _new_id("epic")
        epic = Epic(
            id=epic_id,
            title=title,
            goal=goal,
            body=body,
            state=state,
            home_backend=home_backend,
            revision=0,
            created_at=utc_now(),
            last_edited_at=utc_now(),
        )
        journal_root = self._journal_root_for_epic(epic_id)
        with self.transaction(epic_id):
            self._save_model(self._epic_path(epic_id), epic, journal_root=journal_root)
            self._commit_write(self._body_path(epic_id), body.encode("utf-8"), journal_root=journal_root)
            if idempotency_key is not None and request_hash is not None:
                self._save_epic_idempotency(
                    operation="create_epic",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=epic,
                    journal_root=journal_root,
                )
        return epic

    def load_epic(self, epic_id: str) -> Epic | None:
        return self._load_model(self._epic_path(epic_id), Epic)

    def update_epic(self, epic_id: str, *, expected_revision: int, idempotency_key: str | None = None, **changes: Any) -> Epic:
        validate_epic_update_fields(changes)
        request_hash = None
        if idempotency_key is not None:
            request_hash = self._request_hash(
                "update_epic",
                (epic_id,),
                {"expected_revision": expected_revision, **changes},
            )
            replayed = self._load_epic_idempotency("update_epic", idempotency_key, request_hash)
            if replayed is not None:
                return replayed
        current = self.load_epic(epic_id)
        if current is None:
            raise FileNotFoundError(epic_id)
        self._require_expected_revision(current.revision, expected_revision)
        data = current.model_dump()
        data.update(changes)
        data["revision"] = current.revision + 1
        data["last_edited_at"] = utc_now()
        updated = Epic.model_validate(data)
        journal_root = self._journal_root_for_epic(epic_id)
        with self.transaction(epic_id):
            self._save_model(self._epic_path(epic_id), updated, journal_root=journal_root)
            if "body" in changes:
                self._commit_write(self._body_path(epic_id), updated.body.encode("utf-8"), journal_root=journal_root)
            if idempotency_key is not None and request_hash is not None:
                self._save_epic_idempotency(
                    operation="update_epic",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=updated,
                    journal_root=journal_root,
                )
        return updated

    def list_epics(
        self,
        *,
        active_only: bool = True,
        limit: int = 50,
        home_backend: str | None = None,
    ) -> list[EpicSummary]:
        epics = self._epics()
        epics = [epic for epic in epics if epic.migrated_to is None]
        if active_only:
            epics = [epic for epic in epics if epic.state in _ACTIVE_EPIC_STATES]
        if home_backend is not None:
            epics = [epic for epic in epics if epic.home_backend == home_backend]
        summaries = [EpicSummary.model_validate(epic.model_dump()) for epic in epics[:limit]]
        return summaries

    def search_epics(self, *, query: str, active_only: bool = True, limit: int = 20) -> list[EpicSummary]:
        terms = [term for term in re.findall(r"[\w-]+", normalize_text(query)) if term]
        if not terms:
            return []
        self.rebuild_search_index()
        fts_query = " ".join(f'"{term}"' for term in terms)
        conn = sqlite3.connect(self._search_index_path())
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT e.id,
                       bm25(epic_search) AS fts_rank,
                       CASE
                           WHEN lower(e.title) LIKE ? THEN 3
                           WHEN lower(e.goal) LIKE ? THEN 2
                           ELSE 1
                       END AS match_tier
                FROM epic_search
                JOIN epics e ON e.id = epic_search.id
                WHERE epic_search MATCH ?
                ORDER BY match_tier DESC, fts_rank ASC, e.last_edited_at DESC, e.id DESC
                LIMIT ?
                """,
                [f"%{normalize_text(query)}%", f"%{normalize_text(query)}%", fts_query, limit],
            ).fetchall()
        finally:
            conn.close()
        by_id = {epic.id: epic for epic in self._epics()}
        results: list[EpicSummary] = []
        for row in rows:
            epic = by_id.get(str(row["id"]))
            if epic is None or epic.migrated_to is not None:
                continue
            if active_only and epic.state not in _ACTIVE_EPIC_STATES:
                continue
            results.append(
                EpicSummary.model_validate(
                    {
                        **epic.model_dump(mode="json"),
                        "rank": float(row["fts_rank"]),
                        "match_tier": int(row["match_tier"]),
                        "backend": "file",
                    }
                )
            )
        return results[:limit]

    def _search_index_path(self) -> Path:
        return self.root / "search.sqlite"

    def rebuild_search_index(self) -> None:
        conn = sqlite3.connect(self._search_index_path())
        try:
            conn.execute("DROP TABLE IF EXISTS epics")
            conn.execute("CREATE TABLE epics (id TEXT PRIMARY KEY, title TEXT NOT NULL, goal TEXT NOT NULL, last_edited_at TEXT NOT NULL)")
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS epic_search USING fts5(id UNINDEXED, title, goal, body)")
            conn.execute("DELETE FROM epic_search")
            conn.execute("DELETE FROM epics")
            for epic in sorted(self._epics(), key=lambda row: row.id):
                if epic.migrated_to is not None:
                    continue
                conn.execute(
                    "INSERT INTO epics (id, title, goal, last_edited_at) VALUES (?, ?, ?, ?)",
                    [epic.id, epic.title, epic.goal, epic.last_edited_at.astimezone(UTC).isoformat()],
                )
                conn.execute(
                    "INSERT INTO epic_search (id, title, goal, body) VALUES (?, ?, ?, ?)",
                    [epic.id, epic.title, epic.goal, self.load_body(epic.id)],
                )
            conn.commit()
        finally:
            conn.close()

    def load_body(self, epic_id: str) -> str:
        body_path = self._body_path(epic_id)
        staged = self._active_transaction.staged_bytes(body_path) if self._active_transaction is not None else None
        if staged is not None:
            return staged.decode("utf-8")
        if body_path.exists():
            return body_path.read_text(encoding="utf-8")
        epic = self.load_epic(epic_id)
        if epic is None:
            raise FileNotFoundError(epic_id)
        return epic.body

    def capture_epic_snapshot(self, epic_id: str) -> EpicSnapshot:
        return capture_epic_snapshot(self, epic_id)

    def _delete_epic_owned_file_models(self, epic_id: str, *, model_name: str) -> None:
        if model_name == "images":
            for row in self._images():
                if row.epic_id == epic_id:
                    self._delete_file(self._image_path(row.id))
            return
        if model_name == "second_opinions":
            for row in self._second_opinions():
                if row.epic_id == epic_id:
                    self._delete_file(self._second_opinion_path(row.id))
            return
        raise ValueError(f"Unsupported model collection {model_name!r}")

    def _restore_epic_snapshot(self, snapshot: EpicSnapshot, *, new_revision: int) -> Epic:
        now = utc_now()
        epic_data = dict(snapshot.epic)
        epic_data.update(
            {
                "id": snapshot.epic_id,
                "body": snapshot.body,
                "revision": new_revision,
                "last_edited_at": now,
            }
        )
        restored_epic = Epic.model_validate(epic_data)
        journal_root = self._journal_root_for_epic(snapshot.epic_id)
        self._save_model(self._epic_path(snapshot.epic_id), restored_epic, journal_root=journal_root)
        self._commit_write(self._body_path(snapshot.epic_id), snapshot.body.encode("utf-8"), journal_root=journal_root)

        self._delete_tree(self._checklist_dir(snapshot.epic_id))
        for raw in snapshot.checklist_items:
            item = ChecklistItem.model_validate(raw)
            self._save_model(self._checklist_path(snapshot.epic_id, item.id), item, journal_root=journal_root)

        sprints_root = self._epic_dir(snapshot.epic_id) / "sprints"
        self._delete_tree(sprints_root)
        for raw in snapshot.sprints:
            sprint = Sprint.model_validate(raw)
            self._save_model(self._sprint_path(snapshot.epic_id, sprint.id), sprint, journal_root=journal_root)
        for raw in snapshot.sprint_items:
            item = SprintItem.model_validate(raw)
            sprint = self.load_sprint(item.sprint_id)
            if sprint is None:
                raise StoreError(f"Snapshot sprint item {item.id!r} references missing sprint {item.sprint_id!r}")
            self._save_model(
                self._sprint_items_dir(snapshot.epic_id, item.sprint_id) / f"{item.id}.json",
                item,
                journal_root=journal_root,
            )

        self._delete_epic_owned_file_models(snapshot.epic_id, model_name="images")
        for raw in snapshot.images:
            image = Image.model_validate(raw)
            self._save_model(self._image_path(image.id), image, journal_root=self.root)

        self._delete_epic_owned_file_models(snapshot.epic_id, model_name="second_opinions")
        for raw in snapshot.second_opinions:
            opinion = SecondOpinion.model_validate(raw)
            self._save_model(self._second_opinion_path(opinion.id), opinion, journal_root=self.root)

        return restored_epic

    def _event_snapshot(self, event: EpicEvent, *, field: str) -> EpicSnapshot:
        payload = event.pre_state if field == "pre" else event.post_state
        if payload is None:
            raise StoreError(
                f"Event {event.id!r} from transaction {event.transaction_id!r} lacks {field}_state snapshot"
            )
        return EpicSnapshot.model_validate(payload)

    def revert(
        self,
        epic_id: str,
        to_transaction_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
    ) -> Epic:
        current = self.load_epic(epic_id)
        if current is None:
            raise FileNotFoundError(epic_id)
        self._require_expected_revision(current.revision, expected_revision)
        target_events = [
            event
            for event in self.list_epic_events_for_replay(epic_id)
            if event.transaction_id == to_transaction_id
        ]
        if not target_events:
            raise FileNotFoundError(to_transaction_id)
        target = target_events[0]
        restore_snapshot = self._event_snapshot(target, field="pre")
        if restore_snapshot.epic_id != epic_id:
            raise StoreError(f"Snapshot epic_id {restore_snapshot.epic_id!r} does not match {epic_id!r}")

        pre_snapshot = self.capture_epic_snapshot(epic_id)
        with self.transaction(epic_id):
            restored = self._restore_epic_snapshot(restore_snapshot, new_revision=current.revision + 1)
            post_snapshot = self.capture_epic_snapshot(epic_id)
            self.record_epic_event(
                epic_id=epic_id,
                transaction_id=_new_id("tx"),
                event_type="reverted_to",
                summary=f"Reverted to transaction {to_transaction_id}",
                prior_state={
                    "reverted_to_transaction_id": to_transaction_id,
                    "target_event_id": target.id,
                    "from_revision": current.revision,
                    "to_revision": restored.revision,
                },
                pre_state=pre_snapshot.model_dump(mode="json"),
                post_state=post_snapshot.model_dump(mode="json"),
                pre_state_canonical_json=canonical_json_dumps(pre_snapshot),
                post_state_canonical_json=canonical_json_dumps(post_snapshot),
                pre_state_sha256=canonical_sha256(pre_snapshot),
                post_state_sha256=canonical_sha256(post_snapshot),
                idempotency_key=idempotency_key,
            )
        return restored

    def get_epic_at_time(self, epic_id: str, when: datetime | str) -> EpicSnapshot | None:
        cutoff = _parse_datetime(when)
        if cutoff is None:
            raise ValueError("when is required")
        matching = [
            event
            for event in self.list_epic_events_for_replay(epic_id)
            if event.occurred_at <= cutoff
        ]
        if not matching:
            current = self.load_epic(epic_id)
            if current is not None and current.created_at <= cutoff:
                return self.capture_epic_snapshot(epic_id)
            return None
        return self._event_snapshot(matching[-1], field="post")

    def update_body(self, epic_id: str, body: str, *, expected_revision: int, idempotency_key: str | None = None) -> Epic:
        return self.update_epic(epic_id, expected_revision=expected_revision, body=body)
