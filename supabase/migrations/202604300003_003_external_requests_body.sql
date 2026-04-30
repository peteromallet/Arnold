ALTER TABLE external_requests
    ADD COLUMN IF NOT EXISTS request_body JSONB;
