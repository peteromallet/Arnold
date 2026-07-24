from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest

from arnold.pipeline.native.persistence import NativePersistenceScope
from arnold.pipeline.native.postgres_persistence import PostgresNativePersistenceBackend
from tests.arnold.pipeline.native._persistence_backend_conformance import (
    BackendContext,
    PersistenceBackendConformanceTests,
)


_DEFAULT_LOCAL_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/postgres?connect_timeout=2"
_OWNED_TABLES = (
    "arnold_native_resume_checkpoints",
    "arnold_native_human_gates",
    "arnold_native_composite_cursors",
    "arnold_native_trace_artifacts",
    "arnold_native_audit_records",
    "arnold_native_ordered_events",
)


def _resolve_conninfo() -> str:
    return os.environ.get("ARNOLD_TEST_POSTGRES_DSN") or os.environ.get("POSTGRES_DSN") or _DEFAULT_LOCAL_DSN


class _PostgresBackendHarness:
    def __init__(self, conninfo: str, project_id: str) -> None:
        self._conninfo = conninfo
        self._project_id = project_id

    def open(self, name: str = "default") -> BackendContext:
        backend = PostgresNativePersistenceBackend(conninfo=self._conninfo, apply_migrations=False)
        scope = NativePersistenceScope(
            project_id=self._project_id,
            run_id=f"run-{name}",
            artifact_id=f"artifact-{name}",
        )
        return BackendContext(
            backend=backend,
            scope=scope,
            seed_state=lambda payload: backend.write_trace_artifact(scope, name="state.json", payload=payload),
        )


class TestPostgresPersistenceBackendConformance(PersistenceBackendConformanceTests):
    @pytest.fixture
    def backend_harness(self) -> _PostgresBackendHarness:
        psycopg = pytest.importorskip("psycopg", reason="psycopg is required for Postgres backend conformance")
        conninfo = _resolve_conninfo()
        try:
            with psycopg.connect(conninfo) as conn:
                conn.execute("SELECT 1").fetchone()
        except Exception as exc:
            pytest.skip(f"Postgres unavailable for backend conformance: {exc}")

        PostgresNativePersistenceBackend(conninfo=conninfo, apply_migrations=True)
        project_id = f"pytest-native-persistence-{uuid4().hex}"
        harness = _PostgresBackendHarness(conninfo=conninfo, project_id=project_id)
        try:
            yield harness
        finally:
            with psycopg.connect(conninfo) as conn:
                with conn.transaction():
                    for table in _OWNED_TABLES:
                        conn.execute(f"DELETE FROM {table} WHERE project_id = %s", (project_id,))


def test_postgres_backend_missing_psycopg_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def _raising_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "psycopg":
            raise ModuleNotFoundError("psycopg")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raising_import)
    backend = PostgresNativePersistenceBackend(conninfo="postgresql://unused", apply_migrations=False)

    with pytest.raises(RuntimeError, match="requires psycopg"):
        backend.read_resume_cursor(
            NativePersistenceScope(project_id="p", run_id="r", artifact_id="a")
        )
