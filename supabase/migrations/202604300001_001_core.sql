CREATE TABLE IF NOT EXISTS epics (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    body TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('shaping', 'sprinting', 'planned', 'paused', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_edited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at TIMESTAMPTZ,
    planned_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_epics_state_last_edited_at
    ON epics (state, last_edited_at DESC);
CREATE INDEX IF NOT EXISTS idx_epics_title
    ON epics (title);
CREATE INDEX IF NOT EXISTS idx_epics_goal
    ON epics (goal);

CREATE TABLE IF NOT EXISTS bot_turns (
    id TEXT PRIMARY KEY,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    triggered_by_message_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_snapshot JSONB,
    prompt_version TEXT,
    reasoning TEXT,
    final_output_message_id TEXT,
    status_message_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed', 'failed', 'abandoned')),
    state_at_turn JSONB,
    plan_edited BOOLEAN NOT NULL DEFAULT false,
    code_consulted BOOLEAN NOT NULL DEFAULT false,
    image_generated BOOLEAN NOT NULL DEFAULT false,
    second_opinion_requested BOOLEAN NOT NULL DEFAULT false,
    message_sent BOOLEAN NOT NULL DEFAULT false,
    warnings_issued JSONB,
    current_activity TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    model_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_bot_turns_status_started_at
    ON bot_turns (status, started_at);
CREATE INDEX IF NOT EXISTS idx_bot_turns_epic_started_at
    ON bot_turns (epic_id, started_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    content TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    discord_message_id TEXT UNIQUE,
    has_code_attachment BOOLEAN NOT NULL DEFAULT false,
    has_image_attachment BOOLEAN NOT NULL DEFAULT false,
    in_burst_with JSONB,
    was_voice_message BOOLEAN NOT NULL DEFAULT false,
    audio_storage_url TEXT,
    transcription_metadata JSONB,
    bot_turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_epic_sent_at
    ON messages (epic_id, sent_at);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL REFERENCES bot_turns(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    operation_kind TEXT NOT NULL CHECK (operation_kind IN ('read', 'write')),
    arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    called_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_turn_id
    ON tool_calls (turn_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_name_called_at
    ON tool_calls (tool_name, called_at DESC);

CREATE TABLE IF NOT EXISTS system_logs (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL CHECK (level IN ('debug', 'info', 'warn', 'error')),
    category TEXT NOT NULL CHECK (category IN ('system', 'application', 'tool', 'llm', 'external_api', 'recovery')),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level_occurred_at
    ON system_logs (level, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_category_event_occurred_at
    ON system_logs (category, event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_turn_id
    ON system_logs (turn_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_epic_occurred_at
    ON system_logs (epic_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS epic_locks (
    epic_id TEXT PRIMARY KEY REFERENCES epics(id) ON DELETE CASCADE,
    holder_id TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS external_requests (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL CHECK (provider IN ('anthropic', 'openai', 'groq', 'github', 'discord', 'supabase_storage')),
    endpoint TEXT NOT NULL,
    tool_call_id TEXT REFERENCES tool_calls(id) ON DELETE SET NULL,
    turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL,
    request_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'confirmed', 'failed', 'orphaned')),
    provider_request_id TEXT,
    provider_response_summary JSONB,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    first_attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error_details JSONB
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_external_requests_idempotency_key
    ON external_requests (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_external_requests_provider_status_last_attempted
    ON external_requests (provider, status, last_attempted_at);
CREATE INDEX IF NOT EXISTS idx_external_requests_status_last_attempted
    ON external_requests (status, last_attempted_at);
CREATE INDEX IF NOT EXISTS idx_external_requests_turn_id
    ON external_requests (turn_id);
CREATE INDEX IF NOT EXISTS idx_external_requests_tool_call_id
    ON external_requests (tool_call_id);
