CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    source TEXT NOT NULL CHECK (source IN ('agent_generated', 'user_uploaded', 'caller_uploaded')),
    prompt TEXT,
    storage_url TEXT NOT NULL,
    quality TEXT,
    size TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reference_key TEXT NOT NULL,
    description TEXT,
    caption TEXT,
    in_body BOOLEAN NOT NULL DEFAULT false,
    active BOOLEAN NOT NULL DEFAULT true,
    discord_attachment_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_images_epic_created_at
    ON images (epic_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_images_epic_reference_key_active
    ON images (epic_id, reference_key)
    WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_images_epic_source
    ON images (epic_id, source);
