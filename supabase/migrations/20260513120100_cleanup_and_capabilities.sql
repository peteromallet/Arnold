-- 20260513120100_cleanup_and_capabilities.sql
--
-- Phase A Step 4 (T5) of brief "stop the cross-boundary contract bleeding".
--
-- Triage migration. Runs after 20260513120000_derive_route_key.sql (which
-- defined public.derive_route_key) and BEFORE the Layer-1 trigger migration
-- 20260513120200_tasks_claimable_trigger.sql. Goal: leave the tasks table
-- in a state where the trigger cannot reject any pre-existing row when it
-- attaches.
--
-- Pre-migration audit (T2.2) against live production captured the following
-- (all of which this migration must remain idempotent against):
--   * Hannah's 7-task chain (parent 0168dcc3-… + 6 children) is already
--     status='Failed'. UPDATEs below preserve that and stamp an
--     error_message if any row was Failed without one.
--   * route_backend_capabilities already has vibecomfy rows for both
--     qwen_image_style and animate_character (supports_route=t, enabled=t).
--     The INSERTs below use ON CONFLICT DO NOTHING so a re-run on a fresh
--     dev DB seeds them, while production is unaffected.
--   * No tasks match the ~40-row stuck cohort
--     (status='Queued' AND (selector_namespace IS NULL OR ='production')
--      AND route_key IS NULL). The UPDATEs below are defensive no-ops in
--     production but will heal the cohort if it reappears between now and
--     deploy.
--
-- The tasks.status enum is named public.task_status. error_message is the
-- canonical failure column (verified via information_schema.columns).

BEGIN;

-- 1. Hannah's poisoned chain — mark Failed (idempotent; stamps reason if missing).
UPDATE public.tasks
SET status = 'Failed'::public.task_status,
    error_message = COALESCE(NULLIF(error_message, ''),
                             'poisoned parent_route_key references — terminal'),
    updated_at = now()
WHERE id IN (
    '0168dcc3-2a42-415d-84b5-a28cf6033850',
    'd2114387-b5dc-4521-b6a2-f2989379e891',
    '79308f35-795c-4b1d-a8e5-7bdf8d82b64c',
    '47dc41df-7656-4b88-a0e2-315e71939220',
    '2b40a495-89cc-4bc4-a29e-515119bce2dd',
    'a505b34e-3571-4abc-b29f-7ff773a8d0f2',
    'cc83949d-8f24-407f-9b48-d7ca9962e410'
  )
  AND (status <> 'Failed'::public.task_status
       OR error_message IS NULL OR error_message = '');

-- 2. Backfill stuck Queued rows with NULL route_key in the production namespace.
--    derive_route_key returns NULL when not derivable; only rows that derive
--    cleanly are healed here.
UPDATE public.tasks t
SET route_key = derived.route_key,
    updated_at = now()
FROM (
    SELECT id, public.derive_route_key(task_type, params) AS route_key
    FROM public.tasks
    WHERE status = 'Queued'::public.task_status
      AND (selector_namespace IS NULL OR selector_namespace = 'production')
      AND route_key IS NULL
) AS derived
WHERE t.id = derived.id
  AND derived.route_key IS NOT NULL;

-- 3. Stuck Queued rows older than 24h that still couldn't be backfilled →
--    terminally Fail them so the trigger doesn't reject on UPDATE-into-Queued
--    later. Anything younger than 24h is left alone for the operator to
--    examine.
UPDATE public.tasks
SET status = 'Failed'::public.task_status,
    error_message = COALESCE(NULLIF(error_message, ''),
                             'unclaimable: route_key NULL after derive_route_key backfill — terminal'),
    updated_at = now()
WHERE status = 'Queued'::public.task_status
  AND (selector_namespace IS NULL OR selector_namespace = 'production')
  AND route_key IS NULL
  AND created_at < now() - interval '24 hours';

-- 4. Capability rows for qwen_image_style and animate_character.
--    Production already has vibecomfy rows for both; ON CONFLICT keeps the
--    migration idempotent and ensures a fresh DB or a partially-seeded env
--    converges on the same baseline. The Layer-1 trigger in 120200 calls
--    route_backend_claim_decision, which returns eligible=false with
--    reason='missing_capability' if these rows are absent — by inserting
--    them here we keep the trigger from rejecting valid task_types.
INSERT INTO public.route_backend_capabilities
  (route_key, backend, supports_route, supports_missing_selector, enabled)
VALUES
  ('qwen_image_style',  'vibecomfy', TRUE, FALSE, TRUE),
  ('animate_character', 'vibecomfy', TRUE, FALSE, TRUE)
ON CONFLICT (route_key, backend) DO NOTHING;

-- 5. Post-condition asserts. Fail the migration loudly if Hannah's chain
--    or the capability rows didn't land. The backfill/stuck-fail steps
--    are defensive against the empty-cohort case so we don't assert on
--    them here.
DO $$
DECLARE
    v_hannah_failed integer;
    v_caps integer;
    v_stuck_old integer;
BEGIN
    SELECT count(*) INTO v_hannah_failed
    FROM public.tasks
    WHERE id IN (
        '0168dcc3-2a42-415d-84b5-a28cf6033850',
        'd2114387-b5dc-4521-b6a2-f2989379e891',
        '79308f35-795c-4b1d-a8e5-7bdf8d82b64c',
        '47dc41df-7656-4b88-a0e2-315e71939220',
        '2b40a495-89cc-4bc4-a29e-515119bce2dd',
        'a505b34e-3571-4abc-b29f-7ff773a8d0f2',
        'cc83949d-8f24-407f-9b48-d7ca9962e410'
      )
      AND status = 'Failed'::public.task_status;
    IF v_hannah_failed <> 7 THEN
        RAISE EXCEPTION
            'cleanup_and_capabilities: expected Hannah chain (7 rows) to be Failed, found %',
            v_hannah_failed;
    END IF;

    SELECT count(*) INTO v_caps
    FROM public.route_backend_capabilities
    WHERE route_key IN ('qwen_image_style','animate_character')
      AND backend = 'vibecomfy'
      AND enabled = TRUE
      AND supports_route = TRUE;
    IF v_caps <> 2 THEN
        RAISE EXCEPTION
            'cleanup_and_capabilities: expected 2 vibecomfy capability rows for qwen_image_style+animate_character, found %',
            v_caps;
    END IF;

    SELECT count(*) INTO v_stuck_old
    FROM public.tasks
    WHERE status = 'Queued'::public.task_status
      AND (selector_namespace IS NULL OR selector_namespace = 'production')
      AND route_key IS NULL
      AND created_at < now() - interval '24 hours';
    IF v_stuck_old <> 0 THEN
        RAISE EXCEPTION
            'cleanup_and_capabilities: % stuck Queued rows >24h old still have NULL route_key after triage',
            v_stuck_old;
    END IF;
END $$;

COMMIT;

-- Rollback notes (manual; this migration is data-only triage):
--   Hannah's chain stays Failed — by design, do NOT revive.
--   To roll back the capability inserts on a non-prod DB where they were
--   freshly seeded by this migration:
--     DELETE FROM public.route_backend_capabilities
--       WHERE route_key IN ('qwen_image_style','animate_character')
--         AND backend = 'vibecomfy';
--   Backfill UPDATEs are not reversible without a backup (the prior NULL
--   route_key state was already broken). The 24h-old stuck → Failed UPDATE
--   is similarly not reversible; affected rows were terminally unclaimable.
