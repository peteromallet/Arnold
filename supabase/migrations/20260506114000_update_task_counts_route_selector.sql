-- Sprint 6: align service-role task counts with live claim eligibility.

BEGIN;

DROP FUNCTION IF EXISTS public.count_eligible_tasks_service_role(BOOLEAN, TEXT);
DROP FUNCTION IF EXISTS public.count_queued_tasks_breakdown_service_role(TEXT);

CREATE OR REPLACE FUNCTION public.count_eligible_tasks_service_role(
  p_include_active BOOLEAN DEFAULT FALSE,
  p_run_type TEXT DEFAULT NULL,
  p_worker_backend TEXT DEFAULT 'wgp',
  p_selector_namespace TEXT DEFAULT 'production'
)
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
DECLARE
  v_total_capacity INTEGER := 0;
  v_effective_worker_backend TEXT := COALESCE(NULLIF(p_worker_backend, ''), 'wgp');
  v_effective_selector_namespace TEXT := COALESCE(NULLIF(p_selector_namespace, ''), 'production');
BEGIN
  IF v_effective_worker_backend NOT IN ('wgp', 'vibecomfy') THEN
    RETURN 0;
  END IF;

  IF v_effective_selector_namespace !~ '^[a-z][a-z0-9_-]{0,62}$' THEN
    RETURN 0;
  END IF;

  WITH per_user_capacity AS (
    SELECT
      u.id AS user_id,
      COUNT(CASE
        WHEN t.status = 'In Progress'::task_status
          AND COALESCE(t.task_type, '') NOT ILIKE '%orchestrator%'
        THEN 1
      END) AS in_progress_count,
      COUNT(CASE
        WHEN t.status = 'In Progress'::task_status
          AND COALESCE(t.task_type, '') NOT ILIKE '%orchestrator%'
          AND t.claimed_backend = v_effective_worker_backend
          AND t.claimed_selector_namespace = v_effective_selector_namespace
          AND (
            p_run_type IS NULL
            OR get_task_run_type(t.task_type) = p_run_type
          )
        THEN 1
      END) AS active_backend_count,
      COUNT(CASE
        WHEN t.status = 'Queued'::task_status
          AND all_dependencies_complete(t.dependant_on)
          AND (
            p_run_type IS NULL
            OR get_task_run_type(t.task_type) = p_run_type
          )
          AND EXISTS (
            SELECT 1
            FROM public.route_backend_claim_decision(
              v_effective_selector_namespace,
              t.route_key,
              v_effective_worker_backend,
              now()
            ) rd
            WHERE rd.eligible = true
          )
        THEN 1
      END) AS ready_queued_count
    FROM users u
    LEFT JOIN projects p ON p.user_id = u.id
    LEFT JOIN tasks t ON t.project_id = p.id
    WHERE u.credits > 0
      AND COALESCE((u.settings->'ui'->'generationMethods'->>'inCloud')::boolean, true) = true
    GROUP BY u.id, u.credits, u.settings
  )
  SELECT COALESCE(SUM(
    CASE
      WHEN p_include_active THEN
        active_backend_count + GREATEST(0, LEAST(5 - in_progress_count, ready_queued_count))
      ELSE
        GREATEST(0, LEAST(5 - in_progress_count, ready_queued_count))
    END
  ), 0) INTO v_total_capacity
  FROM per_user_capacity;

  RETURN v_total_capacity;
END;
$$;

