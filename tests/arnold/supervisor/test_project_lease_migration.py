from __future__ import annotations

from pathlib import Path


MIGRATION = Path("arnold/pipeline/native/migrations/001_native_persistence.sql")


def test_native_project_lease_migration_defines_current_state_contract() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS arnold_native_project_leases" in sql
    assert "PRIMARY KEY (project_id, worktree_id)" in sql
    assert "CREATE INDEX IF NOT EXISTS arnold_native_project_leases_scope_idx" in sql
    assert "ON arnold_native_project_leases (project_id, run_id, artifact_id, worktree_id)" in sql
    for column in (
        "owner_id text",
        "lease_token text",
        "lease_expires_at timestamptz",
        "last_heartbeat_at timestamptz",
        "last_progress_at timestamptz",
        "retry_count integer NOT NULL DEFAULT 0",
        "failure_count integer NOT NULL DEFAULT 0",
        "max_failures integer",
        "last_failure_at timestamptz",
        "next_retry_at timestamptz",
        "last_failure_reason text",
        "last_result jsonb",
        "quarantine_reason text",
        "created_at timestamptz NOT NULL DEFAULT now()",
        "updated_at timestamptz NOT NULL DEFAULT now()",
        "lock_version integer NOT NULL DEFAULT 0",
    ):
        assert column in sql
    for status in (
        "'pending'",
        "'leased'",
        "'succeeded'",
        "'failed'",
        "'cancelled'",
        "'quarantined'",
    ):
        assert status in sql
    assert "arnold_native_project_leases_leased_check" in sql
    assert "arnold_native_project_leases_quarantine_check" in sql
