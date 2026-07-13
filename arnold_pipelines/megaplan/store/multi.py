"""Federated Store implementation routing epics across FileStore and DBStore."""

from __future__ import annotations

import base64
import hashlib
import inspect
import uuid
import warnings
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan._core.io import canonical_megaplan_root
from arnold_pipelines.megaplan.schemas import (
    AutomationActor,
    BotTurn,
    ChecklistItem,
    CodeArtifact,
    Codebase,
    ControlMessage,
    CloudRun,
    Epic,
    EpicEvent,
    EpicLock,
    EpicSnapshot,
    ExecutionLease,
    ExternalRequest,
    Feedback,
    Image,
    Message,
    MigrationRun,
    Plan,
    PlanArtifact,
    ProgressEvent,
    ResidentConversation,
    ResidentUserPreference,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    SystemLog,
    Ticket,
    TicketEpicLink,
    ToolCall,
    utc_now,
)
from arnold_pipelines.megaplan.store.base import (
    ArtifactRef,
    ArtifactStat,
    Backend,
    ChecklistItemInput,
    ControlMessageInput,
    CloudRunInput,
    EpicSummary,
    HotContext,
    LeaseConflict,
    MessageSearchHit,
    ProgressEventInput,
    ResidentConversationInput,
    ScheduledJobInput,
    SprintItemInput,
    SprintWithItems,
    Store,
    StoreError,
    Transaction,
    deterministic_idempotency_key,
    validate_plan_artifact_name,
)
from arnold_pipelines.megaplan.store.db import DBStore
from arnold_pipelines.megaplan.store.file import FileStore


