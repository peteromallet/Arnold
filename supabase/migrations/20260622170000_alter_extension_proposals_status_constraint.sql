-- ============================================================================
-- M2 Provider Persistence Spine: Align proposal status constraint with the
-- ExtensionProposalStatus type in DataProvider.ts.
--
-- The initial migration allowed a legacy set of statuses. This migration
-- updates the check constraint and default to match the canonical type:
--   draft | submitted | accepted | rejected | cancelled | expired
-- ============================================================================

alter table public.extension_proposals
  drop constraint if exists extension_proposals_status_check;

alter table public.extension_proposals
  add constraint extension_proposals_status_check
    check (status in ('draft', 'submitted', 'accepted', 'rejected', 'cancelled', 'expired'));

alter table public.extension_proposals
  alter column status set default 'draft';

comment on column public.extension_proposals.status is
  'Lifecycle status: draft, submitted, accepted, rejected, cancelled, or expired.';
