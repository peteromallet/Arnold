"""Project lease store implementations for supervisor-owned worker leases."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Protocol, runtime_checkable

from arnold.kernel.suspension import (
    ManualSuspensionClearRequired,
    SuspensionState,
    ensure_manual_quarantine_clear_allowed,
)

from arnold.runtime.durable_ops.store import (
    interprocess_json_lock,
    write_json_atomically,
)

from .leases import (
    ProjectLease,
    ProjectLeaseIdentity,
    ProjectLeaseState,
    ensure_project_lease_transition,
    is_terminal_project_lease_state,
)

__all__ = [
    "FileProjectLeaseStore",
    "PostgresProjectLeaseStore",
    "ProjectLeaseAlreadyExists",
    "ProjectLeaseConflict",
    "ProjectLeaseLockConflict",
    "ProjectLeaseNotFound",
    "ProjectLeaseStore",
    "ProjectLeaseTokenMismatch",
]


class ProjectLeaseAlreadyExists(ValueError):
    """Raised when creating a lease would overwrite an existing worktree lease."""


class ProjectLeaseNotFound(KeyError):
    """Raised when a project/worktree lease cannot be found."""


class ProjectLeaseLockConflict(RuntimeError):
    """Raised when an optimistic update uses a stale lock version."""


class ProjectLeaseConflict(RuntimeError):
    """Raised when a project/worktree lease cannot be claimed or transitioned."""


class ProjectLeaseTokenMismatch(RuntimeError):
    """Raised when a lease mutation uses the wrong lease token."""


class FileProjectLeaseStore:
    """JSON current-state store for project/worktree leases."""

    lock_timeout_seconds = 30.0

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)
        self._path = self._root / "project_leases.json"
        self._lock_path = self._root / "project_leases.lock"
        self._lock = Lock()

    def create_project_lease(self, lease: ProjectLease) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                leases = data["project_leases"]
                key = _lease_key(lease.project_id, lease.worktree_id)
                if key in leases:
                    raise ProjectLeaseAlreadyExists(key)
                stored = replace(lease, lock_version=0)
                leases[key] = stored.to_json()
                self._write_data(data)
                return stored

    def load_project_lease(self, project_id: str, worktree_id: str) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                return self._load_project_lease_unlocked(project_id, worktree_id)

    def list_project_leases(self) -> tuple[ProjectLease, ...]:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                return tuple(
                    ProjectLease.from_json(data["project_leases"][key])
                    for key in sorted(data["project_leases"])
                )

    def update_project_lease(
        self,
        lease: ProjectLease,
        *,
        expected_lock_version: int,
    ) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                current = self._load_project_lease_unlocked(
                    lease.project_id,
                    lease.worktree_id,
                    data=data,
                )
                if current.lock_version != expected_lock_version:
                    raise ProjectLeaseLockConflict(lease.project_worktree_key)
                stored = replace(lease, lock_version=current.lock_version + 1)
                data["project_leases"][
                    _lease_key(stored.project_id, stored.worktree_id)
                ] = stored.to_json()
                self._write_data(data)
                return stored

    def claim_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        run_id: str,
        owner_id: str,
        lease_token: str,
        lease_seconds: int,
        now: datetime | None = None,
        takeover_validated: bool = False,
        takeover_reason: str | None = None,
    ) -> ProjectLease:
        """Claim a pending or expired project/worktree lease.

        Expired takeover is intentionally gated by ``takeover_validated`` so
        callers cannot treat clock expiry alone as sufficient reconcile trust.
        """

        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                timestamp = now or _utc_now()
                if lease_seconds <= 0 or not owner_id or not lease_token:
                    raise ProjectLeaseConflict(_lease_key(project_id, worktree_id))
                try:
                    current = self._load_project_lease_unlocked(
                        project_id,
                        worktree_id,
                        data=data,
                    )
                except ProjectLeaseNotFound:
                    current = ProjectLease(
                        identity=ProjectLeaseIdentity(
                            project_id=project_id,
                            worktree_id=worktree_id,
                            run_id=run_id,
                        ),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )

                if is_terminal_project_lease_state(current.state):
                    raise ProjectLeaseConflict(current.project_worktree_key)
                if current.next_retry_at is not None and current.next_retry_at > timestamp:
                    raise ProjectLeaseConflict(current.project_worktree_key)
                if current.has_active_lease(timestamp):
                    raise ProjectLeaseConflict(current.project_worktree_key)
                takeover_metadata = None
                if current.state is ProjectLeaseState.LEASED:
                    if not takeover_validated:
                        raise ProjectLeaseConflict(current.project_worktree_key)
                    takeover_metadata = {
                        "previous_owner_id": current.owner_id,
                        "previous_lease_token": current.lease_token,
                        "previous_lease_expires_at": _datetime_to_json(
                            current.lease_expires_at
                        ),
                        "takeover_reason": takeover_reason or "expired_lease_takeover",
                    }
                elif current.state is not ProjectLeaseState.LEASED:
                    try:
                        ensure_project_lease_transition(
                            current.state,
                            ProjectLeaseState.LEASED,
                        )
                    except ValueError as exc:
                        raise ProjectLeaseConflict(current.project_worktree_key) from exc

                last_result = dict(current.last_result or {})
                if takeover_metadata is not None:
                    last_result["expired_takeover"] = takeover_metadata

                stored = replace(
                    current,
                    identity=ProjectLeaseIdentity(
                        project_id=project_id,
                        worktree_id=worktree_id,
                        run_id=run_id,
                    ),
                    state=ProjectLeaseState.LEASED,
                    owner_id=owner_id,
                    lease_token=lease_token,
                    lease_expires_at=timestamp + timedelta(seconds=lease_seconds),
                    last_heartbeat_at=timestamp,
                    next_retry_at=None,
                    quarantine_reason=None,
                    updated_at=timestamp,
                    last_result=last_result or None,
                    lock_version=current.lock_version + 1,
                )
                data["project_leases"][
                    _lease_key(stored.project_id, stored.worktree_id)
                ] = stored.to_json()
                self._write_data(data)
                return stored

    def heartbeat_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        lease_token: str,
        *,
        lease_seconds: int,
        progress: bool = False,
        now: datetime | None = None,
    ) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                current = self._load_project_lease_unlocked(
                    project_id,
                    worktree_id,
                    data=data,
                )
                timestamp = now or _utc_now()
                self._ensure_matching_active_token(current, lease_token, timestamp)
                stored = replace(
                    current,
                    lease_expires_at=timestamp + timedelta(seconds=lease_seconds),
                    last_heartbeat_at=timestamp,
                    last_progress_at=timestamp if progress else current.last_progress_at,
                    updated_at=timestamp,
                    lock_version=current.lock_version + 1,
                )
                data["project_leases"][
                    _lease_key(stored.project_id, stored.worktree_id)
                ] = stored.to_json()
                self._write_data(data)
                return stored

    def complete_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        return self._finish_project_lease(
            project_id,
            worktree_id,
            lease_token=lease_token,
            target_state=ProjectLeaseState.SUCCEEDED,
            result=result,
            now=now,
        )

    def fail_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str,
        reason: str,
        result: dict[str, Any] | None = None,
        retry_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                current = self._load_project_lease_unlocked(
                    project_id,
                    worktree_id,
                    data=data,
                )
                timestamp = now or _utc_now()
                self._ensure_matching_token(current, lease_token)
                failure_count = current.failure_count + 1
                target_state = ProjectLeaseState.FAILED
                if current.max_failures is None or failure_count < current.max_failures:
                    target_state = ProjectLeaseState.PENDING
                ensure_project_lease_transition(current.state, target_state)
                stored = replace(
                    current,
                    state=target_state,
                    owner_id=None,
                    lease_token=None,
                    lease_expires_at=None,
                    retry_count=current.retry_count + 1
                    if target_state is ProjectLeaseState.PENDING
                    else current.retry_count,
                    failure_count=failure_count,
                    last_failure_at=timestamp,
                    next_retry_at=retry_at if target_state is ProjectLeaseState.PENDING else None,
                    last_failure_reason=reason,
                    last_result=result,
                    updated_at=timestamp,
                    lock_version=current.lock_version + 1,
                )
                data["project_leases"][
                    _lease_key(stored.project_id, stored.worktree_id)
                ] = stored.to_json()
                self._write_data(data)
                return stored

    def cancel_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        return self._finish_project_lease(
            project_id,
            worktree_id,
            lease_token=lease_token,
            target_state=ProjectLeaseState.CANCELLED,
            result=result,
            now=now,
        )

    def quarantine_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        reason: str,
        lease_token: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        if not reason:
            raise ProjectLeaseConflict(_lease_key(project_id, worktree_id))
        return self._finish_project_lease(
            project_id,
            worktree_id,
            lease_token=lease_token,
            target_state=ProjectLeaseState.QUARANTINED,
            result=result,
            quarantine_reason=reason,
            now=now,
        )

    def clear_project_quarantine(
        self,
        project_id: str,
        worktree_id: str,
        *,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                current = self._load_project_lease_unlocked(
                    project_id,
                    worktree_id,
                    data=data,
                )
                try:
                    ensure_manual_quarantine_clear_allowed(
                        SuspensionState(current.state.value)
                    )
                except (ManualSuspensionClearRequired, ValueError) as exc:
                    raise ProjectLeaseConflict(current.project_worktree_key) from exc
                timestamp = now or _utc_now()
                stored = replace(
                    current,
                    state=ProjectLeaseState.PENDING,
                    owner_id=None,
                    lease_token=None,
                    lease_expires_at=None,
                    next_retry_at=None,
                    quarantine_reason=None,
                    last_result=result if result is not None else current.last_result,
                    updated_at=timestamp,
                    lock_version=current.lock_version + 1,
                )
                data["project_leases"][
                    _lease_key(stored.project_id, stored.worktree_id)
                ] = stored.to_json()
                self._write_data(data)
                return stored

    def _finish_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str | None,
        target_state: ProjectLeaseState,
        result: dict[str, Any] | None = None,
        quarantine_reason: str | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        with self._lock:
            with interprocess_json_lock(
                self._lock_path,
                timeout_seconds=self.lock_timeout_seconds,
            ):
                data = self._read_data()
                current = self._load_project_lease_unlocked(
                    project_id,
                    worktree_id,
                    data=data,
                )
                timestamp = now or _utc_now()
                if current.state is ProjectLeaseState.LEASED:
                    self._ensure_matching_token(current, lease_token)
                elif lease_token is not None:
                    raise ProjectLeaseTokenMismatch(current.project_worktree_key)
                try:
                    ensure_project_lease_transition(current.state, target_state)
                except ValueError as exc:
                    raise ProjectLeaseConflict(current.project_worktree_key) from exc
                stored = replace(
                    current,
                    state=target_state,
                    owner_id=None,
                    lease_token=None,
                    lease_expires_at=None,
                    last_result=result,
                    quarantine_reason=quarantine_reason,
                    updated_at=timestamp,
                    lock_version=current.lock_version + 1,
                )
                data["project_leases"][
                    _lease_key(stored.project_id, stored.worktree_id)
                ] = stored.to_json()
                self._write_data(data)
                return stored

    def _load_project_lease_unlocked(
        self,
        project_id: str,
        worktree_id: str,
        *,
        data: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> ProjectLease:
        data = data or self._read_data()
        key = _lease_key(project_id, worktree_id)
        try:
            return ProjectLease.from_json(data["project_leases"][key])
        except KeyError as exc:
            raise ProjectLeaseNotFound(key) from exc

    def _ensure_matching_active_token(
        self,
        lease: ProjectLease,
        lease_token: str,
        timestamp: datetime,
    ) -> None:
        self._ensure_matching_token(lease, lease_token)
        if not lease.has_active_lease(timestamp):
            raise ProjectLeaseConflict(lease.project_worktree_key)

    def _ensure_matching_token(
        self,
        lease: ProjectLease,
        lease_token: str | None,
    ) -> None:
        if lease.state is not ProjectLeaseState.LEASED:
            raise ProjectLeaseTokenMismatch(lease.project_worktree_key)
        if not lease_token or lease.lease_token != lease_token:
            raise ProjectLeaseTokenMismatch(lease.project_worktree_key)

    def _read_data(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self._path.exists():
            return {"project_leases": {}}
        data = _read_json_file(self._path)
        leases = data.get("project_leases", {})
        if not isinstance(leases, dict):
            raise ValueError("project_leases must be a JSON object")
        return {"project_leases": leases}

    def _write_data(self, data: dict[str, dict[str, dict[str, Any]]]) -> None:
        write_json_atomically(self._path, data)


class PostgresProjectLeaseStore:
    """Postgres current-state store for project/worktree leases."""

    def __init__(
        self,
        conninfo: str | None = None,
        *,
        connection: Any | None = None,
        artifact_id: str = "project-lease",
    ) -> None:
        if (conninfo is None) == (connection is None):
            raise ValueError("provide exactly one of conninfo or connection")
        if not artifact_id:
            raise ValueError("artifact_id is required")
        self._conninfo = conninfo
        self._connection = connection
        self._artifact_id = artifact_id

    def create_project_lease(self, lease: ProjectLease) -> ProjectLease:
        jsonb = self._jsonb()
        stored = replace(lease, lock_version=0)
        try:
            with self._connect() as conn:
                with conn.transaction():
                    row = conn.execute(
                        """
                        INSERT INTO arnold_native_project_leases
                            (project_id, worktree_id, run_id, artifact_id, status,
                             owner_id, lease_token, lease_expires_at, last_heartbeat_at,
                             last_progress_at, retry_count, failure_count, max_failures,
                             last_failure_at, next_retry_at, last_failure_reason,
                             last_result, quarantine_reason, created_at, updated_at,
                             lock_version)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                             %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        self._lease_params(stored, jsonb=jsonb),
                    ).fetchone()
        except Exception as exc:
            if self._is_unique_violation(exc):
                raise ProjectLeaseAlreadyExists(stored.project_worktree_key) from exc
            raise
        return self._lease_from_row(row)

    def load_project_lease(self, project_id: str, worktree_id: str) -> ProjectLease:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM arnold_native_project_leases
                WHERE project_id = %s AND worktree_id = %s
                """,
                (project_id, worktree_id),
            ).fetchone()
        if row is None:
            raise ProjectLeaseNotFound(_lease_key(project_id, worktree_id))
        return self._lease_from_row(row)

    def list_project_leases(self) -> tuple[ProjectLease, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM arnold_native_project_leases
                ORDER BY project_id, worktree_id
                """
            ).fetchall()
        return tuple(self._lease_from_row(row) for row in rows)

    def update_project_lease(
        self,
        lease: ProjectLease,
        *,
        expected_lock_version: int,
    ) -> ProjectLease:
        jsonb = self._jsonb()
        stored = replace(lease, lock_version=expected_lock_version + 1)
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE arnold_native_project_leases
                    SET run_id = %s,
                        artifact_id = %s,
                        status = %s,
                        owner_id = %s,
                        lease_token = %s,
                        lease_expires_at = %s,
                        last_heartbeat_at = %s,
                        last_progress_at = %s,
                        retry_count = %s,
                        failure_count = %s,
                        max_failures = %s,
                        last_failure_at = %s,
                        next_retry_at = %s,
                        last_failure_reason = %s,
                        last_result = %s,
                        quarantine_reason = %s,
                        created_at = %s,
                        updated_at = %s,
                        lock_version = %s
                    WHERE project_id = %s
                      AND worktree_id = %s
                      AND lock_version = %s
                    RETURNING *
                    """,
                    (
                        stored.run_id,
                        self._artifact_id,
                        stored.state.value,
                        stored.owner_id,
                        stored.lease_token,
                        stored.lease_expires_at,
                        stored.last_heartbeat_at,
                        stored.last_progress_at,
                        stored.retry_count,
                        stored.failure_count,
                        stored.max_failures,
                        stored.last_failure_at,
                        stored.next_retry_at,
                        stored.last_failure_reason,
                        None if stored.last_result is None else jsonb(dict(stored.last_result)),
                        stored.quarantine_reason,
                        stored.created_at,
                        stored.updated_at,
                        stored.lock_version,
                        stored.project_id,
                        stored.worktree_id,
                        expected_lock_version,
                    ),
                ).fetchone()
        if row is None:
            raise ProjectLeaseLockConflict(lease.project_worktree_key)
        return self._lease_from_row(row)

    def claim_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        run_id: str,
        owner_id: str,
        lease_token: str,
        lease_seconds: int,
        now: datetime | None = None,
        takeover_validated: bool = False,
        takeover_reason: str | None = None,
    ) -> ProjectLease:
        timestamp = now or _utc_now()
        if lease_seconds <= 0 or not owner_id or not lease_token:
            raise ProjectLeaseConflict(_lease_key(project_id, worktree_id))
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                row = self._select_for_update(conn, project_id, worktree_id)
                if row is None:
                    current = ProjectLease(
                        identity=ProjectLeaseIdentity(
                            project_id=project_id,
                            worktree_id=worktree_id,
                            run_id=run_id,
                        ),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                else:
                    current = self._lease_from_row(row)

                if is_terminal_project_lease_state(current.state):
                    raise ProjectLeaseConflict(current.project_worktree_key)
                if current.next_retry_at is not None and current.next_retry_at > timestamp:
                    raise ProjectLeaseConflict(current.project_worktree_key)
                if current.has_active_lease(timestamp):
                    raise ProjectLeaseConflict(current.project_worktree_key)
                takeover_metadata = None
                if current.state is ProjectLeaseState.LEASED:
                    if not takeover_validated:
                        raise ProjectLeaseConflict(current.project_worktree_key)
                    takeover_metadata = {
                        "previous_owner_id": current.owner_id,
                        "previous_lease_token": current.lease_token,
                        "previous_lease_expires_at": _datetime_to_json(
                            current.lease_expires_at
                        ),
                        "takeover_reason": takeover_reason or "expired_lease_takeover",
                    }
                else:
                    try:
                        ensure_project_lease_transition(
                            current.state,
                            ProjectLeaseState.LEASED,
                        )
                    except ValueError as exc:
                        raise ProjectLeaseConflict(current.project_worktree_key) from exc

                last_result = dict(current.last_result or {})
                if takeover_metadata is not None:
                    last_result["expired_takeover"] = takeover_metadata

                stored = replace(
                    current,
                    identity=ProjectLeaseIdentity(
                        project_id=project_id,
                        worktree_id=worktree_id,
                        run_id=run_id,
                    ),
                    state=ProjectLeaseState.LEASED,
                    owner_id=owner_id,
                    lease_token=lease_token,
                    lease_expires_at=timestamp + timedelta(seconds=lease_seconds),
                    last_heartbeat_at=timestamp,
                    next_retry_at=None,
                    quarantine_reason=None,
                    updated_at=timestamp,
                    last_result=last_result or None,
                    lock_version=current.lock_version + 1,
                )
                row = self._upsert_locked(conn, stored, jsonb=jsonb)
        return self._lease_from_row(row)

    def heartbeat_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        lease_token: str,
        *,
        lease_seconds: int,
        progress: bool = False,
        now: datetime | None = None,
    ) -> ProjectLease:
        timestamp = now or _utc_now()
        with self._connect() as conn:
            with conn.transaction():
                current = self._load_locked_lease(conn, project_id, worktree_id)
                self._ensure_matching_active_token(current, lease_token, timestamp)
                row = conn.execute(
                    """
                    UPDATE arnold_native_project_leases
                    SET lease_expires_at = %s,
                        last_heartbeat_at = %s,
                        last_progress_at = %s,
                        updated_at = %s,
                        lock_version = lock_version + 1
                    WHERE project_id = %s
                      AND worktree_id = %s
                      AND lease_token = %s
                      AND lock_version = %s
                    RETURNING *
                    """,
                    (
                        timestamp + timedelta(seconds=lease_seconds),
                        timestamp,
                        timestamp if progress else current.last_progress_at,
                        timestamp,
                        project_id,
                        worktree_id,
                        lease_token,
                        current.lock_version,
                    ),
                ).fetchone()
        if row is None:
            raise ProjectLeaseTokenMismatch(_lease_key(project_id, worktree_id))
        return self._lease_from_row(row)

    def complete_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        return self._finish_project_lease(
            project_id,
            worktree_id,
            lease_token=lease_token,
            target_state=ProjectLeaseState.SUCCEEDED,
            result=result,
            now=now,
        )

    def fail_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str,
        reason: str,
        result: dict[str, Any] | None = None,
        retry_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        timestamp = now or _utc_now()
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                current = self._load_locked_lease(conn, project_id, worktree_id)
                self._ensure_matching_token(current, lease_token)
                failure_count = current.failure_count + 1
                target_state = ProjectLeaseState.FAILED
                if current.max_failures is None or failure_count < current.max_failures:
                    target_state = ProjectLeaseState.PENDING
                ensure_project_lease_transition(current.state, target_state)
                row = conn.execute(
                    """
                    UPDATE arnold_native_project_leases
                    SET status = %s,
                        owner_id = NULL,
                        lease_token = NULL,
                        lease_expires_at = NULL,
                        retry_count = %s,
                        failure_count = %s,
                        last_failure_at = %s,
                        next_retry_at = %s,
                        last_failure_reason = %s,
                        last_result = %s,
                        updated_at = %s,
                        lock_version = lock_version + 1
                    WHERE project_id = %s
                      AND worktree_id = %s
                      AND lease_token = %s
                      AND lock_version = %s
                    RETURNING *
                    """,
                    (
                        target_state.value,
                        current.retry_count + 1
                        if target_state is ProjectLeaseState.PENDING
                        else current.retry_count,
                        failure_count,
                        timestamp,
                        retry_at if target_state is ProjectLeaseState.PENDING else None,
                        reason,
                        None if result is None else jsonb(dict(result)),
                        timestamp,
                        project_id,
                        worktree_id,
                        lease_token,
                        current.lock_version,
                    ),
                ).fetchone()
        if row is None:
            raise ProjectLeaseTokenMismatch(_lease_key(project_id, worktree_id))
        return self._lease_from_row(row)

    def cancel_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        return self._finish_project_lease(
            project_id,
            worktree_id,
            lease_token=lease_token,
            target_state=ProjectLeaseState.CANCELLED,
            result=result,
            now=now,
        )

    def quarantine_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        reason: str,
        lease_token: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        if not reason:
            raise ProjectLeaseConflict(_lease_key(project_id, worktree_id))
        return self._finish_project_lease(
            project_id,
            worktree_id,
            lease_token=lease_token,
            target_state=ProjectLeaseState.QUARANTINED,
            result=result,
            quarantine_reason=reason,
            now=now,
        )

    def clear_project_quarantine(
        self,
        project_id: str,
        worktree_id: str,
        *,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        timestamp = now or _utc_now()
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                current = self._load_locked_lease(conn, project_id, worktree_id)
                try:
                    ensure_manual_quarantine_clear_allowed(
                        SuspensionState(current.state.value)
                    )
                except (ManualSuspensionClearRequired, ValueError) as exc:
                    raise ProjectLeaseConflict(current.project_worktree_key) from exc
                row = conn.execute(
                    """
                    UPDATE arnold_native_project_leases
                    SET status = %s,
                        owner_id = NULL,
                        lease_token = NULL,
                        lease_expires_at = NULL,
                        next_retry_at = NULL,
                        last_result = %s,
                        quarantine_reason = NULL,
                        updated_at = %s,
                        lock_version = lock_version + 1
                    WHERE project_id = %s
                      AND worktree_id = %s
                      AND lock_version = %s
                    RETURNING *
                    """,
                    (
                        ProjectLeaseState.PENDING.value,
                        None if result is None else jsonb(dict(result)),
                        timestamp,
                        project_id,
                        worktree_id,
                        current.lock_version,
                    ),
                ).fetchone()
        if row is None:
            raise ProjectLeaseConflict(_lease_key(project_id, worktree_id))
        return self._lease_from_row(row)

    def _finish_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str | None,
        target_state: ProjectLeaseState,
        result: dict[str, Any] | None = None,
        quarantine_reason: str | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:
        timestamp = now or _utc_now()
        jsonb = self._jsonb()
        with self._connect() as conn:
            with conn.transaction():
                current = self._load_locked_lease(conn, project_id, worktree_id)
                if current.state is ProjectLeaseState.LEASED:
                    self._ensure_matching_token(current, lease_token)
                elif lease_token is not None:
                    raise ProjectLeaseTokenMismatch(current.project_worktree_key)
                try:
                    ensure_project_lease_transition(current.state, target_state)
                except ValueError as exc:
                    raise ProjectLeaseConflict(current.project_worktree_key) from exc
                row = conn.execute(
                    """
                    UPDATE arnold_native_project_leases
                    SET status = %s,
                        owner_id = NULL,
                        lease_token = NULL,
                        lease_expires_at = NULL,
                        last_result = %s,
                        quarantine_reason = %s,
                        updated_at = %s,
                        lock_version = lock_version + 1
                    WHERE project_id = %s
                      AND worktree_id = %s
                      AND lock_version = %s
                      AND (%s::text IS NULL OR lease_token = %s)
                    RETURNING *
                    """,
                    (
                        target_state.value,
                        None if result is None else jsonb(dict(result)),
                        quarantine_reason,
                        timestamp,
                        project_id,
                        worktree_id,
                        current.lock_version,
                        lease_token,
                        lease_token,
                    ),
                ).fetchone()
        if row is None:
            raise ProjectLeaseTokenMismatch(_lease_key(project_id, worktree_id))
        return self._lease_from_row(row)

    def _load_locked_lease(
        self,
        conn: Any,
        project_id: str,
        worktree_id: str,
    ) -> ProjectLease:
        row = self._select_for_update(conn, project_id, worktree_id)
        if row is None:
            raise ProjectLeaseNotFound(_lease_key(project_id, worktree_id))
        return self._lease_from_row(row)

    @staticmethod
    def _select_for_update(conn: Any, project_id: str, worktree_id: str) -> Any:
        return conn.execute(
            """
            SELECT *
            FROM arnold_native_project_leases
            WHERE project_id = %s AND worktree_id = %s
            FOR UPDATE
            """,
            (project_id, worktree_id),
        ).fetchone()

    def _upsert_locked(self, conn: Any, lease: ProjectLease, *, jsonb: Any) -> Any:
        existing = conn.execute(
            """
            UPDATE arnold_native_project_leases
            SET run_id = %s,
                artifact_id = %s,
                status = %s,
                owner_id = %s,
                lease_token = %s,
                lease_expires_at = %s,
                last_heartbeat_at = %s,
                last_progress_at = %s,
                retry_count = %s,
                failure_count = %s,
                max_failures = %s,
                last_failure_at = %s,
                next_retry_at = %s,
                last_failure_reason = %s,
                last_result = %s,
                quarantine_reason = %s,
                created_at = %s,
                updated_at = %s,
                lock_version = %s
            WHERE project_id = %s
              AND worktree_id = %s
              AND lock_version = %s
            RETURNING *
            """,
            (
                lease.run_id,
                self._artifact_id,
                lease.state.value,
                lease.owner_id,
                lease.lease_token,
                lease.lease_expires_at,
                lease.last_heartbeat_at,
                lease.last_progress_at,
                lease.retry_count,
                lease.failure_count,
                lease.max_failures,
                lease.last_failure_at,
                lease.next_retry_at,
                lease.last_failure_reason,
                None if lease.last_result is None else jsonb(dict(lease.last_result)),
                lease.quarantine_reason,
                lease.created_at,
                lease.updated_at,
                lease.lock_version,
                lease.project_id,
                lease.worktree_id,
                lease.lock_version - 1,
            ),
        ).fetchone()
        if existing is not None:
            return existing
        return conn.execute(
            """
            INSERT INTO arnold_native_project_leases
                (project_id, worktree_id, run_id, artifact_id, status, owner_id,
                 lease_token, lease_expires_at, last_heartbeat_at, last_progress_at,
                 retry_count, failure_count, max_failures, last_failure_at,
                 next_retry_at, last_failure_reason, last_result, quarantine_reason,
                 created_at, updated_at, lock_version)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            self._lease_params(lease, jsonb=jsonb),
        ).fetchone()

    def _ensure_matching_active_token(
        self,
        lease: ProjectLease,
        lease_token: str,
        timestamp: datetime,
    ) -> None:
        self._ensure_matching_token(lease, lease_token)
        if not lease.has_active_lease(timestamp):
            raise ProjectLeaseConflict(lease.project_worktree_key)

    @staticmethod
    def _ensure_matching_token(
        lease: ProjectLease,
        lease_token: str | None,
    ) -> None:
        if lease.state is not ProjectLeaseState.LEASED:
            raise ProjectLeaseTokenMismatch(lease.project_worktree_key)
        if not lease_token or lease.lease_token != lease_token:
            raise ProjectLeaseTokenMismatch(lease.project_worktree_key)

    def _lease_params(self, lease: ProjectLease, *, jsonb: Any) -> tuple[Any, ...]:
        return (
            lease.project_id,
            lease.worktree_id,
            lease.run_id,
            self._artifact_id,
            lease.state.value,
            lease.owner_id,
            lease.lease_token,
            lease.lease_expires_at,
            lease.last_heartbeat_at,
            lease.last_progress_at,
            lease.retry_count,
            lease.failure_count,
            lease.max_failures,
            lease.last_failure_at,
            lease.next_retry_at,
            lease.last_failure_reason,
            None if lease.last_result is None else jsonb(dict(lease.last_result)),
            lease.quarantine_reason,
            lease.created_at,
            lease.updated_at,
            lease.lock_version,
        )

    @staticmethod
    def _lease_from_row(row: Any) -> ProjectLease:
        if not isinstance(row, dict):
            row = dict(row)
        return ProjectLease(
            identity=ProjectLeaseIdentity(
                project_id=str(row["project_id"]),
                worktree_id=str(row["worktree_id"]),
                run_id=str(row["run_id"]),
            ),
            state=ProjectLeaseState(str(row["status"])),
            owner_id=row.get("owner_id"),
            lease_token=row.get("lease_token"),
            lease_expires_at=row.get("lease_expires_at"),
            last_heartbeat_at=row.get("last_heartbeat_at"),
            last_progress_at=row.get("last_progress_at"),
            retry_count=int(row["retry_count"]),
            failure_count=int(row["failure_count"]),
            max_failures=row.get("max_failures"),
            last_failure_at=row.get("last_failure_at"),
            next_retry_at=row.get("next_retry_at"),
            last_failure_reason=row.get("last_failure_reason"),
            last_result=row.get("last_result"),
            quarantine_reason=row.get("quarantine_reason"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lock_version=int(row["lock_version"]),
        )

    @staticmethod
    def _jsonb() -> Any:
        try:
            from psycopg.types.json import Jsonb
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("PostgresProjectLeaseStore requires psycopg[binary]>=3.1") from exc
        return Jsonb

    @staticmethod
    def _is_unique_violation(exc: Exception) -> bool:
        return exc.__class__.__name__ == "UniqueViolation"

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self._connection is not None:
            yield self._connection
            return
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("PostgresProjectLeaseStore requires psycopg[binary]>=3.1") from exc
        with psycopg.connect(self._conninfo, row_factory=dict_row) as conn:
            yield conn


@runtime_checkable
class ProjectLeaseStore(Protocol):
    """Backend-neutral current-state store for project/worktree leases."""

    def create_project_lease(self, lease: ProjectLease) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def load_project_lease(
        self,
        project_id: str,
        worktree_id: str,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def list_project_leases(self) -> tuple[ProjectLease, ...]:  # pragma: no cover - protocol
        ...

    def update_project_lease(
        self,
        lease: ProjectLease,
        *,
        expected_lock_version: int,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def claim_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        run_id: str,
        owner_id: str,
        lease_token: str,
        lease_seconds: int,
        now: datetime | None = None,
        takeover_validated: bool = False,
        takeover_reason: str | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def heartbeat_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        lease_token: str,
        *,
        lease_seconds: int,
        progress: bool = False,
        now: datetime | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def complete_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def fail_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str,
        reason: str,
        result: dict[str, Any] | None = None,
        retry_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def cancel_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        lease_token: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def quarantine_project_lease(
        self,
        project_id: str,
        worktree_id: str,
        *,
        reason: str,
        lease_token: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...

    def clear_project_quarantine(
        self,
        project_id: str,
        worktree_id: str,
        *,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ProjectLease:  # pragma: no cover - protocol
        ...


def _read_json_file(path: Path) -> dict[str, Any]:
    import json

    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("project lease store root must be a JSON object")
    return raw


def _lease_key(project_id: str, worktree_id: str) -> str:
    if not project_id:
        raise ValueError("project_id is required")
    if not worktree_id:
        raise ValueError("worktree_id is required")
    return f"{project_id}:{worktree_id}"


def _datetime_to_json(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(UTC)