class _NullTransaction:
    def __enter__(self) -> _NullTransaction:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class MultiStore(Store):
    """Store federation that routes each epic to its authoritative backend."""

    def __init__(
        self,
        *,
        file_store: Store | None = None,
        db_store: Store | None = None,
        file_root: str | Path | None = None,
        project_root: str | Path | None = None,
        actor_id: str | None = None,
        dsn: str | None = None,
    ) -> None:
        if file_store is None:
            root = Path(file_root) if file_root is not None else self.canonical_filestore_root(project_root or Path.cwd())
            file_store = FileStore(root)
        if db_store is None:
            db_store = DBStore(actor_id=actor_id, dsn=dsn)
        self.file: Store = file_store
        self.db: Store = db_store
        self.actor_id = actor_id if actor_id is not None else getattr(db_store, "_actor_id", None)
        self._route_cache: dict[str, Backend] = {}

    @staticmethod
    def canonical_filestore_root(project_root: str | Path, *, home: Path | None = None) -> Path:
        return canonical_megaplan_root(Path(project_root), home=home)

    @classmethod
    def for_project(
        cls,
        project_root: str | Path,
        *,
        actor_id: str | None = None,
        dsn: str | None = None,
        home: Path | None = None,
    ) -> MultiStore:
        return cls(
            file_root=cls.canonical_filestore_root(project_root, home=home),
            project_root=project_root,
            actor_id=actor_id,
            dsn=dsn,
        )

    def close(self) -> None:
        for backend in (self.file, self.db):
            close = getattr(backend, "close", None)
            if callable(close):
                close()

    def __enter__(self) -> MultiStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ── MultiStore ownership map ──────────────────────────────────────────
    #
    # This store routes every operation to either the file backend or the DB
    # backend.  The routing rules are:
    #
    # File-owned / epic-scoped entities
    #   Entities that carry an epic_id and whose epic has home_backend="file"
    #   are routed through _route_for_epic → file backend.  This includes
    #   sprints, sprint items, plans (when reachable via epic/sprint),
    #   checklist items, epic events, images, second opinions, feedback,
    #   code artifacts, and progress events.
    #
    # DB-owned control-plane entities
    #   These always route directly to self.db regardless of epic routing:
    #   control messages, resident conversations, scheduled jobs, cloud runs,
    #   external requests (pending/confirmed/failed/orphaned), automation
    #   actors, API cache, migrations, and migration runs.
    #
    # Lookup-by-existing-id entities
    #   Messages, images, codebases, tickets, code artifacts, and feedback
    #   are loaded via _load_from_backends (try file then db) or routed
    #   through _route_by_loaded_method (load first, then route by the
    #   loaded entity's epic/sprint/plan/codebase chain).
    #
    # Codebase ambiguity
    #   create/upsert_codebase: route by associated_epic_id if present, else db.
    #   load_codebase / resolve_codebase_by_root_sha: try both backends.
    #   find_codebase(owner, name): file first, then db.
    #   update_codebase / remove_codebase / touch_codebase_accessed /
    #   mark_codebase_verified: route by the loaded codebase's owner.
    #
    # Ticket ambiguity
    #   create_ticket: route by the codebase's ownership chain.
    #   load_ticket: try both backends.
    #   list_tickets: route by codebase_id if given, else merge both backends.
    #   update_ticket / link / unlink / list_ticket_epic_links: route by
    #     loaded ticket's codebase chain.
    #
    # Transaction-id-only merged event lookup
    #   events_by_transaction(transaction_id) always queries self.db.
    #   Transaction ids are globally unique (UUIDs), so there is no
    #   ambiguity — the single DB lookup is sufficient even when events
    #   may originate from file-home epics that have since been migrated.
    # ─────────────────────────────────────────────────────────────────────

    def _backend(self, backend: Backend) -> Store:
        return self.file if backend == "file" else self.db

    def _load_from_backend(self, backend: Backend, epic_id: str) -> Epic | None:
        try:
            return self._backend(backend).load_epic(epic_id)
        except Exception:
            return None

    def _route_for_epic(self, epic_id: str) -> Store:
        backend = self._route_cache.get(epic_id)
        if backend is not None:
            return self._backend(backend)

        candidates: list[Epic] = []
        for candidate_backend in ("file", "db"):
            epic = self._load_from_backend(candidate_backend, epic_id)
            if epic is not None:
                candidates.append(epic)
        if not candidates:
            raise KeyError(f"Epic {epic_id!r} not found in file or db backends")

        active = [epic for epic in candidates if getattr(epic, "migrated_to", None) is None]
        chosen = active[0] if active else candidates[0]
        if chosen.home_backend not in ("file", "db"):
            raise StoreError(f"Epic {epic_id!r} has invalid home_backend {chosen.home_backend!r}")
        self._route_cache[epic_id] = chosen.home_backend
        return self._backend(chosen.home_backend)

    def _invalidate_epic_route(self, epic_id: str) -> None:
        self._route_cache.pop(epic_id, None)

    def _load_from_backends(self, method: str, *args: Any, **kwargs: Any) -> Any:
        for backend in (self.file, self.db):
            result = getattr(backend, method)(*args, **kwargs)
            if result is not None:
                return result
        return None

    def _load_owned_from_backends(self, method: str, identifier: str, *, context: str) -> tuple[Store, Any] | None:
        matches: list[tuple[Store, Any]] = []
        for backend in (self.file, self.db):
            result = getattr(backend, method)(identifier)
            if result is not None:
                matches.append((backend, result))
        if len(matches) > 1:
            raise StoreError(f"{context} {identifier!r} exists in both file and db backends")
        return matches[0] if matches else None

    def _route_by_loaded_owner(self, method: str, identifier: str, *, context: str) -> Store:
        match = self._load_owned_from_backends(method, identifier, context=context)
        if match is None:
            raise KeyError(f"{context} {identifier!r} not found in file or db backends")
        return match[0]

    def _route_by_codebase_owner(self, codebase_id: str) -> Store:
        return self._route_by_loaded_owner("load_codebase", codebase_id, context="Codebase")

    def _route_by_ticket_owner(self, ticket_id: str) -> Store:
        return self._route_by_loaded_owner("load_ticket", ticket_id, context="Ticket")

    def _route_for_loaded(self, item: Any, *, context: str) -> Store:
        epic_id = getattr(item, "epic_id", None)
        if epic_id is not None:
            return self._route_for_epic(epic_id)
        sprint_id = getattr(item, "sprint_id", None)
        if sprint_id is not None:
            return self._route_for_sprint(sprint_id)
        plan_id = getattr(item, "plan_id", None)
        if plan_id is not None:
            return self._route_for_plan(plan_id)
        associated_epic_id = getattr(item, "associated_epic_id", None)
        if associated_epic_id is not None:
            return self._route_for_epic(associated_epic_id)
        codebase_id = getattr(item, "codebase_id", None)
        if codebase_id is not None:
            codebase = self._load_from_backends("load_codebase", codebase_id)
            if codebase is not None:
                return self._route_for_loaded(codebase, context="Codebase")
        raise KeyError(f"Cannot route {context}: no epic_id, sprint_id, plan_id, associated_epic_id, or codebase_id")

    def _route_for_sprint(self, sprint_id: str) -> Store:
        sprint = self._load_from_backends("load_sprint", sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint {sprint_id!r} not found in file or db backends")
        return self._route_for_epic(sprint.epic_id)

    def _route_for_plan(self, plan_id: str) -> Store:
        plan = self._load_from_backends("load_plan", plan_id)
        if plan is None:
            raise KeyError(f"Plan {plan_id!r} not found in file or db backends")
        if plan.epic_id is not None:
            return self._route_for_epic(plan.epic_id)
        if plan.sprint_id is not None:
            return self._route_for_sprint(plan.sprint_id)
        return self.db

    def _route_by_loaded_method(self, method: str, identifier: str, *, context: str) -> Store:
        match = self._load_owned_from_backends(method, identifier, context=context)
        if match is None:
            raise KeyError(f"{context} {identifier!r} not found in file or db backends")
        item = match[1]
        return self._route_for_loaded(item, context=context)

    def _event_sort_key(self, event: EpicEvent) -> tuple[datetime, str]:
        return (event.occurred_at, event.id)

    def transaction(self, epic_id: str | None = None) -> AbstractContextManager[Transaction]:
        if epic_id is None:
            return _NullTransaction()
        return self._route_for_epic(epic_id).transaction(epic_id)

    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
        home_backend: Backend = "file",
        idempotency_key: str | None = None,
    ) -> Epic:
        if home_backend not in ("file", "db"):
            raise ValueError(f"Unsupported home_backend {home_backend!r}")
        epic = self._backend(home_backend).create_epic(
            title=title,
            goal=goal,
            body=body,
            state=state,
            home_backend=home_backend,
            idempotency_key=idempotency_key,
        )
        self._route_cache[epic.id] = epic.home_backend
        return epic

    def load_epic(self, epic_id: str) -> Epic | None:
        try:
            return self._route_for_epic(epic_id).load_epic(epic_id)
        except KeyError:
            return None

    def update_epic(
        self,
        epic_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Epic:
        backend = self._route_for_epic(epic_id)
        updated = backend.update_epic(
            epic_id,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            **changes,
        )
        self._route_cache[epic_id] = updated.home_backend
        if "home_backend" in changes:
            self._invalidate_epic_route(epic_id)
            self._route_cache[epic_id] = updated.home_backend
        return updated

    def list_epics(
        self,
        *,
        active_only: bool = True,
        limit: int = 50,
        home_backend: Backend | None = None,
    ) -> list[EpicSummary]:
        if home_backend is not None:
            return self._backend(home_backend).list_epics(
                active_only=active_only,
                limit=limit,
                home_backend=home_backend,
            )
        rows = self.file.list_epics(active_only=active_only, limit=limit, home_backend="file")
        rows.extend(self.db.list_epics(active_only=active_only, limit=limit, home_backend="db"))
        rows.sort(key=lambda epic: (epic.last_edited_at, epic.id), reverse=True)
        return rows[:limit]

    def search_epics(
        self,
        *,
        query: str,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[EpicSummary]:
        rows = self.file.search_epics(query=query, active_only=active_only, limit=limit)
        rows.extend(self.db.search_epics(query=query, active_only=active_only, limit=limit))
        rows = [row for row in rows if row.home_backend in {"file", "db"} and getattr(row, "migrated_to", None) is None]
        rows.sort(key=lambda epic: (int(epic.match_tier or 0), epic.last_edited_at, epic.id), reverse=True)
        return rows[:limit]

    def capture_epic_snapshot(self, epic_id: str) -> EpicSnapshot:
        return self._route_for_epic(epic_id).capture_epic_snapshot(epic_id)

    def revert(
        self,
        epic_id: str,
        to_transaction_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
    ) -> Epic:
        return self._route_for_epic(epic_id).revert(
            epic_id,
            to_transaction_id,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )

    def get_epic_at_time(self, epic_id: str, when: datetime | str) -> EpicSnapshot | None:
        return self._route_for_epic(epic_id).get_epic_at_time(epic_id, when)

    def load_body(self, epic_id: str) -> str:
        return self._route_for_epic(epic_id).load_body(epic_id)

    def update_body(self, epic_id: str, body: str, *, expected_revision: int, idempotency_key: str | None = None) -> Epic:
        return self._route_for_epic(epic_id).update_body(
            epic_id,
            body,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )

    def seed_checklist(self, epic_id: str, items: Sequence[str], *, idempotency_key: str | None = None) -> list[ChecklistItem]:
        return self._route_for_epic(epic_id).seed_checklist(epic_id, items, idempotency_key=idempotency_key)

    def list_checklist_items(self, epic_id: str, *, status: str | None = None) -> list[ChecklistItem]:
        return self._route_for_epic(epic_id).list_checklist_items(epic_id, status=status)

    def add_checklist_items(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        return self._route_for_epic(epic_id).add_checklist_items(epic_id, items, idempotency_key=idempotency_key)

    def update_checklist_item(self, item_id: str, *, idempotency_key: str | None = None, **changes: Any) -> ChecklistItem:
        for candidate in (self.file, self.db):
            try:
                return candidate.update_checklist_item(item_id, idempotency_key=idempotency_key, **changes)
            except FileNotFoundError:
                continue
        raise KeyError(f"Checklist item {item_id!r} not found in file or db backends")

    def delete_checklist_items(self, item_ids: Sequence[str], *, idempotency_key: str | None = None) -> None:
        self.file.delete_checklist_items(item_ids, idempotency_key=idempotency_key)
        self.db.delete_checklist_items(item_ids, idempotency_key=idempotency_key)

    def replace_checklist(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        return self._route_for_epic(epic_id).replace_checklist(epic_id, items, idempotency_key=idempotency_key)

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
        return self._route_for_epic(epic_id).create_sprint(
            epic_id=epic_id,
            sprint_number=sprint_number,
            name=name,
            goal=goal,
            status=status,
            queue_position=queue_position,
            pending_reason=pending_reason,
            target_weeks=target_weeks,
            idempotency_key=idempotency_key,
        )

    def load_sprint(self, sprint_id: str) -> Sprint | None:
        return self._load_from_backends("load_sprint", sprint_id)

    def list_sprints(self, epic_id: str, *, status: str | None = None) -> list[Sprint]:
        return self._route_for_epic(epic_id).list_sprints(epic_id, status=status)

    def list_sprints_with_items(self, epic_id: str) -> list[SprintWithItems]:
        return self._route_for_epic(epic_id).list_sprints_with_items(epic_id)

    def update_sprint(
        self,
        sprint_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Sprint:
        return self._route_for_sprint(sprint_id).update_sprint(
            sprint_id,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            **changes,
        )

    def delete_sprint(self, sprint_id: str, *, idempotency_key: str | None = None) -> None:
        return self._route_for_sprint(sprint_id).delete_sprint(sprint_id, idempotency_key=idempotency_key)

    def replace_sprint_items(
        self,
        sprint_id: str,
        items: Sequence[SprintItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[SprintItem]:
        return self._route_for_sprint(sprint_id).replace_sprint_items(sprint_id, items, idempotency_key=idempotency_key)

    def list_sprint_items(self, sprint_id: str) -> list[SprintItem]:
        return self._route_for_sprint(sprint_id).list_sprint_items(sprint_id)

    def set_sprint_queue(
        self,
        epic_id: str,
        ordered_sprint_ids: Sequence[str],
        pending: Mapping[str, str],
        *,
        idempotency_key: str | None = None,
    ) -> list[Sprint]:
        return self._route_for_epic(epic_id).set_sprint_queue(
            epic_id,
            ordered_sprint_ids,
            pending,
            idempotency_key=idempotency_key,
        )

    def record_epic_event(
        self,
        *,
        epic_id: str,
        transaction_id: str,
        event_type: str,
        summary: str,
        prior_state: dict[str, Any] | None,
        pre_state: dict[str, Any] | None = None,
        post_state: dict[str, Any] | None = None,
        pre_state_canonical_json: str | None = None,
        post_state_canonical_json: str | None = None,
        pre_state_sha256: str | None = None,
        post_state_sha256: str | None = None,
        turn_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> EpicEvent:
        return self._route_for_epic(epic_id).record_epic_event(
            epic_id=epic_id,
            transaction_id=transaction_id,
            event_type=event_type,
            summary=summary,
            prior_state=prior_state,
            pre_state=pre_state,
            post_state=post_state,
            pre_state_canonical_json=pre_state_canonical_json,
            post_state_canonical_json=post_state_canonical_json,
            pre_state_sha256=pre_state_sha256,
            post_state_sha256=post_state_sha256,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
        )

    def append_telemetry_event(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        scope: str | None = None,
    ) -> dict[str, Any]:
        return self.file.append_telemetry_event(kind, payload, scope=scope)

    def events_for_plan(self, plan_id: str):
        events = list(self.file.events_for_plan(plan_id)) + list(self.db.events_for_plan(plan_id))
        events.sort(
            key=lambda event: (
                event.seq if event.seq is not None else -1,
                str(event.occurred_at or ""),
                event.source or "",
                event.id or "",
            )
        )
        return iter(events)

    def list_epic_events(self, epic_id: str, *, since: str | None = None, until: str | None = None, kinds: Sequence[str] | None = None, limit: int | None = None) -> list[EpicEvent]:
        return self._route_for_epic(epic_id).list_epic_events(epic_id, since=since, until=until, kinds=kinds, limit=limit)

    def list_epic_events_for_replay(self, epic_id: str) -> list[EpicEvent]:
        return self._route_for_epic(epic_id).list_epic_events_for_replay(epic_id)

    def latest_transaction_id(self, epic_id: str) -> str | None:
        return self._route_for_epic(epic_id).latest_transaction_id(epic_id)

    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
        # Query both backends so file-home events remain visible before migration
        # while still tolerating migration copies that preserve event ids.
        merged: dict[str, EpicEvent] = {}
        for backend in (self.file, self.db):
            for event in backend.events_by_transaction(transaction_id):
                merged.setdefault(event.id, event)
        return sorted(merged.values(), key=self._event_sort_key)

    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        discord_reply_provenance: dict[str, Any] | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: dict[str, Any] | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        backend = self._route_for_epic(epic_id) if epic_id is not None else self.db
        return backend.create_message(
            epic_id=epic_id,
            direction=direction,
            content=content,
            discord_message_id=discord_message_id,
            discord_reply_provenance=discord_reply_provenance,
            bot_turn_id=bot_turn_id,
            has_code_attachment=has_code_attachment,
            has_image_attachment=has_image_attachment,
            in_burst_with=in_burst_with,
            was_voice_message=was_voice_message,
            audio_storage_url=audio_storage_url,
            transcription_metadata=transcription_metadata,
            synthesize_outbound_id=synthesize_outbound_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
        )

    def load_message(self, message_id: str) -> Message | None:
        return self._load_from_backends("load_message", message_id)

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        seen: dict[str, Message] = {}
        for backend in (self.file, self.db):
            for message in backend.load_messages(message_ids):
                seen[message.id] = message
        return [seen[mid] for mid in message_ids if mid in seen]

    def find_conversation_message_by_discord_id(
        self, conversation_id: str, discord_message_id: str
    ) -> Message | None:
        matches = [
            match
            for backend in (self.file, self.db)
            if (
                match := backend.find_conversation_message_by_discord_id(
                    conversation_id, discord_message_id
                )
            )
            is not None
        ]
        matches.sort(key=lambda message: (message.sent_at, message.id), reverse=True)
        return matches[0] if matches else None

    def update_message(self, message_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Message:
        return self._route_by_loaded_method("load_message", message_id, context="Message").update_message(
            message_id,
            idempotency_key=idempotency_key,
            **changes,
        )

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        if epic_id is not None:
            return self._route_for_epic(epic_id).latest_outbound_message(epic_id=epic_id)
        candidates = [candidate for backend in (self.file, self.db) if (candidate := backend.latest_outbound_message()) is not None]
        candidates.sort(key=lambda msg: (msg.sent_at, msg.id), reverse=True)
        return candidates[0] if candidates else None

    def create_turn(
        self,
        *,
        epic_id: str | None,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        state_at_turn: dict[str, Any] | None = None,
        model_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> BotTurn:
        backend = self._route_for_epic(epic_id) if epic_id is not None else self.db
        return backend.create_turn(
            epic_id=epic_id,
            triggered_by_message_ids=triggered_by_message_ids,
            prompt_snapshot=prompt_snapshot,
            prompt_version=prompt_version,
            state_at_turn=state_at_turn,
            model_version=model_version,
            idempotency_key=idempotency_key,
        )

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None, **changes: Any) -> BotTurn:
        for backend in (self.file, self.db):
            try:
                return backend.update_turn(turn_id, idempotency_key=idempotency_key, **changes)
            except Exception:
                continue
        raise KeyError(f"Turn {turn_id!r} not found in file or db backends")

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        rows = self.file.find_abandoned_turns(older_than_seconds) + self.db.find_abandoned_turns(older_than_seconds)
        rows.sort(key=lambda turn: (turn.started_at, turn.id))
        return rows

    def list_recent_turns(self, *, n: int = 10, epic_id: str | None = None) -> list[BotTurn]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_recent_turns(n=n, epic_id=epic_id)
        rows = self.file.list_recent_turns(n=n) + self.db.list_recent_turns(n=n)
        rows.sort(key=lambda turn: (turn.started_at, turn.id), reverse=True)
        return rows[:n]

    def search_messages(self, *, query: str, epic_id: str | None = None, limit: int = 20) -> list[MessageSearchHit]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).search_messages(query=query, epic_id=epic_id, limit=limit)
        rows = self.file.search_messages(query=query, limit=limit) + self.db.search_messages(query=query, limit=limit)
        rows.sort(key=lambda msg: (float(msg.rank or 0), msg.sent_at, msg.id), reverse=True)
        return rows[:limit]

    def list_conversation_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        exclude_ids: Sequence[str] = (),
    ) -> list[Message]:
        # Conversation messages may live in either backend; merge, dedupe, and
        # return the last ``limit`` chronologically (oldest first).
        exclude = set(exclude_ids)
        seen: set[str] = set()
        rows: list[Message] = []
        for backend in (self.file, self.db):
            for message in backend.list_conversation_messages(
                conversation_id,
                limit=limit,
                exclude_ids=tuple(exclude),
            ):
                if message.id in seen or message.id in exclude:
                    continue
                seen.add(message.id)
                rows.append(message)
        rows.sort(key=lambda message: (message.sent_at, message.id))
        return rows[-limit:] if limit else []

    def record_tool_call(self, *, turn_id: str, tool_name: str, operation_kind: str, arguments: dict[str, Any], result: dict[str, Any], duration_ms: int, idempotency_key: str | None = None) -> ToolCall:
        for backend in (self.file, self.db):
            try:
                return backend.record_tool_call(
                    turn_id=turn_id,
                    tool_name=tool_name,
                    operation_kind=operation_kind,
                    arguments=arguments,
                    result=result,
                    duration_ms=duration_ms,
                    idempotency_key=idempotency_key,
                )
            except Exception:
                continue
        raise KeyError(f"Turn {turn_id!r} not found in file or db backends")

    def search_tool_calls_by(self, *, tool_name: str | None = None, epic_id: str | None = None, since: str | None = None, limit: int = 20) -> list[ToolCall]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).search_tool_calls_by(tool_name=tool_name, epic_id=epic_id, since=since, limit=limit)
        rows = self.file.search_tool_calls_by(tool_name=tool_name, since=since, limit=limit) + self.db.search_tool_calls_by(tool_name=tool_name, since=since, limit=limit)
        rows.sort(key=lambda call: (call.called_at, call.id), reverse=True)
        return rows[:limit]

    def log_system_event(self, *, level: str, category: str, event_type: str, message: str, details: dict[str, Any] | None = None, turn_id: str | None = None, epic_id: str | None = None, idempotency_key: str | None = None) -> SystemLog:
        backend = self._route_for_epic(epic_id) if epic_id is not None else self.db
        return backend.log_system_event(level=level, category=category, event_type=event_type, message=message, details=details, turn_id=turn_id, epic_id=epic_id, idempotency_key=idempotency_key)

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        if epic_id is None:
            return self.db.load_hot_context(None)
        return self._route_for_epic(epic_id).load_hot_context(epic_id)

    def find_unprocessed_messages(self, epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[Message]:
        return self._route_for_epic(epic_id).find_unprocessed_messages(epic_id, started_at, exclude_ids)

    def insert_pending(self, *, idempotency_key: str, provider: str, endpoint: str, request_summary: dict[str, Any], request_body: dict[str, Any] | None = None, turn_id: str | None = None, tool_call_id: str | None = None) -> ExternalRequest:
        return self.db.insert_pending(idempotency_key=idempotency_key, provider=provider, endpoint=endpoint, request_summary=request_summary, request_body=request_body, turn_id=turn_id, tool_call_id=tool_call_id)

    def mark_confirmed(self, request_id: str, *, provider_request_id: str | None = None, provider_response_summary: dict[str, Any] | None = None, idempotency_key: str | None = None) -> ExternalRequest:
        return self.db.mark_confirmed(request_id, provider_request_id=provider_request_id, provider_response_summary=provider_response_summary, idempotency_key=idempotency_key)

    def mark_failed(self, request_id: str, *, error_details: dict[str, Any], idempotency_key: str | None = None) -> ExternalRequest:
        return self.db.mark_failed(request_id, error_details=error_details, idempotency_key=idempotency_key)

    def find_pending_external_requests(self, older_than_seconds: int) -> list[ExternalRequest]:
        return self.db.find_pending_external_requests(older_than_seconds)

    def mark_orphaned(self, request_id: str, *, error_details: dict[str, Any], idempotency_key: str | None = None) -> ExternalRequest:
        return self.db.mark_orphaned(request_id, error_details=error_details, idempotency_key=idempotency_key)

    def create_image(self, *, epic_id: str, source: str, storage_url: str, prompt: str | None = None, quality: str | None = None, size: str | None = None, reference_key: str | None = None, description: str | None = None, caption: str | None = None, in_body: bool = False, active: bool = True, discord_attachment_id: str | None = None, blob_backend: str | None = None, blob_id: str | None = None, blob_sha256: str | None = None, blob_size_bytes: int | None = None, content_type: str | None = None, idempotency_key: str | None = None) -> Image:
        return self._route_for_epic(epic_id).create_image(epic_id=epic_id, source=source, storage_url=storage_url, prompt=prompt, quality=quality, size=size, reference_key=reference_key, description=description, caption=caption, in_body=in_body, active=active, discord_attachment_id=discord_attachment_id, blob_backend=blob_backend, blob_id=blob_id, blob_sha256=blob_sha256, blob_size_bytes=blob_size_bytes, content_type=content_type, idempotency_key=idempotency_key)

    def attach_image(self, *, epic_id: str, content: bytes, content_type: str, reference_key: str, source: str = "user_uploaded", prompt: str | None = None, quality: str | None = None, size: str | None = None, description: str | None = None, caption: str | None = None, in_body: bool = True, idempotency_key: str | None = None) -> Image:
        return self._route_for_epic(epic_id).attach_image(epic_id=epic_id, content=content, content_type=content_type, reference_key=reference_key, source=source, prompt=prompt, quality=quality, size=size, description=description, caption=caption, in_body=in_body, idempotency_key=idempotency_key)

    def resolve_image_reference(self, epic_id: str, reference: str, *, signed: bool = False, ttl: int = 3600) -> str | None:
        return self._route_for_epic(epic_id).resolve_image_reference(epic_id, reference, signed=signed, ttl=ttl)

    def load_image(self, image_id: str) -> Image | None:
        return self._load_from_backends("load_image", image_id)

    def list_images(self, *, epic_id: str, source: str | None = None, active: bool | None = True) -> list[Image]:
        return self._route_for_epic(epic_id).list_images(epic_id=epic_id, source=source, active=active)

    def update_image(self, image_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Image:
        return self._route_by_loaded_method("load_image", image_id, context="Image").update_image(image_id, idempotency_key=idempotency_key, **changes)

    def list_active_images(self, epic_id: str) -> list[Image]:
        return self._route_for_epic(epic_id).list_active_images(epic_id)

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> Image | None:
        return self._route_for_epic(epic_id).load_active_image_by_reference(epic_id, reference_key)

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        return self._route_for_epic(epic_id).active_image_reference_exists(epic_id, reference_key)

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str, *, idempotency_key: str | None = None) -> list[Image]:
        return self._route_for_epic(epic_id).deactivate_active_image_reference(epic_id, reference_key, idempotency_key=idempotency_key)

    def create_second_opinion(self, *, epic_id: str, requested_by: str, focus_areas: Sequence[str], raw_response: str, score: int, summary: str, verdict: str, model_used: str, resulting_checklist_item_ids: Sequence[str] | None = None, idempotency_key: str | None = None) -> SecondOpinion:
        return self._route_for_epic(epic_id).create_second_opinion(epic_id=epic_id, requested_by=requested_by, focus_areas=focus_areas, raw_response=raw_response, score=score, summary=summary, verdict=verdict, model_used=model_used, resulting_checklist_item_ids=resulting_checklist_item_ids, idempotency_key=idempotency_key)

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[SecondOpinion]:
        return self._route_for_epic(epic_id).list_second_opinions(epic_id, limit=limit)

    def set_second_opinion_checklist_items(self, second_opinion_id: str, checklist_item_ids: Sequence[str], *, idempotency_key: str | None = None) -> SecondOpinion:
        for backend in (self.file, self.db):
            try:
                return backend.set_second_opinion_checklist_items(second_opinion_id, checklist_item_ids, idempotency_key=idempotency_key)
            except Exception:
                continue
        raise KeyError(f"Second opinion {second_opinion_id!r} not found in file or db backends")

    def create_codebase(self, *, owner: str, name: str, default_branch: str, repo_url: str | None = None, repo_workspace: str | None = None, scope: str = "global", group_name: str | None = None, associated_epic_id: str | None = None, root_commit_sha: str | None = None, added_via: str = "manual", verified_accessible_at: str | None = None, notes: str | None = None, codebase_id: str | None = None, idempotency_key: str | None = None) -> Codebase:
        backend = self._route_for_epic(associated_epic_id) if associated_epic_id is not None else self.db
        return backend.create_codebase(owner=owner, name=name, default_branch=default_branch, repo_url=repo_url, repo_workspace=repo_workspace, scope=scope, group_name=group_name, associated_epic_id=associated_epic_id, root_commit_sha=root_commit_sha, added_via=added_via, verified_accessible_at=verified_accessible_at, notes=notes, codebase_id=codebase_id, idempotency_key=idempotency_key)

    def upsert_codebase(self, *, owner: str, name: str, default_branch: str, repo_url: str | None = None, repo_workspace: str | None = None, scope: str = "global", group_name: str | None = None, associated_epic_id: str | None = None, root_commit_sha: str | None = None, added_via: str = "manual", verified_accessible_at: str | None = None, notes: str | None = None, idempotency_key: str | None = None) -> Codebase:
        backend = self._route_for_epic(associated_epic_id) if associated_epic_id is not None else self.db
        return backend.upsert_codebase(owner=owner, name=name, default_branch=default_branch, repo_url=repo_url, repo_workspace=repo_workspace, scope=scope, group_name=group_name, associated_epic_id=associated_epic_id, root_commit_sha=root_commit_sha, added_via=added_via, verified_accessible_at=verified_accessible_at, notes=notes, idempotency_key=idempotency_key)

    def load_codebase(self, codebase_id: str) -> Codebase | None:
        return self._load_from_backends("load_codebase", codebase_id)

    def find_codebase(self, owner: str, name: str) -> Codebase | None:
        return self.file.find_codebase(owner, name) or self.db.find_codebase(owner, name)

    def load_codebase_by_associated_epic(self, epic_id: str) -> Codebase | None:
        return self._route_for_epic(epic_id).load_codebase_by_associated_epic(epic_id)

    def resolve_codebase_by_root_sha(self, root_commit_sha: str) -> Codebase | None:
        return self.file.resolve_codebase_by_root_sha(root_commit_sha) or self.db.resolve_codebase_by_root_sha(root_commit_sha)

    def list_codebases(self, *, scope: str | None = None, group_name: str | None = None, epic_id: str | None = None, include_global: bool = True) -> list[Codebase]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_codebases(scope=scope, group_name=group_name, epic_id=epic_id, include_global=include_global)
        rows = self.file.list_codebases(scope=scope, group_name=group_name, include_global=include_global) + self.db.list_codebases(scope=scope, group_name=group_name, include_global=include_global)
        rows.sort(key=lambda codebase: (codebase.owner, codebase.name, codebase.id))
        return rows

    def update_codebase(self, codebase_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Codebase:
        return self._route_by_codebase_owner(codebase_id).update_codebase(
            codebase_id,
            idempotency_key=idempotency_key,
            **changes,
        )

    def remove_codebase(self, codebase_id: str, *, idempotency_key: str | None = None) -> None:
        return self._route_by_codebase_owner(codebase_id).remove_codebase(
            codebase_id,
            idempotency_key=idempotency_key,
        )

    def touch_codebase_accessed(self, codebase_id: str, *, accessed_at: str | None = None, idempotency_key: str | None = None) -> Codebase:
        return self._route_by_codebase_owner(codebase_id).touch_codebase_accessed(
            codebase_id,
            accessed_at=accessed_at,
            idempotency_key=idempotency_key,
        )

    def mark_codebase_verified(self, codebase_id: str, *, verified_at: str | None = None, default_branch: str | None = None, idempotency_key: str | None = None) -> Codebase:
        return self._route_by_codebase_owner(codebase_id).mark_codebase_verified(codebase_id, verified_at=verified_at, default_branch=default_branch, idempotency_key=idempotency_key)

    def create_ticket(self, *, codebase_id: str, title: str, body: str = "", source: str = "human", tags: list[str] | None = None, filed_by_actor_id: str | None = None, filed_in_turn_id: str | None = None, slug: str, ticket_id: str | None = None, idempotency_key: str | None = None) -> Ticket:
        backend = self._route_by_codebase_owner(codebase_id)
        return backend.create_ticket(codebase_id=codebase_id, title=title, body=body, source=source, tags=tags, filed_by_actor_id=filed_by_actor_id, filed_in_turn_id=filed_in_turn_id, slug=slug, ticket_id=ticket_id, idempotency_key=idempotency_key)

    def load_ticket(self, ticket_id: str) -> Ticket | None:
        return self._load_from_backends("load_ticket", ticket_id)

    def list_tickets(self, *, codebase_id: str | None = None, codebase_ids: Sequence[str] | None = None, status: str | None = None, tags: Sequence[str] | None = None, keywords: Sequence[str] | None = None, keywords_all: bool = False, sort: str = "created", order: str = "desc", limit: int | None = None) -> list[Ticket]:
        if codebase_id is not None:
            return self._route_by_codebase_owner(codebase_id).list_tickets(codebase_id=codebase_id, status=status, tags=tags, keywords=keywords, keywords_all=keywords_all, sort=sort, order=order, limit=limit)
        rows: list[Ticket] = []
        if codebase_ids is not None:
            owned_ids: dict[Store, list[str]] = {self.file: [], self.db: []}
            for scoped_codebase_id in codebase_ids:
                owned_ids[self._route_by_codebase_owner(scoped_codebase_id)].append(scoped_codebase_id)
            for backend, ids in owned_ids.items():
                if ids:
                    rows.extend(backend.list_tickets(codebase_ids=ids, status=status, tags=tags, keywords=keywords, keywords_all=keywords_all, sort=sort, order=order, limit=limit))
        else:
            rows = self.file.list_tickets(status=status, tags=tags, keywords=keywords, keywords_all=keywords_all, sort=sort, order=order, limit=limit) + self.db.list_tickets(status=status, tags=tags, keywords=keywords, keywords_all=keywords_all, sort=sort, order=order, limit=limit)
        reverse = order.lower() != "asc"
        if sort == "edited":
            rows.sort(key=lambda row: (row.last_edited_at, row.id), reverse=reverse)
        elif sort == "length":
            rows.sort(key=lambda row: (len(row.body or ""), row.id), reverse=reverse)
        elif sort == "title":
            rows.sort(key=lambda row: (row.title.lower(), row.id), reverse=reverse)
        else:
            rows.sort(key=lambda row: (row.created_at, row.id), reverse=reverse)
        return rows[:limit] if limit is not None else rows

    def update_ticket(self, ticket_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Ticket:
        return self._route_by_ticket_owner(ticket_id).update_ticket(ticket_id, idempotency_key=idempotency_key, **changes)

    def link_ticket_to_epic(self, *, ticket_id: str, epic_id: str, resolves_on_complete: bool = False, idempotency_key: str | None = None) -> TicketEpicLink:
        return self._route_by_ticket_owner(ticket_id).link_ticket_to_epic(ticket_id=ticket_id, epic_id=epic_id, resolves_on_complete=resolves_on_complete, idempotency_key=idempotency_key)

    def unlink_ticket_from_epic(self, *, ticket_id: str, epic_id: str, idempotency_key: str | None = None) -> None:
        return self._route_by_ticket_owner(ticket_id).unlink_ticket_from_epic(ticket_id=ticket_id, epic_id=epic_id, idempotency_key=idempotency_key)

    def list_ticket_epic_links(self, *, ticket_id: str | None = None, epic_id: str | None = None) -> list[TicketEpicLink]:
        if ticket_id is not None:
            return self._route_by_ticket_owner(ticket_id).list_ticket_epic_links(ticket_id=ticket_id, epic_id=epic_id)
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_ticket_epic_links(epic_id=epic_id)
        return self.file.list_ticket_epic_links() + self.db.list_ticket_epic_links()

    def address_tickets_resolved_by_epic(self, epic_id: str) -> list[str]:
        return self._route_for_epic(epic_id).address_tickets_resolved_by_epic(epic_id)

    def create_code_artifact(self, *, kind: str, source: str, content: str, codebase_id: str | None = None, epic_id: str | None = None, file_path: str | None = None, line_range: Any = None, scope: str | None = None, content_summary: str | None = None, metadata: dict[str, Any] | None = None, expires_at: str | None = None, artifact_id: str | None = None, idempotency_key: str | None = None) -> CodeArtifact:
        backend = self._route_for_epic(epic_id) if epic_id is not None else self.db
        return backend.create_code_artifact(kind=kind, source=source, content=content, codebase_id=codebase_id, epic_id=epic_id, file_path=file_path, line_range=line_range, scope=scope, content_summary=content_summary, metadata=metadata, expires_at=expires_at, artifact_id=artifact_id, idempotency_key=idempotency_key)

    def load_code_artifact(self, artifact_id: str) -> CodeArtifact | None:
        return self._load_from_backends("load_code_artifact", artifact_id)

    def list_code_artifacts(self, *, codebase_id: str | None = None, epic_id: str | None = None, kind: str | None = None, source: str | None = None, file_path: str | None = None, scope: str | None = None, include_expired: bool = True, limit: int | None = 50) -> list[CodeArtifact]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_code_artifacts(codebase_id=codebase_id, epic_id=epic_id, kind=kind, source=source, file_path=file_path, scope=scope, include_expired=include_expired, limit=limit)
        rows = self.file.list_code_artifacts(codebase_id=codebase_id, kind=kind, source=source, file_path=file_path, scope=scope, include_expired=include_expired, limit=limit) + self.db.list_code_artifacts(codebase_id=codebase_id, kind=kind, source=source, file_path=file_path, scope=scope, include_expired=include_expired, limit=limit)
        rows.sort(key=lambda artifact: (artifact.created_at, artifact.id), reverse=True)
        return rows[:limit] if limit is not None else rows

    def update_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None, **changes: Any) -> CodeArtifact:
        return self._route_by_loaded_method("load_code_artifact", artifact_id, context="Code artifact").update_code_artifact(
            artifact_id,
            idempotency_key=idempotency_key,
            **changes,
        )

    def delete_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None) -> None:
        return self._route_by_loaded_method("load_code_artifact", artifact_id, context="Code artifact").delete_code_artifact(
            artifact_id,
            idempotency_key=idempotency_key,
        )

    def touch_code_artifact_used(self, artifact_id: str, *, used_at: str | None = None, idempotency_key: str | None = None) -> CodeArtifact:
        return self._route_by_loaded_method("load_code_artifact", artifact_id, context="Code artifact").touch_code_artifact_used(
            artifact_id,
            used_at=used_at,
            idempotency_key=idempotency_key,
        )

    def get_api_cache(self, cache_key: str, *, now: str | None = None, touch: bool = True) -> CodeArtifact | None:
        # API cache is control-plane state and intentionally DB-owned.
        return self.db.get_api_cache(cache_key, now=now, touch=touch)

    def upsert_api_cache(self, *, cache_key: str, content: str, content_summary: str | None = None, metadata: dict[str, Any] | None = None, codebase_id: str | None = None, epic_id: str | None = None, file_path: str | None = None, scope: str | None = None, expires_at: str | None = None, ttl_seconds: int = 3600, idempotency_key: str | None = None) -> CodeArtifact:
        backend = self._route_for_epic(epic_id) if epic_id is not None else self.db
        return backend.upsert_api_cache(cache_key=cache_key, content=content, content_summary=content_summary, metadata=metadata, codebase_id=codebase_id, epic_id=epic_id, file_path=file_path, scope=scope, expires_at=expires_at, ttl_seconds=ttl_seconds, idempotency_key=idempotency_key)

    def cleanup_expired_api_cache(self, *, now: str | None = None, idempotency_key: str | None = None) -> int:
        # API cache cleanup is control-plane state and intentionally DB-owned.
        return self.db.cleanup_expired_api_cache(now=now, idempotency_key=idempotency_key)

    def create_feedback(self, *, kind: str, content: str, source: str, source_message_id: str | None = None, epic_id: str | None = None, turn_id: str | None = None, context_snapshot: dict[str, Any] | None = None, idempotency_key: str | None = None) -> Feedback:
        backend = self._route_for_epic(epic_id) if epic_id is not None else self.db
        return backend.create_feedback(kind=kind, content=content, source=source, source_message_id=source_message_id, epic_id=epic_id, turn_id=turn_id, context_snapshot=context_snapshot, idempotency_key=idempotency_key)

    def load_feedback(self, feedback_id: str) -> Feedback | None:
        return self._load_from_backends("load_feedback", feedback_id)

    def update_feedback(self, feedback_id: str, *, idempotency_key: str | None = None, **changes: Any) -> Feedback:
        return self._route_by_loaded_method("load_feedback", feedback_id, context="Feedback").update_feedback(
            feedback_id,
            idempotency_key=idempotency_key,
            **changes,
        )

    def list_feedback(self, *, epic_id: str | None = None, active: bool | None = None, kinds: Sequence[str] | None = None, limit: int | None = None) -> list[Feedback]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_feedback(epic_id=epic_id, active=active, kinds=kinds, limit=limit)
        rows = self.file.list_feedback(active=active, kinds=kinds, limit=limit) + self.db.list_feedback(active=active, kinds=kinds, limit=limit)
        rows.sort(key=lambda feedback: (feedback.created_at, feedback.id), reverse=True)
        return rows[:limit] if limit is not None else rows

    def list_observations(self, *, resolved: bool | None = None, limit: int | None = None) -> list[Feedback]:
        rows = self.file.list_observations(resolved=resolved, limit=limit) + self.db.list_observations(resolved=resolved, limit=limit)
        rows.sort(key=lambda feedback: (feedback.created_at, feedback.id), reverse=True)
        return rows[:limit] if limit is not None else rows

    def create_plan(self, *, sprint_id: str | None, epic_id: str | None, name: str, idea: str, idempotency_key: str | None = None, **fields: Any) -> Plan:
        backend = self._route_for_epic(epic_id) if epic_id is not None else (self._route_for_sprint(sprint_id) if sprint_id is not None else self.db)
        return backend.create_plan(sprint_id=sprint_id, epic_id=epic_id, name=name, idea=idea, idempotency_key=idempotency_key, **fields)

    def load_plan(self, plan_id: str) -> Plan | None:
        return self._load_from_backends("load_plan", plan_id)

    def update_plan(self, plan_id: str, *, expected_revision: int, idempotency_key: str | None = None, **changes: Any) -> Plan:
        return self._route_for_plan(plan_id).update_plan(
            plan_id,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            **changes,
        )

    def list_plans(self, *, sprint_id: str | None = None, epic_id: str | None = None, include_orphans: bool = False) -> list[Plan]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_plans(sprint_id=sprint_id, epic_id=epic_id, include_orphans=include_orphans)
        if sprint_id is not None:
            return self._route_for_sprint(sprint_id).list_plans(sprint_id=sprint_id, include_orphans=include_orphans)
        rows = self.file.list_plans(include_orphans=include_orphans) + self.db.list_plans(include_orphans=include_orphans)
        rows.sort(key=lambda plan: (plan.created_at, plan.id), reverse=True)
        return rows

    def read_plan_artifact(self, plan_id: str, name: str) -> bytes | None:
        return self._route_for_plan(plan_id).read_plan_artifact(plan_id, name)

    def write_plan_artifact(self, plan_id: str, name: str, data: bytes, *, expected_revision: int | None = None, idempotency_key: str | None = None) -> ArtifactRef:
        return self._route_for_plan(plan_id).write_plan_artifact(
            plan_id,
            name,
            data,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )

    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]:
        return self._route_for_plan(plan_id).list_plan_artifacts(plan_id)

    def stat_plan_artifact(self, plan_id: str, name: str) -> ArtifactStat | None:
        return self._route_for_plan(plan_id).stat_plan_artifact(plan_id, name)

    def acquire_execution_lease(self, plan_id: str, holder_id: str, worker_kind: str, ttl_seconds: int, *, epic_id: str | None = None, idempotency_key: str | None = None) -> ExecutionLease:
        plan = self.load_plan(plan_id)
        lease_epic_id = epic_id if epic_id is not None else (plan.epic_id if plan is not None else None)
        backend = self._route_for_epic(lease_epic_id) if lease_epic_id is not None else self.db
        return backend.acquire_execution_lease(
            plan_id,
            holder_id,
            worker_kind,
            ttl_seconds,
            epic_id=lease_epic_id,
            idempotency_key=idempotency_key,
        )

    def heartbeat_lease(self, plan_id: str, holder_id: str, *, idempotency_key: str | None = None) -> ExecutionLease:
        return self._route_for_plan(plan_id).heartbeat_lease(plan_id, holder_id, idempotency_key=idempotency_key)

    def release_lease(self, plan_id: str, holder_id: str, *, idempotency_key: str | None = None) -> None:
        return self._route_for_plan(plan_id).release_lease(plan_id, holder_id, idempotency_key=idempotency_key)

    def get_active_lease(self, plan_id: str) -> ExecutionLease | None:
        try:
            return self._route_for_plan(plan_id).get_active_lease(plan_id)
        except KeyError:
            return self.db.get_active_lease(plan_id)

    def find_active_leases_for_epic(self, epic_id: str) -> list[ExecutionLease]:
        return self._route_for_epic(epic_id).find_active_leases_for_epic(epic_id)

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int, *, idempotency_key: str | None = None) -> EpicLock:
        return self._route_for_epic(epic_id).acquire_lock(epic_id, holder_id, ttl_seconds, idempotency_key=idempotency_key)

    def release_lock(self, epic_id: str, holder_id: str, *, idempotency_key: str | None = None) -> None:
        return self._route_for_epic(epic_id).release_lock(epic_id, holder_id, idempotency_key=idempotency_key)

    def put_control_message(self, msg: ControlMessageInput, *, idempotency_key: str | None = None) -> ControlMessage:
        # Control messages coordinate workers across backends and are DB-owned.
        return self.db.put_control_message(msg, idempotency_key=idempotency_key)

    def claim_pending_control_messages(self, *, processor_id: str, max: int = 10, idempotency_key: str | None = None) -> list[ControlMessage]:
        return self.db.claim_pending_control_messages(processor_id=processor_id, max=max, idempotency_key=idempotency_key)

    def mark_control_message_processed(self, msg_id: str, result: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        return self.db.mark_control_message_processed(msg_id, result, idempotency_key=idempotency_key)

    def recover_stale_control_messages(self, *, processor_id: str, older_than_seconds: int, max: int = 10, idempotency_key: str | None = None) -> list[ControlMessage]:
        return self.db.recover_stale_control_messages(processor_id=processor_id, older_than_seconds=older_than_seconds, max=max, idempotency_key=idempotency_key)

    def list_stale_control_messages(self, *, older_than_seconds: int, limit: int = 10) -> list[ControlMessage]:
        return self.db.list_stale_control_messages(older_than_seconds=older_than_seconds, limit=limit)

    def upsert_resident_conversation(self, conversation: ResidentConversationInput, *, idempotency_key: str | None = None) -> ResidentConversation:
        return self.db.upsert_resident_conversation(conversation, idempotency_key=idempotency_key)

    def load_resident_conversation(self, conversation_id: str) -> ResidentConversation | None:
        return self.db.load_resident_conversation(conversation_id)

    def get_resident_conversation_by_key(self, *, transport: str, conversation_key: str) -> ResidentConversation | None:
        return self.db.get_resident_conversation_by_key(transport=transport, conversation_key=conversation_key)

    def list_resident_conversations(self, *, transport: str | None = None, active_epic_id: str | None = None, limit: int = 50) -> list[ResidentConversation]:
        return self.db.list_resident_conversations(transport=transport, active_epic_id=active_epic_id, limit=limit)

    def update_resident_conversation(self, conversation_id: str, *, idempotency_key: str | None = None, **changes: Any) -> ResidentConversation:
        return self.db.update_resident_conversation(conversation_id, idempotency_key=idempotency_key, **changes)

    def load_resident_user_preference(self, *, transport: str, user_id: str) -> ResidentUserPreference | None:
        return self.db.load_resident_user_preference(transport=transport, user_id=user_id)

    def upsert_resident_user_preference(self, *, transport: str, user_id: str, timezone_name: str | None, metadata: dict[str, Any] | None = None, idempotency_key: str | None = None) -> ResidentUserPreference:
        return self.db.upsert_resident_user_preference(
            transport=transport,
            user_id=user_id,
            timezone_name=timezone_name,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )

    def create_scheduled_job(self, job: ScheduledJobInput, *, idempotency_key: str | None = None) -> ScheduledJob:
        return self.db.create_scheduled_job(job, idempotency_key=idempotency_key)

    def load_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        return self.db.load_scheduled_job(job_id)

    def update_scheduled_job(self, job_id: str, *, idempotency_key: str | None = None, **changes: Any) -> ScheduledJob:
        return self.db.update_scheduled_job(job_id, idempotency_key=idempotency_key, **changes)

    def claim_due_scheduled_jobs(self, *, worker_id: str, now: datetime | None = None, stale_after_seconds: int | None = None, max: int = 10, job_type: str | None = None, idempotency_key: str | None = None) -> list[ScheduledJob]:
        return self.db.claim_due_scheduled_jobs(worker_id=worker_id, now=now, stale_after_seconds=stale_after_seconds, max=max, job_type=job_type, idempotency_key=idempotency_key)

    def list_scheduled_jobs(self, *, conversation_id: str | None = None, cloud_run_id: str | None = None, status: str | None = None, job_type: str | None = None, limit: int = 50) -> list[ScheduledJob]:
        return self.db.list_scheduled_jobs(conversation_id=conversation_id, cloud_run_id=cloud_run_id, status=status, job_type=job_type, limit=limit)

    def create_cloud_run(self, run: CloudRunInput, *, idempotency_key: str | None = None) -> CloudRun:
        if run.epic_id is not None:
            routed = self._route_for_epic(run.epic_id)
            if routed is self.file:
                raise StoreError(
                    "Resident cloud orchestration requires a DB-home epic; "
                    f"epic {run.epic_id!r} is file-home"
                )
        return self.db.create_cloud_run(run, idempotency_key=idempotency_key)

    def load_cloud_run(self, run_id: str) -> CloudRun | None:
        return self.db.load_cloud_run(run_id)

    def update_cloud_run(self, run_id: str, *, idempotency_key: str | None = None, **changes: Any) -> CloudRun:
        return self.db.update_cloud_run(run_id, idempotency_key=idempotency_key, **changes)

    def list_cloud_runs(self, *, conversation_id: str | None = None, epic_id: str | None = None, plan_id: str | None = None, sprint_id: str | None = None, status: str | None = None, limit: int = 50) -> list[CloudRun]:
        return self.db.list_cloud_runs(conversation_id=conversation_id, epic_id=epic_id, plan_id=plan_id, sprint_id=sprint_id, status=status, limit=limit)

    def append_progress_event(self, event: ProgressEventInput, *, idempotency_key: str | None = None) -> ProgressEvent:
        return self._route_for_epic(event.epic_id).append_progress_event(event, idempotency_key=idempotency_key)

    def list_progress_events(self, *, plan_id: str | None = None, epic_id: str | None = None, since: Any = None) -> list[ProgressEvent]:
        if epic_id is not None:
            return self._route_for_epic(epic_id).list_progress_events(plan_id=plan_id, epic_id=epic_id, since=since)
        rows = self.file.list_progress_events(plan_id=plan_id, since=since) + self.db.list_progress_events(plan_id=plan_id, since=since)
        rows.sort(key=lambda event: (event.occurred_at, event.id), reverse=True)
        return rows

    def create_automation_actor(self, *, actor_id: str, name: str, granted_epic_ids: str | Sequence[str], actor_kind: str, idempotency_key: str | None = None) -> AutomationActor:
        return self.db.create_automation_actor(actor_id=actor_id, name=name, granted_epic_ids=granted_epic_ids, actor_kind=actor_kind, idempotency_key=idempotency_key)

    def load_automation_actor(self, actor_id: str) -> AutomationActor | None:
        return self.db.load_automation_actor(actor_id)

    def update_automation_actor(self, actor_id: str, *, idempotency_key: str | None = None, **changes: Any) -> AutomationActor:
        return self.db.update_automation_actor(actor_id, idempotency_key=idempotency_key, **changes)

    def _require_migration_holder(self) -> str:
        holder_id = self.actor_id or getattr(self.db, "_actor_id", None)
        if not holder_id:
            raise StoreError("MultiStore migration requires actor_id or DBStore actor context")
        return holder_id

    def _migration_id(self, epic_id: str, target_backend: Backend) -> str:
        return f"mig_{epic_id}_{target_backend}_{uuid.uuid4().hex[:12]}"

    def _expires_after(self, ttl_seconds: int) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=ttl_seconds)

    def _idem(self, migration_id: str, *parts: object) -> str:
        return deterministic_idempotency_key("migration", migration_id, *parts)

    def _call_with_optional_idem(self, fn: Any, *args: Any, idempotency_key: str, **kwargs: Any) -> Any:
        parameters = inspect.signature(fn).parameters
        if "idempotency_key" not in parameters:
            return fn(*args, **kwargs)
        try:
            return fn(*args, idempotency_key=idempotency_key, **kwargs)
        except TypeError as exc:
            if "idempotency_key" not in str(exc):
                raise
            return fn(*args, **kwargs)

    def _update_migration_run(self, migration_id: str, *, idempotency_key: str, **changes: Any) -> MigrationRun:
        return self._call_with_optional_idem(
            self.db.update_migration_run,
            migration_id,
            idempotency_key=idempotency_key,
            **changes,
        )

    def _create_migration_run(self, run: MigrationRun) -> MigrationRun:
        return self._call_with_optional_idem(
            self.db.create_migration_run,
            run,
            idempotency_key=self._idem(run.id, "create_run"),
        )

    def _copy_model_to_filestore(self, target: Any, path: Path, model: Any) -> bool:
        return bool(target.copy_entity_if_absent(path, model, journal_root=target.root))

    def _entity_rows(self, rows: Sequence[Any]) -> list[dict[str, Any]]:
        return [row.model_dump(mode="json") for row in rows]

    def _copy_rows_to_target(self, target: Store, table: str, rows: Sequence[Any]) -> int:
        if not rows:
            return 0
        copy_rows = getattr(target, "copy_rows_idempotent", None)
        if not callable(copy_rows):
            raise StoreError(f"Target backend does not support migration copy for {table}")
        return int(copy_rows(table, self._entity_rows(rows)))

    def _normal_sha256(self, value: str | None) -> str | None:
        if value is None:
            return None
        return value.removeprefix("sha256:")

    def _artifact_model(self, ref: ArtifactRef, data: bytes) -> PlanArtifact:
        digest = hashlib.sha256(data).hexdigest()
        try:
            content_text = data.decode("utf-8")
            content_base64 = None
        except UnicodeDecodeError:
            content_text = None
            content_base64 = base64.b64encode(data).decode("ascii")
        return PlanArtifact(
            name=ref.name,
            kind=ref.kind or "raw_text",
            role=ref.role or "execution",
            content_text=content_text,
            content_base64=content_base64,
            sha256=digest,
            updated_at=ref.updated_at or utc_now(),
        )

    def _copy_plan_artifacts_to_db(self, target: Store, plan_id: str, artifacts: list[tuple[ArtifactRef, bytes]]) -> int:
        copy_artifacts = getattr(target, "copy_plan_artifacts_idempotent", None)
        if not callable(copy_artifacts):
            raise StoreError("Target backend does not support plan artifact migration copy")
        return int(copy_artifacts(plan_id, [self._artifact_model(ref, data) for ref, data in artifacts]))

    def _copy_plan_artifacts_to_file(self, target: Store, plan_id: str, artifacts: list[tuple[ArtifactRef, bytes]], migration_id: str) -> None:
        for ref, data in artifacts:
            artifact_path = target._plan_artifacts_dir(plan_id) / validate_plan_artifact_name(ref.name)
            if artifact_path.exists():
                continue
            plan = target.load_plan(plan_id)
            if plan is None:
                raise StoreError(f"Target plan {plan_id!r} missing before artifact copy")
            target._commit_write(
                artifact_path,
                data,
                journal_root=target._journal_root_for_epic(plan.epic_id),
            )

    def _collect_migration_manifest(self, source: Store, epic_id: str) -> dict[str, Any]:
        checklist = source.list_checklist_items(epic_id)
        sprints = source.list_sprints(epic_id)
        sprint_items = [item for sprint in sprints for item in source.list_sprint_items(sprint.id)]
        plans = source.list_plans(epic_id=epic_id, include_orphans=True)
        plan_artifacts_by_plan = {
            plan.id: [artifact.name for artifact in source.list_plan_artifacts(plan.id)]
            for plan in plans
        }
        images = source.list_images(epic_id=epic_id, active=None)
        second_opinions = source.list_second_opinions(epic_id)
        feedback = source.list_feedback(epic_id=epic_id)
        code_artifacts = source.list_code_artifacts(epic_id=epic_id, limit=None)
        codebases = source.list_codebases(epic_id=epic_id, include_global=False)
        events = source.list_epic_events(epic_id, limit=None)
        return {
            "epic_id": epic_id,
            "entities": {
                "checklist_items": [row.id for row in checklist],
                "sprints": [row.id for row in sprints],
                "sprint_items": [row.id for row in sprint_items],
                "plans": [row.id for row in plans],
                "plan_artifacts_by_plan": plan_artifacts_by_plan,
                "images": [row.id for row in images],
                "second_opinions": [row.id for row in second_opinions],
                "feedback": [row.id for row in feedback],
                "codebases": [row.id for row in codebases],
                "code_artifacts": [row.id for row in code_artifacts],
                "epic_events": [row.id for row in events],
            },
        }

    def _migration_entities(self, source: Store, epic_id: str) -> dict[str, Any]:
        sprints = source.list_sprints(epic_id)
        plans = source.list_plans(epic_id=epic_id, include_orphans=True)
        artifacts: dict[str, list[tuple[ArtifactRef, bytes]]] = {}
        for plan in plans:
            plan_artifacts: list[tuple[ArtifactRef, bytes]] = []
            for ref in source.list_plan_artifacts(plan.id):
                data = source.read_plan_artifact(plan.id, ref.name)
                if data is None:
                    raise StoreError(f"Plan artifact {plan.id}/{ref.name} disappeared during migration")
                plan_artifacts.append((ref, data))
            artifacts[plan.id] = plan_artifacts
        return {
            "epic": source.load_epic(epic_id),
            "checklist_items": source.list_checklist_items(epic_id),
            "sprints": sprints,
            "sprint_items": [item for sprint in sprints for item in source.list_sprint_items(sprint.id)],
            "plans": plans,
            "plan_artifacts": artifacts,
            "images": source.list_images(epic_id=epic_id, active=None),
            "second_opinions": source.list_second_opinions(epic_id),
            "feedback": source.list_feedback(epic_id=epic_id),
            "codebases": source.list_codebases(epic_id=epic_id, include_global=False),
            "code_artifacts": source.list_code_artifacts(epic_id=epic_id, limit=None),
            "epic_events": source.list_epic_events(epic_id, limit=None),
        }

    def _epic_for_target(self, epic: Epic, target_backend: Backend) -> Epic:
        data = epic.model_dump()
        data["home_backend"] = target_backend
        data["migrated_to"] = None
        return Epic.model_validate(data)

    def _copy_metadata_to_filestore(self, target: Any, entities: dict[str, Any], target_backend: Backend, migration_id: str) -> dict[str, Any]:
        epic = self._epic_for_target(entities["epic"], target_backend)
        copied: dict[str, Any] = {}
        copied["epics"] = [epic.id] if self._copy_model_to_filestore(target, target._epic_path(epic.id), epic) else []
        for item in entities["checklist_items"]:
            self._copy_model_to_filestore(target, target._checklist_path(item.epic_id, item.id), item)
        for sprint in entities["sprints"]:
            self._copy_model_to_filestore(target, target._sprint_path(sprint.epic_id, sprint.id), sprint)
        for item in entities["sprint_items"]:
            sprint = next(row for row in entities["sprints"] if row.id == item.sprint_id)
            self._copy_model_to_filestore(target, target._sprint_items_dir(sprint.epic_id, sprint.id) / f"{item.id}.json", item)
        for plan in entities["plans"]:
            self._copy_model_to_filestore(target, target._plan_path(plan.id, epic_id=plan.epic_id, sprint_id=plan.sprint_id), plan)
            self._copy_plan_artifacts_to_file(target, plan.id, entities["plan_artifacts"][plan.id], migration_id)
        for image in entities["images"]:
            self._copy_model_to_filestore(target, target._image_path(image.id), image)
        for opinion in entities["second_opinions"]:
            self._copy_model_to_filestore(target, target._second_opinion_path(opinion.id), opinion)
        for feedback in entities["feedback"]:
            self._copy_model_to_filestore(target, target._feedback_path(feedback.id), feedback)
        for codebase in entities["codebases"]:
            self._copy_model_to_filestore(target, target._codebase_path(codebase.id), codebase)
        for artifact in entities["code_artifacts"]:
            self._copy_model_to_filestore(target, target._code_artifact_path(artifact.id), artifact)
        events_path = target._events_path(epic.id)
        if entities["epic_events"] and not events_path.exists():
            target._commit_write(
                events_path,
                "\n".join(row.model_dump_json() for row in entities["epic_events"]).encode() + b"\n",
                journal_root=target.root,
            )
        for name in ("checklist_items", "sprints", "sprint_items", "plans", "images", "second_opinions", "feedback", "codebases", "code_artifacts", "epic_events"):
            copied[name] = [row.id for row in entities[name]]
        copied["plan_artifacts_by_plan"] = {
            plan_id: [ref.name for ref, _ in artifacts]
            for plan_id, artifacts in entities["plan_artifacts"].items()
        }
        return copied

    def _copy_metadata_to_db(self, target: Store, entities: dict[str, Any], target_backend: Backend) -> dict[str, Any]:
        epic = self._epic_for_target(entities["epic"], target_backend)
        copied: dict[str, Any] = {"epics": [epic.id]}
        self._copy_rows_to_target(target, "epics", [epic])
        for table in ("checklist_items", "sprints", "sprint_items", "plans", "images", "second_opinions", "feedback", "codebases", "code_artifacts", "epic_events"):
            rows = entities[table]
            self._copy_rows_to_target(target, table, rows)
            copied[table] = [row.id for row in rows]
        copied["plan_artifacts_by_plan"] = {}
        for plan_id, artifacts in entities["plan_artifacts"].items():
            self._copy_plan_artifacts_to_db(target, plan_id, artifacts)
            copied["plan_artifacts_by_plan"][plan_id] = [ref.name for ref, _ in artifacts]
        return copied

    def _copy_metadata(self, target: Store, entities: dict[str, Any], target_backend: Backend, migration_id: str) -> dict[str, Any]:
        if hasattr(target, "copy_entity_if_absent"):
            return self._copy_metadata_to_filestore(target, entities, target_backend, migration_id)
        return self._copy_metadata_to_db(target, entities, target_backend)

    def _verify_plan_artifacts(self, source: Store, target: Store, entities: dict[str, Any]) -> dict[str, Any]:
        progress: dict[str, Any] = {}
        for plan_id, artifacts in entities["plan_artifacts"].items():
            plan_progress: dict[str, str] = {}
            for ref, data in artifacts:
                target_data = target.read_plan_artifact(plan_id, ref.name)
                if target_data is None:
                    raise StoreError(f"Plan artifact {plan_id}/{ref.name} missing after migration")
                source_sha = hashlib.sha256(data).hexdigest()
                target_sha = hashlib.sha256(target_data).hexdigest()
                if source_sha != target_sha:
                    raise StoreError(f"Plan artifact {plan_id}/{ref.name} hash mismatch after migration")
                stat = target.stat_plan_artifact(plan_id, ref.name)
                if stat and self._normal_sha256(stat.sha256) != target_sha:
                    raise StoreError(f"Plan artifact {plan_id}/{ref.name} stat hash mismatch after migration")
                plan_progress[ref.name] = target_sha
            progress[plan_id] = plan_progress
        return progress

    def _copy_and_verify_image_blobs(self, source: Store, target: Store, entities: dict[str, Any]) -> dict[str, Any]:
        source_blobs = getattr(source, "blobs", None)
        target_blobs = getattr(target, "blobs", None)
        progress: dict[str, Any] = {}
        for image in entities["images"]:
            if not image.blob_id:
                continue
            if source_blobs is None or target_blobs is None:
                raise StoreError(f"Image {image.id} has blob metadata but one backend lacks BlobStore support")
            source_bytes = source_blobs.get(image.blob_id)
            source_sha = hashlib.sha256(source_bytes).hexdigest()
            expected_sha = self._normal_sha256(image.blob_sha256)
            if expected_sha is not None and expected_sha != source_sha:
                raise StoreError(f"Image {image.id} source blob hash does not match image metadata")
            target_stat = target_blobs.stat(image.blob_id)
            if target_stat is None:
                target_blobs.put(
                    image.blob_id,
                    source_bytes,
                    content_type=image.content_type or "application/octet-stream",
                )
            target_bytes = target_blobs.get(image.blob_id)
            target_sha = hashlib.sha256(target_bytes).hexdigest()
            if target_sha != source_sha:
                raise StoreError(f"Image {image.id} blob hash mismatch after migration")
            stat = target_blobs.stat(image.blob_id)
            if stat is None or stat.size_bytes != len(source_bytes):
                raise StoreError(f"Image {image.id} target blob stat missing or size mismatch after migration")
            progress[image.reference_key] = {
                "image_id": image.id,
                "blob_id": image.blob_id,
                "source_sha256": source_sha,
                "target_sha256": target_sha,
                "target_stat_size_bytes": stat.size_bytes,
            }
        return progress

    def _verify_metadata(self, target: Store, epic_id: str, entities: dict[str, Any]) -> None:
        target_epic = target.load_epic(epic_id)
        if target_epic is None:
            raise StoreError(f"Target epic {epic_id!r} missing after migration")
        checks = {
            "checklist_items": len(target.list_checklist_items(epic_id)),
            "sprints": len(target.list_sprints(epic_id)),
            "images": len(target.list_images(epic_id=epic_id, active=None)),
            "second_opinions": len(target.list_second_opinions(epic_id)),
            "feedback": len(target.list_feedback(epic_id=epic_id)),
            "code_artifacts": len(target.list_code_artifacts(epic_id=epic_id, limit=None)),
            "epic_events": len(target.list_epic_events(epic_id, limit=None)),
            "plans": len(target.list_plans(epic_id=epic_id, include_orphans=True)),
        }
        for name, actual in checks.items():
            expected = len(entities[name])
            if actual < expected:
                raise StoreError(f"Target {name} count {actual} is lower than source count {expected}")

    def _preflight_migration(self, source: Store, epic_id: str) -> None:
        active_migration = self.db.find_active_migration_for_epic(epic_id)
        if active_migration is not None:
            raise LeaseConflict(f"Epic {epic_id!r} already has active migration {active_migration.id!r}")
        active_leases = source.find_active_leases_for_epic(epic_id)
        if active_leases:
            plans = ", ".join(sorted(lease.plan_id for lease in active_leases))
            raise LeaseConflict(f"Epic {epic_id!r} has active execution leases: {plans}")

    def _preflight_target_collision(self, target: Store, epic_id: str) -> None:
        target_epic = target.load_epic(epic_id)
        if target_epic is not None and target_epic.migrated_to is None:
            raise StoreError(f"Target backend already has active epic {epic_id!r}")

    def _terminal_migration(self, run: MigrationRun) -> bool:
        return run.completed_at is not None or run.phase in {"complete", "aborted"}

    def _phase_index(self, phase: str) -> int:
        phases = ["planning", "copying_meta", "copying_blobs", "verifying", "cutting_over", "tombstoning", "complete"]
        if phase not in phases:
            raise StoreError(f"Unknown migration phase {phase!r}")
        return phases.index(phase)

    def _claim_or_refresh_resume(self, run: MigrationRun, holder_id: str, ttl_seconds: int) -> MigrationRun:
        now = datetime.now(UTC)
        if run.expires_at > now and run.holder_id != holder_id:
            raise LeaseConflict(f"Migration {run.id!r} is still held by {run.holder_id!r}")
        if run.expires_at <= now:
            claim = getattr(self.db, "claim_expired_migration", None)
            if callable(claim):
                return self._call_with_optional_idem(
                    claim,
                    run.id,
                    holder_id,
                    ttl_seconds,
                    idempotency_key=self._idem(run.id, "claim_expired"),
                )
        return self._update_migration_run(
            run.id,
            holder_id=holder_id,
            expires_at=self._expires_after(ttl_seconds),
            idempotency_key=self._idem(run.id, "resume_refresh"),
        )

    def _merge_copied_ids(self, current: Mapping[str, Any], copied: Mapping[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        for key, value in copied.items():
            if key == "plan_artifacts_by_plan":
                existing_by_plan = dict(merged.get(key, {}))
                for plan_id, names in value.items():
                    existing_names = set(existing_by_plan.get(plan_id, []))
                    existing_names.update(names)
                    existing_by_plan[plan_id] = sorted(existing_names)
                merged[key] = existing_by_plan
            elif isinstance(value, list):
                existing = set(merged.get(key, []))
                existing.update(value)
                merged[key] = sorted(existing)
            else:
                merged[key] = value
        return merged

    def _cutover_source_if_needed(self, source: Store, run: MigrationRun) -> None:
        current_source_epic = source.load_epic(run.epic_id)
        if current_source_epic is None:
            raise StoreError(f"Source epic {run.epic_id!r} disappeared during migration")
        if current_source_epic.home_backend == run.target_backend:
            return
        source.update_epic(
            run.epic_id,
            expected_revision=current_source_epic.revision,
            home_backend=run.target_backend,
            idempotency_key=self._idem(run.id, "source", "cutover"),
        )
        self._route_cache[run.epic_id] = run.target_backend

    def _tombstone_source_if_needed(self, source: Store, run: MigrationRun) -> None:
        current_source_epic = source.load_epic(run.epic_id)
        if current_source_epic is None:
            raise StoreError(f"Source epic {run.epic_id!r} disappeared before tombstoning")
        if current_source_epic.migrated_to == run.id:
            return
        source.update_epic(
            run.epic_id,
            expected_revision=current_source_epic.revision,
            migrated_to=run.id,
            idempotency_key=self._idem(run.id, "source", "tombstone"),
        )

    def _continue_migration(self, run: MigrationRun, *, ttl_seconds: int, source_lock_acquired: bool = False) -> MigrationRun:
        source = self._backend(run.source_backend)
        target = self._backend(run.target_backend)
        holder_id = run.holder_id
        if not source_lock_acquired:
            source.acquire_lock(
                run.epic_id,
                holder_id,
                ttl_seconds,
                idempotency_key=self._idem(run.id, "source_lock", "resume"),
            )
        lock_released = False
        try:
            phase_index = self._phase_index(run.phase)
            if phase_index <= self._phase_index("planning"):
                manifest = self._collect_migration_manifest(source, run.epic_id)
                manifest.update({"source_backend": run.source_backend, "target_backend": run.target_backend})
                run = self._update_migration_run(
                    run.id,
                    phase="copying_meta",
                    manifest=manifest,
                    expires_at=self._expires_after(ttl_seconds),
                    idempotency_key=self._idem(run.id, "phase", "copying_meta"),
                )
                phase_index = self._phase_index(run.phase)

            entities = self._migration_entities(source, run.epic_id)
            if phase_index <= self._phase_index("copying_meta"):
                copied_ids = self._copy_metadata(target, entities, run.target_backend, run.id)
                run = self._update_migration_run(
                    run.id,
                    phase="copying_blobs",
                    copied_ids=self._merge_copied_ids(run.copied_ids, copied_ids),
                    expires_at=self._expires_after(ttl_seconds),
                    idempotency_key=self._idem(run.id, "phase", "copying_blobs"),
                )
                phase_index = self._phase_index(run.phase)

            if phase_index <= self._phase_index("copying_blobs"):
                blob_progress = self._verify_plan_artifacts(source, target, entities)
                image_progress = self._copy_and_verify_image_blobs(source, target, entities)
                if image_progress:
                    blob_progress["images"] = image_progress
                run = self._update_migration_run(
                    run.id,
                    phase="verifying",
                    blob_copy_progress={**run.blob_copy_progress, **blob_progress},
                    expires_at=self._expires_after(ttl_seconds),
                    idempotency_key=self._idem(run.id, "phase", "verifying"),
                )
                phase_index = self._phase_index(run.phase)

            if phase_index <= self._phase_index("verifying"):
                self._verify_metadata(target, run.epic_id, entities)
                run = self._update_migration_run(
                    run.id,
                    phase="cutting_over",
                    expires_at=self._expires_after(ttl_seconds),
                    idempotency_key=self._idem(run.id, "phase", "cutting_over"),
                )
                phase_index = self._phase_index(run.phase)

            if phase_index <= self._phase_index("cutting_over"):
                self._cutover_source_if_needed(source, run)
                self._route_cache[run.epic_id] = run.target_backend
                run = self._update_migration_run(
                    run.id,
                    phase="tombstoning",
                    expires_at=self._expires_after(ttl_seconds),
                    idempotency_key=self._idem(run.id, "phase", "tombstoning"),
                )
                phase_index = self._phase_index(run.phase)

            if phase_index <= self._phase_index("tombstoning"):
                self._tombstone_source_if_needed(source, run)
                source.release_lock(
                    run.epic_id,
                    holder_id,
                    idempotency_key=self._idem(run.id, "source_lock", "release"),
                )
                lock_released = True
                completed_at = utc_now()
                return self._update_migration_run(
                    run.id,
                    phase="complete",
                    completed_at=completed_at,
                    expires_at=completed_at,
                    idempotency_key=self._idem(run.id, "phase", "complete"),
                )
            return run
        finally:
            if not lock_released:
                try:
                    source.release_lock(
                        run.epic_id,
                        holder_id,
                        idempotency_key=self._idem(run.id, "source_lock", "finally_release"),
                    )
                except Exception:
                    pass

    def incomplete_migration_warnings(self) -> list[str]:
        iter_runs = getattr(self.db, "_migration_runs", None)
        if not callable(iter_runs):
            return []
        active = [
            run
            for run in iter_runs()
            if not self._terminal_migration(run)
        ]
        active.sort(key=lambda row: (row.expires_at, row.id))
        return [
            f"Migration {run.id} for epic {run.epic_id} is incomplete at phase {run.phase}; resume explicitly with migrate --resume {run.id}."
            for run in active
        ]

    def warn_incomplete_migrations(self) -> list[str]:
        messages = self.incomplete_migration_warnings()
        for message in messages:
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        return messages

    def get_migration_run(self, migration_id: str) -> MigrationRun | None:
        return self.db.load_migration_run(migration_id)

    def migrate_epic(self, epic_id: str, *, to: Backend, ttl_seconds: int = 300) -> MigrationRun:
        holder_id = self._require_migration_holder()
        epic = self.load_epic(epic_id)
        if epic is None:
            raise KeyError(f"Epic {epic_id!r} not found in file or db backends")
        source_backend = epic.home_backend
        target_backend = to
        if source_backend == target_backend:
            raise StoreError(f"Epic {epic_id!r} is already homed in {target_backend!r}")
        source = self._backend(source_backend)
        target = self._backend(target_backend)

        self._preflight_migration(source, epic_id)
        self._preflight_target_collision(target, epic_id)
        migration_id = self._migration_id(epic_id, target_backend)
        source.acquire_lock(
            epic_id,
            holder_id,
            ttl_seconds,
            idempotency_key=self._idem(migration_id, "source_lock"),
        )
        lock_released = False
        try:
            run = MigrationRun(
                id=migration_id,
                epic_id=epic_id,
                source_backend=source_backend,
                target_backend=target_backend,
                phase="planning",
                manifest={},
                copied_ids={},
                blob_copy_progress={},
                holder_id=holder_id,
                expires_at=self._expires_after(ttl_seconds),
            )
            run = self._create_migration_run(run)
            manifest = self._collect_migration_manifest(source, epic_id)
            manifest.update({"source_backend": source_backend, "target_backend": target_backend})
            run = self._update_migration_run(
                migration_id,
                phase="copying_meta",
                manifest=manifest,
                expires_at=self._expires_after(ttl_seconds),
                idempotency_key=self._idem(migration_id, "phase", "copying_meta"),
            )

            entities = self._migration_entities(source, epic_id)
            copied_ids = self._copy_metadata(target, entities, target_backend, migration_id)
            run = self._update_migration_run(
                migration_id,
                phase="copying_blobs",
                copied_ids=copied_ids,
                expires_at=self._expires_after(ttl_seconds),
                idempotency_key=self._idem(migration_id, "phase", "copying_blobs"),
            )

            blob_progress = self._verify_plan_artifacts(source, target, entities)
            image_progress = self._copy_and_verify_image_blobs(source, target, entities)
            if image_progress:
                blob_progress["images"] = image_progress
            run = self._update_migration_run(
                migration_id,
                phase="verifying",
                blob_copy_progress=blob_progress,
                expires_at=self._expires_after(ttl_seconds),
                idempotency_key=self._idem(migration_id, "phase", "verifying"),
            )

            self._verify_metadata(target, epic_id, entities)
            run = self._update_migration_run(
                migration_id,
                phase="cutting_over",
                expires_at=self._expires_after(ttl_seconds),
                idempotency_key=self._idem(migration_id, "phase", "cutting_over"),
            )

            current_source_epic = source.load_epic(epic_id)
            if current_source_epic is None:
                raise StoreError(f"Source epic {epic_id!r} disappeared during migration")
            source.update_epic(
                epic_id,
                expected_revision=current_source_epic.revision,
                home_backend=target_backend,
                idempotency_key=self._idem(migration_id, "source", "cutover"),
            )
            self._route_cache[epic_id] = target_backend
            run = self._update_migration_run(
                migration_id,
                phase="tombstoning",
                expires_at=self._expires_after(ttl_seconds),
                idempotency_key=self._idem(migration_id, "phase", "tombstoning"),
            )

            current_source_epic = source.load_epic(epic_id)
            if current_source_epic is None:
                raise StoreError(f"Source epic {epic_id!r} disappeared before tombstoning")
            source.update_epic(
                epic_id,
                expected_revision=current_source_epic.revision,
                migrated_to=migration_id,
                idempotency_key=self._idem(migration_id, "source", "tombstone"),
            )
            source.release_lock(
                epic_id,
                holder_id,
                idempotency_key=self._idem(migration_id, "source_lock", "release"),
            )
            lock_released = True
            completed_at = utc_now()
            return self._update_migration_run(
                migration_id,
                phase="complete",
                completed_at=completed_at,
                expires_at=completed_at,
                idempotency_key=self._idem(migration_id, "phase", "complete"),
            )
        finally:
            if not lock_released:
                try:
                    source.release_lock(
                        epic_id,
                        holder_id,
                        idempotency_key=self._idem(migration_id, "source_lock", "finally_release"),
                    )
                except Exception:
                    pass

    def resume_migration(self, migration_id: str, *, ttl_seconds: int = 300) -> MigrationRun:
        run = self.db.load_migration_run(migration_id)
        if run is None:
            raise KeyError(f"Migration run {migration_id!r} not found")
        if self._terminal_migration(run):
            return run
        holder_id = self._require_migration_holder()
        run = self._claim_or_refresh_resume(run, holder_id, ttl_seconds)
        return self._continue_migration(run, ttl_seconds=ttl_seconds)
