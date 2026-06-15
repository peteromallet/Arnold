-- Megaplan DBStore foundation schema recovered for the Arnold merge database.
-- Idempotent by design: safe after Arnold base migrations and before Sprint 5/7 deltas.

CREATE OR REPLACE FUNCTION set_actor(actor_id text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM automation_actors WHERE id = actor_id) THEN
    RAISE EXCEPTION 'Unknown automation actor: %', actor_id
      USING ERRCODE = '28000';
  END IF;
  PERFORM set_config('megaplan.actor_id', actor_id, true);
END;
$$;

ALTER TABLE epics
    ADD COLUMN IF NOT EXISTS home_backend text NOT NULL DEFAULT 'db',
    ADD COLUMN IF NOT EXISTS migrated_to text,
    ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1;

ALTER TABLE sprints
    ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS automation_actors (
    id text PRIMARY KEY,
    name text NOT NULL,
    granted_epic_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    actor_kind text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_active_at timestamptz
);

CREATE TABLE IF NOT EXISTS db_idempotency_keys (
    idempotency_key text PRIMARY KEY,
    actor_id text NOT NULL,
    operation text NOT NULL,
    request_hash text NOT NULL,
    response_json jsonb,
    status text NOT NULL CHECK (status IN ('in_progress', 'complete', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_db_idempotency_actor_operation
    ON db_idempotency_keys (actor_id, operation);

CREATE TABLE IF NOT EXISTS plans (
    id text PRIMARY KEY,
    name text NOT NULL,
    epic_id text REFERENCES epics(id) ON DELETE CASCADE,
    sprint_id text REFERENCES sprints(id) ON DELETE SET NULL,
    revision integer NOT NULL DEFAULT 1,
    idea text NOT NULL,
    current_state text NOT NULL DEFAULT 'initialized',
    iteration integer NOT NULL DEFAULT 0,
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    sessions jsonb NOT NULL DEFAULT '{}'::jsonb,
    plan_versions jsonb NOT NULL DEFAULT '[]'::jsonb,
    history jsonb NOT NULL DEFAULT '[]'::jsonb,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_gate jsonb NOT NULL DEFAULT '{}'::jsonb,
    active_step jsonb,
    clarification jsonb,
    latest_finalize jsonb,
    latest_review jsonb,
    latest_execution jsonb,
    latest_failure jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_plans_epic_created_at
    ON plans (epic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_plans_sprint_created_at
    ON plans (sprint_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_plans_state_updated_at
    ON plans (current_state, updated_at DESC);

CREATE TABLE IF NOT EXISTS plan_artifacts (
    plan_id text NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    name text NOT NULL,
    kind text NOT NULL,
    role text NOT NULL,
    version integer,
    batch integer,
    phase text,
    content_text text,
    sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (plan_id, name)
);

CREATE INDEX IF NOT EXISTS idx_plan_artifacts_plan_updated_at
    ON plan_artifacts (plan_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS execution_leases (
    plan_id text PRIMARY KEY REFERENCES plans(id) ON DELETE CASCADE,
    epic_id text REFERENCES epics(id) ON DELETE CASCADE,
    holder_id text NOT NULL,
    worker_kind text NOT NULL,
    phase text NOT NULL,
    acquired_at timestamptz NOT NULL DEFAULT now(),
    heartbeat_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_leases_epic_expires
    ON execution_leases (epic_id, expires_at);

CREATE TABLE IF NOT EXISTS migration_runs (
    id text PRIMARY KEY,
    epic_id text NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    source_backend text NOT NULL,
    target_backend text NOT NULL,
    phase text NOT NULL,
    manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    copied_ids jsonb NOT NULL DEFAULT '{}'::jsonb,
    blob_copy_progress jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    holder_id text NOT NULL,
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_migration_runs_epic_started
    ON migration_runs (epic_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_migration_runs_active_expiry
    ON migration_runs (expires_at)
    WHERE completed_at IS NULL AND phase NOT IN ('complete', 'aborted');

CREATE TABLE IF NOT EXISTS control_messages (
    id text PRIMARY KEY,
    epic_id text NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    actor_id text NOT NULL,
    intent text NOT NULL,
    target_id text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    processor_id text,
    claimed_at timestamptz,
    processed_at timestamptz,
    result jsonb
);

CREATE INDEX IF NOT EXISTS idx_control_messages_pending_created
    ON control_messages (created_at)
    WHERE claimed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_control_messages_epic_created
    ON control_messages (epic_id, created_at DESC);

CREATE TABLE IF NOT EXISTS progress_events (
    id text PRIMARY KEY,
    epic_id text NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    plan_id text REFERENCES plans(id) ON DELETE CASCADE,
    sprint_id text REFERENCES sprints(id) ON DELETE SET NULL,
    idempotency_key text UNIQUE,
    kind text NOT NULL,
    summary text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_progress_events_epic_occurred
    ON progress_events (epic_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_progress_events_plan_occurred
    ON progress_events (plan_id, occurred_at DESC);
