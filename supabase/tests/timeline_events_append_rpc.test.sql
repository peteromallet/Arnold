-- Verification for the timeline event-log append RPCs.
--
-- Run locally (safe -- everything is rolled back at the end):
--   psql "$SUPABASE_DB_URL" -f supabase/tests/timeline_events_append_rpc.test.sql
-- or against a linked project:
--   npx supabase db execute --linked --file supabase/tests/timeline_events_append_rpc.test.sql

BEGIN;

DO $$
DECLARE
  test_user_id uuid := gen_random_uuid();
  other_user_id uuid := gen_random_uuid();
  test_project_id uuid := gen_random_uuid();
  existing_timeline_id uuid := gen_random_uuid();
  created_timeline_id uuid := gen_random_uuid();
  result_config_version integer;
  result_event_ids text[];
  result_timeline_id uuid;
  stored_config jsonb;
  stored_asset_registry jsonb;
  stored_kind text;
  visible_count integer;
  owner_visible_count integer;
  other_visible_count integer;
BEGIN
  INSERT INTO auth.users (id, aud, role, email, created_at, updated_at)
  VALUES
    (test_user_id, 'authenticated', 'authenticated', 'timeline-events-test@example.invalid', now(), now()),
    (other_user_id, 'authenticated', 'authenticated', 'timeline-events-other@example.invalid', now(), now())
  ON CONFLICT (id) DO NOTHING;

  INSERT INTO public.users (id, name, email)
  VALUES
    (test_user_id, 'timeline-events-test', 'timeline-events-test@example.invalid'),
    (other_user_id, 'timeline-events-other', 'timeline-events-other@example.invalid')
  ON CONFLICT (id) DO NOTHING;

  INSERT INTO public.projects (id, name, user_id)
  VALUES (test_project_id, 'timeline-events-test-project', test_user_id);

  INSERT INTO public.timelines (id, project_id, user_id, name, config, asset_registry)
  VALUES (
    existing_timeline_id,
    test_project_id,
    test_user_id,
    'Existing timeline',
    '{"clips":[],"revision":"base"}'::jsonb,
    '{"assets":{"kept":{"url":"old"}}}'::jsonb
  );

  IF has_function_privilege(
    'authenticated',
    'public.append_timeline_event(uuid,jsonb,jsonb,integer,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: authenticated can execute append_timeline_event';
  END IF;

  IF has_function_privilege(
    'authenticated',
    'public.create_timeline_with_initial_event(jsonb,jsonb,jsonb,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: authenticated can execute create_timeline_with_initial_event';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.append_timeline_event(uuid,jsonb,jsonb,integer,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: service_role cannot execute append_timeline_event';
  END IF;

  IF has_function_privilege(
    'authenticated',
    'public.update_timeline_config_versioned(uuid,integer,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: authenticated can execute update_timeline_config_versioned';
  END IF;

  IF has_function_privilege(
    'authenticated',
    'public.update_timeline_versioned(uuid,integer,jsonb,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: authenticated can execute update_timeline_versioned';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.update_timeline_config_versioned(uuid,integer,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: service_role cannot execute update_timeline_config_versioned';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.update_timeline_versioned(uuid,integer,jsonb,jsonb)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'FAIL: service_role cannot execute update_timeline_versioned';
  END IF;

  IF has_table_privilege('authenticated', 'public.timeline_events', 'INSERT')
    OR has_table_privilege('authenticated', 'public.timeline_events', 'UPDATE')
    OR has_table_privilege('authenticated', 'public.timeline_events', 'DELETE') THEN
    RAISE EXCEPTION 'FAIL: authenticated has direct timeline_events write privileges';
  END IF;

  IF NOT has_table_privilege('authenticated', 'public.timeline_events', 'SELECT') THEN
    RAISE EXCEPTION 'FAIL: authenticated cannot read timeline_events';
  END IF;

  PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
  PERFORM set_config('request.jwt.claim.sub', test_user_id::text, true);

  SELECT count(*)
  INTO owner_visible_count
  FROM public.timelines
  WHERE id = existing_timeline_id;

  IF owner_visible_count <> 1 THEN
    RAISE EXCEPTION 'FAIL: owner cannot read own timeline through existing RLS';
  END IF;

  PERFORM set_config('request.jwt.claim.sub', other_user_id::text, true);

  SELECT count(*)
  INTO other_visible_count
  FROM public.timelines
  WHERE id = existing_timeline_id;

  IF other_visible_count <> 0 THEN
    RAISE EXCEPTION 'FAIL: non-owner can read timeline despite existing RLS';
  END IF;

  PERFORM set_config('request.jwt.claim.sub', test_user_id::text, true);

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAA',
          'timeline_id', existing_timeline_id::text,
          'version', 1,
          'prev_hash', null,
          'hash', repeat('a', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{"config":{"clips":[]}}'::jsonb,
          'schema_version', 2,
          'ts', '2026-06-12T00:00:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 1
        )
      ),
      '{"clips":[],"revision":"auth-rejected"}'::jsonb,
      1,
      null
    );
    RAISE EXCEPTION 'FAIL: non-service role append_timeline_event call succeeded';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;

  PERFORM set_config('request.jwt.claim.role', 'service_role', true);

  SELECT r.config_version, r.inserted_event_ids
  INTO result_config_version, result_event_ids
  FROM public.append_timeline_event(
    existing_timeline_id,
    jsonb_build_array(
      jsonb_build_object(
        'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAB',
        'timeline_id', existing_timeline_id::text,
        'version', 1,
        'prev_hash', null,
        'hash', repeat('b', 64),
        'kind', 'timeline.future_unknown',
        'payload', '{"opaque":true}'::jsonb,
        'schema_version', 1,
        'ts', '2026-06-12T00:01:00Z',
        'actor', '{"type":"system","id":"test"}'::jsonb,
        'expected_version', 1
      )
    ),
    '{"clips":[],"revision":"append-1"}'::jsonb,
    1,
    null
  ) AS r;

  IF result_config_version <> 2
    OR result_event_ids <> ARRAY['01ARZ3NDEKTSV4RRFFQ69G5FAB'] THEN
    RAISE EXCEPTION 'FAIL: first append returned %, %', result_config_version, result_event_ids;
  END IF;

  SELECT config, asset_registry INTO stored_config, stored_asset_registry
  FROM public.timelines
  WHERE id = existing_timeline_id;

  IF stored_config ->> 'revision' <> 'append-1' THEN
    RAISE EXCEPTION 'FAIL: append did not update projected config atomically';
  END IF;

  IF stored_asset_registry <> '{"assets":{"kept":{"url":"old"}}}'::jsonb THEN
    RAISE EXCEPTION 'FAIL: asset_registry changed without a registry event';
  END IF;

  SELECT kind INTO stored_kind
  FROM public.timeline_events
  WHERE timeline_id = existing_timeline_id
    AND version = 1;

  IF stored_kind <> 'timeline.future_unknown' THEN
    RAISE EXCEPTION 'FAIL: unknown event kind was not preserved';
  END IF;

  SELECT r.config_version
  INTO result_config_version
  FROM public.append_timeline_event(
    existing_timeline_id,
    jsonb_build_array(
      jsonb_build_object(
        'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAC',
        'timeline_id', existing_timeline_id::text,
        'version', 2,
        'prev_hash', repeat('b', 64),
        'hash', repeat('c', 64),
        'kind', 'timeline.config_replaced',
        'payload', '{"config":{"clips":[1]}}'::jsonb,
        'schema_version', 2,
        'ts', '2026-06-12T00:02:00Z',
        'actor', '{"type":"system","id":"test"}'::jsonb,
        'expected_version', 2
      )
    ),
    '{"clips":[1],"revision":"append-2"}'::jsonb,
    2,
    null
  ) AS r;

  IF result_config_version <> 3 THEN
    RAISE EXCEPTION 'FAIL: second append did not increment config_version once';
  END IF;

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAD',
          'timeline_id', existing_timeline_id::text,
          'version', 3,
          'prev_hash', null,
          'hash', repeat('d', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{}'::jsonb,
          'schema_version', 2,
          'ts', '2026-06-12T00:03:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 3
        )
      ),
      '{"revision":"null-prev-hash"}'::jsonb,
      3,
      null
    );
    RAISE EXCEPTION 'FAIL: null prev_hash append succeeded after first event';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAE',
          'timeline_id', existing_timeline_id::text,
          'version', 4,
          'prev_hash', repeat('c', 64),
          'hash', repeat('e', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{}'::jsonb,
          'schema_version', 2,
          'ts', '2026-06-12T00:04:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 3
        )
      ),
      '{"revision":"version-gap"}'::jsonb,
      3,
      null
    );
    RAISE EXCEPTION 'FAIL: non-contiguous event version append succeeded';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAF',
          'timeline_id', existing_timeline_id::text,
          'version', 3,
          'prev_hash', repeat('c', 64),
          'hash', repeat('f', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{}'::jsonb,
          'schema_version', 2,
          'ts', '2026-06-12T00:05:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 2
        )
      ),
      '{"revision":"cas-miss"}'::jsonb,
      2,
      null
    );
    RAISE EXCEPTION 'FAIL: CAS miss append succeeded';
  EXCEPTION WHEN serialization_failure THEN
    NULL;
  END;

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAG',
          'timeline_id', existing_timeline_id::text,
          'version', 3,
          'prev_hash', repeat('0', 64),
          'hash', repeat('1', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{}'::jsonb,
          'schema_version', 2,
          'ts', '2026-06-12T00:06:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 3
        )
      ),
      '{"revision":"bad-link"}'::jsonb,
      3,
      null
    );
    RAISE EXCEPTION 'FAIL: bad prev_hash append succeeded';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAH',
          'timeline_id', existing_timeline_id::text,
          'version', 3,
          'prev_hash', repeat('c', 64),
          'hash', repeat('2', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{}'::jsonb,
          'schema_version', 99,
          'ts', '2026-06-12T00:07:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 3
        )
      ),
      '{"revision":"future-schema"}'::jsonb,
      3,
      null
    );
    RAISE EXCEPTION 'FAIL: future schema_version append succeeded';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  BEGIN
    PERFORM public.append_timeline_event(
      existing_timeline_id,
      jsonb_build_array(
        jsonb_build_object(
          'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAJ',
          'timeline_id', existing_timeline_id::text,
          'version', 3,
          'prev_hash', repeat('c', 64),
          'hash', repeat('3', 64),
          'kind', 'timeline.config_replaced',
          'payload', '{}'::jsonb,
          'schema_version', 2,
          'ts', '2026-06-12T00:08:00Z',
          'actor', '{"type":"system","id":"test"}'::jsonb,
          'expected_version', 3
        )
      ),
      '{"revision":"registry-without-event"}'::jsonb,
      3,
      '{"assets":{"new":{"url":"blocked"}}}'::jsonb
    );
    RAISE EXCEPTION 'FAIL: asset_registry update without registry event succeeded';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  SELECT r.config_version
  INTO result_config_version
  FROM public.append_timeline_event(
    existing_timeline_id,
    jsonb_build_array(
      jsonb_build_object(
        'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAK',
        'timeline_id', existing_timeline_id::text,
        'version', 3,
        'prev_hash', repeat('c', 64),
        'hash', repeat('4', 64),
        'kind', 'timeline.asset_registry_replaced',
        'payload', '{"asset_registry":{"assets":{"new":{"url":"ok"}}}}'::jsonb,
        'schema_version', 2,
        'ts', '2026-06-12T00:09:00Z',
        'actor', '{"type":"system","id":"test"}'::jsonb,
        'expected_version', 3
      )
    ),
    '{"clips":[1],"revision":"registry"}'::jsonb,
    3,
    '{"assets":{"new":{"url":"ok"}}}'::jsonb
  ) AS r;

  IF result_config_version <> 4 THEN
    RAISE EXCEPTION 'FAIL: registry append did not increment config_version once';
  END IF;

  SELECT asset_registry INTO stored_asset_registry
  FROM public.timelines
  WHERE id = existing_timeline_id;

  IF stored_asset_registry <> '{"assets":{"new":{"url":"ok"}}}'::jsonb THEN
    RAISE EXCEPTION 'FAIL: registry event did not update asset_registry';
  END IF;

  SELECT r.config_version, r.inserted_event_ids
  INTO result_config_version, result_event_ids
  FROM public.append_timeline_event(
    existing_timeline_id,
    jsonb_build_array(
      jsonb_build_object(
        'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAM',
        'timeline_id', existing_timeline_id::text,
        'version', 4,
        'prev_hash', repeat('4', 64),
        'hash', repeat('5', 64),
        'kind', 'timeline.config_replaced',
        'payload', '{"config":{"clips":[1,2]}}'::jsonb,
        'schema_version', 1,
        'ts', '2026-06-12T00:10:00Z',
        'actor', '{"type":"system","id":"test"}'::jsonb,
        'expected_version', 4
      ),
      jsonb_build_object(
        'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAN',
        'timeline_id', existing_timeline_id::text,
        'version', 5,
        'prev_hash', repeat('5', 64),
        'hash', repeat('6', 64),
        'kind', 'timeline.future_unknown',
        'payload', '{"opaque":"batch"}'::jsonb,
        'schema_version', 2,
        'ts', '2026-06-12T00:11:00Z',
        'actor', '{"type":"system","id":"test"}'::jsonb,
        'expected_version', 4
      )
    ),
    '{"clips":[1,2],"revision":"batch-append"}'::jsonb,
    4,
    null
  ) AS r;

  IF result_config_version <> 5
    OR result_event_ids <> ARRAY['01ARZ3NDEKTSV4RRFFQ69G5FAM', '01ARZ3NDEKTSV4RRFFQ69G5FAN'] THEN
    RAISE EXCEPTION 'FAIL: batched append did not increment config_version exactly once';
  END IF;

  SELECT r.timeline_id, r.config_version, r.inserted_event_ids
  INTO result_timeline_id, result_config_version, result_event_ids
  FROM public.create_timeline_with_initial_event(
    jsonb_build_object(
      'id', created_timeline_id::text,
      'project_id', test_project_id::text,
      'user_id', test_user_id::text,
      'name', 'Created timeline'
    ),
    jsonb_build_object(
      'event_id', '01ARZ3NDEKTSV4RRFFQ69G5FAP',
      'timeline_id', created_timeline_id::text,
      'version', 1,
      'prev_hash', null,
      'hash', repeat('7', 64),
      'kind', 'timeline.config_replaced',
      'payload', '{"config":{"created":true}}'::jsonb,
      'schema_version', 2,
      'ts', '2026-06-12T00:12:00Z',
      'actor', '{"type":"system","id":"test"}'::jsonb,
      'expected_version', 0
    ),
    '{"created":true}'::jsonb,
    null
  ) AS r;

  IF result_timeline_id <> created_timeline_id
    OR result_config_version <> 1
    OR result_event_ids <> ARRAY['01ARZ3NDEKTSV4RRFFQ69G5FAP'] THEN
    RAISE EXCEPTION 'FAIL: create-with-initial-event returned unexpected result';
  END IF;

  SELECT count(*)
  INTO visible_count
  FROM public.timeline_events
  WHERE timeline_id = created_timeline_id
    AND version = 1;

  IF visible_count <> 1 THEN
    RAISE EXCEPTION 'FAIL: create-with-initial-event did not persist initial event';
  END IF;

  PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
  PERFORM set_config('request.jwt.claim.sub', test_user_id::text, true);

  SELECT count(*)
  INTO owner_visible_count
  FROM public.timeline_events
  WHERE timeline_id = existing_timeline_id;

  IF owner_visible_count <> 5 THEN
    RAISE EXCEPTION 'FAIL: owner cannot read own timeline events through RLS';
  END IF;

  SELECT count(*)
  INTO owner_visible_count
  FROM public.timelines
  WHERE id = created_timeline_id;

  IF owner_visible_count <> 1 THEN
    RAISE EXCEPTION 'FAIL: owner cannot read created timeline through existing RLS';
  END IF;

  PERFORM set_config('request.jwt.claim.sub', other_user_id::text, true);

  SELECT count(*)
  INTO other_visible_count
  FROM public.timeline_events
  WHERE timeline_id in (existing_timeline_id, created_timeline_id);

  IF other_visible_count <> 0 THEN
    RAISE EXCEPTION 'FAIL: non-owner can read timeline events despite RLS';
  END IF;

  SELECT count(*)
  INTO other_visible_count
  FROM public.timelines
  WHERE id in (existing_timeline_id, created_timeline_id);

  IF other_visible_count <> 0 THEN
    RAISE EXCEPTION 'FAIL: non-owner can read timelines despite existing RLS';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_class
    WHERE oid = 'public.timelines'::regclass
      AND relrowsecurity
  ) THEN
    RAISE EXCEPTION 'FAIL: timelines RLS is not enabled';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'timelines'
      AND policyname = 'Users can update own timelines'
      AND cmd = 'UPDATE'
  ) THEN
    RAISE EXCEPTION 'FAIL: existing timelines owner-update RLS policy missing';
  END IF;
END;
$$;

ROLLBACK;
