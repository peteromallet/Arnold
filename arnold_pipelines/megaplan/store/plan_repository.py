"""Plan-tree access seam for Sprint 1 file mode."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arnold.pipeline.artifact_io import (
    ArtifactIOBlocked,
    validate_artifact_io,
)
from arnold.pipeline.step_io_contract import (
    StepIOContractContext,
    StepIOEnvelope,
    StepIOOperation,
    decide_step_io_read,  # re-exported for back-compat monkeypatching
    decide_step_io_write,  # re-exported for back-compat monkeypatching
    is_step_io_envelope,
)
from arnold.pipeline.step_io_policy import (  # re-exported for back-compat monkeypatching
    decision_blocks_read,
    decision_blocks_write,
)
from arnold.pipeline.step_io_telemetry import emit_decision_telemetry  # re-exported for back-compat
from arnold_pipelines.megaplan.runtime.schema_registry_adapter import (
    create_step_io_contract_context,
)
from arnold.pipeline.step_io_telemetry import TELEMETRY_FILENAME
from arnold_pipelines.megaplan._core.io import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    batch_artifact_index,
    find_plan_dir,
    now_utc,
    plan_search_roots,
    read_json,
)
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.runtime.step_io_policy_adapter import (
    megaplan_policy_for_envelope,
    resolve_megaplan_step_io_policy,
)
from arnold_pipelines.megaplan.orchestration.feedback import load_feedback
from arnold_pipelines.megaplan.schemas import Plan, PlanArtifact
from arnold_pipelines.megaplan.store.base import ProgressEventInput

from .base import Store

_EXECUTION_BATCH_RE = re.compile(r"execution_batch_(\d+)\.json$")
_VERSION_RE = re.compile(r"_v(\d+)(?:\.|_|$)")


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
        repo = cls(plan_dir, store=store, home=home)
        if store is not None and repo.is_bound:
            from arnold_pipelines.megaplan.observability.events_projection import ensure_events_projection

            ensure_events_projection(repo.plan_dir, store=store, plan_id=repo.plan_name)
        return repo

    @classmethod
    def from_artifact_dir(
        cls,
        plan_dir: str | Path,
        *,
        store: Store | None = None,
        home: str | Path | None = None,
    ) -> PlanRepository:
        """Bind directly to an artifact directory even if ``state.json`` is absent."""

        repo = cls(plan_dir, store=store, home=home)
        repo._plan_dir = Path(plan_dir)
        return repo

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

    def read_artifact_json(
        self,
        name: str | Path,
        *,
        contract_context: StepIOContractContext | None = None,
        contract_binding: Any = None,
    ) -> Any | None:
        path = self._resolve_artifact_path(name)
        if not path.exists():
            return None
        value = read_json(path)
        if contract_context is None and not is_step_io_envelope(value):
            return value
        envelope = StepIOEnvelope.from_json(value) if is_step_io_envelope(value) else None
        policy = megaplan_policy_for_envelope(
            envelope,
            plan_dir=self.plan_dir,
            binding=contract_binding,
        )
        context = contract_context or create_step_io_contract_context(
            operation=StepIOOperation.READ,
            explicit_root=self.plan_dir,
        )
        result = validate_artifact_io(
            value,
            operation=StepIOOperation.READ,
            policy=policy,
            contract_context=context,
            artifact=Path(name).as_posix(),
            telemetry_path=self.plan_dir / TELEMETRY_FILENAME,
        )
        return result.value

    def write_artifact_bytes(self, name: str | Path, data: bytes) -> Path:
        path = self._resolve_artifact_path(name)
        atomic_write_bytes(path, data)
        return path

    def write_artifact_text(self, name: str | Path, data: str) -> Path:
        path = self._resolve_artifact_path(name)
        atomic_write_text(path, data)
        return path

    def write_artifact_json(
        self,
        name: str | Path,
        data: Any,
        *,
        contract_context: StepIOContractContext | None = None,
        contract_binding: Any = None,
    ) -> Path:
        path = self._resolve_artifact_path(name)
        if contract_context is not None and not is_step_io_envelope(data):
            # When a contract_context is explicitly provided but the data is legacy
            # (not a typed envelope), the writer intends to participate in typed
            # enforcement.  Resolve the policy as though the producer is typed so
            # that enforce mode can block legacy payloads until they are upgraded
            # to typed envelopes.  The binding (when available) supplies the
            # actual typed status of both sides of the seam.
            policy = resolve_megaplan_step_io_policy(
                plan_dir=self.plan_dir,
                binding=contract_binding,
                producer_typed=True,
                read_lenient_escape=False,
            )
            if policy.enforces:
                raise ValueError(
                    "typed artifact write blocked: missing typed step-IO envelope "
                    "required in enforce mode"
                )
            # shadow / warn / off: legacy payloads pass through unchanged
        if is_step_io_envelope(data):
            envelope = StepIOEnvelope.from_json(data)
            policy = megaplan_policy_for_envelope(
                envelope,
                plan_dir=self.plan_dir,
                binding=contract_binding,
                read_lenient_escape=False,
            )
            context = contract_context or create_step_io_contract_context(
                operation=StepIOOperation.WRITE,
                explicit_root=self.plan_dir,
            )
            validate_artifact_io(
                data,
                operation=StepIOOperation.WRITE,
                policy=policy,
                contract_context=context,
                artifact=Path(name).as_posix(),
                telemetry_path=self.plan_dir / TELEMETRY_FILENAME,
            )
        atomic_write_json(path, data)
        return path

    def delete_artifact(self, name: str | Path) -> None:
        path = self._resolve_artifact_path(name)
        if path.exists():
            path.unlink()

    def load_state(self) -> dict[str, Any]:
        from arnold_pipelines.megaplan._core.io import read_plan_state_cached
        return read_plan_state_cached(self.plan_dir, mode="authority")

    def save_state(self, state: dict[str, Any]) -> None:
        write_plan_state(self.plan_dir, mode="replace", state=state)

    def list_execution_batch_artifacts(self) -> list[Path]:
        # Route through the shared io helper so both the S4 directory layout
        # (execute_batches/batch_{index}/tasks_*.json) and the legacy flat
        # layout (execution_batch_{N}.json) are recognised. Legacy-only callers
        # are unaffected because the helper still matches the flat form.
        indexed = [
            (batch_artifact_index(path), path)
            for path in self.list_artifact_paths()
            if batch_artifact_index(path) is not None
        ]
        return [path for _, path in sorted(indexed, key=lambda item: item[0])]

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
        if name == "contract.json":
            return "contract"
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
        return batch_artifact_index(path)

    def _artifact_phase(self, path: Path) -> str | None:
        name = path.name
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


def write_plan_artifact_json(
    plan_dir: str | Path,
    name: str | Path,
    data: Any,
    *,
    contract_context: StepIOContractContext | None = None,
) -> Path:
    """Write a plan artifact without requiring a bound ``state.json``."""

    return PlanRepository.from_artifact_dir(plan_dir).write_artifact_json(
        name,
        data,
        contract_context=contract_context,
    )
