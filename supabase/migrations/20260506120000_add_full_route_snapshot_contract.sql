-- Sprint 9: full route snapshot contract columns.
--
-- Earlier selector-control migrations persisted the minimal selector fields.
-- This migration adds the full route contract shape used by app and worker
-- normalization for child pinning and legacy-row replay.

BEGIN;

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS support_state text,
  ADD COLUMN IF NOT EXISTS selected_profile text,
  ADD COLUMN IF NOT EXISTS selected_template_id text,
  ADD COLUMN IF NOT EXISTS route_run_id text,
  ADD COLUMN IF NOT EXISTS worker_contract_version integer;

ALTER TABLE public.tasks
  DROP CONSTRAINT IF EXISTS tasks_support_state_check,
  DROP CONSTRAINT IF EXISTS tasks_worker_contract_version_check,
  ADD CONSTRAINT tasks_support_state_check
    CHECK (
      support_state IS NULL
      OR support_state IN ('wgp_only', 'vibecomfy_supported', 'vibecomfy_unsupported')
    ),
  ADD CONSTRAINT tasks_worker_contract_version_check
    CHECK (worker_contract_version IS NULL OR worker_contract_version > 0);

COMMENT ON COLUMN public.tasks.support_state IS
  'Create-time route support state snapshot: wgp_only, vibecomfy_supported, or vibecomfy_unsupported.';
COMMENT ON COLUMN public.tasks.selected_profile IS
  'Create-time selected worker/profile label used for route demand grouping and child route pinning.';
COMMENT ON COLUMN public.tasks.selected_template_id IS
  'Create-time selected VibeComfy template id when the route resolves to a template, otherwise null.';
COMMENT ON COLUMN public.tasks.route_run_id IS
  'Optional route run correlation id propagated to parent-created child rows.';
COMMENT ON COLUMN public.tasks.worker_contract_version IS
  'Version of the worker route snapshot contract persisted with this task row.';

COMMIT;
