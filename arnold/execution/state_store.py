"""Checkpoint state store for manifest execution runs.

The journal remains the durable authority. The state store is a
human/operator-friendly snapshot that lets a restarted runner pick up the
previous run identity, outputs, and budget position without re-deriving
everything from scratch.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from arnold.workflow.native_wbc import begin_native_wbc_attempt


@dataclass(frozen=True)
class BudgetSnapshot:
    """Budget fields saved in a checkpoint."""

    consumed_cost: float = 0.0
    consumed_seconds: float = 0.0
    consumed_tokens: int = 0
    released_cost: float = 0.0
    released_seconds: float = 0.0
    released_tokens: int = 0


@dataclass(frozen=True)
class RoutingSnapshot:
    """Minimal serializable routing snapshot for a checkpoint."""

    completed: tuple[dict[str, Any], ...] = ()
    failed: tuple[dict[str, Any], ...] = ()
    suspended: tuple[dict[str, Any], ...] = ()
    ready: tuple[dict[str, Any], ...] = ()
    blocked: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class JournalPointer:
    """Pointer to a position in the event journal."""

    journal_uri: str
    sequence: int | None = None


@dataclass(frozen=True)
class RunCheckpoint:
    """Snapshot of an in-flight or finished manifest run."""

    run_id: str
    manifest_id: str
    manifest_hash: str
    status: str = "running"
    routing: RoutingSnapshot = field(default_factory=RoutingSnapshot)
    journal_pointer: JournalPointer = field(default_factory=lambda: JournalPointer(journal_uri=""))
    budget: BudgetSnapshot = field(default_factory=BudgetSnapshot)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    scope_stack: tuple[str, ...] = ()
    reentry_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "manifest_id": self.manifest_id,
            "manifest_hash": self.manifest_hash,
            "status": self.status,
            "routing": {
                "completed": list(self.routing.completed),
                "failed": list(self.routing.failed),
                "suspended": list(self.routing.suspended),
                "ready": list(self.routing.ready),
                "blocked": list(self.routing.blocked),
            },
            "journal_pointer": asdict(self.journal_pointer),
            "budget": asdict(self.budget),
            "outputs": dict(self.outputs),
            "scope_stack": list(self.scope_stack),
            "reentry_id": self.reentry_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RunCheckpoint":
        routing_payload = payload.get("routing") or {}
        routing = RoutingSnapshot(
            completed=tuple(routing_payload.get("completed", ())),
            failed=tuple(routing_payload.get("failed", ())),
            suspended=tuple(routing_payload.get("suspended", ())),
            ready=tuple(routing_payload.get("ready", ())),
            blocked=tuple(routing_payload.get("blocked", ())),
        )
        jp = payload.get("journal_pointer") or {}
        journal_pointer = JournalPointer(
            journal_uri=jp.get("journal_uri", ""),
            sequence=jp.get("sequence"),
        )
        budget_payload = payload.get("budget") or {}
        budget = BudgetSnapshot(
            consumed_cost=float(budget_payload.get("consumed_cost", 0.0)),
            consumed_seconds=float(budget_payload.get("consumed_seconds", 0.0)),
            consumed_tokens=int(budget_payload.get("consumed_tokens", 0)),
            released_cost=float(budget_payload.get("released_cost", 0.0)),
            released_seconds=float(budget_payload.get("released_seconds", 0.0)),
            released_tokens=int(budget_payload.get("released_tokens", 0)),
        )
        return cls(
            run_id=payload.get("run_id", ""),
            manifest_id=payload.get("manifest_id", ""),
            manifest_hash=payload.get("manifest_hash", ""),
            status=payload.get("status", "running"),
            routing=routing,
            journal_pointer=journal_pointer,
            budget=budget,
            outputs=dict(payload.get("outputs", {})),
            scope_stack=tuple(payload.get("scope_stack", ())),
            reentry_id=payload.get("reentry_id"),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
        )


class StateStore(Protocol):
    """Protocol for persisting and loading run checkpoints."""

    def load(self, run_id: str) -> RunCheckpoint | None: ...
    def save(self, checkpoint: RunCheckpoint) -> None: ...
    def list(self) -> list[str]: ...


class FileStateStore:
    """File-backed checkpoint store using one JSON file per run."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        # Simple escaping: replace path separators with underscores.
        safe = run_id.replace("/", "_").replace("\\", "_")
        return self._directory / f"{safe}.json"

    def save(self, checkpoint: RunCheckpoint) -> None:
        path = self._path(checkpoint.run_id)
        attempt = begin_native_wbc_attempt(
            self._directory,
            producer_family="arnold_execution",
            surface="state_store",
            run_id=checkpoint.run_id,
            subject={"run_id": checkpoint.run_id, "operation": "save"},
            metadata={"store": self.__class__.__name__},
            start_payload={"path": str(path), "status": checkpoint.status},
        )
        prior_payload: Mapping[str, Any] | None = None
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                loaded = None
            if isinstance(loaded, Mapping):
                prior_payload = loaded
                attempt.reconciliation(
                    "checkpoint_overwrite",
                    outcome="superseded",
                    payload={
                        "prior_status": loaded.get("status"),
                        "prior_updated_at": loaded.get("updated_at"),
                        "path": str(path),
                    },
                )
        try:
            path.write_text(
                json.dumps(checkpoint.to_dict(), sort_keys=True, indent=2),
                encoding="utf-8",
            )
        except BaseException as exc:
            attempt.terminal(
                status="failed",
                outcome="error",
                payload={"error_type": exc.__class__.__name__, "error": str(exc)},
            )
            raise
        attempt.effect_outcome(
            "checkpoint_save",
            status="written",
            payload={
                "path": str(path),
                "status": checkpoint.status,
                "journal_sequence": checkpoint.journal_pointer.sequence,
                "reconciled_prior_snapshot": prior_payload is not None,
            },
        )
        attempt.terminal(
            status="completed",
            outcome="saved",
            payload={"status": checkpoint.status, "path": str(path)},
        )

    def load(self, run_id: str) -> RunCheckpoint | None:
        path = self._path(run_id)
        attempt = begin_native_wbc_attempt(
            self._directory,
            producer_family="arnold_execution",
            surface="state_store",
            run_id=run_id,
            subject={"run_id": run_id, "operation": "load"},
            metadata={"store": self.__class__.__name__},
            start_payload={"path": str(path)},
        )
        if not path.exists():
            attempt.resume("checkpoint_missing", {"path": str(path)})
            attempt.terminal(
                status="completed",
                outcome="missing",
                payload={"path": str(path)},
            )
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except BaseException as exc:
            attempt.terminal(
                status="failed",
                outcome="error",
                payload={"error_type": exc.__class__.__name__, "error": str(exc)},
            )
            raise
        checkpoint = RunCheckpoint.from_dict(payload)
        attempt.resume(
            "checkpoint_loaded",
            {
                "path": str(path),
                "status": checkpoint.status,
                "journal_sequence": checkpoint.journal_pointer.sequence,
            },
        )
        attempt.terminal(
            status="completed",
            outcome="loaded",
            payload={"status": checkpoint.status, "path": str(path)},
        )
        return checkpoint

    def list(self) -> list[str]:
        run_ids = sorted(
            path.stem
            for path in self._directory.iterdir()
            if path.is_file() and path.suffix == ".json"
        )
        attempt = begin_native_wbc_attempt(
            self._directory,
            producer_family="arnold_execution",
            surface="state_store",
            subject={"operation": "list"},
            metadata={"store": self.__class__.__name__},
            start_payload={"directory": str(self._directory)},
        )
        attempt.effect_outcome(
            "checkpoint_list",
            status="enumerated",
            payload={"count": len(run_ids)},
        )
        attempt.terminal(
            status="completed",
            outcome="listed",
            payload={"count": len(run_ids)},
        )
        return run_ids


__all__ = [
    "BudgetSnapshot",
    "FileStateStore",
    "JournalPointer",
    "RoutingSnapshot",
    "RunCheckpoint",
    "StateStore",
]
