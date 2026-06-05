"""Plan and lease mixins for DBStore."""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping

from arnold.pipelines.megaplan.schemas import EpicLock, ExecutionLease, Plan, PlanArtifact
from arnold.pipelines.megaplan.store.base import ArtifactRef, ArtifactStat, LeaseConflict, LockConflict, RevisionConflict, validate_plan_artifact_name

from .common import _ARTIFACT_VALID_FIELDS, _PLAN_COLUMNS, _PLAN_JSONB, _jb

class DBPlanMixin:
    def _load_plan_artifacts(
        self, conn: Any, plan_id: str
    ) -> list[PlanArtifact]:
        rows = conn.execute(
            "SELECT * FROM plan_artifacts WHERE plan_id = %s ORDER BY created_at",
            [plan_id],
        ).fetchall()
        artifacts = []
        for row in rows:
            data = {k: v for k, v in row.items() if k in _ARTIFACT_VALID_FIELDS}
            content_bytes = row.get("content_bytes")
            if content_bytes is not None:
                data["content_base64"] = base64.b64encode(bytes(content_bytes)).decode("ascii")
            artifacts.append(PlanArtifact(**data))
        return artifacts

    def _plan_artifact_bytes(self, row: Mapping[str, Any]) -> bytes:
        content_bytes = row.get("content_bytes")
        if content_bytes is not None:
            return bytes(content_bytes)
        content_text = row.get("content_text")
        if content_text is None:
            return b""
        return content_text.encode("utf-8")

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
        conn = self._get_conn()
        plan_id = str(uuid.uuid4())
        data: dict[str, Any] = {
            "id": plan_id,
            "name": name,
            "epic_id": epic_id,
            "sprint_id": sprint_id,
            "idea": idea,
        }
        for k, v in fields.items():
            if k in _PLAN_COLUMNS:
                data[k] = v
        cols = list(data.keys())
        vals = [_jb(v) if k in _PLAN_JSONB else v for k, v in data.items()]
        col_str = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        returning = ", ".join(_PLAN_COLUMNS)
        row = conn.execute(
            f"INSERT INTO plans ({col_str}) VALUES ({placeholders}) RETURNING {returning}",
            vals,
        ).fetchone()
        artifacts = self._load_plan_artifacts(conn, plan_id)
        return Plan(**row, artifacts=artifacts)

    def load_plan(self, plan_id: str) -> Plan | None:
        conn = self._get_conn()
        col_str = ", ".join(_PLAN_COLUMNS)
        row = conn.execute(
            f"SELECT {col_str} FROM plans WHERE id = %s",
            [plan_id],
        ).fetchone()
        if row is None:
            return None
        artifacts = self._load_plan_artifacts(conn, plan_id)
        return Plan(**row, artifacts=artifacts)

    def update_plan(
        self,
        plan_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Plan:
        conn = self._get_conn()
        if not changes:
            plan = self.load_plan(plan_id)
            if plan is None:
                raise RevisionConflict(f"Plan {plan_id!r} not found")
            return plan
        set_parts = [f"{k} = %s" for k in changes]
        set_parts.extend(["revision = revision + 1", "updated_at = now()"])
        col_str = ", ".join(_PLAN_COLUMNS)
        values = [_jb(v) if k in _PLAN_JSONB else v for k, v in changes.items()]
        values += [plan_id, expected_revision, expected_revision]
        row = conn.execute(
            f"""
            UPDATE plans
            SET {', '.join(set_parts)}
            WHERE id = %s AND (%s IS NULL OR revision = %s)
            RETURNING {col_str}
            """,
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Revision conflict on plan {plan_id!r}")
        artifacts = self._load_plan_artifacts(conn, plan_id)
        return Plan(**row, artifacts=artifacts)

    def list_plans(
        self,
        *,
        sprint_id: str | None = None,
        epic_id: str | None = None,
        include_orphans: bool = False,
    ) -> list[Plan]:
        conn = self._get_conn()
        col_str = ", ".join(_PLAN_COLUMNS)
        conditions: list[str] = []
        values: list[Any] = []
        if sprint_id is not None:
            conditions.append("sprint_id = %s")
            values.append(sprint_id)
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if not include_orphans:
            conditions.append("(epic_id IS NOT NULL OR sprint_id IS NOT NULL)")
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT {col_str} FROM plans{where} ORDER BY created_at DESC",
            values,
        ).fetchall()
        result = []
        for row in rows:
            artifacts = self._load_plan_artifacts(conn, row["id"])
            result.append(Plan(**row, artifacts=artifacts))
        return result

    def write_plan_artifact(
        self,
        plan_id: str,
        name: str,
        data: bytes,
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactRef:
        name = validate_plan_artifact_name(name)
        conn = self._get_conn()
        sha256 = hashlib.sha256(data).hexdigest()
        try:
            content_text: str | None = data.decode("utf-8")
        except UnicodeDecodeError:
            content_text = None
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        kind_map = {"json": "json", "md": "markdown", "jsonl": "jsonl"}
        kind = kind_map.get(ext, "raw_text")
        stem = name.rsplit("/", 1)[-1].split(".")[0]
        if stem.startswith("plan_v"):
            role = "plan_version"
        elif stem in ("gate_signals", "gate"):
            role = "gate_signals"
        elif stem.startswith("critique"):
            role = "critique"
        elif stem.startswith("step_receipt"):
            role = "step_receipt"
        elif stem.startswith("execute"):
            role = "execution_output"
        elif stem.startswith("finalize"):
            role = "finalize"
        elif stem.startswith("faults"):
            role = "faults"
        else:
            role = "template"
        row = conn.execute(
            """
            INSERT INTO plan_artifacts (plan_id, name, kind, role, sha256, content_text, content_bytes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (plan_id, name) DO UPDATE SET
                sha256 = EXCLUDED.sha256,
                content_text = EXCLUDED.content_text,
                content_bytes = EXCLUDED.content_bytes,
                kind = EXCLUDED.kind,
                role = EXCLUDED.role,
                updated_at = now()
            RETURNING plan_id, name, kind, role, sha256, updated_at,
                      COALESCE(octet_length(content_bytes), octet_length(content_text), 0) AS size_bytes
            """,
            [plan_id, name, kind, role, sha256, content_text, data],
        ).fetchone()
        return ArtifactRef(
            plan_id=row["plan_id"],
            name=row["name"],
            kind=row["kind"],
            role=row["role"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            updated_at=row["updated_at"],
        )

    def read_plan_artifact(self, plan_id: str, name: str) -> bytes | None:
        name = validate_plan_artifact_name(name)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content_text, content_bytes FROM plan_artifacts WHERE plan_id = %s AND name = %s",
            [plan_id, name],
        ).fetchone()
        if row is None:
            return None
        return self._plan_artifact_bytes(row)

    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT plan_id, name, kind, role, sha256, updated_at,
                   COALESCE(octet_length(content_bytes), octet_length(content_text), 0) AS size_bytes
            FROM plan_artifacts
            WHERE plan_id = %s
            ORDER BY name
            """,
            [plan_id],
        ).fetchall()
        return [
            ArtifactRef(
                plan_id=row["plan_id"],
                name=row["name"],
                kind=row["kind"],
                role=row["role"],
                sha256=row["sha256"],
                size_bytes=row["size_bytes"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def stat_plan_artifact(self, plan_id: str, name: str) -> ArtifactStat | None:
        name = validate_plan_artifact_name(name)
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT plan_id, name, sha256, updated_at,
                   COALESCE(octet_length(content_bytes), octet_length(content_text), 0) AS size_bytes
            FROM plan_artifacts
            WHERE plan_id = %s AND name = %s
            """,
            [plan_id, name],
        ).fetchone()
        if row is None:
            return None
        return ArtifactStat(
            plan_id=row["plan_id"],
            name=row["name"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            updated_at=row["updated_at"],
        )

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
        conn = self._get_conn()
        if epic_id is None:
            plan_row = conn.execute("SELECT epic_id FROM plans WHERE id = %s", [plan_id]).fetchone()
            epic_id = plan_row["epic_id"] if plan_row else None
        try:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM execution_leases WHERE plan_id = %s AND expires_at <= now()",
                    [plan_id],
                )
                row = conn.execute(
                    """
                    INSERT INTO execution_leases (plan_id, epic_id, holder_id, worker_kind, phase, expires_at)
                    VALUES (%s, %s, %s, %s, 'active', now() + make_interval(secs => %s))
                    RETURNING *
                    """,
                    [plan_id, epic_id, holder_id, worker_kind, ttl_seconds],
                ).fetchone()
        except Exception as exc:
            if getattr(exc, "pgcode", None) == "23505":
                raise LeaseConflict(
                    f"Execution lease already held for plan {plan_id!r}"
                ) from exc
            raise
        return ExecutionLease(**row)

    def heartbeat_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> ExecutionLease:
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE execution_leases
            SET heartbeat_at = now(),
                expires_at = now() + (expires_at - heartbeat_at)
            WHERE plan_id = %s AND holder_id = %s
            RETURNING *
            """,
            [plan_id, holder_id],
        ).fetchone()
        if row is None:
            raise LeaseConflict(f"No active lease for plan {plan_id!r} holder {holder_id!r}")
        return ExecutionLease(**row)

    def release_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM execution_leases WHERE plan_id = %s AND holder_id = %s",
            [plan_id, holder_id],
        )

    def get_active_lease(self, plan_id: str) -> ExecutionLease | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM execution_leases WHERE plan_id = %s AND expires_at > now()",
            [plan_id],
        ).fetchone()
        return ExecutionLease(**row) if row else None

    def find_active_leases_for_epic(self, epic_id: str) -> list[ExecutionLease]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM execution_leases
            WHERE epic_id = %s AND expires_at > now()
            ORDER BY expires_at, plan_id
            """,
            [epic_id],
        ).fetchall()
        return [ExecutionLease(**row) for row in rows]

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> EpicLock:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO epic_locks (epic_id, holder_id, expires_at)
            VALUES (%s, %s, now() + make_interval(secs => %s))
            ON CONFLICT (epic_id) DO UPDATE
            SET holder_id = EXCLUDED.holder_id,
                acquired_at = now(),
                expires_at = EXCLUDED.expires_at
            WHERE epic_locks.expires_at <= now()
               OR epic_locks.holder_id = EXCLUDED.holder_id
            RETURNING *
            """,
            [epic_id, holder_id, ttl_seconds],
        ).fetchone()
        if row is None:
            raise LockConflict(f"Epic lock already held for epic {epic_id!r}")
        return EpicLock(**row)

    def release_lock(self, epic_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM epic_locks WHERE epic_id = %s AND holder_id = %s",
            [epic_id, holder_id],
        )

__all__ = ["DBPlanMixin"]
