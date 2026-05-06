"""File-backed Store implementation for Sprint 1."""

from __future__ import annotations

from collections import defaultdict
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
import hashlib
import json
import mimetypes
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from megaplan._core.io import (
    commit_journal_transaction,
    fsync_dir,
    journal_blob_promotion,
    journal_bytes_write,
    journal_event_log,
    json_dump,
    normalize_text,
    prepare_journal_transaction,
    read_committed_framed_json_records,
    recover_journal,
)
from megaplan.schemas import (
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
    ProgressEvent,
    ResidentConversation,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    SystemLog,
    ToolCall,
)
from megaplan.schemas.base import utc_now

from .base import (
    ArtifactRef,
    ArtifactStat,
    ChecklistItemInput,
    ControlMessageInput,
    CloudRunInput,
    EpicSummary,
    HotContext,
    LeaseConflict,
    LockConflict,
    MessageSearchHit,
    ProgressEventInput,
    ResidentConversationInput,
    RevisionConflict,
    SprintItemInput,
    SprintWithItems,
    Store,
    StoreError,
    ScheduledJobInput,
    Transaction,
    validate_plan_artifact_name,
)
from .blob import LocalDirBlobStore
from .snapshot import canonical_json_dumps, canonical_sha256, capture_epic_snapshot

