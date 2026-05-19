-- Sprint 6: production route selector and backend capability control plane.
-- This migration only creates the schema contract. Claim/count RPC enforcement
-- is added in later migrations.

BEGIN;

CREATE TABLE IF NOT EXISTS public.route_backend_selectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  selector_namespace text NOT NULL DEFAULT 'production',
  route_key text NOT NULL,
  selected_backend text NOT NULL,
  selector_version bigint NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  expires_at timestamptz,
  min_worker_version text,
  reason text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid,

  CONSTRAINT route_backend_selectors_namespace_check
    CHECK (selector_namespace ~ '^[a-z][a-z0-9_-]{0,62}$'),
  CONSTRAINT route_backend_selectors_route_key_check
    CHECK (length(route_key) BETWEEN 1 AND 512 AND route_key !~ '\s'),
  CONSTRAINT route_backend_selectors_backend_check
    CHECK (selected_backend IN ('wgp', 'vibecomfy')),
  CONSTRAINT route_backend_selectors_version_check
    CHECK (selector_version > 0),
  CONSTRAINT route_backend_selectors_metadata_object_check
    CHECK (jsonb_typeof(metadata) = 'object'),
  CONSTRAINT route_backend_selectors_unique_route
    UNIQUE (selector_namespace, route_key)
);

CREATE TABLE IF NOT EXISTS public.route_backend_capabilities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  backend text NOT NULL,
  route_key text NOT NULL,
  supports_route boolean NOT NULL DEFAULT false,
  supports_missing_selector boolean NOT NULL DEFAULT false,
  enabled boolean NOT NULL DEFAULT true,
  capability_version bigint NOT NULL DEFAULT 1,
  expires_at timestamptz,
  min_worker_version text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid,

  CONSTRAINT route_backend_capabilities_backend_check
    CHECK (backend IN ('wgp', 'vibecomfy')),
  CONSTRAINT route_backend_capabilities_route_key_check
    CHECK (length(route_key) BETWEEN 1 AND 512 AND route_key !~ '\s'),
  CONSTRAINT route_backend_capabilities_version_check
    CHECK (capability_version > 0),
  CONSTRAINT route_backend_capabilities_metadata_object_check
    CHECK (jsonb_typeof(metadata) = 'object'),
  CONSTRAINT route_backend_capabilities_missing_selector_wgp_only_check
    CHECK (supports_missing_selector = false OR backend = 'wgp'),
  CONSTRAINT route_backend_capabilities_unique_route_backend
    UNIQUE (backend, route_key)
);

CREATE INDEX IF NOT EXISTS idx_route_backend_selectors_lookup
  ON public.route_backend_selectors (selector_namespace, route_key)
  WHERE enabled = true;

CREATE INDEX IF NOT EXISTS idx_route_backend_selectors_backend
  ON public.route_backend_selectors (selected_backend, selector_namespace)
  WHERE enabled = true;

CREATE INDEX IF NOT EXISTS idx_route_backend_selectors_expires_at
  ON public.route_backend_selectors (expires_at)
  WHERE expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_route_backend_capabilities_lookup
  ON public.route_backend_capabilities (backend, route_key)
  WHERE enabled = true;

CREATE INDEX IF NOT EXISTS idx_route_backend_capabilities_missing_selector
  ON public.route_backend_capabilities (route_key, backend)
  WHERE enabled = true AND supports_missing_selector = true;

CREATE INDEX IF NOT EXISTS idx_route_backend_capabilities_expires_at
  ON public.route_backend_capabilities (expires_at)
  WHERE expires_at IS NOT NULL;

ALTER TABLE public.route_backend_selectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.route_backend_capabilities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "route_backend_selectors_service_role_all" ON public.route_backend_selectors;
DROP POLICY IF EXISTS "route_backend_capabilities_service_role_all" ON public.route_backend_capabilities;

CREATE POLICY "route_backend_selectors_service_role_all"
  ON public.route_backend_selectors
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "route_backend_capabilities_service_role_all"
  ON public.route_backend_capabilities
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

REVOKE ALL ON TABLE public.route_backend_selectors FROM anon, authenticated;
REVOKE ALL ON TABLE public.route_backend_capabilities FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.route_backend_selectors TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.route_backend_capabilities TO service_role;

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS selector_namespace text,
  ADD COLUMN IF NOT EXISTS route_key text,
  ADD COLUMN IF NOT EXISTS selected_backend text,
  ADD COLUMN IF NOT EXISTS selector_version bigint,
  ADD COLUMN IF NOT EXISTS route_selection_snapshot jsonb,
  ADD COLUMN IF NOT EXISTS claimed_backend text,
  ADD COLUMN IF NOT EXISTS claimed_selector_namespace text,
  ADD COLUMN IF NOT EXISTS claimed_route_key text,
  ADD COLUMN IF NOT EXISTS claimed_selector_version bigint,
  ADD COLUMN IF NOT EXISTS claimed_capability_version bigint,
  ADD COLUMN IF NOT EXISTS claim_decision_reason text,
  ADD COLUMN IF NOT EXISTS claim_decision_snapshot jsonb;

