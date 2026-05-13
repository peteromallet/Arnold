-- Phase A Step 7 — Layer 4 sentinel infrastructure.
--
-- Schedules a pg_cron job at one-minute cadence that POSTs to the
-- route-contract-sentinel edge function. The edge function queries tasks
-- directly (not via count_queued_tasks_breakdown_service_role, which excludes
-- orchestrator types) and classifies each tick as one of:
--   OK | NO_WORK | UNCLAIMABLE_WORK | NO_READY_WORKERS | WORKERS_STUCK_INITIALIZING
--
-- On five consecutive UNCLAIMABLE_WORK or WORKERS_STUCK_INITIALIZING ticks the
-- function POSTs to SENTINEL_WEBHOOK_URL and upserts pause_scaling.
--
-- Required Vault setup (operator runs once, before this migration ships):
--
--   SELECT vault.create_secret('<service-role-jwt>', 'sentinel_service_role_jwt');
--
-- Supabase's signature is vault.create_secret(new_secret text, new_name text,
-- new_description text) — VALUE FIRST, then NAME. Do not transpose.
--
-- The cron command below reads the JWT via vault.decrypted_secrets so no raw
-- token is ever materialized in cron.job.command.

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

CREATE TABLE IF NOT EXISTS public.sentinel_ticks (
  ts        timestamptz PRIMARY KEY DEFAULT now(),
  state     text NOT NULL,
  detail    jsonb
);

CREATE TABLE IF NOT EXISTS public.pause_scaling (
  pool   text PRIMARY KEY,
  until  timestamptz NOT NULL,
  reason text
);

-- Drop any pre-existing schedule under the same name so re-runs are idempotent.
DO $unsched$
DECLARE
  v_jobid bigint;
BEGIN
  SELECT jobid INTO v_jobid FROM cron.job WHERE jobname = 'route-contract-sentinel';
  IF v_jobid IS NOT NULL THEN
    PERFORM cron.unschedule(v_jobid);
  END IF;
END;
$unsched$;

SELECT cron.schedule(
  'route-contract-sentinel',
  '* * * * *',
  $cron$
  SELECT net.http_post(
    url := 'https://wczysqzxlwdndgxitrvc.supabase.co/functions/v1/route-contract-sentinel',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (
        SELECT decrypted_secret
        FROM vault.decrypted_secrets
        WHERE name = 'sentinel_service_role_jwt'
        LIMIT 1
      )
    ),
    body := '{}'::jsonb
  );
  $cron$
);

COMMENT ON TABLE public.sentinel_ticks IS
  'Layer 4 sentinel: per-tick classification snapshot. One row per minute when '
  'pg_cron job ''route-contract-sentinel'' fires. State is one of '
  'OK | NO_WORK | UNCLAIMABLE_WORK | NO_READY_WORKERS | WORKERS_STUCK_INITIALIZING.';

COMMENT ON TABLE public.pause_scaling IS
  'Layer 4 sentinel: per-pool scaling pause. Orchestrator reads this and skips '
  'scale-up when until > now(). Cleared by operator after acknowledging the page.';

-- Reversibility
-- ------------
-- To roll this migration back manually:
--   SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = 'route-contract-sentinel';
--   DROP TABLE IF EXISTS public.pause_scaling;
--   DROP TABLE IF EXISTS public.sentinel_ticks;
--   -- pg_cron / pg_net extensions are left in place (shared infrastructure).
