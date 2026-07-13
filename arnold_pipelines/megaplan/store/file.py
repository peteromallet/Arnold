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

from arnold_pipelines.megaplan._core.io import (
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
)
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.tickets.files import (
    iterate_ticket_files as iterate_frontmatter_ticket_files,
    read_ticket_file,
    slugify as ticket_slugify,
    ticket_file_path as frontmatter_ticket_file_path,
    tickets_dir as frontmatter_tickets_dir,
    write_ticket_file,
)
from arnold_pipelines.megaplan.tickets.identity import repo_codebase_identity

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
    validate_epic_update_fields,
    validate_plan_artifact_name,
)
from .blob import LocalDirBlobStore
from .snapshot import canonical_json_dumps, canonical_sha256, capture_epic_snapshot

from ._file import (
    FileChecklistMixin,
    FileCodeArtifactMixin,
    FileCodebaseMixin,
    FileConversationMixin,
    FileEpicMixin,
    FileEventMixin,
    FileExternalRequestMixin,
    FileFeedbackMixin,
    FileImageMixin,
    FileOperationsMixin,
    FilePlanMixin,
    FileSecondOpinionMixin,
    FileSprintMixin,
    FileTicketMixin,
)
from ._file.common import (
    _TERMINAL_TURN_STATUSES,
    _model_bytes,
    _new_id,
    _parse_datetime,
    _utc_key,
)

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


