PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS epics (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    body TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('shaping', 'sprinting', 'planned', 'paused', 'archived')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_edited_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_active_at TEXT,
    planned_at TEXT
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
    triggered_by_message_ids TEXT NOT NULL DEFAULT '[]',
    prompt_snapshot TEXT,
    prompt_version TEXT,
    reasoning TEXT,
    final_output_message_id TEXT,
    status_message_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed', 'failed', 'abandoned')),
    state_at_turn TEXT,
    plan_edited INTEGER NOT NULL DEFAULT 0 CHECK (plan_edited IN (0, 1)),
    code_consulted INTEGER NOT NULL DEFAULT 0 CHECK (code_consulted IN (0, 1)),
    image_generated INTEGER NOT NULL DEFAULT 0 CHECK (image_generated IN (0, 1)),
    second_opinion_requested INTEGER NOT NULL DEFAULT 0 CHECK (second_opinion_requested IN (0, 1)),
    message_sent INTEGER NOT NULL DEFAULT 0 CHECK (message_sent IN (0, 1)),
    warnings_issued TEXT,
    current_activity TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    completed_at TEXT,
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
    sent_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    discord_message_id TEXT UNIQUE,
    has_code_attachment INTEGER NOT NULL DEFAULT 0 CHECK (has_code_attachment IN (0, 1)),
    has_image_attachment INTEGER NOT NULL DEFAULT 0 CHECK (has_image_attachment IN (0, 1)),
    in_burst_with TEXT,
    was_voice_message INTEGER NOT NULL DEFAULT 0 CHECK (was_voice_message IN (0, 1)),
    audio_storage_url TEXT,
    transcription_metadata TEXT,
    bot_turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_epic_sent_at
    ON messages (epic_id, sent_at);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL REFERENCES bot_turns(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    operation_kind TEXT NOT NULL CHECK (operation_kind IN ('read', 'write')),
    arguments TEXT NOT NULL DEFAULT '{}',
    result TEXT NOT NULL DEFAULT '{}',
    called_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
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
    details TEXT NOT NULL DEFAULT '{}',
    turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
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
    acquired_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS external_requests (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL CHECK (provider IN ('anthropic', 'openai', 'groq', 'github', 'discord', 'supabase_storage')),
    endpoint TEXT NOT NULL,
    tool_call_id TEXT REFERENCES tool_calls(id) ON DELETE SET NULL,
    turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL,
    request_summary TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'confirmed', 'failed', 'orphaned')),
    provider_request_id TEXT,
    provider_response_summary TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    first_attempted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_attempted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    completed_at TEXT,
    error_details TEXT
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
