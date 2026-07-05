-- Arnold native runtime persistence substrate.
--
-- These tables intentionally use explicit project/run/artifact partition
-- columns on every persisted artifact family. Search path or schema isolation
-- can still be supplied by the caller, but Arnold's logical partitioning does
-- not depend on schema-per-project layout.

CREATE TABLE IF NOT EXISTS arnold_native_schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arnold_native_resume_checkpoints (
    project_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, run_id, artifact_id)
);

CREATE TABLE IF NOT EXISTS arnold_native_human_gates (
    project_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, run_id, artifact_id)
);

CREATE TABLE IF NOT EXISTS arnold_native_composite_cursors (
    project_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, run_id, artifact_id)
);

CREATE TABLE IF NOT EXISTS arnold_native_trace_artifacts (
    project_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    name text NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, run_id, artifact_id, name),
    CONSTRAINT arnold_native_trace_artifacts_name_check CHECK (
        name IN (
            'state.json',
            'events.ndjson',
            'stages.json',
            'artifacts.json',
            'checkpoint.json',
            'tree.json'
        )
    )
);

CREATE TABLE IF NOT EXISTS arnold_native_audit_records (
    sequence bigserial PRIMARY KEY,
    project_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    kind text,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arnold_native_audit_records_scope_sequence_idx
    ON arnold_native_audit_records (project_id, run_id, artifact_id, sequence);

CREATE SEQUENCE IF NOT EXISTS arnold_native_event_sequence;

CREATE TABLE IF NOT EXISTS arnold_native_ordered_events (
    sequence bigint PRIMARY KEY DEFAULT nextval('arnold_native_event_sequence'),
    project_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    kind text NOT NULL,
    phase text,
    idempotency_key text,
    event_scope text,
    payload jsonb NOT NULL,
    event jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arnold_native_ordered_events_scope_sequence_idx
    ON arnold_native_ordered_events (project_id, run_id, artifact_id, sequence);

CREATE TABLE IF NOT EXISTS arnold_native_project_leases (
    project_id text NOT NULL,
    worktree_id text NOT NULL,
    run_id text NOT NULL,
    artifact_id text NOT NULL,
    status text NOT NULL,
    owner_id text,
    lease_token text,
    lease_expires_at timestamptz,
    last_heartbeat_at timestamptz,
    last_progress_at timestamptz,
    retry_count integer NOT NULL DEFAULT 0,
    failure_count integer NOT NULL DEFAULT 0,
    max_failures integer,
    last_failure_at timestamptz,
    next_retry_at timestamptz,
    last_failure_reason text,
    last_result jsonb,
    quarantine_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    lock_version integer NOT NULL DEFAULT 0,
    PRIMARY KEY (project_id, worktree_id),
    CONSTRAINT arnold_native_project_leases_status_check CHECK (
        status IN (
            'pending',
            'leased',
            'succeeded',
            'failed',
            'cancelled',
            'quarantined'
        )
    ),
    CONSTRAINT arnold_native_project_leases_counts_check CHECK (
        retry_count >= 0
        AND failure_count >= 0
        AND lock_version >= 0
        AND (max_failures IS NULL OR max_failures >= 1)
        AND (max_failures IS NULL OR failure_count <= max_failures)
    ),
    CONSTRAINT arnold_native_project_leases_leased_check CHECK (
        status <> 'leased'
        OR (
            owner_id IS NOT NULL
            AND lease_token IS NOT NULL
            AND lease_expires_at IS NOT NULL
        )
    ),
    CONSTRAINT arnold_native_project_leases_quarantine_check CHECK (
        status <> 'quarantined'
        OR quarantine_reason IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS arnold_native_project_leases_scope_idx
    ON arnold_native_project_leases (project_id, run_id, artifact_id, worktree_id);

CREATE INDEX IF NOT EXISTS arnold_native_project_leases_status_expiry_idx
    ON arnold_native_project_leases (status, lease_expires_at);
