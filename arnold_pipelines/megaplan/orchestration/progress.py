"""Progress event emission and subprocess-safe runtime context."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.schemas import ProgressEvent
from arnold_pipelines.megaplan.store import DBStore, FileStore, MultiStore, ProgressEventInput, Store, deterministic_idempotency_key

ENV_PREFIX = "MEGAPLAN_PROGRESS_"
ENV_ENABLED = f"{ENV_PREFIX}ENABLED"
ENV_BACKEND = f"{ENV_PREFIX}BACKEND"
ENV_PROJECT_ROOT = f"{ENV_PREFIX}PROJECT_ROOT"
ENV_FILE_ROOT = f"{ENV_PREFIX}FILE_ROOT"
ENV_ACTOR_ID = f"{ENV_PREFIX}ACTOR_ID"
ENV_DSN_ENV = f"{ENV_PREFIX}DSN_ENV"
ENV_EPIC_ID = f"{ENV_PREFIX}EPIC_ID"
ENV_PLAN_ID = f"{ENV_PREFIX}PLAN_ID"
ENV_SPRINT_ID = f"{ENV_PREFIX}SPRINT_ID"
ENV_RUN_ID = f"{ENV_PREFIX}RUN_ID"

_ALLOWED_BACKENDS = {"file", "db", "multi"}
_DEFAULT_DSN_ENV = "SUPABASE_DB_URL"


@dataclass(frozen=True)
class ProgressContext:
    """Non-secret references needed to reconstruct progress emission."""

    backend: str = "multi"
    project_root: str | None = None
    file_root: str | None = None
    actor_id: str | None = None
    dsn_env: str | None = None
    epic_id: str | None = None
    plan_id: str | None = None
    sprint_id: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if self.backend not in _ALLOWED_BACKENDS:
            raise ValueError(f"unsupported progress backend {self.backend!r}")
        if self.backend in {"file", "multi"} and not (self.project_root or self.file_root):
            raise ValueError("progress context requires project_root or file_root for file-backed emission")
        if self.backend == "db" and not self.actor_id:
            raise ValueError("progress context requires actor_id for db-backed emission")

    def to_env(self) -> dict[str, str]:
        env = {
            ENV_ENABLED: "1",
            ENV_BACKEND: self.backend,
        }
        optional = {
            ENV_PROJECT_ROOT: self.project_root,
            ENV_FILE_ROOT: self.file_root,
            ENV_ACTOR_ID: self.actor_id,
            ENV_DSN_ENV: self.dsn_env,
            ENV_EPIC_ID: self.epic_id,
            ENV_PLAN_ID: self.plan_id,
            ENV_SPRINT_ID: self.sprint_id,
            ENV_RUN_ID: self.run_id,
        }
        env.update({key: value for key, value in optional.items() if value})
        return env

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ProgressContext | None:
        source = os.environ if env is None else env
        if source.get(ENV_ENABLED) != "1":
            return None
        backend = source.get(ENV_BACKEND, "multi")
        if backend not in _ALLOWED_BACKENDS:
            return None
        try:
            return cls(
                backend=backend,
                project_root=source.get(ENV_PROJECT_ROOT),
                file_root=source.get(ENV_FILE_ROOT),
                actor_id=source.get(ENV_ACTOR_ID),
                dsn_env=source.get(ENV_DSN_ENV),
                epic_id=source.get(ENV_EPIC_ID),
                plan_id=source.get(ENV_PLAN_ID),
                sprint_id=source.get(ENV_SPRINT_ID),
                run_id=source.get(ENV_RUN_ID),
            )
        except ValueError:
            return None

    def build_store(self) -> Store:
        dsn = os.environ.get(self.dsn_env or _DEFAULT_DSN_ENV) if self.backend in {"db", "multi"} else None
        if self.backend == "file":
            root = self.file_root or MultiStore.canonical_filestore_root(Path(self.project_root or "."))
            return FileStore(root)
        if self.backend == "db":
            return DBStore(actor_id=self.actor_id, dsn=dsn)
        if self.file_root:
            return MultiStore(file_root=self.file_root, project_root=self.project_root, actor_id=self.actor_id, dsn=dsn)
        return MultiStore.for_project(Path(self.project_root or "."), actor_id=self.actor_id, dsn=dsn)


def strip_progress_env(env: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in env.items() if not key.startswith(ENV_PREFIX)}


class ProgressEmitter:
    """Store-backed progress publisher with a no-op disabled mode."""

    def __init__(
        self,
        store: Store | None = None,
        *,
        context: ProgressContext | None = None,
        epic_id: str | None = None,
        plan_id: str | None = None,
        sprint_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.store = store
        self.context = context
        self.epic_id = epic_id or (context.epic_id if context else None)
        self.plan_id = plan_id or (context.plan_id if context else None)
        self.sprint_id = sprint_id or (context.sprint_id if context else None)
        self.run_id = run_id or (context.run_id if context else None)

    @classmethod
    def disabled(cls) -> ProgressEmitter:
        return cls()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ProgressEmitter:
        context = ProgressContext.from_env(env)
        if context is None:
            return cls.disabled()
        return cls(context.build_store(), context=context)

    def emit(
        self,
        kind: str,
        summary: str,
        *,
        details: Mapping[str, Any] | None = None,
        epic_id: str | None = None,
        plan_id: str | None = None,
        sprint_id: str | None = None,
        idempotency_key: str | None = None,
        key_parts: tuple[object, ...] = (),
    ) -> ProgressEvent | None:
        target_epic_id = epic_id or self.epic_id
        if self.store is None or target_epic_id is None:
            return None
        target_plan_id = plan_id if plan_id is not None else self.plan_id
        target_sprint_id = sprint_id if sprint_id is not None else self.sprint_id
        event_details = dict(details or {})
        event_details = _project_recovery_claims(event_details)
        if self.run_id and "run_id" not in event_details:
            event_details["run_id"] = self.run_id
        effective_key = idempotency_key or self.idempotency_key(kind, target_epic_id, target_plan_id, target_sprint_id, *key_parts)
        event = ProgressEventInput(
            epic_id=target_epic_id,
            plan_id=target_plan_id,
            sprint_id=target_sprint_id,
            idempotency_key=effective_key,
            kind=kind,
            summary=summary,
            details=event_details,
        )
        return self.store.append_progress_event(event, idempotency_key=effective_key)

    def idempotency_key(self, kind: str, epic_id: str, plan_id: str | None, sprint_id: str | None, *parts: object) -> str:
        return deterministic_idempotency_key("progress", self.run_id, epic_id, plan_id, sprint_id, kind, *parts)

    def phase_start(self, phase: str, *, summary: str | None = None, **details: Any) -> ProgressEvent | None:
        return self.emit("phase_start", summary or f"{phase} started", details={"phase": phase, **details}, key_parts=(phase, "start"))

    def phase_end(self, phase: str, *, summary: str | None = None, **details: Any) -> ProgressEvent | None:
        return self.emit("phase_end", summary or f"{phase} finished", details={"phase": phase, **details}, key_parts=(phase, "end"))

    def batch_complete(self, batch_id: str, *, summary: str | None = None, **details: Any) -> ProgressEvent | None:
        return self.emit("batch_complete", summary or f"Batch {batch_id} complete", details={"batch_id": batch_id, **details}, key_parts=(batch_id,))

    def gate_pending(self, gate_id: str, *, summary: str | None = None, **details: Any) -> ProgressEvent | None:
        return self.emit("gate_pending", summary or "Gate approval needed", details={"gate_id": gate_id, **details}, key_parts=(gate_id,))

    def gate_resolved(self, gate_id: str, decision: str, *, summary: str | None = None, **details: Any) -> ProgressEvent | None:
        return self.emit("gate_resolved", summary or f"Gate {decision}", details={"gate_id": gate_id, "decision": decision, **details}, key_parts=(gate_id, decision))

    def plan_done(self, *, summary: str = "Plan complete", **details: Any) -> ProgressEvent | None:
        return self.emit("plan_done", summary, details=details, key_parts=("done",))

    def plan_failed(self, *, summary: str = "Plan failed", **details: Any) -> ProgressEvent | None:
        return self.emit("plan_failed", summary, details=details, key_parts=("failed",))

    def execution_blocked(self, *, summary: str = "Execution blocked", **details: Any) -> ProgressEvent | None:
        return self.emit("execution_blocked", summary, details=details, key_parts=("blocked",))

    def manual_fix_attached(self, *, summary: str = "Manual fix attached", **details: Any) -> ProgressEvent | None:
        return self.emit("manual_fix_attached", summary, details=details, key_parts=("manual-fix",))

    def recovery_observed(
        self,
        recovery_verification: Mapping[str, Any],
        *,
        summary: str = "Repair recovery observed",
        **details: Any,
    ) -> ProgressEvent | None:
        """Emit a progress projection that preserves recovery evidence state."""
        projected = {
            **details,
            "phase": "repair_recovery",
            "recovery_verification": dict(recovery_verification),
        }
        classified = _project_recovery_claims(projected)
        return self.emit(
            "phase_end",
            summary,
            details=classified,
            key_parts=(
                "repair_recovery",
                classified["recovery_status"],
                classified["unknown_type"],
            ),
        )


def _project_recovery_claims(details: dict[str, Any]) -> dict[str, Any]:
    """Replace caller-asserted recovery claims with the core classification."""
    recovery_keys = {
        "recovery_verification",
        "recovery_state",
        "recovery_status",
        "recovery_verified",
        "authorizes_verified_recovered",
    }
    if not recovery_keys.intersection(details):
        return details

    from arnold_pipelines.megaplan.cloud.repair_contract import (
        classify_recovery_verification,
    )

    raw = details.get("recovery_verification")
    verification = raw if isinstance(raw, Mapping) else {}
    classified = classify_recovery_verification(
        original_blocker=verification.get("original_blocker"),
        observation=verification.get("observation"),
        repair_completed_at=verification.get("repair_completed_at"),
    )
    details.update(
        {
            "recovery_verification": dict(verification),
            "recovery_state": classified["status"],
            "recovery_status": classified["status"],
            "recovery_verified": classified["recovery_verified"],
            "authorizes_verified_recovered": classified[
                "authorizes_verified_recovered"
            ],
            "unknown_type": classified["unknown_type"],
            "recovery_reason": classified["reason"],
        }
    )
    return details


__all__ = [
    "ENV_PREFIX",
    "ENV_ENABLED",
    "ENV_BACKEND",
    "ENV_PROJECT_ROOT",
    "ENV_FILE_ROOT",
    "ENV_ACTOR_ID",
    "ENV_DSN_ENV",
    "ENV_EPIC_ID",
    "ENV_PLAN_ID",
    "ENV_SPRINT_ID",
    "ENV_RUN_ID",
    "ProgressContext",
    "ProgressEmitter",
    "strip_progress_env",
]
