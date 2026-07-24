from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest

from arnold.pipeline.native.postgres_persistence import PostgresNativePersistenceBackend
from arnold.supervisor.leases import ProjectLease, ProjectLeaseIdentity
from arnold.supervisor.store import PostgresProjectLeaseStore
from tests.arnold.supervisor.project_lease_store_conformance import (
    NOW,
    ProjectLeaseStoreConformance,
)


_DEFAULT_LOCAL_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/postgres?connect_timeout=2"


def _resolve_conninfo() -> str:
    return (
        os.environ.get("ARNOLD_TEST_POSTGRES_DSN")
        or os.environ.get("POSTGRES_DSN")
        or _DEFAULT_LOCAL_DSN
    )


class TestPostgresProjectLeaseStoreConformance(ProjectLeaseStoreConformance):
    @pytest.fixture
    def store_factory(self):
        psycopg = pytest.importorskip(
            "psycopg",
            reason="psycopg is required for Postgres lease-store conformance",
        )
        conninfo = _resolve_conninfo()
        try:
            with psycopg.connect(conninfo) as conn:
                conn.execute("SELECT 1").fetchone()
        except Exception as exc:
            pytest.skip(f"Postgres unavailable for lease-store conformance: {exc}")

        PostgresNativePersistenceBackend(conninfo=conninfo, apply_migrations=True)
        project_id = f"pytest-project-lease-{uuid4().hex}"

        def _factory() -> PostgresProjectLeaseStore:
            return PostgresProjectLeaseStore(
                conninfo=conninfo,
                artifact_id="pytest-project-lease",
            )

        yield _ProjectIdRewritingFactory(_factory, project_id)

        with psycopg.connect(conninfo) as conn:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM arnold_native_project_leases WHERE project_id = %s",
                    (project_id,),
                )


class _ProjectIdRewritingFactory:
    def __init__(self, factory: Any, project_id: str) -> None:
        self._factory = factory
        self._project_id = project_id

    def __call__(self) -> "_ProjectIdRewritingStore":
        return _ProjectIdRewritingStore(self._factory(), self._project_id)


class _ProjectIdRewritingStore:
    def __init__(self, store: PostgresProjectLeaseStore, project_id: str) -> None:
        self._store = store
        self._project_id = project_id

    def create_project_lease(self, lease: ProjectLease) -> ProjectLease:
        return self._store.create_project_lease(
            ProjectLease(
                identity=ProjectLeaseIdentity(
                    project_id=self._project_id,
                    worktree_id=lease.worktree_id,
                    run_id=lease.run_id,
                ),
                state=lease.state,
                owner_id=lease.owner_id,
                lease_token=lease.lease_token,
                lease_expires_at=lease.lease_expires_at,
                last_heartbeat_at=lease.last_heartbeat_at,
                last_progress_at=lease.last_progress_at,
                retry_count=lease.retry_count,
                failure_count=lease.failure_count,
                max_failures=lease.max_failures,
                last_failure_at=lease.last_failure_at,
                next_retry_at=lease.next_retry_at,
                last_failure_reason=lease.last_failure_reason,
                last_result=lease.last_result,
                quarantine_reason=lease.quarantine_reason,
                created_at=lease.created_at,
                updated_at=lease.updated_at,
                lock_version=lease.lock_version,
            )
        )

    def load_project_lease(self, project_id: str, worktree_id: str) -> ProjectLease:
        return self._store.load_project_lease(self._project_id, worktree_id)

    def list_project_leases(self) -> tuple[ProjectLease, ...]:
        return tuple(
            lease
            for lease in self._store.list_project_leases()
            if lease.project_id == self._project_id
        )

    def update_project_lease(
        self,
        lease: ProjectLease,
        *,
        expected_lock_version: int,
    ) -> ProjectLease:
        return self._store.update_project_lease(
            ProjectLease(
                identity=ProjectLeaseIdentity(
                    project_id=self._project_id,
                    worktree_id=lease.worktree_id,
                    run_id=lease.run_id,
                ),
                state=lease.state,
                owner_id=lease.owner_id,
                lease_token=lease.lease_token,
                lease_expires_at=lease.lease_expires_at,
                last_heartbeat_at=lease.last_heartbeat_at,
                last_progress_at=lease.last_progress_at,
                retry_count=lease.retry_count,
                failure_count=lease.failure_count,
                max_failures=lease.max_failures,
                last_failure_at=lease.last_failure_at,
                next_retry_at=lease.next_retry_at,
                last_failure_reason=lease.last_failure_reason,
                last_result=lease.last_result,
                quarantine_reason=lease.quarantine_reason,
                created_at=lease.created_at,
                updated_at=lease.updated_at,
                lock_version=lease.lock_version,
            ),
            expected_lock_version=expected_lock_version,
        )

    def claim_project_lease(self, project_id: str, worktree_id: str, **kwargs: Any):
        return self._store.claim_project_lease(self._project_id, worktree_id, **kwargs)

    def heartbeat_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        lease_token: str,
        **kwargs: Any,
    ):
        return self._store.heartbeat_project_lease(
            self._project_id,
            worktree_id,
            lease_token,
            **kwargs,
        )

    def complete_project_lease(self, project_id: str, worktree_id: str, **kwargs: Any):
        return self._store.complete_project_lease(
            self._project_id,
            worktree_id,
            **kwargs,
        )

    def fail_project_lease(self, project_id: str, worktree_id: str, **kwargs: Any):
        return self._store.fail_project_lease(self._project_id, worktree_id, **kwargs)

    def cancel_project_lease(self, project_id: str, worktree_id: str, **kwargs: Any):
        return self._store.cancel_project_lease(
            self._project_id,
            worktree_id,
            **kwargs,
        )

    def quarantine_project_lease(self, project_id: str, worktree_id: str, **kwargs: Any):
        return self._store.quarantine_project_lease(
            self._project_id,
            worktree_id,
            **kwargs,
        )

    def clear_project_quarantine(self, project_id: str, worktree_id: str, **kwargs: Any):
        return self._store.clear_project_quarantine(
            self._project_id,
            worktree_id,
            **kwargs,
        )


def test_postgres_project_lease_store_missing_psycopg_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = __import__

    def _raising_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "psycopg":
            raise ModuleNotFoundError("psycopg")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raising_import)
    store = PostgresProjectLeaseStore(conninfo="postgresql://unused")

    with pytest.raises(RuntimeError, match="requires psycopg"):
        store.load_project_lease("p", "w")