ALTER TABLE public.tasks
  DROP CONSTRAINT IF EXISTS tasks_selector_namespace_check,
  DROP CONSTRAINT IF EXISTS tasks_claimed_selector_namespace_check,
  DROP CONSTRAINT IF EXISTS tasks_route_key_check,
  DROP CONSTRAINT IF EXISTS tasks_claimed_route_key_check,
  DROP CONSTRAINT IF EXISTS tasks_selected_backend_check,
  DROP CONSTRAINT IF EXISTS tasks_claimed_backend_check,
  DROP CONSTRAINT IF EXISTS tasks_selector_version_check,
  DROP CONSTRAINT IF EXISTS tasks_claimed_selector_version_check,
  DROP CONSTRAINT IF EXISTS tasks_claimed_capability_version_check,
  DROP CONSTRAINT IF EXISTS tasks_route_selection_snapshot_object_check,
  DROP CONSTRAINT IF EXISTS tasks_claim_decision_snapshot_object_check,
  ADD CONSTRAINT tasks_selector_namespace_check
    CHECK (selector_namespace IS NULL OR selector_namespace ~ '^[a-z][a-z0-9_-]{0,62}$'),
  ADD CONSTRAINT tasks_claimed_selector_namespace_check
    CHECK (claimed_selector_namespace IS NULL OR claimed_selector_namespace ~ '^[a-z][a-z0-9_-]{0,62}$'),
  ADD CONSTRAINT tasks_route_key_check
    CHECK (route_key IS NULL OR (length(route_key) BETWEEN 1 AND 512 AND route_key !~ '\s')),
  ADD CONSTRAINT tasks_claimed_route_key_check
    CHECK (claimed_route_key IS NULL OR (length(claimed_route_key) BETWEEN 1 AND 512 AND claimed_route_key !~ '\s')),
  ADD CONSTRAINT tasks_selected_backend_check
    CHECK (selected_backend IS NULL OR selected_backend IN ('wgp', 'vibecomfy')),
  ADD CONSTRAINT tasks_claimed_backend_check
    CHECK (claimed_backend IS NULL OR claimed_backend IN ('wgp', 'vibecomfy')),
  ADD CONSTRAINT tasks_selector_version_check
    CHECK (selector_version IS NULL OR selector_version > 0),
  ADD CONSTRAINT tasks_claimed_selector_version_check
    CHECK (claimed_selector_version IS NULL OR claimed_selector_version > 0),
  ADD CONSTRAINT tasks_claimed_capability_version_check
    CHECK (claimed_capability_version IS NULL OR claimed_capability_version > 0),
  ADD CONSTRAINT tasks_route_selection_snapshot_object_check
    CHECK (route_selection_snapshot IS NULL OR jsonb_typeof(route_selection_snapshot) = 'object'),
  ADD CONSTRAINT tasks_claim_decision_snapshot_object_check
    CHECK (claim_decision_snapshot IS NULL OR jsonb_typeof(claim_decision_snapshot) = 'object');

CREATE INDEX IF NOT EXISTS idx_tasks_route_key_queued
  ON public.tasks (route_key, created_at)
  WHERE status = 'Queued'::task_status AND route_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_selected_backend_queued
  ON public.tasks (selected_backend, created_at)
  WHERE status = 'Queued'::task_status AND selected_backend IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_claimed_backend_active
  ON public.tasks (claimed_backend, claimed_selector_namespace, updated_at)
  WHERE status = 'In Progress'::task_status AND claimed_backend IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_claimed_route_key_active
  ON public.tasks (claimed_route_key, updated_at)
  WHERE status = 'In Progress'::task_status AND claimed_route_key IS NOT NULL;