_ACTIVE_EPIC_STATES = {"shaping", "sprinting", "planned", "paused"}
_TERMINAL_TURN_STATUSES = {"completed", "failed", "abandoned"}
_OBSERVATION_KINDS = {"friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"}
_SOURCE_REFERENCE_PREFIX = {
    "user_uploaded": "img_user_upload",
    "caller_uploaded": "img_caller_upload",
    "agent_generated": "img_agent_generated",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _utc_key(value: datetime | None) -> tuple[datetime, bool]:
    if value is None:
        return (datetime.min.replace(tzinfo=UTC), True)
    return (value, False)


def _model_bytes(model: Any) -> bytes:
    if hasattr(model, "model_dump"):
        return json_dump(model.model_dump(mode="json")).encode("utf-8")
    return json_dump(model).encode("utf-8")


class _FileStoreTransaction(AbstractContextManager["_FileStoreTransaction"]):
    def __init__(
        self,
        store: "FileStore",
        journal_root: Path,
        *,
        joined: bool = False,
        parent: "_FileStoreTransaction | None" = None,
    ) -> None:
        self.store = store
        self.journal_root = journal_root
        self.tx_id = _new_id("tx")
        self._joined = joined
        self._parent = parent
        self._writes: list[dict[str, Any]] = []
        self._blobs: list[dict[str, Any]] = []
        self._event_logs: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def __enter__(self) -> _FileStoreTransaction:
        if self._joined and self._parent is not None:
            return self._parent
        self.store._active_transaction = self
        return self

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        if self._joined:
            return False
        self.store._active_transaction = None
        if exc_type is not None:
            return False
        if not self._writes and not self._blobs and not self._event_logs:
            return False
        prepare_journal_transaction(
            self.journal_root,
            self.tx_id,
            writes=self._writes,
            event_logs=[
                journal_event_log(Path(path), records)
                for path, records in self._event_logs.items()
            ],
            blobs=self._blobs,
        )
        commit_journal_transaction(self.journal_root, self.tx_id)
        return False

    def add_write(self, path: Path, data: bytes) -> None:
        self._writes.append(journal_bytes_write(path, data, tx_id=self.tx_id))

    def staged_bytes(self, path: Path) -> bytes | None:
        path_str = str(path)
        for entry in reversed(self._writes):
            if entry.get("target_path") != path_str:
                continue
            content = entry.get("content")
            if entry.get("content_storage") == "base64":
                import base64

                return base64.b64decode(str(content).encode("ascii"))
            if isinstance(content, str):
                return content.encode("utf-8")
        return None

    def staged_records(self, path: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for record in self._event_logs.get(str(path), []):
            records.append(dict(record))
        return records

    def add_blob(self, blob_dir: Path, content: bytes, *, extension: str, metadata: Mapping[str, Any]) -> None:
        self._blobs.append(
            journal_blob_promotion(
                blob_dir,
                content,
                extension=extension,
                metadata=metadata,
            )
        )

    def add_event(self, path: Path, record: Mapping[str, Any]) -> None:
        self._event_logs[str(path)].append(dict(record))


class FileStore(Store):
    """Filesystem-backed Store implementation.

    The implementation favors compatibility and correctness over cleverness:
    records live as JSON files in a stable directory layout, and mutations flow
    through the journal helpers added to ``megaplan._core.io`` in Sprint 1.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._active_transaction: _FileStoreTransaction | None = None
        self.blobs = LocalDirBlobStore(self.root / "blobs")
        self._recover_all_journals()

    # ------------------------------------------------------------------
    # Journal / transaction helpers
    # ------------------------------------------------------------------

    def _recover_all_journals(self) -> None:
        recover_journal(self.root)
        epics_root = self.root / "epics"
        if epics_root.exists():
            for epic_dir in epics_root.iterdir():
                if epic_dir.is_dir():
                    recover_journal(epic_dir)

    def _journal_root_for_epic(self, epic_id: str | None) -> Path:
        return self._epic_dir(epic_id) if epic_id else self.root

    def _commit_write(
        self,
        path: Path,
        data: bytes,
        *,
        journal_root: Path,
    ) -> None:
        transaction = self._active_transaction
        if transaction is not None:
            transaction.add_write(path, data)
            return
        tx_id = _new_id("tx")
        prepare_journal_transaction(
            journal_root,
            tx_id,
            writes=[journal_bytes_write(path, data, tx_id=tx_id)],
        )
        commit_journal_transaction(journal_root, tx_id)

    def _commit_blob(
        self,
        blob_dir: Path,
        content: bytes,
        *,
        extension: str,
        metadata: Mapping[str, Any],
        journal_root: Path,
    ) -> None:
        transaction = self._active_transaction
        if transaction is not None:
            transaction.add_blob(blob_dir, content, extension=extension, metadata=metadata)
            return
        tx_id = _new_id("tx")
        prepare_journal_transaction(
            journal_root,
            tx_id,
            blobs=[journal_blob_promotion(blob_dir, content, extension=extension, metadata=metadata)],
        )
        commit_journal_transaction(journal_root, tx_id)

    def _commit_event(self, epic_id: str, record: Mapping[str, Any]) -> None:
        events_path = self._events_path(epic_id)
        transaction = self._active_transaction
        if transaction is not None:
            transaction.add_event(events_path, record)
            return
        tx_id = _new_id("tx")
        prepare_journal_transaction(
            self._journal_root_for_epic(epic_id),
            tx_id,
            event_logs=[journal_event_log(events_path, [record])],
        )
        commit_journal_transaction(self._journal_root_for_epic(epic_id), tx_id)

    def transaction(self, epic_id: str | None = None) -> AbstractContextManager[Transaction]:
        if self._active_transaction is not None:
            return _FileStoreTransaction(
                self,
                self._active_transaction.journal_root,
                joined=True,
                parent=self._active_transaction,
            )
        return _FileStoreTransaction(self, self._journal_root_for_epic(epic_id))

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _epic_dir(self, epic_id: str | None) -> Path:
        if not epic_id:
            return self.root
        return self.root / "epics" / epic_id

    def _epic_path(self, epic_id: str) -> Path:
        return self._epic_dir(epic_id) / "epic.json"

    def _body_path(self, epic_id: str) -> Path:
        return self._epic_dir(epic_id) / "body.md"

    def _checklist_dir(self, epic_id: str) -> Path:
        return self._epic_dir(epic_id) / "checklist"

    def _events_path(self, epic_id: str) -> Path:
        return self._epic_dir(epic_id) / "events.jsonl"

    def _messages_dir(self) -> Path:
        return self.root / "messages"

    def _turns_dir(self) -> Path:
        return self.root / "turns"

    def _tool_calls_dir(self) -> Path:
        return self.root / "tool_calls"

    def _system_logs_dir(self) -> Path:
        return self.root / "system_logs"

    def _external_requests_dir(self) -> Path:
        return self.root / "external_requests"

    def _images_dir(self) -> Path:
        return self.root / "images"

    def _feedback_dir(self) -> Path:
        return self.root / "feedback"

    def _second_opinions_dir(self) -> Path:
        return self.root / "second_opinions"

    def _codebases_dir(self) -> Path:
        return self.root / "codebases"

    def _code_artifacts_dir(self) -> Path:
        return self.root / "code_artifacts"

    def _leases_dir(self) -> Path:
        return self.root / "leases"

    def _locks_dir(self) -> Path:
        return self.root / "locks"

    def _control_messages_dir(self) -> Path:
        return self.root / "control_messages"

    def _progress_events_dir(self) -> Path:
        return self.root / "progress_events"

    def _resident_conversations_dir(self) -> Path:
        return self.root / "resident_conversations"

    def _scheduled_jobs_dir(self) -> Path:
        return self.root / "scheduled_jobs"

    def _cloud_runs_dir(self) -> Path:
        return self.root / "cloud_runs"

    def _automation_actors_dir(self) -> Path:
        return self.root / "automation_actors"

    def _migration_runs_dir(self) -> Path:
        return self.root / "migration_runs"

    def _message_path(self, message_id: str) -> Path:
        return self._messages_dir() / f"{message_id}.json"

    def _turn_path(self, turn_id: str) -> Path:
        return self._turns_dir() / f"{turn_id}.json"

    def _tool_call_path(self, tool_call_id: str) -> Path:
        return self._tool_calls_dir() / f"{tool_call_id}.json"

    def _system_log_path(self, log_id: str) -> Path:
        return self._system_logs_dir() / f"{log_id}.json"

    def _external_request_path(self, request_id: str) -> Path:
        return self._external_requests_dir() / f"{request_id}.json"

    def _image_path(self, image_id: str) -> Path:
        return self._images_dir() / f"{image_id}.json"

    def _feedback_path(self, feedback_id: str) -> Path:
        return self._feedback_dir() / f"{feedback_id}.json"

    def _second_opinion_path(self, opinion_id: str) -> Path:
        return self._second_opinions_dir() / f"{opinion_id}.json"

    def _codebase_path(self, codebase_id: str) -> Path:
        return self._codebases_dir() / f"{codebase_id}.json"

    def _code_artifact_path(self, artifact_id: str) -> Path:
        return self._code_artifacts_dir() / f"{artifact_id}.json"

    def _lease_path(self, plan_id: str) -> Path:
        return self._leases_dir() / f"{plan_id}.json"

    def _lock_path(self, epic_id: str) -> Path:
        return self._locks_dir() / f"{epic_id}.json"

    def _control_message_path(self, msg_id: str) -> Path:
        return self._control_messages_dir() / f"{msg_id}.json"

    def _progress_event_path(self, event_id: str) -> Path:
        return self._progress_events_dir() / f"{event_id}.json"

    def _resident_conversation_path(self, conversation_id: str) -> Path:
        return self._resident_conversations_dir() / f"{conversation_id}.json"

    def _scheduled_job_path(self, job_id: str) -> Path:
        return self._scheduled_jobs_dir() / f"{job_id}.json"

    def _cloud_run_path(self, run_id: str) -> Path:
        return self._cloud_runs_dir() / f"{run_id}.json"

    def _automation_actor_path(self, actor_id: str) -> Path:
        return self._automation_actors_dir() / f"{actor_id}.json"

    def _migration_run_path(self, migration_id: str) -> Path:
        return self._migration_runs_dir() / f"{migration_id}.json"

    def _sprint_dir(self, epic_id: str, sprint_id: str) -> Path:
        return self._epic_dir(epic_id) / "sprints" / sprint_id

    def _sprint_path(self, epic_id: str, sprint_id: str) -> Path:
        return self._sprint_dir(epic_id, sprint_id) / "sprint.json"

    def _sprint_items_dir(self, epic_id: str, sprint_id: str) -> Path:
        return self._sprint_dir(epic_id, sprint_id) / "items"

    def _checklist_path(self, epic_id: str, item_id: str) -> Path:
        return self._checklist_dir(epic_id) / f"{item_id}.json"

    def _plan_dir(self, plan_id: str, *, epic_id: str | None, sprint_id: str | None) -> Path:
        if epic_id is None:
            return self.root / "orphan_plans" / plan_id
        if sprint_id:
            return self._sprint_dir(epic_id, sprint_id) / "plans" / plan_id
        return self._epic_dir(epic_id) / "plans" / plan_id

    def _plan_path(self, plan_id: str, *, epic_id: str | None, sprint_id: str | None) -> Path:
        return self._plan_dir(plan_id, epic_id=epic_id, sprint_id=sprint_id) / "plan.json"

    def _plan_artifacts_dir(self, plan_id: str) -> Path:
        plan = self.load_plan(plan_id)
        if plan is None:
            raise FileNotFoundError(f"Unknown plan {plan_id}")
        return self._plan_dir(plan_id, epic_id=plan.epic_id, sprint_id=plan.sprint_id) / "artifacts"

    def _find_path(self, pattern: str) -> Path | None:
        for candidate in sorted(self.root.glob(pattern)):
            if candidate.is_file():
                return candidate
        return None

    def _find_checklist_path(self, item_id: str) -> Path | None:
        return self._find_path(f"epics/*/checklist/{item_id}.json")

    def _find_sprint_path(self, sprint_id: str) -> Path | None:
        return self._find_path(f"epics/*/sprints/{sprint_id}/sprint.json")

    def _find_plan_path(self, plan_id: str) -> Path | None:
        patterns = [
            f"orphan_plans/{plan_id}/plan.json",
            f"epics/*/plans/{plan_id}/plan.json",
            f"epics/*/sprints/*/plans/{plan_id}/plan.json",
        ]
        for pattern in patterns:
            path = self._find_path(pattern)
            if path is not None:
                return path
        return None

    # ------------------------------------------------------------------
    # Generic read/write helpers
    # ------------------------------------------------------------------

    def _load_model(self, path: Path, model_cls: Any) -> Any | None:
        staged = self._active_transaction.staged_bytes(path) if self._active_transaction is not None else None
        if staged is not None:
            return model_cls.model_validate(json.loads(staged.decode("utf-8")))
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return model_cls.model_validate(data)

    def _iter_models(self, directory: Path, model_cls: Any) -> list[Any]:
        paths = set(sorted(directory.glob("*.json"))) if directory.exists() else set()
        if self._active_transaction is not None:
            for entry in self._active_transaction._writes:
                target_path = Path(str(entry.get("target_path", "")))
                if target_path.parent == directory and target_path.suffix == ".json":
                    paths.add(target_path)
        models = []
        for path in sorted(paths):
            model = self._load_model(path, model_cls)
            if model is not None:
                models.append(model)
        return models

    def _save_model(self, path: Path, model: Any, *, journal_root: Path) -> None:
        self._commit_write(path, _model_bytes(model), journal_root=journal_root)

    def copy_entity_if_absent(self, entity_path: Path, model: Any, *, journal_root: Path) -> bool:
        if entity_path.exists():
            return False
        self._save_model(entity_path, model, journal_root=journal_root)
        return True

    def _delete_file(self, path: Path) -> None:
        if not path.exists():
            return
        path.unlink()
        fsync_dir(path.parent)

    def _delete_tree(self, path: Path) -> None:
        if not path.exists():
            return
        shutil.rmtree(path)
        fsync_dir(path.parent)

    def _require_expected_revision(self, current_revision: int, expected_revision: int | None) -> None:
        if expected_revision is not None and current_revision != expected_revision:
            raise RevisionConflict(
                f"expected revision {expected_revision}, found {current_revision}",
            )

    def _terminal_turn(self, status: str) -> bool:
        return status in _TERMINAL_TURN_STATUSES

    def _touch_updated_at(self, data: dict[str, Any], *, field_name: str = "updated_at") -> None:
        if field_name in data:
            data[field_name] = utc_now()

    def _update_model(
        self,
        path: Path,
        model_cls: Any,
        *,
        expected_revision: int | None = None,
        journal_root: Path,
        **changes: Any,
    ) -> Any:
        current = self._load_model(path, model_cls)
        if current is None:
            raise FileNotFoundError(path)
        data = current.model_dump()
        if "revision" in data:
            self._require_expected_revision(int(data["revision"]), expected_revision)
            data["revision"] = int(data["revision"]) + 1
        data.update(changes)
        if "updated_at" in data and "updated_at" not in changes:
            data["updated_at"] = utc_now()
        if "last_edited_at" in data and "last_edited_at" not in changes:
            data["last_edited_at"] = utc_now()
        if model_cls is BotTurn and self._terminal_turn(str(data.get("status"))) and not data.get("completed_at"):
            data["completed_at"] = utc_now()
        if model_cls is Feedback and data.get("resolved") and not data.get("resolved_at"):
            data["resolved_at"] = utc_now()
        updated = model_cls.model_validate(data)
        self._save_model(path, updated, journal_root=journal_root)
        return updated

    def _messages(self) -> list[Message]:
        return self._iter_models(self._messages_dir(), Message)

    def _turns(self) -> list[BotTurn]:
        return self._iter_models(self._turns_dir(), BotTurn)

    def _tool_calls(self) -> list[ToolCall]:
        return self._iter_models(self._tool_calls_dir(), ToolCall)

    def _system_logs(self) -> list[SystemLog]:
        return self._iter_models(self._system_logs_dir(), SystemLog)

    def _external_requests(self) -> list[ExternalRequest]:
        return self._iter_models(self._external_requests_dir(), ExternalRequest)

    def _images(self) -> list[Image]:
        return self._iter_models(self._images_dir(), Image)

    def _feedback_records(self) -> list[Feedback]:
        return self._iter_models(self._feedback_dir(), Feedback)

    def _second_opinions(self) -> list[SecondOpinion]:
        return self._iter_models(self._second_opinions_dir(), SecondOpinion)

    def _codebases(self) -> list[Codebase]:
        return self._iter_models(self._codebases_dir(), Codebase)

    def _code_artifacts(self) -> list[CodeArtifact]:
        return self._iter_models(self._code_artifacts_dir(), CodeArtifact)

    def _control_messages(self) -> list[ControlMessage]:
        return self._iter_models(self._control_messages_dir(), ControlMessage)

    def _progress_events(self) -> list[ProgressEvent]:
        return self._iter_models(self._progress_events_dir(), ProgressEvent)

    def _resident_conversations(self) -> list[ResidentConversation]:
        return self._iter_models(self._resident_conversations_dir(), ResidentConversation)

    def _scheduled_jobs(self) -> list[ScheduledJob]:
        return self._iter_models(self._scheduled_jobs_dir(), ScheduledJob)

    def _cloud_runs(self) -> list[CloudRun]:
        return self._iter_models(self._cloud_runs_dir(), CloudRun)

    def _automation_actors(self) -> list[AutomationActor]:
        return self._iter_models(self._automation_actors_dir(), AutomationActor)

    def _migration_runs(self) -> list[MigrationRun]:
        return self._iter_models(self._migration_runs_dir(), MigrationRun)

    def _epics(self) -> list[Epic]:
        epics_root = self.root / "epics"
        if not epics_root.exists():
            return []
        epics: list[Epic] = []
        for path in sorted(epics_root.glob("*/epic.json")):
            epic = self._load_model(path, Epic)
            if epic is not None:
                epics.append(epic)
        return epics

    def _checklist_items(self, epic_id: str) -> list[ChecklistItem]:
        items = self._iter_models(self._checklist_dir(epic_id), ChecklistItem)
        return sorted(items, key=lambda item: (item.position, item.id))

    def _sprints(self, epic_id: str) -> list[Sprint]:
        sprints_root = self._epic_dir(epic_id) / "sprints"
        if not sprints_root.exists():
            return []
        sprints: list[Sprint] = []
        for path in sorted(sprints_root.glob("*/sprint.json")):
            sprint = self._load_model(path, Sprint)
            if sprint is not None:
                sprints.append(sprint)
        return sorted(sprints, key=lambda sprint: (sprint.sprint_number, sprint.id))

    def _plan_roots(self) -> list[Path]:
        roots: list[Path] = []
        orphan_root = self.root / "orphan_plans"
        if orphan_root.exists():
            roots.extend(path for path in sorted(orphan_root.iterdir()) if path.is_dir())
        epics_root = self.root / "epics"
        if epics_root.exists():
            for epic_dir in sorted(path for path in epics_root.iterdir() if path.is_dir()):
                direct_plans = epic_dir / "plans"
                if direct_plans.exists():
                    roots.extend(path for path in sorted(direct_plans.iterdir()) if path.is_dir())
                sprint_root = epic_dir / "sprints"
                if sprint_root.exists():
                    for sprint_dir in sorted(path for path in sprint_root.iterdir() if path.is_dir()):
                        plans_dir = sprint_dir / "plans"
                        if plans_dir.exists():
                            roots.extend(path for path in sorted(plans_dir.iterdir()) if path.is_dir())
        return roots

    def _plans(self) -> list[Plan]:
        plans: list[Plan] = []
        for plan_dir in self._plan_roots():
            plan = self._load_model(plan_dir / "plan.json", Plan)
            if plan is not None:
                plans.append(plan)
        return sorted(plans, key=lambda plan: (plan.name, plan.id))

    def _artifact_ref(self, plan_id: str, path: Path, *, artifact_root: Path | None = None) -> ArtifactRef:
        stat = path.stat()
        name = path.name if artifact_root is None else path.relative_to(artifact_root).as_posix()
        return ArtifactRef(
            plan_id=plan_id,
            name=name,
            size_bytes=stat.st_size,
            sha256=self._sha256_bytes(path.read_bytes()),
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    def _sha256_bytes(self, content: bytes) -> str:
        import hashlib

        return "sha256:" + hashlib.sha256(content).hexdigest()

    # ------------------------------------------------------------------
    # Epic + body
    # ------------------------------------------------------------------

    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
        home_backend: str = "file",
        idempotency_key: str | None = None,
    ) -> Epic:
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
        return epic

    def load_epic(self, epic_id: str) -> Epic | None:
        return self._load_model(self._epic_path(epic_id), Epic)

    def update_epic(self, epic_id: str, *, expected_revision: int, idempotency_key: str | None = None, **changes: Any) -> Epic:
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

    # ------------------------------------------------------------------
    # Checklist
    # ------------------------------------------------------------------

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
        journal_root = self._journal_root_for_epic(epic_id)
        with self.transaction(epic_id):
            for entry in items:
                position = entry.position or next_position
                next_position = max(next_position, position + 1)
                item = ChecklistItem(
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
                self._save_model(self._checklist_path(epic_id, item.id), item, journal_root=journal_root)
                created.append(item)
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

    # ------------------------------------------------------------------
    # Sprints
    # ------------------------------------------------------------------

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
        items_dir = self._sprint_items_dir(sprint.epic_id, sprint.id)
        self._delete_tree(items_dir)
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
            self._save_model(items_dir / f"{item.id}.json", item, journal_root=self._journal_root_for_epic(sprint.epic_id))
            created.append(item)
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

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

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
        event = EpicEvent(
            id=_new_id("evt"),
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
            occurred_at=utc_now(),
        )
        self._commit_event(epic_id, event.model_dump(mode="json"))
        return event

    def list_epic_events(
        self,
        epic_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[EpicEvent]:
        events_path = self._events_path(epic_id)
        events = [
            EpicEvent.model_validate({key: value for key, value in record.items() if key != "tx_id"})
            for record in read_committed_framed_json_records(events_path)
        ]
        if self._active_transaction is not None:
            events.extend(
                EpicEvent.model_validate(record)
                for record in self._active_transaction.staged_records(events_path)
            )
        since_dt = _parse_datetime(since)
        until_dt = _parse_datetime(until)
        filtered: list[EpicEvent] = []
        for event in events:
            if kinds and event.event_type not in kinds:
                continue
            if since_dt and event.occurred_at < since_dt:
                continue
            if until_dt and event.occurred_at > until_dt:
                continue
            filtered.append(event)
        filtered.sort(key=lambda event: (event.occurred_at, event.id), reverse=True)
        if limit is not None:
            return filtered[:limit]
        return filtered

    def list_epic_events_for_replay(self, epic_id: str) -> list[EpicEvent]:
        events = self.list_epic_events(epic_id, limit=None)
        return sorted(events, key=lambda event: (event.occurred_at, event.id))

    def latest_transaction_id(self, epic_id: str) -> str | None:
        events = self.list_epic_events(epic_id)
        if not events:
            return None
        return events[0].transaction_id

    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
        results: list[EpicEvent] = []
        for epic in self._epics():
            results.extend(
                event
                for event in self.list_epic_events_for_replay(epic.id)
                if event.transaction_id == transaction_id
            )
        results.sort(key=lambda event: (event.occurred_at, event.id))
        return results

    # ------------------------------------------------------------------
    # Messages / turns / tools / logs
    # ------------------------------------------------------------------

    def _next_invocation_message_id(self, turn_id: str) -> str:
        count = sum(1 for row in self._messages() if row.bot_turn_id == turn_id and row.direction == "outbound")
        return f"inv_{turn_id}_{count + 1}"

    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
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
        if idempotency_key is not None:
            for existing in self._messages():
                if existing.idempotency_key == idempotency_key:
                    return existing
        if synthesize_outbound_id and direction == "outbound" and discord_message_id is None and bot_turn_id:
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        message = Message(
            id=_new_id("msg"),
            epic_id=epic_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            direction=direction,
            content=content,
            sent_at=utc_now(),
            discord_message_id=discord_message_id,
            has_code_attachment=has_code_attachment,
            has_image_attachment=has_image_attachment,
            in_burst_with=list(in_burst_with or []),
            was_voice_message=was_voice_message,
            audio_storage_url=audio_storage_url,
            transcription_metadata=transcription_metadata,
            bot_turn_id=bot_turn_id,
        )
        self._save_model(self._message_path(message.id), message, journal_root=self.root)
        return message

    def load_message(self, message_id: str) -> Message | None:
        return self._load_model(self._message_path(message_id), Message)

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        by_id = {message.id: message for message in self._messages()}
        return [by_id[msg_id] for msg_id in message_ids if msg_id in by_id]

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        return self._update_model(
            self._message_path(message_id),
            Message,
            journal_root=self.root,
            **changes,
        )

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        messages = [row for row in self._messages() if row.direction == "outbound"]
        if epic_id is not None:
            messages = [row for row in messages if row.epic_id == epic_id]
        messages.sort(key=lambda row: (_utc_key(row.sent_at), row.id), reverse=True)
        return messages[0] if messages else None

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
        turn = BotTurn(
            id=_new_id("turn"),
            epic_id=epic_id,
            triggered_by_message_ids=list(triggered_by_message_ids),
            prompt_snapshot=prompt_snapshot,
            prompt_version=prompt_version,
            status="in_progress",
            state_at_turn=state_at_turn,
            model_version=model_version,
            started_at=utc_now(),
        )
        self._save_model(self._turn_path(turn.id), turn, journal_root=self.root)
        return turn

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        return self._update_model(self._turn_path(turn_id), BotTurn, journal_root=self.root, **changes)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        return sorted(
            [
                turn
                for turn in self._turns()
                if turn.status == "in_progress" and turn.started_at <= cutoff
            ],
            key=lambda turn: (turn.started_at, turn.id),
        )

    def list_recent_turns(self, *, n: int = 10, epic_id: str | None = None) -> list[BotTurn]:
        turns = self._turns()
        if epic_id is not None:
            turns = [turn for turn in turns if turn.epic_id == epic_id]
        turns.sort(key=lambda turn: (_utc_key(turn.started_at), turn.id), reverse=True)
        return turns[:n]

    def search_messages(self, *, query: str, epic_id: str | None = None, limit: int = 20) -> list[MessageSearchHit]:
        needle = normalize_text(query)
        hits: list[tuple[int, Message]] = []
        for message in self._messages():
            if epic_id is not None and message.epic_id != epic_id:
                continue
            content = normalize_text(message.content)
            if needle in content:
                hits.append((content.count(needle), message))
        hits.sort(key=lambda item: (-item[0], item[1].id))
        return [
            MessageSearchHit.model_validate({**msg.model_dump(mode="json"), "rank": score})
            for score, msg in hits[:limit]
        ]

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        tool_call = ToolCall(
            id=_new_id("tool"),
            turn_id=turn_id,
            tool_name=tool_name,
            operation_kind=operation_kind,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            called_at=utc_now(),
        )
        self._save_model(self._tool_call_path(tool_call.id), tool_call, journal_root=self.root)
        return tool_call

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[ToolCall]:
        since_dt = _parse_datetime(since)
        turns_by_id = {turn.id: turn for turn in self._turns()}
        matches: list[ToolCall] = []
        for row in self._tool_calls():
            if tool_name is not None and row.tool_name != tool_name:
                continue
            if epic_id is not None and turns_by_id.get(row.turn_id, BotTurn(id="", status="in_progress")).epic_id != epic_id:
                continue
            if since_dt and row.called_at < since_dt:
                continue
            matches.append(row)
        matches.sort(key=lambda row: (_utc_key(row.called_at), row.id), reverse=True)
        return matches[:limit]

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        log = SystemLog(
            id=_new_id("log"),
            level=level,
            category=category,
            event_type=event_type,
            message=message,
            details=details or {},
            turn_id=turn_id,
            epic_id=epic_id,
            occurred_at=utc_now(),
        )
        self._save_model(self._system_log_path(log.id), log, journal_root=self.root)
        return log

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        recent_messages = self.search_messages(query="", epic_id=epic_id, limit=10) if False else []
        messages = [msg for msg in self._messages() if msg.epic_id == epic_id]
        messages.sort(key=lambda msg: (_utc_key(msg.sent_at), msg.id), reverse=True)
        tool_calls = self.search_tool_calls_by(epic_id=epic_id, limit=10)
        feedback = self.list_feedback(epic_id=epic_id, active=True, limit=20)
        unresolved = [
            item
            for item in self.list_observations(resolved=False, limit=20)
            if item.epic_id == epic_id
        ]
        sprints = self.list_sprints_with_items(epic_id) if epic_id else []
        active_images = self.list_active_images(epic_id) if epic_id else []
        opinions = self.list_second_opinions(epic_id, limit=10) if epic_id else []
        all_pending = bool(sprints) and all(sprint.status == "pending" for sprint in sprints)
        return HotContext(
            epic=self.load_epic(epic_id) if epic_id else None,
            recent_messages=messages[:10],
            recent_tool_calls=tool_calls,
            active_feedback=feedback,
            unresolved_observations=unresolved,
            sprints=sprints,
            codebases=self.list_codebases(epic_id=epic_id),
            recent_code_artifacts=self.list_code_artifacts(epic_id=epic_id, limit=10),
            active_images=active_images,
            recent_second_opinions=opinions,
            all_sprints_pending_no_queued=all_pending and not any(sprint.status == "queued" for sprint in sprints),
        )

    def find_unprocessed_messages(self, epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[Message]:
        start_dt = _parse_datetime(started_at)
        return sorted(
            [
                msg
                for msg in self._messages()
                if msg.epic_id == epic_id
                and msg.direction == "inbound"
                and msg.bot_turn_id is None
                and msg.id not in set(exclude_ids)
                and (start_dt is None or msg.sent_at >= start_dt)
            ],
            key=lambda msg: (msg.sent_at, msg.id),
        )

    # ------------------------------------------------------------------
    # External requests
    # ------------------------------------------------------------------

    def insert_pending(
        self,
        *,
        idempotency_key: str,
        provider: str,
        endpoint: str,
        request_summary: dict[str, Any],
        request_body: dict[str, Any] | None = None,
        turn_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> ExternalRequest:
        if any(row.idempotency_key == idempotency_key for row in self._external_requests()):
            raise ValueError(f"duplicate idempotency_key: {idempotency_key}")
        request = ExternalRequest(
            id=_new_id("req"),
            idempotency_key=idempotency_key,
            provider=provider,
            endpoint=endpoint,
            tool_call_id=tool_call_id,
            turn_id=turn_id,
            request_summary=request_summary,
            request_body=request_body,
            status="pending",
            attempt_count=1,
            first_attempted_at=utc_now(),
            last_attempted_at=utc_now(),
        )
        self._save_model(self._external_request_path(request.id), request, journal_root=self.root)
        return request

    def _update_external_request(self, request_id: str, **changes: Any) -> ExternalRequest:
        return self._update_model(self._external_request_path(request_id), ExternalRequest, journal_root=self.root, **changes)

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        return self._update_external_request(
            request_id,
            status="confirmed",
            provider_request_id=provider_request_id,
            provider_response_summary=provider_response_summary,
            completed_at=utc_now(),
            last_attempted_at=utc_now(),
        )

    def mark_failed(self, request_id: str, *, error_details: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        return self._update_external_request(
            request_id,
            status="failed",
            error_details=error_details,
            completed_at=utc_now(),
            last_attempted_at=utc_now(),
        )

    def find_pending_external_requests(self, older_than_seconds: int) -> list[ExternalRequest]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        return sorted(
            [
                row
                for row in self._external_requests()
                if row.status == "pending" and row.last_attempted_at <= cutoff
            ],
            key=lambda row: (row.last_attempted_at, row.id),
        )

    def mark_orphaned(self, request_id: str, *, error_details: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        return self._update_external_request(
            request_id,
            status="orphaned",
            error_details=error_details,
            completed_at=utc_now(),
            last_attempted_at=utc_now(),
        )

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def _next_image_reference(self, source: str) -> str:
        prefix = _SOURCE_REFERENCE_PREFIX.get(source, f"img_{source}")
        count = sum(1 for row in self._images() if row.source == source)
        return f"{prefix}_{count + 1}"

    def create_image(
        self,
        *,
        epic_id: str,
        source: str,
        storage_url: str,
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        reference_key: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = False,
        active: bool = True,
        discord_attachment_id: str | None = None,
        blob_backend: str | None = None,
        blob_id: str | None = None,
        blob_sha256: str | None = None,
        blob_size_bytes: int | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        ref = reference_key or self._next_image_reference(source)
        if active:
            self.deactivate_active_image_reference(epic_id, ref)
        image = Image(
            id=_new_id("img"),
            epic_id=epic_id,
            source=source,
            prompt=prompt,
            storage_url=storage_url,
            quality=quality,
            size=size,
            created_at=utc_now(),
            reference_key=ref,
            description=description,
            caption=caption,
            in_body=in_body,
            active=active,
            discord_attachment_id=discord_attachment_id,
            blob_backend=blob_backend,
            blob_id=blob_id,
            blob_sha256=blob_sha256,
            blob_size_bytes=blob_size_bytes,
            content_type=content_type,
        )
        self._save_model(self._image_path(image.id), image, journal_root=self.root)
        return image

    def attach_image(
        self,
        *,
        epic_id: str,
        content: bytes,
        content_type: str,
        reference_key: str,
        source: str = "user_uploaded",
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = True,
        idempotency_key: str | None = None,
    ) -> Image:
        digest = hashlib.sha256(content).hexdigest()
        blob_id = f"{epic_id}/{reference_key}/{digest}"
        with self.transaction(epic_id):
            extension = (mimetypes.guess_extension(content_type, strict=False) or ".bin").lstrip(".")
            blob_dir = self.blobs._blob_dir(blob_id)
            metadata = {
                "blob_id": blob_id,
                "content_type": content_type,
                "size_bytes": len(content),
                "updated_at": utc_now().isoformat().replace("+00:00", "Z"),
            }
            self._commit_blob(
                blob_dir,
                content,
                extension=extension,
                metadata=metadata,
                journal_root=self._journal_root_for_epic(epic_id),
            )
            return self.create_image(
                epic_id=epic_id,
                source=source,
                storage_url=str(blob_dir / f"data.{extension}"),
                prompt=prompt,
                quality=quality,
                size=size,
                reference_key=reference_key,
                description=description,
                caption=caption,
                in_body=in_body,
                active=True,
                blob_backend="file",
                blob_id=blob_id,
                blob_sha256=digest,
                blob_size_bytes=len(content),
                content_type=content_type,
                idempotency_key=idempotency_key,
            )

    def resolve_image_reference(
        self,
        epic_id: str,
        reference: str,
        *,
        signed: bool = False,
        ttl: int = 3600,
    ) -> str | None:
        key = reference.removeprefix("mp://image/").removeprefix("image:")
        image = self.load_active_image_by_reference(epic_id, key)
        if image is None:
            return None
        if image.blob_id:
            return self.blobs.url(image.blob_id, signed=signed, ttl=ttl)
        return image.storage_url

    def load_image(self, image_id: str) -> Image | None:
        return self._load_model(self._image_path(image_id), Image)

    def list_images(self, *, epic_id: str, source: str | None = None, active: bool | None = True) -> list[Image]:
        images = [row for row in self._images() if row.epic_id == epic_id]
        if source is not None:
            images = [row for row in images if row.source == source]
        if active is not None:
            images = [row for row in images if row.active == active]
        images.sort(key=lambda row: (row.created_at, row.id))
        return images

    def update_image(self, image_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Image:
        if changes.get("active") and changes.get("reference_key"):
            epic_id = changes.get("epic_id") or (self.load_image(image_id).epic_id if self.load_image(image_id) else None)
            if epic_id:
                self.deactivate_active_image_reference(epic_id, changes["reference_key"])
        return self._update_model(self._image_path(image_id), Image, journal_root=self.root, **changes)

    def list_active_images(self, epic_id: str) -> list[Image]:
        return self.list_images(epic_id=epic_id, active=True)

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> Image | None:
        for image in self.list_active_images(epic_id):
            if image.reference_key == reference_key:
                return image
        return None

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        return self.load_active_image_by_reference(epic_id, reference_key) is not None

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str,
        *,
        idempotency_key: str | None = None,
    ) -> list[Image]:
        updated: list[Image] = []
        for image in self.list_active_images(epic_id):
            if image.reference_key != reference_key:
                continue
            updated.append(self.update_image(image.id, active=False))
        return updated

    # ------------------------------------------------------------------
    # Second opinions
    # ------------------------------------------------------------------

    def create_second_opinion(
        self,
        *,
        epic_id: str,
        requested_by: str,
        focus_areas: Sequence[str],
        raw_response: str,
        score: int,
        summary: str,
        verdict: str,
        model_used: str,
        resulting_checklist_item_ids: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        opinion = SecondOpinion(
            id=_new_id("opinion"),
            epic_id=epic_id,
            requested_at=utc_now(),
            requested_by=requested_by,
            focus_areas=list(focus_areas),
            raw_response=raw_response,
            score=score,
            summary=summary,
            verdict=verdict,
            resulting_checklist_item_ids=list(resulting_checklist_item_ids or []),
            model_used=model_used,
        )
        self._save_model(self._second_opinion_path(opinion.id), opinion, journal_root=self.root)
        return opinion

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[SecondOpinion]:
        opinions = [row for row in self._second_opinions() if row.epic_id == epic_id]
        opinions.sort(key=lambda row: (_utc_key(row.requested_at), row.id), reverse=True)
        return opinions[:limit] if limit is not None else opinions

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        return self._update_model(
            self._second_opinion_path(second_opinion_id),
            SecondOpinion,
            journal_root=self.root,
            resulting_checklist_item_ids=list(checklist_item_ids),
        )

    # ------------------------------------------------------------------
    # Codebases / code artifacts
    # ------------------------------------------------------------------

    def create_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        codebase_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        codebase = Codebase(
            id=codebase_id or _new_id("codebase"),
            owner=owner.lower(),
            name=name.lower(),
            default_branch=default_branch,
            scope=scope,
            group_name=group_name,
            associated_epic_id=associated_epic_id,
            added_at=utc_now(),
            added_via=added_via,
            verified_accessible_at=_parse_datetime(verified_accessible_at),
            notes=notes,
        )
        self._save_model(self._codebase_path(codebase.id), codebase, journal_root=self.root)
        return codebase

    def upsert_codebase(self, *, idempotency_key: str | None = None,
        **fields: Any) -> Codebase:
        existing = self.find_codebase(fields["owner"], fields["name"])
        if existing is None:
            return self.create_codebase(**fields)
        return self.update_codebase(existing.id, **fields)

    def load_codebase(self, codebase_id: str) -> Codebase | None:
        return self._load_model(self._codebase_path(codebase_id), Codebase)

    def find_codebase(self, owner: str, name: str) -> Codebase | None:
        owner_l = owner.lower()
        name_l = name.lower()
        for codebase in self._codebases():
            if codebase.owner == owner_l and codebase.name == name_l:
                return codebase
        return None

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[Codebase]:
        codebases = self._codebases()
        if scope is not None:
            codebases = [row for row in codebases if row.scope == scope]
        if group_name is not None:
            codebases = [row for row in codebases if row.group_name == group_name]
        if epic_id is not None:
            codebases = [
                row
                for row in codebases
                if row.associated_epic_id == epic_id or (include_global and row.scope == "global")
            ]
        elif not include_global:
            codebases = [row for row in codebases if row.scope != "global"]
        codebases.sort(key=lambda row: (row.owner, row.name, row.id))
        return codebases

    def update_codebase(self, codebase_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Codebase:
        if "owner" in changes:
            changes["owner"] = changes["owner"].lower()
        if "name" in changes:
            changes["name"] = changes["name"].lower()
        return self._update_model(self._codebase_path(codebase_id), Codebase, journal_root=self.root, **changes)

    def remove_codebase(self, codebase_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._delete_file(self._codebase_path(codebase_id))

    def touch_codebase_accessed(self, codebase_id: str, *, accessed_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        return self.update_codebase(codebase_id, last_accessed_at=_parse_datetime(accessed_at) or utc_now())

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        changes: dict[str, Any] = {"verified_accessible_at": _parse_datetime(verified_at) or utc_now()}
        if default_branch is not None:
            changes["default_branch"] = default_branch
        return self.update_codebase(codebase_id, **changes)

    def create_code_artifact(
        self,
        *,
        kind: str,
        source: str,
        content: str,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        line_range: Any = None,
        scope: str | None = None,
        content_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        expires_at: str | None = None,
        artifact_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        artifact = CodeArtifact(
            id=artifact_id or _new_id("artifact"),
            codebase_id=codebase_id,
            epic_id=epic_id,
            kind=kind,
            source=source,
            file_path=file_path,
            line_range=line_range,
            scope=scope,
            content=content,
            content_summary=content_summary,
            metadata=metadata or {},
            created_at=utc_now(),
            expires_at=_parse_datetime(expires_at),
        )
        self._save_model(self._code_artifact_path(artifact.id), artifact, journal_root=self.root)
        return artifact

    def load_code_artifact(self, artifact_id: str) -> CodeArtifact | None:
        return self._load_model(self._code_artifact_path(artifact_id), CodeArtifact)

    def list_code_artifacts(
        self,
        *,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        kind: str | None = None,
        source: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        include_expired: bool = True,
        limit: int | None = 50,
    ) -> list[CodeArtifact]:
        now_dt = datetime.now(UTC)
        artifacts = self._code_artifacts()
        filtered: list[CodeArtifact] = []
        for artifact in artifacts:
            if codebase_id is not None and artifact.codebase_id != codebase_id:
                continue
            if epic_id is not None and artifact.epic_id != epic_id:
                continue
            if kind is not None and artifact.kind != kind:
                continue
            if source is not None and artifact.source != source:
                continue
            if file_path is not None and artifact.file_path != file_path:
                continue
            if scope is not None and artifact.scope != scope:
                continue
            if not include_expired and artifact.expires_at is not None and artifact.expires_at <= now_dt:
                continue
            filtered.append(artifact)
        filtered.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        if limit is not None:
            return filtered[:limit]
        return filtered

    def update_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> CodeArtifact:
        return self._update_model(self._code_artifact_path(artifact_id), CodeArtifact, journal_root=self.root, **changes)

    def delete_code_artifact(self, artifact_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._delete_file(self._code_artifact_path(artifact_id))

    def touch_code_artifact_used(self, artifact_id: str, *, used_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        return self.update_code_artifact(artifact_id, last_used_at=_parse_datetime(used_at) or utc_now())

    def get_api_cache(self, cache_key: str, *, now: str | None = None, touch: bool = True) -> CodeArtifact | None:
        now_dt = _parse_datetime(now) or datetime.now(UTC)
        for artifact in self._code_artifacts():
            if artifact.kind != "api_cache":
                continue
            if artifact.metadata.get("cache_key") != cache_key:
                continue
            if artifact.expires_at is not None and artifact.expires_at <= now_dt:
                return None
            if touch:
                return self.touch_code_artifact_used(artifact.id)
            return artifact
        return None

    def upsert_api_cache(
        self,
        *,
        cache_key: str,
        content: str,
        content_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        expires_at: str | None = None,
        ttl_seconds: int = 3600,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        existing = self.get_api_cache(cache_key, touch=False)
        expiry = _parse_datetime(expires_at) or (datetime.now(UTC) + timedelta(seconds=ttl_seconds))
        merged_metadata = dict(metadata or {})
        merged_metadata["cache_key"] = cache_key
        if existing is None:
            return self.create_code_artifact(
                kind="api_cache",
                source="conversation",
                content=content,
                codebase_id=codebase_id,
                epic_id=epic_id,
                file_path=file_path,
                scope=scope,
                content_summary=content_summary,
                metadata=merged_metadata,
                expires_at=expiry.isoformat().replace("+00:00", "Z"),
            )
        return self.update_code_artifact(
            existing.id,
            content=content,
            content_summary=content_summary,
            metadata=merged_metadata,
            codebase_id=codebase_id,
            epic_id=epic_id,
            file_path=file_path,
            scope=scope,
            expires_at=expiry,
        )

    def cleanup_expired_api_cache(self, *, now: str | None = None,
        idempotency_key: str | None = None,
    ) -> int:
        now_dt = _parse_datetime(now) or datetime.now(UTC)
        expired = [
            artifact
            for artifact in self._code_artifacts()
            if artifact.kind == "api_cache" and artifact.expires_at is not None and artifact.expires_at <= now_dt
        ]
        for artifact in expired:
            self.delete_code_artifact(artifact.id)
        return len(expired)

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def create_feedback(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        source_message_id: str | None = None,
        epic_id: str | None = None,
        turn_id: str | None = None,
        context_snapshot: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Feedback:
        feedback = Feedback(
            id=_new_id("fb"),
            kind=kind,
            content=content,
            source=source,
            source_message_id=source_message_id,
            epic_id=epic_id,
            turn_id=turn_id,
            context_snapshot=context_snapshot,
            created_at=utc_now(),
        )
        self._save_model(self._feedback_path(feedback.id), feedback, journal_root=self.root)
        return feedback

    def load_feedback(self, feedback_id: str) -> Feedback | None:
        return self._load_model(self._feedback_path(feedback_id), Feedback)

    def update_feedback(self, feedback_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Feedback:
        return self._update_model(self._feedback_path(feedback_id), Feedback, journal_root=self.root, **changes)

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        feedback = self._feedback_records()
        if epic_id is not None:
            feedback = [row for row in feedback if row.epic_id == epic_id]
        if active is not None:
            feedback = [row for row in feedback if row.active == active]
        if kinds is not None:
            allowed = set(kinds)
            feedback = [row for row in feedback if row.kind in allowed]
        feedback.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        return feedback[:limit] if limit is not None else feedback

    def list_observations(self, *, resolved: bool | None = None, limit: int | None = None) -> list[Feedback]:
        feedback = [row for row in self._feedback_records() if row.kind in _OBSERVATION_KINDS]
        if resolved is not None:
            feedback = [row for row in feedback if row.resolved == resolved]
        feedback.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        return feedback[:limit] if limit is not None else feedback

    # ------------------------------------------------------------------
    # Plans / artifacts
    # ------------------------------------------------------------------

    def create_plan(
        self,
        *,
        sprint_id: str | None,
        epic_id: str | None,
        name: str,
        idea: str,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> Plan:
        now_dt = utc_now()
        plan_id = fields.pop("plan_id", name)
        plan = Plan(
            id=plan_id,
            name=name,
            epic_id=epic_id,
            sprint_id=sprint_id,
            revision=int(fields.pop("revision", 0)),
            idea=idea,
            current_state=fields.pop("current_state", "initialized"),
            iteration=int(fields.pop("iteration", 1)),
            config=dict(fields.pop("config", {})),
            sessions=dict(fields.pop("sessions", {})),
            plan_versions=list(fields.pop("plan_versions", [])),
            history=list(fields.pop("history", [])),
            meta=dict(fields.pop("meta", {})),
            last_gate=dict(fields.pop("last_gate", {})),
            active_step=fields.pop("active_step", None),
            clarification=fields.pop("clarification", None),
            latest_finalize=fields.pop("latest_finalize", None),
            latest_review=fields.pop("latest_review", None),
            latest_execution=fields.pop("latest_execution", None),
            latest_failure=fields.pop("latest_failure", None),
            resume_cursor=fields.pop("resume_cursor", None),
            artifacts=list(fields.pop("artifacts", [])),
            created_at=_parse_datetime(fields.pop("created_at", now_dt)) or now_dt,
            updated_at=_parse_datetime(fields.pop("updated_at", now_dt)) or now_dt,
        )
        self._save_model(
            self._plan_path(plan.id, epic_id=epic_id, sprint_id=sprint_id),
            plan,
            journal_root=self._journal_root_for_epic(epic_id),
        )
        return plan

    def load_plan(self, plan_id: str) -> Plan | None:
        path = self._find_plan_path(plan_id)
        return self._load_model(path, Plan) if path is not None else None

    def update_plan(self, plan_id: str, *, expected_revision: int, idempotency_key: str | None = None, **changes: Any) -> Plan:
        current = self.load_plan(plan_id)
        if current is None:
            raise FileNotFoundError(plan_id)
        self._require_expected_revision(current.revision, expected_revision)
        data = current.model_dump()
        data.update(changes)
        data["revision"] = current.revision + 1
        data["updated_at"] = utc_now()
        updated = Plan.model_validate(data)
        self._save_model(
            self._plan_path(plan_id, epic_id=updated.epic_id, sprint_id=updated.sprint_id),
            updated,
            journal_root=self._journal_root_for_epic(updated.epic_id),
        )
        return updated

    def list_plans(
        self,
        *,
        sprint_id: str | None = None,
        epic_id: str | None = None,
        include_orphans: bool = False,
    ) -> list[Plan]:
        plans = self._plans()
        if sprint_id is not None:
            plans = [plan for plan in plans if plan.sprint_id == sprint_id]
        if epic_id is not None:
            plans = [plan for plan in plans if plan.epic_id == epic_id]
        elif not include_orphans:
            plans = [plan for plan in plans if plan.epic_id is not None]
        return plans

    def read_plan_artifact(self, plan_id: str, name: str) -> bytes | None:
        path = self._plan_artifact_path(plan_id, name)
        return path.read_bytes() if path.is_file() else None

    def write_plan_artifact(
        self,
        plan_id: str,
        name: str,
        data: bytes,
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactRef:
        plan = self.load_plan(plan_id)
        if plan is None:
            raise FileNotFoundError(plan_id)
        self._require_expected_revision(plan.revision, expected_revision)
        artifact_path = self._plan_artifact_path(plan_id, name)
        self._commit_write(artifact_path, data, journal_root=self._journal_root_for_epic(plan.epic_id))
        return self._artifact_ref(plan_id, artifact_path, artifact_root=self._plan_artifacts_dir(plan_id))

    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]:
        artifact_dir = self._plan_artifacts_dir(plan_id)
        if not artifact_dir.exists():
            return []
        refs = [
            self._artifact_ref(plan_id, path, artifact_root=artifact_dir)
            for path in sorted(artifact_dir.rglob("*"))
            if path.is_file()
        ]
        refs.sort(key=lambda ref: ref.name)
        return refs

    def stat_plan_artifact(self, plan_id: str, name: str) -> ArtifactStat | None:
        path = self._plan_artifact_path(plan_id, name)
        if not path.is_file():
            return None
        stat = path.stat()
        return ArtifactStat(
            plan_id=plan_id,
            name=name,
            size_bytes=stat.st_size,
            sha256=self._sha256_bytes(path.read_bytes()),
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    def _plan_artifact_path(self, plan_id: str, name: str) -> Path:
        safe_name = validate_plan_artifact_name(name)
        return self._plan_artifacts_dir(plan_id) / safe_name

    # ------------------------------------------------------------------
    # Migration run audit helpers
    # ------------------------------------------------------------------

    def save_migration_run(self, run: MigrationRun) -> MigrationRun:
        self._save_model(self._migration_run_path(run.id), run, journal_root=self.root)
        return run

    def create_migration_run(self, run: MigrationRun) -> MigrationRun:
        path = self._migration_run_path(run.id)
        if path.exists():
            raise FileExistsError(run.id)
        return self.save_migration_run(run)

    def load_migration_run(self, migration_id: str) -> MigrationRun | None:
        return self._load_model(self._migration_run_path(migration_id), MigrationRun)

    def update_migration_run(self, migration_id: str, **changes: Any) -> MigrationRun:
        current = self.load_migration_run(migration_id)
        if current is None:
            raise FileNotFoundError(migration_id)
        data = current.model_dump()
        data.update(changes)
        data["updated_at"] = utc_now()
        updated = MigrationRun.model_validate(data)
        self.save_migration_run(updated)
        return updated

    def heartbeat_migration(self, migration_id: str, ttl_seconds: int) -> MigrationRun:
        return self.update_migration_run(
            migration_id,
            updated_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )

    def find_active_migration_for_epic(self, epic_id: str) -> MigrationRun | None:
        """Audit-only local migration lookup; DB migration_runs coordinate correctness."""
        active = [
            run
            for run in self._migration_runs()
            if run.epic_id == epic_id
            and run.completed_at is None
            and run.expires_at > datetime.now(UTC)
        ]
        active.sort(key=lambda run: run.started_at, reverse=True)
        return active[0] if active else None

    # ------------------------------------------------------------------
    # Leases / locks
    # ------------------------------------------------------------------

    def acquire_execution_lease(
        self,
        plan_id: str,
        holder_id: str,
        worker_kind: str,
        ttl_seconds: int,
        *,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutionLease:
        current = self.get_active_lease(plan_id)
        if current is not None and current.holder_id != holder_id:
            raise LeaseConflict(plan_id)
        plan = self.load_plan(plan_id)
        lease_epic_id = epic_id if epic_id is not None else (plan.epic_id if plan else None)
        lease = ExecutionLease(
            plan_id=plan_id,
            epic_id=lease_epic_id,
            holder_id=holder_id,
            phase=plan.current_state if plan else "unknown",
            worker_kind=worker_kind,
            acquired_at=utc_now(),
            heartbeat_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
        self._save_model(self._lease_path(plan_id), lease, journal_root=self.root)
        return lease

    def find_active_leases_for_epic(self, epic_id: str) -> list[ExecutionLease]:
        now = datetime.now(UTC)
        leases = [
            lease
            for lease in self._iter_models(self._leases_dir(), ExecutionLease)
            if lease.epic_id == epic_id and lease.expires_at > now
        ]
        leases.sort(key=lambda lease: (lease.expires_at, lease.plan_id))
        return leases

    def heartbeat_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> ExecutionLease:
        lease = self.get_active_lease(plan_id)
        if lease is None or lease.holder_id != holder_id:
            raise LeaseConflict(plan_id)
        ttl_seconds = max(int((lease.expires_at - lease.heartbeat_at).total_seconds()), 60)
        return self._update_model(
            self._lease_path(plan_id),
            ExecutionLease,
            journal_root=self.root,
            heartbeat_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )

    def release_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        lease = self.get_active_lease(plan_id)
        if lease is None or lease.holder_id != holder_id:
            return
        self._delete_file(self._lease_path(plan_id))

    def get_active_lease(self, plan_id: str) -> ExecutionLease | None:
        lease = self._load_model(self._lease_path(plan_id), ExecutionLease)
        if lease is None:
            return None
        if lease.expires_at <= datetime.now(UTC):
            self._delete_file(self._lease_path(plan_id))
            return None
        return lease

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> EpicLock:
        current = self._load_model(self._lock_path(epic_id), EpicLock)
        if current is not None and current.expires_at > datetime.now(UTC) and current.holder_id != holder_id:
            raise LockConflict(epic_id)
        lock = EpicLock(
            epic_id=epic_id,
            holder_id=holder_id,
            acquired_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
        self._save_model(self._lock_path(epic_id), lock, journal_root=self.root)
        return lock

    def release_lock(self, epic_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        current = self._load_model(self._lock_path(epic_id), EpicLock)
        if current is None or current.holder_id != holder_id:
            return
        self._delete_file(self._lock_path(epic_id))

    # ------------------------------------------------------------------
    # Control plane / progress
    # ------------------------------------------------------------------

    def put_control_message(self, msg: ControlMessageInput,
        *,
        idempotency_key: str | None = None,
    ) -> ControlMessage:
        control = ControlMessage(
            id=_new_id("ctrl"),
            epic_id=msg.epic_id,
            actor_id=msg.actor_id,
            intent=msg.intent,
            target_id=msg.target_id,
            payload=msg.payload,
            idempotency_key=msg.idempotency_key,
            created_at=utc_now(),
        )
        self._save_model(self._control_message_path(control.id), control, journal_root=self.root)
        return control

    def claim_pending_control_messages(self, *, processor_id: str, max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        pending = [
            row
            for row in self._control_messages()
            if row.claimed_at is None and row.processed_at is None
        ]
        pending.sort(key=lambda row: (_utc_key(row.created_at), row.id))
        claimed: list[ControlMessage] = []
        for row in pending[:max]:
            claimed.append(
                self._update_model(
                    self._control_message_path(row.id),
                    ControlMessage,
                    journal_root=self.root,
                    processor_id=processor_id,
                    claimed_at=utc_now(),
                )
            )
        return claimed

    def recover_stale_control_messages(
        self,
        *,
        processor_id: str,
        older_than_seconds: int,
        max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        stale = [
            row
            for row in self._control_messages()
            if row.processed_at is None
            and row.claimed_at is not None
            and row.claimed_at <= cutoff
        ]
        stale.sort(key=lambda row: (_utc_key(row.claimed_at), row.id))
        recovered: list[ControlMessage] = []
        for row in stale[:max]:
            recovered.append(
                self._update_model(
                    self._control_message_path(row.id),
                    ControlMessage,
                    journal_root=self.root,
                    processor_id=processor_id,
                    claimed_at=utc_now(),
                )
            )
        return recovered

    def list_stale_control_messages(
        self,
        *,
        older_than_seconds: int,
        limit: int = 10,
    ) -> list[ControlMessage]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        stale = [
            row
            for row in self._control_messages()
            if row.processed_at is None
            and row.claimed_at is not None
            and row.claimed_at <= cutoff
        ]
        stale.sort(key=lambda row: (_utc_key(row.claimed_at), row.id))
        return stale[:limit]

    def mark_control_message_processed(self, msg_id: str, result: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._update_model(
            self._control_message_path(msg_id),
            ControlMessage,
            journal_root=self.root,
            result=result,
            processed_at=utc_now(),
        )

    # ------------------------------------------------------------------
    # Resident orchestration
    # ------------------------------------------------------------------

    def upsert_resident_conversation(
        self,
        conversation: ResidentConversationInput,
        *,
        idempotency_key: str | None = None,
    ) -> ResidentConversation:
        existing = self.get_resident_conversation_by_key(
            transport=conversation.transport,
            conversation_key=conversation.conversation_key,
        )
        now = utc_now()
        data = conversation.model_dump(mode="python")
        if existing is not None:
            changes = {
                key: value
                for key, value in data.items()
                if key not in {"transport", "conversation_key"} and value is not None
            }
            changes["updated_at"] = now
            return self._update_model(
                self._resident_conversation_path(existing.id),
                ResidentConversation,
                journal_root=self.root,
                **changes,
            )
        resident = ResidentConversation(
            id=_new_id("rconv"),
            **data,
            created_at=now,
            updated_at=now,
            last_active_at=now,
        )
        self._save_model(self._resident_conversation_path(resident.id), resident, journal_root=self.root)
        return resident

    def load_resident_conversation(self, conversation_id: str) -> ResidentConversation | None:
        return self._load_model(self._resident_conversation_path(conversation_id), ResidentConversation)

    def get_resident_conversation_by_key(
        self,
        *,
        transport: str,
        conversation_key: str,
    ) -> ResidentConversation | None:
        for row in self._resident_conversations():
            if row.transport == transport and row.conversation_key == conversation_key:
                return row
        return None

    def list_resident_conversations(
        self,
        *,
        transport: str | None = None,
        active_epic_id: str | None = None,
        limit: int = 50,
    ) -> list[ResidentConversation]:
        rows = self._resident_conversations()
        if transport is not None:
            rows = [row for row in rows if row.transport == transport]
        if active_epic_id is not None:
            rows = [row for row in rows if row.active_epic_id == active_epic_id]
        rows.sort(key=lambda row: (_utc_key(row.last_active_at), row.id), reverse=True)
        return rows[:limit]

    def update_resident_conversation(
        self,
        conversation_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ResidentConversation:
        changes.setdefault("updated_at", utc_now())
        return self._update_model(
            self._resident_conversation_path(conversation_id),
            ResidentConversation,
            journal_root=self.root,
            **changes,
        )

    def create_scheduled_job(
        self,
        job: ScheduledJobInput,
        *,
        idempotency_key: str | None = None,
    ) -> ScheduledJob:
        scheduled = ScheduledJob(
            id=_new_id("job"),
            **job.model_dump(mode="python"),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._save_model(self._scheduled_job_path(scheduled.id), scheduled, journal_root=self.root)
        return scheduled

    def load_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        return self._load_model(self._scheduled_job_path(job_id), ScheduledJob)

    def update_scheduled_job(
        self,
        job_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ScheduledJob:
        changes.setdefault("updated_at", utc_now())
        return self._update_model(
            self._scheduled_job_path(job_id),
            ScheduledJob,
            journal_root=self.root,
            **changes,
        )

    def claim_due_scheduled_jobs(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        stale_after_seconds: int | None = None,
        max: int = 10,
        job_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> list[ScheduledJob]:
        effective_now = now or utc_now()
        stale_cutoff = (
            effective_now - timedelta(seconds=stale_after_seconds)
            if stale_after_seconds is not None
            else None
        )
        due: list[ScheduledJob] = []
        for row in self._scheduled_jobs():
            if job_type is not None and row.job_type != job_type:
                continue
            pending_due = row.status == "pending" and row.scheduled_for <= effective_now
            stale_claim = (
                row.status == "claimed"
                and stale_cutoff is not None
                and row.claimed_at is not None
                and row.claimed_at <= stale_cutoff
            )
            if pending_due or stale_claim:
                due.append(row)
        due.sort(key=lambda row: (_utc_key(row.scheduled_for), row.id))
        claimed: list[ScheduledJob] = []
        for row in due[:max]:
            claimed.append(
                self.update_scheduled_job(
                    row.id,
                    status="claimed",
                    claimed_by=worker_id,
                    claimed_at=effective_now,
                    attempt_count=row.attempt_count + 1,
                    idempotency_key=idempotency_key,
                )
            )
        return claimed

    def list_scheduled_jobs(
        self,
        *,
        conversation_id: str | None = None,
        cloud_run_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[ScheduledJob]:
        rows = self._scheduled_jobs()
        if conversation_id is not None:
            rows = [row for row in rows if row.conversation_id == conversation_id]
        if cloud_run_id is not None:
            rows = [row for row in rows if row.cloud_run_id == cloud_run_id]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        if job_type is not None:
            rows = [row for row in rows if row.job_type == job_type]
        rows.sort(key=lambda row: (_utc_key(row.scheduled_for), row.id), reverse=True)
        return rows[:limit]

    def create_cloud_run(
        self,
        run: CloudRunInput,
        *,
        idempotency_key: str | None = None,
    ) -> CloudRun:
        effective_key = idempotency_key or run.idempotency_key
        if effective_key is not None:
            for existing in self._cloud_runs():
                if existing.idempotency_key == effective_key:
                    return existing
        cloud_run = CloudRun(
            id=_new_id("cloud"),
            **{**run.model_dump(mode="python"), "idempotency_key": effective_key},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._save_model(self._cloud_run_path(cloud_run.id), cloud_run, journal_root=self.root)
        return cloud_run

    def load_cloud_run(self, run_id: str) -> CloudRun | None:
        return self._load_model(self._cloud_run_path(run_id), CloudRun)

    def update_cloud_run(
        self,
        run_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> CloudRun:
        changes.setdefault("updated_at", utc_now())
        return self._update_model(
            self._cloud_run_path(run_id),
            CloudRun,
            journal_root=self.root,
            **changes,
        )

    def list_cloud_runs(
        self,
        *,
        conversation_id: str | None = None,
        epic_id: str | None = None,
        plan_id: str | None = None,
        sprint_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CloudRun]:
        rows = self._cloud_runs()
        if conversation_id is not None:
            rows = [row for row in rows if row.conversation_id == conversation_id]
        if epic_id is not None:
            rows = [row for row in rows if row.epic_id == epic_id]
        if plan_id is not None:
            rows = [row for row in rows if row.plan_id == plan_id]
        if sprint_id is not None:
            rows = [row for row in rows if row.sprint_id == sprint_id]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        rows.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        return rows[:limit]

    def append_progress_event(self, event: ProgressEventInput,
        *,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        effective_idempotency_key = idempotency_key or event.idempotency_key
        if effective_idempotency_key is not None:
            for existing in self._progress_events():
                if existing.idempotency_key == effective_idempotency_key:
                    return existing
        progress = ProgressEvent(
            id=_new_id("prog"),
            epic_id=event.epic_id,
            plan_id=event.plan_id,
            sprint_id=event.sprint_id,
            idempotency_key=effective_idempotency_key,
            kind=event.kind,
            summary=event.summary,
            details=event.details,
            occurred_at=utc_now(),
        )
        self._save_model(self._progress_event_path(progress.id), progress, journal_root=self.root)
        return progress

    def list_progress_events(
        self,
        *,
        plan_id: str | None = None,
        epic_id: str | None = None,
        since: datetime | None = None,
    ) -> list[ProgressEvent]:
        events = self._progress_events()
        if plan_id is not None:
            events = [row for row in events if row.plan_id == plan_id]
        if epic_id is not None:
            events = [row for row in events if row.epic_id == epic_id]
        if since is not None:
            events = [row for row in events if row.occurred_at >= since]
        events.sort(key=lambda row: (row.occurred_at, row.id))
        return events

    # ------------------------------------------------------------------
    # Automation actors
    # ------------------------------------------------------------------

    def create_automation_actor(
        self,
        *,
        actor_id: str,
        name: str,
        granted_epic_ids: str | Sequence[str],
        actor_kind: str,
        idempotency_key: str | None = None,
    ) -> AutomationActor:
        actor = AutomationActor(
            id=actor_id,
            name=name,
            granted_epic_ids=granted_epic_ids,
            actor_kind=actor_kind,
            created_at=utc_now(),
        )
        self._save_model(self._automation_actor_path(actor.id), actor, journal_root=self.root)
        return actor

    def load_automation_actor(self, actor_id: str) -> AutomationActor | None:
        return self._load_model(self._automation_actor_path(actor_id), AutomationActor)

    def update_automation_actor(self, actor_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> AutomationActor:
        if "last_active_at" not in changes:
            changes["last_active_at"] = utc_now()
        return self._update_model(self._automation_actor_path(actor_id), AutomationActor, journal_root=self.root, **changes)


__all__ = ["FileStore"]
