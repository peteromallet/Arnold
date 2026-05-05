CREATE TABLE IF NOT EXISTS checklist_items (
    id TEXT PRIMARY KEY,
    epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    status TEXT CHECK (status IN ('open', 'done', 'skipped', 'superseded')),
    position INTEGER NOT NULL,
    source TEXT CHECK (source IN ('bot_inferred', 'user_requested', 'carried_over', 'default_seed', 'second_opinion')),
    skip_reason TEXT,
    superseded_by_item_id TEXT REFERENCES checklist_items(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_checklist_items_epic_status_position
    ON checklist_items (epic_id, status, position);

CREATE TABLE IF NOT EXISTS epic_events (
    id TEXT PRIMARY KEY,
    epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    transaction_id TEXT NOT NULL,
    event_type TEXT CHECK (event_type IN (
        'body_edit',
        'checklist_change',
        'sprints_change',
        'state_change',
        'forced_handoff',
        'created',
        'code_referenced',
        'codebase_added',
        'image_generated',
        'second_opinion_requested',
        'reverted_to',
        'sprint_status_change'
    )),
    summary TEXT NOT NULL,
    prior_state JSONB,
    turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_epic_events_epic_occurred_at
    ON epic_events (epic_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_epic_events_transaction_id
    ON epic_events (transaction_id);
