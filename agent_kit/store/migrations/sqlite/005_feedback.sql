PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN (
        'style',
        'process',
        'epic_specific',
        'friction',
        'ambiguity',
        'tool_failure',
        'confusion',
        'pattern_noticed'
    )),
    content TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'user_volunteered',
        'agent_proposed_user_confirmed',
        'explicit_save_request',
        'agent_observation'
    )),
    source_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
    epic_id TEXT REFERENCES epics(id) ON DELETE CASCADE,
    turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL,
    context_snapshot TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    deactivation_reason TEXT,
    resolved INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
    resolution_note TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_referenced_at TEXT,
    last_applied_at TEXT,
    CHECK (
        (
            kind IN ('style', 'process', 'epic_specific')
            AND source IN (
                'user_volunteered',
                'agent_proposed_user_confirmed',
                'explicit_save_request'
            )
        )
        OR
        (
            kind IN (
                'friction',
                'ambiguity',
                'tool_failure',
                'confusion',
                'pattern_noticed'
            )
            AND source = 'agent_observation'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_feedback_active_global_kind_created
    ON feedback (kind, active, created_at DESC)
    WHERE epic_id IS NULL
      AND kind IN ('style', 'process')
      AND active = 1;

CREATE INDEX IF NOT EXISTS idx_feedback_epic_active_kind_created
    ON feedback (epic_id, kind, active, created_at DESC)
    WHERE epic_id IS NOT NULL
      AND kind = 'epic_specific'
      AND active = 1;

CREATE INDEX IF NOT EXISTS idx_feedback_unresolved_observations_created
    ON feedback (resolved, created_at DESC)
    WHERE kind IN (
        'friction',
        'ambiguity',
        'tool_failure',
        'confusion',
        'pattern_noticed'
    )
      AND resolved = 0;
