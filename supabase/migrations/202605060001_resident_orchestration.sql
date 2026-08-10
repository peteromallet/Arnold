-- Resident Discord orchestration persistence.
-- Adds durable conversation targets, resident/cloud run metadata, scheduled
-- jobs, message idempotency, and stale-claim lookup indexes.

INSERT INTO automation_actors (id, name, actor_kind)
VALUES ('resident', 'Megaplan Resident Discord Agent', 'resident')
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    actor_kind = EXCLUDED.actor_kind;

CREATE TABLE IF NOT EXISTS resident_conversations (
    id text PRIMARY KEY,
    transport text NOT NULL DEFAULT 'discord' CHECK (transport IN ('discord')),
    conversation_key text NOT NULL,
    active_epic_id text REFERENCES epics(id) ON DELETE SET NULL,
    guild_id text,
    channel_id text,
    thread_id text,
    dm_user_id text,
    last_inbound_message_id text REFERENCES messages(id) ON DELETE SET NULL,
    last_outbound_message_id text REFERENCES messages(id) ON DELETE SET NULL,
    delivery_cursor text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_active_at timestamptz,
    UNIQUE (transport, conversation_key)
);

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS conversation_id text REFERENCES resident_conversations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_idempotency_key_unique
    ON messages (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_conversation_idempotency_unique
    ON messages (conversation_id, idempotency_key)
    WHERE conversation_id IS NOT NULL AND idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_conversation_sent_at
    ON messages (conversation_id, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_resident_conversations_transport_key
    ON resident_conversations (transport, conversation_key);
CREATE INDEX IF NOT EXISTS idx_resident_conversations_active_epic
    ON resident_conversations (active_epic_id, last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_resident_conversations_discord_channel
    ON resident_conversations (guild_id, channel_id, thread_id);
CREATE INDEX IF NOT EXISTS idx_resident_conversations_dm_user
    ON resident_conversations (dm_user_id)
    WHERE dm_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cloud_runs (
    id text PRIMARY KEY,
    operation text NOT NULL CHECK (operation IN ('chain', 'bootstrap', 'resume', 'sprint', 'status')),
    status text NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued', 'starting', 'running', 'blocked', 'failed', 'gate-needed', 'completed', 'cancelled', 'unknown')
    ),
    conversation_id text REFERENCES resident_conversations(id) ON DELETE SET NULL,
    epic_id text REFERENCES epics(id) ON DELETE SET NULL,
    sprint_id text REFERENCES sprints(id) ON DELETE SET NULL,
    plan_id text REFERENCES plans(id) ON DELETE SET NULL,
    provider text,
    provider_run_id text,
    target_id text,
    command_summary text,
    progress_summary text,
    last_status jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key text,
    started_by_actor_id text REFERENCES automation_actors(id) ON DELETE SET NULL,
    started_at timestamptz,
    last_checked_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cloud_runs_idempotency_key_unique
    ON cloud_runs (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cloud_runs_provider_run_unique
    ON cloud_runs (provider, provider_run_id)
    WHERE provider IS NOT NULL AND provider_run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cloud_runs_conversation_created
    ON cloud_runs (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_epic_created
    ON cloud_runs (epic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_plan_created
    ON cloud_runs (plan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_sprint_created
    ON cloud_runs (sprint_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_status_checked
    ON cloud_runs (status, last_checked_at NULLS FIRST, updated_at DESC);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id text PRIMARY KEY,
    job_type text NOT NULL CHECK (job_type IN ('cloud_check', 'deferred_turn', 'heartbeat', 'confirmation_expiry')),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'claimed', 'fired', 'cancelled', 'failed')),
    conversation_id text REFERENCES resident_conversations(id) ON DELETE SET NULL,
    cloud_run_id text REFERENCES cloud_runs(id) ON DELETE CASCADE,
    epic_id text REFERENCES epics(id) ON DELETE SET NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    scheduled_for timestamptz NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    claimed_by text,
    claimed_at timestamptz,
    fired_at timestamptz,
    cancelled_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_due_claim
    ON scheduled_jobs (scheduled_for, created_at)
    WHERE status = 'pending' AND claimed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_stale_claim
    ON scheduled_jobs (claimed_at, scheduled_for)
    WHERE status = 'claimed' AND claimed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_conversation_due
    ON scheduled_jobs (conversation_id, scheduled_for)
    WHERE status IN ('pending', 'claimed');
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_cloud_run_due
    ON scheduled_jobs (cloud_run_id, scheduled_for)
    WHERE status IN ('pending', 'claimed');
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_type_status_due
    ON scheduled_jobs (job_type, status, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_control_messages_stale_claim
    ON control_messages (claimed_at, created_at)
    WHERE processed_at IS NULL AND claimed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_control_messages_processor_claimed
    ON control_messages (processor_id, claimed_at)
    WHERE processed_at IS NULL AND processor_id IS NOT NULL;
