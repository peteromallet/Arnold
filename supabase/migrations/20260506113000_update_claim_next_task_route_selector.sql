-- Sprint 6: enforce live selector/capability eligibility during service-role claims.

BEGIN;

DROP FUNCTION IF EXISTS public.claim_next_task_service_role(TEXT, BOOLEAN, TEXT, BOOLEAN, INT);

CREATE OR REPLACE FUNCTION public.claim_next_task_service_role(
  p_worker_id TEXT,
  p_include_active BOOLEAN DEFAULT FALSE,
  p_run_type TEXT DEFAULT NULL,
  p_same_model_only BOOLEAN DEFAULT FALSE,
  p_max_task_wait_minutes INT DEFAULT 5,
  p_worker_backend TEXT DEFAULT 'wgp',
  p_selector_namespace TEXT DEFAULT 'production'
)
RETURNS TABLE(
  task_id UUID,
  params JSONB,
  task_type TEXT,
  project_id UUID,
  user_id UUID,
  selector_namespace TEXT,
  route_key TEXT,
  selected_backend TEXT,
  selector_version BIGINT,
  route_selection_snapshot JSONB,
  task_selector_namespace TEXT,
  task_route_key TEXT,
  task_selected_backend TEXT,
  task_selector_version BIGINT,
  task_route_selection_snapshot JSONB,
  claimed_backend TEXT,
  claimed_selector_namespace TEXT,
  claimed_route_key TEXT,
  claimed_selector_version BIGINT,
  claimed_capability_version BIGINT,
  claim_decision_reason TEXT,
  claim_decision_snapshot JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_task_id UUID;
  v_params JSONB;
  v_task_type TEXT;
  v_project_id UUID;
  v_user_id UUID;
  v_selector_namespace TEXT;
  v_route_key TEXT;
  v_selected_backend TEXT;
  v_selector_version BIGINT;
  v_route_selection_snapshot JSONB;
  v_task_selector_namespace TEXT;
  v_task_route_key TEXT;
  v_task_selected_backend TEXT;
  v_task_selector_version BIGINT;
  v_task_route_selection_snapshot JSONB;
  v_claimed_backend TEXT;
  v_claimed_selector_namespace TEXT;
  v_claimed_route_key TEXT;
  v_claimed_selector_version BIGINT;
  v_claimed_capability_version BIGINT;
  v_claim_decision_reason TEXT;
  v_claim_decision_snapshot JSONB;
  v_status_filter task_status[];
  v_worker_model TEXT;
  v_has_starving_task BOOLEAN := FALSE;
  v_no_matching_tasks BOOLEAN := FALSE;
  v_effective_max_task_wait_minutes INT := COALESCE(p_max_task_wait_minutes, 5);
  v_effective_worker_backend TEXT := COALESCE(NULLIF(p_worker_backend, ''), 'wgp');
  v_effective_selector_namespace TEXT := COALESCE(NULLIF(p_selector_namespace, ''), 'production');
BEGIN
  IF v_effective_worker_backend NOT IN ('wgp', 'vibecomfy') THEN
    RETURN;
  END IF;

  IF v_effective_selector_namespace !~ '^[a-z][a-z0-9_-]{0,62}$' THEN
    RETURN;
  END IF;

  IF p_include_active THEN
    v_status_filter := ARRAY['Queued'::task_status, 'In Progress'::task_status];
  ELSE
    v_status_filter := ARRAY['Queued'::task_status];
  END IF;

  SELECT current_model INTO v_worker_model
  FROM workers
  WHERE id = p_worker_id AND status = 'active';

  CREATE TEMP TABLE _eligible_users ON COMMIT DROP AS
    SELECT
      u.id as user_id,
      u.credits,
      COALESCE((u.settings->'ui'->'generationMethods'->>'inCloud')::boolean, true) as allows_cloud,
      COUNT(in_progress_tasks.id) as in_progress_count
    FROM users u
    LEFT JOIN projects p ON p.user_id = u.id
    LEFT JOIN tasks in_progress_tasks ON in_progress_tasks.project_id = p.id
      AND in_progress_tasks.status = 'In Progress'::task_status
      AND COALESCE(in_progress_tasks.task_type, '') NOT ILIKE '%orchestrator%'
    WHERE u.credits > 0
      AND COALESCE((u.settings->'ui'->'generationMethods'->>'inCloud')::boolean, true) = true
    GROUP BY u.id, u.credits, u.settings
    HAVING COUNT(in_progress_tasks.id) < 5;

  IF p_same_model_only AND v_worker_model IS NOT NULL THEN
    SELECT
      NOT bool_or(get_task_model(t.params) = v_worker_model),
      bool_or(t.created_at < NOW() - (v_effective_max_task_wait_minutes || ' minutes')::interval)
    INTO v_no_matching_tasks, v_has_starving_task
    FROM tasks t
    JOIN projects p ON t.project_id = p.id
    JOIN LATERAL public.route_backend_claim_decision(
      v_effective_selector_namespace,
      t.route_key,
      v_effective_worker_backend,
      now()
    ) rd ON rd.eligible
    WHERE t.status = 'Queued'::task_status
      AND all_dependencies_complete(t.dependant_on)
      AND EXISTS (
        SELECT 1 FROM _eligible_users eu WHERE eu.user_id = p.user_id
      )
      AND (
        p_run_type IS NULL OR
        get_task_run_type(t.task_type) = p_run_type
      );

    v_no_matching_tasks := COALESCE(v_no_matching_tasks, TRUE);
    v_has_starving_task := COALESCE(v_has_starving_task, FALSE);
  END IF;

  WITH ready_tasks AS (
    SELECT
      t.id,
      t.params,
      t.task_type,
      t.project_id,
      t.created_at,
      t.selector_namespace,
      t.route_key,
      t.selected_backend,
      t.selector_version,
      t.route_selection_snapshot,
      p.user_id,
      rd.worker_backend AS decision_worker_backend,
      rd.selected_backend AS decision_selected_backend,
      rd.selector_namespace AS decision_selector_namespace,
      rd.route_key AS decision_route_key,
      rd.selector_version AS decision_selector_version,
      rd.capability_version AS decision_capability_version,
      rd.decision_reason,
      jsonb_build_object(
        'decision_reason', rd.decision_reason,
        'selector_namespace', rd.selector_namespace,
        'route_key', rd.route_key,
        'worker_backend', rd.worker_backend,
        'selected_backend', rd.selected_backend,
        'selector_version', rd.selector_version,
        'selector_present', rd.selector_present,
        'selector_enabled', rd.selector_enabled,
        'selector_expired', rd.selector_expired,
        'capability_present', rd.capability_present,
        'capability_version', rd.capability_version,
        'capability_supports_route', rd.capability_supports_route,
        'capability_supports_missing_selector', rd.capability_supports_missing_selector,
        'selector_snapshot', rd.selector_snapshot,
        'capability_snapshot', rd.capability_snapshot,
        'task_snapshot', jsonb_build_object(
          'selector_namespace', t.selector_namespace,
          'route_key', t.route_key,
          'selected_backend', t.selected_backend,
          'selector_version', t.selector_version,
          'route_selection_snapshot', t.route_selection_snapshot
        )
      ) AS decision_snapshot,
      ROW_NUMBER() OVER (
        ORDER BY
          CASE
            WHEN v_has_starving_task OR v_no_matching_tasks THEN NULL
            WHEN v_worker_model IS NOT NULL
                 AND get_task_model(t.params) = v_worker_model
            THEN 0
            ELSE 1
          END NULLS LAST,
          t.created_at ASC
      ) as rn
    FROM tasks t
    JOIN projects p ON t.project_id = p.id
    JOIN LATERAL public.route_backend_claim_decision(
      v_effective_selector_namespace,
      t.route_key,
      v_effective_worker_backend,
      now()
    ) rd ON rd.eligible
    WHERE t.status = 'Queued'::task_status
      AND all_dependencies_complete(t.dependant_on)
      AND EXISTS (
        SELECT 1 FROM _eligible_users eu WHERE eu.user_id = p.user_id
      )
      AND (
        p_run_type IS NULL OR
        get_task_run_type(t.task_type) = p_run_type
      )
      AND (
        v_has_starving_task
        OR v_no_matching_tasks
        OR NOT p_same_model_only
        OR v_worker_model IS NULL
        OR get_task_model(t.params) = v_worker_model
      )
  )
  UPDATE tasks
  SET
    status = CASE
      WHEN tasks.status = 'Queued'::task_status THEN 'In Progress'::task_status
      ELSE tasks.status
    END,
    worker_id = CASE
      WHEN tasks.status = 'Queued'::task_status THEN p_worker_id
      ELSE tasks.worker_id
    END,
    updated_at = CASE
      WHEN tasks.status = 'Queued'::task_status THEN NOW()
      ELSE tasks.updated_at
    END,
    generation_started_at = CASE
      WHEN tasks.status = 'Queued'::task_status THEN NOW()
      ELSE tasks.generation_started_at
    END,
    claimed_backend = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_worker_backend
      ELSE tasks.claimed_backend
    END,
    claimed_selector_namespace = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_selector_namespace
      ELSE tasks.claimed_selector_namespace
    END,
    claimed_route_key = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_route_key
      ELSE tasks.claimed_route_key
    END,
    claimed_selector_version = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_selector_version
      ELSE tasks.claimed_selector_version
    END,
    claimed_capability_version = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_capability_version
      ELSE tasks.claimed_capability_version
    END,
    claim_decision_reason = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_reason
      ELSE tasks.claim_decision_reason
    END,
    claim_decision_snapshot = CASE
      WHEN tasks.status = 'Queued'::task_status THEN rt.decision_snapshot
      ELSE tasks.claim_decision_snapshot
    END
  FROM ready_tasks rt
  WHERE tasks.id = rt.id
    AND rt.rn = 1
    AND (NOT p_include_active OR tasks.status = 'Queued'::task_status)
  RETURNING
    tasks.id,
    tasks.params,
    tasks.task_type,
    tasks.project_id,
    rt.user_id,
    tasks.claimed_selector_namespace,
    tasks.claimed_route_key,
    rt.decision_selected_backend,
    tasks.claimed_selector_version,
    tasks.claim_decision_snapshot,
    rt.selector_namespace,
    rt.route_key,
    rt.selected_backend,
    rt.selector_version,
    rt.route_selection_snapshot,
    tasks.claimed_backend,
    tasks.claimed_selector_namespace,
    tasks.claimed_route_key,
    tasks.claimed_selector_version,
    tasks.claimed_capability_version,
    tasks.claim_decision_reason,
    tasks.claim_decision_snapshot
  INTO
    v_task_id,
    v_params,
    v_task_type,
    v_project_id,
    v_user_id,
    v_selector_namespace,
    v_route_key,
    v_selected_backend,
    v_selector_version,
    v_route_selection_snapshot,
    v_task_selector_namespace,
    v_task_route_key,
    v_task_selected_backend,
    v_task_selector_version,
    v_task_route_selection_snapshot,
    v_claimed_backend,
    v_claimed_selector_namespace,
    v_claimed_route_key,
    v_claimed_selector_version,
    v_claimed_capability_version,
    v_claim_decision_reason,
    v_claim_decision_snapshot;

  IF v_task_id IS NOT NULL THEN
    task_id := v_task_id;
    params := v_params;
    task_type := v_task_type;
    project_id := v_project_id;
    user_id := v_user_id;
    selector_namespace := v_selector_namespace;
    route_key := v_route_key;
    selected_backend := v_selected_backend;
    selector_version := v_selector_version;
    route_selection_snapshot := v_route_selection_snapshot;
    task_selector_namespace := v_task_selector_namespace;
    task_route_key := v_task_route_key;
    task_selected_backend := v_task_selected_backend;
    task_selector_version := v_task_selector_version;
    task_route_selection_snapshot := v_task_route_selection_snapshot;
    claimed_backend := v_claimed_backend;
    claimed_selector_namespace := v_claimed_selector_namespace;
    claimed_route_key := v_claimed_route_key;
    claimed_selector_version := v_claimed_selector_version;
    claimed_capability_version := v_claimed_capability_version;
    claim_decision_reason := v_claim_decision_reason;
    claim_decision_snapshot := v_claim_decision_snapshot;
    RETURN NEXT;
  END IF;

  RETURN;
END;
$$;

COMMENT ON FUNCTION public.claim_next_task_service_role(TEXT, BOOLEAN, TEXT, BOOLEAN, INT, TEXT, TEXT) IS
'Claims next eligible task for service role using live route_backend_selectors plus route_backend_capabilities. Missing capability rows mean no-claim; missing selector rows can only be claimed by WGP when capability explicitly supports missing-selector fallback. Persists and returns claim-time selector/backend fields.';

COMMIT;
