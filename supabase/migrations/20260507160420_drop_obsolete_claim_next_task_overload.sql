-- Sprint 9 live parity: remove the obsolete worker-pool overload so
-- PostgREST can unambiguously call the route-selector claim RPC.

BEGIN;

DROP FUNCTION IF EXISTS public.claim_next_task_service_role(
  TEXT,
  BOOLEAN,
  TEXT,
  BOOLEAN,
  INT,
  TEXT,
  TEXT[]
);

COMMIT;
