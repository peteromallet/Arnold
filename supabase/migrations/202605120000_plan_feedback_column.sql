ALTER TABLE plans
    ADD COLUMN IF NOT EXISTS feedback jsonb;
