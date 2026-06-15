CREATE INDEX IF NOT EXISTS idx_messages_content_fts
    ON messages USING gin (to_tsvector('english', content));
