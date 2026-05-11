-- Tickets MVP: tickets + ticket_epics tables and codebases.root_commit_sha
-- ============================================================================
-- Additive-only migration. No existing tables are modified except for the new
-- column on codebases.
--
-- DELIBERATE DIVERGENCE FROM docs/tickets.md:
--   filed_in_turn_id is declared as plain text WITHOUT a FOREIGN KEY to
--   bot_turns(id). This allows synthetic plan-phase markers (e.g.,
--   'plan_worker_{plan_id}') to be stored cleanly. Real bot_turns.id values
--   still work when the CLI inherits MEGAPLAN_TURN_ID from a resident-driven
--   path, but referential integrity is not enforced at the DB level.
--
--   DO NOT add the FK back in future migrations without also defining how
--   synthetic markers would be stored alongside real turn references.

-- (a) Add root_commit_sha to codebases ---------------------------------------

ALTER TABLE codebases
    ADD COLUMN IF NOT EXISTS root_commit_sha text;

CREATE INDEX IF NOT EXISTS idx_codebases_root_commit_sha
    ON codebases (root_commit_sha);

-- (b) tickets table -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS tickets (
    id text PRIMARY KEY,
    codebase_id text REFERENCES codebases(id) NOT NULL,
    title text NOT NULL,
    body text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'addressed', 'dismissed')),
    source text NOT NULL
        CHECK (source IN ('human', 'agent')),
    tags text[] DEFAULT '{}',
    filed_by_actor_id text REFERENCES automation_actors(id),
    filed_in_turn_id text,
    -- ^ plain text, NO FK to bot_turns(id) — see migration comment above
    slug text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_edited_at timestamptz NOT NULL DEFAULT now(),
    resolution_note text,
    addressed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_tickets_codebase_status
    ON tickets (codebase_id, status);

CREATE INDEX IF NOT EXISTS idx_tickets_codebase_created
    ON tickets (codebase_id, created_at DESC);

-- (c) ticket_epics join table -------------------------------------------------

CREATE TABLE IF NOT EXISTS ticket_epics (
    ticket_id text REFERENCES tickets(id) ON DELETE CASCADE,
    epic_id text REFERENCES epics(id) ON DELETE CASCADE,
    resolves_on_complete boolean NOT NULL DEFAULT false,
    linked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticket_id, epic_id)
);

CREATE INDEX IF NOT EXISTS idx_ticket_epics_epic
    ON ticket_epics (epic_id);