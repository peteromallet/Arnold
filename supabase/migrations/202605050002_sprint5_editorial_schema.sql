-- Sprint 5 editorial persistence plumbing.
-- Adds deterministic event snapshot columns, blob-backed image metadata, active
-- image reference uniqueness, and backend-native DB search index support.

ALTER TABLE epic_events
    ADD COLUMN IF NOT EXISTS pre_state jsonb,
    ADD COLUMN IF NOT EXISTS post_state jsonb,
    ADD COLUMN IF NOT EXISTS pre_state_canonical_json text,
    ADD COLUMN IF NOT EXISTS post_state_canonical_json text,
    ADD COLUMN IF NOT EXISTS pre_state_sha256 text,
    ADD COLUMN IF NOT EXISTS post_state_sha256 text;

ALTER TABLE images
    ADD COLUMN IF NOT EXISTS blob_backend text,
    ADD COLUMN IF NOT EXISTS blob_id text,
    ADD COLUMN IF NOT EXISTS blob_sha256 text,
    ADD COLUMN IF NOT EXISTS blob_size_bytes bigint,
    ADD COLUMN IF NOT EXISTS content_type text;

CREATE UNIQUE INDEX IF NOT EXISTS images_one_active_reference
    ON images (epic_id, reference_key)
    WHERE active IS TRUE;

CREATE INDEX IF NOT EXISTS epic_events_pre_state_gin
    ON epic_events USING gin (pre_state);

CREATE INDEX IF NOT EXISTS epic_events_post_state_gin
    ON epic_events USING gin (post_state);

CREATE INDEX IF NOT EXISTS epic_events_pre_state_sha256_idx
    ON epic_events (pre_state_sha256);

CREATE INDEX IF NOT EXISTS epic_events_post_state_sha256_idx
    ON epic_events (post_state_sha256);

CREATE INDEX IF NOT EXISTS images_blob_sha256_idx
    ON images (blob_sha256)
    WHERE blob_sha256 IS NOT NULL;

CREATE INDEX IF NOT EXISTS epics_search_tsv_gin
    ON epics USING gin (
        to_tsvector(
            'english',
            coalesce(title, '') || ' ' || coalesce(goal, '') || ' ' || coalesce(body, '')
        )
    );
