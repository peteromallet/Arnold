PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS second_opinions (
    id TEXT PRIMARY KEY,
    epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    requested_by TEXT NOT NULL CHECK (requested_by IN ('user', 'auto_state_gate')),
    focus_areas TEXT NOT NULL DEFAULT '[]',
    raw_response TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 10),
    summary TEXT NOT NULL,
    verdict TEXT NOT NULL,
    resulting_checklist_item_ids TEXT NOT NULL DEFAULT '[]',
    model_used TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_second_opinions_epic_requested_at
    ON second_opinions (epic_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_second_opinions_score
    ON second_opinions (score);