CREATE OR REPLACE FUNCTION public.count_queued_tasks_breakdown_service_role(
  p_run_type TEXT DEFAULT NULL,
  p_worker_backend TEXT DEFAULT 'wgp',
  p_selector_namespace TEXT DEFAULT 'production'
)
RETURNS TABLE(
  claimable_now INTEGER,
  blocked_by_capacity INTEGER,
  blocked_by_deps INTEGER,
  blocked_by_settings INTEGER,
  total_queued INTEGER
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
DECLARE
  v_effective_worker_backend TEXT := COALESCE(NULLIF(p_worker_backend, ''), 'wgp');
  v_effective_selector_namespace TEXT := COALESCE(NULLIF(p_selector_namespace, ''), 'production');
BEGIN
  IF v_effective_worker_backend NOT IN ('wgp', 'vibecomfy')
     OR v_effective_selector_namespace !~ '^[a-z][a-z0-9_-]{0,62}$' THEN
    RETURN QUERY SELECT 0, 0, 0, 0, 0;
    RETURN;
  END IF;

  RETURN QUERY
  WITH user_capacity AS (
    SELECT
      u.id AS user_id,
      u.credits,
      COALESCE((u.settings->'ui'->'generationMethods'->>'inCloud')::boolean, true) AS allows_cloud,
      COUNT(t.id) FILTER (
        WHERE t.status = 'In Progress'::task_status
        AND COALESCE(t.task_type, '') NOT ILIKE '%orchestrator%'
      ) AS in_progress_count
    FROM users u
    LEFT JOIN projects p ON p.user_id = u.id
    LEFT JOIN tasks t ON t.project_id = p.id
    WHERE u.credits > 0
    GROUP BY u.id, u.credits, u.settings
  ),
  categorized_tasks AS (
    SELECT
      t.id AS task_id,
      uc.user_id,
      uc.credits,
      uc.allows_cloud,
      uc.in_progress_count,
      all_dependencies_complete(t.dependant_on) AS deps_complete,
      rd.eligible AS route_eligible,
      CASE
        WHEN uc.credits IS NULL OR uc.credits <= 0 THEN 'excluded'
        WHEN NOT uc.allows_cloud THEN 'blocked_by_settings'
        WHEN NOT all_dependencies_complete(t.dependant_on) THEN 'blocked_by_deps'
        WHEN uc.in_progress_count >= 5 THEN 'blocked_by_capacity'
        WHEN COALESCE(rd.eligible, false) = false THEN 'blocked_by_settings'
        ELSE 'claimable_now'
      END AS category
    FROM tasks t
    JOIN projects p ON t.project_id = p.id
    LEFT JOIN user_capacity uc ON uc.user_id = p.user_id
    LEFT JOIN LATERAL public.route_backend_claim_decision(
      v_effective_selector_namespace,
      t.route_key,
      v_effective_worker_backend,
      now()
    ) rd ON true
    WHERE t.status = 'Queued'::task_status
      AND COALESCE(t.task_type, '') NOT ILIKE '%orchestrator%'
      AND (
        p_run_type IS NULL
        OR get_task_run_type(t.task_type) = p_run_type
      )
  )
  SELECT
    COUNT(*) FILTER (WHERE category = 'claimable_now')::INTEGER AS claimable_now,
    COUNT(*) FILTER (WHERE category = 'blocked_by_capacity')::INTEGER AS blocked_by_capacity,
    COUNT(*) FILTER (WHERE category = 'blocked_by_deps')::INTEGER AS blocked_by_deps,
    COUNT(*) FILTER (WHERE category = 'blocked_by_settings')::INTEGER AS blocked_by_settings,
    COUNT(*) FILTER (WHERE category != 'excluded')::INTEGER AS total_queued
  FROM categorized_tasks;
END;
$$;

COMMENT ON FUNCTION public.count_eligible_tasks_service_role(BOOLEAN, TEXT, TEXT, TEXT) IS
'Counts service-role claimable workload for a backend and selector namespace. Queued tasks use live selector/capability eligibility; active tasks use persisted claimed_* fields.';

COMMENT ON FUNCTION public.count_queued_tasks_breakdown_service_role(TEXT, TEXT, TEXT) IS
'Breaks down queued tasks using the same live selector/capability eligibility as service-role claim for the requested backend and selector namespace.';

COMMIT;
