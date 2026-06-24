from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan.schemas import Plan
from arnold.pipelines.megaplan.schemas.base import utc_now

from ..base import ArtifactRef, ArtifactStat, validate_plan_artifact_name
from .common import _parse_datetime


class FilePlanMixin:
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
