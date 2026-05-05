ALTER TABLE plan_artifacts
    ADD COLUMN IF NOT EXISTS content_bytes bytea;
