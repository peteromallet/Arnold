-- Add relationship kind and provenance columns to ticket_epics join table.
-- Backward-compatible: existing rows get NULLs; the TicketEpicLink model
-- defaults kind to 'associated' and provenance to None at deserialization.

ALTER TABLE IF EXISTS ticket_epics
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'associated';

ALTER TABLE IF EXISTS ticket_epics
    ADD COLUMN IF NOT EXISTS provenance text;

-- The default on kind ensures existing rows migrate cleanly without a
-- backfill; new writes from link_ticket_to_epic always supply explicit values.
