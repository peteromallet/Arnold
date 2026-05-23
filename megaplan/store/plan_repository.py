"""Plan-tree access seam for Sprint 1 file mode."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from megaplan._core.io import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    find_plan_dir,
    now_utc,
    plan_search_roots,
    read_json,
)
from megaplan.orchestration.feedback import load_feedback
from megaplan.schemas import Plan, PlanArtifact
from megaplan.store.base import ProgressEventInput
from megaplan.execute_resume_cursor import validate_state_resume_cursor
from megaplan.worktrees.identity import (
    TaskIdentity,
    decode_original_task_id,
    validate_task_key,
)

from .base import Store

_EXECUTION_BATCH_RE = re.compile(r"execution_batch_(\d+)\.json$")
_VERSION_RE = re.compile(r"_v(\d+)(?:\.|_|$)")
_TASK_EXECUTION_PARTS = ("tasks", "execution.json")


class PlanRepository:
    """File-mode repository for the existing megaplan tree layout.

    The repository intentionally operates on the current on-disk plan tree
    instead of routing plan artifacts through ``Store``. This preserves the
    byte-sensitive fixture and worker surface that still expects a real
    filesystem directory.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        store: Store | None = None,
        home: str | Path | None = None,
    ) -> None:
        self.root = Path(root)
        self.store = store
        self.home = Path(home) if home is not None else None
        self._plan_dir = self.root if self._looks_like_plan_dir(self.root) else None

    @classmethod
    def from_plan_dir(
        cls,
        plan_dir: str | Path,
        *,
        store: Store | None = None,
        home: str | Path | None = None,
    ) -> PlanRepository:
        return cls(plan_dir, store=store, home=home)

    @staticmethod
    def _looks_like_plan_dir(path: Path) -> bool:
        return (path / "state.json").exists()

    def _home_path(self) -> Path | None:
        if self.home is None:
            return None
        return self.home.expanduser().resolve()

    def _require_plan_dir(self) -> Path:
        if self._plan_dir is None:
            raise RuntimeError("PlanRepository is not bound to a plan directory")
        return self._plan_dir

    def _resolve_artifact_path(self, name: str | Path) -> Path:
        relative = Path(name)
        if relative.is_absolute() or any(part == ".." for part in relative.parts):
            raise ValueError(f"Artifact path must stay inside the plan tree: {name!r}")
        return self.plan_dir / relative

    def _coerce_task_key(self, task: TaskIdentity | str) -> str:
        if isinstance(task, TaskIdentity):
            return task.task_key
        if isinstance(task, str):
            return validate_task_key(task)
        raise TypeError("task must be a TaskIdentity or validated task key string")

    def task_execution_artifact_name(self, task: TaskIdentity | str) -> str:
        task_key = self._coerce_task_key(task)
        return f"tasks/{task_key}/execution.json"

    def task_execution_artifact_path(self, task: TaskIdentity | str) -> Path:
        return self.artifact_path(self.task_execution_artifact_name(task))

    @property
    def is_bound(self) -> bool:
        return self._plan_dir is not None

    @property
    def plan_dir(self) -> Path:
        return self._require_plan_dir()

    @property
    def plan_name(self) -> str:
        return self.plan_dir.name

    @property
    def working_dir(self) -> Path:
        return self.plan_dir

    @property
    def compatibility_lock_path(self) -> Path:
        return self.plan_dir / ".plan.lock"

    def resolve_plan_dir(self, plan_name: str) -> Path:
        if self._plan_dir is not None:
            if self.plan_dir.name != plan_name:
                raise FileNotFoundError(plan_name)
            return self.plan_dir
        plan_dir = find_plan_dir(self.root, plan_name, home=self._home_path())
        if plan_dir is None:
            raise FileNotFoundError(plan_name)
        return plan_dir

    def for_plan(self, plan_name: str) -> PlanRepository:
        return type(self)(self.resolve_plan_dir(plan_name), store=self.store, home=self.home)

    def active_plan_dirs(self) -> list[Path]:
        by_name: dict[str, Path] = {}
        for candidate_root in plan_search_roots(self.root, home=self._home_path()):
            if not candidate_root.exists():
                continue
            for child in candidate_root.iterdir():
                if child.is_dir() and self._looks_like_plan_dir(child):
                    by_name.setdefault(child.name, child)
        return [by_name[name] for name in sorted(by_name)]

    def exists(self) -> bool:
        return self._require_plan_dir().exists()

    def list_artifact_paths(self) -> list[Path]:
        plan_dir = self._require_plan_dir()
        return sorted(
            (path for path in plan_dir.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(plan_dir).as_posix(),
        )

    def list_artifact_names(self) -> list[str]:
        plan_dir = self._require_plan_dir()
        return [path.relative_to(plan_dir).as_posix() for path in self.list_artifact_paths()]

    def artifact_path(self, name: str | Path) -> Path:
        return self._resolve_artifact_path(name)

    def read_artifact_bytes(self, name: str | Path) -> bytes | None:
        path = self._resolve_artifact_path(name)
        return path.read_bytes() if path.exists() else None

    def read_artifact_text(self, name: str | Path) -> str | None:
        data = self.read_artifact_bytes(name)
        return data.decode("utf-8") if data is not None else None

    def read_artifact_json(self, name: str | Path) -> dict[str, Any] | list[Any] | None:
        path = self._resolve_artifact_path(name)
        return read_json(path) if path.exists() else None

    def write_artifact_bytes(self, name: str | Path, data: bytes) -> Path:
        path = self._resolve_artifact_path(name)
        atomic_write_bytes(path, data)
        return path

    def write_artifact_text(self, name: str | Path, data: str) -> Path:
        path = self._resolve_artifact_path(name)
        atomic_write_text(path, data)
        return path

    def write_artifact_json(self, name: str | Path, data: Any) -> Path:
        path = self._resolve_artifact_path(name)
        atomic_write_json(path, data)
        return path

    def read_task_execution_artifact(
        self,
        task: TaskIdentity | str,
    ) -> dict[str, Any] | list[Any] | None:
        return self.read_artifact_json(self.task_execution_artifact_name(task))

    def write_task_execution_artifact(self, task: TaskIdentity | str, data: Any) -> Path:
        return self.write_artifact_json(self.task_execution_artifact_name(task), data)

    def delete_artifact(self, name: str | Path) -> None:
        path = self._resolve_artifact_path(name)
        if path.exists():
            path.unlink()

    def load_state(self) -> dict[str, Any]:
        return read_json(self.plan_dir / "state.json")

    def save_state(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.plan_dir / "state.json", state)

    def list_execution_batch_artifacts(self) -> list[Path]:
        return sorted(
            (
                path
                for path in self.list_artifact_paths()
                if _EXECUTION_BATCH_RE.fullmatch(path.name)
            ),
            key=lambda path: path.name,
        )

    def list_top_level_execution_batch_artifacts(self) -> list[Path]:
        plan_dir = self._require_plan_dir()
        return sorted(
            (
                path
                for path in plan_dir.glob("execution_batch_*.json")
                if path.is_file() and _EXECUTION_BATCH_RE.fullmatch(path.name)
            ),
            key=lambda path: path.name,
        )

    def list_task_execution_artifacts(self) -> list[Path]:
        plan_dir = self._require_plan_dir()
        tasks_dir = plan_dir / _TASK_EXECUTION_PARTS[0]
        if not tasks_dir.exists():
            return []
        artifacts: list[Path] = []
        for path in tasks_dir.glob(f"*/{_TASK_EXECUTION_PARTS[1]}"):
            if not path.is_file():
                continue
            try:
                validate_task_key(path.parent.name)
            except (TypeError, ValueError):
                continue
            artifacts.append(path)
        return sorted(artifacts, key=lambda path: path.relative_to(plan_dir).as_posix())

    def list_task_execution_summaries(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in self.list_task_execution_artifacts():
            try:
                payload = read_json(path)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            summaries.append(self._task_execution_summary(path, payload))
        return summaries

    def _task_execution_summary(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = payload.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        identity = metadata.get("identity")
        identity = identity if isinstance(identity, dict) else {}
        trailers = metadata.get("trailers")
        trailers = trailers if isinstance(trailers, dict) else {}
        progress = metadata.get("progress")
        progress = progress if isinstance(progress, dict) else {}
        patch = metadata.get("patch")
        patch = patch if isinstance(patch, dict) else {}
        secret_scan = metadata.get("secret_scan")
        secret_scan = secret_scan if isinstance(secret_scan, dict) else {}
        payload_secret_scan = payload.get("secret_scan")
        payload_secret_scan = payload_secret_scan if isinstance(payload_secret_scan, dict) else {}
        patch_secret_scan = patch.get("secret_scan")
        patch_secret_scan = patch_secret_scan if isinstance(patch_secret_scan, dict) else {}
        registry = metadata.get("registry")
        registry = registry if isinstance(registry, dict) else {}
        integration = metadata.get("integration")
        integration = integration if isinstance(integration, dict) else {}
        integration_entries = [
            entry
            for entry in integration.get("entries", [])
            if isinstance(entry, dict)
        ]
        registry_entries = [
            entry
            for entry in registry.get("entries", [])
            if isinstance(entry, dict)
        ]
        latest_integration = integration_entries[-1] if integration_entries else None
        latest_registry = registry_entries[-1] if registry_entries else None
        latest_entry = latest_integration or latest_registry
        latest_payload = latest_entry.get("payload") if isinstance(latest_entry, dict) else None
        latest_payload = latest_payload if isinstance(latest_payload, dict) else {}
        tier = metadata.get("tier")
        tier = tier if isinstance(tier, dict) else {}
        receipt = metadata.get("receipt")
        receipt = receipt if isinstance(receipt, dict) else {}
        task_key = (
            payload.get("task_key")
            or metadata.get("task_key")
            or identity.get("task_key")
            or path.parent.name
        )
        encoded_task_id = (
            payload.get("task_id_encoded")
            or identity.get("original_task_id_encoded")
            or progress.get("task_id_encoded")
            or trailers.get("Task-Id-B64")
        )
        task_id = payload.get("task_id") or metadata.get("task_id") or progress.get("task_id")
        if not isinstance(task_id, str) and isinstance(encoded_task_id, str):
            try:
                task_id = decode_original_task_id(encoded_task_id)
            except ValueError:
                task_id = None
        status = payload.get("status") or progress.get("status")
        if not isinstance(status, str):
            for update in payload.get("task_updates", []) or []:
                if isinstance(update, dict) and isinstance(update.get("status"), str):
                    status = update["status"]
                    break
        return {
            "task_id": task_id,
            "task_key": task_key,
            "status": status,
            "artifact": path.relative_to(self.plan_dir).as_posix(),
            "artifact_path": str(path),
            "worktree_preserved": bool(payload.get("worktree_preserved")),
            "blocked_reason": payload.get("blocked_reason"),
            "patch": {
                "available": bool(patch.get("available")),
                "manifest_path": patch.get("manifest_path"),
                "patch_path": patch.get("patch_path"),
                "base_head": patch.get("base_head"),
                "sha256": patch.get("sha256"),
                "size_bytes": patch.get("size_bytes"),
                "changed_paths": patch.get("changed_paths", []),
            },
            "secret_scan": {
                "mode": secret_scan.get("mode") or payload_secret_scan.get("mode"),
                "source": secret_scan.get("source") or payload_secret_scan.get("source"),
                "status": patch_secret_scan.get("status") or secret_scan.get("status"),
                "policy": patch_secret_scan.get("policy"),
                "opt_in": patch_secret_scan.get("opt_in"),
            },
            "tier": {
                "task_complexity": tier.get("task_complexity"),
                "tier_model_spec": tier.get("tier_model_spec"),
                "selected_agent": tier.get("resolved_agent") or receipt.get("agent"),
                "selected_mode": tier.get("resolved_mode") or receipt.get("mode"),
                "selected_model": tier.get("resolved_model") or receipt.get("model"),
            },
            "progress": {
                "event": progress.get("event"),
                "status": progress.get("status") or status,
                "sense_check_ids": progress.get("sense_check_ids", []),
                "task_id_encoded": encoded_task_id,
                "task_id_encoding": (
                    payload.get("task_id_encoding")
                    or progress.get("task_id_encoding")
                    or identity.get("original_task_id_encoding")
                ),
            },
            "registry": {
                "available": bool(registry.get("available")),
                "run_id": registry.get("run_id"),
                "entry_count": registry.get("entry_count", len(registry_entries)),
                "latest_entry_type": (
                    latest_registry.get("entry_type")
                    if isinstance(latest_registry, dict)
                    else None
                ),
            },
            "integration": {
                "available": bool(integration.get("available")),
                "state": (
                    latest_integration.get("entry_type")
                    if isinstance(latest_integration, dict)
                    else None
                ),
                "entry_count": len(integration_entries),
                "commit_sha": latest_payload.get("commit_sha"),
                "terminal": latest_payload.get("terminal"),
            },
            "commit_identity": {
                "task_key": task_key,
                "trailers": trailers,
                "trailers_present": bool(trailers),
                "commit_sha": latest_payload.get("commit_sha"),
                "registry_entry_type": (
                    latest_entry.get("entry_type") if isinstance(latest_entry, dict) else None
                ),
            },
        }

    def latest_execution_batch_artifact(self) -> Path | None:
        batches = self.list_execution_batch_artifacts()
        return batches[-1] if batches else None

    def latest_plan_markdown_artifact(self) -> Path | None:
        state = self.load_state()
        plan_versions = state.get("plan_versions") or []
        if not plan_versions:
            return None
        latest = plan_versions[-1]
        if not isinstance(latest, dict):
            return None
        filename = latest.get("file")
        if not isinstance(filename, str) or not filename:
            return None
        path = self.artifact_path(filename)
        return path if path.exists() else None

    def _artifact_kind(self, path: Path) -> str:
        if path.suffix == ".md":
            return "markdown"
        if path.suffix == ".json":
            return "json"
        if path.suffix == ".jsonl":
            return "jsonl"
        if path.suffix == ".lock":
            return "lock"
        if path.suffix == ".txt":
            return "raw_text"
        return "derived"

    def _artifact_role(self, path: Path) -> str | None:
        name = path.name
        if self._is_task_execution_artifact(path):
            return "execution_task"
        if name == "state.json" or (name.startswith("plan_v") and name.endswith(".meta.json")):
            return "plan_meta"
        if name.startswith("plan_v") and name.endswith(".md"):
            return "plan_version"
        if name == "prep.json":
            return "prep"
        if name == "review.json":
            return "review"
        if name.startswith("review_v") and name.endswith("_raw.txt"):
            return "raw_worker_output"
        if name == "gate.json":
            return "gate"
        if name.startswith("gate_signals_v"):
            return "gate_signals"
        if name == "execution.json":
            return "execution"
        if name.startswith("execution_batch_"):
            return "execution_batch"
        if name == "execution_audit.json":
            return "execution_audit"
        if name == "execution_checkpoint.json":
            return "execution_checkpoint"
        if name == "execution_trace.jsonl":
            return "execution_trace"
        if name.startswith("execute_v") and name.endswith("_raw.txt"):
            return "raw_worker_output"
        if name == "finalize.json" or name == "finalize_snapshot.json":
            return "finalize_snapshot" if name == "finalize_snapshot.json" else "finalize"
        if name.startswith("critique"):
            return "critique"
        if name == "faults.json":
            return "faults"
        if name.startswith("step_receipt_"):
            return "receipt"
        if name == "final.md":
            return "derived_final"
        if name == "directors_notes.json":
            return "directors_notes"
        if name == "human_verifications.json":
            return "human_verifications"
        if name == "tiebreaker_decisions.json":
            return "tiebreaker_decisions"
        if name == "tiebreaker_payload.json":
            return "tiebreaker_payload"
        if name == "feedback.md":
            return "feedback"
        if name.endswith(".tmpl") or name.endswith(".template"):
            return "template"
        if name.startswith("research") or name.endswith(".research.json"):
            return "research"
        return None

    def _artifact_version(self, path: Path) -> int | None:
        match = _VERSION_RE.search(path.name)
        return int(match.group(1)) if match is not None else None

    def _artifact_batch(self, path: Path) -> int | None:
        match = _EXECUTION_BATCH_RE.fullmatch(path.name)
        return int(match.group(1)) if match is not None else None

    def _is_task_execution_artifact(self, path: Path) -> bool:
        try:
            parts = path.relative_to(self.plan_dir).parts
        except ValueError:
            return False
        if (
            len(parts) != 3
            or parts[0] != _TASK_EXECUTION_PARTS[0]
            or parts[2] != _TASK_EXECUTION_PARTS[1]
        ):
            return False
        try:
            validate_task_key(parts[1])
        except (TypeError, ValueError):
            return False
        return True

    def _artifact_phase(self, path: Path) -> str | None:
        name = path.name
        if self._is_task_execution_artifact(path):
            return "execute"
        if name == "state.json":
            return "state"
        if name == "final.md":
            return "finalize"
        if name.startswith("step_receipt_"):
            phase = name[len("step_receipt_"):]
            if "_v" in phase:
                return phase.split("_v", 1)[0]
            return phase.removesuffix(".json")
        if name.startswith("execution_batch_"):
            return "execute"
        if "_v" in name:
            return name.split("_v", 1)[0]
        if "." in name:
            return name.split(".", 1)[0]
        return None

    def describe_artifact(self, name: str | Path) -> PlanArtifact:
        path = self._resolve_artifact_path(name)
        if not path.exists():
            raise FileNotFoundError(path)
        role = self._artifact_role(path)
        if role is None:
            raise ValueError(f"Artifact has no typed PlanArtifact role: {path.name}")
        data = path.read_bytes()
        return PlanArtifact(
            name=path.relative_to(self.plan_dir).as_posix(),
            kind=self._artifact_kind(path),
            role=role,
            version=self._artifact_version(path),
            batch=self._artifact_batch(path),
            phase=self._artifact_phase(path),
            sha256="sha256:" + hashlib.sha256(data).hexdigest(),
        )

    def list_artifacts(self) -> list[PlanArtifact]:
        artifacts: list[PlanArtifact] = []
        for name in self.list_artifact_names():
            path = self._resolve_artifact_path(name)
            if self._artifact_role(path) is None:
                continue
            artifacts.append(self.describe_artifact(name))
        return artifacts

    def load_plan(self) -> Plan:
        state = self.load_state()
        review = self.read_artifact_json("review.json")
        finalize = self.read_artifact_json("finalize.json")
        execution = self.read_artifact_json("execution.json")
        latest_failure = None
        resume_cursor = state.get("resume_cursor") if isinstance(state.get("resume_cursor"), dict) else None
        history = state.get("history") or []
        if isinstance(history, list):
            for entry in reversed(history):
                if isinstance(entry, dict) and entry.get("result") == "failed":
                    latest_failure = dict(entry)
                    break
        if latest_failure is None and isinstance(state.get("latest_failure"), dict):
            latest_failure = dict(state["latest_failure"])
        timestamps = [path.stat().st_mtime for path in self.list_artifact_paths()]
        updated_at = (
            datetime.fromtimestamp(max(timestamps), tz=UTC)
            if timestamps
            else datetime.fromisoformat(now_utc().replace("Z", "+00:00"))
        )
        feedback = load_feedback(self.plan_dir)
        feedback_dict = feedback.to_dict() if feedback is not None else None
        return Plan.from_plan_state(
            state,
            plan_id=self.plan_name,
            artifacts=self.list_artifacts(),
            latest_finalize=finalize if isinstance(finalize, dict) else None,
            latest_review=review if isinstance(review, dict) else None,
            latest_execution=execution if isinstance(execution, dict) else None,
            latest_failure=latest_failure,
            resume_cursor=resume_cursor,
            feedback=feedback_dict,
            updated_at=updated_at,
        )

    def save_plan(self, plan: Plan) -> None:
        self.save_state(plan.to_plan_state())

    def record_lifecycle_failure(
        self,
        *,
        kind: str,
        message: str,
        current_state: str,
        phase: str | None,
        resume_cursor: dict[str, Any] | None,
        last_artifact: str | None = None,
        suggested_action: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a queryable failure record and optional resume cursor."""

        state = self.load_state()
        failure: dict[str, Any] = {
            "kind": kind,
            "message": message,
            "phase": phase,
            "state": current_state,
            "recorded_at": now_utc(),
            "last_artifact": last_artifact,
            "suggested_action": suggested_action,
            "metadata": metadata or {},
        }
        state["current_state"] = current_state
        state.pop("active_step", None)
        state["latest_failure"] = failure
        if resume_cursor is None:
            state.pop("resume_cursor", None)
        else:
            state["resume_cursor"] = dict(resume_cursor)
        validate_state_resume_cursor(self.plan_dir, state)
        self.save_state(state)

        epic_id = state.get("epic_id") or (state.get("meta") or {}).get("epic_id")
        if self.store is not None and isinstance(epic_id, str) and epic_id:
            event_kind = "execution_blocked" if current_state == "blocked" else "plan_failed"
            idempotency_key = f"plan-lifecycle:{self.plan_name}:{event_kind}:{phase or 'unknown'}:{kind}"
            self.store.append_progress_event(
                ProgressEventInput(
                    epic_id=epic_id,
                    plan_id=self.plan_name,
                    kind=event_kind,
                    summary=message,
                    details=failure,
                    idempotency_key=idempotency_key,
                ),
                idempotency_key=idempotency_key,
            )
        return failure
