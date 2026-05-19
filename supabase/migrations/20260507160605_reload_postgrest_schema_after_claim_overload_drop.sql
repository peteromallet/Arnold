-- Force PostgREST to reload its schema cache after dropping the obsolete
-- claim_next_task_service_role overload.

BEGIN;

NOTIFY pgrst, 'reload schema';

COMMIT;
