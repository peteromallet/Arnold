"""Migration helpers for DBStore."""

from __future__ import annotations

import base64
from typing import Any, Mapping, Sequence

from megaplan.schemas import MigrationRun, PlanArtifact
from megaplan.store.base import LeaseConflict, validate_plan_artifact_name

from .common import _COPY_JSONB_COLUMNS, _COPY_TABLE_COLUMNS, _MIGRATION_RUN_COLUMNS, _MIGRATION_RUN_JSONB, _jb

class DBMigrationMixin:
    def _migration_run_from_row(self, row: Mapping[str, Any] | None) -> MigrationRun | None:
        return MigrationRun(**row) if row else None

    def create_migration_run(
        self,
        run: MigrationRun,
        *,
        idempotency_key: str | None = None,
    ) -> MigrationRun:
        self._require_actor()
        conn = self._get_conn()
        data = run.model_dump()
        columns = [column for column in _MIGRATION_RUN_COLUMNS if column in data]
        values = [_jb(data[column]) if column in _MIGRATION_RUN_JSONB else data[column] for column in columns]
        row = conn.execute(
            f"""
            INSERT INTO migration_runs ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            values,
        ).fetchone()
        return MigrationRun(**row)

    def load_migration_run(self, migration_id: str) -> MigrationRun | None:
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT {', '.join(_MIGRATION_RUN_COLUMNS)} FROM migration_runs WHERE id = %s",
            [migration_id],
        ).fetchone()
        return self._migration_run_from_row(row)

    def update_migration_run(
        self,
        migration_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> MigrationRun:
        self._require_actor()
        if not changes:
            current = self.load_migration_run(migration_id)
            if current is None:
                raise KeyError(f"Migration run {migration_id!r} not found")
            return current
        invalid = set(changes) - set(_MIGRATION_RUN_COLUMNS)
        if invalid:
            raise ValueError(f"Invalid migration_run columns: {', '.join(sorted(invalid))}")
        conn = self._get_conn()
        set_parts = [f"{column} = %s" for column in changes]
        set_parts.append("updated_at = now()")
        values = [
            _jb(value) if column in _MIGRATION_RUN_JSONB else value
            for column, value in changes.items()
        ]
        values.append(migration_id)
        row = conn.execute(
            f"""
            UPDATE migration_runs
            SET {', '.join(set_parts)}
            WHERE id = %s
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            values,
        ).fetchone()
        if row is None:
            raise KeyError(f"Migration run {migration_id!r} not found")
        return MigrationRun(**row)

    def heartbeat_migration(
        self,
        migration_id: str,
        holder_id: str,
        ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> MigrationRun:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            f"""
            UPDATE migration_runs
            SET updated_at = now(),
                expires_at = now() + make_interval(secs => %s)
            WHERE id = %s
              AND holder_id = %s
              AND completed_at IS NULL
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            [ttl_seconds, migration_id, holder_id],
        ).fetchone()
        if row is None:
            raise LeaseConflict(f"Migration {migration_id!r} is not held by {holder_id!r}")
        return MigrationRun(**row)

    def find_active_migration_for_epic(self, epic_id: str) -> MigrationRun | None:
        conn = self._get_conn()
        row = conn.execute(
            f"""
            SELECT {', '.join(_MIGRATION_RUN_COLUMNS)}
            FROM migration_runs
            WHERE epic_id = %s
              AND completed_at IS NULL
              AND phase NOT IN ('complete', 'aborted')
              AND expires_at > now()
            ORDER BY started_at DESC
            LIMIT 1
            """,
            [epic_id],
        ).fetchone()
        return self._migration_run_from_row(row)

    def claim_expired_migration(
        self,
        migration_id: str,
        holder_id: str,
        ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> MigrationRun:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            f"""
            UPDATE migration_runs
            SET holder_id = %s,
                updated_at = now(),
                expires_at = now() + make_interval(secs => %s)
            WHERE id = %s
              AND completed_at IS NULL
              AND phase NOT IN ('complete', 'aborted')
              AND expires_at <= now()
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            [holder_id, ttl_seconds, migration_id],
        ).fetchone()
        if row is None:
            raise LeaseConflict(f"Migration {migration_id!r} is still active or does not exist")
        return MigrationRun(**row)

    def _copy_sql_identifiers(self, names: Sequence[str]) -> Any:
        import psycopg

        return psycopg.sql.SQL(", ").join(psycopg.sql.Identifier(name) for name in names)

    def copy_rows_idempotent(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Migration-private copy path for ID-addressed tables.

        Plan artifacts are deliberately excluded because their durable identity is
        ``(plan_id, name)``; use copy_plan_artifacts_idempotent() for those rows.
        """
        self._require_actor()
        if table == "plan_artifacts":
            raise ValueError("plan_artifacts must be copied with copy_plan_artifacts_idempotent")
        allowed_columns = _COPY_TABLE_COLUMNS.get(table)
        if allowed_columns is None:
            raise ValueError(f"Table {table!r} is not supported for migration copy")
        if not rows:
            return 0
        conn = self._get_conn()
        import psycopg
        inserted = 0
        with conn.transaction():
            for raw_row in rows:
                row = dict(raw_row)
                if "id" not in row:
                    raise ValueError(f"Cannot copy row for {table!r} without id")
                columns = [column for column in row if column in allowed_columns]
                if not columns:
                    raise ValueError(f"Row for {table!r} has no supported columns")
                values = [_jb(row[column]) if column in _COPY_JSONB_COLUMNS else row[column] for column in columns]
                query = psycopg.sql.SQL(
                    "INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
                    "ON CONFLICT (id) DO NOTHING"
                ).format(
                    table=psycopg.sql.Identifier(table),
                    columns=self._copy_sql_identifiers(columns),
                    placeholders=psycopg.sql.SQL(", ").join(psycopg.sql.Placeholder() for _ in columns),
                )
                cur = conn.execute(query, values)
                inserted += cur.rowcount
        return inserted

    def copy_plan_artifacts_idempotent(
        self,
        plan_id: str,
        artifacts: list[PlanArtifact],
    ) -> int:
        self._require_actor()
        if not artifacts:
            return 0
        conn = self._get_conn()
        import psycopg
        inserted = 0
        with conn.transaction():
            for artifact in artifacts:
                data = artifact.model_dump()
                name = validate_plan_artifact_name(data["name"])
                row = {
                    "plan_id": plan_id,
                    "name": name,
                    "kind": data["kind"],
                    "role": data["role"],
                    "version": data.get("version"),
                    "batch": data.get("batch"),
                    "phase": data.get("phase"),
                    "content_text": data.get("content_text"),
                    "content_bytes": (
                        base64.b64decode(data["content_base64"])
                        if data.get("content_base64") is not None
                        else None
                    ),
                    "sha256": data["sha256"],
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                }
                columns = [column for column, value in row.items() if value is not None]
                values = [row[column] for column in columns]
                query = psycopg.sql.SQL(
                    "INSERT INTO plan_artifacts ({columns}) VALUES ({placeholders}) "
                    "ON CONFLICT (plan_id, name) DO NOTHING"
                ).format(
                    columns=self._copy_sql_identifiers(columns),
                    placeholders=psycopg.sql.SQL(", ").join(psycopg.sql.Placeholder() for _ in columns),
                )
                cur = conn.execute(query, values)
                inserted += cur.rowcount
        return inserted

__all__ = ["DBMigrationMixin"]
