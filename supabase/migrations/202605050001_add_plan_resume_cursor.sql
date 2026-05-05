ALTER TABLE plans
    ADD COLUMN IF NOT EXISTS resume_cursor jsonb;
