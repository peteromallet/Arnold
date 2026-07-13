ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS discord_reply_provenance JSONB;

COMMENT ON COLUMN messages.discord_reply_provenance IS
    'Immutable, bounded Discord reply ancestry captured with the inbound source message.';
