-- ============================================================================
-- M3 Proposal Spine: Add base_version, expires_at, accepted_at, rejected_at
-- columns to extension_proposals, plus a composite index and updated status
-- constraint that is a superset of legacy and SDK ProposalState values.
--
-- Per SD2: the DB constraint is a superset of both legacy statuses
-- ('draft','submitted','accepted','rejected','cancelled','expired') and the
-- SDK ProposalState ('pending','accepted','rejected','stale','expired').
-- ============================================================================

-- 1. New columns ------------------------------------------------------------

alter table public.extension_proposals
  add column if not exists base_version integer not null default 1
    constraint extension_proposals_base_version_positive_check
      check (base_version > 0);

alter table public.extension_proposals
  add column if not exists expires_at timestamptz;

alter table public.extension_proposals
  add column if not exists accepted_at timestamptz;

alter table public.extension_proposals
  add column if not exists rejected_at timestamptz;

-- 2. Updated status constraint (superset: legacy + SDK) ---------------------

alter table public.extension_proposals
  drop constraint if exists extension_proposals_status_check;

alter table public.extension_proposals
  add constraint extension_proposals_status_check
    check (status in (
      'draft',      -- legacy equivalent of 'pending'
      'submitted',  -- legacy
      'accepted',
      'rejected',
      'cancelled',  -- legacy
      'expired',
      'pending',    -- SDK canonical "created, awaiting action"
      'stale'       -- SDK canonical "base version mismatch"
    ));

-- 3. Composite index for proposal queries -----------------------------------

create index if not exists extension_proposals_timeline_id_status_expires_at_idx
  on public.extension_proposals (timeline_id, status, expires_at);

-- 4. Column comments --------------------------------------------------------

comment on column public.extension_proposals.base_version is
  'Timeline config version at the time the proposal was created.';

comment on column public.extension_proposals.expires_at is
  'Expiry timestamp for the proposal (nullable; no TTL when absent).';

comment on column public.extension_proposals.accepted_at is
  'Timestamp when the proposal was accepted (nullable).';

comment on column public.extension_proposals.rejected_at is
  'Timestamp when the proposal was rejected (nullable).';

comment on column public.extension_proposals.status is
  'Lifecycle status: draft, submitted, accepted, rejected, cancelled, expired, pending, or stale. The pending/stale values are SDK-canonical states introduced in M3.';
