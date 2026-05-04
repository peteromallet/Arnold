-- Extend claim_next_task_service_role to support worker pools (e.g. banodoco)
-- and an explicit task_types allow-list.
--
-- Background:
-- The banodoco worker pool sends:
--   { run_type: "banodoco-worker", worker_pool: "banodoco",
--     task_types: ["banodoco_timeline_generate", "banodoco_render_timeline"] }
-- The previous overload only knew about p_run_type ('gpu' | 'api') and would
-- never return banodoco_* tasks because get_task_run_type() doesn't classify
-- them. This migration adds two optional parameters:
--
--   p_worker_pool TEXT DEFAULT NULL
--     When 'banodoco', restricts the candidate set to tasks whose task_type
--     starts with 'banodoco_'. Other (or NULL) values preserve current
--     behavior, except that we also EXCLUDE banodoco_* tasks from non-banodoco
--     pools so they aren't accidentally claimed by gpu/api workers.
--
--   p_task_types TEXT[] DEFAULT NULL
--     When non-null and non-empty, restricts candidate tasks to those whose
--     task_type appears in the array. Layered on top of any pool / run_type
--     filter.
--
-- Existing 5-arg call sites (gpu/api workers) remain valid: when these new
-- parameters are NULL, the only behavioral change is that banodoco_* tasks
-- are no longer eligible for gpu/api workers (which is the correct desired
-- behavior since those workers can't execute them).

BEGIN;

-- Drop the prior 5-arg overload so we can replace it with the new 7-arg one.
DROP FUNCTION IF EXISTS public.claim_next_task_service_role(TEXT, BOOLEAN, TEXT, BOOLEAN, INT);

CREATE OR REPLACE FUNCTION claim_next_task_service_role(
  p_worker_id TEXT,
  p_include_active BOOLEAN DEFAULT FALSE,
  p_run_type TEXT DEFAULT NULL,
  p_same_model_only BOOLEAN DEFAULT FALSE,
  p_max_task_wait_minutes INT DEFAULT 5,
  p_worker_pool TEXT DEFAULT NULL,
  p_task_types TEXT[] DEFAULT NULL
)
RETURNS TABLE(
  task_id UUID,
  params JSONB,
  task_type TEXT,
  project_id UUID,
  user_id UUID
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
  v_status_filter task_status[];
  v_worker_model TEXT;
  v_has_starving_task BOOLEAN := FALSE;
  v_no_matching_tasks BOOLEAN := FALSE;
  v_effective_max_task_wait_minutes INT := COALESCE(p_max_task_wait_minutes, 5);
  v_is_banodoco_pool BOOLEAN := (p_worker_pool = 'banodoco');
  v_has_task_types_filter BOOLEAN := (p_task_types IS NOT NULL AND array_length(p_task_types, 1) > 0);
BEGIN
  -- Set status filter based on include_active flag
  IF p_include_active THEN
    v_status_filter := ARRAY['Queued'::task_status, 'In Progress'::task_status];
  ELSE
    v_status_filter := ARRAY['Queued'::task_status];
  END IF;

  -- Get worker's current model for affinity matching
  SELECT current_model INTO v_worker_model
  FROM workers
  WHERE id = p_worker_id AND status = 'active';

  -- Compute eligible users once and reuse for both starvation check and claim query
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

  -- Bypass model affinity when:
  -- 1. No matching-model tasks exist (nothing to wait for), OR
  -- 2. Any eligible task has waited longer than the max wait threshold (starvation protection)
  IF p_same_model_only AND v_worker_model IS NOT NULL THEN
    SELECT
      NOT bool_or(get_task_model(t.params) = v_worker_model),  -- no matching tasks
      bool_or(t.created_at < NOW() - (v_effective_max_task_wait_minutes || ' minutes')::interval)  -- any starving task
    INTO v_no_matching_tasks, v_has_starving_task
    FROM tasks t
    JOIN projects p ON t.project_id = p.id
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
        -- Banodoco pool: only banodoco_* task types
        (v_is_banodoco_pool AND t.task_type LIKE 'banodoco\_%' ESCAPE '\')
        OR
        -- Non-banodoco pool: exclude banodoco_* (they belong to dedicated workers)
        (NOT v_is_banodoco_pool AND t.task_type NOT LIKE 'banodoco\_%' ESCAPE '\')
      )
      AND (
        NOT v_has_task_types_filter
        OR t.task_type = ANY(p_task_types)
      );

    -- Coalesce NULLs (empty queue = no matching tasks, no starving tasks)
    v_no_matching_tasks := COALESCE(v_no_matching_tasks, TRUE);
    v_has_starving_task := COALESCE(v_has_starving_task, FALSE);
  END IF;

  -- Single atomic query to find and claim the next eligible task
  WITH ready_tasks AS (
    SELECT
      t.id,
      t.params,
      t.task_type,
      t.project_id,
      t.created_at,
      p.user_id,
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
        -- Banodoco pool: only banodoco_* task types
        (v_is_banodoco_pool AND t.task_type LIKE 'banodoco\_%' ESCAPE '\')
        OR
        -- Non-banodoco pool: exclude banodoco_* (dedicated workers handle these)
        (NOT v_is_banodoco_pool AND t.task_type NOT LIKE 'banodoco\_%' ESCAPE '\')
      )
      AND (
        NOT v_has_task_types_filter
        OR t.task_type = ANY(p_task_types)
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
      WHEN status = 'Queued'::task_status THEN 'In Progress'::task_status
      ELSE status
    END,
    worker_id = CASE
      WHEN status = 'Queued'::task_status THEN p_worker_id
      ELSE worker_id
    END,
    updated_at = CASE
      WHEN status = 'Queued'::task_status THEN NOW()
      ELSE updated_at
    END,
    generation_started_at = CASE
      WHEN status = 'Queued'::task_status THEN NOW()
      ELSE generation_started_at
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
    rt.user_id
  INTO v_task_id, v_params, v_task_type, v_project_id, v_user_id;

  IF v_task_id IS NOT NULL THEN
    task_id := v_task_id;
    params := v_params;
    task_type := v_task_type;
    project_id := v_project_id;
    user_id := v_user_id;
    RETURN NEXT;
  END IF;

  RETURN;
END;
$$;

COMMENT ON FUNCTION claim_next_task_service_role(TEXT, BOOLEAN, TEXT, BOOLEAN, INT, TEXT, TEXT[]) IS
'Claims next eligible task for service role. Supports worker pools via p_worker_pool (e.g. ''banodoco'' restricts to banodoco_* task_types; other values exclude banodoco_*) and task_type allow-list via p_task_types. Preserves prior behavior for gpu/api callers (which now also no longer accidentally pick up banodoco_* tasks).';

COMMIT;
