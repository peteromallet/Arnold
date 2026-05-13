-- Phase A Step 5 — Layer 1 trigger: reject unclaimable Queued rows at write time.
--
-- This trigger is intentionally STRICTER than the current claim semantics in
-- claim_next_task_service_role (which validates route_contract inline but does
-- not call route_backend_claim_decision). Any "queued but categorically
-- unclaimable" row that was previously valid-at-insert-but-stuck-at-claim now
-- becomes a write-time invariant violation with a clear, per-backend reason
-- chain. Reanimate paths that flip Failed/Complete rows back to Queued will
-- also surface RAISE here — that is intentional structural loudness.

CREATE OR REPLACE FUNCTION public.tasks_assert_claimable()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_namespace text;
  v_backend text;
  v_decision record;
  v_eligible boolean := false;
  v_reasons text[] := ARRAY[]::text[];
BEGIN
  IF NEW.params IS NULL
     OR NEW.params -> 'route_contract' IS NULL
     OR NEW.params -> 'route_contract' = 'null'::jsonb THEN
    RAISE EXCEPTION
      'route_contract validation failed: params.route_contract is required for claimable tasks (task_type=%, route_key=%)',
      NEW.task_type, NEW.route_key
      USING ERRCODE = 'check_violation';
  END IF;

  v_namespace := COALESCE(NEW.selector_namespace, 'production');

  IF NEW.selected_backend IS NOT NULL THEN
    SELECT * INTO v_decision
    FROM public.route_backend_claim_decision(
      v_namespace,
      NEW.route_key,
      NEW.selected_backend,
      now()
    )
    LIMIT 1;

    IF v_decision.eligible IS TRUE THEN
      v_eligible := true;
    ELSE
      v_reasons := array_append(
        v_reasons,
        format('%s: %s', NEW.selected_backend, COALESCE(v_decision.decision_reason, 'unknown'))
      );
    END IF;
  ELSE
    FOREACH v_backend IN ARRAY ARRAY['wgp', 'vibecomfy']
    LOOP
      SELECT * INTO v_decision
      FROM public.route_backend_claim_decision(
        v_namespace,
        NEW.route_key,
        v_backend,
        now()
      )
      LIMIT 1;

      IF v_decision.eligible IS TRUE THEN
        v_eligible := true;
        EXIT;
      END IF;

      v_reasons := array_append(
        v_reasons,
        format('%s: %s', v_backend, COALESCE(v_decision.decision_reason, 'unknown'))
      );
    END LOOP;
  END IF;

  IF NOT v_eligible THEN
    RAISE EXCEPTION
      'route_contract validation failed: no backend eligible for route_key=% in namespace=% (reasons: %)',
      NEW.route_key, v_namespace, array_to_string(v_reasons, '; ')
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS tasks_assert_claimable_trigger ON public.tasks;

CREATE TRIGGER tasks_assert_claimable_trigger
BEFORE INSERT OR UPDATE ON public.tasks
FOR EACH ROW
WHEN (NEW.status = 'Queued' AND NEW.task_type NOT LIKE '%_orchestrator')
EXECUTE FUNCTION public.tasks_assert_claimable();

COMMENT ON FUNCTION public.tasks_assert_claimable() IS
  'Layer 1 of contract enforcement (sprint fix/contract-enforcement-db). '
  'Rejects any Queued non-orchestrator INSERT/UPDATE whose params.route_contract '
  'is missing or whose (selector_namespace, route_key, backend) cannot be '
  'satisfied by route_backend_claim_decision against either wgp or vibecomfy. '
  'On rejection BOTH backends'' rejection reasons are included in the error '
  'message via array_to_string(v_reasons, ''; ''). This is stricter than the '
  'current claim RPC and will surface RAISE on reanimate paths — intentional.';

-- In-migration smoke asserts: (1) bad insert raises with both backend reasons,
-- (2) orchestrator-type Queued + NULL route_key succeeds (trigger does not
-- fire), (3) valid insert succeeds. Uses an existing project_id from
-- public.projects so the FK constraint is satisfied; rows are DELETEd after
-- assertion to avoid persisting test fixtures.
DO $smoke$
DECLARE
  v_project_id uuid;
  v_test_orch_id uuid := gen_random_uuid();
  v_test_valid_id uuid := gen_random_uuid();
  v_caught boolean := false;
  v_msg text;
BEGIN
  SELECT id INTO v_project_id FROM public.projects LIMIT 1;
  IF v_project_id IS NULL THEN
    RAISE NOTICE 'tasks_assert_claimable smoke: no projects row — skipping asserts (fresh DB).';
    RETURN;
  END IF;

  -- (1) Bad insert: route_contract present but route_key references nothing.
  -- Both backends should reject with their own reason; the RAISE must list
  -- both. selected_backend left NULL to force the FOREACH path.
  BEGIN
    INSERT INTO public.tasks (
      task_type, status, project_id, route_key, params
    ) VALUES (
      'image_edit',
      'Queued',
      v_project_id,
      'definitely_not_a_real_route_key_smoke_test',
      jsonb_build_object('route_contract', jsonb_build_object('route_key', 'definitely_not_a_real_route_key_smoke_test'))
    );
  EXCEPTION WHEN OTHERS THEN
    v_caught := true;
    v_msg := SQLERRM;
  END;

  IF NOT v_caught THEN
    RAISE EXCEPTION 'tasks_assert_claimable smoke (1): expected trigger to reject bogus route_key insert, but it succeeded';
  END IF;
  IF v_msg NOT LIKE '%wgp:%' OR v_msg NOT LIKE '%vibecomfy:%' THEN
    RAISE EXCEPTION
      'tasks_assert_claimable smoke (1): expected both ''wgp:'' and ''vibecomfy:'' prefixes in error, got: %',
      v_msg;
  END IF;

  -- (2) Orchestrator-type with NULL route_key — trigger WHEN clause must skip.
  INSERT INTO public.tasks (
    id, task_type, status, project_id, route_key, params
  ) VALUES (
    v_test_orch_id,
    'travel_orchestrator',
    'Queued',
    v_project_id,
    NULL,
    jsonb_build_object('smoke', 'orch_null_route_key')
  );
  DELETE FROM public.tasks WHERE id = v_test_orch_id;

  -- (3) Valid insert: image_edit + wgp + production is eligible per
  -- route_backend_claim_decision (verified via probe at migration-authoring
  -- time). Trigger fires and accepts.
  INSERT INTO public.tasks (
    id, task_type, status, project_id, route_key, selector_namespace,
    selected_backend, params
  ) VALUES (
    v_test_valid_id,
    'image_edit',
    'Queued',
    v_project_id,
    'image_edit',
    'production',
    'wgp',
    jsonb_build_object(
      'route_contract',
      jsonb_build_object(
        'route_key', 'image_edit',
        'selector_namespace', 'production',
        'selected_backend', 'wgp'
      )
    )
  );
  DELETE FROM public.tasks WHERE id = v_test_valid_id;

  RAISE NOTICE 'tasks_assert_claimable smoke: all three asserts passed.';
END;
$smoke$;

-- Reversibility
-- ------------
-- To roll this migration back manually:
--   DROP TRIGGER IF EXISTS tasks_assert_claimable_trigger ON public.tasks;
--   DROP FUNCTION IF EXISTS public.tasks_assert_claimable();