CREATE OR REPLACE FUNCTION public.route_backend_claim_decision(
  p_selector_namespace text,
  p_route_key text,
  p_worker_backend text,
  p_now timestamptz DEFAULT now()
)
RETURNS TABLE(
  selector_namespace text,
  route_key text,
  worker_backend text,
  selected_backend text,
  selector_version bigint,
  selector_present boolean,
  selector_enabled boolean,
  selector_expired boolean,
  capability_present boolean,
  capability_version bigint,
  capability_supports_route boolean,
  capability_supports_missing_selector boolean,
  eligible boolean,
  decision_reason text,
  selector_snapshot jsonb,
  capability_snapshot jsonb
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH normalized AS (
    SELECT
      COALESCE(NULLIF(p_selector_namespace, ''), 'production') AS selector_namespace,
      p_route_key AS route_key,
      p_worker_backend AS worker_backend,
      p_now AS decision_at
  ),
  selector_row AS (
    SELECT s.*
    FROM public.route_backend_selectors s
    JOIN normalized n
      ON s.selector_namespace = n.selector_namespace
     AND s.route_key = n.route_key
    LIMIT 1
  ),
  capability_row AS (
    SELECT c.*
    FROM public.route_backend_capabilities c
    JOIN normalized n
      ON c.backend = n.worker_backend
     AND c.route_key = n.route_key
    LIMIT 1
  )
  SELECT
    n.selector_namespace,
    n.route_key,
    n.worker_backend,
    s.selected_backend,
    s.selector_version,
    (s.id IS NOT NULL) AS selector_present,
    COALESCE(s.enabled, false) AS selector_enabled,
    COALESCE(s.expires_at <= n.decision_at, false) AS selector_expired,
    (c.id IS NOT NULL) AS capability_present,
    c.capability_version,
    COALESCE(c.supports_route AND c.enabled AND (c.expires_at IS NULL OR c.expires_at > n.decision_at), false)
      AS capability_supports_route,
    COALESCE(c.supports_missing_selector AND c.enabled AND (c.expires_at IS NULL OR c.expires_at > n.decision_at), false)
      AS capability_supports_missing_selector,
    CASE
      WHEN n.worker_backend NOT IN ('wgp', 'vibecomfy') THEN false
      WHEN n.route_key IS NULL OR n.route_key = '' OR n.route_key ~ '\s' THEN false
      WHEN c.id IS NULL THEN false
      WHEN s.id IS NULL THEN
        n.worker_backend = 'wgp'
        AND COALESCE(c.supports_missing_selector AND c.enabled AND (c.expires_at IS NULL OR c.expires_at > n.decision_at), false)
      ELSE
        s.enabled
        AND (s.expires_at IS NULL OR s.expires_at > n.decision_at)
        AND s.selected_backend = n.worker_backend
        AND COALESCE(c.supports_route AND c.enabled AND (c.expires_at IS NULL OR c.expires_at > n.decision_at), false)
    END AS eligible,
    CASE
      WHEN n.worker_backend NOT IN ('wgp', 'vibecomfy') THEN 'malformed_worker_backend'
      WHEN n.route_key IS NULL OR n.route_key = '' OR n.route_key ~ '\s' THEN 'malformed_route_key'
      WHEN c.id IS NULL THEN 'missing_capability'
      WHEN s.id IS NULL AND n.worker_backend = 'vibecomfy' THEN 'missing_selector_vibecomfy_no_claim'
      WHEN s.id IS NULL AND NOT COALESCE(c.supports_missing_selector AND c.enabled AND (c.expires_at IS NULL OR c.expires_at > n.decision_at), false) THEN 'missing_selector_capability_unsupported'
      WHEN s.id IS NULL THEN 'missing_selector_wgp_capability_supported'
      WHEN NOT s.enabled THEN 'selector_disabled'
      WHEN s.expires_at IS NOT NULL AND s.expires_at <= n.decision_at THEN 'selector_expired'
      WHEN s.selected_backend <> n.worker_backend THEN 'backend_mismatch'
      WHEN NOT COALESCE(c.enabled, false) THEN 'capability_disabled'
      WHEN c.expires_at IS NOT NULL AND c.expires_at <= n.decision_at THEN 'capability_expired'
      WHEN NOT COALESCE(c.supports_route, false) THEN 'capability_unsupported'
      ELSE 'eligible'
    END AS decision_reason,
    CASE
      WHEN s.id IS NULL THEN NULL
      ELSE jsonb_build_object(
        'selector_namespace', s.selector_namespace,
        'route_key', s.route_key,
        'selected_backend', s.selected_backend,
        'selector_version', s.selector_version,
        'enabled', s.enabled,
        'expires_at', s.expires_at,
        'min_worker_version', s.min_worker_version
      )
    END AS selector_snapshot,
    CASE
      WHEN c.id IS NULL THEN NULL
      ELSE jsonb_build_object(
        'backend', c.backend,
        'route_key', c.route_key,
        'supports_route', c.supports_route,
        'supports_missing_selector', c.supports_missing_selector,
        'capability_version', c.capability_version,
        'enabled', c.enabled,
        'expires_at', c.expires_at,
        'min_worker_version', c.min_worker_version
      )
    END AS capability_snapshot
  FROM normalized n
  LEFT JOIN selector_row s ON true
  LEFT JOIN capability_row c ON true;
$$;

REVOKE EXECUTE ON FUNCTION public.route_backend_claim_decision(text, text, text, timestamptz) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.route_backend_claim_decision(text, text, text, timestamptz) TO service_role;

INSERT INTO public.route_backend_capabilities (
  backend,
  route_key,
  supports_route,
  supports_missing_selector,
  capability_version,
  metadata
)
SELECT
  'wgp' AS backend,
  tt.name AS route_key,
  true AS supports_route,
  true AS supports_missing_selector,
  1 AS capability_version,
  jsonb_build_object(
    'seeded_by', '20260506110000_add_route_backend_selector_control_plane',
    'source', 'active_gpu_task_types',
    'task_type', tt.name
  ) AS metadata
FROM public.task_types tt
WHERE tt.is_active = true
  AND tt.run_type = 'gpu'
ON CONFLICT (backend, route_key) DO NOTHING;

COMMENT ON TABLE public.route_backend_selectors IS
  'Production backend selector allowlist keyed by selector namespace and canonical route key. Missing production rows are not an implicit VibeComfy fallback.';
COMMENT ON COLUMN public.route_backend_selectors.selector_namespace IS
  'Selector namespace, normally production. Allows bounded non-production selector maps without malformed namespace values.';
COMMENT ON COLUMN public.route_backend_selectors.route_key IS
  'Canonical route key produced by app/worker serializers. Direct routes use task type; dimensional routes include route dimensions.';
COMMENT ON COLUMN public.route_backend_selectors.selected_backend IS
  'Selected execution backend. Valid values are wgp and vibecomfy; comfy is intentionally not accepted as an alias.';
COMMENT ON COLUMN public.route_backend_selectors.selector_version IS
  'Monotonic selector version emitted in claim responses, task metadata, logs, and child route snapshots.';
COMMENT ON COLUMN public.route_backend_selectors.expires_at IS
  'Optional stale-entry guard. Expired selectors fail closed during claim decisions.';

COMMENT ON TABLE public.route_backend_capabilities IS
  'SQL-side backend capability registry used by claim/count decisions. Missing rows mean no-claim by construction.';
COMMENT ON COLUMN public.route_backend_capabilities.supports_missing_selector IS
  'Allows WGP to claim a route when the selector row is missing. A check constraint forbids this for vibecomfy.';
COMMENT ON CONSTRAINT route_backend_capabilities_missing_selector_wgp_only_check ON public.route_backend_capabilities IS
  'VibeComfy must never support missing selector fallback; production missing selectors cannot imply VibeComfy.';

COMMENT ON COLUMN public.tasks.selector_namespace IS
  'Create-time route selector namespace snapshot for observability and later child-row pinning.';
COMMENT ON COLUMN public.tasks.route_key IS
  'Create-time canonical route key snapshot. Claim authorization still uses live selector/capability data.';
COMMENT ON COLUMN public.tasks.selected_backend IS
  'Create-time selected backend snapshot for observability and child route pinning.';
COMMENT ON COLUMN public.tasks.selector_version IS
  'Create-time selector version snapshot. Claim-time selector version is persisted separately.';
COMMENT ON COLUMN public.tasks.route_selection_snapshot IS
  'Create-time route selection snapshot JSON, including support state needed by parent-created child rows.';
COMMENT ON COLUMN public.tasks.claimed_backend IS
  'Claim-time backend that actually claimed the task. Active accounting should use this persisted field.';
COMMENT ON COLUMN public.tasks.claimed_selector_namespace IS
  'Claim-time selector namespace used for the live decision.';
COMMENT ON COLUMN public.tasks.claimed_route_key IS
  'Claim-time canonical route key used for the live decision.';
COMMENT ON COLUMN public.tasks.claimed_selector_version IS
  'Claim-time selector version used for the live decision, visible in worker logs and task metadata.';
COMMENT ON COLUMN public.tasks.claimed_capability_version IS
  'Claim-time capability row version used for backend eligibility.';
COMMENT ON COLUMN public.tasks.claim_decision_reason IS
  'Claim-time reason such as eligible, missing_capability, backend_mismatch, selector_expired, or missing_selector_wgp_capability_supported.';
COMMENT ON COLUMN public.tasks.claim_decision_snapshot IS
  'Claim-time selector/capability snapshot for logs, debugging, rollback accounting, and fail-closed diagnostics.';

COMMENT ON FUNCTION public.route_backend_claim_decision(text, text, text, timestamptz) IS
  'Evaluates live selector plus backend capability eligibility. Missing capability rows return eligible=false. Missing selector rows can only be claimed by WGP when capability explicitly supports missing-selector fallback.';

COMMIT;
