PRAGMA foreign_keys = ON;

ALTER TABLE external_requests
    ADD COLUMN request_body TEXT;