class FileStore(
    FileEpicMixin,
    FileChecklistMixin,
    FileSprintMixin,
    FileEventMixin,
    FileConversationMixin,
    FileExternalRequestMixin,
    FileImageMixin,
    FileSecondOpinionMixin,
    FileCodebaseMixin,
    FileTicketMixin,
    FileCodeArtifactMixin,
    FileFeedbackMixin,
    FilePlanMixin,
    FileOperationsMixin,
    Store,
):
    """Filesystem-backed Store implementation.

    The implementation favors compatibility and correctness over cleverness:
    records live as JSON files in a stable directory layout, and mutations flow
    through the journal helpers added to ``megaplan._core.io`` in Sprint 1.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        repo_root: str | Path | None = None,
        tickets_dir: str | Path | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if repo_root is not None and tickets_dir is not None:
            raise ValueError("Pass either repo_root or tickets_dir, not both")
        self.repo_root = Path(repo_root).expanduser().resolve() if repo_root is not None else self.root
        self._explicit_tickets_dir = Path(tickets_dir).expanduser().resolve() if tickets_dir is not None else None
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

    def _tickets_dir(self) -> Path:
        if self._explicit_tickets_dir is not None:
            self._explicit_tickets_dir.mkdir(parents=True, exist_ok=True)
            return self._explicit_tickets_dir
        return frontmatter_tickets_dir(self.repo_root)

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

    def _resident_user_preferences_dir(self) -> Path:
        return self.root / "resident_user_preferences"

    def _scheduled_jobs_dir(self) -> Path:
        return self.root / "scheduled_jobs"

    def _cloud_runs_dir(self) -> Path:
        return self.root / "cloud_runs"

    def _automation_actors_dir(self) -> Path:
        return self.root / "automation_actors"

    def _migration_runs_dir(self) -> Path:
        return self.root / "migration_runs"

    def _idempotency_dir(self, operation: str) -> Path:
        return self.root / "idempotency" / operation

    def _idempotency_path(self, operation: str, idempotency_key: str) -> Path:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self._idempotency_dir(operation) / f"{digest}.json"

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

    def _ticket_path(self, ticket_id: str) -> Path:
        existing = self._find_ticket_frontmatter_path(ticket_id)
        if existing is not None:
            return existing
        return frontmatter_ticket_file_path(self.repo_root, ticket_id, ticket_slugify(ticket_id))

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

    def _resident_user_preference_path(self, transport: str, user_id: str) -> Path:
        key = hashlib.sha256(f"{transport}\0{user_id}".encode("utf-8")).hexdigest()
        return self._resident_user_preferences_dir() / f"{key}.json"

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

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        staged = self._active_transaction.staged_bytes(path) if self._active_transaction is not None else None
        if staged is not None:
            return json.loads(staged.decode("utf-8"))
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

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

    def _request_hash(self, operation: str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> str:
        payload = {"operation": operation, "args": list(args), "kwargs": dict(kwargs)}
        encoded = json.dumps(payload, default=self._json_default, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _json_default(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, (set, tuple)):
            return list(value)
        return str(value)

    def _load_epic_idempotency(self, idempotency_key: str, request_hash: str) -> Epic | None:
        record_path = self._idempotency_path("update_epic", idempotency_key)
        record = self._load_json(record_path)
        if record is None:
            return None
        if record.get("operation") != "update_epic" or record.get("request_hash") != request_hash:
            raise ValueError(f"idempotency_key {idempotency_key!r} was reused with a different request")
        return Epic.model_validate(record["response"])

    def _save_epic_idempotency(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: Epic,
        journal_root: Path,
    ) -> None:
        record = {
            "operation": "update_epic",
            "request_hash": request_hash,
            "response": response.model_dump(mode="json"),
        }
        self._commit_write(
            self._idempotency_path("update_epic", idempotency_key),
            json_dump(record).encode("utf-8"),
            journal_root=journal_root,
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

    def _ticket_file_records(self) -> list[tuple[Path, dict[str, Any]]]:
        if self._explicit_tickets_dir is not None:
            ticket_dir = self._tickets_dir()
            records: list[tuple[Path, dict[str, Any]]] = []
            for entry in sorted(ticket_dir.iterdir()):
                if entry.suffix != ".md":
                    continue
                record = read_ticket_file(entry)
                if record is not None:
                    records.append((entry, record))
            return records
        return list(iterate_frontmatter_ticket_files(self.repo_root))

    def _find_ticket_frontmatter_path(self, ticket_id: str) -> Path | None:
        for path, record in self._ticket_file_records():
            if record.get("id") == ticket_id:
                return path
        return None

    def _resolve_ticket_codebase(self) -> Codebase:
        try:
            identity = repo_codebase_identity(self.repo_root)
        except Exception as exc:
            raise StoreError(
                "FileStore ticket operations require a git repository with a root commit"
            ) from exc
        existing = self.resolve_codebase_by_root_sha(identity.root_commit_sha)
        if existing is not None:
            return existing
        return self.upsert_codebase(
            owner=identity.owner,
            name=identity.name,
            default_branch=identity.default_branch,
            root_commit_sha=identity.root_commit_sha,
        )

    def _ticket_from_frontmatter(self, record: Mapping[str, Any]) -> Ticket:
        codebase_id = record.get("codebase_id")
        if not isinstance(codebase_id, str) or not codebase_id:
            codebase_id = self._resolve_ticket_codebase().id
        return Ticket(
            id=str(record["id"]),
            codebase_id=codebase_id,
            title=str(record.get("title") or ""),
            body=str(record.get("__body__") or ""),
            status=str(record.get("status") or "open"),
            source=str(record.get("source") or "human"),
            tags=list(record.get("tags") or []),
            filed_by_actor_id=record.get("filed_by_actor_id"),
            filed_in_turn_id=record.get("filed_in_turn_id"),
            slug=ticket_slugify(str(record.get("title") or record["id"])),
            created_at=_parse_datetime(record.get("created_at")) or utc_now(),
            last_edited_at=_parse_datetime(record.get("last_edited_at")) or utc_now(),
            resolution_note=record.get("resolution_note"),
            addressed_at=_parse_datetime(record.get("addressed_at")),
        )

    def _write_ticket_frontmatter(
        self,
        ticket: Ticket,
        *,
        path: Path | None = None,
        links: Sequence[TicketEpicLink] | None = None,
    ) -> Path:
        target = path or (
            self._tickets_dir() / f"{ticket.id}-{ticket.slug}.md"
            if self._explicit_tickets_dir is not None
            else frontmatter_ticket_file_path(self.repo_root, ticket.id, ticket.slug)
        )
        if links is None and path is not None:
            existing = read_ticket_file(path)
            links = self._ticket_frontmatter_links(existing or {})
        if links is None:
            links = []
        write_ticket_file(
            target,
            {
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status,
                "source": ticket.source,
                "tags": list(ticket.tags or []),
                "filed_by_actor_id": ticket.filed_by_actor_id,
                "filed_in_turn_id": ticket.filed_in_turn_id,
                "codebase_id": ticket.codebase_id,
                "created_at": ticket.created_at,
                "last_edited_at": ticket.last_edited_at,
                "resolution_note": ticket.resolution_note,
                "addressed_at": ticket.addressed_at,
                "epics": [
                    {
                        "epic_id": link.epic_id,
                        "resolves_on_complete": link.resolves_on_complete,
                        "linked_at": link.linked_at,
                    }
                    for link in links
                ],
                "__body__": ticket.body,
            },
        )
        return target

    def _tickets(self) -> list[Ticket]:
        return [self._ticket_from_frontmatter(record) for _path, record in self._ticket_file_records()]

    def _ticket_frontmatter_links(
        self,
        record: Mapping[str, Any],
    ) -> list[TicketEpicLink]:
        ticket_id = record.get("id")
        if not isinstance(ticket_id, str) or not ticket_id:
            return []
        links: list[TicketEpicLink] = []
        for entry in record.get("epics") or []:
            if not isinstance(entry, Mapping):
                continue
            epic_id = entry.get("epic_id")
            if not isinstance(epic_id, str) or not epic_id:
                continue
            links.append(
                TicketEpicLink(
                    ticket_id=ticket_id,
                    epic_id=epic_id,
                    resolves_on_complete=bool(entry.get("resolves_on_complete")),
                    linked_at=_parse_datetime(entry.get("linked_at")) or utc_now(),
                )
            )
        return links

    def _ticket_epic_links(self) -> list[TicketEpicLink]:
        links: list[TicketEpicLink] = []
        for _path, record in self._ticket_file_records():
            links.extend(self._ticket_frontmatter_links(record))
        return links

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


__all__ = ["FileStore"]
