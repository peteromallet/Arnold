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
