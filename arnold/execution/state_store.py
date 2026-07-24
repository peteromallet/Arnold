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
        path.write_text(
            json.dumps(checkpoint.to_dict(), sort_keys=True, indent=2),
            encoding="utf-8",
        )

    def load(self, run_id: str) -> RunCheckpoint | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return RunCheckpoint.from_dict(payload)

    def list(self) -> list[str]:
        return sorted(
            path.stem
            for path in self._directory.iterdir()
            if path.is_file() and path.suffix == ".json"
        )


__all__ = [
    "BudgetSnapshot",
    "FileStateStore",
    "JournalPointer",
    "RoutingSnapshot",
    "RunCheckpoint",
    "StateStore",
]
