PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    source TEXT NOT NULL CHECK (source IN ('agent_generated', 'user_uploaded')),
    prompt TEXT,
    storage_url TEXT NOT NULL,
    quality TEXT,
    size TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    reference_key TEXT NOT NULL,
    description TEXT,
    caption TEXT,
    in_body INTEGER NOT NULL DEFAULT 0 CHECK (in_body IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    discord_attachment_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_images_epic_created_at
    ON images (epic_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_images_epic_reference_key_active
    ON images (epic_id, reference_key)
    WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_images_epic_source
    ON images (epic_id, source);
