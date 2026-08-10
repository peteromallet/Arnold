"""Postgres-backed native persistence backend.

The backend owns only durable storage for the native persistence protocol. It
does not decide routing, loop exits, replay policy, or runtime control flow.
Mutable cursor/gate operations run inside explicit psycopg transactions, while
audit and event appends remain independent append-only writes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.persistence import (
    NativePersistenceBackend,
    NativePersistenceScope,
    OrderedPersistenceRow,
    ResolvedResumeSurface,
    ResumeSurfaceObservation,
    TraceArtifactName,
    TypedResumeMetadata,
)


_TRACE_ARTIFACT_NAMES: set[str] = {
    "state.json",
    "events.ndjson",
    "stages.json",
    "artifacts.json",
    "checkpoint.json",
    "tree.json",
}
_MIGRATION_DIR = Path(__file__).with_name("migrations")


class PostgresNativePersistenceBackend:
    """psycopg3 implementation of :class:`NativePersistenceBackend`.

    Parameters
    ----------
    conninfo:
        psycopg connection string. When supplied, each backend operation opens
        its own connection and closes it after the transaction completes.
    connection:
        Existing psycopg connection. The backend does not close caller-owned
        connections.
    apply_migrations:
        Apply Arnold-owned migrations during initialization. This is convenient
        for local development and tests; production callers may apply migration
        files separately and pass ``False``.
    """

    def __init__(
        self,
        conninfo: str | None = None,
        *,
        connection: Any | None = None,
        apply_migrations: bool = True,
        migrations_dir: str | Path | None = None,
    ) -> None:
        if (conninfo is None) == (connection is None):
            raise ValueError("provide exactly one of conninfo or connection")
        self._conninfo = conninfo
        self._connection = connection
        self._migrations_dir = Path(migrations_dir) if migrations_dir is not None else _MIGRATION_DIR
        if apply_migrations:
            self.apply_migrations()

    def apply_migrations(self) -> None:
        """Apply bundled SQL migrations idempotently inside one transaction."""

        migrations = sorted(self._migrations_dir.glob("*.sql"))
        with self._connect() as conn:
            with conn.transaction():
                for path in migrations:
                    version = path.stem
                    if self._migration_applied(conn, version):
                        continue
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO arnold_native_schema_migrations (version) VALUES (%s)",
                        (version,),
                    )

    def write_resume_cursor(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        self._upsert_payload("arnold_native_resume_checkpoints", scope, payload)
        return self._artifact_ref(scope, "resume_cursor.json")

    def read_resume_cursor(self, scope: NativePersistenceScope) -> dict[str, Any] | None:
        return self._read_payload("arnold_native_resume_checkpoints", scope)

    def delete_resume_cursor(self, scope: NativePersistenceScope) -> None:
        self._delete_scope_row("arnold_native_resume_checkpoints", scope)

    def read_state_resume_cursor(self, scope: NativePersistenceScope) -> dict[str, Any] | None:
        state = self.read_trace_artifact(scope, name="state.json")
        if not isinstance(state, dict):
            return None
        cursor = state.get("resume_cursor")
        return dict(cursor) if isinstance(cursor, dict) else None

    def write_composite_resume_cursor(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        self._upsert_payload("arnold_native_composite_cursors", scope, payload)
        return self._artifact_ref(scope, "composite_resume_cursor.json")

    def read_composite_resume_cursor(self, scope: NativePersistenceScope) -> dict[str, Any] | None:
        return self._read_payload("arnold_native_composite_cursors", scope)

    def delete_composite_resume_cursor(self, scope: NativePersistenceScope) -> None:
        self._delete_scope_row("arnold_native_composite_cursors", scope)

    def write_human_gate(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        self._upsert_payload("arnold_native_human_gates", scope, payload)
        return self._artifact_ref(scope, "awaiting_user.json")

    def read_human_gate(self, scope: NativePersistenceScope) -> dict[str, Any] | None:
        return self._read_payload("arnold_native_human_gates", scope)

    def delete_human_gate(self, scope: NativePersistenceScope) -> None:
        self._delete_scope_row("arnold_native_human_gates", scope)

    def resolve_resume_surface(self, scope: NativePersistenceScope) -> ResolvedResumeSurface:
        observations = (
            self._inspect_state_resume_cursor(scope),
            self._inspect_typed_contract(scope),
            self._inspect_composite_resume_cursor(scope),
            self._inspect_human_gate(scope),
            self._inspect_resume_cursor(scope),
        )
        for observation in observations:
            if not observation.present:
                continue
            return ResolvedResumeSurface(
                source=observation.source,
                kind=observation.kind,
                blocked=not observation.valid,
                payload=observation.payload,
                path=observation.path,
                diagnostic=observation.diagnostic,
                observations=observations,
            )
        return ResolvedResumeSurface(
            source="none",
            kind="none",
            blocked=False,
            observations=observations,
        )

    def append_audit_record(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> OrderedPersistenceRow:
        payload_dict = dict(payload)
        raw_kind = payload_dict.get("event")
        kind = raw_kind if isinstance(raw_kind, str) else "audit"
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO arnold_native_audit_records
                        (project_id, run_id, artifact_id, kind, payload)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING sequence, kind, payload
                    """,
                    (*self._scope_params(scope), kind, jsonb(payload_dict)),
                ).fetchone()
        return self._ordered_row(row)

    def read_audit_records(self, scope: NativePersistenceScope) -> list[OrderedPersistenceRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sequence, kind, payload
                FROM arnold_native_audit_records
                WHERE project_id = %s AND run_id = %s AND artifact_id = %s
                ORDER BY sequence ASC
                """,
                self._scope_params(scope),
            ).fetchall()
        return [self._ordered_row(row) for row in rows]

    def emit_event(
        self,
        scope: NativePersistenceScope,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        phase: str | None = None,
        idempotency_key: str | None = None,
        event_scope: str | None = None,
    ) -> OrderedPersistenceRow:
        payload_dict = dict(payload or {})
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                sequence = self._first_value(
                    conn.execute("SELECT nextval('arnold_native_event_sequence')").fetchone()
                )
                event = {
                    "seq": int(sequence),
                    "schema_version": 1,
                    "ts_utc": datetime.now(timezone.utc).isoformat(),
                    "ts_rel_init_s": None,
                    "kind": kind,
                    "payload": payload_dict,
                }
                if event_scope is not None:
                    event["scope"] = event_scope
                if phase is not None:
                    event["phase"] = phase
                if idempotency_key is not None:
                    event["idempotency_key"] = idempotency_key
                row = conn.execute(
                    """
                    INSERT INTO arnold_native_ordered_events
                        (sequence, project_id, run_id, artifact_id, kind, phase,
                         idempotency_key, event_scope, payload, event)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING sequence, kind, event AS payload
                    """,
                    (
                        int(sequence),
                        *self._scope_params(scope),
                        kind,
                        phase,
                        idempotency_key,
                        event_scope,
                        jsonb(payload_dict),
                        jsonb(event),
                    ),
                ).fetchone()
        return self._ordered_row(row)

    def read_events(
        self,
        scope: NativePersistenceScope,
        *,
        since_sequence: int | None = None,
        to_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[OrderedPersistenceRow]:
        clauses = ["project_id = %s", "run_id = %s", "artifact_id = %s"]
        params: list[Any] = list(self._scope_params(scope))
        if since_sequence is not None:
            clauses.append("sequence > %s")
            params.append(since_sequence)
        if to_sequence is not None:
            clauses.append("sequence < %s")
            params.append(to_sequence)
        sql = f"""
            SELECT sequence, kind, event AS payload
            FROM arnold_native_ordered_events
            WHERE {' AND '.join(clauses)}
            ORDER BY sequence ASC
        """
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._ordered_row(row) for row in rows]

    def write_trace_artifact(
        self,
        scope: NativePersistenceScope,
        *,
        name: TraceArtifactName,
        payload: Any,
    ) -> str | None:
        if name not in _TRACE_ARTIFACT_NAMES:
            raise ValueError(f"unsupported trace artifact name: {name!r}")
        if name == "events.ndjson" and isinstance(payload, str):
            payload = self._decode_ndjson(payload)
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO arnold_native_trace_artifacts
                        (project_id, run_id, artifact_id, name, payload, updated_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (project_id, run_id, artifact_id, name)
                    DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (*self._scope_params(scope), name, jsonb(payload)),
                )
        return self._artifact_ref(scope, name)

    def read_trace_artifact(
        self,
        scope: NativePersistenceScope,
        *,
        name: TraceArtifactName,
    ) -> Any:
        if name not in _TRACE_ARTIFACT_NAMES:
            raise ValueError(f"unsupported trace artifact name: {name!r}")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload
                FROM arnold_native_trace_artifacts
                WHERE project_id = %s AND run_id = %s AND artifact_id = %s AND name = %s
                """,
                (*self._scope_params(scope), name),
            ).fetchone()
        return self._payload_from_row(row)

    def _upsert_payload(
        self,
        table: str,
        scope: NativePersistenceScope,
        payload: Mapping[str, Any],
    ) -> None:
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    f"""
                    INSERT INTO {table}
                        (project_id, run_id, artifact_id, payload, updated_at)
                    VALUES (%s, %s, %s, %s, now())
                    ON CONFLICT (project_id, run_id, artifact_id)
                    DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (*self._scope_params(scope), jsonb(dict(payload))),
                )

    def _read_payload(self, table: str, scope: NativePersistenceScope) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT payload
                FROM {table}
                WHERE project_id = %s AND run_id = %s AND artifact_id = %s
                """,
                self._scope_params(scope),
            ).fetchone()
        payload = self._payload_from_row(row)
        return dict(payload) if isinstance(payload, dict) else None

    def _delete_scope_row(self, table: str, scope: NativePersistenceScope) -> None:
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE project_id = %s AND run_id = %s AND artifact_id = %s
                    """,
                    self._scope_params(scope),
                )

    def _inspect_state_resume_cursor(self, scope: NativePersistenceScope) -> ResumeSurfaceObservation:
        path = self._artifact_ref(scope, "state.json")
        state = self.read_trace_artifact(scope, name="state.json")
        if state is None:
            return self._missing_observation("state_resume_cursor", path)
        if not isinstance(state, dict):
            return ResumeSurfaceObservation(
                source="state_resume_cursor",
                present=True,
                valid=False,
                kind="invalid_state",
                path=path,
                payload=state,
                diagnostic="state.json must contain a JSON object",
            )
        cursor = state.get("resume_cursor")
        if cursor is None:
            return self._missing_observation("state_resume_cursor", path)
        if not isinstance(cursor, dict):
            return ResumeSurfaceObservation(
                source="state_resume_cursor",
                present=True,
                valid=False,
                kind="invalid_state_resume_cursor",
                path=path,
                payload=cursor,
                diagnostic="state.json::resume_cursor must be a JSON object",
            )
        return ResumeSurfaceObservation(
            source="state_resume_cursor",
            present=True,
            valid=True,
            kind="state_resume_cursor",
            path=path,
            payload=dict(cursor),
        )

    def _inspect_typed_contract(self, scope: NativePersistenceScope) -> ResumeSurfaceObservation:
        path = self._artifact_ref(scope, "state.json")
        metadata = self._extract_typed_resume_metadata(scope)
        if metadata is None:
            return self._missing_observation("typed_contract", path)
        return ResumeSurfaceObservation(
            source="typed_contract",
            present=True,
            valid=True,
            kind="typed_contract",
            path=path,
            payload=metadata,
        )

    def _inspect_composite_resume_cursor(self, scope: NativePersistenceScope) -> ResumeSurfaceObservation:
        path = self._artifact_ref(scope, "composite_resume_cursor.json")
        payload = self.read_composite_resume_cursor(scope)
        if payload is None:
            return self._missing_observation("composite_resume_cursor", path)
        if payload.get("kind") != "composite_suspension":
            return ResumeSurfaceObservation(
                source="composite_resume_cursor",
                present=True,
                valid=False,
                kind="invalid_composite_resume_cursor",
                path=path,
                payload=payload,
                diagnostic="composite_resume_cursor.json must declare kind='composite_suspension'",
            )
        return ResumeSurfaceObservation(
            source="composite_resume_cursor",
            present=True,
            valid=True,
            kind="composite_resume_cursor",
            path=path,
            payload=payload,
        )

    def _inspect_human_gate(self, scope: NativePersistenceScope) -> ResumeSurfaceObservation:
        path = self._artifact_ref(scope, "awaiting_user.json")
        payload = self.read_human_gate(scope)
        if payload is None:
            return self._missing_observation("awaiting_user", path)
        return ResumeSurfaceObservation(
            source="awaiting_user",
            present=True,
            valid=True,
            kind="awaiting_user",
            path=path,
            payload=payload,
        )

    def _inspect_resume_cursor(self, scope: NativePersistenceScope) -> ResumeSurfaceObservation:
        from arnold.pipeline.resume import classify_resume_cursor_payload

        path = self._artifact_ref(scope, "resume_cursor.json")
        payload = self.read_resume_cursor(scope)
        if payload is None:
            return self._missing_observation("resume_cursor", path)
        runtime = classify_resume_cursor_payload(payload)
        if runtime == "corrupt_native":
            return ResumeSurfaceObservation(
                source="resume_cursor",
                present=True,
                valid=False,
                kind="corrupt_native",
                path=path,
                payload=payload,
                diagnostic="resume_cursor.json claims native ownership but the native payload is invalid",
            )
        return ResumeSurfaceObservation(
            source="resume_cursor",
            present=True,
            valid=True,
            kind=f"{runtime}_resume_cursor",
            path=path,
            payload=payload,
        )

    def _extract_typed_resume_metadata(self, scope: NativePersistenceScope) -> TypedResumeMetadata | None:
        state = self.read_trace_artifact(scope, name="state.json")
        if not isinstance(state, dict):
            return None
        raw_contract = state.get("contract_result")
        if not isinstance(raw_contract, dict):
            return None

        from arnold.pipeline.types import ContractResult, ContractStatus

        try:
            contract = ContractResult.from_json(raw_contract)
        except (KeyError, TypeError, ValueError):
            return None
        if contract.status is not ContractStatus.SUSPENDED or contract.suspension is None:
            return None

        suspension = contract.suspension
        cursor_data = self._decode_json_cursor(suspension.resume_cursor)
        phase = None
        if isinstance(cursor_data, Mapping):
            raw_phase = cursor_data.get("phase") or cursor_data.get("stage")
            phase = raw_phase if isinstance(raw_phase, str) and raw_phase else None

        resume_input_schema: Mapping[str, Any] = (
            dict(suspension.resume_input_schema)
            if isinstance(suspension.resume_input_schema, Mapping)
            else {}
        )
        choices: list[str] | None = None
        props = resume_input_schema.get("properties")
        if isinstance(props, Mapping):
            choice_prop = props.get("choice")
            if isinstance(choice_prop, Mapping):
                enum = choice_prop.get("enum")
                if isinstance(enum, list) and all(isinstance(choice, str) for choice in enum):
                    choices = [str(choice) for choice in enum]

        return TypedResumeMetadata(
            contract=contract,
            phase=phase,
            pipeline=suspension.thread_ref,
            choices=choices,
            resume_input_schema=resume_input_schema,
            cursor_data=cursor_data,
            suspension_kind=suspension.kind,
            awaitable=suspension.awaitable,
        )

    @staticmethod
    def _missing_observation(source: str, path: str) -> ResumeSurfaceObservation:
        return ResumeSurfaceObservation(
            source=source,  # type: ignore[arg-type]
            present=False,
            valid=False,
            kind="none",
            path=path,
        )

    @staticmethod
    def _scope_params(scope: NativePersistenceScope) -> tuple[str, str, str]:
        return (scope.project_id, scope.run_id, scope.artifact_id)

    @staticmethod
    def _artifact_ref(scope: NativePersistenceScope, name: str) -> str:
        return f"postgres://{scope.project_id}/{scope.run_id}/{scope.artifact_id}/{name}"

    @staticmethod
    def _decode_json_cursor(raw: str | None) -> Any:
        if raw is None or not isinstance(raw, str):
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    @staticmethod
    def _decode_ndjson(raw: str) -> list[Any]:
        rows: list[Any] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return rows

    @staticmethod
    def _payload_from_row(row: Any) -> Any:
        if row is None:
            return None
        if isinstance(row, Mapping):
            return row.get("payload")
        return row[0]

    @staticmethod
    def _ordered_row(row: Any) -> OrderedPersistenceRow:
        if isinstance(row, Mapping):
            sequence = int(row["sequence"])
            payload = row["payload"]
            kind = row.get("kind")
        else:
            sequence = int(row[0])
            kind = row[1]
            payload = row[2]
        return OrderedPersistenceRow(
            sequence=sequence,
            payload=dict(payload) if isinstance(payload, Mapping) else {"value": payload},
            kind=kind if isinstance(kind, str) else None,
        )

    @staticmethod
    def _jsonb() -> Any:
        try:
            from psycopg.types.json import Jsonb
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("PostgresNativePersistenceBackend requires psycopg[binary]>=3.1") from exc
        return Jsonb

    @staticmethod
    def _migration_applied(conn: Any, version: str) -> bool:
        exists = PostgresNativePersistenceBackend._first_value(conn.execute(
            """
            SELECT to_regclass('arnold_native_schema_migrations') IS NOT NULL
            """
        ).fetchone())
        if not exists:
            return False
        return bool(
            conn.execute(
                "SELECT 1 FROM arnold_native_schema_migrations WHERE version = %s",
                (version,),
            ).fetchone()
        )

    @staticmethod
    def _first_value(row: Any) -> Any:
        if isinstance(row, Mapping):
            return next(iter(row.values()))
        return row[0]

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self._connection is not None:
            yield self._connection
            return
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("PostgresNativePersistenceBackend requires psycopg[binary]>=3.1") from exc
        with psycopg.connect(self._conninfo, row_factory=dict_row) as conn:
            yield conn


__all__ = ["PostgresNativePersistenceBackend"]
