CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id UNINDEXED,
    content
);

INSERT INTO messages_fts (message_id, content)
SELECT id, content FROM messages
WHERE id NOT IN (SELECT message_id FROM messages_fts);

CREATE TRIGGER IF NOT EXISTS messages_ai_fts
AFTER INSERT ON messages
BEGIN
    INSERT INTO messages_fts (message_id, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad_fts
AFTER DELETE ON messages
BEGIN
    DELETE FROM messages_fts WHERE message_id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS messages_au_fts
AFTER UPDATE OF content ON messages
BEGIN
    UPDATE messages_fts
    SET content = new.content
    WHERE message_id = new.id;
END;
