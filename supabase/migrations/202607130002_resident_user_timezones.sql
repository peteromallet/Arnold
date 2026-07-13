-- Durable user-level presentation preferences for the Discord resident.
-- Authoritative event/control timestamps remain timestamptz/UTC; this table
-- controls presentation only.

CREATE TABLE IF NOT EXISTS resident_user_preferences (
    transport text NOT NULL DEFAULT 'discord' CHECK (transport IN ('discord')),
    user_id text NOT NULL,
    timezone_name text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (transport, user_id)
);

CREATE INDEX IF NOT EXISTS idx_resident_user_preferences_updated
    ON resident_user_preferences (updated_at DESC);
