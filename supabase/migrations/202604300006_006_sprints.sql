CREATE TABLE IF NOT EXISTS sprints (
    id TEXT PRIMARY KEY,
    epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    sprint_number INTEGER NOT NULL CHECK (sprint_number > 0),
    name TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'queued', 'pending', 'done')),
    queue_position INTEGER CHECK (queue_position IS NULL OR queue_position > 0),
    pending_reason TEXT,
    target_weeks INTEGER NOT NULL DEFAULT 2 CHECK (target_weeks > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    queued_at TIMESTAMPTZ,
    CHECK (status != 'queued' OR queue_position IS NOT NULL),
    CHECK (status != 'pending' OR pending_reason IS NOT NULL),
    CHECK (status = 'queued' OR queue_position IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_sprints_epic_sprint_number
    ON sprints (epic_id, sprint_number);
CREATE INDEX IF NOT EXISTS idx_sprints_epic_status
    ON sprints (epic_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sprints_epic_queued_position
    ON sprints (epic_id, queue_position)
    WHERE status = 'queued';

CREATE TABLE IF NOT EXISTS sprint_items (
    id TEXT PRIMARY KEY,
    sprint_id TEXT NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    estimated_complexity TEXT NOT NULL CHECK (estimated_complexity IN ('small', 'medium', 'large')),
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'done')),
    source_section TEXT,
    position INTEGER NOT NULL CHECK (position > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sprint_items_sprint_position
    ON sprint_items (sprint_id, position);
