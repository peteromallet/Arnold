PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS codebases (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL CHECK (owner = lower(owner) AND length(owner) > 0),
    name TEXT NOT NULL CHECK (name = lower(name) AND length(name) > 0),
    default_branch TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global' CHECK (scope IN ('global', 'epic_specific')),
    group_name TEXT,
    associated_epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    added_via TEXT NOT NULL DEFAULT 'manual',
    last_accessed_at TEXT,
    verified_accessible_at TEXT,
    notes TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_codebases_owner_name_unique
    ON codebases (lower(owner), lower(name));
CREATE INDEX IF NOT EXISTS idx_codebases_scope_group
    ON codebases (scope, group_name);
CREATE INDEX IF NOT EXISTS idx_codebases_associated_epic
    ON codebases (associated_epic_id);
CREATE INDEX IF NOT EXISTS idx_codebases_last_accessed
    ON codebases (last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_codebases_verified_accessible
    ON codebases (verified_accessible_at DESC);

CREATE TABLE IF NOT EXISTS code_artifacts (
    id TEXT PRIMARY KEY,
    codebase_id TEXT REFERENCES codebases(id) ON DELETE SET NULL,
    epic_id TEXT REFERENCES epics(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('excerpt', 'summary', 'api_cache')),
    source TEXT NOT NULL CHECK (source IN ('conversation', 'codebase')),
    file_path TEXT,
    line_range TEXT,
    scope TEXT CHECK (scope IN ('file', 'directory', 'cross_codebase')),
    content TEXT NOT NULL,
    content_summary TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_used_at TEXT,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_code_artifacts_codebase_created
    ON code_artifacts (codebase_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_code_artifacts_epic_created
    ON code_artifacts (epic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_code_artifacts_kind_scope
    ON code_artifacts (kind, scope);
CREATE INDEX IF NOT EXISTS idx_code_artifacts_file_path
    ON code_artifacts (codebase_id, file_path);
CREATE INDEX IF NOT EXISTS idx_code_artifacts_api_cache_expires
    ON code_artifacts (expires_at)
    WHERE kind = 'api_cache' AND expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_code_artifacts_api_cache_key
    ON code_artifacts (json_extract(metadata, '$.cache_key'))
    WHERE kind = 'api_cache';
